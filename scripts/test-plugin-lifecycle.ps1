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
    throw "Required Phase 32 file is missing: $RelativePath"
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
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\plugin-lifecycle" (Get-Date -Format "yyyyMMdd-HHmmss"))
} elseif (-not [System.IO.Path]::IsPathRooted($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root $EvidenceDir
}
$EvidenceDir = Test-UnderRoot $EvidenceDir
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$script:Checks = @()
$script:Failures = @()
$contract = Read-ProjectJson "evals\phase32-plugin-lifecycle-contract.json"
$schemas = Read-ProjectFile ([string]$contract.schemas)
$productization = Read-ProjectFile ([string]$contract.productization_engine)
$ecosystem = Read-ProjectFile ([string]$contract.ecosystem_engine)
$storage = Read-ProjectFile ([string]$contract.storage)
$productizationRoutes = Read-ProjectFile ([string]$contract.productization_routes)
$ecosystemRoutes = Read-ProjectFile ([string]$contract.ecosystem_routes)
$backendMain = Read-ProjectFile ([string]$contract.backend_main)
$productizationTests = Read-ProjectFile ([string]$contract.productization_tests)
$ecosystemTests = Read-ProjectFile ([string]$contract.ecosystem_tests)
$docs = Read-ProjectFile "docs\PLUGIN_LIFECYCLE_EVIDENCE.md"
$pluginDocs = Read-ProjectFile "docs\PLUGIN_ECOSYSTEM.md"
$validationDocs = Read-ProjectFile "docs\VALIDATION_MATRIX.md"
$ledgerDocs = Read-ProjectFile "docs\EVIDENCE_LEDGER.md"
$ledgerContract = Read-ProjectFile "evals\phase16-evidence-ledger-contract.json"
$validator = Read-ProjectFile "scripts\validate-ecosystem.ps1"

Add-Check -Id "contract-schema-version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Message "Phase 32 contract must use schema version 2026.05.21."
Add-Check -Id "contract-evidence-root" -Passed ([string]$contract.evidence_root -eq ".aegis/plugin-lifecycle") -Message "Phase 32 evidence root must be .aegis/plugin-lifecycle."
Add-Check -Id "contract-required-status" -Passed ([string]$contract.current_required_status -eq "ready") -Message "Phase 32 required status must be ready."

foreach ($relativePath in @($contract.required_contract_files)) {
  Add-Check -Id "contract-file-$(ConvertTo-CheckId ([string]$relativePath))" -Passed (Test-Path -LiteralPath (Join-ProjectPath ([string]$relativePath)) -PathType Leaf) -Message "Required Phase 32 file must exist: $relativePath"
}
foreach ($marker in @($contract.required_schema_markers)) {
  Add-Check -Id "schema-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($schemas.Contains([string]$marker)) -Message "Schemas must include '$marker'."
}
foreach ($marker in @($contract.required_productization_markers)) {
  Add-Check -Id "productization-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($productization.Contains([string]$marker)) -Message "Productization engine must include '$marker'."
}
foreach ($marker in @($contract.required_ecosystem_markers)) {
  Add-Check -Id "ecosystem-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($ecosystem.Contains([string]$marker) -or $backendMain.Contains([string]$marker)) -Message "Ecosystem lifecycle must include '$marker'."
}
foreach ($marker in @($contract.required_storage_markers)) {
  Add-Check -Id "storage-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($storage.Contains([string]$marker)) -Message "Storage must include '$marker'."
}
foreach ($marker in @($contract.required_route_markers)) {
  $text = if ([string]$marker -like "/api/productization/*") { $productizationRoutes } else { $ecosystemRoutes }
  Add-Check -Id "route-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($text.Contains([string]$marker)) -Message "Lifecycle routes must include '$marker'."
}
foreach ($marker in @($contract.required_main_markers)) {
  Add-Check -Id "main-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($backendMain.Contains([string]$marker)) -Message "Backend main lifecycle wiring must include '$marker'."
}
foreach ($marker in @($contract.required_test_markers)) {
  Add-Check -Id "test-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed ($productizationTests.Contains([string]$marker) -or $ecosystemTests.Contains([string]$marker)) -Message "Phase 32 tests must cover '$marker'."
}

Add-Check -Id "docs-command" -Passed ($docs.Contains("test-plugin-lifecycle.ps1")) -Message "Plugin lifecycle docs must include the validation command."
Add-Check -Id "docs-evidence-root" -Passed ($docs.Contains(".aegis/plugin-lifecycle")) -Message "Plugin lifecycle docs must include the evidence root."
Add-Check -Id "plugin-docs-phase32" -Passed ($pluginDocs.Contains("phase32-plugin-lifecycle-contract.json") -and $pluginDocs.Contains("Rollback")) -Message "Plugin ecosystem docs must describe Phase 32 lifecycle evidence."
Add-Check -Id "validation-doc-gate" -Passed ($validationDocs.Contains("plugin-lifecycle-contract") -and $validationDocs.Contains("test-plugin-lifecycle")) -Message "Validation matrix must document the plugin lifecycle gate."
Add-Check -Id "ledger-doc-source" -Passed ($ledgerDocs.Contains(".aegis/plugin-lifecycle") -or $ledgerDocs.Contains("plugin_lifecycle")) -Message "Evidence ledger docs must include the plugin lifecycle source."
Add-Check -Id "ledger-contract-source" -Passed ($ledgerContract.Contains("plugin_lifecycle") -and $ledgerContract.Contains(".aegis/plugin-lifecycle")) -Message "Evidence ledger contract must include plugin lifecycle as a ledger source."
Add-Check -Id "validator-gate" -Passed ($validator.Contains("test-plugin-lifecycle.ps1") -and $validator.Contains("plugin-lifecycle-contract")) -Message "Ecosystem validator must run the plugin lifecycle gate."

$commandResults = @()
$commandResults += Invoke-LoggedCommand -Id "backend-productization-tests" -WorkingDirectory "website\backend" -Executable "python" -Arguments @("-m", "pytest", "tests/test_productization.py", "-q")
$commandResults += Invoke-LoggedCommand -Id "backend-ecosystem-tests" -WorkingDirectory "website\backend" -Executable "python" -Arguments @("-m", "pytest", "tests/test_ecosystem.py", "-q")

$summary = [pscustomobject]@{
  schema_version = "2026.05.21"
  phase = 32
  status = if ($script:Failures.Count -eq 0) { "ready" } else { "blocked" }
  generated_at = (Get-Date).ToString("o")
  evidence_dir = ConvertTo-ProjectRelativePath $EvidenceDir
  contract = "evals/phase32-plugin-lifecycle-contract.json"
  slice = [string]$contract.slice
  productization_routes = [string]$contract.productization_routes
  ecosystem_routes = [string]$contract.ecosystem_routes
  commands = $commandResults
  failures = $script:Failures
  checks = $script:Checks
}

$jsonPath = Join-Path $EvidenceDir "plugin-lifecycle.json"
$markdownPath = Join-Path $EvidenceDir "plugin-lifecycle-summary.md"
$summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 32 Plugin Lifecycle Evidence"
$markdown += ""
$markdown += "- Status: $($summary.status)"
$markdown += "- Generated at: $($summary.generated_at)"
$markdown += "- Evidence dir: $($summary.evidence_dir)"
$markdown += "- Slice: $($summary.slice)"
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
  throw "Plugin lifecycle validation failed:`n - $($script:Failures -join "`n - ")"
}
