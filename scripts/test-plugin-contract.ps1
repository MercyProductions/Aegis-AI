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
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\plugin-evidence" (Get-Date -Format "yyyyMMdd-HHmmss"))
} else {
  $EvidenceDir = [System.IO.Path]::GetFullPath($EvidenceDir)
}

$script:Checks = @()
$script:Failures = @()

function Read-ProjectFile {
  param([Parameter(Mandatory = $true)][string]$RelativePath)

  $path = Join-Path $Root $RelativePath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "Required plugin contract file is missing: $RelativePath"
  }
  return Get-Content -LiteralPath $path -Raw
}

function Read-ProjectJson {
  param([Parameter(Mandatory = $true)][string]$RelativePath)

  return Read-ProjectFile $RelativePath | ConvertFrom-Json
}

function Add-PluginCheck {
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

  Add-PluginCheck -Id $Id -Passed ([bool]($Text -match $Pattern)) -Detail $Detail
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
    Add-PluginCheck -Id "$IdPrefix-$item" -Passed ($actual -contains $item) -Detail "$Label must include '$item'."
  }
}

function Assert-JsonManifest {
  param(
    [Parameter(Mandatory = $true)][string]$PluginId,
    [Parameter(Mandatory = $true)][string]$RelativePath
  )

  $manifest = Read-ProjectJson $RelativePath
  Add-PluginCheck -Id "reference-plugin-id-$PluginId" -Passed ([string]$manifest.id -eq $PluginId) -Detail "Reference plugin manifest must preserve id '$PluginId'."
  Add-PluginCheck -Id "reference-plugin-version-$PluginId" -Passed (-not [string]::IsNullOrWhiteSpace([string]$manifest.version)) -Detail "Reference plugin '$PluginId' must declare version."
  Add-PluginCheck -Id "reference-plugin-api-$PluginId" -Passed ([string]$manifest.api_version -eq [string]$contract.core_plugin_runtime.api_version) -Detail "Reference plugin '$PluginId' must use the current plugin API version."
  Add-PluginCheck -Id "reference-plugin-permissions-$PluginId" -Passed (@($manifest.permission_scopes).Count -gt 0) -Detail "Reference plugin '$PluginId' must declare permission scopes."
  Add-PluginCheck -Id "reference-plugin-compatibility-$PluginId" -Passed ($null -ne $manifest.runtime_compatibility -and -not [string]::IsNullOrWhiteSpace([string]$manifest.runtime_compatibility.min_core_version)) -Detail "Reference plugin '$PluginId' must declare Core runtime compatibility."
  Add-PluginCheck -Id "reference-plugin-package-$PluginId" -Passed ($null -ne $manifest.package -and -not [string]::IsNullOrWhiteSpace([string]$manifest.package.checksum) -and -not [string]::IsNullOrWhiteSpace([string]$manifest.package.signature)) -Detail "Reference plugin '$PluginId' must declare checksum and signature metadata."
}

$contract = Read-ProjectJson "evals\phase13-plugin-productization-contract.json"
$pluginRuntime = Read-ProjectFile "aegis-core\aegis_core\plugin_runtime.py"
$coreServer = Read-ProjectFile "aegis-core\aegis_core\server.py"
$coreContracts = Read-ProjectFile "aegis-core\aegis_core\contracts.py"
$ecosystemMaturity = Read-ProjectFile "aegis-core\aegis_core\ecosystem_maturity.py"
$corePluginTests = Read-ProjectFile "aegis-core\tests\test_plugin_runtime.py"
$coreEcosystemTests = Read-ProjectFile "aegis-core\tests\test_ecosystem_maturity.py"
$productization = Read-ProjectFile "website\backend\aegis_ai\productization.py"
$ecosystem = Read-ProjectFile "website\backend\aegis_ai\ecosystem.py"
$productizationRoutes = Read-ProjectFile "website\backend\aegis_ai\routes\productization.py"
$ecosystemRoutes = Read-ProjectFile "website\backend\aegis_ai\routes\ecosystem.py"
$productizationTests = Read-ProjectFile "website\backend\tests\test_productization.py"
$ecosystemTests = Read-ProjectFile "website\backend\tests\test_ecosystem.py"
$pluginDocs = Read-ProjectFile "docs\PLUGIN_ECOSYSTEM.md"
$workspaceSafety = Read-ProjectFile "docs\WORKSPACE_SAFETY.md"
$validator = Read-ProjectFile "scripts\validate-ecosystem.ps1"

