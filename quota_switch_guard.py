#!/usr/bin/env python3
"""
Model Quota Guard & Switcher for Codex Desktop.

Features:
- Monitors active model quota (OpenAI Official, Gemini-OAuth, Claude via Proxy).
- Threshold alerts:
  - <= 10%: Warning alert.
  - <= 5%: Critical switch recommendation / auto-switch confirmation.
  - Dual-depleted alert when both OpenAI and Gemini-OAuth are depleted (<= 10% / <= 5%).
- Seamless switching between providers (OpenAI, Gemini, Claude):
  - Updates ~/.codex/config.toml (with automatic timestamped backup).
  - Syncs ~/.cc-switch database & settings when present.
  - Automatically runs sanitize_history.py when switching to OpenAI to prevent invalid_encrypted_content errors.
- Graceful restart of Codex Desktop (macOS & Windows).
"""

import argparse
import datetime
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPO_DIR = Path(__file__).resolve().parent
CODEX_DIR = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
CC_SWITCH_DIR = Path.home() / ".cc-switch"

# Thresholds
DEFAULT_WARN_THRESHOLD = 10.0
DEFAULT_SWITCH_THRESHOLD = 5.0

# Priority model defaults
DEFAULT_OPENAI_MODEL = "gpt-5.5"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash-high"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-6"


def load_check_quota_module():
    """Import check_quota module dynamically from repo."""
    sys.path.insert(0, str(REPO_DIR))
    try:
        import check_quota
        return check_quota
    except ImportError:
        pass
    scripts_dir = REPO_DIR / "scripts"
    if scripts_dir.exists():
        sys.path.insert(0, str(scripts_dir))
        try:
            import check_quota
            return check_quota
        except ImportError:
            pass
    return None


def read_current_codex_config() -> Dict[str, Any]:
    """Inspect ~/.codex/config.toml to detect current provider and model."""
    config_path = CODEX_DIR / "config.toml"
    result = {
        "provider": "openai",
        "model": "unknown",
        "model_provider_raw": None,
        "model_catalog_json": None,
        "config_exists": config_path.exists(),
    }
    if not config_path.exists():
        return result

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line_str = line.strip()
            if line_str.startswith("["):
                break  # Provider/model are root keys, not fields from nested tables.
            if line_str.startswith("#"):
                continue
            if "=" in line_str:
                k, _, v = line_str.partition("=")
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k == "model_provider":
                    result["model_provider_raw"] = v
                elif k == "model":
                    result["model"] = v
                elif k == "model_catalog_json":
                    result["model_catalog_json"] = v

        raw_provider = result["model_provider_raw"]
        model = result["model"]
        if raw_provider in ("custom", "cc-switch", "gemini-oauth"):
            if model.startswith("gemini"):
                result["provider"] = "gemini"
            elif model.startswith("claude"):
                result["provider"] = "claude"
            elif model.startswith("gpt") or model.startswith("o1") or model.startswith("o3") or model.startswith("o4") or "codex" in model.lower():
                result["provider"] = "openai"
            elif not result.get("model_catalog_json"):
                result["provider"] = "openai"
            else:
                result["provider"] = "gemini"
        elif raw_provider in ("openai", "openai_http", "default", None):
            result["provider"] = "openai"
        else:
            result["provider"] = "openai"
    except Exception as e:
        result["error"] = str(e)

    return result


