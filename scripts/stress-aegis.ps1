param(
    [string]$BackendUrl = "http://127.0.0.1:8787",
    [string]$ExpectedProjectRoot = "",
    [int]$ApiIterations = 60,
    [switch]$RunDesktopSmoke,
    [switch]$RunScaffoldSmoke,
    [string]$OutputDir = "",
    [string]$ExePath = "",
    [int]$DesktopSetupWaitSeconds = 4,
    [int]$DesktopDashboardWaitSeconds = 16
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptRoot

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputDir = Join-Path $repoRoot "stress-artifacts\$stamp"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$BackendUrl = $BackendUrl.TrimEnd("/")
$workspaceRoot = Join-Path $OutputDir "workspace"
$planTarget = Join-Path $workspaceRoot "stress-console"
New-Item -ItemType Directory -Force -Path $workspaceRoot | Out-Null

function Invoke-AegisJsonGet {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSec = 45
    )

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Method Get -Uri $Url -TimeoutSec $TimeoutSec
    }
    catch {
        throw "GET $Url failed after ${TimeoutSec}s: $($_.Exception.Message)"
    }
    if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 300) {
        throw "GET $Url returned HTTP $($response.StatusCode)"
    }
    return $response.Content | ConvertFrom-Json
}

function Invoke-AegisJsonPost {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)]$Body,
        [int]$TimeoutSec = 75
    )

    $json = $Body | ConvertTo-Json -Depth 12
    try {
        $response = Invoke-WebRequest `
            -UseBasicParsing `
            -Method Post `
            -Uri $Url `
            -ContentType "application/json" `
            -Body $json `
            -TimeoutSec $TimeoutSec
    }
    catch {
        throw "POST $Url failed after ${TimeoutSec}s: $($_.Exception.Message)"
    }

    if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 300) {
        throw "POST $Url returned HTTP $($response.StatusCode)"
    }
    return $response.Content | ConvertFrom-Json
}

function Assert-Aegis {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-AegisHealthProjectRoot {
    param(
        [Parameter(Mandatory = $true)]$Health,
        [Parameter(Mandatory = $true)][string]$ExpectedRoot,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if ([string]::IsNullOrWhiteSpace($ExpectedRoot)) {
        return
    }

    $property = $Health.PSObject.Properties["project_root"]
    Assert-Aegis ($null -ne $property -and $null -ne $property.Value -and -not [string]::IsNullOrWhiteSpace([string]$property.Value)) "$Label health response did not include project_root."
    $expectedRootPath = [System.IO.Path]::GetFullPath($ExpectedRoot).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    $actualProjectRoot = [System.IO.Path]::GetFullPath([string]$property.Value).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    Assert-Aegis ([string]::Equals($actualProjectRoot, $expectedRootPath, [System.StringComparison]::OrdinalIgnoreCase)) "$Label backend project root mismatch. Expected '$expectedRootPath' but health reported '$actualProjectRoot'."
}

function Write-AegisUtf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Value
    )

    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Value, $encoding)
}

function Write-AegisJsonFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Value,
        [int]$Depth = 12
    )

    Write-AegisUtf8NoBom -Path $Path -Value ($Value | ConvertTo-Json -Depth $Depth)
}

function Get-AegisPropertyValue {
    param(
        [Parameter(Mandatory = $false)]$Object,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if ($null -eq $Object) {
        return $null
    }

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Assert-AegisReadiness {
    param(
        [Parameter(Mandatory = $true)]$Profile,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $readiness = Get-AegisPropertyValue -Object $Profile -Name "readiness"
    Assert-Aegis ($null -ne $readiness) "$Label profile is missing readiness."

    $status = [string](Get-AegisPropertyValue -Object $readiness -Name "status")
    $score = [int](Get-AegisPropertyValue -Object $readiness -Name "score")
    $nextAction = [string](Get-AegisPropertyValue -Object $readiness -Name "next_action")

    Assert-Aegis (-not [string]::IsNullOrWhiteSpace($status)) "$Label readiness did not include a status."
    Assert-Aegis ($score -ge 0 -and $score -le 100) "$Label readiness score $score was outside 0-100."
    Assert-Aegis (-not ($nextAction -match "^\s*(Preset|Framework|Package manager|Language|Stack|Tags|CMake CLI)\s*:")) "$Label readiness next action leaked metadata: $nextAction"

    return $readiness
}

function Assert-AegisInstructionStatusHasNoMetadataNoise {
    param(
        [Parameter(Mandatory = $true)]$Profile,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $instructionStatus = Get-AegisPropertyValue -Object $Profile -Name "instruction_status"
    $files = Get-AegisPropertyValue -Object $instructionStatus -Name "files"
    if ($null -eq $files) {
        return
    }

    $pendingItems = New-Object System.Collections.Generic.List[string]
    foreach ($file in @($files)) {
        $items = Get-AegisPropertyValue -Object $file -Name "pending_items"
        if ($null -eq $items) {
            continue
        }
        foreach ($item in @($items)) {
            $text = [string]$item
            if (-not [string]::IsNullOrWhiteSpace($text)) {
                $pendingItems.Add($text)
            }
        }
    }

    $pendingText = ($pendingItems.ToArray() -join "`n")
    Assert-Aegis (-not ($pendingText -match "(?m)^\s*(Preset|Framework|Package manager|Language|Stack|Tags|CMake CLI)\s*:")) "$Label instruction pending items leaked metadata: $pendingText"
}

function Get-Percentile {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][double[]]$Values,
        [Parameter(Mandatory = $true)][double]$Percentile
    )

    $items = @($Values)
    if ($items.Count -eq 0) {
        return 0
    }

    $sorted = @($items | Sort-Object)
    $index = [Math]::Ceiling(($Percentile / 100.0) * $sorted.Count) - 1
    $index = [Math]::Max(0, [Math]::Min($sorted.Count - 1, $index))
    return [Math]::Round([double]$sorted[$index], 2)
}

function Measure-AegisCall {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    $sw = [Diagnostics.Stopwatch]::StartNew()
    $result = & $Action
    $sw.Stop()
    return @{
        Result = $result
        Milliseconds = [Math]::Round($sw.Elapsed.TotalMilliseconds, 2)
    }
}

Write-Host "Aegis stress test"
Write-Host "Backend: $BackendUrl"
Write-Host "Iterations: $ApiIterations"
Write-Host "Output: $OutputDir"

$health = Invoke-AegisJsonGet "$BackendUrl/api/health"
Assert-Aegis ([bool]$health.ready) "Backend health endpoint is not ready."
Assert-AegisHealthProjectRoot -Health $health -ExpectedRoot $ExpectedProjectRoot -Label "Initial"

$presetIdsToRequire = @(
    "cpp-msvc-console-sln",
    "cpp-cmake-dll",
    "cpp-imgui-win32-dx11",
    "cpp-windows-internals-hooking",
    "windows-kernel-driver-controller",
    "python-sln-refactor-tool",
    "static-html-site",
    "node-fullstack-js"
)

$durations = New-Object System.Collections.Generic.List[double]
$failures = New-Object System.Collections.Generic.List[string]
$lastPresetCount = 0
$lastCppPlan = ""
$lastFullStackPlan = ""
$scaffoldSmoke = $null
$msvcConsoleSmoke = $null
$continuitySmoke = $null
$cmakeValidationSmoke = $null
$diagnosticExtractionSmoke = $null
$readinessContinuationSmoke = $null
$genericInstructionSmoke = $null
$desktopAutopilotPromptContractSmoke = $null
$desktopBuildFollowupContractSmoke = $null
$backendValidationOnlyContractSmoke = $null
$backendWorkspaceCacheContractSmoke = $null
$backendNaturalPromptContractSmoke = $null
$nativeContinuityCommandSmoke = $null
$cppDllHostSmoke = $null
$windowsInternalsMinHookSmoke = $null
$solutionRefactorMaterializeSmoke = $null

$chatAppSourcePath = Join-Path $repoRoot "src\AegisChatApp.cpp"
Assert-Aegis (Test-Path -LiteralPath $chatAppSourcePath) "Desktop prompt contract smoke could not find AegisChatApp.cpp."
$chatAppSource = Get-Content -LiteralPath $chatAppSourcePath -Raw
Assert-Aegis ($chatAppSource -match "Backend queued instruction items to work in order") "Desktop autopilot prompt contract does not include backend queued instruction items."
Assert-Aegis ($chatAppSource -match "authoritative roadmap") "Desktop autopilot prompt contract does not prioritize backend queued instruction items as the roadmap."
Assert-Aegis ($chatAppSource -match "Next queued item:") "Desktop autopilot suggestions do not surface the next queued item."
Assert-Aegis ($chatAppSource -match "Repair brief") "Desktop autopilot prompt contract does not include the backend repair brief."
Assert-Aegis ($chatAppSource -match "Failed command") "Desktop autopilot prompt contract does not include the backend failed command."
Assert-Aegis ($chatAppSource -match "First diagnostic") "Desktop autopilot prompt contract does not include the backend first diagnostic."
Assert-Aegis ($chatAppSource -match " at this path") "Desktop path extraction does not stop before repeated 'at this path' wording."
Assert-Aegis ($chatAppSource -match "PromptTargetsExistingNativeOrDllWork") "Desktop routing no longer protects existing DLL/native refinement prompts from scaffold routing."
$mainSourcePath = Join-Path $repoRoot "src\Main.cpp"
Assert-Aegis (Test-Path -LiteralPath $mainSourcePath) "Desktop chrome contract smoke could not find Main.cpp."
$mainSource = Get-Content -LiteralPath $mainSourcePath -Raw
Assert-Aegis ($mainSource -match "rect.right - chrome_width") "Desktop frameless hit-test no longer reserves window chrome for ImGui buttons."
$platformSourcePath = Join-Path $repoRoot "src\Platform.cpp"
Assert-Aegis (Test-Path -LiteralPath $platformSourcePath) "Desktop backend identity smoke could not find Platform.cpp."
$platformSource = Get-Content -LiteralPath $platformSourcePath -Raw
Assert-Aegis ($platformSource -match "BackendHealthProjectRootMatches") "Desktop backend health no longer validates the reported backend project root."
Assert-Aegis ($platformSource -match "different project root") "Desktop backend startup no longer reports stale backend-root mismatches."
Assert-Aegis ($platformSource -match "does not include project_root") "Desktop backend startup no longer rejects stale health responses without project_root."
Assert-Aegis ($platformSource -match "invalid backend health response") "Desktop backend startup no longer rejects invalid health responses from foreign services."
$clientHeaderPath = Join-Path $repoRoot "src\AegisClient.h"
$clientSourcePath = Join-Path $repoRoot "src\AegisClient.cpp"
Assert-Aegis (Test-Path -LiteralPath $clientHeaderPath) "Desktop client contract smoke could not find AegisClient.h."
Assert-Aegis (Test-Path -LiteralPath $clientSourcePath) "Desktop client contract smoke could not find AegisClient.cpp."
$clientHeaderSource = Get-Content -LiteralPath $clientHeaderPath -Raw
$clientSource = Get-Content -LiteralPath $clientSourcePath -Raw
Assert-Aegis ($clientHeaderSource -match "failed_step_command") "Desktop client status model does not store failed_step_command."
Assert-Aegis ($clientHeaderSource -match "first_diagnostic") "Desktop client status model does not store first_diagnostic."
Assert-Aegis ($clientHeaderSource -match "repair_brief") "Desktop client status model does not store repair_brief."
Assert-Aegis ($clientSource -match 'value\["failed_step_command"\]') "Desktop client parser does not read failed_step_command."
Assert-Aegis ($clientSource -match 'value\["first_diagnostic"\]') "Desktop client parser does not read first_diagnostic."
    Assert-Aegis ($clientSource -match 'value\["repair_brief"\]') "Desktop client parser does not read repair_brief."
    Assert-Aegis ($clientSource -match "BackendHealthProjectRootMatches") "Desktop client no longer rejects health responses from the wrong backend root."
    $backendCommandsSourcePath = Join-Path $repoRoot "website\backend\aegis_ai\commands.py"
    Assert-Aegis (Test-Path -LiteralPath $backendCommandsSourcePath) "Backend command parser contract smoke could not find commands.py."
    $backendCommandsSource = Get-Content -LiteralPath $backendCommandsSourcePath -Raw
    Assert-Aegis ($backendCommandsSource -match "_space_unquoted_shell_metacharacters") "Backend command parser no longer tokenizes glued shell operators before safe parsing."
    Assert-Aegis ($backendCommandsSource -match "SHELL_OPERATOR_SCAN_ORDER") "Backend command parser no longer scans longest shell operators first."
    $desktopAutopilotPromptContractSmoke = @{
        source_path = $chatAppSourcePath
        queue_contract = $true
        repair_brief_contract = $true
        client_parse_contract = $true
        command_parser_contract = $true
    }
$frontendQueueSourcePath = Join-Path $repoRoot "website\frontend\src\utils\messageQueue.ts"
$frontendAppSourcePath = Join-Path $repoRoot "website\frontend\src\App.tsx"
$frontendMissionAnchorSourcePath = Join-Path $repoRoot "website\frontend\src\utils\missionAnchor.ts"
Assert-Aegis (Test-Path -LiteralPath $frontendQueueSourcePath) "Frontend queue contract smoke could not find messageQueue.ts."
Assert-Aegis (Test-Path -LiteralPath $frontendAppSourcePath) "Frontend queue contract smoke could not find App.tsx."
Assert-Aegis (Test-Path -LiteralPath $frontendMissionAnchorSourcePath) "Frontend queue contract smoke could not find missionAnchor.ts."
$frontendQueueSource = Get-Content -LiteralPath $frontendQueueSourcePath -Raw
$frontendAppSource = Get-Content -LiteralPath $frontendAppSourcePath -Raw
$frontendMissionAnchorSource = Get-Content -LiteralPath $frontendMissionAnchorSourcePath -Raw
Assert-Aegis ($frontendQueueSource -match "threadId") "Frontend queued prompts no longer persist their origin thread id."
Assert-Aegis ($frontendQueueSource -match "sanitizeHistory") "Frontend queued prompts no longer persist a sanitized history snapshot."
Assert-Aegis ($frontendQueueSource -match "missionAnchor") "Frontend queued prompts no longer persist their mission anchor."
Assert-Aegis ($frontendQueueSource -match "normalizeQueuedMessage") "Frontend queued prompt loader no longer normalizes legacy queue entries."
Assert-Aegis ($frontendAppSource -match "threadIdForSubmit") "Frontend queued prompt replay no longer restores the origin thread before sending."
Assert-Aegis ($frontendAppSource -match "queuedHistoryAlreadyHasPrompt") "Frontend queued prompt replay no longer protects legacy entries from dropping the user prompt."
Assert-Aegis ($frontendAppSource -match "buildAgentRequestHistory") "Frontend submit no longer prepends mission anchors to bounded request history."
Assert-Aegis ($frontendAppSource -match "createMissionAnchorMessage") "Frontend queue/retry path no longer creates mission anchors."
Assert-Aegis ($frontendMissionAnchorSource -match "Aegis mission anchor") "Frontend mission anchor source no longer labels hidden continuity context."
Assert-Aegis ($frontendMissionAnchorSource -match "vague follow-ups") "Frontend mission anchor no longer documents continuation behavior."
$frontendQueueContractSmoke = @{
    queue_source_path = $frontendQueueSourcePath
    app_source_path = $frontendAppSourcePath
    mission_anchor_source_path = $frontendMissionAnchorSourcePath
    thread_id_contract = $true
    history_snapshot_contract = $true
    mission_anchor_contract = $true
    legacy_queue_contract = $true
}
Assert-Aegis ($chatAppSource -match "Auto-selected from existing project files for a build/run follow-up") "Desktop build follow-up contract is still limited to native C++ projects."
Assert-Aegis ($chatAppSource -match "Preserve the detected stack, build system, and app type") "Desktop continuity directive does not preserve the detected project stack."
Assert-Aegis ($chatAppSource -match "run build") "Desktop build follow-up validation does not infer package build commands."
$desktopBuildFollowupContractSmoke = @{
    source_path = $chatAppSourcePath
    generic_build_followup = $true
}

$aegisRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $repoRoot))
$localBackendMainSourcePath = Join-Path $repoRoot "website\backend\aegis_ai\main.py"
$legacyBackendMainSourcePath = Join-Path $aegisRoot "Website\ChatBot\backend\aegis_ai\main.py"
$backendMainSourcePath = if (Test-Path -LiteralPath $localBackendMainSourcePath) { $localBackendMainSourcePath } else { $legacyBackendMainSourcePath }
Assert-Aegis (Test-Path -LiteralPath $backendMainSourcePath) "Backend workspace cache contract smoke could not find main.py."
$backendMainSource = Get-Content -LiteralPath $backendMainSourcePath -Raw
Assert-Aegis ($backendMainSource -match "_workspace_status_snapshot") "Backend workspace profile/autopilot endpoints no longer share a cached workspace snapshot."
Assert-Aegis ($backendMainSource -match "_cached_project_plan") "Backend project-builder planning no longer uses the short-lived plan cache."
Assert-Aegis ($backendMainSource -match "_invalidate_workspace_caches") "Backend workspace cache invalidation contract is missing."
Assert-Aegis ($backendMainSource -match "_WORKSPACE_SNAPSHOT_TTL_SECONDS") "Backend workspace snapshot cache TTL is missing."
Assert-Aegis ($backendMainSource -match "_PROJECT_PLAN_CACHE_TTL_SECONDS") "Backend project plan cache TTL is missing."
Assert-Aegis ($backendMainSource -match "_chat_stream_workspace_root") "Backend chat stream meta no longer resolves the effective prompt-selected workspace."
$backendWorkspaceCacheContractSmoke = @{
    source_path = $backendMainSourcePath
    profile_autopilot_snapshot_cache = $true
    project_plan_cache = $true
    invalidation_contract = $true
    prompt_workspace_stream_meta = $true
}

