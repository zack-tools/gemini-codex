#!/bin/bash
cd "$(dirname "$0")" || exit 1
echo "正在推送至 GitHub (zack-tools/gemini-codex)..."
git push origin main
echo "推送完成！"
