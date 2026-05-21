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
    throw "Required editor parity file is missing: $RelativePath"
  }
  return Get-Content -LiteralPath $path -Raw
}

function Add-EditorParityCheck {
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

  Add-EditorParityCheck -Id $Id -Passed ([bool]($Text -match $Pattern)) -Detail $Detail
}

function Assert-VsCodeCommand {
  param(
    [Parameter(Mandatory = $true)][object]$Manifest,
    [Parameter(Mandatory = $true)][string]$Command,
    [Parameter(Mandatory = $true)][string]$Label
  )

  $contributed = @($Manifest.contributes.commands | ForEach-Object { [string]$_.command })
  $activationEvents = @($Manifest.activationEvents | Where-Object { $_ -like "onCommand:*" } | ForEach-Object { ([string]$_).Substring("onCommand:".Length) })
  Add-EditorParityCheck `
    -Id "vscode-command-$Label" `
    -Passed ($contributed -contains $Command -and $activationEvents -contains $Command) `
    -Detail "VS Code must contribute and activate $Label through $Command."
}

function Assert-EditorEndpointPair {
  param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][string]$Endpoint,
    [Parameter(Mandatory = $true)][string]$VsCodeText,
    [Parameter(Mandatory = $true)][string]$VisualStudioText,
    [Parameter(Mandatory = $true)][string]$Detail
  )

  $pattern = [regex]::Escape($Endpoint)
  Add-EditorParityCheck `
    -Id "editor-endpoint-$Id" `
    -Passed ([bool]($VsCodeText -match $pattern) -and [bool]($VisualStudioText -match $pattern)) `
    -Detail $Detail
}

$vscodePackagePath = Join-Path $Root "vscode-plugins\aegis-local-autopilot\package.json"
if (-not (Test-Path -LiteralPath $vscodePackagePath -PathType Leaf)) {
  throw "Required editor parity file is missing: vscode-plugins\aegis-local-autopilot\package.json"
}

$vscodeManifest = Get-Content -LiteralPath $vscodePackagePath -Raw | ConvertFrom-Json
$vscodeExtension = Read-ProjectFile "vscode-plugins\aegis-local-autopilot\extension.js"
$vscodeCoreClient = Read-ProjectFile "vscode-plugins\aegis-local-autopilot\src\core\aegisCoreClient.ts"
$vscodeWorkflowClient = Read-ProjectFile "vscode-plugins\aegis-local-autopilot\src\workflowClient.ts"
$vscodeValidation = Read-ProjectFile "vscode-plugins\aegis-local-autopilot\src\validation\validationDetector.ts"
$vscodeRollback = Read-ProjectFile "vscode-plugins\aegis-local-autopilot\src\proposal\rollback.ts"
$vscodeMemory = Read-ProjectFile "vscode-plugins\aegis-local-autopilot\src\memory\aegisMemory.ts"
$vscodeSettings = Read-ProjectFile "vscode-plugins\aegis-local-autopilot\src\settings\settings.ts"

$vsCoreClient = Read-ProjectFile "visual-studio-extensions\aegis-local-agent-vs\src\AegisLocalAgentVs\Services\AegisCoreClient.cs"
$vsCommands = Read-ProjectFile "visual-studio-extensions\aegis-local-agent-vs\src\AegisLocalAgentVs\Commands\AegisCommands.cs"
$vsCommandIds = Read-ProjectFile "visual-studio-extensions\aegis-local-agent-vs\src\AegisLocalAgentVs\CommandIds.cs"
$vsRuntime = Read-ProjectFile "visual-studio-extensions\aegis-local-agent-vs\src\AegisLocalAgentVs\Services\AegisAgentRuntime.cs"
$vsSafeEdit = Read-ProjectFile "visual-studio-extensions\aegis-local-agent-vs\src\AegisLocalAgentVs\Services\SafeEditService.cs"
$vsMemory = Read-ProjectFile "visual-studio-extensions\aegis-local-agent-vs\src\AegisLocalAgentVs\Services\ProjectMemoryService.cs"
$vsOptions = Read-ProjectFile "visual-studio-extensions\aegis-local-agent-vs\src\AegisLocalAgentVs\Options\AegisOptionsPage.cs"
$vsReadme = Read-ProjectFile "visual-studio-extensions\aegis-local-agent-vs\README.md"

