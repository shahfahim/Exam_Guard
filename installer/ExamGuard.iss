; ═══════════════════════════════════════════════════════════════════════════
; ExamGuard.iss — Inno Setup 6 Installer Script
; ExamGuard v4.0.0 — Lab Exam Integrity Monitor
; Publisher : shahfahim  |  https://github.com/shahfahim/Exam_Guard
;
; Requirements : Inno Setup 6.2+  (https://jrsoftware.org/isdl.php)
; Build with   : iscc ExamGuard.iss
; Output       : installer\Output\ExamGuardSetup_v4.0.0.exe
; ═══════════════════════════════════════════════════════════════════════════

#define MyAppName        "ExamGuard"
#define MyAppVersion     "4.0.0"
#define MyAppPublisher   "shahfahim"
#define MyAppURL         "https://github.com/shahfahim/Exam_Guard"
#define MyAppExeName     "ExamGuard.exe"
#define MyAppDescription "Lab Exam Integrity Monitor"
; GUID — uniquely identifies this product for Windows (never change after release)
#define MyAppGUID        "7C3E8A92-4F5D-4B1E-9D2A-8F6C3E7A1B45"

; ── [Setup] ─────────────────────────────────────────────────────────────────
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

; Install location — {autopf} = C:\Program Files on 64-bit
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

; Compression (best for distribution)
Compression                 = lzma2/ultra64
SolidCompression            = yes
LZMAUseSeparateProcess      = yes
LZMANumBlockThreads         = 4

; UAC — request Administrator elevation
PrivilegesRequired          = admin
PrivilegesRequiredOverridesAllowed = dialog

; Platform requirements
MinVersion                  = 10.0.17763     ; Windows 10 1809 minimum
ArchitecturesAllowed        = x64compatible
ArchitecturesInstallIn64BitMode = x64compatible

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
; Prevent running while app is already open
AppMutex                    = ExamGuard_Running_{#MyAppGUID}

; ── [Languages] ─────────────────────────────────────────────────────────────
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; ── [CustomMessages] ────────────────────────────────────────────────────────
[CustomMessages]
english.WelcomeLabel1       = Welcome to the {#MyAppName} {#MyAppVersion} Setup Wizard
english.WelcomeLabel2       = This wizard will install {#MyAppName} on your computer.%n%n{#MyAppDescription}%n%nAll exam data is stored locally — nothing is sent to the internet.%n%nClick Next to continue, or Cancel to exit.
english.FinishHeadingLabel  = {#MyAppName} has been installed successfully!

; ── [Tasks] ─────────────────────────────────────────────────────────────────
[Tasks]
; Desktop icon — checked by default
Name: "desktopicon";    Description: "Create a &Desktop shortcut";        GroupDescription: "Additional shortcuts:"; Flags: checkedonce
; Quick Launch / Taskbar pin hint
Name: "taskbarpin";     Description: "Pin to &Taskbar (after launch)";   GroupDescription: "Additional shortcuts:"; Flags: unchecked

; ── [Files] ─────────────────────────────────────────────────────────────────
[Files]
; ── Main application (PyInstaller one-folder output) ─────────────────────────
Source: "..\dist\ExamGuard\*"; \
    DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs; \
    Comment: "ExamGuard application files"

; ── [Dirs] ──────────────────────────────────────────────────────────────────
[Dirs]
; Pre-create the APPDATA directory with correct permissions
Name: "{userappdata}\{#MyAppName}";           Permissions: users-full
Name: "{userappdata}\{#MyAppName}\screenshots"; Permissions: users-full
Name: "{userappdata}\{#MyAppName}\.vault";    Permissions: users-full
Name: "{userappdata}\{#MyAppName}\logs";      Permissions: users-full

; ── [Icons] ─────────────────────────────────────────────────────────────────
[Icons]
; Start Menu shortcuts
Name: "{group}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    IconFilename: "{app}\{#MyAppExeName}"; \
    Comment: "{#MyAppDescription}"; \
    WorkingDir: "{app}"

Name: "{group}\Uninstall {#MyAppName}"; \
    Filename: "{uninstallexe}"; \
    Comment: "Remove {#MyAppName} from this computer"

; Desktop shortcut (if task selected)
Name: "{autodesktop}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    IconFilename: "{app}\{#MyAppExeName}"; \
    Comment: "{#MyAppDescription}"; \
    WorkingDir: "{app}"; \
    Tasks: desktopicon

; ── [Registry] ──────────────────────────────────────────────────────────────
[Registry]
; Installation metadata (used by update detection & duplicate-install guard)
Root: HKLM64; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; \
    ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; \
    Flags: uninsdeletekey createvalueifdoesntexist

Root: HKLM64; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; \
    ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; \
    Flags: uninsdeletevalue

Root: HKLM64; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; \
    ValueType: string; ValueName: "Publisher"; ValueData: "{#MyAppPublisher}"; \
    Flags: uninsdeletevalue

Root: HKLM64; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; \
    ValueType: string; ValueName: "URL"; ValueData: "{#MyAppURL}"; \
    Flags: uninsdeletevalue

; ── [Run] — Post-install launch ─────────────────────────────────────────────
[Run]
Filename: "{app}\{#MyAppExeName}"; \
    Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
    WorkingDir: "{app}"; \
    Flags: nowait postinstall skipifsilent unchecked; \
    Comment: "Launch ExamGuard after installation"

; ── [Code] — Custom Pascal Script ────────────────────────────────────────────
[Code]

// ── Helpers ────────────────────────────────────────────────────────────────

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

// Compare two dotted-version strings, returns:
//  -1  if V1 < V2
//   0  if V1 = V2
//  +1  if V1 > V2
function CompareVersionStrings(V1, V2: String): Integer;
var
  N1, N2, P: Integer;
begin
  Result := 0;
  while (Length(V1) > 0) or (Length(V2) > 0) do
  begin
    // Extract next numeric segment from V1
    P := Pos('.', V1);
    if P > 0 then
    begin
      N1 := StrToIntDef(Copy(V1, 1, P - 1), 0);
      V1 := Copy(V1, P + 1, MaxInt);
    end
    else
    begin
      N1 := StrToIntDef(V1, 0);
      V1 := '';
    end;

    // Extract next numeric segment from V2
    P := Pos('.', V2);
    if P > 0 then
    begin
      N2 := StrToIntDef(Copy(V2, 1, P - 1), 0);
      V2 := Copy(V2, P + 1, MaxInt);
    end
    else
    begin
      N2 := StrToIntDef(V2, 0);
      V2 := '';
    end;

    if N1 < N2 then begin Result := -1; Exit; end
    else if N1 > N2 then begin Result := 1; Exit; end;
  end;
end;

// ── InitializeSetup — runs before the wizard shows ─────────────────────────
function InitializeSetup(): Boolean;
var
  InstalledVer, Msg: String;
  Cmp: Integer;
begin
  Result := True;

  // ── 1. Require 64-bit Windows 10+ ──────────────────────────────────────
  if not IsWin64 then
  begin
    MsgBox(
      '{#MyAppName} requires a 64-bit version of Windows 10 or later.' + #13#10 +
      'Your system does not meet this requirement.',
      mbError, MB_OK);
    Result := False;
    Exit;
  end;

  // ── 2. Duplicate / downgrade guard ─────────────────────────────────────
  InstalledVer := GetInstalledVersion();
  if InstalledVer <> '' then
  begin
    Cmp := CompareVersionStrings(InstalledVer, '{#MyAppVersion}');
    if Cmp > 0 then
    begin
      // Newer version already installed
      Msg := 'A newer version of {#MyAppName} (' + InstalledVer + ') is already installed.' + #13#10 +
             'Installing version {#MyAppVersion} will downgrade it.' + #13#10#13#10 +
             'Do you want to continue?';
      if MsgBox(Msg, mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDNO then
      begin
        Result := False;
        Exit;
      end;
    end
    else if Cmp = 0 then
    begin
      // Same version already installed
      Msg := '{#MyAppName} {#MyAppVersion} is already installed on this computer.' + #13#10 +
             'Do you want to repair / reinstall it?';
      if MsgBox(Msg, mbConfirmation, MB_YESNO) = IDNO then
      begin
        Result := False;
        Exit;
      end;
    end;
    // If Cmp < 0 → upgrading to newer version — allow silently
  end;
end;

// ── CurStepChanged — post-install actions ──────────────────────────────────
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Nothing extra needed — APPDATA dirs are created by [Dirs] section
  end;
end;

// ── Uninstall: offer to remove user data ───────────────────────────────────
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
        '(database, screenshots, logs)' + #13#10#13#10 +
        '  Location: ' + AppDataPath + #13#10#13#10 +
        'Click Yes to delete all records, or No to keep them.',
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(AppDataPath, True, True, True);
      end;
    end;
  end;
end;

// ── GetUninstallString — locate existing uninstaller for upgrade ────────────
function GetUninstallString(): String;
var
  sUnInstPath, sUnInstallString: String;
begin
  sUnInstPath := ExpandConstant(
    'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{{{#MyAppGUID}}_is1');
  sUnInstallString := '';
  if not RegQueryStringValue(HKLM, sUnInstPath, 'UninstallString', sUnInstallString) then
    RegQueryStringValue(HKCU, sUnInstPath, 'UninstallString', sUnInstallString);
  Result := sUnInstallString;
end;
