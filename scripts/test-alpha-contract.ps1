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
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\alpha-evidence" (Get-Date -Format "yyyyMMdd-HHmmss"))
} else {
  $EvidenceDir = [System.IO.Path]::GetFullPath($EvidenceDir)
}

$script:Checks = @()
$script:Failures = @()

function Read-ProjectFile {
  param([Parameter(Mandatory = $true)][string]$RelativePath)

  $path = Join-Path $Root $RelativePath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "Required alpha contract file is missing: $RelativePath"
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

function Add-AlphaCheck {
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

  Add-AlphaCheck -Id $Id -Passed ([bool]($Text -match $Pattern)) -Detail $Detail
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
    Add-AlphaCheck -Id "$IdPrefix-$(ConvertTo-CheckId $item)" -Passed ($actual -contains $item) -Detail "$Label must include '$item'."
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
    Add-AlphaCheck -Id "$IdPrefix-$(ConvertTo-CheckId $item)" -Passed ($actual -contains $item) -Detail "$Label must include '$item'."
  }
}

function Assert-ApiPathsInSource {
  param(
    [Parameter(Mandatory = $true)][string]$IdPrefix,
    [Parameter(Mandatory = $true)][object[]]$Apis,
    [Parameter(Mandatory = $true)][string]$Text,
    [Parameter(Mandatory = $true)][string]$Label
  )

  foreach ($api in $Apis) {
    $apiText = [string]$api
    $match = [regex]::Match($apiText, "/v1/[^\s]+")
    Add-AlphaCheck -Id "$IdPrefix-$(ConvertTo-CheckId $apiText)" -Passed ($match.Success -and [bool]($Text -match [regex]::Escape($match.Value))) -Detail "$Label must expose $apiText."
  }
}

$contract = Read-ProjectJson "evals\phase14-alpha-readiness-contract.json"
$alphaDocs = Read-ProjectFile "docs\CONTROLLED_EXTERNAL_ALPHA.md"
$dogfoodingDocs = Read-ProjectFile "docs\REAL_WORLD_DOGFOODING_AND_WORKFLOW_REFINEMENT.md"
$onboardingDocs = Read-ProjectFile "docs\FIRST_RUN_ONBOARDING.md"
$validator = Read-ProjectFile "scripts\validate-ecosystem.ps1"
$alphaSource = Read-ProjectFile "aegis-core\aegis_core\alpha.py"
$dogfoodingSource = Read-ProjectFile "aegis-core\aegis_core\dogfooding.py"
$onboardingSource = Read-ProjectFile "aegis-core\aegis_core\onboarding.py"
$coreServer = Read-ProjectFile "aegis-core\aegis_core\server.py"
$alphaTests = Read-ProjectFile "aegis-core\tests\test_alpha_readiness.py"
$dogfoodingTests = Read-ProjectFile "aegis-core\tests\test_dogfooding.py"
$onboardingTests = Read-ProjectFile "aegis-core\tests\test_onboarding.py"
$websiteSettings = Read-ProjectFile "website\backend\aegis_ai\services\settings_service.py"

Add-AlphaCheck -Id "contract-schema-version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Detail "Phase 14 alpha contract must use the current schema version."
Add-AlphaCheck -Id "contract-evidence-root" -Passed ([string]$contract.evidence_root -eq ".aegis/alpha-evidence") -Detail "Phase 14 alpha evidence must have a stable .aegis root."

foreach ($file in @($contract.required_contract_files)) {
  $relativePath = [string]$file
  Add-AlphaCheck -Id "contract-file-$(ConvertTo-CheckId $relativePath)" -Passed (Test-Path -LiteralPath (Join-Path $Root $relativePath) -PathType Leaf) -Detail "Required Phase 14 contract file must exist: $relativePath"
}

Assert-SetIncludes -IdPrefix "feature-stable-alpha" -Values @($contract.feature_tiers.stable_alpha) -Required @("workspace_scan", "chat_with_model_route", "propose_patch", "preview_diff", "checkpoint", "apply_after_approval", "validate", "rollback", "memory_resume", "diagnostics_export") -Label "Stable alpha features"
Assert-SetIncludes -IdPrefix "feature-beta" -Values @($contract.feature_tiers.beta) -Required @("provider_setup", "local_model_routing", "website_runtime_status", "desktop_runtime_status", "vscode_extension_loop", "visual_studio_extension_loop", "quality_gates", "dogfooding_friction_tracking") -Label "Beta features"
Assert-SetIncludes -IdPrefix "feature-experimental" -Values @($contract.feature_tiers.experimental) -Required @("plugins", "distributed_runtime", "adaptive_intelligence", "autonomous_engineering", "creative_media", "operating_environment") -Label "Experimental features"
Assert-SetIncludes -IdPrefix "feature-internal-only" -Values @($contract.feature_tiers.internal_only) -Required @("release_signing", "external_plugin_execution", "remote_worker_execution", "desktop_automation_adapters", "unrestricted_autonomy", "provider_credential_internals") -Label "Internal-only features"

