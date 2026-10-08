#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# 優先使用 launchctl 管理服務
PLIST="$HOME/Library/LaunchAgents/com.zack.cli-proxy-api.plist"
if [ -f "$PLIST" ]; then
    echo "透過 launchctl 載入並啟動 CLIProxyAPI 服務..."
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST"
    sleep 1
    if pgrep -f "cli-proxy-api" >/dev/null; then
        echo "[成功] CLIProxyAPI 正在後台運行中 (PID: $(pgrep -f 'cli-proxy-api'))"
        exit 0
    fi
fi

# 備用直接後台啟動
mkdir -p "$DIR/logs"
nohup ./cli-proxy-api > "$DIR/logs/proxy.log" 2> "$DIR/logs/proxy_err.log" &
sleep 1
echo "[成功] 代理伺服器已在後台啟動 (PID: $!)"
