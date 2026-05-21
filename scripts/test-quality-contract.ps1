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
  $EvidenceDir = Join-Path $Root (Join-Path ".aegis\quality-evidence" (Get-Date -Format "yyyyMMdd-HHmmss"))
} else {
  $EvidenceDir = [System.IO.Path]::GetFullPath($EvidenceDir)
}

$script:Checks = @()
$script:Failures = @()

function Read-ProjectFile {
  param([Parameter(Mandatory = $true)][string]$RelativePath)

  $path = Join-Path $Root $RelativePath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "Required quality contract file is missing: $RelativePath"
  }
  return Get-Content -LiteralPath $path -Raw
}

function Read-ProjectJson {
  param([Parameter(Mandatory = $true)][string]$RelativePath)

  return Read-ProjectFile $RelativePath | ConvertFrom-Json
}

function Add-QualityCheck {
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

  Add-QualityCheck -Id $Id -Passed ([bool]($Text -match $Pattern)) -Detail $Detail
}

function Assert-SourceMarker {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][string]$RelativePath,
    [Parameter(Mandatory = $true)][string]$Marker,
    [Parameter(Mandatory = $true)][string]$Detail
  )

  $text = Read-ProjectFile $RelativePath
  Add-QualityCheck -Id $Id -Passed ([bool]($text -match [regex]::Escape($Marker))) -Detail $Detail
}

function Assert-ContractItems {
  param(
    [Parameter(Mandatory = $true)][string]$Kind,
    [Parameter(Mandatory = $true)][object[]]$Items,
    [Parameter(Mandatory = $true)][string[]]$RequiredIds
  )

  $ids = @($Items | ForEach-Object { [string]$_.id })
  foreach ($required in $RequiredIds) {
    Add-QualityCheck -Id "$Kind-$required" -Passed ($ids -contains $required) -Detail "Phase 12 contract must define $Kind '$required'."
  }
}

$contract = Read-ProjectJson "evals\phase12-quality-contract.json"
$qualityDocs = Read-ProjectFile "docs\QUALITY_GATES.md"
$validator = Read-ProjectFile "scripts\validate-ecosystem.ps1"
$coreServer = Read-ProjectFile "aegis-core\aegis_core\server.py"
$coreQuality = Read-ProjectFile "aegis-core\aegis_core\quality.py"
$coreQualityGates = Read-ProjectFile "aegis-core\aegis_core\quality_gates.py"
$coreQualityTests = Read-ProjectFile "aegis-core\tests\test_quality_gates.py"
$websiteQualityRoutes = Read-ProjectFile "website\backend\aegis_ai\routes\quality_evaluation.py"
$websiteMain = Read-ProjectFile "website\backend\aegis_ai\main.py"
$telemetryRoutes = Read-ProjectFile "website\backend\aegis_ai\routes\telemetry.py"
$storageQuality = Read-ProjectFile "website\backend\aegis_ai\storage_quality.py"
$goldenTests = Read-ProjectFile "website\backend\tests\test_golden_workflows.py"

Add-QualityCheck -Id "contract-schema-version" -Passed ([string]$contract.schema_version -eq "2026.05.21") -Detail "Phase 12 quality contract must use the current schema version."
Add-QualityCheck -Id "contract-evidence-root" -Passed ([string]$contract.evidence_root -eq ".aegis/quality-evidence") -Detail "Phase 12 quality evidence must have a stable .aegis root."

foreach ($file in @($contract.required_contract_files)) {
  $relativePath = [string]$file
  Add-QualityCheck -Id "contract-file-$($relativePath.Replace('/', '-').Replace('\', '-'))" -Passed (Test-Path -LiteralPath (Join-Path $Root $relativePath) -PathType Leaf) -Detail "Required Phase 12 contract file must exist: $relativePath"
}

$requiredWorkflows = @(
  "chat_no_write",
  "coding_diff_checkpoint",
  "review_quality_gate",
  "scaffold_project",
  "validation_repair",
  "model_routing",
  "provider_fallback",
  "memory_continuation",
  "apply_rollback",
  "extension_parity"
)
$goldenWorkflows = @($contract.golden_workflows)
Assert-ContractItems -Kind "golden-workflow" -Items $goldenWorkflows -RequiredIds $requiredWorkflows

