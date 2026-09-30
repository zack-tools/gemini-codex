@echo off
title Gemini OAuth Login
echo =======================================================
echo Starting Google OAuth Login...
echo Please log in with your Google account in the browser.
echo =======================================================
cd /d "%~dp0"
cli-proxy-api.exe -antigravity-login
pause
