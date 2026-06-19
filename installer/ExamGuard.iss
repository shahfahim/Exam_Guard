; ===========================================================================
; ExamGuard.iss -- Inno Setup 6 Installer Script
; ExamGuard v4.0.0 -- Lab Exam Integrity Monitor
; Publisher : shahfahim  |  https://github.com/shahfahim/Exam_Guard
;
; Requirements : Inno Setup 6.2+  (https://jrsoftware.org/isdl.php)
; Build with   : iscc ExamGuard.iss
; Output       : installer\Output\ExamGuardSetup_v4.0.0.exe
; ===========================================================================

#define MyAppName        "ExamGuard"
#define MyAppVersion     "4.0.0"
#define MyAppPublisher   "shahfahim"
#define MyAppURL         "https://github.com/shahfahim/Exam_Guard"
#define MyAppExeName     "ExamGuard.exe"
#define MyAppDescription "Lab Exam Integrity Monitor"
#define MyAppGUID        "7C3E8A92-4F5D-4B1E-9D2A-8F6C3E7A1B45"
#define MinDiskMB        300

; ---------------------------------------------------------------------------
; [Setup]
; ---------------------------------------------------------------------------
[Setup]
AppId                       = {{{#MyAppGUID}}
AppName                     = {#MyAppName}
AppVersion                  = {#MyAppVersion}
AppVerName                  = {#MyAppName} {#MyAppVersion}
AppPublisher                = {#MyAppPublisher}
AppPublisherURL             = {#MyAppURL}
AppSupportURL               = {#MyAppURL}/issues
AppUpdatesURL               = {#MyAppURL}/releases
AppCopyright                = Copyright (C) 2024 {#MyAppPublisher}

DefaultDirName              = {autopf}\{#MyAppName}
DefaultGroupName            = {#MyAppName}

UninstallDisplayIcon        = {app}\{#MyAppExeName}
UninstallDisplayName        = {#MyAppName} {#MyAppVersion}
CreateUninstallRegKey       = yes

OutputDir                   = Output
OutputBaseFilename          = ExamGuardSetup_v{#MyAppVersion}

SetupIconFile               = assets\examguard.ico
WizardImageFile             = assets\wizard_banner.bmp
WizardSmallImageFile        = assets\wizard_header.bmp
WizardStyle                 = modern
WizardSizePercent           = 120

LicenseFile                 = assets\license.txt

Compression                 = lzma2/ultra64
SolidCompression            = yes
LZMAUseSeparateProcess      = yes

PrivilegesRequired          = admin
PrivilegesRequiredOverridesAllowed = dialog

MinVersion                  = 6.1sp1
ArchitecturesAllowed        = x64compatible
ArchitecturesInstallIn64BitMode = x64compatible
UsedUserAreasWarning        = no

VersionInfoVersion          = {#MyAppVersion}.0
VersionInfoCompany          = {#MyAppPublisher}
VersionInfoDescription      = {#MyAppName} Setup
VersionInfoProductName      = {#MyAppName}
VersionInfoProductVersion   = {#MyAppVersion}
VersionInfoCopyright        = Copyright (C) 2024 {#MyAppPublisher}

AllowNoIcons                = yes
DisableDirPage              = no
DisableProgramGroupPage     = no
AlwaysShowDirOnReadyPage    = yes
ShowLanguageDialog          = no
AppMutex                    = ExamGuard_Running_{#MyAppGUID}

; ---------------------------------------------------------------------------
; [Languages]
; ---------------------------------------------------------------------------
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; ---------------------------------------------------------------------------
; [Tasks]
; ---------------------------------------------------------------------------
[Tasks]
Name: "desktopicon"; Description: "Create a &Desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

; ---------------------------------------------------------------------------
; [Files]
; ---------------------------------------------------------------------------
[Files]
Source: "..\dist\ExamGuard\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "prereq\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: VCRedistNeeded

; ---------------------------------------------------------------------------
; [Dirs]
; ---------------------------------------------------------------------------
[Dirs]
Name: "{userappdata}\{#MyAppName}";              Permissions: users-full
Name: "{userappdata}\{#MyAppName}\screenshots";  Permissions: users-full
Name: "{userappdata}\{#MyAppName}\.vault";       Permissions: users-full
Name: "{userappdata}\{#MyAppName}\logs";         Permissions: users-full

; ---------------------------------------------------------------------------
; [Icons]
; ---------------------------------------------------------------------------
[Icons]
Name: "{group}\{#MyAppName}";             Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppDescription}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}";   Filename: "{uninstallexe}"; Comment: "Remove {#MyAppName} from this computer"
Name: "{autodesktop}\{#MyAppName}";       Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppDescription}"; WorkingDir: "{app}"; Tasks: desktopicon

; ---------------------------------------------------------------------------
; [Registry]
; ---------------------------------------------------------------------------
[Registry]
Root: HKLM64; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey createvalueifdoesntexist
Root: HKLM64; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "Version";     ValueData: "{#MyAppVersion}"; Flags: uninsdeletevalue
Root: HKLM64; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "Publisher";   ValueData: "{#MyAppPublisher}"; Flags: uninsdeletevalue
Root: HKLM64; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "URL";         ValueData: "{#MyAppURL}"; Flags: uninsdeletevalue

; ---------------------------------------------------------------------------
; [Run]
; ---------------------------------------------------------------------------
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent unchecked

; ---------------------------------------------------------------------------
; [Code]
; ---------------------------------------------------------------------------
[Code]

// Win32 API for disk space check
function GetDiskFreeSpaceExW(
  lpDirName              : String;
  var FreeBytesAvailable : Int64;
  var TotalBytes         : Int64;
  var TotalFreeBytes     : Int64
): Boolean;
external 'GetDiskFreeSpaceExW@kernel32.dll stdcall';


// ---------------------------------------------------------------------------
// Global state
// ---------------------------------------------------------------------------
var
  RequirementsPage : TWizardPage;
  ReqMemo          : TNewMemo;
  ReqAllPassed     : Boolean;
  g_NeedVCRedist   : Boolean;


// ---------------------------------------------------------------------------
// Dependency detection helpers
// ---------------------------------------------------------------------------

// Returns True if VC++ 2015-2022 x64 runtime is NOT installed (needs install)
function VCRedistNeeded(): Boolean;
var
  RegVal : Cardinal;
begin
  Result := True;
  if RegQueryDWordValue(HKLM64,
      'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64',
      'Installed', RegVal) then
    if RegVal >= 1 then begin Result := False; Exit; end;
  if RegQueryDWordValue(HKLM,
      'SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64',
      'Installed', RegVal) then
    if RegVal >= 1 then Result := False;
end;

// Returns True if the target drive has at least RequiredMB free
function HasEnoughDiskSpace(RequiredMB: Integer): Boolean;
var
  Free, Total, TotalFree : Int64;
  Drive                  : String;
begin
  Result := True;
  Drive  := ExtractFileDrive(WizardDirValue) + '\';
  try
    if GetDiskFreeSpaceExW(Drive, Free, Total, TotalFree) then
      Result := (Free >= Int64(RequiredMB) * 1048576);
  except
    Result := True;
  end;
end;


// ---------------------------------------------------------------------------
// Requirements page content builder
// ---------------------------------------------------------------------------
procedure RefreshRequirementsPage();
var
  L        : TStrings;
  HasSpace : Boolean;
begin
  L            := ReqMemo.Lines;
  ReqAllPassed := True;

  L.Clear;
  L.Add('');
  L.Add('  Checking your system...');
  L.Add('');
  L.Add('  +---------------------------------------------------+');
  L.Add('  |  #   Requirement                   Status         |');
  L.Add('  +---------------------------------------------------+');

  // 1. OS (already enforced by InitializeSetup)
  L.Add('  |  1   Windows 10 / 11 (64-bit)      [ PASS ]       |');

  // 2. Disk space
  HasSpace := HasEnoughDiskSpace({#MinDiskMB});
  if HasSpace then
    L.Add('  |  2   Free disk space ({#MinDiskMB} MB min)     [ PASS ]       |')
  else
  begin
    L.Add('  |  2   Free disk space ({#MinDiskMB} MB min)     [ FAIL ]       |');
    ReqAllPassed := False;
  end;

  // 3. VC++ Redistributable
  g_NeedVCRedist := VCRedistNeeded();
  if not g_NeedVCRedist then
    L.Add('  |  3   VC++ 2022 Runtime             [ PASS ]       |')
  else
    L.Add('  |  3   VC++ 2022 Runtime             [ AUTO-INST ]  |');

  // 4. Python (bundled)
  L.Add('  |  4   Python 3 Runtime              [ BUNDLED ]    |');

  // 5. App packages (bundled)
  L.Add('  |  5   All app packages              [ BUNDLED ]    |');

  L.Add('  +---------------------------------------------------+');
  L.Add('');

  if not HasSpace then
  begin
    L.Add('  FAIL: Drive ' + ExtractFileDrive(WizardDirValue) +
          ' needs at least {#MinDiskMB} MB free.');
    L.Add('        Click Back, pick a different install folder, then');
    L.Add('        come back to this page.');
    L.Add('');
  end;

  if g_NeedVCRedist then
  begin
    L.Add('  INFO: Visual C++ 2022 Runtime is not installed.');
    L.Add('        It will be installed SILENTLY when you click Install.');
    L.Add('        No action required from you.');
    L.Add('');
  end;

  if ReqAllPassed then
    L.Add('  All requirements are met. Click Next to continue.')
  else
    L.Add('  ERROR: Please resolve the FAIL items above before continuing.');
end;


// ---------------------------------------------------------------------------
// Wizard event handlers
// ---------------------------------------------------------------------------

procedure InitializeWizard();
begin
  ReqAllPassed   := True;
  g_NeedVCRedist := False;

  RequirementsPage := CreateCustomPage(
    wpLicense,
    'System Requirements Check',
    'Setup is checking your system before installing {#MyAppName}.'
  );

  ReqMemo            := TNewMemo.Create(RequirementsPage);
  ReqMemo.Parent     := RequirementsPage.Surface;
  ReqMemo.Left       := 0;
  ReqMemo.Top        := 0;
  ReqMemo.Width      := RequirementsPage.SurfaceWidth;
  ReqMemo.Height     := RequirementsPage.SurfaceHeight;
  ReqMemo.ScrollBars := ssVertical;
  ReqMemo.ReadOnly   := True;
  ReqMemo.WordWrap   := False;
  ReqMemo.Font.Name  := 'Courier New';
  ReqMemo.Font.Size  := 9;
  ReqMemo.Lines.Add('');
  ReqMemo.Lines.Add('  Waiting to check requirements...');
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = RequirementsPage.ID then
  begin
    RefreshRequirementsPage();
    WizardForm.NextButton.Enabled := ReqAllPassed;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = RequirementsPage.ID) and (not ReqAllPassed) then
  begin
    MsgBox(
      'One or more requirements have not been met.' + #13#10 +
      'Please click Back, resolve the issue, and try again.',
      mbError, MB_OK);
    Result := False;
  end;
end;


// ---------------------------------------------------------------------------
// PrepareToInstall -- auto-install missing dependencies silently
// ---------------------------------------------------------------------------
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  VCPath     : String;
  ResultCode : Integer;
begin
  Result       := '';
  NeedsRestart := False;

  if not g_NeedVCRedist then Exit;

  VCPath := ExpandConstant('{tmp}\vc_redist.x64.exe');
  if not FileExists(VCPath) then Exit;

  if not Exec(VCPath, '/install /quiet /norestart', '',
              SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Result := 'Could not install Visual C++ Redistributable.' + #13#10 +
              'Download manually: https://aka.ms/vs/17/release/vc_redist.x64.exe' + #13#10 +
              'Then run this Setup again.';
    Exit;
  end;

  case ResultCode of
    0, 1638 : ;
    3010    : NeedsRestart := True;
    1603    : Result := 'Visual C++ installation failed (error 1603). ' +
                        'Please install it manually and re-run Setup.';
  end;
end;


// ---------------------------------------------------------------------------
// Version / duplicate-install helpers
// ---------------------------------------------------------------------------

function GetInstalledVersion(): String;
var
  Reg : String;
begin
  Result := '';
  RegQueryStringValue(HKLM64,
    'SOFTWARE\{#MyAppPublisher}\{#MyAppName}', 'Version', Reg);
  if Reg = '' then
    RegQueryStringValue(HKLM,
      'SOFTWARE\{#MyAppPublisher}\{#MyAppName}', 'Version', Reg);
  Result := Reg;
end;

function CompareVersionStrings(V1, V2: String): Integer;
var
  N1, N2, P : Integer;
begin
  Result := 0;
  while (Length(V1) > 0) or (Length(V2) > 0) do
  begin
    P := Pos('.', V1);
    if P > 0 then begin
      N1 := StrToIntDef(Copy(V1, 1, P-1), 0);
      V1 := Copy(V1, P+1, MaxInt);
    end else begin
      N1 := StrToIntDef(V1, 0);
      V1 := '';
    end;
    P := Pos('.', V2);
    if P > 0 then begin
      N2 := StrToIntDef(Copy(V2, 1, P-1), 0);
      V2 := Copy(V2, P+1, MaxInt);
    end else begin
      N2 := StrToIntDef(V2, 0);
      V2 := '';
    end;
    if N1 < N2 then begin Result := -1; Exit; end
    else if N1 > N2 then begin Result := 1; Exit; end;
  end;
end;

function InitializeSetup(): Boolean;
var
  InstalledVer, Msg : String;
  Cmp               : Integer;
begin
  Result := True;

  if not IsWin64 then
  begin
    MsgBox('{#MyAppName} requires Windows 10 (64-bit) or later.',
           mbError, MB_OK);
    Result := False; Exit;
  end;

  if GetWindowsVersion() < $0A000000 then
  begin
    MsgBox('{#MyAppName} requires Windows 10 or later.',
           mbError, MB_OK);
    Result := False; Exit;
  end;

  InstalledVer := GetInstalledVersion();
  if InstalledVer <> '' then
  begin
    Cmp := CompareVersionStrings(InstalledVer, '{#MyAppVersion}');
    if Cmp > 0 then
    begin
      Msg := 'A newer version (' + InstalledVer + ') is already installed.' + #13#10 +
             'Downgrade to {#MyAppVersion}?';
      if MsgBox(Msg, mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDNO then
      begin Result := False; Exit; end;
    end
    else if Cmp = 0 then
    begin
      Msg := '{#MyAppName} {#MyAppVersion} is already installed.' + #13#10 +
             'Reinstall it?';
      if MsgBox(Msg, mbConfirmation, MB_YESNO) = IDNO then
      begin Result := False; Exit; end;
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataPath : String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataPath := ExpandConstant('{userappdata}\{#MyAppName}');
    if DirExists(DataPath) then
      if MsgBox(
        'Remove {#MyAppName} user data (database, screenshots, logs)?' + #13#10 + #13#10 +
        'Location: ' + DataPath,
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataPath, True, True, True);
  end;
end;
