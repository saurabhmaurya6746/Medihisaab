@echo off
REM ==============================================================================
REM Pharmacy POS - Hardware & Printer Diagnostic Launcher
REM ==============================================================================

echo [HARDWARE DIAGNOSTIC] Launching Pharmacy POS Hardware Tester...
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
  echo [ERROR] Python runtime not found in PATH.
  pause
  exit /b 1
)

python "%~dp0test-hardware.py" %*

echo.
pause
