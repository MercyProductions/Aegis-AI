param(
  [string]$Root = "",
  [string]$EvidenceDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Root)) {
  $ScriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
  $Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $ScriptRoot))
} else {
  $Root = [System.IO.Path]::GetFullPath($Root)
}

function Join-ProjectPath {
  param([Parameter(Mandatory = $true)][string]$Path)
  return Join-Path $Root $Path
}

function Test-UnderRoot {
  param([Parameter(Mandatory = $true)][string]$Path)

  $full = [System.IO.Path]::GetFullPath($Path)
  $rootWithSlash = $Root.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
  if (-not ($full.Equals($Root, [System.StringComparison]::OrdinalIgnoreCase) -or $full.StartsWith($rootWithSlash, [System.StringComparison]::OrdinalIgnoreCase))) {
    throw "Refusing to write outside project root: $full"
  }
  return $full
}

function ConvertTo-ProjectRelativePath {
  param([Parameter(Mandatory = $true)][string]$Path)

  $full = [System.IO.Path]::GetFullPath($Path)
  $rootWithSlash = $Root.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
  if ($full.StartsWith($rootWithSlash, [System.StringComparison]::OrdinalIgnoreCase)) {
    return $full.Substring($rootWithSlash.Length)
  }
  return $full
}

function ConvertTo-CheckId {
  param([Parameter(Mandatory = $true)][string]$Value)
  return $Value.Replace("/", "-").Replace("\", "-").Replace(" ", "-").Replace(":", "").Replace("{", "").Replace("}", "").ToLowerInvariant()
}

function Read-ProjectFile {
  param([Parameter(Mandatory = $true)][string]$RelativePath)

  $path = Join-ProjectPath $RelativePath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "Required Phase 26 file is missing: $RelativePath"
  }
  return Get-Content -LiteralPath $path -Raw
}

function Read-ProjectJson {
  param([Parameter(Mandatory = $true)][string]$RelativePath)
  return Read-ProjectFile $RelativePath | ConvertFrom-Json
}

function Add-Check {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][bool]$Passed,
    [Parameter(Mandatory = $true)][string]$Message,
    [object]$Details = $null
  )

  $script:Checks += [pscustomobject]@{
    id = $Id
    passed = $Passed
    message = $Message
    details = $Details
  }
  if (-not $Passed) {
    $script:Failures += $Message
  }
}

function Invoke-LoggedCommand {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [Parameter(Mandatory = $true)][string]$Executable,
    [string[]]$Arguments = @()
  )

  $resolvedWorkingDirectory = [System.IO.Path]::GetFullPath((Join-Path $Root $WorkingDirectory))
  $logPath = Join-Path $EvidenceDir "$Id.log"
  $command = (@($Executable) + $Arguments) -join " "
  $started = Get-Date
  $exitCode = 0
  $status = "passed"
  $reason = ""

  @(
    "Command: $command",
    "Working directory: $resolvedWorkingDirectory",
    "Started: $($started.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))",
    ""
  ) | Set-Content -LiteralPath $logPath -Encoding UTF8

  try {
    Push-Location $resolvedWorkingDirectory
    $global:LASTEXITCODE = 0
    & $Executable @Arguments *>> $logPath
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    if ($exitCode -ne 0) {
      $status = "failed"
      $reason = "Exited with code $exitCode."
    }
  } catch {
    $status = "failed"
    $exitCode = 1
    $reason = $_.Exception.Message
    "" | Add-Content -LiteralPath $logPath -Encoding UTF8
    "Exception:" | Add-Content -LiteralPath $logPath -Encoding UTF8
    ($_ | Out-String) | Add-Content -LiteralPath $logPath -Encoding UTF8
  } finally {
    Pop-Location
  }

  $ended = Get-Date
  $duration = [Math]::Round(($ended - $started).TotalSeconds, 2)
  @(
    "",
    "Ended: $($ended.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))",
    "Duration seconds: $duration",
    "Exit code: $exitCode",
    "Status: $status",
    "Reason: $reason"
  ) | Add-Content -LiteralPath $logPath -Encoding UTF8

  Add-Check -Id "command-$(ConvertTo-CheckId $Id)" -Passed ($status -eq "passed") -Message "Validation command must pass: $command" -Details @{ log = ConvertTo-ProjectRelativePath $logPath; duration_seconds = $duration }

  return [pscustomobject]@{
    id = $Id
    command = $command
    working_directory = ConvertTo-ProjectRelativePath $resolvedWorkingDirectory
    status = $status
    exit_code = $exitCode
    duration_seconds = $duration
    log = ConvertTo-ProjectRelativePath $logPath
  }
}

