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

function Read-JsonFile {
  param([string]$Path)
  return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

function Read-TextIfPresent {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return ""
  }
  return Get-Content -LiteralPath $Path -Raw
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

function Invoke-CapturedCommand {
  param(
    [string]$Executable,
    [string[]]$Arguments,
    [string]$LogPath
  )

  $oldErrorActionPreference = $ErrorActionPreference
  $oldNativePreference = $null
  $hasNativePreference = Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope Global -ErrorAction SilentlyContinue
  if ($null -ne $hasNativePreference) {
    $oldNativePreference = $Global:PSNativeCommandUseErrorActionPreference
    $Global:PSNativeCommandUseErrorActionPreference = $false
  }
  $ErrorActionPreference = "Continue"
  try {
    $output = & $Executable @Arguments 2>&1
    $exitCode = $LASTEXITCODE
  } catch {
    $output = @($_)
    $exitCode = if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) { $LASTEXITCODE } else { 1 }
  } finally {
    $ErrorActionPreference = $oldErrorActionPreference
    if ($null -ne $hasNativePreference) {
      $Global:PSNativeCommandUseErrorActionPreference = $oldNativePreference
    }
  }
  $text = ($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
  Set-Content -LiteralPath $LogPath -Value $text -Encoding UTF8

  return [pscustomobject]@{
    exit_code = $exitCode
    output = $text
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

function Get-ComponentTarget {
  param([string]$InstallRoot, [string]$ComponentId)
  switch ($ComponentId) {
    "aegis-core" { return Join-Path $InstallRoot "aegis-core" }
    "website" { return Join-Path $InstallRoot "website" }
    "desktop" { return Join-Path $InstallRoot "x64\Release" }
    "vscode-extension" { return Join-Path $InstallRoot "vscode-plugins\aegis-local-autopilot\release" }
    "visual-studio-extension" { return Join-Path $InstallRoot "visual-studio-extensions\aegis-local-agent-vs\release" }
    default { throw "Unknown component target '$ComponentId'." }
  }
}

function Test-UnderInstallRoot {
  param([string]$InstallRoot, [string]$Path)
  $full = [System.IO.Path]::GetFullPath($Path)
  $root = [System.IO.Path]::GetFullPath($InstallRoot)
  $rootWithSlash = $root.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
  return $full.Equals($root, [System.StringComparison]::OrdinalIgnoreCase) -or $full.StartsWith($rootWithSlash, [System.StringComparison]::OrdinalIgnoreCase)
}

function New-InitialTarget {
  param([string]$InstallRoot, [string]$ComponentId)
  $target = Get-ComponentTarget -InstallRoot $InstallRoot -ComponentId $ComponentId
  New-Item -ItemType Directory -Force -Path $target | Out-Null
  $marker = Join-Path $target "rollback-marker.txt"
  "original:$ComponentId" | Set-Content -LiteralPath $marker -Encoding UTF8
  return [pscustomobject]@{
    target = $target
    marker = $marker
  }
}

function Invoke-Updater {
  param(
    [string]$UpdaterScript,
    [string]$ManifestPath,
    [string]$InstallRoot,
    [string]$Component,
    [string]$LogPath,
    [switch]$Apply,
    [switch]$Rollback,
    [switch]$SafeMode,
    [string]$PackagePath = ""
  )

  $arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $UpdaterScript, "-Manifest", $ManifestPath, "-InstallRoot", $InstallRoot)
  if ($Rollback) {
    $arguments += "-Rollback"
  } else {
    $arguments += @("-Component", $Component)
  }
  if ($Apply) {
    $arguments += "-Apply"
  }
  if ($SafeMode) {
    $arguments += "-SafeMode"
  }
  if (-not [string]::IsNullOrWhiteSpace($PackagePath)) {
    $arguments += @("-PackagePath", $PackagePath)
  }

  return Invoke-CapturedCommand -Executable "powershell" -Arguments $arguments -LogPath $LogPath
}

if ([string]::IsNullOrWhiteSpace($EvidenceDir)) {
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $EvidenceDir = Join-Path $Root ".aegis\release-apply-rollback\$stamp"
} elseif (-not [System.IO.Path]::IsPathRooted($EvidenceDir)) {
  $EvidenceDir = Join-Path $Root $EvidenceDir
}

$EvidenceDir = Test-UnderRoot $EvidenceDir
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$contract = Read-JsonFile (Join-ProjectPath "evals\phase21-release-apply-rollback-contract.json")
$checks = [System.Collections.Generic.List[object]]::new()
$failures = [System.Collections.Generic.List[string]]::new()

foreach ($relativePath in @($contract.required_contract_files)) {
  $exists = Test-Path -LiteralPath (Join-ProjectPath ([string]$relativePath)) -PathType Leaf
  Add-Check -Checks $checks -Id "contract_file:$relativePath" -Passed $exists -Message "Required contract file is present: $relativePath"
}

$manifestPath = Join-ProjectPath "release\version-manifest.json"
$releaseUpdaterPath = Join-ProjectPath "release\aegis-update.ps1"
$sourceUpdaterPath = Join-ProjectPath "scripts\aegis-update.ps1"
$sourceUpdaterText = Read-TextIfPresent $sourceUpdaterPath
$releaseUpdaterText = Read-TextIfPresent $releaseUpdaterPath

Add-Check -Checks $checks -Id "final_manifest_present" -Passed (Test-Path -LiteralPath $manifestPath -PathType Leaf) -Message "Root release/version-manifest.json exists."
Add-Check -Checks $checks -Id "release_updater_copied" -Passed (Test-Path -LiteralPath $releaseUpdaterPath -PathType Leaf) -Message "Shipped release updater exists in release/aegis-update.ps1."
Add-Check -Checks $checks -Id "source_updater_clears_target_on_rollback" -Passed ([bool]($sourceUpdaterText -match 'Remove-Item\s+-LiteralPath\s+\$target\s+-Recurse\s+-Force')) -Message "Source updater clears target before rollback restore."
Add-Check -Checks $checks -Id "release_updater_clears_target_on_rollback" -Passed ([bool]($releaseUpdaterText -match 'Remove-Item\s+-LiteralPath\s+\$target\s+-Recurse\s+-Force')) -Message "Shipped updater clears target before rollback restore."
Add-Check -Checks $checks -Id "install_root_guarded" -Passed ([bool]($releaseUpdaterText -match 'Refusing to operate outside install root') -and [bool]($releaseUpdaterText -match 'StartsWith\(\$installRootWithSlash')) -Message "Updater guards operations to the install root."

$manifest = Read-JsonFile $manifestPath
$installRoot = Join-Path $EvidenceDir "install-root"
New-Item -ItemType Directory -Force -Path $installRoot | Out-Null
Copy-Item -LiteralPath (Join-ProjectPath "release") -Destination $installRoot -Recurse -Force
$tempManifestPath = Join-Path $installRoot "release\version-manifest.json"
$tempUpdaterPath = Join-Path $installRoot "release\aegis-update.ps1"

Add-Check -Checks $checks -Id "temporary_install_root" -Passed (Test-UnderInstallRoot -InstallRoot $EvidenceDir -Path $installRoot) -Message "Temporary install root lives under the Phase 21 evidence directory." -Details @{ install_root = ConvertTo-ProjectRelativePath $installRoot }

$componentResults = [System.Collections.Generic.List[object]]::new()
$securityAuditPath = Join-Path $installRoot ".aegis\security-audit.jsonl"

foreach ($componentId in @($contract.components)) {
  $component = Get-ManifestComponent -Manifest $manifest -Id ([string]$componentId)
  $targetInfo = New-InitialTarget -InstallRoot $installRoot -ComponentId ([string]$componentId)
  $artifact = [string]$component.package.artifact

  $planLog = Join-Path $EvidenceDir "plan-$componentId.log"
  $planResult = Invoke-Updater -UpdaterScript $tempUpdaterPath -ManifestPath $tempManifestPath -InstallRoot $installRoot -Component ([string]$componentId) -LogPath $planLog
  $planJsonPath = Join-Path $EvidenceDir "plan-$componentId.json"
  $plan = $null
  if ($planResult.exit_code -eq 0) {
    $plan = $planResult.output | ConvertFrom-Json
    $plan | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $planJsonPath -Encoding UTF8
  }

  $applyLog = Join-Path $EvidenceDir "apply-$componentId.log"
  $applyResult = Invoke-Updater -UpdaterScript $tempUpdaterPath -ManifestPath $tempManifestPath -InstallRoot $installRoot -Component ([string]$componentId) -Apply -SafeMode -LogPath $applyLog
  $successState = Read-JsonFile (Join-Path $installRoot ".aegis\update-state.json")

  $markerRemovedForRollback = $false
  if (Test-Path -LiteralPath $targetInfo.marker -PathType Leaf) {
    Remove-Item -LiteralPath $targetInfo.marker -Force
    $markerRemovedForRollback = $true
  }
  $strayPath = Join-Path $targetInfo.target "post-apply-stray.txt"
  "stray:$componentId" | Set-Content -LiteralPath $strayPath -Encoding UTF8

  $rollbackLog = Join-Path $EvidenceDir "rollback-$componentId.log"
  $rollbackResult = Invoke-Updater -UpdaterScript $tempUpdaterPath -ManifestPath $tempManifestPath -InstallRoot $installRoot -Component ([string]$componentId) -Rollback -LogPath $rollbackLog
  $rollbackState = Read-JsonFile (Join-Path $installRoot ".aegis\update-state.json")
  $markerAfterRollback = if (Test-Path -LiteralPath $targetInfo.marker -PathType Leaf) { Get-Content -LiteralPath $targetInfo.marker -Raw } else { "" }

  $componentResults.Add([pscustomobject]@{
    component = [string]$componentId
    artifact = $artifact
    plan_state = if ($null -ne $plan) { [string]$plan.state } else { "" }
    plan_exit_code = $planResult.exit_code
    apply_exit_code = $applyResult.exit_code
    apply_state = [string]$successState.state
    rollback_exit_code = $rollbackResult.exit_code
    rollback_state = [string]$rollbackState.state
    target_path = ConvertTo-ProjectRelativePath $targetInfo.target
    target_under_install_root = Test-UnderInstallRoot -InstallRoot $installRoot -Path $targetInfo.target
    backup_path = if ($null -ne $successState.backup_path) { ConvertTo-ProjectRelativePath ([string]$successState.backup_path) } else { "" }
    backup_present = $null -ne $successState.backup_path -and (Test-Path -LiteralPath ([string]$successState.backup_path) -PathType Container)
    marker_removed_before_rollback = $markerRemovedForRollback
    marker_restored = ([string]$markerAfterRollback).Trim() -eq "original:$componentId"
    stray_removed = -not (Test-Path -LiteralPath $strayPath -PathType Leaf)
    safe_mode = [bool]$successState.safe_mode
    rollback_available = [bool]$successState.rollback_available
    checksum_required = if ($null -ne $plan) { [bool]$plan.checksum_required } else { $false }
    logs = [pscustomobject]@{
      plan = ConvertTo-ProjectRelativePath $planLog
      apply = ConvertTo-ProjectRelativePath $applyLog
      rollback = ConvertTo-ProjectRelativePath $rollbackLog
    }
  }) | Out-Null
}

$planReady = -not [bool](@($componentResults) | Where-Object { $_.plan_exit_code -ne 0 -or $_.plan_state -ne "planned" -or -not $_.checksum_required } | Select-Object -First 1)
$applyReady = -not [bool](@($componentResults) | Where-Object { $_.apply_exit_code -ne 0 -or $_.apply_state -ne "success" -or -not $_.backup_present -or -not $_.rollback_available } | Select-Object -First 1)
$rollbackReady = -not [bool](@($componentResults) | Where-Object { $_.rollback_exit_code -ne 0 -or $_.rollback_state -ne "rolled_back" -or -not $_.marker_restored } | Select-Object -First 1)
$strayRemoved = -not [bool](@($componentResults) | Where-Object { -not $_.stray_removed } | Select-Object -First 1)
$targetsGuarded = -not [bool](@($componentResults) | Where-Object { -not $_.target_under_install_root } | Select-Object -First 1)

Add-Check -Checks $checks -Id "update_plan_dry_runs" -Passed $planReady -Message "All components produce planned update dry-runs against the copied release manifest."
Add-Check -Checks $checks -Id "apply_all_components" -Passed $applyReady -Message "All components apply successfully in the temporary install root."
Add-Check -Checks $checks -Id "rollback_all_components" -Passed $rollbackReady -Message "All components roll back successfully in the temporary install root."
Add-Check -Checks $checks -Id "rollback_removes_stray_files" -Passed $strayRemoved -Message "Rollback removes stray files left after simulated apply damage."
Add-Check -Checks $checks -Id "component_targets_under_install_root" -Passed $targetsGuarded -Message "All component targets remain under the temporary install root."

$corruptDir = Join-Path $installRoot "corrupt"
New-Item -ItemType Directory -Force -Path $corruptDir | Out-Null
$desktop = Get-ManifestComponent -Manifest $manifest -Id "desktop"
$corruptPackage = Join-Path $corruptDir ([string]$desktop.package.artifact)
"corrupt package for checksum failure" | Set-Content -LiteralPath $corruptPackage -Encoding UTF8
$failureLog = Join-Path $EvidenceDir "apply-corrupt-desktop.log"
$failureResult = Invoke-Updater -UpdaterScript $tempUpdaterPath -ManifestPath $tempManifestPath -InstallRoot $installRoot -Component "desktop" -PackagePath $corruptPackage -Apply -LogPath $failureLog
$failedState = Read-JsonFile (Join-Path $installRoot ".aegis\update-state.json")
$auditText = Read-TextIfPresent $securityAuditPath

$checksumFailureReady = $failureResult.exit_code -ne 0 -and [string]$failedState.state -eq "failed" -and [bool]$failedState.failed_update_detected -and [bool]$failedState.safe_mode -and [string]$failedState.last_error -match "checksum mismatch"
$auditReady = (Test-Path -LiteralPath $securityAuditPath -PathType Leaf) -and [bool]($auditText -match "update.package_verified") -and [bool]($auditText -match "update.failed_security_check")
Add-Check -Checks $checks -Id "checksum_failure_sets_failed_safe_mode" -Passed $checksumFailureReady -Message "Corrupt package apply fails checksum validation and records failed safe-mode state."
Add-Check -Checks $checks -Id "security_audit_written" -Passed $auditReady -Message "Updater writes security audit entries for package verification and failed checksum checks."

foreach ($required in @($contract.required_checks)) {
  $matching = @($checks | Where-Object { [string]$_.id -eq [string]$required -or [string]$_.id -like "$required*" })
  $passed = $matching.Count -gt 0 -and -not [bool]($matching | Where-Object { -not $_.passed } | Select-Object -First 1)
  Add-Check -Checks $checks -Id "required_check:$required" -Passed $passed -Message "Required check group passed: $required"
}

foreach ($check in $checks) {
  if (-not $check.passed) {
    $failures.Add([string]$check.message) | Out-Null
  }
}

$status = if ($failures.Count -eq 0) { "ready" } else { "blocked" }
$summary = [pscustomobject]@{
  schema_version = [string]$contract.schema_version
  phase = 21
  status = $status
  generated_at = (Get-Date).ToString("o")
  evidence_dir = ConvertTo-ProjectRelativePath $EvidenceDir
  install_root = ConvertTo-ProjectRelativePath $installRoot
  manifest = ConvertTo-ProjectRelativePath $tempManifestPath
  updater = ConvertTo-ProjectRelativePath $tempUpdaterPath
  components = $componentResults
  checksum_failure = [pscustomobject]@{
    exit_code = $failureResult.exit_code
    state = [string]$failedState.state
    failed_update_detected = [bool]$failedState.failed_update_detected
    safe_mode = [bool]$failedState.safe_mode
    log = ConvertTo-ProjectRelativePath $failureLog
  }
  failures = $failures
  checks = $checks
}

$jsonPath = Join-Path $EvidenceDir "release-apply-rollback.json"
$markdownPath = Join-Path $EvidenceDir "release-apply-rollback-summary.md"
$summary | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$markdown = @()
$markdown += "# Release Apply Rollback Evidence"
$markdown += ""
$markdown += "- Status: $status"
$markdown += "- Generated: $($summary.generated_at)"
$markdown += "- Evidence: $($summary.evidence_dir)"
$markdown += "- Install root: $($summary.install_root)"
$markdown += "- Manifest: $($summary.manifest)"
$markdown += "- Updater: $($summary.updater)"
$markdown += "- Checksum failure state: $($summary.checksum_failure.state)"
$markdown += ""
$markdown += "## Components"
$markdown += ""
$markdown += "| Component | Plan | Apply | Rollback | Marker Restored | Stray Removed |"
$markdown += "| --- | --- | --- | --- | --- | --- |"
foreach ($component in $componentResults) {
  $markdown += "| $($component.component) | $($component.plan_state) | $($component.apply_state) | $($component.rollback_state) | $($component.marker_restored) | $($component.stray_removed) |"
}
$markdown += ""
$markdown += "## Checks"
$markdown += ""
$markdown += "| Check | Status | Message |"
$markdown += "| --- | --- | --- |"
foreach ($check in $checks) {
  $checkStatus = if ($check.passed) { "passed" } else { "failed" }
  $message = ([string]$check.message).Replace("|", "\|")
  $markdown += "| $($check.id) | $checkStatus | $message |"
}
$markdown | Set-Content -LiteralPath $markdownPath -Encoding UTF8

$summary | ConvertTo-Json -Depth 20

if ($failures.Count -gt 0) {
  throw "Release apply rollback evidence failed:`n - $($failures -join "`n - ")"
}
