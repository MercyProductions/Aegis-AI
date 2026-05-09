$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $Root ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $Root "backend\requirements.txt"
$FrontendDir = Join-Path $Root "frontend"
$BackendScript = Join-Path $Root "scripts\start-backend.ps1"
$FrontendScript = Join-Path $Root "scripts\start-frontend.ps1"
$LogsDir = Join-Path $Root "logs"
$BackendOut = Join-Path $LogsDir "backend.out.log"
$BackendErr = Join-Path $LogsDir "backend.err.log"
$FrontendOut = Join-Path $LogsDir "frontend.out.log"
$FrontendErr = Join-Path $LogsDir "frontend.err.log"
$ModelOut = Join-Path $LogsDir "ollama.out.log"
$ModelErr = Join-Path $LogsDir "ollama.err.log"
$EnvPath = Join-Path $Root ".env"
$EnvExample = Join-Path $Root ".env.example"
$BackendHealthUrl = "http://127.0.0.1:8787/api/health"
$BackendOpenApiUrl = "http://127.0.0.1:8787/openapi.json"
$RequiredBackendRoutes = @("/api/workspace/setup", "/api/auth/register")
$RequirePartialConfigUpdate = $true
$FrontendUrl = "http://127.0.0.1:5173"

function Test-HttpReady {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 4
    )

    try {
        Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec $TimeoutSeconds | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Get-HttpJson {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 4
    )

    try {
        $response = Invoke-WebRequest -UseBasicParsing $Url -Headers @{ Accept = "application/json" } -TimeoutSec $TimeoutSeconds
        if (-not $response.Content) {
            return $null
        }
        return $response.Content | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Normalize-PathForCompare {
    param([string]$Path)

    try {
        $resolved = Resolve-Path -LiteralPath $Path
        return $resolved.Path.TrimEnd("\", "/").ToLowerInvariant()
    } catch {
        return [System.IO.Path]::GetFullPath($Path).TrimEnd("\", "/").ToLowerInvariant()
    }
}

function Test-BackendReadyForRoot {
    param(
        [string]$Url,
        [string]$ExpectedRoot,
        [string[]]$RequiredRoutes = @(),
        [bool]$RequirePartialConfigUpdate = $false
    )

    $health = Get-HttpJson -Url $Url
    if ($null -eq $health -or -not $health.ready) {
        return $false
    }

    if (-not $health.project_root) {
        return $false
    }

    $actualRoot = Normalize-PathForCompare -Path $health.project_root
    $expected = Normalize-PathForCompare -Path $ExpectedRoot
    if ($actualRoot -ne $expected) {
        return $false
    }

    if ($RequiredRoutes.Count -eq 0 -and -not $RequirePartialConfigUpdate) {
        return $true
    }

    $openApiUrl = $Url -replace "/api/health$", "/openapi.json"
    $schema = Get-HttpJson -Url $openApiUrl
    if ($null -eq $schema -or $null -eq $schema.paths) {
        return $false
    }

    $routeNames = @($schema.paths.PSObject.Properties.Name)
    foreach ($route in $RequiredRoutes) {
        if ($routeNames -notcontains $route) {
            return $false
        }
    }

    if ($RequirePartialConfigUpdate -and -not (Test-OpenApiConfigUpdateSupportsPartial -Schema $schema)) {
        return $false
    }

    return $true
}

function Test-OpenApiConfigUpdateSupportsPartial {
    param([object]$Schema)

    if ($null -eq $Schema -or $null -eq $Schema.components -or $null -eq $Schema.components.schemas) {
        return $false
    }

    $configUpdate = $Schema.components.schemas.ConfigUpdateRequest
    if ($null -eq $configUpdate -or $null -eq $configUpdate.properties) {
        return $false
    }

    if ($null -eq $configUpdate.properties.default_workspace) {
        return $false
    }

    $requiredFields = @()
    if ($null -ne $configUpdate.required) {
        $requiredFields = @($configUpdate.required)
    }

    foreach ($field in @("assistant_name", "assistant_mission", "default_mode", "default_workspace")) {
        if ($requiredFields -contains $field) {
            return $false
        }
    }
    return $true
}

function Get-ListeningPids {
    param([int]$Port)

    $pattern = "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$"
    netstat -ano | ForEach-Object {
        if ($_ -match $pattern) {
            [int]$Matches[1]
        }
    } | Sort-Object -Unique
}

function Get-ProcessLineage {
    param([int]$ProcessId)

    $lineage = @()
    $seen = @{}
    $current = $ProcessId
    while ($current -gt 0 -and -not $seen.ContainsKey($current)) {
        $seen[$current] = $true
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $current" -ErrorAction SilentlyContinue
        if (-not $process) {
            break
        }
        $lineage += $process
        $current = [int]$process.ParentProcessId
    }
    return $lineage
}

function Test-ProcessLineageContainsPath {
    param(
        [int]$ProcessId,
        [string]$ExpectedPath
    )

    $expected = Normalize-PathForCompare -Path $ExpectedPath
    foreach ($process in Get-ProcessLineage -ProcessId $ProcessId) {
        $commandLine = [string]$process.CommandLine
        if ($commandLine.ToLowerInvariant().Contains($expected)) {
            return $true
        }
    }
    return $false
}

function Test-ProcessLineageLooksLikeAegisFrontend {
    param([int]$ProcessId)

    foreach ($process in Get-ProcessLineage -ProcessId $ProcessId) {
        $commandLine = ([string]$process.CommandLine).ToLowerInvariant()
        if ($commandLine.Contains("vite") -or $commandLine.Contains("npm-cli.js")) {
            return $true
        }
    }
    return $false
}

function Stop-ProcessLineage {
    param([int]$ProcessId)

    foreach ($process in Get-ProcessLineage -ProcessId $ProcessId) {
        $commandLine = ([string]$process.CommandLine).ToLowerInvariant()
        if ($commandLine.Contains("vite") -or $commandLine.Contains("npm-cli.js")) {
            Stop-Process -Id ([int]$process.ProcessId) -Force -ErrorAction SilentlyContinue
        }
    }
}

function Stop-AegisBackendOnPort {
    param([int]$Port)

    foreach ($listenerPid in Get-ListeningPids -Port $Port) {
        foreach ($process in Get-ProcessLineage -ProcessId $listenerPid) {
            if ($process -and $process.CommandLine -match "aegis_ai\.main:app" -and $process.CommandLine -match "--port\s+$Port") {
                Stop-Process -Id ([int]$process.ProcessId) -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Start-Sleep -Milliseconds 800
}

function Stop-MismatchedAegisBackend {
    param(
        [string]$Url,
        [string]$ExpectedRoot,
        [int]$Port
    )

    $health = Get-HttpJson -Url $Url
    if ($null -eq $health -or -not $health.project_root) {
        return
    }

    $actualRoot = Normalize-PathForCompare -Path $health.project_root
    $expected = Normalize-PathForCompare -Path $ExpectedRoot
    if ($actualRoot -eq $expected) {
        return
    }

    if ($health.app -ne "Auralith OS") {
        Write-Warning "Port $Port is already in use by another service. Stop it or change the Aegis backend port."
        return
    }

    Write-Warning "Port $Port is running Aegis from '$($health.project_root)', not '$ExpectedRoot'. Restarting that Aegis backend for this project."
    Stop-AegisBackendOnPort -Port $Port
}

function Test-BackendPortBlocked {
    param(
        [string]$Url,
        [string]$ExpectedRoot,
        [int]$Port
    )

    $listeners = @(Get-ListeningPids -Port $Port)
    if ($listeners.Count -eq 0) {
        return $false
    }

    $health = Get-HttpJson -Url $Url
    if ($health -and $health.app -eq "Auralith OS" -and $health.project_root) {
        $actualRoot = Normalize-PathForCompare -Path $health.project_root
        $expected = Normalize-PathForCompare -Path $ExpectedRoot
        if ($actualRoot -eq $expected) {
            Write-Warning "Port $Port is already owned by this project's Aegis backend, but it is not ready. Check $BackendOut and $BackendErr before restarting."
        } else {
            Write-Warning "Port $Port is still running Aegis from '$($health.project_root)'. Stop that backend before starting this project."
        }
        return $true
    }

    Write-Warning "Port $Port is already in use but did not return Auralith OS backend health JSON. Stop that process or change the Aegis backend port."
    return $true
}

function Test-FrontendReadyForRoot {
    param(
        [string]$Url,
        [string]$ExpectedFrontendDir,
        [int]$Port
    )

    if (-not (Test-HttpReady -Url $Url)) {
        return $false
    }

    $listeners = @(Get-ListeningPids -Port $Port)
    if ($listeners.Count -eq 0) {
        return $false
    }

    foreach ($listenerPid in $listeners) {
        if (Test-ProcessLineageContainsPath -ProcessId $listenerPid -ExpectedPath $ExpectedFrontendDir) {
            return $true
        }
    }
    return $false
}

function Stop-MismatchedAegisFrontend {
    param(
        [string]$Url,
        [string]$ExpectedFrontendDir,
        [int]$Port
    )

    if (-not (Test-HttpReady -Url $Url)) {
        return
    }

    $stopped = $false
    foreach ($listenerPid in Get-ListeningPids -Port $Port) {
        if (Test-ProcessLineageContainsPath -ProcessId $listenerPid -ExpectedPath $ExpectedFrontendDir) {
            return
        }
        if (Test-ProcessLineageLooksLikeAegisFrontend -ProcessId $listenerPid) {
            Write-Warning "Port $Port is running an Aegis UI from a different folder. Restarting the frontend for this project."
            Stop-ProcessLineage -ProcessId $listenerPid
            $stopped = $true
        }
    }

    if ($stopped) {
        Start-Sleep -Milliseconds 800
    } else {
        Write-Warning "Port $Port is already in use by another service. Stop it or change the Aegis frontend port."
    }
}

function Test-FrontendPortBlocked {
    param(
        [string]$ExpectedFrontendDir,
        [int]$Port
    )

    $listeners = @(Get-ListeningPids -Port $Port)
    if ($listeners.Count -eq 0) {
        return $false
    }

    foreach ($listenerPid in $listeners) {
        if (Test-ProcessLineageContainsPath -ProcessId $listenerPid -ExpectedPath $ExpectedFrontendDir) {
            Write-Warning "Port $Port is already owned by this project's frontend, but it is not ready. Check $FrontendOut and $FrontendErr before restarting."
            return $true
        }
    }

    Write-Warning "Port $Port is already in use by another service. Stop it or change the Aegis frontend port."
    return $true
}

function Wait-HttpReady {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpReady -Url $Url) {
            return $true
        }
        Start-Sleep -Milliseconds 800
    }
    return $false
}

function Wait-FrontendReadyForRoot {
    param(
        [string]$Url,
        [string]$ExpectedFrontendDir,
        [int]$Port,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-FrontendReadyForRoot -Url $Url -ExpectedFrontendDir $ExpectedFrontendDir -Port $Port) {
            return $true
        }
        Start-Sleep -Milliseconds 800
    }
    return $false
}

function Wait-BackendReadyForRoot {
    param(
        [string]$Url,
        [string]$ExpectedRoot,
        [string[]]$RequiredRoutes = @(),
        [bool]$RequirePartialConfigUpdate = $false,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-BackendReadyForRoot -Url $Url -ExpectedRoot $ExpectedRoot -RequiredRoutes $RequiredRoutes -RequirePartialConfigUpdate $RequirePartialConfigUpdate) {
            return $true
        }
        Start-Sleep -Milliseconds 800
    }
    return $false
}

function Get-EnvValue {
    param(
        [string]$Path,
        [string]$Name,
        [string]$Default
    )

    if (-not (Test-Path $Path)) {
        return $Default
    }

    $pattern = "^\s*$([regex]::Escape($Name))\s*=\s*(.*)\s*$"
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match $pattern) {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $Default
}

function Resolve-OllamaExe {
    $command = Get-Command ollama -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $localExe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path $localExe) {
        return $localExe
    }

    return $null
}

Write-Host ""
Write-Host "Auralith OS launcher" -ForegroundColor Cyan
Write-Host "Project: $Root"
Write-Host ""

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found on PATH."
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm was not found on PATH."
}

if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating Python virtual environment..."
    python -m venv $VenvDir
}

