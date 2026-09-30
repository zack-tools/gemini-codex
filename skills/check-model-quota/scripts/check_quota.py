import os
import sys
import glob
import json
import urllib.request
import urllib.parse
import urllib.error
import argparse
import math
from pathlib import Path
from datetime import datetime
try:
    import zoneinfo
    TAIPEI_TZ = zoneinfo.ZoneInfo("Asia/Taipei")
except Exception:
    from datetime import timezone, timedelta
    TAIPEI_TZ = timezone(timedelta(hours=8))

CLIENT_ID = os.environ.get("ANTIGRAVITY_OAUTH_CLIENT_ID")
CLIENT_SECRET = os.environ.get("ANTIGRAVITY_OAUTH_CLIENT_SECRET")

def get_auth_file():
    user_home = os.path.expanduser("~")
    cpa_dir = os.path.join(user_home, ".cli-proxy-api")
    files = glob.glob(os.path.join(cpa_dir, "antigravity-*.json"))
    if files:
        return files[0]
    return None

def refresh_token(auth_path, refresh_token_val):
    if not CLIENT_ID or not CLIENT_SECRET:
        return None
    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token_val,
        "grant_type": "refresh_token"
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            new_at = res.get("access_token")
            if new_at and auth_path:
                try:
                    with open(auth_path, "r", encoding="utf-8") as f:
                        cur = json.load(f)
                    cur["access_token"] = new_at
                    with open(auth_path, "w", encoding="utf-8") as f:
                        json.dump(cur, f, indent=2)
                except Exception:
                    pass
            return new_at
    except Exception as e:
        return None