Assert-VsCodeCommand -Manifest $vscodeManifest -Command "aegisLocalAutopilot.runHealthCheck" -Label "health"
Assert-VsCodeCommand -Manifest $vscodeManifest -Command "aegisLocalAutopilot.runValidation" -Label "validation"
Assert-VsCodeCommand -Manifest $vscodeManifest -Command "aegisLocalAutopilot.generateProjectRoadmap" -Label "roadmap"
Assert-VsCodeCommand -Manifest $vscodeManifest -Command "aegisLocalAutopilot.continueFromRoadmap" -Label "roadmap-continuation"
Assert-VsCodeCommand -Manifest $vscodeManifest -Command "aegisLocalAutopilot.proposePatch" -Label "proposal"
Assert-VsCodeCommand -Manifest $vscodeManifest -Command "aegisLocalAutopilot.applyLastProposal" -Label "apply"
Assert-VsCodeCommand -Manifest $vscodeManifest -Command "aegisLocalAutopilot.rollbackLastChange" -Label "rollback"
Assert-VsCodeCommand -Manifest $vscodeManifest -Command "aegisLocalAutopilot.scanModels" -Label "model-status"

Assert-SourceContains -Id "vs-command-health" -Text $vsCommands -Pattern "CommandIds\.RunHealthCheck" -Detail "Visual Studio must register a health-check command."
Assert-SourceContains -Id "vs-command-roadmap" -Text $vsCommands -Pattern "CommandIds\.GenerateRoadmap[\s\S]*CommandIds\.ContinueFromRoadmap" -Detail "Visual Studio must register roadmap generation and continuation commands."
Assert-SourceContains -Id "vs-command-rollback" -Text $vsCommands -Pattern "CommandIds\.RollbackLastChange" -Detail "Visual Studio must register rollback."
Assert-SourceContains -Id "vs-command-rescan" -Text $vsCommands -Pattern "CommandIds\.RescanSolutionIntelligence" -Detail "Visual Studio must register solution intelligence rescan."
Assert-SourceContains -Id "vs-command-id-health" -Text $vsCommandIds -Pattern "RunHealthCheck" -Detail "Visual Studio command IDs must preserve the health workflow command."
Assert-SourceContains -Id "vs-command-id-roadmap" -Text $vsCommandIds -Pattern "GenerateRoadmap" -Detail "Visual Studio command IDs must preserve the roadmap workflow command."
Assert-SourceContains -Id "vs-command-id-roadmap-continuation" -Text $vsCommandIds -Pattern "ContinueFromRoadmap" -Detail "Visual Studio command IDs must preserve the roadmap continuation workflow command."
Assert-SourceContains -Id "vs-command-id-rollback" -Text $vsCommandIds -Pattern "RollbackLastChange" -Detail "Visual Studio command IDs must preserve the rollback workflow command."

Assert-EditorEndpointPair -Id "health" -Endpoint "/v1/health" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must query Core health."
Assert-EditorEndpointPair -Id "release-manifest" -Endpoint "/v1/release/manifest" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must read the Core release manifest."
Assert-EditorEndpointPair -Id "release-compatibility" -Endpoint "/v1/release/compatibility" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must check release compatibility."
Assert-EditorEndpointPair -Id "security" -Endpoint "/v1/security/status" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must expose Core security status."
Assert-EditorEndpointPair -Id "client-sync" -Endpoint "/v1/clients/sync" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must sync client presence with Core."
Assert-EditorEndpointPair -Id "workspace-scan" -Endpoint "/v1/workspaces/scan" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must be able to scan workspace/solution state through Core."
Assert-EditorEndpointPair -Id "workspace-intelligence" -Endpoint "/v1/workspaces/intelligence" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must refresh Core workspace intelligence."
Assert-EditorEndpointPair -Id "roadmap" -Endpoint "/v1/workspaces/roadmap" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must generate roadmaps through Core."
Assert-EditorEndpointPair -Id "model-registry" -Endpoint "/v1/models/registry" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must consume the Core model registry."
Assert-EditorEndpointPair -Id "model-route" -Endpoint "/v1/models/route" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must route model/workflow choices through Core."
Assert-EditorEndpointPair -Id "workflow-create" -Endpoint "/v1/workflows" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must create Core workflows."
Assert-EditorEndpointPair -Id "changes-propose" -Endpoint "/v1/changes/propose" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must record proposed changes in Core."
Assert-EditorEndpointPair -Id "changes-apply" -Endpoint "/v1/changes/apply" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must apply approved changes through Core."
Assert-EditorEndpointPair -Id "quality-gates" -Endpoint "/v1/quality-gates/evaluate" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must evaluate Core quality gates before apply."
Assert-EditorEndpointPair -Id "checkpoints-list" -Endpoint "/v1/checkpoints" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must list Core checkpoints."
Assert-EditorEndpointPair -Id "checkpoint-restore" -Endpoint "/v1/checkpoints/restore" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must restore Core checkpoints."
Assert-EditorEndpointPair -Id "validation-run" -Endpoint "/v1/validation/run" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must run validation through Core."
Assert-EditorEndpointPair -Id "autopilot-start" -Endpoint "/v1/autopilot/start" -VsCodeText $vscodeCoreClient -VisualStudioText $vsCoreClient -Detail "Both editor clients must start Core-owned autopilot workflows."

