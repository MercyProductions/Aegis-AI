param(
  [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
  [string]$EvidenceDir = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\alpha-readiness-polish" (Get-Date -Format "yyyyMMdd-HHmmss"))
} elseif (-not [System.IO.Path]::IsPathRooted($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root $EvidenceDir
}

$script:Checks = @()
$script:Failures = @()

function Join-ProjectPath {
  param([Parameter(Mandatory = $true)][string]$Path)
  if ([System.IO.Path]::IsPathRooted($Path)) {
    return $Path
  }
  return Join-Path $Root $Path
}

function ConvertTo-ProjectRelativePath {
  param([Parameter(Mandatory = $true)][string]$Path)
  $resolved = [System.IO.Path]::GetFullPath($Path)
  $resolvedRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
  if ($resolved.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    return $resolved.Substring($resolvedRoot.Length).TrimStart('\', '/')
  }
  return $Path
}

function ConvertTo-CheckId {
  param([Parameter(Mandatory = $true)][string]$Value)
  return (($Value.ToLowerInvariant() -replace '[^a-z0-9]+', '-') -replace '^-|-$', '')
}

function Read-ProjectFile {
  param([Parameter(Mandatory = $true)][string]$Path)
  $fullPath = Join-ProjectPath $Path
  if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
    return ""
  }
  return Get-Content -LiteralPath $fullPath -Raw
}

function Read-ProjectJson {
  param([Parameter(Mandatory = $true)][string]$Path)
  $fullPath = Join-ProjectPath $Path
  if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
    throw "Missing required JSON file: $Path"
  }
  return Get-Content -LiteralPath $fullPath -Raw | ConvertFrom-Json
}

function Add-Check {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][bool]$Passed,
    [Parameter(Mandatory = $true)][string]$Message
  )

  $script:Checks += [pscustomobject]@{
    id = $Id
    passed = $Passed
    message = $Message
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

  New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
  $logPath = Join-Path $EvidenceDir "$Id.log"
  $started = Get-Date
  Push-Location (Join-ProjectPath $WorkingDirectory)
  try {
    "Command: $Executable $($Arguments -join ' ')" | Set-Content -LiteralPath $logPath -Encoding UTF8
    "Working directory: $(Get-Location)" | Add-Content -LiteralPath $logPath -Encoding UTF8
    "Started: $($started.ToUniversalTime().ToString('o'))" | Add-Content -LiteralPath $logPath -Encoding UTF8
    "" | Add-Content -LiteralPath $logPath -Encoding UTF8
    & $Executable @Arguments 2>&1 | ForEach-Object { [string]$_ } | Add-Content -LiteralPath $logPath -Encoding UTF8
    $exitCode = if ($null -ne $LASTEXITCODE) { [int]$LASTEXITCODE } else { 0 }
  } catch {
    $_ | Add-Content -LiteralPath $logPath -Encoding UTF8
    $exitCode = 1
  } finally {
    Pop-Location
  }
  $ended = Get-Date
  "" | Add-Content -LiteralPath $logPath -Encoding UTF8
  "Ended: $($ended.ToUniversalTime().ToString('o'))" | Add-Content -LiteralPath $logPath -Encoding UTF8
  "Duration seconds: $([Math]::Round(($ended - $started).TotalSeconds, 2))" | Add-Content -LiteralPath $logPath -Encoding UTF8
  "Exit code: $exitCode" | Add-Content -LiteralPath $logPath -Encoding UTF8
  return [pscustomobject]@{
    id = $Id
    status = if ($exitCode -eq 0) { "passed" } else { "failed" }
    exit_code = $exitCode
    duration_seconds = [Math]::Round(($ended - $started).TotalSeconds, 2)
    log = ConvertTo-ProjectRelativePath $logPath
  }
}

