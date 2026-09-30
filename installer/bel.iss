; Inno Setup script. Build with scripts\build-installer.ps1 (runs PyInstaller first).
; Per-user install: no admin prompt, lands in %LOCALAPPDATA%\Programs\Bel.

#define AppName "Bel"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{B3E1C0DE-5A1F-4B7A-9C2D-BE1000000001}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=Bel-Setup-{#AppVersion}
SetupIconFile=..\assets\bel.ico
UninstallDisplayIcon={app}\Bel.exe
Compression=lzma2
SolidCompression=yes
DisableProgramGroupPage=yes
WizardStyle=modern

[Tasks]
Name: "autostart"; Description: "Start Bel when I sign in to Windows"

[Files]
Source: "..\dist\Bel\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Bel"; Filename: "{app}\Bel.exe"
Name: "{userstartup}\Bel"; Filename: "{app}\Bel.exe"; Tasks: autostart

[Run]
Filename: "{app}\Bel.exe"; Description: "Launch Bel"; Flags: nowait postinstall

[Code]
// A running exe is locked, so an upgrade or uninstall would fail on it.
procedure QuitBel();
var
  code: Integer;
begin
  Exec('taskkill.exe', '/F /IM Bel.exe', '', SW_HIDE, ewWaitUntilTerminated, code);
end;

function InitializeSetup(): Boolean;
begin
  QuitBel();
  Result := True;
end;

function InitializeUninstall(): Boolean;
begin
  QuitBel();
  Result := True;
end;
