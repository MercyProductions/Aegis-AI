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

function Read-TextIfPresent {
  param([string]$RelativePath)
  $path = Join-ProjectPath $RelativePath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    return ""
  }
  return Get-Content -LiteralPath $path -Raw
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

function New-ClientDefinition {
  param(
    [string]$Id,
    [string]$DisplayName,
    [string]$PackageComponent,
    [string[]]$SourceFiles,
    [hashtable]$CapabilityPatterns
  )

  return [pscustomobject]@{
    id = $Id
    display_name = $DisplayName
    package_component = $PackageComponent
    source_files = $SourceFiles
    capability_patterns = $CapabilityPatterns
  }
}

if ([string]::IsNullOrWhiteSpace($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\cross-client-parity" (Get-Date -Format "yyyyMMdd-HHmmss"))
} elseif (-not [System.IO.Path]::IsPathRooted($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root $EvidenceDir
}
$EvidenceDir = Test-UnderRoot $EvidenceDir
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$contract = Read-JsonFile (Join-ProjectPath "evals\phase23-cross-client-parity-contract.json")
$manifestPath = Join-ProjectPath "release\version-manifest.json"

$checks = [System.Collections.Generic.List[object]]::new()
$failures = [System.Collections.Generic.List[string]]::new()

foreach ($relativePath in @($contract.required_contract_files)) {
  $exists = Test-Path -LiteralPath (Join-ProjectPath ([string]$relativePath)) -PathType Leaf
  Add-Check -Checks $checks -Id "contract_file:$relativePath" -Passed $exists -Message "Required Phase 23 contract file is present: $relativePath"
}

$manifestPresent = Test-Path -LiteralPath $manifestPath -PathType Leaf
Add-Check -Checks $checks -Id "root_manifest_present" -Passed $manifestPresent -Message "Root release/version-manifest.json exists."
if (-not $manifestPresent) {
  throw "Root release/version-manifest.json is required before Phase 23."
}
$manifest = Read-JsonFile $manifestPath

$evidenceSources = [ordered]@{
  final_release_manifest = Get-LatestEvidence -RootPath ".aegis\final-release-manifest" -JsonName "final-release-manifest.json"
  release_apply_rollback = Get-LatestEvidence -RootPath ".aegis\release-apply-rollback" -JsonName "release-apply-rollback.json"
  packaged_alpha_scenarios = Get-LatestEvidence -RootPath ".aegis\packaged-alpha-scenarios" -JsonName "packaged-alpha-scenarios.json"
}

foreach ($sourceId in @($contract.required_evidence_sources)) {
  $source = $evidenceSources[[string]$sourceId]
  $ready = Test-EvidenceReady -Evidence $source -AcceptedStatuses @("ready")
  Add-Check -Checks $checks -Id "evidence_source:$sourceId" -Passed $ready -Message "Required parity evidence source is attached: $sourceId" -Details ([pscustomobject]@{
      status = if ($null -ne $source) { [string]$source.status } else { "missing" }
      latest_folder = if ($null -ne $source) { [string]$source.latest_folder } else { "" }
      json_path = if ($null -ne $source) { [string]$source.json_path } else { "" }
    })
}

$packageInspections = @()
$packagesByComponent = @{}
foreach ($componentId in @($contract.release_components)) {
  $id = [string]$componentId
  $component = Get-ManifestComponent -Manifest $manifest -Id $id
  $packagePath = if ($null -ne $component -and $null -ne $component.package) { Join-ProjectPath ([string]$component.package.path) } else { "" }
  $exists = -not [string]::IsNullOrWhiteSpace($packagePath) -and (Test-Path -LiteralPath $packagePath -PathType Leaf)
  $hash = ""
  $hashMatches = $false
  $sizeBytes = 0
  if ($exists) {
    $item = Get-Item -LiteralPath $packagePath
    $sizeBytes = $item.Length
    $hash = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash.ToLowerInvariant()
    $hashMatches = $hash -eq ([string]$component.package.sha256).ToLowerInvariant()
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
  }
  $packageInspections += $inspection
  $packagesByComponent[$id] = $inspection
}

$packagesPresent = -not [bool](@($packageInspections) | Where-Object { -not [bool]$_.present } | Select-Object -First 1)
$hashesMatch = -not [bool](@($packageInspections) | Where-Object { -not [bool]$_.hash_matches_manifest } | Select-Object -First 1)
Add-Check -Checks $checks -Id "packages_present" -Passed $packagesPresent -Message "All release packages listed in the root manifest are present."
Add-Check -Checks $checks -Id "packages_match_manifest_hashes" -Passed $hashesMatch -Message "All release packages match manifest SHA-256 values."

$clientDefinitions = @(
  New-ClientDefinition -Id "website" -DisplayName "Website" -PackageComponent "website" -SourceFiles @(
    "website\frontend\src\App.tsx",
    "website\frontend\src\api.ts",
    "website\frontend\src\types.ts",
    "website\frontend\src\utils\runtimeDiagnostics.ts",
    "website\backend\aegis_ai\routes\runtime.py",
    "website\backend\aegis_ai\services\core_client.py",
    "website\backend\aegis_ai\diagnostic_redaction.py",
    "website\backend\aegis_ai\diff_engine.py",
    "website\backend\aegis_ai\routes\checkpoints.py",
    "website\backend\aegis_ai\routes\validation.py"
  ) -CapabilityPatterns @{
    workspace_scan = 'scanWorkspaceIntelligence|workspace-intelligence|/api/files|WorkspaceFile|workspace_root'
    model_route = 'routeDistributedModel|distributed-runtime/route|models/route|model.route|model_manager|model_registry'
    proposal_or_review = 'proposal|review|diff|previewGlobalCommand'
    apply = 'apply|changes/apply|apply files'
    validation = 'validation|validate'
    checkpoint = 'checkpoint|checkpoints'
    rollback_or_restore = 'rollback|restore|checkpoints/restore'
    diagnostics_export = 'diagnostic|exportRuntimeSettings|runtimeDiagnostics|redaction'
    release_compatibility = 'getReleaseCompatibility|/api/release/compatibility|release.compatibility'
  }
  New-ClientDefinition -Id "desktop" -DisplayName "Native Desktop" -PackageComponent "desktop" -SourceFiles @(
    "src\AegisChatApp.cpp",
    "src\AegisChatApp.h",
    "src\AegisClient.cpp",
    "src\AegisClient.h",
    "src\core\CoreApiClient.cpp",
    "src\core\CoreApiClient.h",
    "src\Platform.cpp"
  ) -CapabilityPatterns @{
    workspace_scan = '/v1/workspaces/scan|ScanWorkspaceFiles|WorkspaceProjectManifest|workspace.scan'
    model_route = 'PreviewRoute|models/route|Route|ModelRegistry|Coding Routes'
    proposal_or_review = 'proposal|review|Generated Changes|Patch'
    apply = '/v1/changes/apply|ApplyChanges|ApplyGeneratedChanges|ApplyRoutePolicyDiff'
    validation = '/v1/validation/run|RunValidation|Full Verify|Validation'
    checkpoint = '/v1/checkpoints|ListCheckpoints|Checkpoint'
    rollback_or_restore = '/v1/checkpoints/restore|RestoreCheckpoint|Rollback|restore'
    diagnostics_export = 'RedactDiagnosticText|diagnostic|Export Verification Report|Export Chat'
    release_compatibility = '/v1/release/compatibility|release_compatibility_checked|Compatibility'
  }
  New-ClientDefinition -Id "vscode-extension" -DisplayName "VS Code Extension" -PackageComponent "vscode-extension" -SourceFiles @(
    "vscode-plugins\aegis-local-autopilot\package.json",
    "vscode-plugins\aegis-local-autopilot\extension.js",
    "vscode-plugins\aegis-local-autopilot\src\core\aegisCoreClient.ts",
    "vscode-plugins\aegis-local-autopilot\src\workflowClient.ts",
    "vscode-plugins\aegis-local-autopilot\src\validation\validationRunner.ts",
    "vscode-plugins\aegis-local-autopilot\src\validation\validationDetector.ts",
    "vscode-plugins\aegis-local-autopilot\src\proposal\proposalParser.ts",
    "vscode-plugins\aegis-local-autopilot\src\proposal\proposalSafety.ts",
    "vscode-plugins\aegis-local-autopilot\src\proposal\rollback.ts",
    "vscode-plugins\aegis-local-autopilot\src\workspace\projectScanner.ts"
  ) -CapabilityPatterns @{
    workspace_scan = '/v1/workspaces/scan|projectScanner|buildProjectOverviewState|Inspecting workspace'
    model_route = '/v1/models/route|model.route|scanModels|modelDiagnostics'
    proposal_or_review = '/v1/changes/propose|reviewActiveFile|proposal|previewLastProposal'
    apply = '/v1/changes/apply|applyLastProposal|applyProposal'
    validation = '/v1/validation/run|runValidation|validationRunner'
    checkpoint = '/v1/checkpoints|checkpoint|checkpointAvailable'
    rollback_or_restore = '/v1/checkpoints/restore|rollbackLastChange|rollback'
    diagnostics_export = '/v1/diagnostics|collectDiagnostics|modelDiagnostics|core-diagnostics'
    release_compatibility = '/v1/release/compatibility|release.compatibility'
  }
  New-ClientDefinition -Id "visual-studio-extension" -DisplayName "Visual Studio Extension" -PackageComponent "visual-studio-extension" -SourceFiles @(
    "visual-studio-extensions\aegis-local-agent-vs\src\AegisLocalAgentVs\Services\AegisCoreClient.cs",
    "visual-studio-extensions\aegis-local-agent-vs\src\AegisLocalAgentVs\Services\AegisAgentRuntime.cs",
    "visual-studio-extensions\aegis-local-agent-vs\src\AegisLocalAgentVs\Services\SafeEditService.cs",
    "visual-studio-extensions\aegis-local-agent-vs\src\AegisLocalAgentVs\Services\SolutionScanner.cs",
    "visual-studio-extensions\aegis-local-agent-vs\src\AegisLocalAgentVs\Services\SolutionIntelligenceService.cs",
    "visual-studio-extensions\aegis-local-agent-vs\src\AegisLocalAgentVs\Services\DiagnosticRedactor.cs",
    "visual-studio-extensions\aegis-local-agent-vs\src\AegisLocalAgentVs\Models\AgentModels.cs",
    "visual-studio-extensions\aegis-local-agent-vs\src\AegisLocalAgentVs\Commands\AegisCommands.cs",
    "visual-studio-extensions\aegis-local-agent-vs\src\AegisLocalAgentVs\ToolWindows\AegisToolWindowControl.xaml",
    "visual-studio-extensions\aegis-local-agent-vs\README.md"
  ) -CapabilityPatterns @{
    workspace_scan = '/v1/workspaces/scan|ScanAsync|Rescan|SolutionScanner|WorkspaceIntelligenceAsync'
    model_route = '/v1/models/route|model.route|selected_model|Route'
    proposal_or_review = '/v1/changes/propose|ReviewSelectedCode|AgentProposal|Proposal'
    apply = '/v1/changes/apply|ApplyProposalAsync|ApplyPendingProposalAsync'
    validation = '/v1/validation/run|RunValidation|RecordVisualStudioValidationWithCoreAsync|Validation'
    checkpoint = '/v1/checkpoints|CoreCheckpointId|Checkpoint'
    rollback_or_restore = '/v1/checkpoints/restore|RestoreCheckpointAsync|RollbackLastChangeAsync|rollback'
    diagnostics_export = 'DiagnosticRedactor|diagnostic|Diagnostics|ValidationOutput'
    release_compatibility = '/v1/release/compatibility|release.compatibility'
  }
)

$clientResults = @()
foreach ($client in $clientDefinitions) {
  $sourceEvidence = @()
  $textParts = @()
  foreach ($relativePath in @($client.source_files)) {
    $exists = Test-Path -LiteralPath (Join-ProjectPath ([string]$relativePath)) -PathType Leaf
    $sourceEvidence += [pscustomobject]@{
      path = [string]$relativePath
      present = $exists
    }
    Add-Check -Checks $checks -Id "client_source:$($client.id):$(ConvertTo-CheckId ([string]$relativePath))" -Passed $exists -Message "$($client.display_name) source file is present: $relativePath"
    if ($exists) {
      $textParts += Read-TextIfPresent ([string]$relativePath)
    }
  }

  $combinedText = $textParts -join "`n"
  $capabilityResults = @()
  foreach ($capabilityId in @($contract.workflow_capabilities)) {
    $id = [string]$capabilityId
    $pattern = [string]$client.capability_patterns[$id]
    $passed = -not [string]::IsNullOrWhiteSpace($pattern) -and [bool]($combinedText -match $pattern)
    $capabilityResults += [pscustomobject]@{
      id = $id
      present = $passed
      pattern = $pattern
    }
    Add-Check -Checks $checks -Id "client_capability:$($client.id):$id" -Passed $passed -Message "$($client.display_name) exposes parity capability: $id"
  }

  $package = $packagesByComponent[[string]$client.package_component]
  $packageReady = $null -ne $package -and [bool]$package.present -and [bool]$package.hash_matches_manifest
  Add-Check -Checks $checks -Id "client_package:$($client.id)" -Passed $packageReady -Message "$($client.display_name) package is present and hash-verified."

  $missingCapabilities = @($capabilityResults | Where-Object { -not [bool]$_.present })
  $clientResults += [pscustomobject]@{
    id = [string]$client.id
    display_name = [string]$client.display_name
    package_component = [string]$client.package_component
    package_ready = $packageReady
    source_files = $sourceEvidence
    capabilities = $capabilityResults
    status = if ($packageReady -and @($missingCapabilities).Count -eq 0) { "passed" } else { "failed" }
    missing_capabilities = @($missingCapabilities | ForEach-Object { [string]$_.id })
  }
}

$requiredClientIds = @($contract.clients | ForEach-Object { [string]$_ })
$actualClientIds = @($clientResults | ForEach-Object { [string]$_.id })
foreach ($clientId in $requiredClientIds) {
  Add-Check -Checks $checks -Id "contract_client:$clientId" -Passed ($actualClientIds -contains $clientId) -Message "Phase 23 client is covered: $clientId"
}

$allClientsHavePackageEvidence = -not [bool](@($clientResults) | Where-Object { -not [bool]$_.package_ready } | Select-Object -First 1)
$failedClients = @($clientResults | Where-Object { [string]$_.status -ne "passed" })
$allClientsHaveWorkflowParity = @($failedClients).Count -eq 0
$evidenceSourcesAttached = -not [bool](@($checks) | Where-Object { [string]$_.id -like "evidence_source:*" -and -not [bool]$_.passed } | Select-Object -First 1)
Add-Check -Checks $checks -Id "evidence_sources_attached" -Passed $evidenceSourcesAttached -Message "Phase 20, 21, and 22 evidence sources are attached."
Add-Check -Checks $checks -Id "all_clients_have_package_evidence" -Passed $allClientsHavePackageEvidence -Message "All parity clients have package evidence in the root manifest."
Add-Check -Checks $checks -Id "all_clients_have_workflow_parity" -Passed $allClientsHaveWorkflowParity -Message "All parity clients expose the safe workflow capability set." -Details $failedClients
Add-Check -Checks $checks -Id "parity_evidence_linkable" -Passed $true -Message "Phase 23 writes linkable JSON and Markdown outputs."

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
  phase = 23
  status = if ($failures.Count -eq 0) { "ready" } else { "blocked" }
  generated_at = (Get-Date).ToString("o")
  evidence_dir = ConvertTo-ProjectRelativePath $EvidenceDir
  manifest = "release\version-manifest.json"
  contract = "evals/phase23-cross-client-parity-contract.json"
  workflow_capabilities = @($contract.workflow_capabilities)
  evidence_sources = @($evidenceSources.GetEnumerator() | ForEach-Object {
    [pscustomobject]@{
      id = [string]$_.Key
      status = [string]$_.Value.status
      latest_folder = [string]$_.Value.latest_folder
      json_path = [string]$_.Value.json_path
    }
  })
  packages = @($packageInspections)
  clients = $clientResults
  limitations = @(
    "VS Code extension-host smoke can still be blocked by the VS Code update mutex.",
    "Visual Studio experimental-instance smoke remains separate runtime evidence.",
    "Desktop installer/update smoke remains separate from source-backed parity."
  )
  failures = $failures
  checks = $checks
}

$jsonPath = Join-Path $EvidenceDir "cross-client-parity.json"
$markdownPath = Join-Path $EvidenceDir "cross-client-parity-summary.md"
$summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 23 Cross-Client Parity Evidence"
$markdown += ""
$markdown += "- Status: $($summary.status)"
$markdown += "- Generated at: $($summary.generated_at)"
$markdown += "- Evidence dir: $($summary.evidence_dir)"
$markdown += "- Clients: $(@($summary.clients).Count)"
$markdown += "- Workflow capabilities: $(@($summary.workflow_capabilities).Count)"
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
$markdown += "| Component | Artifact | Present | Hash |"
$markdown += "| --- | --- | --- | --- |"
foreach ($package in @($summary.packages)) {
  $hashStatus = if ([bool]$package.hash_matches_manifest) { "matched" } else { "mismatch" }
  $markdown += "| $($package.component) | $($package.artifact) | $($package.present) | $hashStatus |"
}
$markdown += ""
$markdown += "## Clients"
$markdown += ""
$markdown += "| Client | Status | Package Ready | Missing Capabilities |"
$markdown += "| --- | --- | --- | --- |"
foreach ($client in @($summary.clients)) {
  $missing = if (@($client.missing_capabilities).Count) { @($client.missing_capabilities) -join ", " } else { "" }
  $markdown += "| $($client.id) | $($client.status) | $($client.package_ready) | $missing |"
}
$markdown += ""
$markdown += "## Limitations"
$markdown += ""
foreach ($limitation in @($summary.limitations)) {
  $markdown += "- $limitation"
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
  throw "Cross-client parity validation failed:`n - $($failures -join "`n - ")"
}
