<#
.SYNOPSIS
    ExamGuard - Windows Installer Build Script

.DESCRIPTION
    Builds ExamGuard.exe with PyInstaller, then packages it with Inno Setup 6.
    Run from the ExamGuard project root OR the installer subfolder.

.PARAMETER Version
    Version string to embed. Default: read from version.py.

.PARAMETER SkipPyInstaller
    Skip PyInstaller step (reuse existing dist\ folder).

.PARAMETER SkipInnoSetup
    Skip Inno Setup step (bundle only).

.PARAMETER Clean
    Delete dist\, build\, installer\Output\ before building.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File installer\build.ps1
    powershell -ExecutionPolicy Bypass -File installer\build.ps1 -Clean
    powershell -ExecutionPolicy Bypass -File installer\build.ps1 -SkipPyInstaller
#>
[CmdletBinding()]
param(
    [string]$Version         = "",
    [switch]$SkipPyInstaller,
    [switch]$SkipInnoSetup,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Resolve paths regardless of where the script is called from
# ---------------------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# If the script lives inside installer\ the project root is one level up
if ((Split-Path -Leaf $ScriptDir) -eq "installer") {
    $ProjectRoot = Split-Path -Parent $ScriptDir
} else {
    $ProjectRoot = $ScriptDir
    $ScriptDir   = Join-Path $ProjectRoot "installer"
}

# ---------------------------------------------------------------------------
# Console helpers
# ---------------------------------------------------------------------------
function Write-Header {
    param([string]$msg)
    Write-Host ""
    Write-Host ("=" * 62) -ForegroundColor DarkGray
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host ("=" * 62) -ForegroundColor DarkGray
}
function Write-Step {
    param([string]$msg)
    Write-Host ""
    Write-Host "  >> $msg" -ForegroundColor Cyan
}
function Write-OK {
    param([string]$msg)
    Write-Host "     OK   $msg" -ForegroundColor Green
}
function Write-WARN {
    param([string]$msg)
    Write-Host "     WARN $msg" -ForegroundColor Yellow
}
function Write-FAIL {
    param([string]$msg)
    Write-Host "     ERR  $msg" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
Write-Header "ExamGuard Build Pipeline"
Write-Host "  Project : $ProjectRoot" -ForegroundColor Gray
Write-Host "  Date    : $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -ForegroundColor Gray

# ---------------------------------------------------------------------------
# Step 0: Read version from version.py if not supplied
# ---------------------------------------------------------------------------
if ($Version -eq "") {
    $vFile = Join-Path $ProjectRoot "version.py"
    if (Test-Path $vFile) {
        $vLine = Select-String -Path $vFile -Pattern 'VERSION\s*=\s*"([^"]+)"' |
                 Select-Object -First 1
        if ($vLine) {
            $Version = $vLine.Matches[0].Groups[1].Value
        }
    }
    if ($Version -eq "") { $Version = "4.0.0" }
}
Write-OK "Version : $Version"

# ---------------------------------------------------------------------------
# Step 1: Validate environment
# ---------------------------------------------------------------------------
Write-Step "Validating build environment..."

# Python
try {
    $pyOut = (& python --version 2>&1)
    Write-OK "Python  : $pyOut"
} catch {
    Write-FAIL "Python not found. Install Python 3.10+ from https://python.org"
}

# Python version >= 3.10
$pyVer = (& python -c "import sys; print(sys.version_info.major * 100 + sys.version_info.minor)" 2>&1)
if ([int]$pyVer -lt 310) {
    Write-FAIL "Python 3.10+ required. Found version number: $pyVer"
}

# pip
try {
    $pipOut = (& pip --version 2>&1) | Select-Object -First 1
    Write-OK "pip     : $pipOut"
} catch {
    Write-FAIL "pip not found. Run: python -m ensurepip"
}

# PyInstaller
$piExe = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $piExe) {
    Write-WARN "PyInstaller not found, installing..."
    & pip install pyinstaller --quiet
    if ($LASTEXITCODE -ne 0) { Write-FAIL "Failed to install PyInstaller" }
    Write-OK "PyInstaller installed"
}
# Always invoke via 'python -m PyInstaller' so PATH does not matter
$pyiCmd = { param($spec) & python -m PyInstaller $spec --noconfirm --clean }
$piVer = (& python -m PyInstaller --version 2>&1)
Write-OK "PyInstaller : $piVer"

# Inno Setup 6
$pf86     = [System.Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
$pf64     = $env:ProgramFiles
$isccList = @(
    "$pf86\Inno Setup 6\ISCC.exe",
    "$pf64\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$isccPath = $null
foreach ($p in $isccList) {
    if ($p -and (Test-Path $p)) { $isccPath = $p; break }
}

if (-not $isccPath) {
    Write-WARN "Inno Setup 6 not found."
    Write-Host "  Download from: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    if (-not $SkipInnoSetup) {
        $ans = Read-Host "  Build app bundle only without installer? [y/N]"
        if ($ans -ne "y" -and $ans -ne "Y") { exit 1 }
        $SkipInnoSetup = $true
    }
} else {
    Write-OK "Inno Setup : $isccPath"
}

# ---------------------------------------------------------------------------
# Step 2: Clean
# ---------------------------------------------------------------------------
if ($Clean) {
    Write-Step "Cleaning previous build artifacts..."
    $cleanDirs = @(
        (Join-Path $ProjectRoot "dist"),
        (Join-Path $ProjectRoot "build"),
        (Join-Path $ScriptDir   "Output")
    )
    foreach ($d in $cleanDirs) {
        if (Test-Path $d) {
            Remove-Item -Recurse -Force $d -ErrorAction SilentlyContinue
            Write-OK "Removed : $d"
        }
    }
}

# ---------------------------------------------------------------------------
# Step 3: Install Python dependencies
# ---------------------------------------------------------------------------
Write-Step "Installing Python dependencies..."
Push-Location $ProjectRoot
& pip install -r requirements.txt --quiet
& pip install pillow pyinstaller --quiet
if ($LASTEXITCODE -ne 0) { Write-FAIL "pip install failed" }
Write-OK "All dependencies installed"
Pop-Location

# ---------------------------------------------------------------------------
# Step 4: Generate installer assets (ICO + BMP graphics)
# ---------------------------------------------------------------------------
Write-Step "Generating installer assets..."
$assetScript = Join-Path $ScriptDir "generate_assets.py"
$env:PYTHONIOENCODING = "utf-8"
& python $assetScript
if ($LASTEXITCODE -ne 0) { Write-FAIL "Asset generation failed" }

$icoPath = Join-Path $ScriptDir "assets\examguard.ico"
if (-not (Test-Path $icoPath)) {
    Write-FAIL "Icon not generated: $icoPath"
}
Write-OK "Icon ready : $icoPath"

# ---------------------------------------------------------------------------
# Step 5: Build with PyInstaller
# ---------------------------------------------------------------------------
if (-not $SkipPyInstaller) {
    Write-Step "Building with PyInstaller..."
    Push-Location $ProjectRoot
    & python -m PyInstaller ExamGuard.spec --noconfirm --clean
    $pyiExit = $LASTEXITCODE
    Pop-Location

    if ($pyiExit -ne 0) { Write-FAIL "PyInstaller failed with exit code $pyiExit" }

    $distExe = Join-Path $ProjectRoot "dist\ExamGuard\ExamGuard.exe"
    if (-not (Test-Path $distExe)) {
        Write-FAIL "Bundle exe not found: $distExe"
    }
    $sizeMB = [Math]::Round((Get-Item $distExe).Length / 1MB, 1)
    Write-OK "Bundle  : dist\ExamGuard\ExamGuard.exe [$sizeMB MB]"
} else {
    Write-WARN "PyInstaller skipped - using existing dist folder"
    $distExe = Join-Path $ProjectRoot "dist\ExamGuard\ExamGuard.exe"
    if (-not (Test-Path $distExe)) {
        Write-FAIL "No existing bundle found at: $distExe"
    }
    Write-OK "Bundle exists: $distExe"
}

# ---------------------------------------------------------------------------
# Step 6: Build installer with Inno Setup
# ---------------------------------------------------------------------------
if ((-not $SkipInnoSetup) -and $isccPath) {
    Write-Step "Building installer with Inno Setup 6..."
    $issFile   = Join-Path $ScriptDir "ExamGuard.iss"
    $outputDir = Join-Path $ScriptDir "Output"
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

    & $isccPath $issFile "/DMyAppVersion=$Version" "/O$outputDir"
    if ($LASTEXITCODE -ne 0) { Write-FAIL "Inno Setup compiler failed" }

    $installerName = "ExamGuardSetup_v$Version.exe"
    $installerPath = Join-Path $outputDir $installerName
    if (-not (Test-Path $installerPath)) {
        Write-FAIL "Installer not found after build: $installerPath"
    }
    $instMB = [Math]::Round((Get-Item $installerPath).Length / 1MB, 1)
    Write-OK "Installer : $installerPath [$instMB MB]"
} elseif ($SkipInnoSetup) {
    Write-WARN "Inno Setup skipped - no installer produced"
} else {
    Write-WARN "Inno Setup not found - no installer produced"
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host ("=" * 62) -ForegroundColor Green
Write-Host "  BUILD COMPLETE   ExamGuard v$Version" -ForegroundColor Green
Write-Host ("=" * 62) -ForegroundColor Green
Write-Host ""
Write-Host "  App bundle : $ProjectRoot\dist\ExamGuard\" -ForegroundColor White
if ((-not $SkipInnoSetup) -and $isccPath) {
    Write-Host "  Installer  : $ScriptDir\Output\ExamGuardSetup_v$Version.exe" -ForegroundColor White
}
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test    : run installer\Output\ExamGuardSetup_v$Version.exe" -ForegroundColor Gray
Write-Host "  2. Sign    : signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 <exe>" -ForegroundColor Gray
Write-Host "  3. Release : git tag v$Version; git push origin v$Version" -ForegroundColor Gray
Write-Host ""
