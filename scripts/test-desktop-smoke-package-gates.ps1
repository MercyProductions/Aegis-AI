param(
  [string]$Root = "",
  [string]$EvidenceDir = "",
  [switch]$AttemptDesktopSmoke,
  [switch]$AttemptReleasePackageDryRun,
  [switch]$AttemptUpdatePlanner,
  [switch]$IncludeDashboardSmoke
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
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\desktop-smoke-package-gates" (Get-Date -Format "yyyyMMdd-HHmmss"))
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

function Get-LatestAcceptedEvidence {
  param(
    [Parameter(Mandatory = $true)][string]$RootPath,
    [Parameter(Mandatory = $true)][string]$JsonName,
    [string]$SummaryName = "",
    [string[]]$AcceptedStatuses = @()
  )

  $fullRoot = Join-ProjectPath $RootPath
  if (-not (Test-Path -LiteralPath $fullRoot -PathType Container)) {
    return Get-LatestEvidence -RootPath $RootPath -JsonName $JsonName -SummaryName $SummaryName
  }

  foreach ($folder in @(Get-ChildItem -LiteralPath $fullRoot -Directory | Sort-Object Name -Descending)) {
    $jsonPath = Join-Path $folder.FullName $JsonName
    if (-not (Test-Path -LiteralPath $jsonPath -PathType Leaf)) {
      continue
    }
    $payload = Read-JsonIfPresent -Path $jsonPath
    $status = Get-PayloadStatus $payload
    $summaryPath = if ([string]::IsNullOrWhiteSpace($SummaryName)) { "" } else { Join-Path $folder.FullName $SummaryName }
    $summaryPresent = -not [string]::IsNullOrWhiteSpace($summaryPath) -and (Test-Path -LiteralPath $summaryPath -PathType Leaf)
    if (($AcceptedStatuses -contains $status) -and $summaryPresent) {
      return [pscustomobject]@{
        status = $status
        latest_folder = ConvertTo-ProjectRelativePath $folder.FullName
        json_path = ConvertTo-ProjectRelativePath $jsonPath
        summary_path = ConvertTo-ProjectRelativePath $summaryPath
        summary_present = $true
        payload = $payload
      }
    }
  }

  return Get-LatestEvidence -RootPath $RootPath -JsonName $JsonName -SummaryName $SummaryName
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
    "skipped" { "requires_execution"; break }
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

function New-GateAttempt {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][string]$GateId,
    [Parameter(Mandatory = $true)][string]$Status,
    [string]$Reason = "",
    [string]$Category = "",
    [string]$Command = "",
    [string]$Log = "",
    [string]$Artifacts = "",
    [double]$DurationSeconds = 0,
    [object]$ExitCode = $null
  )

  return [pscustomobject]@{
    id = $Id
    gate_id = $GateId
    status = $Status
    reason = $Reason
    category = $Category
    command = $Command
    log = $Log
    artifacts = $Artifacts
    duration_seconds = $DurationSeconds
    exit_code = $ExitCode
    owner = "Release owner"
  }
}

function Format-CommandLine {
  param(
    [Parameter(Mandatory = $true)][string]$Executable,
    [string[]]$Arguments = @()
  )

  $parts = @($Executable) + $Arguments
  $quoted = @()
  foreach ($part in $parts) {
    $text = [string]$part
    if ($text -match '\s') {
      $quoted += '"' + ($text -replace '"', '\"') + '"'
    } else {
      $quoted += $text
    }
  }
  return ($quoted -join " ")
}

function Classify-DesktopSmokeFailure {
  param([string]$LogText)

  if ($LogText -match 'desktop exe was not found|Run build\.ps1 first') {
    return [pscustomobject]@{ status = "blocked"; category = "package"; reason = "Desktop executable is missing; run the native Release build before smoke." }
  }
  if ($LogText -match 'Timed out waiting|MainWindowHandle|Start-Process') {
    return [pscustomobject]@{ status = "blocked"; category = "ui_startup"; reason = "Desktop process did not expose a usable main window." }
  }
  if ($LogText -match 'appears blank|non-black ratio') {
    return [pscustomobject]@{ status = "blocked"; category = "ui_render"; reason = "Desktop smoke capture appears blank or below the nonblack-pixel threshold." }
  }
  if ($LogText -match 'user32\.dll|System\.Windows\.Forms|interactive|desktop heap|session') {
    return [pscustomobject]@{ status = "retryable"; category = "environment"; reason = "Desktop smoke needs an interactive Windows session with capture APIs available." }
  }
  return [pscustomobject]@{ status = "blocked"; category = "runtime"; reason = "Desktop smoke command exited non-zero; inspect the log for the concrete runtime failure." }
}

