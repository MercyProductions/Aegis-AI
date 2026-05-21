param(
  [string]$Root = "",
  [string]$EvidenceDir = "",
  [switch]$AttemptDesktopSmoke,
  [switch]$AttemptVsCodeSmoke,
  [switch]$AttemptVisualStudioValidate,
  [switch]$AttemptReleasePackageDryRun,
  [switch]$AttemptUpdatePlanner
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Root)) {
  $ScriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
  $Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $ScriptRoot))
} else {
  $Root = [System.IO.Path]::GetFullPath($Root)
}

if ([string]::IsNullOrWhiteSpace($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\live-smoke-rc" (Get-Date -Format "yyyyMMdd-HHmmss"))
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

function Read-JsonIfPresent {
  param([Parameter(Mandatory = $true)][string]$Path)

  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return $null
  }
  try {
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
  } catch {
    return $null
  }
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

function Get-PayloadStatus {
  param([object]$Payload)

  if ($null -eq $Payload) {
    return "missing"
  }
  if ($null -ne $Payload.PSObject.Properties["status"]) {
    return [string]$Payload.status
  }
  if ($null -ne $Payload.PSObject.Properties["overall_status"]) {
    return [string]$Payload.overall_status
  }
  return "present"
}

function Get-LatestEvidence {
  param(
    [Parameter(Mandatory = $true)][string]$RootPath,
    [Parameter(Mandatory = $true)][string]$JsonName,
    [string]$SummaryName = ""
  )

  $fullRoot = Join-ProjectPath $RootPath
  if (-not (Test-Path -LiteralPath $fullRoot -PathType Container)) {
    return [pscustomobject]@{
      status = "missing"
      latest_folder = ""
      json_path = ""
      summary_path = ""
      summary_present = $false
      payload = $null
    }
  }

  foreach ($folder in @(Get-ChildItem -LiteralPath $fullRoot -Directory | Sort-Object Name -Descending)) {
    $jsonPath = Join-Path $folder.FullName $JsonName
    if (-not (Test-Path -LiteralPath $jsonPath -PathType Leaf)) {
      continue
    }
    $payload = Read-JsonIfPresent -Path $jsonPath
    $summaryPath = if ([string]::IsNullOrWhiteSpace($SummaryName)) { "" } else { Join-Path $folder.FullName $SummaryName }
    return [pscustomobject]@{
      status = Get-PayloadStatus $payload
      latest_folder = ConvertTo-ProjectRelativePath $folder.FullName
      json_path = ConvertTo-ProjectRelativePath $jsonPath
      summary_path = if (-not [string]::IsNullOrWhiteSpace($summaryPath) -and (Test-Path -LiteralPath $summaryPath -PathType Leaf)) { ConvertTo-ProjectRelativePath $summaryPath } else { "" }
      summary_present = -not [string]::IsNullOrWhiteSpace($summaryPath) -and (Test-Path -LiteralPath $summaryPath -PathType Leaf)
      payload = $payload
    }
  }

  return [pscustomobject]@{
    status = "missing"
    latest_folder = ""
    json_path = ""
    summary_path = ""
    summary_present = $false
    payload = $null
  }
}

function Get-GateObservation {
  param(
    [object]$ReleaseValidation,
    [Parameter(Mandatory = $true)][string]$GateId
  )

  if ($null -eq $ReleaseValidation -or $null -eq $ReleaseValidation.payload -or $null -eq $ReleaseValidation.payload.results) {
    return [pscustomobject]@{
      id = $GateId
      status = "not_observed"
      reason = "No release validation matrix is attached."
      closure_status = "not_observed"
    }
  }

  $gate = @($ReleaseValidation.payload.results | Where-Object { [string]$_.id -eq $GateId } | Select-Object -First 1)
  if ($gate.Count -eq 0) {
    return [pscustomobject]@{
      id = $GateId
      status = "not_observed"
      reason = "Gate was not present in the latest release validation matrix."
      closure_status = "not_observed"
    }
  }

  $status = [string]$gate[0].status
  $reason = [string]$gate[0].reason
  $closureStatus = switch ($status) {
    "passed" { "closed"; break }
    "skipped" { "requires_intentional_run"; break }
    "retryable" { "retry_after_environment_clears"; break }
    "failed" { "blocked"; break }
    default { "attention"; break }
  }

  return [pscustomobject]@{
    id = $GateId
    status = $status
    reason = $reason
    closure_status = $closureStatus
  }
}

function Invoke-LoggedCommand {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [Parameter(Mandatory = $true)][string]$Executable,
    [string[]]$Arguments = @(),
    [scriptblock]$FailureClassifier = $null
  )

  New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
  $resolvedWorkingDirectory = Join-ProjectPath $WorkingDirectory
  $logPath = Join-Path $EvidenceDir "$Id.log"
  $command = (@($Executable) + $Arguments) -join " "
  $started = Get-Date
  $status = "passed"
  $reason = ""
  $exitCode = 0

  @(
    "Command: $command",
    "Working directory: $resolvedWorkingDirectory",
    "Started: $($started.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))",
    ""
  ) | Set-Content -LiteralPath $logPath -Encoding UTF8

  try {
    Push-Location $resolvedWorkingDirectory
    $global:LASTEXITCODE = 0
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $Executable @Arguments *>> $logPath
    $ErrorActionPreference = $previousErrorActionPreference
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
    if ($exitCode -ne 0) {
      $status = "failed"
      $reason = "Exited with code $exitCode."
    }
  } catch {
    if ($null -ne (Get-Variable -Name previousErrorActionPreference -Scope Local -ErrorAction SilentlyContinue)) {
      $ErrorActionPreference = $previousErrorActionPreference
    }
    $status = "failed"
    $exitCode = 1
    $reason = $_.Exception.Message
    "" | Add-Content -LiteralPath $logPath -Encoding UTF8
    "Exception:" | Add-Content -LiteralPath $logPath -Encoding UTF8
    ($_ | Out-String) | Add-Content -LiteralPath $logPath -Encoding UTF8
  } finally {
    Pop-Location
  }

  if ($status -eq "failed" -and $null -ne $FailureClassifier) {
    $logText = if (Test-Path -LiteralPath $logPath -PathType Leaf) { Get-Content -LiteralPath $logPath -Raw } else { "" }
    $classification = & $FailureClassifier $logText
    if ($null -ne $classification) {
      $status = [string]$classification.status
      $reason = [string]$classification.reason
    }
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

  return [pscustomobject]@{
    id = $Id
    command = $command
    working_directory = ConvertTo-ProjectRelativePath $resolvedWorkingDirectory
    status = $status
    reason = $reason
    exit_code = $exitCode
    duration_seconds = $duration
    log = ConvertTo-ProjectRelativePath $logPath
  }
}

function Classify-VsCodeSmokeFailure {
  param([string]$LogText)

  $normalizedLogText = $LogText -replace "`0", ""
  if ($normalizedLogText -match 'vscode-updating|mutex|updat(e|ing)|another instance') {
    return [pscustomobject]@{
      status = "retryable"
      reason = "VS Code extension-host smoke was blocked by the VS Code update mutex."
    }
  }
  return $null
}

$EvidenceDir = Test-UnderRoot $EvidenceDir
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$contract = Read-ProjectJson "evals\phase36-live-smoke-rc-contract.json"
$validator = Read-ProjectFile "scripts\validate-ecosystem.ps1"
$ledgerDocs = Read-ProjectFile "docs\EVIDENCE_LEDGER.md"
$ledgerContractText = Read-ProjectFile "evals\phase16-evidence-ledger-contract.json"
$docsText = @(
  Read-ProjectFile "docs\LIVE_SMOKE_RC_SCOPING_EVIDENCE.md"
  Read-ProjectFile "docs\VALIDATION_MATRIX.md"
  Read-ProjectFile "docs\EVIDENCE_LEDGER.md"
  Read-ProjectFile "docs\EXTERNAL_ALPHA_RELEASE_NOTES.md"
  Read-ProjectFile "docs\EXTERNAL_ALPHA_RELEASE_REPORT.md"
  Read-ProjectFile "KNOWN_UNSTABLE_SURFACES.md"
  Read-ProjectFile "FULL_PROJECT_REMAINING_ROADMAP_2026-05-21.md"
  Read-ProjectFile "FULL_PROJECT_REVIEW_ROADMAP_2026-05-21.md"
  Read-ProjectFile "CHATBOT_PROJECT_REVIEW_ROADMAP_2026-05-21.md"
) -join "`n"

Add-Check -Id "contract-schema-version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Message "Phase 36 contract must use schema version 2026.05.21."
Add-Check -Id "contract-phase" -Passed ([int]$contract.phase -eq 36) -Message "Phase 36 contract must identify phase 36."
Add-Check -Id "contract-evidence-root" -Passed ([string]$contract.evidence_root -eq ".aegis/live-smoke-rc") -Message "Phase 36 evidence root must be .aegis/live-smoke-rc."
Add-Check -Id "contract-status" -Passed ([string]$contract.current_required_status -eq "ready") -Message "Phase 36 evidence contract status must be ready."

foreach ($file in @($contract.required_contract_files)) {
  $relativePath = [string]$file
  Add-Check -Id "contract-file-$(ConvertTo-CheckId $relativePath)" -Passed (Test-Path -LiteralPath (Join-ProjectPath $relativePath) -PathType Leaf) -Message "Required Phase 36 contract file must exist: $relativePath"
}

foreach ($marker in @($contract.required_doc_markers)) {
  $markerText = [string]$marker
  Add-Check -Id "doc-marker-$(ConvertTo-CheckId $markerText)" -Passed ($docsText -match [regex]::Escape($markerText)) -Message "Phase 36 docs must include '$markerText'."
}

foreach ($marker in @($contract.required_rc_scope_markers)) {
  $markerText = [string]$marker
  Add-Check -Id "scope-marker-$(ConvertTo-CheckId $markerText)" -Passed ($docsText.Contains($markerText) -or $validator.Contains($markerText)) -Message "Phase 36 scope must include marker '$markerText'."
}

Add-Check -Id "validator-gate" -Passed ($validator.Contains("test-live-smoke-rc.ps1") -and $validator.Contains("live-smoke-rc-contract")) -Message "Ecosystem validator must run the Phase 36 live smoke RC gate."
Add-Check -Id "ledger-doc-source" -Passed ($ledgerDocs.Contains(".aegis/live-smoke-rc") -or $ledgerDocs.Contains("live_smoke_rc")) -Message "Evidence ledger docs must include the Phase 36 live smoke RC source."
Add-Check -Id "ledger-contract-source" -Passed ($ledgerContractText.Contains("live_smoke_rc") -and $ledgerContractText.Contains(".aegis/live-smoke-rc")) -Message "Evidence ledger contract must include Phase 36 live smoke RC evidence."

$evidenceSources = @()
foreach ($source in @($contract.required_evidence_sources)) {
  $evidence = Get-LatestEvidence -RootPath ([string]$source.root) -JsonName ([string]$source.json) -SummaryName ([string]$source.summary)
  $accepted = @($source.accepted_statuses | ForEach-Object { [string]$_ })
  $isAccepted = $accepted -contains [string]$evidence.status
  $hasSummary = [bool]$evidence.summary_present
  Add-Check -Id "evidence-source-$([string]$source.id)" -Passed ($isAccepted -and $hasSummary) -Message "Required Phase 36 upstream evidence '$([string]$source.id)' must be attached with an accepted status and summary."
  $evidenceSources += [pscustomobject]@{
    id = [string]$source.id
    status = [string]$evidence.status
    accepted = $isAccepted
    latest_folder = [string]$evidence.latest_folder
    json_path = [string]$evidence.json_path
    summary_path = [string]$evidence.summary_path
  }
}

$releaseValidation = Get-LatestEvidence -RootPath ".aegis\release-evidence" -JsonName "validation-matrix.json" -SummaryName "validation-summary.md"
$gateObservations = @()
foreach ($gateId in @($contract.required_live_gate_ids)) {
  $gateObservations += Get-GateObservation -ReleaseValidation $releaseValidation -GateId ([string]$gateId)
}

$optionalAttempts = @()
if ($AttemptDesktopSmoke) {
  $optionalAttempts += Invoke-LoggedCommand -Id "desktop-smoke-attempt" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-ProjectPath "scripts\smoke-desktop.ps1"), "-SkipDashboard", "-UseIsolatedAppData")
}
if ($AttemptVsCodeSmoke) {
  $optionalAttempts += Invoke-LoggedCommand -Id "vscode-smoke-attempt" -WorkingDirectory "vscode-plugins\aegis-local-autopilot" -Executable "npm" -Arguments @("run", "test:smoke") -FailureClassifier ${function:Classify-VsCodeSmokeFailure}
}
if ($AttemptVisualStudioValidate) {
  $optionalAttempts += Invoke-LoggedCommand -Id "visual-studio-validate-attempt" -WorkingDirectory "visual-studio-extensions\aegis-local-agent-vs" -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-ProjectPath "visual-studio-extensions\aegis-local-agent-vs\build.ps1"), "-ValidateOnly")
}
if ($AttemptReleasePackageDryRun) {
  $optionalAttempts += Invoke-LoggedCommand -Id "release-package-dry-run-attempt" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-ProjectPath "scripts\test-release-package-dry-run.ps1"), "-Root", $Root, "-EvidenceDir", (Join-Path $EvidenceDir "release-package-dry-run-attempt"))
}
if ($AttemptUpdatePlanner) {
  foreach ($componentId in @("aegis-core", "website", "desktop", "vscode-extension", "visual-studio-extension")) {
    $optionalAttempts += Invoke-LoggedCommand -Id "update-plan-$componentId" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-ProjectPath "scripts\aegis-update.ps1"), "-Manifest", (Join-ProjectPath "release\version-manifest.json"), "-Component", $componentId, "-InstallRoot", $Root)
  }
}

