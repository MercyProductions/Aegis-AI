param(
  [string]$Root = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Root)) {
  $ScriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
  $Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $ScriptRoot))
} else {
  $Root = [System.IO.Path]::GetFullPath($Root)
}

$script:Checks = @()
$script:Failures = @()

function Read-ProjectFile {
  param([Parameter(Mandatory = $true)][string]$RelativePath)

  $path = Join-Path $Root $RelativePath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "Required release contract file is missing: $RelativePath"
  }
  return Get-Content -LiteralPath $path -Raw
}

function Add-ReleaseCheck {
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

  Add-ReleaseCheck -Id $Id -Passed ([bool]($Text -match $Pattern)) -Detail $Detail
}

function Assert-VersionString {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [string]$Value,
    [Parameter(Mandatory = $true)][string]$Detail
  )

  Add-ReleaseCheck -Id $Id -Passed ([bool]([string]$Value -match '^\d+\.\d+\.\d+$')) -Detail $Detail
}

function Assert-Component {
  param(
    [Parameter(Mandatory = $true)][object]$Manifest,
    [Parameter(Mandatory = $true)][string]$ComponentId,
    [Parameter(Mandatory = $true)][string]$ExpectedType
  )

  $property = $Manifest.components.PSObject.Properties[$ComponentId]
  Add-ReleaseCheck -Id "manifest-component-$ComponentId" -Passed ($null -ne $property) -Detail "VERSION.json must define component '$ComponentId'."
  if ($null -eq $property) {
    return
  }

  $component = $property.Value
  Assert-VersionString -Id "manifest-component-version-$ComponentId" -Value ([string]$component.version) -Detail "Component '$ComponentId' must use semantic version x.y.z."
  Add-ReleaseCheck -Id "manifest-component-type-$ComponentId" -Passed ([string]$component.type -eq $ExpectedType) -Detail "Component '$ComponentId' must have type '$ExpectedType'."
  Add-ReleaseCheck -Id "manifest-component-min-core-$ComponentId" -Passed (-not [string]::IsNullOrWhiteSpace([string]$component.minimum_compatible_core)) -Detail "Component '$ComponentId' must declare minimum_compatible_core."
  Add-ReleaseCheck -Id "manifest-component-min-schema-$ComponentId" -Passed ([string]$component.minimum_compatible_schema -eq [string]$Manifest.schema_version) -Detail "Component '$ComponentId' must declare the current minimum_compatible_schema."
  Add-ReleaseCheck -Id "manifest-component-package-$ComponentId" -Passed ($null -ne $component.package -and -not [string]::IsNullOrWhiteSpace([string]$component.package.artifact) -and -not [string]::IsNullOrWhiteSpace([string]$component.package.path)) -Detail "Component '$ComponentId' must declare package artifact and path."
}

$manifestPath = Join-Path $Root "VERSION.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
  throw "VERSION.json is required for release validation."
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$buildRelease = Read-ProjectFile "scripts\build-release.ps1"
$updater = Read-ProjectFile "scripts\aegis-update.ps1"
$validator = Read-ProjectFile "scripts\validate-ecosystem.ps1"
$releaseDocs = Read-ProjectFile "docs\RELEASE_PACKAGING_AND_UPDATES.md"
$coreRelease = Read-ProjectFile "aegis-core\aegis_core\release.py"
$coreReleaseTests = Read-ProjectFile "aegis-core\tests\test_release_infrastructure.py"
$desktopContract = Read-ProjectFile "scripts\test-desktop-contract.ps1"
$editorParity = Read-ProjectFile "scripts\test-editor-parity.ps1"

Add-ReleaseCheck -Id "manifest-version" -Passed ([int]$manifest.manifest_version -ge 1) -Detail "VERSION.json must include manifest_version >= 1."
Add-ReleaseCheck -Id "manifest-schema" -Passed ([string]$manifest.schema_version -eq "2026.05.12") -Detail "VERSION.json schema_version must match the current Core contract schema."
Add-ReleaseCheck -Id "manifest-channel" -Passed (-not [string]::IsNullOrWhiteSpace([string]$manifest.release_channel)) -Detail "VERSION.json must declare release_channel."
Add-ReleaseCheck -Id "manifest-components-object" -Passed ($null -ne $manifest.components) -Detail "VERSION.json must define components."
Add-ReleaseCheck -Id "manifest-compatibility-object" -Passed ($null -ne $manifest.compatibility) -Detail "VERSION.json must define compatibility."
Add-ReleaseCheck -Id "manifest-update-policy-object" -Passed ($null -ne $manifest.update_policy) -Detail "VERSION.json must define update_policy."