function Invoke-LoggedCommand {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][string]$GateId,
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [Parameter(Mandatory = $true)][string]$Executable,
    [string[]]$Arguments = @(),
    [string]$Artifacts = "",
    [scriptblock]$FailureClassifier = $null
  )

  New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
  $resolvedWorkingDirectory = Join-ProjectPath $WorkingDirectory
  $logPath = Join-Path $EvidenceDir "$Id.log"
  $command = Format-CommandLine -Executable $Executable -Arguments $Arguments
  $started = Get-Date
  $status = "passed"
  $reason = ""
  $category = ""
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
      $status = "blocked"
      $reason = "Exited with code $exitCode."
      $category = "command"
    }
  } catch {
    if ($null -ne (Get-Variable -Name previousErrorActionPreference -Scope Local -ErrorAction SilentlyContinue)) {
      $ErrorActionPreference = $previousErrorActionPreference
    }
    $status = "blocked"
    $exitCode = 1
    $reason = $_.Exception.Message
    $category = "exception"
    "" | Add-Content -LiteralPath $logPath -Encoding UTF8
    "Exception:" | Add-Content -LiteralPath $logPath -Encoding UTF8
    ($_ | Out-String) | Add-Content -LiteralPath $logPath -Encoding UTF8
  } finally {
    Pop-Location
  }

  if ($status -eq "blocked" -and $null -ne $FailureClassifier) {
    $logText = if (Test-Path -LiteralPath $logPath -PathType Leaf) { Get-Content -LiteralPath $logPath -Raw } else { "" }
    $classification = & $FailureClassifier $logText
    if ($null -ne $classification) {
      $status = [string]$classification.status
      $reason = [string]$classification.reason
      $category = [string]$classification.category
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
    "Category: $category",
    "Reason: $reason"
  ) | Add-Content -LiteralPath $logPath -Encoding UTF8

  return New-GateAttempt -Id $Id -GateId $GateId -Status $status -Reason $reason -Category $category -Command $command -Log (ConvertTo-ProjectRelativePath $logPath) -Artifacts $Artifacts -DurationSeconds $duration -ExitCode $exitCode
}

$EvidenceDir = Test-UnderRoot $EvidenceDir
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$contract = Read-ProjectJson "evals\phase38-desktop-smoke-package-gates-contract.json"
$validator = Read-ProjectFile "scripts\validate-ecosystem.ps1"
$ledgerDocs = Read-ProjectFile "docs\EVIDENCE_LEDGER.md"
$ledgerContractText = Read-ProjectFile "evals\phase16-evidence-ledger-contract.json"
$docsText = @(
  Read-ProjectFile "docs\DESKTOP_SMOKE_PACKAGE_GATES_EVIDENCE.md"
  Read-ProjectFile "docs\VALIDATION_MATRIX.md"
  Read-ProjectFile "docs\EVIDENCE_LEDGER.md"
  Read-ProjectFile "docs\EXTERNAL_ALPHA_RELEASE_NOTES.md"
  Read-ProjectFile "docs\EXTERNAL_ALPHA_RELEASE_REPORT.md"
  Read-ProjectFile "KNOWN_UNSTABLE_SURFACES.md"
  Read-ProjectFile "FULL_PROJECT_REMAINING_ROADMAP_2026-05-21.md"
  Read-ProjectFile "FULL_PROJECT_REVIEW_ROADMAP_2026-05-21.md"
  Read-ProjectFile "CHATBOT_PROJECT_REVIEW_ROADMAP_2026-05-21.md"
) -join "`n"

