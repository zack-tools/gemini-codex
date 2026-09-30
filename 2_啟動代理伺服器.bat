@echo off
title CLIProxyAPI Server
echo =======================================================
echo Starting CLIProxyAPI Server on port 8317...
echo Endpoint: http://127.0.0.1:8317/v1
echo Please keep this window open in the background!
echo =======================================================
cd /d "%~dp0"
cli-proxy-api.exe
pause
