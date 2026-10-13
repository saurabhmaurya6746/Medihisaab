@echo off
REM ==============================================================================
REM Offline Pharmacy Management System - LAN Server Launcher
REM Binds to 0.0.0.0:38291 to accept connections from counter terminals on the local network
REM ==============================================================================

echo ==============================================================================
echo  MEDIHISAAB - MULTI-COUNTER LAN SERVER MODE
echo ==============================================================================
echo [INFO] Binding to all network interfaces (0.0.0.0:38291)...
echo.

set "SCRIPT_DIR=%~dp0"
set "DAEMON_SRC=%SCRIPT_DIR%..\apps\daemon\src"

set "PHARMACY_HOST=0.0.0.0"
set "PHARMACY_PORT=38291"

echo [NETWORK] Discovering local IP addresses for secondary billing terminals...
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | ForEach-Object { Write-Host ('   - Terminal URL: http://' + $_.IPAddress + ':38291') }"
echo.
echo [FIREWALL NOTE] Ensure Windows Defender Firewall allows inbound TCP on port 38291.
echo [FIREWALL CMD] netsh advfirewall firewall add rule name="MediHisaab LAN Server" dir=in action=allow protocol=TCP localport=38291 profile=private
echo.
echo [START] Launching daemon in LAN mode... Press Ctrl+C to stop.
echo ------------------------------------------------------------------------------

REM Check for standalone executable
set "DAEMON_EXE="
if exist "%SCRIPT_DIR%daemon\pharmacy-daemon.exe" set "DAEMON_EXE=%SCRIPT_DIR%daemon\pharmacy-daemon.exe"
if exist "%SCRIPT_DIR%pharmacy-daemon\pharmacy-daemon.exe" set "DAEMON_EXE=%SCRIPT_DIR%pharmacy-daemon\pharmacy-daemon.exe"
if exist "%SCRIPT_DIR%..\dist\pharmacy-daemon\pharmacy-daemon.exe" set "DAEMON_EXE=%SCRIPT_DIR%..\dist\pharmacy-daemon\pharmacy-daemon.exe"
if exist "%SCRIPT_DIR%pharmacy-daemon.exe" set "DAEMON_EXE=%SCRIPT_DIR%pharmacy-daemon.exe"

if defined DAEMON_EXE (
  echo [INFO] Running standalone daemon in LAN mode...
  "%DAEMON_EXE%"
  if %ERRORLEVEL% neq 0 (
    echo [ERROR] Pharmacy LAN Server exited with error code %ERRORLEVEL%.
    pause
    exit /b %ERRORLEVEL%
  )
  goto :lan_done
)

REM Fallback to Python if in development repository
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
  echo [ERROR] Neither standalone Pharmacy Daemon executable nor Python runtime was found.
  pause
  exit /b 1
)

set "PYTHONPATH=%DAEMON_SRC%;%PYTHONPATH%"
python -m pharmacy_daemon
if %ERRORLEVEL% neq 0 (
  echo [ERROR] Pharmacy LAN Server exited with error code %ERRORLEVEL%.
  pause
  exit /b %ERRORLEVEL%
)

:lan_done
pause
