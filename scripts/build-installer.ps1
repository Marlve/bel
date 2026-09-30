# Builds dist\installer\Bel-Setup-<version>.exe (runs build.ps1 first).
# Needs Inno Setup 6: winget install JRSoftware.InnoSetup
#
#   powershell -ExecutionPolicy Bypass -File scripts\build-installer.ps1

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$iscc = @(
    (Get-Command iscc -ErrorAction SilentlyContinue).Source
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found - run: winget install JRSoftware.InnoSetup" }

& (Join-Path $PSScriptRoot 'build.ps1')
# src\version.py is the one place the version lives; Bel checks updates against it.
$version = (Select-String -Path src\version.py -Pattern 'VERSION = "(.+)"').Matches[0].Groups[1].Value
& $iscc "/DAppVersion=$version" installer\bel.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