$localBackendAgentSourcePath = Join-Path $repoRoot "website\backend\aegis_ai\agent.py"
$legacyBackendAgentSourcePath = Join-Path $aegisRoot "Website\ChatBot\backend\aegis_ai\agent.py"
$backendAgentSourcePath = if (Test-Path -LiteralPath $localBackendAgentSourcePath) { $localBackendAgentSourcePath } else { $legacyBackendAgentSourcePath }
Assert-Aegis (Test-Path -LiteralPath $backendAgentSourcePath) "Backend validation contract smoke could not find agent.py."
$backendAgentSource = Get-Content -LiteralPath $backendAgentSourcePath -Raw
Assert-Aegis ($backendAgentSource -match "Validation requested for current workspace") "Backend no-change validation path does not announce current-workspace validation."
Assert-Aegis ($backendAgentSource -match "Validation deferred until changes are applied") "Backend no-change validation path does not defer preview-only validation safely."
Assert-Aegis ($backendAgentSource -match "Aegis ran validation and") "Backend no-change validation replies do not summarize validation results."
Assert-Aegis ($backendAgentSource -match "_draft_stack_mismatch_reasons") "Backend agent no longer rejects stack-drifted model drafts."
Assert-Aegis ($backendAgentSource -match "_draft_task_adherence_reasons") "Backend agent no longer judges task adherence before accepting autopilot progress."
Assert-Aegis ($backendAgentSource -match "_workspace_stack_family") "Backend agent no longer infers the active workspace stack for manifest-free projects."
Assert-Aegis (-not ($backendAgentSource -match '\{"cmakelists\.txt", "cmakepresets\.json", "makefile", "build\.py"\}')) "Backend agent is treating generic build.py validators as native C++ workspace markers again."
Assert-Aegis ($backendAgentSource -match "not to make a website/web app") "Backend agent no longer rejects web-stack drafts after explicit web negation."
Assert-Aegis ($backendAgentSource -match "_request_mentions_desktop_project") "Backend agent no longer recognizes explicit desktop/GUI implementation requests."
Assert-Aegis ($backendAgentSource -match "_draft_has_desktop_host_surface") "Backend agent no longer verifies that desktop drafts include a desktop host surface."
Assert-Aegis ($backendAgentSource -match "website/static frontend") "Backend agent no longer rejects static website drafts for desktop app requests."
Assert-Aegis ($backendAgentSource -match "_draft_manifest_contract_mismatch_reasons") "Backend agent no longer rejects drafts that violate the saved workspace mission contract."
Assert-Aegis ($backendAgentSource -match "_draft_has_concrete_source_surface") "Backend agent no longer requires concrete source changes for implementation drafts."
Assert-Aegis ($backendAgentSource -match "_draft_destructive_change_reasons") "Backend agent no longer rejects destructive model drafts before apply."
Assert-Aegis ($backendAgentSource -match "_prompt_explicitly_allows_destructive_changes") "Backend agent no longer checks whether the latest prompt explicitly allows destructive changes."
Assert-Aegis ($backendAgentSource -match "tried to delete or empty important project files") "Backend agent no longer reports destructive draft replacement."
Assert-Aegis ($backendAgentSource -match "_draft_existing_project_scaffold_drift_reasons") "Backend agent no longer rejects fresh starter drafts for existing-project continuation."
Assert-Aegis ($backendAgentSource -match "_prompt_allows_fresh_scaffold_in_existing_project") "Backend agent no longer distinguishes explicit fresh scaffold requests from continuation work."
Assert-Aegis ($backendAgentSource -match "looked like a fresh starter scaffold for an existing project") "Backend agent no longer reports existing-project starter drift."
Assert-Aegis ($backendAgentSource -match "_draft_existing_file_overwrite_reasons") "Backend agent no longer rejects create-as-overwrite model drafts for existing files."
Assert-Aegis ($backendAgentSource -match "used create on existing project files") "Backend agent no longer reports create-as-overwrite draft replacement."
Assert-Aegis ($backendAgentSource -match "The model draft did not match the saved workspace mission contract") "Backend agent no longer reports mission-contract draft replacement."
Assert-Aegis ($backendAgentSource -match "The C\+\+ entry point does not wait for user input") "Backend agent no longer checks native console prompts for requested input pause behavior."
Assert-Aegis ($backendAgentSource -match "authoritative task contract") "Backend model prompt no longer makes the latest user request authoritative over stale chat/workspace context."
Assert-Aegis ($backendAgentSource -match "Mission rule: preserve this stack") "Backend model prompt no longer surfaces the manifest mission preservation rule."
Assert-Aegis ($backendAgentSource -match "_mission_continuity_contract_context") "Backend model prompt no longer includes the mission continuity contract block."
Assert-Aegis ($backendAgentSource -match "_mission_anchor_from_history") "Backend agent no longer parses frontend mission anchors from request history."
Assert-Aegis ($backendAgentSource -match "_mission_aware_message") "Backend agent no longer converts vague follow-ups into mission-aware planning input."
Assert-Aegis ($backendAgentSource -match "Aegis mission anchor") "Backend mission anchor parser no longer recognizes the frontend anchor label."
Assert-Aegis ($backendAgentSource -match "Vague follow-ups must preserve") "Backend mission anchor contract no longer preserves vague follow-up path/stack/artifact intent."
Assert-Aegis ($backendAgentSource -match "Native/C\+\+ guardrail") "Backend model prompt no longer tells native/C++ work to avoid accidental web scaffolds."
Assert-Aegis ($backendAgentSource -match "Words after that explicit path are instructions") "Backend model prompt no longer protects explicit paths from trailing instruction text."
Assert-Aegis ($backendAgentSource -match "_turn_expects_file_work") "Backend full-build contract no longer treats manifest-backed continuation as implementation work."
Assert-Aegis ($backendAgentSource -match "_resolve_workspace_for_prompted_request") "Backend agent no longer resolves explicit prompt paths as the effective workspace."
Assert-Aegis ($backendAgentSource -match "stream_meta_workspace_root") "Backend agent no longer exposes the prompt-selected workspace for stream metadata."
Assert-Aegis ($backendAgentSource -match "Explicit prompt workspace selected") "Backend agent no longer emits a live activity event for prompt-selected workspaces."
Assert-Aegis ($backendAgentSource -match '"work on"') "Backend direct-chat guard no longer treats natural 'work on' prompts as file-changing work."
Assert-Aegis ($backendAgentSource -match '"clean up"') "Backend direct-chat guard no longer treats natural 'clean up' prompts as file-changing work."
Assert-Aegis ($backendAgentSource -match '"polish"') "Backend direct-chat guard no longer treats natural refinement prompts as file-changing work."
Assert-Aegis ($backendAgentSource -match "_existing_project_no_change_continuation_draft") "Backend no-change existing-project recovery helper is missing."
Assert-Aegis ($backendAgentSource -match "strict existing-project continuation pass") "Backend no-change existing-project recovery no longer prepares a strict continuation pass."
Assert-Aegis ($backendAgentSource -match "_existing_project_continuation_validation_command") "Backend no-change existing-project recovery no longer proposes a validation command."
Assert-Aegis ($backendAgentSource -match "_draft_validation_override_recipe") "Backend draft-proposed validation commands are no longer promoted into the validation loop."
Assert-Aegis ($backendAgentSource -match "Draft validation command selected") "Backend draft-proposed validation command selection is no longer visible in activity events."
Assert-Aegis ($backendAgentSource -match 'source="draft-proposal"') "Backend draft-proposed validation recipes no longer carry an auditable source label."
Assert-Aegis ($backendAgentSource -match "_should_remember_validation_recipe") "Backend validation command learning policy is missing."
Assert-Aegis ($backendAgentSource -match "Validation command learned") "Backend successful draft validation commands are no longer surfaced as learned workspace knowledge."
$backendValidationSourcePath = Join-Path $repoRoot "website\backend\aegis_ai\validation.py"
Assert-Aegis (Test-Path -LiteralPath $backendValidationSourcePath) "Backend validation manager contract smoke could not find validation.py."
$backendValidationSource = Get-Content -LiteralPath $backendValidationSourcePath -Raw
Assert-Aegis ($backendValidationSource -match "COMMAND_HISTORY_PATH") "Backend validation manager no longer knows the command history path."
Assert-Aegis ($backendValidationSource -match "_history_candidate") "Backend validation manager no longer recovers validation commands from command history."
Assert-Aegis ($backendValidationSource -match "_safe_history_validation_command") "Backend validation manager no longer filters unsafe remembered validation commands."
Assert-Aegis ($backendValidationSource -match "aegis.command_history.v1") "Backend validation manager no longer verifies the command-history schema."
$backendFallbackSourcePath = Join-Path $repoRoot "website\backend\aegis_ai\fallback.py"
Assert-Aegis (Test-Path -LiteralPath $backendFallbackSourcePath) "Backend fallback contract smoke could not find fallback.py."
$backendFallbackSource = Get-Content -LiteralPath $backendFallbackSourcePath -Raw
Assert-Aegis ($backendFallbackSource -match "_should_preserve_existing_workspace") "Backend fallback no longer preserves existing workspaces before starter generation."
Assert-Aegis ($backendFallbackSource -match "_existing_workspace_continuation_changes") "Backend fallback no longer has a stack-preserving existing-project continuation path."
Assert-Aegis ($backendFallbackSource -match "without recreating source files") "Backend fallback no longer adds validation helpers without recreating source files."
$backendWorkspaceSourcePath = Join-Path $repoRoot "website\backend\aegis_ai\workspace.py"
Assert-Aegis (Test-Path -LiteralPath $backendWorkspaceSourcePath) "Backend workspace contract smoke could not find workspace.py."
$backendWorkspaceSource = Get-Content -LiteralPath $backendWorkspaceSourcePath -Raw
Assert-Aegis ($backendWorkspaceSource -match "skipped create because the file already exists") "Backend apply layer no longer prevents create actions from overwriting existing files."
Assert-Aegis ($backendWorkspaceSource -match "use update to modify existing files") "Backend apply layer no longer explains that existing files require update actions."
Assert-Aegis ($backendWorkspaceSource -match "skipped update because the file does not exist") "Backend apply layer no longer prevents update actions from creating missing files."
Assert-Aegis ($backendWorkspaceSource -match "use create to add new files") "Backend apply layer no longer explains that missing files require create actions."
Assert-Aegis ($backendWorkspaceSource -match "skipped append because the file does not exist") "Backend apply layer no longer prevents append actions from creating missing files."
Assert-Aegis ($backendWorkspaceSource -match "use create before append") "Backend apply layer no longer explains that append actions require a seed create first."
Assert-Aegis ($backendWorkspaceSource -match "seed create for this file did not apply") "Backend apply layer no longer prevents append actions after a skipped seed create."
Assert-Aegis ($backendWorkspaceSource -match "refusing to delete the existing file") "Backend apply layer no longer prevents delete actions after a skipped seed create."
Assert-Aegis ($backendWorkspaceSource -match "skipped_create_paths") "Backend apply layer no longer tracks skipped create actions across an apply batch."
Assert-Aegis ($backendWorkspaceSource -match "casefold") "Backend apply layer no longer normalizes batch path keys for Windows-style casing."
$backendValidationOnlyContractSmoke = @{
    source_path = $backendAgentSourcePath
    validates_current_workspace_without_file_changes = $true
    stack_drift_guard = $true
    authoritative_latest_request = $true
    mission_continuity_contract = $true
    native_cpp_guardrail_contract = $true
    continuation_file_work_contract = $true
    explicit_prompt_workspace_contract = $true
    prompt_workspace_stream_meta = $true
    command_history_validation_recovery_contract = $true
    backend_mission_anchor_parser = $true
    mission_aware_followups = $true
}

$localBackendPlannerSourcePath = Join-Path $repoRoot "website\backend\aegis_ai\task_planner.py"
$legacyBackendPlannerSourcePath = Join-Path $aegisRoot "Website\ChatBot\backend\aegis_ai\task_planner.py"
$backendPlannerSourcePath = if (Test-Path -LiteralPath $localBackendPlannerSourcePath) { $localBackendPlannerSourcePath } else { $legacyBackendPlannerSourcePath }
Assert-Aegis (Test-Path -LiteralPath $backendPlannerSourcePath) "Backend natural prompt contract smoke could not find task_planner.py."
$backendPlannerSource = Get-Content -LiteralPath $backendPlannerSourcePath -Raw
Assert-Aegis ($backendPlannerSource -match '"work on"') "Backend task planner no longer classifies natural 'work on' prompts as implementation work."
Assert-Aegis ($backendPlannerSource -match '"optimize"') "Backend task planner no longer classifies natural optimization prompts as implementation work."
Assert-Aegis ($backendPlannerSource -match '"modernize"') "Backend task planner no longer classifies natural modernization prompts as implementation work."
Assert-Aegis ($backendPlannerSource -match "_prompt_negates_web_stack") "Backend task planner no longer suppresses web routing for negated website phrases."
Assert-Aegis ($backendPlannerSource -match "without converting it to a website") "Backend task planner no longer suppresses web routing for 'without converting it to a website' phrases."
Assert-Aegis ($backendPlannerSource -match 'intent == "conversation" and project_manifest is None') "Backend task planner no longer clears specialist route profiles for plain conversational questions."
Assert-Aegis ($backendPlannerSource -match "_looks_like_external_research") "Backend task planner no longer separates source-code work from external research prompts."
Assert-Aegis ($backendPlannerSource -match "_looks_like_workspace_bound_research") "Backend task planner no longer clears unrelated research route profiles inside code workspaces."
Assert-Aegis ($backendPlannerSource -match "source_context = bool") "Backend task planner no longer treats source code/layout follow-ups as local implementation context."
Assert-Aegis ($backendPlannerSource -match "cmakelists.txt") "Backend task planner no longer recognizes CMake workspaces before desktop/web fallback profiles."

