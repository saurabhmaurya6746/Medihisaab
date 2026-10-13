@echo off
REM ==============================================================================
REM Offline Pharmacy Management System - Local Development Orchestrator
REM Milestone 1A Launcher Placeholder
REM ==============================================================================

echo [PHARMACY POS] Starting local development environment...
echo [INFO] Monorepo: %~dp0..
echo.

if not exist "%~dp0..\node_modules" (
  echo [NOTICE] Dependencies not yet installed.
  echo Run 'npm install' once implementation milestones are active.
)

echo [READY] Backend service placeholder: scripts\start-backend.bat
echo [READY] Frontend client placeholder: scripts\start-frontend.bat
echo.
pause
