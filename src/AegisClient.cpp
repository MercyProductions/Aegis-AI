#include "AegisClient.h"

#include "Json.h"
#include "core/CoreApiClient.h"

#include <algorithm>
#include <chrono>
#include <functional>
#include <sstream>
#include <stdexcept>
#include <thread>
#include <utility>

namespace aegis {
namespace {

std::string JsonString(const std::string& value)
{
    return "\"" + EscapeJson(value) + "\"";
}

std::string JsonBool(bool value)
{
    return value ? "true" : "false";
}

std::string JsonStringArray(const std::vector<std::string>& values)
{
    std::ostringstream body;
    body << "[";
    for (size_t i = 0; i < values.size(); ++i) {
        if (i > 0) {
            body << ",";
        }
        body << JsonString(values[i]);
    }
    body << "]";
    return body.str();
}

std::vector<std::string> ParseStringArray(const JsonValue& value)
{
    std::vector<std::string> out;
    if (!value.IsArray()) {
        return out;
    }
    out.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        out.push_back(item.AsString());
    }
    return out;
}

bool ShouldFallbackFromCoreError(const std::exception& error)
{
    const std::string message = Lower(error.what());
    if (message.find("http 400") != std::string::npos ||
        message.find("http 403") != std::string::npos ||
        message.find("unsafe") != std::string::npos ||
        message.find("outside the workspace") != std::string::npos ||
        message.find("secret") != std::string::npos ||
        message.find("refusing") != std::string::npos) {
        return false;
    }
    return true;
}

std::string CoreEnvelopeError(const JsonValue& envelope)
{
    const JsonValue& data = envelope["data"];
    const std::string error = data["error"].AsString();
    if (!error.empty()) {
        return RedactDiagnosticText(error);
    }
    const std::string message = data["message"].AsString();
    if (!message.empty()) {
        return RedactDiagnosticText(message);
    }
    const std::string detail = envelope["detail"].AsString();
    if (!detail.empty()) {
        return RedactDiagnosticText(detail);
    }

    const JsonValue& deprecations = envelope["deprecations"];
    if (deprecations.IsArray() && !deprecations.array_value.empty()) {
        std::ostringstream joined;
        for (size_t i = 0; i < deprecations.array_value.size(); ++i) {
            if (i > 0) {
                joined << "; ";
            }
            joined << deprecations.array_value[i].AsString();
        }
        const std::string text = joined.str();
        if (!text.empty()) {
            return RedactDiagnosticText(text);
        }
    }

    return "Core returned ok=false.";
}

void ValidateCoreEnvelope(const JsonValue& envelope, const std::string& expected_kind, bool require_ok = false)
{
    if (!envelope.IsObject()) {
        throw std::runtime_error("Aegis Core returned a non-object response.");
    }

    const std::string api_version = envelope["api_version"].AsString();
    if (api_version != "v1") {
        const std::string safe_api_version = api_version.empty() ? std::string("missing") : RedactDiagnosticText(api_version);
        throw std::runtime_error("Aegis Core response used unexpected api_version: " + safe_api_version + ".");
    }

    const std::string kind = envelope["kind"].AsString();
    if (kind != expected_kind) {
        const std::string safe_kind = kind.empty() ? std::string("missing") : RedactDiagnosticText(kind);
        throw std::runtime_error("Aegis Core response kind mismatch: expected " + expected_kind + ", got " + safe_kind + ".");
    }

    if (require_ok && envelope.Has("ok") && !envelope["ok"].AsBool(true)) {
        throw std::runtime_error("Aegis Core " + expected_kind + " failed: " + CoreEnvelopeError(envelope));
    }
}

std::vector<WorkspaceFile> ParseWorkspaceFiles(const JsonValue& value)
{
    std::vector<WorkspaceFile> files;
    if (!value.IsArray()) {
        return files;
    }
    files.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        WorkspaceFile file;
        file.path = item["path"].AsString();
        file.size = item["size"].AsInt(0);
        file.kind = item["kind"].AsString();
        files.push_back(std::move(file));
    }
    return files;
}

AegisCoreDashboardInfo ParseCoreDashboard(const JsonValue& value)
{
    AegisCoreDashboardInfo dashboard;
    const JsonValue& data = value["data"].IsObject() ? value["data"] : value;
    dashboard.reachable = value["ok"].AsBool(true);
    dashboard.workspace_root = data["workspace"].AsString();

    const JsonValue& clients = data["clients"];
    if (clients.IsArray()) {
        dashboard.connected_client_count = static_cast<int>(clients.array_value.size());
    }
    const JsonValue& active_tasks = data["active_tasks"];
    if (active_tasks.IsArray()) {
        dashboard.active_task_count = static_cast<int>(active_tasks.array_value.size());
    }
    const JsonValue& recent_tasks = data["recent_tasks"];
    if (recent_tasks.IsArray()) {
        dashboard.recent_task_count = static_cast<int>(recent_tasks.array_value.size());
    }

    const JsonValue& model_status = data["model_status"];
    dashboard.ollama_reachable = model_status["reachable"].AsBool(false);
    dashboard.selected_model = model_status["selected_model"].AsString();
    if (model_status["installed_models"].IsArray()) {
        dashboard.installed_model_count = static_cast<int>(model_status["installed_models"].array_value.size());
    }

    const JsonValue& commands = data["validation"]["commands"];
    if (commands.IsArray()) {
        dashboard.validation_command_count = static_cast<int>(commands.array_value.size());
    }
    dashboard.roadmap_excerpt = data["roadmap"]["excerpt"].AsString();
    dashboard.diagnostic_excerpt = data["diagnostics"]["logs"]["core_log"]["tail"].AsString();
    return dashboard;
}

CommandRun ParseCommandRun(const JsonValue& value, bool* present);

ProjectScaffoldPresetInfo ParseProjectScaffoldPreset(const JsonValue& value)
{
    ProjectScaffoldPresetInfo preset;
    if (!value.IsObject()) {
        return preset;
    }
    preset.id = value["id"].AsString();
    preset.label = value["label"].AsString();
    preset.framework = value["framework"].AsString();
    preset.language = value["language"].AsString();
    preset.package_manager = value["package_manager"].AsString();
    preset.install_command = value["install_command"].AsString();
    preset.validation_command = value["validation_command"].AsString();
    preset.description = value["description"].AsString();
    preset.tags = ParseStringArray(value["tags"]);
    return preset;
}

std::vector<ProjectScaffoldPresetInfo> ParseProjectScaffoldPresets(const JsonValue& value)
{
    std::vector<ProjectScaffoldPresetInfo> presets;
    if (!value.IsArray()) {
        return presets;
    }
    presets.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (item.IsObject()) {
            presets.push_back(ParseProjectScaffoldPreset(item));
        }
    }
    return presets;
}

std::vector<ProjectScaffoldFileInfo> ParseProjectScaffoldFiles(const JsonValue& value)
{
    std::vector<ProjectScaffoldFileInfo> files;
    if (!value.IsArray()) {
        return files;
    }
    files.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        ProjectScaffoldFileInfo file;
        file.path = item["path"].AsString();
        file.action = item["action"].AsString();
        file.summary = item["summary"].AsString();
        file.size = item["size"].AsInt(0);
        files.push_back(std::move(file));
    }
    return files;
}

std::vector<ProjectBuildStageInfo> ParseProjectBuildStages(const JsonValue& value)
{
    std::vector<ProjectBuildStageInfo> stages;
    if (!value.IsArray()) {
        return stages;
    }
    stages.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        ProjectBuildStageInfo stage;
        stage.id = item["id"].AsString();
        stage.label = item["label"].AsString();
        stage.status = item["status"].AsString();
        stage.detail = item["detail"].AsString();
        stage.command = item["command"].AsString();
        stage.output_excerpt = item["output_excerpt"].AsString();
        stage.error = item["error"].AsString();
        stages.push_back(std::move(stage));
    }
    return stages;
}

ProjectScaffoldResult ParseProjectScaffoldResult(const JsonValue& value)
{
    ProjectScaffoldResult result;
    if (!value.IsObject()) {
        return result;
    }
    result.ok = value["ok"].AsBool(false);
    result.message = value["message"].AsString();
    result.execution_mode = value["execution_mode"].AsString("scaffold");
    result.primary_action = value["primary_action"].AsString("create_or_update_files");
    result.target_path = value["target_path"].AsString();
    result.preset = ParseProjectScaffoldPreset(value["preset"]);
    result.plan_steps = ParseStringArray(value["plan_steps"]);
    result.risk_warnings = ParseStringArray(value["risk_warnings"]);
    result.diff_summary = ParseStringArray(value["diff_summary"]);
    result.memory_paths = ParseStringArray(value["memory_paths"]);
    result.files = ParseProjectScaffoldFiles(value["files"]);
    result.file_change_count = value["file_change_count"].AsInt(static_cast<int>(result.files.size()));
    result.applied = ParseStringArray(value["applied"]);
    result.warnings = ParseStringArray(value["warnings"]);
    result.checkpoint = value["checkpoint"].AsString();
    result.install_command = value["install_command"].AsString();
    result.validation_command = value["validation_command"].AsString();
    result.roadmap_path = value["roadmap_path"].AsString();
    result.build_log_path = value["build_log_path"].AsString();
    result.stages = ParseProjectBuildStages(value["stages"]);
    result.validation = ParseCommandRun(value["validation"], &result.has_validation);
    result.next_steps = ParseStringArray(value["next_steps"]);
    result.workspace_files = ParseWorkspaceFiles(value["workspace_files"]);
    return result;
}

ProjectScaffoldPlanResult ParseProjectScaffoldPlanResult(const JsonValue& value)
{
    ProjectScaffoldPlanResult result;
    if (!value.IsObject()) {
        return result;
    }
    result.ok = value["ok"].AsBool(false);
    result.message = value["message"].AsString();
    result.prompt = value["prompt"].AsString();
    result.execution_mode = value["execution_mode"].AsString("scaffold");
    result.primary_action = value["primary_action"].AsString("create_or_update_files");
    result.confidence = value["confidence"].AsDouble(0.0);
    result.preset = ParseProjectScaffoldPreset(value["preset"]);
    result.project_name = value["project_name"].AsString();
    result.target_path = value["target_path"].AsString();
    result.install_command = value["install_command"].AsString();
    result.validation_command = value["validation_command"].AsString();
    result.overwrite = value["overwrite"].AsBool(false);
    result.include_gitignore = value["include_gitignore"].AsBool(true);
    result.plan_steps = ParseStringArray(value["plan_steps"]);
    result.risk_warnings = ParseStringArray(value["risk_warnings"]);
    result.reasons = ParseStringArray(value["reasons"]);
    result.assumptions = ParseStringArray(value["assumptions"]);
    result.detected_keywords = ParseStringArray(value["detected_keywords"]);
    return result;
}

WorkspaceProjectManifestInfo ParseWorkspaceProjectManifest(const JsonValue& value)
{
    WorkspaceProjectManifestInfo manifest;
    if (!value.IsObject()) {
        return manifest;
    }
    manifest.schema = value["schema"].AsString();
    manifest.project_name = value["project_name"].AsString();
    manifest.title = value["title"].AsString();
    manifest.preset_id = value["preset_id"].AsString();
    manifest.preset_label = value["preset_label"].AsString();
    manifest.framework = value["framework"].AsString();
    manifest.language = value["language"].AsString();
    manifest.package_manager = value["package_manager"].AsString();
    manifest.install_command = value["install_command"].AsString();
    manifest.validation_command = value["validation_command"].AsString();
    manifest.tags = ParseStringArray(value["tags"]);
    manifest.generated_by = value["generated_by"].AsString();

    const JsonValue& handoff = value["agent_handoff"];
    if (handoff.IsObject()) {
        manifest.handoff_goal = handoff["primary_goal"].AsString();
        manifest.first_pass = ParseStringArray(handoff["first_pass"]);
        manifest.safety = ParseStringArray(handoff["safety"]);
    }
    return manifest;
}

WorkspaceDependencyInfo ParseWorkspaceDependency(const JsonValue& value)
{
    WorkspaceDependencyInfo dependency;
    if (!value.IsObject()) {
        return dependency;
    }
    dependency.name = value["name"].AsString();
    dependency.version = value["version"].AsString();
    dependency.source = value["source"].AsString();
    dependency.group = value["group"].AsString();
    return dependency;
}

WorkspaceScriptInfo ParseWorkspaceScript(const JsonValue& value)
{
    WorkspaceScriptInfo script;
    if (!value.IsObject()) {
        return script;
    }
    script.name = value["name"].AsString();
    script.command = value["command"].AsString();
    script.source = value["source"].AsString();
    return script;
}

std::vector<WorkspaceDependencyInfo> ParseWorkspaceDependencies(const JsonValue& value)
{
    std::vector<WorkspaceDependencyInfo> dependencies;
    if (!value.IsArray()) {
        return dependencies;
    }
    dependencies.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        dependencies.push_back(ParseWorkspaceDependency(item));
    }
    return dependencies;
}

std::vector<WorkspaceScriptInfo> ParseWorkspaceScripts(const JsonValue& value)
{
    std::vector<WorkspaceScriptInfo> scripts;
    if (!value.IsArray()) {
        return scripts;
    }
    scripts.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        scripts.push_back(ParseWorkspaceScript(item));
    }
    return scripts;
}

WorkspaceDependencyProfileInfo ParseWorkspaceDependencyProfile(const JsonValue& value)
{
    WorkspaceDependencyProfileInfo profile;
    if (!value.IsObject()) {
        return profile;
    }
    profile.project_type = value["project_type"].AsString();
    profile.languages = ParseStringArray(value["languages"]);
    profile.frameworks = ParseStringArray(value["frameworks"]);
    profile.package_managers = ParseStringArray(value["package_managers"]);
    profile.build_systems = ParseStringArray(value["build_systems"]);
    profile.config_files = ParseStringArray(value["config_files"]);
    profile.entry_points = ParseStringArray(value["entry_points"]);
    profile.test_files = ParseStringArray(value["test_files"]);
    profile.install_commands = ParseStringArray(value["install_commands"]);
    profile.validation_commands = ParseStringArray(value["validation_commands"]);
    profile.scripts = ParseWorkspaceScripts(value["scripts"]);
    profile.dependencies = ParseWorkspaceDependencies(value["dependencies"]);
    profile.dev_dependencies = ParseWorkspaceDependencies(value["dev_dependencies"]);
    profile.database_tools = ParseStringArray(value["database_tools"]);
    profile.warnings = ParseStringArray(value["warnings"]);
    return profile;
}

WorkspaceInstructionStatusFileInfo ParseWorkspaceInstructionStatusFile(const JsonValue& value)
{
    WorkspaceInstructionStatusFileInfo file;
    if (!value.IsObject()) {
        return file;
    }
    file.path = value["path"].AsString();
    file.title = value["title"].AsString();
    file.kind = value["kind"].AsString();
    file.score = value["score"].AsDouble(0.0);
    file.open_items = value["open_items"].AsInt(0);
    file.completed_items = value["completed_items"].AsInt(0);
    file.total_items = value["total_items"].AsInt(0);
    file.pending_items = ParseStringArray(value["pending_items"]);
    file.summary = value["summary"].AsString();
    return file;
}

std::vector<WorkspaceInstructionStatusFileInfo> ParseWorkspaceInstructionStatusFiles(const JsonValue& value)
{
    std::vector<WorkspaceInstructionStatusFileInfo> files;
    if (!value.IsArray()) {
        return files;
    }
    files.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (item.IsObject()) {
            files.push_back(ParseWorkspaceInstructionStatusFile(item));
        }
    }
    return files;
}

WorkspaceInstructionStatusInfo ParseWorkspaceInstructionStatus(const JsonValue& value)
{
    WorkspaceInstructionStatusInfo status;
    if (!value.IsObject()) {
        return status;
    }
    status.schema = value["schema"].AsString();
    status.updated_at = value["updated_at"].AsString();
    status.source_message = value["source_message"].AsString();
    status.instruction_file_count = value["instruction_file_count"].AsInt(0);
    status.open_items = value["open_items"].AsInt(0);
    status.completed_items = value["completed_items"].AsInt(0);
    status.total_items = value["total_items"].AsInt(0);
    status.files = ParseWorkspaceInstructionStatusFiles(value["files"]);
    status.applied = ParseStringArray(value["applied"]);
    status.recommendation = value["recommendation"].AsString();

    const JsonValue& validation = value["last_validation"];
    if (validation.IsObject()) {
        status.validation_status = validation["status"].AsString();
        status.validation_command = validation["command"].AsString();
        status.validation_summary = validation["summary"].AsString();
    }

    const JsonValue& completion = value["completion"];
    if (completion.IsObject()) {
        status.completion_status = completion["status"].AsString();
        status.completion_score = completion["score"].AsDouble(0.0);
        status.has_completion_score = true;
        status.should_continue = completion["should_continue"].AsBool(false);
        status.completion_reasons = ParseStringArray(completion["reasons"]);
        status.completion_next_actions = ParseStringArray(completion["next_actions"]);
    }
    return status;
}

WorkspaceValidationPlanStepInfo ParseWorkspaceValidationPlanStep(const JsonValue& value)
{
    WorkspaceValidationPlanStepInfo step;
    if (!value.IsObject()) {
        return step;
    }
    step.id = value["id"].AsString();
    step.phase = value["phase"].AsString();
    step.command = value["command"].AsString();
    step.label = value["label"].AsString();
    step.required = value["required"].AsBool(true);
    step.source_command = value["source_command"].AsString();
    step.chain_index = value["chain_index"].AsInt(0);
    step.chain_total = value["chain_total"].AsInt(0);
    return step;
}

std::vector<WorkspaceValidationPlanStepInfo> ParseWorkspaceValidationPlanSteps(const JsonValue& value)
{
    std::vector<WorkspaceValidationPlanStepInfo> steps;
    if (!value.IsArray()) {
        return steps;
    }
    steps.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (item.IsObject()) {
            steps.push_back(ParseWorkspaceValidationPlanStep(item));
        }
    }
    return steps;
}

WorkspaceValidationPlanInfo ParseWorkspaceValidationPlan(const JsonValue& value)
{
    WorkspaceValidationPlanInfo plan;
    if (!value.IsObject()) {
        return plan;
    }
    plan.schema = value["schema"].AsString();
    plan.updated_at = value["updated_at"].AsString();
    plan.project_name = value["project_name"].AsString();
    plan.preset_id = value["preset_id"].AsString();
    plan.preset_label = value["preset_label"].AsString();
    plan.install_command = value["install_command"].AsString();
    plan.validation_command = value["validation_command"].AsString();
    plan.steps = ParseWorkspaceValidationPlanSteps(value["steps"]);
    plan.notes = ParseStringArray(value["notes"]);

    const JsonValue& last_run = value["last_run"];
    if (last_run.IsObject()) {
        plan.last_run_status = last_run["status"].AsString();
        plan.last_run_command = last_run["command"].AsString();
        plan.last_run_summary = last_run["summary"].AsString();
        plan.last_run_failed_step = last_run["failed_step"].AsString();
        plan.last_run_build_log_path = last_run["build_log_path"].AsString();
    }
    return plan;
}

WorkspaceReadinessInfo ParseWorkspaceReadiness(const JsonValue& value)
{
    WorkspaceReadinessInfo readiness;
    if (!value.IsObject()) {
        return readiness;
    }
    readiness.status = value["status"].AsString();
    readiness.score = value["score"].AsInt(0);
    readiness.summary = value["summary"].AsString();
    readiness.next_action = value["next_action"].AsString();
    readiness.blockers = ParseStringArray(value["blockers"]);
    readiness.signals = ParseStringArray(value["signals"]);
    return readiness;
}

WorkspaceProfileInfo ParseWorkspaceProfile(const JsonValue& value)
{
    WorkspaceProfileInfo profile;
    if (!value.IsObject()) {
        return profile;
    }
    profile.workspace_root = value["workspace_root"].AsString();
    profile.has_manifest = value["has_manifest"].AsBool(false);
    profile.manifest = ParseWorkspaceProjectManifest(value["manifest"]);
    profile.dependency_profile = ParseWorkspaceDependencyProfile(value["dependency_profile"]);
    profile.has_instruction_status = value["has_instruction_status"].AsBool(false);
    profile.instruction_status = ParseWorkspaceInstructionStatus(value["instruction_status"]);
    profile.has_validation_plan = value["has_validation_plan"].AsBool(false);
    profile.validation_plan = ParseWorkspaceValidationPlan(value["validation_plan"]);
    profile.readiness = ParseWorkspaceReadiness(value["readiness"]);
    profile.recommendations = ParseStringArray(value["recommendations"]);
    return profile;
}

WorkspaceAutopilotStatusInfo ParseWorkspaceAutopilotStatus(const JsonValue& value)
{
    WorkspaceAutopilotStatusInfo status;
    if (!value.IsObject()) {
        return status;
    }
    status.workspace_root = value["workspace_root"].AsString();
    status.phase = value["phase"].AsString("unconfigured");
    status.should_continue = value["should_continue"].AsBool(false);
    status.recommended_mode = value["recommended_mode"].AsString("build");
    status.suggested_prompt = value["suggested_prompt"].AsString();
    status.next_action = value["next_action"].AsString();
    status.stop_reason = value["stop_reason"].AsString();
    status.pass_budget = value["pass_budget"].AsInt(0);
    status.run_validation = value["run_validation"].AsBool(false);
    status.max_repair_attempts = value["max_repair_attempts"].AsInt(0);
    status.readiness = ParseWorkspaceReadiness(value["readiness"]);
    status.open_items = value["open_items"].AsInt(0);
    status.completed_items = value["completed_items"].AsInt(0);
    status.total_items = value["total_items"].AsInt(0);
    status.validation_command = value["validation_command"].AsString();
    status.latest_validation_status = value["latest_validation_status"].AsString();
    status.failed_step = value["failed_step"].AsString();
    status.failed_step_command = value["failed_step_command"].AsString();
    status.first_diagnostic = value["first_diagnostic"].AsString();
    status.repair_brief = value["repair_brief"].AsString();
    status.blockers = ParseStringArray(value["blockers"]);
    status.signals = ParseStringArray(value["signals"]);
    status.recommendations = ParseStringArray(value["recommendations"]);
    status.instruction_files = ParseWorkspaceInstructionStatusFiles(value["instruction_files"]);
    status.next_open_items = ParseStringArray(value["next_open_items"]);
    status.instruction_source = value["instruction_source"].AsString();
    return status;
}

std::vector<CheckpointFileInfo> ParseCheckpointFiles(const JsonValue& value)
{
    std::vector<CheckpointFileInfo> files;
    if (!value.IsArray()) {
        return files;
    }
    files.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        CheckpointFileInfo file;
        file.path = item["path"].AsString();
        file.state = item["state"].AsString();
        files.push_back(std::move(file));
    }
    return files;
}