$localBackendRouterSourcePath = Join-Path $repoRoot "website\backend\aegis_ai\routing.py"
$legacyBackendRouterSourcePath = Join-Path $aegisRoot "Website\ChatBot\backend\aegis_ai\routing.py"
$backendRouterSourcePath = if (Test-Path -LiteralPath $localBackendRouterSourcePath) { $localBackendRouterSourcePath } else { $legacyBackendRouterSourcePath }
Assert-Aegis (Test-Path -LiteralPath $backendRouterSourcePath) "Backend natural prompt contract smoke could not find routing.py."
$backendRouterSource = Get-Content -LiteralPath $backendRouterSourcePath -Raw
Assert-Aegis ($backendRouterSource -match "_looks_like_code_work") "Backend router no longer keeps source-code follow-ups in code/debug lanes."
Assert-Aegis ($backendRouterSource -match "_looks_like_external_research") "Backend router no longer protects external research routing from source-code wording."
Assert-Aegis ($backendRouterSource -match "latest_source_context") "Backend router no longer keeps 'latest source layout' prompts local-first."

$localPromptIntentSourcePath = Join-Path $repoRoot "website\backend\aegis_ai\prompt_intent.py"
$legacyPromptIntentSourcePath = Join-Path $aegisRoot "Website\ChatBot\backend\aegis_ai\prompt_intent.py"
$promptIntentSourcePath = if (Test-Path -LiteralPath $localPromptIntentSourcePath) { $localPromptIntentSourcePath } else { $legacyPromptIntentSourcePath }
Assert-Aegis (Test-Path -LiteralPath $promptIntentSourcePath) "Backend validation-intent contract smoke could not find prompt_intent.py."
$promptIntentSource = Get-Content -LiteralPath $promptIntentSourcePath -Raw
Assert-Aegis ($promptIntentSource -match "last failed build") "Backend validation-intent matrix no longer treats failed-build continuations as build/repair work."
Assert-Aegis ($promptIntentSource -match "rerun validation") "Backend validation-intent matrix no longer treats validation reruns as build/repair work."

$localBackendFallbackSourcePath = Join-Path $repoRoot "website\backend\aegis_ai\fallback.py"
$legacyBackendFallbackSourcePath = Join-Path $aegisRoot "Website\ChatBot\backend\aegis_ai\fallback.py"
$backendFallbackSourcePath = if (Test-Path -LiteralPath $localBackendFallbackSourcePath) { $localBackendFallbackSourcePath } else { $legacyBackendFallbackSourcePath }
Assert-Aegis (Test-Path -LiteralPath $backendFallbackSourcePath) "Backend natural prompt contract smoke could not find fallback.py."
$backendFallbackSource = Get-Content -LiteralPath $backendFallbackSourcePath -Raw
Assert-Aegis ($backendFallbackSource -match '"work on"') "Backend fallback no longer treats natural 'work on' prompts as project work."
Assert-Aegis ($backendFallbackSource -match '"clean up"') "Backend fallback no longer treats natural cleanup prompts as project work."
Assert-Aegis ($backendFallbackSource -match '"polish"') "Backend fallback no longer treats natural polish prompts as project work."
$backendNaturalPromptContractSmoke = @{
    agent_source_path = $backendAgentSourcePath
    planner_source_path = $backendPlannerSourcePath
    fallback_source_path = $backendFallbackSourcePath
    direct_chat_guard = $true
    task_planner_intent = $true
    fallback_intent = $true
    source_code_not_research_contract = $true
    native_cmake_profile_contract = $true
    external_research_profile_boundary = $true
}

$localBackendScaffolderSourcePath = Join-Path $repoRoot "website\backend\aegis_ai\project_scaffolder.py"
$legacyBackendScaffolderSourcePath = Join-Path $aegisRoot "Website\ChatBot\backend\aegis_ai\project_scaffolder.py"
$backendScaffolderSourcePath = if (Test-Path -LiteralPath $localBackendScaffolderSourcePath) { $localBackendScaffolderSourcePath } else { $legacyBackendScaffolderSourcePath }
Assert-Aegis (Test-Path -LiteralPath $backendScaffolderSourcePath) "Backend native continuity contract smoke could not find project_scaffolder.py."
$backendScaffolderSource = Get-Content -LiteralPath $backendScaffolderSourcePath -Raw
Assert-Aegis ($backendScaffolderSource -match "cmake -S \. -B build && cmake --build build --config Release") "Backend existing CMake validation no longer configures before the first build."
Assert-Aegis ($backendScaffolderSource -match '" write me "') "Backend existing-project validation still treats implementation prompts as pure validation."
Assert-Aegis ($backendScaffolderSource -match "_existing_project_validation_command") "Backend native continuity validation command helper is missing."
Assert-Aegis ($backendScaffolderSource -match "_stack_lock_keywords_for_prompt") "Backend project planner no longer exposes explicit stack-lock routing signals."
Assert-Aegis ($backendScaffolderSource -match "stack-lock:native-cpp") "Backend project planner no longer marks native C++ stack-lock prompts."
Assert-Aegis ($backendScaffolderSource -match "stack-lock:solution-refactor") "Backend project planner no longer marks Visual Studio solution refactor prompts."
Assert-Aegis ($backendScaffolderSource -match "stack-lock:desktop") "Backend project planner no longer marks desktop app stack-lock prompts."
Assert-Aegis ($backendScaffolderSource -match '"electron-react-ts",\s*"tauri-react-ts"') "Backend project planner no longer treats Electron/Tauri presets as desktop stack contracts."
Assert-Aegis ($backendScaffolderSource -match "my dll") "Backend continuity routing no longer treats existing DLL refinement as existing project work."
Assert-Aegis ($backendScaffolderSource -match "_prompt_negates_web_stack") "Backend planner no longer ignores negated web phrases like 'without turning it into a website'."
Assert-Aegis ($backendScaffolderSource -match "_stack_locks_conflict_with_preset") "Backend planner no longer rejects stale workspace stack continuity when the latest prompt declares a different stack."
Assert-Aegis ($backendScaffolderSource -match "current prompt stack override") "Backend planner no longer surfaces current-prompt stack override diagnostics."
Assert-Aegis ($backendScaffolderSource -match "electron-react-ts") "Backend planner no longer maps existing Electron projects to the valid Electron preset id."
Assert-Aegis ($backendScaffolderSource -match "_path_stop_phrase_is_boundary") "Backend planner no longer keeps action words inside prompt path folder names."
Assert-Aegis ($backendScaffolderSource -match "_path_action_boundary_preserves_leaf") "Backend planner no longer preserves folder names that contain instruction-like words before the real action."
Assert-Aegis ($backendScaffolderSource -match "location_markers") "Backend planner no longer rejects repeated location phrases before choosing an action boundary."
Assert-Aegis ($backendScaffolderSource.Contains('r"\s+-+$"')) "Backend prompt path parser no longer trims separator dashes before natural instructions."
Assert-Aegis ($backendScaffolderSource -match "_trailing_wrapper_belongs_to_path") "Backend prompt path parser no longer preserves balanced wrapper punctuation inside folder names."
Assert-Aegis ($backendScaffolderSource -match "previous_char\.isalnum\(\).*next_char\.isalnum\(\)") "Backend prompt path parser no longer preserves apostrophes inside folder names."
Assert-Aegis ($backendScaffolderSource -match '" design and "') "Backend prompt path parser no longer stops before natural 'design and build' instructions."
Assert-Aegis ($backendScaffolderSource -match '" refine "') "Backend prompt path parser no longer stops before natural refinement instructions."
Assert-Aegis ($backendScaffolderSource -match '" optimize "') "Backend prompt path parser no longer stops before natural optimization instructions."
Assert-Aegis ($backendScaffolderSource -match '" clean up "') "Backend prompt path parser no longer stops before natural cleanup instructions."
Assert-Aegis ($backendScaffolderSource -match '"keep going"') "Backend existing-project planner no longer treats vague continuation prompts as existing workspace work."
Assert-Aegis ($backendScaffolderSource -match '"make it production ready"') "Backend existing-project planner no longer treats production-ready follow-ups as validation work."
Assert-Aegis ($backendScaffolderSource -match "without making a website") "Backend web-negation guard no longer handles 'without making a website' follow-ups."
Assert-Aegis ($backendScaffolderSource -match "do not make a website") "Backend web-negation guard no longer handles 'do not make a website' follow-ups."
Assert-Aegis ($backendScaffolderSource -match "_path_action_stop_positions") "Backend prompt path parser no longer prioritizes action boundaries before later punctuation separators."
Assert-Aegis ($backendScaffolderSource -match "mission_contract") "Backend project manifest no longer stores the mission contract for long autopilot continuity."
Assert-Aegis ($backendScaffolderSource -match "_prompt_allows_stack_switch") "Backend project planner no longer distinguishes explicit stack switches from accidental drift words."
Assert-Aegis ($backendScaffolderSource -match "mission-contract:locked-stack") "Backend project planner no longer reports mission-contract stack locking."
Assert-Aegis ($backendScaffolderSource -match "continuity_policy") "Backend project manifest no longer records the continuity policy."
Assert-Aegis ($backendScaffolderSource -match "native dll/plugin library") "Backend preset scoring no longer boosts native DLL/plugin prompts into the DLL preset."
Assert-Aegis ($backendScaffolderSource -match "cpp-cmake-dll") "Backend C++ DLL/shared-library preset is missing."
Assert-Aegis ($backendScaffolderSource -match "run_host_validation") "Backend C++ DLL/shared-library preset no longer runs host validation."
Assert-Aegis ($backendScaffolderSource -match "aegis_plugin_description") "Backend C++ DLL/shared-library preset no longer exports plugin metadata."
Assert-Aegis ($backendScaffolderSource -match "Host loaded plugin") "Backend C++ DLL/shared-library preset no longer validates runtime host loading."
Assert-Aegis ($backendScaffolderSource -match "vendor/minhook_shim/MinHook.h") "Backend Windows internals preset no longer embeds the MinHook-compatible shim."
Assert-Aegis ($backendScaffolderSource -match "MH_CreateHook") "Backend Windows internals preset no longer exercises the MinHook create-hook boundary."
Assert-Aegis ($backendScaffolderSource -match "install_preview") "Backend Windows internals preset no longer exposes the MinHook adapter preview path."
Assert-Aegis ($backendScaffolderSource -match "materialize_merge") "Backend solution refactor preset no longer materializes merged workspaces."
Assert-Aegis ($backendScaffolderSource -match "--copy-projects") "Backend solution refactor preset no longer exposes project-folder copying."
Assert-Aegis ($backendScaffolderSource -match "samples/AppOne/AppOne.vcxproj") "Backend solution refactor preset no longer includes sample project artifacts."
Assert-Aegis ($backendScaffolderSource -match "analyze_vcxproj") "Backend solution refactor preset no longer analyzes Visual Studio project metadata."
Assert-Aegis ($backendScaffolderSource -match "AdditionalDependencies") "Backend solution refactor preset no longer extracts native linker dependencies."
Assert-Aegis ($backendScaffolderSource -match "ProjectReference") "Backend solution refactor preset no longer extracts project references."
Assert-Aegis ($backendScaffolderSource -match "--include-references") "Backend solution refactor preset no longer exposes reference-aware split/merge."
Assert-Aegis ($backendScaffolderSource -match "included_references") "Backend solution refactor preset no longer reports included project references."
Assert-Aegis ($backendScaffolderSource -match "build_solution_graph") "Backend solution refactor preset no longer builds a project dependency graph."
Assert-Aegis ($backendScaffolderSource -match "build_order") "Backend solution refactor preset no longer reports dependency-aware build order."

$existingDllTarget = Join-Path $workspaceRoot "existing-native-dll"
New-Item -ItemType Directory -Force -Path (Join-Path $existingDllTarget "src") | Out-Null
Write-AegisUtf8NoBom -Path (Join-Path $existingDllTarget "ExistingNativeDll.vcxproj") -Value @"
<Project DefaultTargets="Build" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <PropertyGroup Label="Configuration">
    <ConfigurationType>DynamicLibrary</ConfigurationType>
  </PropertyGroup>
</Project>
"@
Write-AegisUtf8NoBom -Path (Join-Path $existingDllTarget "src\dllmain.cpp") -Value @"
#include <windows.h>

BOOL APIENTRY DllMain(HMODULE, DWORD, LPVOID) {
    return TRUE;
}
"@

$staleWebTarget = Join-Path $workspaceRoot "stale-web-manifest-native-request"
New-Item -ItemType Directory -Force -Path (Join-Path $staleWebTarget ".aegis") | Out-Null
Write-AegisUtf8NoBom -Path (Join-Path $staleWebTarget ".aegis\project.json") -Value @"
{
  "schema": "aegis.project.v1",
  "project_name": "stale-web-site",
  "preset_id": "static-html-site",
  "preset_label": "Static HTML/CSS/JS Website",
  "validation_command": "node build.js"
}
"@
Write-AegisUtf8NoBom -Path (Join-Path $staleWebTarget "index.html") -Value "<main>stale web project</main>`n"

