; Inno Setup script for Cuvis.AI UI
; Requires Inno Setup 6+ (https://jrsoftware.org/isinfo.php)

#define MyAppName "Cuvis.AI UI"
#define MyAppExeName "cuvis-ui.exe"
#define MyAppPublisher "Cubert GmbH"
#define MyAppURL "https://github.com/cubert-hyperspectral/cuvis-ai-ui"

; Version is injected by build.bat via /D flag, defaults to "0.0.0"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

[Setup]
AppId={{B7E3F2A1-9C4D-4E8B-A1F6-3D2C5E7A9B01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=cuvis-ai-ui-setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
SetupIconFile=logo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "installserver"; Description: "Install the local cuvis-ai-core gRPC server (~3 GB download, requires internet). Uncheck if you only want the UI to connect to a remote server."; GroupDescription: "Server runtime:"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; UI PyInstaller bundle
Source: "..\dist\cuvis-ui\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Server payload — small (3.5 MB source + scripts). Always shipped so the user
; can run bootstrap.ps1 later via "Setup local server…" if they unchecked it now.
Source: "payload\cuvis-ai-core\*"; DestDir: "{app}\server\source"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "bootstrap.ps1"; DestDir: "{app}\server"; Flags: ignoreversion
Source: "server-launcher.cmd"; DestDir: "{app}\server"; Flags: ignoreversion
Source: "server_launcher.py"; DestDir: "{app}\server"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
; Server runner — visible only when the server task was selected.
Name: "{group}\Cuvis.AI Server"; Filename: "{app}\server\server-launcher.cmd"; WorkingDir: "{app}\server"; IconFilename: "{app}\{#MyAppExeName}"; Comment: "Start the local cuvis-ai-core gRPC server (launch before Cuvis.AI UI)"; Tasks: installserver
; Re-runner for users who skipped the server install or want to repair it later.
Name: "{group}\Setup local server"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\server\bootstrap.ps1"" -InstallDir ""{app}"""; WorkingDir: "{app}\server"; IconFilename: "{app}\{#MyAppExeName}"; Comment: "Re-run server bootstrap (creates venv, installs deps, downloads ffmpeg + graphviz)"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Bootstrap the server environment (uv venv + uv sync + ffmpeg/graphviz download). May take several minutes on first install.
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\server\bootstrap.ps1"" -InstallDir ""{app}"""; StatusMsg: "Setting up the server environment (downloads ~3 GB on first install)..."; Flags: runhidden waituntilterminated; Tasks: installserver
; Optional: launch the UI after install
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    if MsgBox(
      'Cuvis SDK is required for reading .cu3s / .cu3 hyperspectral cubes.' + #13#10 + #13#10 +
      'It is NOT bundled with this installer. Without it, file readers will fail at runtime.' + #13#10 + #13#10 +
      'Open the Cubert SDK download page now?',
      mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open',
        'https://cloud.cubert-gmbh.de/s/qpxkyWkycrmBK9m',
        '', '', SW_SHOW, ewNoWait, ResultCode);
    end;
  end;
end;
