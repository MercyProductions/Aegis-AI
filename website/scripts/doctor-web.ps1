param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$BackendUrl = "http://127.0.0.1:8787",
    [string]$FrontendUrl = "http://127.0.0.1:5173",
    [switch]$SkipConfigMutation,
    [switch]$AllowModelOffline
)

$ErrorActionPreference = "Stop"

function Normalize-PathForCompare {
    param([string]$Path)

    try {
        $resolved = Resolve-Path -LiteralPath $Path
        return $resolved.Path.TrimEnd("\", "/").ToLowerInvariant()
    } catch {
        return [System.IO.Path]::GetFullPath($Path).TrimEnd("\", "/").ToLowerInvariant()
    }
}

function Encode-QueryValue {
    param([string]$Value)
    return [System.Uri]::EscapeDataString($Value)
}

function Get-DotEnvValue {
    param(
        [string]$Path,
        [string]$Name,
        [string]$DefaultValue
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $DefaultValue
    }

    $line = Get-Content -LiteralPath $Path |
        Where-Object { $_ -match "^\s*$([regex]::Escape($Name))\s*=" } |
        Select-Object -Last 1
    if ([string]::IsNullOrWhiteSpace($line)) {
        return $DefaultValue
    }

    return ($line -replace "^\s*$([regex]::Escape($Name))\s*=\s*", "").Trim().Trim("'").Trim('"')
}

function Get-RestoreWorkspaceValue {
    param(
        [string]$Root,
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return "workspace"
    }

    $tmpRoot = [System.IO.Path]::GetFullPath((Join-Path $Root ".tmp")).TrimEnd("\", "/")
    $candidate = if ([System.IO.Path]::IsPathRooted($Value)) {
        [System.IO.Path]::GetFullPath($Value).TrimEnd("\", "/")
    } else {
        [System.IO.Path]::GetFullPath((Join-Path $Root $Value)).TrimEnd("\", "/")
    }
    $leaf = Split-Path -Leaf $candidate
    $expectedPrefix = "$tmpRoot$([System.IO.Path]::DirectorySeparatorChar)"

    if ($candidate.StartsWith($expectedPrefix, [System.StringComparison]::OrdinalIgnoreCase) -and $leaf -match "^(smoke|doctor)-") {
        return "workspace"
    }
    return $Value
}

function Invoke-WithConfigMutationLock {
    param(
        [string]$Root,
        [scriptblock]$Body
    )

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Root.ToLowerInvariant()))
    } finally {
        $sha.Dispose()
    }
    $hash = -join ($bytes[0..7] | ForEach-Object { $_.ToString("x2") })
    $mutex = [System.Threading.Mutex]::new($false, "Global\AegisChatBotConfigMutation-$hash")
    $lockTaken = $false
    try {
        $lockTaken = $mutex.WaitOne([TimeSpan]::FromSeconds(90))
        if (-not $lockTaken) {
            throw "Timed out waiting for config mutation lock."
        }
        & $Body
    } finally {
        if ($lockTaken) {
            $mutex.ReleaseMutex()
        }
        $mutex.Dispose()
    }
}

function Invoke-AegisJson {
    param(
        [ValidateSet("GET", "POST")]
        [string]$Method,
        [string]$Path,
        [object]$Body = $null
    )

    $uri = "$BackendUrl$Path"
    if ($null -eq $Body) {
        return Invoke-RestMethod -Method $Method -Uri $uri -Headers @{ Accept = "application/json" } -TimeoutSec 15
    }

    $json = $Body | ConvertTo-Json -Depth 12
    return Invoke-RestMethod -Method $Method -Uri $uri -ContentType "application/json" -Headers @{ Accept = "application/json" } -Body $json -TimeoutSec 15
}

function Add-Failure {
    param([string]$Message)
    $script:Failures += $Message
    Write-Host "[doctor] FAIL $Message"
}

function Add-Warning {
    param([string]$Message)
    $script:Warnings += $Message
    Write-Host "[doctor] WARN $Message"
}

function Add-Pass {
    param([string]$Message)
    Write-Host "[doctor] OK   $Message"
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

function Remove-DoctorTempDirectory {
    param(
        [string]$Path,
        [string]$Root
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) {
        return
    }

    $tmpRoot = [System.IO.Path]::GetFullPath((Join-Path $Root ".tmp")).TrimEnd("\", "/")
    $target = [System.IO.Path]::GetFullPath($Path).TrimEnd("\", "/")
    $leaf = Split-Path -Leaf $target
    $expectedPrefix = "$tmpRoot$([System.IO.Path]::DirectorySeparatorChar)"

    if (-not $target.StartsWith($expectedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to delete doctor temp directory outside .tmp: $target"
    }
    if ($leaf -notmatch "^doctor-config-") {
        throw "Refusing to delete unexpected doctor temp directory: $target"
    }

    Remove-Item -LiteralPath $target -Recurse -Force
}

$Root = (Resolve-Path -LiteralPath $Root).Path
$BackendUrl = $BackendUrl.TrimEnd("/")
$FrontendUrl = $FrontendUrl.TrimEnd("/")
$script:Failures = @()
$script:Warnings = @()
$expectedRoot = Normalize-PathForCompare -Path $Root

Write-Host "Aegis web doctor"
Write-Host "Project: $Root"
Write-Host "Frontend: $FrontendUrl"
Write-Host "Backend: $BackendUrl"

try {
    $frontend = Invoke-WebRequest -UseBasicParsing $FrontendUrl -TimeoutSec 15
    if ($frontend.StatusCode -ge 200 -and $frontend.StatusCode -lt 300 -and $frontend.Content -match "Aegis Coding AI") {
        Add-Pass "frontend returned Aegis HTML"
    } else {
        Add-Failure "frontend responded but did not look like the Aegis app"
    }
} catch {
    Add-Failure "frontend is not reachable at $FrontendUrl ($($_.Exception.Message))"
}

$health = $null
try {
    $health = Invoke-AegisJson -Method GET -Path "/api/health"
    if ([bool]$health.ready) {
        Add-Pass "backend reports ready"
    } else {
        Add-Failure "backend responded but ready=false"
    }

    if ($health.app -eq "Aegis Coding AI") {
        Add-Pass "backend identity is Aegis Coding AI"
    } else {
        Add-Failure "backend identity was '$($health.app)'"
    }

    if ((Normalize-PathForCompare -Path $health.project_root) -eq $expectedRoot) {
        Add-Pass "backend project root matches this checkout"
    } else {
        Add-Failure "backend project_root was '$($health.project_root)', expected '$Root'"
    }

    if ([bool]$health.model_ready) {
        Add-Pass "configured model is reachable"
    } elseif ($AllowModelOffline) {
        Add-Warning "configured model is offline: $($health.model_message)"
    } else {
        Add-Failure "configured model is offline: $($health.model_message)"
    }
} catch {
    Add-Failure "backend health is not reachable at $BackendUrl ($($_.Exception.Message))"
}

try {
    $openApi = Invoke-AegisJson -Method GET -Path "/openapi.json"
    $routes = @($openApi.paths.PSObject.Properties.Name)
    foreach ($route in @("/api/config", "/api/workspace/setup", "/api/workspace/profile", "/api/validate", "/api/chat")) {
        if ($routes -contains $route) {
            Add-Pass "route present: $route"
        } else {
            Add-Failure "route missing: $route"
        }
    }

    if (Test-OpenApiConfigUpdateSupportsPartial -Schema $openApi) {
        Add-Pass "config update contract supports partial payloads"
    } else {
        Add-Failure "config update contract still requires full payloads"
    }
} catch {
    Add-Failure "OpenAPI contract is not reachable ($($_.Exception.Message))"
}

if ($SkipConfigMutation) {
    Add-Warning "skipped partial config mutation probe"
} else {
    Invoke-WithConfigMutationLock -Root $Root -Body {
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $probeRoot = Join-Path $Root ".tmp\doctor-config-$stamp"
        $rawDefaultWorkspace = Get-RestoreWorkspaceValue -Root $Root -Value (Get-DotEnvValue -Path (Join-Path $Root ".env") -Name "DEFAULT_WORKSPACE" -DefaultValue "workspace")
        New-Item -ItemType Directory -Path $probeRoot -Force | Out-Null
        $probeSucceeded = $false
        try {
            $partialConfig = Invoke-AegisJson -Method POST -Path "/api/config" -Body @{
                default_workspace = $probeRoot
            }
            if ((Normalize-PathForCompare -Path $partialConfig.default_workspace) -eq (Normalize-PathForCompare -Path $probeRoot)) {
                Add-Pass "partial config update switched default workspace"
            } else {
                Add-Failure "partial config update returned '$($partialConfig.default_workspace)', expected '$probeRoot'"
            }

            $files = Invoke-AegisJson -Method GET -Path "/api/files?max_files=5"
            if ((Normalize-PathForCompare -Path $files.workspace_root) -eq (Normalize-PathForCompare -Path $probeRoot)) {
                Add-Pass "default workspace APIs use updated config"
            } else {
                Add-Failure "default workspace API returned '$($files.workspace_root)', expected '$probeRoot'"
            }
            $probeSucceeded = $true
        } catch {
            Add-Failure "partial config mutation probe failed ($($_.Exception.Message))"
        } finally {
            try {
                Invoke-AegisJson -Method POST -Path "/api/config" -Body @{
                    default_workspace = $rawDefaultWorkspace
                } | Out-Null
                Add-Pass "default workspace restored to '$rawDefaultWorkspace'"
            } catch {
                Add-Failure "failed to restore default workspace to '$rawDefaultWorkspace' ($($_.Exception.Message))"
            }

            if ($probeSucceeded) {
                Remove-DoctorTempDirectory -Path $probeRoot -Root $Root
                Add-Pass "temporary doctor workspace cleaned up"
            } else {
                Add-Warning "kept doctor workspace for debugging: $probeRoot"
            }
        }
    }
}

Write-Host ""
if ($Failures.Count -gt 0) {
    Write-Host "Aegis web doctor found $($Failures.Count) issue(s)." -ForegroundColor Red
    exit 1
}

if ($Warnings.Count -gt 0) {
    Write-Host "Aegis web doctor passed with $($Warnings.Count) warning(s)." -ForegroundColor Yellow
} else {
    Write-Host "Aegis web doctor passed." -ForegroundColor Green
}