for ($i = 1; $i -le $ApiIterations; $i++) {
    try {
        $call = Measure-AegisCall {
            $health = Invoke-AegisJsonGet "$BackendUrl/api/health"
            Assert-Aegis ([bool]$health.ready) "Iteration $i health check was not ready."
            Assert-AegisHealthProjectRoot -Health $health -ExpectedRoot $ExpectedProjectRoot -Label "Iteration $i"

            $config = Invoke-AegisJsonGet "$BackendUrl/api/config"
            Assert-Aegis (-not [string]::IsNullOrWhiteSpace([string]$config.model_name)) "Iteration $i config did not include model_name."

            $presets = Invoke-AegisJsonGet "$BackendUrl/api/project-builder/presets"
            $presetCount = @($presets).Count
            Assert-Aegis ($presetCount -ge 30) "Iteration $i expected at least 30 project presets, found $presetCount."

            $presetIds = @($presets | ForEach-Object { $_.id })
            foreach ($presetId in $presetIdsToRequire) {
                Assert-Aegis ($presetIds -contains $presetId) "Iteration $i missing required preset '$presetId'."
            }

            $encodedWorkspace = [Uri]::EscapeDataString($workspaceRoot)
            $profile = Invoke-AegisJsonGet "$BackendUrl/api/workspace/profile?workspace_root=$encodedWorkspace"
            Assert-Aegis ([string]$profile.workspace_root -eq $workspaceRoot) "Iteration $i workspace profile returned an unexpected root."
            [void](Assert-AegisReadiness -Profile $profile -Label "Iteration $i workspace profile")
            Assert-AegisInstructionStatusHasNoMetadataNoise -Profile $profile -Label "Iteration $i workspace profile"

            $autopilotStatus = Invoke-AegisJsonGet "$BackendUrl/api/workspace/autopilot-status?workspace_root=$encodedWorkspace"
            Assert-Aegis ([string]$autopilotStatus.workspace_root -eq $workspaceRoot) "Iteration $i autopilot status returned an unexpected root."
            Assert-Aegis (@("ready", "work", "validate", "repair", "unconfigured") -contains [string]$autopilotStatus.phase) "Iteration $i autopilot status returned unknown phase '$($autopilotStatus.phase)'."
            Assert-Aegis (@("build", "develop", "review", "chat") -contains [string]$autopilotStatus.recommended_mode) "Iteration $i autopilot status returned unknown mode '$($autopilotStatus.recommended_mode)'."
            Assert-Aegis ([int]$autopilotStatus.pass_budget -ge 0 -and [int]$autopilotStatus.pass_budget -le 50) "Iteration $i autopilot status returned invalid pass budget '$($autopilotStatus.pass_budget)'."
            Assert-Aegis ($null -ne $autopilotStatus.readiness) "Iteration $i autopilot status did not include readiness."

            $contract = Invoke-AegisJsonGet "$BackendUrl/api/chat/stream/contract"
            Assert-Aegis ([string]$contract.endpoint -eq "/api/chat/stream") "Iteration $i stream contract endpoint changed unexpectedly."

            $cppPlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "Create a C++ Visual Studio console app called Stress Console that prints hello world, waits for Enter, and also build it."
                workspace_root = $workspaceRoot
                preferred_target_path = $planTarget
            } -TimeoutSec 90
            Assert-Aegis ([bool]$cppPlan.ok) "Iteration $i C++ plan did not complete successfully."
            Assert-Aegis ([string]$cppPlan.preset.id -eq "cpp-msvc-console-sln") "Iteration $i C++ plan selected '$($cppPlan.preset.id)' instead of cpp-msvc-console-sln."
            Assert-Aegis ([bool]$cppPlan.scaffold_request.run_validation) "Iteration $i C++ build intent did not enable scaffold validation."
            $cppProjectName = [string]$cppPlan.project_name

            $fullStackPlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "Create a full-stack CRUD dashboard app called Stress Tasks with frontend, backend, tests, and validation."
                workspace_root = $workspaceRoot
                preferred_target_path = (Join-Path $workspaceRoot "stress-tasks")
            } -TimeoutSec 90
            Assert-Aegis ([bool]$fullStackPlan.ok) "Iteration $i full-stack plan did not complete successfully."
            Assert-Aegis ([string]$fullStackPlan.preset.id -eq "node-fullstack-js") "Iteration $i full-stack plan selected '$($fullStackPlan.preset.id)' instead of node-fullstack-js."
            Assert-Aegis ([bool]$fullStackPlan.scaffold_request.run_validation) "Iteration $i full-stack validation intent did not enable scaffold validation."
            $fullStackProjectName = [string]$fullStackPlan.project_name

            $dllPlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "at this path $existingDllTarget work on my existing DLL that I already made, add a diagnostics UI, refine the native project, build it, and do not make a website"
                workspace_root = $workspaceRoot
                preferred_target_path = $existingDllTarget
            } -TimeoutSec 90
            $dllDetectedKeywords = @($dllPlan.detected_keywords)
            Assert-Aegis ([bool]$dllPlan.ok) "Iteration $i existing DLL plan did not complete successfully."
            Assert-Aegis ([string]$dllPlan.preset.id -eq "cpp-cmake-dll") "Iteration $i existing DLL plan selected '$($dllPlan.preset.id)' instead of cpp-cmake-dll."
            Assert-Aegis ([string]$dllPlan.target_path -eq [string](Resolve-Path -LiteralPath $existingDllTarget)) "Iteration $i existing DLL plan did not preserve the requested target path."
            Assert-Aegis ($dllDetectedKeywords -contains "stack-lock:native-library") "Iteration $i existing DLL plan did not preserve the native-library stack lock."
            Assert-Aegis (-not ($dllDetectedKeywords -contains "stack-lock:web")) "Iteration $i existing DLL plan incorrectly added a web stack lock from negated website wording."

            $plainNativeQuestionRoute = Invoke-AegisJsonPost "$BackendUrl/api/routing/preview" @{
                message = "what is a DLL and why would an app use one?"
                workspace_root = $existingDllTarget
                mode = "develop"
            } -TimeoutSec 60
            $plainNativeQuestionProfileId = Get-AegisPropertyValue -Object $plainNativeQuestionRoute.task_plan.route_profile -Name "id"
            Assert-Aegis ([string]$plainNativeQuestionRoute.task_plan.intent -eq "conversation") "Iteration $i plain DLL question did not stay in conversational intent."
            Assert-Aegis ([string]::IsNullOrWhiteSpace([string]$plainNativeQuestionProfileId)) "Iteration $i plain DLL question incorrectly advertised a specialist route profile '$plainNativeQuestionProfileId'."

            $sourceFollowupHistory = @(
                @{
                    role = "system"
                    content = "Aegis mission anchor:`n- Original user mission: at this path $existingDllTarget refine the existing native C++ source code and build it`n- Active workspace root: $existingDllTarget`n- Continuity rule: Preserve target stack and validation intent."
                }
            )
            $sourceFollowupRoute = Invoke-AegisJsonPost "$BackendUrl/api/routing/preview" @{
                message = "continue working on the source files"
                history = $sourceFollowupHistory
                workspace_root = $workspaceRoot
                mode = "develop"
            } -TimeoutSec 60
            $sourceFollowupProfileId = Get-AegisPropertyValue -Object $sourceFollowupRoute.task_plan.route_profile -Name "id"
            Assert-Aegis ([string]$sourceFollowupRoute.task_plan.intent -eq "implementation") "Iteration $i source-code follow-up drifted away from implementation intent."
            Assert-Aegis ([string]$sourceFollowupProfileId -eq "native-binary") "Iteration $i source-code follow-up selected '$sourceFollowupProfileId' instead of native-binary."
            Assert-Aegis ([string]$sourceFollowupRoute.task_plan.routing.task_role -eq "code") "Iteration $i source-code follow-up selected '$($sourceFollowupRoute.task_plan.routing.task_role)' instead of code."
            Assert-Aegis ([string]$sourceFollowupRoute.task_plan.routing.privacy_mode -eq "local-first") "Iteration $i source-code follow-up did not stay local-first."

            $latestSourceRoute = Invoke-AegisJsonPost "$BackendUrl/api/routing/preview" @{
                message = "use the latest source layout and build it"
                history = $sourceFollowupHistory
                workspace_root = $workspaceRoot
                mode = "develop"
            } -TimeoutSec 60
            Assert-Aegis ([string]$latestSourceRoute.task_plan.intent -eq "implementation") "Iteration $i latest-source follow-up incorrectly routed as research."
            Assert-Aegis ([string]$latestSourceRoute.task_plan.routing.privacy_mode -eq "local-first") "Iteration $i latest-source follow-up incorrectly requested cloud privacy."

            $externalResearchRoute = Invoke-AegisJsonPost "$BackendUrl/api/routing/preview" @{
                message = "look up latest AI news"
                workspace_root = $existingDllTarget
                mode = "develop"
            } -TimeoutSec 60
            $externalResearchProfileId = Get-AegisPropertyValue -Object $externalResearchRoute.task_plan.route_profile -Name "id"
            Assert-Aegis ([string]$externalResearchRoute.task_plan.intent -eq "research_and_synthesize") "Iteration $i external research prompt did not stay research intent."
            Assert-Aegis ([string]$externalResearchRoute.task_plan.routing.task_role -eq "research") "Iteration $i external research prompt selected '$($externalResearchRoute.task_plan.routing.task_role)' instead of research."
            Assert-Aegis ([string]::IsNullOrWhiteSpace([string]$externalResearchProfileId)) "Iteration $i external research prompt inherited specialist route profile '$externalResearchProfileId'."

            $designInstructionTarget = Join-Path $workspaceRoot "Designed DLL"
            $designInstructionPlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "at this path $designInstructionTarget design and build a C++ DLL project with CMake and validate it"
                workspace_root = $workspaceRoot
                preferred_target_path = $designInstructionTarget
            } -TimeoutSec 90
            Assert-Aegis ([bool]$designInstructionPlan.ok) "Iteration $i design-instruction plan did not complete successfully."
            Assert-Aegis ([string]$designInstructionPlan.preset.id -eq "cpp-cmake-dll") "Iteration $i design-instruction plan selected '$($designInstructionPlan.preset.id)' instead of cpp-cmake-dll."
            Assert-Aegis ([string]$designInstructionPlan.target_path -eq [string]$designInstructionTarget) "Iteration $i design-instruction prompt swallowed instruction words into the target path."

            $naturalRefinementPlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "at this path $existingDllTarget refine my DLL plugin; it is not a website and should stay native"
                workspace_root = $workspaceRoot
                preferred_target_path = $existingDllTarget
            } -TimeoutSec 90
            Assert-Aegis ([bool]$naturalRefinementPlan.ok) "Iteration $i natural-refinement plan did not complete successfully."
            Assert-Aegis ([string]$naturalRefinementPlan.preset.id -eq "cpp-cmake-dll") "Iteration $i natural-refinement DLL plan selected '$($naturalRefinementPlan.preset.id)' instead of cpp-cmake-dll."
            Assert-Aegis ([string]$naturalRefinementPlan.target_path -eq [string](Resolve-Path -LiteralPath $existingDllTarget)) "Iteration $i natural-refinement prompt swallowed instruction words into the target path."

            $separatorRefinementPlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "at this path $existingDllTarget - refine my DLL plugin; it is not a website and should stay native"
                workspace_root = $workspaceRoot
                preferred_target_path = $existingDllTarget
            } -TimeoutSec 90
            Assert-Aegis ([bool]$separatorRefinementPlan.ok) "Iteration $i separator-refinement plan did not complete successfully."
            Assert-Aegis ([string]$separatorRefinementPlan.preset.id -eq "cpp-cmake-dll") "Iteration $i separator-refinement DLL plan selected '$($separatorRefinementPlan.preset.id)' instead of cpp-cmake-dll."
            Assert-Aegis ([string]$separatorRefinementPlan.target_path -eq [string](Resolve-Path -LiteralPath $existingDllTarget)) "Iteration $i separator-refinement prompt swallowed the separator into the target path."

            $wrapperPathTarget = Join-Path $workspaceRoot "Aegis Tool (1)"
            $wrapperPathPlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "at this path $wrapperPathTarget create a C++ console app and build it"
                workspace_root = $workspaceRoot
            } -TimeoutSec 90
            Assert-Aegis ([bool]$wrapperPathPlan.ok) "Iteration $i wrapper-path plan did not complete successfully."
            Assert-Aegis ([string]$wrapperPathPlan.target_path -eq [System.IO.Path]::GetFullPath($wrapperPathTarget)) "Iteration $i wrapper-path plan dropped balanced punctuation from the target path."

            $apostrophePathTarget = Join-Path $workspaceRoot "Rick Culler's Website"
            $apostrophePathPlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "at this path $apostrophePathTarget create a barber website"
                workspace_root = $workspaceRoot
            } -TimeoutSec 90
            Assert-Aegis ([bool]$apostrophePathPlan.ok) "Iteration $i apostrophe-path plan did not complete successfully."
            Assert-Aegis ([string]$apostrophePathPlan.preset.id -eq "static-html-site") "Iteration $i apostrophe-path website plan selected '$($apostrophePathPlan.preset.id)' instead of static-html-site."
            Assert-Aegis ([string]$apostrophePathPlan.target_path -eq [System.IO.Path]::GetFullPath($apostrophePathTarget)) "Iteration $i apostrophe-path plan truncated the target path."

            $instructionWordPathTarget = Join-Path $workspaceRoot "Aegis Tool With Tests"
            $instructionWordPathPlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "at this path $instructionWordPathTarget create a C++ console app and build it"
                workspace_root = $workspaceRoot
            } -TimeoutSec 90
            Assert-Aegis ([bool]$instructionWordPathPlan.ok) "Iteration $i instruction-word path plan did not complete successfully."
            Assert-Aegis ([string]$instructionWordPathPlan.preset.id -eq "cpp-cmake-cli") "Iteration $i instruction-word path plan selected '$($instructionWordPathPlan.preset.id)' instead of cpp-cmake-cli."
            Assert-Aegis ([string]$instructionWordPathPlan.target_path -eq [System.IO.Path]::GetFullPath($instructionWordPathTarget)) "Iteration $i instruction-word path plan trimmed folder words like 'With Tests' out of the target path."

            $launchToolPathTarget = Join-Path $workspaceRoot "New Launch Tool"
            $launchToolPathPlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "at this path $launchToolPathTarget create a Python CLI called New Launch Tool and build it"
                workspace_root = $workspaceRoot
            } -TimeoutSec 90
            Assert-Aegis ([bool]$launchToolPathPlan.ok) "Iteration $i launch-tool path plan did not complete successfully."
            Assert-Aegis ([string]$launchToolPathPlan.target_path -eq [System.IO.Path]::GetFullPath($launchToolPathTarget)) "Iteration $i launch-tool path plan trimmed folder words like 'Launch Tool' out of the target path."
            Assert-Aegis ([bool]$launchToolPathPlan.scaffold_request.run_validation) "Iteration $i launch-tool path plan did not preserve build intent."

            $failedBuildFollowupPlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "continue from the last failed build"
                workspace_root = $existingDllTarget
                preferred_target_path = $existingDllTarget
            } -TimeoutSec 90
            Assert-Aegis ([bool]$failedBuildFollowupPlan.ok) "Iteration $i failed-build follow-up plan did not complete successfully."
            Assert-Aegis ([bool]$failedBuildFollowupPlan.scaffold_request.run_validation) "Iteration $i failed-build follow-up plan did not enable validation."
            Assert-Aegis ([string]$failedBuildFollowupPlan.target_path -eq [string](Resolve-Path -LiteralPath $existingDllTarget)) "Iteration $i failed-build follow-up plan did not preserve the active workspace target path."

            $bareContinuePlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "continue"
                workspace_root = $existingDllTarget
                preferred_target_path = $existingDllTarget
            } -TimeoutSec 90
            Assert-Aegis ([bool]$bareContinuePlan.ok) "Iteration $i bare continue plan did not complete successfully."
            Assert-Aegis ([string]$bareContinuePlan.preset.id -eq "cpp-cmake-dll") "Iteration $i bare continue plan selected '$($bareContinuePlan.preset.id)' instead of cpp-cmake-dll."
            Assert-Aegis ([string]$bareContinuePlan.execution_mode -eq "existing_validation") "Iteration $i bare continue plan did not switch to existing_validation."
            Assert-Aegis ([bool]$bareContinuePlan.scaffold_request.run_validation) "Iteration $i bare continue plan did not enable validation."
            Assert-Aegis ([string]$bareContinuePlan.target_path -eq [string](Resolve-Path -LiteralPath $existingDllTarget)) "Iteration $i bare continue plan did not preserve the active workspace target path."

            $negatedNativeUiPlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "add a settings UI but do not turn it into a website"
                workspace_root = $existingDllTarget
                preferred_target_path = $existingDllTarget
            } -TimeoutSec 90
            $negatedNativeUiKeywords = @($negatedNativeUiPlan.detected_keywords)
            Assert-Aegis ([bool]$negatedNativeUiPlan.ok) "Iteration $i negated native UI follow-up plan did not complete successfully."
            Assert-Aegis ([string]$negatedNativeUiPlan.preset.id -eq "cpp-cmake-dll") "Iteration $i negated native UI follow-up selected '$($negatedNativeUiPlan.preset.id)' instead of cpp-cmake-dll."
            Assert-Aegis ($negatedNativeUiKeywords -contains "existing workspace continuity") "Iteration $i negated native UI follow-up did not reuse the existing native workspace."
            Assert-Aegis (-not ($negatedNativeUiKeywords -contains "current prompt stack override")) "Iteration $i negated native UI follow-up incorrectly treated negated website wording as a stack override."
            Assert-Aegis (-not ($negatedNativeUiKeywords -contains "stack-lock:web")) "Iteration $i negated native UI follow-up incorrectly added a web stack lock."

            $frontendDriftPlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "continue the roadmap and add a frontend-style diagnostics dashboard without changing stacks"
                workspace_root = $existingDllTarget
                preferred_target_path = $existingDllTarget
            } -TimeoutSec 90
            $frontendDriftKeywords = @($frontendDriftPlan.detected_keywords)
            Assert-Aegis ([bool]$frontendDriftPlan.ok) "Iteration $i frontend drift follow-up plan did not complete successfully."
            Assert-Aegis ([string]$frontendDriftPlan.preset.id -eq "cpp-cmake-dll") "Iteration $i frontend drift follow-up selected '$($frontendDriftPlan.preset.id)' instead of cpp-cmake-dll."
            Assert-Aegis ($frontendDriftKeywords -contains "stack-lock:web") "Iteration $i frontend drift follow-up did not expose the ambiguous web stack-lock signal."
            Assert-Aegis ($frontendDriftKeywords -contains "mission-contract:locked-stack") "Iteration $i frontend drift follow-up did not lock to the existing mission contract."
            Assert-Aegis ($frontendDriftKeywords -contains "existing workspace continuity") "Iteration $i frontend drift follow-up did not preserve existing workspace continuity."
            Assert-Aegis (-not ($frontendDriftKeywords -contains "current prompt stack override")) "Iteration $i frontend drift follow-up incorrectly allowed an accidental stack override."

            $withoutMakingWebsitePlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "add a dashboard to show logs without making a website"
                workspace_root = $existingDllTarget
                preferred_target_path = $existingDllTarget
            } -TimeoutSec 90
            $withoutMakingWebsiteKeywords = @($withoutMakingWebsitePlan.detected_keywords)
            Assert-Aegis ([bool]$withoutMakingWebsitePlan.ok) "Iteration $i without-making-website follow-up plan did not complete successfully."
            Assert-Aegis ([string]$withoutMakingWebsitePlan.preset.id -eq "cpp-cmake-dll") "Iteration $i without-making-website follow-up selected '$($withoutMakingWebsitePlan.preset.id)' instead of cpp-cmake-dll."
            Assert-Aegis (-not ($withoutMakingWebsiteKeywords -contains "stack-lock:web")) "Iteration $i without-making-website follow-up incorrectly added a web stack lock."

            $staleOverridePlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "at this path $staleWebTarget create a C++ DLL shared library with CMake and a host executable, then build it"
                workspace_root = $workspaceRoot
                preferred_target_path = $staleWebTarget
            } -TimeoutSec 90
            $staleOverrideKeywords = @($staleOverridePlan.detected_keywords)
            Assert-Aegis ([bool]$staleOverridePlan.ok) "Iteration $i stale-web override plan did not complete successfully."
            Assert-Aegis ([string]$staleOverridePlan.preset.id -eq "cpp-cmake-dll") "Iteration $i stale-web override selected '$($staleOverridePlan.preset.id)' instead of cpp-cmake-dll."
            Assert-Aegis ($staleOverrideKeywords -contains "current prompt stack override") "Iteration $i stale-web override did not record current prompt stack override."
            Assert-Aegis (-not ($staleOverrideKeywords -contains "existing workspace continuity")) "Iteration $i stale-web override incorrectly reused stale web continuity."

            $solutionRouteTarget = Join-Path $workspaceRoot "Solution Tool"
            $solutionRoutePlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
                prompt = "at this path $solutionRouteTarget combine two Visual Studio sln projects into one and preserve project references"
                workspace_root = $workspaceRoot
                preferred_target_path = $solutionRouteTarget
            } -TimeoutSec 90
            $solutionRouteKeywords = @($solutionRoutePlan.detected_keywords)
            Assert-Aegis ([bool]$solutionRoutePlan.ok) "Iteration $i solution route plan did not complete successfully."
            Assert-Aegis ([string]$solutionRoutePlan.preset.id -eq "python-sln-refactor-tool") "Iteration $i solution route selected '$($solutionRoutePlan.preset.id)' instead of python-sln-refactor-tool."
            Assert-Aegis ([string]$solutionRoutePlan.target_path -eq [string](Join-Path $workspaceRoot "Solution Tool")) "Iteration $i solution route swallowed the instruction into the target path."
            Assert-Aegis ($solutionRouteKeywords -contains "stack-lock:solution-refactor") "Iteration $i solution route did not preserve the solution-refactor stack lock."

            return @{
                preset_count = $presetCount
                cpp_plan = $cppProjectName
                full_stack_plan = $fullStackProjectName
                dll_plan = [string]$dllPlan.preset.id
                design_instruction_plan = [string]$designInstructionPlan.preset.id
                natural_refinement_plan = [string]$naturalRefinementPlan.preset.id
                separator_refinement_plan = [string]$separatorRefinementPlan.preset.id
                wrapper_path_plan = [string]$wrapperPathPlan.preset.id
                apostrophe_path_plan = [string]$apostrophePathPlan.preset.id
                failed_build_followup_validation = [bool]$failedBuildFollowupPlan.scaffold_request.run_validation
                bare_continue_execution_mode = [string]$bareContinuePlan.execution_mode
                negated_native_ui_plan = [string]$negatedNativeUiPlan.preset.id
                without_making_website_plan = [string]$withoutMakingWebsitePlan.preset.id
                stale_override_plan = [string]$staleOverridePlan.preset.id
                solution_route_plan = [string]$solutionRoutePlan.preset.id
            }
        }

        $durations.Add([double]$call.Milliseconds)
        $lastPresetCount = [int]$call.Result.preset_count
        $lastCppPlan = [string]$call.Result.cpp_plan
        $lastFullStackPlan = [string]$call.Result.full_stack_plan
        if (($i % 10) -eq 0 -or $i -eq $ApiIterations) {
            Write-Host "API iteration $i/$ApiIterations passed in $($call.Milliseconds) ms"
        }
    }
    catch {
        $message = "Iteration $i failed: $($_.Exception.Message)"
        $failures.Add($message)
        Write-Warning $message
    }
}

