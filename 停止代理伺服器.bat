@echo off
chcp 65001 >nul
echo 正在停止 Gemini 代理伺服器 (cli-proxy-api.exe)...
taskkill /F /IM cli-proxy-api.exe >nul 2>&1
echo [完成] Gemini 代理伺服器已停止。
timeout /t 3 >nul

