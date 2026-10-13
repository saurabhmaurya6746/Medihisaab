@echo off
REM ==============================================================================
REM Offline Pharmacy Management System - 1-Click Application Launcher
REM Launches the backend daemon service and opens the pharmacy user interface.
REM ==============================================================================

setlocal enabledelayedexpansion
title MediHisaab - Launching...

echo ==============================================================================
echo  MEDIHISAAB - OFFLINE PHARMACY MANAGEMENT SYSTEM
echo ==============================================================================
echo [INFO] Initializing MediHisaab...

set "SCRIPT_DIR=%~dp0"
set "DAEMON_SRC=%SCRIPT_DIR%..\apps\daemon\src"
set "APP_URL=http://127.0.0.1:38291"
set "PHARMACY_WEB_DIR=%SCRIPT_DIR%web"

REM The installed daemon serves the UI from PHARMACY_WEB_DIR. Set this explicitly
REM because the executable lives under daemon\ while the UI lives under web\.
if not exist "%PHARMACY_WEB_DIR%\index.html" (
  echo [ERROR] MediHisaab UI files were not found at "%PHARMACY_WEB_DIR%".
  echo [ERROR] Repair or reinstall MediHisaab so the web folder is installed beside this launcher.
  pause
  exit /b 1
)

REM Check if daemon is already running on port 38291
if exist "%SCRIPT_DIR%check-daemon.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%check-daemon.ps1" -Port 38291 -BaseUrl "%APP_URL%"
  if !ERRORLEVEL! equ 2 goto :verify_app_page
  if !ERRORLEVEL! equ 1 (
    echo [ERROR] Another application is using port 38291. Close it and retry.
    pause
    exit /b 1
  )
)

netstat -ano | findstr ":38291 " | findstr "LISTENING" >nul 2>nul
if %ERRORLEVEL% equ 0 (
  echo [INFO] MediHisaab backend daemon is already running on port 38291.
  goto :verify_app_page
)

REM Detect standalone compiled daemon binary
set "DAEMON_EXE="
if exist "%SCRIPT_DIR%daemon\pharmacy-daemon.exe" set "DAEMON_EXE=%SCRIPT_DIR%daemon\pharmacy-daemon.exe"
if exist "%SCRIPT_DIR%pharmacy-daemon\pharmacy-daemon.exe" set "DAEMON_EXE=%SCRIPT_DIR%pharmacy-daemon\pharmacy-daemon.exe"
if exist "%SCRIPT_DIR%..\dist\pharmacy-daemon\pharmacy-daemon.exe" set "DAEMON_EXE=%SCRIPT_DIR%..\dist\pharmacy-daemon\pharmacy-daemon.exe"
if exist "%SCRIPT_DIR%pharmacy-daemon.exe" set "DAEMON_EXE=%SCRIPT_DIR%pharmacy-daemon.exe"

if defined DAEMON_EXE (
  echo [INFO] Starting standalone MediHisaab Daemon: !DAEMON_EXE!
  start "MediHisaab Daemon" /min "!DAEMON_EXE!"
  goto :wait_for_daemon
)

REM Fallback to Python if running in development environment
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
  echo [ERROR] Neither standalone MediHisaab Daemon executable nor Python runtime was found.
  echo [ERROR] Please install MediHisaab using the official installer.
  pause
  exit /b 1
)

REM Start daemon via Python interpreter
echo [INFO] Starting MediHisaab Daemon via Python on port 38291...
set "PYTHONPATH=%DAEMON_SRC%;%PYTHONPATH%"
start "MediHisaab Daemon" /min python -m pharmacy_daemon

:wait_for_daemon

REM Wait for port 38291 to become active (up to 15 seconds)
echo [INFO] Waiting for service initialization...
set /a ATTEMPTS=0
:wait_loop
ping 127.0.0.1 -n 2 >nul
netstat -ano | findstr ":38291 " | findstr "LISTENING" >nul 2>nul
if %ERRORLEVEL% equ 0 (
  echo [SUCCESS] Backend daemon is active and listening!
  goto :verify_app_page
)
set /a ATTEMPTS+=1
if !ATTEMPTS! lss 15 (
  goto :wait_loop
)

