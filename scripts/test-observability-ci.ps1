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
    throw "Required Phase 33 file is missing: $RelativePath"
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
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\observability-ci" (Get-Date -Format "yyyyMMdd-HHmmss"))
} elseif (-not [System.IO.Path]::IsPathRooted($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root $EvidenceDir
}
$EvidenceDir = Test-UnderRoot $EvidenceDir
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$script:Checks = @()
$script:Failures = @()
$contract = Read-ProjectJson "evals\phase33-observability-ci-contract.json"
$workflow = Read-ProjectFile ([string]$contract.workflow)
$qualityContractText = Read-ProjectFile ([string]$contract.quality_contract)
$qualityContract = $qualityContractText | ConvertFrom-Json
$qualityScript = Read-ProjectFile ([string]$contract.quality_script)
$goldenWorkflows = Read-ProjectFile ([string]$contract.golden_workflows)
$telemetryRoutes = Read-ProjectFile ([string]$contract.telemetry_routes)
$storageQuality = Read-ProjectFile ([string]$contract.storage_quality)
$validator = Read-ProjectFile ([string]$contract.validator)
$ledgerContract = Read-ProjectFile ([string]$contract.ledger_contract)
$docs = Read-ProjectFile "docs\OBSERVABILITY_EVALS_CI_EVIDENCE.md"
$validationDocs = Read-ProjectFile "docs\VALIDATION_MATRIX.md"
$ledgerDocs = Read-ProjectFile "docs\EVIDENCE_LEDGER.md"
$ledgerScript = Read-ProjectFile "scripts\test-evidence-ledger-contract.ps1"

Add-Check -Id "contract-schema-version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Message "Phase 33 contract must use schema version 2026.05.21."
Add-Check -Id "contract-evidence-root" -Passed ([string]$contract.evidence_root -eq ".aegis/observability-ci") -Message "Phase 33 evidence root must be .aegis/observability-ci."
Add-Check -Id "contract-required-status" -Passed ([string]$contract.current_required_status -eq "ready") -Message "Phase 33 required status must be ready."

foreach ($relativePath in @($contract.required_contract_files)) {
  Add-Check -Id "contract-file-$(ConvertTo-CheckId ([string]$relativePath))" -Passed (Test-Path -LiteralPath (Join-ProjectPath ([string]$relativePath)) -PathType Leaf) -Message "Required Phase 33 file must exist: $relativePath"
}

foreach ($job in @($contract.required_workflow_jobs)) {
  Add-Check -Id "workflow-job-$(ConvertTo-CheckId ([string]$job))" -Passed ($workflow.Contains("$($job):")) -Message "GitHub Actions workflow must define job '$job'."
}

foreach ($command in @($contract.required_ci_commands)) {
  Add-Check -Id "workflow-command-$(ConvertTo-CheckId ([string]$command))" -Passed ($workflow.Contains([string]$command)) -Message "GitHub Actions workflow must run '$command'."
}

foreach ($marker in @($contract.required_golden_eval_markers)) {
  Add-Check -Id "golden-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($goldenWorkflows.Contains([string]$marker)) -Message "Golden workflow tests must include '$marker'."
}

foreach ($marker in @($contract.required_quality_contract_markers)) {
  Add-Check -Id "quality-contract-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($qualityContractText.Contains([string]$marker)) -Message "Phase 12 quality contract must include '$marker'."
}

foreach ($marker in @($contract.required_observability_markers)) {
  $hasMarker = $telemetryRoutes.Contains([string]$marker) -or $storageQuality.Contains([string]$marker)
  Add-Check -Id "observability-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed $hasMarker -Message "Telemetry observability sources must include '$marker'."
}

foreach ($marker in @($contract.required_validator_markers)) {
  Add-Check -Id "validator-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($validator.Contains([string]$marker)) -Message "Ecosystem validator must include '$marker'."
}

foreach ($marker in @($contract.required_ledger_markers)) {
  $hasMarker = $ledgerContract.Contains([string]$marker) -or $ledgerDocs.Contains([string]$marker) -or $ledgerScript.Contains([string]$marker)
  Add-Check -Id "ledger-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed $hasMarker -Message "Evidence ledger wiring must include '$marker'."
}

Add-Check -Id "quality-contract-golden-count" -Passed (@($qualityContract.golden_workflows).Count -ge 10) -Message "Phase 12 quality contract must keep at least ten golden workflows."
Add-Check -Id "quality-contract-observability-count" -Passed (@($qualityContract.observability_signals).Count -ge 6) -Message "Phase 12 quality contract must keep at least six observability signals."
Add-Check -Id "quality-contract-budget-count" -Passed (@($qualityContract.performance_budgets).Count -ge 6) -Message "Phase 12 quality contract must keep at least six performance budgets."
Add-Check -Id "quality-script-telemetry-assertions" -Passed ($qualityScript.Contains("telemetry-route-quality") -and $qualityScript.Contains("telemetry-token-calibration")) -Message "Quality contract validator must assert telemetry route quality and token calibration."
Add-Check -Id "docs-command" -Passed ($docs.Contains("test-observability-ci.ps1")) -Message "Phase 33 docs must include the validation command."
Add-Check -Id "docs-evidence-root" -Passed ($docs.Contains(".aegis/observability-ci")) -Message "Phase 33 docs must include the evidence root."
Add-Check -Id "validation-doc-gate" -Passed ($validationDocs.Contains("observability-ci-contract") -and $validationDocs.Contains("test-observability-ci")) -Message "Validation matrix must document the observability CI gate."
Add-Check -Id "ledger-doc-source" -Passed ($ledgerDocs.Contains(".aegis/observability-ci") -or $ledgerDocs.Contains("observability_ci")) -Message "Evidence ledger docs must include the observability CI source."

$commandResults = @()
$commandResults += Invoke-LoggedCommand -Id "quality-contract" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Root "scripts\test-quality-contract.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "quality-contract"))
$commandResults += Invoke-LoggedCommand -Id "backend-golden-workflows" -WorkingDirectory "website\backend" -Executable "python" -Arguments @("-m", "pytest", "tests/test_golden_workflows.py", "-q")

$summary = [pscustomobject]@{
  schema_version = "2026.05.21"
  phase = 33
  status = if ($script:Failures.Count -eq 0) { "ready" } else { "blocked" }
  generated_at = (Get-Date).ToString("o")
  evidence_dir = ConvertTo-ProjectRelativePath $EvidenceDir
  contract = "evals/phase33-observability-ci-contract.json"
  slice = [string]$contract.slice
  workflow = [string]$contract.workflow
  quality_contract = [string]$contract.quality_contract
  commands = $commandResults
  failures = $script:Failures
  checks = $script:Checks
}

$jsonPath = Join-Path $EvidenceDir "observability-ci.json"
$markdownPath = Join-Path $EvidenceDir "observability-ci-summary.md"
$summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 33 Observability, Evals, And CI Evidence"
$markdown += ""
$markdown += "- Status: $($summary.status)"
$markdown += "- Generated at: $($summary.generated_at)"
$markdown += "- Evidence dir: $($summary.evidence_dir)"
$markdown += "- Slice: $($summary.slice)"
$markdown += "- Workflow: $($summary.workflow)"
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
  throw "Observability CI validation failed:`n - $($script:Failures -join "`n - ")"
}
