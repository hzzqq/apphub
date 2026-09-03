@echo off
setlocal
echo ============================================================
echo   App Hub - Restart (stop + start)
echo ============================================================
echo.

echo [*] Step 1/2: stop existing backend ...
call "%~dp0stop.bat"

echo.
echo [*] Step 2/2: start fresh backend ...
call "%~dp0start.bat"
