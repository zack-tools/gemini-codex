@echo off
chcp 65001 >nul
title ChatGPT / Codex Portable Updater

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-ChatGPT-Portable.ps1" %*

echo.
pause
