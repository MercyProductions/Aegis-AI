param(
    [string]$BackendUrl = "http://127.0.0.1:8787",
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
$workspaceRoot = Join-Path $env:TEMP "aegis-stress-workspace"
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

$presetIdsToRequire = @(
    "cpp-msvc-console-sln",
    "cpp-cmake-dll",
    "cpp-imgui-win32-dx11",
    "cpp-windows-internals-hooking",
    "windows-kernel-driver-controller",
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
$desktopAutopilotPromptContractSmoke = @{
    source_path = $chatAppSourcePath
    queue_contract = $true
    repair_brief_contract = $true
    client_parse_contract = $true
}
Assert-Aegis ($chatAppSource -match "Auto-selected from existing project files for a build/run follow-up") "Desktop build follow-up contract is still limited to native C++ projects."
Assert-Aegis ($chatAppSource -match "Preserve the detected stack, build system, and app type") "Desktop continuity directive does not preserve the detected project stack."
Assert-Aegis ($chatAppSource -match "run build") "Desktop build follow-up validation does not infer package build commands."
$desktopBuildFollowupContractSmoke = @{
    source_path = $chatAppSourcePath
    generic_build_followup = $true
}

$aegisRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $repoRoot))
$backendMainSourcePath = Join-Path $aegisRoot "Website\ChatBot\backend\aegis_ai\main.py"
Assert-Aegis (Test-Path -LiteralPath $backendMainSourcePath) "Backend workspace cache contract smoke could not find main.py."
$backendMainSource = Get-Content -LiteralPath $backendMainSourcePath -Raw
Assert-Aegis ($backendMainSource -match "_workspace_status_snapshot") "Backend workspace profile/autopilot endpoints no longer share a cached workspace snapshot."
Assert-Aegis ($backendMainSource -match "_cached_project_plan") "Backend project-builder planning no longer uses the short-lived plan cache."
Assert-Aegis ($backendMainSource -match "_invalidate_workspace_caches") "Backend workspace cache invalidation contract is missing."
Assert-Aegis ($backendMainSource -match "_WORKSPACE_SNAPSHOT_TTL_SECONDS") "Backend workspace snapshot cache TTL is missing."
Assert-Aegis ($backendMainSource -match "_PROJECT_PLAN_CACHE_TTL_SECONDS") "Backend project plan cache TTL is missing."
$backendWorkspaceCacheContractSmoke = @{
    source_path = $backendMainSourcePath
    profile_autopilot_snapshot_cache = $true
    project_plan_cache = $true
    invalidation_contract = $true
}

$backendAgentSourcePath = Join-Path $aegisRoot "Website\ChatBot\backend\aegis_ai\agent.py"
Assert-Aegis (Test-Path -LiteralPath $backendAgentSourcePath) "Backend validation contract smoke could not find agent.py."
$backendAgentSource = Get-Content -LiteralPath $backendAgentSourcePath -Raw
Assert-Aegis ($backendAgentSource -match "Validation requested for current workspace") "Backend no-change validation path does not announce current-workspace validation."
Assert-Aegis ($backendAgentSource -match "Validation deferred until changes are applied") "Backend no-change validation path does not defer preview-only validation safely."
Assert-Aegis ($backendAgentSource -match "Aegis ran validation and") "Backend no-change validation replies do not summarize validation results."
Assert-Aegis ($backendAgentSource -match "_draft_stack_mismatch_reasons") "Backend agent no longer rejects stack-drifted model drafts."
Assert-Aegis ($backendAgentSource -match "The C\+\+ entry point does not wait for user input") "Backend agent no longer checks native console prompts for requested input pause behavior."
$backendValidationOnlyContractSmoke = @{
    source_path = $backendAgentSourcePath
    validates_current_workspace_without_file_changes = $true
    stack_drift_guard = $true
}

