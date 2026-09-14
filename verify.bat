@echo off
setlocal
cd /d "%~dp0"
set "PY=C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12.old.18140\python.exe"
if not exist "%PY%" set "PY=python"
echo [App Hub] Running 12-gate verification ...
echo [App Hub] Interpreter: %PY%
"%PY%" -u verify_all.py
set RC=%ERRORLEVEL%
echo [App Hub] verify_all exit code = %RC%   (0 = all gates passed)
pause
exit /b %RC%
