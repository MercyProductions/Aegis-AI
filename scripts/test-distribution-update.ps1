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
  return $Value.Replace("/", "-").Replace("\", "-").Replace(" ", "-").Replace(":", "").Replace("{", "").Replace("}", "").Replace("*", "star").ToLowerInvariant()
}

function Read-ProjectFile {
  param([Parameter(Mandatory = $true)][string]$RelativePath)
  $path = Join-ProjectPath $RelativePath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "Required Phase 34 file is missing: $RelativePath"
  }
  return Get-Content -LiteralPath $path -Raw
}

function Read-ProjectJson {
  param([Parameter(Mandatory = $true)][string]$RelativePath)
  return Read-ProjectFile $RelativePath | ConvertFrom-Json
}

function Read-JsonPath {
  param([Parameter(Mandatory = $true)][string]$Path)
  return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
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

function Get-PayloadStatus {
  param([object]$Payload)
  if ($null -eq $Payload) {
    return "missing"
  }
  $statusProperty = $Payload.PSObject.Properties["status"]
  if ($null -ne $statusProperty) {
    return [string]$statusProperty.Value
  }
  $overallStatusProperty = $Payload.PSObject.Properties["overall_status"]
  if ($null -ne $overallStatusProperty) {
    return [string]$overallStatusProperty.Value
  }
  return "present"
}

function Get-LatestEvidence {
  param(
    [string]$RootPath,
    [string]$JsonName,
    [string]$SummaryName
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
    $summaryPath = Join-Path $folder.FullName $SummaryName
    if (Test-Path -LiteralPath $jsonPath -PathType Leaf) {
      $payload = Read-JsonPath $jsonPath
      return [pscustomobject]@{
        status = Get-PayloadStatus $payload
        latest_folder = ConvertTo-ProjectRelativePath $folder.FullName
        json_path = ConvertTo-ProjectRelativePath $jsonPath
        summary_path = if (Test-Path -LiteralPath $summaryPath -PathType Leaf) { ConvertTo-ProjectRelativePath $summaryPath } else { "" }
        summary_present = Test-Path -LiteralPath $summaryPath -PathType Leaf
        payload = $payload
      }
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
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\distribution-update" (Get-Date -Format "yyyyMMdd-HHmmss"))
} elseif (-not [System.IO.Path]::IsPathRooted($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root $EvidenceDir
}
$EvidenceDir = Test-UnderRoot $EvidenceDir
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$script:Checks = @()
$script:Failures = @()
$contract = Read-ProjectJson "evals\phase34-distribution-update-contract.json"
$sourceManifest = Read-ProjectJson ([string]$contract.source_manifest)
$releaseManifest = Read-ProjectJson ([string]$contract.release_manifest)
$distributionDoc = Read-ProjectFile ([string]$contract.distribution_doc)
$releasePackagingDoc = Read-ProjectFile ([string]$contract.release_packaging_doc)
$artifactDecisionDoc = Read-ProjectFile ([string]$contract.release_artifact_decision_doc)
$externalReleaseNotes = Read-ProjectFile ([string]$contract.external_release_notes)
$sourceUpdater = Read-ProjectFile ([string]$contract.source_updater)
$releaseUpdater = Read-ProjectFile ([string]$contract.release_updater)
$buildRelease = Read-ProjectFile ([string]$contract.package_builder)
$componentManifest = Read-ProjectJson ([string]$contract.component_manifest)
$diagnosticsSource = Read-ProjectFile ([string]$contract.diagnostics_source)
$diagnosticsTests = Read-ProjectFile ([string]$contract.diagnostics_tests)
$validationDocs = Read-ProjectFile "docs\VALIDATION_MATRIX.md"
$ledgerDocs = Read-ProjectFile "docs\EVIDENCE_LEDGER.md"
$ledgerContract = Read-ProjectFile "evals\phase16-evidence-ledger-contract.json"
$validator = Read-ProjectFile "scripts\validate-ecosystem.ps1"

Add-Check -Id "contract-schema-version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Message "Phase 34 contract must use schema version 2026.05.21."
Add-Check -Id "contract-evidence-root" -Passed ([string]$contract.evidence_root -eq ".aegis/distribution-update") -Message "Phase 34 evidence root must be .aegis/distribution-update."
Add-Check -Id "contract-required-status" -Passed ([string]$contract.current_required_status -eq "ready") -Message "Phase 34 required status must be ready."
Add-Check -Id "contract-distribution-mode" -Passed ([string]$contract.distribution_mode -eq "portable_zip_and_vsix") -Message "Phase 34 distribution mode must remain portable ZIP plus VSIX for this private alpha slice."
Add-Check -Id "contract-installer-status" -Passed ([string]$contract.installer_status -match "deferred") -Message "Phase 34 must keep signed installer status deferred until broad release."
Add-Check -Id "contract-signing-status" -Passed ([string]$contract.signing_status -match "unsigned") -Message "Phase 34 must keep unsigned local build status explicit."

foreach ($relativePath in @($contract.required_contract_files)) {
  Add-Check -Id "contract-file-$(ConvertTo-CheckId ([string]$relativePath))" -Passed (Test-Path -LiteralPath (Join-ProjectPath ([string]$relativePath)) -PathType Leaf) -Message "Required Phase 34 file must exist: $relativePath"
}

foreach ($marker in @($contract.required_doc_markers)) {
  $found = $distributionDoc.Contains([string]$marker) -or $releasePackagingDoc.Contains([string]$marker) -or $artifactDecisionDoc.Contains([string]$marker) -or $externalReleaseNotes.Contains([string]$marker)
  Add-Check -Id "doc-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed $found -Message "Distribution docs must include '$marker'."
}

$sourcePolicy = $sourceManifest.update_policy
$releasePolicy = $releaseManifest.update_policy
foreach ($property in @($contract.required_update_policy.PSObject.Properties)) {
  $name = [string]$property.Name
  $expected = [bool]$property.Value
  $sourceValue = $null -ne $sourcePolicy -and $null -ne $sourcePolicy.PSObject.Properties[$name] -and [bool]$sourcePolicy.$name -eq $expected
  $releaseValue = $null -ne $releasePolicy -and $null -ne $releasePolicy.PSObject.Properties[$name] -and [bool]$releasePolicy.$name -eq $expected
  Add-Check -Id "source-update-policy-$(ConvertTo-CheckId $name)" -Passed $sourceValue -Message "VERSION.json update policy must set $name to $expected."
  Add-Check -Id "release-update-policy-$(ConvertTo-CheckId $name)" -Passed $releaseValue -Message "Root release manifest update policy must set $name to $expected."
}

$artifactResults = @()
foreach ($componentId in @($contract.release_components)) {
  $componentId = [string]$componentId
  $sourceComponent = Get-ManifestComponent -Manifest $sourceManifest -Id $componentId
  $releaseComponent = Get-ManifestComponent -Manifest $releaseManifest -Id $componentId
  $expectation = @($contract.package_expectations | Where-Object { [string]$_.id -eq $componentId } | Select-Object -First 1)

  Add-Check -Id "manifest-source-component-$(ConvertTo-CheckId $componentId)" -Passed ($null -ne $sourceComponent) -Message "VERSION.json must include component $componentId."
  Add-Check -Id "manifest-release-component-$(ConvertTo-CheckId $componentId)" -Passed ($null -ne $releaseComponent) -Message "release/version-manifest.json must include component $componentId."
  if ($null -eq $sourceComponent -or $null -eq $releaseComponent) {
    continue
  }

  Add-Check -Id "manifest-version-match-$(ConvertTo-CheckId $componentId)" -Passed ([string]$sourceComponent.version -eq [string]$releaseComponent.version) -Message "Source and release manifests must agree on $componentId version."

  $package = $releaseComponent.package
  $hasPackageFields = $null -ne $package -and
    -not [string]::IsNullOrWhiteSpace([string]$package.artifact) -and
    -not [string]::IsNullOrWhiteSpace([string]$package.path) -and
    [string]$package.sha256 -match '^[a-fA-F0-9]{64}$' -and
    [int64]$package.size_bytes -gt 0
  Add-Check -Id "package-fields-$(ConvertTo-CheckId $componentId)" -Passed $hasPackageFields -Message "Release manifest package metadata must be complete for $componentId."
  if (-not $hasPackageFields) {
    continue
  }

  $artifactMatches = $true
  if ($null -ne $expectation) {
    $artifactMatches = [string]$package.artifact -like [string]$expectation.artifact_pattern
  }
  Add-Check -Id "artifact-pattern-$(ConvertTo-CheckId $componentId)" -Passed $artifactMatches -Message "Artifact name must match the Phase 34 distribution expectation for $componentId."

  $pathIsReleaseRelative = (([string]$package.path) -replace '\\', '/') -like "release/*"
  Add-Check -Id "artifact-release-relative-$(ConvertTo-CheckId $componentId)" -Passed $pathIsReleaseRelative -Message "Package path must be release-relative for $componentId."

  $artifactPath = Join-ProjectPath (([string]$package.path) -replace '/', '\')
  $artifactPresent = Test-Path -LiteralPath $artifactPath -PathType Leaf
  Add-Check -Id "artifact-present-$(ConvertTo-CheckId $componentId)" -Passed $artifactPresent -Message "Package artifact must exist for $componentId."
  $actualHash = ""
  $actualSize = 0
  if ($artifactPresent) {
    $item = Get-Item -LiteralPath $artifactPath
    $actualSize = [int64]$item.Length
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $artifactPath).Hash.ToLowerInvariant()
    Add-Check -Id "artifact-size-$(ConvertTo-CheckId $componentId)" -Passed ($actualSize -eq [int64]$package.size_bytes) -Message "Package size must match manifest for $componentId."
    Add-Check -Id "artifact-sha-$(ConvertTo-CheckId $componentId)" -Passed ($actualHash -eq ([string]$package.sha256).ToLowerInvariant()) -Message "Package SHA-256 must match manifest for $componentId."
  }

  $artifactResults += [pscustomobject]@{
    id = $componentId
    artifact = [string]$package.artifact
    path = [string]$package.path
    expected_kind = if ($null -ne $expectation) { [string]$expectation.distribution_kind } else { "" }
    present = $artifactPresent
    size_bytes = $actualSize
    sha256 = $actualHash
  }
}

foreach ($marker in @($contract.required_updater_markers)) {
  $found = $sourceUpdater.Contains([string]$marker) -and $releaseUpdater.Contains([string]$marker)
  Add-Check -Id "updater-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed $found -Message "Source and shipped updater must include '$marker'."
}

Add-Check -Id "package-builder-copies-updater" -Passed ($buildRelease.Contains("aegis-update.ps1") -and $buildRelease.Contains("version-manifest.json")) -Message "Package builder must copy the updater and generate the version manifest."
Add-Check -Id "component-manifest-rollback-order" -Passed ([bool]$componentManifest.update_policy.rollback_required -and @($componentManifest.update_policy.install_order).Count -ge 5) -Message "Component installer manifest must require rollback and define install order."

foreach ($marker in @($contract.required_diagnostics_markers)) {
  $found = $diagnosticsSource.Contains([string]$marker) -or $diagnosticsTests.Contains([string]$marker)
  Add-Check -Id "diagnostics-marker-$(ConvertTo-CheckId ([string]$marker))" -Passed $found -Message "Diagnostics export sources must include '$marker'."
}

Add-Check -Id "validator-gate" -Passed ($validator.Contains("test-distribution-update.ps1") -and $validator.Contains("distribution-update-contract")) -Message "Ecosystem validator must run the Phase 34 distribution/update gate."
Add-Check -Id "validation-doc-gate" -Passed ($validationDocs.Contains("distribution-update-contract") -and $validationDocs.Contains("test-distribution-update")) -Message "Validation matrix must document the Phase 34 distribution/update gate."
Add-Check -Id "ledger-doc-source" -Passed ($ledgerDocs.Contains(".aegis/distribution-update") -or $ledgerDocs.Contains("distribution_update")) -Message "Evidence ledger docs must include the Phase 34 distribution/update source."
Add-Check -Id "ledger-contract-source" -Passed ($ledgerContract.Contains("distribution_update") -and $ledgerContract.Contains(".aegis/distribution-update")) -Message "Evidence ledger contract must include distribution/update evidence."

$evidenceSources = @()
foreach ($source in @($contract.required_evidence_sources)) {
  $latest = Get-LatestEvidence -RootPath ([string]$source.root) -JsonName ([string]$source.json) -SummaryName ([string]$source.summary)
  $accepted = @($source.accepted_statuses | ForEach-Object { [string]$_ })
  $ready = $accepted -contains [string]$latest.status
  Add-Check -Id "evidence-source-$(ConvertTo-CheckId ([string]$source.id))" -Passed ($ready -and [bool]$latest.summary_present) -Message "Required evidence source '$($source.id)' must be attached with an accepted status."
  $evidenceSources += [pscustomobject]@{
    id = [string]$source.id
    status = [string]$latest.status
    latest_folder = [string]$latest.latest_folder
    json_path = [string]$latest.json_path
    summary_path = [string]$latest.summary_path
  }
}

$commandResults = @()
foreach ($componentId in @($contract.release_components)) {
  $componentId = [string]$componentId
  $command = Invoke-LoggedCommand -Id "update-plan-$componentId" -WorkingDirectory "." -Executable "powershell" -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-ProjectPath "scripts\aegis-update.ps1"), "-Manifest", (Join-ProjectPath "release\version-manifest.json"), "-Component", $componentId, "-InstallRoot", $Root)
  $commandResults += $command
  $planText = if (Test-Path -LiteralPath (Join-ProjectPath $command.log) -PathType Leaf) { Get-Content -LiteralPath (Join-ProjectPath $command.log) -Raw } else { "" }
  $planText = $planText -replace ([string][char]0), ""
  $plan = $null
  try {
    $jsonStart = $planText.IndexOf("{")
    $jsonEnd = $planText.LastIndexOf("}")
    if ($jsonStart -ge 0 -and $jsonEnd -gt $jsonStart) {
      $plan = $planText.Substring($jsonStart, ($jsonEnd - $jsonStart + 1)) | ConvertFrom-Json
    }
  } catch {
    $plan = $null
  }
  $planned = $command.status -eq "passed" -and $null -ne $plan -and [string]$plan.state -eq "planned" -and [bool]$plan.checksum_required -eq $true
  Add-Check -Id "update-plan-planned-$(ConvertTo-CheckId $componentId)" -Passed $planned -Message "Updater dry-run plan must be planned and checksum-required for $componentId."
}

$summary = [pscustomobject]@{
  schema_version = "2026.05.21"
  phase = 34
  status = if ($script:Failures.Count -eq 0) { "ready" } else { "blocked" }
  generated_at = (Get-Date).ToString("o")
  evidence_dir = ConvertTo-ProjectRelativePath $EvidenceDir
  contract = "evals/phase34-distribution-update-contract.json"
  slice = [string]$contract.slice
  distribution_mode = [string]$contract.distribution_mode
  installer_status = [string]$contract.installer_status
  signing_status = [string]$contract.signing_status
  release_manifest = [string]$contract.release_manifest
  artifacts = $artifactResults
  evidence_sources = $evidenceSources
  commands = $commandResults
  failures = $script:Failures
  checks = $script:Checks
}

$jsonPath = Join-Path $EvidenceDir "distribution-update.json"
$markdownPath = Join-Path $EvidenceDir "distribution-update-summary.md"
$summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 34 Distribution, Installer, Signing, And Auto-Update Evidence"
$markdown += ""
$markdown += "- Status: $($summary.status)"
$markdown += "- Generated at: $($summary.generated_at)"
$markdown += "- Evidence dir: $($summary.evidence_dir)"
$markdown += "- Distribution mode: $($summary.distribution_mode)"
$markdown += "- Installer status: $($summary.installer_status)"
$markdown += "- Signing status: $($summary.signing_status)"
$markdown += ""
$markdown += "## Artifacts"
$markdown += ""
$markdown += "| Component | Kind | Artifact | Size Bytes | SHA-256 |"
$markdown += "| --- | --- | --- | ---: | --- |"
foreach ($artifact in @($summary.artifacts)) {
  $markdown += "| $($artifact.id) | $($artifact.expected_kind) | $($artifact.path) | $($artifact.size_bytes) | $($artifact.sha256) |"
}
$markdown += ""
$markdown += "## Evidence Sources"
$markdown += ""
$markdown += "| Source | Status | Latest Folder |"
$markdown += "| --- | --- | --- |"
foreach ($source in @($summary.evidence_sources)) {
  $markdown += "| $($source.id) | $($source.status) | $($source.latest_folder) |"
}
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
  throw "Distribution/update validation failed:`n - $($script:Failures -join "`n - ")"
}
