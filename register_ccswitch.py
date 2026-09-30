import sqlite3
import json
import time

db_path = r"C:\Users\Zack.ct.chen\.cc-switch\cc-switch.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

catalog_path = r"C:\Users\Zack.ct.chen\.codex\model_catalog.json".replace("\\", "\\\\")

settings_data = {
    "auth": {
        "OPENAI_API_KEY": "sk-gemini-local"
    },
    "config": f'model_catalog_json = "{catalog_path}"\nmodel_provider = "openai"\nopenai_base_url = "http://127.0.0.1:8317/v1"\nmodel = "gemini-3.8-flash-high"\n'
}

now = int(time.time() * 1000)

cursor.execute("SELECT id FROM providers WHERE id=? AND app_type=?", ("gemini-oauth", "codex"))
if cursor.fetchone():
    cursor.execute("""
        UPDATE providers 
        SET settings_config=?, name='Gemini-OAuth'
        WHERE id='gemini-oauth' AND app_type='codex'
    """, (json.dumps(settings_data),))
    print("Updated existing gemini-oauth provider in CC-Switch with model_catalog_json!")
else:
    cursor.execute("""
        INSERT INTO providers (
            id, app_type, name, settings_config, website_url, category, 
            created_at, sort_index, notes, icon, icon_color, meta, 
            is_current, in_failover_queue, cost_multiplier, limit_daily_usd, limit_monthly_usd, provider_type
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """, (
        "gemini-oauth", "codex", "Gemini-OAuth", json.dumps(settings_data),
        "http://127.0.0.1:8317", "custom", now, 10,
        "Google Gemini OAuth Local Proxy", "gemini", "#4285F4", "{}",
        0, 0, "1.0", None, None, "custom"
    ))
    print("Successfully added Gemini-OAuth provider to CC-Switch database!")

conn.commit()
conn.close()

