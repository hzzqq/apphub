@echo off
setlocal EnableDelayedExpansion
REM Port: read .port.env (allocated by port-doctor); fall back to 8787 when absent
if exist "%~dp0.port.env" for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0.port.env") do if not "%%A"=="#" set "%%A=%%B"
if not defined PORT set "PORT=8787"
set "HUB_CMD=%1"
if "%HUB_CMD%"=="" set "HUB_CMD=start"
if /i "%HUB_CMD%"=="start"   goto :do_start
if /i "%HUB_CMD%"=="stop"    goto :do_stop
if /i "%HUB_CMD%"=="restart" goto :do_restart
if /i "%HUB_CMD%"=="status"  goto :do_status
if /i "%HUB_CMD%"=="doctor"  goto :do_doctor
goto :usage

:usage
echo ============================================================
echo   App Hub - Unified Launcher
echo   Usage: hub.bat [start^|stop^|restart^|status^|doctor]
echo     start   (default) launch backend + open browser
echo     stop    kill backend, clean lock
echo     restart stop + start
echo     status  show if port 8787 is listening
echo     doctor  self-check launcher deps and runtime state
echo ============================================================
pause
exit /b 1

:do_doctor
rem port comes from .port.env (see header)
set "APPDIR=%~dp0"
if "%APPDIR:~-1%"=="\" set "APPDIR=%APPDIR:~0,-1%"
echo ============================================================
echo   App Hub - Doctor
echo ============================================================
echo.
if not exist "%APPDIR%\backend\doctor.py" (
  echo [ERROR] backend\doctor.py is missing - cannot run the self-check.
  pause
  exit /b 1
)
set "DRPY=E:\python\python.exe"
if not exist "%DRPY%" set "DRPY=python"
"%DRPY%" "%APPDIR%\backend\doctor.py"
set "DRC=!ERRORLEVEL!"
echo.
pause
exit /b !DRC!
:do_status
rem port comes from .port.env (see header)
set "HUBFOUND="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":%PORT%"') do set "HUBFOUND=1"
if defined HUBFOUND (
  echo [status] port %PORT% LISTENING
) else (
  echo [status] port %PORT% NOT listening
)
echo   Run "hub.bat" or "hub.bat start" to launch.
pause
exit /b 0
:do_stop
rem port comes from .port.env (see header)
set "LOCKF=%TEMP%\hub_backend.lock"
echo ============================================================
echo   App Hub - Stop Backend
echo ============================================================
echo.
set "HUBFOUND=0"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":%PORT%"') do (
  echo [*] Found backend on port %PORT% PID=%%P - killing ...
  taskkill /F /PID %%P >nul 2>&1
  if errorlevel 1 (
    echo [WARN] Failed to kill PID %%P - may have died or be protected.
  ) else (
    echo [ok] PID %%P stopped.
  )
  set /a HUBFOUND+=1
)
if exist "%LOCKF%" (
  del "%LOCKF%" >nul 2>&1
  echo [ok] Lock file removed: %LOCKF%
)
if "!HUBFOUND!"=="0" (
  echo [INFO] No process is listening on port %PORT%.
  echo        Maybe you never ran hub.bat, or the backend already stopped.
)
echo.
pause
exit /b 0
:do_restart
echo ============================================================
echo   App Hub - Restart (stop + start)
echo ============================================================
echo.
call :do_stop
echo.
goto :do_start

:do_start
rem port comes from .port.env (see header)
set "LOCKF=%TEMP%\hub_backend.lock"

echo ============================================================
echo   App Hub - One-click Launcher (Windows)
echo ============================================================
echo.