$nativeContinuityRoot = Join-Path $workspaceRoot ("native-continuity-smoke-" + (New-Guid).ToString("N"))
New-Item -ItemType Directory -Force -Path (Join-Path $nativeContinuityRoot "src") | Out-Null
Write-AegisUtf8NoBom -Path (Join-Path $nativeContinuityRoot "CMakeLists.txt") -Value @"
cmake_minimum_required(VERSION 3.20)
project(AegisNativeContinuity LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_executable(AegisNativeContinuity src/main.cpp)
"@
Write-AegisUtf8NoBom -Path (Join-Path $nativeContinuityRoot "src\main.cpp") -Value @"
#include <iostream>

int main() {
    std::cout << "Native continuity smoke" << std::endl;
    return 0;
}
"@
$nativeContinuityPlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
    prompt = "you didn't build it, build it and fix any errors"
    workspace_root = $nativeContinuityRoot
} -TimeoutSec 90
Assert-Aegis ([bool]$nativeContinuityPlan.ok) "Native continuity smoke plan did not complete successfully."
Assert-Aegis ([string]$nativeContinuityPlan.preset.id -eq "cpp-cmake-cli") "Native continuity smoke selected '$($nativeContinuityPlan.preset.id)' instead of cpp-cmake-cli."
Assert-Aegis ([string]$nativeContinuityPlan.execution_mode -eq "existing_validation") "Native continuity smoke did not stay in existing_validation mode."
Assert-Aegis ([string]$nativeContinuityPlan.primary_action -eq "validate_existing_project") "Native continuity smoke did not expose validate_existing_project action."
Assert-Aegis ([string]$nativeContinuityPlan.validation_command -eq "cmake -S . -B build && cmake --build build --config Release") "Native continuity smoke selected unexpected command '$($nativeContinuityPlan.validation_command)'."
Assert-Aegis ([string]$nativeContinuityPlan.scaffold_request.validation_command -eq [string]$nativeContinuityPlan.validation_command) "Native continuity smoke scaffold request did not mirror the corrected validation command."
$nativeContinuityCommandSmoke = @{
    target_path = $nativeContinuityRoot
    preset_id = [string]$nativeContinuityPlan.preset.id
    execution_mode = [string]$nativeContinuityPlan.execution_mode
    validation_command = [string]$nativeContinuityPlan.validation_command
}
Write-Host "Native continuity command smoke test passed at $nativeContinuityRoot"

$genericPlanRoot = Join-Path $workspaceRoot ("generic-plan-smoke-" + (New-Guid).ToString("N"))
New-Item -ItemType Directory -Force -Path $genericPlanRoot | Out-Null
Set-Content -LiteralPath (Join-Path $genericPlanRoot "anything.md") -Encoding UTF8 -Value @"
# Launch Blueprint

## Product Goal
Build the smallest reliable desktop-ready coding assistant test workspace.

## MVP Work Items
- [ ] Run the CMake release build.
- [ ] Add a smoke test that proves the executable starts.
- [ ] Document the finished verification steps.
- [x] Pick the C++ console app stack.
"@

$encodedGenericPlanRoot = [Uri]::EscapeDataString($genericPlanRoot)
$genericProfile = Invoke-AegisJsonGet "$BackendUrl/api/workspace/profile?workspace_root=$encodedGenericPlanRoot"
$genericReadiness = Assert-AegisReadiness -Profile $genericProfile -Label "Generic instruction smoke"
Assert-Aegis ([string]$genericReadiness.status -eq "needs_work") "Generic instruction smoke readiness should be needs_work for open arbitrary Markdown instructions, got '$($genericReadiness.status)'."
Assert-AegisInstructionStatusHasNoMetadataNoise -Profile $genericProfile -Label "Generic instruction smoke"

$genericAutopilotStatus = Invoke-AegisJsonGet "$BackendUrl/api/workspace/autopilot-status?workspace_root=$encodedGenericPlanRoot"
Assert-Aegis ([string]$genericAutopilotStatus.phase -eq "work") "Generic instruction smoke autopilot phase should be work, got '$($genericAutopilotStatus.phase)'."
Assert-Aegis ([bool]$genericAutopilotStatus.should_continue) "Generic instruction smoke autopilot did not recommend continuation."
Assert-Aegis (@($genericAutopilotStatus.instruction_files).Count -gt 0) "Generic instruction smoke autopilot did not return instruction files."
Assert-Aegis ([string]$genericAutopilotStatus.instruction_files[0].path -eq "anything.md") "Generic instruction smoke autopilot did not preserve the arbitrary instruction filename."
Assert-Aegis (@($genericAutopilotStatus.next_open_items).Count -ge 3) "Generic instruction smoke autopilot did not return the next open instruction queue."
$genericNextOpenText = (@($genericAutopilotStatus.next_open_items) -join "`n")
Assert-Aegis ($genericNextOpenText -match "CMake release build") "Generic instruction smoke autopilot queue missed the CMake release build item."
Assert-Aegis ([string]$genericAutopilotStatus.suggested_prompt -match "Next open instruction items") "Generic instruction smoke autopilot prompt did not include queued instruction details."

$genericInstructionSmoke = @{
    target_path = $genericPlanRoot
    readiness_status = [string]$genericReadiness.status
    readiness_score = [int]$genericReadiness.score
    autopilot_phase = [string]$genericAutopilotStatus.phase
    instruction_file = [string]$genericAutopilotStatus.instruction_files[0].path
    first_open_item = [string]$genericAutopilotStatus.next_open_items[0]
    open_item_count = @($genericAutopilotStatus.next_open_items).Count
}
Write-Host "Generic instruction smoke test passed at $genericPlanRoot"