if ([string]::IsNullOrWhiteSpace($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\backend-modularization" (Get-Date -Format "yyyyMMdd-HHmmss"))
} elseif (-not [System.IO.Path]::IsPathRooted($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root $EvidenceDir
}
$EvidenceDir = Test-UnderRoot $EvidenceDir
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$script:Checks = @()
$script:Failures = @()
$contract = Read-ProjectJson "evals\phase26-backend-modularization-contract.json"
$mainSource = Read-ProjectFile ([string]$contract.thin_orchestrator)
$moduleSource = Read-ProjectFile ([string]$contract.extracted_module)
$docs = Read-ProjectFile "docs\BACKEND_MODULARIZATION_EVIDENCE.md"
$validationDocs = Read-ProjectFile "docs\VALIDATION_MATRIX.md"
$validator = Read-ProjectFile "scripts\validate-ecosystem.ps1"

Add-Check -Id "contract-schema-version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Message "Phase 26 contract must use schema version 2026.05.21."
Add-Check -Id "contract-evidence-root" -Passed ([string]$contract.evidence_root -eq ".aegis/backend-modularization") -Message "Phase 26 evidence root must be .aegis/backend-modularization."
Add-Check -Id "contract-required-status" -Passed ([string]$contract.current_required_status -eq "ready") -Message "Phase 26 required status must be ready."

foreach ($relativePath in @($contract.required_contract_files)) {
  $path = Join-ProjectPath ([string]$relativePath)
  Add-Check -Id "contract-file-$(ConvertTo-CheckId ([string]$relativePath))" -Passed (Test-Path -LiteralPath $path -PathType Leaf) -Message "Required Phase 26 file must exist: $relativePath"
}

foreach ($marker in @($contract.required_module_exports)) {
  Add-Check -Id "module-export-$(ConvertTo-CheckId ([string]$marker))" -Passed ($moduleSource.Contains("def $marker")) -Message "Extracted module must export '$marker'."
}

foreach ($marker in @($contract.required_main_markers)) {
  Add-Check -Id "main-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($mainSource.Contains([string]$marker)) -Message "main.py must keep orchestration marker '$marker'."
}

foreach ($marker in @($contract.removed_main_helpers)) {
  Add-Check -Id "main-helper-removed-$(ConvertTo-CheckId ([string]$marker))" -Passed (-not $mainSource.Contains([string]$marker)) -Message "main.py must not retain extracted helper '$marker'."
}

foreach ($testPath in @($contract.required_tests)) {
  $testSource = Read-ProjectFile ([string]$testPath)
  Add-Check -Id "test-file-$(ConvertTo-CheckId ([string]$testPath))" -Passed ($testSource.Contains("route_preview") -or $testSource.Contains("runtime_ownership")) -Message "Required backend modularization test must cover its target: $testPath"
}

Add-Check -Id "docs-command" -Passed ($docs.Contains("test-backend-modularization.ps1")) -Message "Backend modularization docs must include the validation command."
Add-Check -Id "docs-evidence-root" -Passed ($docs.Contains(".aegis/backend-modularization")) -Message "Backend modularization docs must include the evidence root."
Add-Check -Id "validation-doc-gate" -Passed ($validationDocs.Contains("backend-modularization-contract") -and $validationDocs.Contains("test-backend-modularization")) -Message "Validation matrix must document the backend modularization gate."
Add-Check -Id "validator-gate" -Passed ($validator.Contains("test-backend-modularization.ps1") -and $validator.Contains("backend-modularization-contract")) -Message "Ecosystem validator must run the backend modularization gate."

$commandResults = @()
$commandResults += Invoke-LoggedCommand -Id "backend-modularization-tests" -WorkingDirectory "website\backend" -Executable "python" -Arguments @("-m", "pytest", "tests/test_route_preview_service.py", "tests/test_runtime_ownership.py", "-q")

$summary = [pscustomobject]@{
  schema_version = "2026.05.21"
  phase = 26
  status = if ($script:Failures.Count -eq 0) { "ready" } else { "blocked" }
  generated_at = (Get-Date).ToString("o")
  evidence_dir = ConvertTo-ProjectRelativePath $EvidenceDir
  contract = "evals/phase26-backend-modularization-contract.json"
  slice = [string]$contract.slice
  extracted_module = [string]$contract.extracted_module
  thin_orchestrator = [string]$contract.thin_orchestrator
  commands = $commandResults
  failures = $script:Failures
  checks = $script:Checks
}

$jsonPath = Join-Path $EvidenceDir "backend-modularization.json"
$markdownPath = Join-Path $EvidenceDir "backend-modularization-summary.md"
$summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 26 Backend Modularization Evidence"
$markdown += ""
$markdown += "- Status: $($summary.status)"
$markdown += "- Generated at: $($summary.generated_at)"
$markdown += "- Evidence dir: $($summary.evidence_dir)"
$markdown += "- Slice: $($summary.slice)"
$markdown += "- Extracted module: $($summary.extracted_module)"
$markdown += "- Thin orchestrator: $($summary.thin_orchestrator)"
$markdown += ""
$markdown += "## Commands"
$markdown += ""
$markdown += "| Command | Status | Seconds | Log |"
$markdown += "| --- | --- | ---: | --- |"
foreach ($command in @($summary.commands)) {
  $markdown += "| $($command.command.Replace('|', '\|')) | $($command.status) | $($command.duration_seconds) | $($command.log) |"
}
$markdown += ""
$markdown += "## Checks"
$markdown += ""
$markdown += "| Check | Status | Message |"
$markdown += "| --- | --- | --- |"
foreach ($check in @($summary.checks)) {
  $status = if ([bool]$check.passed) { "passed" } else { "failed" }
  $message = ([string]$check.message).Replace("|", "\|")
  $markdown += "| $($check.id) | $status | $message |"
}
$markdown | Set-Content -LiteralPath $markdownPath -Encoding UTF8

$summary | ConvertTo-Json -Depth 12

if ($script:Failures.Count -gt 0) {
  throw "Backend modularization validation failed:`n - $($script:Failures -join "`n - ")"
}