Add-Check -Id "contract-schema-version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Message "Phase 38 contract must use schema version 2026.05.21."
Add-Check -Id "contract-phase" -Passed ([int]$contract.phase -eq 38) -Message "Phase 38 contract must identify phase 38."
Add-Check -Id "contract-evidence-root" -Passed ([string]$contract.evidence_root -eq ".aegis/desktop-smoke-package-gates") -Message "Phase 38 evidence root must be .aegis/desktop-smoke-package-gates."
Add-Check -Id "contract-status" -Passed ([string]$contract.current_required_status -eq "ready") -Message "Phase 38 evidence contract status must be ready."

foreach ($file in @($contract.required_contract_files)) {
  $relativePath = [string]$file
  Add-Check -Id "contract-file-$(ConvertTo-CheckId $relativePath)" -Passed (Test-Path -LiteralPath (Join-ProjectPath $relativePath) -PathType Leaf) -Message "Required Phase 38 contract file must exist: $relativePath"
}

foreach ($marker in @($contract.required_doc_markers)) {
  $markerText = [string]$marker
  Add-Check -Id "doc-marker-$(ConvertTo-CheckId $markerText)" -Passed ($docsText -match [regex]::Escape($markerText)) -Message "Phase 38 docs must include '$markerText'."
}

foreach ($marker in @($contract.required_execution_markers)) {
  $markerText = [string]$marker
  Add-Check -Id "execution-marker-$(ConvertTo-CheckId $markerText)" -Passed ($docsText.Contains($markerText) -or $validator.Contains($markerText) -or (Read-ProjectFile "scripts\test-desktop-smoke-package-gates.ps1").Contains($markerText)) -Message "Phase 38 execution scope must include marker '$markerText'."
}

Add-Check -Id "validator-gate" -Passed ($validator.Contains("test-desktop-smoke-package-gates.ps1") -and $validator.Contains("desktop-smoke-package-gates-contract")) -Message "Ecosystem validator must run the Phase 38 desktop smoke package gates contract."
Add-Check -Id "ledger-doc-source" -Passed ($ledgerDocs.Contains(".aegis/desktop-smoke-package-gates") -or $ledgerDocs.Contains("desktop_smoke_package_gates")) -Message "Evidence ledger docs must include the Phase 38 desktop smoke package gates source."
Add-Check -Id "ledger-contract-source" -Passed ($ledgerContractText.Contains("desktop_smoke_package_gates") -and $ledgerContractText.Contains(".aegis/desktop-smoke-package-gates")) -Message "Evidence ledger contract must include Phase 38 desktop smoke package gate evidence."

$evidenceSources = @()
foreach ($source in @($contract.required_evidence_sources)) {
  $accepted = @($source.accepted_statuses | ForEach-Object { [string]$_ })
  $evidence = Get-LatestAcceptedEvidence -RootPath ([string]$source.root) -JsonName ([string]$source.json) -SummaryName ([string]$source.summary) -AcceptedStatuses $accepted
  $isAccepted = $accepted -contains [string]$evidence.status
  $hasSummary = [bool]$evidence.summary_present
  Add-Check -Id "evidence-source-$([string]$source.id)" -Passed ($isAccepted -and $hasSummary) -Message "Required Phase 38 upstream evidence '$([string]$source.id)' must be attached with an accepted status and summary."
  $evidenceSources += [pscustomobject]@{
    id = [string]$source.id
    status = [string]$evidence.status
    accepted = $isAccepted
    latest_folder = [string]$evidence.latest_folder
    json_path = [string]$evidence.json_path
    summary_path = [string]$evidence.summary_path
  }
}

$releaseValidationSource = @($evidenceSources | Where-Object { [string]$_.id -eq "release_validation" } | Select-Object -First 1)
$releaseValidation = if ($null -ne $releaseValidationSource -and -not [string]::IsNullOrWhiteSpace([string]$releaseValidationSource.latest_folder)) {
  Get-LatestAcceptedEvidence -RootPath ".aegis\release-evidence" -JsonName "validation-matrix.json" -SummaryName "validation-summary.md" -AcceptedStatuses @("attention", "passed")
} else {
  $null
}

