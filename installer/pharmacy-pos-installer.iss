; ==============================================================================
; Inno Setup 6 Script: Pharmacy POS (Offline Pharmacy Management System)
; Version: 1.0.8
; Architecture: Windows 10 / 11 (x64)
; ==============================================================================

#define MyAppName "MediHisaab"
#define MyAppVersion "1.0.8"
#define MyAppPublisher "Apex Health Technologies"
#define MyAppURL "https://github.com/apex-health/pharmacy-pos"
#define MyAppExeName "start-pharmacy.bat"

[Setup]
; Basic Application Info
AppId={{9F82C4A1-5B3E-4D78-9E1A-7A2B6C3D4E5F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={code:GetDefaultInstallDir}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\dist-release
OutputBaseFilename=MediHisaab-Setup-{#MyAppVersion}
SetupIconFile=..\assets\medihisaab-icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
; Ask Restart Manager to close MediHisaab before replacing its running binaries.
; Force the close after the user confirms so a lingering daemon cannot leave an
; old executable locked and cause a partial upgrade.
CloseApplications=force
CloseApplicationsFilter=pharmacy-daemon.exe,desktop-window.exe
RestartApplications=no
DisableProgramGroupPage=yes

; Version Info in Windows Explorer Properties
VersionInfoVersion=1.0.8.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Offline Pharmacy Management System & POS
VersionInfoCopyright=Copyright (C) 2026 {#MyAppPublisher}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; 1. Built Frontend Static Assets
Source: "..\apps\web\dist\*"; DestDir: "{app}\web"; Flags: ignoreversion recursesubdirs createallsubdirs

; 2. Standalone Packaged Backend Daemon Executable & Dependencies (PyInstaller)
Source: "..\dist\pharmacy-daemon\*"; DestDir: "{app}\daemon"; Flags: ignoreversion recursesubdirs createallsubdirs

; 3. Production Launchers and Utility Scripts
Source: "..\assets\medihisaab-icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\medihisaab-logo.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\scripts\start-pharmacy.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\scripts\start-pharmacy-hidden.vbs"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\scripts\start-lan-server.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\scripts\check-daemon.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\scripts\desktop-window.py"; DestDir: "{app}"; Flags: ignoreversion
; Standalone PyInstaller desktop shell. Includes pywebview/WebView2 integration and Python runtime.
Source: "..\dist\desktop-window.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\scripts\test-hardware.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\scripts\test-hardware.py"; DestDir: "{app}"; Flags: ignoreversion

; 4. Documentation & Offline Guides
Source: "..\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu Shortcuts
Name: "{autoprograms}\{#MyAppName}\{#MyAppName}"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\start-pharmacy-hidden.vbs"""; WorkingDir: "{app}"; IconFilename: "{app}\medihisaab-icon.ico"; Comment: "Launch MediHisaab single workstation"
Name: "{autoprograms}\{#MyAppName}\{#MyAppName} (Diagnostic Mode)"; Filename: "{app}\start-pharmacy.bat"; WorkingDir: "{app}"; IconFilename: "{app}\medihisaab-icon.ico"; Comment: "Launch MediHisaab with diagnostic console visible"
Name: "{autoprograms}\{#MyAppName}\{#MyAppName} (LAN Server Mode)"; Filename: "{app}\start-lan-server.bat"; WorkingDir: "{app}"; IconFilename: "{app}\medihisaab-icon.ico"; Comment: "Launch MediHisaab in multi-counter LAN mode"
Name: "{autoprograms}\{#MyAppName}\Hardware & Printer Test"; Filename: "{app}\test-hardware.bat"; WorkingDir: "{app}"; Comment: "Hardware and ESC/POS printer diagnostics"
Name: "{autoprograms}\{#MyAppName}\MediHisaab Backups Folder"; Filename: "{localappdata}\PharmacyApp\backups"; WorkingDir: "{localappdata}\PharmacyApp"; Comment: "Open local automated backup storage"
Name: "{autoprograms}\{#MyAppName}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"; IconFilename: "{app}\medihisaab-icon.ico"

; Desktop Shortcut
Name: "{autodesktop}\{#MyAppName}"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\start-pharmacy-hidden.vbs"""; WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\medihisaab-icon.ico"; Comment: "Launch MediHisaab"

[Run]
Filename: "{sys}\wscript.exe"; Parameters: """{app}\start-pharmacy-hidden.vbs"""; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: shellexec postinstall nowait skipifsilent

[Code]
// ==============================================================================
// Custom Pascal Scripting for Safe Upgrades & Uninstall Data Protection
// ==============================================================================

// Locate existing MediHisaab installation directory
function GetDefaultInstallDir(Param: String): String;
var
  LocalPrograms: String;
  PrevInstall: String;
  FindRec: TFindRec;
  Candidate: String;
  FoundDir: String;
begin
  LocalPrograms := ExpandConstant('{localappdata}\Programs');
  FoundDir := '';

  // 1. Check registry uninstall key from previous Inno Setup installation
  if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{9F82C4A1-5B3E-4D78-9E1A-7A2B6C3D4E5F}_is1', 'InstallLocation', PrevInstall) or
     RegQueryStringValue(HKLM, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{9F82C4A1-5B3E-4D78-9E1A-7A2B6C3D4E5F}_is1', 'InstallLocation', PrevInstall) then
  begin
    if (PrevInstall <> '') and DirExists(PrevInstall) and FileExists(PrevInstall + '\start-pharmacy.bat') then
    begin
      Result := PrevInstall;
      Exit;
    end;
  end;

  // 2. Check specific existing versions in Local Programs
  Candidate := LocalPrograms + '\MediHisaab-1.0.2';
  if FileExists(Candidate + '\start-pharmacy.bat') then
  begin
    Result := Candidate;
    Exit;
  end;

  Candidate := LocalPrograms + '\MediHisaab';
  if FileExists(Candidate + '\start-pharmacy.bat') then
  begin
    Result := Candidate;
    Exit;
  end;

  // Search for any existing MediHisaab-* directory containing the launcher
  if FindFirst(LocalPrograms + '\MediHisaab*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0) and
           (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          Candidate := LocalPrograms + '\' + FindRec.Name;
          if FileExists(Candidate + '\start-pharmacy.bat') then
          begin
            FoundDir := Candidate;
          end;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;

  if FoundDir <> '' then
  begin
    Result := FoundDir;
    Exit;
  end;

  Result := ExpandConstant('{autopf}\{#MyAppName}');
end;

// Helper to check if a process name is currently running
function IsProcessRunning(ExeName: String): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('cmd.exe', '/c tasklist /FI "IMAGENAME eq ' + ExeName + '" | findstr /i "' + ExeName + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

// Warn before stopping running processes to protect pharmacy data
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
  IsRunning: Boolean;
begin
  Result := True;
  IsRunning := IsProcessRunning('pharmacy-daemon.exe') or IsProcessRunning('desktop-window.exe');

  if IsRunning then
  begin
    if not WizardSilent() then
    begin
      if MsgBox('MediHisaab is currently running.' + #13#10#13#10 +
                'Please finish and save any open billing work before updating.' + #13#10#13#10 +
                'Would you like Setup to close MediHisaab now and proceed with the update?' + #13#10 +
                '(Your pharmacy databases and backups will NOT be deleted)',
                mbConfirmation, MB_YESNO) <> IDYES then
      begin
        Result := False;
        Exit;
      end;
    end;

    // Gracefully stop the desktop window and backend daemon
    Exec('taskkill.exe', '/F /IM desktop-window.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec('taskkill.exe', '/F /IM pharmacy-daemon.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1000);
  end;
end;

// Protect User Database and Financial Ledgers on Uninstall
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\PharmacyApp');
    if DirExists(DataDir) then
    begin
      if MsgBox('Do you want to DELETE your store database and transaction history located at:' + #13#10 +
                DataDir + #13#10#13#10 +
                'Select NO to preserve all sales invoices, ledger balances, and backup archives.' + #13#10 +
                '(Recommended: Select NO)', mbConfirmation, MB_YESNO) = IDYES then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;
