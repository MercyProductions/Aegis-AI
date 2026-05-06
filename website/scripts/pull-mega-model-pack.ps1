param(
    [double]$MinimumFreeGb = 24,
    [string]$LogSubfolder = "model-pulls-mega"
)

$ErrorActionPreference = "Continue"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$LogsDir = Join-Path $Root "logs\$LogSubfolder"
$SummaryPath = Join-Path $LogsDir "summary.json"

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

function Resolve-OllamaExe {
    $command = Get-Command ollama -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $localExe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path $localExe) {
        return $localExe
    }

    throw "ollama.exe was not found on PATH or in LocalAppData."
}

function ConvertTo-SafeName {
    param([string]$Name)
    return ($Name -replace "[^a-zA-Z0-9_.-]", "_")
}

function Get-FreeGbForPath {
    param([string]$Path)
    $root = [System.IO.Path]::GetPathRoot((Resolve-Path $Path).Path)
    $driveName = $root.TrimEnd("\").TrimEnd(":")
    $drive = Get-PSDrive -Name $driveName -ErrorAction Stop
    return [math]::Round($drive.Free / 1GB, 2)
}

function Get-InstalledModelNames {
    param([string]$OllamaExe)
    $names = New-Object System.Collections.Generic.HashSet[string]
    try {
        $lines = & $OllamaExe list
        foreach ($line in $lines | Select-Object -Skip 1) {
            $name = (($line -split "\s+")[0]).Trim()
            if (-not $name) {
                continue
            }
            [void]$names.Add($name)
            if ($name.EndsWith(":latest")) {
                [void]$names.Add($name.Substring(0, $name.Length - 7))
            } elseif (-not $name.Contains(":")) {
                [void]$names.Add("$name`:latest")
            }
        }
    } catch {
        Write-Warning "Could not inspect installed Ollama models: $_"
    }
    return $names
}

$OllamaExe = Resolve-OllamaExe

$Models = @(
    @{ name = "qwen3-coder:30b"; lane = "agentic_code"; size_gb = 19.0 },
    @{ name = "gemma3:27b"; lane = "large_multilingual_vision"; size_gb = 17.0 },
    @{ name = "llama3.2-vision:11b"; lane = "vision"; size_gb = 7.9 },
    @{ name = "qwen3:30b"; lane = "large_reasoning"; size_gb = 19.0 },
    @{ name = "qwq:32b"; lane = "large_reasoning"; size_gb = 20.0 },
    @{ name = "qwen2.5:32b"; lane = "large_general_json"; size_gb = 19.0 },
    @{ name = "mistral-small:24b"; lane = "large_chat"; size_gb = 14.0 },
    @{ name = "magistral:24b"; lane = "large_reasoning"; size_gb = 14.0 },
    @{ name = "command-r:35b"; lane = "rag_chat"; size_gb = 20.0 },
    @{ name = "mixtral:8x7b"; lane = "moe_chat"; size_gb = 26.0 },
    @{ name = "llava:13b"; lane = "vision"; size_gb = 7.4 },
    @{ name = "llava:34b"; lane = "large_vision"; size_gb = 20.0 },
    @{ name = "yi:34b"; lane = "multilingual_chat"; size_gb = 19.0 },
    @{ name = "llama3.3:70b"; lane = "large_chat"; size_gb = 42.0 },
    @{ name = "llama3.1:70b"; lane = "large_chat"; size_gb = 42.0 },
    @{ name = "qwen2.5:72b"; lane = "frontier_local_chat"; size_gb = 47.0 },
    @{ name = "llama3.2-vision:90b"; lane = "frontier_local_vision"; size_gb = 55.0 },
    @{ name = "bge-m3"; lane = "embeddings"; size_gb = 1.2 },
    @{ name = "snowflake-arctic-embed2"; lane = "embeddings"; size_gb = 1.2 }
)

$Results = New-Object System.Collections.Generic.List[object]
$installed = Get-InstalledModelNames $OllamaExe

foreach ($model in $Models) {
    $name = [string]$model.name
    $safe = ConvertTo-SafeName $name
    $outPath = Join-Path $LogsDir "$safe.out.log"
    $errPath = Join-Path $LogsDir "$safe.err.log"
    $freeBefore = Get-FreeGbForPath $Root
    $estimatedSize = [double]$model.size_gb

    if ($installed.Contains($name)) {
        $Results.Add([ordered]@{
            name = $name
            lane = [string]$model.lane
            estimated_size_gb = $estimatedSize
            status = "already-installed"
            exit_code = 0
            free_gb_before = $freeBefore
            free_gb_after = $freeBefore
            started_at = (Get-Date).ToString("o")
            finished_at = (Get-Date).ToString("o")
            duration_seconds = 0
            stdout_log = $outPath
            stderr_log = $errPath
        })
        $Results | ConvertTo-Json -Depth 5 | Set-Content -Path $SummaryPath -Encoding UTF8
        continue
    }

    if (($freeBefore - $estimatedSize) -lt $MinimumFreeGb) {
        $Results.Add([ordered]@{
            name = $name
            lane = [string]$model.lane
            estimated_size_gb = $estimatedSize
            status = "skipped-low-space"
            exit_code = $null
            free_gb_before = $freeBefore
            free_gb_after = $freeBefore
            minimum_free_gb = $MinimumFreeGb
            started_at = (Get-Date).ToString("o")
            finished_at = (Get-Date).ToString("o")
            duration_seconds = 0
            stdout_log = $outPath
            stderr_log = $errPath
        })
        $Results | ConvertTo-Json -Depth 5 | Set-Content -Path $SummaryPath -Encoding UTF8
        continue
    }

    $started = Get-Date
    Write-Host "Pulling $name ..."
    $process = Start-Process -FilePath $OllamaExe `
        -ArgumentList @("pull", $name) `
        -Wait `
        -PassThru `
        -WindowStyle Hidden `
        -RedirectStandardOutput $outPath `
        -RedirectStandardError $errPath

    $finished = Get-Date
    $freeAfter = Get-FreeGbForPath $Root
    $status = if ($process.ExitCode -eq 0) { "pulled" } else { "failed" }
    if ($process.ExitCode -eq 0) {
        [void]$installed.Add($name)
    }

    $Results.Add([ordered]@{
        name = $name
        lane = [string]$model.lane
        estimated_size_gb = $estimatedSize
        status = $status
        exit_code = $process.ExitCode
        free_gb_before = $freeBefore
        free_gb_after = $freeAfter
        minimum_free_gb = $MinimumFreeGb
        started_at = $started.ToString("o")
        finished_at = $finished.ToString("o")
        duration_seconds = [int]($finished - $started).TotalSeconds
        stdout_log = $outPath
        stderr_log = $errPath
    })

    $Results | ConvertTo-Json -Depth 5 | Set-Content -Path $SummaryPath -Encoding UTF8
    Write-Host "$name -> $status"
}

& $OllamaExe list | Tee-Object -FilePath (Join-Path $LogsDir "ollama-list.txt")
Write-Host "Summary written to $SummaryPath"
