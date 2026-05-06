param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$BackendUrl = "http://127.0.0.1:8787",
    [string]$FrontendUrl = "http://127.0.0.1:5173",
    [switch]$Headed,
    [switch]$KeepWorkspace
)

$ErrorActionPreference = "Stop"

function Invoke-WithConfigMutationLock {
    param(
        [string]$Root,
        [scriptblock]$Body
    )

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Root.ToLowerInvariant()))
    } finally {
        $sha.Dispose()
    }
    $hash = -join ($bytes[0..7] | ForEach-Object { $_.ToString("x2") })
    $mutex = [System.Threading.Mutex]::new($false, "Global\AegisChatBotConfigMutation-$hash")
    $lockTaken = $false
    try {
        $lockTaken = $mutex.WaitOne([TimeSpan]::FromSeconds(90))
        if (-not $lockTaken) {
            throw "Timed out waiting for config mutation lock."
        }
        & $Body
    } finally {
        if ($lockTaken) {
            $mutex.ReleaseMutex()
        }
        $mutex.Dispose()
    }
}

function Test-HttpReady {
    param([string]$Url)

    try {
        Invoke-WebRequest -UseBasicParsing $Url | Out-Null
        return $true
    } catch {
        return $false
    }
}

$Script = Join-Path $Root "scripts\e2e-web.mjs"
$PlaywrightCore = Join-Path $Root "node_modules\playwright-core"
if (-not (Test-Path -LiteralPath $Script)) {
    throw "E2E script is missing at $Script."
}
if (-not (Test-Path -LiteralPath $PlaywrightCore)) {
    throw "playwright-core is missing. Run npm install from $Root."
}
if (-not (Test-HttpReady "$BackendUrl/api/health")) {
    throw "Backend is not reachable at $BackendUrl."
}
if (-not (Test-HttpReady $FrontendUrl)) {
    throw "Frontend is not reachable at $FrontendUrl."
}

Write-Host "Aegis web UI E2E"
Write-Host "Project: $Root"
Write-Host "Frontend: $FrontendUrl"
Write-Host "Backend: $BackendUrl"

Invoke-WithConfigMutationLock -Root $Root -Body {
    $previousRoot = $env:AEGIS_E2E_ROOT
    $previousBackend = $env:AEGIS_E2E_BACKEND_URL
    $previousFrontend = $env:AEGIS_E2E_FRONTEND_URL
    $previousHeaded = $env:AEGIS_E2E_HEADED
    $previousKeep = $env:AEGIS_E2E_KEEP_WORKSPACE

    try {
        $env:AEGIS_E2E_ROOT = $Root
        $env:AEGIS_E2E_BACKEND_URL = $BackendUrl
        $env:AEGIS_E2E_FRONTEND_URL = $FrontendUrl
        $env:AEGIS_E2E_HEADED = if ($Headed) { "1" } else { "0" }
        $env:AEGIS_E2E_KEEP_WORKSPACE = if ($KeepWorkspace) { "1" } else { "0" }

        & node $Script
        if ($LASTEXITCODE -ne 0) {
            throw "Aegis web UI E2E failed."
        }
    } finally {
        $env:AEGIS_E2E_ROOT = $previousRoot
        $env:AEGIS_E2E_BACKEND_URL = $previousBackend
        $env:AEGIS_E2E_FRONTEND_URL = $previousFrontend
        $env:AEGIS_E2E_HEADED = $previousHeaded
        $env:AEGIS_E2E_KEEP_WORKSPACE = $previousKeep
    }
}