$requiredAlphaApis = @(
  "GET /v1/alpha/readiness",
  "GET /v1/alpha/features",
  "GET /v1/alpha/feature-flags",
  "POST /v1/alpha/feature-flags",
  "GET /v1/alpha/diagnostics",
  "POST /v1/alpha/diagnostics/export",
  "POST /v1/alpha/feedback",
  "GET /v1/alpha/feedback",
  "GET /v1/alpha/observability",
  "GET /v1/alpha/release-channels",
  "GET /v1/alpha/simulations"
)
$requiredDogfoodingApis = @(
  "GET /v1/dogfooding",
  "POST /v1/dogfooding/events",
  "GET /v1/dogfooding/friction",
  "GET /v1/dogfooding/confidence",
  "GET /v1/dogfooding/workflows",
  "GET /v1/dogfooding/long-session-plan"
)
Assert-SetIncludes -IdPrefix "contract-alpha-api" -Values @($contract.core_alpha_apis) -Required $requiredAlphaApis -Label "Core alpha APIs"
Assert-SetIncludes -IdPrefix "contract-dogfooding-api" -Values @($contract.dogfooding_apis) -Required $requiredDogfoodingApis -Label "Dogfooding APIs"
Assert-ApiPathsInSource -IdPrefix "server-alpha-api" -Apis @($contract.core_alpha_apis) -Text $coreServer -Label "Core server"
Assert-ApiPathsInSource -IdPrefix "server-dogfooding-api" -Apis @($contract.dogfooding_apis) -Text $coreServer -Label "Core server"

Assert-SetIncludes -IdPrefix "onboarding-requirement" -Values @($contract.onboarding_requirements) -Required @("welcome", "privacy", "local_models", "providers", "workspace", "safety", "theme", "first_workflow", "finish", "settings_import_export", "validate_only_first_workflow") -Label "Onboarding requirements"
Assert-SetIncludes -IdPrefix "recovery-state" -Values @($contract.recovery_states) -Required @("backend_down", "core_offline", "ollama_offline", "model_unavailable", "key_missing", "provider_missing", "workspace_blocked", "update_failed", "validation_failed", "extension_disconnected", "desktop_blank_state") -Label "Recovery states"
Assert-ObjectIdsInclude -IdPrefix "scenario" -Objects @($contract.scenario_suite) -Required @("create_app", "modify_app", "repair_validation", "review_code", "connect_provider", "use_local_model", "run_vscode_extension", "run_visual_studio_extension", "update_component", "rollback_component") -Label "Alpha scenario suite"
Assert-SetIncludes -IdPrefix "evidence-file" -Values @($contract.evidence_files) -Required @(".aegis/alpha-readiness.json", ".aegis/alpha-feature-flags.json", ".aegis/alpha-feedback.jsonl", ".aegis/alpha-diagnostics/", ".aegis/dogfooding-events.jsonl", ".aegis/dogfooding-report.json", ".aegis/dogfooding-summary.md") -Label "Alpha evidence files"

