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
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\release-preflight" (Get-Date -Format "yyyyMMdd-HHmmss"))
} else {
  $EvidenceDir = [System.IO.Path]::GetFullPath($EvidenceDir)
}

$script:Checks = @()
$script:Failures = @()

function Read-ProjectFile {
  param([Parameter(Mandatory = $true)][string]$RelativePath)

  $path = Join-Path $Root $RelativePath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "Required release preflight file is missing: $RelativePath"
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

function Add-ContractCheck {
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

  Add-ContractCheck -Id $Id -Passed ([bool]($Text -match $Pattern)) -Detail $Detail
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
    Add-ContractCheck -Id "$IdPrefix-$(ConvertTo-CheckId $item)" -Passed ($actual -contains $item) -Detail "$Label must include '$item'."
  }
}

function Get-RelativePath {
  param([Parameter(Mandatory = $true)][string]$FullPath)

  $rootUri = [System.Uri]::new(($Root.TrimEnd('\') + '\'))
  $pathUri = [System.Uri]::new([System.IO.Path]::GetFullPath($FullPath))
  return [System.Uri]::UnescapeDataString($rootUri.MakeRelativeUri($pathUri).ToString()).Replace("/", "\")
}

function Test-ProjectPath {
  param(
    [Parameter(Mandatory = $true)][string]$RelativePath,
    [Parameter(Mandatory = $true)][string]$Kind
  )

  $path = Join-Path $Root $RelativePath
  if ($Kind -eq "container") {
    return Test-Path -LiteralPath $path -PathType Container
  }
  return Test-Path -LiteralPath $path -PathType Leaf
}

function New-InputResult {
  param(
    [Parameter(Mandatory = $true)][string]$RelativePath,
    [Parameter(Mandatory = $true)][string]$Kind
  )

  return [pscustomobject]@{
    path = $RelativePath
    kind = $Kind
    present = [bool](Test-ProjectPath -RelativePath $RelativePath -Kind $Kind)
  }
}

function New-PreflightCheck {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][string]$Status,
    [Parameter(Mandatory = $true)][string]$Detail
  )

  return [pscustomobject]@{
    id = $Id
    status = $Status
    detail = $Detail
  }
}

function New-Blocker {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][string]$Detail
  )

  return [pscustomobject]@{
    id = $Id
    detail = $Detail
  }
}

function Test-AllInputsPresent {
  param([Parameter(Mandatory = $true)][object[]]$Inputs)

  return -not [bool](@($Inputs) | Where-Object { -not $_.present } | Select-Object -First 1)
}

function Get-MissingInputText {
  param([Parameter(Mandatory = $true)][object[]]$Inputs)

  $missing = @($Inputs | Where-Object { -not $_.present } | ForEach-Object { [string]$_.path })
  if ($missing.Count -eq 0) {
    return ""
  }
  return $missing -join ", "
}

