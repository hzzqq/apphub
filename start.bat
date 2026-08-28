@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo   App Hub - One-click Launcher (Windows)
echo ============================================================
echo.

REM 1) Check Python
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Install Python and tick "Add python.exe to PATH".
  echo          Download: https://www.python.org/downloads/
  pause
  exit /b 1
)
echo [ok] Python found:
python --version

REM 2) Ensure backend deps (Flask required; akshare only for crawler)
python -c "import flask" >nul 2>nul
if errorlevel 1 (
  echo [*] Installing backend deps: Flask + flask-cors ...
  python -m pip install Flask flask-cors
) else (
  echo [ok] Backend deps ready
)

REM 3) Decide data mode by akshare availability
python -c "import akshare" >nul 2>nul
if not errorlevel 1 (
  set OFFLINE_MODE=False
  echo [*] akshare detected -> LIVE data mode (real-time fetch + auto-refresh)
) else (
  set OFFLINE_MODE=True
  echo [*] akshare NOT installed -> OFFLINE mode (bundled real cached data + samples)
)
echo [*] Starting backend at http://127.0.0.1:8787 (OFFLINE_MODE=%OFFLINE_MODE%) ...
start "HubBackend" python backend/app.py

REM 4) Wait for backend
echo [*] Waiting for backend to boot, about 4s ...
timeout /t 4 >nul

REM 5) Fetch real futures data (needs internet; failure is safe, hub still works)
python -c "import akshare" >nul 2>nul
if not errorlevel 1 (
  echo [*] Fetching real futures data, e.g. pulp SP. Failure is harmless ...
  python backend/fetch_real_futures.py || echo [SKIP] fetch failed, futures-inventory will use built-in samples
) else (
  echo [NOTE] akshare not installed, skip real-data fetch. Optional: python -m pip install akshare
)

REM 6) Open the App hub
echo [*] Opening App hub ...
start "" "%~dp0index.html"

echo.
echo ============================================================
echo   Done
echo   - Backend window is running. Close it to stop all APIs.
echo   - Browser opened the App hub.
echo   - To refetch real data, double-click refresh_data.bat
echo ============================================================
pause