function Get-LatestEvidence {
  param(
    [Parameter(Mandatory = $true)][pscustomobject]$Source
  )

  $rootPath = Join-ProjectPath ([string]$Source.root)
  $jsonName = [string]$Source.json
  $accepted = @($Source.accepted_statuses | ForEach-Object { [string]$_ })
  $result = [pscustomobject]@{
    id = [string]$Source.id
    root = [string]$Source.root
    latest_folder = ""
    json_path = ""
    status = "missing"
    accepted = $false
  }
  if (-not (Test-Path -LiteralPath $rootPath -PathType Container)) {
    return $result
  }
  $folders = @(Get-ChildItem -LiteralPath $rootPath -Directory | Sort-Object Name -Descending)
  foreach ($folder in $folders) {
    $jsonPath = Join-Path $folder.FullName $jsonName
    if (-not (Test-Path -LiteralPath $jsonPath -PathType Leaf)) {
      continue
    }
    $json = Get-Content -LiteralPath $jsonPath -Raw | ConvertFrom-Json
    $status = [string]$json.status
    $result.latest_folder = ConvertTo-ProjectRelativePath $folder.FullName
    $result.json_path = ConvertTo-ProjectRelativePath $jsonPath
    $result.status = $status
    $result.accepted = $accepted -contains $status
    return $result
  }
  return $result
}

$contract = Read-ProjectJson "evals\phase35-alpha-readiness-polish-contract.json"
$alphaSource = Read-ProjectFile "aegis-core\aegis_core\alpha.py"
$alphaTests = Read-ProjectFile "aegis-core\tests\test_alpha_readiness.py"
$docsText = @(
  Read-ProjectFile "docs\ALPHA_READINESS_POLISH_EVIDENCE.md"
  Read-ProjectFile "docs\CONTROLLED_EXTERNAL_ALPHA.md"
  Read-ProjectFile "docs\FIRST_RUN_ONBOARDING.md"
  Read-ProjectFile "docs\EXTERNAL_ALPHA_RELEASE_NOTES.md"
  Read-ProjectFile "KNOWN_UNSTABLE_SURFACES.md"
  Read-ProjectFile "docs\VALIDATION_MATRIX.md"
  Read-ProjectFile "docs\EVIDENCE_LEDGER.md"
) -join "`n"
$validator = Read-ProjectFile "scripts\validate-ecosystem.ps1"

Add-Check -Id "contract-schema-version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Message "Phase 35 contract must use schema version 2026.05.21."
Add-Check -Id "contract-phase" -Passed ([int]$contract.phase -eq 35) -Message "Phase 35 contract must identify phase 35."
Add-Check -Id "contract-evidence-root" -Passed ([string]$contract.evidence_root -eq ".aegis/alpha-readiness-polish") -Message "Phase 35 evidence root must be .aegis/alpha-readiness-polish."
Add-Check -Id "contract-status" -Passed ([string]$contract.current_required_status -eq "ready") -Message "Phase 35 required status must be ready."

foreach ($file in @($contract.required_contract_files)) {
  $relativePath = [string]$file
  Add-Check -Id "contract-file-$(ConvertTo-CheckId $relativePath)" -Passed (Test-Path -LiteralPath (Join-ProjectPath $relativePath) -PathType Leaf) -Message "Required Phase 35 contract file must exist: $relativePath"
}

foreach ($tier in @($contract.required_feature_tiers)) {
  $tierText = [string]$tier
  Add-Check -Id "feature-tier-$tierText" -Passed ($alphaSource.Contains($tierText) -or $docsText.Contains($tierText)) -Message "Phase 35 handoff must include feature tier '$tierText'."
}

foreach ($step in @($contract.required_default_alpha_path)) {
  $stepText = [string]$step
  Add-Check -Id "default-path-$stepText" -Passed ($alphaSource.Contains($stepText) -or $docsText.Contains($stepText)) -Message "Phase 35 handoff must include default alpha path step '$stepText'."
}

foreach ($marker in @($contract.required_handoff_markers)) {
  $markerText = [string]$marker
  Add-Check -Id "source-marker-$(ConvertTo-CheckId $markerText)" -Passed ($alphaSource.Contains($markerText)) -Message "Core alpha runtime must include marker '$markerText'."
}

foreach ($marker in @($contract.required_doc_markers)) {
  $markerText = [string]$marker
  Add-Check -Id "doc-marker-$(ConvertTo-CheckId $markerText)" -Passed ($docsText -match [regex]::Escape($markerText)) -Message "Phase 35 docs must include '$markerText'."
}