REM ===== 1) Locate python =====
REM Project uses the canonical E:\python\python.exe (3.11.9 with pythonw.exe).
REM Hardcoded to avoid picking the WindowsApps Store stub that lacks pythonw.exe
REM (and to avoid cmd's notorious nested-if + for-loop parsing traps on this box).
REM To use a different Python install, edit this line.
set "PYEXE=E:\python\python.exe"
if not exist "%PYEXE%" (
  echo [ERROR] Python not found at %PYEXE%.
  echo          Project expects E:\python\python.exe - 3.11.x with pythonw.exe.
  echo          Install it there, or edit the PYEXE line in hub.bat to point at another install.
  pause
  exit /b 1
)
echo [ok] Python: %PYEXE%
"%PYEXE%" --version

REM Derive pythonw.exe (GUI subsystem, runs WITHOUT a console window) for windowless backend
REM NOTE: direct `set "PYEXEW=%PYEXE:python.exe=pythonw.exe%"` chokes cmd because the
REM second `=` inside the variable substitution is misread as set's OLD=NEW syntax
REM (cmd parses set arguments BEFORE expanding %VAR%, so the unexpanded %PYEXE:...%
REM looks like an invalid OLD=NEW token). The fix is `call set` with `%%` -> `%`:
call set "PYEXEW=%%PYEXE:python.exe=pythonw.exe%%"
if not exist "%PYEXEW%" (
  echo [ERROR] pythonw.exe not found next to %PYEXE%.
  echo          Backend needs to run windowless; reinstall Python including the "py launcher" option.
  pause
  exit /b 1
)
echo [ok] Backend will run windowless via: %PYEXEW%

REM ===== 2) Ensure backend deps (Flask plus flask-cors) =====
"%PYEXE%" -c "import flask, flask_cors" >nul 2>nul
if errorlevel 1 (
  echo [*] Installing backend deps: Flask plus flask-cors ...
  "%PYEXE%" -m pip install Flask flask-cors
) else (
  echo [ok] Backend deps ready
)

REM ===== 3) Single-instance guard via lock file =====
if exist "%LOCKF%" (
  set "OLDPID="
  for /f "usebackq delims=" %%L in ("%LOCKF%") do set "OLDPID=%%L"
  if defined OLDPID (
    tasklist /FI "PID eq !OLDPID!" /NH 2>nul | findstr /I "python" >nul && (
      echo [ERROR] Another HubBackend already running. PID=!OLDPID! still alive. Run "hub.bat stop" first.
      pause
      exit /b 1
    )
  )
  echo [WARN] Stale lock file. PID=!OLDPID! not alive, removing ...
  del "%LOCKF%" >nul 2>&1
)

REM ===== 4) Port 8787 conflict detection (kill leftover) =====
echo [*] Checking port %PORT% ...
set "TMPCHK=%TEMP%\hub_portchk_%RANDOM%.txt"
netstat -ano 2>nul | findstr "LISTENING" | findstr ":%PORT% " > "%TMPCHK%" 2>nul
set "OLDPID="
for /f "usebackq tokens=5" %%P in ("%TMPCHK%") do (
  if not defined OLDPID set "OLDPID=%%P"
)
del "%TMPCHK%" >nul 2>&1
if defined OLDPID (
  echo [WARN] Port %PORT% taken by PID !OLDPID!. Killing to start fresh ...
  taskkill /F /PID !OLDPID! >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] Failed to kill PID !OLDPID!. Close it manually.
    pause
    exit /b 1
  )
  echo [ok] Killed PID !OLDPID!.
)

REM ===== 5) Data mode by akshare availability =====
"%PYEXE%" -c "import akshare" >nul 2>nul
if not errorlevel 1 (
  set OFFLINE_MODE=False
  echo [*] akshare detected - LIVE data mode
) else (
  set OFFLINE_MODE=True
  echo [*] akshare NOT installed - OFFLINE mode - bundled cached data
)

