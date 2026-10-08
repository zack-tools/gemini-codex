#!/bin/bash
PLIST="$HOME/Library/LaunchAgents/com.zack.cli-proxy-api.plist"
if [ -f "$PLIST" ]; then
    launchctl unload "$PLIST" 2>/dev/null || true
fi

pkill -f "cli-proxy-api" 2>/dev/null || true
echo "[完成] 代理伺服器已停止。"