std::vector<CheckpointSummaryInfo> ParseCheckpoints(const JsonValue& value)
{
    std::vector<CheckpointSummaryInfo> checkpoints;
    if (!value.IsArray()) {
        return checkpoints;
    }
    checkpoints.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        CheckpointSummaryInfo checkpoint;
        checkpoint.id = item["id"].AsString();
        checkpoint.created_at = item["created_at"].AsString();
        checkpoint.file_count = item["file_count"].AsInt(0);
        checkpoint.present_count = item["present_count"].AsInt(0);
        checkpoint.missing_count = item["missing_count"].AsInt(0);
        checkpoint.files = ParseCheckpointFiles(item["files"]);
        checkpoints.push_back(std::move(checkpoint));
    }
    return checkpoints;
}

MemoryNoteInfo ParseMemoryNote(const JsonValue& value)
{
    MemoryNoteInfo note;
    if (!value.IsObject()) {
        return note;
    }
    note.id = value["id"].AsString();
    note.title = value["title"].AsString();
    note.content = value["content"].AsString();
    note.category = value["category"].AsString();
    note.created_at = value["created_at"].AsString();
    note.updated_at = value["updated_at"].AsString();
    note.pinned = value["pinned"].AsBool(false);
    note.tags = ParseStringArray(value["tags"]);
    note.related_files = ParseStringArray(value["related_files"]);
    note.confidence = value["confidence"].AsDouble(0.8);
    return note;
}

std::vector<MemoryNoteInfo> ParseMemoryNotes(const JsonValue& value)
{
    std::vector<MemoryNoteInfo> notes;
    if (!value.IsArray()) {
        return notes;
    }
    notes.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (item.IsObject()) {
            notes.push_back(ParseMemoryNote(item));
        }
    }
    return notes;
}

std::vector<FileChange> ParseChanges(const JsonValue& value)
{
    std::vector<FileChange> changes;
    if (!value.IsArray()) {
        return changes;
    }
    changes.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        FileChange change;
        change.action = item["action"].AsString();
        change.path = item["path"].AsString();
        change.has_content = item.Has("content") && !item["content"].IsNull();
        change.content = change.has_content ? item["content"].AsString() : "";
        change.summary = item["summary"].AsString();
        changes.push_back(std::move(change));
    }
    return changes;
}

std::vector<ToolEvent> ParseEvents(const JsonValue& value)
{
    std::vector<ToolEvent> events;
    if (!value.IsArray()) {
        return events;
    }
    events.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        ToolEvent event;
        event.kind = item["kind"].AsString();
        event.title = item["title"].AsString();
        event.status = item["status"].AsString("ok");
        event.detail = item["detail"].AsString();
        event.created_at = item["created_at"].AsString();
        events.push_back(std::move(event));
    }
    return events;
}

std::vector<RouteCandidateInfo> ParseRouteCandidates(const JsonValue& value)
{
    std::vector<RouteCandidateInfo> candidates;
    if (!value.IsArray()) {
        return candidates;
    }
    candidates.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        RouteCandidateInfo candidate;
        candidate.candidate_id = item["candidate_id"].AsString();
        candidate.role = item["role"].AsString();
        candidate.provider_hint = item["provider_hint"].AsString();
        candidate.required_capabilities = ParseStringArray(item["required_capabilities"]);
        candidate.privacy_mode = item["privacy_mode"].AsString("local-first");
        candidate.reason = item["reason"].AsString();
        candidate.confidence = item["confidence"].AsDouble(0.0);
        candidates.push_back(std::move(candidate));
    }
    return candidates;
}

RoutingDecisionInfo ParseRoutingDecision(const JsonValue& value, bool* present = nullptr)
{
    RoutingDecisionInfo routing;
    if (present != nullptr) {
        *present = value.IsObject();
    }
    if (!value.IsObject()) {
        return routing;
    }
    routing.task_role = value["task_role"].AsString();
    routing.provider_hint = value["provider_hint"].AsString();
    routing.privacy_mode = value["privacy_mode"].AsString("local-first");
    routing.candidates = ParseRouteCandidates(value["candidates"]);
    routing.fallback_roles = ParseStringArray(value["fallback_roles"]);
    routing.requires_tools = value["requires_tools"].AsBool(false);
    routing.requires_workspace = value["requires_workspace"].AsBool(false);
    routing.summary = value["summary"].AsString();
    routing.confidence = value["confidence"].AsDouble(0.0);
    return routing;
}

RouteProfileInfo ParseRouteProfile(const JsonValue& value)
{
    RouteProfileInfo profile;
    if (!value.IsObject()) {
        return profile;
    }
    profile.id = value["id"].AsString();
    profile.label = value["label"].AsString();
    profile.category = value["category"].AsString();
    profile.reason = value["reason"].AsString();
    profile.preferred_roles = ParseStringArray(value["preferred_roles"]);
    profile.stack_keywords = ParseStringArray(value["stack_keywords"]);
    profile.focus_paths = ParseStringArray(value["focus_paths"]);
    return profile;
}

TaskPlanInfo ParseTaskPlan(const JsonValue& value, bool* present = nullptr)
{
    TaskPlanInfo plan;
    if (present != nullptr) {
        *present = value.IsObject();
    }
    if (!value.IsObject()) {
        return plan;
    }
    plan.intent = value["intent"].AsString();
    plan.objective = value["objective"].AsString();
    plan.workflow = value["workflow"].AsString();
    plan.route_profile = ParseRouteProfile(value["route_profile"]);
    plan.steps = ParseStringArray(value["steps"]);
    plan.context_requirements = ParseStringArray(value["context_requirements"]);
    plan.tool_requirements = ParseStringArray(value["tool_requirements"]);
    plan.risks = ParseStringArray(value["risks"]);
    plan.completion_criteria = ParseStringArray(value["completion_criteria"]);
    plan.routing = ParseRoutingDecision(value["routing"], &plan.has_routing);
    return plan;
}

std::vector<ContextBudgetItemInfo> ParseContextBudgetItems(const JsonValue& value)
{
    std::vector<ContextBudgetItemInfo> items;
    if (!value.IsArray()) {
        return items;
    }
    items.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        ContextBudgetItemInfo budget_item;
        budget_item.kind = item["kind"].AsString();
        budget_item.ref = item["ref"].AsString();
        budget_item.estimated_tokens = item["estimated_tokens"].AsInt(0);
        budget_item.included = item["included"].AsBool(true);
        budget_item.reason = item["reason"].AsString();
        items.push_back(std::move(budget_item));
    }
    return items;
}

ContextBudgetInfo ParseContextBudget(const JsonValue& value, bool* present = nullptr)
{
    ContextBudgetInfo budget;
    if (present != nullptr) {
        *present = value.IsObject();
    }
    if (!value.IsObject()) {
        return budget;
    }
    budget.intent = value["intent"].AsString();
    budget.route_role = value["route_role"].AsString();
    budget.strategy = value["strategy"].AsString();
    budget.privacy_mode = value["privacy_mode"].AsString("local-first");
    budget.max_context_tokens = value["max_context_tokens"].AsInt(0);
    budget.estimated_context_tokens = value["estimated_context_tokens"].AsInt(0);
    budget.estimated_file_tokens = value["estimated_file_tokens"].AsInt(0);
    budget.reserve_response_tokens = value["reserve_response_tokens"].AsInt(0);
    budget.max_context_files = value["max_context_files"].AsInt(0);
    budget.selected_file_count = value["selected_file_count"].AsInt(0);
    budget.workspace_file_count = value["workspace_file_count"].AsInt(0);
    budget.selected_memory_count = value["selected_memory_count"].AsInt(0);
    budget.selected_project_memory_count = value["selected_project_memory_count"].AsInt(0);
    budget.omitted_file_count = value["omitted_file_count"].AsInt(0);
    budget.omitted_memory_count = value["omitted_memory_count"].AsInt(0);
    budget.omitted_project_memory_count = value["omitted_project_memory_count"].AsInt(0);
    budget.max_file_chars = value["max_file_chars"].AsInt(0);
    budget.max_history_turns = value["max_history_turns"].AsInt(0);
    budget.notes = ParseStringArray(value["notes"]);
    budget.items = ParseContextBudgetItems(value["items"]);
    return budget;
}

ModelAttemptInfo ParseModelAttempt(const JsonValue& item)
{
    ModelAttemptInfo attempt;
    if (!item.IsObject()) {
        return attempt;
    }
    attempt.attempt = item["attempt"].AsInt(0);
    attempt.role = item["role"].AsString();
    attempt.provider_id = item["provider_id"].AsString();
    attempt.provider_label = item["provider_label"].AsString();
    attempt.provider_api = item["provider_api"].AsString();
    attempt.model = item["model"].AsString();
    attempt.endpoint = item["endpoint"].AsString();
    attempt.privacy_mode = item["privacy_mode"].AsString("local-first");
    attempt.status = item["status"].AsString("planned");
    attempt.reason = item["reason"].AsString();
    attempt.error = item["error"].AsString();
    attempt.retryable = item["retryable"].AsBool(true);
    attempt.has_input_tokens = item.Has("input_tokens") && !item["input_tokens"].IsNull();
    attempt.input_tokens = item["input_tokens"].AsInt(0);
    attempt.has_output_tokens = item.Has("output_tokens") && !item["output_tokens"].IsNull();
    attempt.output_tokens = item["output_tokens"].AsInt(0);
    attempt.has_estimated_cost = item.Has("estimated_cost_usd") && !item["estimated_cost_usd"].IsNull();
    attempt.estimated_cost_usd = item["estimated_cost_usd"].AsDouble(0.0);
    attempt.has_latency = item.Has("latency_ms") && !item["latency_ms"].IsNull();
    attempt.latency_ms = item["latency_ms"].AsInt(0);
    const JsonValue& metadata = item["metadata"];
    if (metadata.IsObject()) {
        attempt.candidate_id = metadata["candidate_id"].AsString();
        attempt.candidate_source = metadata["candidate_source"].AsString();
        attempt.candidate_provider_hint = metadata["candidate_provider_hint"].AsString();
        attempt.route_profile.id = metadata["route_profile_id"].AsString();
        attempt.route_profile.label = metadata["route_profile_label"].AsString();
        attempt.route_profile.category = metadata["route_profile_category"].AsString();
        attempt.route_profile.reason = metadata["route_profile_reason"].AsString();
        attempt.route_profile.preferred_roles = ParseStringArray(metadata["route_profile_preferred_roles"]);
        attempt.route_profile.stack_keywords = ParseStringArray(metadata["route_profile_stack_keywords"]);
        attempt.route_profile.focus_paths = ParseStringArray(metadata["route_profile_focus_paths"]);
        const std::string estimator_family = metadata["token_estimator_family"].AsString();
        const std::string estimator_source = metadata["token_estimator_source"].AsString();
        if (!estimator_family.empty() || !estimator_source.empty()) {
            attempt.token_estimator_source = estimator_family.empty()
                ? estimator_source
                : (estimator_source.empty() ? estimator_family : estimator_family + " / " + estimator_source);
        }
        attempt.benchmark_suite = metadata["benchmark_suite"].AsString();
        attempt.has_benchmark_suite_score = metadata.Has("benchmark_suite_score") && !metadata["benchmark_suite_score"].IsNull();
        attempt.benchmark_suite_score = metadata["benchmark_suite_score"].AsDouble(0.0);
        attempt.has_benchmark_overall_score = metadata.Has("benchmark_overall_score") && !metadata["benchmark_overall_score"].IsNull();
        attempt.benchmark_overall_score = metadata["benchmark_overall_score"].AsDouble(0.0);
        attempt.has_benchmark_avg_latency_ms = metadata.Has("benchmark_avg_latency_ms") && !metadata["benchmark_avg_latency_ms"].IsNull();
        attempt.benchmark_avg_latency_ms = metadata["benchmark_avg_latency_ms"].AsInt(0);
        attempt.benchmark_run_count = metadata["benchmark_run_count"].AsInt(0);
        attempt.benchmark_recommendation = metadata["benchmark_recommendation"].AsString();
        attempt.route_health_attempts = metadata["route_health_attempts"].AsInt(0);
        attempt.route_health_terminal_attempts = metadata["route_health_terminal_attempts"].AsInt(0);
        attempt.has_route_health_success_rate = metadata.Has("route_health_success_rate") && !metadata["route_health_success_rate"].IsNull();
        attempt.route_health_success_rate = metadata["route_health_success_rate"].AsDouble(0.0);
        attempt.has_route_health_failure_rate = metadata.Has("route_health_failure_rate") && !metadata["route_health_failure_rate"].IsNull();
        attempt.route_health_failure_rate = metadata["route_health_failure_rate"].AsDouble(0.0);
        attempt.has_route_health_penalty = metadata.Has("route_health_penalty") && !metadata["route_health_penalty"].IsNull();
        attempt.route_health_penalty = metadata["route_health_penalty"].AsDouble(0.0);
        attempt.route_health_cooldown = metadata["route_health_cooldown"].AsBool(false);
        attempt.route_health_recommendation = metadata["route_health_recommendation"].AsString();
        attempt.has_context_window = metadata.Has("context_window") && !metadata["context_window"].IsNull();
        attempt.context_window = metadata["context_window"].AsInt(0);
        attempt.has_context_window_utilization = metadata.Has("context_window_utilization") && !metadata["context_window_utilization"].IsNull();
        attempt.context_window_utilization = metadata["context_window_utilization"].AsDouble(0.0);
        attempt.structured_preview_delta_count = metadata["structured_preview_delta_count"].AsInt(0);
        attempt.structured_preview_char_count = metadata["structured_preview_char_count"].AsInt(0);
        attempt.structured_preview_reset_count = metadata["structured_preview_reset_count"].AsInt(0);
        attempt.structured_preview_emitted = metadata["structured_preview_emitted"].AsBool(false);
        attempt.structured_preview_retired = metadata["structured_preview_retired"].AsBool(false);
        attempt.structured_preview_final_winner = metadata["structured_preview_final_winner"].AsBool(false);
        attempt.structured_preview_retired_reason = metadata["structured_preview_retired_reason"].AsString();
    }
    if (attempt.candidate_id.empty()) {
        attempt.candidate_id = item["candidate_id"].AsString();
    }
    if (attempt.candidate_source.empty()) {
        attempt.candidate_source = item["candidate_source"].AsString();
    }
    if (attempt.candidate_provider_hint.empty()) {
        attempt.candidate_provider_hint = item["candidate_provider_hint"].AsString();
    }
    if (attempt.token_estimator_source.empty()) {
        attempt.token_estimator_source = item["token_estimator_source"].AsString();
    }
    if (!attempt.has_context_window) {
        attempt.has_context_window = item.Has("context_window") && !item["context_window"].IsNull();
        attempt.context_window = item["context_window"].AsInt(0);
    }
    if (!attempt.has_context_window_utilization) {
        attempt.has_context_window_utilization = item.Has("context_window_utilization") && !item["context_window_utilization"].IsNull();
        attempt.context_window_utilization = item["context_window_utilization"].AsDouble(0.0);
    }
    return attempt;
}

std::vector<ModelAttemptInfo> ParseModelAttempts(const JsonValue& value)
{
    std::vector<ModelAttemptInfo> attempts;
    if (!value.IsArray()) {
        return attempts;
    }
    attempts.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        attempts.push_back(ParseModelAttempt(item));
    }
    return attempts;
}

ContextBudgetTelemetryEntryInfo ParseContextBudgetTelemetryEntry(const JsonValue& item, bool* present = nullptr)
{
    ContextBudgetTelemetryEntryInfo entry;
    if (present != nullptr) {
        *present = item.IsObject();
    }
    if (!item.IsObject()) {
        return entry;
    }

    entry.task_id = item["task_id"].AsString();
    entry.created_at = item["created_at"].AsString();
    entry.workspace_root = item["workspace_root"].AsString();
    entry.intent = item["intent"].AsString();
    entry.route_role = item["route_role"].AsString();
    entry.strategy = item["strategy"].AsString();
    entry.privacy_mode = item["privacy_mode"].AsString("local-first");
    entry.max_context_tokens = item["max_context_tokens"].AsInt(0);
    entry.estimated_context_tokens = item["estimated_context_tokens"].AsInt(0);
    entry.estimated_file_tokens = item["estimated_file_tokens"].AsInt(0);
    entry.reserve_response_tokens = item["reserve_response_tokens"].AsInt(0);
    entry.selected_file_count = item["selected_file_count"].AsInt(0);
    entry.omitted_file_count = item["omitted_file_count"].AsInt(0);
    const bool has_payload = item["payload"].IsObject();
    entry.payload = ParseContextBudget(item["payload"]);
    if (entry.payload.intent.empty()) {
        entry.payload.intent = entry.intent;
    }
    if (entry.payload.route_role.empty()) {
        entry.payload.route_role = entry.route_role;
    }
    if (entry.payload.strategy.empty()) {
        entry.payload.strategy = entry.strategy;
    }
    if (!has_payload) {
        entry.payload.privacy_mode = entry.privacy_mode;
    }
    if (entry.payload.max_context_tokens == 0) {
        entry.payload.max_context_tokens = entry.max_context_tokens;
    }
    if (entry.payload.estimated_context_tokens == 0) {
        entry.payload.estimated_context_tokens = entry.estimated_context_tokens;
    }
    if (entry.payload.estimated_file_tokens == 0) {
        entry.payload.estimated_file_tokens = entry.estimated_file_tokens;
    }
    if (entry.payload.reserve_response_tokens == 0) {
        entry.payload.reserve_response_tokens = entry.reserve_response_tokens;
    }
    if (entry.payload.selected_file_count == 0) {
        entry.payload.selected_file_count = entry.selected_file_count;
    }
    if (entry.payload.omitted_file_count == 0) {
        entry.payload.omitted_file_count = entry.omitted_file_count;
    }
    return entry;
}

std::vector<ContextBudgetTelemetryEntryInfo> ParseContextBudgetTelemetryEntries(const JsonValue& value)
{
    std::vector<ContextBudgetTelemetryEntryInfo> entries;
    if (!value.IsArray()) {
        return entries;
    }
    entries.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        entries.push_back(ParseContextBudgetTelemetryEntry(item));
    }
    return entries;
}

ModelAttemptTelemetryEntryInfo ParseModelAttemptTelemetryEntry(const JsonValue& item)
{
    ModelAttemptTelemetryEntryInfo entry;
    if (!item.IsObject()) {
        return entry;
    }
    entry.task_id = item["task_id"].AsString();
    entry.created_at = item["created_at"].AsString();
    entry.workspace_root = item["workspace_root"].AsString();
    entry.attempt = ParseModelAttempt(item["attempt"]);
    return entry;
}

std::vector<ModelAttemptTelemetryEntryInfo> ParseModelAttemptTelemetryEntries(const JsonValue& value)
{
    std::vector<ModelAttemptTelemetryEntryInfo> entries;
    if (!value.IsArray()) {
        return entries;
    }
    entries.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        entries.push_back(ParseModelAttemptTelemetryEntry(item));
    }
    return entries;
}

TelemetrySnapshot ParseTelemetry(const JsonValue& value)
{
    TelemetrySnapshot snapshot;
    if (!value.IsObject()) {
        return snapshot;
    }
    snapshot.workspace_root = value["workspace_root"].AsString();
    snapshot.context_budgets = ParseContextBudgetTelemetryEntries(value["context_budgets"]);
    snapshot.model_attempts = ParseModelAttemptTelemetryEntries(value["model_attempts"]);
    return snapshot;
}

RouteQualityOverviewInfo ParseRouteQualityOverview(const JsonValue& value)
{
    RouteQualityOverviewInfo overview;
    if (!value.IsObject()) {
        return overview;
    }
    overview.task_count = value["task_count"].AsInt(0);
    overview.context_budget_count = value["context_budget_count"].AsInt(0);
    overview.model_attempt_count = value["model_attempt_count"].AsInt(0);
    overview.succeeded_attempts = value["succeeded_attempts"].AsInt(0);
    overview.failed_attempts = value["failed_attempts"].AsInt(0);
    overview.planned_attempts = value["planned_attempts"].AsInt(0);
    overview.fallback_attempts = value["fallback_attempts"].AsInt(0);
    overview.retryable_failures = value["retryable_failures"].AsInt(0);
    overview.success_rate = value["success_rate"].AsDouble(0.0);
    overview.fallback_rate = value["fallback_rate"].AsDouble(0.0);
    overview.estimated_cost_usd = value["estimated_cost_usd"].AsDouble(0.0);
    overview.input_tokens = value["input_tokens"].AsInt(0);
    overview.output_tokens = value["output_tokens"].AsInt(0);
    overview.has_average_latency = value.Has("average_latency_ms") && !value["average_latency_ms"].IsNull();
    overview.average_latency_ms = value["average_latency_ms"].AsDouble(0.0);
    overview.has_average_context_utilization = value.Has("average_context_utilization") && !value["average_context_utilization"].IsNull();
    overview.average_context_utilization = value["average_context_utilization"].AsDouble(0.0);
    overview.average_context_tokens = value["average_context_tokens"].AsDouble(0.0);
    overview.average_selected_files = value["average_selected_files"].AsDouble(0.0);
    overview.average_omitted_files = value["average_omitted_files"].AsDouble(0.0);
    overview.reliability_score = value["reliability_score"].AsDouble(0.0);
    overview.feedback_count = value["feedback_count"].AsInt(0);
    overview.positive_feedback = value["positive_feedback"].AsInt(0);
    overview.negative_feedback = value["negative_feedback"].AsInt(0);
    overview.revised_feedback = value["revised_feedback"].AsInt(0);
    overview.regenerated_feedback = value["regenerated_feedback"].AsInt(0);
    overview.applied_feedback = value["applied_feedback"].AsInt(0);
    overview.rolled_back_feedback = value["rolled_back_feedback"].AsInt(0);
    overview.corrected_feedback = value["corrected_feedback"].AsInt(0);
    overview.positive_feedback_rate = value["positive_feedback_rate"].AsDouble(0.0);
    overview.negative_feedback_rate = value["negative_feedback_rate"].AsDouble(0.0);
    return overview;
}

std::vector<RouteQualityProviderRollupInfo> ParseRouteQualityProviders(const JsonValue& value)
{
    std::vector<RouteQualityProviderRollupInfo> providers;
    if (!value.IsArray()) {
        return providers;
    }
    providers.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        RouteQualityProviderRollupInfo provider;
        provider.provider_id = item["provider_id"].AsString();
        provider.provider_label = item["provider_label"].AsString();
        provider.provider_api = item["provider_api"].AsString();
        provider.model = item["model"].AsString();
        provider.task_count = item["task_count"].AsInt(0);
        provider.attempts = item["attempts"].AsInt(0);
        provider.successes = item["successes"].AsInt(0);
        provider.failures = item["failures"].AsInt(0);
        provider.planned = item["planned"].AsInt(0);
        provider.fallback_attempts = item["fallback_attempts"].AsInt(0);
        provider.success_rate = item["success_rate"].AsDouble(0.0);
        provider.fallback_rate = item["fallback_rate"].AsDouble(0.0);
        provider.estimated_cost_usd = item["estimated_cost_usd"].AsDouble(0.0);
        provider.input_tokens = item["input_tokens"].AsInt(0);
        provider.output_tokens = item["output_tokens"].AsInt(0);
        provider.has_average_latency = item.Has("average_latency_ms") && !item["average_latency_ms"].IsNull();
        provider.average_latency_ms = item["average_latency_ms"].AsDouble(0.0);
        provider.has_average_context_utilization = item.Has("average_context_utilization") && !item["average_context_utilization"].IsNull();
        provider.average_context_utilization = item["average_context_utilization"].AsDouble(0.0);
        provider.token_estimator_sources = ParseStringArray(item["token_estimator_sources"]);
        providers.push_back(std::move(provider));
    }
    return providers;
}

