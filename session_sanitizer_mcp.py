#!/usr/bin/env python
"""MCP server for safe cross-provider session sanitization."""

import json
import os
from pathlib import Path

from history_sanitizer import sanitize_json, sanitize_rollouts, sanitize_sqlite

try:
    from mcp.server.mcpserver import MCPServer
    app = MCPServer("session-sanitizer")
except ImportError:
    from mcp.server.fastmcp import FastMCP
    app = FastMCP("session-sanitizer")

CODEX_DIR = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))


@app.tool()
def sanitize_cross_provider_history() -> str:
    db_changed, db_carriers, backup_path = sanitize_sqlite(CODEX_DIR / "thread_history_1.sqlite")
    cleaned_sessions, _, session_carriers = sanitize_rollouts(CODEX_DIR / "sessions")
    backup_text = f", backup: {backup_path}" if backup_path else ""
    return (
        f"Sanitization complete: cleaned {cleaned_sessions} session files, "
        f"removed {session_carriers + db_carriers} carrier fields, "
        f"updated {db_changed} SQLite rows{backup_text}."
    )


@app.tool()
def check_history_status() -> str:
    found_count = 0
    sessions_dir = CODEX_DIR / "sessions"
    if sessions_dir.exists():
        for path in sessions_dir.rglob("rollout-*.jsonl"):
            try:
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        try:
                            _, changed = sanitize_json(json.loads(line))
                        except (json.JSONDecodeError, TypeError):
                            continue
                        if changed:
                            found_count += 1
                            break
            except OSError:
                continue
    if found_count:
        return f"Warning: found {found_count} session files with carrier fields. Run sanitize_cross_provider_history to fix."
    return "All session files are clean and compatible across providers."


if __name__ == "__main__":
    app.run()
