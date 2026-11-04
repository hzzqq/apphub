# backend/_spawn.ps1
# Called by start.bat. Launch the Flask backend OUTSIDE cmd's Job Object via WMI,
# so closing the launcher window does NOT kill the server. On this box
# CREATE_BREAKAWAY_FROM_JOB is rejected with WinError 5, so the WMI service
# (a separate SYSTEM process) is the only reliable way to detach.
#
# Args : pythonw.exe path, project root, optional OFFLINE_MODE (default True)
# Log  : %TEMP%\hub_backend.log
# Note : start.bat still detects the real listener PID via netstat, because the
#        PID returned here belongs to the short-lived cmd.exe wrapper.

param(
    [Parameter(Mandatory = $true)][string]$PyExeW,
    [Parameter(Mandatory = $true)][string]$AppDir,
    [string]$OfflineMode = "True"
)

$ErrorActionPreference = "Stop"

$log = Join-Path $env:TEMP "hub_backend.log"
$app = Join-Path $AppDir "backend\app.py"
$port = "8787"
if ($env:PORT) { $port = $env:PORT }

if (-not (Test-Path $PyExeW)) { Write-Error "pythonw.exe not found: $PyExeW"; exit 1 }
if (-not (Test-Path $app))   { Write-Error "backend/app.py not found: $app"; exit 1 }

# cmd /s /c "<body>" : /s strips ONLY the outermost quotes, avoiding cmd's
# classic multi-quote parsing trap. The inner cmd sets the env vars and
# redirects stdout/stderr to the log (pythonw has no console of its own).
$body = 'set OFFLINE_MODE=' + $OfflineMode + ' && set PORT=' + $port + ' && "' + $PyExeW + '" "' + $app + '" > "' + $log + '" 2>&1'
$cmdLine = 'cmd.exe /s /c "' + $body + '"'

try {
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine      = $cmdLine
        CurrentDirectory = $AppDir
    }
    if ($null -eq $r -or $r.ReturnValue -ne 0) {
        $rc = if ($r) { $r.ReturnValue } else { "null" }
        Write-Error "Win32_Process.Create failed, ReturnValue=$rc"
        exit 1
    }
    Write-Output ("SPAWNED_PID=" + $r.ProcessId)
    exit 0
} catch {
    Write-Error ("spawn failed: " + $_.Exception.Message)
    exit 1
}