def fetch_all_quotas() -> Dict[str, Any]:
    """Retrieve quotas for Antigravity (Gemini, Claude) and OpenAI."""
    check_quota = load_check_quota_module()
    if not check_quota:
        return {"error": "check_quota module not found"}

    quotas = {
        "gemini": None,
        "claude": None,
        "openai": None,
    }
    current = read_current_codex_config()

    def model_quota(rows, provider, fallback):
        model = current.get("model", "") if current.get("provider") == provider else fallback
        model = model.rsplit("/", 1)[-1]
        row = next((r for r in rows if r.get("modelId") == model), None)
        if row is None:
            return None
        return {"percent": row.get("percent"), "resetTimeLocal": row.get("resetTimeLocal"),
                "modelId": row.get("modelId")}

    # 1. Antigravity quotas
    try:
        anti = check_quota.collect_antigravity_quota()
        if anti:
            quotas["gemini"] = model_quota(anti.get("geminiModels") or [], "gemini", DEFAULT_GEMINI_MODEL)
            quotas["claude"] = model_quota(anti.get("claudeModels") or [], "claude", DEFAULT_CLAUDE_MODEL)
            if anti.get("error"):
                quotas["gemini_error"] = anti["error"]
    except Exception as e:
        quotas["gemini_error"] = str(e)

    # 2. OpenAI quotas
    try:
        oai = check_quota.collect_openai_quota()
        rl = next((limit for limit in (oai or {}).get("rateLimits", []) if limit.get("name") == "codex"), None)
        if oai and oai.get("error"):
            quotas["openai_error"] = oai["error"]
        if rl is not None:
            primary = rl.get("primary", {})
            secondary = rl.get("secondary", {})
            primary = primary or {}
            secondary = secondary or {}
            p_rem = primary.get("remainingPercent")
            s_rem = secondary.get("remainingPercent")
            known = [window for window in (primary, secondary) if isinstance(window.get("remainingPercent"), (int, float))]
            limiting = min(known, key=lambda w: w["remainingPercent"]) if known else {}
            effective_percent = limiting.get("remainingPercent")
            reset_time = limiting.get("resetTimeLocal")
            quotas["openai"] = {
                "percent": effective_percent,
                "primaryPercent": p_rem,
                "secondaryPercent": s_rem,
                "resetTimeLocal": reset_time,
                "planType": oai.get("planType"),
            }
    except Exception as e:
        quotas["openai_error"] = str(e)

    return quotas


def evaluate_status(
    config_info: Dict[str, Any],
    quotas: Dict[str, Any],
    warn_threshold: float = DEFAULT_WARN_THRESHOLD,
    switch_threshold: float = DEFAULT_SWITCH_THRESHOLD,
) -> Dict[str, Any]:
    """Evaluate whether current model needs warning or switching."""
    current_provider = config_info.get("provider", "openai")
    current_model = config_info.get("model", "unknown")

    gemini_q = quotas.get("gemini") or {}
    gemini_pct = gemini_q.get("percent")

    openai_q = quotas.get("openai") or {}
    openai_pct = openai_q.get("percent")

    claude_q = quotas.get("claude") or {}
    claude_pct = claude_q.get("percent")

    def above(value, threshold):
        return isinstance(value, (int, float)) and value > threshold

    def below(value, threshold):
        return isinstance(value, (int, float)) and value <= threshold

    if current_provider == "gemini":
        current_pct = gemini_pct
        current_reset = gemini_q.get("resetTimeLocal")
    elif current_provider == "claude":
        current_pct = claude_pct
        current_reset = claude_q.get("resetTimeLocal")
    else:
        current_pct = openai_pct
        current_reset = openai_q.get("resetTimeLocal")

    dual_depleted = below(openai_pct, warn_threshold) and below(gemini_pct, warn_threshold)
    dual_critical = below(openai_pct, switch_threshold) and below(gemini_pct, switch_threshold)

    # Next target provider according to user priority:
    # Target default is OpenAI. When OpenAI is depleted, fallback to Gemini.
    if current_provider == "openai":
        target_provider = "gemini"
        target_model = DEFAULT_GEMINI_MODEL
        target_pct = gemini_pct
    elif current_provider == "gemini":
        if above(openai_pct, warn_threshold):
            target_provider = "openai"
            target_model = DEFAULT_OPENAI_MODEL
            target_pct = openai_pct
        else:
            target_provider = "claude"
            target_model = DEFAULT_CLAUDE_MODEL
            target_pct = claude_pct
    else:  # claude
        if above(openai_pct, warn_threshold):
            target_provider = "openai"
            target_model = DEFAULT_OPENAI_MODEL
            target_pct = openai_pct
        elif above(gemini_pct, warn_threshold):
            target_provider = "gemini"
            target_model = DEFAULT_GEMINI_MODEL
            target_pct = gemini_pct
        else:
            target_provider = "claude"
            target_model = DEFAULT_CLAUDE_MODEL
            target_pct = claude_pct

    if not isinstance(current_pct, (int, float)):
        level = "UNKNOWN"
        message = "目前模型額度未知；不能判定耗盡，也不能據此自動切換。"
    elif current_pct <= switch_threshold:
        level = "CRITICAL_SWITCH"
        message = (
            f"當前模型 [{current_provider}:{current_model}] 額度僅剩 {current_pct:.1f}% "
            f"（<= {switch_threshold:.1f}% 臨界門檻），請先確認備援模型 [{target_provider}] 可用。"
        )
    elif current_pct <= warn_threshold:
        level = "WARNING"
        message = (
            f"【額度預警】當前模型 [{current_provider}:{current_model}] 額度剩餘 {current_pct:.1f}% "
            f"（<= {warn_threshold:.1f}% 預警門檻），預計重置時間為 {current_reset}。"
        )
    else:
        level = "OK"
        message = f"額度充足（剩餘 {current_pct:.1f}%），狀態正常。"

    if dual_critical:
        dual_message = f"【雙重耗盡警報】OpenAI ({openai_pct:.1f}%) 與 Gemini ({gemini_pct:.1f}%) 皆已見底；請核實 Claude 額度與模型可用性。"
    elif dual_depleted:
        dual_message = f"【雙重緊繃預警】OpenAI ({openai_pct:.1f}%) 與 Gemini ({gemini_pct:.1f}%) 均低於預警線！"
    else:
        dual_message = None

    return {
        "level": level,
        "message": message,
        "dual_depleted": dual_depleted,
        "dual_critical": dual_critical,
        "dual_message": dual_message,
        "current": {
            "provider": current_provider,
            "model": current_model,
            "percent": current_pct,
            "resetTimeLocal": current_reset,
        },
        "target": {
            "provider": target_provider,
            "model": target_model,
            "percent": target_pct,
            "quota_available": above(target_pct, switch_threshold),
        },
        "all_quotas": {
            "openai": openai_q,
            "gemini": gemini_q,
            "claude": claude_q,
        },
        "thresholds": {
            "warn": warn_threshold,
            "switch": switch_threshold,
        },
    }


