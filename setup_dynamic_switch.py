import sqlite3
import json
import shutil
import os

catalog_path = r"C:\Users\Zack.ct.chen\.codex\model_catalog.json"
catalog_bak = r"C:\Users\Zack.ct.chen\.codex\model_catalog.json.bak"
cache_path = r"C:\Users\Zack.ct.chen\.codex\models_cache.json"
cache_bak = r"C:\Users\Zack.ct.chen\.codex\models_cache.json.bak_openai"

# 1. Ensure model_catalog.json exists
if os.path.exists(catalog_bak):
    shutil.copyfile(catalog_bak, catalog_path)
    print("Restored model_catalog.json")

# 2. Ensure models_cache.json is clean official OpenAI
if os.path.exists(cache_bak):
    shutil.copyfile(cache_bak, cache_path)
    print("Cleaned models_cache.json to official OpenAI")

# 3. Update CC-Switch sqlite database
db_path = r"C:\Users\Zack.ct.chen\.cc-switch\cc-switch.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT settings_config FROM providers WHERE id='gemini-oauth'")
row = cursor.fetchone()
if row:
    data = json.loads(row[0])
    escaped_catalog = catalog_path.replace("\\", "\\\\")
    catalog_line = f'model_catalog_json = "{escaped_catalog}"\n'
    
    # Strip any existing model_catalog_json lines
    lines = [line for line in data["config"].split("\n") if not line.startswith("model_catalog_json")]
    new_config = catalog_line + "\n".join(lines)
    data["config"] = new_config
    
    cursor.execute("UPDATE providers SET settings_config=? WHERE id='gemini-oauth'", (json.dumps(data),))
    conn.commit()
    print("Successfully linked model_catalog_json to gemini-oauth in CC-Switch!")

conn.close()

