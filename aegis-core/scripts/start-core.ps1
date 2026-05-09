$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$CoreHost = "127.0.0.1"
$CorePort = 8788
$CoreBaseUrl = "http://${CoreHost}:$CorePort"
$CoreUrl = "$CoreBaseUrl/v1/health"
$VenvPython = Join-Path $root ".venv\Scripts\python.exe"

function Resolve-CorePython {
    if (Test-Path -LiteralPath $VenvPython) {
        return $VenvPython
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    throw "Python was not found. Create .venv for Aegis Core or install Python 3.10+ on PATH."
}

function Test-AegisCoreHealth {
    try {
        $response = Invoke-WebRequest -UseBasicParsing $CoreUrl -Headers @{ Accept = "application/json" } -TimeoutSec 2
    } catch {
        $statusCode = $null
        if ($_.Exception.Response) {
            $statusCode = [int]$_.Exception.Response.StatusCode
        }

        return [pscustomobject]@{
            Reachable = ($null -ne $statusCode)
            IsCore = $false
            ContractVersion = $null
            StatusCode = $statusCode
            Reason = "http_error"
        }
    }

    try {
        $body = $response.Content | ConvertFrom-Json
    } catch {
        return [pscustomobject]@{
            Reachable = $true
            IsCore = $false
            ContractVersion = $null
            StatusCode = [int]$response.StatusCode
            Reason = "invalid_json"
        }
    }

    return [pscustomobject]@{
        Reachable = $true
        IsCore = ($response.StatusCode -eq 200 -and $body.api_version -eq "v1" -and $body.kind -eq "health")
        ContractVersion = $body.contract_version
        StatusCode = [int]$response.StatusCode
        Reason = if ($response.StatusCode -eq 200) { "unexpected_envelope" } else { "http_status" }
    }
}

function Test-TcpPortOpen {
    param(
        [string]$HostName,
        [int]$Port,
        [int]$TimeoutMilliseconds = 750
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    $async = $null
    try {
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne($TimeoutMilliseconds)) {
            return $false
        }

        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        if ($async -and $async.AsyncWaitHandle) {
            $async.AsyncWaitHandle.Close()
        }
        $client.Close()
    }
}

$probe = Test-AegisCoreHealth
if ($probe.IsCore) {
    Write-Host "Aegis Core is already running at $CoreBaseUrl (contract $($probe.ContractVersion))"
    return
}

if ($probe.Reachable) {
    throw "Port $CorePort is responding, but it is not Aegis Core /v1 health (status $($probe.StatusCode), reason $($probe.Reason)). Stop that process before starting Aegis Core."
}

if (Test-TcpPortOpen -HostName $CoreHost -Port $CorePort) {
    throw "Port $CorePort is open, but Aegis Core /v1 health did not respond within the startup probe timeout. Stop that process before starting Aegis Core."
}

$Python = Resolve-CorePython
& $Python -c "import aegis_core.server, uvicorn"
if ($LASTEXITCODE -ne 0) {
    throw "Aegis Core dependencies are missing. From aegis-core, run: python -m pip install -e ."
}

& $Python -m uvicorn aegis_core.server:create_app --factory --host 127.0.0.1 --port 8788