$targetGateObservations = @()
foreach ($gateId in @($contract.target_gate_ids)) {
  $targetGateObservations += Get-GateObservation -ReleaseValidation $releaseValidation -GateId ([string]$gateId)
}

$gateAttempts = @()
$desktopArtifacts = Join-Path $EvidenceDir "desktop-smoke-artifacts"
if ($AttemptDesktopSmoke) {
  $desktopArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-ProjectPath "scripts\smoke-desktop.ps1"), "-OutputDir", $desktopArtifacts, "-UseIsolatedAppData")
  if (-not $IncludeDashboardSmoke) {
    $desktopArgs += "-SkipDashboard"
  }
  $gateAttempts += Invoke-LoggedCommand -Id "desktop-smoke-attempt" -GateId "desktop-smoke" -WorkingDirectory "." -Executable "powershell" -Arguments $desktopArgs -Artifacts (ConvertTo-ProjectRelativePath $desktopArtifacts) -FailureClassifier ${function:Classify-DesktopSmokeFailure}
} else {
  $gateAttempts += New-GateAttempt -Id "desktop-smoke-attempt" -GateId "desktop-smoke" -Status "not_run" -Reason "Run with -AttemptDesktopSmoke to execute desktop smoke with isolated app data." -Category "needs_explicit_attempt" -Artifacts (ConvertTo-ProjectRelativePath $desktopArtifacts)
}

if ($AttemptReleasePackageDryRun) {
  $packageEvidenceDir = Join-Path $EvidenceDir "release-package-dry-run-attempt"
  $gateAttempts += Invoke-LoggedCommand -Id "release-package-dry-run-attempt" -GateId "release-package-dry-run" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-ProjectPath "scripts\test-release-package-dry-run.ps1"), "-Root", $Root, "-EvidenceDir", $packageEvidenceDir) -Artifacts (ConvertTo-ProjectRelativePath $packageEvidenceDir)
} else {
  $gateAttempts += New-GateAttempt -Id "release-package-dry-run-attempt" -GateId "release-package-dry-run" -Status "not_run" -Reason "Run with -AttemptReleasePackageDryRun to refresh non-root package dry-run evidence." -Category "needs_explicit_attempt"
}

if ($AttemptUpdatePlanner) {
  $manifestPath = Join-ProjectPath "release\version-manifest.json"
  $gateAttempts += Invoke-LoggedCommand -Id "update-plan-dry-run-attempt" -GateId "update-plan-dry-run" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-ProjectPath "scripts\aegis-update.ps1"), "-Manifest", $manifestPath, "-Component", "aegis-core", "-InstallRoot", $Root)
} else {
  $gateAttempts += New-GateAttempt -Id "update-plan-dry-run-attempt" -GateId "update-plan-dry-run" -Status "not_run" -Reason "Update planner already runs in the ecosystem matrix; run with -AttemptUpdatePlanner to capture standalone Phase 38 evidence." -Category "needs_explicit_attempt"
}

$gateAttempts += New-GateAttempt -Id "visual-studio-package-decision" -GateId "visual-studio-package" -Status "not_run" -Reason "Visual Studio package mutates extension release artifacts and requires an explicit release artifact decision." -Category "release_artifact_decision_required"
$gateAttempts += New-GateAttempt -Id "final-release-manifest-decision" -GateId "final-release-manifest-contract" -Status "not_run" -Reason "Final release manifest mutates the root release folder and requires an explicit release artifact decision." -Category "release_artifact_decision_required"

$desktopSmokeAttempt = @($gateAttempts | Where-Object { [string]$_.gate_id -eq "desktop-smoke" } | Select-Object -First 1)
$packageGateDecisions = @($gateAttempts | Where-Object { [string]$_.gate_id -ne "desktop-smoke" })
$convertedAttempts = @($gateAttempts | Where-Object { @("passed", "retryable", "blocked") -contains [string]$_.status })
$executionStatus = if ($convertedAttempts.Count -gt 0) { "ready" } else { "attention" }