Add-PluginCheck -Id "contract-schema-version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Detail "Phase 13 plugin contract must use the current schema version."
Add-PluginCheck -Id "contract-evidence-root" -Passed ([string]$contract.evidence_root -eq ".aegis/plugin-evidence") -Detail "Phase 13 plugin evidence must have a stable .aegis root."
Add-PluginCheck -Id "contract-core-api-version" -Passed ([string]$contract.core_plugin_runtime.api_version -eq "2026.05.12") -Detail "Phase 13 contract must pin the current Core plugin API version."

foreach ($file in @($contract.required_contract_files)) {
  $relativePath = [string]$file
  Add-PluginCheck -Id "contract-file-$($relativePath.Replace('/', '-').Replace('\', '-'))" -Passed (Test-Path -LiteralPath (Join-Path $Root $relativePath) -PathType Leaf) -Detail "Required Phase 13 contract file must exist: $relativePath"
}

Assert-SetIncludes -IdPrefix "manifest-name" -Values @($contract.core_plugin_runtime.manifest_names) -Required @("aegis-plugin.json", "plugin.json", "manifest.json") -Label "Plugin manifest names"
Assert-SetIncludes -IdPrefix "manifest-field" -Values @($contract.core_plugin_runtime.required_manifest_fields) -Required @("id", "name", "version", "api_version", "category", "capabilities", "permission_scopes") -Label "Plugin manifest required fields"
Assert-SetIncludes -IdPrefix "plugin-category" -Values @($contract.core_plugin_runtime.categories) -Required @("model_providers", "workflow_types", "analyzers", "validators", "repair_strategies", "project_templates", "media_generators", "ide_integrations", "deployment_tools", "observability_tools") -Label "Plugin categories"
Assert-SetIncludes -IdPrefix "permission-scope" -Values @($contract.core_plugin_runtime.permission_scopes) -Required @("filesystem_read", "filesystem_write", "network_access", "model_access", "workspace_scan", "process_execution", "validation_execution", "ui_extension", "observability_read", "provider_credentials") -Label "Plugin permission scopes"
Assert-SetIncludes -IdPrefix "high-risk-scope" -Values @($contract.core_plugin_runtime.high_risk_scopes) -Required @("filesystem_write", "network_access", "process_execution", "validation_execution", "provider_credentials") -Label "Plugin high-risk scopes"
Assert-SetIncludes -IdPrefix "builtin-handler" -Values @($contract.core_plugin_runtime.builtin_handlers) -Required @("builtin.echo", "builtin.validation_hint", "builtin.architecture_summary", "builtin.roadmap_hint", "builtin.provider_status", "builtin.observability_snapshot") -Label "Plugin builtin handlers"

Assert-SetIncludes -IdPrefix "lifecycle-guard" -Values @($contract.lifecycle_guards | ForEach-Object { $_.id }) -Required @("manifest_discovery", "manifest_validation", "trust_before_high_risk_enable", "approval_before_high_risk_tool", "external_handler_block", "observability_audit", "disable_as_safe_removal") -Label "Plugin lifecycle guards"

