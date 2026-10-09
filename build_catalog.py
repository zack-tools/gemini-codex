import subprocess
import json
import copy

import os
import shutil
from pathlib import Path

codex_bin = shutil.which("codex")
if not codex_bin:
    potential_paths = [
        "/opt/homebrew/bin/codex",
        "/usr/local/bin/codex",
        r"D:/OpenAI.Codex_26.908.4834.0_x64__2p2nqsd0c76g0/app/resources/codex.exe",
    ]
    for p in potential_paths:
        if os.path.exists(p):
            codex_bin = p
            break

if not codex_bin:
    raise FileNotFoundError("Could not find 'codex' executable. Please make sure codex is in PATH.")

output = subprocess.check_output([codex_bin, "debug", "models", "--bundled"])
data = json.loads(output)
template = data["models"][0]

standard_reasoning_levels = [
    {
        "effort": "low",
        "description": "低思考強度：快速回應，適合日常簡短問答"
    },
    {
        "effort": "medium",
        "description": "中思考強度：平衡速度與推理深度，適合大多數任務"
    },
    {
        "effort": "high",
        "description": "高思考強度：深入推理，適合複雜問題與編程"
    }
]

models_info = [
    ("gemini-3.8-flash-high", "Gemini 3.8 Flash", "Google Gemini 3.8 Flash", "Google Gemini 3.8 Flash", "medium", standard_reasoning_levels),
    ("gemini-3.7-flash-high", "Gemini 3.7 Flash", "Google Gemini 3.7 Flash", "Google Gemini 3.7 Flash", "medium", standard_reasoning_levels),
    ("gemini-3.6-flash-high", "Gemini 3.6 Flash", "Google Gemini 3.6 Flash", "Google Gemini 3.6 Flash", "medium", standard_reasoning_levels),
    ("gemini-3.1-pro-high", "Gemini 3.1 Pro", "Google Gemini 3.1 Pro", "Google Gemini 3.1 Pro", "high", standard_reasoning_levels),
    ("claude-sonnet-4-6", "Claude Sonnet 4.6 (Thinking)", "Anthropic Claude Sonnet 4.6 via Google OAuth", "Anthropic Claude Sonnet 4.6", "high", standard_reasoning_levels),
    ("claude-opus-4-6-thinking", "Claude Opus 4.6 (Thinking)", "Anthropic Claude Opus 4.6 via Google OAuth", "Anthropic Claude Opus 4.6", "high", standard_reasoning_levels),
    ("gpt-oss-120b-medium", "OSS 120B", "GPT-OSS 120B via Google OAuth", "GPT-OSS 120B", None, []),
]

new_models = []
for i, (slug, display_name, desc, brand, def_level, r_levels) in enumerate(models_info):
    m = copy.deepcopy(template)
    m["slug"] = slug
    m["display_name"] = display_name
    m["description"] = desc
    m["visibility"] = "list"
    m["priority"] = i
    m["default_reasoning_level"] = def_level
    m["supported_reasoning_levels"] = r_levels
    
    for text_field in ["base_instructions"]:
        if text_field in m and m[text_field]:
            m[text_field] = m[text_field].replace("an agent based on GPT-6", f"an agent powered by {brand}")
            m[text_field] = m[text_field].replace("a coding agent based on GPT-5", f"an agent powered by {brand}")
            m[text_field] = m[text_field].replace("GPT-6", brand).replace("GPT-5", brand)
    if "model_messages" in m and isinstance(m["model_messages"], dict):
        if "instructions_template" in m["model_messages"] and m["model_messages"]["instructions_template"]:
            it = m["model_messages"]["instructions_template"]
            it = it.replace("an agent based on GPT-6", f"an agent powered by {brand}")
            it = it.replace("a coding agent based on GPT-5", f"an agent powered by {brand}")
            it = it.replace("GPT-6", brand).replace("GPT-5", brand)
            m["model_messages"]["instructions_template"] = it
            
    new_models.append(m)

data["models"] = new_models

codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
codex_home.mkdir(parents=True, exist_ok=True)
catalog_path = codex_home / "model_catalog.json"
with open(catalog_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"SUCCESS: {catalog_path} updated with clean models and functional sliders!")

# Also sync cc-switch-model-catalog.json if present
cc_cat_path = codex_home / "cc-switch-model-catalog.json"
if cc_cat_path.exists():
    try:
        with open(cc_cat_path, "r", encoding="utf-8") as f:
            cc_data = json.load(f)
        official_map = {mod["slug"]: mod for mod in new_models}
        cc_updated = 0
        for cc_m in cc_data.get("models", []):
            cc_slug = cc_m.get("slug", "")
            if cc_slug.startswith("ccs-gemini/"):
                base_slug = cc_slug.split("/", 1)[1]
                target_m = official_map.get(base_slug)
                if not target_m:
                    if "gemini-3.1-pro" in base_slug: target_m = official_map.get("gemini-3.1-pro-high")
                    elif "claude-sonnet" in base_slug: target_m = official_map.get("claude-sonnet-4-6")
                    elif "claude-opus" in base_slug: target_m = official_map.get("claude-opus-4-6-thinking")
                    elif "gpt-oss" in base_slug: target_m = official_map.get("gpt-oss-120b-medium")
                if target_m and "model_messages" in target_m:
                    cc_m["model_messages"] = copy.deepcopy(target_m["model_messages"])
                    if "base_instructions" in target_m:
                        cc_m["base_instructions"] = target_m["base_instructions"]
                    cc_updated += 1
        with open(cc_cat_path, "w", encoding="utf-8") as f:
            json.dump(cc_data, f, ensure_ascii=False, indent=2)
        print(f"SUCCESS: Also synced {cc_updated} ccs-gemini models in {cc_cat_path}!")
    except Exception as e:
        print(f"Warning syncing cc-switch catalog: {e}")


