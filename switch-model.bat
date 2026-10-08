@echo off
chcp 65001 >nul
cd /d "%~dp0"
if "%~1"=="" (
    echo 使用方式: switch-model.bat ^<openai^|gemini^|claude^> [--restart]
    pause
    exit /b 1
)
python quota_switch_guard.py --switch %*
pause