if (-not (Test-Path $EnvPath) -and (Test-Path $EnvExample)) {
    Copy-Item $EnvExample $EnvPath
}

$ModelApi = Get-EnvValue -Path $EnvPath -Name "AEGIS_MODEL_API" -Default "ollama"
$ModelEndpoint = Get-EnvValue -Path $EnvPath -Name "AEGIS_MODEL_ENDPOINT" -Default "http://127.0.0.1:11434"
$ModelName = Get-EnvValue -Path $EnvPath -Name "AEGIS_MODEL_NAME" -Default "qwen2.5-coder:7b"

if ($ModelApi.Trim().ToLowerInvariant() -eq "ollama" -and $ModelEndpoint -match "^http://(127\.0\.0\.1|localhost):11434/?$") {
    if (-not (Test-HttpReady -Url "http://127.0.0.1:11434/api/tags")) {
        $OllamaExe = Resolve-OllamaExe
        if ($OllamaExe) {
            Write-Host "Starting Ollama local model server..."
            Start-Process -FilePath $OllamaExe `
                -WorkingDirectory $Root `
                -ArgumentList @("serve") `
                -WindowStyle Hidden `
                -RedirectStandardOutput $ModelOut `
                -RedirectStandardError $ModelErr | Out-Null
            Wait-HttpReady -Url "http://127.0.0.1:11434/api/tags" -TimeoutSeconds 25 | Out-Null
        } else {
            Write-Warning "Ollama is configured but ollama.exe was not found. Install Ollama or change the local model settings in the UI."
        }
    }

    if (Test-HttpReady -Url "http://127.0.0.1:11434/api/tags") {
        Write-Host "Ollama is reachable for local model runtime. Configured model: $ModelName"
    }
}

Write-Host "Installing backend dependencies..."
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r $Requirements

if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "Installing frontend dependencies..."
    npm --prefix $FrontendDir install
}

if (-not (Test-BackendReadyForRoot -Url $BackendHealthUrl -ExpectedRoot $Root -RequiredRoutes $RequiredBackendRoutes -RequirePartialConfigUpdate $RequirePartialConfigUpdate)) {
    Stop-MismatchedAegisBackend -Url $BackendHealthUrl -ExpectedRoot $Root -Port 8787
}

if (-not (Test-BackendReadyForRoot -Url $BackendHealthUrl -ExpectedRoot $Root -RequiredRoutes $RequiredBackendRoutes -RequirePartialConfigUpdate $RequirePartialConfigUpdate)) {
    $health = Get-HttpJson -Url $BackendHealthUrl
    if ($health -and $health.project_root) {
        $actualRoot = Normalize-PathForCompare -Path $health.project_root
        $expectedRoot = Normalize-PathForCompare -Path $Root
        if ($actualRoot -eq $expectedRoot) {
            Write-Warning "Aegis backend on port 8787 is from this project but does not expose the expected API contract. Restarting it."
            Stop-AegisBackendOnPort -Port 8787
        }
    }
}

$backendPortBlocked = $false
if (-not (Test-BackendReadyForRoot -Url $BackendHealthUrl -ExpectedRoot $Root -RequiredRoutes $RequiredBackendRoutes -RequirePartialConfigUpdate $RequirePartialConfigUpdate)) {
    $backendPortBlocked = Test-BackendPortBlocked -Url $BackendHealthUrl -ExpectedRoot $Root -Port 8787
}

if (-not $backendPortBlocked -and -not (Test-BackendReadyForRoot -Url $BackendHealthUrl -ExpectedRoot $Root -RequiredRoutes $RequiredBackendRoutes -RequirePartialConfigUpdate $RequirePartialConfigUpdate)) {
    Write-Host "Starting Aegis API..."
    Start-Process -FilePath "powershell.exe" `
        -WorkingDirectory $Root `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$BackendScript`"") `
        -WindowStyle Hidden `
        -RedirectStandardOutput $BackendOut `
        -RedirectStandardError $BackendErr | Out-Null
}

if (-not (Test-FrontendReadyForRoot -Url $FrontendUrl -ExpectedFrontendDir $FrontendDir -Port 5173)) {
    Stop-MismatchedAegisFrontend -Url $FrontendUrl -ExpectedFrontendDir $FrontendDir -Port 5173
}

$frontendPortBlocked = $false
if (-not (Test-FrontendReadyForRoot -Url $FrontendUrl -ExpectedFrontendDir $FrontendDir -Port 5173)) {
    $frontendPortBlocked = Test-FrontendPortBlocked -ExpectedFrontendDir $FrontendDir -Port 5173
}

if (-not $frontendPortBlocked -and -not (Test-FrontendReadyForRoot -Url $FrontendUrl -ExpectedFrontendDir $FrontendDir -Port 5173)) {
    Write-Host "Starting Aegis UI..."
    Start-Process -FilePath "powershell.exe" `
        -WorkingDirectory $Root `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$FrontendScript`"") `
        -WindowStyle Hidden `
        -RedirectStandardOutput $FrontendOut `
        -RedirectStandardError $FrontendErr | Out-Null
}

$backendReady = Wait-BackendReadyForRoot -Url $BackendHealthUrl -ExpectedRoot $Root -RequiredRoutes $RequiredBackendRoutes -RequirePartialConfigUpdate $RequirePartialConfigUpdate -TimeoutSeconds 40
$frontendReady = Wait-FrontendReadyForRoot -Url $FrontendUrl -ExpectedFrontendDir $FrontendDir -Port 5173 -TimeoutSeconds 40

Write-Host ""
if (-not $backendReady) {
    Write-Warning "Backend did not become ready. Check $BackendOut and $BackendErr"
}

if (-not $frontendReady) {
    Write-Warning "Frontend did not become ready. Check $FrontendOut and $FrontendErr"
}

if ($backendReady -and $frontendReady) {
    Write-Host "Auralith OS is ready at $FrontendUrl" -ForegroundColor Green
    Start-Process $FrontendUrl
}
