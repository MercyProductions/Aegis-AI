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
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\evidence-ledger" (Get-Date -Format "yyyyMMdd-HHmmss"))
} else {
  $EvidenceDir = [System.IO.Path]::GetFullPath($EvidenceDir)
}

$script:Checks = @()
$script:Failures = @()

function Read-ProjectFile {
  param([Parameter(Mandatory = $true)][string]$RelativePath)

  $path = Join-Path $Root $RelativePath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "Required evidence ledger file is missing: $RelativePath"
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

function Add-LedgerCheck {
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

  Add-LedgerCheck -Id $Id -Passed ([bool]($Text -match $Pattern)) -Detail $Detail
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
    Add-LedgerCheck -Id "$IdPrefix-$(ConvertTo-CheckId $item)" -Passed ($actual -contains $item) -Detail "$Label must include '$item'."
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
    Add-LedgerCheck -Id "$IdPrefix-$(ConvertTo-CheckId $item)" -Passed ($actual -contains $item) -Detail "$Label must include '$item'."
  }
}

function Get-RelativePath {
  param([Parameter(Mandatory = $true)][string]$FullPath)

  $rootUri = [System.Uri]::new(($Root.TrimEnd('\') + '\'))
  $pathUri = [System.Uri]::new($FullPath)
  return [System.Uri]::UnescapeDataString($rootUri.MakeRelativeUri($pathUri).ToString()).Replace("/", "\")
}

function Get-LatestEvidenceFolder {
  param([Parameter(Mandatory = $true)][string]$RelativeRoot)

  $path = Join-Path $Root $RelativeRoot
  if (-not (Test-Path -LiteralPath $path -PathType Container)) {
    return $null
  }
  return Get-ChildItem -LiteralPath $path -Directory | Sort-Object Name -Descending | Select-Object -First 1
}

function Get-LedgerSource {
  param([Parameter(Mandatory = $true)][object]$Source)

  $latest = Get-LatestEvidenceFolder -RelativeRoot ([string]$Source.root)
  $files = @()
  $missing = @()
  if ($null -ne $latest) {
    foreach ($file in @($Source.required_files)) {
      $fileName = [string]$file
      $path = Join-Path $latest.FullName $fileName
      if (Test-Path -LiteralPath $path -PathType Leaf) {
        $files += [pscustomobject]@{
          name = $fileName
          path = Get-RelativePath $path
          present = $true
        }
      } else {
        $missing += $fileName
        $files += [pscustomobject]@{
          name = $fileName
          path = Get-RelativePath $path
          present = $false
        }
      }
    }
  } else {
    $missing = @($Source.required_files | ForEach-Object { [string]$_ })
  }

  return [pscustomobject]@{
    id = [string]$Source.id
    root = [string]$Source.root
    latest_folder = if ($null -ne $latest) { Get-RelativePath $latest.FullName } else { "" }
    status = if ($null -eq $latest) { "missing" } elseif ($missing.Count -gt 0) { "attention" } else { "present" }
    files = $files
    missing_files = $missing
  }
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

function Get-ReleaseGateSummary {
  param([string]$ReleaseFolder)

  if ([string]::IsNullOrWhiteSpace($ReleaseFolder)) {
    return [pscustomobject]@{
      overall_status = "missing"
      gate_counts = @{}
      gates = @()
    }
  }
  $matrixPath = Join-Path $Root (Join-Path $ReleaseFolder "validation-matrix.json")
  $matrix = Read-JsonIfPresent -Path $matrixPath
  if ($null -eq $matrix) {
    return [pscustomobject]@{
      overall_status = "missing"
      gate_counts = @{}
      gates = @()
    }
  }
  $counts = @{}
  foreach ($result in @($matrix.results)) {
    $status = [string]$result.status
    if (-not $counts.ContainsKey($status)) {
      $counts[$status] = 0
    }
    $counts[$status] = [int]$counts[$status] + 1
  }
  return [pscustomobject]@{
    overall_status = [string]$matrix.overall_status
    gate_counts = $counts
    gates = @($matrix.results | ForEach-Object {
      [pscustomobject]@{
        id = [string]$_.id
        status = [string]$_.status
        reason = [string]$_.reason
      }
    })
  }
}

function Test-GatePassed {
  param(
    [Parameter(Mandatory = $true)][object]$GateSummary,
    [Parameter(Mandatory = $true)][string]$GateId
  )

  return [bool](@($GateSummary.gates) | Where-Object { [string]$_.id -eq $GateId -and [string]$_.status -eq "passed" } | Select-Object -First 1)
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

$contract = Read-ProjectJson "evals\phase16-evidence-ledger-contract.json"
$ledgerDocs = Read-ProjectFile "docs\EVIDENCE_LEDGER.md"
$externalReport = Read-ProjectFile "docs\EXTERNAL_ALPHA_RELEASE_REPORT.md"
$validationDocs = Read-ProjectFile "docs\VALIDATION_MATRIX.md"
$knownUnstable = Read-ProjectFile "KNOWN_UNSTABLE_SURFACES.md"
$validator = Read-ProjectFile "scripts\validate-ecosystem.ps1"
$externalAlphaScript = Read-ProjectFile "scripts\test-external-alpha-contract.ps1"

Add-LedgerCheck -Id "contract-schema-version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Detail "Phase 16 evidence ledger contract must use the current schema version."
Add-LedgerCheck -Id "contract-evidence-root" -Passed ([string]$contract.evidence_root -eq ".aegis/evidence-ledger") -Detail "Phase 16 evidence ledger must have a stable .aegis root."
Add-LedgerCheck -Id "contract-current-status-attention" -Passed ([string]$contract.current_required_status -eq "attention") -Detail "Current evidence ledger status must be attention after Phase 37 handoff while live smoke and publish gaps remain."
Assert-SetIncludes -IdPrefix "status-value" -Values @($contract.status_values) -Required @("missing", "blocked", "attention", "ready") -Label "Ledger status values"
Assert-SetIncludes -IdPrefix "evidence-root" -Values @($contract.evidence_roots) -Required @(".aegis/release-evidence", ".aegis/release-preflight", ".aegis/release-package-dry-run", ".aegis/final-release-manifest", ".aegis/release-apply-rollback", ".aegis/packaged-alpha-scenarios", ".aegis/cross-client-parity", ".aegis/release-notes-limitations", ".aegis/core-website-ownership", ".aegis/backend-modularization", ".aegis/frontend-extraction", ".aegis/desktop-shell-hardening", ".aegis/editor-extension-modularization", ".aegis/provider-secret-safety", ".aegis/memory-governance", ".aegis/plugin-lifecycle", ".aegis/observability-ci", ".aegis/distribution-update", ".aegis/alpha-readiness-polish", ".aegis/live-smoke-rc", ".aegis/commit-scoping-github-handoff", ".aegis/desktop-smoke-package-gates", ".aegis/editor-smoke-release-package-decision", ".aegis/extension-package-candidates", ".aegis/quality-evidence", ".aegis/plugin-evidence", ".aegis/alpha-evidence", ".aegis/external-alpha-evidence", ".aegis/evidence-ledger") -Label "Evidence roots"
Assert-ObjectIdsInclude -IdPrefix "ledger-source" -Objects @($contract.ledger_sources) -Required @("release_validation", "release_artifact_preflight", "release_package_dry_run", "final_release_manifest", "release_apply_rollback", "packaged_alpha_scenarios", "cross_client_parity", "release_notes_limitations", "core_website_ownership", "backend_modularization", "frontend_extraction", "desktop_shell_hardening", "editor_extension_modularization", "provider_secret_safety", "memory_governance", "plugin_lifecycle", "observability_ci", "distribution_update", "alpha_readiness_polish", "live_smoke_rc", "commit_scoping_github_handoff", "desktop_smoke_package_gates", "editor_smoke_release_package_decision", "extension_package_candidates", "quality_contract", "plugin_contract", "alpha_contract", "external_alpha_contract") -Label "Ledger sources"
Add-LedgerCheck -Id "blocker-list-cleared" -Passed (@($contract.required_blocker_ids).Count -eq 0) -Detail "Ledger contract must not require runtime blockers after Phase 37 commit scoping handoff evidence is attached."
Assert-SetIncludes -IdPrefix "required-gate" -Values @($contract.required_validation_gate_ids) -Required @("release-package-dry-run-contract", "final-release-manifest-contract", "release-apply-rollback-contract", "packaged-alpha-scenarios-contract", "cross-client-parity-contract", "release-notes-limitations-contract", "core-website-ownership-contract", "backend-modularization-contract", "frontend-extraction-contract", "desktop-shell-hardening-contract", "editor-extension-modularization-contract", "provider-secret-safety-contract", "memory-governance-contract", "plugin-lifecycle-contract", "observability-ci-contract", "distribution-update-contract", "alpha-readiness-polish-contract", "live-smoke-rc-contract", "commit-scoping-github-handoff-contract", "desktop-smoke-package-gates-contract", "editor-smoke-release-package-decision-contract", "release-package-dry-run", "update-plan-dry-run", "release-artifact-preflight", "extension-package-candidates", "alpha-contract", "external-alpha-contract", "evidence-ledger-contract") -Label "Required validation gates"
Assert-SetIncludes -IdPrefix "ledger-output" -Values @($contract.ledger_outputs) -Required @("evidence-ledger.json", "evidence-ledger-summary.md") -Label "Ledger outputs"

foreach ($file in @($contract.required_contract_files)) {
  $relativePath = [string]$file
  Add-LedgerCheck -Id "contract-file-$(ConvertTo-CheckId $relativePath)" -Passed (Test-Path -LiteralPath (Join-Path $Root $relativePath) -PathType Leaf) -Detail "Required Phase 16 contract file must exist: $relativePath"
}

Assert-SourceContains -Id "docs-ledger-contract-link" -Text $ledgerDocs -Pattern 'phase16-evidence-ledger-contract\.json' -Detail "Evidence ledger docs must link the Phase 16 contract."
Assert-SourceContains -Id "docs-ledger-command" -Text $ledgerDocs -Pattern 'test-evidence-ledger-contract\.ps1' -Detail "Evidence ledger docs must document the validation command."
Assert-SourceContains -Id "docs-ledger-output" -Text $ledgerDocs -Pattern 'evidence-ledger-summary\.md' -Detail "Evidence ledger docs must document markdown output."
Assert-SourceContains -Id "docs-ledger-attention" -Text $ledgerDocs -Pattern 'current status is attention' -Detail "Evidence ledger docs must keep current attention status explicit."
Assert-SourceContains -Id "docs-ledger-preflight-source" -Text $ledgerDocs -Pattern '\.aegis/release-preflight|release_artifact_preflight' -Detail "Evidence ledger docs must include the release preflight source."
Assert-SourceContains -Id "docs-ledger-package-dry-run-source" -Text $ledgerDocs -Pattern '\.aegis/release-package-dry-run|release_package_dry_run' -Detail "Evidence ledger docs must include the release package dry-run source."
Assert-SourceContains -Id "docs-ledger-final-manifest-source" -Text $ledgerDocs -Pattern '\.aegis/final-release-manifest|final_release_manifest' -Detail "Evidence ledger docs must include the final release manifest source."
Assert-SourceContains -Id "docs-ledger-release-apply-rollback-source" -Text $ledgerDocs -Pattern '\.aegis/release-apply-rollback|release_apply_rollback' -Detail "Evidence ledger docs must include the release apply/rollback source."
Assert-SourceContains -Id "docs-ledger-packaged-alpha-scenarios-source" -Text $ledgerDocs -Pattern '\.aegis/packaged-alpha-scenarios|packaged_alpha_scenarios' -Detail "Evidence ledger docs must include the packaged alpha scenario source."
Assert-SourceContains -Id "docs-ledger-cross-client-parity-source" -Text $ledgerDocs -Pattern '\.aegis/cross-client-parity|cross_client_parity' -Detail "Evidence ledger docs must include the cross-client parity source."
Assert-SourceContains -Id "docs-ledger-release-notes-limitations-source" -Text $ledgerDocs -Pattern '\.aegis/release-notes-limitations|release_notes_limitations' -Detail "Evidence ledger docs must include the release notes limitations source."
Assert-SourceContains -Id "docs-ledger-core-website-ownership-source" -Text $ledgerDocs -Pattern '\.aegis/core-website-ownership|core_website_ownership' -Detail "Evidence ledger docs must include the Core/Website ownership source."
Assert-SourceContains -Id "docs-ledger-backend-modularization-source" -Text $ledgerDocs -Pattern '\.aegis/backend-modularization|backend_modularization' -Detail "Evidence ledger docs must include the backend modularization source."
Assert-SourceContains -Id "docs-ledger-frontend-extraction-source" -Text $ledgerDocs -Pattern '\.aegis/frontend-extraction|frontend_extraction' -Detail "Evidence ledger docs must include the frontend extraction source."
Assert-SourceContains -Id "docs-ledger-desktop-shell-hardening-source" -Text $ledgerDocs -Pattern '\.aegis/desktop-shell-hardening|desktop_shell_hardening' -Detail "Evidence ledger docs must include the native desktop shell source."
Assert-SourceContains -Id "docs-ledger-editor-extension-modularization-source" -Text $ledgerDocs -Pattern '\.aegis/editor-extension-modularization|editor_extension_modularization' -Detail "Evidence ledger docs must include the editor extension modularization source."
Assert-SourceContains -Id "docs-ledger-provider-secret-safety-source" -Text $ledgerDocs -Pattern '\.aegis/provider-secret-safety|provider_secret_safety' -Detail "Evidence ledger docs must include the provider secret safety source."
Assert-SourceContains -Id "docs-ledger-memory-governance-source" -Text $ledgerDocs -Pattern '\.aegis/memory-governance|memory_governance' -Detail "Evidence ledger docs must include the memory governance source."
Assert-SourceContains -Id "docs-ledger-plugin-lifecycle-source" -Text $ledgerDocs -Pattern '\.aegis/plugin-lifecycle|plugin_lifecycle' -Detail "Evidence ledger docs must include the plugin lifecycle source."
Assert-SourceContains -Id "docs-ledger-observability-ci-source" -Text $ledgerDocs -Pattern '\.aegis/observability-ci|observability_ci' -Detail "Evidence ledger docs must include the observability CI source."
Assert-SourceContains -Id "docs-ledger-distribution-update-source" -Text $ledgerDocs -Pattern '\.aegis/distribution-update|distribution_update' -Detail "Evidence ledger docs must include the distribution/update source."
Assert-SourceContains -Id "docs-ledger-alpha-readiness-polish-source" -Text $ledgerDocs -Pattern '\.aegis/alpha-readiness-polish|alpha_readiness_polish' -Detail "Evidence ledger docs must include the alpha readiness polish source."
Assert-SourceContains -Id "docs-ledger-live-smoke-rc-source" -Text $ledgerDocs -Pattern '\.aegis/live-smoke-rc|live_smoke_rc' -Detail "Evidence ledger docs must include the Phase 36 live smoke RC source."
Assert-SourceContains -Id "docs-ledger-commit-scoping-github-handoff-source" -Text $ledgerDocs -Pattern '\.aegis/commit-scoping-github-handoff|commit_scoping_github_handoff' -Detail "Evidence ledger docs must include the Phase 37 commit scoping GitHub handoff source."
Assert-SourceContains -Id "docs-ledger-desktop-smoke-package-gates-source" -Text $ledgerDocs -Pattern '\.aegis/desktop-smoke-package-gates|desktop_smoke_package_gates' -Detail "Evidence ledger docs must include the Phase 38 desktop smoke package gates source."
Assert-SourceContains -Id "docs-ledger-editor-smoke-release-package-decision-source" -Text $ledgerDocs -Pattern '\.aegis/editor-smoke-release-package-decision|editor_smoke_release_package_decision' -Detail "Evidence ledger docs must include the Phase 39 editor smoke release package decision source."
Assert-SourceContains -Id "docs-ledger-package-candidates-source" -Text $ledgerDocs -Pattern '\.aegis/extension-package-candidates|extension_package_candidates' -Detail "Evidence ledger docs must include the extension package candidates source."
Assert-SourceContains -Id "external-report-ledger" -Text $externalReport -Pattern 'EVIDENCE_LEDGER\.md|evidence-ledger' -Detail "External alpha report must reference the evidence ledger."
Assert-SourceContains -Id "external-report-preflight" -Text $externalReport -Pattern 'release-preflight|RELEASE_ARTIFACT_PREFLIGHT' -Detail "External alpha report must reference release artifact preflight evidence."
Assert-SourceContains -Id "validation-doc-ledger" -Text $validationDocs -Pattern 'evidence-ledger-contract|test-evidence-ledger-contract' -Detail "Validation matrix docs must document the evidence ledger gate."
Assert-SourceContains -Id "validation-doc-preflight" -Text $validationDocs -Pattern 'release-artifact-preflight|test-release-artifact-preflight' -Detail "Validation matrix docs must document the release preflight gate."
Assert-SourceContains -Id "validation-doc-package-dry-run" -Text $validationDocs -Pattern 'release-package-dry-run-contract|test-release-package-dry-run' -Detail "Validation matrix docs must document the package dry-run contract gate."
Assert-SourceContains -Id "validation-doc-packaged-alpha-scenarios" -Text $validationDocs -Pattern 'packaged-alpha-scenarios-contract|test-packaged-alpha-scenarios' -Detail "Validation matrix docs must document the packaged alpha scenario gate."
Assert-SourceContains -Id "validation-doc-cross-client-parity" -Text $validationDocs -Pattern 'cross-client-parity-contract|test-cross-client-parity' -Detail "Validation matrix docs must document the cross-client parity gate."
Assert-SourceContains -Id "validation-doc-release-notes-limitations" -Text $validationDocs -Pattern 'release-notes-limitations-contract|test-release-notes-limitations' -Detail "Validation matrix docs must document the release notes limitations gate."
Assert-SourceContains -Id "validation-doc-core-website-ownership" -Text $validationDocs -Pattern 'core-website-ownership-contract|test-core-website-ownership' -Detail "Validation matrix docs must document the Core/Website ownership gate."
Assert-SourceContains -Id "validation-doc-backend-modularization" -Text $validationDocs -Pattern 'backend-modularization-contract|test-backend-modularization' -Detail "Validation matrix docs must document the backend modularization gate."
Assert-SourceContains -Id "validation-doc-frontend-extraction" -Text $validationDocs -Pattern 'frontend-extraction-contract|test-frontend-extraction' -Detail "Validation matrix docs must document the frontend extraction gate."
Assert-SourceContains -Id "validation-doc-desktop-shell-hardening" -Text $validationDocs -Pattern 'desktop-shell-hardening-contract|test-native-desktop-shell' -Detail "Validation matrix docs must document the native desktop shell gate."
Assert-SourceContains -Id "validation-doc-editor-extension-modularization" -Text $validationDocs -Pattern 'editor-extension-modularization-contract|test-editor-extension-modularization' -Detail "Validation matrix docs must document the editor extension modularization gate."
Assert-SourceContains -Id "validation-doc-provider-secret-safety" -Text $validationDocs -Pattern 'provider-secret-safety-contract|test-provider-secret-safety' -Detail "Validation matrix docs must document the provider secret safety gate."
Assert-SourceContains -Id "validation-doc-memory-governance" -Text $validationDocs -Pattern 'memory-governance-contract|test-memory-governance' -Detail "Validation matrix docs must document the memory governance gate."
Assert-SourceContains -Id "validation-doc-plugin-lifecycle" -Text $validationDocs -Pattern 'plugin-lifecycle-contract|test-plugin-lifecycle' -Detail "Validation matrix docs must document the plugin lifecycle gate."
Assert-SourceContains -Id "validation-doc-observability-ci" -Text $validationDocs -Pattern 'observability-ci-contract|test-observability-ci' -Detail "Validation matrix docs must document the observability CI gate."
Assert-SourceContains -Id "validation-doc-distribution-update" -Text $validationDocs -Pattern 'distribution-update-contract|test-distribution-update' -Detail "Validation matrix docs must document the distribution/update gate."
Assert-SourceContains -Id "validation-doc-alpha-readiness-polish" -Text $validationDocs -Pattern 'alpha-readiness-polish-contract|test-alpha-readiness-polish' -Detail "Validation matrix docs must document the alpha readiness polish gate."
Assert-SourceContains -Id "validation-doc-live-smoke-rc" -Text $validationDocs -Pattern 'live-smoke-rc-contract|test-live-smoke-rc' -Detail "Validation matrix docs must document the Phase 36 live smoke RC gate."
Assert-SourceContains -Id "validation-doc-commit-scoping-github-handoff" -Text $validationDocs -Pattern 'commit-scoping-github-handoff-contract|test-commit-scoping-github-handoff' -Detail "Validation matrix docs must document the Phase 37 commit scoping GitHub handoff gate."
Assert-SourceContains -Id "validation-doc-desktop-smoke-package-gates" -Text $validationDocs -Pattern 'desktop-smoke-package-gates-contract|test-desktop-smoke-package-gates' -Detail "Validation matrix docs must document the Phase 38 desktop smoke package gates gate."
Assert-SourceContains -Id "validation-doc-editor-smoke-release-package-decision" -Text $validationDocs -Pattern 'editor-smoke-release-package-decision-contract|test-editor-smoke-release-package-decision' -Detail "Validation matrix docs must document the Phase 39 editor smoke release package decision gate."
Assert-SourceContains -Id "validation-doc-package-candidates" -Text $validationDocs -Pattern 'extension-package-candidates|test-extension-package-candidates' -Detail "Validation matrix docs must document the extension package candidates gate."
Assert-SourceContains -Id "known-unstable-release" -Text $knownUnstable -Pattern 'conditional private external alpha|Release promotion is blocked|Release packaging is blocked' -Detail "Known unstable surfaces must keep release packaging or conditional alpha boundary visible."
Assert-SourceContains -Id "validator-ledger-gate" -Text $validator -Pattern 'test-evidence-ledger-contract\.ps1' -Detail "Ecosystem validation must run the evidence ledger contract gate."
Assert-SourceContains -Id "validator-ledger-evidence-dir" -Text $validator -Pattern 'evidence-ledger-contract' -Detail "Ecosystem validation must place evidence ledger output under the release evidence directory."
Assert-SourceContains -Id "validator-provider-secret-safety-gate" -Text $validator -Pattern 'test-provider-secret-safety\.ps1' -Detail "Ecosystem validation must run the provider secret safety contract gate."
Assert-SourceContains -Id "validator-memory-governance-gate" -Text $validator -Pattern 'test-memory-governance\.ps1' -Detail "Ecosystem validation must run the memory governance contract gate."
Assert-SourceContains -Id "validator-plugin-lifecycle-gate" -Text $validator -Pattern 'test-plugin-lifecycle\.ps1' -Detail "Ecosystem validation must run the plugin lifecycle contract gate."
Assert-SourceContains -Id "validator-observability-ci-gate" -Text $validator -Pattern 'test-observability-ci\.ps1' -Detail "Ecosystem validation must run the observability CI contract gate."
Assert-SourceContains -Id "validator-distribution-update-gate" -Text $validator -Pattern 'test-distribution-update\.ps1' -Detail "Ecosystem validation must run the distribution/update contract gate."
Assert-SourceContains -Id "validator-alpha-readiness-polish-gate" -Text $validator -Pattern 'test-alpha-readiness-polish\.ps1' -Detail "Ecosystem validation must run the alpha readiness polish contract gate."
Assert-SourceContains -Id "validator-live-smoke-rc-gate" -Text $validator -Pattern 'test-live-smoke-rc\.ps1' -Detail "Ecosystem validation must run the Phase 36 live smoke RC contract gate."
Assert-SourceContains -Id "validator-commit-scoping-github-handoff-gate" -Text $validator -Pattern 'test-commit-scoping-github-handoff\.ps1' -Detail "Ecosystem validation must run the Phase 37 commit scoping GitHub handoff contract gate."
Assert-SourceContains -Id "validator-desktop-smoke-package-gates-gate" -Text $validator -Pattern 'test-desktop-smoke-package-gates\.ps1' -Detail "Ecosystem validation must run the Phase 38 desktop smoke package gates contract gate."
Assert-SourceContains -Id "validator-editor-smoke-release-package-decision-gate" -Text $validator -Pattern 'test-editor-smoke-release-package-decision\.ps1' -Detail "Ecosystem validation must run the Phase 39 editor smoke release package decision contract gate."
Assert-SourceContains -Id "external-alpha-script-ledger-source" -Text $externalAlphaScript -Pattern 'phase15-external-alpha-release-contract\.json' -Detail "External alpha contract remains the upstream decision gate for ledger reporting."

$sources = @($contract.ledger_sources | ForEach-Object { Get-LedgerSource -Source $_ })
$releaseSource = @($sources | Where-Object { $_.id -eq "release_validation" } | Select-Object -First 1)
$releaseSummary = Get-ReleaseGateSummary -ReleaseFolder ([string]$releaseSource.latest_folder)
$packageDryRunEvidence = Get-LatestReleasePackageDryRunEvidence
$packageDryRunReady = $null -ne $packageDryRunEvidence -and [string]$packageDryRunEvidence.status -eq "ready"
$updatePlansReady = Test-UpdatePlansReady -DryRunEvidence $packageDryRunEvidence -ComponentIds @("aegis-core", "website", "desktop", "vscode-extension", "visual-studio-extension")
$finalReleaseManifestEvidence = Get-LatestFinalReleaseManifestEvidence
$finalReleaseManifestReady = $null -ne $finalReleaseManifestEvidence -and [string]$finalReleaseManifestEvidence.status -eq "ready"

$releaseManifestPath = Join-Path $Root "release\version-manifest.json"
$releaseManifestPresent = Test-Path -LiteralPath $releaseManifestPath -PathType Leaf
$blockers = @()
if (-not $releaseManifestPresent) {
  $blockers += New-Blocker -Id "release_manifest_missing" -Detail "release/version-manifest.json is not present."
}
if (-not $finalReleaseManifestReady) {
  $blockers += New-Blocker -Id "final_release_manifest_not_ready" -Detail "No ready Phase 20 final release manifest evidence is attached."
}
if (-not $packageDryRunReady) {
  $blockers += New-Blocker -Id "release_package_dry_run_not_passed" -Detail "No ready Phase 19 package dry-run evidence is attached."
}
if (-not $updatePlansReady) {
  $blockers += New-Blocker -Id "update_plan_dry_run_not_passed" -Detail "No ready Phase 19 evidence includes planned update dry-runs for every component."
}
$preflightSource = @($sources | Where-Object { $_.id -eq "release_artifact_preflight" } | Select-Object -First 1)
$preflightJsonPath = if ($null -ne $preflightSource -and -not [string]::IsNullOrWhiteSpace([string]$preflightSource.latest_folder)) { Join-Path $Root (Join-Path ([string]$preflightSource.latest_folder) "release-artifact-preflight.json") } else { "" }
$preflightJson = if (-not [string]::IsNullOrWhiteSpace($preflightJsonPath)) { Read-JsonIfPresent -Path $preflightJsonPath } else { $null }
$packagedAlphaScenariosSource = @($sources | Where-Object { $_.id -eq "packaged_alpha_scenarios" } | Select-Object -First 1)
$packagedAlphaScenariosJsonPath = if ($null -ne $packagedAlphaScenariosSource -and -not [string]::IsNullOrWhiteSpace([string]$packagedAlphaScenariosSource.latest_folder)) { Join-Path $Root (Join-Path ([string]$packagedAlphaScenariosSource.latest_folder) "packaged-alpha-scenarios.json") } else { "" }
$packagedAlphaScenariosJson = if (-not [string]::IsNullOrWhiteSpace($packagedAlphaScenariosJsonPath)) { Read-JsonIfPresent -Path $packagedAlphaScenariosJsonPath } else { $null }
$packagedAlphaScenariosReady = $null -ne $packagedAlphaScenariosJson -and [string]$packagedAlphaScenariosJson.status -eq "ready"
$crossClientParitySource = @($sources | Where-Object { $_.id -eq "cross_client_parity" } | Select-Object -First 1)
$crossClientParityJsonPath = if ($null -ne $crossClientParitySource -and -not [string]::IsNullOrWhiteSpace([string]$crossClientParitySource.latest_folder)) { Join-Path $Root (Join-Path ([string]$crossClientParitySource.latest_folder) "cross-client-parity.json") } else { "" }
$crossClientParityJson = if (-not [string]::IsNullOrWhiteSpace($crossClientParityJsonPath)) { Read-JsonIfPresent -Path $crossClientParityJsonPath } else { $null }
$crossClientParityReady = $null -ne $crossClientParityJson -and [string]$crossClientParityJson.status -eq "ready"
$releaseNotesLimitationsSource = @($sources | Where-Object { $_.id -eq "release_notes_limitations" } | Select-Object -First 1)
$releaseNotesLimitationsJsonPath = if ($null -ne $releaseNotesLimitationsSource -and -not [string]::IsNullOrWhiteSpace([string]$releaseNotesLimitationsSource.latest_folder)) { Join-Path $Root (Join-Path ([string]$releaseNotesLimitationsSource.latest_folder) "release-notes-limitations.json") } else { "" }
$releaseNotesLimitationsJson = if (-not [string]::IsNullOrWhiteSpace($releaseNotesLimitationsJsonPath)) { Read-JsonIfPresent -Path $releaseNotesLimitationsJsonPath } else { $null }
$releaseNotesLimitationsReady = $null -ne $releaseNotesLimitationsJson -and [string]$releaseNotesLimitationsJson.status -eq "ready"
$coreWebsiteOwnershipSource = @($sources | Where-Object { $_.id -eq "core_website_ownership" } | Select-Object -First 1)
$coreWebsiteOwnershipJsonPath = if ($null -ne $coreWebsiteOwnershipSource -and -not [string]::IsNullOrWhiteSpace([string]$coreWebsiteOwnershipSource.latest_folder)) { Join-Path $Root (Join-Path ([string]$coreWebsiteOwnershipSource.latest_folder) "core-website-ownership.json") } else { "" }
$coreWebsiteOwnershipJson = if (-not [string]::IsNullOrWhiteSpace($coreWebsiteOwnershipJsonPath)) { Read-JsonIfPresent -Path $coreWebsiteOwnershipJsonPath } else { $null }
$coreWebsiteOwnershipReady = $null -ne $coreWebsiteOwnershipJson -and [string]$coreWebsiteOwnershipJson.status -eq "ready"
$backendModularizationSource = @($sources | Where-Object { $_.id -eq "backend_modularization" } | Select-Object -First 1)
$backendModularizationJsonPath = if ($null -ne $backendModularizationSource -and -not [string]::IsNullOrWhiteSpace([string]$backendModularizationSource.latest_folder)) { Join-Path $Root (Join-Path ([string]$backendModularizationSource.latest_folder) "backend-modularization.json") } else { "" }
$backendModularizationJson = if (-not [string]::IsNullOrWhiteSpace($backendModularizationJsonPath)) { Read-JsonIfPresent -Path $backendModularizationJsonPath } else { $null }
$backendModularizationReady = $null -ne $backendModularizationJson -and [string]$backendModularizationJson.status -eq "ready"
$frontendExtractionSource = @($sources | Where-Object { $_.id -eq "frontend_extraction" } | Select-Object -First 1)
$frontendExtractionJsonPath = if ($null -ne $frontendExtractionSource -and -not [string]::IsNullOrWhiteSpace([string]$frontendExtractionSource.latest_folder)) { Join-Path $Root (Join-Path ([string]$frontendExtractionSource.latest_folder) "frontend-extraction.json") } else { "" }
$frontendExtractionJson = if (-not [string]::IsNullOrWhiteSpace($frontendExtractionJsonPath)) { Read-JsonIfPresent -Path $frontendExtractionJsonPath } else { $null }
$frontendExtractionReady = $null -ne $frontendExtractionJson -and [string]$frontendExtractionJson.status -eq "ready"
$desktopShellHardeningSource = @($sources | Where-Object { $_.id -eq "desktop_shell_hardening" } | Select-Object -First 1)
$desktopShellHardeningJsonPath = if ($null -ne $desktopShellHardeningSource -and -not [string]::IsNullOrWhiteSpace([string]$desktopShellHardeningSource.latest_folder)) { Join-Path $Root (Join-Path ([string]$desktopShellHardeningSource.latest_folder) "desktop-shell-hardening.json") } else { "" }
$desktopShellHardeningJson = if (-not [string]::IsNullOrWhiteSpace($desktopShellHardeningJsonPath)) { Read-JsonIfPresent -Path $desktopShellHardeningJsonPath } else { $null }
$desktopShellHardeningReady = $null -ne $desktopShellHardeningJson -and [string]$desktopShellHardeningJson.status -eq "ready"
$editorExtensionModularizationSource = @($sources | Where-Object { $_.id -eq "editor_extension_modularization" } | Select-Object -First 1)
$editorExtensionModularizationJsonPath = if ($null -ne $editorExtensionModularizationSource -and -not [string]::IsNullOrWhiteSpace([string]$editorExtensionModularizationSource.latest_folder)) { Join-Path $Root (Join-Path ([string]$editorExtensionModularizationSource.latest_folder) "editor-extension-modularization.json") } else { "" }
$editorExtensionModularizationJson = if (-not [string]::IsNullOrWhiteSpace($editorExtensionModularizationJsonPath)) { Read-JsonIfPresent -Path $editorExtensionModularizationJsonPath } else { $null }
$editorExtensionModularizationReady = $null -ne $editorExtensionModularizationJson -and [string]$editorExtensionModularizationJson.status -eq "ready"
$providerSecretSafetySource = @($sources | Where-Object { $_.id -eq "provider_secret_safety" } | Select-Object -First 1)
$providerSecretSafetyJsonPath = if ($null -ne $providerSecretSafetySource -and -not [string]::IsNullOrWhiteSpace([string]$providerSecretSafetySource.latest_folder)) { Join-Path $Root (Join-Path ([string]$providerSecretSafetySource.latest_folder) "provider-secret-safety.json") } else { "" }
$providerSecretSafetyJson = if (-not [string]::IsNullOrWhiteSpace($providerSecretSafetyJsonPath)) { Read-JsonIfPresent -Path $providerSecretSafetyJsonPath } else { $null }
$providerSecretSafetyReady = $null -ne $providerSecretSafetyJson -and [string]$providerSecretSafetyJson.status -eq "ready"
$memoryGovernanceSource = @($sources | Where-Object { $_.id -eq "memory_governance" } | Select-Object -First 1)
$memoryGovernanceJsonPath = if ($null -ne $memoryGovernanceSource -and -not [string]::IsNullOrWhiteSpace([string]$memoryGovernanceSource.latest_folder)) { Join-Path $Root (Join-Path ([string]$memoryGovernanceSource.latest_folder) "memory-governance.json") } else { "" }
$memoryGovernanceJson = if (-not [string]::IsNullOrWhiteSpace($memoryGovernanceJsonPath)) { Read-JsonIfPresent -Path $memoryGovernanceJsonPath } else { $null }
$memoryGovernanceReady = $null -ne $memoryGovernanceJson -and [string]$memoryGovernanceJson.status -eq "ready"
$pluginLifecycleSource = @($sources | Where-Object { $_.id -eq "plugin_lifecycle" } | Select-Object -First 1)
$pluginLifecycleJsonPath = if ($null -ne $pluginLifecycleSource -and -not [string]::IsNullOrWhiteSpace([string]$pluginLifecycleSource.latest_folder)) { Join-Path $Root (Join-Path ([string]$pluginLifecycleSource.latest_folder) "plugin-lifecycle.json") } else { "" }
$pluginLifecycleJson = if (-not [string]::IsNullOrWhiteSpace($pluginLifecycleJsonPath)) { Read-JsonIfPresent -Path $pluginLifecycleJsonPath } else { $null }
$pluginLifecycleReady = $null -ne $pluginLifecycleJson -and [string]$pluginLifecycleJson.status -eq "ready"
$observabilityCiSource = @($sources | Where-Object { $_.id -eq "observability_ci" } | Select-Object -First 1)
$observabilityCiJsonPath = if ($null -ne $observabilityCiSource -and -not [string]::IsNullOrWhiteSpace([string]$observabilityCiSource.latest_folder)) { Join-Path $Root (Join-Path ([string]$observabilityCiSource.latest_folder) "observability-ci.json") } else { "" }
$observabilityCiJson = if (-not [string]::IsNullOrWhiteSpace($observabilityCiJsonPath)) { Read-JsonIfPresent -Path $observabilityCiJsonPath } else { $null }
$observabilityCiReady = $null -ne $observabilityCiJson -and [string]$observabilityCiJson.status -eq "ready"
$distributionUpdateSource = @($sources | Where-Object { $_.id -eq "distribution_update" } | Select-Object -First 1)
$distributionUpdateJsonPath = if ($null -ne $distributionUpdateSource -and -not [string]::IsNullOrWhiteSpace([string]$distributionUpdateSource.latest_folder)) { Join-Path $Root (Join-Path ([string]$distributionUpdateSource.latest_folder) "distribution-update.json") } else { "" }
$distributionUpdateJson = if (-not [string]::IsNullOrWhiteSpace($distributionUpdateJsonPath)) { Read-JsonIfPresent -Path $distributionUpdateJsonPath } else { $null }
$distributionUpdateReady = $null -ne $distributionUpdateJson -and [string]$distributionUpdateJson.status -eq "ready"
$alphaReadinessPolishSource = @($sources | Where-Object { $_.id -eq "alpha_readiness_polish" } | Select-Object -First 1)
$alphaReadinessPolishJsonPath = if ($null -ne $alphaReadinessPolishSource -and -not [string]::IsNullOrWhiteSpace([string]$alphaReadinessPolishSource.latest_folder)) { Join-Path $Root (Join-Path ([string]$alphaReadinessPolishSource.latest_folder) "alpha-readiness-polish.json") } else { "" }
$alphaReadinessPolishJson = if (-not [string]::IsNullOrWhiteSpace($alphaReadinessPolishJsonPath)) { Read-JsonIfPresent -Path $alphaReadinessPolishJsonPath } else { $null }
$alphaReadinessPolishReady = $null -ne $alphaReadinessPolishJson -and [string]$alphaReadinessPolishJson.status -eq "ready"
$liveSmokeRcSource = @($sources | Where-Object { $_.id -eq "live_smoke_rc" } | Select-Object -First 1)
$liveSmokeRcJsonPath = if ($null -ne $liveSmokeRcSource -and -not [string]::IsNullOrWhiteSpace([string]$liveSmokeRcSource.latest_folder)) { Join-Path $Root (Join-Path ([string]$liveSmokeRcSource.latest_folder) "live-smoke-rc.json") } else { "" }
$liveSmokeRcJson = if (-not [string]::IsNullOrWhiteSpace($liveSmokeRcJsonPath)) { Read-JsonIfPresent -Path $liveSmokeRcJsonPath } else { $null }
$liveSmokeRcReady = $null -ne $liveSmokeRcJson -and [string]$liveSmokeRcJson.status -eq "ready"
$liveSmokeRcCandidateReady = $liveSmokeRcReady -and [string]$liveSmokeRcJson.release_candidate_status -eq "ready"
$commitScopingGithubHandoffSource = @($sources | Where-Object { $_.id -eq "commit_scoping_github_handoff" } | Select-Object -First 1)
$commitScopingGithubHandoffJsonPath = if ($null -ne $commitScopingGithubHandoffSource -and -not [string]::IsNullOrWhiteSpace([string]$commitScopingGithubHandoffSource.latest_folder)) { Join-Path $Root (Join-Path ([string]$commitScopingGithubHandoffSource.latest_folder) "commit-scoping-github-handoff.json") } else { "" }
$commitScopingGithubHandoffJson = if (-not [string]::IsNullOrWhiteSpace($commitScopingGithubHandoffJsonPath)) { Read-JsonIfPresent -Path $commitScopingGithubHandoffJsonPath } else { $null }
$commitScopingGithubHandoffReady = $null -ne $commitScopingGithubHandoffJson -and [string]$commitScopingGithubHandoffJson.status -eq "ready"
$commitScopingHandoffReady = $commitScopingGithubHandoffReady -and [string]$commitScopingGithubHandoffJson.handoff_status -eq "ready"
$desktopSmokePackageGatesSource = @($sources | Where-Object { $_.id -eq "desktop_smoke_package_gates" } | Select-Object -First 1)
$desktopSmokePackageGatesJsonPath = if ($null -ne $desktopSmokePackageGatesSource -and -not [string]::IsNullOrWhiteSpace([string]$desktopSmokePackageGatesSource.latest_folder)) { Join-Path $Root (Join-Path ([string]$desktopSmokePackageGatesSource.latest_folder) "desktop-smoke-package-gates.json") } else { "" }
$desktopSmokePackageGatesJson = if (-not [string]::IsNullOrWhiteSpace($desktopSmokePackageGatesJsonPath)) { Read-JsonIfPresent -Path $desktopSmokePackageGatesJsonPath } else { $null }
$desktopSmokePackageGatesReady = $null -ne $desktopSmokePackageGatesJson -and [string]$desktopSmokePackageGatesJson.status -eq "ready"
$desktopSmokePackageExecutionReady = $desktopSmokePackageGatesReady -and [string]$desktopSmokePackageGatesJson.execution_status -eq "ready"
$editorSmokeReleasePackageDecisionSource = @($sources | Where-Object { $_.id -eq "editor_smoke_release_package_decision" } | Select-Object -First 1)
$editorSmokeReleasePackageDecisionJsonPath = if ($null -ne $editorSmokeReleasePackageDecisionSource -and -not [string]::IsNullOrWhiteSpace([string]$editorSmokeReleasePackageDecisionSource.latest_folder)) { Join-Path $Root (Join-Path ([string]$editorSmokeReleasePackageDecisionSource.latest_folder) "editor-smoke-release-package-decision.json") } else { "" }
$editorSmokeReleasePackageDecisionJson = if (-not [string]::IsNullOrWhiteSpace($editorSmokeReleasePackageDecisionJsonPath)) { Read-JsonIfPresent -Path $editorSmokeReleasePackageDecisionJsonPath } else { $null }
$editorSmokeReleasePackageDecisionReady = $null -ne $editorSmokeReleasePackageDecisionJson -and [string]$editorSmokeReleasePackageDecisionJson.status -eq "ready"
$editorSmokeReleasePackageExecutionReady = $editorSmokeReleasePackageDecisionReady -and [string]$editorSmokeReleasePackageDecisionJson.execution_status -eq "ready"
if ($null -ne $preflightJson) {
  foreach ($blocker in @($preflightJson.blockers)) {
    $blockerId = [string]$blocker.id
    if (-not [bool](@($blockers) | Where-Object { [string]$_.id -eq $blockerId } | Select-Object -First 1)) {
      $blockers += New-Blocker -Id $blockerId -Detail "Release preflight: $([string]$blocker.detail)"
    }
  }
} else {
  foreach ($id in @("dirty_release_artifacts_need_decision")) {
    $blockers += New-Blocker -Id $id -Detail "Release artifact preflight evidence is missing or unreadable."
  }
}
if (-not $packagedAlphaScenariosReady) {
  $blockers += New-Blocker -Id "alpha_scenario_suite_not_attached" -Detail "No ready Phase 22 packaged alpha scenario evidence is attached."
}
if (-not $crossClientParityReady) {
  $blockers += New-Blocker -Id "cross_client_parity_not_attached" -Detail "No ready Phase 23 cross-client parity evidence is attached."
}
if (-not $releaseNotesLimitationsReady) {
  $blockers += New-Blocker -Id "release_notes_limitations_not_attached" -Detail "No ready Phase 24 release notes limitations evidence is attached."
}
if (-not $coreWebsiteOwnershipReady) {
  $blockers += New-Blocker -Id "core_website_ownership_not_attached" -Detail "No ready Phase 25 Core/Website ownership evidence is attached."
}
if (-not $backendModularizationReady) {
  $blockers += New-Blocker -Id "backend_modularization_not_attached" -Detail "No ready Phase 26 backend modularization evidence is attached."
}
if (-not $frontendExtractionReady) {
  $blockers += New-Blocker -Id "frontend_extraction_not_attached" -Detail "No ready Phase 27 frontend extraction evidence is attached."
}
if (-not $desktopShellHardeningReady) {
  $blockers += New-Blocker -Id "desktop_shell_hardening_not_attached" -Detail "No ready Phase 28 native desktop shell evidence is attached."
}
if (-not $editorExtensionModularizationReady) {
  $blockers += New-Blocker -Id "editor_extension_modularization_not_attached" -Detail "No ready Phase 29 editor extension modularization evidence is attached."
}
if (-not $providerSecretSafetyReady) {
  $blockers += New-Blocker -Id "provider_secret_safety_not_attached" -Detail "No ready Phase 30 provider secret safety evidence is attached."
}
if (-not $memoryGovernanceReady) {
  $blockers += New-Blocker -Id "memory_governance_not_attached" -Detail "No ready Phase 31 memory governance evidence is attached."
}
if (-not $pluginLifecycleReady) {
  $blockers += New-Blocker -Id "plugin_lifecycle_not_attached" -Detail "No ready Phase 32 plugin lifecycle evidence is attached."
}
if (-not $observabilityCiReady) {
  $blockers += New-Blocker -Id "observability_ci_not_attached" -Detail "No ready Phase 33 observability CI evidence is attached."
}
if (-not $distributionUpdateReady) {
  $blockers += New-Blocker -Id "distribution_update_not_attached" -Detail "No ready Phase 34 distribution/update evidence is attached."
}
if (-not $alphaReadinessPolishReady) {
  $blockers += New-Blocker -Id "alpha_readiness_polish_not_attached" -Detail "No ready Phase 35 alpha readiness polish evidence is attached."
}
if (-not $liveSmokeRcReady) {
  $blockers += New-Blocker -Id "live_smoke_rc_not_attached" -Detail "No ready Phase 36 live smoke RC scoping evidence is attached."
}
if (-not $commitScopingGithubHandoffReady) {
  $blockers += New-Blocker -Id "commit_scoping_github_handoff_not_attached" -Detail "No ready Phase 37 commit scoping GitHub handoff evidence is attached."
}
if (-not $desktopSmokePackageGatesReady) {
  $blockers += New-Blocker -Id "desktop_smoke_package_gates_not_attached" -Detail "No ready Phase 38 desktop smoke package gate evidence is attached."
}
if (-not $editorSmokeReleasePackageDecisionReady) {
  $blockers += New-Blocker -Id "editor_smoke_release_package_decision_not_attached" -Detail "No ready Phase 39 editor smoke release package decision evidence is attached."
}

if (@($contract.required_blocker_ids).Count -gt 0) {
  Assert-ObjectIdsInclude -IdPrefix "ledger-runtime-blocker" -Objects $blockers -Required @($contract.required_blocker_ids) -Label "Runtime ledger blockers"
} else {
  Add-LedgerCheck -Id "ledger-runtime-blockers-cleared" -Passed ($blockers.Count -eq 0) -Detail "Runtime ledger blockers must be cleared after Phase 37 commit scoping handoff evidence is attached."
}

$ledgerStatus = if ($blockers.Count -gt 0) { "blocked" } elseif ([string]$releaseSummary.overall_status -eq "passed" -and $liveSmokeRcCandidateReady -and $commitScopingHandoffReady -and $desktopSmokePackageExecutionReady -and $editorSmokeReleasePackageExecutionReady) { "ready" } else { "attention" }
Add-LedgerCheck -Id "ledger-current-status" -Passed ($ledgerStatus -eq [string]$contract.current_required_status) -Detail "Ledger status must remain '$($contract.current_required_status)' for the current evidence state."

$ledger = [pscustomobject]@{
  root = $Root
  status = $ledgerStatus
  generated_at = (Get-Date).ToString("o")
  evidence_dir = $EvidenceDir
  contract = [pscustomobject]@{
    schema_version = [string]$contract.schema_version
    evidence_root = [string]$contract.evidence_root
  }
  sources = $sources
  release_validation = $releaseSummary
  release_package_dry_run = if ($null -ne $packageDryRunEvidence) {
    [pscustomobject]@{
      status = [string]$packageDryRunEvidence.status
      latest_folder = [string]$packageDryRunEvidence.folder
      json_path = [string]$packageDryRunEvidence.json_path
      update_plans_ready = $updatePlansReady
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      latest_folder = ""
      json_path = ""
      update_plans_ready = $false
    }
  }
  final_release_manifest = if ($null -ne $finalReleaseManifestEvidence) {
    [pscustomobject]@{
      status = [string]$finalReleaseManifestEvidence.status
      latest_folder = [string]$finalReleaseManifestEvidence.folder
      json_path = [string]$finalReleaseManifestEvidence.json_path
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      latest_folder = ""
      json_path = ""
    }
  }
  release_artifact_preflight = if ($null -ne $preflightJson) {
    [pscustomobject]@{
      status = [string]$preflightJson.status
      latest_folder = [string]$preflightSource.latest_folder
      blockers = @($preflightJson.blockers | ForEach-Object { [string]$_.id })
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      latest_folder = if ($null -ne $preflightSource) { [string]$preflightSource.latest_folder } else { "" }
      blockers = @("dirty_release_artifacts_need_decision")
    }
  }
  packaged_alpha_scenarios = if ($null -ne $packagedAlphaScenariosJson) {
    [pscustomobject]@{
      status = [string]$packagedAlphaScenariosJson.status
      latest_folder = [string]$packagedAlphaScenariosSource.latest_folder
      scenario_count = @($packagedAlphaScenariosJson.scenarios).Count
      failed_scenario_count = @($packagedAlphaScenariosJson.scenarios | Where-Object { [string]$_.status -ne "passed" }).Count
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      latest_folder = if ($null -ne $packagedAlphaScenariosSource) { [string]$packagedAlphaScenariosSource.latest_folder } else { "" }
      scenario_count = 0
      failed_scenario_count = 0
    }
  }
  cross_client_parity = if ($null -ne $crossClientParityJson) {
    [pscustomobject]@{
      status = [string]$crossClientParityJson.status
      latest_folder = [string]$crossClientParitySource.latest_folder
      client_count = @($crossClientParityJson.clients).Count
      failed_client_count = @($crossClientParityJson.clients | Where-Object { [string]$_.status -ne "passed" }).Count
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      latest_folder = if ($null -ne $crossClientParitySource) { [string]$crossClientParitySource.latest_folder } else { "" }
      client_count = 0
      failed_client_count = 0
    }
  }
  release_notes_limitations = if ($null -ne $releaseNotesLimitationsJson) {
    [pscustomobject]@{
      status = [string]$releaseNotesLimitationsJson.status
      latest_folder = [string]$releaseNotesLimitationsSource.latest_folder
      release_note_count = @($releaseNotesLimitationsJson.release_notes).Count
      limitation_count = @($releaseNotesLimitationsJson.limitations).Count
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      latest_folder = if ($null -ne $releaseNotesLimitationsSource) { [string]$releaseNotesLimitationsSource.latest_folder } else { "" }
      release_note_count = 0
      limitation_count = 0
    }
  }
  core_website_ownership = if ($null -ne $coreWebsiteOwnershipJson) {
    [pscustomobject]@{
      status = [string]$coreWebsiteOwnershipJson.status
      latest_folder = [string]$coreWebsiteOwnershipSource.latest_folder
      domain_count = @($coreWebsiteOwnershipJson.domains).Count
      client_count = @($coreWebsiteOwnershipJson.clients).Count
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      latest_folder = if ($null -ne $coreWebsiteOwnershipSource) { [string]$coreWebsiteOwnershipSource.latest_folder } else { "" }
      domain_count = 0
      client_count = 0
    }
  }
  backend_modularization = if ($null -ne $backendModularizationJson) {
    [pscustomobject]@{
      status = [string]$backendModularizationJson.status
      latest_folder = [string]$backendModularizationSource.latest_folder
      slice = [string]$backendModularizationJson.slice
      command_count = @($backendModularizationJson.commands).Count
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      latest_folder = if ($null -ne $backendModularizationSource) { [string]$backendModularizationSource.latest_folder } else { "" }
      slice = ""
      command_count = 0
    }
  }
  frontend_extraction = if ($null -ne $frontendExtractionJson) {
    [pscustomobject]@{
      status = [string]$frontendExtractionJson.status
      latest_folder = [string]$frontendExtractionSource.latest_folder
      slice = [string]$frontendExtractionJson.slice
      command_count = @($frontendExtractionJson.commands).Count
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      latest_folder = if ($null -ne $frontendExtractionSource) { [string]$frontendExtractionSource.latest_folder } else { "" }
      slice = ""
      command_count = 0
    }
  }
  desktop_shell_hardening = if ($null -ne $desktopShellHardeningJson) {
    [pscustomobject]@{
      status = [string]$desktopShellHardeningJson.status
      latest_folder = [string]$desktopShellHardeningSource.latest_folder
      slice = [string]$desktopShellHardeningJson.slice
      command_count = @($desktopShellHardeningJson.commands).Count
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      latest_folder = if ($null -ne $desktopShellHardeningSource) { [string]$desktopShellHardeningSource.latest_folder } else { "" }
      slice = ""
      command_count = 0
    }
  }
  editor_extension_modularization = if ($null -ne $editorExtensionModularizationJson) {
    [pscustomobject]@{
      status = [string]$editorExtensionModularizationJson.status
      latest_folder = [string]$editorExtensionModularizationSource.latest_folder
      slice = [string]$editorExtensionModularizationJson.slice
      command_count = @($editorExtensionModularizationJson.commands).Count
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      latest_folder = if ($null -ne $editorExtensionModularizationSource) { [string]$editorExtensionModularizationSource.latest_folder } else { "" }
      slice = ""
      command_count = 0
    }
  }
  provider_secret_safety = if ($null -ne $providerSecretSafetyJson) {
    [pscustomobject]@{
      status = [string]$providerSecretSafetyJson.status
      latest_folder = [string]$providerSecretSafetySource.latest_folder
      slice = [string]$providerSecretSafetyJson.slice
      command_count = @($providerSecretSafetyJson.commands).Count
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      latest_folder = if ($null -ne $providerSecretSafetySource) { [string]$providerSecretSafetySource.latest_folder } else { "" }
      slice = ""
      command_count = 0
    }
  }
  memory_governance = if ($null -ne $memoryGovernanceJson) {
    [pscustomobject]@{
      status = [string]$memoryGovernanceJson.status
      latest_folder = [string]$memoryGovernanceSource.latest_folder
      slice = [string]$memoryGovernanceJson.slice
      command_count = @($memoryGovernanceJson.commands).Count
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      latest_folder = if ($null -ne $memoryGovernanceSource) { [string]$memoryGovernanceSource.latest_folder } else { "" }
      slice = ""
      command_count = 0
    }
  }
  plugin_lifecycle = if ($null -ne $pluginLifecycleJson) {
    [pscustomobject]@{
      status = [string]$pluginLifecycleJson.status
      latest_folder = [string]$pluginLifecycleSource.latest_folder
      slice = [string]$pluginLifecycleJson.slice
      command_count = @($pluginLifecycleJson.commands).Count
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      latest_folder = if ($null -ne $pluginLifecycleSource) { [string]$pluginLifecycleSource.latest_folder } else { "" }
      slice = ""
      command_count = 0
    }
  }
  observability_ci = if ($null -ne $observabilityCiJson) {
    [pscustomobject]@{
      status = [string]$observabilityCiJson.status
      latest_folder = [string]$observabilityCiSource.latest_folder
      slice = [string]$observabilityCiJson.slice
      workflow = [string]$observabilityCiJson.workflow
      command_count = @($observabilityCiJson.commands).Count
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      latest_folder = if ($null -ne $observabilityCiSource) { [string]$observabilityCiSource.latest_folder } else { "" }
      slice = ""
      workflow = ""
      command_count = 0
    }
  }
  distribution_update = if ($null -ne $distributionUpdateJson) {
    [pscustomobject]@{
      status = [string]$distributionUpdateJson.status
      latest_folder = [string]$distributionUpdateSource.latest_folder
      slice = [string]$distributionUpdateJson.slice
      distribution_mode = [string]$distributionUpdateJson.distribution_mode
      installer_status = [string]$distributionUpdateJson.installer_status
      signing_status = [string]$distributionUpdateJson.signing_status
      artifact_count = @($distributionUpdateJson.artifacts).Count
      command_count = @($distributionUpdateJson.commands).Count
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      latest_folder = if ($null -ne $distributionUpdateSource) { [string]$distributionUpdateSource.latest_folder } else { "" }
      slice = ""
      distribution_mode = ""
      installer_status = ""
      signing_status = ""
      artifact_count = 0
      command_count = 0
    }
  }
  alpha_readiness_polish = if ($null -ne $alphaReadinessPolishJson) {
    [pscustomobject]@{
      status = [string]$alphaReadinessPolishJson.status
      latest_folder = [string]$alphaReadinessPolishSource.latest_folder
      slice = [string]$alphaReadinessPolishJson.slice
      feature_tier_count = @($alphaReadinessPolishJson.feature_tiers).Count
      default_path_count = @($alphaReadinessPolishJson.default_alpha_path).Count
      command_count = @($alphaReadinessPolishJson.commands).Count
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      latest_folder = if ($null -ne $alphaReadinessPolishSource) { [string]$alphaReadinessPolishSource.latest_folder } else { "" }
      slice = ""
      feature_tier_count = 0
      default_path_count = 0
      command_count = 0
    }
  }
  live_smoke_rc = if ($null -ne $liveSmokeRcJson) {
    [pscustomobject]@{
      status = [string]$liveSmokeRcJson.status
      release_candidate_status = [string]$liveSmokeRcJson.release_candidate_status
      latest_folder = [string]$liveSmokeRcSource.latest_folder
      slice = [string]$liveSmokeRcJson.slice
      gate_count = @($liveSmokeRcJson.live_gate_closure).Count
      open_gate_count = @($liveSmokeRcJson.live_gate_closure | Where-Object { [string]$_.closure_status -ne "closed" }).Count
      optional_attempt_count = @($liveSmokeRcJson.optional_attempts).Count
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      release_candidate_status = "missing"
      latest_folder = if ($null -ne $liveSmokeRcSource) { [string]$liveSmokeRcSource.latest_folder } else { "" }
      slice = ""
      gate_count = 0
      open_gate_count = 0
      optional_attempt_count = 0
    }
  }
  commit_scoping_github_handoff = if ($null -ne $commitScopingGithubHandoffJson) {
    [pscustomobject]@{
      status = [string]$commitScopingGithubHandoffJson.status
      handoff_status = [string]$commitScopingGithubHandoffJson.handoff_status
      latest_folder = [string]$commitScopingGithubHandoffSource.latest_folder
      slice = [string]$commitScopingGithubHandoffJson.slice
      total_changed_paths = [int]$commitScopingGithubHandoffJson.worktree.total_changed_paths
      commit_group_count = @($commitScopingGithubHandoffJson.commit_groups).Count
      publish_blocker_count = @($commitScopingGithubHandoffJson.publish_blockers).Count
      detected_remote = [string]$commitScopingGithubHandoffJson.github_target.detected_remote
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      handoff_status = "missing"
      latest_folder = if ($null -ne $commitScopingGithubHandoffSource) { [string]$commitScopingGithubHandoffSource.latest_folder } else { "" }
      slice = ""
      total_changed_paths = 0
      commit_group_count = 0
      publish_blocker_count = 0
      detected_remote = ""
    }
  }
  desktop_smoke_package_gates = if ($null -ne $desktopSmokePackageGatesJson) {
    [pscustomobject]@{
      status = [string]$desktopSmokePackageGatesJson.status
      execution_status = [string]$desktopSmokePackageGatesJson.execution_status
      latest_folder = [string]$desktopSmokePackageGatesSource.latest_folder
      slice = [string]$desktopSmokePackageGatesJson.slice
      target_gate_count = @($desktopSmokePackageGatesJson.target_gate_observations).Count
      gate_attempt_count = @($desktopSmokePackageGatesJson.gate_attempts).Count
      owner_next_action_count = @($desktopSmokePackageGatesJson.owner_next_actions).Count
      phase36_refresh_required = [bool]$desktopSmokePackageGatesJson.phase36_refresh_required
      phase37_refresh_required = [bool]$desktopSmokePackageGatesJson.phase37_refresh_required
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      execution_status = "missing"
      latest_folder = if ($null -ne $desktopSmokePackageGatesSource) { [string]$desktopSmokePackageGatesSource.latest_folder } else { "" }
      slice = ""
      target_gate_count = 0
      gate_attempt_count = 0
      owner_next_action_count = 0
      phase36_refresh_required = $false
      phase37_refresh_required = $false
    }
  }
  editor_smoke_release_package_decision = if ($null -ne $editorSmokeReleasePackageDecisionJson) {
    [pscustomobject]@{
      status = [string]$editorSmokeReleasePackageDecisionJson.status
      execution_status = [string]$editorSmokeReleasePackageDecisionJson.execution_status
      latest_folder = [string]$editorSmokeReleasePackageDecisionSource.latest_folder
      slice = [string]$editorSmokeReleasePackageDecisionJson.slice
      target_gate_count = @($editorSmokeReleasePackageDecisionJson.target_gate_observations).Count
      gate_attempt_count = @($editorSmokeReleasePackageDecisionJson.gate_attempts).Count
      owner_next_action_count = @($editorSmokeReleasePackageDecisionJson.owner_next_actions).Count
      phase36_refresh_required = [bool]$editorSmokeReleasePackageDecisionJson.phase36_refresh_required
      phase37_refresh_required = [bool]$editorSmokeReleasePackageDecisionJson.phase37_refresh_required
      phase38_refresh_required = [bool]$editorSmokeReleasePackageDecisionJson.phase38_refresh_required
    }
  } else {
    [pscustomobject]@{
      status = "missing"
      execution_status = "missing"
      latest_folder = if ($null -ne $editorSmokeReleasePackageDecisionSource) { [string]$editorSmokeReleasePackageDecisionSource.latest_folder } else { "" }
      slice = ""
      target_gate_count = 0
      gate_attempt_count = 0
      owner_next_action_count = 0
      phase36_refresh_required = $false
      phase37_refresh_required = $false
      phase38_refresh_required = $false
    }
  }
  release_manifest = [pscustomobject]@{
    path = "release\version-manifest.json"
    present = $releaseManifestPresent
  }
  blockers = $blockers
  checks = $script:Checks
}

New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$summaryPath = Join-Path $EvidenceDir "evidence-ledger.json"
$markdownPath = Join-Path $EvidenceDir "evidence-ledger-summary.md"
$ledger | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 16 Evidence Ledger"
$markdown += ""
$markdown += "- Status: $($ledger.status)"
$markdown += "- Generated at: $($ledger.generated_at)"
$markdown += "- Evidence dir: $EvidenceDir"
$markdown += "- Release manifest present: $releaseManifestPresent"
$markdown += "- Latest release evidence: $($releaseSource.latest_folder)"
$markdown += "- Latest release preflight: $($preflightSource.latest_folder)"
$markdown += "- Latest package dry-run: $(if ($null -ne $packageDryRunEvidence) { $packageDryRunEvidence.folder } else { '' })"
$markdown += "- Latest final release manifest: $(if ($null -ne $finalReleaseManifestEvidence) { $finalReleaseManifestEvidence.folder } else { '' })"
$markdown += "- Latest packaged alpha scenarios: $(if ($null -ne $packagedAlphaScenariosSource) { $packagedAlphaScenariosSource.latest_folder } else { '' })"
$markdown += "- Latest cross-client parity: $(if ($null -ne $crossClientParitySource) { $crossClientParitySource.latest_folder } else { '' })"
$markdown += "- Latest release notes limitations: $(if ($null -ne $releaseNotesLimitationsSource) { $releaseNotesLimitationsSource.latest_folder } else { '' })"
$markdown += "- Latest Core Website ownership: $(if ($null -ne $coreWebsiteOwnershipSource) { $coreWebsiteOwnershipSource.latest_folder } else { '' })"
$markdown += "- Latest backend modularization: $(if ($null -ne $backendModularizationSource) { $backendModularizationSource.latest_folder } else { '' })"
$markdown += "- Latest frontend extraction: $(if ($null -ne $frontendExtractionSource) { $frontendExtractionSource.latest_folder } else { '' })"
$markdown += "- Latest native desktop shell: $(if ($null -ne $desktopShellHardeningSource) { $desktopShellHardeningSource.latest_folder } else { '' })"
$markdown += "- Latest editor extension modularization: $(if ($null -ne $editorExtensionModularizationSource) { $editorExtensionModularizationSource.latest_folder } else { '' })"
$markdown += "- Latest provider secret safety: $(if ($null -ne $providerSecretSafetySource) { $providerSecretSafetySource.latest_folder } else { '' })"
$markdown += "- Latest memory governance: $(if ($null -ne $memoryGovernanceSource) { $memoryGovernanceSource.latest_folder } else { '' })"
$markdown += "- Latest plugin lifecycle: $(if ($null -ne $pluginLifecycleSource) { $pluginLifecycleSource.latest_folder } else { '' })"
$markdown += "- Latest observability CI: $(if ($null -ne $observabilityCiSource) { $observabilityCiSource.latest_folder } else { '' })"
$markdown += "- Latest distribution/update: $(if ($null -ne $distributionUpdateSource) { $distributionUpdateSource.latest_folder } else { '' })"
$markdown += "- Latest alpha readiness polish: $(if ($null -ne $alphaReadinessPolishSource) { $alphaReadinessPolishSource.latest_folder } else { '' })"
$markdown += "- Latest live smoke RC scoping: $(if ($null -ne $liveSmokeRcSource) { $liveSmokeRcSource.latest_folder } else { '' })"
$markdown += "- Live smoke RC status: $(if ($null -ne $liveSmokeRcJson) { [string]$liveSmokeRcJson.release_candidate_status } else { 'missing' })"
$markdown += "- Latest commit scoping GitHub handoff: $(if ($null -ne $commitScopingGithubHandoffSource) { $commitScopingGithubHandoffSource.latest_folder } else { '' })"
$markdown += "- Commit scoping handoff status: $(if ($null -ne $commitScopingGithubHandoffJson) { [string]$commitScopingGithubHandoffJson.handoff_status } else { 'missing' })"
$markdown += "- Latest desktop smoke package gates: $(if ($null -ne $desktopSmokePackageGatesSource) { $desktopSmokePackageGatesSource.latest_folder } else { '' })"
$markdown += "- Desktop smoke package execution status: $(if ($null -ne $desktopSmokePackageGatesJson) { [string]$desktopSmokePackageGatesJson.execution_status } else { 'missing' })"
$markdown += "- Latest editor smoke release package decision: $(if ($null -ne $editorSmokeReleasePackageDecisionSource) { $editorSmokeReleasePackageDecisionSource.latest_folder } else { '' })"
$markdown += "- Editor smoke release package execution status: $(if ($null -ne $editorSmokeReleasePackageDecisionJson) { [string]$editorSmokeReleasePackageDecisionJson.execution_status } else { 'missing' })"
$markdown += "- Release validation status: $($releaseSummary.overall_status)"
$markdown += "- Blockers: $($blockers.Count)"
$markdown += ""
$markdown += "## Sources"
$markdown += ""
$markdown += "| Source | Status | Latest Folder | Missing Files |"
$markdown += "| --- | --- | --- | --- |"
foreach ($source in $sources) {
  $missingText = if (@($source.missing_files).Count) { @($source.missing_files) -join ", " } else { "" }
  $markdown += "| $($source.id) | $($source.status) | $($source.latest_folder) | $missingText |"
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
$markdown += "## Checks"
$markdown += ""
$markdown += "| Check | Status | Detail |"
$markdown += "| --- | --- | --- |"
foreach ($check in $script:Checks) {
  $status = if ($check.passed) { "passed" } else { "failed" }
  $detail = ([string]$check.detail).Replace("|", "\|")
  $markdown += "| $($check.id) | $status | $detail |"
}
$markdown | Set-Content -LiteralPath $markdownPath -Encoding UTF8

$ledger | ConvertTo-Json -Depth 10

if ($script:Failures.Count -gt 0) {
  throw "Evidence ledger contract validation failed:`n - $($script:Failures -join "`n - ")"
}