Assert-SourceContains -Id "runtime-api-version" -Text $pluginRuntime -Pattern 'PLUGIN_API_VERSION\s*=\s*"2026\.05\.12"' -Detail "Core plugin runtime must pin the current plugin API version."
Assert-SourceContains -Id "runtime-core-version" -Text $pluginRuntime -Pattern 'CORE_RUNTIME_VERSION\s*=\s*"0\.1\.0"' -Detail "Core plugin runtime must declare runtime compatibility version."
Assert-SourceContains -Id "runtime-manifest-names" -Text $pluginRuntime -Pattern 'PLUGIN_MANIFEST_NAMES[\s\S]*aegis-plugin\.json[\s\S]*plugin\.json[\s\S]*manifest\.json' -Detail "Core plugin runtime must discover supported manifest names."
Assert-SourceContains -Id "runtime-state-file" -Text $pluginRuntime -Pattern 'PLUGIN_STATE_FILE\s*=\s*"plugin-state\.json"' -Detail "Core plugin runtime must persist plugin state."
Assert-SourceContains -Id "runtime-observability-file" -Text $pluginRuntime -Pattern 'PLUGIN_OBSERVABILITY_FILE\s*=\s*"plugin-observability\.jsonl"' -Detail "Core plugin runtime must persist plugin observability."
Assert-SourceContains -Id "runtime-no-code-import" -Text $pluginRuntime -Pattern '"code_execution": False[\s\S]*"external_processes": False' -Detail "Core plugin runtime must keep manifest-only isolation defaults."
Assert-SourceContains -Id "runtime-external-handler-block" -Text $pluginRuntime -Pattern 'Plugin code execution is disabled until an isolated external sandbox is available' -Detail "Core plugin runtime must block non-builtin handlers."
Assert-SourceContains -Id "runtime-high-risk-enable-block" -Text $pluginRuntime -Pattern 'plugin\.enable_blocked[\s\S]*Approval and trust are required for high-risk plugin scopes' -Detail "Core plugin runtime must block high-risk enable without approval or trust."
Assert-SourceContains -Id "runtime-high-risk-tool-block" -Text $pluginRuntime -Pattern 'User approval is required before running high-risk plugin tool scopes' -Detail "Core plugin runtime must block high-risk tool runs without approval."
Assert-SourceContains -Id "runtime-compat-min" -Text $pluginRuntime -Pattern 'Plugin requires Core >=' -Detail "Core plugin runtime must reject plugins requiring a future Core."
Assert-SourceContains -Id "runtime-compat-max" -Text $pluginRuntime -Pattern 'Plugin supports Core only through' -Detail "Core plugin runtime must reject plugins outside max Core compatibility."
Assert-SourceContains -Id "runtime-checksum" -Text $pluginRuntime -Pattern 'computed_checksum[\s\S]*Plugin manifest checksum does not match' -Detail "Core plugin runtime must validate package checksums."
Assert-SourceContains -Id "runtime-packaging-format" -Text $pluginRuntime -Pattern 'signature_fields[\s\S]*update_metadata[\s\S]*arbitrary plugin code is not imported' -Detail "Core plugin runtime must expose packaging/signing/update metadata."

foreach ($endpoint in @("/v1/plugins", "/v1/plugins/state", "/v1/plugins/hooks", "/v1/plugins/tools/run")) {
  Assert-SourceContains -Id "core-endpoint-$($endpoint.Trim('/').Replace('/', '-'))" -Text $coreServer -Pattern ([regex]::Escape($endpoint)) -Detail "Core must expose plugin endpoint $endpoint."
}
foreach ($kind in @("plugin.dashboard", "plugin.state", "plugin.tool.run", "plugin.hooks")) {
  Assert-SourceContains -Id "core-contract-$kind" -Text $coreContracts -Pattern ([regex]::Escape($kind)) -Detail "Core contracts must register $kind."
}

Assert-SourceContains -Id "ecosystem-maturity-quality" -Text $ecosystemMaturity -Pattern 'plugin_ecosystem_quality' -Detail "Core ecosystem maturity must expose plugin quality scoring."
Assert-SourceContains -Id "ecosystem-maturity-badges" -Text $ecosystemMaturity -Pattern 'compatibility_badges[\s\S]*permission_transparency[\s\S]*review_tools' -Detail "Core ecosystem maturity must expose compatibility badges and review tools."
Assert-SourceContains -Id "ecosystem-maturity-showcase" -Text $ecosystemMaturity -Pattern 'plugin_workflow' -Detail "Core ecosystem maturity must include a plugin workflow showcase."

$referencePluginRoot = "aegis-core\example-plugins"
Assert-JsonManifest -PluginId "aegis-custom-validator" -RelativePath "$referencePluginRoot\custom-validator\aegis-plugin.json"
Assert-JsonManifest -PluginId "aegis-architecture-analyzer" -RelativePath "$referencePluginRoot\architecture-analyzer\aegis-plugin.json"
Assert-JsonManifest -PluginId "aegis-local-provider-adapter" -RelativePath "$referencePluginRoot\local-provider-adapter\aegis-plugin.json"
Assert-JsonManifest -PluginId "aegis-roadmap-enhancement" -RelativePath "$referencePluginRoot\roadmap-enhancement\aegis-plugin.json"
Assert-JsonManifest -PluginId "aegis-observability-widget" -RelativePath "$referencePluginRoot\observability-widget\aegis-plugin.json"
Assert-SourceContains -Id "reference-source-drop-provider" -Text (Read-ProjectFile "$referencePluginRoot\local-provider-adapter\aegis-plugin.json") -Pattern 'provider_extensions[\s\S]*provider_type[\s\S]*local' -Detail "Reference provider plugin must model source-drop/local provider extension metadata."

