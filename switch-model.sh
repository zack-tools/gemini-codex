#!/bin/bash
cd "$(dirname "$0")" || exit 1
if [ -z "$1" ]; then
    echo "使用方式: ./switch-model.sh <openai|gemini|claude> [--restart]"
    exit 1
fi
python3 quota_switch_guard.py --switch "$1" "${@:2}"