Assert-Component -Manifest $manifest -ComponentId "aegis-core" -ExpectedType "python-service"
Assert-Component -Manifest $manifest -ComponentId "website" -ExpectedType "web-app"
Assert-Component -Manifest $manifest -ComponentId "desktop" -ExpectedType "native-desktop"
Assert-Component -Manifest $manifest -ComponentId "vscode-extension" -ExpectedType "vscode-vsix"
Assert-Component -Manifest $manifest -ComponentId "visual-studio-extension" -ExpectedType "visual-studio-vsix"

Add-ReleaseCheck -Id "compatibility-api-version" -Passed ([string]$manifest.compatibility.core_api_version -eq "v1") -Detail "Compatibility metadata must declare Core API v1."
Add-ReleaseCheck -Id "compatibility-contract-version" -Passed ([string]$manifest.compatibility.core_contract_version -eq [string]$manifest.schema_version) -Detail "Compatibility contract version must match manifest schema_version."
foreach ($client in @("website", "desktop", "vscode-extension", "visual-studio-extension")) {
  $minimum = $manifest.compatibility.minimum_clients.PSObject.Properties[$client]
  Add-ReleaseCheck -Id "compatibility-minimum-client-$client" -Passed ($null -ne $minimum -and -not [string]::IsNullOrWhiteSpace([string]$minimum.Value)) -Detail "Compatibility metadata must include minimum client version for '$client'."
}

Add-ReleaseCheck -Id "policy-checksum" -Passed ([bool]$manifest.update_policy.requires_checksum) -Detail "Update policy must require checksums."
Add-ReleaseCheck -Id "policy-backup" -Passed ([bool]$manifest.update_policy.backup_before_apply) -Detail "Update policy must require backup before apply."
Add-ReleaseCheck -Id "policy-rollback" -Passed ([bool]$manifest.update_policy.rollback_on_failure) -Detail "Update policy must require rollback on failure."
Add-ReleaseCheck -Id "policy-safe-mode" -Passed ([bool]$manifest.update_policy.safe_mode_supported) -Detail "Update policy must declare safe mode support."

Assert-SourceContains -Id "build-release-skip-build" -Text $buildRelease -Pattern '\[switch\]\$SkipBuild' -Detail "build-release.ps1 must support -SkipBuild for packaging from existing artifacts."
Assert-SourceContains -Id "build-release-version-authority" -Text $buildRelease -Pattern 'VERSION\.json is required before packaging' -Detail "build-release.ps1 must require VERSION.json before packaging."
Assert-SourceContains -Id "build-release-checksums" -Text $buildRelease -Pattern 'Get-FileHash[\s\S]*SHA256[\s\S]*component\.package\.sha256' -Detail "build-release.ps1 must stamp package SHA256 metadata."
Assert-SourceContains -Id "build-release-manifest-output" -Text $buildRelease -Pattern 'version-manifest\.json' -Detail "build-release.ps1 must write version-manifest.json."
Assert-SourceContains -Id "build-release-root-boundary" -Text $buildRelease -Pattern 'rootWithSlash[\s\S]*StartsWith\(\$rootWithSlash' -Detail "build-release.ps1 must guard workspace paths with exact-root/root-with-slash matching."
Assert-SourceContains -Id "build-release-copies-update-tool" -Text $buildRelease -Pattern 'aegis-update\.ps1' -Detail "Release output must include the update launcher."

Assert-SourceContains -Id "update-manifest-trust" -Text $updater -Pattern 'Assert-ReleaseManifestTrust' -Detail "aegis-update.ps1 must validate manifest trust before planning/applying updates."
Assert-SourceContains -Id "update-checksum-required" -Text $updater -Pattern 'Package SHA256 is required before update apply' -Detail "aegis-update.ps1 must require SHA256 before update apply."
Assert-SourceContains -Id "update-checksum-compare" -Text $updater -Pattern 'Package checksum mismatch' -Detail "aegis-update.ps1 must reject checksum mismatches."
Assert-SourceContains -Id "update-backup" -Text $updater -Pattern 'Backup-Target' -Detail "aegis-update.ps1 must create backups before apply."
Assert-SourceContains -Id "update-rollback" -Text $updater -Pattern 'Restore-Backup' -Detail "aegis-update.ps1 must support rollback."
Assert-SourceContains -Id "update-safe-mode" -Text $updater -Pattern 'safe-mode\.json' -Detail "aegis-update.ps1 must support safe mode markers."
Assert-SourceContains -Id "update-security-audit" -Text $updater -Pattern 'security-audit\.jsonl' -Detail "aegis-update.ps1 must write update security audit events."
Assert-SourceContains -Id "update-install-boundary" -Text $updater -Pattern 'installRootWithSlash[\s\S]*StartsWith\(\$installRootWithSlash' -Detail "aegis-update.ps1 must guard install paths with exact-root/root-with-slash matching."
Assert-SourceContains -Id "update-no-downgrade-default" -Text $updater -Pattern 'Downgrade protection blocked' -Detail "aegis-update.ps1 must block downgrades unless explicitly allowed."