std::vector<RouteQualityTokenCalibrationInfo> ParseRouteQualityTokenCalibration(const JsonValue& value)
{
    std::vector<RouteQualityTokenCalibrationInfo> calibrations;
    if (!value.IsArray()) {
        return calibrations;
    }
    calibrations.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        RouteQualityTokenCalibrationInfo calibration;
        calibration.provider_id = item["provider_id"].AsString();
        calibration.provider_label = item["provider_label"].AsString();
        calibration.provider_api = item["provider_api"].AsString();
        calibration.model = item["model"].AsString();
        calibration.attempts = item["attempts"].AsInt(0);
        calibration.calibrated_attempts = item["calibrated_attempts"].AsInt(0);
        calibration.calibration_status = item["calibration_status"].AsString("insufficient");
        calibration.estimated_input_tokens = item["estimated_input_tokens"].AsInt(0);
        calibration.reported_input_tokens = item["reported_input_tokens"].AsInt(0);
        calibration.estimated_output_tokens = item["estimated_output_tokens"].AsInt(0);
        calibration.reported_output_tokens = item["reported_output_tokens"].AsInt(0);
        calibration.has_average_input_token_error = item.Has("average_input_token_error") && !item["average_input_token_error"].IsNull();
        calibration.average_input_token_error = item["average_input_token_error"].AsDouble(0.0);
        calibration.has_worst_input_token_error = item.Has("worst_input_token_error") && !item["worst_input_token_error"].IsNull();
        calibration.worst_input_token_error = item["worst_input_token_error"].AsDouble(0.0);
        calibration.has_average_output_token_error = item.Has("average_output_token_error") && !item["average_output_token_error"].IsNull();
        calibration.average_output_token_error = item["average_output_token_error"].AsDouble(0.0);
        calibration.has_worst_output_token_error = item.Has("worst_output_token_error") && !item["worst_output_token_error"].IsNull();
        calibration.worst_output_token_error = item["worst_output_token_error"].AsDouble(0.0);
        calibration.token_estimator_sources = ParseStringArray(item["token_estimator_sources"]);
        calibration.reported_token_sources = ParseStringArray(item["reported_token_sources"]);
        calibration.recommendation = item["recommendation"].AsString();
        calibrations.push_back(std::move(calibration));
    }
    return calibrations;
}

std::vector<RouteQualityTokenCalibrationTrendInfo> ParseRouteQualityTokenCalibrationTrends(const JsonValue& value)
{
    std::vector<RouteQualityTokenCalibrationTrendInfo> trends;
    if (!value.IsArray()) {
        return trends;
    }
    trends.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        RouteQualityTokenCalibrationTrendInfo trend;
        trend.provider_id = item["provider_id"].AsString();
        trend.provider_label = item["provider_label"].AsString();
        trend.provider_api = item["provider_api"].AsString();
        trend.model = item["model"].AsString();
        trend.period_start = item["period_start"].AsString();
        trend.attempts = item["attempts"].AsInt(0);
        trend.calibrated_attempts = item["calibrated_attempts"].AsInt(0);
        trend.calibration_status = item["calibration_status"].AsString("insufficient");
        trend.trend_direction = item["trend_direction"].AsString("baseline");
        trend.estimated_input_tokens = item["estimated_input_tokens"].AsInt(0);
        trend.reported_input_tokens = item["reported_input_tokens"].AsInt(0);
        trend.estimated_output_tokens = item["estimated_output_tokens"].AsInt(0);
        trend.reported_output_tokens = item["reported_output_tokens"].AsInt(0);
        trend.has_average_input_token_error = item.Has("average_input_token_error") && !item["average_input_token_error"].IsNull();
        trend.average_input_token_error = item["average_input_token_error"].AsDouble(0.0);
        trend.has_worst_input_token_error = item.Has("worst_input_token_error") && !item["worst_input_token_error"].IsNull();
        trend.worst_input_token_error = item["worst_input_token_error"].AsDouble(0.0);
        trend.has_average_output_token_error = item.Has("average_output_token_error") && !item["average_output_token_error"].IsNull();
        trend.average_output_token_error = item["average_output_token_error"].AsDouble(0.0);
        trend.has_worst_output_token_error = item.Has("worst_output_token_error") && !item["worst_output_token_error"].IsNull();
        trend.worst_output_token_error = item["worst_output_token_error"].AsDouble(0.0);
        trend.recommendation = item["recommendation"].AsString();
        trends.push_back(std::move(trend));
    }
    return trends;
}

std::vector<RouteQualityStructuredPreviewInfo> ParseRouteQualityStructuredPreview(const JsonValue& value)
{
    std::vector<RouteQualityStructuredPreviewInfo> previews;
    if (!value.IsArray()) {
        return previews;
    }
    previews.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        RouteQualityStructuredPreviewInfo preview;
        preview.provider_id = item["provider_id"].AsString();
        preview.provider_label = item["provider_label"].AsString();
        preview.provider_api = item["provider_api"].AsString();
        preview.model = item["model"].AsString();
        preview.attempts = item["attempts"].AsInt(0);
        preview.previewed_attempts = item["previewed_attempts"].AsInt(0);
        preview.final_winning_attempts = item["final_winning_attempts"].AsInt(0);
        preview.retired_attempts = item["retired_attempts"].AsInt(0);
        preview.reset_count = item["reset_count"].AsInt(0);
        preview.delta_count = item["delta_count"].AsInt(0);
        preview.char_count = item["char_count"].AsInt(0);
        preview.preview_success_rate = item["preview_success_rate"].AsDouble(0.0);
        preview.retired_rate = item["retired_rate"].AsDouble(0.0);
        preview.average_preview_chars = item["average_preview_chars"].AsDouble(0.0);
        preview.preview_status = item["preview_status"].AsString("insufficient");
        preview.retired_reasons = ParseStringArray(item["retired_reasons"]);
        preview.recommendation = item["recommendation"].AsString();
        previews.push_back(std::move(preview));
    }
    return previews;
}

std::vector<RouteQualityRoleRollupInfo> ParseRouteQualityRoles(const JsonValue& value)
{
    std::vector<RouteQualityRoleRollupInfo> roles;
    if (!value.IsArray()) {
        return roles;
    }
    roles.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        RouteQualityRoleRollupInfo role;
        role.role = item["role"].AsString();
        role.task_count = item["task_count"].AsInt(0);
        role.attempts = item["attempts"].AsInt(0);
        role.successes = item["successes"].AsInt(0);
        role.failures = item["failures"].AsInt(0);
        role.planned = item["planned"].AsInt(0);
        role.fallback_attempts = item["fallback_attempts"].AsInt(0);
        role.success_rate = item["success_rate"].AsDouble(0.0);
        role.estimated_cost_usd = item["estimated_cost_usd"].AsDouble(0.0);
        role.has_average_latency = item.Has("average_latency_ms") && !item["average_latency_ms"].IsNull();
        role.average_latency_ms = item["average_latency_ms"].AsDouble(0.0);
        roles.push_back(std::move(role));
    }
    return roles;
}

std::vector<RouteQualityContextRollupInfo> ParseRouteQualityContexts(const JsonValue& value)
{
    std::vector<RouteQualityContextRollupInfo> contexts;
    if (!value.IsArray()) {
        return contexts;
    }
    contexts.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        RouteQualityContextRollupInfo context;
        context.route_role = item["route_role"].AsString();
        context.intent = item["intent"].AsString();
        context.budget_count = item["budget_count"].AsInt(0);
        context.average_context_tokens = item["average_context_tokens"].AsDouble(0.0);
        context.average_file_tokens = item["average_file_tokens"].AsDouble(0.0);
        context.average_reserved_response_tokens = item["average_reserved_response_tokens"].AsDouble(0.0);
        context.average_selected_files = item["average_selected_files"].AsDouble(0.0);
        context.average_omitted_files = item["average_omitted_files"].AsDouble(0.0);
        context.has_average_budget_utilization = item.Has("average_budget_utilization") && !item["average_budget_utilization"].IsNull();
        context.average_budget_utilization = item["average_budget_utilization"].AsDouble(0.0);
        contexts.push_back(std::move(context));
    }
    return contexts;
}

std::vector<RouteQualityContextDrilldownInfo> ParseRouteQualityContextDrilldowns(const JsonValue& value)
{
    std::vector<RouteQualityContextDrilldownInfo> drilldowns;
    if (!value.IsArray()) {
        return drilldowns;
    }
    drilldowns.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        RouteQualityContextDrilldownInfo drilldown;
        drilldown.task_id = item["task_id"].AsString();
        drilldown.created_at = item["created_at"].AsString();
        drilldown.route_role = item["route_role"].AsString();
        drilldown.intent = item["intent"].AsString();
        drilldown.strategy = item["strategy"].AsString();
        drilldown.privacy_mode = item["privacy_mode"].AsString("local-first");
        drilldown.max_context_tokens = item["max_context_tokens"].AsInt(0);
        drilldown.estimated_context_tokens = item["estimated_context_tokens"].AsInt(0);
        drilldown.estimated_file_tokens = item["estimated_file_tokens"].AsInt(0);
        drilldown.reserve_response_tokens = item["reserve_response_tokens"].AsInt(0);
        drilldown.has_utilization = item.Has("utilization") && !item["utilization"].IsNull();
        drilldown.utilization = item["utilization"].AsDouble(0.0);
        drilldown.selected_file_count = item["selected_file_count"].AsInt(0);
        drilldown.omitted_file_count = item["omitted_file_count"].AsInt(0);
        drilldown.selected_memory_count = item["selected_memory_count"].AsInt(0);
        drilldown.omitted_memory_count = item["omitted_memory_count"].AsInt(0);
        drilldown.selected_project_memory_count = item["selected_project_memory_count"].AsInt(0);
        drilldown.omitted_project_memory_count = item["omitted_project_memory_count"].AsInt(0);
        drilldown.selected_refs = ParseStringArray(item["selected_refs"]);
        drilldown.omitted_refs = ParseStringArray(item["omitted_refs"]);
        drilldown.largest_refs = ParseStringArray(item["largest_refs"]);
        drilldown.notes = ParseStringArray(item["notes"]);
        drilldown.recommendations = ParseStringArray(item["recommendations"]);
        drilldowns.push_back(std::move(drilldown));
    }
    return drilldowns;
}

std::vector<FeedbackAttributionRollupInfo> ParseFeedbackAttributionRollups(const JsonValue& value)
{
    std::vector<FeedbackAttributionRollupInfo> rollups;
    if (!value.IsArray()) {
        return rollups;
    }
    rollups.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        FeedbackAttributionRollupInfo rollup;
        rollup.dimension = item["dimension"].AsString();
        rollup.key = item["key"].AsString();
        rollup.label = item["label"].AsString();
        rollup.feedback_count = item["feedback_count"].AsInt(0);
        rollup.task_count = item["task_count"].AsInt(0);
        rollup.positive_count = item["positive_count"].AsInt(0);
        rollup.negative_count = item["negative_count"].AsInt(0);
        rollup.copied_count = item["copied_count"].AsInt(0);
        rollup.revised_count = item["revised_count"].AsInt(0);
        rollup.regenerated_count = item["regenerated_count"].AsInt(0);
        rollup.applied_count = item["applied_count"].AsInt(0);
        rollup.rolled_back_count = item["rolled_back_count"].AsInt(0);
        rollup.corrected_count = item["corrected_count"].AsInt(0);
        rollup.positive_rate = item["positive_rate"].AsDouble(0.0);
        rollup.negative_rate = item["negative_rate"].AsDouble(0.0);
        rollup.latest_at = item["latest_at"].AsString();
        rollups.push_back(std::move(rollup));
    }
    return rollups;
}

std::vector<FeedbackTrendBucketInfo> ParseFeedbackTrendBuckets(const JsonValue& value)
{
    std::vector<FeedbackTrendBucketInfo> buckets;
    if (!value.IsArray()) {
        return buckets;
    }
    buckets.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        FeedbackTrendBucketInfo bucket;
        bucket.period_start = item["period_start"].AsString();
        bucket.feedback_count = item["feedback_count"].AsInt(0);
        bucket.positive_count = item["positive_count"].AsInt(0);
        bucket.negative_count = item["negative_count"].AsInt(0);
        bucket.copied_count = item["copied_count"].AsInt(0);
        bucket.revised_count = item["revised_count"].AsInt(0);
        bucket.regenerated_count = item["regenerated_count"].AsInt(0);
        bucket.applied_count = item["applied_count"].AsInt(0);
        bucket.rolled_back_count = item["rolled_back_count"].AsInt(0);
        bucket.corrected_count = item["corrected_count"].AsInt(0);
        bucket.positive_rate = item["positive_rate"].AsDouble(0.0);
        bucket.negative_rate = item["negative_rate"].AsDouble(0.0);
        buckets.push_back(std::move(bucket));
    }
    return buckets;
}

std::vector<FeedbackTelemetryEntryInfo> ParseFeedbackTelemetryEntries(const JsonValue& value)
{
    std::vector<FeedbackTelemetryEntryInfo> entries;
    if (!value.IsArray()) {
        return entries;
    }
    entries.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        FeedbackTelemetryEntryInfo entry;
        entry.id = item["id"].AsString();
        entry.created_at = item["created_at"].AsString();
        entry.task_id = item["task_id"].AsString();
        entry.sentiment = item["sentiment"].AsString("neutral");
        entry.action = item["action"].AsString("manual");
        entry.target = item["target"].AsString("assistant_response");
        entry.model_label = item["model_label"].AsString();
        entry.route_role = item["route_role"].AsString();
        entry.candidate_id = item["candidate_id"].AsString();
        entry.content_hash = item["content_hash"].AsString();
        entry.context = item["context"].AsString();
        entries.push_back(std::move(entry));
    }
    return entries;
}

RouteQualitySnapshot ParseRouteQuality(const JsonValue& value)
{
    RouteQualitySnapshot snapshot;
    if (!value.IsObject()) {
        return snapshot;
    }
    snapshot.workspace_root = value["workspace_root"].AsString();
    snapshot.limit = value["limit"].AsInt(0);
    snapshot.overview = ParseRouteQualityOverview(value["overview"]);
    snapshot.providers = ParseRouteQualityProviders(value["providers"]);
    snapshot.token_calibration = ParseRouteQualityTokenCalibration(value["token_calibration"]);
    snapshot.token_calibration_trends = ParseRouteQualityTokenCalibrationTrends(value["token_calibration_trends"]);
    snapshot.structured_preview = ParseRouteQualityStructuredPreview(value["structured_preview"]);
    snapshot.roles = ParseRouteQualityRoles(value["roles"]);
    snapshot.contexts = ParseRouteQualityContexts(value["contexts"]);
    snapshot.context_drilldowns = ParseRouteQualityContextDrilldowns(value["context_drilldowns"]);
    snapshot.feedback_rollups = ParseFeedbackAttributionRollups(value["feedback_rollups"]);
    snapshot.feedback_trends = ParseFeedbackTrendBuckets(value["feedback_trends"]);
    snapshot.feedback_events = ParseFeedbackTelemetryEntries(value["feedback_events"]);
    snapshot.recommendations = ParseStringArray(value["recommendations"]);
    return snapshot;
}

std::vector<RouteHealthInfo> ParseRouteHealthSignals(const JsonValue& value)
{
    std::vector<RouteHealthInfo> signals;
    if (!value.IsArray()) {
        return signals;
    }
    signals.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        RouteHealthInfo signal;
        signal.provider_id = item["provider_id"].AsString();
        signal.provider_label = item["provider_label"].AsString();
        signal.model = item["model"].AsString();
        signal.role = item["role"].AsString();
        signal.attempts = item["attempts"].AsInt(0);
        signal.terminal_attempts = item["terminal_attempts"].AsInt(0);
        signal.successes = item["successes"].AsInt(0);
        signal.failures = item["failures"].AsInt(0);
        signal.fallback_attempts = item["fallback_attempts"].AsInt(0);
        signal.success_rate = item["success_rate"].AsDouble(0.0);
        signal.failure_rate = item["failure_rate"].AsDouble(0.0);
        signal.has_average_latency = item.Has("average_latency_ms") && !item["average_latency_ms"].IsNull();
        signal.average_latency_ms = item["average_latency_ms"].AsDouble(0.0);
        signal.structured_preview_attempts = item["structured_preview_attempts"].AsInt(0);
        signal.structured_preview_retired_attempts = item["structured_preview_retired_attempts"].AsInt(0);
        signal.structured_preview_reset_count = item["structured_preview_reset_count"].AsInt(0);
        signal.structured_preview_final_winners = item["structured_preview_final_winners"].AsInt(0);
        signal.structured_preview_retired_rate = item["structured_preview_retired_rate"].AsDouble(0.0);
        signal.penalty = item["penalty"].AsDouble(0.0);
        signal.cooldown = item["cooldown"].AsBool(false);
        signal.latest_error = item["latest_error"].AsString();
        signal.latest_at = item["latest_at"].AsString();
        signal.recommendation = item["recommendation"].AsString();
        signals.push_back(std::move(signal));
    }
    return signals;
}

std::vector<FallbackInspectorCandidateInfo> ParseFallbackInspectorCandidates(const JsonValue& value)
{
    std::vector<FallbackInspectorCandidateInfo> candidates;
    if (!value.IsArray()) {
        return candidates;
    }
    candidates.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        FallbackInspectorCandidateInfo candidate;
        candidate.index = item["index"].AsInt(0);
        candidate.candidate_id = item["candidate_id"].AsString();
        candidate.role = item["role"].AsString();
        candidate.provider_hint = item["provider_hint"].AsString();
        candidate.required_capabilities = ParseStringArray(item["required_capabilities"]);
        candidate.privacy_mode = item["privacy_mode"].AsString("local-first");
        candidate.reason = item["reason"].AsString();
        candidate.confidence = item["confidence"].AsDouble(0.0);
        candidate.status = item["status"].AsString("not-planned");
        candidate.has_matched_attempt_number = item.Has("matched_attempt_number") && !item["matched_attempt_number"].IsNull();
        candidate.matched_attempt_number = item["matched_attempt_number"].AsInt(0);
        candidate.provider_id = item["provider_id"].AsString();
        candidate.provider_label = item["provider_label"].AsString();
        candidate.provider_api = item["provider_api"].AsString();
        candidate.model = item["model"].AsString();
        candidate.has_registry_resolved = item.Has("registry_resolved") && !item["registry_resolved"].IsNull();
        candidate.registry_resolved = item["registry_resolved"].AsBool(false);
        candidate.has_retryable = item.Has("retryable") && !item["retryable"].IsNull();
        candidate.retryable = item["retryable"].AsBool(false);
        candidate.has_input_tokens = item.Has("input_tokens") && !item["input_tokens"].IsNull();
        candidate.input_tokens = item["input_tokens"].AsInt(0);
        candidate.has_output_tokens = item.Has("output_tokens") && !item["output_tokens"].IsNull();
        candidate.output_tokens = item["output_tokens"].AsInt(0);
        candidate.has_estimated_cost = item.Has("estimated_cost_usd") && !item["estimated_cost_usd"].IsNull();
        candidate.estimated_cost_usd = item["estimated_cost_usd"].AsDouble(0.0);
        candidate.has_latency = item.Has("latency_ms") && !item["latency_ms"].IsNull();
        candidate.latency_ms = item["latency_ms"].AsInt(0);
        candidate.token_estimator_source = item["token_estimator_source"].AsString();
        candidate.has_context_window = item.Has("context_window") && !item["context_window"].IsNull();
        candidate.context_window = item["context_window"].AsInt(0);
        candidate.has_context_window_utilization = item.Has("context_window_utilization") && !item["context_window_utilization"].IsNull();
        candidate.context_window_utilization = item["context_window_utilization"].AsDouble(0.0);
        candidate.error = item["error"].AsString();
        candidates.push_back(std::move(candidate));
    }
    return candidates;
}

std::vector<FallbackInspectorTaskInfo> ParseFallbackInspectorTasks(const JsonValue& value)
{
    std::vector<FallbackInspectorTaskInfo> tasks;
    if (!value.IsArray()) {
        return tasks;
    }
    tasks.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        FallbackInspectorTaskInfo task;
        task.task_id = item["task_id"].AsString();
        task.created_at = item["created_at"].AsString();
        task.finished_at = item["finished_at"].AsString();
        task.mode = item["mode"].AsString();
        task.workspace_root = item["workspace_root"].AsString();
        task.message = item["message"].AsString();
        task.status = item["status"].AsString();
        task.task_plan = ParseTaskPlan(item["task_plan"], &task.has_task_plan);
        task.context_budget = ParseContextBudgetTelemetryEntry(item["context_budget"], &task.has_context_budget);
        task.attempts = ParseModelAttemptTelemetryEntries(item["attempts"]);
        task.candidates = ParseFallbackInspectorCandidates(item["candidates"]);
        task.fallback_roles = ParseStringArray(item["fallback_roles"]);
        task.summary = item["summary"].AsString();
        task.recommendations = ParseStringArray(item["recommendations"]);
        tasks.push_back(std::move(task));
    }
    return tasks;
}

FallbackInspectorSnapshot ParseFallbackInspector(const JsonValue& value)
{
    FallbackInspectorSnapshot snapshot;
    if (!value.IsObject()) {
        return snapshot;
    }
    snapshot.workspace_root = value["workspace_root"].AsString();
    snapshot.limit = value["limit"].AsInt(0);
    snapshot.task_count = value["task_count"].AsInt(0);
    snapshot.tasks = ParseFallbackInspectorTasks(value["tasks"]);
    snapshot.recommendations = ParseStringArray(value["recommendations"]);
    return snapshot;
}