REM ===== 6) Start backend as a WINDOWLESS background process =====
REM Use pythonw.exe (GUI subsystem) so NO console window is created at all.
REM CRITICAL: we CANNOT just `start pythonw ...` because cmd wraps every child
REM in a Job Object; when cmd naturally exits (pause EOF / user closes window)
REM the Job is destroyed and pythonw is killed too. That was the real cause of
REM "won't start" in the browser after double-click.
REM The fix: launch pythonw via WMI (Invoke-CimMethod Win32_Process.Create).
REM WMI is a SYSTEM service outside cmd's Job, so the spawned pythonw lives
REM independently of cmd. (We tried CREATE_BREAKAWAY_FROM_JOB first but cmd's
REM Job rejects it with WinError 5 (access denied).)
REM Strip trailing backslash from %~dp0 so /D "path" has no backslash-before-quote (cmd parse break)
set "APPDIR=%~dp0"
if "%APPDIR:~-1%"=="\" set "APPDIR=%APPDIR:~0,-1%"
echo [*] Starting backend (windowless) at http://127.0.0.1:%PORT% - OFFLINE_MODE=%OFFLINE_MODE% ...
echo         Logs: %TEMP%\hub_backend.log
if not exist "%APPDIR%\backend\_spawn.ps1" (
  echo [ERROR] backend/_spawn.ps1 missing - launcher cannot start the backend.
  echo         This helper must ship with the repo; it is no longer gitignored.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%APPDIR%\backend\_spawn.ps1" "%PYEXEW%" "%APPDIR%" "%OFFLINE_MODE%" > "%TEMP%\hub_spawn.log" 2>&1
if errorlevel 1 (
  echo [ERROR] Backend spawn failed. Details:
  type "%TEMP%\hub_spawn.log"
  pause
  exit /b 1
)
echo [ok] Backend process spawned (windowless).

REM ===== 7) Smart wait: poll /api/health via python urllib (no curl dependency) =====
echo [*] Waiting for backend - up to 20s ...
set /a WAIT=0
:wait_loop
set /a WAIT+=1
if !WAIT! gtr 20 goto :wait_timeout
"%PYEXE%" -c "import urllib.request; urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:%PORT%/api/health', timeout=2)" >nul 2>&1 && (
  echo [ok] Backend ready after !WAIT! s
  goto :wait_done
)
ping -n 2 127.0.0.1 >nul
goto :wait_loop
:wait_timeout
echo [ERROR] Backend not responding after 20s - webpage CANNOT be opened.
echo         Refusing to open the browser. Old behaviour opened it anyway and
echo         produced ERR_CONNECTION_REFUSED. Diagnostics:
echo ---- spawn log ----
if exist "%TEMP%\hub_spawn.log" type "%TEMP%\hub_spawn.log"
echo ---- backend log ----
if exist "%TEMP%\hub_backend.log" (
  type "%TEMP%\hub_backend.log"
) else (
  echo         hub_backend.log missing - pythonw never started
)
echo.
echo         Fix: run "hub.bat stop", then "hub.bat start" again.
pause
exit /b 1
:wait_done

REM ===== 8) Record backend PID to lock file =====
set "TMPNP=%TEMP%\hub_newpid_%RANDOM%.txt"
netstat -ano 2>nul | findstr "LISTENING" | findstr ":%PORT% " > "%TMPNP%" 2>nul
set "NEWPID="
for /f "usebackq tokens=5" %%P in ("%TMPNP%") do (
  if not defined NEWPID set "NEWPID=%%P"
)
del "%TMPNP%" >nul 2>&1
if defined NEWPID (
  echo !NEWPID! > "%LOCKF%"
  echo [ok] Lock saved: PID=!NEWPID! at %LOCKF%
) else (
  echo [WARN] Could not detect backend PID, lock not written
)

REM ===== 9) Fetch real futures data (optional, needs internet) =====
REM Fix: the old synchronous call blocked the launcher when SHFE/CZCE hung,
REM       creating a false "startup failed" impression. Now run it in a
REM       minimized background window (12s timeout + atomic write). Backend is
REM       already up from step 6; new data takes effect after next refresh.
"%PYEXE%" -c "import akshare" >nul 2>nul
if not errorlevel 1 (
  echo [*] Fetching real futures data in background (non-blocking, ~60s) ...
  if exist "%TEMP%\hub_fetch.log" del "%TEMP%\hub_fetch.log" >nul 2>&1
  start "" /MIN "%PYEXE%" backend/fetch_real_futures.py ^> "%TEMP%\hub_fetch.log" 2^>^&1
) else (
  echo [NOTE] akshare not installed, skip real-data fetch. Optional: pip install akshare
)

REM ===== 10) Open the hub via BACKEND http:// (same-origin, NOT file://) =====
echo [*] Opening App hub in browser: http://127.0.0.1:%PORT%/
start "" "http://127.0.0.1:%PORT%/"

echo.
echo ============================================================
echo   Done
echo   - Backend runs WINDOWLESS (pythonw). No backend window to worry about.
echo   - LAUNCHER window: press any key (or close with X) - project keeps running.
echo     The backend is fully detached; closing this window does NOT stop the apps.
echo   - To STOP the backend: run "hub.bat stop"
echo   - To RESTART the backend: run "hub.bat restart"
echo     (or from a shell: taskkill /F /IM pythonw.exe)
echo   - Browser opened http://127.0.0.1:%PORT%/ - backend serves frontend, same-origin.
echo   - If Edge shows ERR_CONNECTION_REFUSED: bypass the proxy for 127.0.0.1
echo     (Proxy settings ^> "Do not use proxy for local addresses").
echo   - Diagnostic log : %TEMP%\hub_backend.log
echo   - Lock file      : %LOCKF% - auto maintained
echo ============================================================
pause
