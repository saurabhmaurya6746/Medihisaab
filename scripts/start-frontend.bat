@echo off
REM ==============================================================================
REM Offline Pharmacy Management System - React Vite Frontend Launcher
REM Port: 5173
REM Milestone 1A Launcher Placeholder
REM ==============================================================================

echo [WEB CLIENT] Starting React Vite POS client...
echo [INFO] Target URL: http://localhost:5173
echo.

if not exist "%~dp0..\apps\web" (
  echo [NOTICE] Frontend application will be created in Milestone 1C.
  echo.
  pause
  exit /b 0
)

npm --workspace=apps/web run dev
pause
