; ==============================================================================
; Inno Setup 6 Script: Pharmacy POS (Offline Pharmacy Management System)
; Version: 1.0.1
; Architecture: Windows 10 / 11 (x64)
; ==============================================================================

#define MyAppName "MediHisaab"
#define MyAppVersion "1.0.1"
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
DefaultDirName={autopf}\{#MyAppName}
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
VersionInfoVersion=1.0.1.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Offline Pharmacy Management System & POS
VersionInfoCopyright=Copyright (C) 2026 {#MyAppPublisher}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 1. Built Frontend Static Assets
Source: "..\apps\web\dist\*"; DestDir: "{app}\web"; Flags: ignoreversion recursesubdirs createallsubdirs

; 2. Standalone Packaged Backend Daemon Executable & Dependencies (PyInstaller)
Source: "..\dist\pharmacy-daemon\*"; DestDir: "{app}\daemon"; Flags: ignoreversion recursesubdirs createallsubdirs

; 3. Production Launchers and Utility Scripts
Source: "..\assets\medihisaab-icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\medihisaab-logo.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\scripts\start-pharmacy.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\scripts\start-lan-server.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\scripts\desktop-window.py"; DestDir: "{app}"; Flags: ignoreversion
; Standalone PyInstaller desktop shell. Includes pywebview/WebView2 integration and Python runtime.
Source: "..\dist\desktop-window.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\scripts\test-hardware.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\scripts\test-hardware.py"; DestDir: "{app}"; Flags: ignoreversion

; 4. Documentation & Offline Guides
Source: "..\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu Shortcuts
Name: "{autoprograms}\{#MyAppName}\{#MyAppName}"; Filename: "{app}\start-pharmacy.bat"; WorkingDir: "{app}"; IconFilename: "{app}\medihisaab-icon.ico"; Comment: "Launch MediHisaab single workstation"
Name: "{autoprograms}\{#MyAppName}\{#MyAppName} (LAN Server Mode)"; Filename: "{app}\start-lan-server.bat"; WorkingDir: "{app}"; IconFilename: "{app}\medihisaab-icon.ico"; Comment: "Launch MediHisaab in multi-counter LAN mode"
Name: "{autoprograms}\{#MyAppName}\Hardware & Printer Test"; Filename: "{app}\test-hardware.bat"; WorkingDir: "{app}"; Comment: "Hardware and ESC/POS printer diagnostics"
Name: "{autoprograms}\{#MyAppName}\MediHisaab Backups Folder"; Filename: "{localappdata}\PharmacyApp\backups"; WorkingDir: "{localappdata}\PharmacyApp"; Comment: "Open local automated backup storage"
Name: "{autoprograms}\{#MyAppName}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"; IconFilename: "{app}\medihisaab-icon.ico"

; Desktop Shortcut
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\start-pharmacy.bat"; WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\medihisaab-icon.ico"; Comment: "Launch MediHisaab"

[Run]
Filename: "{app}\start-pharmacy.bat"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: shellexec postinstall nowait skipifsilent

[Code]
// ==============================================================================
// Custom Pascal Scripting for Safe Upgrades & Uninstall Data Protection
// ==============================================================================

// Standalone binary requires no third-party runtimes (Python or Node.js)
function InitializeSetup(): Boolean;
begin
  Result := True;
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
