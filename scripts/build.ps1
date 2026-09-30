# Builds dist\Bel\Bel.exe (a folder build, so it starts fast at logon).
#
#   powershell -ExecutionPolicy Bypass -File scripts\build.ps1

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

python -m PyInstaller --noconfirm --clean --windowed --name Bel `
    --icon assets\bel.ico --paths src `
    --add-data "assets;assets" `
    src\main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Write-Host "Built $repo\dist\Bel\Bel.exe"
