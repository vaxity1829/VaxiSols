# Build frozen Windows exe (requires: pip install -r requirements.txt pyinstaller)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install --upgrade pip pyinstaller | Out-Host
pyinstaller --noconfirm --clean VaxiSols.spec | Out-Host

Write-Host "Done: dist\VaxiSols.exe"
