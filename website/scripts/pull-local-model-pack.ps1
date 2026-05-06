$ErrorActionPreference = "Continue"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$LogsDir = Join-Path $Root "logs\model-pulls"
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

$OllamaExe = Resolve-OllamaExe

$Models = @(
    @{ name = "llama3.2:1b"; lane = "fast_chat"; size_gb = 1.3 },
    @{ name = "llama3.2:3b"; lane = "chat"; size_gb = 2.0 },
    @{ name = "llama3.1:8b"; lane = "chat"; size_gb = 4.7 },
    @{ name = "gemma3:1b"; lane = "tiny_chat"; size_gb = 0.8 },
    @{ name = "phi4-mini"; lane = "fast_reasoning"; size_gb = 2.5 },
    @{ name = "phi4"; lane = "reasoning"; size_gb = 9.1 },
    @{ name = "gpt-oss:20b"; lane = "open_weight_reasoning"; size_gb = 13.0 },
    @{ name = "qwen3:4b"; lane = "reasoning"; size_gb = 2.5 },
    @{ name = "qwen3:8b"; lane = "reasoning"; size_gb = 5.2 },
    @{ name = "qwen3:14b"; lane = "deep_reasoning"; size_gb = 9.3 },
    @{ name = "deepseek-r1:1.5b"; lane = "tiny_reasoning"; size_gb = 1.1 },
    @{ name = "deepseek-r1:7b"; lane = "reasoning"; size_gb = 4.7 },
    @{ name = "deepseek-r1:8b"; lane = "reasoning"; size_gb = 5.2 },
    @{ name = "deepseek-r1:14b"; lane = "deep_reasoning"; size_gb = 9.0 },
    @{ name = "gemma3:4b"; lane = "vision_chat"; size_gb = 3.3 },
    @{ name = "gemma3:12b"; lane = "vision_reasoning"; size_gb = 8.1 },
    @{ name = "mistral:7b"; lane = "tools_chat"; size_gb = 4.4 },
    @{ name = "qwen2.5:7b"; lane = "general_json"; size_gb = 4.7 },
    @{ name = "qwen2.5:14b"; lane = "general_json"; size_gb = 9.0 },
    @{ name = "qwen2.5-coder:1.5b"; lane = "tiny_code"; size_gb = 1.0 },
    @{ name = "qwen2.5-coder:3b"; lane = "fast_code"; size_gb = 1.9 },
    @{ name = "qwen2.5-coder:7b"; lane = "code"; size_gb = 4.7 },
    @{ name = "qwen2.5-coder:14b"; lane = "strong_code"; size_gb = 9.0 },
    @{ name = "qwen2.5-coder:32b"; lane = "frontier_local_code"; size_gb = 20.0 },
    @{ name = "codellama:7b"; lane = "code_completion"; size_gb = 3.8 },
    @{ name = "deepseek-coder-v2:16b"; lane = "strong_code"; size_gb = 8.9 },
    @{ name = "devstral:24b"; lane = "agentic_code"; size_gb = 14.0 },
    @{ name = "starcoder2:3b"; lane = "code_completion"; size_gb = 1.7 },
    @{ name = "starcoder2:7b"; lane = "code_completion"; size_gb = 4.0 },
    @{ name = "granite-code:3b"; lane = "long_context_code"; size_gb = 2.0 },
    @{ name = "granite-code:8b"; lane = "long_context_code"; size_gb = 4.6 },
    @{ name = "codegemma:2b"; lane = "autocomplete_code"; size_gb = 1.6 },
    @{ name = "nomic-embed-text"; lane = "embeddings"; size_gb = 0.3 },
    @{ name = "mxbai-embed-large"; lane = "embeddings"; size_gb = 0.7 },
    @{ name = "all-minilm"; lane = "embeddings"; size_gb = 0.05 }
)

$Results = New-Object System.Collections.Generic.List[object]

foreach ($model in $Models) {
    $name = [string]$model.name
    $safe = ConvertTo-SafeName $name
    $outPath = Join-Path $LogsDir "$safe.out.log"
    $errPath = Join-Path $LogsDir "$safe.err.log"
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
    $status = if ($process.ExitCode -eq 0) { "pulled" } else { "failed" }
    $Results.Add([ordered]@{
        name = $name
        lane = [string]$model.lane
        estimated_size_gb = [double]$model.size_gb
        status = $status
        exit_code = $process.ExitCode
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
