param(
    [int]$Port = 8797,
    [int]$ApiIterations = 1,
    [switch]$RunScaffoldSmoke,
    [switch]$RunDesktopSmoke,
    [switch]$RunForeignHealthSmoke,
    [switch]$RunForeignProjectRootSmoke,
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptRoot
$backendRoot = Join-Path $repoRoot "website"
$backendScript = Join-Path $backendRoot "scripts\start-backend.ps1"
$python = Join-Path $backendRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $backendScript)) {
    throw "Local backend start script was not found at $backendScript."
}
if (-not (Test-Path -LiteralPath $python)) {
    throw "Local backend virtual environment is missing at $python."
}

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputDir = Join-Path $repoRoot "stress-artifacts\local-backend-$stamp"
}

function Get-AegisHealth {
    param([Parameter(Mandatory = $true)][string]$BaseUrl)

    try {
        return Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/health" -TimeoutSec 2
    }
    catch {
        return $null
    }
}

function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    return [System.IO.Path]::GetFullPath($Path).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
}

function Get-HealthProjectRoot {
    param([Parameter(Mandatory = $true)]$Health)

    if ($null -eq $Health) {
        return ""
    }

    $property = $Health.PSObject.Properties["project_root"]
    if ($null -eq $property -or $null -eq $property.Value) {
        return ""
    }

    return [string]$property.Value
}

function Stop-ForeignHealthSmokeServer {
    param($Job)

    if ($null -eq $Job) {
        return
    }

    Stop-Job $Job -ErrorAction SilentlyContinue | Out-Null
    Remove-Job $Job -Force -ErrorAction SilentlyContinue | Out-Null
}

function Start-ForeignHealthSmokeServer {
    param(
        [Parameter(Mandatory = $true)][int]$StartPort,
        [string]$ProjectRoot = ""
    )

    $payloadObject = @{
        ready = $true
        ok = $true
        app = "foreign-aegis-smoke"
    }
    if (-not [string]::IsNullOrWhiteSpace($ProjectRoot)) {
        $payloadObject.project_root = $ProjectRoot
    }
    $payload = $payloadObject | ConvertTo-Json -Compress

    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        $candidatePort = $StartPort + $attempt
        $candidateUrl = "http://127.0.0.1:$candidatePort"
        if ($null -ne (Get-AegisHealth -BaseUrl $candidateUrl)) {
            continue
        }

        $job = Start-Job -ScriptBlock {
            param([int]$ListenPort, [string]$HealthPayload)

            $listener = [System.Net.HttpListener]::new()
            $listener.Prefixes.Add("http://127.0.0.1:$ListenPort/")
            $listener.Start()
            try {
                while ($listener.IsListening) {
                    $context = $listener.GetContext()
                    $response = $context.Response
                    $bytes = [System.Text.Encoding]::UTF8.GetBytes($HealthPayload)
                    $response.StatusCode = 200
                    $response.ContentType = "application/json"
                    $response.OutputStream.Write($bytes, 0, $bytes.Length)
                    $response.Close()
                }
            }
            finally {
                $listener.Close()
            }
        } -ArgumentList $candidatePort, $payload

        $ready = $false
        for ($wait = 0; $wait -lt 20; $wait++) {
            $health = Get-AegisHealth -BaseUrl $candidateUrl
            if ($null -ne $health -and [bool]$health.ready) {
                $healthProjectRoot = Get-HealthProjectRoot -Health $health
                if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
                    if ([string]::IsNullOrWhiteSpace($healthProjectRoot)) {
                        $ready = $true
                        break
                    }
                }
                elseif (-not [string]::IsNullOrWhiteSpace($healthProjectRoot)) {
                    $actualRoot = Get-NormalizedPath $healthProjectRoot
                    $expectedFakeRoot = Get-NormalizedPath $ProjectRoot
                    if ([string]::Equals($actualRoot, $expectedFakeRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                        $ready = $true
                        break
                    }
                }
            }
            Start-Sleep -Milliseconds 250
        }

        if ($ready) {
            return @{
                Job = $job
                Port = $candidatePort
                Url = $candidateUrl
            }
        }

        $jobErrors = Receive-Job $job -Keep -ErrorAction SilentlyContinue 2>&1 | Out-String
        Stop-ForeignHealthSmokeServer -Job $job
        if (-not [string]::IsNullOrWhiteSpace($jobErrors)) {
            Write-Host "Could not start foreign health smoke on $candidateUrl`: $($jobErrors.Trim())"
        }
    }

    throw "Could not start foreign health collision smoke server on any port from $StartPort."
}

$expectedRoot = Get-NormalizedPath $backendRoot
$selectedPort = $Port
$baseUrl = ""
$startedProcess = $null
$reuseExisting = $false
$foreignHealthJob = $null
$foreignHealthPort = 0
$foreignSmokeLabel = ""

