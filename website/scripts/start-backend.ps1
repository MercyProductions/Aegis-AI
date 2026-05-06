param(
    [int]$Port = 8787,
    [string]$HostName = "127.0.0.1",
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$BackendMain = Join-Path $Root "backend\aegis_ai\main.py"

if (-not (Test-Path $Python)) {
    throw "Virtual environment is missing. Run launch.ps1 first."
}
if (-not (Test-Path $BackendMain)) {
    throw "Backend entrypoint is missing at $BackendMain."
}
if ($Port -lt 1 -or $Port -gt 65535) {
    throw "Port must be between 1 and 65535."
}

$Args = @(
    "-m", "uvicorn",
    "aegis_ai.main:app",
    "--app-dir", (Join-Path $Root "backend"),
    "--host", $HostName,
    "--port", "$Port"
)
if ($Reload) {
    $Args += "--reload"
}

& $Python @Args
