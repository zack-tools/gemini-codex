#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
echo "請在開啟的瀏覽器視窗中完成 Google 帳號授權登入..."
./cli-proxy-api -antigravity-login
