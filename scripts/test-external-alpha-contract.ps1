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
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\external-alpha-evidence" (Get-Date -Format "yyyyMMdd-HHmmss"))
} else {
  $EvidenceDir = [System.IO.Path]::GetFullPath($EvidenceDir)
}

$script:Checks = @()
$script:Failures = @()

function Read-ProjectFile {
  param([Parameter(Mandatory = $true)][string]$RelativePath)

  $path = Join-Path $Root $RelativePath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "Required external alpha contract file is missing: $RelativePath"
  }
  return Get-Content -LiteralPath $path -Raw
}

function Read-ProjectJson {
  param([Parameter(Mandatory = $true)][string]$RelativePath)

  return Read-ProjectFile $RelativePath | ConvertFrom-Json
}

function ConvertTo-CheckId {
  param([Parameter(Mandatory = $true)][string]$Value)

  return $Value.Replace("/", "-").Replace("\", "-").Replace(" ", "-").Replace(":", "").Replace("{", "").Replace("}", "").ToLowerInvariant()
}

function Add-ExternalAlphaCheck {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][bool]$Passed,
    [Parameter(Mandatory = $true)][string]$Detail
  )

  $script:Checks += [pscustomobject]@{
    id = $Id
    passed = $Passed
    detail = $Detail
  }
  if (-not $Passed) {
    $script:Failures += $Detail
  }
}

function Assert-SourceContains {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][string]$Text,
    [Parameter(Mandatory = $true)][string]$Pattern,
    [Parameter(Mandatory = $true)][string]$Detail
  )

  Add-ExternalAlphaCheck -Id $Id -Passed ([bool]($Text -match $Pattern)) -Detail $Detail
}

function Assert-SetIncludes {
  param(
    [Parameter(Mandatory = $true)][string]$IdPrefix,
    [Parameter(Mandatory = $true)][object[]]$Values,
    [Parameter(Mandatory = $true)][string[]]$Required,
    [Parameter(Mandatory = $true)][string]$Label
  )

  $actual = @($Values | ForEach-Object { [string]$_ })
  foreach ($item in $Required) {
    Add-ExternalAlphaCheck -Id "$IdPrefix-$(ConvertTo-CheckId $item)" -Passed ($actual -contains $item) -Detail "$Label must include '$item'."
  }
}

function Assert-ObjectIdsInclude {
  param(
    [Parameter(Mandatory = $true)][string]$IdPrefix,
    [Parameter(Mandatory = $true)][object[]]$Objects,
    [Parameter(Mandatory = $true)][string[]]$Required,
    [Parameter(Mandatory = $true)][string]$Label
  )

  $actual = @($Objects | ForEach-Object { [string]$_.id })
  foreach ($item in $Required) {
    Add-ExternalAlphaCheck -Id "$IdPrefix-$(ConvertTo-CheckId $item)" -Passed ($actual -contains $item) -Detail "$Label must include '$item'."
  }
}

$contract = Read-ProjectJson "evals\phase15-external-alpha-release-contract.json"
$alphaContract = Read-ProjectJson "evals\phase14-alpha-readiness-contract.json"
$versionManifest = Read-ProjectJson "VERSION.json"
$report = Read-ProjectFile "docs\EXTERNAL_ALPHA_RELEASE_REPORT.md"
$controlledAlpha = Read-ProjectFile "docs\CONTROLLED_EXTERNAL_ALPHA.md"
$validationMatrix = Read-ProjectFile "docs\VALIDATION_MATRIX.md"
$releaseDocs = Read-ProjectFile "docs\RELEASE_PACKAGING_AND_UPDATES.md"
$knownUnstable = Read-ProjectFile "KNOWN_UNSTABLE_SURFACES.md"
$validator = Read-ProjectFile "scripts\validate-ecosystem.ps1"
$buildRelease = Read-ProjectFile "scripts\build-release.ps1"
$updater = Read-ProjectFile "scripts\aegis-update.ps1"
$releaseContract = Read-ProjectFile "scripts\test-release-contract.ps1"
$alphaContractScript = Read-ProjectFile "scripts\test-alpha-contract.ps1"