echo [WARNING] Daemon did not report listening within 15 seconds.

:verify_app_page
set /a VERIFY_ATTEMPTS=0
:verify_page_loop
powershell -NoProfile -Command "try { $r=Invoke-WebRequest -Uri '%APP_URL%/' -UseBasicParsing -TimeoutSec 3; if($r.StatusCode -ne 200 -or $r.Headers['Content-Type'] -notmatch 'text/html') { exit 1 } } catch { exit 1 }"
if %ERRORLEVEL% equ 0 goto :open_desktop_window
set /a VERIFY_ATTEMPTS+=1
if !VERIFY_ATTEMPTS! lss 5 (
  ping 127.0.0.1 -n 2 >nul
  goto :verify_page_loop
)
echo [ERROR] MediHisaab UI did not load from %APP_URL%. Restart the app and try again.
pause
exit /b 1

:open_desktop_window
echo [INFO] Opening MediHisaab in dedicated desktop window...

REM Prefer the packaged standalone desktop-window host (no system Python required).
set "WINDOW_EXE="
if exist "%SCRIPT_DIR%desktop-window\desktop-window.exe" set "WINDOW_EXE=%SCRIPT_DIR%desktop-window\desktop-window.exe"
if exist "%SCRIPT_DIR%desktop-window.exe" set "WINDOW_EXE=%SCRIPT_DIR%desktop-window.exe"
if exist "%SCRIPT_DIR%..\dist\desktop-window.exe" set "WINDOW_EXE=%SCRIPT_DIR%..\dist\desktop-window.exe"
if defined WINDOW_EXE (
  start "MediHisaab Window" /b "!WINDOW_EXE!" --url "%APP_URL%" --wait
  goto :done
)

REM Development-only fallback: run the desktop shell from Python when available.
set "WINDOW_SCRIPT="
if exist "%SCRIPT_DIR%scripts\desktop-window.py" set "WINDOW_SCRIPT=%SCRIPT_DIR%scripts\desktop-window.py"
if exist "%SCRIPT_DIR%desktop-window.py" set "WINDOW_SCRIPT=%SCRIPT_DIR%desktop-window.py"
if exist "%SCRIPT_DIR%..\scripts\desktop-window.py" set "WINDOW_SCRIPT=%SCRIPT_DIR%..\scripts\desktop-window.py"

where python >nul 2>nul
if %ERRORLEVEL% equ 0 if defined WINDOW_SCRIPT (
  start "MediHisaab Window" /b python "!WINDOW_SCRIPT!" --url "%APP_URL%" --wait
  goto :done
)

REM Fallback 1: Microsoft Edge dedicated app mode window (no browser tabs/chrome)
set "EDGE_EXE="
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "EDGE_EXE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "EDGE_EXE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if exist "%LocalAppData%\Microsoft\Edge\Application\msedge.exe" set "EDGE_EXE=%LocalAppData%\Microsoft\Edge\Application\msedge.exe"

if defined EDGE_EXE (
  start "" "!EDGE_EXE!" --app="%APP_URL%" --window-size=1366,860 --disable-features=TranslateUI --no-first-run
  goto :done
)

REM Fallback 2: Google Chrome dedicated app mode window
set "CHROME_EXE="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"

if defined CHROME_EXE (
  start "" "!CHROME_EXE!" --app="%APP_URL%" --window-size=1366,860 --no-first-run
  goto :done
)

echo [ERROR] No desktop window host is installed and no supported app-mode browser was found.
echo [ERROR] Repair MediHisaab or install Microsoft Edge WebView2, then try again.
pause
exit /b 1

:done
echo.
echo [READY] MediHisaab is ready for operation.
ping 127.0.0.1 -n 3 >nul
exit /b 0
