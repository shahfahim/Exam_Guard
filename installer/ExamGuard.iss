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

; Install location
DefaultDirName              = {autopf}\{#MyAppName}
DefaultGroupName            = {#MyAppName}

; Uninstaller
UninstallDisplayIcon        = {app}\{#MyAppExeName}
UninstallDisplayName        = {#MyAppName} {#MyAppVersion}
CreateUninstallRegKey       = yes

; Output
OutputDir                   = Output
OutputBaseFilename          = ExamGuardSetup_v{#MyAppVersion}

; Visuals
SetupIconFile               = assets\examguard.ico
WizardImageFile             = assets\wizard_banner.bmp
WizardSmallImageFile        = assets\wizard_header.bmp
WizardStyle                 = modern
WizardSizePercent           = 120

; License
LicenseFile                 = assets\license.txt

; Compression
Compression                 = lzma2/ultra64
SolidCompression            = yes
LZMAUseSeparateProcess      = yes

; UAC -- request Administrator elevation
PrivilegesRequired          = admin
PrivilegesRequiredOverridesAllowed = dialog

; Platform requirements (enforced further in [Code] section)
MinVersion                  = 6.1sp1
ArchitecturesAllowed        = x64compatible
ArchitecturesInstallIn64BitMode = x64compatible
UsedUserAreasWarning        = no

; Version info embedded in setup exe
VersionInfoVersion          = {#MyAppVersion}.0
VersionInfoCompany          = {#MyAppPublisher}
VersionInfoDescription      = {#MyAppName} Setup
VersionInfoProductName      = {#MyAppName}
VersionInfoProductVersion   = {#MyAppVersion}
VersionInfoCopyright        = Copyright (C) 2024 {#MyAppPublisher}

; Misc
AllowNoIcons                = yes
DisableDirPage              = no
DisableProgramGroupPage     = no
ChangesAssociations         = no
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
; [Run] -- Post-install actions
; ---------------------------------------------------------------------------
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent unchecked

; ---------------------------------------------------------------------------
; [Code] -- Custom Pascal Script
; ---------------------------------------------------------------------------
[Code]

function GetInstalledVersion(): String;
var
  Reg: String;
begin
  Result := '';
  RegQueryStringValue(HKLM64,
    'SOFTWARE\{#MyAppPublisher}\{#MyAppName}',
    'Version', Reg);
  if Reg = '' then
    RegQueryStringValue(HKLM,
      'SOFTWARE\{#MyAppPublisher}\{#MyAppName}',
      'Version', Reg);
  Result := Reg;
end;

function CompareVersionStrings(V1, V2: String): Integer;
var
  N1, N2, P: Integer;
begin
  Result := 0;
  while (Length(V1) > 0) or (Length(V2) > 0) do
  begin
    P := Pos('.', V1);
    if P > 0 then begin
      N1 := StrToIntDef(Copy(V1, 1, P - 1), 0);
      V1 := Copy(V1, P + 1, MaxInt);
    end else begin
      N1 := StrToIntDef(V1, 0);
      V1 := '';
    end;
    P := Pos('.', V2);
    if P > 0 then begin
      N2 := StrToIntDef(Copy(V2, 1, P - 1), 0);
      V2 := Copy(V2, P + 1, MaxInt);
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
  InstalledVer, Msg: String;
  Cmp: Integer;
begin
  Result := True;

  // Require 64-bit Windows 10+
  if not IsWin64 then
  begin
    MsgBox(
      '{#MyAppName} requires a 64-bit version of Windows 10 or later.' + #13#10 +
      'Your system does not meet this requirement.',
      mbError, MB_OK);
    Result := False;
    Exit;
  end;

  // Check Windows 10 minimum (build 10240)
  if not (GetWindowsVersion >= $0A000000) then
  begin
    MsgBox(
      '{#MyAppName} requires Windows 10 or later.' + #13#10 +
      'Please upgrade your operating system.',
      mbError, MB_OK);
    Result := False;
    Exit;
  end;

  // Duplicate / downgrade guard
  InstalledVer := GetInstalledVersion();
  if InstalledVer <> '' then
  begin
    Cmp := CompareVersionStrings(InstalledVer, '{#MyAppVersion}');
    if Cmp > 0 then
    begin
      Msg := 'A newer version of {#MyAppName} (' + InstalledVer + ') is already installed.' + #13#10 +
             'Installing version {#MyAppVersion} will downgrade it.' + #13#10 + #13#10 +
             'Do you want to continue?';
      if MsgBox(Msg, mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDNO then
      begin
        Result := False;
        Exit;
      end;
    end
    else if Cmp = 0 then
    begin
      Msg := '{#MyAppName} {#MyAppVersion} is already installed.' + #13#10 +
             'Do you want to repair or reinstall it?';
      if MsgBox(Msg, mbConfirmation, MB_YESNO) = IDNO then
      begin
        Result := False;
        Exit;
      end;
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDataPath: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppDataPath := ExpandConstant('{userappdata}\{#MyAppName}');
    if DirExists(AppDataPath) then
    begin
      if MsgBox(
        'Do you want to remove {#MyAppName} user data?' + #13#10 +
        '(database, screenshots, logs)' + #13#10 + #13#10 +
        'Location: ' + AppDataPath + #13#10 + #13#10 +
        'Click Yes to delete all records, or No to keep them.',
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(AppDataPath, True, True, True);
      end;
    end;
  end;
end;