if ($RunScaffoldSmoke) {
    $scaffoldRoot = Join-Path $workspaceRoot ("scaffold-smoke-" + (New-Guid).ToString("N"))
    $scaffoldPrompt = "Create a C++ CMake console app called Stress Console that prints hello world, waits for Enter, and also build it."
    Write-Host "Running scaffold smoke test at $scaffoldRoot..."

    $scaffold = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/scaffold" @{
        target_path = $scaffoldRoot
        preset_id = "cpp-cmake-cli"
        project_name = "Stress Console"
        prompt = $scaffoldPrompt
        run_validation = $true
        overwrite = $true
    } -TimeoutSec 180

    Assert-Aegis ([bool]$scaffold.ok) "Scaffold smoke request did not complete successfully."
    Assert-Aegis ([string]$scaffold.preset.id -eq "cpp-cmake-cli") "Scaffold smoke selected '$($scaffold.preset.id)' instead of cpp-cmake-cli."
    Assert-Aegis ($null -ne $scaffold.validation) "Scaffold smoke did not include validation output."
    Assert-Aegis ([int]$scaffold.validation.exit_code -eq 0) "Scaffold smoke validation failed with exit code $($scaffold.validation.exit_code)."
    Assert-Aegis (-not [string]::IsNullOrWhiteSpace([string]$scaffold.build_log_path)) "Scaffold smoke did not return a build_log_path."

    $buildLogPath = Join-Path ([string]$scaffold.target_path) ([string]$scaffold.build_log_path)
    Assert-Aegis (Test-Path -LiteralPath $buildLogPath) "Scaffold smoke build log was not written at $buildLogPath."
    $buildLog = Get-Content -LiteralPath $buildLogPath -Raw
    Assert-Aegis ($buildLog.Contains("Aegis Build Log")) "Scaffold smoke build log is missing its title."
    Assert-Aegis ($buildLog.Contains("Validation")) "Scaffold smoke build log is missing validation details."

    $commandHistoryPath = Join-Path ([string]$scaffold.target_path) ".aegis\command_history.json"
    Assert-Aegis (Test-Path -LiteralPath $commandHistoryPath) "Scaffold smoke command history was not written at $commandHistoryPath."
    $commandHistory = Get-Content -LiteralPath $commandHistoryPath -Raw | ConvertFrom-Json
    $validationHistory = @($commandHistory.commands | Where-Object { [string]$_.kind -eq "validation" })
    Assert-Aegis ($validationHistory.Count -gt 0) "Scaffold smoke command history did not include validation."
    $latestValidation = $validationHistory[$validationHistory.Count - 1]
    Assert-Aegis ([string]$latestValidation.status -eq "passed") "Scaffold smoke latest validation history was not marked passed."
    Assert-Aegis ([string]$latestValidation.build_log_path -eq [string]$scaffold.build_log_path) "Scaffold smoke validation history did not link the saved build log."

    $encodedScaffoldRoot = [Uri]::EscapeDataString([string]$scaffold.target_path)
    $scaffoldProfile = Invoke-AegisJsonGet "$BackendUrl/api/workspace/profile?workspace_root=$encodedScaffoldRoot"
    $scaffoldReadiness = Assert-AegisReadiness -Profile $scaffoldProfile -Label "Scaffold smoke"
    Assert-Aegis ([string]$scaffoldReadiness.status -ne "unconfigured") "Scaffold smoke readiness stayed unconfigured after generated project metadata."
    Assert-AegisInstructionStatusHasNoMetadataNoise -Profile $scaffoldProfile -Label "Scaffold smoke"
    $scaffoldInstructionStatus = Get-AegisPropertyValue -Object $scaffoldProfile -Name "instruction_status"
    $scaffoldInstructionFiles = @(Get-AegisPropertyValue -Object $scaffoldInstructionStatus -Name "files")
    $scaffoldPendingText = (($scaffoldInstructionFiles | ForEach-Object { @(Get-AegisPropertyValue -Object $_ -Name "pending_items") }) -join "`n")
    Assert-Aegis ($scaffoldPendingText -match "Complete the requested command-line behavior") "Scaffold smoke did not write the C++ console autopilot checklist."

    $scaffoldAutopilotStatus = Invoke-AegisJsonGet "$BackendUrl/api/workspace/autopilot-status?workspace_root=$encodedScaffoldRoot"
    Assert-Aegis ([string]$scaffoldAutopilotStatus.phase -eq "work") "Scaffold smoke autopilot phase should be work, got '$($scaffoldAutopilotStatus.phase)'."
    Assert-Aegis ([bool]$scaffoldAutopilotStatus.should_continue) "Scaffold smoke autopilot status did not recommend continuation for open checklist items."
    Assert-Aegis ([string]$scaffoldAutopilotStatus.recommended_mode -eq "build") "Scaffold smoke autopilot status should recommend build mode."
    Assert-Aegis ([string]$scaffoldAutopilotStatus.suggested_prompt -match "Complete the requested command-line behavior") "Scaffold smoke autopilot prompt did not preserve the next checklist item."
    Assert-Aegis ([int]$scaffoldAutopilotStatus.pass_budget -ge 4) "Scaffold smoke autopilot pass budget was too low."

    $scaffoldSmoke = @{
        target_path = [string]$scaffold.target_path
        build_log_path = [string]$scaffold.build_log_path
        validation_exit_code = [int]$scaffold.validation.exit_code
        readiness_status = [string]$scaffoldReadiness.status
        readiness_score = [int]$scaffoldReadiness.score
        readiness_next_action = [string]$scaffoldReadiness.next_action
        autopilot_phase = [string]$scaffoldAutopilotStatus.phase
        autopilot_pass_budget = [int]$scaffoldAutopilotStatus.pass_budget
        first_open_item = [string]($scaffoldPendingText -split "`n" | Select-Object -First 1)
    }

    Write-Host "Scaffold smoke test passed. Build log: $buildLogPath"

    $msvcSmokeRoot = Join-Path $workspaceRoot ("msvc-console-smoke-" + (New-Guid).ToString("N"))
    $msvcPrompt = "Create a C++ Visual Studio console app called Stress Console Sln that prints hello world, waits for Enter, and also build it."
    Write-Host "Running MSVC console solution smoke test at $msvcSmokeRoot..."

    $msvcScaffold = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/scaffold" @{
        target_path = $msvcSmokeRoot
        preset_id = "cpp-msvc-console-sln"
        project_name = "Stress Console Sln"
        prompt = $msvcPrompt
        run_validation = $true
        overwrite = $true
    } -TimeoutSec 240

    Assert-Aegis ([bool]$msvcScaffold.ok) "MSVC console smoke request did not complete successfully."
    Assert-Aegis ([string]$msvcScaffold.preset.id -eq "cpp-msvc-console-sln") "MSVC console smoke selected '$($msvcScaffold.preset.id)' instead of cpp-msvc-console-sln."
    Assert-Aegis ($null -ne $msvcScaffold.validation) "MSVC console smoke did not include validation output."
    Assert-Aegis ([int]$msvcScaffold.validation.exit_code -eq 0) "MSVC console smoke validation failed with exit code $($msvcScaffold.validation.exit_code): $($msvcScaffold.validation.stderr)"
    Assert-Aegis ([string]$msvcScaffold.validation.command -eq "python build.py") "MSVC console smoke ran unexpected validation command '$($msvcScaffold.validation.command)'."
    Assert-Aegis ([string]$msvcScaffold.validation.stdout -match "Hello, world!") "MSVC console smoke did not capture hello-world output from the built executable."
    Assert-Aegis (-not [string]::IsNullOrWhiteSpace([string]$msvcScaffold.build_log_path)) "MSVC console smoke did not return a build_log_path."

    $msvcBuildLogPath = Join-Path ([string]$msvcScaffold.target_path) ([string]$msvcScaffold.build_log_path)
    Assert-Aegis (Test-Path -LiteralPath $msvcBuildLogPath) "MSVC console smoke build log was not written at $msvcBuildLogPath."
    $msvcCommandHistoryPath = Join-Path ([string]$msvcScaffold.target_path) ".aegis\command_history.json"
    Assert-Aegis (Test-Path -LiteralPath $msvcCommandHistoryPath) "MSVC console smoke command history was not written at $msvcCommandHistoryPath."
    $msvcCommandHistory = Get-Content -LiteralPath $msvcCommandHistoryPath -Raw | ConvertFrom-Json
    $msvcValidationHistory = @($msvcCommandHistory.commands | Where-Object { [string]$_.kind -eq "validation" })
    Assert-Aegis ($msvcValidationHistory.Count -gt 0) "MSVC console smoke command history did not include validation."
    $latestMsvcValidation = $msvcValidationHistory[$msvcValidationHistory.Count - 1]
    Assert-Aegis ([string]$latestMsvcValidation.status -eq "passed") "MSVC console smoke latest validation history was not marked passed."
    Assert-Aegis ([string]$latestMsvcValidation.build_log_path -eq [string]$msvcScaffold.build_log_path) "MSVC console smoke validation history did not link the saved build log."

    $msvcConsoleSmoke = @{
        target_path = [string]$msvcScaffold.target_path
        build_log_path = [string]$msvcScaffold.build_log_path
        validation_command = [string]$msvcScaffold.validation.command
        validation_exit_code = [int]$msvcScaffold.validation.exit_code
    }

    Write-Host "MSVC console solution smoke test passed. Build log: $msvcBuildLogPath"

    $cppDllRoot = Join-Path $workspaceRoot ("cpp-dll-host-smoke-" + (New-Guid).ToString("N"))
    Write-Host "Running C++ DLL host loader smoke test at $cppDllRoot..."

    $cppDllScaffold = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/scaffold" @{
        target_path = $cppDllRoot
        preset_id = "cpp-cmake-dll"
        project_name = "Runtime Plugin"
        prompt = "Create a C++ DLL plugin called Runtime Plugin with exported API functions, a host exe, and validation."
        run_validation = $true
        overwrite = $true
        max_repair_attempts = 0
    } -TimeoutSec 240

    Assert-Aegis ([bool]$cppDllScaffold.ok) "C++ DLL host smoke request did not complete successfully."
    Assert-Aegis ([string]$cppDllScaffold.preset.id -eq "cpp-cmake-dll") "C++ DLL host smoke selected '$($cppDllScaffold.preset.id)' instead of cpp-cmake-dll."
    Assert-Aegis ($null -ne $cppDllScaffold.validation) "C++ DLL host smoke did not include validation output."
    Assert-Aegis ([int]$cppDllScaffold.validation.exit_code -eq 0) "C++ DLL host smoke validation failed with exit code $($cppDllScaffold.validation.exit_code): $($cppDllScaffold.validation.stderr)"
    Assert-Aegis ([string]$cppDllScaffold.validation.command -eq "python build.py") "C++ DLL host smoke ran unexpected validation command '$($cppDllScaffold.validation.command)'."
    Assert-Aegis ([string]$cppDllScaffold.validation.stdout -match "Host loaded plugin: Runtime Plugin") "C++ DLL host smoke did not validate runtime library loading."
    Assert-Aegis ([string]$cppDllScaffold.validation.stdout -match "aegis_add\(21, 21\)=42") "C++ DLL host smoke did not validate exported function calls."

    $cppDllTarget = [string]$cppDllScaffold.target_path
    $cppDllHostPath = Join-Path $cppDllTarget "host\main.cpp"
    $cppDllHeaderPath = Join-Path $cppDllTarget "include\runtime_plugin\library.h"
    Assert-Aegis (Test-Path -LiteralPath $cppDllHostPath) "C++ DLL host smoke did not write host/main.cpp."
    Assert-Aegis (Test-Path -LiteralPath $cppDllHeaderPath) "C++ DLL host smoke did not write the exported API header."
    Assert-Aegis ((Get-Content -LiteralPath $cppDllHostPath -Raw) -match "GetProcAddress|dlsym") "C++ DLL host smoke host loader is missing runtime symbol lookup."
    Assert-Aegis ((Get-Content -LiteralPath $cppDllHeaderPath -Raw) -match "aegis_plugin_description") "C++ DLL host smoke header is missing exported plugin metadata."
    Assert-Aegis (-not [string]::IsNullOrWhiteSpace([string]$cppDllScaffold.build_log_path)) "C++ DLL host smoke did not return a build_log_path."

    $cppDllBuildLogPath = Join-Path $cppDllTarget ([string]$cppDllScaffold.build_log_path)
    Assert-Aegis (Test-Path -LiteralPath $cppDllBuildLogPath) "C++ DLL host smoke build log was not written at $cppDllBuildLogPath."

    $cppDllHostSmoke = @{
        target_path = $cppDllTarget
        build_log_path = [string]$cppDllScaffold.build_log_path
        validation_command = [string]$cppDllScaffold.validation.command
        validation_exit_code = [int]$cppDllScaffold.validation.exit_code
        host_loader = "host/main.cpp"
        exported_metadata = $true
    }

    Write-Host "C++ DLL host loader smoke test passed. Build log: $cppDllBuildLogPath"

    $windowsInternalsRoot = Join-Path $workspaceRoot ("windows-internals-minhook-smoke-" + (New-Guid).ToString("N"))
    Write-Host "Running Windows internals MinHook adapter smoke test at $windowsInternalsRoot..."

    $windowsInternalsScaffold = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/scaffold" @{
        target_path = $windowsInternalsRoot
        preset_id = "cpp-windows-internals-hooking"
        project_name = "Internals Hook Lab"
        prompt = "Create a C++ Windows internals MinHook instrumentation tool for authorized module diagnostics and validate it."
        run_validation = $true
        overwrite = $true
        max_repair_attempts = 0
    } -TimeoutSec 240

    Assert-Aegis ([bool]$windowsInternalsScaffold.ok) "Windows internals smoke request did not complete successfully."
    Assert-Aegis ([string]$windowsInternalsScaffold.preset.id -eq "cpp-windows-internals-hooking") "Windows internals smoke selected '$($windowsInternalsScaffold.preset.id)' instead of cpp-windows-internals-hooking."
    Assert-Aegis ($null -ne $windowsInternalsScaffold.validation) "Windows internals smoke did not include validation output."
    Assert-Aegis ([int]$windowsInternalsScaffold.validation.exit_code -eq 0) "Windows internals smoke validation failed with exit code $($windowsInternalsScaffold.validation.exit_code): $($windowsInternalsScaffold.validation.stderr)"
    Assert-Aegis ([string]$windowsInternalsScaffold.validation.command -eq "python build.py") "Windows internals smoke ran unexpected validation command '$($windowsInternalsScaffold.validation.command)'."
    Assert-Aegis ([string]$windowsInternalsScaffold.validation.stdout -match "Windows internals tool") "Windows internals smoke did not run the generated executable validation."
    Assert-Aegis ([string]$windowsInternalsScaffold.validation.stdout -match "Hook preview=Hook preview validated through MinHook-compatible API boundary\.") "Windows internals smoke did not validate the MinHook adapter preview path."

    $windowsInternalsTarget = [string]$windowsInternalsScaffold.target_path
    $windowsMinHookShimPath = Join-Path $windowsInternalsTarget "vendor\minhook_shim\MinHook.h"
    $windowsMinHookAdapterPath = Join-Path $windowsInternalsTarget "include\internals_hook_lab\minhook_adapter.h"
    Assert-Aegis (Test-Path -LiteralPath $windowsMinHookShimPath) "Windows internals smoke did not create the embedded MinHook shim at $windowsMinHookShimPath."
    Assert-Aegis (Test-Path -LiteralPath $windowsMinHookAdapterPath) "Windows internals smoke did not create the MinHook adapter at $windowsMinHookAdapterPath."
    Assert-Aegis ((Get-Content -LiteralPath $windowsMinHookShimPath -Raw) -match "MH_CreateHook") "Windows internals smoke shim is missing MH_CreateHook."
    Assert-Aegis ((Get-Content -LiteralPath $windowsMinHookAdapterPath -Raw) -match "install_preview") "Windows internals smoke adapter is missing install_preview."
    Assert-Aegis (-not [string]::IsNullOrWhiteSpace([string]$windowsInternalsScaffold.build_log_path)) "Windows internals smoke did not return a build_log_path."

    $windowsInternalsBuildLogPath = Join-Path $windowsInternalsTarget ([string]$windowsInternalsScaffold.build_log_path)
    Assert-Aegis (Test-Path -LiteralPath $windowsInternalsBuildLogPath) "Windows internals smoke build log was not written at $windowsInternalsBuildLogPath."

    $windowsInternalsMinHookSmoke = @{
        target_path = $windowsInternalsTarget
        build_log_path = [string]$windowsInternalsScaffold.build_log_path
        validation_command = [string]$windowsInternalsScaffold.validation.command
        validation_exit_code = [int]$windowsInternalsScaffold.validation.exit_code
        shim_path = "vendor/minhook_shim/MinHook.h"
        adapter_preview = $true
    }

    Write-Host "Windows internals MinHook adapter smoke test passed. Build log: $windowsInternalsBuildLogPath"

    $solutionRefactorRoot = Join-Path $workspaceRoot ("solution-refactor-materialize-smoke-" + (New-Guid).ToString("N"))
    Write-Host "Running Visual Studio solution materialize smoke test at $solutionRefactorRoot..."

    $solutionRefactorScaffold = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/scaffold" @{
        target_path = $solutionRefactorRoot
        preset_id = "python-sln-refactor-tool"
        project_name = "Solution Surgeon"
        prompt = "Create a Visual Studio solution tool that can merge two sln files, split a project into its own sln, copy the referenced vcxproj folders, and validate it."
        run_validation = $true
        overwrite = $true
        max_repair_attempts = 0
    } -TimeoutSec 180

    Assert-Aegis ([bool]$solutionRefactorScaffold.ok) "Solution refactor materialize smoke request did not complete successfully."
    Assert-Aegis ([string]$solutionRefactorScaffold.preset.id -eq "python-sln-refactor-tool") "Solution refactor materialize smoke selected '$($solutionRefactorScaffold.preset.id)' instead of python-sln-refactor-tool."
    Assert-Aegis ($null -ne $solutionRefactorScaffold.validation) "Solution refactor materialize smoke did not include validation output."
    Assert-Aegis ([int]$solutionRefactorScaffold.validation.exit_code -eq 0) "Solution refactor materialize smoke validation failed with exit code $($solutionRefactorScaffold.validation.exit_code): $($solutionRefactorScaffold.validation.stderr)"
    Assert-Aegis ([string]$solutionRefactorScaffold.validation.command -eq "python build.py") "Solution refactor materialize smoke ran unexpected validation command '$($solutionRefactorScaffold.validation.command)'."
    Assert-Aegis ([string]$solutionRefactorScaffold.validation.stdout -match "Visual Studio solution refactor validation passed") "Solution refactor materialize smoke did not run generated validation."

    $solutionRefactorTarget = [string]$solutionRefactorScaffold.target_path
    $solutionRefactorSourcePath = Join-Path $solutionRefactorTarget "solution_surgeon\sln.py"
    $solutionRefactorCliPath = Join-Path $solutionRefactorTarget "solution_surgeon\cli.py"
    $solutionRefactorMergedProject = Join-Path $solutionRefactorTarget "merged\AppOne\AppOne.vcxproj"
    $solutionRefactorMergedReference = Join-Path $solutionRefactorTarget "merged\Shared\Shared.vcxproj"
    $solutionRefactorSplitProject = Join-Path $solutionRefactorTarget "split\AppTwo\AppTwo.vcxproj"
    $solutionRefactorSplitReference = Join-Path $solutionRefactorTarget "split\Shared\Shared.vcxproj"
    $solutionRefactorSampleProject = Join-Path $solutionRefactorTarget "samples\AppOne\AppOne.vcxproj"
    Assert-Aegis (Test-Path -LiteralPath $solutionRefactorSourcePath) "Solution refactor materialize smoke did not create sln.py."
    Assert-Aegis (Test-Path -LiteralPath $solutionRefactorCliPath) "Solution refactor materialize smoke did not create cli.py."
    Assert-Aegis ((Get-Content -LiteralPath $solutionRefactorSourcePath -Raw) -match "materialize_merge") "Solution refactor materialize smoke is missing materialize_merge."
    Assert-Aegis ((Get-Content -LiteralPath $solutionRefactorSourcePath -Raw) -match "analyze_vcxproj") "Solution refactor materialize smoke is missing vcxproj analysis."
    Assert-Aegis ((Get-Content -LiteralPath $solutionRefactorSourcePath -Raw) -match "build_solution_graph") "Solution refactor materialize smoke is missing dependency graph analysis."
    Assert-Aegis ((Get-Content -LiteralPath $solutionRefactorSourcePath -Raw) -match "build_order") "Solution refactor materialize smoke is missing build-order output."
    Assert-Aegis ((Get-Content -LiteralPath $solutionRefactorSourcePath -Raw) -match "copy_projects") "Solution refactor materialize smoke is missing copy-project support."
    Assert-Aegis ((Get-Content -LiteralPath $solutionRefactorCliPath -Raw) -match "--copy-projects") "Solution refactor materialize smoke CLI is missing --copy-projects."
    Assert-Aegis ((Get-Content -LiteralPath $solutionRefactorCliPath -Raw) -match "--include-references") "Solution refactor materialize smoke CLI is missing --include-references."
    Assert-Aegis ((Get-Content -LiteralPath $solutionRefactorCliPath -Raw) -match "analyze") "Solution refactor materialize smoke CLI is missing analyze command."
    Assert-Aegis ((Get-Content -LiteralPath $solutionRefactorCliPath -Raw) -match "graph") "Solution refactor materialize smoke CLI is missing graph command."
    Assert-Aegis (Test-Path -LiteralPath $solutionRefactorMergedProject) "Solution refactor materialize smoke did not copy merged AppOne.vcxproj."
    Assert-Aegis (Test-Path -LiteralPath $solutionRefactorMergedReference) "Solution refactor materialize smoke did not copy merged Shared.vcxproj."
    Assert-Aegis (Test-Path -LiteralPath $solutionRefactorSplitProject) "Solution refactor materialize smoke did not copy split AppTwo.vcxproj."
    Assert-Aegis (Test-Path -LiteralPath $solutionRefactorSplitReference) "Solution refactor materialize smoke did not copy referenced Shared.vcxproj."
    Assert-Aegis (Test-Path -LiteralPath $solutionRefactorSampleProject) "Solution refactor materialize smoke did not create the sample AppOne.vcxproj."
    Assert-Aegis ((Get-Content -LiteralPath $solutionRefactorSampleProject -Raw) -match "d3d11\.lib") "Solution refactor materialize smoke sample project is missing native linker dependency metadata."
    Assert-Aegis ((Get-Content -LiteralPath $solutionRefactorSampleProject -Raw) -match "ProjectReference") "Solution refactor materialize smoke sample project is missing project reference metadata."

    $solutionRefactorMaterializeSmoke = @{
        target_path = $solutionRefactorTarget
        build_log_path = [string]$solutionRefactorScaffold.build_log_path
        validation_command = [string]$solutionRefactorScaffold.validation.command
        validation_exit_code = [int]$solutionRefactorScaffold.validation.exit_code
        materialize_merge = $true
        copy_projects = $true
        vcxproj_analysis = $true
        include_references = $true
        build_order = $true
    }

    Write-Host "Visual Studio solution materialize smoke test passed."

    $continuityPlan = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/plan" @{
        prompt = "at this path $($msvcScaffold.target_path) build it and fix any errors"
        workspace_root = $workspaceRoot
        preferred_target_path = [string]$msvcScaffold.target_path
    } -TimeoutSec 60
    Assert-Aegis ([bool]$continuityPlan.ok) "Continuity smoke plan did not complete successfully."
    Assert-Aegis ([string]$continuityPlan.preset.id -eq "cpp-msvc-console-sln") "Continuity smoke selected '$($continuityPlan.preset.id)' instead of cpp-msvc-console-sln."
    Assert-Aegis ([string]$continuityPlan.execution_mode -eq "existing_validation") "Continuity smoke plan did not expose existing_validation mode."
    Assert-Aegis ([string]$continuityPlan.primary_action -eq "validate_existing_project") "Continuity smoke plan did not expose validate_existing_project action."
    Assert-Aegis ([string]$continuityPlan.target_path -eq [string]$msvcScaffold.target_path) "Continuity smoke changed the target path unexpectedly."
    Assert-Aegis ([bool]$continuityPlan.scaffold_request.run_validation) "Continuity smoke did not preserve build/validation intent."
    Assert-Aegis (@($continuityPlan.detected_keywords) -contains "existing workspace continuity") "Continuity smoke did not report existing workspace continuity."

    $continuityScaffold = Invoke-AegisJsonPost "$BackendUrl/api/project-builder/scaffold" @{
        target_path = [string]$msvcScaffold.target_path
        prompt = "at this path $($msvcScaffold.target_path) build it and fix any errors"
        max_repair_attempts = 0
    } -TimeoutSec 240
    Assert-Aegis ([bool]$continuityScaffold.ok) "Continuity scaffold smoke did not complete successfully."
    Assert-Aegis ([string]$continuityScaffold.message -match "existing project") "Continuity scaffold smoke did not enter existing-project mode."
    Assert-Aegis ([string]$continuityScaffold.execution_mode -eq "existing_validation") "Continuity scaffold smoke did not expose existing_validation mode."
    Assert-Aegis ([string]$continuityScaffold.primary_action -eq "validate_existing_project") "Continuity scaffold smoke did not expose validate_existing_project action."
    Assert-Aegis ([int]$continuityScaffold.file_change_count -eq 0) "Continuity scaffold smoke reported file changes for an existing-project validation pass."
    Assert-Aegis (@($continuityScaffold.files).Count -eq 0) "Continuity scaffold smoke unexpectedly planned starter files."
    Assert-Aegis (@($continuityScaffold.applied).Count -eq 0) "Continuity scaffold smoke unexpectedly applied file changes."
    Assert-Aegis ($null -ne $continuityScaffold.validation) "Continuity scaffold smoke did not run validation."
    Assert-Aegis ([int]$continuityScaffold.validation.exit_code -eq 0) "Continuity scaffold validation failed with exit code $($continuityScaffold.validation.exit_code)."
    Assert-Aegis ([string]$continuityScaffold.validation.command -eq "python build.py") "Continuity scaffold smoke ran unexpected validation command '$($continuityScaffold.validation.command)'."

    $continuitySmoke = @{
        target_path = [string]$continuityPlan.target_path
        preset_id = [string]$continuityPlan.preset.id
        execution_mode = [string]$continuityScaffold.execution_mode
        primary_action = [string]$continuityScaffold.primary_action
        run_validation = [bool]$continuityPlan.scaffold_request.run_validation
        file_change_count = [int]$continuityScaffold.file_change_count
        scaffold_files = @($continuityScaffold.files).Count
        applied_changes = @($continuityScaffold.applied).Count
        validation_exit_code = [int]$continuityScaffold.validation.exit_code
    }
    Write-Host "Existing project continuity smoke test passed."

    $cmakeSmokeRoot = Join-Path $workspaceRoot ("cmake-validation-smoke-" + (New-Guid).ToString("N"))
    $cmakeSmokeSrc = Join-Path $cmakeSmokeRoot "src"
    New-Item -ItemType Directory -Force -Path $cmakeSmokeSrc | Out-Null
    Set-Content -LiteralPath (Join-Path $cmakeSmokeRoot "CMakeLists.txt") -Encoding UTF8 -Value @"
