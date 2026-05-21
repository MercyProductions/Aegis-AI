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

function Assert-DesktopUrlNormalizationGuards {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootDirectory
    )

    $platformText = Get-Content -Raw -LiteralPath (Join-Path $RootDirectory "src\Platform.cpp")
    $clientText = Get-Content -Raw -LiteralPath (Join-Path $RootDirectory "src\AegisClient.cpp")

    $issues = @()
    if ($platformText -notmatch 'StripKnownServiceEndpointPath') {
        $issues += "Platform.cpp must preserve reverse-proxy prefixes while trimming known endpoint suffixes."
    }
    if ($platformText -notmatch 'base \+ path_prefix') {
        $issues += "NormalizeHttpBaseUrl must return the normalized authority plus any preserved path prefix."
    }
    if ($platformText -notmatch '"v1"' -or $platformText -notmatch '"health"' -or $platformText -notmatch '"models"') {
        $issues += "Core URL normalization must strip known /v1, /health, and /models endpoint suffixes."
    }
    if ($platformText -notmatch '"api"' -or $platformText -notmatch '"health"' -or $platformText -notmatch '"config"' -or $platformText -notmatch '"tags"' -or $platformText -notmatch '"chat"') {
        $issues += "Backend/Ollama-style URL normalization must strip known /api endpoint suffixes."
    }
    if ($clientText -notmatch 'JoinUrl\(NormalizeHttpBaseUrl\(settings_\.api_base_url' -or
        $clientText -notmatch 'JoinUrl\(NormalizeHttpBaseUrl\(settings_\.core_api_base_url') {
        $issues += "AegisClient must build backend and Core URLs through NormalizeHttpBaseUrl plus JoinUrl."
    }

    if ($issues.Count -gt 0) {
        throw "Desktop URL normalization validation failed:`n - $($issues -join "`n - ")"
    }
}

Assert-DesktopUrlNormalizationGuards -RootDirectory $Root
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\test-desktop-contract.ps1") -Root $Root
if ($LASTEXITCODE -ne 0) {
    throw "Desktop source contract failed with exit code $LASTEXITCODE."
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