Assert-SourceContains -Id "vscode-client-type" -Text $vscodeCoreClient -Pattern "vscode-extension" -Detail "VS Code Core client must report client_type vscode-extension."
Assert-SourceContains -Id "vs-client-type" -Text $vsCoreClient -Pattern "visual-studio-extension" -Detail "Visual Studio Core client must report client_type visual-studio-extension."
Assert-SourceContains -Id "vscode-schema-version" -Text $vscodeCoreClient -Pattern "schema_version:\s*options\.schemaVersion\s*\|\|\s*'2026\.05\.12'" -Detail "VS Code must send the current Core contract schema version."
Assert-SourceContains -Id "vs-schema-version" -Text $vsCoreClient -Pattern 'CoreContractVersion\s*=\s*"2026\.05\.12"' -Detail "Visual Studio must send the current Core contract schema version."
Assert-SourceContains -Id "vscode-core-auth" -Text $vscodeCoreClient -Pattern "AEGIS_CORE_LOCAL_TOKEN[\s\S]*AEGIS_LOCAL_AUTH_TOKEN" -Detail "VS Code must forward local Core auth tokens when configured."
Assert-SourceContains -Id "vs-core-auth" -Text $vsCoreClient -Pattern "ApplyCoreAuthHeaders" -Detail "Visual Studio must forward local Core auth tokens when configured."
Assert-SourceContains -Id "vscode-default-core-url" -Text $vscodeSettings -Pattern "127\.0\.0\.1:8788" -Detail "VS Code settings must default Aegis Core to localhost 8788."
Assert-SourceContains -Id "vs-default-core-url" -Text $vsOptions -Pattern "127\.0\.0\.1:8788" -Detail "Visual Studio settings must default Aegis Core to localhost 8788."

Assert-SourceContains -Id "vscode-local-memory" -Text $vscodeMemory -Pattern "\.aegis" -Detail "VS Code must keep inspectable local .aegis memory support."
Assert-SourceContains -Id "vs-local-memory" -Text $vsMemory -Pattern "\.aegis" -Detail "Visual Studio must keep inspectable local .aegis memory support."
Assert-SourceContains -Id "vscode-validation-detector" -Text $vscodeValidation -Pattern "detectValidationCommands|classifyValidationFailure" -Detail "VS Code must keep safe validation detection helpers."
Assert-SourceContains -Id "vs-validation-runtime" -Text $vsRuntime -Pattern "ValidateSessionAsync|RunValidationAsync" -Detail "Visual Studio must keep Core/local validation flow."
Assert-SourceContains -Id "vscode-rollback-safety" -Text $vscodeRollback -Pattern "rollback|checkpoint|backup" -Detail "VS Code must keep rollback/checkpoint safety helpers."
Assert-SourceContains -Id "vs-rollback-safety" -Text $vsSafeEdit -Pattern "RollbackLastChangeAsync|backup" -Detail "Visual Studio must keep local rollback safety helpers."
Assert-SourceContains -Id "vscode-workflow-facade" -Text $vscodeWorkflowClient -Pattern "continueRoadmap|validateProject|repairProject|scanWorkspace" -Detail "VS Code must keep a workflow facade over Core."
Assert-SourceContains -Id "vs-core-first-docs" -Text $vsReadme -Pattern "Core-First Runtime" -Detail "Visual Studio docs must state the Core-first runtime model."

$summary = [pscustomobject]@{
  root = $Root
  status = if ($script:Failures.Count -eq 0) { "passed" } else { "failed" }
  checked_at = (Get-Date).ToString("o")
  vscode = [pscustomobject]@{
    package_version = [string]$vscodeManifest.version
    command_count = @($vscodeManifest.contributes.commands).Count
    source_modules_present = $true
  }
  visual_studio = [pscustomobject]@{
    client_id = "aegis-visual-studio"
    command_contract_present = $true
  }
  checks = $script:Checks
}

$summary | ConvertTo-Json -Depth 5

if ($script:Failures.Count -gt 0) {
  throw "Editor client parity validation failed:`n - $($script:Failures -join "`n - ")"
}
