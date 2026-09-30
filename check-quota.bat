@echo off
setlocal
set PYTHONIOENCODING=utf-8
if exist "%LOCALAPPDATA%\Python\pythoncore-3.13-64\python.exe" goto local_python
py -3 -c "import sys; assert sys.version_info >= (3, 9)" >nul 2>nul
if errorlevel 1 goto path_python
py -3 "%~dp0check_quota.py" %*
exit /b %errorlevel%
:local_python
"%LOCALAPPDATA%\Python\pythoncore-3.13-64\python.exe" "%~dp0check_quota.py" %*
exit /b %errorlevel%
:path_python
python "%~dp0check_quota.py" %*
exit /b %errorlevel%
