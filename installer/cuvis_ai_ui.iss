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

; The Cuvis SDK release offered below (CuvisSdkVersion, CuvisSdkAsset, CuvisSdkUrl,
; CuvisSdkSha256, CuvisSdkSizeMB); installer\update_cuvis_sdk.py writes it.
#include "cuvis_sdk.iss"

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
; Offered when the machine has no Cuvis SDK or an older one; the local server reads cubes with it.
Name: "installserver\cuvissdk"; Description: "Install the Cuvis SDK {#CuvisSdkVersion} (about {#CuvisSdkSizeMB} MB download, needs administrator rights). The server needs it to read .cu3s / .cu3 cubes."; Check: SdkOffered
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
{ The Cuvis SDK is installed machine-wide by its own installer, downloaded from its GitHub release
  (cuvis_sdk.iss) and checked against the published SHA-256. Only that step asks for administrator
  rights; the rest of this installer stays per user. }
const
  MachineEnvKey = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';
  SdkUninstallKey = 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Cubert GmbH Cuvis_C_SDK';
  SdkTask = 'installserver\cuvissdk';
  SdkPage = 'https://sdk.cuvis.ai/';
  ErrorCancelled = 1223;

var
  DownloadPage: TDownloadWizardPage;
  SdkDownloadTried: Boolean;
  SdkDownloaded: Boolean;
  SdkMessageShown: Boolean;

function MachineCuvis: String;
begin
  if not RegQueryStringValue(HKLM, MachineEnvKey, 'CUVIS', Result) then
    Result := '';
end;

{ The NSIS-based SDK installer registers in the 32-bit view. }
function InstalledSdkVersion: String;
begin
  if not RegQueryStringValue(HKLM32, SdkUninstallKey, 'DisplayVersion', Result) then
    if not RegQueryStringValue(HKLM64, SdkUninstallKey, 'DisplayVersion', Result) then
      Result := '';
end;

{ False for a missing or unparsable version and for 0.0.0.0 (development builds). }
function KnownVersion(const S: String; var V: Int64): Boolean;
begin
  Result := StrToVersion(S, V) and (V <> 0);
end;

{ The installed SDK's major.minor is newer than the pin's: leave it alone, never downgrade. }
function SdkNewerSeries: Boolean;
var
  Installed, Pin: Int64;
  IMajor, IMinor, PMajor, PMinor, Rev, Build: Word;
begin
  Result := False;
  if KnownVersion(InstalledSdkVersion, Installed) and StrToVersion('{#CuvisSdkVersion}', Pin) then
  begin
    UnpackVersionComponents(Installed, IMajor, IMinor, Rev, Build);
    UnpackVersionComponents(Pin, PMajor, PMinor, Rev, Build);
    Result := (IMajor > PMajor) or ((IMajor = PMajor) and (IMinor > PMinor));
  end;
end;

{ No SDK, or one older than the pin. A present SDK of unknown version is left alone. }
function SdkNeeded: Boolean;
var
  Installed, Pin: Int64;
begin
  if MachineCuvis = '' then
    Result := True
  else
    Result := KnownVersion(InstalledSdkVersion, Installed)
      and StrToVersion('{#CuvisSdkVersion}', Pin)
      and (ComparePackedVersion(Installed, Pin) < 0);
end;

function SdkCurrent: Boolean;
var
  Installed, Pin: Int64;
begin
  Result := (MachineCuvis <> '')
    and KnownVersion(InstalledSdkVersion, Installed)
    and StrToVersion('{#CuvisSdkVersion}', Pin)
    and (ComparePackedVersion(Installed, Pin) >= 0);
end;

function HasSwitch(const Name: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), Name) = 0 then
      Result := True;
end;

{ /FORCESDK offers the SDK even when the machine has it (repair, testing). }
function SdkOffered: Boolean;
begin
  Result := SdkNeeded or HasSwitch('/FORCESDK');
end;

procedure OfferSdkPage(const Reason: String; Icon: TMsgBoxType);
var
  ResultCode: Integer;
