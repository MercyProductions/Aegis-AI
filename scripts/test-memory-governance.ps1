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
    throw "Required Phase 31 file is missing: $RelativePath"
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
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\memory-governance" (Get-Date -Format "yyyyMMdd-HHmmss"))
} elseif (-not [System.IO.Path]::IsPathRooted($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root $EvidenceDir
}
$EvidenceDir = Test-UnderRoot $EvidenceDir
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$script:Checks = @()
$script:Failures = @()
$contract = Read-ProjectJson "evals\phase31-memory-governance-contract.json"
$backendService = Read-ProjectFile ([string]$contract.backend_service)
$backendCoreClient = Read-ProjectFile ([string]$contract.backend_core_client)
$backendRoutes = Read-ProjectFile ([string]$contract.backend_routes)
$backendMain = Read-ProjectFile ([string]$contract.backend_main)
$backendTests = Read-ProjectFile ([string]$contract.backend_tests)
$frontendApi = Read-ProjectFile ([string]$contract.frontend_api)
$frontendTypes = Read-ProjectFile ([string]$contract.frontend_types)
$frontendTests = Read-ProjectFile ([string]$contract.frontend_tests)
$docs = Read-ProjectFile "docs\MEMORY_GOVERNANCE_EVIDENCE.md"
$validationDocs = Read-ProjectFile "docs\VALIDATION_MATRIX.md"
$ledgerDocs = Read-ProjectFile "docs\EVIDENCE_LEDGER.md"
$ledgerContract = Read-ProjectFile "evals\phase16-evidence-ledger-contract.json"
$validator = Read-ProjectFile "scripts\validate-ecosystem.ps1"

Add-Check -Id "contract-schema-version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Message "Phase 31 contract must use schema version 2026.05.21."
Add-Check -Id "contract-evidence-root" -Passed ([string]$contract.evidence_root -eq ".aegis/memory-governance") -Message "Phase 31 evidence root must be .aegis/memory-governance."
Add-Check -Id "contract-required-status" -Passed ([string]$contract.current_required_status -eq "ready") -Message "Phase 31 required status must be ready."

foreach ($relativePath in @($contract.required_contract_files)) {
  $path = Join-ProjectPath ([string]$relativePath)
  Add-Check -Id "contract-file-$(ConvertTo-CheckId ([string]$relativePath))" -Passed (Test-Path -LiteralPath $path -PathType Leaf) -Message "Required Phase 31 file must exist: $relativePath"
}

foreach ($marker in @($contract.required_service_markers)) {
  Add-Check -Id "service-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($backendService.Contains([string]$marker)) -Message "Utility memory service must include '$marker'."
}

foreach ($marker in @($contract.required_core_client_markers)) {
  Add-Check -Id "core-client-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($backendCoreClient.Contains([string]$marker)) -Message "Core client must include '$marker'."
}

foreach ($marker in @($contract.required_route_markers)) {
  Add-Check -Id "route-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($backendRoutes.Contains([string]$marker)) -Message "Utility routes must include '$marker'."
}

foreach ($marker in @($contract.required_main_markers)) {
  Add-Check -Id "main-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($backendMain.Contains([string]$marker)) -Message "Backend main route wiring must include '$marker'."
}

foreach ($marker in @($contract.required_backend_test_markers)) {
  Add-Check -Id "backend-test-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($backendTests.Contains([string]$marker)) -Message "Backend memory governance tests must cover '$marker'."
}

foreach ($marker in @($contract.required_frontend_api_markers)) {
  Add-Check -Id "frontend-api-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($frontendApi.Contains([string]$marker)) -Message "Frontend memory API must include '$marker'."
}

foreach ($marker in @($contract.required_frontend_type_markers)) {
  Add-Check -Id "frontend-type-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($frontendTypes.Contains([string]$marker)) -Message "Frontend memory types must include '$marker'."
}

foreach ($marker in @($contract.required_frontend_test_markers)) {
  Add-Check -Id "frontend-test-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($frontendTests.Contains([string]$marker)) -Message "Frontend API tests must cover '$marker'."
}

Add-Check -Id "docs-command" -Passed ($docs.Contains("test-memory-governance.ps1")) -Message "Memory governance docs must include the validation command."
Add-Check -Id "docs-evidence-root" -Passed ($docs.Contains(".aegis/memory-governance")) -Message "Memory governance docs must include the evidence root."
Add-Check -Id "validation-doc-gate" -Passed ($validationDocs.Contains("memory-governance-contract") -and $validationDocs.Contains("test-memory-governance")) -Message "Validation matrix must document the memory governance gate."
Add-Check -Id "ledger-doc-source" -Passed ($ledgerDocs.Contains(".aegis/memory-governance") -or $ledgerDocs.Contains("memory_governance")) -Message "Evidence ledger docs must include the memory governance source."
Add-Check -Id "ledger-contract-source" -Passed ($ledgerContract.Contains("memory_governance") -and $ledgerContract.Contains(".aegis/memory-governance")) -Message "Evidence ledger contract must include memory governance as a ledger source."
Add-Check -Id "validator-gate" -Passed ($validator.Contains("test-memory-governance.ps1") -and $validator.Contains("memory-governance-contract")) -Message "Ecosystem validator must run the memory governance gate."

$commandResults = @()
$commandResults += Invoke-LoggedCommand -Id "backend-core-runtime-delegation-tests" -WorkingDirectory "website\backend" -Executable "python" -Arguments @("-m", "pytest", "tests/test_core_runtime_delegation.py", "-q")
$commandResults += Invoke-LoggedCommand -Id "frontend-api-tests" -WorkingDirectory "website\frontend" -Executable "npm" -Arguments @("test", "--", "api.test.ts")

$summary = [pscustomobject]@{
  schema_version = "2026.05.21"
  phase = 31
  status = if ($script:Failures.Count -eq 0) { "ready" } else { "blocked" }
  generated_at = (Get-Date).ToString("o")
  evidence_dir = ConvertTo-ProjectRelativePath $EvidenceDir
  contract = "evals/phase31-memory-governance-contract.json"
  slice = [string]$contract.slice
  backend_service = [string]$contract.backend_service
  backend_routes = [string]$contract.backend_routes
  frontend_api = [string]$contract.frontend_api
  commands = $commandResults
  failures = $script:Failures
  checks = $script:Checks
}

$jsonPath = Join-Path $EvidenceDir "memory-governance.json"
$markdownPath = Join-Path $EvidenceDir "memory-governance-summary.md"
$summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 31 Memory Governance Evidence"
$markdown += ""
$markdown += "- Status: $($summary.status)"
$markdown += "- Generated at: $($summary.generated_at)"
$markdown += "- Evidence dir: $($summary.evidence_dir)"
$markdown += "- Slice: $($summary.slice)"
$markdown += "- Backend service: $($summary.backend_service)"
$markdown += "- Backend routes: $($summary.backend_routes)"
$markdown += "- Frontend API: $($summary.frontend_api)"
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
  throw "Memory governance validation failed:`n - $($script:Failures -join "`n - ")"
}
