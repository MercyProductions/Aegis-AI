param(
    [switch]$Smoke
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"

if (-not (Test-Path $VsWhere)) {
    throw "vswhere.exe was not found. Install Visual Studio with C++ desktop tools."
}

$MSBuild = & $VsWhere -latest -requires Microsoft.Component.MSBuild -find "MSBuild\**\Bin\MSBuild.exe" | Select-Object -First 1
if (-not $MSBuild) {
    throw "MSBuild was not found. Install Visual Studio with C++ desktop tools."
}

& $MSBuild "$Root\AegisChatBotDesktop.sln" /p:Configuration=Release /p:Platform=x64 /m
if ($LASTEXITCODE -ne 0) {
    throw "MSBuild failed with exit code $LASTEXITCODE."
}

Write-Host "Built: $Root\x64\Release\AegisChatBotDesktop.exe"

if ($Smoke) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\scripts\smoke-desktop.ps1"
    if ($LASTEXITCODE -ne 0) {
        throw "Desktop smoke check failed with exit code $LASTEXITCODE."
    }
}
