param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$BackendUrl = "http://127.0.0.1:8787",
    [string]$FrontendUrl = "http://127.0.0.1:5173",
    [switch]$SkipChat,
    [switch]$KeepWorkspace
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

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw "Smoke check failed: $Message"
    }
}

function Encode-QueryValue {
    param([string]$Value)
    return [System.Uri]::EscapeDataString($Value)
}

function Invoke-AegisJson {
    param(
        [ValidateSet("GET", "POST", "PUT", "DELETE")]
        [string]$Method,
        [string]$Path,
        [object]$Body = $null
    )

    $uri = "$BackendUrl$Path"
    if ($null -eq $Body) {
        return Invoke-RestMethod -Method $Method -Uri $uri -Headers @{ Accept = "application/json" }
    }

    $json = $Body | ConvertTo-Json -Depth 16
    return Invoke-RestMethod -Method $Method -Uri $uri -ContentType "application/json" -Headers @{ Accept = "application/json" } -Body $json
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

function Write-Step {
    param([string]$Message)
    Write-Host "[smoke] $Message"
}

function Remove-SmokeTempDirectory {
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
        throw "Refusing to delete smoke temp directory outside .tmp: $target"
    }
    if ($leaf -notmatch "^(smoke-web|smoke-config)-") {
        throw "Refusing to delete unexpected smoke temp directory: $target"
    }

    Remove-Item -LiteralPath $target -Recurse -Force
}

$Root = (Resolve-Path -LiteralPath $Root).Path
$BackendUrl = $BackendUrl.TrimEnd("/")
$FrontendUrl = $FrontendUrl.TrimEnd("/")
$expectedRoot = Normalize-PathForCompare -Path $Root

Write-Step "checking frontend at $FrontendUrl"
$frontend = Invoke-WebRequest -UseBasicParsing $FrontendUrl
Assert-True ($frontend.StatusCode -ge 200 -and $frontend.StatusCode -lt 300) "frontend did not return a 2xx response"
Assert-True ($frontend.Content -match "Auralith OS") "frontend HTML did not look like the Auralith OS app"

Write-Step "checking backend identity at $BackendUrl"
$health = Invoke-AegisJson -Method GET -Path "/api/health"
Assert-True ([bool]$health.ready) "backend reported not ready"
Assert-True ((Normalize-PathForCompare -Path $health.project_root) -eq $expectedRoot) "backend project_root was '$($health.project_root)', expected '$Root'"
Assert-True ([bool]$health.model_ready) "local model was not ready: $($health.model_message)"

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$smokeRoot = Join-Path $Root ".tmp\smoke-web-$stamp"
New-Item -ItemType Directory -Path $smokeRoot -Force | Out-Null

Write-Step "checking partial config update"
$initialConfig = Invoke-AegisJson -Method GET -Path "/api/config"
$rawDefaultWorkspace = Get-RestoreWorkspaceValue -Root $Root -Value (Get-DotEnvValue -Path (Join-Path $Root ".env") -Name "DEFAULT_WORKSPACE" -DefaultValue "workspace")
$configProbeRoot = Join-Path $Root ".tmp\smoke-config-$stamp"
New-Item -ItemType Directory -Path $configProbeRoot -Force | Out-Null
if ($env:AEGIS_SMOKE_FORCE_FAILURE_AFTER_WORKSPACE_CREATE -eq "1") {
    throw "Forced smoke failure after workspace creation."
}
Invoke-WithConfigMutationLock -Root $Root -Body {
    try {
        $partialConfig = Invoke-AegisJson -Method POST -Path "/api/config" -Body @{
            default_workspace = $configProbeRoot
        }
        Assert-True ((Normalize-PathForCompare -Path $partialConfig.default_workspace) -eq (Normalize-PathForCompare -Path $configProbeRoot)) "partial config update did not switch default workspace"
        Assert-True ($partialConfig.assistant_name -eq $initialConfig.assistant_name) "partial config update changed assistant_name unexpectedly"
        $defaultFiles = Invoke-AegisJson -Method GET -Path "/api/files?max_files=20"
        Assert-True ((Normalize-PathForCompare -Path $defaultFiles.workspace_root) -eq (Normalize-PathForCompare -Path $configProbeRoot)) "default workspace APIs did not use partial config workspace"
    }
    finally {
        Invoke-AegisJson -Method POST -Path "/api/config" -Body @{
            default_workspace = $rawDefaultWorkspace
        } | Out-Null
    }
}

@"
{
  "name": "aegis-smoke-workspace",
  "private": true,
  "scripts": {
    "test": "node smoke.js"
  }
}
"@ | Set-Content -LiteralPath (Join-Path $smokeRoot "package.json") -Encoding UTF8

@"
const fs = require('node:fs');
if (!fs.existsSync('generated/smoke.txt')) {
  throw new Error('generated smoke file is missing');
}
const content = fs.readFileSync('generated/smoke.txt', 'utf8');
if (!content.includes('Auralith OS smoke test passed')) {
  throw new Error('generated smoke file content was not applied');
}
console.log('auralith validation smoke ok');
"@ | Set-Content -LiteralPath (Join-Path $smokeRoot "smoke.js") -Encoding UTF8

