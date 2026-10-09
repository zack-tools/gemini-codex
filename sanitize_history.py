import os
from pathlib import Path

from history_sanitizer import sanitize_rollouts, sanitize_sqlite

codex_dir = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))

print("1. 正在清理 SQLite 資料庫 (thread_history_1.sqlite)...")
try:
    changed, carriers, backup_path = sanitize_sqlite(codex_dir / "thread_history_1.sqlite")
    if backup_path:
        print(f"   [OK] 更新 {changed} 筆資料，移除 {carriers} 個載體欄位。備份: {backup_path}")
    else:
        print("   [--] SQLite 資料庫不存在。")
except Exception as exc:
    raise SystemExit(f"   [!] SQLite 清理失敗，未提交變更: {exc}")

print("2. 正在清理 Session Rollout 歷史檔案 (*.jsonl)...")
cleaned_files, changed_lines, removed_items = sanitize_rollouts(codex_dir / "sessions")
print(f"   [OK] 更新 {cleaned_files} 個 Session 檔案、{changed_lines} 行，移除 {removed_items} 個載體欄位。")
print("\n轉譯清理完成！")