Add-ExternalAlphaCheck -Id "contract-schema-version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Detail "Phase 15 external alpha contract must use the current schema version."
Add-ExternalAlphaCheck -Id "contract-evidence-root" -Passed ([string]$contract.evidence_root -eq ".aegis/external-alpha-evidence") -Detail "Phase 15 evidence must have a stable .aegis root."
Add-ExternalAlphaCheck -Id "contract-current-decision-conditional" -Passed ([string]$contract.current_required_decision -eq "conditional") -Detail "Current external alpha decision must be conditional after release notes limitations evidence is attached."
Assert-SetIncludes -IdPrefix "decision-state" -Values @($contract.decision_states) -Required @("blocked", "conditional", "ready") -Label "Decision states"

foreach ($file in @($contract.required_contract_files)) {
  $relativePath = [string]$file
  Add-ExternalAlphaCheck -Id "contract-file-$(ConvertTo-CheckId $relativePath)" -Passed (Test-Path -LiteralPath (Join-Path $Root $relativePath) -PathType Leaf) -Detail "Required Phase 15 contract file must exist: $relativePath"
}

$requiredBlockers = @(
  "release_artifact_matrix",
  "ecosystem_validation_evidence",
  "alpha_scenario_suite_evidence",
  "cross_client_parity_evidence",
  "rollback_update_dry_run",
  "known_limitations_release_notes",
  "signing_checksum_disclosure"
)
Assert-ObjectIdsInclude -IdPrefix "blocker" -Objects @($contract.hard_blockers) -Required $requiredBlockers -Label "Hard blockers"

$requiredSections = @(
  "go_no_go_summary",
  "evidence_index",
  "release_artifact_matrix",
  "validation_matrix",
  "alpha_scenario_suite",
  "known_issues_limitations",
  "recovery_rollback",
  "cross_client_parity",
  "decision_log"
)
Assert-ObjectIdsInclude -IdPrefix "report-section" -Objects @($contract.report_sections) -Required $requiredSections -Label "Report sections"
Assert-SetIncludes -IdPrefix "artifact-component" -Values @($contract.artifact_components) -Required @("aegis-core", "website", "desktop", "vscode-extension", "visual-studio-extension") -Label "Artifact components"
Assert-SetIncludes -IdPrefix "scenario" -Values @($contract.scenario_suite) -Required @($alphaContract.scenario_suite | ForEach-Object { [string]$_.id }) -Label "External alpha scenario suite"
Assert-SetIncludes -IdPrefix "validation-gate" -Values @($contract.validation_gates) -Required @("core-tests", "website-backend-tests", "website-frontend-tests", "website-frontend-build", "desktop-contract", "release-contract", "release-artifact-preflight", "extension-package-candidates", "release-package-dry-run-contract", "final-release-manifest-contract", "release-apply-rollback-contract", "packaged-alpha-scenarios-contract", "cross-client-parity-contract", "release-notes-limitations-contract", "quality-contract", "plugin-contract", "alpha-contract", "external-alpha-contract", "desktop-release-build", "vscode-unit", "vscode-lint", "editor-parity", "visual-studio-validate", "release-package-dry-run", "update-plan-dry-run") -Label "Validation gates"

foreach ($component in @($contract.artifact_components)) {
  $componentId = [string]$component
  $manifestProperty = $versionManifest.components.PSObject.Properties[$componentId]
  Add-ExternalAlphaCheck -Id "version-component-$(ConvertTo-CheckId $componentId)" -Passed ($null -ne $manifestProperty) -Detail "VERSION.json must define external alpha component '$componentId'."
}

