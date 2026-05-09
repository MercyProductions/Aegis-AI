param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$BackendUrl = "http://127.0.0.1:8787",
    [string]$FrontendUrl = "http://127.0.0.1:5173"
)

$ErrorActionPreference = "Stop"

function Test-HttpReady {
    param([string]$Url)

    try {
        Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Invoke-NpmScript {
    param([string[]]$Arguments)

    & npm @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "npm $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Invoke-WebsiteScript {
    param(
        [string]$Name,
        [string[]]$Arguments = @()
    )

    $scriptPath = Join-Path $Root "scripts\$Name"
    if (-not (Test-Path -LiteralPath $scriptPath)) {
        throw "Website script is missing at $scriptPath."
    }

    & powershell -NoProfile -ExecutionPolicy Bypass -File $scriptPath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    $started = Get-Date
    Write-Host ""
    Write-Host "[$Name] Starting..." -ForegroundColor Cyan

    try {
        & $Command
        $elapsed = (Get-Date) - $started
        Write-Host "[$Name] Passed in $([math]::Round($elapsed.TotalSeconds, 1))s" -ForegroundColor Green
    } catch {
        $elapsed = (Get-Date) - $started
        Write-Host "[$Name] Failed after $([math]::Round($elapsed.TotalSeconds, 1))s" -ForegroundColor Red
        throw
    }
}

$Root = (Resolve-Path -LiteralPath $Root).Path
$BackendUrl = $BackendUrl.TrimEnd("/")
$FrontendUrl = $FrontendUrl.TrimEnd("/")
Set-Location -LiteralPath $Root

Write-Host ""
Write-Host "Auralith OS acceptance gate" -ForegroundColor Cyan
Write-Host "Project: $Root"
Write-Host "Frontend: $FrontendUrl"
Write-Host "Backend:  $BackendUrl"

Invoke-Step -Name "Validate frontend and backend" -Command {
    Invoke-NpmScript -Arguments @("run", "validate")
}

$backendHealthUrl = "$BackendUrl/api/health"
if (-not (Test-HttpReady -Url $backendHealthUrl) -or -not (Test-HttpReady -Url $FrontendUrl)) {
    throw "The live Auralith OS app is not reachable. Start it with .\launch.ps1, then rerun npm run acceptance:web. Checked $backendHealthUrl and $FrontendUrl."
}

Invoke-Step -Name "Runtime doctor" -Command {
    Invoke-WebsiteScript -Name "doctor-web.ps1" -Arguments @(
        "-Root", $Root,
        "-BackendUrl", $BackendUrl,
        "-FrontendUrl", $FrontendUrl
    )
}

Invoke-Step -Name "Backend smoke flow" -Command {
    Invoke-WebsiteScript -Name "smoke-web.ps1" -Arguments @(
        "-Root", $Root,
        "-BackendUrl", $BackendUrl,
        "-FrontendUrl", $FrontendUrl
    )
}

Invoke-Step -Name "Browser e2e flow" -Command {
    Invoke-WebsiteScript -Name "e2e-web.ps1" -Arguments @(
        "-Root", $Root,
        "-BackendUrl", $BackendUrl,
        "-FrontendUrl", $FrontendUrl
    )
}

Write-Host ""
Write-Host "Auralith OS acceptance gate passed." -ForegroundColor Green