std::vector<RoutePolicyProviderProposalInfo> ParseRoutePolicyProviderProposals(const JsonValue& value)
{
    std::vector<RoutePolicyProviderProposalInfo> proposals;
    if (!value.IsArray()) {
        return proposals;
    }
    proposals.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        RoutePolicyProviderProposalInfo proposal;
        proposal.provider_id = item["provider_id"].AsString();
        proposal.provider_label = item["provider_label"].AsString();
        proposal.provider_api = item["provider_api"].AsString();
        proposal.model = item["model"].AsString();
        proposal.observed_rank = item["observed_rank"].AsInt(0);
        proposal.proposed_rank = item["proposed_rank"].AsInt(0);
        proposal.action = item["action"].AsString("hold");
        proposal.risk_level = item["risk_level"].AsString("low");
        proposal.confidence = item["confidence"].AsDouble(0.0);
        proposal.score = item["score"].AsDouble(0.0);
        proposal.attempts = item["attempts"].AsInt(0);
        proposal.successes = item["successes"].AsInt(0);
        proposal.failures = item["failures"].AsInt(0);
        proposal.fallback_rate = item["fallback_rate"].AsDouble(0.0);
        proposal.success_rate = item["success_rate"].AsDouble(0.0);
        proposal.positive_feedback_rate = item["positive_feedback_rate"].AsDouble(0.0);
        proposal.negative_feedback_rate = item["negative_feedback_rate"].AsDouble(0.0);
        proposal.has_average_latency = item.Has("average_latency_ms") && !item["average_latency_ms"].IsNull();
        proposal.average_latency_ms = item["average_latency_ms"].AsDouble(0.0);
        proposal.has_average_context_utilization = item.Has("average_context_utilization") && !item["average_context_utilization"].IsNull();
        proposal.average_context_utilization = item["average_context_utilization"].AsDouble(0.0);
        proposal.estimated_cost_usd = item["estimated_cost_usd"].AsDouble(0.0);
        proposal.reasons = ParseStringArray(item["reasons"]);
        proposal.risks = ParseStringArray(item["risks"]);
        proposals.push_back(std::move(proposal));
    }
    return proposals;
}

std::vector<RoutePolicyRoleProposalInfo> ParseRoutePolicyRoleProposals(const JsonValue& value)
{
    std::vector<RoutePolicyRoleProposalInfo> proposals;
    if (!value.IsArray()) {
        return proposals;
    }
    proposals.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        RoutePolicyRoleProposalInfo proposal;
        proposal.role = item["role"].AsString();
        proposal.action = item["action"].AsString("keep");
        proposal.observed_primary_provider = item["observed_primary_provider"].AsString();
        proposal.proposed_primary_provider = item["proposed_primary_provider"].AsString();
        proposal.confidence = item["confidence"].AsDouble(0.0);
        proposal.task_count = item["task_count"].AsInt(0);
        proposal.attempts = item["attempts"].AsInt(0);
        proposal.success_rate = item["success_rate"].AsDouble(0.0);
        proposal.fallback_attempts = item["fallback_attempts"].AsInt(0);
        proposal.score_delta = item["score_delta"].AsDouble(0.0);
        proposal.candidate_provider_ids = ParseStringArray(item["candidate_provider_ids"]);
        proposal.reasons = ParseStringArray(item["reasons"]);
        proposal.risks = ParseStringArray(item["risks"]);
        proposals.push_back(std::move(proposal));
    }
    return proposals;
}

RoutePolicyDiffInfo ParseRoutePolicyDiff(const JsonValue& value)
{
    RoutePolicyDiffInfo diff;
    if (!value.IsObject()) {
        return diff;
    }
    diff.workspace_root = value["workspace_root"].AsString();
    diff.generated_at = value["generated_at"].AsString();
    diff.limit = value["limit"].AsInt(0);
    diff.source = value["source"].AsString("live");
    diff.source_snapshot_id = value["source_snapshot_id"].AsString();
    diff.source_snapshot_age_seconds = value["source_snapshot_age_seconds"].AsInt(0);
    diff.source_snapshot_stale = value["source_snapshot_stale"].AsBool(false);
    diff.min_attempts = value["min_attempts"].AsInt(3);
    diff.provider_proposals = ParseRoutePolicyProviderProposals(value["provider_proposals"]);
    diff.role_proposals = ParseRoutePolicyRoleProposals(value["role_proposals"]);
    diff.recommendations = ParseStringArray(value["recommendations"]);
    diff.warnings = ParseStringArray(value["warnings"]);
    return diff;
}

CommandRun ParseCommandRun(const JsonValue& value, bool* present = nullptr)
{
    CommandRun command;
    if (present != nullptr) {
        *present = value.IsObject();
    }
    if (!value.IsObject()) {
        return command;
    }

    command.command = value["command"].AsString();
    command.cwd = value["cwd"].AsString();
    command.allowed = value["allowed"].AsBool(false);
    command.has_exit_code = value.Has("exit_code") && !value["exit_code"].IsNull();
    command.exit_code = value["exit_code"].AsInt(0);
    command.stdout_text = value["stdout"].AsString();
    command.stderr_text = value["stderr"].AsString();
    command.timed_out = value["timed_out"].AsBool(false);
    command.reason = value["reason"].AsString();
    command.category = value["category"].AsString();
    command.summary = value["summary"].AsString();
    return command;
}

ValidationRecipeInfo ParseValidationRecipe(const JsonValue& value, bool* present = nullptr)
{
    ValidationRecipeInfo recipe;
    if (present != nullptr) {
        *present = value.IsObject();
    }
    if (!value.IsObject()) {
        return recipe;
    }
    recipe.command = value["command"].AsString();
    recipe.label = value["label"].AsString();
    recipe.source = value["source"].AsString();
    recipe.updated_at = value["updated_at"].AsString();
    recipe.notes = value["notes"].AsString();
    return recipe;
}

ValidationProfileInfo ParseValidationProfile(const JsonValue& value)
{
    ValidationProfileInfo profile;
    if (!value.IsObject()) {
        return profile;
    }
    profile.workspace_root = value["workspace_root"].AsString();
    profile.profile = ParseValidationRecipe(value["profile"], &profile.has_profile);

    const JsonValue& suggestions = value["suggestions"];
    if (suggestions.IsArray()) {
        profile.suggestions.reserve(suggestions.array_value.size());
        for (const JsonValue& item : suggestions.array_value) {
            if (!item.IsObject()) {
                continue;
            }
            ValidationSuggestionInfo suggestion;
            suggestion.command = item["command"].AsString();
            suggestion.label = item["label"].AsString();
            suggestion.category = item["category"].AsString();
            suggestion.reason = item["reason"].AsString();
            profile.suggestions.push_back(std::move(suggestion));
        }
    }
    return profile;
}

VerificationStepInfo ParseVerificationStep(const JsonValue& value)
{
    VerificationStepInfo step;
    if (!value.IsObject()) {
        return step;
    }
    step.id = value["id"].AsString();
    step.phase = value["phase"].AsString();
    step.command = value["command"].AsString();
    step.label = value["label"].AsString();
    step.category = value["category"].AsString();
    step.required = value["required"].AsBool(true);
    step.reason = value["reason"].AsString();
    step.status = value["status"].AsString();
    step.run = ParseCommandRun(value["run"], &step.has_run);
    return step;
}

std::vector<VerificationStepInfo> ParseVerificationSteps(const JsonValue& value)
{
    std::vector<VerificationStepInfo> steps;
    if (!value.IsArray()) {
        return steps;
    }
    steps.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (item.IsObject()) {
            steps.push_back(ParseVerificationStep(item));
        }
    }
    return steps;
}

VerificationResult ParseVerificationResult(const JsonValue& value)
{
    VerificationResult result;
    if (!value.IsObject()) {
        return result;
    }
    result.task_id = value["task_id"].AsString();
    result.workspace_root = value["workspace_root"].AsString();
    result.status = value["status"].AsString();
    result.steps = ParseVerificationSteps(value["steps"]);
    result.events = ParseEvents(value["events"]);
    result.validation_profile = ParseValidationRecipe(value["validation_profile"], &result.has_validation_profile);
    result.first_failure = ParseCommandRun(value["first_failure"], &result.has_first_failure);
    result.warnings = ParseStringArray(value["warnings"]);
    return result;
}

std::vector<TaskSummary> ParseTasks(const JsonValue& value)
{
    std::vector<TaskSummary> tasks;
    if (!value.IsArray()) {
        return tasks;
    }
    tasks.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        TaskSummary task;
        task.id = item["id"].AsString();
        task.created_at = item["created_at"].AsString();
        task.finished_at = item["finished_at"].AsString();
        task.mode = item["mode"].AsString();
        task.workspace_root = item["workspace_root"].AsString();
        task.message = item["message"].AsString();
        task.status = item["status"].AsString();
        tasks.push_back(std::move(task));
    }
    return tasks;
}

std::vector<RepairAttemptInfo> ParseRepairAttempts(const JsonValue& value)
{
    std::vector<RepairAttemptInfo> attempts;
    if (!value.IsArray()) {
        return attempts;
    }
    attempts.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        RepairAttemptInfo attempt;
        attempt.attempt = item["attempt"].AsInt(0);
        attempt.category = item["category"].AsString();
        attempt.before_signature = item["before_signature"].AsString();
        attempt.after_signature = item["after_signature"].AsString();
        attempt.outcome = item["outcome"].AsString();
        attempt.checkpoint = item["checkpoint"].AsString();
        attempt.summary = item["summary"].AsString();
        attempt.created_at = item["created_at"].AsString();
        attempts.push_back(std::move(attempt));
    }
    return attempts;
}

CompletionQualityInfo ParseCompletionQuality(const JsonValue& value)
{
    CompletionQualityInfo quality;
    if (!value.IsObject()) {
        return quality;
    }
    quality.status = value["status"].AsString("unknown");
    quality.score = value["score"].AsDouble(0.0);
    quality.reasons = ParseStringArray(value["reasons"]);
    quality.next_actions = ParseStringArray(value["next_actions"]);
    quality.should_continue = value["should_continue"].AsBool(false);
    return quality;
}

AgentResponse ParseAgentResponse(const JsonValue& root, const std::string& workspace_root)
{
    AgentResponse response;
    response.task_id = root["task_id"].AsString();
    response.reply = root["reply"].AsString();
    response.plan = ParseStringArray(root["plan"]);
    response.changes = ParseChanges(root["changes"]);
    response.applied = ParseStringArray(root["applied"]);
    response.checkpoint = root["checkpoint"].AsString();
    response.warnings = ParseStringArray(root["warnings"]);
    response.events = ParseEvents(root["events"]);
    response.validation = ParseCommandRun(root["validation"], &response.has_validation);
    response.validation_profile = ParseValidationRecipe(root["validation_profile"], &response.has_validation_profile);
    response.task_plan = ParseTaskPlan(root["task_plan"], &response.has_task_plan);
    response.context_budget = ParseContextBudget(root["context_budget"], &response.has_context_budget);
    response.model_attempts = ParseModelAttempts(root["model_attempts"]);
    response.assistant_name = root["assistant_name"].AsString("Auralith Prime");
    response.mode = root["mode"].AsString("build");
    response.engine = root["engine"].AsString();
    response.registry_message = root["registry_message"].AsString();
    response.benchmark_message = root["benchmark_message"].AsString();
    response.routing_recommendations = ParseStringArray(root["recommendations"]);
    response.workspace_root = root["workspace_root"].AsString(workspace_root);
    response.workspace_files = ParseWorkspaceFiles(root["workspace_files"]);
    response.context_files = ParseWorkspaceFiles(root["context_files"]);
    response.recent_tasks = ParseTasks(root["recent_tasks"]);
    response.repair_attempts = ParseRepairAttempts(root["repair_attempts"]);
    response.completion_quality = ParseCompletionQuality(root["completion_quality"]);
    return response;
}

ModelCapabilities ParseModelCapabilities(const JsonValue& value)
{
    ModelCapabilities capabilities;
    if (!value.IsObject()) {
        return capabilities;
    }
    capabilities.chat = value["chat"].AsBool(true);
    capabilities.code = value["code"].AsBool(false);
    capabilities.debug = value["debug"].AsBool(false);
    capabilities.refactor = value["refactor"].AsBool(false);
    capabilities.reasoning = value["reasoning"].AsBool(false);
    capabilities.research = value["research"].AsBool(false);
    capabilities.streaming = value["streaming"].AsBool(false);
    capabilities.structured_json = value["structured_json"].AsBool(false);
    capabilities.tools = value["tools"].AsBool(false);
    capabilities.vision = value["vision"].AsBool(false);
    capabilities.audio = value["audio"].AsBool(false);
    capabilities.embeddings = value["embeddings"].AsBool(false);
    capabilities.image = value["image"].AsBool(false);
    capabilities.video = value["video"].AsBool(false);
    capabilities.realtime = value["realtime"].AsBool(false);
    capabilities.judge = value["judge"].AsBool(false);
    capabilities.computer_use = value["computer_use"].AsBool(false);
    return capabilities;
}

ModelInventory ParseModelInventory(const JsonValue& value)
{
    ModelInventory inventory;
    if (!value.IsObject()) {
        return inventory;
    }

    inventory.active_model = value["active_model"].AsString();
    inventory.active_api = value["active_api"].AsString();
    inventory.active_endpoint = value["active_endpoint"].AsString();
    inventory.router_enabled = value["router_enabled"].AsBool(false);
    inventory.fallback_supported = value["fallback_supported"].AsBool(false);
    inventory.message = value["message"].AsString();

    const JsonValue& models = value["models"];
    if (models.IsArray()) {
        inventory.models.reserve(models.array_value.size());
        for (const JsonValue& item : models.array_value) {
            if (!item.IsObject()) {
                continue;
            }
            ModelInfo model;
            model.id = item["id"].AsString();
            model.name = item["name"].AsString();
            model.provider = item["provider"].AsString();
            model.api = item["api"].AsString();
            model.endpoint = item["endpoint"].AsString();
            model.local = item["local"].AsBool(true);
            model.configured = item["configured"].AsBool(false);
            model.available = item["available"].AsBool(false);
            model.ready = item["ready"].AsBool(false);
            model.message = item["message"].AsString();
            model.size = static_cast<long long>(item["size"].AsDouble(0.0));
            model.modified_at = item["modified_at"].AsString();
            model.capabilities = ParseModelCapabilities(item["capabilities"]);
            inventory.models.push_back(std::move(model));
        }
    }

    return inventory;
}

ModelRegistrySnapshot ParseModelRegistry(const JsonValue& value)
{
    ModelRegistrySnapshot registry;
    if (!value.IsObject()) {
        return registry;
    }

    registry.version = value["version"].AsInt(1);
    registry.active_provider_id = value["active_provider_id"].AsString();
    registry.active_model = value["active_model"].AsString();
    registry.router_enabled = value["router_enabled"].AsBool(false);
    registry.fallback_supported = value["fallback_supported"].AsBool(false);
    registry.message = value["message"].AsString();

    const JsonValue& providers = value["providers"];
    if (providers.IsArray()) {
        registry.providers.reserve(providers.array_value.size());
        for (const JsonValue& item : providers.array_value) {
            if (!item.IsObject()) {
                continue;
            }
            ModelRegistryProviderInfo provider;
            provider.id = item["id"].AsString();
            provider.label = item["label"].AsString();
            provider.api = item["api"].AsString();
            provider.endpoint = item["endpoint"].AsString();
            provider.model_name = item["model_name"].AsString();
            provider.model_aliases = ParseStringArray(item["model_aliases"]);
            provider.secret_env = item["secret_env"].AsString();
            provider.local = item["local"].AsBool(true);
            provider.enabled = item["enabled"].AsBool(true);
            provider.configured = item["configured"].AsBool(false);
            provider.capabilities = ParseStringArray(item["capabilities"]);
            provider.roles = ParseStringArray(item["roles"]);
            provider.cost_tier = item["cost_tier"].AsString();
            provider.context_window = item["context_window"].AsInt(0);
            provider.rate_limit_rpm = item["rate_limit_rpm"].AsInt(0);
            provider.input_cost_per_million = item["input_cost_per_million"].AsDouble(0.0);
            provider.output_cost_per_million = item["output_cost_per_million"].AsDouble(0.0);
            provider.health = item["health"].AsString();
            provider.notes = item["notes"].AsString();
            registry.providers.push_back(std::move(provider));
        }
    }

    const JsonValue& roles = value["roles"];
    if (roles.IsArray()) {
        registry.roles.reserve(roles.array_value.size());
        for (const JsonValue& item : roles.array_value) {
            if (!item.IsObject()) {
                continue;
            }
            ModelRegistryRoleInfo role;
            role.id = item["id"].AsString();
            role.label = item["label"].AsString();
            role.description = item["description"].AsString();
            role.primary_model = item["primary_model"].AsString();
            role.fallback_models = ParseStringArray(item["fallback_models"]);
            role.required_capabilities = ParseStringArray(item["required_capabilities"]);
            role.privacy_mode = item["privacy_mode"].AsString();
            role.cost_tier = item["cost_tier"].AsString();
            role.status = item["status"].AsString();
            registry.roles.push_back(std::move(role));
        }
    }

    const JsonValue& presets = value["presets"];
    if (presets.IsArray()) {
        registry.presets.reserve(presets.array_value.size());
        for (const JsonValue& item : presets.array_value) {
            if (!item.IsObject()) {
                continue;
            }
            ModelRoutingPresetInfo preset;
            preset.id = item["id"].AsString();
            preset.label = item["label"].AsString();
            preset.description = item["description"].AsString();
            preset.role_order = ParseStringArray(item["role_order"]);
            preset.privacy_mode = item["privacy_mode"].AsString();
            registry.presets.push_back(std::move(preset));
        }
    }

    return registry;
}

ModelRegistryAuditIssueInfo ParseModelRegistryAuditIssue(const JsonValue& value)
{
    ModelRegistryAuditIssueInfo issue;
    issue.severity = value["severity"].AsString();
    issue.category = value["category"].AsString();
    issue.provider_id = value["provider_id"].AsString();
    issue.role = value["role"].AsString();
    issue.message = value["message"].AsString();
    issue.recommendation = value["recommendation"].AsString();
    return issue;
}

ModelRegistrySetupActionInfo ParseModelRegistrySetupAction(const JsonValue& value)
{
    ModelRegistrySetupActionInfo action;
    action.id = value["id"].AsString();
    action.kind = value["kind"].AsString();
    action.priority = value["priority"].AsString();
    action.title = value["title"].AsString();
    action.detail = value["detail"].AsString();
    action.recommendation = value["recommendation"].AsString();
    action.env_var = value["env_var"].AsString();
    action.role = value["role"].AsString();
    action.provider_ids = ParseStringArray(value["provider_ids"]);
    action.command = value["command"].AsString();
    return action;
}

ModelRegistryRouteCoverageInfo ParseModelRegistryRouteCoverage(const JsonValue& value)
{
    ModelRegistryRouteCoverageInfo route;
    route.role = value["role"].AsString();
    route.label = value["label"].AsString();
    route.status = value["status"].AsString();
    route.primary_model = value["primary_model"].AsString();
    route.primary_provider_id = value["primary_provider_id"].AsString();
    route.primary_configured = value["primary_configured"].AsBool(false);
    route.required_capabilities = ParseStringArray(value["required_capabilities"]);
    route.eligible_provider_count = value["eligible_provider_count"].AsInt(0);
    route.configured_provider_count = value["configured_provider_count"].AsInt(0);
    route.enabled_provider_count = value["enabled_provider_count"].AsInt(0);
    route.fallback_configured_count = value["fallback_configured_count"].AsInt(0);
    route.candidate_provider_ids = ParseStringArray(value["candidate_provider_ids"]);
    route.recommendations = ParseStringArray(value["recommendations"]);
    return route;
}

ModelAdapterHealthInfo ParseModelAdapterHealth(const JsonValue& value)
{
    ModelAdapterHealthInfo health;
    health.provider_id = value["provider_id"].AsString();
    health.provider_label = value["provider_label"].AsString();
    health.api = value["api"].AsString();
    health.endpoint = value["endpoint"].AsString();
    health.model = value["model"].AsString();
    health.local = value["local"].AsBool(true);
    health.enabled = value["enabled"].AsBool(true);
    health.configured = value["configured"].AsBool(false);
    health.status = value["status"].AsString();
    health.error_code = value["error_code"].AsString();
    health.message = value["message"].AsString();
    health.secret_env = value["secret_env"].AsString();
    health.secret_present = value["secret_present"].AsBool(false);
    health.capabilities = ParseStringArray(value["capabilities"]);
    health.roles = ParseStringArray(value["roles"]);
    health.recent_attempts = value["recent_attempts"].AsInt(0);
    health.recent_successes = value["recent_successes"].AsInt(0);
    health.recent_failures = value["recent_failures"].AsInt(0);
    health.recent_skips = value["recent_skips"].AsInt(0);
    health.preflight_skips = value["preflight_skips"].AsInt(0);
    health.cooldown = value["cooldown"].AsBool(false);
    health.latest_error = value["latest_error"].AsString();
    health.latest_at = value["latest_at"].AsString();
    health.recommendation = value["recommendation"].AsString();
    return health;
}

ModelTokenizerDiagnosticInfo ParseModelTokenizerDiagnostic(const JsonValue& value)
{
    ModelTokenizerDiagnosticInfo diagnostic;
    diagnostic.provider_id = value["provider_id"].AsString();
    diagnostic.provider_label = value["provider_label"].AsString();
    diagnostic.api = value["api"].AsString();
    diagnostic.model = value["model"].AsString();
    diagnostic.local = value["local"].AsBool(true);
    diagnostic.enabled = value["enabled"].AsBool(true);
    diagnostic.configured = value["configured"].AsBool(false);
    diagnostic.has_context_window = value.Has("context_window") && !value["context_window"].IsNull();
    diagnostic.context_window = value["context_window"].AsInt(0);
    diagnostic.status = value["status"].AsString("unobserved");
    diagnostic.recent_attempts = value["recent_attempts"].AsInt(0);
    diagnostic.exact_attempts = value["exact_attempts"].AsInt(0);
    diagnostic.profiled_attempts = value["profiled_attempts"].AsInt(0);
    diagnostic.heuristic_attempts = value["heuristic_attempts"].AsInt(0);
    diagnostic.missing_attempts = value["missing_attempts"].AsInt(0);
    diagnostic.estimator_sources = ParseStringArray(value["estimator_sources"]);
    diagnostic.primary_estimator_source = value["primary_estimator_source"].AsString();
    diagnostic.has_average_context_utilization = value.Has("average_context_utilization") && !value["average_context_utilization"].IsNull();
    diagnostic.average_context_utilization = value["average_context_utilization"].AsDouble(0.0);
    diagnostic.calibrated_attempts = value["calibrated_attempts"].AsInt(0);
    diagnostic.has_average_input_token_error = value.Has("average_input_token_error") && !value["average_input_token_error"].IsNull();
    diagnostic.average_input_token_error = value["average_input_token_error"].AsDouble(0.0);
    diagnostic.has_worst_input_token_error = value.Has("worst_input_token_error") && !value["worst_input_token_error"].IsNull();
    diagnostic.worst_input_token_error = value["worst_input_token_error"].AsDouble(0.0);
    diagnostic.has_average_output_token_error = value.Has("average_output_token_error") && !value["average_output_token_error"].IsNull();
    diagnostic.average_output_token_error = value["average_output_token_error"].AsDouble(0.0);
    diagnostic.has_worst_output_token_error = value.Has("worst_output_token_error") && !value["worst_output_token_error"].IsNull();
    diagnostic.worst_output_token_error = value["worst_output_token_error"].AsDouble(0.0);
    diagnostic.reported_token_sources = ParseStringArray(value["reported_token_sources"]);
    diagnostic.calibration_status = value["calibration_status"].AsString("insufficient");
    diagnostic.calibration_recommendation = value["calibration_recommendation"].AsString();
    diagnostic.recommendation = value["recommendation"].AsString();
    return diagnostic;
}

