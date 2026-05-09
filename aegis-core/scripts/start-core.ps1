$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$CoreUrl = "http://127.0.0.1:8788/v1/health"

try {
    $response = Invoke-WebRequest -UseBasicParsing $CoreUrl -TimeoutSec 2
    if ($response.StatusCode -eq 200) {
        Write-Host "Aegis Core is already running at http://127.0.0.1:8788"
        return
    }
} catch {
    $statusCode = $null
    if ($_.Exception.Response) {
        $statusCode = [int]$_.Exception.Response.StatusCode
    }

    if ($statusCode) {
        throw "Port 8788 is responding, but it is not Aegis Core /v1. Stop that process before starting Aegis Core."
    }
}

python -m uvicorn aegis_core.server:create_app --factory --host 127.0.0.1 --port 8788
