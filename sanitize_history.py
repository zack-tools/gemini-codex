import sqlite3
import json
import shutil
from pathlib import Path

codex_dir = Path.home() / ".codex"

print("1. 正在清理 SQLite 資料庫 (thread_history_1.sqlite)...")
db_path = codex_dir / "thread_history_1.sqlite"
if db_path.exists():
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("DELETE FROM thread_items WHERE item_type='reasoning' AND (item_id LIKE '%vrtx%' OR item_json LIKE '%cpa-gemini%' OR item_json LIKE '%vrtx%')")
        c.execute("UPDATE thread_turns SET error_json=NULL WHERE error_json LIKE '%invalid_encrypted_content%'")
        conn.commit()
        conn.close()
        print("   [OK] SQLite 資料庫清理完畢。")
    except Exception as e:
        print(f"   [!] SQLite 清理略過: {e}")

print("2. 正在清理 Session Rollout 歷史檔案 (*.jsonl)...")
sessions_dir = codex_dir / "sessions"
cleaned_files = 0
total_items_removed = 0

if sessions_dir.exists():
    for jsonl_file in sessions_dir.rglob("rollout-*.jsonl"):
        try:
            with open(jsonl_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            modified = False
            new_lines = []
            for line in lines:
                if "cpa-gemini" in line or "rs_resp_req_vrtx" in line:
                    modified = True
                    total_items_removed += 1
                    continue
                new_lines.append(line)
            
            if modified:
                with open(jsonl_file, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                cleaned_files += 1
        except Exception as e:
            pass

print(f"   [OK] 共掃描並轉義修復了 {cleaned_files} 個 Session 檔案，移除了 {total_items_removed} 筆加密思考項。")
print("\n轉義清理完成！")
