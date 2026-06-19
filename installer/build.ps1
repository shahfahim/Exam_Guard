<#
.SYNOPSIS
    ExamGuard — Professional Windows Installer Build Script
    Builds ExamGuard.exe (PyInstaller) then packages it with Inno Setup 6.

.DESCRIPTION
    One-command build pipeline:
      1. Validate environment (Python, pip, PyInstaller, Inno Setup)
      2. Install / update Python dependencies
      3. Generate installer assets (ICO, BMP graphics)
      4. Bundle the app with PyInstaller → dist\ExamGuard\
      5. Compile the installer with Inno Setup → installer\Output\ExamGuardSetup_v*.exe

.PARAMETER Version
    Version string to embed (default: read from version.py).

.PARAMETER SkipPyInstaller
    Skip the PyInstaller step (use existing dist\ folder).

.PARAMETER SkipInnoSetup
    Skip the Inno Setup step (only build the PyInstaller bundle).

.PARAMETER Clean
    Delete dist\, build\, and installer\Output\ before building.

.EXAMPLE
    .\installer\build.ps1
    .\installer\build.ps1 -Clean
    .\installer\build.ps1 -SkipPyInstaller   # re-build installer only
    .\installer\build.ps1 -Version "4.1.0"

.NOTES
    Run from any directory — the script resolves paths automatically.
    Requires: Python 3.10+, pip, Inno Setup 6 (https://jrsoftware.org/isdl.php)
#>

[CmdletBinding()]
param(
    [string]$Version       = "",
    [switch]$SkipPyInstaller,
    [switch]$SkipInnoSetup,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$PSDefaultParameterValues["*:Encoding"] = "utf8"

# ── Resolve paths ─────────────────────────────────────────────────────────────
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# ── Console helpers ───────────────────────────────────────────────────────────
function Write-Header($msg) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor DarkGray
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor DarkGray
}
function Write-Step($msg)  { Write-Host "`n  >> $msg" -ForegroundColor Cyan }
function Write-OK($msg)    { Write-Host "     [OK]  $msg" -ForegroundColor Green }
function Write-WARN($msg)  { Write-Host "     [!!]  $msg" -ForegroundColor Yellow }
function Write-FAIL($msg)  { Write-Host "     [ERR] $msg" -ForegroundColor Red; exit 1 }

# ── Banner ────────────────────────────────────────────────────────────────────
Write-Header "ExamGuard Build Pipeline"
Write-Host "  Project: $ProjectRoot" -ForegroundColor Gray
Write-Host "  Date   : $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -ForegroundColor Gray

# ── Step 0: Read version from version.py if not supplied ─────────────────────
if ($Version -eq "") {
    $versionFile = Join-Path $ProjectRoot "version.py"
    if (Test-Path $versionFile) {
        $versionLine = Select-String -Path $versionFile -Pattern 'VERSION\s*=\s*"([^"]+)"' | Select-Object -First 1
        if ($versionLine) {
            $Version = $versionLine.Matches[0].Groups[1].Value
        }
    }
    if ($Version -eq "") { $Version = "4.0.0" }
}
Write-OK "Building version: $Version"

# ── Step 1: Validate environment ──────────────────────────────────────────────
Write-Step "Validating build environment..."

# Python
try {
    $pyOut = & python --version 2>&1
    Write-OK "Python  : $pyOut"
} catch {
    Write-FAIL "Python not found. Install Python 3.10+ from https://python.org"
}

# Check Python version >= 3.10
$pyVerLine = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1)
$pyMajor, $pyMinor = ($pyVerLine -split "\.") | Select-Object -First 2
if ([int]$pyMajor -lt 3 -or ([int]$pyMajor -eq 3 -and [int]$pyMinor -lt 10)) {
    Write-FAIL "Python 3.10 or newer is required. Found: $pyVerLine"
}

# pip
try {
    $pipOut = & pip --version 2>&1 | Select-Object -First 1
    Write-OK "pip     : $pipOut"
} catch {
    Write-FAIL "pip not found. Run: python -m ensurepip"
}

# PyInstaller
$pyinstallerExe = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $pyinstallerExe) {
    Write-WARN "PyInstaller not found — installing..."
    & pip install pyinstaller --quiet
    if ($LASTEXITCODE -ne 0) { Write-FAIL "Failed to install PyInstaller" }
    Write-OK "PyInstaller installed"
} else {
    $piVer = (& pyinstaller --version 2>&1)
    Write-OK "PyInstaller: $piVer"
}

# Inno Setup 6
$isccPaths = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$isccPath = $null
foreach ($p in $isccPaths) {
    if (Test-Path $p) { $isccPath = $p; break }
}