Assert-SourceContains -Id "core-tests-dashboard" -Text $corePluginTests -Pattern 'test_plugin_dashboard_discovers_reference_plugins_and_contracts' -Detail "Core plugin tests must cover dashboard/reference plugin discovery."
Assert-SourceContains -Id "core-tests-high-risk-enable" -Text $corePluginTests -Pattern 'test_high_risk_plugin_enable_requires_approval' -Detail "Core plugin tests must cover high-risk enable approval."
Assert-SourceContains -Id "core-tests-high-risk-tool" -Text $corePluginTests -Pattern 'test_tool_execution_blocks_high_risk_without_approval_then_runs_builtin_handler' -Detail "Core plugin tests must cover high-risk tool approval and builtin execution."
Assert-SourceContains -Id "core-tests-isolation" -Text $corePluginTests -Pattern 'test_plugin_failure_isolation_for_bad_manifest_and_external_handler' -Detail "Core plugin tests must cover bad manifest and external handler isolation."
Assert-SourceContains -Id "core-tests-compatibility" -Text $corePluginTests -Pattern 'test_compatibility_rejection_and_workflow_hook_filtering' -Detail "Core plugin tests must cover compatibility rejection and hook filtering."
Assert-SourceContains -Id "core-tests-ecosystem-maturity" -Text $coreEcosystemTests -Pattern 'test_workflow_plugin_observability_and_maturity_scores' -Detail "Core ecosystem tests must cover plugin maturity scoring."

Assert-SourceContains -Id "productization-stable-api" -Text $productization -Pattern 'plugin\.sdk\.v1' -Detail "Website productization must expose Plugin SDK stable API metadata."
Assert-SourceContains -Id "productization-high-risk-sandbox" -Text $productization -Pattern 'High-risk plugin permissions require isolated, sandbox, or restricted sandbox_profile' -Detail "Website productization must require sandbox isolation for high-risk plugin permissions."
Assert-SourceContains -Id "productization-high-risk-trust" -Text $productization -Pattern 'Enabled plugins with high-risk permissions must be explicitly trusted' -Detail "Website productization must require trust for enabled high-risk plugins."
Assert-SourceContains -Id "productization-signing-policy" -Text $productization -Pattern 'plugin_signing_required[\s\S]*Plugin signature and signing_key_fingerprint are required by policy' -Detail "Website productization must enforce plugin signing policy."
Assert-SourceContains -Id "productization-lifecycle-hook-permissions" -Text $productization -Pattern 'Lifecycle hook[\s\S]*asks for permissions not granted by the manifest' -Detail "Website productization must validate lifecycle hook permissions."

foreach ($route in @("/api/productization/plugins", "/api/productization/plugins/validate", "/api/productization/plugins/register", "/api/productization/plugins/{plugin_id}/enable", "/api/productization/plugins/{plugin_id}/disable", "/api/productization/plugins/{plugin_id}/trust")) {
  Assert-SourceContains -Id "productization-route-$($route.Replace('/', '-').Replace('{', '').Replace('}', ''))" -Text $productizationRoutes -Pattern ([regex]::Escape($route)) -Detail "Website productization routes must expose $route."
}
Assert-SourceContains -Id "productization-tests-lifecycle" -Text $productizationTests -Pattern 'test_api_hardening_snapshot_plugin_lifecycle_and_policy' -Detail "Website productization tests must cover plugin lifecycle and policy API."
Assert-SourceContains -Id "productization-tests-risk" -Text $productizationTests -Pattern 'test_plugin_validation_blocks_risky_unsandboxed_manifest' -Detail "Website productization tests must cover risky unsandboxed plugin validation."

Assert-SourceContains -Id "ecosystem-high-risk-package" -Text $ecosystem -Pattern 'HIGH_RISK_PACKAGE_PERMISSIONS' -Detail "Website ecosystem must define high-risk package permissions."
Assert-SourceContains -Id "ecosystem-trust-score" -Text $ecosystem -Pattern 'TRUST_SCORE' -Detail "Website ecosystem must score package trust levels."
Assert-SourceContains -Id "ecosystem-marketplace" -Text $ecosystem -Pattern 'def marketplace_catalog' -Detail "Website ecosystem must expose a marketplace catalog."
Assert-SourceContains -Id "ecosystem-signed-policy" -Text $ecosystem -Pattern 'require_signed_packages[\s\S]*Package signature and signing_key_fingerprint are required by organization policy' -Detail "Website ecosystem must enforce signed package policy."
Assert-SourceContains -Id "ecosystem-high-risk-sandbox" -Text $ecosystem -Pattern 'High-risk package permissions require isolated, sandbox, or restricted sandbox_permissions' -Detail "Website ecosystem must require sandbox isolation for high-risk packages."
Assert-SourceContains -Id "ecosystem-high-risk-trust" -Text $ecosystem -Pattern 'Enabled high-risk ecosystem packages must be trusted, organization-approved, or signed' -Detail "Website ecosystem must require trust for enabled high-risk packages."
Assert-SourceContains -Id "ecosystem-reproducibility" -Text $ecosystem -Pattern 'def create_reproducibility_record' -Detail "Website ecosystem must create reproducibility records."
Assert-SourceContains -Id "ecosystem-audit" -Text $ecosystem -Pattern 'record_ecosystem_audit_event' -Detail "Website ecosystem must audit package/workflow/profile lifecycle events."