$workspaceQuery = Encode-QueryValue -Value $smokeRoot

Write-Step "listing disposable workspace files"
$files = Invoke-AegisJson -Method GET -Path "/api/files?workspace_root=$workspaceQuery&max_files=50"
Assert-True (($files.files | Where-Object { $_.path -eq "package.json" } | Measure-Object).Count -eq 1) "workspace file listing did not include package.json"

Write-Step "checking validation profile inference"
$profile = Invoke-AegisJson -Method GET -Path "/api/validation/profile?workspace_root=$workspaceQuery"
Assert-True (($profile.suggestions | Where-Object { $_.command -eq "npm test" } | Measure-Object).Count -eq 1) "validation suggestions did not include npm test"

Write-Step "setting up workspace manifest"
$setup = Invoke-AegisJson -Method POST -Path "/api/workspace/setup" -Body @{
    workspace_root = $smokeRoot
}
Assert-True (($setup.created_files | Where-Object { $_ -eq ".aegis/project.json" } | Measure-Object).Count -eq 1) "workspace setup did not create project manifest"
Assert-True (($setup.created_files | Where-Object { $_ -eq ".aegis/validation_profile.json" } | Measure-Object).Count -eq 1) "workspace setup did not save validation profile"
Assert-True ($setup.manifest.validation_command -eq "npm test") "workspace setup manifest did not preserve inferred validation command"
Assert-True ($setup.validation_profile.command -eq "npm test") "workspace setup validation profile did not preserve inferred command"
Assert-True ($setup.profile.has_manifest) "workspace setup profile did not report manifest"
Assert-True (Test-Path -LiteralPath (Join-Path $smokeRoot ".aegis\project.json")) "workspace setup manifest file was not written"

Write-Step "checking diff engine"
$diff = Invoke-AegisJson -Method POST -Path "/api/diff/compare" -Body @{
    path = "generated/smoke.txt"
    action = "create"
    old_content = ""
    new_content = "Auralith OS smoke test passed`n"
}
Assert-True ($diff.patch -match "Auralith OS smoke test passed") "diff response did not include generated content"

Write-Step "applying generated file through API"
$apply = Invoke-AegisJson -Method POST -Path "/api/apply" -Body @{
    workspace_root = $smokeRoot
    changes = @(
        @{
            action = "create"
            path = "generated/smoke.txt"
            content = "Auralith OS smoke test passed`n"
            summary = "Create smoke-test output file"
        }
    )
}
Assert-True (($apply.applied | Where-Object { $_ -like "*generated/smoke.txt" } | Measure-Object).Count -eq 1) "apply response did not report generated/smoke.txt"

Write-Step "reading generated file through API"
$file = Invoke-AegisJson -Method GET -Path "/api/file?workspace_root=$workspaceQuery&path=generated%2Fsmoke.txt"
Assert-True ($file.content -eq "Auralith OS smoke test passed`n") "read-back content did not match applied content"

Write-Step "running inferred validation command"
$validation = Invoke-AegisJson -Method POST -Path "/api/validate" -Body @{
    workspace_root = $smokeRoot
}
Assert-True ($null -ne $validation.validation) "validation response did not include a command result"
Assert-True ($validation.validation.allowed) "validation command was blocked: $($validation.validation.reason)"
Assert-True ($validation.validation.exit_code -eq 0) "validation command failed: $($validation.validation.summary)"
Assert-True ($validation.validation.stdout -match "auralith validation smoke ok") "validation output did not include smoke success text"

Write-Step "checking readiness after validation"
$readyProfile = Invoke-AegisJson -Method GET -Path "/api/workspace/profile?workspace_root=$workspaceQuery"
Assert-True ($readyProfile.has_manifest) "readiness profile lost the setup manifest"
Assert-True ($readyProfile.readiness.status -eq "ready") "readiness did not become ready after validation: $($readyProfile.readiness.status)"
Assert-True ($readyProfile.readiness.score -ge 85) "readiness score stayed too low after validation: $($readyProfile.readiness.score)"

if (-not $SkipChat) {
    Write-Step "sending a real chat turn"
    $chat = Invoke-AegisJson -Method POST -Path "/api/chat" -Body @{
        message = "Smoke test: reply with one short sentence confirming Auralith Prime is responding."
        mode = "chat"
        workspace_root = $smokeRoot
        apply_changes = $false
        run_validation = $false
        history = @()
    }
    Assert-True (-not [string]::IsNullOrWhiteSpace($chat.reply)) "chat response was empty"
    Assert-True (-not [string]::IsNullOrWhiteSpace($chat.task_id)) "chat response did not include a task id"
}

Write-Host "Auralith OS smoke test passed."
if ($KeepWorkspace) {
    Write-Host "Workspace: $smokeRoot"
    Write-Host "Config probe workspace: $configProbeRoot"
} else {
    Remove-SmokeTempDirectory -Path $smokeRoot -Root $Root
    Remove-SmokeTempDirectory -Path $configProbeRoot -Root $Root
    Write-Host "Temporary smoke workspaces cleaned up."
}
