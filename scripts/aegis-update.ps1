param(
  [string]$Manifest = "release\version-manifest.json",
  [string]$Component,
  [string]$PackagePath = "",
  [string]$InstallRoot = "",
  [string]$BackupRoot = "",
  [switch]$Apply,
  [switch]$Rollback,
  [switch]$SafeMode,
  [switch]$AllowDowngrade
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
  $InstallRoot = $RepoRoot
}
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
if ([string]::IsNullOrWhiteSpace($BackupRoot)) {
  $BackupRoot = Join-Path $InstallRoot ".aegis\updates"
}
$BackupRoot = [System.IO.Path]::GetFullPath($BackupRoot)
$StateRoot = Join-Path $InstallRoot ".aegis"
$StatePath = Join-Path $StateRoot "update-state.json"

function Assert-UnderInstall {
  param([string]$Path)
  $full = [System.IO.Path]::GetFullPath($Path)
  $installRootWithSlash = $InstallRoot.TrimEnd("\") + "\"
  if (-not $full.Equals($InstallRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
      -not $full.StartsWith($installRootWithSlash, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to operate outside install root: $full"
  }
  return $full
}

function Ensure-Directory {
  param([string]$Path)
  $full = Assert-UnderInstall $Path
  New-Item -ItemType Directory -Force -Path $full | Out-Null
  return $full
}

function Write-UpdateState {
  param([hashtable]$State)
  Ensure-Directory $StateRoot | Out-Null
  $State.updated_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  $State | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $StatePath -Encoding UTF8
}

function Write-SecurityAudit {
  param([string]$Event, [string]$Status, [string]$Detail, [hashtable]$Metadata = @{})
  try {
    Ensure-Directory $StateRoot | Out-Null
    $audit = @{
      timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
      event = $Event
      status = $Status
      detail = $Detail
      metadata = $Metadata
    }
    ($audit | ConvertTo-Json -Depth 20 -Compress) | Add-Content -LiteralPath (Join-Path $StateRoot "security-audit.jsonl") -Encoding UTF8
  } catch {
    # Security audit writes should never hide the update failure itself.
  }
}

function Read-JsonFile {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) {
    return $null
  }
  return Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
}

function Compare-Version {
  param([string]$Left, [string]$Right)
  $leftParts = [regex]::Matches([string]$Left, '\d+') | ForEach-Object { [int]$_.Value }
  $rightParts = [regex]::Matches([string]$Right, '\d+') | ForEach-Object { [int]$_.Value }
  $max = [Math]::Max([Math]::Max($leftParts.Count, $rightParts.Count), 1)
  for ($i = 0; $i -lt $max; $i++) {
    $l = if ($i -lt $leftParts.Count) { $leftParts[$i] } else { 0 }
    $r = if ($i -lt $rightParts.Count) { $rightParts[$i] } else { 0 }
    if ($l -lt $r) { return -1 }
    if ($l -gt $r) { return 1 }
  }
  return 0
}

function Get-InstalledComponentVersion {
  param([string]$ComponentId)
  $releaseState = Read-JsonFile (Join-Path $StateRoot "release-state.json")
  if ($null -ne $releaseState -and $null -ne $releaseState.components) {
    $property = $releaseState.components.PSObject.Properties[$ComponentId]
    if ($null -ne $property -and -not [string]::IsNullOrWhiteSpace([string]$property.Value.version)) {
      return [string]$property.Value.version
    }
  }
  return ""
}

function Read-Manifest {
  param([string]$Location)
  if ($Location -match '^https?://') {
    $downloadPath = Join-Path (Ensure-Directory (Join-Path $BackupRoot "downloads")) "manifest.json"
    Invoke-WebRequest -Uri $Location -OutFile $downloadPath
    return Read-JsonFile $downloadPath
  }
  $path = $Location
  if (-not [System.IO.Path]::IsPathRooted($path)) {
    $path = Join-Path $InstallRoot $path
  }
  return Read-JsonFile ([System.IO.Path]::GetFullPath($path))
}

function Get-ComponentInfo {
  param([object]$ManifestObject, [string]$ComponentId)
  if ($null -eq $ManifestObject -or $null -eq $ManifestObject.components) {
    throw "Release manifest is missing components."
  }
  $property = $ManifestObject.components.PSObject.Properties[$ComponentId]
  if ($null -eq $property) {
    throw "Release manifest does not contain component '$ComponentId'."
  }
  return $property.Value
}

function Assert-ReleaseManifestTrust {
  param([object]$ManifestObject, [string]$ComponentId, [object]$ComponentInfo, [string]$PackageLocation, [string]$PackageName, [string]$ExpectedSha)
  if ($null -eq $ManifestObject -or [int]$ManifestObject.manifest_version -lt 1) {
    throw "Release manifest is missing a valid manifest_version."
  }
  if ([string]::IsNullOrWhiteSpace([string]$ManifestObject.schema_version)) {
    throw "Release manifest is missing schema_version."
  }
  if ($null -eq $ComponentInfo.package) {
    throw "Component '$ComponentId' is missing package metadata."
  }
  $artifact = [string]$ComponentInfo.package.artifact
  if ([string]::IsNullOrWhiteSpace($artifact)) {
    throw "Component '$ComponentId' package artifact is missing."
  }
  if (-not [string]::Equals($artifact, $PackageName, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Package artifact mismatch. Manifest declares '$artifact' but update resolved '$PackageName'."
  }
  if (-not [string]::IsNullOrWhiteSpace($ExpectedSha) -and $ExpectedSha -notmatch '^[a-fA-F0-9]{64}$') {
    throw "Package SHA256 must be a 64-character hex digest."
  }
  $installedVersion = Get-InstalledComponentVersion $ComponentId
  $targetVersion = [string]$ComponentInfo.version
  if (-not $AllowDowngrade -and -not [string]::IsNullOrWhiteSpace($installedVersion) -and -not [string]::IsNullOrWhiteSpace($targetVersion)) {
    if ((Compare-Version $targetVersion $installedVersion) -lt 0) {
      throw "Downgrade protection blocked $ComponentId $installedVersion -> $targetVersion. Re-run with -AllowDowngrade only after explicit approval."
    }
  }
  if ($Apply -and $PackageLocation -notmatch '^https?://' -and -not (Test-Path -LiteralPath $PackageLocation)) {
    throw "Package not found during trust validation: $PackageLocation"
  }
}

function Get-ComponentTarget {
  param([string]$ComponentId)
  switch ($ComponentId) {
    "aegis-core" { return Join-Path $InstallRoot "aegis-core" }
    "website" { return Join-Path $InstallRoot "website" }
    "desktop" { return Join-Path $InstallRoot "x64\Release" }
    "vscode-extension" { return Join-Path $InstallRoot "vscode-plugins\aegis-local-autopilot\release" }
    "visual-studio-extension" { return Join-Path $InstallRoot "visual-studio-extensions\aegis-local-agent-vs\release" }
    default { throw "Unknown component target '$ComponentId'." }
  }
}

function Resolve-Package {
  param([object]$ComponentInfo, [string]$Override)
  if (-not [string]::IsNullOrWhiteSpace($Override)) {
    return $Override
  }
  $candidate = [string]$ComponentInfo.package.path
  if ([string]::IsNullOrWhiteSpace($candidate)) {
    throw "Component package path is missing."
  }
  if ($candidate -match '^https?://') {
    return $candidate
  }
  if ([System.IO.Path]::IsPathRooted($candidate)) {
    return $candidate
  }
  return Join-Path $InstallRoot $candidate
}

function Get-LocalPackage {
  param([string]$Location, [string]$FileName)
  $downloads = Ensure-Directory (Join-Path $BackupRoot "downloads")
  if ($Location -match '^https?://') {
    $destination = Join-Path $downloads $FileName
    Invoke-WebRequest -Uri $Location -OutFile $destination
    return $destination
  }
  $path = $Location
  if (-not [System.IO.Path]::IsPathRooted($path)) {
    $path = Join-Path $InstallRoot $path
  }
  if (-not (Test-Path -LiteralPath $path)) {
    throw "Package not found: $path"
  }
  $destination = Join-Path $downloads ([System.IO.Path]::GetFileName($path))
  Copy-Item -LiteralPath $path -Destination $destination -Force
  return $destination
}

function Test-Checksum {
  param([string]$Path, [string]$ExpectedHash)
  if ([string]::IsNullOrWhiteSpace($ExpectedHash)) {
    throw "Package SHA256 is required before update apply."
  }
  $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
  if (-not [string]::Equals($actual, $ExpectedHash.ToLowerInvariant(), [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Package checksum mismatch. Expected $ExpectedHash, got $actual."
  }
  return $actual
}

function Test-SignaturePolicy {
  param([string]$Path, [object]$ManifestObject)
  $optional = $true
  if ($null -ne $ManifestObject.update_policy -and $null -ne $ManifestObject.update_policy.signature_optional_for_local_builds) {
    $optional = [bool]$ManifestObject.update_policy.signature_optional_for_local_builds
  }
  try {
    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($signature.Status -eq "Valid") {
      return "valid"
    }
    if (-not $optional) {
      throw "Package signature is not valid: $($signature.Status)"
    }
    return "not-signed-local-allowed"
  } catch {
    if (-not $optional) {
      throw
    }
    return "signature-check-unavailable-local-allowed"
  }
}

function Backup-Target {
  param([string]$Target, [string]$ComponentId)
  $timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
  $backup = Join-Path (Ensure-Directory (Join-Path $BackupRoot "backups")) "$ComponentId-$timestamp"
  New-Item -ItemType Directory -Force -Path $backup | Out-Null
  if (Test-Path -LiteralPath $Target) {
    foreach ($item in @(Get-ChildItem -LiteralPath $Target -Force)) {
      Copy-Item -LiteralPath $item.FullName -Destination $backup -Recurse -Force
    }
  }
  return $backup
}

function Apply-Package {
  param([string]$ComponentId, [string]$Package, [string]$Target)
  Ensure-Directory $Target | Out-Null
  if ($Package.EndsWith(".vsix", [System.StringComparison]::OrdinalIgnoreCase)) {
    Copy-Item -LiteralPath $Package -Destination (Join-Path $Target ([System.IO.Path]::GetFileName($Package))) -Force
    return
  }

  $stage = Join-Path (Ensure-Directory (Join-Path $BackupRoot "staging")) "$ComponentId-current"
  if (Test-Path -LiteralPath $stage) {
    Remove-Item -LiteralPath (Assert-UnderInstall $stage) -Recurse -Force
  }
  New-Item -ItemType Directory -Force -Path $stage | Out-Null
  Expand-Archive -LiteralPath $Package -DestinationPath $stage -Force
  Copy-Item -LiteralPath (Join-Path $stage "*") -Destination $Target -Recurse -Force
}

function Restore-Backup {
  $state = Read-JsonFile $StatePath
  if ($null -eq $state -or [string]::IsNullOrWhiteSpace($state.backup_path) -or [string]::IsNullOrWhiteSpace($state.target_path)) {
    throw "No rollback backup is recorded in $StatePath."
  }
  $backup = [System.IO.Path]::GetFullPath([string]$state.backup_path)
  $target = Assert-UnderInstall ([string]$state.target_path)
  if (-not (Test-Path -LiteralPath $backup)) {
    throw "Recorded backup does not exist: $backup"
  }
  if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
  }
  Ensure-Directory $target | Out-Null
  foreach ($item in @(Get-ChildItem -LiteralPath $backup -Force)) {
    Copy-Item -LiteralPath $item.FullName -Destination $target -Recurse -Force
  }
  Write-UpdateState @{
    state = "rolled_back"
    component = [string]$state.component
    target_path = $target
    backup_path = $backup
    failed_update_detected = $false
    safe_mode = $false
    message = "Rollback restored the recorded backup."
  }
  Write-Host "Rollback restored $target from $backup"
}

if ($SafeMode) {
  Ensure-Directory $StateRoot | Out-Null
  @{
    enabled = $true
    reason = "Requested by aegis-update.ps1"
    updated_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  } | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $StateRoot "safe-mode.json") -Encoding UTF8
}

if ($Rollback) {
  Restore-Backup
  return
}

if ([string]::IsNullOrWhiteSpace($Component)) {
  throw "-Component is required unless -Rollback is used."
}

$ManifestObject = Read-Manifest $Manifest
$ComponentInfo = Get-ComponentInfo $ManifestObject $Component
$PackageLocation = Resolve-Package $ComponentInfo $PackagePath
$PackageName = if (-not [string]::IsNullOrWhiteSpace($ComponentInfo.package.artifact)) { [string]$ComponentInfo.package.artifact } else { [System.IO.Path]::GetFileName($PackageLocation) }
$Target = Assert-UnderInstall (Get-ComponentTarget $Component)
$ExpectedSha = [string]$ComponentInfo.package.sha256
Assert-ReleaseManifestTrust $ManifestObject $Component $ComponentInfo $PackageLocation $PackageName $ExpectedSha

$plan = @{
  state = if ($Apply) { "ready_to_apply" } else { "planned" }
  component = $Component
  target_version = [string]$ComponentInfo.version
  package = $PackageLocation
  target_path = $Target
  backup_root = $BackupRoot
  checksum_required = $true
  signature_optional_for_local_builds = [bool]$ManifestObject.update_policy.signature_optional_for_local_builds
  safe_mode = [bool]$SafeMode
  downgrade_allowed = [bool]$AllowDowngrade
  trust = @{
    manifest_validation = $true
    checksum_required = $true
    downgrade_protection = -not [bool]$AllowDowngrade
    tamper_detection = "manifest artifact and SHA256"
  }
}

if (-not $Apply) {
  $plan | ConvertTo-Json -Depth 20
  return
}

try {
  $LocalPackage = Get-LocalPackage $PackageLocation $PackageName
  $ActualSha = Test-Checksum $LocalPackage $ExpectedSha
  $SignatureStatus = Test-SignaturePolicy $LocalPackage $ManifestObject
  Write-SecurityAudit "update.package_verified" "ok" "Package checksum and signature policy verified." @{
    component = $Component
    target_version = [string]$ComponentInfo.version
    sha256 = $ActualSha
    signature_status = $SignatureStatus
  }
  $BackupPath = Backup-Target $Target $Component
  Write-UpdateState @{
    state = "pending"
    component = $Component
    target_version = [string]$ComponentInfo.version
    package = $LocalPackage
    target_path = $Target
    backup_path = $BackupPath
    sha256 = $ActualSha
    signature_status = $SignatureStatus
    failed_update_detected = $false
    safe_mode = [bool]$SafeMode
  }
  Apply-Package $Component $LocalPackage $Target
  Write-UpdateState @{
    state = "success"
    component = $Component
    target_version = [string]$ComponentInfo.version
    package = $LocalPackage
    target_path = $Target
    backup_path = $BackupPath
    sha256 = $ActualSha
    signature_status = $SignatureStatus
    failed_update_detected = $false
    rollback_available = $true
    safe_mode = [bool]$SafeMode
  }
  Write-Host "Updated $Component at $Target. Backup: $BackupPath"
} catch {
  Write-SecurityAudit "update.failed_security_check" "failed" $_.Exception.Message @{
    component = $Component
    target_version = [string]$ComponentInfo.version
  }
  Write-UpdateState @{
    state = "failed"
    component = $Component
    target_version = [string]$ComponentInfo.version
    package = $PackageLocation
    target_path = $Target
    failed_update_detected = $true
    safe_mode = $true
    last_error = $_.Exception.Message
  }
  throw
}