foreach ($workflow in $goldenWorkflows) {
  $workflowId = [string]$workflow.id
  Add-QualityCheck -Id "golden-workflow-description-$workflowId" -Passed (-not [string]::IsNullOrWhiteSpace([string]$workflow.description)) -Detail "Golden workflow '$workflowId' must explain the workflow being guarded."
  Add-QualityCheck -Id "golden-workflow-metrics-$workflowId" -Passed (@($workflow.metrics).Count -gt 0) -Detail "Golden workflow '$workflowId' must list comparable metrics."

  $evidence = $workflow.required_evidence
  Add-QualityCheck -Id "golden-workflow-evidence-$workflowId" -Passed ($null -ne $evidence -and -not [string]::IsNullOrWhiteSpace([string]$evidence.source_file) -and -not [string]::IsNullOrWhiteSpace([string]$evidence.marker)) -Detail "Golden workflow '$workflowId' must point to source evidence."
  if ($null -ne $evidence -and -not [string]::IsNullOrWhiteSpace([string]$evidence.source_file) -and -not [string]::IsNullOrWhiteSpace([string]$evidence.marker)) {
    Assert-SourceMarker -Id "golden-workflow-marker-$workflowId" -RelativePath ([string]$evidence.source_file) -Marker ([string]$evidence.marker) -Detail "Golden workflow '$workflowId' evidence marker must exist in $($evidence.source_file)."
  }
}

$requiredSignals = @(
  "route_quality",
  "fallback_inspector",
  "feedback",
  "token_calibration",
  "structured_preview",
  "policy_diff"
)
$signals = @($contract.observability_signals)
Assert-ContractItems -Kind "observability-signal" -Items $signals -RequiredIds $requiredSignals
foreach ($signal in $signals) {
  $signalId = [string]$signal.id
  Add-QualityCheck -Id "observability-endpoint-$signalId" -Passed (-not [string]::IsNullOrWhiteSpace([string]$signal.endpoint)) -Detail "Observability signal '$signalId' must declare its endpoint."
  Assert-SourceMarker -Id "observability-marker-$signalId" -RelativePath ([string]$signal.source_file) -Marker ([string]$signal.marker) -Detail "Observability signal '$signalId' marker must exist in $($signal.source_file)."
}

$requiredBudgets = @(
  "workspace_scan",
  "model_route_preview",
  "chat_first_token",
  "apply_quality_gate",
  "validation_command",
  "frontend_render"
)
$budgets = @($contract.performance_budgets)
Assert-ContractItems -Kind "performance-budget" -Items $budgets -RequiredIds $requiredBudgets
foreach ($budget in $budgets) {
  $budgetId = [string]$budget.id
  $p95 = [double]$budget.p95_seconds
  $warning = [double]$budget.warning_seconds
  Add-QualityCheck -Id "performance-budget-threshold-$budgetId" -Passed ($p95 -gt 0 -and $warning -gt 0 -and $warning -le $p95) -Detail "Performance budget '$budgetId' must define positive warning and p95 thresholds."
  Add-QualityCheck -Id "performance-budget-evidence-$budgetId" -Passed (-not [string]::IsNullOrWhiteSpace([string]$budget.evidence)) -Detail "Performance budget '$budgetId' must name the evidence source."
}

Assert-SourceContains -Id "docs-quality-contract" -Text $qualityDocs -Pattern 'phase12-quality-contract\.json' -Detail "Quality docs must link the machine-readable Phase 12 contract."
Assert-SourceContains -Id "docs-performance-budgets" -Text $qualityDocs -Pattern 'Performance Budgets' -Detail "Quality docs must document performance budgets."
Assert-SourceContains -Id "docs-evidence-root" -Text $qualityDocs -Pattern '\.aegis/quality-evidence' -Detail "Quality docs must document the quality evidence root."

Assert-SourceContains -Id "validator-quality-contract-gate" -Text $validator -Pattern 'test-quality-contract\.ps1' -Detail "Ecosystem validation must run the Phase 12 quality contract gate."
Assert-SourceContains -Id "validator-quality-evidence-dir" -Text $validator -Pattern 'quality-contract' -Detail "Ecosystem validation must place quality contract output under the release evidence directory."

Assert-SourceContains -Id "core-quality-dashboard" -Text $coreServer -Pattern '/v1/quality' -Detail "Core must expose the quality dashboard endpoint."
Assert-SourceContains -Id "core-quality-snapshot" -Text $coreServer -Pattern '/v1/quality/snapshot' -Detail "Core must expose the quality snapshot endpoint."
Assert-SourceContains -Id "core-quality-gates" -Text $coreServer -Pattern '/v1/quality-gates' -Detail "Core must expose quality gate endpoints."
Assert-SourceContains -Id "core-benchmarks" -Text $coreServer -Pattern '/v1/benchmarks' -Detail "Core must expose benchmark endpoints."
Assert-SourceContains -Id "core-evaluation-reports" -Text $coreServer -Pattern '/v1/evaluation-reports' -Detail "Core must expose evaluation report endpoints."
Assert-SourceContains -Id "core-quality-history" -Text $coreQuality -Pattern 'health-history\.json' -Detail "Core quality snapshots must persist health history."