def fetch_models(access_token):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "antigravity/1.0.0"
    }
    req = urllib.request.Request(
        "https://cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels",
        headers=headers,
        data=b"{}"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        models = json.loads(resp.read().decode("utf-8"))
    # This endpoint explicitly returns zero when fetchAvailableModels omits it.
    quota_req = urllib.request.Request(
        "https://cloudcode-pa.googleapis.com/v1internal:retrieveUserQuota",
        headers=headers, data=b"{}"
    )
    try:
        with urllib.request.urlopen(quota_req, timeout=10) as resp:
            quota = json.load(resp)
        buckets = {}
        for bucket in quota.get("buckets", []):
            fraction = bucket.get("remainingFraction")
            model_id = bucket.get("modelId")
            if model_id and isinstance(fraction, (int, float)) and not isinstance(fraction, bool) and 0 <= fraction <= 1:
                if model_id not in buckets or fraction < buckets[model_id]["remainingFraction"]:
                    buckets[model_id] = bucket
        for model_id, bucket in buckets.items():
            info = models.setdefault("models", {}).setdefault(model_id, {})
            info.setdefault("quotaInfo", {}).update({
                "remainingFraction": bucket["remainingFraction"],
                **({"resetTime": bucket["resetTime"]} if bucket.get("resetTime") else {})
            })
    except (urllib.error.URLError, OSError, ValueError, TypeError, AttributeError):
        # Preserve model-list values; absent fractions remain unknown.
        pass
    return models

def format_iso_time(iso_str):
    if not iso_str:
        return "N/A"
    try:
        dt_utc = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt_utc.astimezone(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_str

def collect_antigravity_quota():
    auth_file = get_auth_file()
    if not auth_file or not os.path.exists(auth_file):
        err = {"error": "未找到 Antigravity 憑證檔 (~/.cli-proxy-api/antigravity-*.json)"}
        return err

    with open(auth_file, "r", encoding="utf-8") as f:
        auth_data = json.load(f)

    token = auth_data.get("access_token")
    rf = auth_data.get("refresh_token")
    email = auth_data.get("email", "未知")

    data = None
    try:
        data = fetch_models(token)
    except urllib.error.HTTPError as e:
        if e.code == 401 and rf:
            token = refresh_token(auth_file, rf)
            if token:
                data = fetch_models(token)
            else:
                err = {"error": "Token 已過期且刷新失敗，請重新登入"}
                return err
        else:
            raise e
    except Exception:
        return {"error": "Antigravity 查詢失敗，請檢查網路或重新登入"}

    now_loc = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S")
    models = data.get("models", {})

    gemini_quota = None
    gemini_models = []
    claude_models = []
    claude_reset = None

    for m_id, m_info in models.items():
        q = m_info.get("quotaInfo")
        if not q:
            continue
        rem = q.get("remainingFraction")
        rst = q.get("resetTime")
        if m_id.lower().startswith("gemini-"):
            gemini_models.append({
                "modelId": m_id,
                "remainingFraction": rem,
                "percent": round(rem * 100, 1) if rem is not None else None,
                "resetTime": rst,
                "resetTimeLocal": format_iso_time(rst)
            })
        if "claude" in m_id.lower() or "opus" in m_id.lower() or "sonnet" in m_id.lower():
            claude_models.append({"modelId": m_id, "remainingFraction": rem,
                                  "percent": round(rem * 100, 1) if rem is not None else None,
                                  "resetTime": rst, "resetTimeLocal": format_iso_time(rst)})
            if rst and not claude_reset:
                claude_reset = format_iso_time(rst)

    if gemini_models:
        # Missing fractions are unknown, not 100% (or an assumed zero).
        gemini_quota = min(gemini_models, key=lambda item: (
            item["remainingFraction"] is not None,
            item["remainingFraction"] if item["remainingFraction"] is not None else 0
        ))

    result = {
        "account": email,
        "queryTime": now_loc,
        "gemini": gemini_quota,
        "geminiModels": gemini_models,
        "claudeModels": claude_models,
        "claudeResetTime": claude_reset
    }

    return result


def print_quota_section(vendor, product, account, source, rows, error=None):
    print("=" * 64)
    print(f"【{vendor} / {product}】")
    print(f"  帳號: {account or '未知'}")
    print(f"  額度來源: {source}")
    if error:
        print(f"  查詢狀態: {error}")
    elif not rows:
        print("  剩餘額度: 未取得資料")
        print("  重置時間: 未取得資料")
    for label, percent, reset in rows:
        remaining = f"{percent:g}%" if percent is not None else "未知（API 未回傳比例）"
        print(f"  {label}")
        print(f"    剩餘額度: {remaining}")
        print(f"    重置時間: {reset or '未知'}")
    print()


def antigravity_rows(models):
    # Group only models with identical quota and reset values.
    groups = {}
    for model in sorted(models, key=lambda item: item['modelId']):
        key = (model['percent'], model['resetTimeLocal'])
        groups.setdefault(key, []).append(model['modelId'])
    return [("所有已回傳模型" if len(groups) == 1 else ", ".join(ids), percent, reset)
            for (percent, reset), ids in groups.items()]


def print_antigravity(result):
    for vendor, product, field in (("Google", "Gemini", "geminiModels"),
                                    ("Anthropic", "Claude", "claudeModels")):
        print_quota_section(vendor, product, result.get('account'), 'Antigravity',
                            antigravity_rows(result.get(field, [])), result.get('error'))


def openai_auth_path(explicit=None):
    if explicit:
        return Path(explicit).expanduser()
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"


def normalize_window(window):
    if not isinstance(window, dict):
        return None
    used = window.get("used_percent")
    remaining = None
    if isinstance(used, (int, float)) and not isinstance(used, bool) and math.isfinite(used):
        remaining = round(max(0, min(100, 100 - used)), 1)
    reset = window.get("reset_at")
    reset_local = None
    if isinstance(reset, (int, float)):
        try:
            reset_local = datetime.fromtimestamp(reset, TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OverflowError, OSError):
            pass
    return {"usedPercent": used, "remainingPercent": remaining,
            "windowDurationSeconds": window.get("limit_window_seconds"),
            "resetsAt": reset, "resetTimeLocal": reset_local}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def collect_openai_quota(auth_path=None):
    path = openai_auth_path(auth_path)
    try:
        auth = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {"error": "未找到 OpenAI OAuth 憑證，請執行 codex login 或用 --openai-auth 指定憑證檔"}
    except (OSError, ValueError):
        return {"error": "OpenAI OAuth 憑證檔無法讀取或 JSON 格式錯誤"}
    if not isinstance(auth, dict):
        return {"error": "OpenAI OAuth 憑證格式錯誤"}
    tokens = auth.get("tokens") or auth
    if not isinstance(tokens, dict) or not isinstance(tokens.get("access_token"), str) or not tokens["access_token"]:
        return {"error": "憑證缺少 OAuth access_token；API key 無法查詢 ChatGPT 訂閱額度，請執行 codex login"}
    headers = {"Authorization": "Bearer " + tokens["access_token"],
               "Accept": "application/json", "User-Agent": "codex-cli"}
    account_id = tokens.get("account_id") or auth.get("account_id")
    if account_id:
        headers["ChatGPT-Account-Id"] = str(account_id)
    request = urllib.request.Request("https://chatgpt.com/backend-api/wham/usage", headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
            data = json.load(response)
        if not isinstance(data, dict):
            return {"error": "OpenAI 額度回應格式錯誤"}
        limits = []
        groups = [("codex", data.get("rate_limit")), ("code_review", data.get("code_review_rate_limit"))]
        for extra in data.get("additional_rate_limits") or []:
            groups.append((extra.get("limit_name") or extra.get("metered_feature") or "additional", extra.get("rate_limit")))
        for name, limit in groups:
            if not isinstance(limit, dict):
                continue
            limits.append({"name": name, "allowed": limit.get("allowed"),
                           "limitReached": limit.get("limit_reached"),
                           "primary": normalize_window(limit.get("primary_window")),
                           "secondary": normalize_window(limit.get("secondary_window"))})
        return {"account": data.get("email") or auth.get("email"),
                "planType": data.get("plan_type"), "rateLimits": limits}
    except urllib.error.HTTPError as exc:
        message = "OAuth 已失效，請執行 codex login 重新登入" if exc.code == 401 else "請確認帳號權限與網路連線"
        return {"error": f"OpenAI 查詢失敗 (HTTP {exc.code})：{message}"}
    except Exception:
        # Never include response bodies, credential contents, or request headers.
        return {"error": "OpenAI 查詢失敗，請檢查網路連線或服務回應格式"}


def print_openai(result):
    rows = []
    for limit in result.get("rateLimits", []):
        for key in ("primary", "secondary"):
            window = limit[key]
            if window is None:
                continue
            seconds = window['windowDurationSeconds']
            duration = {18000: '5 小時', 604800: '每週'}.get(seconds, f'{seconds} 秒' if seconds else key)
            label = duration if limit['name'] == 'codex' else f"{limit['name']} / {duration}"
            rows.append((label, window['remainingPercent'], window['resetTimeLocal']))
    plan = result.get('planType')
    source = f"ChatGPT 訂閱（{plan}）" if plan else "ChatGPT 訂閱"
    print_quota_section("OpenAI", "Codex", result.get('account'), source, rows, result.get('error'))


def check_quota(as_json=False, provider="all", openai_auth=None):
    result = {}
    statuses = []
    if not as_json:
        print(f"查詢時間: {datetime.now(TAIPEI_TZ):%Y-%m-%d %H:%M:%S}（台北時間，以下重置時間皆同）")
    if provider in ("all", "antigravity"):
        try:
            antigravity = collect_antigravity_quota()
        except Exception:
            antigravity = {"error": "Antigravity 查詢失敗，請檢查憑證或網路連線"}
        result.update(antigravity)  # Preserve existing JSON fields.
        statuses.append("error" not in antigravity)
        if not as_json:
            print_antigravity(antigravity)
    if provider in ("all", "openai"):
        result["openai"] = collect_openai_quota(openai_auth)
        statuses.append("error" not in result["openai"])
        if not as_json:
            print_openai(result["openai"])
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(statuses) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="查詢 Antigravity 與 OpenAI / Codex 訂閱額度")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--provider", choices=("all", "antigravity", "openai"), default="all")
    parser.add_argument("--openai-auth", help="OpenAI OAuth JSON 路徑；預設 CODEX_HOME/auth.json 或 ~/.codex/auth.json")
    args = parser.parse_args()
    sys.exit(check_quota(args.json, args.provider, args.openai_auth))
