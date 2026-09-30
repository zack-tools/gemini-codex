#!/usr/bin/env python
"""
MCP Server for Codex: Cross-Provider Session Sanitizer
Automatically strips conflicting provider-specific encrypted reasoning blocks
(e.g., cpa-gemini-responses-carrier / rs_resp_req_vrtx) so conversations can transition
seamlessly between OpenAI and Gemini/Claude without 400 errors.
"""

import sys
import sqlite3
import json
from pathlib import Path

try:
    from mcp.server.mcpserver import MCPServer
    app = MCPServer("session-sanitizer")
except ImportError:
    from mcp.server.fastmcp import FastMCP
    app = FastMCP("session-sanitizer")

CODEX_DIR = Path.home() / ".codex"

@app.tool()
def sanitize_cross_provider_history() -> str:
    """
    Scan and sanitize Codex session rollout files (*.jsonl) and SQLite database,
    removing incompatible cross-provider encrypted reasoning carrier items
    (such as cpa-gemini-responses-carrier or rs_resp_req_vrtx) so old conversations
    can be continued across different AI providers (e.g. switching between Gemini and OpenAI).
    """
    cleaned_sessions = 0
    removed_items = 0
    
    # 1. Clean SQLite
    db_path = CODEX_DIR / "thread_history_1.sqlite"
    sqlite_status = "not found"
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("DELETE FROM thread_items WHERE item_type='reasoning' AND (item_id LIKE '%vrtx%' OR item_json LIKE '%cpa-gemini%' OR item_json LIKE '%vrtx%')")
            c.execute("UPDATE thread_turns SET error_json=NULL WHERE error_json LIKE '%invalid_encrypted_content%'")
            conn.commit()
            conn.close()
            sqlite_status = "success"
        except Exception as e:
            sqlite_status = f"error: {e}"

    # 2. Clean Session Rollouts
    sessions_dir = CODEX_DIR / "sessions"
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
                        removed_items += 1
                        continue
                    new_lines.append(line)
                
                if modified:
                    with open(jsonl_file, "w", encoding="utf-8") as f:
                        f.writelines(new_lines)
                    cleaned_sessions += 1
            except Exception:
                pass
                
    return (
        f"Sanitization complete: Cleaned {cleaned_sessions} session files on disk, "
        f"removed {removed_items} conflicting encrypted reasoning blocks. SQLite status: {sqlite_status}."
    )

@app.tool()
def check_history_status() -> str:
    """
    Check if there are any conflicting cross-provider encrypted items in recent Codex sessions.
    """
    found_count = 0
    sessions_dir = CODEX_DIR / "sessions"
    if sessions_dir.exists():
        for jsonl_file in sessions_dir.rglob("rollout-*.jsonl"):
            try:
                with open(jsonl_file, "r", encoding="utf-8") as f:
                    content = f.read()
                if "cpa-gemini" in content or "rs_resp_req_vrtx" in content:
                    found_count += 1
            except Exception:
                pass
                
    if found_count > 0:
        return f"Warning: Found {found_count} session files containing cross-provider encrypted reasoning blocks. Run sanitize_cross_provider_history to fix."
    return "All session files are clean and compatible across providers."

if __name__ == "__main__":
    app.run()