def switch_provider(target: str, model_override: Optional[str] = None) -> bool:
    """
    Switch ~/.codex/config.toml and sync with ~/.cc-switch.
    Allowed targets: 'openai', 'gemini', 'claude'.
    """
    target = target.lower()
    if target not in ("openai", "gemini", "claude"):
        print(f"[-] 不支援的目標 provider: {target}，僅支援 openai / gemini / claude")
        return False

    config_path = CODEX_DIR / "config.toml"
    if not config_path.exists():
        print(f"[-] 找不到設定檔: {config_path}")
        return False

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = CODEX_DIR / f"config.toml.bak_{timestamp}"
    shutil.copyfile(config_path, backup_path)
    print(f"[+] 已建立設定檔備份: {backup_path.name}")

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    catalog_path = CODEX_DIR / "model_catalog.json"

    lines = content.split("\n")
    new_lines = []
    has_catalog_line = False
    has_provider_line = False
    has_model_line = False
    in_table = False

    target_model = model_override
    if not target_model:
        if target == "openai":
            target_model = DEFAULT_OPENAI_MODEL
        elif target == "gemini":
            target_model = DEFAULT_GEMINI_MODEL
        elif target == "claude":
            target_model = DEFAULT_CLAUDE_MODEL

    for line in lines:
        line_strip = line.strip()
        if line_strip.startswith("["):
            in_table = True
        if not in_table and line_strip.startswith("model_catalog_json"):
            if target == "openai":
                new_lines.append(f"# {line_strip}")
            else:
                new_lines.append(f'model_catalog_json = "{catalog_path}"')
            has_catalog_line = True
        elif not in_table and line_strip.startswith("model_provider"):
            if target == "openai":
                new_lines.append('model_provider = "openai_http"')
            else:
                new_lines.append('model_provider = "custom"')
            has_provider_line = True
        elif not in_table and (line_strip.startswith("model =") or line_strip.startswith("model=")):
            new_lines.append(f'model = "{target_model}"')
            has_model_line = True
        else:
            new_lines.append(line)

    header_additions = []
    if target != "openai" and not has_catalog_line:
        header_additions.append(f'model_catalog_json = "{catalog_path}"')
    if not has_provider_line:
        p_val = "openai_http" if target == "openai" else "custom"
        header_additions.append(f'model_provider = "{p_val}"')
    if not has_model_line:
        header_additions.append(f'model = "{target_model}"')

    if header_additions:
        new_lines = header_additions + new_lines

    with open(config_path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))
    print(f"[+] ~/.codex/config.toml 已更新為 {target.upper()} (model: {target_model})！")

    sync_cc_switch(target)

    if target in ("gemini", "claude"):
        try:
            build_script = REPO_DIR / "build_catalog.py"
            if build_script.exists():
                subprocess.run([sys.executable, str(build_script)], check=True)
                print("[+] 已自動同步並修復模型目錄 (model_catalog & cc-switch-model-catalog)！")
        except Exception as e:
            print(f"[-] 同步模型目錄失敗: {e}")

    sanitize_history_if_available()

    return True


