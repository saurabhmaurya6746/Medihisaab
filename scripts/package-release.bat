@echo off
REM ==============================================================================
REM Pharmacy POS - Production Packaging & Release Builder
REM Stages the release payload and compiles the Inno Setup Windows installer
REM ==============================================================================

setlocal enabledelayedexpansion
title MediHisaab - Packaging Release

echo ==============================================================================
echo  MEDIHISAAB - PRODUCTION RELEASE PACKAGING
echo ==============================================================================
echo.

set "REPO_ROOT=%~dp0.."
set "DIST_DIR=%REPO_ROOT%\dist-release"
set "STAGE_DIR=%DIST_DIR%\MediHisaab-v1.0.3"

echo [STEP 1/4] Building web frontend production bundle...
cd /d "%REPO_ROOT%"
call npm run build --workspace=apps/web
if %ERRORLEVEL% neq 0 (
  echo [ERROR] Web frontend build failed!
  pause
  exit /b 1
)

echo.
echo [STEP 1B/5] Building standalone MediHisaab daemon...
python -m PyInstaller --noconfirm --clean "%REPO_ROOT%\pharmacy-daemon.spec"
if %ERRORLEVEL% neq 0 (
  echo [ERROR] MediHisaab daemon packaging failed!
  pause
  exit /b 1
)

echo.
echo [STEP 1C/5] Building standalone desktop window host...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name desktop-window --icon "%REPO_ROOT%\assets\medihisaab-icon.ico" --hidden-import webview.platforms.winforms --hidden-import webview.platforms.edgechromium scripts\desktop-window.py
if %ERRORLEVEL% neq 0 (
  echo [ERROR] Desktop window packaging failed!
  pause
  exit /b 1
)

echo.
echo [STEP 2/4] Staging distribution payload in %STAGE_DIR%...
if exist "%STAGE_DIR%" rmdir /s /q "%STAGE_DIR%"
mkdir "%STAGE_DIR%"
mkdir "%STAGE_DIR%\web"
mkdir "%STAGE_DIR%\daemon\pharmacy_daemon"
mkdir "%STAGE_DIR%\docs"

REM Copy Web Assets
xcopy "%REPO_ROOT%\apps\web\dist\*" "%STAGE_DIR%\web\" /s /e /y >nul

REM Copy Daemon Package
xcopy "%REPO_ROOT%\apps\daemon\src\pharmacy_daemon\*" "%STAGE_DIR%\daemon\pharmacy_daemon\" /s /e /y >nul
copy "%REPO_ROOT%\apps\daemon\pyproject.toml" "%STAGE_DIR%\daemon\" >nul

REM Copy the standalone daemon bundle used by the production launcher
xcopy "%REPO_ROOT%\dist\pharmacy-daemon\*" "%STAGE_DIR%\daemon\" /s /e /y >nul

REM Copy Branding Assets
copy "%REPO_ROOT%\assets\medihisaab-icon.ico" "%STAGE_DIR%\" >nul
copy "%REPO_ROOT%\assets\medihisaab-logo.png" "%STAGE_DIR%\" >nul

REM Copy Launchers
copy "%REPO_ROOT%\scripts\start-pharmacy.bat" "%STAGE_DIR%\" >nul
copy "%REPO_ROOT%\scripts\start-pharmacy-hidden.vbs" "%STAGE_DIR%\" >nul
copy "%REPO_ROOT%\scripts\start-lan-server.bat" "%STAGE_DIR%\" >nul
copy "%REPO_ROOT%\scripts\check-daemon.ps1" "%STAGE_DIR%\" >nul
copy "%REPO_ROOT%\scripts\desktop-window.py" "%STAGE_DIR%\" >nul
copy "%REPO_ROOT%\dist\desktop-window.exe" "%STAGE_DIR%\" >nul
copy "%REPO_ROOT%\scripts\test-hardware.bat" "%STAGE_DIR%\" >nul
copy "%REPO_ROOT%\scripts\test-hardware.py" "%STAGE_DIR%\" >nul

REM Copy Documentation
xcopy "%REPO_ROOT%\docs\*" "%STAGE_DIR%\docs\" /s /e /y >nul 2>nul

echo [SUCCESS] Staged application files successfully.

echo.
echo [STEP 3/4] Creating portable ZIP archive...
powershell -Command "Compress-Archive -Path '%STAGE_DIR%\*' -DestinationPath '%DIST_DIR%\MediHisaab-v1.0.3-Portable.zip' -Force"
if %ERRORLEVEL% equ 0 (
  echo [SUCCESS] Created portable package: %DIST_DIR%\MediHisaab-v1.0.3-Portable.zip
)

echo.
echo [STEP 4/5] Building standalone setup installer...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name MediHisaab-Setup-1.0.3 --icon "%REPO_ROOT%\assets\medihisaab-icon.ico" --add-data "%DIST_DIR%\MediHisaab-v1.0.3-Portable.zip;." --distpath "%DIST_DIR%" --workpath "%REPO_ROOT%\build\portable-installer" --specpath "%REPO_ROOT%\build\portable-installer" "%REPO_ROOT%\scripts\portable-installer.py"
if %ERRORLEVEL% neq 0 (
  echo [ERROR] Standalone setup installer build failed!
  pause
  exit /b 1
)
  echo [SUCCESS] Created setup installer: %DIST_DIR%\MediHisaab-Setup-1.0.3.exe

echo.
echo [STEP 5/5] Checking for Inno Setup Compiler ISCC.exe...
set "ISCC_EXE="
where iscc >nul 2>nul
if %ERRORLEVEL% equ 0 set "ISCC_EXE=iscc"

if not defined ISCC_EXE (
  if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
  if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
  if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)

if defined ISCC_EXE (
  echo [INFO] Inno Setup compiler found at: !ISCC_EXE!
  echo [INFO] Compiling Windows installer executable...
  "!ISCC_EXE!" "%REPO_ROOT%\installer\pharmacy-pos-installer.iss"
  if %ERRORLEVEL% equ 0 (
    echo [SUCCESS] Windows installer compiled: %DIST_DIR%\MediHisaab-Setup-1.0.3.exe
  ) else (
    echo [WARN] Inno Setup compilation encountered an issue. Portable zip is still available.
  )
) else (
  echo [INFO] Inno Setup Compiler ISCC not found in PATH or standard directories.
  echo [INFO] To compile the standalone setup .exe:
  echo        1. Download Inno Setup 6 from https://jrsoftware.org/isdl.php
  echo        2. Open installer\pharmacy-pos-installer.iss in Inno Setup Compiler and click Compile.
)

echo.
echo ==============================================================================
echo  PACKAGING COMPLETE
  echo  Staged Folder:    %STAGE_DIR%
  echo  Portable Archive: %DIST_DIR%\MediHisaab-v1.0.3-Portable.zip
echo ==============================================================================
pause