ModelRegistryAuditInfo ParseModelRegistryAudit(const JsonValue& value)
{
    ModelRegistryAuditInfo audit;
    audit.generated_at = value["generated_at"].AsString();
    audit.readiness_score = value["readiness_score"].AsInt(0);
    audit.status = value["status"].AsString();
    audit.provider_count = value["provider_count"].AsInt(0);
    audit.enabled_provider_count = value["enabled_provider_count"].AsInt(0);
    audit.configured_provider_count = value["configured_provider_count"].AsInt(0);
    audit.disabled_provider_count = value["disabled_provider_count"].AsInt(0);
    audit.local_provider_count = value["local_provider_count"].AsInt(0);
    audit.cloud_provider_count = value["cloud_provider_count"].AsInt(0);
    audit.role_count = value["role_count"].AsInt(0);
    audit.warnings = ParseStringArray(value["warnings"]);
    audit.recommendations = ParseStringArray(value["recommendations"]);

    const JsonValue& route_coverages = value["route_coverages"];
    if (route_coverages.IsArray()) {
        audit.route_coverages.reserve(route_coverages.array_value.size());
        for (const JsonValue& item : route_coverages.array_value) {
            if (item.IsObject()) {
                audit.route_coverages.push_back(ParseModelRegistryRouteCoverage(item));
            }
        }
    }

    const JsonValue& issues = value["issues"];
    if (issues.IsArray()) {
        audit.issues.reserve(issues.array_value.size());
        for (const JsonValue& item : issues.array_value) {
            if (item.IsObject()) {
                audit.issues.push_back(ParseModelRegistryAuditIssue(item));
            }
        }
    }

    const JsonValue& setup_actions = value["setup_actions"];
    if (setup_actions.IsArray()) {
        audit.setup_actions.reserve(setup_actions.array_value.size());
        for (const JsonValue& item : setup_actions.array_value) {
            if (item.IsObject()) {
                audit.setup_actions.push_back(ParseModelRegistrySetupAction(item));
            }
        }
    }

    const JsonValue& adapter_health = value["adapter_health"];
    if (adapter_health.IsArray()) {
        audit.adapter_health.reserve(adapter_health.array_value.size());
        for (const JsonValue& item : adapter_health.array_value) {
            if (item.IsObject()) {
                audit.adapter_health.push_back(ParseModelAdapterHealth(item));
            }
        }
    }

    const JsonValue& tokenizer_diagnostics = value["tokenizer_diagnostics"];
    if (tokenizer_diagnostics.IsArray()) {
        audit.tokenizer_diagnostics.reserve(tokenizer_diagnostics.array_value.size());
        for (const JsonValue& item : tokenizer_diagnostics.array_value) {
            if (item.IsObject()) {
                audit.tokenizer_diagnostics.push_back(ParseModelTokenizerDiagnostic(item));
            }
        }
    }

    return audit;
}

ModelRegistryRoleDiffInfo ParseModelRegistryRoleDiff(const JsonValue& value)
{
    ModelRegistryRoleDiffInfo diff;
    if (!value.IsObject()) {
        return diff;
    }
    diff.role = value["role"].AsString();
    diff.action = value["action"].AsString("keep");
    diff.current_primary_model = value["current_primary_model"].AsString();
    diff.proposed_primary_model = value["proposed_primary_model"].AsString();
    diff.current_fallback_models = ParseStringArray(value["current_fallback_models"]);
    diff.proposed_fallback_models = ParseStringArray(value["proposed_fallback_models"]);
    diff.winner_provider_id = value["winner_provider_id"].AsString();
    diff.winner_provider_label = value["winner_provider_label"].AsString();
    diff.winner_model = value["winner_model"].AsString();
    diff.winner_score = value["winner_score"].AsDouble(0.0);
    diff.health_penalty = value["health_penalty"].AsDouble(0.0);
    diff.health_cooldown = value["health_cooldown"].AsBool(false);
    diff.health_recommendation = value["health_recommendation"].AsString();
    diff.reasons = ParseStringArray(value["reasons"]);
    return diff;
}

std::vector<ModelRegistryRoleDiffInfo> ParseModelRegistryRoleDiffs(const JsonValue& value)
{
    std::vector<ModelRegistryRoleDiffInfo> diffs;
    if (!value.IsArray()) {
        return diffs;
    }
    diffs.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (item.IsObject()) {
            diffs.push_back(ParseModelRegistryRoleDiff(item));
        }
    }
    return diffs;
}

ModelRegistryBenchmarkPreviewInfo ParseModelRegistryBenchmarkPreview(const JsonValue& value)
{
    ModelRegistryBenchmarkPreviewInfo preview;
    if (!value.IsObject()) {
        return preview;
    }
    preview.applicable = value["applicable"].AsBool(false);
    preview.message = value["message"].AsString();
    preview.role_diffs = ParseModelRegistryRoleDiffs(value["role_diffs"]);
    preview.warnings = ParseStringArray(value["warnings"]);
    preview.recommendations = ParseStringArray(value["recommendations"]);
    return preview;
}

ModelRegistryCheckpointInfo ParseModelRegistryCheckpointInfo(const JsonValue& value)
{
    ModelRegistryCheckpointInfo checkpoint;
    if (!value.IsObject()) {
        return checkpoint;
    }
    checkpoint.id = value["id"].AsString();
    checkpoint.created_at = value["created_at"].AsString();
    checkpoint.reason = value["reason"].AsString();
    checkpoint.provider_count = value["provider_count"].AsInt(0);
    checkpoint.role_count = value["role_count"].AsInt(0);
    checkpoint.router_enabled = value["router_enabled"].AsBool(false);
    checkpoint.active_provider_id = value["active_provider_id"].AsString();
    checkpoint.message = value["message"].AsString();
    checkpoint.restore_provider_add_count = value["restore_provider_add_count"].AsInt(0);
    checkpoint.restore_provider_remove_count = value["restore_provider_remove_count"].AsInt(0);
    checkpoint.restore_provider_change_count = value["restore_provider_change_count"].AsInt(0);
    checkpoint.restore_role_add_count = value["restore_role_add_count"].AsInt(0);
    checkpoint.restore_role_remove_count = value["restore_role_remove_count"].AsInt(0);
    checkpoint.restore_role_change_count = value["restore_role_change_count"].AsInt(0);
    checkpoint.restore_settings_change_count = value["restore_settings_change_count"].AsInt(0);
    checkpoint.restore_total_change_count = value["restore_total_change_count"].AsInt(0);
    checkpoint.restore_summary = value["restore_summary"].AsString();
    return checkpoint;
}

ModelRegistryCheckpointList ParseModelRegistryCheckpointList(const JsonValue& value)
{
    ModelRegistryCheckpointList list;
    const JsonValue& checkpoints = value["checkpoints"];
    if (!checkpoints.IsArray()) {
        return list;
    }
    list.checkpoints.reserve(checkpoints.array_value.size());
    for (const JsonValue& item : checkpoints.array_value) {
        if (item.IsObject()) {
            list.checkpoints.push_back(ParseModelRegistryCheckpointInfo(item));
        }
    }
    return list;
}

ModelRegistryCheckpointEntityDiffInfo ParseModelRegistryCheckpointEntityDiff(const JsonValue& value)
{
    ModelRegistryCheckpointEntityDiffInfo diff;
    if (!value.IsObject()) {
        return diff;
    }
    diff.id = value["id"].AsString();
    diff.label = value["label"].AsString();
    diff.action = value["action"].AsString("unchanged");
    diff.current_summary = value["current_summary"].AsString();
    diff.checkpoint_summary = value["checkpoint_summary"].AsString();
    return diff;
}

std::vector<ModelRegistryCheckpointEntityDiffInfo> ParseModelRegistryCheckpointEntityDiffs(const JsonValue& value)
{
    std::vector<ModelRegistryCheckpointEntityDiffInfo> diffs;
    if (!value.IsArray()) {
        return diffs;
    }
    diffs.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (item.IsObject()) {
            diffs.push_back(ParseModelRegistryCheckpointEntityDiff(item));
        }
    }
    return diffs;
}

ModelRegistryCheckpointSettingDiffInfo ParseModelRegistryCheckpointSettingDiff(const JsonValue& value)
{
    ModelRegistryCheckpointSettingDiffInfo diff;
    if (!value.IsObject()) {
        return diff;
    }
    diff.key = value["key"].AsString();
    diff.current_value = value["current_value"].AsString();
    diff.checkpoint_value = value["checkpoint_value"].AsString();
    return diff;
}

std::vector<ModelRegistryCheckpointSettingDiffInfo> ParseModelRegistryCheckpointSettingDiffs(const JsonValue& value)
{
    std::vector<ModelRegistryCheckpointSettingDiffInfo> diffs;
    if (!value.IsArray()) {
        return diffs;
    }
    diffs.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (item.IsObject()) {
            diffs.push_back(ParseModelRegistryCheckpointSettingDiff(item));
        }
    }
    return diffs;
}

ModelRegistryCheckpointDiffInfo ParseModelRegistryCheckpointDiff(const JsonValue& value)
{
    ModelRegistryCheckpointDiffInfo diff;
    if (!value.IsObject()) {
        return diff;
    }
    diff.checkpoint = ParseModelRegistryCheckpointInfo(value["checkpoint"]);
    diff.provider_diffs = ParseModelRegistryCheckpointEntityDiffs(value["provider_diffs"]);
    diff.role_diffs = ParseModelRegistryCheckpointEntityDiffs(value["role_diffs"]);
    diff.setting_diffs = ParseModelRegistryCheckpointSettingDiffs(value["setting_diffs"]);
    diff.recommendations = ParseStringArray(value["recommendations"]);
    return diff;
}

ModelDiskInfo ParseModelDiskInfo(const JsonValue& value)
{
    ModelDiskInfo disk;
    if (!value.IsObject()) {
        return disk;
    }
    disk.drive_root = value["drive_root"].AsString();
    disk.project_root = value["project_root"].AsString();
    disk.model_store_path = value["model_store_path"].AsString();
    disk.total_bytes = static_cast<long long>(value["total_bytes"].AsDouble(0.0));
    disk.used_bytes = static_cast<long long>(value["used_bytes"].AsDouble(0.0));
    disk.free_bytes = static_cast<long long>(value["free_bytes"].AsDouble(0.0));
    disk.model_store_bytes = static_cast<long long>(value["model_store_bytes"].AsDouble(0.0));
    disk.free_percent = value["free_percent"].AsDouble(0.0);
    disk.low_space = value["low_space"].AsBool(false);
    disk.minimum_free_bytes = static_cast<long long>(value["minimum_free_bytes"].AsDouble(0.0));
    return disk;
}

ManagedModelInfo ParseManagedModelInfo(const JsonValue& value)
{
    ManagedModelInfo model;
    if (!value.IsObject()) {
        return model;
    }
    model.provider_id = value["provider_id"].AsString();
    model.label = value["label"].AsString();
    model.api = value["api"].AsString();
    model.endpoint = value["endpoint"].AsString();
    model.name = value["name"].AsString();
    model.local = value["local"].AsBool(true);
    model.enabled = value["enabled"].AsBool(true);
    model.installed = value["installed"].AsBool(false);
    model.configured = value["configured"].AsBool(false);
    model.active = value["active"].AsBool(false);
    model.pullable = value["pullable"].AsBool(false);
    model.health = value["health"].AsString();
    model.roles = ParseStringArray(value["roles"]);
    model.capabilities = ParseStringArray(value["capabilities"]);
    model.has_size_bytes = value.Has("size_bytes") && !value["size_bytes"].IsNull();
    model.size_bytes = static_cast<long long>(value["size_bytes"].AsDouble(0.0));
    model.has_estimated_pull_bytes = value.Has("estimated_pull_bytes") && !value["estimated_pull_bytes"].IsNull();
    model.estimated_pull_bytes = static_cast<long long>(value["estimated_pull_bytes"].AsDouble(0.0));
    model.modified_at = value["modified_at"].AsString();
    model.notes = value["notes"].AsString();
    return model;
}

ModelOperationInfo ParseModelOperationInfo(const JsonValue& value)
{
    ModelOperationInfo operation;
    if (!value.IsObject()) {
        return operation;
    }
    operation.id = value["id"].AsString();
    operation.model_name = value["model_name"].AsString();
    operation.action = value["action"].AsString();
    operation.status = value["status"].AsString();
    operation.message = value["message"].AsString();
    operation.has_pid = value.Has("pid") && !value["pid"].IsNull();
    operation.pid = value["pid"].AsInt(0);
    operation.started_at = value["started_at"].AsString();
    operation.finished_at = value["finished_at"].AsString();
    operation.stdout_log = value["stdout_log"].AsString();
    operation.stderr_log = value["stderr_log"].AsString();
    operation.minimum_free_bytes = static_cast<long long>(value["minimum_free_bytes"].AsDouble(0.0));
    operation.has_estimated_pull_bytes = value.Has("estimated_pull_bytes") && !value["estimated_pull_bytes"].IsNull();
    operation.estimated_pull_bytes = static_cast<long long>(value["estimated_pull_bytes"].AsDouble(0.0));
    operation.has_free_bytes_before = value.Has("free_bytes_before") && !value["free_bytes_before"].IsNull();
    operation.free_bytes_before = static_cast<long long>(value["free_bytes_before"].AsDouble(0.0));
    return operation;
}

ModelPullLogSummaryInfo ParseModelPullLogSummaryInfo(const JsonValue& value)
{
    ModelPullLogSummaryInfo summary;
    if (!value.IsObject()) {
        return summary;
    }
    summary.source = value["source"].AsString();
    summary.total = value["total"].AsInt(0);
    summary.pulled = value["pulled"].AsInt(0);
    summary.skipped = value["skipped"].AsInt(0);
    summary.failed = value["failed"].AsInt(0);
    summary.latest_at = value["latest_at"].AsString();
    return summary;
}

ModelManagerSnapshot ParseModelManagerSnapshot(const JsonValue& value)
{
    ModelManagerSnapshot snapshot;
    if (!value.IsObject()) {
        return snapshot;
    }
    snapshot.ok = value["ok"].AsBool(false);
    snapshot.message = value["message"].AsString();
    snapshot.disk = ParseModelDiskInfo(value["disk"]);
    snapshot.active_model = value["active_model"].AsString();
    snapshot.active_provider_id = value["active_provider_id"].AsString();
    snapshot.providers_total = value["providers_total"].AsInt(0);
    snapshot.local_total = value["local_total"].AsInt(0);
    snapshot.installed_total = value["installed_total"].AsInt(0);
    snapshot.pullable_total = value["pullable_total"].AsInt(0);
    snapshot.cloud_total = value["cloud_total"].AsInt(0);

    const JsonValue& models = value["models"];
    if (models.IsArray()) {
        snapshot.models.reserve(models.array_value.size());
        for (const JsonValue& item : models.array_value) {
            snapshot.models.push_back(ParseManagedModelInfo(item));
        }
    }

    const JsonValue& operations = value["operations"];
    if (operations.IsArray()) {
        snapshot.operations.reserve(operations.array_value.size());
        for (const JsonValue& item : operations.array_value) {
            snapshot.operations.push_back(ParseModelOperationInfo(item));
        }
    }

    const JsonValue& pull_logs = value["pull_logs"];
    if (pull_logs.IsArray()) {
        snapshot.pull_logs.reserve(pull_logs.array_value.size());
        for (const JsonValue& item : pull_logs.array_value) {
            snapshot.pull_logs.push_back(ParseModelPullLogSummaryInfo(item));
        }
    }
    return snapshot;
}

ModelBenchmarkSuiteInfo ParseModelBenchmarkSuiteInfo(const JsonValue& value)
{
    ModelBenchmarkSuiteInfo suite;
    if (!value.IsObject()) {
        return suite;
    }
    suite.id = value["id"].AsString();
    suite.label = value["label"].AsString();
    suite.description = value["description"].AsString();
    return suite;
}

ModelBenchmarkResultInfo ParseModelBenchmarkResultInfo(const JsonValue& value)
{
    ModelBenchmarkResultInfo result;
    if (!value.IsObject()) {
        return result;
    }
    result.id = value["id"].AsString();
    result.created_at = value["created_at"].AsString();
    result.provider_id = value["provider_id"].AsString();
    result.provider_label = value["provider_label"].AsString();
    result.api = value["api"].AsString();
    result.endpoint = value["endpoint"].AsString();
    result.model_name = value["model_name"].AsString();
    result.suite_id = value["suite_id"].AsString();
    result.suite_label = value["suite_label"].AsString();
    result.status = value["status"].AsString();
    result.score = value["score"].AsDouble(0.0);
    result.has_latency_ms = value.Has("latency_ms") && !value["latency_ms"].IsNull();
    result.latency_ms = value["latency_ms"].AsInt(0);
    result.error = value["error"].AsString();
    result.answer_excerpt = value["answer_excerpt"].AsString();
    result.expected = value["expected"].AsString();
    return result;
}

ModelBenchmarkProviderScoreInfo ParseModelBenchmarkProviderScoreInfo(const JsonValue& value)
{
    ModelBenchmarkProviderScoreInfo score;
    if (!value.IsObject()) {
        return score;
    }
    score.provider_id = value["provider_id"].AsString();
    score.provider_label = value["provider_label"].AsString();
    score.api = value["api"].AsString();
    score.model_name = value["model_name"].AsString();
    score.local = value["local"].AsBool(true);
    score.enabled = value["enabled"].AsBool(true);
    score.configured = value["configured"].AsBool(false);
    score.overall_score = value["overall_score"].AsDouble(0.0);
    score.has_chat_score = value.Has("chat_score") && !value["chat_score"].IsNull();
    score.chat_score = value["chat_score"].AsDouble(0.0);
    score.has_code_score = value.Has("code_score") && !value["code_score"].IsNull();
    score.code_score = value["code_score"].AsDouble(0.0);
    score.has_reasoning_score = value.Has("reasoning_score") && !value["reasoning_score"].IsNull();
    score.reasoning_score = value["reasoning_score"].AsDouble(0.0);
    score.has_avg_latency_ms = value.Has("avg_latency_ms") && !value["avg_latency_ms"].IsNull();
    score.avg_latency_ms = value["avg_latency_ms"].AsInt(0);
    score.run_count = value["run_count"].AsInt(0);
    score.latest_at = value["latest_at"].AsString();
    score.recommendation = value["recommendation"].AsString();
    return score;
}

ModelBenchmarkSuiteSummaryInfo ParseModelBenchmarkSuiteSummaryInfo(const JsonValue& value)
{
    ModelBenchmarkSuiteSummaryInfo summary;
    if (!value.IsObject()) {
        return summary;
    }
    summary.suite_id = value["suite_id"].AsString();
    summary.suite_label = value["suite_label"].AsString();
    summary.best_provider_id = value["best_provider_id"].AsString();
    summary.best_provider_label = value["best_provider_label"].AsString();
    summary.best_model_name = value["best_model_name"].AsString();
    summary.best_score = value["best_score"].AsDouble(0.0);
    summary.has_best_latency_ms = value.Has("best_latency_ms") && !value["best_latency_ms"].IsNull();
    summary.best_latency_ms = value["best_latency_ms"].AsInt(0);
    summary.run_count = value["run_count"].AsInt(0);
    return summary;
}

ModelBenchmarkJobInfo ParseModelBenchmarkJobInfo(const JsonValue& value)
{
    ModelBenchmarkJobInfo job;
    if (!value.IsObject()) {
        return job;
    }
    job.id = value["id"].AsString();
    job.status = value["status"].AsString();
    job.message = value["message"].AsString();
    job.created_at = value["created_at"].AsString();
    job.started_at = value["started_at"].AsString();
    job.finished_at = value["finished_at"].AsString();
    job.suite_ids = ParseStringArray(value["suite_ids"]);
    job.provider_ids = ParseStringArray(value["provider_ids"]);
    job.max_models = value["max_models"].AsInt(0);
    job.local_only = value["local_only"].AsBool(true);
    job.timeout_seconds = value["timeout_seconds"].AsDouble(45.0);
    job.total_runs = value["total_runs"].AsInt(0);
    job.completed_runs = value["completed_runs"].AsInt(0);
    job.failed_runs = value["failed_runs"].AsInt(0);
    job.current_provider_id = value["current_provider_id"].AsString();
    job.current_model_name = value["current_model_name"].AsString();
    job.current_suite_id = value["current_suite_id"].AsString();
    job.error = value["error"].AsString();
    return job;
}

ModelBenchmarkSnapshot ParseModelBenchmarkSnapshot(const JsonValue& value)
{
    ModelBenchmarkSnapshot snapshot;
    if (!value.IsObject()) {
        return snapshot;
    }
    snapshot.ok = value["ok"].AsBool(false);
    snapshot.message = value["message"].AsString();
    snapshot.results_total = value["results_total"].AsInt(0);
    snapshot.latest_at = value["latest_at"].AsString();
    snapshot.recommendations = ParseStringArray(value["recommendations"]);

    const JsonValue& suites = value["suites"];
    if (suites.IsArray()) {
        snapshot.suites.reserve(suites.array_value.size());
        for (const JsonValue& item : suites.array_value) {
            snapshot.suites.push_back(ParseModelBenchmarkSuiteInfo(item));
        }
    }

    const JsonValue& provider_scores = value["provider_scores"];
    if (provider_scores.IsArray()) {
        snapshot.provider_scores.reserve(provider_scores.array_value.size());
        for (const JsonValue& item : provider_scores.array_value) {
            snapshot.provider_scores.push_back(ParseModelBenchmarkProviderScoreInfo(item));
        }
    }

    const JsonValue& suite_summaries = value["suite_summaries"];
    if (suite_summaries.IsArray()) {
        snapshot.suite_summaries.reserve(suite_summaries.array_value.size());
        for (const JsonValue& item : suite_summaries.array_value) {
            snapshot.suite_summaries.push_back(ParseModelBenchmarkSuiteSummaryInfo(item));
        }
    }

    const JsonValue& recent_results = value["recent_results"];
    if (recent_results.IsArray()) {
        snapshot.recent_results.reserve(recent_results.array_value.size());
        for (const JsonValue& item : recent_results.array_value) {
            snapshot.recent_results.push_back(ParseModelBenchmarkResultInfo(item));
        }
    }

    const JsonValue& jobs = value["jobs"];
    if (jobs.IsArray()) {
        snapshot.jobs.reserve(jobs.array_value.size());
        for (const JsonValue& item : jobs.array_value) {
            snapshot.jobs.push_back(ParseModelBenchmarkJobInfo(item));
        }
    }
    return snapshot;
}