def sync_cc_switch(target: str):
    """Sync ~/.cc-switch/cc-switch.db and settings.json."""
    db_path = CC_SWITCH_DIR / "cc-switch.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("UPDATE providers SET is_current=0 WHERE app_type='codex'")
            if target == "openai":
                c.execute("UPDATE providers SET is_current=1 WHERE id IN ('default', 'codex-official') AND app_type='codex'")
            else:
                c.execute("UPDATE providers SET is_current=1 WHERE id='gemini-oauth' AND app_type='codex'")
            conn.commit()
            conn.close()
            print("   [CC-Switch] 資料庫目前提供者狀態已同步。")
        except Exception as e:
            print(f"   [!] CC-Switch 資料庫同步略過: {e}")

    settings_path = CC_SWITCH_DIR / "settings.json"
    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
            settings["currentProviderCodex"] = "default" if target == "openai" else "gemini-oauth"
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            print("   [CC-Switch] settings.json 已更新。")
        except Exception as e:
            print(f"   [!] CC-Switch settings.json 更新略過: {e}")

    # 3. Update live-state.json (Crucial for CC Switch 路由 mode)
    live_state_path = CC_SWITCH_DIR / "live-state.json"
    if live_state_path.exists():
        try:
            with open(live_state_path, "r", encoding="utf-8") as f:
                live_state = json.load(f)
            codex_app = live_state.get("apps", {}).get("codex", {})
            if codex_app:
                route_id = "codex-official" if target == "openai" else "gemini-oauth"
                codex_app["proxy_route"] = route_id
                with open(live_state_path, "w", encoding="utf-8") as f:
                    json.dump(live_state, f, indent=2, ensure_ascii=False)
                print(f"   [CC-Switch] live-state.json proxy_route 已同步為 {route_id}。")
        except Exception as e:
            print(f"   [!] CC-Switch live-state.json 更新略過: {e}")


def sanitize_history_if_available():
    """Run sanitize_history.py to remove cross-provider carrier and compaction blocks."""
    san_script = REPO_DIR / "sanitize_history.py"
    if san_script.exists():
        print("[*] 正在執行對話歷史清理，防止跨 Provider 切換引發上下文壓縮或加密欄位報錯...")
        try:
            subprocess.run([sys.executable, str(san_script)], check=True,
                           env={**os.environ, "CODEX_HOME": str(CODEX_DIR)})
        except Exception as e:
            print(f"   [!] 清理腳本執行警示: {e}")


def restart_codex(delay_sec: int = 1):
    """Trigger a clean, detached restart of Codex Desktop / ChatGPT.app."""
    print("[*] 正在觸發 Codex / ChatGPT Desktop 重開...")
    if sys.platform == "darwin":
        cmd_parts = [
            f"sleep {delay_sec}",
            "osascript -e 'tell application \"ChatGPT\" to quit' 2>/dev/null || true",
            "sleep 2",
            "if pgrep -f '/Applications/ChatGPT.app/Contents/MacOS/ChatGPT' >/dev/null; then pkill -f '/Applications/ChatGPT.app/Contents/MacOS/ChatGPT' 2>/dev/null || true; fi",
            "sleep 1",
            "open -a '/Applications/ChatGPT.app'"
        ]
        cmd = " && ".join(cmd_parts)
        subprocess.Popen(["sh", "-c", cmd], start_new_session=True)
        print(f"[+] 重啟命令已派發（將在 {delay_sec} 秒後關閉 ChatGPT 並重開）。")
    elif sys.platform == "win32":
        ps_cmd = (
            f"Start-Sleep -Seconds {delay_sec}; "
            'Stop-Process -Name "ChatGPT" -Force -ErrorAction SilentlyContinue; '
            r'Start-Process "$env:LOCALAPPDATA\Programs\ChatGPT\ChatGPT.exe"'
        )
        subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_cmd], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        print("[+] Windows 重啟命令已派發。")
    else:
        print("[!] 非 macOS / Windows 平台，請手動重開 Codex 程式以套用新設定。")


