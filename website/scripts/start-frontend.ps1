$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Frontend = Join-Path $Root "frontend"

if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    throw "Frontend dependencies are missing. Run launch.ps1 first."
}

npm --prefix $Frontend run dev -- --host 127.0.0.1 --port 5173
