$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -m uvicorn aegis_core.server:create_app --factory --host 127.0.0.1 --port 8788
