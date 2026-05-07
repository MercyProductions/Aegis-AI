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
    Invoke-NpmScript -Arguments @("run", "doctor:web")
}

Invoke-Step -Name "Backend smoke flow" -Command {
    Invoke-NpmScript -Arguments @("run", "smoke:web")
}

Invoke-Step -Name "Browser e2e flow" -Command {
    Invoke-NpmScript -Arguments @("run", "e2e:web")
}

Write-Host ""
Write-Host "Auralith OS acceptance gate passed." -ForegroundColor Green
