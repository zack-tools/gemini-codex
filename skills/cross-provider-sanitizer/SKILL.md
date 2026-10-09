---
name: cross-provider-sanitizer
description: Handles and automatically resolves cross-provider encryption and compaction errors (such as invalid_encrypted_content, Encrypted content could not be decrypted, rs_resp_req_vrtx, Upstream returned no summary text for the compaction turn, invalid compaction capsule, or when switching between OpenAI official and Google Gemini / Claude models via CC Switch).
---

# Cross-Provider Session Sanitizer Skill

This skill ensures smooth switching between multiple AI model providers (e.g. OpenAI official models vs. Google Gemini/Claude through local proxy) in Codex Desktop.

## Background & Problem
1. **Carrier tokens**: When running models through the Gemini/Google proxy, responses may include internal reasoning tokens signed by Google (such as `rs_resp_req_vrtx_...` or `cpa-gemini-responses-carrier-v1`). When switching back to OpenAI official models, OpenAI's API rejects these items with:
   `The encrypted content for item ... could not be verified. Reason: Encrypted content could not be decrypted or parsed.`
2. **Compaction capsules**: When context compaction triggers in Codex Desktop under an OpenAI model or CC Switch, it saves compaction items with `encrypted_content` (e.g. `gAAAAAB...` Fernet tokens or `ccswitch-compaction-v1:...` base64 summaries). When switching to Gemini/Claude via `cli-proxy-api`, the local proxy does not recognize foreign compaction capsules and throws `HTTP 400: invalid compaction capsule: unrecognized compaction capsule format`, causing Codex Desktop to abort with:
   `stream disconnected before completion: Upstream returned no summary text for the compaction turn`.

## Actions & Workflow

1. **Detection**:
   If the user reports `invalid_encrypted_content`, `Encrypted content could not be decrypted or parsed`, `Upstream returned no summary text for the compaction turn`, or mentions switching models between OpenAI and Gemini/Claude:
   
2. **Execute Sanitization**:
   - Prefer using the MCP tool `session-sanitizer` (`sanitize_cross_provider_history`) to immediately strip incompatible carrier blocks from both SQLite and rollout JSONL session files.
   - Alternatively, execute the repository sanitize script relative to this project root:
     - On macOS / Linux:
       `python3 sanitize_history.py` or `./轉譯清理對話歷史.sh`
     - On Windows:
       `python sanitize_history.py` or `轉譯清理對話歷史.bat`

3. **User Guidance**:
   - Remind the user that after sanitizing on disk, restarting Codex Desktop (Quit and Reopen) will reload the clean session into memory.
   - If the user prefers not to restart Codex, advise them to click **New Chat** to start a clean thread immediately.

