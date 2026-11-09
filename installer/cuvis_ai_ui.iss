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

; The SDK download page (TDownloadWizardPage.ShowBaseNameInsteadOfUrl) needs Inno Setup 6.3.
#if Ver < EncodeVer(6, 3, 0)
  #error Inno Setup 6.3 or newer is needed to build this installer
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

{ CUVIS is set and its folder holds the SDK library. }
function SdkLibraryPresent: Boolean;
begin
  Result := (MachineCuvis <> '') and FileExists(AddBackslash(MachineCuvis) + 'cuvis.dll');
end;

{ No SDK, one whose library is gone from the CUVIS folder, or one older than the pin. A present SDK
  of unknown version, or of a newer series, is left alone. }
function SdkNeeded: Boolean;
var
  Installed, Pin: Int64;
begin
  if SdkNewerSeries then
    Result := False
  else if not SdkLibraryPresent then
    Result := True
  else
    Result := KnownVersion(InstalledSdkVersion, Installed)
      and StrToVersion('{#CuvisSdkVersion}', Pin)
      and (ComparePackedVersion(Installed, Pin) < 0);
end;

{ Registered at or above the pin, with its library where CUVIS points. }
function SdkCurrent: Boolean;
var
  Installed, Pin: Int64;
begin
  Result := SdkLibraryPresent
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

{ /FORCESDK offers the SDK even when the machine has the pinned version (repair, testing); a newer
  series is never replaced. }
function SdkOffered: Boolean;
begin
  Result := (SdkNeeded or HasSwitch('/FORCESDK')) and not SdkNewerSeries;
end;

procedure OfferSdkPage(const Reason: String; Icon: TMsgBoxType);
var
  ResultCode: Integer;
begin
  SdkMessageShown := True;
  { A silent install logs the reason and never waits on a question. }
  Log('Cuvis SDK: ' + Reason);
  if WizardSilent then
    exit;
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

{ Download on the Ready page (progress bar, Stop). Silent installs pass through here too. Stopping or a
  failed download leaves the UI install going without the SDK. }
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpReady) and WizardIsTaskSelected(SdkTask) then
  begin
    DownloadPage.Clear;
    DownloadPage.Add('{#CuvisSdkUrl}', '{#CuvisSdkAsset}', '{#CuvisSdkSha256}');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
        SdkDownloaded := True;
      except
        if DownloadPage.AbortedByUser then
          Log('Cuvis SDK download stopped')
        else
          OfferSdkPage('The Cuvis SDK could not be downloaded: ' + GetExceptionMessage + #13#10 +
            'Cuvis.AI UI installs without it.', mbError);
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;

{ The SDK installer is NSIS: /S runs it without pages, behind the administrator prompt. Success needs
  exit code 0, the registration at or above the pin and the library on disk. }
procedure InstallSdk;
var
  ResultCode, Waited: Integer;
  Installer, Sha: String;
begin
  { Another setup may have installed a newer series since the task page; never downgrade it. The end
    of the install names it. }
  if SdkNewerSeries then
  begin
    Log('Cuvis SDK ' + InstalledSdkVersion + ' was installed while this setup ran; the pinned installer was not run');
    exit;
  end;
  Installer := ExpandConstant('{tmp}\{#CuvisSdkAsset}');
  { The file waited in the user's temp folder since its download check; check it again right before
    it runs with administrator rights, so a swapped file is never elevated. }
  try
    Sha := GetSHA256OfFile(Installer);
  except
    Sha := '';
  end;
  if CompareText(Sha, '{#CuvisSdkSha256}') <> 0 then
  begin
    OfferSdkPage('The downloaded Cuvis SDK installer no longer matches its published checksum, so it was not run.', mbError);
    exit;
  end;
  WizardForm.StatusLabel.Caption := 'Installing the Cuvis SDK {#CuvisSdkVersion} (administrator rights required)...';
  if not ShellExec('runas', Installer, '/S', '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
  begin
    Log(Format('Cuvis SDK installer not started: code=%d', [ResultCode]));
    if ResultCode = ErrorCancelled then
      OfferSdkPage('Administrator rights were declined, so the Cuvis SDK was not installed.', mbError)
    else
      OfferSdkPage('The Cuvis SDK installer could not be started: ' + SysErrorMessage(ResultCode), mbError);
    exit;
  end;
  Log(Format('Cuvis SDK installer exited with code %d', [ResultCode]));
  if ResultCode <> 0 then
  begin
    OfferSdkPage(Format('The Cuvis SDK installer stopped with exit code %d, so the SDK may be incomplete.', [ResultCode]), mbError);
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
    OfferSdkPage('The Cuvis SDK installer finished, but SDK {#CuvisSdkVersion} is not complete on this machine.', mbError);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  { Before the files and the server bootstrap, so the administrator prompt comes right after Install. }
  if (CurStep = ssInstall) and WizardIsTaskSelected(SdkTask) and SdkDownloaded then
    InstallSdk;

  if (CurStep = ssPostInstall) and not WizardSilent and not SdkMessageShown then
  begin
    if SdkNewerSeries then
      SuppressibleMsgBox('The Cuvis SDK ' + InstalledSdkVersion + ' on this machine is newer than the ' +
        '{#CuvisSdkVersion} series the cu3s data plugin is built for, so reading cubes may fail. ' +
        'This installer does not replace it.', mbInformation, MB_OK, IDOK)
    else if MachineCuvis = '' then
      OfferSdkPage('The Cuvis SDK is not installed on this machine.', mbConfirmation)
    else if not SdkLibraryPresent then
      OfferSdkPage('The Cuvis SDK on this machine is incomplete: CUVIS points to ' + MachineCuvis +
        ', which has no cuvis.dll.', mbConfirmation)
    else if SdkNeeded then
      OfferSdkPage('The Cuvis SDK on this machine is older than {#CuvisSdkVersion}.', mbConfirmation);
  end;
end;
