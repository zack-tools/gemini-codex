# Check Model Quota

Run `scripts/check_quota.py --json` relative to this skill directory using an available Python 3.9+ interpreter. On Windows, set `PYTHONIOENCODING=utf-8`. Use `--provider openai` or `--provider antigravity` when the user requests only one service; default is both.

Report account, provider/product, quota source, remaining percentages, and reset times in Asia/Taipei:

- Google / Gemini and Anthropic / Claude: Antigravity credentials from the first `~/.cli-proxy-api/antigravity-*.json` match. These are not Gemini App/API or Claude direct subscription quotas.
- OpenAI / Codex: ChatGPT subscription using `CODEX_HOME/auth.json`, or `~/.codex/auth.json` when unset. `--openai-auth PATH` overrides this. API keys and keyring-only credentials are unsupported. On OAuth HTTP 401, report the instruction to run `codex login`.

Read `geminiModels` and `claudeModels` for per-model percentages and reset times. Only group identical values; do not describe a summary as the currently selected model. Read `openai.rateLimits` for primary, secondary, and any additional windows. `remainingPercent` is already the remaining allowance, not usage.

`fetchAvailableModels` can omit a zero fraction; the script supplements it using explicit `retrieveUserQuota` buckets. Missing values remain unknown. Never infer 100% from an internal autocomplete model or infer zero from a missing field. Do not expose token values or credential contents.

Exit code 1 may include valid results for the other service. Report successful results and the failed service's error separately. A failed supplementary Antigravity query can fall back to model-list data with unknown fractions and exit code 0. Antigravity token refresh requires matching `ANTIGRAVITY_OAUTH_CLIENT_ID` and `ANTIGRAVITY_OAUTH_CLIENT_SECRET` environment variables; without them, ask the user to sign in again through the original login tool when the access token expires. Successful refresh updates the existing credential file; OpenAI credentials are read-only.
