---
name: cross-provider-sanitizer
description: Handles and automatically resolves cross-provider encryption errors (such as invalid_encrypted_content, Encrypted content could not be decrypted, rs_resp_req_vrtx, or when the user switches between OpenAI official and Google Gemini / Claude models via CC Switch).
---

# Cross-Provider Session Sanitizer Skill

This skill ensures smooth switching between multiple AI model providers (e.g. OpenAI official models vs. Google Gemini/Claude through local proxy) in Codex Desktop.

## Background & Problem
When running models through the Gemini/Google proxy, responses may include internal reasoning tokens signed by Google (such as `rs_resp_req_vrtx_...` or `cpa-gemini-responses-carrier-v1`).
When switching back to OpenAI official models, OpenAI's API rejects these items with:
`The encrypted content for item ... could not be verified. Reason: Encrypted content could not be decrypted or parsed.`

## Actions & Workflow

1. **Detection**:
   If the user reports `invalid_encrypted_content`, `Encrypted content could not be decrypted or parsed`, or mentions switching models from Gemini to OpenAI (or vice versa):
   
2. **Execute Sanitization**:
   - Use the MCP tool `session-sanitizer` (`sanitize_cross_provider_history`) to immediately strip incompatible carrier blocks from both SQLite and rollout JSONL session files.
   - Alternatively, execute:
     `python "D:\Tools\CLIProxyAPI\sanitize_history.py"`

3. **User Guidance**:
   - Remind the user that after sanitizing on disk, restarting Codex Desktop (Quit and Reopen) will reload the clean session into memory.
   - If the user prefers not to restart Codex, advise them to click **New Chat** to start a clean thread immediately.
