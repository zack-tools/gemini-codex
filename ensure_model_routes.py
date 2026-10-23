"""Keep Codex catalogs compatible with the existing CC Switch aggregate route."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import tempfile


def save(path, content):
    if path.exists() and path.read_bytes() == content:
        return False
    if path.exists():
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(path, path.with_name(path.name + ".bak-route-" + stamp))
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        f.write(content)
        temp = Path(f.name)
    os.replace(temp, path)
    return True


def repair(home, switch):
    live_path = switch / "live-state.json"
    if not live_path.exists():
        return {"status": "skipped", "reason": "CC Switch live state absent"}
    live = json.loads(live_path.read_text(encoding="utf-8"))
    codex = live.get("apps", {}).get("codex", {})
    if not codex.get("stack", {}).get("enabled"):
        return {"status": "skipped", "reason": "aggregate mode inactive"}
    catalog_path = home / "cc-switch-model-catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    models = catalog.get("models", [])
    if not models or not any(m.get("slug", "").startswith("ccs-gemini/") for m in models):
        raise ValueError("Aggregate catalog has no Gemini routes; regenerate it in CC Switch first")
    invalid = [m.get("slug", "") for m in models if m.get("slug", "").startswith(("gemini-", "claude-", "gpt-oss-"))]
    if invalid:
        raise ValueError("Aggregate catalog contains unqualified external models: " + repr(invalid))
    config_path = home / "config.toml"
    config = config_path.read_text(encoding="utf-8")
    # Only the top-level catalog/model values may change; preserve provider tables.
    parts = re.split(r"(?m)(?=^\[)", config, maxsplit=1)
    header = parts[0]
    pattern = r'(?m)^model_catalog_json\s*=.*$'
    line = 'model_catalog_json = "cc-switch-model-catalog.json"'
    header = re.sub(pattern, line, header) if re.search(pattern, header) else line + "\n" + header
    known = {m["slug"].split("/", 1)[1]: m["slug"] for m in models if m.get("slug", "").startswith("ccs-gemini/")}
    header = re.sub(r'(?m)^(model\s*=\s*")([^"\n]+)(".*)$', lambda m: m[1] + known.get(m[2], m[2]) + m[3], header)
    changed = []
    if save(config_path, (header + "".join(parts[1:])).encode("utf-8")):
        changed.append("config.toml")
    # Legacy readers must see the same qualified model IDs as the active catalog.
    if save(home / "model_catalog.json", catalog_path.read_bytes()):
        changed.append("model_catalog.json")
    return {"status": "ok", "models": len(models), "changed": changed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")))
    parser.add_argument("--switch-home", type=Path, default=Path.home() / ".cc-switch")
    args = parser.parse_args()
    print(json.dumps(repair(args.codex_home, args.switch_home)))