$openGates = @($gateObservations | Where-Object { [string]$_.closure_status -ne "closed" })
$failedAttempts = @($optionalAttempts | Where-Object { [string]$_.status -eq "failed" })
$retryableAttempts = @($optionalAttempts | Where-Object { [string]$_.status -eq "retryable" })
$releaseCandidateStatus = if ($openGates.Count -eq 0 -and $failedAttempts.Count -eq 0 -and $retryableAttempts.Count -eq 0) { "ready" } else { "attention" }

$summary = [pscustomobject]@{
  schema_version = "2026.05.21"
  phase = 36
  status = if ($script:Failures.Count -eq 0) { "ready" } else { "blocked" }
  release_candidate_status = $releaseCandidateStatus
  generated_at = (Get-Date).ToString("o")
  evidence_dir = ConvertTo-ProjectRelativePath $EvidenceDir
  contract = "evals/phase36-live-smoke-rc-contract.json"
  slice = [string]$contract.slice
  latest_release_validation = [pscustomobject]@{
    status = [string]$releaseValidation.status
    latest_folder = [string]$releaseValidation.latest_folder
    json_path = [string]$releaseValidation.json_path
    summary_path = [string]$releaseValidation.summary_path
  }
  live_gate_closure = $gateObservations
  release_candidate_scope = [pscustomobject]@{
    intentional_release_artifact_decision = $false
    worktree_scope_required = $true
    github_target_pending = "Confirm MercyProductions/Aegis-AI before push."
    broad_alpha_blocked = $true
  }
  evidence_sources = $evidenceSources
  optional_attempts = $optionalAttempts
  failures = $script:Failures
  checks = $script:Checks
}

