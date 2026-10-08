#!/bin/bash
cd "$(dirname "$0")" || exit 1
python3 quota_switch_guard.py --check "$@"
