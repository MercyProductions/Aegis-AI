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

if ([string]::IsNullOrWhiteSpace($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\commit-scoping-github-handoff" (Get-Date -Format "yyyyMMdd-HHmmss"))
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

function Invoke-GitLines {
  param([Parameter(Mandatory = $true)][string[]]$Arguments)

  $output = & git -C $Root @Arguments 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "git $($Arguments -join ' ') failed: $($output -join [Environment]::NewLine)"
  }
  return @($output | ForEach-Object { [string]$_ })
}

function Get-RemoteUrl {
  try {
    return ((Invoke-GitLines -Arguments @("remote", "get-url", "origin")) | Select-Object -First 1)
  } catch {
    return ""
  }
}

function Get-BranchName {
  try {
    return ((Invoke-GitLines -Arguments @("branch", "--show-current")) | Select-Object -First 1)
  } catch {
    return ""
  }
}

function Normalize-StatusPath {
  param([Parameter(Mandatory = $true)][string]$Path)

  $trimmed = $Path.Trim()
  if ($trimmed.StartsWith('"') -and $trimmed.EndsWith('"')) {
    $trimmed = $trimmed.Substring(1, $trimmed.Length - 2)
    $trimmed = $trimmed.Replace('\"', '"')
  }
  return $trimmed.Replace('\', '/')
}

function Get-StatusEntries {
  $lines = Invoke-GitLines -Arguments @("status", "--short")
  $entries = @()
  foreach ($line in $lines) {
    if ([string]::IsNullOrWhiteSpace($line) -or $line.Length -lt 4) {
      continue
    }
    $status = $line.Substring(0, 2)
    $path = Normalize-StatusPath -Path $line.Substring(3)
    $state = "changed"
    if ($status -eq "??") {
      $state = "untracked"
    } elseif ($status.Contains("D")) {
      $state = "deleted"
    } elseif ($status.Contains("A")) {
      $state = "added"
    } elseif ($status.Contains("M")) {
      $state = "modified"
    } elseif ($status.Contains("R")) {
      $state = "renamed"
    }
    $entries += [pscustomobject]@{
      status = $status
      state = $state
      path = $path
      group = Get-CommitGroup -Path $path
    }
  }
  return $entries
}

function Get-CommitGroup {
  param([Parameter(Mandatory = $true)][string]$Path)

  $p = $Path.Replace('\', '/')
  if ($p -eq "website inspiration.png" -or $p -match '^vscode-plugins/assets/|^visual-studio-extensions/assets/') {
    return "design_assets_and_misc"
  }
  if ($p -match '^release/|/release/|^VERSION\.json$|^scripts/(build-release|aegis-update)\.ps1$') {
    return "release_update_artifacts"
  }
  if ($p -match '^evals/|^scripts/test-|^scripts/validate-ecosystem\.ps1$|^\.github/') {
    return "evidence_contracts_and_validation"
  }
  if ($p -match '^docs/|^[^/]+\.md$|^KNOWN_UNSTABLE_SURFACES\.md$|^.*ROADMAP.*\.md$|^WORKTREE_STABILIZATION_') {
    return "roadmaps_and_docs"
  }
  if ($p -match '^aegis-core/') {
    return "aegis_core_runtime"
  }
  if ($p -match '^website/backend/') {
    return "website_backend"
  }
  if ($p -match '^website/frontend/') {
    return "website_frontend"
  }
  if ($p -match '^src/|^AegisChatBotDesktop\.vcxproj|^CMakeLists\.txt$|^build\.ps1$') {
    return "native_desktop"
  }
  if ($p -match '^vscode-plugins/aegis-local-autopilot/') {
    return "vscode_extension"
  }
  if ($p -match '^visual-studio-extensions/aegis-local-agent-vs/') {
    return "visual_studio_extension"
  }
  return "design_assets_and_misc"
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

function New-CommitGroupSummary {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][object[]]$Entries
  )

  $paths = @($Entries | Where-Object { [string]$_.group -eq $Id } | ForEach-Object { [string]$_.path } | Sort-Object -Unique)
  $states = @{}
  foreach ($entry in @($Entries | Where-Object { [string]$_.group -eq $Id })) {
    $state = [string]$entry.state
    if (-not $states.ContainsKey($state)) {
      $states[$state] = 0
    }
    $states[$state] = [int]$states[$state] + 1
  }
  return [pscustomobject]@{
    id = $Id
    path_count = $paths.Count
    states = $states
    sample_paths = @($paths | Select-Object -First 12)
    stage_policy = "explicit_file_list_only"
  }
}

$EvidenceDir = Test-UnderRoot $EvidenceDir
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$contract = Read-ProjectJson "evals\phase37-commit-scoping-github-handoff-contract.json"
$validator = Read-ProjectFile "scripts\validate-ecosystem.ps1"
$ledgerDocs = Read-ProjectFile "docs\EVIDENCE_LEDGER.md"
$ledgerContractText = Read-ProjectFile "evals\phase16-evidence-ledger-contract.json"
$docsText = @(
  Read-ProjectFile "docs\COMMIT_SCOPING_GITHUB_HANDOFF_EVIDENCE.md"
  Read-ProjectFile "docs\VALIDATION_MATRIX.md"
  Read-ProjectFile "docs\EVIDENCE_LEDGER.md"
  Read-ProjectFile "docs\EXTERNAL_ALPHA_RELEASE_NOTES.md"
  Read-ProjectFile "docs\EXTERNAL_ALPHA_RELEASE_REPORT.md"
  Read-ProjectFile "KNOWN_UNSTABLE_SURFACES.md"
  Read-ProjectFile "FULL_PROJECT_REMAINING_ROADMAP_2026-05-21.md"
  Read-ProjectFile "FULL_PROJECT_REVIEW_ROADMAP_2026-05-21.md"
  Read-ProjectFile "CHATBOT_PROJECT_REVIEW_ROADMAP_2026-05-21.md"
) -join "`n"

Add-Check -Id "contract-schema-version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Message "Phase 37 contract must use schema version 2026.05.21."
Add-Check -Id "contract-phase" -Passed ([int]$contract.phase -eq 37) -Message "Phase 37 contract must identify phase 37."
Add-Check -Id "contract-evidence-root" -Passed ([string]$contract.evidence_root -eq ".aegis/commit-scoping-github-handoff") -Message "Phase 37 evidence root must be .aegis/commit-scoping-github-handoff."
Add-Check -Id "contract-status" -Passed ([string]$contract.current_required_status -eq "ready") -Message "Phase 37 evidence contract status must be ready."

foreach ($file in @($contract.required_contract_files)) {
  $relativePath = [string]$file
  Add-Check -Id "contract-file-$(ConvertTo-CheckId $relativePath)" -Passed (Test-Path -LiteralPath (Join-ProjectPath $relativePath) -PathType Leaf) -Message "Required Phase 37 contract file must exist: $relativePath"
}

foreach ($marker in @($contract.required_doc_markers)) {
  $markerText = [string]$marker
  Add-Check -Id "doc-marker-$(ConvertTo-CheckId $markerText)" -Passed ($docsText -match [regex]::Escape($markerText)) -Message "Phase 37 docs must include '$markerText'."
}

foreach ($marker in @($contract.required_scope_markers)) {
  $markerText = [string]$marker
  Add-Check -Id "scope-marker-$(ConvertTo-CheckId $markerText)" -Passed ($docsText.Contains($markerText) -or $validator.Contains($markerText)) -Message "Phase 37 scope must include marker '$markerText'."
}

Add-Check -Id "validator-gate" -Passed ($validator.Contains("test-commit-scoping-github-handoff.ps1") -and $validator.Contains("commit-scoping-github-handoff-contract")) -Message "Ecosystem validator must run the Phase 37 commit scoping GitHub handoff gate."
Add-Check -Id "ledger-doc-source" -Passed ($ledgerDocs.Contains(".aegis/commit-scoping-github-handoff") -or $ledgerDocs.Contains("commit_scoping_github_handoff")) -Message "Evidence ledger docs must include the Phase 37 commit scoping source."
Add-Check -Id "ledger-contract-source" -Passed ($ledgerContractText.Contains("commit_scoping_github_handoff") -and $ledgerContractText.Contains(".aegis/commit-scoping-github-handoff")) -Message "Evidence ledger contract must include Phase 37 commit scoping evidence."

$remoteUrl = Get-RemoteUrl
$branchName = Get-BranchName
$statusEntries = @(Get-StatusEntries)
$statusTextPath = Join-Path $EvidenceDir "git-status-short.txt"
($statusEntries | ForEach-Object { "$($_.status) $($_.path)" }) | Set-Content -LiteralPath $statusTextPath -Encoding UTF8

$commitGroups = @()
foreach ($groupId in @($contract.required_commit_groups)) {
  $commitGroups += New-CommitGroupSummary -Id ([string]$groupId) -Entries $statusEntries
}

foreach ($groupId in @($contract.required_commit_groups)) {
  Add-Check -Id "commit-group-$(ConvertTo-CheckId ([string]$groupId))" -Passed ([bool](@($commitGroups) | Where-Object { [string]$_.id -eq [string]$groupId } | Select-Object -First 1)) -Message "Commit scope must include group '$groupId'."
}

$deletedAssetEntries = @($statusEntries | Where-Object { [string]$_.path -eq "website inspiration.png" -and [string]$_.state -eq "deleted" })
$deletedAssetDecision = if ($deletedAssetEntries.Count -gt 0) { "needs_owner_decision" } else { "not_detected" }

$evidenceSources = @()
foreach ($source in @($contract.required_evidence_sources)) {
  $accepted = @($source.accepted_statuses | ForEach-Object { [string]$_ })
  $evidence = Get-LatestAcceptedEvidence -RootPath ([string]$source.root) -JsonName ([string]$source.json) -SummaryName ([string]$source.summary) -AcceptedStatuses $accepted
  $isAccepted = $accepted -contains [string]$evidence.status
  $hasSummary = [bool]$evidence.summary_present
  Add-Check -Id "evidence-source-$([string]$source.id)" -Passed ($isAccepted -and $hasSummary) -Message "Required Phase 37 upstream evidence '$([string]$source.id)' must be attached with an accepted status and summary."
  $evidenceSources += [pscustomobject]@{
    id = [string]$source.id
    status = [string]$evidence.status
    accepted = $isAccepted
    latest_folder = [string]$evidence.latest_folder
    json_path = [string]$evidence.json_path
    summary_path = [string]$evidence.summary_path
  }
}

$liveSmokeRcEvidence = @($evidenceSources | Where-Object { [string]$_.id -eq "live_smoke_rc" } | Select-Object -First 1)
$liveSmokePayload = $null
if ($null -ne $liveSmokeRcEvidence -and -not [string]::IsNullOrWhiteSpace([string]$liveSmokeRcEvidence.json_path)) {
  $liveSmokePayload = Read-JsonIfPresent -Path (Join-ProjectPath ([string]$liveSmokeRcEvidence.json_path))
}
$liveSmokeCandidateStatus = if ($null -ne $liveSmokePayload) { [string]$liveSmokePayload.release_candidate_status } else { "missing" }

$publishBlockers = @()
if ($statusEntries.Count -gt 0) {
  $publishBlockers += [pscustomobject]@{
    id = "worktree_dirty_scope_required"
    detail = "Worktree has $($statusEntries.Count) changed paths; group commits before push."
  }
}
if ($deletedAssetDecision -eq "needs_owner_decision") {
  $publishBlockers += [pscustomobject]@{
    id = "deleted_asset_decision_pending"
    detail = "Deleted asset 'website inspiration.png' needs an owner decision before publish."
  }
}
if ([string]::IsNullOrWhiteSpace($remoteUrl) -or [string]$remoteUrl -ne [string]$contract.expected_remote) {
  $publishBlockers += [pscustomobject]@{
    id = "github_target_mismatch"
    detail = "Detected origin '$remoteUrl' does not match expected '$($contract.expected_remote)'."
  }
} else {
  $publishBlockers += [pscustomobject]@{
    id = "github_target_unconfirmed_by_user"
    detail = "Origin matches expected target, but user confirmation is still required before push."
  }
}
if ($liveSmokeCandidateStatus -ne "ready") {
  $publishBlockers += [pscustomobject]@{
    id = "release_candidate_attention"
    detail = "Phase 36 release_candidate_status is '$liveSmokeCandidateStatus'."
  }
}

$handoffStatus = if ($publishBlockers.Count -eq 0) { "ready" } else { "attention" }

$summary = [pscustomobject]@{
  schema_version = "2026.05.21"
  phase = 37
  status = if ($script:Failures.Count -eq 0) { "ready" } else { "blocked" }
  handoff_status = $handoffStatus
  generated_at = (Get-Date).ToString("o")
  evidence_dir = ConvertTo-ProjectRelativePath $EvidenceDir
  contract = "evals/phase37-commit-scoping-github-handoff-contract.json"
  slice = [string]$contract.slice
  github_target = [pscustomobject]@{
    expected_remote = [string]$contract.expected_remote
    detected_remote = $remoteUrl
    detected_branch = $branchName
    remote_matches_expected = [string]$remoteUrl -eq [string]$contract.expected_remote
    confirmed_by_user = $false
  }
  worktree = [pscustomobject]@{
    total_changed_paths = $statusEntries.Count
    modified_count = @($statusEntries | Where-Object { [string]$_.state -eq "modified" }).Count
    deleted_count = @($statusEntries | Where-Object { [string]$_.state -eq "deleted" }).Count
    untracked_count = @($statusEntries | Where-Object { [string]$_.state -eq "untracked" }).Count
    status_path = ConvertTo-ProjectRelativePath $statusTextPath
  }
  deleted_asset_decision = [pscustomobject]@{
    path = "website inspiration.png"
    status = $deletedAssetDecision
  }
  release_artifact_separation = [pscustomobject]@{
    group = "release_update_artifacts"
    stage_separately = $true
    reason = "Generated release packages, manifests, and update scripts need an intentional release-artifact review."
  }
  no_blind_stage = [pscustomobject]@{
    enabled = $true
    blocked_command = "git add -A"
    required_policy = "Use explicit file lists per commit group."
  }
  commit_groups = $commitGroups
  evidence_sources = $evidenceSources
  publish_blockers = $publishBlockers
  failures = $script:Failures
  checks = $script:Checks
}

$jsonPath = Join-Path $EvidenceDir "commit-scoping-github-handoff.json"
$markdownPath = Join-Path $EvidenceDir "commit-scoping-github-handoff-summary.md"
$summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 37 Commit Scoping And GitHub Handoff Evidence"
$markdown += ""
$markdown += "- Status: $($summary.status)"
$markdown += "- Handoff status: $($summary.handoff_status)"
$markdown += "- Generated at: $($summary.generated_at)"
$markdown += "- Evidence dir: $($summary.evidence_dir)"
$markdown += "- Contract: $($summary.contract)"
$markdown += "- Detected remote: $($summary.github_target.detected_remote)"
$markdown += "- Detected branch: $($summary.github_target.detected_branch)"
$markdown += "- Changed paths: $($summary.worktree.total_changed_paths)"
$markdown += "- Deleted asset decision: $($summary.deleted_asset_decision.status)"
$markdown += ""
$markdown += "## Publish Blockers"
$markdown += ""
$markdown += "| Blocker | Detail |"
$markdown += "| --- | --- |"
foreach ($blocker in @($summary.publish_blockers)) {
  $detail = ([string]$blocker.detail).Replace("|", "\|")
  $markdown += "| $($blocker.id) | $detail |"
}
$markdown += ""
$markdown += "## Commit Groups"
$markdown += ""
$markdown += "| Group | Paths | Stage Policy | Sample Paths |"
$markdown += "| --- | ---: | --- | --- |"
foreach ($group in @($summary.commit_groups)) {
  $sample = (@($group.sample_paths) -join "<br>").Replace("|", "\|")
  $markdown += "| $($group.id) | $($group.path_count) | $($group.stage_policy) | $sample |"
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
  throw "Commit scoping GitHub handoff validation failed:`n - $($script:Failures -join "`n - ")"
}
