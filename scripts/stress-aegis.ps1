param(
    [string]$BackendUrl = "http://127.0.0.1:8787",
    [int]$ApiIterations = 60,
    [switch]$RunDesktopSmoke,
    [string]$OutputDir = "",
    [string]$ExePath = "",
    [int]$DesktopSetupWaitSeconds = 4,
    [int]$DesktopDashboardWaitSeconds = 16
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptRoot

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputDir = Join-Path $repoRoot "stress-artifacts\$stamp"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$BackendUrl = $BackendUrl.TrimEnd("/")
$workspaceRoot = Join-Path $env:TEMP "aegis-stress-workspace"
$planTarget = Join-Path $workspaceRoot "stress-console"
New-Item -ItemType Directory -Force -Path $workspaceRoot | Out-Null

function Invoke-AegisJsonGet {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSec = 20
    )

    $response = Invoke-WebRequest -UseBasicParsing -Method Get -Uri $Url -TimeoutSec $TimeoutSec
    if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 300) {
        throw "GET $Url returned HTTP $($response.StatusCode)"
    }
    return $response.Content | ConvertFrom-Json
}

function Invoke-AegisJsonPost {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)]$Body,
        [int]$TimeoutSec = 30
    )

    $json = $Body | ConvertTo-Json -Depth 12
    $response = Invoke-WebRequest `
        -UseBasicParsing `
        -Method Post `
        -Uri $Url `
        -ContentType "application/json" `
        -Body $json `
        -TimeoutSec $TimeoutSec

    if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 300) {
        throw "POST $Url returned HTTP $($response.StatusCode)"
    }
    return $response.Content | ConvertFrom-Json
}

function Assert-Aegis {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Get-Percentile {
    param(
        [Parameter(Mandatory = $true)][double[]]$Values,
        [Parameter(Mandatory = $true)][double]$Percentile
    )

    if ($Values.Count -eq 0) {
        return 0
    }

    $sorted = $Values | Sort-Object
    $index = [Math]::Ceiling(($Percentile / 100.0) * $sorted.Count) - 1
    $index = [Math]::Max(0, [Math]::Min($sorted.Count - 1, $index))
    return [Math]::Round([double]$sorted[$index], 2)
}

function Measure-AegisCall {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    $sw = [Diagnostics.Stopwatch]::StartNew()
    $result = & $Action
    $sw.Stop()
    return @{
        Result = $result
        Milliseconds = [Math]::Round($sw.Elapsed.TotalMilliseconds, 2)
    }
}

Write-Host "Aegis stress test"
Write-Host "Backend: $BackendUrl"
Write-Host "Iterations: $ApiIterations"
Write-Host "Output: $OutputDir"

$health = Invoke-AegisJsonGet "$BackendUrl/api/health"
Assert-Aegis ([bool]$health.ready) "Backend health endpoint is not ready."

$presetIdsToRequire = @(
    "cpp-msvc-console-sln",
    "cpp-imgui-win32-dx11",
    "windows-kernel-driver-controller",
    "static-html-site",
    "node-fullstack-js"
)

$durations = New-Object System.Collections.Generic.List[double]
$failures = New-Object System.Collections.Generic.List[string]
$lastPresetCount = 0
$lastCppPlan = ""
$lastFullStackPlan = ""

for ($i = 1; $i -le $ApiIterations; $i++) {
    try {
        $call = Measure-AegisCall {
            $health = Invoke-AegisJsonGet "$BackendUrl/api/health"
            Assert-Aegis ([bool]$health.ready) "Iteration $i health check was not ready."

            $config = Invoke-AegisJsonGet "$BackendUrl/api/config"
            Assert-Aegis (-not [string]::IsNullOrWhiteSpace([string]$config.model_name)) "Iteration $i config did not include model_name."

            $presets = Invoke-AegisJsonGet "$BackendUrl/api/project-builder/presets"
            $presetCount = @($presets).Count
            Assert-Aegis ($presetCount -ge 30) "Iteration $i expected at least 30 project presets, found $presetCount."

            $presetIds = @($presets | ForEach-Object { $_.id })
            foreach ($presetId in $presetIdsToRequire) {
                Assert-Aegis ($presetIds -contains $presetId) "Iteration $i missing required preset '$presetId'."
            }

            $encodedWorkspace = [Uri]::EscapeDataString($workspaceRoot)
            $profile = Invoke-AegisJsonGet "$BackendUrl/api/workspace/profile?workspace_root=$encodedWorkspace"
            Assert-Aegis ([string]$profile.workspace_root -eq $workspaceRoot) "Iteration $i workspace profile returned an unexpected root."

            $contract = Invoke-AegisJsonGet "$BackendUrl/api/chat/stream/contract"
            Assert-Aegis ([string]$contract.endpoint -eq "/api/chat/stream") "Iteration $i stream contract endpoint changed unexpectedly."

            $cppPlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "Create a C++ Visual Studio console app called Stress Console that prints hello world and waits for Enter."
                workspace_root = $workspaceRoot
                preferred_target_path = $planTarget
            }
            Assert-Aegis ([bool]$cppPlan.ok) "Iteration $i C++ plan did not complete successfully."
            Assert-Aegis ([string]$cppPlan.preset.id -eq "cpp-msvc-console-sln") "Iteration $i C++ plan selected '$($cppPlan.preset.id)' instead of cpp-msvc-console-sln."
            $cppProjectName = [string]$cppPlan.project_name

            $fullStackPlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "Create a full-stack CRUD dashboard app called Stress Tasks with frontend, backend, tests, and validation."
                workspace_root = $workspaceRoot
                preferred_target_path = (Join-Path $workspaceRoot "stress-tasks")
            }
            Assert-Aegis ([bool]$fullStackPlan.ok) "Iteration $i full-stack plan did not complete successfully."
            Assert-Aegis ([string]$fullStackPlan.preset.id -eq "node-fullstack-js") "Iteration $i full-stack plan selected '$($fullStackPlan.preset.id)' instead of node-fullstack-js."
            $fullStackProjectName = [string]$fullStackPlan.project_name

            return @{
                preset_count = $presetCount
                cpp_plan = $cppProjectName
                full_stack_plan = $fullStackProjectName
            }
        }

        $durations.Add([double]$call.Milliseconds)
        $lastPresetCount = [int]$call.Result.preset_count
        $lastCppPlan = [string]$call.Result.cpp_plan
        $lastFullStackPlan = [string]$call.Result.full_stack_plan
        if (($i % 10) -eq 0 -or $i -eq $ApiIterations) {
            Write-Host "API iteration $i/$ApiIterations passed in $($call.Milliseconds) ms"
        }
    }
    catch {
        $message = "Iteration $i failed: $($_.Exception.Message)"
        $failures.Add($message)
        Write-Warning $message
    }
}