if (-not $isccPath) {
    Write-WARN "Inno Setup 6 not found."
    Write-Host ""
    Write-Host "  Please download and install it from:" -ForegroundColor Yellow
    Write-Host "  https://jrsoftware.org/isdl.php" -ForegroundColor Cyan
    Write-Host ""
    if (-not $SkipInnoSetup) {
        $choice = Read-Host "  Continue without building installer? [y/N]"
        if ($choice -ne "y" -and $choice -ne "Y") { exit 1 }
        $SkipInnoSetup = $true
    }
} else {
    Write-OK "Inno Setup: $isccPath"
}

# ── Step 2: Clean ─────────────────────────────────────────────────────────────
if ($Clean) {
    Write-Step "Cleaning previous build artifacts..."
    @("$ProjectRoot\dist", "$ProjectRoot\build", "$ScriptDir\Output") | ForEach-Object {
        if (Test-Path $_) {
            Remove-Item -Recurse -Force $_ -ErrorAction SilentlyContinue
            Write-OK "Removed: $_"
        }
    }
}

# ── Step 3: Install Python dependencies ───────────────────────────────────────
Write-Step "Installing Python dependencies..."
Push-Location $ProjectRoot
& pip install -r requirements.txt --quiet
& pip install pillow pyinstaller --quiet   # ensure asset generator deps
if ($LASTEXITCODE -ne 0) { Write-FAIL "pip install failed" }
Write-OK "All dependencies installed"
Pop-Location

# ── Step 4: Generate installer assets ─────────────────────────────────────────
Write-Step "Generating installer assets (ICO, BMP graphics)..."
$assetScript = Join-Path $ScriptDir "generate_assets.py"
& python $assetScript
if ($LASTEXITCODE -ne 0) { Write-FAIL "Asset generation failed" }

$icoPath = Join-Path $ScriptDir "assets\examguard.ico"
if (-not (Test-Path $icoPath)) { Write-FAIL "examguard.ico was not generated: $icoPath" }
Write-OK "Assets ready: $icoPath"

# ── Step 5: PyInstaller bundle ────────────────────────────────────────────────
if (-not $SkipPyInstaller) {
    Write-Step "Building application bundle with PyInstaller..."
    Push-Location $ProjectRoot
    & pyinstaller ExamGuard.spec --noconfirm --clean
    $exitCode = $LASTEXITCODE
    Pop-Location

    if ($exitCode -ne 0) { Write-FAIL "PyInstaller exited with code $exitCode" }

    $distExe = Join-Path $ProjectRoot "dist\ExamGuard\ExamGuard.exe"
    if (-not (Test-Path $distExe)) { Write-FAIL "Expected bundle not found: $distExe" }

    $sizeMB = [Math]::Round((Get-Item $distExe).Length / 1MB, 1)
    Write-OK "Bundle OK: dist\ExamGuard\ExamGuard.exe ($sizeMB MB)"
} else {
    Write-WARN "PyInstaller step skipped (--SkipPyInstaller)"
    $distExe = Join-Path $ProjectRoot "dist\ExamGuard\ExamGuard.exe"
    if (-not (Test-Path $distExe)) { Write-FAIL "Existing bundle not found — cannot skip PyInstaller step" }
}

# ── Step 6: Inno Setup installer ──────────────────────────────────────────────
if (-not $SkipInnoSetup -and $isccPath) {
    Write-Step "Building installer with Inno Setup 6..."
    $issFile     = Join-Path $ScriptDir "ExamGuard.iss"
    $outputDir   = Join-Path $ScriptDir "Output"
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

    & $isccPath $issFile /DMyAppVersion=$Version /O$outputDir
    if ($LASTEXITCODE -ne 0) { Write-FAIL "Inno Setup compiler failed" }

    $installerExe = Join-Path $outputDir "ExamGuardSetup_v$Version.exe"
    if (-not (Test-Path $installerExe)) { Write-FAIL "Installer not found: $installerExe" }

    $installerMB = [Math]::Round((Get-Item $installerExe).Length / 1MB, 1)
    Write-OK "Installer: $installerExe ($installerMB MB)"
} elseif ($SkipInnoSetup) {
    Write-WARN "Inno Setup step skipped (--SkipInnoSetup)"
}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host "  BUILD COMPLETE  —  ExamGuard v$Version" -ForegroundColor Green
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host ""
Write-Host "  App bundle  :  $ProjectRoot\dist\ExamGuard\" -ForegroundColor White
if (-not $SkipInnoSetup -and $isccPath) {
    Write-Host "  Installer   :  $ScriptDir\Output\ExamGuardSetup_v$Version.exe" -ForegroundColor White
}
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test:  .\installer\Output\ExamGuardSetup_v$Version.exe" -ForegroundColor Gray
Write-Host "  2. Sign:  signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 <installer.exe>" -ForegroundColor Gray
Write-Host "  3. Tag:   git tag v$Version && git push origin v$Version   (triggers GitHub Actions release)" -ForegroundColor Gray
Write-Host ""