$jsonPath = Join-Path $EvidenceDir "live-smoke-rc.json"
$markdownPath = Join-Path $EvidenceDir "live-smoke-rc-summary.md"
$summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 36 Live Smoke Closure And Release Candidate Scoping Evidence"
$markdown += ""
$markdown += "- Status: $($summary.status)"
$markdown += "- Release candidate status: $($summary.release_candidate_status)"
$markdown += "- Generated at: $($summary.generated_at)"
$markdown += "- Evidence dir: $($summary.evidence_dir)"
$markdown += "- Contract: $($summary.contract)"
$markdown += "- Latest release validation: $($summary.latest_release_validation.latest_folder)"
$markdown += ""
$markdown += "## Live Gate Closure"
$markdown += ""
$markdown += "| Gate | Status | Closure | Reason |"
$markdown += "| --- | --- | --- | --- |"
foreach ($gate in @($summary.live_gate_closure)) {
  $reason = ([string]$gate.reason).Replace("|", "\|")
  $markdown += "| $($gate.id) | $($gate.status) | $($gate.closure_status) | $reason |"
}
$markdown += ""
$markdown += "## Scope"
$markdown += ""
$markdown += "- intentional_release_artifact_decision: $($summary.release_candidate_scope.intentional_release_artifact_decision)"
$markdown += "- worktree_scope_required: $($summary.release_candidate_scope.worktree_scope_required)"
$markdown += "- github_target_pending: $($summary.release_candidate_scope.github_target_pending)"
$markdown += "- broad_alpha_blocked: $($summary.release_candidate_scope.broad_alpha_blocked)"
$markdown += ""
$markdown += "## Evidence Sources"
$markdown += ""
$markdown += "| Source | Status | Accepted | Latest Folder |"
$markdown += "| --- | --- | --- | --- |"
foreach ($source in @($summary.evidence_sources)) {
  $markdown += "| $($source.id) | $($source.status) | $($source.accepted) | $($source.latest_folder) |"
}
$markdown += ""
$markdown += "## Optional Attempts"
$markdown += ""
$markdown += "| Attempt | Status | Seconds | Log |"
$markdown += "| --- | --- | ---: | --- |"
foreach ($attempt in @($summary.optional_attempts)) {
  $markdown += "| $($attempt.id) | $($attempt.status) | $($attempt.duration_seconds) | $($attempt.log) |"
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
  throw "Live smoke RC scoping validation failed:`n - $($script:Failures -join "`n - ")"
}
