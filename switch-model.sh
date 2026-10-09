#!/bin/bash
cd "/Users/Zack/Tools/CLIProxyAPI" || exit 1
if [ -z "$1" ]; then
    echo "使用方式: switch-model <gemini|claude|openai> [--no-restart] [--model <model_name>]"
    echo ""
    echo "範例:"
    echo "  switch-model gemini    # 自動切換到 Gemini、自動清理歷史膠囊並重啟 Codex"
    echo "  switch-model claude    # 自動切換到 Claude、自動清理歷史膠囊並重啟 Codex"
    echo "  switch-model openai    # 自動切換到 OpenAI、自動清理歷史膠囊並重啟 Codex"
    exit 1
fi

TARGET="$1"
shift

RESTART_FLAG="--restart"
ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-restart)
            RESTART_FLAG=""
            shift
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done

python3 quota_switch_guard.py --switch "$TARGET" $RESTART_FLAG "${ARGS[@]}"