Assert-SourceContains -Id "report-conditional" -Text $report -Pattern 'Current decision:\s*Conditional' -Detail "External alpha report must set the current decision as Conditional."
Assert-SourceContains -Id "report-status-conditional" -Text $report -Pattern 'Status:\s*conditional' -Detail "External alpha report must keep current status conditional."
Assert-SourceContains -Id "report-contract-link" -Text $report -Pattern 'phase15-external-alpha-release-contract\.json' -Detail "External alpha report must link the Phase 15 contract."
Assert-SourceContains -Id "report-evidence-root" -Text $report -Pattern '\.aegis/external-alpha-evidence' -Detail "External alpha report must document external alpha evidence root."
Assert-SourceContains -Id "report-release-evidence" -Text $report -Pattern '\.aegis/release-evidence' -Detail "External alpha report must require release evidence."
Assert-SourceContains -Id "report-alpha-evidence" -Text $report -Pattern '\.aegis/alpha-evidence' -Detail "External alpha report must require alpha evidence."
Assert-SourceContains -Id "report-known-unstable" -Text $report -Pattern 'KNOWN_UNSTABLE_SURFACES\.md' -Detail "External alpha report must reference known unstable surfaces."
Assert-SourceContains -Id "report-version-manifest" -Text $report -Pattern 'release/version-manifest\.json' -Detail "External alpha report must require generated release manifest evidence."
Assert-SourceContains -Id "report-unsigned-disclosure" -Text $report -Pattern 'unsigned-build limitation' -Detail "External alpha report must require unsigned-build disclosure."
Assert-SourceContains -Id "report-release-apply-rollback" -Text $report -Pattern 'release-apply-rollback|RELEASE_APPLY_ROLLBACK_EVIDENCE' -Detail "External alpha report must require release apply/rollback evidence."
Assert-SourceContains -Id "report-packaged-alpha-scenarios" -Text $report -Pattern 'packaged-alpha-scenarios|PACKAGED_ALPHA_SCENARIO_EVIDENCE' -Detail "External alpha report must require packaged alpha scenario evidence."
Assert-SourceContains -Id "report-cross-client-parity" -Text $report -Pattern 'cross-client-parity|CROSS_CLIENT_PARITY_EVIDENCE' -Detail "External alpha report must require cross-client parity evidence."
Assert-SourceContains -Id "report-release-notes-limitations" -Text $report -Pattern 'release-notes-limitations|RELEASE_NOTES_LIMITATIONS_EVIDENCE|EXTERNAL_ALPHA_RELEASE_NOTES' -Detail "External alpha report must require release notes limitations evidence."

foreach ($section in @($contract.report_sections)) {
  Assert-SourceContains -Id "report-section-$($section.id)" -Text $report -Pattern ([regex]::Escape("## $($section.title)")) -Detail "External alpha report must include section '$($section.title)'."
}
foreach ($blocker in @($contract.hard_blockers)) {
  Assert-SourceContains -Id "report-blocker-$($blocker.id)" -Text $report -Pattern ([regex]::Escape([string]$blocker.id)) -Detail "External alpha report must list blocker '$($blocker.id)'."
}
foreach ($scenario in @($contract.scenario_suite)) {
  Assert-SourceContains -Id "report-scenario-$(ConvertTo-CheckId ([string]$scenario))" -Text $report -Pattern ([regex]::Escape([string]$scenario)) -Detail "External alpha report must list scenario '$scenario'."
}
foreach ($component in @($contract.artifact_components)) {
  Assert-SourceContains -Id "report-component-$(ConvertTo-CheckId ([string]$component))" -Text $report -Pattern ([regex]::Escape([string]$component)) -Detail "External alpha report must list artifact component '$component'."
}

Assert-SourceContains -Id "validator-external-alpha-gate" -Text $validator -Pattern 'test-external-alpha-contract\.ps1' -Detail "Ecosystem validation must run the Phase 15 external alpha contract gate."
Assert-SourceContains -Id "validator-external-alpha-evidence-dir" -Text $validator -Pattern 'external-alpha-contract' -Detail "Ecosystem validation must place external alpha contract output under the release evidence directory."
Assert-SourceContains -Id "validator-release-evidence" -Text $validator -Pattern 'validation-matrix\.json' -Detail "Ecosystem validation must produce validation matrix evidence."
Assert-SourceContains -Id "validator-release-artifact-status" -Text $validator -Pattern 'release-artifact-status\.txt' -Detail "Ecosystem validation must capture release artifact status."
Assert-SourceContains -Id "validator-release-package" -Text $validator -Pattern 'release-package-dry-run' -Detail "Ecosystem validation must include release package dry-run gate."
Assert-SourceContains -Id "validator-update-plan" -Text $validator -Pattern 'update-plan-dry-run' -Detail "Ecosystem validation must include update planner dry-run gate."
Assert-SourceContains -Id "validator-release-notes-limitations" -Text $validator -Pattern 'test-release-notes-limitations\.ps1' -Detail "Ecosystem validation must include the release notes limitations gate."

