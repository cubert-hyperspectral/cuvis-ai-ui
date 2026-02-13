; Inno Setup script for Cuvis.AI UI
; Requires Inno Setup 6+ (https://jrsoftware.org/isinfo.php)

#define MyAppName "Cuvis.AI UI"
#define MyAppExeName "cuvis-ui.exe"
#define MyAppPublisher "Cubert GmbH"
#define MyAppURL "https://gitlab.cubert.local/cubert/cuvis-ai-ui"

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
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Bundle the UI (PyInstaller dist/cuvis-ui/)
Source: "..\dist\cuvis-ui\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Bundle the gRPC server (PyInstaller dist/cuvis-server/) into {app}\server\
Source: "..\dist\cuvis-server\*"; DestDir: "{app}\server"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