$desktopSmoke = $null
if ($RunDesktopSmoke) {
    $smokeScript = Join-Path $scriptRoot "smoke-desktop.ps1"
    if (-not (Test-Path -LiteralPath $smokeScript)) {
        throw "Could not find smoke-desktop.ps1 at $smokeScript"
    }

    $smokeOutput = Join-Path $OutputDir "desktop-smoke"
    $smokeArgs = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $smokeScript,
        "-OutputDir",
        $smokeOutput,
        "-SetupWaitSeconds",
        $DesktopSetupWaitSeconds,
        "-DashboardWaitSeconds",
        $DesktopDashboardWaitSeconds
    )

    if (-not [string]::IsNullOrWhiteSpace($ExePath)) {
        $smokeArgs += @("-ExePath", $ExePath)
    }

    Write-Host "Running desktop smoke test..."
    & powershell @smokeArgs
    $smokeExitCode = $LASTEXITCODE
    $desktopSmoke = @{
        exit_code = $smokeExitCode
        output_dir = $smokeOutput
    }

    if ($smokeExitCode -ne 0) {
        throw "Desktop smoke test failed with exit code $smokeExitCode."
    }
}

$summary = [ordered]@{
    ok = ($failures.Count -eq 0)
    backend_url = $BackendUrl
    api_iterations = $ApiIterations
    failures = @($failures)
    duration_ms = @{
        average = if ($durations.Count -gt 0) { [Math]::Round(($durations | Measure-Object -Average).Average, 2) } else { 0 }
        p95 = Get-Percentile -Values @($durations) -Percentile 95
        max = if ($durations.Count -gt 0) { [Math]::Round(($durations | Measure-Object -Maximum).Maximum, 2) } else { 0 }
    }
    preset_count = $lastPresetCount
    required_presets = $presetIdsToRequire
    last_cpp_plan = $lastCppPlan
    last_full_stack_plan = $lastFullStackPlan
    desktop_smoke = $desktopSmoke
    output_dir = $OutputDir
}

$summaryPath = Join-Path $OutputDir "summary.json"
$summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
$summary | ConvertTo-Json -Depth 12

if (-not $summary.ok) {
    exit 1
}