def main():
    parser = argparse.ArgumentParser(description="Model Quota Guard & Switcher for Codex Desktop")
    parser.add_argument("--check", action="store_true", help="檢查當前模型額度與切換建議")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式輸出")
    parser.add_argument("--warn-threshold", type=float, default=DEFAULT_WARN_THRESHOLD, help="預警門檻 (預設 10.0%%)")
    parser.add_argument("--switch-threshold", type=float, default=DEFAULT_SWITCH_THRESHOLD, help="切換門檻 (預設 5.0%%)")
    parser.add_argument("--switch", type=str, choices=["openai", "gemini", "claude"], help="手動切換至指定 provider")
    parser.add_argument("--model", type=str, help="切換時指定特定 model 名稱")
    parser.add_argument("--restart", action="store_true", help="切換後自動重開 Codex")
    parser.add_argument("--auto-guard", action="store_true", help="若額度 <= switch-threshold 則自動執行切換並重開")

    args = parser.parse_args()

    config_info = read_current_codex_config()

    if args.switch:
        success = switch_provider(args.switch, model_override=args.model)
        if success and args.restart:
            restart_codex()
        return

    quotas = fetch_all_quotas()
    evaluation = evaluate_status(
        config_info=config_info,
        quotas=quotas,
        warn_threshold=args.warn_threshold,
        switch_threshold=args.switch_threshold,
    )

    if args.auto_guard:
        if evaluation["level"] == "CRITICAL_SWITCH" and evaluation["target"]["quota_available"]:
            target = evaluation["target"]["provider"]
            print(f"[!] 偵測到臨界額度！正在自動執行切換至 {target.upper()}...")
            switch_provider(target)
            if args.restart:
                restart_codex()
            return

    if args.json:
        print(json.dumps(evaluation, indent=2, ensure_ascii=False))
        return

    curr = evaluation["current"]
    tgt = evaluation["target"]
    all_q = evaluation["all_quotas"]

    def percent_text(value):
        return f"{value:.1f}%" if isinstance(value, (int, float)) else "未知"

    print("=" * 60)
    print("           Codex Model Quota Guard & Switcher")
    print("=" * 60)
    print(f"目前運行提供者 : {curr['provider'].upper()} (模型: {curr['model']})")
    print(f"目前剩餘額度   : {percent_text(curr['percent'])}")
    print(f"下次重置時間   : {curr['resetTimeLocal'] or '未知'}")
    print("-" * 60)
    print(f"OpenAI 官方額度: {percent_text(all_q['openai'].get('percent'))} (重置: {all_q['openai'].get('resetTimeLocal', '無')})")
    print(f"Gemini-OAuth   : {percent_text(all_q['gemini'].get('percent'))} (重置: {all_q['gemini'].get('resetTimeLocal', '無')})")
    print(f"Claude (Proxy) : {percent_text(all_q['claude'].get('percent'))} (重置: {all_q['claude'].get('resetTimeLocal', '無')})")
    print("-" * 60)
    print(f"狀態等級       : [{evaluation['level']}]")
    print(f"狀態訊息       : {evaluation['message']}")
    if evaluation.get("dual_message"):
        print(f"警報提醒       : {evaluation['dual_message']}")
    print("-" * 60)
    if evaluation["level"] == "CRITICAL_SWITCH":
        print(f"建議動作       : 先確認 {tgt['provider'].upper()} 可用 ({percent_text(tgt['percent'])} 剩餘)")
        print(f"指令參考       : python3 quota_switch_guard.py --switch {tgt['provider']} --restart")
    elif evaluation["level"] == "WARNING":
        print(f"建議動作       : 額度即將不足，建議準備備援或暫停超長任務")
    elif evaluation["level"] == "OK":
        print(f"建議動作       : 額度充裕，正常工作")
    else:
        print("建議動作       : 額度未知，先檢查查詢來源")
    print("=" * 60)


if __name__ == "__main__":
    main()