Assert-SourceContains -Id "validation-doc-release-evidence" -Text $validationMatrix -Pattern '\.aegis\\release-evidence' -Detail "Validation matrix docs must document release evidence path."
Assert-SourceContains -Id "validation-doc-matrix-json" -Text $validationMatrix -Pattern 'validation-matrix\.json' -Detail "Validation matrix docs must document validation-matrix.json."
Assert-SourceContains -Id "validation-doc-artifact-status" -Text $validationMatrix -Pattern 'release-artifact-status\.txt' -Detail "Validation matrix docs must document release artifact status."
Assert-SourceContains -Id "release-doc-build" -Text $releaseDocs -Pattern 'build-release\.ps1' -Detail "Release docs must document package build."
Assert-SourceContains -Id "release-doc-update" -Text $releaseDocs -Pattern 'aegis-update\.ps1' -Detail "Release docs must document update flow."
Assert-SourceContains -Id "release-doc-rollback" -Text $releaseDocs -Pattern 'Rollback And Recovery' -Detail "Release docs must document rollback and recovery."
Assert-SourceContains -Id "release-doc-manifest" -Text $releaseDocs -Pattern 'version-manifest\.json' -Detail "Release docs must document generated release manifest."
Assert-SourceContains -Id "known-release-boundary" -Text $knownUnstable -Pattern 'conditional private external alpha|Broad external alpha is still blocked|Release promotion is blocked|Release packaging is blocked' -Detail "Known unstable surfaces must keep release packaging or conditional alpha boundary visible."
Assert-SourceContains -Id "known-cross-client" -Text $knownUnstable -Pattern 'cross-client parity evidence|Cross-client parity evidence|cross-client parity' -Detail "Known unstable surfaces must keep cross-client parity evidence visible."
Assert-SourceContains -Id "controlled-alpha-release-artifacts" -Text $controlledAlpha -Pattern 'Release Artifacts' -Detail "Controlled alpha docs must document release artifacts."
Assert-SourceContains -Id "controlled-alpha-known-limitations" -Text $controlledAlpha -Pattern 'Known Limitations' -Detail "Controlled alpha docs must document known limitations."
Assert-SourceContains -Id "build-release-manifest" -Text $buildRelease -Pattern 'version-manifest\.json' -Detail "Build release script must generate version-manifest.json."
Assert-SourceContains -Id "updater-rollback" -Text $updater -Pattern 'Restore-Backup' -Detail "Updater must support rollback."
Assert-SourceContains -Id "release-contract-checksum" -Text $releaseContract -Pattern 'policy-checksum' -Detail "Release contract must guard checksum policy."
Assert-SourceContains -Id "alpha-contract-scenarios" -Text $alphaContractScript -Pattern 'Alpha scenario suite' -Detail "Alpha contract script must guard scenario suite."

$summary = [pscustomobject]@{
  root = $Root
  status = if ($script:Failures.Count -eq 0) { "passed" } else { "failed" }
  checked_at = (Get-Date).ToString("o")
  evidence_dir = $EvidenceDir
  contract = [pscustomobject]@{
    schema_version = [string]$contract.schema_version
    current_required_decision = [string]$contract.current_required_decision
    blocker_count = @($contract.hard_blockers).Count
    report_section_count = @($contract.report_sections).Count
    scenario_count = @($contract.scenario_suite).Count
    validation_gate_count = @($contract.validation_gates).Count
  }
  checks = $script:Checks
}

New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$summaryPath = Join-Path $EvidenceDir "external-alpha-contract.json"
$markdownPath = Join-Path $EvidenceDir "external-alpha-contract-summary.md"
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 15 External Alpha Contract"
$markdown += ""
$markdown += "- Status: $($summary.status)"
$markdown += "- Checked at: $($summary.checked_at)"
$markdown += "- Current required decision: $($summary.contract.current_required_decision)"
$markdown += "- Hard blockers: $($summary.contract.blocker_count)"
$markdown += "- Report sections: $($summary.contract.report_section_count)"
$markdown += "- Scenario suite entries: $($summary.contract.scenario_count)"
$markdown += "- Validation gates: $($summary.contract.validation_gate_count)"
$markdown += ""
$markdown += "| Check | Status | Detail |"
$markdown += "| --- | --- | --- |"
foreach ($check in $script:Checks) {
  $status = if ($check.passed) { "passed" } else { "failed" }
  $detail = ([string]$check.detail).Replace("|", "\|")
  $markdown += "| $($check.id) | $status | $detail |"
}
$markdown | Set-Content -LiteralPath $markdownPath -Encoding UTF8

$summary | ConvertTo-Json -Depth 8

if ($script:Failures.Count -gt 0) {
  throw "External alpha release contract validation failed:`n - $($script:Failures -join "`n - ")"
}