MediaJobSummary ParseMediaJob(const JsonValue& value)
{
    MediaJobSummary job;
    job.id = value["id"].AsString();
    job.created_at = value["created_at"].AsString();
    job.kind = value["kind"].AsString();
    job.status = value["status"].AsString();
    job.prompt = value["prompt"].AsString();
    job.feedback = value["feedback"].AsString();
    job.previous_job_id = value["previous_job_id"].AsString();
    job.theme_color = value["theme_color"].AsString();
    job.palette = ParseStringArray(value["palette"]);
    job.aspect_ratio = value["aspect_ratio"].AsString();
    job.style = value["style"].AsString();
    job.job_dir = value["job_dir"].AsString();
    job.plan = ParseStringArray(value["plan"]);
    job.warnings = ParseStringArray(value["warnings"]);
    job.next_actions = ParseStringArray(value["next_actions"]);

    std::ostringstream message;
    message << "Creative Studio job ready";
    if (!job.id.empty()) {
        message << ": " << job.id;
    }
    if (!job.theme_color.empty()) {
        message << "\nTheme color: " << job.theme_color;
    }
    if (!job.job_dir.empty()) {
        message << "\nProject folder: " << job.job_dir;
    }

    if (!job.plan.empty()) {
        message << "\n\nPlan:";
        for (const std::string& item : job.plan) {
            message << "\n- " << item;
        }
    }

    const JsonValue& assets = value["assets"];
    if (assets.IsArray() && !assets.array_value.empty()) {
        message << "\n\nAssets:";
        for (const JsonValue& item : assets.array_value) {
            if (!item.IsObject()) {
                continue;
            }
            const std::string path = item["path"].AsString();
            const std::string format = item["format"].AsString();
            const std::string role = item["role"].AsString();
            MediaAssetInfo asset;
            asset.path = path;
            asset.kind = item["kind"].AsString();
            asset.format = format;
            asset.role = role;
            asset.mime_type = item["mime_type"].AsString();
            asset.editable = item["editable"].AsBool(false);
            asset.derived_from = item["derived_from"].AsString();
            job.assets.push_back(std::move(asset));
            message << "\n- " << role << " (" << format << "): " << path;
        }
    }

    if (!job.warnings.empty()) {
        message << "\n\nWarnings:";
        for (const std::string& warning : job.warnings) {
            message << "\n- " << warning;
        }
    }

    job.message = message.str();
    return job;
}

std::vector<MediaJobSummary> ParseMediaJobs(const JsonValue& value)
{
    std::vector<MediaJobSummary> jobs;
    if (!value.IsArray()) {
        return jobs;
    }
    jobs.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (item.IsObject()) {
            jobs.push_back(ParseMediaJob(item));
        }
    }
    return jobs;
}

HealthStatus ParseHealth(const JsonValue& value)
{
    HealthStatus health;
    health.ok = value["ok"].AsBool(false);
    health.ready = value["ready"].AsBool(false);
    health.status = value["status"].AsString();
    health.app = value["app"].AsString();
    health.version = value["version"].AsString();
    health.engine = value["engine"].AsString();
    health.engine_ready = value["engine_ready"].AsBool(false);
    health.engine_message = value["engine_message"].AsString();
    health.model_name = value["model_name"].AsString();
    health.model_api = value["model_api"].AsString();
    health.model_endpoint = value["model_endpoint"].AsString();
    health.model_ready = value["model_ready"].AsBool(false);
    health.model_message = value["model_message"].AsString();
    health.project_root = value["project_root"].AsString();
    health.workspace_root = value["workspace_root"].AsString();
    health.database_path = value["database_path"].AsString();
    health.env_exists = value["env_exists"].AsBool(false);
    health.router_execution_enabled = value["router_execution_enabled"].AsBool(false);
    health.router_enabled = value["router_enabled"].AsBool(false);
    health.fallback_supported = value["fallback_supported"].AsBool(false);
    health.provider_count = value["provider_count"].AsInt(0);
    health.configured_provider_count = value["configured_provider_count"].AsInt(0);
    health.enabled_provider_count = value["enabled_provider_count"].AsInt(0);
    health.role_count = value["role_count"].AsInt(0);
    health.recommendations = ParseStringArray(value["recommendations"]);
    return health;
}

AppConfig ParseConfig(const JsonValue& value)
{
    AppConfig config;
    config.assistant_name = value["assistant_name"].AsString("Auralith Prime");
    config.assistant_mission = value["assistant_mission"].AsString();
    config.default_mode = value["default_mode"].AsString("build");
    config.default_workspace = value["default_workspace"].AsString();
    config.engine = value["engine"].AsString();
    config.engine_ready = value["engine_ready"].AsBool(false);
    config.engine_message = value["engine_message"].AsString();
    config.model_name = value["model_name"].AsString();
    config.model_endpoint = value["model_endpoint"].AsString();
    config.model_api = value["model_api"].AsString("ollama");
    config.model_ready = value["model_ready"].AsBool(false);
    config.model_message = value["model_message"].AsString();
    config.database_path = value["database_path"].AsString();
    config.command_allowlist = value["command_allowlist"].AsString();
    config.command_timeout_seconds = value["command_timeout_seconds"].AsInt(120);
    config.auto_run_validation = value["auto_run_validation"].AsBool(false);
    config.router_execution_enabled = value["router_execution_enabled"].AsBool(false);
    config.shared_workspace_mode = value["shared_workspace_mode"].AsBool(false);
    config.feedback_capture_excerpts = value["feedback_capture_excerpts"].AsBool(true);
    config.feedback_redaction_enabled = value["feedback_redaction_enabled"].AsBool(true);
    config.feedback_max_excerpt_chars = value["feedback_max_excerpt_chars"].AsInt(320);
    config.feedback_hash_content = value["feedback_hash_content"].AsBool(true);
    config.env_exists = value["env_exists"].AsBool(false);

    const JsonValue& modes = value["modes"];
    if (modes.IsArray()) {
        for (const JsonValue& mode_value : modes.array_value) {
            if (!mode_value.IsObject()) {
                continue;
            }
            ModeOption mode;
            mode.id = mode_value["id"].AsString();
            mode.label = mode_value["label"].AsString();
            mode.description = mode_value["description"].AsString();
            config.modes.push_back(std::move(mode));
        }
    }

    if (config.modes.empty()) {
        config.modes = {
            {"build", "Build", "Create a first working slice."},
            {"develop", "Develop", "Extend the current workspace."},
            {"review", "Review", "Inspect and suggest next moves."},
            {"chat", "Chat", "Keep the exchange conversational."}
        };
    }

    return config;
}

std::string BuildConfigBody(const AppConfig& config)
{
    std::ostringstream body;
    body << "{";
    body << "\"assistant_name\":" << JsonString(config.assistant_name) << ",";
    body << "\"assistant_mission\":" << JsonString(config.assistant_mission.empty()
        ? "Your personal coding AI for planning, building, reviewing, and shipping work inside this workspace."
        : config.assistant_mission) << ",";
    body << "\"default_mode\":" << JsonString(config.default_mode.empty() ? "build" : config.default_mode) << ",";
    body << "\"default_workspace\":" << JsonString(config.default_workspace.empty() ? "workspace" : config.default_workspace) << ",";
    body << "\"model_api\":" << JsonString(config.model_api.empty() ? "ollama" : config.model_api) << ",";
    body << "\"model_endpoint\":" << JsonString(config.model_endpoint.empty() ? "http://127.0.0.1:11434" : config.model_endpoint) << ",";
    body << "\"model_name\":" << JsonString(config.model_name.empty() ? "qwen2.5-coder:7b" : config.model_name) << ",";
    body << "\"command_allowlist\":" << JsonString(config.command_allowlist.empty()
        ? "python,py,node,npm,npx,pnpm,yarn,bun,pytest,uvicorn,tsc,vite,cargo,rustc,go,dotnet,cmake,ctest,msbuild,ninja,make,gradle,gradlew,mvn,mvnw,javac,java,flutter,swift,powershell,pwsh,ruff,mypy,sqlfluff"
        : config.command_allowlist) << ",";
    body << "\"command_timeout_seconds\":" << std::max(5, std::min(3600, config.command_timeout_seconds)) << ",";
    body << "\"auto_run_validation\":" << JsonBool(config.auto_run_validation) << ",";
    body << "\"shared_workspace_mode\":" << JsonBool(config.shared_workspace_mode) << ",";
    body << "\"feedback_capture_excerpts\":" << JsonBool(config.feedback_capture_excerpts) << ",";
    body << "\"feedback_redaction_enabled\":" << JsonBool(config.feedback_redaction_enabled) << ",";
    body << "\"feedback_max_excerpt_chars\":" << std::max(0, std::min(2000, config.feedback_max_excerpt_chars)) << ",";
    body << "\"feedback_hash_content\":" << JsonBool(config.feedback_hash_content);
    body << "}";
    return body.str();
}

std::string BuildAgentRequestBody(
    const std::string& message,
    const std::vector<ChatMessage>& history,
    const std::string& workspace_root,
    const std::string& mode,
    bool apply_changes,
    bool run_validation,
    int max_repair_attempts,
    int max_files,
    const std::string& validation_command_override,
    const std::string& validation_label_override,
    const std::string& validation_notes_override)
{
    std::ostringstream body;
    body << "{";
    body << "\"message\":" << JsonString(message) << ",";
    body << "\"history\":[";
    const size_t start = history.size() > 8 ? history.size() - 8 : 0;
    bool first = true;
    for (size_t i = start; i < history.size(); ++i) {
        if (Trim(history[i].content).empty()) {
            continue;
        }
        if (!first) {
            body << ",";
        }
        first = false;
        body << "{";
        body << "\"role\":" << JsonString(history[i].role.empty() ? "user" : history[i].role) << ",";
        body << "\"content\":" << JsonString(history[i].content);
        body << "}";
    }
    body << "],";
    body << "\"workspace_root\":" << JsonString(workspace_root) << ",";
    body << "\"mode\":" << JsonString(mode.empty() ? "build" : mode) << ",";
    body << "\"apply_changes\":" << JsonBool(apply_changes) << ",";
    body << "\"run_validation\":" << JsonBool(run_validation) << ",";
    body << "\"max_repair_attempts\":" << std::max(0, std::min(5, max_repair_attempts)) << ",";
    body << "\"validation_command_override\":" << JsonString(validation_command_override) << ",";
    body << "\"validation_label_override\":" << JsonString(validation_label_override) << ",";
    body << "\"validation_notes_override\":" << JsonString(validation_notes_override) << ",";
    body << "\"max_files\":" << std::max(1, std::min(300, max_files));
    body << "}";
    return body.str();
}

struct SseFrame {
    std::string event = "message";
    std::string data;
};

std::vector<SseFrame> PopSseFrames(std::string& buffer)
{
    std::vector<SseFrame> frames;
    for (;;) {
        const size_t lf = buffer.find("\n\n");
        const size_t crlf = buffer.find("\r\n\r\n");
        size_t pos = std::string::npos;
        size_t delimiter = 0;
        if (lf != std::string::npos && (crlf == std::string::npos || lf < crlf)) {
            pos = lf;
            delimiter = 2;
        } else if (crlf != std::string::npos) {
            pos = crlf;
            delimiter = 4;
        }
        if (pos == std::string::npos) {
            break;
        }

        std::string raw = buffer.substr(0, pos);
        buffer.erase(0, pos + delimiter);
        std::istringstream lines(raw);
        std::string line;
        SseFrame frame;
        while (std::getline(lines, line)) {
            if (!line.empty() && line.back() == '\r') {
                line.pop_back();
            }
            if (line.rfind("event:", 0) == 0) {
                frame.event = Trim(line.substr(6));
            } else if (line.rfind("data:", 0) == 0) {
                if (!frame.data.empty()) {
                    frame.data += "\n";
                }
                frame.data += Trim(line.substr(5));
            }
        }
        if (!frame.data.empty()) {
            frames.push_back(std::move(frame));
        }
    }
    return frames;
}

std::string StreamStatusMessage(const JsonValue& payload)
{
    const std::string message = payload["message"].AsString();
    if (!message.empty()) {
        return message;
    }
    const std::string stage = payload["stage"].AsString();
    return stage.empty() ? "" : ("Aegis stream: " + stage + ".");
}

std::string BuildChangesBody(const std::string& workspace_root, const std::vector<FileChange>& changes)
{
    std::ostringstream body;
    body << "{";
    body << "\"workspace_root\":" << JsonString(workspace_root) << ",";
    body << "\"changes\":[";
    for (size_t i = 0; i < changes.size(); ++i) {
        const FileChange& change = changes[i];
        if (i > 0) {
            body << ",";
        }
        body << "{";
        body << "\"action\":" << JsonString(change.action) << ",";
        body << "\"path\":" << JsonString(change.path) << ",";
        body << "\"content\":";
        if (change.has_content) {
            body << JsonString(change.content);
        } else {
            body << "null";
        }
        body << ",";
        body << "\"summary\":" << JsonString(change.summary);
        body << "}";
    }
    body << "]}";
    return body.str();
}

std::string BuildProjectScaffoldBody(
    const std::string& target_path,
    const std::string& preset_id,
    const std::string& project_name,
    const std::string& install_command,
    const std::string& validation_command,
    bool overwrite,
    bool include_gitignore,
    const std::string& prompt,
    bool run_install,
    bool run_validation,
    int max_repair_attempts)
{
    std::ostringstream body;
    body << "{";
    body << "\"target_path\":" << JsonString(target_path) << ",";
    body << "\"preset_id\":" << JsonString(preset_id.empty() ? "nextjs-ts-tailwind" : preset_id) << ",";
    body << "\"project_name\":" << JsonString(project_name.empty() ? "aegis-app" : project_name) << ",";
    body << "\"prompt\":" << JsonString(prompt) << ",";
    body << "\"install_command\":" << JsonString(install_command) << ",";
    body << "\"validation_command\":" << JsonString(validation_command) << ",";
    body << "\"overwrite\":" << JsonBool(overwrite) << ",";
    body << "\"include_gitignore\":" << JsonBool(include_gitignore) << ",";
    body << "\"create_roadmap\":true,";
    body << "\"run_install\":" << JsonBool(run_install) << ",";
    body << "\"run_validation\":" << JsonBool(run_validation) << ",";
    body << "\"max_repair_attempts\":" << std::max(0, std::min(5, max_repair_attempts));
    body << "}";
    return body.str();
}

std::string BuildProjectScaffoldPlanBody(
    const std::string& prompt,
    const std::string& workspace_root,
    const std::string& preferred_target_path)
{
    std::ostringstream body;
    body << "{";
    body << "\"prompt\":" << JsonString(prompt) << ",";
    body << "\"workspace_root\":" << JsonString(workspace_root) << ",";
    body << "\"preferred_target_path\":" << JsonString(preferred_target_path);
    body << "}";
    return body.str();
}

std::string BuildRestoreCheckpointBody(const std::string& workspace_root, const std::string& checkpoint)
{
    std::ostringstream body;
    body << "{";
    body << "\"workspace_root\":" << JsonString(workspace_root) << ",";
    body << "\"checkpoint\":" << JsonString(checkpoint);
    body << "}";
    return body.str();
}

std::string BuildMediaJobBody(
    const std::string& kind,
    const std::string& prompt,
    const std::string& feedback,
    const std::string& previous_job_id,
    const MediaGenerationOptions& options)
{
    const int width = std::clamp(options.width, 256, 4096);
    const int height = std::clamp(options.height, 256, 4096);
    const int fps = std::clamp(options.fps, 1, 60);
    const double duration = std::max(0.5, std::min(120.0, options.duration_seconds));
    const std::string aspect_ratio = options.aspect_ratio.empty() ? "16:9" : options.aspect_ratio;
    const std::string style = options.style.empty() ? "premium native desktop product" : options.style;

    std::ostringstream body;
    body << "{";
    body << "\"kind\":" << JsonString(kind.empty() ? "image" : kind) << ",";
    body << "\"prompt\":" << JsonString(prompt.empty() ? "Create a premium Aegis creative asset." : prompt) << ",";
    body << "\"feedback\":" << JsonString(feedback) << ",";
    body << "\"previous_job_id\":" << JsonString(previous_job_id) << ",";
    body << "\"theme_color\":" << JsonString(options.theme_color) << ",";
    body << "\"aspect_ratio\":" << JsonString(aspect_ratio) << ",";
    body << "\"style\":" << JsonString(style) << ",";
    body << "\"width\":" << width << ",";
    body << "\"height\":" << height << ",";
    body << "\"duration_seconds\":" << duration << ",";
    body << "\"fps\":" << fps << ",";
    body << "\"output_formats\":" << JsonStringArray(options.output_formats);
    body << "}";
    return body.str();
}

std::string BuildValidationProfileBody(
    const std::string& command,
    const std::string& label,
    const std::string& notes)
{
    std::ostringstream body;
    body << "{";
    body << "\"command\":" << JsonString(command) << ",";
    body << "\"label\":" << JsonString(label) << ",";
    body << "\"notes\":" << JsonString(notes);
    body << "}";
    return body.str();
}

std::string BuildFeedbackBody(
    const std::string& sentiment,
    const std::string& content,
    const std::string& context,
    const std::string& task_id,
    const std::string& action,
    const std::string& target,
    const std::string& model_label,
    const std::string& route_role,
    const std::string& candidate_id)
{
    std::ostringstream body;
    body << "{";
    body << "\"sentiment\":" << JsonString(sentiment) << ",";
    body << "\"action\":" << JsonString(action.empty() ? "manual" : action) << ",";
    body << "\"target\":" << JsonString(target.empty() ? "assistant_response" : target) << ",";
    body << "\"task_id\":" << JsonString(task_id) << ",";
    body << "\"content\":" << JsonString(content) << ",";
    body << "\"context\":" << JsonString(context) << ",";
    body << "\"model_label\":" << JsonString(model_label) << ",";
    body << "\"route_role\":" << JsonString(route_role) << ",";
    body << "\"candidate_id\":" << JsonString(candidate_id) << ",";
    body << "\"metadata\":{";
    body << "\"client\":" << JsonString("aegis-desktop") << ",";
    body << "\"content_length\":" << content.size();
    body << "}";
    body << "}";
    return body.str();
}

std::string BuildMemoryNoteBody(const MemoryNoteInfo& note)
{
    std::ostringstream body;
    body << "{";
    body << "\"title\":" << JsonString(note.title.empty() ? "Untitled memory" : note.title) << ",";
    body << "\"content\":" << JsonString(note.content) << ",";
    body << "\"category\":" << JsonString(note.category.empty() ? "insight" : note.category) << ",";
    body << "\"pinned\":" << JsonBool(note.pinned) << ",";
    body << "\"tags\":" << JsonStringArray(note.tags) << ",";
    body << "\"related_files\":" << JsonStringArray(note.related_files) << ",";
    body << "\"confidence\":" << std::max(0.0, std::min(1.0, note.confidence));
    body << "}";
    return body.str();
}

std::string BuildModelRegistryProviderBody(const ModelRegistryProviderInfo& provider)
{
    std::ostringstream body;
    body << "{";
    body << "\"id\":" << JsonString(provider.id) << ",";
    body << "\"label\":" << JsonString(provider.label) << ",";
    body << "\"api\":" << JsonString(provider.api) << ",";
    body << "\"endpoint\":" << JsonString(provider.endpoint) << ",";
    body << "\"model_name\":" << JsonString(provider.model_name) << ",";
    body << "\"model_aliases\":" << JsonStringArray(provider.model_aliases) << ",";
    body << "\"secret_env\":" << JsonString(provider.secret_env) << ",";
    body << "\"local\":" << JsonBool(provider.local) << ",";
    body << "\"enabled\":" << JsonBool(provider.enabled) << ",";
    body << "\"configured\":" << JsonBool(provider.configured) << ",";
    body << "\"capabilities\":" << JsonStringArray(provider.capabilities) << ",";
    body << "\"roles\":" << JsonStringArray(provider.roles) << ",";
    body << "\"cost_tier\":" << JsonString(provider.cost_tier) << ",";
    if (provider.context_window > 0) {
        body << "\"context_window\":" << provider.context_window << ",";
    } else {
        body << "\"context_window\":null,";
    }
    if (provider.rate_limit_rpm > 0) {
        body << "\"rate_limit_rpm\":" << provider.rate_limit_rpm << ",";
    } else {
        body << "\"rate_limit_rpm\":null,";
    }
    if (provider.input_cost_per_million > 0.0) {
        body << "\"input_cost_per_million\":" << provider.input_cost_per_million << ",";
    } else {
        body << "\"input_cost_per_million\":null,";
    }
    if (provider.output_cost_per_million > 0.0) {
        body << "\"output_cost_per_million\":" << provider.output_cost_per_million << ",";
    } else {
        body << "\"output_cost_per_million\":null,";
    }
    body << "\"health\":" << JsonString(provider.health) << ",";
    body << "\"notes\":" << JsonString(provider.notes);
    body << "}";
    return body.str();
}

std::string BuildModelPullBody(const std::string& model_name, double minimum_free_gb)
{
    std::ostringstream body;
    body << "{";
    body << "\"model_name\":" << JsonString(model_name) << ",";
    body << "\"minimum_free_gb\":" << std::max(0.0, minimum_free_gb);
    body << "}";
    return body.str();
}

std::string BuildModelDeleteBody(const std::string& model_name)
{
    std::ostringstream body;
    body << "{";
    body << "\"model_name\":" << JsonString(model_name) << ",";
    body << "\"confirm_model_name\":" << JsonString(model_name);
    body << "}";
    return body.str();
}

std::string BuildModelBenchmarkRunBody(
    const std::vector<std::string>& suite_ids,
    const std::vector<std::string>& provider_ids,
    int max_models,
    bool local_only,
    double timeout_seconds)
{
    std::ostringstream body;
    body << "{";
    body << "\"suite_ids\":" << JsonStringArray(suite_ids) << ",";
    body << "\"provider_ids\":" << JsonStringArray(provider_ids) << ",";
    body << "\"max_models\":" << std::max(1, std::min(20, max_models)) << ",";
    body << "\"local_only\":" << JsonBool(local_only) << ",";
    body << "\"timeout_seconds\":" << std::max(5.0, std::min(180.0, timeout_seconds));
    body << "}";
    return body.str();
}

}

AegisClient::AegisClient(DesktopSettings settings) : settings_(std::move(settings)) {}