try {
    if ($RunForeignHealthSmoke -and $RunForeignProjectRootSmoke) {
        throw "Use either -RunForeignHealthSmoke or -RunForeignProjectRootSmoke, not both."
    }

    if ($RunForeignHealthSmoke -or $RunForeignProjectRootSmoke) {
        $fakeProjectRoot = ""
        $foreignSmokeLabel = "foreign health"
        if ($RunForeignProjectRootSmoke) {
            $fakeProjectRoot = Join-Path $env:TEMP "aegis-foreign-project-root-smoke"
            $foreignSmokeLabel = "foreign project-root"
        }
        $foreignHealth = Start-ForeignHealthSmokeServer -StartPort $Port -ProjectRoot $fakeProjectRoot
        $foreignHealthJob = $foreignHealth.Job
        $foreignHealthPort = [int]$foreignHealth.Port
        $selectedPort = $foreignHealthPort
        Write-Host "$foreignSmokeLabel collision smoke active on $($foreignHealth.Url)"
    }

    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        $candidateUrl = "http://127.0.0.1:$selectedPort"
        $health = Get-AegisHealth -BaseUrl $candidateUrl
        if ($null -eq $health) {
            $baseUrl = $candidateUrl
            break
        }

        $healthProjectRoot = Get-HealthProjectRoot -Health $health
        if ([string]::IsNullOrWhiteSpace($healthProjectRoot)) {
            Write-Host "Port $selectedPort returned health without project_root; treating it as foreign and trying the next port."
            $selectedPort++
            continue
        }

        $actualRoot = Get-NormalizedPath $healthProjectRoot
        if ([string]::Equals($actualRoot, $expectedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            $baseUrl = $candidateUrl
            $reuseExisting = $true
            break
        }

        Write-Host "Port $selectedPort is occupied by another Aegis backend: $actualRoot"
        $selectedPort++
    }

    if ([string]::IsNullOrWhiteSpace($baseUrl)) {
        throw "Could not find a free local backend stress port starting from $Port."
    }
    if (($RunForeignHealthSmoke -or $RunForeignProjectRootSmoke) -and $selectedPort -eq $foreignHealthPort) {
        throw "$foreignSmokeLabel collision smoke was not skipped; selected port is still $selectedPort."
    }
    if ($RunForeignHealthSmoke -or $RunForeignProjectRootSmoke) {
        Write-Host "$foreignSmokeLabel collision smoke skipped port $foreignHealthPort and selected $baseUrl"
    }
}
catch {
    Stop-ForeignHealthSmokeServer -Job $foreignHealthJob
    throw
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$backendStdout = Join-Path $OutputDir "backend.stdout.log"
$backendStderr = Join-Path $OutputDir "backend.stderr.log"

try {
    if ($reuseExisting) {
        Write-Host "Reusing local backend on $baseUrl"
    }
    else {
        Write-Host "Starting local backend on $baseUrl"
        $backendCommand = "-NoProfile -ExecutionPolicy Bypass -File `"$backendScript`" -Port $selectedPort"
        $startedProcess = Start-Process `
            -FilePath "powershell.exe" `
            -ArgumentList $backendCommand `
            -WorkingDirectory $backendRoot `
            -RedirectStandardOutput $backendStdout `
            -RedirectStandardError $backendStderr `
            -PassThru `
            -WindowStyle Hidden

        $ready = $false
        for ($i = 0; $i -lt 50; $i++) {
            $health = Get-AegisHealth -BaseUrl $baseUrl
            if ($null -ne $health -and [bool]$health.ready) {
                $healthProjectRoot = Get-HealthProjectRoot -Health $health
                if ([string]::IsNullOrWhiteSpace($healthProjectRoot)) {
                    throw "Backend on $baseUrl became ready but did not report project_root."
                }
                $actualRoot = Get-NormalizedPath $healthProjectRoot
                if (-not [string]::Equals($actualRoot, $expectedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                    throw "Backend on $baseUrl reported '$actualRoot' instead of '$expectedRoot'."
                }
                $ready = $true
                break
            }
            Start-Sleep -Milliseconds 500
        }
        if (-not $ready) {
            $stderr = if (Test-Path -LiteralPath $backendStderr) { Get-Content -LiteralPath $backendStderr -Raw -ErrorAction SilentlyContinue } else { "" }
            $stdout = if (Test-Path -LiteralPath $backendStdout) { Get-Content -LiteralPath $backendStdout -Raw -ErrorAction SilentlyContinue } else { "" }
            $tail = (($stderr, $stdout) -join "`n").Trim()
            if ($tail.Length -gt 1200) {
                $tail = $tail.Substring($tail.Length - 1200)
            }
            throw "Local backend on $baseUrl did not become ready. Backend logs: $tail"
        }
    }

    $stressArgs = @{
        BackendUrl = $baseUrl
        ExpectedProjectRoot = $expectedRoot
        ApiIterations = $ApiIterations
        OutputDir = $OutputDir
    }
    if ($RunScaffoldSmoke) {
        $stressArgs.RunScaffoldSmoke = $true
    }
    if ($RunDesktopSmoke) {
        $stressArgs.RunDesktopSmoke = $true
    }

    & (Join-Path $scriptRoot "stress-aegis.ps1") @stressArgs
}
finally {
    Stop-ForeignHealthSmokeServer -Job $foreignHealthJob
    if ($null -ne $startedProcess) {
        $backendProcesses = Get-CimInstance Win32_Process | Where-Object {
            $null -ne $_.CommandLine `
                -and $_.CommandLine.Contains($backendRoot) `
                -and $_.CommandLine -match "--port\s+$selectedPort"
        }
        foreach ($backendProcess in @($backendProcesses)) {
            Write-Host "Stopping local backend child process $($backendProcess.ProcessId)"
            Stop-Process -Id $backendProcess.ProcessId -Force -ErrorAction SilentlyContinue
        }
        if (-not $startedProcess.HasExited) {
            Write-Host "Stopping local backend launcher process $($startedProcess.Id)"
            Stop-Process -Id $startedProcess.Id -Force -ErrorAction SilentlyContinue
        }
        Wait-Process -Id $startedProcess.Id -Timeout 5 -ErrorAction SilentlyContinue
    }
}