foreach ($marker in @("ALPHA_READINESS_FILE", "ALPHA_FEATURE_FLAGS_FILE", "ALPHA_FEEDBACK_FILE", "ALPHA_DIAGNOSTICS_DIR", "def alpha_readiness", "def alpha_feature_flags", "def export_diagnostics_bundle", "def record_feedback", "def feedback_summary", "def alpha_observability", "def release_channels", "def alpha_simulations", "def recommended_alpha_scope")) {
  Assert-SourceContains -Id "alpha-source-$(ConvertTo-CheckId $marker)" -Text $alphaSource -Pattern ([regex]::Escape($marker)) -Detail "Core alpha runtime must keep marker '$marker'."
}
foreach ($marker in @("EVENT_FILE", "REPORT_FILE", "SUMMARY_FILE", "FRICTION_LABELS", "def dogfooding_workflows", "def record_dogfooding_event", "def dogfooding_dashboard", "def friction_report", "def production_confidence", "def long_session_plan")) {
  Assert-SourceContains -Id "dogfooding-source-$(ConvertTo-CheckId $marker)" -Text $dogfoodingSource -Pattern ([regex]::Escape($marker)) -Detail "Core dogfooding runtime must keep marker '$marker'."
}
foreach ($marker in @("ONBOARDING_STEPS", "FIRST_WORKFLOW_STEPS", "RECOVERY_CARDS", "def onboarding_status", "def export_settings", "def import_settings", "def run_first_workflow")) {
  Assert-SourceContains -Id "onboarding-source-$(ConvertTo-CheckId $marker)" -Text $onboardingSource -Pattern ([regex]::Escape($marker)) -Detail "Core onboarding runtime must keep marker '$marker'."
}
foreach ($state in @($contract.recovery_states)) {
  $id = [string]$state
  Assert-SourceContains -Id "onboarding-recovery-$id" -Text $onboardingSource -Pattern ([regex]::Escape("`"$id`"")) -Detail "Core onboarding recovery cards must include '$id'."
  Assert-SourceContains -Id "website-fallback-recovery-$id" -Text $websiteSettings -Pattern ([regex]::Escape("`"$id`"")) -Detail "Website fallback onboarding recovery must include '$id'."
}

Assert-SourceContains -Id "alpha-tests-readiness" -Text $alphaTests -Pattern 'test_alpha_readiness_collects_checklist_safe_defaults_and_risks' -Detail "Core alpha tests must cover readiness checklist and safe defaults."
Assert-SourceContains -Id "alpha-tests-endpoints" -Text $alphaTests -Pattern 'test_alpha_endpoints_are_contract_wrapped' -Detail "Core alpha tests must cover endpoint envelopes."
Assert-SourceContains -Id "dogfooding-tests-events" -Text $dogfoodingTests -Pattern 'test_record_dogfooding_event_persists_local_redacted_signal' -Detail "Core dogfooding tests must cover local redacted events."
Assert-SourceContains -Id "dogfooding-tests-endpoints" -Text $dogfoodingTests -Pattern 'test_dogfooding_endpoints_are_contract_wrapped' -Detail "Core dogfooding tests must cover endpoint envelopes."
Assert-SourceContains -Id "onboarding-tests-recovery" -Text $onboardingTests -Pattern 'recovery_ids' -Detail "Core onboarding tests must cover Phase 14 recovery ids."
Assert-SourceContains -Id "onboarding-tests-first-workflow" -Text $onboardingTests -Pattern 'test_first_workflow_actions_capture_scan_validation_and_checkpoint_preview' -Detail "Core onboarding tests must cover guided first workflow."

Assert-SourceContains -Id "docs-alpha-contract" -Text $alphaDocs -Pattern 'phase14-alpha-readiness-contract\.json' -Detail "Controlled alpha docs must link the Phase 14 machine-readable contract."
Assert-SourceContains -Id "docs-alpha-evidence-root" -Text $alphaDocs -Pattern '\.aegis/alpha-evidence' -Detail "Controlled alpha docs must document alpha evidence root."
Assert-SourceContains -Id "docs-alpha-scenario-suite" -Text $alphaDocs -Pattern 'Alpha Scenario Suite' -Detail "Controlled alpha docs must document the alpha scenario suite."
Assert-SourceContains -Id "docs-dogfooding-contract" -Text $dogfoodingDocs -Pattern 'phase14-alpha-readiness-contract\.json' -Detail "Dogfooding docs must link the Phase 14 contract."
Assert-SourceContains -Id "docs-dogfooding-evidence-root" -Text $dogfoodingDocs -Pattern '\.aegis/alpha-evidence' -Detail "Dogfooding docs must document alpha evidence output."
Assert-SourceContains -Id "docs-onboarding-recovery-contract" -Text $onboardingDocs -Pattern 'Phase 14 Recovery Contract' -Detail "First-run docs must document the Phase 14 recovery contract."
foreach ($state in @($contract.recovery_states)) {
  $id = [string]$state
  Assert-SourceContains -Id "docs-onboarding-recovery-$id" -Text $onboardingDocs -Pattern ([regex]::Escape($id)) -Detail "First-run docs must mention recovery state '$id'."
}

Assert-SourceContains -Id "validator-alpha-contract-gate" -Text $validator -Pattern 'test-alpha-contract\.ps1' -Detail "Ecosystem validation must run the Phase 14 alpha contract gate."
Assert-SourceContains -Id "validator-alpha-evidence-dir" -Text $validator -Pattern 'alpha-contract' -Detail "Ecosystem validation must place alpha contract output under the release evidence directory."

$scenarioCount = @($contract.scenario_suite).Count
$summary = [pscustomobject]@{
  root = $Root
  status = if ($script:Failures.Count -eq 0) { "passed" } else { "failed" }
  checked_at = (Get-Date).ToString("o")
  evidence_dir = $EvidenceDir
  contract = [pscustomobject]@{
    schema_version = [string]$contract.schema_version
    alpha_api_count = @($contract.core_alpha_apis).Count
    dogfooding_api_count = @($contract.dogfooding_apis).Count
    recovery_state_count = @($contract.recovery_states).Count
    scenario_count = $scenarioCount
  }
  checks = $script:Checks
}

New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$summaryPath = Join-Path $EvidenceDir "alpha-contract.json"
$markdownPath = Join-Path $EvidenceDir "alpha-contract-summary.md"
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 14 Alpha Readiness Contract"
$markdown += ""
$markdown += "- Status: $($summary.status)"
$markdown += "- Checked at: $($summary.checked_at)"
$markdown += "- Alpha APIs: $($summary.contract.alpha_api_count)"
$markdown += "- Dogfooding APIs: $($summary.contract.dogfooding_api_count)"
$markdown += "- Recovery states: $($summary.contract.recovery_state_count)"
$markdown += "- Scenario suite entries: $($summary.contract.scenario_count)"
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
  throw "Alpha readiness contract validation failed:`n - $($script:Failures -join "`n - ")"
}
