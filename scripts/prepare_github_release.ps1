# Build exe and assemble "github repo release" (source tree + portable folder).
param(
    [switch] $SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

if (-not $SkipBuild) {
    Write-Host "Building dist\VaxiSols.exe ..."
    & (Join-Path $Root "build.ps1")
}

$releaseRoot = Join-Path $Root "github repo release"
if (Test-Path $releaseRoot) {
  Remove-Item -LiteralPath $releaseRoot -Recurse -Force
}
$srcOut = Join-Path $releaseRoot "VaxiSols-source"
$portableOut = Join-Path $releaseRoot "VaxiSols-portable"
New-Item -ItemType Directory -Path $srcOut -Force | Out-Null
New-Item -ItemType Directory -Path $portableOut -Force | Out-Null

robocopy $Root $srcOut /E /R:1 /W:1 `
  /XD ".venv" "build" "dist" "reference" "__pycache__" ".git" "github repo release" `
  /XF "*.pyc" "default.json.DO_NOT_COMMIT.backup" `
  | Out-Host
if ($LASTEXITCODE -ge 8) {
  throw "robocopy failed with exit code $LASTEXITCODE"
}

# Never ship personal config in the source bundle
$badCfg = Join-Path $srcOut "config\default.json"
if (Test-Path $badCfg) {
  Remove-Item -LiteralPath $badCfg -Force
}
$ex = Join-Path $srcOut "config\default.json.example"
if (-not (Test-Path $ex)) {
  throw "Missing config/default.json.example in repo root; cannot prepare release."
}

Copy-Item -LiteralPath (Join-Path $Root "dist\VaxiSols.exe") -Destination $portableOut -Force

$preadme = @'
VaxiSols - portable build (Windows)

1. Place VaxiSols.exe in any folder you prefer (for example Desktop\VaxiSols).
2. Copy config\default.json.example from the GitHub source zip/repo into that folder as config\default.json
   (create the config folder next to the exe), OR launch once and configure accounts/webhooks from the UI; the app creates config\default.json beside the exe when you save.
3. Double-click VaxiSols.exe.

Optional OCR: install Tesseract on PATH if you enable OCR assist in Settings.

Unofficial tool - use at your own risk.
'@
Set-Content -LiteralPath (Join-Path $portableOut "README.txt") -Value $preadme -Encoding UTF8

New-Item -ItemType Directory -Path (Join-Path $portableOut "config") -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $Root "config\default.json.example") -Destination (Join-Path $portableOut "config\default.json.example") -Force

Write-Host ""
Write-Host "Release folders ready:"
Write-Host "  Source (for GitHub push): $srcOut"
Write-Host "  Portable zip contents:    $portableOut"