$backendScaffolderSourcePath = Join-Path $aegisRoot "Website\ChatBot\backend\aegis_ai\project_scaffolder.py"
Assert-Aegis (Test-Path -LiteralPath $backendScaffolderSourcePath) "Backend native continuity contract smoke could not find project_scaffolder.py."
$backendScaffolderSource = Get-Content -LiteralPath $backendScaffolderSourcePath -Raw
Assert-Aegis ($backendScaffolderSource -match "cmake -S \. -B build && cmake --build build --config Release") "Backend existing CMake validation no longer configures before the first build."
Assert-Aegis ($backendScaffolderSource -match '" write me "') "Backend existing-project validation still treats implementation prompts as pure validation."
Assert-Aegis ($backendScaffolderSource -match "_existing_project_validation_command") "Backend native continuity validation command helper is missing."
Assert-Aegis ($backendScaffolderSource -match "_stack_lock_keywords_for_prompt") "Backend project planner no longer exposes explicit stack-lock routing signals."
Assert-Aegis ($backendScaffolderSource -match "stack-lock:native-cpp") "Backend project planner no longer marks native C++ stack-lock prompts."
Assert-Aegis ($backendScaffolderSource -match "my dll") "Backend continuity routing no longer treats existing DLL refinement as existing project work."
Assert-Aegis ($backendScaffolderSource -match "_prompt_negates_web_stack") "Backend planner no longer ignores negated web phrases like 'without turning it into a website'."
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

for ($i = 1; $i -le $ApiIterations; $i++) {
    try {
        $call = Measure-AegisCall {
            $health = Invoke-AegisJsonGet "$BackendUrl/api/health"
            Assert-Aegis ([bool]$health.ready) "Iteration $i health check was not ready."

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
                prompt = "at this path $existingDllTarget work on my existing DLL that I already made and refine the native project without turning it into a website"
                workspace_root = $workspaceRoot
                preferred_target_path = $existingDllTarget
            } -TimeoutSec 90
            $dllDetectedKeywords = @($dllPlan.detected_keywords)
            Assert-Aegis ([bool]$dllPlan.ok) "Iteration $i existing DLL plan did not complete successfully."
            Assert-Aegis ([string]$dllPlan.preset.id -eq "cpp-cmake-dll") "Iteration $i existing DLL plan selected '$($dllPlan.preset.id)' instead of cpp-cmake-dll."
            Assert-Aegis ([string]$dllPlan.target_path -eq [string](Resolve-Path -LiteralPath $existingDllTarget)) "Iteration $i existing DLL plan did not preserve the requested target path."
            Assert-Aegis ($dllDetectedKeywords -contains "stack-lock:native-library") "Iteration $i existing DLL plan did not preserve the native-library stack lock."
            Assert-Aegis (-not ($dllDetectedKeywords -contains "stack-lock:web")) "Iteration $i existing DLL plan incorrectly added a web stack lock from negated website wording."

            return @{
                preset_count = $presetCount
                cpp_plan = $cppProjectName
                full_stack_plan = $fullStackProjectName
                dll_plan = [string]$dllPlan.preset.id
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

    $cmakeVerify = Invoke-AegisJsonPost "$BackendUrl/api/verify" @{
        workspace_root = $cmakeSmokeRoot
        max_steps = 1
        continue_on_failure = $false
    } -TimeoutSec 180
    Assert-Aegis ([string]$cmakeVerify.status -eq "passed") "CMake verification smoke returned status '$($cmakeVerify.status)'."
    Assert-Aegis (@($cmakeVerify.steps).Count -ge 1) "CMake verification smoke did not return any verification steps."
    Assert-Aegis ([string]$cmakeVerify.steps[0].status -eq "succeeded") "CMake verification smoke first step did not succeed."

    $cmakeHistory = Get-Content -LiteralPath $cmakeHistoryPath -Raw | ConvertFrom-Json
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
    desktop_build_followup_contract_smoke = $desktopBuildFollowupContractSmoke
    backend_validation_only_contract_smoke = $backendValidationOnlyContractSmoke
    backend_workspace_cache_contract_smoke = $backendWorkspaceCacheContractSmoke
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
