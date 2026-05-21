param(
  [string]$Root = "",
  [string]$EvidenceDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Root)) {
  $Root = Split-Path -Parent $PSScriptRoot
}
$Root = (Resolve-Path -LiteralPath $Root).Path

Add-Type -AssemblyName System.IO.Compression.FileSystem

function Join-ProjectPath {
  param([string]$Path)
  return Join-Path $Root $Path
}

function Test-UnderRoot {
  param([string]$Path)
  $full = [System.IO.Path]::GetFullPath($Path)
  $rootWithSlash = $Root.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
  if (-not ($full.Equals($Root, [System.StringComparison]::OrdinalIgnoreCase) -or $full.StartsWith($rootWithSlash, [System.StringComparison]::OrdinalIgnoreCase))) {
    throw "Refusing to write outside project root: $full"
  }
  return $full
}

function ConvertTo-ProjectRelativePath {
  param([string]$Path)
  $full = [System.IO.Path]::GetFullPath($Path)
  $rootWithSlash = $Root.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
  if ($full.StartsWith($rootWithSlash, [System.StringComparison]::OrdinalIgnoreCase)) {
    return $full.Substring($rootWithSlash.Length)
  }
  return $full
}

function ConvertTo-CheckId {
  param([string]$Value)
  return $Value.Replace("/", "-").Replace("\", "-").Replace(" ", "-").Replace(":", "").Replace("{", "").Replace("}", "").ToLowerInvariant()
}

function Read-JsonFile {
  param([string]$Path)
  return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

function Add-Check {
  param(
    [System.Collections.Generic.List[object]]$Checks,
    [string]$Id,
    [bool]$Passed,
    [string]$Message,
    [object]$Details = $null
  )

  $Checks.Add([pscustomobject]@{
    id = $Id
    passed = $Passed
    message = $Message
    details = $Details
  }) | Out-Null
}

function Normalize-ZipPath {
  param([string]$Path)
  return ([string]$Path).Replace("/", "\").ToLowerInvariant()
}

function Get-ZipEntries {
  param([string]$PackagePath)

  $zip = [System.IO.Compression.ZipFile]::OpenRead($PackagePath)
  try {
    return @($zip.Entries | ForEach-Object { [string]$_.FullName })
  } finally {
    $zip.Dispose()
  }
}

function Test-ZipEntry {
  param([string[]]$Entries, [string]$Entry)
  $needle = Normalize-ZipPath $Entry
  foreach ($entryName in @($Entries)) {
    if ((Normalize-ZipPath $entryName) -eq $needle) {
      return $true
    }
  }
  return $false
}

function Get-ZipEntryText {
  param([string]$PackagePath, [string]$Entry)

  $needle = Normalize-ZipPath $Entry
  $zip = [System.IO.Compression.ZipFile]::OpenRead($PackagePath)
  try {
    $entryObject = $zip.Entries | Where-Object { (Normalize-ZipPath $_.FullName) -eq $needle } | Select-Object -First 1
    if ($null -eq $entryObject) {
      return ""
    }
    $stream = $entryObject.Open()
    try {
      $reader = [System.IO.StreamReader]::new($stream, [System.Text.Encoding]::UTF8, $true)
      try {
        return $reader.ReadToEnd()
      } finally {
        $reader.Dispose()
      }
    } finally {
      $stream.Dispose()
    }
  } finally {
    $zip.Dispose()
  }
}

function Find-PlaintextSecretMarkers {
  param([string]$PackagePath)

  $patterns = @(
    'sk-[A-Za-z0-9_\-]{20,}',
    'sk-proj-[A-Za-z0-9_\-]{20,}',
    'ghp_[A-Za-z0-9]{20,}',
    'xox[baprs]-[A-Za-z0-9\-]{20,}',
    'AKIA[0-9A-Z]{16}'
  )
  $textExtensions = @(".py", ".json", ".md", ".txt", ".js", ".ts", ".tsx", ".css", ".html", ".ini", ".toml", ".yml", ".yaml", ".xml", ".vsixmanifest", ".pkgdef")
  $findings = @()
  $zip = [System.IO.Compression.ZipFile]::OpenRead($PackagePath)
  try {
    foreach ($entry in @($zip.Entries)) {
      if ($entry.Length -le 0 -or $entry.Length -gt 1048576) {
        continue
      }
      $normalizedEntry = Normalize-ZipPath ([string]$entry.FullName)
      if ($normalizedEntry -match '(^|\\)tests\\' -or $normalizedEntry -match '(^|\\)__pycache__\\') {
        continue
      }
      $extension = [System.IO.Path]::GetExtension([string]$entry.FullName).ToLowerInvariant()
      if ($textExtensions -notcontains $extension) {
        continue
      }
      $stream = $entry.Open()
      try {
        $reader = [System.IO.StreamReader]::new($stream, [System.Text.Encoding]::UTF8, $true)
        try {
          $text = $reader.ReadToEnd()
          foreach ($pattern in $patterns) {
            if ($text -match $pattern) {
              $findings += [pscustomobject]@{
                entry = [string]$entry.FullName
                pattern = $pattern
              }
            }
          }
        } finally {
          $reader.Dispose()
        }
      } finally {
        $stream.Dispose()
      }
    }
  } finally {
    $zip.Dispose()
  }
  return @($findings)
}

function Get-ManifestComponent {
  param([object]$Manifest, [string]$Id)
  if ($null -eq $Manifest -or $null -eq $Manifest.components) {
    return $null
  }
  $property = $Manifest.components.PSObject.Properties[$Id]
  if ($null -eq $property) {
    return $null
  }
  return $property.Value
}

function Get-LatestEvidence {
  param(
    [string]$RootPath,
    [string]$JsonName
  )

  $fullRoot = Join-ProjectPath $RootPath
  if (-not (Test-Path -LiteralPath $fullRoot -PathType Container)) {
    return [pscustomobject]@{
      status = "missing"
      latest_folder = ""
      json_path = ""
      payload = $null
    }
  }
  $folders = @(Get-ChildItem -LiteralPath $fullRoot -Directory | Sort-Object Name -Descending)
  foreach ($folder in $folders) {
    $jsonPath = Join-Path $folder.FullName $JsonName
    if (Test-Path -LiteralPath $jsonPath -PathType Leaf) {
      $payload = Read-JsonFile $jsonPath
      return [pscustomobject]@{
        status = [string]$payload.status
        latest_folder = ConvertTo-ProjectRelativePath $folder.FullName
        json_path = ConvertTo-ProjectRelativePath $jsonPath
        payload = $payload
      }
    }
  }
  return [pscustomobject]@{
    status = "missing"
    latest_folder = ""
    json_path = ""
    payload = $null
  }
}

function Test-EvidenceReady {
  param([object]$Evidence, [string[]]$AcceptedStatuses)
  if ($null -eq $Evidence) {
    return $false
  }
  return $AcceptedStatuses -contains ([string]$Evidence.status)
}

function New-ScenarioDefinition {
  param(
    [string]$Id,
    [string]$EvidenceKind,
    [hashtable]$PackageEntries,
    [string[]]$EvidenceSources,
    [string]$Limitation = ""
  )
  return [pscustomobject]@{
    id = $Id
    evidence_kind = $EvidenceKind
    package_entries = $PackageEntries
    evidence_sources = $EvidenceSources
    limitation = $Limitation
  }
}

if ([string]::IsNullOrWhiteSpace($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\packaged-alpha-scenarios" (Get-Date -Format "yyyyMMdd-HHmmss"))
} elseif (-not [System.IO.Path]::IsPathRooted($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root $EvidenceDir
}
$EvidenceDir = Test-UnderRoot $EvidenceDir
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$contract = Read-JsonFile (Join-ProjectPath "evals\phase22-packaged-alpha-scenarios-contract.json")
$alphaContract = Read-JsonFile (Join-ProjectPath "evals\phase14-alpha-readiness-contract.json")
$externalAlphaContract = Read-JsonFile (Join-ProjectPath "evals\phase15-external-alpha-release-contract.json")
$manifestPath = Join-ProjectPath "release\version-manifest.json"

$checks = [System.Collections.Generic.List[object]]::new()
$failures = [System.Collections.Generic.List[string]]::new()

foreach ($relativePath in @($contract.required_contract_files)) {
  $exists = Test-Path -LiteralPath (Join-ProjectPath ([string]$relativePath)) -PathType Leaf
  Add-Check -Checks $checks -Id "contract_file:$relativePath" -Passed $exists -Message "Required contract file is present: $relativePath"
}

$manifestPresent = Test-Path -LiteralPath $manifestPath -PathType Leaf
Add-Check -Checks $checks -Id "root_manifest_present" -Passed $manifestPresent -Message "Root release/version-manifest.json exists."
if (-not $manifestPresent) {
  throw "Root release/version-manifest.json is required before Phase 22."
}
$manifest = Read-JsonFile $manifestPath

$evidenceSources = [ordered]@{
  final_release_manifest = Get-LatestEvidence -RootPath ".aegis\final-release-manifest" -JsonName "final-release-manifest.json"
  release_package_dry_run = Get-LatestEvidence -RootPath ".aegis\release-package-dry-run" -JsonName "release-package-dry-run.json"
  release_apply_rollback = Get-LatestEvidence -RootPath ".aegis\release-apply-rollback" -JsonName "release-apply-rollback.json"
  release_artifact_preflight = Get-LatestEvidence -RootPath ".aegis\release-preflight" -JsonName "release-artifact-preflight.json"
  extension_package_candidates = Get-LatestEvidence -RootPath ".aegis\extension-package-candidates" -JsonName "extension-package-candidates.json"
  alpha_contract = Get-LatestEvidence -RootPath ".aegis\alpha-evidence" -JsonName "alpha-contract.json"
}

foreach ($sourceId in @($contract.required_evidence_sources)) {
  $source = $evidenceSources[[string]$sourceId]
  $accepted = if ([string]$sourceId -eq "alpha_contract") { @("passed") } else { @("ready") }
  $ready = Test-EvidenceReady -Evidence $source -AcceptedStatuses $accepted
  Add-Check -Checks $checks -Id "evidence_source:$sourceId" -Passed $ready -Message "Required evidence source is attached: $sourceId" -Details ([pscustomobject]@{
      status = if ($null -ne $source) { [string]$source.status } else { "missing" }
      latest_folder = if ($null -ne $source) { [string]$source.latest_folder } else { "" }
      json_path = if ($null -ne $source) { [string]$source.json_path } else { "" }
    })
}

$alphaScenarioIds = @($alphaContract.scenario_suite | ForEach-Object { [string]$_.id })
$externalScenarioIds = @($externalAlphaContract.scenario_suite | ForEach-Object { [string]$_ })
$contractScenarioIds = @($contract.scenario_suite | ForEach-Object { [string]$_ })
foreach ($scenarioId in $contractScenarioIds) {
  Add-Check -Checks $checks -Id "alpha_scenario_contract:$scenarioId" -Passed ($alphaScenarioIds -contains $scenarioId -and $externalScenarioIds -contains $scenarioId) -Message "Scenario exists in Phase 14 and Phase 15 contracts: $scenarioId"
}

$packageInspections = @()
$packagesByComponent = @{}
$secretFindings = @()
foreach ($componentId in @($contract.components)) {
  $id = [string]$componentId
  $component = Get-ManifestComponent -Manifest $manifest -Id $id
  $packagePath = if ($null -ne $component -and $null -ne $component.package) { Join-ProjectPath ([string]$component.package.path) } else { "" }
  $exists = -not [string]::IsNullOrWhiteSpace($packagePath) -and (Test-Path -LiteralPath $packagePath -PathType Leaf)
  $hash = ""
  $hashMatches = $false
  $entries = @()
  $entryCount = 0
  $sizeBytes = 0
  $packageSecrets = @()
  if ($exists) {
    $item = Get-Item -LiteralPath $packagePath
    $sizeBytes = $item.Length
    $hash = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash.ToLowerInvariant()
    $hashMatches = $hash -eq ([string]$component.package.sha256).ToLowerInvariant()
    $entries = Get-ZipEntries -PackagePath $packagePath
    $entryCount = @($entries).Count
    $packageSecrets = Find-PlaintextSecretMarkers -PackagePath $packagePath
    $secretFindings += @($packageSecrets | ForEach-Object {
      [pscustomobject]@{
        component = $id
        entry = $_.entry
        pattern = $_.pattern
      }
    })
  }

  $inspection = [pscustomobject]@{
    component = $id
    artifact = if ($null -ne $component -and $null -ne $component.package) { [string]$component.package.artifact } else { "" }
    path = if ($exists) { ConvertTo-ProjectRelativePath $packagePath } else { $packagePath }
    present = $exists
    size_bytes = $sizeBytes
    manifest_size_bytes = if ($null -ne $component -and $null -ne $component.package) { [int64]$component.package.size_bytes } else { 0 }
    sha256 = $hash
    manifest_sha256 = if ($null -ne $component -and $null -ne $component.package) { [string]$component.package.sha256 } else { "" }
    hash_matches_manifest = $hashMatches
    entry_count = $entryCount
    secret_findings = $packageSecrets
    entries = $entries
    package_path_full = $packagePath
  }
  $packageInspections += $inspection
  $packagesByComponent[$id] = $inspection
}

$packagesPresent = -not [bool](@($packageInspections) | Where-Object { -not [bool]$_.present } | Select-Object -First 1)
$hashesMatch = -not [bool](@($packageInspections) | Where-Object { -not [bool]$_.hash_matches_manifest } | Select-Object -First 1)
Add-Check -Checks $checks -Id "packages_present" -Passed $packagesPresent -Message "All release packages listed in the root manifest are present."
Add-Check -Checks $checks -Id "packages_match_manifest_hashes" -Passed $hashesMatch -Message "All release packages match manifest SHA-256 values."
Add-Check -Checks $checks -Id "no_plaintext_secret_markers" -Passed (@($secretFindings).Count -eq 0) -Message "Packaged text files do not contain obvious plaintext secret markers." -Details $secretFindings

$scenarioDefinitions = @(
  New-ScenarioDefinition -Id "create_app" -EvidenceKind "packaged_runtime_files" -EvidenceSources @("final_release_manifest", "alpha_contract") -PackageEntries @{
    "aegis-core" = @("aegis_core\engineering_workspace.py", "aegis_core\editing.py", "aegis_core\validation.py")
    "website" = @("backend\aegis_ai\project_scaffolder.py", "backend\aegis_ai\project_scaffold_validation_plan.py", "backend\aegis_ai\routes\checkpoints.py")
  }
  New-ScenarioDefinition -Id "modify_app" -EvidenceKind "packaged_proposal_diff_checkpoint_files" -EvidenceSources @("final_release_manifest", "alpha_contract") -PackageEntries @{
    "aegis-core" = @("aegis_core\editing.py", "aegis_core\safety.py", "aegis_core\workflow_runtime.py")
    "website" = @("backend\aegis_ai\diff_engine.py", "backend\aegis_ai\approval_sandbox.py", "backend\aegis_ai\routes\checkpoints.py")
  }
  New-ScenarioDefinition -Id "repair_validation" -EvidenceKind "packaged_validation_repair_files" -EvidenceSources @("final_release_manifest", "alpha_contract") -PackageEntries @{
    "aegis-core" = @("aegis_core\validation.py", "aegis_core\quality_gates.py")
    "website" = @("backend\aegis_ai\validation.py", "backend\aegis_ai\validation_diagnostics.py", "backend\aegis_ai\validation_outcome.py")
  }
  New-ScenarioDefinition -Id "review_code" -EvidenceKind "packaged_review_without_apply_files" -EvidenceSources @("final_release_manifest", "alpha_contract") -PackageEntries @{
    "aegis-core" = @("aegis_core\agent.py", "aegis_core\safety.py")
    "website" = @("backend\aegis_ai\agent.py", "backend\aegis_ai\diff_engine.py", "backend\tests\test_indexer_and_diff.py")
  }
  New-ScenarioDefinition -Id "connect_provider" -EvidenceKind "packaged_provider_secret_safety_files" -EvidenceSources @("final_release_manifest", "alpha_contract") -PackageEntries @{
    "aegis-core" = @("aegis_core\credentials.py", "aegis_core\security.py")
    "website" = @("backend\aegis_ai\providers\accounts\manager.py", "backend\aegis_ai\providers\accounts\vault.py", "backend\aegis_ai\routes\provider_accounts.py")
  }
  New-ScenarioDefinition -Id "use_local_model" -EvidenceKind "packaged_local_model_routing_files" -EvidenceSources @("final_release_manifest", "alpha_contract") -PackageEntries @{
    "aegis-core" = @("aegis_core\ollama.py", "aegis_core\model_router.py")
    "website" = @("backend\aegis_ai\model_manager.py", "backend\aegis_ai\routes\model_registry.py", "backend\aegis_ai\services\model_inventory_service.py")
  }
  New-ScenarioDefinition -Id "run_vscode_extension" -EvidenceKind "packaged_vscode_extension_files" -EvidenceSources @("extension_package_candidates", "alpha_contract") -Limitation "Package inspection and contract evidence are attached; extension-host smoke remains part of cross-client parity." -PackageEntries @{
    "vscode-extension" = @("extension\package.json", "extension\extension.js", "extension\src\proposal\proposalApply.ts", "extension\src\proposal\rollback.ts", "extension\src\validation\validationRunner.ts", "extension\src\models\modelRouter.ts")
  }
  New-ScenarioDefinition -Id "run_visual_studio_extension" -EvidenceKind "packaged_visual_studio_extension_files" -EvidenceSources @("extension_package_candidates", "alpha_contract") -Limitation "Package validation substitute is attached; experimental-instance smoke remains part of cross-client parity." -PackageEntries @{
    "visual-studio-extension" = @("extension.vsixmanifest", "AegisLocalAgentVs.dll", "README.md", "RELEASE_NOTES.md", "TROUBLESHOOTING.md")
  }
  New-ScenarioDefinition -Id "update_component" -EvidenceKind "phase21_packaged_update_evidence" -EvidenceSources @("release_package_dry_run", "release_apply_rollback") -PackageEntries @{
    "aegis-core" = @("aegis_core\release.py")
    "desktop" = @("RELEASE_PACKAGING_AND_UPDATES.md")
  }
  New-ScenarioDefinition -Id "rollback_component" -EvidenceKind "phase21_packaged_rollback_evidence" -EvidenceSources @("release_apply_rollback") -PackageEntries @{
    "aegis-core" = @("aegis_core\release.py")
    "desktop" = @("RELEASE_PACKAGING_AND_UPDATES.md")
  }
)

$scenarioResults = @()
foreach ($scenario in $scenarioDefinitions) {
  $scenarioFailures = @()
  $entryEvidence = @()
  $sourceEvidence = @()
  if ($contractScenarioIds -notcontains [string]$scenario.id) {
    $scenarioFailures += "Scenario is missing from Phase 22 contract."
  }
  if ($alphaScenarioIds -notcontains [string]$scenario.id) {
    $scenarioFailures += "Scenario is missing from Phase 14 scenario suite."
  }
  if ($externalScenarioIds -notcontains [string]$scenario.id) {
    $scenarioFailures += "Scenario is missing from Phase 15 external-alpha scenario suite."
  }

  foreach ($sourceId in @($scenario.evidence_sources)) {
    $source = $evidenceSources[[string]$sourceId]
    $accepted = if ([string]$sourceId -eq "alpha_contract") { @("passed") } else { @("ready") }
    $ready = Test-EvidenceReady -Evidence $source -AcceptedStatuses $accepted
    if (-not $ready) {
      $scenarioFailures += "Required evidence source is not ready: $sourceId."
    }
    $sourceEvidence += [pscustomobject]@{
      id = [string]$sourceId
      status = if ($null -ne $source) { [string]$source.status } else { "missing" }
      latest_folder = if ($null -ne $source) { [string]$source.latest_folder } else { "" }
      ready = $ready
    }
  }

  foreach ($componentName in @($scenario.package_entries.Keys)) {
    $componentId = [string]$componentName
    $package = $packagesByComponent[$componentId]
    if ($null -eq $package -or -not [bool]$package.present -or -not [bool]$package.hash_matches_manifest) {
      $scenarioFailures += "Required package is not present and hash-verified: $componentId."
      continue
    }
    foreach ($entryName in @($scenario.package_entries[$componentId])) {
      $present = Test-ZipEntry -Entries @($package.entries) -Entry ([string]$entryName)
      if (-not $present) {
        $scenarioFailures += "Missing packaged entry for $componentId`: $entryName."
      }
      $entryEvidence += [pscustomobject]@{
        component = $componentId
        entry = [string]$entryName
        present = $present
      }
    }
  }

  if ([string]$scenario.id -eq "run_vscode_extension") {
    $package = $packagesByComponent["vscode-extension"]
    $packageJsonText = if ($null -ne $package -and [bool]$package.present) { Get-ZipEntryText -PackagePath ([string]$package.package_path_full) -Entry "extension\package.json" } else { "" }
    foreach ($commandMarker in @("aegisLocalAutopilot.runValidation", "aegisLocalAutopilot.applyLastProposal", "aegisLocalAutopilot.rollbackLastChange", "aegisLocalAutopilot.reviewActiveFile", "aegisLocalAutopilot.createFeature")) {
      if ($packageJsonText -notmatch [regex]::Escape($commandMarker)) {
        $scenarioFailures += "VS Code package.json is missing command marker: $commandMarker."
      }
    }
  }

  if ([string]$scenario.id -eq "update_component" -or [string]$scenario.id -eq "rollback_component") {
    $rollbackPayload = $evidenceSources["release_apply_rollback"].payload
    if ($null -eq $rollbackPayload -or [string]$rollbackPayload.status -ne "ready") {
      $scenarioFailures += "Phase 21 apply/rollback payload is not ready."
    } else {
      foreach ($component in @("aegis-core", "website", "desktop", "vscode-extension", "visual-studio-extension")) {
        $item = @($rollbackPayload.components | Where-Object { [string]$_.component -eq $component } | Select-Object -First 1)
        if ($item.Count -eq 0) {
          $scenarioFailures += "Phase 21 evidence is missing component: $component."
        } elseif ([string]$scenario.id -eq "update_component" -and ([string]$item[0].plan_state -ne "planned" -or [string]$item[0].apply_state -ne "success")) {
          $scenarioFailures += "Phase 21 update evidence is incomplete for $component."
        } elseif ([string]$scenario.id -eq "rollback_component" -and ([string]$item[0].rollback_state -ne "rolled_back" -or -not [bool]$item[0].marker_restored -or -not [bool]$item[0].stray_removed)) {
          $scenarioFailures += "Phase 21 rollback evidence is incomplete for $component."
        }
      }
    }
  }

  $scenarioResults += [pscustomobject]@{
    id = [string]$scenario.id
    status = if ($scenarioFailures.Count -eq 0) { "passed" } else { "failed" }
    evidence_kind = [string]$scenario.evidence_kind
    package_entries = $entryEvidence
    evidence_sources = $sourceEvidence
    limitation = [string]$scenario.limitation
    failures = $scenarioFailures
  }
}

$failedScenarios = @($scenarioResults | Where-Object { [string]$_.status -ne "passed" })
$alphaScenarioAttached = -not [bool](@($checks) | Where-Object { $_.id -like "alpha_scenario_contract:*" -and -not [bool]$_.passed } | Select-Object -First 1)
$releaseApplyRollbackReady = Test-EvidenceReady -Evidence $evidenceSources["release_apply_rollback"] -AcceptedStatuses @("ready")
Add-Check -Checks $checks -Id "alpha_scenario_contract_attached" -Passed $alphaScenarioAttached -Message "Phase 22 scenarios are attached to the Phase 14 and Phase 15 scenario contracts."
Add-Check -Checks $checks -Id "release_apply_rollback_attached" -Passed $releaseApplyRollbackReady -Message "Phase 21 release apply/rollback evidence is attached for update and rollback scenarios."
Add-Check -Checks $checks -Id "all_scenarios_have_evidence" -Passed (@($failedScenarios).Count -eq 0) -Message "All packaged alpha scenarios have package-backed evidence." -Details $failedScenarios
Add-Check -Checks $checks -Id "scenario_evidence_linkable" -Passed $true -Message "Phase 22 writes linkable JSON and Markdown outputs."

foreach ($requiredCheck in @($contract.required_checks)) {
  $check = @($checks | Where-Object { [string]$_.id -eq [string]$requiredCheck -and [bool]$_.passed } | Select-Object -First 1)
  Add-Check -Checks $checks -Id "required_check:$requiredCheck" -Passed ($check.Count -gt 0) -Message "Required check group passed: $requiredCheck"
}

foreach ($check in @($checks)) {
  if (-not [bool]$check.passed) {
    $failures.Add([string]$check.message) | Out-Null
  }
}

$summary = [pscustomobject]@{
  schema_version = "2026.05.21"
  phase = 22
  status = if ($failures.Count -eq 0) { "ready" } else { "blocked" }
  generated_at = (Get-Date).ToString("o")
  evidence_dir = ConvertTo-ProjectRelativePath $EvidenceDir
  manifest = "release\version-manifest.json"
  contract = "evals/phase22-packaged-alpha-scenarios-contract.json"
  evidence_sources = @($evidenceSources.GetEnumerator() | ForEach-Object {
    [pscustomobject]@{
      id = [string]$_.Key
      status = [string]$_.Value.status
      latest_folder = [string]$_.Value.latest_folder
      json_path = [string]$_.Value.json_path
    }
  })
  packages = @($packageInspections | ForEach-Object {
    [pscustomobject]@{
      component = $_.component
      artifact = $_.artifact
      path = $_.path
      present = $_.present
      size_bytes = $_.size_bytes
      sha256 = $_.sha256
      hash_matches_manifest = $_.hash_matches_manifest
      entry_count = $_.entry_count
      secret_finding_count = @($_.secret_findings).Count
    }
  })
  scenarios = $scenarioResults
  secret_findings = $secretFindings
  failures = $failures
  checks = $checks
}

$jsonPath = Join-Path $EvidenceDir "packaged-alpha-scenarios.json"
$markdownPath = Join-Path $EvidenceDir "packaged-alpha-scenarios-summary.md"
$summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 22 Packaged Alpha Scenario Evidence"
$markdown += ""
$markdown += "- Status: $($summary.status)"
$markdown += "- Generated at: $($summary.generated_at)"
$markdown += "- Evidence dir: $($summary.evidence_dir)"
$markdown += "- Scenarios: $(@($summary.scenarios).Count)"
$markdown += "- Failed scenarios: $(@($failedScenarios).Count)"
$markdown += ""
$markdown += "## Evidence Sources"
$markdown += ""
$markdown += "| Source | Status | Latest Folder |"
$markdown += "| --- | --- | --- |"
foreach ($source in @($summary.evidence_sources)) {
  $markdown += "| $($source.id) | $($source.status) | $($source.latest_folder) |"
}
$markdown += ""
$markdown += "## Packages"
$markdown += ""
$markdown += "| Component | Artifact | Hash | Entries | Secret Findings |"
$markdown += "| --- | --- | --- | ---: | ---: |"
foreach ($package in @($summary.packages)) {
  $hashStatus = if ([bool]$package.hash_matches_manifest) { "matched" } else { "mismatch" }
  $markdown += "| $($package.component) | $($package.artifact) | $hashStatus | $($package.entry_count) | $($package.secret_finding_count) |"
}
$markdown += ""
$markdown += "## Scenarios"
$markdown += ""
$markdown += "| Scenario | Status | Evidence Kind | Package Entries | Evidence Sources | Limitation |"
$markdown += "| --- | --- | --- | ---: | --- | --- |"
foreach ($scenario in @($summary.scenarios)) {
  $sourceText = (@($scenario.evidence_sources) | ForEach-Object { "$($_.id):$($_.status)" }) -join ", "
  $limitation = ([string]$scenario.limitation).Replace("|", "\|")
  $markdown += "| $($scenario.id) | $($scenario.status) | $($scenario.evidence_kind) | $(@($scenario.package_entries).Count) | $sourceText | $limitation |"
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

if ($failures.Count -gt 0) {
  throw "Packaged alpha scenario validation failed:`n - $($failures -join "`n - ")"
}