Add-Check -Id "test-handoff-summary" -Passed ($alphaTests.Contains("test_alpha_handoff_summary_labels_default_path_and_blockers")) -Message "Alpha readiness tests must cover Phase 35 handoff summary labels, default path, and blockers."
Add-Check -Id "readiness-includes-handoff" -Passed ($alphaSource.Contains('"handoff_summary": alpha_handoff_summary()')) -Message "Alpha readiness payload must include the Phase 35 handoff summary."
Add-Check -Id "validator-gate" -Passed ($validator.Contains("test-alpha-readiness-polish.ps1") -and $validator.Contains("alpha-readiness-polish-contract")) -Message "Ecosystem validator must run the Phase 35 alpha readiness polish gate."

$evidenceSources = @()
foreach ($source in @($contract.required_evidence_sources)) {
  $evidence = Get-LatestEvidence -Source $source
  $evidenceSources += $evidence
  Add-Check -Id "evidence-source-$($evidence.id)" -Passed ([bool]$evidence.accepted) -Message "Required Phase 35 upstream evidence '$($evidence.id)' must be attached with an accepted status."
}

$commands = @()
$commands += Invoke-LoggedCommand -Id "alpha-readiness-tests" -WorkingDirectory "aegis-core" -Executable "python" -Arguments @("-m", "pytest", "tests/test_alpha_readiness.py", "-q")
Add-Check -Id "alpha-readiness-tests" -Passed ($commands[-1].status -eq "passed") -Message "Core alpha readiness tests must pass."

$summary = [pscustomobject]@{
  schema_version = "2026.05.21"
  phase = 35
  status = if ($script:Failures.Count -eq 0) { "ready" } else { "blocked" }
  generated_at = (Get-Date).ToString("o")
  evidence_dir = ConvertTo-ProjectRelativePath $EvidenceDir
  contract = "evals/phase35-alpha-readiness-polish-contract.json"
  slice = [string]$contract.slice
  default_alpha_path = @($contract.required_default_alpha_path)
  feature_tiers = @($contract.required_feature_tiers)
  evidence_sources = $evidenceSources
  commands = $commands
  failures = $script:Failures
  checks = $script:Checks
}

New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$jsonPath = Join-Path $EvidenceDir "alpha-readiness-polish.json"
$markdownPath = Join-Path $EvidenceDir "alpha-readiness-polish-summary.md"
$summary | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 35 Alpha Readiness Polish Evidence"
$markdown += ""
$markdown += "- Status: $($summary.status)"
$markdown += "- Generated at: $($summary.generated_at)"
$markdown += "- Evidence dir: $($summary.evidence_dir)"
$markdown += "- Contract: $($summary.contract)"
$markdown += ""
$markdown += "## Feature Tiers"
$markdown += ""
foreach ($tier in @($summary.feature_tiers)) {
  $markdown += "- $tier"
}
$markdown += ""
$markdown += "## Default Alpha Path"
$markdown += ""
foreach ($step in @($summary.default_alpha_path)) {
  $markdown += "- $step"
}
$markdown += ""
$markdown += "## Evidence Sources"
$markdown += ""
$markdown += "| Source | Status | Accepted | Latest Folder |"
$markdown += "| --- | --- | --- | --- |"
foreach ($source in $evidenceSources) {
  $markdown += "| $($source.id) | $($source.status) | $($source.accepted) | $($source.latest_folder) |"
}
$markdown += ""
$markdown += "## Commands"
$markdown += ""
$markdown += "| Command | Status | Seconds | Log |"
$markdown += "| --- | --- | ---: | --- |"
foreach ($command in $commands) {
  $markdown += "| $($command.id) | $($command.status) | $($command.duration_seconds) | $($command.log) |"
}
$markdown += ""
$markdown += "## Checks"
$markdown += ""
$markdown += "| Check | Status | Message |"
$markdown += "| --- | --- | --- |"
foreach ($check in $script:Checks) {
  $markdown += "| $($check.id) | $(if ($check.passed) { 'passed' } else { 'failed' }) | $($check.message) |"
}
$markdown | Set-Content -LiteralPath $markdownPath -Encoding UTF8

$summary | ConvertTo-Json -Depth 10

if ($script:Failures.Count -gt 0) {
  throw "Alpha readiness polish validation failed:`n - $($script:Failures -join "`n - ")"
}