begin
  SdkMessageShown := True;
  { /SUPPRESSMSGBOXES answers No. }
  if SuppressibleMsgBox(Reason + #13#10 + #13#10 +
      'Reading .cu3s / .cu3 cubes needs the Cuvis SDK {#CuvisSdkVersion} (through the cuvis-ai-dataloader plugin); ' +
      'drawing and editing pipelines works without it.' + #13#10 + #13#10 +
      'Open the Cuvis SDK download page now?',
      Icon, MB_YESNO, IDNO) = IDYES then
    ShellExec('open', SdkPage, '', '', SW_SHOW, ewNoWait, ResultCode);
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), nil);
  DownloadPage.ShowBaseNameInsteadOfUrl := True;
end;

{ Interactive installs download on the Ready page with a progress bar and Cancel. }
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpReady) and WizardIsTaskSelected(SdkTask) then
  begin
    SdkDownloadTried := True;
    DownloadPage.Clear;
    DownloadPage.Add('{#CuvisSdkUrl}', '{#CuvisSdkAsset}', '{#CuvisSdkSha256}');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
        SdkDownloaded := True;
      except
        if DownloadPage.AbortedByUser then
          Log('Cuvis SDK download cancelled')
        else
          OfferSdkPage('The Cuvis SDK could not be downloaded: ' + GetExceptionMessage + #13#10 +
            'Cuvis.AI UI installs without it.', mbError);
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;

{ Silent installs skip the wizard pages, so they download here. }
procedure DownloadSdkSilently;
begin
  SdkDownloadTried := True;
  try
    DownloadTemporaryFile('{#CuvisSdkUrl}', '{#CuvisSdkAsset}', '{#CuvisSdkSha256}', nil);
    SdkDownloaded := True;
  except
    Log('Cuvis SDK download failed: ' + GetExceptionMessage);
    OfferSdkPage('The Cuvis SDK could not be downloaded: ' + GetExceptionMessage, mbError);
  end;
end;

{ The SDK installer is NSIS: /S runs it without pages, behind the administrator prompt. Success is
  read from the registry, since ShellExec does not promise the exit code. }
procedure InstallSdk;
var
  ResultCode, Waited: Integer;
  Started: Boolean;
begin
  WizardForm.StatusLabel.Caption := 'Installing the Cuvis SDK {#CuvisSdkVersion} (administrator rights required)...';
  Started := ShellExec('runas', ExpandConstant('{tmp}\{#CuvisSdkAsset}'), '/S', '',
    SW_SHOW, ewWaitUntilTerminated, ResultCode);
  Log(Format('Cuvis SDK installer: started=%d code=%d', [Ord(Started), ResultCode]));
  if not Started then
  begin
    if ResultCode = ErrorCancelled then
      OfferSdkPage('Administrator rights were declined, so the Cuvis SDK was not installed.', mbError)
    else
      OfferSdkPage('The Cuvis SDK installer could not be started: ' + SysErrorMessage(ResultCode), mbError);
    exit;
  end;
  Waited := 0;
  while not SdkCurrent and (Waited < 10000) do
  begin
    Sleep(500);
    Waited := Waited + 500;
  end;
  if SdkCurrent then
    Log('Cuvis SDK ' + InstalledSdkVersion + ' installed')
  else
    OfferSdkPage(Format('The Cuvis SDK installer finished (code %d), ' +
      'but SDK {#CuvisSdkVersion} is not registered on this machine.', [ResultCode]), mbError);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  { Before the files and the server bootstrap, so the administrator prompt comes right after Install. }
  if (CurStep = ssInstall) and WizardIsTaskSelected(SdkTask) then
  begin
    if not SdkDownloadTried then
      DownloadSdkSilently;
    if SdkDownloaded then
      InstallSdk;
  end;

  if (CurStep = ssPostInstall) and not WizardSilent and not SdkMessageShown then
  begin
    if MachineCuvis = '' then
      OfferSdkPage('The Cuvis SDK is not installed on this machine.', mbConfirmation)
    else if SdkNewerSeries then
      SuppressibleMsgBox('The Cuvis SDK ' + InstalledSdkVersion + ' on this machine is newer than the ' +
        '{#CuvisSdkVersion} series the cu3s data plugin is built for, so reading cubes may fail. ' +
        'This installer does not replace it.', mbInformation, MB_OK, IDOK);
  end;
end;
