#!/usr/bin/env python3
"""Export full Codex conversation history from SQLite / rollouts to readable Markdown."""

from __future__ import annotations

import argparse
import datetime
import json
import sqlite3
import sys
from pathlib import Path


def get_default_db() -> Path:
    return Path.home() / ".codex" / "thread_history_1.sqlite"


def list_recent_threads(db_path: Path, limit: int = 10) -> None:
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}", file=sys.stderr)
        return
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        """
        SELECT thread_id, count(*) as turn_count, max(started_at) as last_time
        FROM thread_turns
        GROUP BY thread_id
        ORDER BY last_time DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = c.fetchall()
    print(f"{'Thread ID':<38} {'Turns':<8} {'Last Updated'}")
    print("-" * 68)
    for tid, count, last_time in rows:
        time_str = (
            datetime.datetime.fromtimestamp(last_time).strftime("%Y-%m-%d %H:%M:%S")
            if last_time
            else "Unknown"
        )
        print(f"{tid:<38} {count:<8} {time_str}")


def export_thread(db_path: Path, thread_id: str, output_path: Path | None = None) -> Path:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        """
        SELECT item_id, turn_id, item_type, created_at_ms, item_json 
        FROM thread_items 
        WHERE thread_id=? 
        ORDER BY created_at_ms ASC
        """,
        (thread_id,),
    )
    rows = c.fetchall()
    if not rows:
        raise ValueError(f"No items found for thread ID: {thread_id}")

    if output_path is None:
        output_path = Path.cwd() / f"thread_{thread_id}.md"

    lines = [
        f"# Codex Thread History: {thread_id}\n",
        f"> Exported at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        "---\n",
    ]

    current_turn = None
    turn_num = 1

    for item_id, turn_id, itype, created_at_ms, raw in rows:
        if turn_id != current_turn:
            current_turn = turn_id
            dt = datetime.datetime.fromtimestamp(created_at_ms / 1000.0).strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"\n## Turn {turn_num} ({dt})\n")
            turn_num += 1

        data = json.loads(raw)
        t_time = datetime.datetime.fromtimestamp(created_at_ms / 1000.0).strftime("%H:%M:%S")

        if itype == "userMessage":
            content = data.get("content", [])
            txt = ""
            for part in content:
                if isinstance(part, dict) and "text" in part:
                    txt += part["text"]
            lines.append(f"### 👤 User ({t_time})\n\n{txt.strip()}\n")

        elif itype == "agentMessage":
            txt = data.get("text", "")
            lines.append(f"### 🤖 Assistant ({t_time})\n\n{txt.strip()}\n")

        elif itype == "contextCompaction":
            lines.append(f"\n> ⚠️ *[Context Compaction Boundary: Earlier history folded by Codex]*\n")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Codex thread history to Markdown")
    parser.add_argument("thread_id", nargs="?", help="Thread UUID to export")
    parser.add_argument("-l", "--list", action="store_true", help="List recent threads")
    parser.add_argument("-o", "--output", type=Path, help="Output markdown file path")
    parser.add_argument("--db", type=Path, default=get_default_db(), help="Path to thread_history_1.sqlite")

    args = parser.parse_args()

    if args.list or not args.thread_id:
        list_recent_threads(args.db)
        if not args.thread_id:
            print("\nUsage: export_thread_history.py <thread_id> [-o output.md]")
            return

    try:
        out = export_thread(args.db, args.thread_id, args.output)
        print(f"Successfully exported thread {args.thread_id} to: {out}")
    except Exception as e:
        print(f"Export failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