RuntimeSnapshot AegisClient::LoadRuntime(bool allow_backend_start, const std::string& preferred_workspace)
{
    RuntimeSnapshot snapshot;
    const auto try_core_only_snapshot = [&](const std::string& website_error) -> bool {
        const std::string workspace = Trim(preferred_workspace);
        if (workspace.empty()) {
            return false;
        }
        CoreApiClient core(settings_);
        DesktopRuntimeStatus runtime_status = core.ProbeRuntime(workspace, nullptr);
        if (!runtime_status.core_connected) {
            snapshot.runtime_status = runtime_status;
            return false;
        }
        snapshot.runtime_status = std::move(runtime_status);
        snapshot.workspace_root = workspace;
        snapshot.config.default_workspace = workspace;
        snapshot.health.ok = true;
        snapshot.health.ready = true;
        snapshot.health.status = "core";
        snapshot.health.app = "Aegis Desktop";
        snapshot.health.engine = "Aegis Core";
        snapshot.health.engine_ready = true;
        snapshot.health.engine_message = "Core connected. Website backend fallback is unavailable: " + RedactDiagnosticText(website_error);
        snapshot.health.model_ready = snapshot.runtime_status.ollama_connected;
        snapshot.health.model_message = snapshot.runtime_status.ollama_connected ? "Ollama is reachable through Core." : "Core is reachable; model runtime is not ready.";
        try {
            snapshot.files = core.ScanWorkspaceFiles(workspace, settings_.max_files);
        } catch (const std::exception&) {
        }
        snapshot.ok = true;
        return true;
    };

    try {
        snapshot.health = GetHealth();
    } catch (const std::exception& first_error) {
        if (allow_backend_start && settings_.auto_start_backend) {
            std::string backend_error;
            if (!StartBackendProcess(settings_, backend_error)) {
                if (try_core_only_snapshot(std::string(first_error.what()) + " Backend start failed: " + backend_error)) {
                    return snapshot;
                }
                snapshot.error = std::string(first_error.what()) + " Backend start failed: " + backend_error;
                return snapshot;
            }
            std::string last_health_error = first_error.what();
            bool health_ready = false;
            for (int attempt = 0; attempt < 8; ++attempt) {
                try {
                    snapshot.health = GetHealth();
                    health_ready = true;
                    break;
                } catch (const std::exception& retry_error) {
                    last_health_error = retry_error.what();
                    std::this_thread::sleep_for(std::chrono::milliseconds(650));
                }
            }
            if (!health_ready) {
                if (try_core_only_snapshot("Backend process started, but health check did not become ready: " + last_health_error)) {
                    return snapshot;
                }
                snapshot.error = "Backend process started, but health check did not become ready: " + last_health_error;
                return snapshot;
            }
        } else {
            if (try_core_only_snapshot(first_error.what())) {
                return snapshot;
            }
            snapshot.error = first_error.what();
            return snapshot;
        }
    }

    snapshot.config = GetConfig();
    try {
        snapshot.model_inventory = GetModels();
    } catch (const std::exception& error) {
        snapshot.model_inventory.active_model = snapshot.config.model_name;
        snapshot.model_inventory.active_api = snapshot.config.model_api;
        snapshot.model_inventory.active_endpoint = snapshot.config.model_endpoint;
        snapshot.model_inventory.message = error.what();
    }
    try {
        snapshot.model_registry = GetModelRegistry();
    } catch (const std::exception& error) {
        snapshot.model_registry.active_model = snapshot.config.model_name;
        snapshot.model_registry.active_provider_id = snapshot.config.model_api + ":active";
        snapshot.model_registry.message = error.what();
    }
    snapshot.workspace_root = Trim(preferred_workspace).empty() ? snapshot.config.default_workspace : Trim(preferred_workspace);
    try {
        snapshot.model_registry_audit = GetModelRegistryAudit(snapshot.workspace_root);
        snapshot.has_model_registry_audit = true;
    } catch (const std::exception& error) {
        snapshot.model_registry_audit_error = error.what();
    }
    try {
        snapshot.model_manager = GetModelManager();
    } catch (const std::exception& error) {
        snapshot.model_manager.active_model = snapshot.config.model_name;
        snapshot.model_manager.active_provider_id = snapshot.model_registry.active_provider_id;
        snapshot.model_manager.message = error.what();
    }
    try {
        snapshot.model_benchmarks = GetModelBenchmarks();
    } catch (const std::exception& error) {
        snapshot.model_benchmarks.message = error.what();
    }
    try {
        snapshot.route_apply_preview = GetBenchmarkRoutePreview(snapshot.workspace_root);
        snapshot.has_route_apply_preview = true;
    } catch (const std::exception& error) {
        snapshot.route_apply_preview_error = error.what();
    }
    try {
        snapshot.model_registry_checkpoints = GetModelRegistryCheckpoints(8);
        snapshot.has_model_registry_checkpoints = true;
    } catch (const std::exception& error) {
        snapshot.model_registry_checkpoints_error = error.what();
    }
    snapshot.files = ListFiles(snapshot.workspace_root, settings_.max_files, &snapshot.workspace_root);
    try {
        snapshot.workspace_profile = GetWorkspaceProfile(snapshot.workspace_root);
        snapshot.has_workspace_profile = true;
    } catch (const std::exception& error) {
        snapshot.workspace_profile_error = error.what();
    }
    try {
        snapshot.workspace_autopilot_status = GetWorkspaceAutopilotStatus(snapshot.workspace_root);
        snapshot.has_workspace_autopilot_status = true;
    } catch (const std::exception& error) {
        snapshot.workspace_autopilot_status_error = error.what();
    }
    snapshot.recent_tasks = GetHistory(snapshot.workspace_root, 8);
    snapshot.runtime_status = CoreApiClient(settings_).ProbeRuntime(snapshot.workspace_root, &snapshot.health);
    snapshot.ok = true;
    return snapshot;
}

HealthStatus AegisClient::GetHealth()
{
    const std::string body = RequireJson(HttpGet(Endpoint("/api/health")), "load health");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    HealthStatus health = ParseHealth(parsed.value);
    std::string root_error;
    if (!BackendHealthProjectRootMatches(settings_, health.project_root, &root_error)) {
        throw std::runtime_error(root_error);
    }
    return health;
}

AppConfig AegisClient::GetConfig()
{
    const std::string body = RequireJson(HttpGet(Endpoint("/api/config")), "load config");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseConfig(parsed.value);
}

ModelInventory AegisClient::GetModels()
{
    const std::string body = RequireJson(HttpGet(Endpoint("/api/models")), "load model inventory");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelInventory(parsed.value);
}

ModelRegistrySnapshot AegisClient::GetModelRegistry()
{
    try {
        const std::string workspace = settings_.backend_root.empty()
            ? std::string(".")
            : WideToUtf8(settings_.backend_root.wstring());
        return CoreApiClient(settings_).GetModelRegistry(workspace);
    } catch (const std::exception& error) {
        CoreApiClient(settings_).RecordWebsiteFallback("model.registry", error.what());
    }
    const std::string body = RequireJson(HttpGet(Endpoint("/api/model-registry")), "load model registry");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelRegistry(parsed.value);
}

ModelRegistryAuditInfo AegisClient::GetModelRegistryAudit(const std::string& workspace_root)
{
    std::string path = "/api/model-registry/audit";
    if (!Trim(workspace_root).empty()) {
        path += "?workspace_root=" + UrlEncode(workspace_root);
    }
    const std::string body = RequireJson(HttpGet(Endpoint(path)), "load model registry audit");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelRegistryAudit(parsed.value);
}

ModelManagerSnapshot AegisClient::GetModelManager(double minimum_free_gb)
{
    std::ostringstream path;
    path << "/api/model-manager?minimum_free_gb=" << std::max(0.0, minimum_free_gb);
    const std::string body = RequireJson(HttpGet(Endpoint(path.str())), "load model manager");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelManagerSnapshot(parsed.value);
}

ModelBenchmarkSnapshot AegisClient::GetModelBenchmarks()
{
    const std::string body = RequireJson(HttpGet(Endpoint("/api/model-benchmarks")), "load model benchmarks");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelBenchmarkSnapshot(parsed.value);
}

ModelBenchmarkSnapshot AegisClient::RunModelBenchmarks(
    const std::vector<std::string>& suite_ids,
    int max_models,
    bool local_only,
    double timeout_seconds,
    const std::vector<std::string>& provider_ids)
{
    const std::string body = RequireJson(
        HttpPostJson(
            Endpoint("/api/model-benchmarks/run"),
            BuildModelBenchmarkRunBody(suite_ids, provider_ids, max_models, local_only, timeout_seconds)),
        "run model benchmarks");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelBenchmarkSnapshot(parsed.value);
}

ModelBenchmarkJobInfo AegisClient::StartModelBenchmarkJob(
    const std::vector<std::string>& suite_ids,
    int max_models,
    bool local_only,
    double timeout_seconds,
    const std::vector<std::string>& provider_ids)
{
    const std::string body = RequireJson(
        HttpPostJson(
            Endpoint("/api/model-benchmarks/jobs"),
            BuildModelBenchmarkRunBody(suite_ids, provider_ids, max_models, local_only, timeout_seconds)),
        "start model benchmark job");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelBenchmarkJobInfo(parsed.value);
}

ModelBenchmarkJobInfo AegisClient::CancelModelBenchmarkJob(const std::string& job_id)
{
    const std::string body = RequireJson(
        HttpPostJson(Endpoint("/api/model-benchmarks/jobs/" + UrlEncode(job_id) + "/cancel"), "{}"),
        "cancel model benchmark job");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelBenchmarkJobInfo(parsed.value);
}

ModelOperationInfo AegisClient::PullModel(const std::string& model_name, double minimum_free_gb)
{
    const std::string body = RequireJson(
        HttpPostJson(Endpoint("/api/model-manager/pull"), BuildModelPullBody(model_name, minimum_free_gb)),
        "pull model");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelOperationInfo(parsed.value);
}

ModelOperationInfo AegisClient::DeleteLocalModel(const std::string& model_name)
{
    const std::string body = RequireJson(
        HttpPostJson(Endpoint("/api/model-manager/delete"), BuildModelDeleteBody(model_name)),
        "delete local model");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelOperationInfo(parsed.value);
}

ModelRegistryBenchmarkPreviewInfo AegisClient::GetBenchmarkRoutePreview(const std::string& workspace_root)
{
    std::string path = "/api/model-registry/benchmark-winners-preview";
    if (!Trim(workspace_root).empty()) {
        path += "?workspace_root=" + UrlEncode(workspace_root);
    }
    const std::string body = RequireJson(HttpGet(Endpoint(path)), "preview benchmark route winners");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelRegistryBenchmarkPreview(parsed.value);
}

ModelRegistryCheckpointList AegisClient::GetModelRegistryCheckpoints(int limit)
{
    std::ostringstream path;
    path << "/api/model-registry/checkpoints?limit=" << std::max(1, std::min(100, limit));
    const std::string body = RequireJson(HttpGet(Endpoint(path.str())), "load model registry checkpoints");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelRegistryCheckpointList(parsed.value);
}

ModelRegistryCheckpointInfo AegisClient::CreateModelRegistryCheckpoint(const std::string& reason)
{
    const std::string body = RequireJson(
        HttpPostJson(
            Endpoint("/api/model-registry/checkpoints"),
            std::string("{\"reason\":") + JsonString(Trim(reason).empty() ? "Manual model registry checkpoint from Aegis desktop." : reason) + "}"),
        "create model registry checkpoint");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelRegistryCheckpointInfo(parsed.value);
}

ModelRegistryCheckpointDiffInfo AegisClient::GetModelRegistryCheckpointDiff(const std::string& checkpoint_id)
{
    const std::string body = RequireJson(
        HttpGet(Endpoint("/api/model-registry/checkpoints/" + UrlEncode(checkpoint_id) + "/diff")),
        "load model registry checkpoint diff");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelRegistryCheckpointDiff(parsed.value);
}

ModelRegistrySnapshot AegisClient::RestoreModelRegistryCheckpoint(const std::string& checkpoint_id)
{
    const std::string body = RequireJson(
        HttpPostJson(Endpoint("/api/model-registry/checkpoints/" + UrlEncode(checkpoint_id) + "/restore"), "{}"),
        "restore model registry checkpoint");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelRegistry(parsed.value);
}

ModelRegistrySnapshot AegisClient::ApplyBenchmarkWinnersToRegistry(const std::string& workspace_root)
{
    std::string path = "/api/model-registry/apply-benchmark-winners";
    if (!Trim(workspace_root).empty()) {
        path += "?workspace_root=" + UrlEncode(workspace_root);
    }
    const std::string body = RequireJson(
        HttpPostJson(Endpoint(path), "{}"),
        "apply benchmark winners to registry");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelRegistry(parsed.value);
}

ModelRegistrySnapshot AegisClient::ApplyRoutePolicyDiffToRegistry(
    const std::string& workspace_root,
    int limit,
    int min_attempts,
    double min_confidence,
    bool allow_high_risk)
{
    std::string path = "/api/model-registry/apply-policy-diff?limit=" +
        std::to_string(std::max(1, std::min(500, limit))) +
        "&min_attempts=" + std::to_string(std::max(1, std::min(50, min_attempts))) +
        "&min_confidence=" + std::to_string(std::max(0.0, std::min(1.0, min_confidence))) +
        "&allow_high_risk=" + std::string(allow_high_risk ? "true" : "false");
    if (!Trim(workspace_root).empty()) {
        path += "&workspace_root=" + UrlEncode(workspace_root);
    }
    const std::string body = RequireJson(
        HttpPostJson(Endpoint(path), "{}"),
        "apply route policy diff to registry");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelRegistry(parsed.value);
}

ModelRegistrySnapshot AegisClient::SaveModelRegistryProvider(const ModelRegistryProviderInfo& provider)
{
    const std::string body = RequireJson(
        HttpPostJson(Endpoint("/api/model-registry/providers"), BuildModelRegistryProviderBody(provider)),
        "save model registry provider");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelRegistry(parsed.value);
}

ModelRegistrySnapshot AegisClient::DeleteModelRegistryProvider(const std::string& provider_id)
{
    const std::string body = RequireJson(
        HttpDelete(Endpoint("/api/model-registry/providers/" + UrlEncode(provider_id))),
        "delete model registry provider");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseModelRegistry(parsed.value);
}

AppConfig AegisClient::SaveConfig(const AppConfig& config)
{
    const std::string body = RequireJson(HttpPostJson(Endpoint("/api/config"), BuildConfigBody(config)), "save config");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseConfig(parsed.value);
}

WorkspaceProfileInfo AegisClient::GetWorkspaceProfile(const std::string& workspace_root)
{
    std::string path = "/api/workspace/profile";
    if (!Trim(workspace_root).empty()) {
        path += "?workspace_root=" + UrlEncode(workspace_root);
    }

    const std::string body = RequireJson(HttpGet(Endpoint(path)), "load workspace profile");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseWorkspaceProfile(parsed.value);
}

WorkspaceAutopilotStatusInfo AegisClient::GetWorkspaceAutopilotStatus(const std::string& workspace_root)
{
    std::string path = "/api/workspace/autopilot-status";
    if (!Trim(workspace_root).empty()) {
        path += "?workspace_root=" + UrlEncode(workspace_root);
    }

    const std::string body = RequireJson(HttpGet(Endpoint(path)), "load workspace autopilot status");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseWorkspaceAutopilotStatus(parsed.value);
}

std::vector<WorkspaceFile> AegisClient::ListFiles(const std::string& workspace_root, int max_files, std::string* resolved_root)
{
    CoreApiClient core(settings_);
    try {
        std::vector<WorkspaceFile> files = core.ScanWorkspaceFiles(workspace_root, max_files);
        if (!files.empty()) {
            if (resolved_root != nullptr) {
                *resolved_root = workspace_root;
            }
            return files;
        }
    } catch (const std::exception& error) {
        core.RecordWebsiteFallback("workspace.scan", error.what());
    }

    std::string path = "/api/files?max_files=" + std::to_string(std::max(1, std::min(500, max_files)));
    if (!Trim(workspace_root).empty()) {
        path += "&workspace_root=" + UrlEncode(workspace_root);
    }

    const std::string body = RequireJson(HttpGet(Endpoint(path)), "list files");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    if (resolved_root != nullptr) {
        *resolved_root = parsed.value["workspace_root"].AsString(workspace_root);
    }
    std::vector<WorkspaceFile> files = ParseWorkspaceFiles(parsed.value["files"]);
    core.RecordWebsiteSuccess("workspace.scan", "Website fallback listed " + std::to_string(files.size()) + " workspace file(s).");
    return files;
}

std::vector<TaskSummary> AegisClient::GetHistory(const std::string& workspace_root, int limit)
{
    std::string path = "/api/history?limit=" + std::to_string(std::max(1, std::min(25, limit)));
    if (!Trim(workspace_root).empty()) {
        path += "&workspace_root=" + UrlEncode(workspace_root);
    }

    const std::string body = RequireJson(HttpGet(Endpoint(path)), "load history");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseTasks(parsed.value["recent_tasks"]);
}

TelemetrySnapshot AegisClient::GetTelemetry(const std::string& workspace_root, int limit)
{
    std::string path = "/api/telemetry?limit=" + std::to_string(std::max(1, std::min(100, limit)));
    if (!Trim(workspace_root).empty()) {
        path += "&workspace_root=" + UrlEncode(workspace_root);
    }

    const std::string body = RequireJson(HttpGet(Endpoint(path)), "load telemetry");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseTelemetry(parsed.value);
}

RouteQualitySnapshot AegisClient::GetRouteQuality(const std::string& workspace_root, int limit)
{
    std::string path = "/api/telemetry/route-quality?limit=" + std::to_string(std::max(1, std::min(500, limit)));
    if (!Trim(workspace_root).empty()) {
        path += "&workspace_root=" + UrlEncode(workspace_root);
    }

    const std::string body = RequireJson(HttpGet(Endpoint(path)), "load route quality");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseRouteQuality(parsed.value);
}

std::vector<RouteHealthInfo> AegisClient::GetRouteHealth(const std::string& workspace_root, int limit)
{
    std::string path = "/api/telemetry/route-health?limit=" + std::to_string(std::max(1, std::min(500, limit)));
    if (!Trim(workspace_root).empty()) {
        path += "&workspace_root=" + UrlEncode(workspace_root);
    }

    const std::string body = RequireJson(HttpGet(Endpoint(path)), "load route health");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseRouteHealthSignals(parsed.value);
}

FallbackInspectorSnapshot AegisClient::GetFallbackInspector(const std::string& workspace_root, int limit)
{
    std::string path = "/api/telemetry/fallback-inspector?limit=" + std::to_string(std::max(1, std::min(100, limit)));
    if (!Trim(workspace_root).empty()) {
        path += "&workspace_root=" + UrlEncode(workspace_root);
    }

    const std::string body = RequireJson(HttpGet(Endpoint(path)), "load fallback inspector");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseFallbackInspector(parsed.value);
}

RoutePolicyDiffInfo AegisClient::GetRoutePolicyDiff(const std::string& workspace_root, int limit, int min_attempts)
{
    std::string path = "/api/telemetry/policy-diff?limit=" +
        std::to_string(std::max(1, std::min(500, limit))) +
        "&min_attempts=" + std::to_string(std::max(1, std::min(50, min_attempts)));
    if (!Trim(workspace_root).empty()) {
        path += "&workspace_root=" + UrlEncode(workspace_root);
    }

    const std::string body = RequireJson(HttpGet(Endpoint(path)), "load route policy diff");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseRoutePolicyDiff(parsed.value);
}

AgentResponse AegisClient::SendMessage(
    const std::string& message,
    const std::vector<ChatMessage>& history,
    const std::string& workspace_root,
    const std::string& mode,
    bool apply_changes,
    bool run_validation,
    int max_repair_attempts,
    const std::string& validation_command_override,
    const std::string& validation_label_override,
    const std::string& validation_notes_override)
{
    const std::string body = BuildAgentRequestBody(
        message,
        history,
        workspace_root,
        mode,
        apply_changes,
        run_validation,
        max_repair_attempts,
        settings_.max_files,
        validation_command_override,
        validation_label_override,
        validation_notes_override);
    const std::string json = RequireJson(HttpPostJson(Endpoint("/api/chat"), body), "send chat message");
    const JsonParseResult parsed = ParseJson(json);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }

    return ParseAgentResponse(parsed.value, workspace_root);
}

AgentResponse AegisClient::SendMessageStream(
    const std::string& message,
    const std::vector<ChatMessage>& history,
    const std::string& workspace_root,
    const std::string& mode,
    bool apply_changes,
    bool run_validation,
    int max_repair_attempts,
    const std::function<void(const std::string&)>& on_status,
    const std::string& validation_command_override,
    const std::string& validation_label_override,
    const std::string& validation_notes_override,
    const std::function<void(const StreamDeltaInfo&)>& on_delta)
{
    const std::string body = BuildAgentRequestBody(
        message,
        history,
        workspace_root,
        mode,
        apply_changes,
        run_validation,
        max_repair_attempts,
        settings_.max_files,
        validation_command_override,
        validation_label_override,
        validation_notes_override);

    std::string stream_buffer;
    AgentResponse final_response;
    bool has_final = false;
    std::string stream_error;

    const auto handle_frame = [&](const SseFrame& frame) {
        const JsonParseResult parsed = ParseJson(frame.data);
        if (!parsed.ok) {
            return;
        }
        if (frame.event == "status") {
            const std::string message = StreamStatusMessage(parsed.value);
            if (!message.empty() && on_status) {
                on_status(message);
            }
        } else if (frame.event == "meta") {
            const std::string mode_label = parsed.value["stream_mode"].AsString();
            if (!mode_label.empty() && on_status) {
                on_status("Streaming response started (" + mode_label + ").");
            }
        } else if (frame.event == "delta") {
            StreamDeltaInfo delta_info;
            delta_info.delta = parsed.value["delta"].AsString();
            delta_info.source = parsed.value["source"].AsString();
            delta_info.preview_action = parsed.value["preview_action"].AsString("append");
            delta_info.preview_attempt = parsed.value["preview_attempt"].AsInt(0);
            delta_info.provider_label = parsed.value["provider_label"].AsString();
            delta_info.provider_api = parsed.value["provider_api"].AsString();
            delta_info.model = parsed.value["model"].AsString();
            delta_info.message = parsed.value["message"].AsString();
            if (delta_info.source == "structured_preview_reconciliation" && on_status) {
                on_status("Reconciling streamed preview with final response.");
            }
            if (delta_info.source == "structured_reply_preview" && delta_info.preview_action == "reset" && on_status) {
                if (!delta_info.message.empty()) {
                    on_status(delta_info.message);
                } else if (!delta_info.provider_label.empty()) {
                    on_status("Retiring " + delta_info.provider_label + " preview before trying the next route.");
                } else {
                    on_status("Retiring failed provider preview before trying the next route.");
                }
            }
            if (on_delta && (!delta_info.delta.empty() || delta_info.preview_action == "reset")) {
                on_delta(delta_info);
            }
        } else if (frame.event == "final") {
            final_response = ParseAgentResponse(parsed.value["response"], workspace_root);
            has_final = true;
            if (on_status) {
                on_status("Final response received.");
            }
        } else if (frame.event == "error") {
            stream_error = parsed.value["message"].AsString("Aegis streaming request failed.");
            const std::string detail = parsed.value["detail"].AsString();
            if (!detail.empty()) {
                stream_error += " " + detail;
            }
        }
    };

    const HttpResponse response = HttpPostJsonStream(
        Endpoint("/api/chat/stream"),
        body,
        [&](const std::string& chunk) {
            stream_buffer += chunk;
            const std::vector<SseFrame> frames = PopSseFrames(stream_buffer);
            for (const SseFrame& frame : frames) {
                handle_frame(frame);
            }
        });
    (void)RequireJson(response, "stream chat message");
    const std::vector<SseFrame> frames = PopSseFrames(stream_buffer);
    for (const SseFrame& frame : frames) {
        handle_frame(frame);
    }
    if (!stream_error.empty()) {
        throw std::runtime_error(stream_error);
    }
    if (!has_final) {
        return SendMessage(
            message,
            history,
            workspace_root,
            mode,
            apply_changes,
            run_validation,
            max_repair_attempts,
            validation_command_override,
            validation_label_override,
            validation_notes_override);
    }
    return final_response;
}

