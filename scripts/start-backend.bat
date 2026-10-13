@echo off
REM ==============================================================================
REM Offline Pharmacy Management System - FastAPI Backend Service Launcher
REM Port: 38291 (Default loopback/LAN binding)
REM ==============================================================================

echo [BACKEND DAEMON] Initializing Python FastAPI backend service...
echo [INFO] Target port: 38291
echo [INFO] Authoritative database: %%LOCALAPPDATA%%\PharmacyApp\data\pharmacy.db
echo.

set "DAEMON_SRC=%~dp0..\apps\daemon\src"

if not exist "%~dp0..\apps\daemon" (
  echo [ERROR] Backend application directory not found: %~dp0..\apps\daemon
  echo [ERROR] Please verify project structure before launching.
  pause
  exit /b 1
)

if not exist "%DAEMON_SRC%\pharmacy_daemon" (
  echo [ERROR] Backend daemon module not found in: %DAEMON_SRC%\pharmacy_daemon
  echo [ERROR] Please verify installation before launching.
  pause
  exit /b 1
)

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
  echo [ERROR] Python runtime is not installed or not in system PATH.
  echo [ERROR] Please install Python 3.12+ and add it to PATH.
  pause
  exit /b 1
)

set "PYTHONPATH=%DAEMON_SRC%;%PYTHONPATH%"

python -m pharmacy_daemon
if %ERRORLEVEL% neq 0 (
  echo.
  echo [ERROR] Pharmacy Daemon exited with error code %ERRORLEVEL%.
  pause
  exit /b %ERRORLEVEL%
)

pause