cmake_minimum_required(VERSION 3.20)
project(AegisCMakeSmoke LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_executable(AegisCMakeSmoke src/main.cpp)
"@
    Set-Content -LiteralPath (Join-Path $cmakeSmokeSrc "main.cpp") -Encoding UTF8 -Value @"
#include <iostream>

int main() {
    std::cout << "Aegis CMake smoke" << std::endl;
    return 0;
}
"@

    $encodedCmakeSmokeRoot = [Uri]::EscapeDataString($cmakeSmokeRoot)
    $cmakeProfile = Invoke-AegisJsonGet "$BackendUrl/api/validation/profile?workspace_root=$encodedCmakeSmokeRoot"
    Assert-Aegis ($null -ne $cmakeProfile.profile) "CMake validation smoke did not infer a validation profile."
    Assert-Aegis ([string]$cmakeProfile.profile.command -eq "cmake -S . -B build && cmake --build build") "CMake validation smoke inferred '$($cmakeProfile.profile.command)' instead of the configure+build chain."

    $cmakeValidation = Invoke-AegisJsonPost "$BackendUrl/api/validate" @{
        workspace_root = $cmakeSmokeRoot
    } -TimeoutSec 180
    Assert-Aegis ($null -ne $cmakeValidation.validation) "CMake validation smoke did not return validation output."
    Assert-Aegis ([int]$cmakeValidation.validation.exit_code -eq 0) "CMake validation smoke failed with exit code $($cmakeValidation.validation.exit_code)."
    Assert-Aegis ([string]$cmakeValidation.validation.command -eq "cmake -S . -B build && cmake --build build") "CMake validation smoke ran an unexpected command '$($cmakeValidation.validation.command)'."

    $cmakeHistoryPath = Join-Path $cmakeSmokeRoot ".aegis\command_history.json"
    Assert-Aegis (Test-Path -LiteralPath $cmakeHistoryPath) "CMake validation smoke did not persist command history."
    $cmakeHistory = Get-Content -LiteralPath $cmakeHistoryPath -Raw | ConvertFrom-Json
    $cmakeValidationHistory = @($cmakeHistory.commands | Where-Object { [string]$_.kind -eq "validation" })
    Assert-Aegis ($cmakeValidationHistory.Count -gt 0) "CMake validation smoke history did not include validation."
    $latestCmakeValidation = $cmakeValidationHistory[$cmakeValidationHistory.Count - 1]
    Assert-Aegis ([string]$latestCmakeValidation.status -eq "passed") "CMake validation smoke history was not marked passed."
    Assert-Aegis (-not [string]::IsNullOrWhiteSpace([string]$latestCmakeValidation.build_log_path)) "CMake validation smoke history did not link a build log."
    Assert-Aegis (@($latestCmakeValidation.steps).Count -ge 2) "CMake validation smoke did not persist chained command steps."
    $cmakeBuildLogPath = Join-Path $cmakeSmokeRoot ([string]$latestCmakeValidation.build_log_path)
    Assert-Aegis (Test-Path -LiteralPath $cmakeBuildLogPath) "CMake validation smoke build log was not written at $cmakeBuildLogPath."
    $cmakeBuildLogText = Get-Content -LiteralPath $cmakeBuildLogPath -Raw
    Assert-Aegis ($cmakeBuildLogText -match "## Command Steps") "CMake validation smoke build log did not include command steps."

    $cmakeValidationProfilePath = Join-Path $cmakeSmokeRoot ".aegis\validation_profile.json"
    if (Test-Path -LiteralPath $cmakeValidationProfilePath) {
        Remove-Item -LiteralPath $cmakeValidationProfilePath -Force
    }
    $cmakeRecoveredProfile = Invoke-AegisJsonGet "$BackendUrl/api/validation/profile?workspace_root=$encodedCmakeSmokeRoot"
    Assert-Aegis ($null -ne $cmakeRecoveredProfile.profile) "CMake validation smoke did not recover a validation profile from command history."
    Assert-Aegis ([string]$cmakeRecoveredProfile.profile.command -eq "cmake -S . -B build && cmake --build build") "CMake validation smoke recovered '$($cmakeRecoveredProfile.profile.command)' instead of the command-history validation command."
    Assert-Aegis ([string]$cmakeRecoveredProfile.suggestions[0].command -eq "cmake -S . -B build && cmake --build build") "CMake validation smoke command-history recovery was not the top validation suggestion."

    $cmakeVerify = Invoke-AegisJsonPost "$BackendUrl/api/verify" @{
        workspace_root = $cmakeSmokeRoot
        max_steps = 1
        continue_on_failure = $false
    } -TimeoutSec 180
    Assert-Aegis ([string]$cmakeVerify.status -eq "passed") "CMake verification smoke returned status '$($cmakeVerify.status)'."
    Assert-Aegis (@($cmakeVerify.steps).Count -ge 2) "CMake verification smoke did not keep the configure/build chain together."
    Assert-Aegis ([string]$cmakeVerify.steps[0].phase -eq "configure") "CMake verification smoke first step should be configure, got '$($cmakeVerify.steps[0].phase)'."
    Assert-Aegis ([string]$cmakeVerify.steps[0].status -eq "succeeded") "CMake verification smoke first step did not succeed."
    Assert-Aegis ([string]$cmakeVerify.steps[1].phase -eq "build") "CMake verification smoke second step should be build, got '$($cmakeVerify.steps[1].phase)'."
    Assert-Aegis ([string]$cmakeVerify.steps[1].status -eq "succeeded") "CMake verification smoke build step did not succeed."

    $cmakeHistory = Get-Content -LiteralPath $cmakeHistoryPath -Raw | ConvertFrom-Json
    $cmakeConfigureHistory = @($cmakeHistory.commands | Where-Object { [string]$_.kind -eq "verification:configure" })
    Assert-Aegis ($cmakeConfigureHistory.Count -gt 0) "CMake verification smoke history did not include a verification:configure command."
    $cmakeVerifyHistory = @($cmakeHistory.commands | Where-Object { [string]$_.kind -eq "verification:build" })
    Assert-Aegis ($cmakeVerifyHistory.Count -gt 0) "CMake verification smoke history did not include a verification:build command."
    $latestCmakeVerify = $cmakeVerifyHistory[$cmakeVerifyHistory.Count - 1]
    Assert-Aegis ([string]$latestCmakeVerify.status -eq "passed") "CMake verification smoke history was not marked passed."
    Assert-Aegis (-not [string]::IsNullOrWhiteSpace([string]$latestCmakeVerify.build_log_path)) "CMake verification smoke history did not link a build log."
    $cmakeVerifyLogPath = Join-Path $cmakeSmokeRoot ([string]$latestCmakeVerify.build_log_path)
    Assert-Aegis (Test-Path -LiteralPath $cmakeVerifyLogPath) "CMake verification smoke build log was not written at $cmakeVerifyLogPath."

    $cmakeWorkspaceProfile = Invoke-AegisJsonGet "$BackendUrl/api/workspace/profile?workspace_root=$encodedCmakeSmokeRoot"
    $cmakeReadiness = Assert-AegisReadiness -Profile $cmakeWorkspaceProfile -Label "CMake validation smoke"
    Assert-Aegis ([string]$cmakeReadiness.status -eq "ready") "CMake validation smoke readiness should be ready after validation and verification passed, got '$($cmakeReadiness.status)'."
    Assert-AegisInstructionStatusHasNoMetadataNoise -Profile $cmakeWorkspaceProfile -Label "CMake validation smoke"

    $cmakeAutopilotStatus = Invoke-AegisJsonGet "$BackendUrl/api/workspace/autopilot-status?workspace_root=$encodedCmakeSmokeRoot"
    Assert-Aegis ([string]$cmakeAutopilotStatus.phase -eq "ready") "CMake validation smoke autopilot phase should be ready, got '$($cmakeAutopilotStatus.phase)'."
    Assert-Aegis (-not [bool]$cmakeAutopilotStatus.should_continue) "CMake validation smoke autopilot should not continue after ready readiness."
    Assert-Aegis ([int]$cmakeAutopilotStatus.pass_budget -eq 0) "CMake validation smoke autopilot ready phase should have zero pass budget."

    $cmakeValidationSmoke = @{
        target_path = $cmakeSmokeRoot
        validation_command = [string]$cmakeValidation.validation.command
        validation_exit_code = [int]$cmakeValidation.validation.exit_code
        validation_step_count = @($latestCmakeValidation.steps).Count
        build_log_path = [string]$latestCmakeValidation.build_log_path
        command_history_recovery = $true
        verification_status = [string]$cmakeVerify.status
        verification_build_log_path = [string]$latestCmakeVerify.build_log_path
        readiness_status = [string]$cmakeReadiness.status
        readiness_score = [int]$cmakeReadiness.score
        autopilot_phase = [string]$cmakeAutopilotStatus.phase
    }

    Write-Host "CMake validation smoke test passed at $cmakeSmokeRoot"

    $diagnosticSmokeRoot = Join-Path $workspaceRoot ("diagnostic-smoke-" + (New-Guid).ToString("N"))
    $diagnosticAegisDir = Join-Path $diagnosticSmokeRoot ".aegis"
    New-Item -ItemType Directory -Force -Path $diagnosticAegisDir | Out-Null
    $diagnosticCommand = "python -c ""import sys; print('src/main.cpp(12,34): error C2143: syntax error: missing semicolon'); sys.exit(9)"""
    $diagnosticProfilePayload = @{
        command = $diagnosticCommand
        label = "Diagnostic extraction smoke"
        source = "manual"
        updated_at = (Get-Date).ToUniversalTime().ToString("o")
        notes = "Stress smoke for compiler diagnostic extraction."
    }
    Write-AegisJsonFile -Path (Join-Path $diagnosticAegisDir "validation_profile.json") -Value $diagnosticProfilePayload -Depth 8

    $diagnosticValidation = Invoke-AegisJsonPost "$BackendUrl/api/validate" @{
        workspace_root = $diagnosticSmokeRoot
    } -TimeoutSec 90
    Assert-Aegis ($null -ne $diagnosticValidation.validation) "Diagnostic extraction smoke did not return validation output."
    Assert-Aegis ([int]$diagnosticValidation.validation.exit_code -eq 9) "Diagnostic extraction smoke returned unexpected exit code $($diagnosticValidation.validation.exit_code)."
    $diagnostics = @($diagnosticValidation.validation.diagnostics)
    Assert-Aegis ($diagnostics.Count -ge 1) "Diagnostic extraction smoke did not return diagnostics."
    Assert-Aegis ([string]$diagnostics[0].file -eq "src/main.cpp") "Diagnostic extraction smoke captured unexpected file '$($diagnostics[0].file)'."
    Assert-Aegis ([int]$diagnostics[0].line -eq 12) "Diagnostic extraction smoke captured unexpected line '$($diagnostics[0].line)'."
    Assert-Aegis ([int]$diagnostics[0].column -eq 34) "Diagnostic extraction smoke captured unexpected column '$($diagnostics[0].column)'."
    Assert-Aegis ([string]$diagnostics[0].code -eq "C2143") "Diagnostic extraction smoke captured unexpected code '$($diagnostics[0].code)'."

    $diagnosticHistoryPath = Join-Path $diagnosticSmokeRoot ".aegis\command_history.json"
    Assert-Aegis (Test-Path -LiteralPath $diagnosticHistoryPath) "Diagnostic extraction smoke did not persist command history."
    $diagnosticHistory = Get-Content -LiteralPath $diagnosticHistoryPath -Raw | ConvertFrom-Json
    $latestDiagnosticHistory = @($diagnosticHistory.commands)[@($diagnosticHistory.commands).Count - 1]
    Assert-Aegis (@($latestDiagnosticHistory.diagnostics).Count -ge 1) "Diagnostic extraction smoke did not persist diagnostics in command history."
    $diagnosticKnownPath = Join-Path $diagnosticSmokeRoot ".aegis\known_errors.json"
    Assert-Aegis (Test-Path -LiteralPath $diagnosticKnownPath) "Diagnostic extraction smoke did not persist known errors."
    $diagnosticKnown = Get-Content -LiteralPath $diagnosticKnownPath -Raw | ConvertFrom-Json
    $latestDiagnosticError = @($diagnosticKnown.errors)[@($diagnosticKnown.errors).Count - 1]
    Assert-Aegis (@($latestDiagnosticError.diagnostics).Count -ge 1) "Diagnostic extraction smoke did not persist diagnostics in known errors."
    $diagnosticBuildLogPath = Join-Path $diagnosticSmokeRoot ([string]$latestDiagnosticHistory.build_log_path)
    Assert-Aegis (Test-Path -LiteralPath $diagnosticBuildLogPath) "Diagnostic extraction smoke build log was not written."
    $diagnosticBuildLogText = Get-Content -LiteralPath $diagnosticBuildLogPath -Raw
    Assert-Aegis ($diagnosticBuildLogText -match "## Diagnostics") "Diagnostic extraction smoke build log did not include diagnostics."
    Assert-Aegis ($diagnosticBuildLogText -match "src/main.cpp:12:34 error C2143") "Diagnostic extraction smoke build log did not include the captured compiler diagnostic."

    $encodedDiagnosticSmokeRoot = [Uri]::EscapeDataString($diagnosticSmokeRoot)
    $diagnosticWorkspaceProfile = Invoke-AegisJsonGet "$BackendUrl/api/workspace/profile?workspace_root=$encodedDiagnosticSmokeRoot"
    $diagnosticReadiness = Assert-AegisReadiness -Profile $diagnosticWorkspaceProfile -Label "Diagnostic extraction smoke"
    Assert-Aegis ([string]$diagnosticReadiness.status -eq "needs_repair") "Diagnostic extraction smoke readiness should be needs_repair after failing validation, got '$($diagnosticReadiness.status)'."
    Assert-Aegis ([string]$diagnosticReadiness.next_action -match "src/main.cpp:12:34 error C2143") "Diagnostic extraction smoke readiness did not target the captured diagnostic."

    $diagnosticExtractionSmoke = @{
        target_path = $diagnosticSmokeRoot
        validation_command = [string]$diagnosticValidation.validation.command
        validation_exit_code = [int]$diagnosticValidation.validation.exit_code
        diagnostic = [string]"$($diagnostics[0].file):$($diagnostics[0].line):$($diagnostics[0].column) $($diagnostics[0].severity) $($diagnostics[0].code)"
        build_log_path = [string]$latestDiagnosticHistory.build_log_path
        readiness_status = [string]$diagnosticReadiness.status
        readiness_next_action = [string]$diagnosticReadiness.next_action
    }

    Write-Host "Diagnostic extraction smoke test passed at $diagnosticSmokeRoot"

    $readinessContinueRoot = Join-Path $workspaceRoot ("readiness-continue-smoke-" + (New-Guid).ToString("N"))
    $readinessAegisDir = Join-Path $readinessContinueRoot ".aegis"
    New-Item -ItemType Directory -Force -Path $readinessAegisDir | Out-Null
    Set-Content -LiteralPath (Join-Path $readinessContinueRoot "CMakeLists.txt") -Encoding UTF8 -Value @"
cmake_minimum_required(VERSION 3.20)
project(AegisReadinessContinue LANGUAGES CXX)
add_executable(AegisReadinessContinue src/main.cpp)
"@
    $readinessHistoryPayload = @{
        schema = "aegis.command_history.v1"
        validation_command = "cmake -S . -B build && cmake --build build"
        commands = @(
            @{
                kind = "validation"
                command = "cmake -S . -B build && cmake --build build"
                status = "failed"
                summary = "Compile failed."
                exit_code = 1
                failed_step = "2"
                failed_step_command = "cmake --build build"
                diagnostics = @(
                    @{
                        file = "src/main.cpp"
                        line = 17
                        column = 5
                        severity = "error"
                        code = "C2143"
                        message = "syntax error: missing semicolon"
                        raw = "src/main.cpp(17,5): error C2143: syntax error: missing semicolon"
                    }
                )
                steps = @(
                    @{
                        index = 1
                        command = "cmake -S . -B build"
                        allowed = $true
                        exit_code = 0
                        timed_out = $false
                        reason = "Command finished."
                        ok = $true
                    },
                    @{
                        index = 2
                        command = "cmake --build build"
                        allowed = $true
                        exit_code = 1
                        timed_out = $false
                        reason = "Command finished."
                        ok = $false
                    }
                )
            }
        )
    }
    Write-AegisJsonFile -Path (Join-Path $readinessAegisDir "command_history.json") -Value $readinessHistoryPayload -Depth 8

    $readinessContinuePreview = Invoke-AegisJsonPost "$BackendUrl/api/routing/preview" @{
        message = "continue"
        workspace_root = $readinessContinueRoot
        mode = "build"
    } -TimeoutSec 60
    Assert-Aegis ([string]$readinessContinuePreview.task_plan.intent -eq "debug_and_repair") "Readiness continuation smoke did not route to debug_and_repair."
    Assert-Aegis ([string]$readinessContinuePreview.task_plan.objective -match "Continue workspace readiness") "Readiness continuation smoke did not expose a readiness objective."
    Assert-Aegis ([string]$readinessContinuePreview.task_plan.objective -match "Repair step 2: cmake --build build") "Readiness continuation smoke did not preserve the saved failed-step repair action."
    Assert-Aegis ([string]$readinessContinuePreview.task_plan.objective -match "src/main.cpp:17:5 error C2143") "Readiness continuation smoke did not preserve the saved diagnostic repair target."
    Assert-Aegis ([string]$readinessContinuePreview.task_plan.objective -match "rerun validation") "Readiness continuation smoke did not preserve the compact rerun-validation action."
    Assert-Aegis ([string]$readinessContinuePreview.task_plan.routing.task_role -eq "debug") "Readiness continuation smoke did not select the debug route."

    $readinessBuildFollowupPreview = Invoke-AegisJsonPost "$BackendUrl/api/routing/preview" @{
        message = "you didn't build it"
        workspace_root = $readinessContinueRoot
        mode = "build"
    } -TimeoutSec 60
    Assert-Aegis ([string]$readinessBuildFollowupPreview.task_plan.intent -eq "debug_and_repair") "Build follow-up readiness smoke did not route to debug_and_repair."
    Assert-Aegis ([string]$readinessBuildFollowupPreview.task_plan.objective -match "Continue workspace readiness") "Build follow-up readiness smoke did not expose a readiness objective."
    Assert-Aegis ([string]$readinessBuildFollowupPreview.task_plan.objective -match "Repair step 2: cmake --build build") "Build follow-up readiness smoke did not preserve the saved failed-step repair action."
    Assert-Aegis ([string]$readinessBuildFollowupPreview.task_plan.objective -match "src/main.cpp:17:5 error C2143") "Build follow-up readiness smoke did not preserve the saved diagnostic repair target."

    $encodedReadinessContinueRoot = [Uri]::EscapeDataString($readinessContinueRoot)
    $readinessAutopilotStatus = Invoke-AegisJsonGet "$BackendUrl/api/workspace/autopilot-status?workspace_root=$encodedReadinessContinueRoot"
    Assert-Aegis (@("ready", "repair", "validate", "work", "unconfigured") -contains [string]$readinessAutopilotStatus.phase) "Readiness continuation smoke autopilot status returned an unknown phase."
    Assert-Aegis ([string]$readinessAutopilotStatus.phase -eq "repair") "Readiness continuation smoke autopilot status should stay in repair phase."
    Assert-Aegis ([string]$readinessAutopilotStatus.failed_step -eq "2") "Readiness continuation smoke autopilot status did not preserve the failed step."
    Assert-Aegis ([string]$readinessAutopilotStatus.failed_step_command -eq "cmake --build build") "Readiness continuation smoke autopilot status did not preserve the failed command."
    Assert-Aegis ([string]$readinessAutopilotStatus.first_diagnostic -match "src/main.cpp:17:5 error C2143") "Readiness continuation smoke autopilot status did not expose the first diagnostic."
    Assert-Aegis ([string]$readinessAutopilotStatus.repair_brief -match "Repair step 2: cmake --build build") "Readiness continuation smoke autopilot status did not expose the compact repair brief."
    Assert-Aegis ([string]$readinessAutopilotStatus.suggested_prompt -match "Repair brief:") "Readiness continuation smoke autopilot prompt did not include the repair brief."

    $readinessContinuationSmoke = @{
        target_path = $readinessContinueRoot
        intent = [string]$readinessContinuePreview.task_plan.intent
        route = [string]$readinessContinuePreview.task_plan.routing.task_role
        objective = [string]$readinessContinuePreview.task_plan.objective
        build_followup_objective = [string]$readinessBuildFollowupPreview.task_plan.objective
        failed_step = "2"
        failed_step_command = "cmake --build build"
        diagnostic = "src/main.cpp:17:5 error C2143"
        autopilot_phase = [string]$readinessAutopilotStatus.phase
        autopilot_repair_brief = [string]$readinessAutopilotStatus.repair_brief
    }
    Write-Host "Readiness continuation smoke test passed at $readinessContinueRoot"
}