AgentResponse AegisClient::PreviewRoute(
    const std::string& message,
    const std::vector<ChatMessage>& history,
    const std::string& workspace_root,
    const std::string& mode)
{
    std::ostringstream body;
    body << "{";
    body << "\"message\":" << JsonString(message) << ",";
    body << "\"history\":[";
    const size_t start = history.size() > 8 ? history.size() - 8 : 0;
    bool first = true;
    for (size_t i = start; i < history.size(); ++i) {
        if (Trim(history[i].content).empty()) {
            continue;
        }
        if (!first) {
            body << ",";
        }
        first = false;
        body << "{";
        body << "\"role\":" << JsonString(history[i].role.empty() ? "user" : history[i].role) << ",";
        body << "\"content\":" << JsonString(history[i].content);
        body << "}";
    }
    body << "],";
    body << "\"workspace_root\":" << JsonString(workspace_root) << ",";
    body << "\"mode\":" << JsonString(mode.empty() ? "build" : mode) << ",";
    body << "\"max_files\":" << std::max(1, std::min(300, settings_.max_files));
    body << "}";

    const std::string json = RequireJson(HttpPostJson(Endpoint("/api/routing/preview"), body.str()), "preview route");
    const JsonParseResult parsed = ParseJson(json);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }

    const JsonValue& root = parsed.value;
    AgentResponse response;
    response.workspace_root = root["workspace_root"].AsString(workspace_root);
    response.mode = root["mode"].AsString(mode.empty() ? "build" : mode);
    response.task_plan = ParseTaskPlan(root["task_plan"], &response.has_task_plan);
    response.context_budget = ParseContextBudget(root["context_budget"], &response.has_context_budget);
    response.model_attempts = ParseModelAttempts(root["model_attempts"]);
    response.registry_message = root["registry_message"].AsString();
    response.benchmark_message = root["benchmark_message"].AsString();
    response.routing_recommendations = ParseStringArray(root["recommendations"]);
    const JsonValue& primary = root["primary_attempt"];
    if (primary.IsObject()) {
        const ModelAttemptInfo primary_attempt = ParseModelAttempt(primary);
        response.engine = primary_attempt.model.empty() ? primary_attempt.provider_label : primary_attempt.model;
    } else if (!response.model_attempts.empty()) {
        response.engine = response.model_attempts.front().model;
    }
    return response;
}

ApplyResult AegisClient::ApplyChanges(const std::string& workspace_root, const std::vector<FileChange>& changes)
{
    CoreApiClient core(settings_);
    try {
        return core.ApplyChanges(workspace_root, changes);
    } catch (const std::exception& error) {
        if (!ShouldFallbackFromCoreError(error)) {
            throw;
        }
        core.RecordWebsiteFallback("changes.apply", error.what());
    }

    const std::string json = RequireJson(HttpPostJson(Endpoint("/api/apply"), BuildChangesBody(workspace_root, changes)), "apply changes");
    const JsonParseResult parsed = ParseJson(json);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }

    ApplyResult result;
    result.applied = ParseStringArray(parsed.value["applied"]);
    result.warnings = ParseStringArray(parsed.value["warnings"]);
    result.checkpoint = parsed.value["checkpoint"].AsString();
    result.workspace_root = parsed.value["workspace_root"].AsString(workspace_root);
    result.workspace_files = ParseWorkspaceFiles(parsed.value["workspace_files"]);
    core.RecordWebsiteSuccess("changes.apply", "Website fallback applied " + std::to_string(result.applied.size()) + " change(s).", result.checkpoint);
    return result;
}

std::vector<ProjectScaffoldPresetInfo> AegisClient::GetProjectScaffoldPresets()
{
    const std::string body = RequireJson(HttpGet(Endpoint("/api/project-builder/presets")), "load project builder presets");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseProjectScaffoldPresets(parsed.value);
}

ProjectScaffoldPlanResult AegisClient::PlanProjectScaffold(
    const std::string& prompt,
    const std::string& workspace_root,
    const std::string& preferred_target_path)
{
    const std::string json = RequireJson(
        HttpPostJson(
            Endpoint("/api/project-builder/plan"),
            BuildProjectScaffoldPlanBody(prompt, workspace_root, preferred_target_path)),
        "plan project scaffold");
    const JsonParseResult parsed = ParseJson(json);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseProjectScaffoldPlanResult(parsed.value);
}

ProjectScaffoldResult AegisClient::ScaffoldProject(
    const std::string& target_path,
    const std::string& preset_id,
    const std::string& project_name,
    const std::string& install_command,
    const std::string& validation_command,
    bool overwrite,
    bool include_gitignore,
    const std::string& prompt,
    bool run_install,
    bool run_validation,
    int max_repair_attempts)
{
    const std::string json = RequireJson(
        HttpPostJson(
            Endpoint("/api/project-builder/scaffold"),
            BuildProjectScaffoldBody(
                target_path,
                preset_id,
                project_name,
                install_command,
                validation_command,
                overwrite,
                include_gitignore,
                prompt,
                run_install,
                run_validation,
                max_repair_attempts)),
        "scaffold project");
    const JsonParseResult parsed = ParseJson(json);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseProjectScaffoldResult(parsed.value);
}

ProjectScaffoldResult AegisClient::PreviewProjectScaffold(
    const std::string& target_path,
    const std::string& preset_id,
    const std::string& project_name,
    const std::string& install_command,
    const std::string& validation_command,
    bool overwrite,
    bool include_gitignore,
    const std::string& prompt,
    bool run_install,
    bool run_validation,
    int max_repair_attempts)
{
    const std::string json = RequireJson(
        HttpPostJson(
            Endpoint("/api/project-builder/preview"),
            BuildProjectScaffoldBody(
                target_path,
                preset_id,
                project_name,
                install_command,
                validation_command,
                overwrite,
                include_gitignore,
                prompt,
                run_install,
                run_validation,
                max_repair_attempts)),
        "preview project scaffold");
    const JsonParseResult parsed = ParseJson(json);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseProjectScaffoldResult(parsed.value);
}

RestoreResult AegisClient::RestoreCheckpoint(const std::string& workspace_root, const std::string& checkpoint)
{
    CoreApiClient core(settings_);
    try {
        return core.RestoreCheckpoint(workspace_root, checkpoint);
    } catch (const std::exception& error) {
        if (!ShouldFallbackFromCoreError(error)) {
            throw;
        }
        core.RecordWebsiteFallback("checkpoints.restore", error.what());
    }

    const std::string json = RequireJson(
        HttpPostJson(Endpoint("/api/restore-checkpoint"), BuildRestoreCheckpointBody(workspace_root, checkpoint)),
        "restore checkpoint");
    const JsonParseResult parsed = ParseJson(json);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }

    RestoreResult result;
    result.restored = ParseStringArray(parsed.value["restored"]);
    result.warnings = ParseStringArray(parsed.value["warnings"]);
    result.workspace_root = parsed.value["workspace_root"].AsString(workspace_root);
    result.workspace_files = ParseWorkspaceFiles(parsed.value["workspace_files"]);
    core.RecordWebsiteSuccess("checkpoints.restore", "Website fallback restored " + std::to_string(result.restored.size()) + " file item(s).", checkpoint);
    return result;
}

CheckpointListResult AegisClient::ListCheckpoints(const std::string& workspace_root, int limit)
{
    CoreApiClient core(settings_);
    try {
        return core.ListCheckpoints(workspace_root, limit);
    } catch (const std::exception& error) {
        core.RecordWebsiteFallback("checkpoints.list", error.what());
    }

    std::string endpoint = "/api/checkpoints?limit=" + std::to_string(std::max(1, std::min(200, limit)));
    if (!Trim(workspace_root).empty()) {
        endpoint += "&workspace_root=" + UrlEncode(workspace_root);
    }

    const std::string body = RequireJson(HttpGet(Endpoint(endpoint)), "list checkpoints");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }

    CheckpointListResult result;
    result.workspace_root = parsed.value["workspace_root"].AsString(workspace_root);
    result.checkpoints = ParseCheckpoints(parsed.value["checkpoints"]);
    core.RecordWebsiteSuccess("checkpoints.list", "Website fallback loaded " + std::to_string(result.checkpoints.size()) + " checkpoint(s).");
    return result;
}

AgentResponse AegisClient::ValidateWorkspace(const std::string& workspace_root)
{
    CoreApiClient core(settings_);
    try {
        return core.RunValidation(workspace_root);
    } catch (const std::exception& error) {
        if (!ShouldFallbackFromCoreError(error)) {
            throw;
        }
        core.RecordWebsiteFallback("validation.run", error.what());
    }

    std::ostringstream body;
    body << "{\"workspace_root\":" << JsonString(workspace_root) << "}";
    const std::string json = RequireJson(HttpPostJson(Endpoint("/api/validate"), body.str()), "run validation");
    const JsonParseResult parsed = ParseJson(json);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }

    AgentResponse response;
    response.task_id = parsed.value["task_id"].AsString();
    response.workspace_root = parsed.value["workspace_root"].AsString(workspace_root);
    response.events = ParseEvents(parsed.value["events"]);
    response.warnings = ParseStringArray(parsed.value["warnings"]);
    response.validation = ParseCommandRun(parsed.value["validation"], &response.has_validation);
    response.validation_profile = ParseValidationRecipe(parsed.value["validation_profile"], &response.has_validation_profile);
    response.repair_attempts = ParseRepairAttempts(parsed.value["repair_attempts"]);
    core.RecordWebsiteSuccess(
        "validation.run",
        response.has_validation
            ? (response.validation.summary.empty() ? "Website fallback validation completed." : response.validation.summary)
            : "Website fallback validation completed.");
    return response;
}

VerificationResult AegisClient::VerifyWorkspace(
    const std::string& workspace_root,
    bool include_install,
    bool continue_on_failure,
    int max_steps)
{
    std::ostringstream body;
    body << "{";
    body << "\"workspace_root\":" << JsonString(workspace_root) << ",";
    body << "\"include_install\":" << JsonBool(include_install) << ",";
    body << "\"continue_on_failure\":" << JsonBool(continue_on_failure) << ",";
    body << "\"max_steps\":" << std::max(1, std::min(20, max_steps));
    body << "}";
    const std::string json = RequireJson(HttpPostJson(Endpoint("/api/verify"), body.str()), "run full verification");
    const JsonParseResult parsed = ParseJson(json);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseVerificationResult(parsed.value);
}

void AegisClient::RecordFeedback(
    const std::string& workspace_root,
    const std::string& sentiment,
    const std::string& content,
    const std::string& context,
    const std::string& task_id,
    const std::string& action,
    const std::string& target,
    const std::string& model_label,
    const std::string& route_role,
    const std::string& candidate_id)
{
    std::string endpoint = "/api/feedback";
    if (!Trim(workspace_root).empty()) {
        endpoint += "?workspace_root=" + UrlEncode(workspace_root);
    }
    (void)RequireJson(
        HttpPostJson(Endpoint(endpoint), BuildFeedbackBody(sentiment, content, context, task_id, action, target, model_label, route_role, candidate_id)),
        "record feedback");
}

MemoryListResult AegisClient::ListMemoryNotes(const std::string& workspace_root, const std::string& category)
{
    std::string endpoint = "/api/memory";
    bool has_query = false;
    if (!Trim(workspace_root).empty()) {
        endpoint += "?workspace_root=" + UrlEncode(workspace_root);
        has_query = true;
    }
    if (!Trim(category).empty()) {
        endpoint += has_query ? "&" : "?";
        endpoint += "category=" + UrlEncode(category);
    }

    const std::string body = RequireJson(HttpGet(Endpoint(endpoint)), "load memory notes");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }

    MemoryListResult result;
    result.workspace_root = parsed.value["workspace_root"].AsString(workspace_root);
    result.notes = ParseMemoryNotes(parsed.value["notes"]);
    return result;
}

MemoryNoteInfo AegisClient::SaveMemoryNote(const std::string& workspace_root, const MemoryNoteInfo& note)
{
    std::string endpoint = "/api/memory";
    if (!Trim(note.id).empty()) {
        endpoint += "/" + UrlEncode(note.id);
    }
    if (!Trim(workspace_root).empty()) {
        endpoint += "?workspace_root=" + UrlEncode(workspace_root);
    }

    const std::string body = Trim(note.id).empty()
        ? RequireJson(HttpPostJson(Endpoint(endpoint), BuildMemoryNoteBody(note)), "create memory note")
        : RequireJson(HttpPutJson(Endpoint(endpoint), BuildMemoryNoteBody(note)), "update memory note");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseMemoryNote(parsed.value);
}

void AegisClient::DeleteMemoryNote(const std::string& workspace_root, const std::string& note_id)
{
    if (Trim(note_id).empty()) {
        throw std::runtime_error("memory note id is required");
    }

    std::string endpoint = "/api/memory/" + UrlEncode(note_id);
    if (!Trim(workspace_root).empty()) {
        endpoint += "?workspace_root=" + UrlEncode(workspace_root);
    }
    (void)RequireJson(HttpDelete(Endpoint(endpoint)), "delete memory note");
}

void AegisClient::RegisterCoreClient(
    const std::string& workspace_root,
    const std::string& client_id,
    const std::string& client_type,
    const std::string& name,
    const std::string& version,
    const std::vector<std::string>& capabilities)
{
    CoreApiClient(settings_).RegisterClient(workspace_root, client_id, client_type, name, version, capabilities);
}

AegisCoreDashboardInfo AegisClient::GetCoreDashboard(const std::string& workspace_root)
{
    return CoreApiClient(settings_).GetDashboard(workspace_root);
}

AgentSupervisionInfo AegisClient::GetAgentSupervision(const std::string& workspace_root)
{
    try {
        return CoreApiClient(settings_).GetAgentSupervision(workspace_root);
    } catch (const std::exception& error) {
        CoreApiClient(settings_).RecordWebsiteFallback("agent.supervision", error.what());
        AgentSupervisionInfo info;
        info.workspace_root = workspace_root;
        info.last_error = error.what();
        info.fallback_mode = true;
        return info;
    }
}

QualityGateSnapshotInfo AegisClient::GetQualityGates(const std::string& workspace_root)
{
    try {
        return CoreApiClient(settings_).GetQualityGates(workspace_root);
    } catch (const std::exception& error) {
        CoreApiClient(settings_).RecordWebsiteFallback("quality.gates", error.what());
        QualityGateSnapshotInfo info;
        info.workspace_root = workspace_root;
        info.available = false;
        info.core_connected = false;
        info.status = "offline";
        info.summary = error.what();
        return info;
    }
}

bool AegisClient::StepCoreWorkflow(
    const std::string& workspace_root,
    const std::string& workflow_id,
    const std::string& action,
    const std::string& task_id,
    bool approval,
    const std::string& summary)
{
    try {
        return CoreApiClient(settings_).StepWorkflow(workspace_root, workflow_id, action, task_id, approval, summary);
    } catch (const std::exception& error) {
        CoreApiClient(settings_).RecordWebsiteFallback("workflow." + action, error.what());
        return false;
    }
}

DesktopRuntimeStatus AegisClient::GetRuntimeStatus(const std::string& workspace_root)
{
    HealthStatus health;
    bool has_health = false;
    try {
        health = GetHealth();
        has_health = true;
    } catch (const std::exception&) {
    }
    return CoreApiClient(settings_).ProbeRuntime(workspace_root, has_health ? &health : nullptr);
}

DesktopRuntimeStatus AegisClient::GetCachedRuntimeStatus() const
{
    return CoreApiClient(settings_).CachedStatus();
}

std::string AegisClient::StartRepairWorkflow(
    const std::string& workspace_root,
    const std::string& validation_summary,
    const std::string& validation_command,
    const std::string& task_id)
{
    const std::string objective = Trim(validation_summary).empty()
        ? "Repair the latest validation failure from the desktop client."
        : validation_summary;
    try {
        return CoreApiClient(settings_).CreateWorkflow(
            workspace_root,
            "repair_project",
            objective + (Trim(validation_command).empty() ? "" : ("\nCommand: " + validation_command)),
            {},
            task_id);
    } catch (const std::exception& error) {
        CoreApiClient(settings_).RecordWebsiteFallback("workflow.repair_project", error.what());
        return "";
    }
}

std::string AegisClient::StartRoadmapWorkflow(
    const std::string& workspace_root,
    const std::string& objective,
    const std::vector<std::string>& context_files)
{
    try {
        return CoreApiClient(settings_).CreateWorkflow(
            workspace_root,
            "continue_roadmap",
            objective.empty() ? "Continue the workspace roadmap from the desktop client." : objective,
            context_files);
    } catch (const std::exception& error) {
        CoreApiClient(settings_).RecordWebsiteFallback("workflow.continue_roadmap", error.what());
        return "";
    }
}

ValidationProfileInfo AegisClient::GetValidationProfile(const std::string& workspace_root)
{
    std::string endpoint = "/api/validation/profile";
    if (!Trim(workspace_root).empty()) {
        endpoint += "?workspace_root=" + UrlEncode(workspace_root);
    }

    const std::string body = RequireJson(HttpGet(Endpoint(endpoint)), "load validation profile");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseValidationProfile(parsed.value);
}

ValidationProfileInfo AegisClient::SaveValidationProfile(
    const std::string& workspace_root,
    const std::string& command,
    const std::string& label,
    const std::string& notes)
{
    std::string endpoint = "/api/validation/profile";
    if (!Trim(workspace_root).empty()) {
        endpoint += "?workspace_root=" + UrlEncode(workspace_root);
    }

    const std::string body = RequireJson(
        HttpPutJson(Endpoint(endpoint), BuildValidationProfileBody(command, label, notes)),
        Trim(command).empty() ? "clear validation profile" : "save validation profile");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseValidationProfile(parsed.value);
}

FileContent AegisClient::ReadFile(const std::string& workspace_root, const std::string& path)
{
    std::string endpoint = "/api/file?path=" + UrlEncode(path);
    if (!Trim(workspace_root).empty()) {
        endpoint += "&workspace_root=" + UrlEncode(workspace_root);
    }

    const std::string body = RequireJson(HttpGet(Endpoint(endpoint)), "read file");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }

    FileContent content;
    content.workspace_root = parsed.value["workspace_root"].AsString(workspace_root);
    content.path = parsed.value["path"].AsString(path);
    content.content = parsed.value["content"].AsString();
    return content;
}

std::vector<MediaJobSummary> AegisClient::ListMediaJobs(int limit, const std::string& kind)
{
    std::string endpoint = "/api/media/jobs?limit=" + std::to_string(std::max(1, std::min(200, limit)));
    if (!Trim(kind).empty()) {
        endpoint += "&kind=" + UrlEncode(kind);
    }

    const std::string body = RequireJson(HttpGet(Endpoint(endpoint)), "list media jobs");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseMediaJobs(parsed.value);
}

MediaJobSummary AegisClient::GetMediaJob(const std::string& job_id)
{
    const std::string body = RequireJson(HttpGet(Endpoint("/api/media/jobs/" + UrlEncode(job_id))), "load media job");
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseMediaJob(parsed.value);
}

MediaJobSummary AegisClient::CreateMediaJob(
    const std::string& kind,
    const std::string& prompt,
    const std::string& feedback,
    const std::string& previous_job_id,
    const MediaGenerationOptions& options)
{
    const std::string json = RequireJson(
        HttpPostJson(Endpoint("/api/media/jobs"), BuildMediaJobBody(kind, prompt, feedback, previous_job_id, options)),
        "create media job");
    const JsonParseResult parsed = ParseJson(json);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    return ParseMediaJob(parsed.value);
}

std::string AegisClient::Endpoint(const std::string& path) const
{
    return JoinUrl(NormalizeHttpBaseUrl(settings_.api_base_url, "http://127.0.0.1:8787"), path);
}

std::string AegisClient::CoreEndpoint(const std::string& path) const
{
    return JoinUrl(NormalizeHttpBaseUrl(settings_.core_api_base_url, "http://127.0.0.1:8788"), path);
}

std::string AegisClient::RequireJson(const HttpResponse& response, const std::string& action) const
{
    if (!response.error.empty()) {
        throw std::runtime_error("Could not " + action + ": " + RedactDiagnosticText(response.error));
    }
    if (response.status_code < 200 || response.status_code >= 300) {
        const std::string detail = FirstJsonErrorDetail(response.body);
        std::ostringstream message;
        message << "Could not " << action << ": HTTP " << response.status_code;
        if (!detail.empty()) {
            message << " - " << detail;
        }
        throw std::runtime_error(message.str());
    }
    return response.body;
}

std::string BuildAssistantSummary(const AgentResponse& response)
{
    std::vector<std::string> parts;
    if (!Trim(response.reply).empty()) {
        parts.push_back(Trim(response.reply));
    }
    if (!response.changes.empty()) {
        std::ostringstream stream;
        stream << "Generated files:";
        for (const FileChange& change : response.changes) {
            stream << "\n- " << change.path << " (" << change.action << ")";
        }
        parts.push_back(stream.str());
    }
    if (!response.applied.empty()) {
        std::ostringstream stream;
        stream << "Applied changes:";
        for (const std::string& item : response.applied) {
            stream << "\n- " << item;
        }
        parts.push_back(stream.str());
    }
    if (response.has_validation) {
        std::ostringstream stream;
        stream << "Validation: " << (response.validation.allowed && response.validation.has_exit_code && response.validation.exit_code == 0 ? "passed" : "needs attention");
        if (!response.validation.summary.empty()) {
            stream << "\n" << response.validation.summary;
        }
        if (!response.validation.command.empty()) {
            stream << "\nCommand: " << response.validation.command;
        }
        parts.push_back(stream.str());
    }
    if (!response.repair_attempts.empty()) {
        std::ostringstream stream;
        stream << "Repair attempts:";
        for (const RepairAttemptInfo& attempt : response.repair_attempts) {
            stream << "\n- Attempt " << attempt.attempt << " [" << attempt.outcome << "]";
            if (!attempt.summary.empty()) {
                stream << ": " << attempt.summary;
            }
        }
        parts.push_back(stream.str());
    }
    if (response.completion_quality.should_continue || Lower(response.completion_quality.status) == "blocked") {
        std::ostringstream stream;
        stream << "Completion quality: " << (response.completion_quality.status.empty() ? "needs review" : response.completion_quality.status);
        if (response.completion_quality.score > 0.0) {
            stream << " (" << static_cast<int>(response.completion_quality.score * 100.0) << "%)";
        }
        for (const std::string& reason : response.completion_quality.reasons) {
            stream << "\n- " << reason;
        }
        if (!response.completion_quality.next_actions.empty()) {
            stream << "\nNext:";
            for (const std::string& action : response.completion_quality.next_actions) {
                stream << "\n- " << action;
            }
        }
        parts.push_back(stream.str());
    }

    std::ostringstream joined;
    for (size_t i = 0; i < parts.size(); ++i) {
        if (i > 0) {
            joined << "\n\n";
        }
        joined << parts[i];
    }
    return joined.str();
}

}