foreach ($gate in @("syntax_check", "build_check", "test_check", "lint_check", "type_check", "security_scan", "dependency_risk", "file_change_risk", "rollback_readiness", "user_approval_required")) {
  Assert-SourceContains -Id "core-gate-$gate" -Text $coreQualityGates -Pattern $gate -Detail "Core quality gates must keep '$gate'."
}

foreach ($suite in @("coding_task_quality", "repair_accuracy", "validation_success", "routing_decisions", "model_provider_performance", "agent_handoff_reliability")) {
  Assert-SourceContains -Id "core-benchmark-suite-$suite" -Text $coreQualityGates -Pattern $suite -Detail "Core benchmark suites must keep '$suite'."
}

Assert-SourceContains -Id "core-tests-quality-block" -Text $coreQualityTests -Pattern 'test_quality_gate_blocks_unsafe_path_and_apply_preserves_file' -Detail "Core quality tests must prove blocked apply leaves files unchanged."
Assert-SourceContains -Id "core-tests-benchmark-report" -Text $coreQualityTests -Pattern 'test_benchmark_and_evaluation_report_are_recorded' -Detail "Core quality tests must prove benchmarks and reports are recorded."

Assert-SourceContains -Id "website-quality-route-status" -Text $websiteQualityRoutes -Pattern '/api/quality-gates' -Detail "Website must expose quality gate compatibility routes."
Assert-SourceContains -Id "website-quality-route-benchmark" -Text $websiteQualityRoutes -Pattern '/api/benchmarks/run' -Detail "Website must expose benchmark compatibility routes."
Assert-SourceContains -Id "website-quality-route-reports" -Text $websiteQualityRoutes -Pattern '/api/evaluation-reports' -Detail "Website must expose evaluation report compatibility routes."
Assert-SourceContains -Id "website-quality-delegates-core" -Text $websiteMain -Pattern 'core_runtime_client\.evaluate_quality_gates' -Detail "Website quality evaluation must delegate to Core."
Assert-SourceContains -Id "website-benchmark-delegates-core" -Text $websiteMain -Pattern 'core_runtime_client\.run_benchmark' -Detail "Website benchmark execution must delegate to Core."

Assert-SourceContains -Id "telemetry-route-quality" -Text $telemetryRoutes -Pattern 'route-quality' -Detail "Telemetry routes must expose route quality."
Assert-SourceContains -Id "telemetry-feedback" -Text $telemetryRoutes -Pattern 'feedback' -Detail "Telemetry routes must expose feedback telemetry."
Assert-SourceContains -Id "telemetry-snapshot" -Text $telemetryRoutes -Pattern 'snapshot' -Detail "Telemetry routes must expose materialized snapshots."
Assert-SourceContains -Id "telemetry-policy-diff" -Text $telemetryRoutes -Pattern 'policy-diff' -Detail "Telemetry routes must expose policy diffs."
Assert-SourceContains -Id "telemetry-token-calibration" -Text $storageQuality -Pattern 'token_calibration_status' -Detail "Telemetry quality helpers must keep token calibration status."
Assert-SourceContains -Id "telemetry-structured-preview" -Text $storageQuality -Pattern 'structured_preview_status' -Detail "Telemetry quality helpers must keep structured preview status."

Assert-SourceContains -Id "golden-tests-chat" -Text $goldenTests -Pattern 'test_normal_question_does_not_generate_file_changes' -Detail "Golden workflow tests must include chat no-write coverage."
Assert-SourceContains -Id "golden-tests-rollback" -Text $goldenTests -Pattern 'restore_checkpoint' -Detail "Golden workflow tests must include rollback coverage."
Assert-SourceContains -Id "golden-tests-memory" -Text $goldenTests -Pattern 'project_memory' -Detail "Golden workflow tests must include memory continuation coverage."

$summary = [pscustomobject]@{
  root = $Root
  status = if ($script:Failures.Count -eq 0) { "passed" } else { "failed" }
  checked_at = (Get-Date).ToString("o")
  evidence_dir = $EvidenceDir
  contract = [pscustomobject]@{
    schema_version = [string]$contract.schema_version
    golden_workflow_count = $goldenWorkflows.Count
    observability_signal_count = $signals.Count
    performance_budget_count = $budgets.Count
  }
  checks = $script:Checks
}

New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$summaryPath = Join-Path $EvidenceDir "quality-contract.json"
$markdownPath = Join-Path $EvidenceDir "quality-contract-summary.md"
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

$markdown = @()
$markdown += "# Phase 12 Quality Contract"
$markdown += ""
$markdown += "- Status: $($summary.status)"
$markdown += "- Checked at: $($summary.checked_at)"
$markdown += "- Golden workflows: $($summary.contract.golden_workflow_count)"
$markdown += "- Observability signals: $($summary.contract.observability_signal_count)"
$markdown += "- Performance budgets: $($summary.contract.performance_budget_count)"
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
  throw "Quality contract validation failed:`n - $($script:Failures -join "`n - ")"
}
