@echo off
setlocal EnableDelayedExpansion
set PORT=8787
set "LOCKF=%TEMP%\hub_backend.lock"

echo ============================================================
echo   App Hub - Stop Backend
echo ============================================================
echo.

REM Step 1: netstat + findstr pipeline -> temp file
REM 原因:for /f in ('netstat | findstr | findstr') 内联管道在某些 cmd 环境下被切碎.
set "TMPF=%TEMP%\hub_pids_%RANDOM%.txt"
netstat -ano | findstr "LISTENING" | findstr ":%PORT% " > "%TMPF%" 2>nul

REM Step 2: parse PIDs, dedup (IPv4+IPv6 same PID), kill
set "FOUND=0"
set "LASTPID="
for /f "usebackq tokens=5" %%P in ("%TMPF%") do (
  if not "%%P"=="!LASTPID!" (
    set "LASTPID=%%P"
    set /a FOUND+=1
    echo [*] Found backend on port %PORT% (PID=%%P). Killing ...
    taskkill /F /PID %%P >nul 2>&1
    if errorlevel 1 (
      echo [WARN] Failed to kill PID %%P (may have died or be protected).
    ) else (
      echo [ok] PID %%P stopped.
    )
  )
)
del "%TMPF%" >nul 2>&1

REM Step 3: clean up lock file
if exist "%LOCKF%" (
  del "%LOCKF%" >nul 2>&1
  echo [ok] Lock file removed: %LOCKF%
)

if "%FOUND%"=="0" (
  echo [INFO] No process is listening on port %PORT%.
  echo        (Maybe you never ran start.bat, or backend already stopped.)
)

echo.
echo ============================================================
echo   - Frontend (browser) still works, but real-data features will fail.
echo   - To restart: double-click start.bat (or restart.bat for stop + start).
echo ============================================================
pause