$desktopSmoke = $null
if ($RunDesktopSmoke) {
    $smokeScript = Join-Path $scriptRoot "smoke-desktop.ps1"
    if (-not (Test-Path -LiteralPath $smokeScript)) {
        throw "Could not find smoke-desktop.ps1 at $smokeScript"
    }

    $smokeOutput = Join-Path $OutputDir "desktop-smoke"
    $smokeArgs = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $smokeScript,
        "-OutputDir",
        $smokeOutput,
        "-SetupWaitSeconds",
        $DesktopSetupWaitSeconds,
        "-DashboardWaitSeconds",
        $DesktopDashboardWaitSeconds,
        "-RunConversationSmoke",
        "-UseIsolatedAppData"
    )

    if (-not [string]::IsNullOrWhiteSpace($ExePath)) {
        $smokeArgs += @("-ExePath", $ExePath)
    }

    Write-Host "Running desktop smoke test..."
    & powershell @smokeArgs
    $smokeExitCode = $LASTEXITCODE
    $desktopSmoke = @{
        exit_code = $smokeExitCode
        output_dir = $smokeOutput
    }

    if ($smokeExitCode -ne 0) {
        throw "Desktop smoke test failed with exit code $smokeExitCode."
    }
}

$summary = [ordered]@{
    ok = ($failures.Count -eq 0)
    backend_url = $BackendUrl
    api_iterations = $ApiIterations
    failures = @($failures)
    duration_ms = @{
        average = if ($durations.Count -gt 0) { [Math]::Round(($durations | Measure-Object -Average).Average, 2) } else { 0 }
        p95 = Get-Percentile -Values @($durations) -Percentile 95
        max = if ($durations.Count -gt 0) { [Math]::Round(($durations | Measure-Object -Maximum).Maximum, 2) } else { 0 }
    }
    preset_count = $lastPresetCount
    required_presets = $presetIdsToRequire
    last_cpp_plan = $lastCppPlan
    last_full_stack_plan = $lastFullStackPlan
    scaffold_smoke = $scaffoldSmoke
    msvc_console_smoke = $msvcConsoleSmoke
    cpp_dll_host_smoke = $cppDllHostSmoke
    windows_internals_minhook_smoke = $windowsInternalsMinHookSmoke
    solution_refactor_materialize_smoke = $solutionRefactorMaterializeSmoke
    existing_project_continuity_smoke = $continuitySmoke
    cmake_validation_smoke = $cmakeValidationSmoke
    diagnostic_extraction_smoke = $diagnosticExtractionSmoke
    readiness_continuation_smoke = $readinessContinuationSmoke
    generic_instruction_smoke = $genericInstructionSmoke
    desktop_autopilot_prompt_contract_smoke = $desktopAutopilotPromptContractSmoke
    frontend_queue_contract_smoke = $frontendQueueContractSmoke
    desktop_build_followup_contract_smoke = $desktopBuildFollowupContractSmoke
    backend_validation_only_contract_smoke = $backendValidationOnlyContractSmoke
    backend_workspace_cache_contract_smoke = $backendWorkspaceCacheContractSmoke
    backend_natural_prompt_contract_smoke = $backendNaturalPromptContractSmoke
    native_continuity_command_smoke = $nativeContinuityCommandSmoke
    desktop_smoke = $desktopSmoke
    output_dir = $OutputDir
}

$summaryPath = Join-Path $OutputDir "summary.json"
Write-AegisJsonFile -Path $summaryPath -Value $summary -Depth 12
$summary | ConvertTo-Json -Depth 12

if (-not $summary.ok) {
    exit 1
}
