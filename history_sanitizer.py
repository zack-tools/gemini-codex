"""Safe removal and conversion of provider-specific encrypted carrier fields and compaction capsules."""

from __future__ import annotations

import base64
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

MARKER_PREFIXES = ("cpa-gemini-responses-carrier-v1:", "rs_resp_req_vrtx_")
CARRIER_KEYS = {"encrypted_content", "thought_signature", "thinking_signature"}
KNOWN_COMPACTION_PREFIXES = ("cpa-ag-compact-v1:", "cli-proxy-api:lcp-compaction-session:v1")


def is_heavy_image(value: dict[str, Any]) -> bool:
    if value.get("type") == "input_image":
        url = value.get("image_url", "")
        if isinstance(url, str) and url.startswith("data:image/") and len(url) > 1024:
            return True
    return False


def is_carrier(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return value.startswith(MARKER_PREFIXES) or value.startswith("gAAAAAB")


def sanitize_compaction_item(value: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """
    Safely convert cross-provider compaction items.
    If it's ccswitch-compaction-v1, restore the base64 Markdown summary as assistant text.
    If it's gAAAAAB or any foreign capsule unreadable by CLIProxyAPI / Gemini / Claude,
    convert it to an assistant summary message so the upstream proxy will not reject it with 400 Bad Request.
    """
    enc = value.get("encrypted_content")
    item_id = value.get("id", "cmp_sanitized")
    passthrough = value.get("internal_chat_message_metadata_passthrough", {})

    if isinstance(enc, str):
        if enc.startswith("ccswitch-compaction-v1:"):
            raw = enc[len("ccswitch-compaction-v1:"):]
            try:
                text = base64.b64decode(raw + "==").decode("utf-8", errors="replace")
            except Exception:
                text = "*(Context checkpoint handoff)*"
            return {
                "type": "message",
                "id": item_id,
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
                "internal_chat_message_metadata_passthrough": passthrough,
            }, True
        elif enc.startswith("gAAAAAB") or not enc.startswith(KNOWN_COMPACTION_PREFIXES):
            return {
                "type": "message",
                "id": item_id,
                "role": "assistant",
                "content": [{
                    "type": "output_text",
                    "text": "*(Prior conversation context compacted by upstream model)*",
                }],
                "internal_chat_message_metadata_passthrough": passthrough,
            }, True

    return value, False


def sanitize_json(value: Any) -> tuple[Any, bool]:
    if isinstance(value, dict):
        if is_heavy_image(value):
            return {
                "type": "input_text",
                "text": "[Historical image attachment omitted to prevent token/quota exhaustion]"
            }, True

        if value.get("type") == "compaction":
            converted, changed = sanitize_compaction_item(value)
            if changed:
                return converted, True

        result = {}
        changed = False
        for key, child in value.items():
            if key in CARRIER_KEYS and is_carrier(child):
                changed = True
                continue
            cleaned, child_changed = sanitize_json(child)
            result[key] = cleaned
            changed |= child_changed
        return result, changed
    if isinstance(value, list):
        result = []
        changed = False
        for child in value:
            cleaned, child_changed = sanitize_json(child)
            result.append(cleaned)
            changed |= child_changed
        return result, changed
    return value, False


def atomic_write(path: Path, content: str) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def backup(path: Path) -> Path:
    target = path.with_name(f"{path.name}.bak-sanitize")
    shutil.copy2(path, target)
    return target


def backup_sqlite(connection: sqlite3.Connection, path: Path) -> Path:
    target = path.with_name(f"{path.name}.bak-sanitize")
    if target.exists():
        target.unlink()
    target_connection = sqlite3.connect(target)
    try:
        connection.backup(target_connection)
    finally:
        target_connection.close()
    return target


def sanitize_rollouts(sessions_dir: Path) -> tuple[int, int, int]:
    files = changed_lines = removed_carriers = 0
    if not sessions_dir.exists():
        return files, changed_lines, removed_carriers
    for path in sessions_dir.rglob("rollout-*.jsonl"):
        output = []
        changed = False
        file_carriers = 0
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    output.append(line)
                    continue
                cleaned, record_changed = sanitize_json(record)
                if record_changed:
                    changed = True
                    changed_lines += 1
                    file_carriers += 1
                    line = json.dumps(cleaned, ensure_ascii=False, separators=(",", ":")) + "\n"
                output.append(line)
        if changed:
            backup(path)
            atomic_write(path, "".join(output))
            files += 1
            removed_carriers += file_carriers
    return files, changed_lines, removed_carriers


def sanitize_sqlite(db_path: Path) -> tuple[int, int, Path | None]:
    if not db_path.exists():
        return 0, 0, None
    changed = carriers = 0
    connection = sqlite3.connect(db_path)
    try:
        backup_path = backup_sqlite(connection, db_path)
        connection.execute("BEGIN IMMEDIATE")
        for table in ("thread_items", "thread_realtime_items"):
            columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            if "item_json" not in columns:
                continue
            rows = connection.execute(f"SELECT rowid, item_json FROM {table}").fetchall()
            for rowid, raw in rows:
                try:
                    parsed = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    continue
                cleaned, row_changed = sanitize_json(parsed)
                if row_changed:
                    connection.execute(
                        f"UPDATE {table} SET item_json=? WHERE rowid=?",
                        (json.dumps(cleaned, ensure_ascii=False, separators=(",", ":")), rowid)
                    )
                    changed += 1
                    carriers += 1
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return changed, carriers, backup_path