function Get-LatestEvidenceFolder {
  param([Parameter(Mandatory = $true)][string]$RelativeRoot)

  $path = Join-Path $Root $RelativeRoot
  if (-not (Test-Path -LiteralPath $path -PathType Container)) {
    return $null
  }
  return Get-ChildItem -LiteralPath $path -Directory | Sort-Object Name -Descending | Select-Object -First 1
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

function Get-ReleaseGate {
  param(
    [object]$Matrix,
    [Parameter(Mandatory = $true)][string]$GateId
  )

  if ($null -eq $Matrix) {
    return [pscustomobject]@{
      id = $GateId
      status = "missing"
      reason = "No validation-matrix.json was found in the latest release evidence folder."
    }
  }

  $gate = @($Matrix.results | Where-Object { [string]$_.id -eq $GateId } | Select-Object -First 1)
  if ($gate.Count -eq 0) {
    return [pscustomobject]@{
      id = $GateId
      status = "missing"
      reason = "Gate is not present in validation-matrix.json."
    }
  }

  return [pscustomobject]@{
    id = [string]$gate[0].id
    status = [string]$gate[0].status
    reason = [string]$gate[0].reason
  }
}

function Get-LatestReleasePackageDryRunEvidence {
  $candidateJsonPaths = @()

  $standaloneRoot = Join-Path $Root ".aegis\release-package-dry-run"
  if (Test-Path -LiteralPath $standaloneRoot -PathType Container) {
    foreach ($folder in @(Get-ChildItem -LiteralPath $standaloneRoot -Directory)) {
      $jsonPath = Join-Path $folder.FullName "release-package-dry-run.json"
      if (Test-Path -LiteralPath $jsonPath -PathType Leaf) {
        $candidateJsonPaths += $jsonPath
      }
    }
  }

  $releaseEvidenceRoot = Join-Path $Root ".aegis\release-evidence"
  if (Test-Path -LiteralPath $releaseEvidenceRoot -PathType Container) {
    foreach ($folder in @(Get-ChildItem -LiteralPath $releaseEvidenceRoot -Directory)) {
      $jsonPath = Join-Path $folder.FullName "release-package-dry-run-contract\release-package-dry-run.json"
      if (Test-Path -LiteralPath $jsonPath -PathType Leaf) {
        $candidateJsonPaths += $jsonPath
      }
    }
  }

  $candidates = @()
  foreach ($jsonPath in $candidateJsonPaths) {
    $payload = Read-JsonIfPresent -Path $jsonPath
    if ($null -ne $payload) {
      $item = Get-Item -LiteralPath $jsonPath
      $candidates += [pscustomobject]@{
        json_path = Get-RelativePath $jsonPath
        folder = Get-RelativePath (Split-Path -Parent $jsonPath)
        status = [string]$payload.status
        generated_at = [string]$payload.generated_at
        payload = $payload
        last_write_utc = $item.LastWriteTimeUtc
      }
    }
  }

  $selected = $candidates | Sort-Object last_write_utc -Descending | Select-Object -First 1
  if ($null -eq $selected) {
    return $null
  }
  return $selected
}

function Get-LatestFinalReleaseManifestEvidence {
  $candidateJsonPaths = @()

  $standaloneRoot = Join-Path $Root ".aegis\final-release-manifest"
  if (Test-Path -LiteralPath $standaloneRoot -PathType Container) {
    foreach ($folder in @(Get-ChildItem -LiteralPath $standaloneRoot -Directory)) {
      $jsonPath = Join-Path $folder.FullName "final-release-manifest.json"
      if (Test-Path -LiteralPath $jsonPath -PathType Leaf) {
        $candidateJsonPaths += $jsonPath
      }
    }
  }

  $releaseEvidenceRoot = Join-Path $Root ".aegis\release-evidence"
  if (Test-Path -LiteralPath $releaseEvidenceRoot -PathType Container) {
    foreach ($folder in @(Get-ChildItem -LiteralPath $releaseEvidenceRoot -Directory)) {
      $jsonPath = Join-Path $folder.FullName "final-release-manifest-contract\final-release-manifest.json"
      if (Test-Path -LiteralPath $jsonPath -PathType Leaf) {
        $candidateJsonPaths += $jsonPath
      }
    }
  }

  $candidates = @()
  foreach ($jsonPath in $candidateJsonPaths) {
    $payload = Read-JsonIfPresent -Path $jsonPath
    if ($null -ne $payload) {
      $item = Get-Item -LiteralPath $jsonPath
      $candidates += [pscustomobject]@{
        json_path = Get-RelativePath $jsonPath
        folder = Get-RelativePath (Split-Path -Parent $jsonPath)
        status = [string]$payload.status
        generated_at = [string]$payload.generated_at
        payload = $payload
        last_write_utc = $item.LastWriteTimeUtc
      }
    }
  }

  $selected = $candidates | Sort-Object last_write_utc -Descending | Select-Object -First 1
  if ($null -eq $selected) {
    return $null
  }
  return $selected
}

function Test-UpdatePlansReady {
  param(
    [object]$DryRunEvidence,
    [string[]]$ComponentIds
  )

  if ($null -eq $DryRunEvidence -or [string]$DryRunEvidence.status -ne "ready") {
    return $false
  }

  $plans = @($DryRunEvidence.payload.update_plans)
  foreach ($componentId in $ComponentIds) {
    $plan = @($plans | Where-Object {
      [string]$_.component -eq $componentId -and
      [string]$_.state -eq "planned" -and
      [bool]$_.checksum_required -eq $true -and
      -not [string]::IsNullOrWhiteSpace([string]$_.target_version)
    } | Select-Object -First 1)
    if ($plan.Count -eq 0) {
      return $false
    }
  }

  return $true
}

function Get-GitStatusForReleaseArtifacts {
  $paths = @(
    "release",
    "vscode-plugins/aegis-local-autopilot/release",
    "visual-studio-extensions/aegis-local-agent-vs/release",
    "VERSION.json",
    "scripts/build-release.ps1",
    "scripts/aegis-update.ps1"
  )

  try {
    $arguments = @("-C", $Root, "status", "--short", "--") + $paths
    return @(& git @arguments 2>&1 | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
  } catch {
    return @("git status failed: $($_.Exception.Message)")
  }
}

function Get-Component {
  param(
    [object]$Manifest,
    [Parameter(Mandatory = $true)][string]$Name
  )

  if ($null -eq $Manifest -or $null -eq $Manifest.components) {
    return $null
  }
  $property = $Manifest.components.PSObject.Properties[$Name]
  if ($null -eq $property) {
    return $null
  }
  return $property.Value
}

function Get-VsixCandidates {
  param(
    [Parameter(Mandatory = $true)][string]$ComponentName,
    [Parameter(Mandatory = $true)][string[]]$RelativePaths
  )

  $component = Get-Component -Manifest $sourceManifest -Name $ComponentName
  $artifact = ""
  if ($null -ne $component -and $null -ne $component.package) {
    $artifact = [string]$component.package.artifact
  }

  $candidates = @()
  foreach ($relativeBase in $RelativePaths) {
    if (-not [string]::IsNullOrWhiteSpace($artifact)) {
      $relativePath = Join-Path $relativeBase $artifact
      $fullPath = Join-Path $Root $relativePath
      $candidates += [pscustomobject]@{
        path = $relativePath
        present = [bool](Test-Path -LiteralPath $fullPath -PathType Leaf)
        size_bytes = if (Test-Path -LiteralPath $fullPath -PathType Leaf) { (Get-Item -LiteralPath $fullPath).Length } else { 0 }
      }
    }
  }

  return $candidates
}

$contract = Read-ProjectJson "evals\phase17-release-artifact-preflight-contract.json"
$preflightDocs = Read-ProjectFile "docs\RELEASE_ARTIFACT_PREFLIGHT.md"
$releaseDocs = Read-ProjectFile "docs\RELEASE_PACKAGING_AND_UPDATES.md"
$ledgerDocs = Read-ProjectFile "docs\EVIDENCE_LEDGER.md"
$externalReport = Read-ProjectFile "docs\EXTERNAL_ALPHA_RELEASE_REPORT.md"
$validationDocs = Read-ProjectFile "docs\VALIDATION_MATRIX.md"
$validator = Read-ProjectFile "scripts\validate-ecosystem.ps1"

Add-ContractCheck -Id "contract-schema-version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Detail "Phase 17 release artifact preflight contract must use the current schema version."
Add-ContractCheck -Id "contract-evidence-root" -Passed ([string]$contract.evidence_root -eq ".aegis/release-preflight") -Detail "Phase 17 preflight must have a stable .aegis root."
Add-ContractCheck -Id "contract-current-status-ready" -Passed ([string]$contract.current_required_status -eq "ready") -Detail "Current release preflight status must be ready once the final manifest and artifact decision evidence exists."
Assert-SetIncludes -IdPrefix "status-value" -Values @($contract.status_values) -Required @("blocked", "attention", "ready") -Label "Preflight status values"
Assert-SetIncludes -IdPrefix "component" -Values @($contract.components) -Required @("aegis-core", "website", "desktop", "vscode-extension", "visual-studio-extension") -Label "Preflight components"
Assert-SetIncludes -IdPrefix "preflight-check" -Values @($contract.required_preflight_checks) -Required @("source_manifest_present", "release_scripts_present", "components_in_manifest", "core_stage_inputs", "website_stage_inputs", "desktop_stage_inputs", "vscode_vsix_candidate", "visual_studio_vsix_candidate", "release_manifest_generated", "final_release_manifest_evidence", "dirty_release_artifact_decision", "release_package_dry_run", "update_plan_dry_run") -Label "Preflight checks"
Assert-SetIncludes -IdPrefix "tracked-blocker" -Values @($contract.tracked_blocker_ids) -Required @("release_manifest_missing", "release_package_dry_run_not_passed", "update_plan_dry_run_not_passed", "dirty_release_artifacts_need_decision", "vscode_vsix_missing", "visual_studio_vsix_missing") -Label "Tracked preflight blockers"
Add-ContractCheck -Id "blocker-none-currently-required" -Passed (@($contract.required_blocker_ids).Count -eq 0) -Detail "Current required preflight blockers must be empty after Phase 20 final manifest evidence."
Assert-SetIncludes -IdPrefix "preflight-output" -Values @($contract.preflight_outputs) -Required @("release-artifact-preflight.json", "release-artifact-preflight-summary.md") -Label "Preflight outputs"

foreach ($file in @($contract.required_contract_files)) {
  $relativePath = [string]$file
  Add-ContractCheck -Id "contract-file-$(ConvertTo-CheckId $relativePath)" -Passed (Test-Path -LiteralPath (Join-Path $Root $relativePath) -PathType Leaf) -Detail "Required Phase 17 contract file must exist: $relativePath"
}

Assert-SourceContains -Id "docs-preflight-contract-link" -Text $preflightDocs -Pattern 'phase17-release-artifact-preflight-contract\.json' -Detail "Preflight docs must link the Phase 17 contract."
Assert-SourceContains -Id "docs-preflight-command" -Text $preflightDocs -Pattern 'test-release-artifact-preflight\.ps1' -Detail "Preflight docs must document the validation command."
Assert-SourceContains -Id "docs-preflight-output" -Text $preflightDocs -Pattern '\.aegis/release-preflight' -Detail "Preflight docs must document the evidence root."
Assert-SourceContains -Id "docs-preflight-non-mutating" -Text $preflightDocs -Pattern 'does not create packages' -Detail "Preflight docs must state that this gate is non-mutating."
Assert-SourceContains -Id "docs-preflight-package-dry-run" -Text $preflightDocs -Pattern 'release-package-dry-run' -Detail "Preflight docs must reference Phase 19 package dry-run evidence."
Assert-SourceContains -Id "docs-preflight-final-manifest" -Text $preflightDocs -Pattern 'final-release-manifest|RELEASE_ARTIFACT_DECISION' -Detail "Preflight docs must reference Phase 20 final manifest and artifact decision evidence."
Assert-SourceContains -Id "release-doc-preflight" -Text $releaseDocs -Pattern 'test-release-artifact-preflight\.ps1' -Detail "Release packaging docs must include the preflight command."
Assert-SourceContains -Id "ledger-doc-preflight" -Text $ledgerDocs -Pattern '\.aegis/release-preflight|release_artifact_preflight' -Detail "Evidence ledger docs must include release preflight evidence."
Assert-SourceContains -Id "external-report-preflight" -Text $externalReport -Pattern 'release-preflight|RELEASE_ARTIFACT_PREFLIGHT' -Detail "External alpha report must include release preflight evidence."
Assert-SourceContains -Id "validation-doc-preflight" -Text $validationDocs -Pattern 'release-artifact-preflight|test-release-artifact-preflight' -Detail "Validation matrix docs must document the release preflight gate."
Assert-SourceContains -Id "validator-preflight-script" -Text $validator -Pattern 'test-release-artifact-preflight\.ps1' -Detail "Ecosystem validation must run the release artifact preflight gate."
Assert-SourceContains -Id "validator-preflight-gate" -Text $validator -Pattern 'release-artifact-preflight' -Detail "Ecosystem validation must name the release artifact preflight gate."

$sourceManifestPath = Join-Path $Root "VERSION.json"
$sourceManifestPresent = Test-Path -LiteralPath $sourceManifestPath -PathType Leaf
$sourceManifest = if ($sourceManifestPresent) { Read-ProjectJson "VERSION.json" } else { $null }
$preflightChecks = @()
$blockers = @()

$preflightChecks += New-PreflightCheck -Id "source_manifest_present" -Status $(if ($sourceManifestPresent) { "passed" } else { "blocked" }) -Detail $(if ($sourceManifestPresent) { "VERSION.json is present." } else { "VERSION.json is missing." })

$releaseScripts = @(
  New-InputResult -RelativePath "scripts\build-release.ps1" -Kind "leaf"
  New-InputResult -RelativePath "scripts\aegis-update.ps1" -Kind "leaf"
)
$releaseScriptsReady = Test-AllInputsPresent -Inputs $releaseScripts
$preflightChecks += New-PreflightCheck -Id "release_scripts_present" -Status $(if ($releaseScriptsReady) { "passed" } else { "blocked" }) -Detail $(if ($releaseScriptsReady) { "Release and update scripts are present." } else { "Missing release scripts: $(Get-MissingInputText -Inputs $releaseScripts)" })

$manifestComponents = @()
foreach ($componentName in @($contract.components)) {
  $manifestComponents += [pscustomobject]@{
    id = [string]$componentName
    present = [bool](Get-Component -Manifest $sourceManifest -Name ([string]$componentName))
  }
}
$componentsReady = -not [bool](@($manifestComponents) | Where-Object { -not $_.present } | Select-Object -First 1)
$preflightChecks += New-PreflightCheck -Id "components_in_manifest" -Status $(if ($componentsReady) { "passed" } else { "blocked" }) -Detail $(if ($componentsReady) { "All release components are present in VERSION.json." } else { "Missing manifest components: $(@($manifestComponents | Where-Object { -not $_.present } | ForEach-Object { $_.id }) -join ', ')" })

$coreInputs = @(
  New-InputResult -RelativePath "aegis-core\aegis_core" -Kind "container"
  New-InputResult -RelativePath "aegis-core\pyproject.toml" -Kind "leaf"
  New-InputResult -RelativePath "aegis-core\README.md" -Kind "leaf"
  New-InputResult -RelativePath "aegis-core\docs" -Kind "container"
)
$websiteInputs = @(
  New-InputResult -RelativePath "website\backend" -Kind "container"
  New-InputResult -RelativePath "website\frontend\dist" -Kind "container"
  New-InputResult -RelativePath "website\frontend\package.json" -Kind "leaf"
  New-InputResult -RelativePath "website\README.md" -Kind "leaf"
  New-InputResult -RelativePath "WEBSITE_CORE_ADAPTER.md" -Kind "leaf"
)
$desktopInputs = @(
  New-InputResult -RelativePath "x64\Release\AegisChatBotDesktop.exe" -Kind "leaf"
  New-InputResult -RelativePath "AegisChatBot.config.ini" -Kind "leaf"
  New-InputResult -RelativePath "README.md" -Kind "leaf"
  New-InputResult -RelativePath "INSTALL.md" -Kind "leaf"
  New-InputResult -RelativePath "docs\RELEASE_PACKAGING_AND_UPDATES.md" -Kind "leaf"
)

foreach ($inputGroup in @(
  @{ Id = "core_stage_inputs"; Inputs = $coreInputs; Label = "Core" },
  @{ Id = "website_stage_inputs"; Inputs = $websiteInputs; Label = "Website" },
  @{ Id = "desktop_stage_inputs"; Inputs = $desktopInputs; Label = "Desktop" }
)) {
  $ready = Test-AllInputsPresent -Inputs @($inputGroup.Inputs)
  $missingText = Get-MissingInputText -Inputs @($inputGroup.Inputs)
  $preflightChecks += New-PreflightCheck -Id $inputGroup.Id -Status $(if ($ready) { "passed" } else { "blocked" }) -Detail $(if ($ready) { "$($inputGroup.Label) stage inputs are present." } else { "$($inputGroup.Label) stage inputs are missing: $missingText" })
  if (-not $ready) {
    $blockers += New-Blocker -Id "$($inputGroup.Id)_missing" -Detail "$($inputGroup.Label) stage inputs are missing: $missingText"
  }
}

$vscodeCandidates = @(Get-VsixCandidates -ComponentName "vscode-extension" -RelativePaths @("vscode-plugins\aegis-local-autopilot\release", "vscode-plugins\aegis-local-autopilot"))
$visualStudioCandidates = @(Get-VsixCandidates -ComponentName "visual-studio-extension" -RelativePaths @("visual-studio-extensions\aegis-local-agent-vs\release"))

foreach ($candidateGroup in @(
  @{ Id = "vscode_vsix_candidate"; Candidates = $vscodeCandidates; Blocker = "vscode_vsix_missing"; Label = "VS Code" },
  @{ Id = "visual_studio_vsix_candidate"; Candidates = $visualStudioCandidates; Blocker = "visual_studio_vsix_missing"; Label = "Visual Studio" }
)) {
  $presentCandidate = @($candidateGroup.Candidates | Where-Object { $_.present } | Select-Object -First 1)
  $candidatePaths = @($candidateGroup.Candidates | ForEach-Object { [string]$_.path }) -join ", "
  $ready = $presentCandidate.Count -gt 0
  $preflightChecks += New-PreflightCheck -Id $candidateGroup.Id -Status $(if ($ready) { "passed" } else { "blocked" }) -Detail $(if ($ready) { "$($candidateGroup.Label) VSIX candidate is present: $($presentCandidate[0].path)" } else { "$($candidateGroup.Label) VSIX candidate is missing. Checked: $candidatePaths" })
  if (-not $ready) {
    $blockers += New-Blocker -Id $candidateGroup.Blocker -Detail "$($candidateGroup.Label) VSIX candidate is missing. Checked: $candidatePaths"
  }
}

$releaseManifestPath = Join-Path $Root "release\version-manifest.json"
$releaseManifestPresent = Test-Path -LiteralPath $releaseManifestPath -PathType Leaf
$preflightChecks += New-PreflightCheck -Id "release_manifest_generated" -Status $(if ($releaseManifestPresent) { "passed" } else { "blocked" }) -Detail $(if ($releaseManifestPresent) { "release/version-manifest.json is present." } else { "release/version-manifest.json is not present." })
if (-not $releaseManifestPresent) {
  $blockers += New-Blocker -Id "release_manifest_missing" -Detail "release/version-manifest.json is not present."
}

$releaseStatus = @(Get-GitStatusForReleaseArtifacts)
$releaseArtifactsDirty = $releaseStatus.Count -gt 0

$latestFinalReleaseManifestEvidence = Get-LatestFinalReleaseManifestEvidence
$finalReleaseManifestReady = $null -ne $latestFinalReleaseManifestEvidence -and [string]$latestFinalReleaseManifestEvidence.status -eq "ready"
$artifactDecisionPath = Join-Path $Root "docs\RELEASE_ARTIFACT_DECISION.md"
$artifactDecisionRecorded = $finalReleaseManifestReady -and (Test-Path -LiteralPath $artifactDecisionPath -PathType Leaf)
$preflightChecks += New-PreflightCheck -Id "final_release_manifest_evidence" -Status $(if ($finalReleaseManifestReady) { "passed" } else { "blocked" }) -Detail $(if ($finalReleaseManifestReady) { "Latest Phase 20 final release manifest evidence is ready: $($latestFinalReleaseManifestEvidence.folder)" } else { "No ready Phase 20 final release manifest evidence is attached." })
if (-not $finalReleaseManifestReady) {
  $blockers += New-Blocker -Id "final_release_manifest_not_ready" -Detail "No ready Phase 20 final release manifest evidence is attached."
}

$preflightChecks += New-PreflightCheck -Id "dirty_release_artifact_decision" -Status $(if (-not $releaseArtifactsDirty -or $artifactDecisionRecorded) { "passed" } else { "blocked" }) -Detail $(if (-not $releaseArtifactsDirty) { "Release artifact paths are clean." } elseif ($artifactDecisionRecorded) { "Release artifact paths have Git status entries, and Phase 20 records the accepted generated artifact decision." } else { "Release artifact paths have Git status entries that need an intentional decision." })
if ($releaseArtifactsDirty -and -not $artifactDecisionRecorded) {
  $blockers += New-Blocker -Id "dirty_release_artifacts_need_decision" -Detail "Release artifact paths have Git status entries that need an intentional decision before package mutation."
}

$latestReleaseEvidence = Get-LatestEvidenceFolder -RelativeRoot ".aegis\release-evidence"
$latestReleaseEvidenceRelative = if ($null -ne $latestReleaseEvidence) { Get-RelativePath $latestReleaseEvidence.FullName } else { "" }
$releaseMatrixPath = if ($null -ne $latestReleaseEvidence) { Join-Path $latestReleaseEvidence.FullName "validation-matrix.json" } else { "" }
$releaseMatrix = if (-not [string]::IsNullOrWhiteSpace($releaseMatrixPath)) { Read-JsonIfPresent -Path $releaseMatrixPath } else { $null }
$latestPackageDryRunEvidence = Get-LatestReleasePackageDryRunEvidence
$packageDryRunReady = $null -ne $latestPackageDryRunEvidence -and [string]$latestPackageDryRunEvidence.status -eq "ready"
$updatePlansReady = Test-UpdatePlansReady -DryRunEvidence $latestPackageDryRunEvidence -ComponentIds @($contract.components | ForEach-Object { [string]$_ })

$releasePackageGate = if ($packageDryRunReady) {
  [pscustomobject]@{
    id = "release_package_dry_run"
    status = "passed"
    reason = "Latest Phase 19 package dry-run evidence is ready: $($latestPackageDryRunEvidence.folder)"
  }
} else {
  Get-ReleaseGate -Matrix $releaseMatrix -GateId "release-package-dry-run"
}

$updatePlanGate = if ($updatePlansReady) {
  [pscustomobject]@{
    id = "update_plan_dry_run"
    status = "passed"
    reason = "Latest Phase 19 package dry-run evidence includes planned update dry-runs for every component: $($latestPackageDryRunEvidence.folder)"
  }
} else {
  Get-ReleaseGate -Matrix $releaseMatrix -GateId "update-plan-dry-run"
}

foreach ($gateGroup in @(
  @{ Id = "release_package_dry_run"; Gate = $releasePackageGate; Blocker = "release_package_dry_run_not_passed"; Label = "release-package-dry-run" },
  @{ Id = "update_plan_dry_run"; Gate = $updatePlanGate; Blocker = "update_plan_dry_run_not_passed"; Label = "update-plan-dry-run" }
)) {
  $passed = [string]$gateGroup.Gate.status -eq "passed"
  $preflightChecks += New-PreflightCheck -Id $gateGroup.Id -Status $(if ($passed) { "passed" } else { "blocked" }) -Detail "$($gateGroup.Label) status is '$($gateGroup.Gate.status)'. $($gateGroup.Gate.reason)"
  if (-not $passed) {
    $blockers += New-Blocker -Id $gateGroup.Blocker -Detail "No latest release evidence shows $($gateGroup.Label) passed. Current status: $($gateGroup.Gate.status)."
  }
}

Assert-SetIncludes -IdPrefix "runtime-preflight-check" -Values @($preflightChecks | ForEach-Object { $_.id }) -Required @($contract.required_preflight_checks | ForEach-Object { [string]$_ }) -Label "Runtime preflight checks"
if (@($contract.required_blocker_ids).Count -gt 0) {
  Assert-SetIncludes -IdPrefix "runtime-blocker" -Values @($blockers | ForEach-Object { $_.id }) -Required @($contract.required_blocker_ids | ForEach-Object { [string]$_ }) -Label "Runtime preflight blockers"
} else {
  Add-ContractCheck -Id "runtime-blockers-empty" -Passed ($blockers.Count -eq 0) -Detail "Runtime preflight blockers must be empty for the current ready release evidence state."
}

$preflightStatus = if ($blockers.Count -gt 0) { "blocked" } elseif ($releaseManifestPresent) { "ready" } else { "attention" }
Add-ContractCheck -Id "preflight-current-status" -Passed ($preflightStatus -eq [string]$contract.current_required_status) -Detail "Release preflight status must remain '$($contract.current_required_status)' for the current evidence state."

$payload = [pscustomobject]@{
  root = $Root
  status = $preflightStatus
  generated_at = (Get-Date).ToString("o")
  evidence_dir = $EvidenceDir
  contract = [pscustomobject]@{
    schema_version = [string]$contract.schema_version
    evidence_root = [string]$contract.evidence_root
  }
  source_manifest = [pscustomobject]@{
    path = "VERSION.json"
    present = $sourceManifestPresent
    schema_version = if ($null -ne $sourceManifest) { [string]$sourceManifest.schema_version } else { "" }
    components = $manifestComponents
  }
  release_manifest = [pscustomobject]@{
    path = "release\version-manifest.json"
    present = $releaseManifestPresent
  }
  stage_inputs = [pscustomobject]@{
    core = $coreInputs
    website = $websiteInputs
    desktop = $desktopInputs
    vscode_candidates = $vscodeCandidates
    visual_studio_candidates = $visualStudioCandidates
  }
  dirty_release_artifacts = [pscustomobject]@{
    dirty = $releaseArtifactsDirty
    status_lines = $releaseStatus
  }
  latest_release_evidence = [pscustomobject]@{
    folder = $latestReleaseEvidenceRelative
    validation_matrix = if (-not [string]::IsNullOrWhiteSpace($releaseMatrixPath)) { Get-RelativePath $releaseMatrixPath } else { "" }
    release_package_dry_run = $releasePackageGate
    update_plan_dry_run = $updatePlanGate
  }
  release_package_dry_run_evidence = if ($null -ne $latestPackageDryRunEvidence) {
    [pscustomobject]@{
      folder = [string]$latestPackageDryRunEvidence.folder
      json_path = [string]$latestPackageDryRunEvidence.json_path
      status = [string]$latestPackageDryRunEvidence.status
      update_plans_ready = $updatePlansReady
    }
  } else {
    [pscustomobject]@{
      folder = ""
      json_path = ""
      status = "missing"
      update_plans_ready = $false
    }
  }
  final_release_manifest_evidence = if ($null -ne $latestFinalReleaseManifestEvidence) {
    [pscustomobject]@{
      folder = [string]$latestFinalReleaseManifestEvidence.folder
      json_path = [string]$latestFinalReleaseManifestEvidence.json_path
      status = [string]$latestFinalReleaseManifestEvidence.status
      artifact_decision_recorded = $artifactDecisionRecorded
    }
  } else {
    [pscustomobject]@{
      folder = ""
      json_path = ""
      status = "missing"
      artifact_decision_recorded = $artifactDecisionRecorded
    }
  }
  preflight_checks = $preflightChecks
  blockers = $blockers
  contract_checks = $script:Checks
}

New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$jsonPath = Join-Path $EvidenceDir "release-artifact-preflight.json"
$markdownPath = Join-Path $EvidenceDir "release-artifact-preflight-summary.md"
$payload | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 17 Release Artifact Preflight"
$markdown += ""
$markdown += "- Status: $($payload.status)"
$markdown += "- Generated at: $($payload.generated_at)"
$markdown += "- Evidence dir: $EvidenceDir"
$markdown += "- Source manifest present: $sourceManifestPresent"
$markdown += "- Release manifest present: $releaseManifestPresent"
$markdown += "- Latest release evidence: $latestReleaseEvidenceRelative"
$markdown += "- Latest package dry-run evidence: $(if ($null -ne $latestPackageDryRunEvidence) { $latestPackageDryRunEvidence.folder } else { '' })"
$markdown += "- Latest final release manifest evidence: $(if ($null -ne $latestFinalReleaseManifestEvidence) { $latestFinalReleaseManifestEvidence.folder } else { '' })"
$markdown += "- Dirty release artifact paths: $releaseArtifactsDirty"
$markdown += "- Artifact decision recorded: $artifactDecisionRecorded"
$markdown += "- Blockers: $($blockers.Count)"
$markdown += ""
$markdown += "## Preflight Checks"
$markdown += ""
$markdown += "| Check | Status | Detail |"
$markdown += "| --- | --- | --- |"
foreach ($check in $preflightChecks) {
  $detail = ([string]$check.detail).Replace("|", "\|")
  $markdown += "| $($check.id) | $($check.status) | $detail |"
}
$markdown += ""
$markdown += "## Blockers"
$markdown += ""
$markdown += "| Blocker | Detail |"
$markdown += "| --- | --- |"
foreach ($blocker in $blockers) {
  $detail = ([string]$blocker.detail).Replace("|", "\|")
  $markdown += "| $($blocker.id) | $detail |"
}
$markdown += ""
$markdown += "## Stage Inputs"
$markdown += ""
$markdown += "| Area | Path | Present |"
$markdown += "| --- | --- | --- |"
foreach ($entry in @($coreInputs | ForEach-Object { [pscustomobject]@{ Area = "core"; Entry = $_ } }) + @($websiteInputs | ForEach-Object { [pscustomobject]@{ Area = "website"; Entry = $_ } }) + @($desktopInputs | ForEach-Object { [pscustomobject]@{ Area = "desktop"; Entry = $_ } })) {
  $markdown += "| $($entry.Area) | $($entry.Entry.path) | $($entry.Entry.present) |"
}
$markdown += ""
$markdown += "## VSIX Candidates"
$markdown += ""
$markdown += "| Area | Path | Present | Size Bytes |"
$markdown += "| --- | --- | --- | ---: |"
foreach ($entry in @($vscodeCandidates | ForEach-Object { [pscustomobject]@{ Area = "vscode"; Entry = $_ } }) + @($visualStudioCandidates | ForEach-Object { [pscustomobject]@{ Area = "visual-studio"; Entry = $_ } })) {
  $markdown += "| $($entry.Area) | $($entry.Entry.path) | $($entry.Entry.present) | $($entry.Entry.size_bytes) |"
}
$markdown += ""
$markdown += "## Dirty Release Artifact Status"
$markdown += ""
if ($releaseStatus.Count -gt 0) {
  foreach ($line in $releaseStatus) {
    $markdown += "- ``$line``"
  }
} else {
  $markdown += "- No release artifact Git status entries."
}
$markdown | Set-Content -LiteralPath $markdownPath -Encoding UTF8

$payload | ConvertTo-Json -Depth 12

if ($script:Failures.Count -gt 0) {
  throw "Release artifact preflight validation failed:`n - $($script:Failures -join "`n - ")"
}
