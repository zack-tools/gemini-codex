---
name: model-quota-guard
description: Monitor active Codex model quota, trigger 10% warning alerts and 5% critical switch confirmations, seamlessly switch between OpenAI official, Gemini-OAuth, and Claude, and restart Codex safely.
metadata:
  short-description: Monitor model quota and auto-switch on depletion
---

# Model Quota Guard & Switcher

This skill monitors model quotas in real-time, alerts on quota depletion thresholds, and handles provider failovers.

## Policy & Priority Chain

1. **Default Primary**: OpenAI Official (`gpt-5.5` or subscription defaults).
2. **Fallback Provider**: Gemini-OAuth (`gemini-3.8-flash-high` via local proxy).
3. **Emergency Backup**: Claude (`claude-sonnet-4-6` via local proxy).

## Threshold Guidelines

- **Remaining > 10%**: Quota is healthy. Proceed with tasks silently.
- **Remaining <= 10% and > 5%**: **[WARNING]** Attach an alert in the response indicating remaining quota percentage and estimated reset time.
- **Remaining <= 5%**: **[CRITICAL SWITCH]** Halt resource-intensive generations, notify the user, and prompt for confirmation to switch to the fallback provider.
- **Dual Depleted (<= 10% or <= 5% for both OpenAI & Gemini)**: Issue a dual-depleted warning and recommend switching to Claude.

## Usage

Run the quota guard script relative to this skill directory:

```bash
# Check quota and evaluate status (human-readable)
python3 scripts/quota_switch_guard.py --check

# Check quota (JSON format for agents)
python3 scripts/quota_switch_guard.py --check --json

# Switch to a target provider (options: openai, gemini, claude)
python3 scripts/quota_switch_guard.py --switch openai

# Switch provider and automatically restart Codex Desktop
python3 scripts/quota_switch_guard.py --switch gemini --restart
```

## Safety & Cross-Provider Token Sanitation

When switching from Gemini/Vertex back to OpenAI official:
- The script automatically runs `sanitize_history.py` to remove incompatible reasoning token carrier blocks (`cpa-gemini-responses-carrier-v1` / `rs_resp_req_vrtx_...`).
- Advise the user to open a **New Chat** if switching between providers to avoid cross-provider decryption errors (`invalid_encrypted_content`).