Assert-SourceContains -Id "validator-release-tracking" -Text $validator -Pattern 'release-artifact-status\.txt' -Detail "validate-ecosystem.ps1 must capture release artifact status."
Assert-SourceContains -Id "validator-dirty-release-gate" -Text $validator -Pattern 'AllowDirtyReleaseArtifacts' -Detail "validate-ecosystem.ps1 must avoid mutating dirty release artifacts unless explicitly allowed."
Assert-SourceContains -Id "validator-desktop-contract" -Text $validator -Pattern 'test-desktop-contract\.ps1' -Detail "Release validation must include desktop compatibility contract."
Assert-SourceContains -Id "validator-editor-parity" -Text $validator -Pattern 'test-editor-parity\.ps1' -Detail "Release validation must include editor parity contract."
Assert-SourceContains -Id "validator-release-package" -Text $validator -Pattern 'release-package-dry-run' -Detail "Release validation must include package dry-run gate."
Assert-SourceContains -Id "validator-update-plan" -Text $validator -Pattern 'update-plan-dry-run' -Detail "Release validation must include update planner dry-run gate."

Assert-SourceContains -Id "core-release-manifest" -Text $coreRelease -Pattern 'def release_manifest' -Detail "Aegis Core must expose release manifest logic."
Assert-SourceContains -Id "core-release-compatibility" -Text $coreRelease -Pattern 'def check_compatibility' -Detail "Aegis Core must expose release compatibility logic."
Assert-SourceContains -Id "core-release-migrations" -Text $coreRelease -Pattern 'def run_migrations' -Detail "Aegis Core must expose release migrations."
Assert-SourceContains -Id "core-release-update-plan" -Text $coreRelease -Pattern 'def update_plan' -Detail "Aegis Core must expose update plan logic."
Assert-SourceContains -Id "core-release-tests" -Text $coreReleaseTests -Pattern 'test_release_update_plan_requires_checksum_and_lists_rollback' -Detail "Aegis Core release tests must cover checksum and rollback planning."

Assert-SourceContains -Id "docs-release-packaging" -Text $releaseDocs -Pattern 'build-release\.ps1' -Detail "Release docs must document packaging."
Assert-SourceContains -Id "docs-release-update" -Text $releaseDocs -Pattern 'aegis-update\.ps1' -Detail "Release docs must document updates."
Assert-SourceContains -Id "docs-release-rollback" -Text $releaseDocs -Pattern 'Rollback' -Detail "Release docs must document rollback."
Assert-SourceContains -Id "docs-release-migrations" -Text $releaseDocs -Pattern 'Migrations' -Detail "Release docs must document migrations."

Assert-SourceContains -Id "desktop-release-contract" -Text $desktopContract -Pattern 'release-compatibility' -Detail "Desktop release validation must include Core compatibility checks."
Assert-SourceContains -Id "editor-release-contract" -Text $editorParity -Pattern '/v1/release/compatibility' -Detail "Editor parity validation must include Core release compatibility checks."

$summary = [pscustomobject]@{
  root = $Root
  status = if ($script:Failures.Count -eq 0) { "passed" } else { "failed" }
  checked_at = (Get-Date).ToString("o")
  manifest = [pscustomobject]@{
    schema_version = [string]$manifest.schema_version
    release_channel = [string]$manifest.release_channel
    component_count = @($manifest.components.PSObject.Properties).Count
  }
  checks = $script:Checks
}

$summary | ConvertTo-Json -Depth 5

if ($script:Failures.Count -gt 0) {
  throw "Release contract validation failed:`n - $($script:Failures -join "`n - ")"
}
