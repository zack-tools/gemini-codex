@echo off
chcp 65001 >nul
cd /d "%~dp0"
python quota_switch_guard.py --check %*
pause