$ownerNextActions = @()
foreach ($attempt in @($gateAttempts | Where-Object { [string]$_.status -ne "passed" })) {
  $ownerNextActions += [pscustomobject]@{
    gate_id = [string]$attempt.gate_id
    owner = "Release owner"
    next_action = [string]$attempt.reason
    category = [string]$attempt.category
  }
}

$summary = [pscustomobject]@{
  schema_version = "2026.05.21"
  phase = 38
  status = if ($script:Failures.Count -eq 0) { "ready" } else { "blocked" }
  execution_status = $executionStatus
  generated_at = (Get-Date).ToString("o")
  evidence_dir = ConvertTo-ProjectRelativePath $EvidenceDir
  contract = "evals/phase38-desktop-smoke-package-gates-contract.json"
  slice = [string]$contract.slice
  target_gate_observations = $targetGateObservations
  gate_attempts = $gateAttempts
  desktop_smoke_attempt = $desktopSmokeAttempt
  package_gate_decisions = $packageGateDecisions
  owner_next_actions = $ownerNextActions
  artifacts = [pscustomobject]@{
    desktop_smoke_output = ConvertTo-ProjectRelativePath $desktopArtifacts
    command_logs = @($gateAttempts | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_.log) } | ForEach-Object { [string]$_.log })
  }
  phase36_refresh_required = $convertedAttempts.Count -gt 0
  phase37_refresh_required = $convertedAttempts.Count -gt 0
  evidence_sources = $evidenceSources
  failures = $script:Failures
  checks = $script:Checks
}

$jsonPath = Join-Path $EvidenceDir "desktop-smoke-package-gates.json"
$markdownPath = Join-Path $EvidenceDir "desktop-smoke-package-gates-summary.md"
$summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 38 Desktop Smoke And Package Gate Evidence"
$markdown += ""
$markdown += "- Status: $($summary.status)"
$markdown += "- Execution status: $($summary.execution_status)"
$markdown += "- Generated at: $($summary.generated_at)"
$markdown += "- Evidence dir: $($summary.evidence_dir)"
$markdown += "- Contract: $($summary.contract)"
$markdown += "- Phase 36 refresh required: $($summary.phase36_refresh_required)"
$markdown += "- Phase 37 refresh required: $($summary.phase37_refresh_required)"
$markdown += ""
$markdown += "## Target Gate Observations"
$markdown += ""
$markdown += "| Gate | Latest Status | Closure | Reason |"
$markdown += "| --- | --- | --- | --- |"
foreach ($gate in @($summary.target_gate_observations)) {
  $reason = ([string]$gate.reason).Replace("|", "\|")
  $markdown += "| $($gate.id) | $($gate.status) | $($gate.closure_status) | $reason |"
}
$markdown += ""
$markdown += "## Gate Attempts"
$markdown += ""
$markdown += "| Attempt | Gate | Status | Category | Reason | Artifacts | Log |"
$markdown += "| --- | --- | --- | --- | --- | --- | --- |"
foreach ($attempt in @($summary.gate_attempts)) {
  $reason = ([string]$attempt.reason).Replace("|", "\|")
  $markdown += "| $($attempt.id) | $($attempt.gate_id) | $($attempt.status) | $($attempt.category) | $reason | $($attempt.artifacts) | $($attempt.log) |"
}
$markdown += ""
$markdown += "## Owner Next Actions"
$markdown += ""
$markdown += "| Gate | Owner | Category | Next Action |"
$markdown += "| --- | --- | --- | --- |"
foreach ($action in @($summary.owner_next_actions)) {
  $nextAction = ([string]$action.next_action).Replace("|", "\|")
  $markdown += "| $($action.gate_id) | $($action.owner) | $($action.category) | $nextAction |"
}
$markdown += ""
$markdown += "## Evidence Sources"
$markdown += ""
$markdown += "| Source | Status | Accepted | Latest Folder |"
$markdown += "| --- | --- | --- | --- |"
foreach ($source in @($summary.evidence_sources)) {
  $markdown += "| $($source.id) | $($source.status) | $($source.accepted) | $($source.latest_folder) |"
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
  throw "Desktop smoke package gate validation failed:`n - $($script:Failures -join "`n - ")"
}