foreach ($route in @($contract.ecosystem_routes)) {
  Assert-SourceContains -Id "ecosystem-route-$($route.Replace('/', '-').Replace('{', '').Replace('}', ''))" -Text $ecosystemRoutes -Pattern ([regex]::Escape([string]$route)) -Detail "Website ecosystem routes must expose $route."
}
Assert-SourceContains -Id "ecosystem-tests-lifecycle" -Text $ecosystemTests -Pattern 'test_api_ecosystem_snapshot_lifecycle_workflow_policy_and_search' -Detail "Website ecosystem tests must cover marketplace, package lifecycle, workflows, profiles, policy, search, reproducibility, and audit."
Assert-SourceContains -Id "ecosystem-tests-risk" -Text $ecosystemTests -Pattern 'test_risky_package_requires_sandbox_and_trust' -Detail "Website ecosystem tests must cover risky package sandbox/trust validation."

Assert-SourceContains -Id "docs-contract" -Text $pluginDocs -Pattern 'phase13-plugin-productization-contract\.json' -Detail "Plugin docs must link the Phase 13 machine-readable contract."
Assert-SourceContains -Id "docs-evidence-root" -Text $pluginDocs -Pattern '\.aegis/plugin-evidence' -Detail "Plugin docs must document the plugin evidence root."
Assert-SourceContains -Id "docs-lifecycle-matrix" -Text $pluginDocs -Pattern 'Lifecycle Matrix' -Detail "Plugin docs must document the lifecycle matrix."
Assert-SourceContains -Id "docs-no-arbitrary-code" -Text $pluginDocs -Pattern 'No arbitrary Python, JavaScript, native, or shell plugin code is loaded' -Detail "Plugin docs must keep the no-arbitrary-code limit explicit."
Assert-SourceContains -Id "docs-safe-removal" -Text $pluginDocs -Pattern 'Disable is the safe removal path' -Detail "Plugin docs must explain disable as the current safe removal path."
Assert-SourceContains -Id "workspace-safety-plugin-boundary" -Text $workspaceSafety -Pattern 'Plugin Boundary[\s\S]*does not execute plugin code[\s\S]*approval' -Detail "Workspace safety docs must keep plugin boundaries explicit."
Assert-SourceContains -Id "validator-plugin-contract-gate" -Text $validator -Pattern 'test-plugin-contract\.ps1' -Detail "Ecosystem validation must run the Phase 13 plugin contract gate."

$summary = [pscustomobject]@{
  root = $Root
  status = if ($script:Failures.Count -eq 0) { "passed" } else { "failed" }
  checked_at = (Get-Date).ToString("o")
  evidence_dir = $EvidenceDir
  contract = [pscustomobject]@{
    schema_version = [string]$contract.schema_version
    api_version = [string]$contract.core_plugin_runtime.api_version
    reference_plugin_count = @($contract.reference_plugins).Count
    productization_route_count = @($contract.productization_routes).Count
    ecosystem_route_count = @($contract.ecosystem_routes).Count
  }
  checks = $script:Checks
}

New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$summaryPath = Join-Path $EvidenceDir "plugin-contract.json"
$markdownPath = Join-Path $EvidenceDir "plugin-contract-summary.md"
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 13 Plugin Productization Contract"
$markdown += ""
$markdown += "- Status: $($summary.status)"
$markdown += "- Checked at: $($summary.checked_at)"
$markdown += "- Plugin API version: $($summary.contract.api_version)"
$markdown += "- Reference plugins: $($summary.contract.reference_plugin_count)"
$markdown += "- Productization routes: $($summary.contract.productization_route_count)"
$markdown += "- Ecosystem routes: $($summary.contract.ecosystem_route_count)"
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
  throw "Plugin productization contract validation failed:`n - $($script:Failures -join "`n - ")"
}
