# NAI Tag Classifier Build Script
# PowerShell version for Windows

param(
    [switch]$SkipNpm,
    [switch]$Help
)

if ($Help) {
    Write-Host "Usage: .\build.ps1 [-SkipNpm] [-Help]"
    Write-Host "  -SkipNpm  Skip npm build step"
    Write-Host "  -Help     Show this help"
    exit 0
}

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=============================================="
Write-Host "NAI Tag Classifier Build"
Write-Host "=============================================="

# Activate venv
$venvActivate = Join-Path $Root "venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    Write-Host "[1/4] Activating Python virtual environment..."
    . $venvActivate
} else {
    Write-Host "Warning: venv not found at $venvActivate"
}

# Check PyInstaller
Write-Host "[2/4] Checking PyInstaller..."
$pyinstaller = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $pyinstaller) {
    Write-Host "Installing PyInstaller..."
    pip install pyinstaller --quiet
}

# Build viewer-ui
if (-not $SkipNpm) {
    Write-Host "[3/4] Building viewer-ui..."
    Push-Location (Join-Path $Root "viewer-ui")
    npm run build
    Pop-Location
} else {
    Write-Host "[3/4] Skipping npm build..."
}

# Check viewer-ui/dist exists
$distPath = Join-Path $Root "viewer-ui\dist"
if (-not (Test-Path $distPath)) {
    Write-Error "viewer-ui/dist not found. Run npm build first."
    exit 1
}

# Run PyInstaller
Write-Host "[4/4] Running PyInstaller..."
Push-Location $Root
pyinstaller build.spec --noconfirm
Pop-Location

Write-Host ""
Write-Host "=============================================="
Write-Host "Build Complete!"
Write-Host "=============================================="
Write-Host "Output: dist\nai-classifier-server.exe"
Write-Host ""
Write-Host "Run with: .\dist\nai-classifier-server.exe"
Write-Host "=============================================="
