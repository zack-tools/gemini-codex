@echo off
chcp 65001 >nul
cd /d D:\Git\gemini-codex
echo ==============================================
echo 正在推送 gemini-codex 至 GitHub (zack-tools/gemini-codex)...
echo ==============================================
git -c http.sslbackend=openssl push -u origin main
echo.
echo 若顯示 [Everything up-to-date] 或 [main -> main] 代表推送成功！
echo.
pause


