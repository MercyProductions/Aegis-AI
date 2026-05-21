#include "CoreApiClient.h"

#include "../Json.h"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <initializer_list>
#include <mutex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace aegis {
namespace {

constexpr const char* kDesktopClientId = "aegis-desktop-native";
constexpr const char* kDesktopClientName = "Aegis Desktop";
constexpr const char* kDesktopClientVersion = "0.2.0";
constexpr const char* kDesktopReleaseSchemaVersion = "2026.05.12";

std::mutex g_runtime_status_mutex;
DesktopRuntimeStatus g_runtime_status;

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

std::vector<std::string> DesktopRuntimeCapabilities()
{
    return {
        "core-runtime-status",
        "editing-runtime",
        "workflow-runtime",
        "checkpoint-restore",
        "validation-run",
        "workspace-intelligence",
        "release-compatibility",
        "first-run-onboarding",
        "distributed-runtime",
        "runtime-interaction",
    };
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
    return "Core returned ok=false.";
}

JsonValue ParseCoreEnvelopeBody(const std::string& body, const std::string& expected_kind, bool require_ok)
{
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }
    if (!parsed.value.IsObject()) {
        throw std::runtime_error("Aegis Core returned a non-object response.");
    }
    const std::string api_version = parsed.value["api_version"].AsString();
    if (api_version != "v1") {
        throw std::runtime_error("Aegis Core response used unexpected api_version: " + (api_version.empty() ? "missing" : api_version) + ".");
    }
    const std::string kind = parsed.value["kind"].AsString();
    if (kind != expected_kind) {
        throw std::runtime_error("Aegis Core response kind mismatch: expected " + expected_kind + ", got " + (kind.empty() ? "missing" : kind) + ".");
    }
    if (require_ok && parsed.value.Has("ok") && !parsed.value["ok"].AsBool(true)) {
        throw std::runtime_error("Aegis Core " + expected_kind + " failed: " + CoreEnvelopeError(parsed.value));
    }
    return parsed.value["data"];
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
        file.kind = item["kind"].AsString("text");
        if (!file.path.empty()) {
            files.push_back(std::move(file));
        }
    }
    return files;
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

std::string CommandText(const JsonValue& value)
{
    if (value.IsArray()) {
        std::vector<std::string> parts;
        for (const JsonValue& item : value.array_value) {
            const std::string part = item.AsString();
            if (!part.empty()) {
                parts.push_back(part);
            }
        }
        std::ostringstream joined;
        for (size_t i = 0; i < parts.size(); ++i) {
            if (i > 0) {
                joined << " ";
            }
            joined << parts[i];
        }
        return joined.str();
    }
    return value.AsString();
}

CommandRun ParseCoreValidationRun(const JsonValue& validation, bool* present)
{
    CommandRun command;
    if (present != nullptr) {
        *present = validation.IsObject();
    }
    if (!validation.IsObject()) {
        return command;
    }
    command.command = CommandText(validation["command"]);
    command.cwd = validation["workspace"].AsString();
    command.allowed = !validation["blocked"].AsBool(false);
    command.has_exit_code = validation.Has("returncode") && !validation["returncode"].IsNull();
    command.exit_code = validation["returncode"].AsInt(0);
    command.stdout_text = validation["stdout"].AsString();
    command.stderr_text = validation["stderr"].AsString();
    command.timed_out = validation["timed_out"].AsBool(false);
    command.reason = validation["blocked"].AsBool(false) ? "Blocked by Core validation command safety." : validation["stderr"].AsString();
    command.category = validation["blocked"].AsBool(false) ? "blocked" : "validation";
    if (validation["ok"].AsBool(false)) {
        command.summary = "Core validation passed.";
    } else if (!command.stderr_text.empty()) {
        command.summary = RedactDiagnosticText(command.stderr_text);
    } else {
        command.summary = "Core validation failed.";
    }
    return command;
}

AegisCoreDashboardInfo ParseCoreDashboard(const JsonValue& value, const std::string& workspace_root)
{
    AegisCoreDashboardInfo dashboard;
    dashboard.reachable = true;
    dashboard.workspace_root = value["workspace"].AsString(workspace_root);

    const JsonValue& clients = value["clients"];
    if (clients.IsArray()) {
        dashboard.connected_client_count = static_cast<int>(clients.array_value.size());
    }
    const JsonValue& active_tasks = value["active_tasks"];
    if (active_tasks.IsArray()) {
        dashboard.active_task_count = static_cast<int>(active_tasks.array_value.size());
    }
    const JsonValue& recent_tasks = value["recent_tasks"];
    if (recent_tasks.IsArray()) {
        dashboard.recent_task_count = static_cast<int>(recent_tasks.array_value.size());
    }

    const JsonValue& model_status = value["model_status"];
    dashboard.ollama_reachable = model_status["reachable"].AsBool(false);
    dashboard.selected_model = model_status["selected_model"].AsString();
    if (model_status["installed_models"].IsArray()) {
        dashboard.installed_model_count = static_cast<int>(model_status["installed_models"].array_value.size());
    }
    const JsonValue& commands = value["validation"]["commands"];
    if (commands.IsArray()) {
        dashboard.validation_command_count = static_cast<int>(commands.array_value.size());
    }
    dashboard.roadmap_excerpt = value["roadmap"]["excerpt"].AsString();
    dashboard.diagnostic_excerpt = value["diagnostics"]["logs"]["core_log"]["tail"].AsString();
    return dashboard;
}

std::vector<std::string> ParseNamedStringArray(const JsonValue& value)
{
    std::vector<std::string> out;
    if (!value.IsArray()) {
        return out;
    }
    out.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        std::string text = item.AsString();
        if (text.empty() && item.IsObject()) {
            text = item["path"].AsString(item["file"].AsString(item["name"].AsString(item["id"].AsString())));
        }
        if (!text.empty()) {
            out.push_back(text);
        }
    }
    return out;
}

std::string FirstText(const JsonValue& value, const std::initializer_list<const char*>& keys, const std::string& fallback = "")
{
    if (!value.IsObject()) {
        return fallback;
    }
    for (const char* key : keys) {
        const std::string text = value[key].AsString();
        if (!text.empty()) {
            return text;
        }
    }
    return fallback;
}

std::string ModelProfileText(const JsonValue& value)
{
    if (!value.IsObject()) {
        return value.AsString();
    }
    const std::string route = value["route_profile"].AsString(value["profile"].AsString());
    const std::string provider = value["provider_id"].AsString(value["provider"].AsString());
    const std::string model = value["model"].AsString(value["model_id"].AsString(value["primary_model"].AsString()));
    if (!provider.empty() && !model.empty()) {
        return provider + " / " + model;
    }
    if (!model.empty()) {
        return model;
    }
    return route.empty() ? "route pending" : route;
}

std::vector<ToolEvent> ParseCoreTimeline(const JsonValue& value)
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
        event.kind = item["kind"].AsString(item["event_type"].AsString(item["type"].AsString("workflow")));
        event.title = item["title"].AsString(item["message"].AsString("Workflow event"));
        event.status = item["status"].AsString("ok");
        event.detail = item["detail"].AsString(item["message"].AsString());
        event.created_at = item["created_at"].AsString(item["timestamp"].AsString());
        events.push_back(std::move(event));
    }
    return events;
}

AgentSupervisionTaskInfo ParseAgentSupervisionTask(const JsonValue& value)
{
    AgentSupervisionTaskInfo task;
    if (!value.IsObject()) {
        return task;
    }
    task.id = value["id"].AsString(value["task_id"].AsString());
    task.title = value["title"].AsString(value["key"].AsString(task.id));
    task.status = value["status"].AsString("pending");
    task.agent_id = value["agent_id"].AsString();
    task.agent_role = value["agent_role"].AsString(value["agent_profile"]["role"].AsString());
    task.execution_mode = value["execution_mode"].AsString(value["stage"].AsString(value["kind"].AsString()));
    task.risk_level = value["risk_level"].AsString(value["risk"].AsString(value["estimated_risk"].AsString("unknown")));
    task.summary = value["summary"].AsString(value["reason"].AsString());
    task.model_profile = ModelProfileText(value["model_profile"]);
    task.approval_required =
        value["approval_required"].AsBool(false) ||
        (value["approval_gates"].IsArray() && !value["approval_gates"].array_value.empty()) ||
        task.status == "waiting_input";
    task.rollback_available = value["rollback_available"].AsBool(false) || !value["checkpoint_id"].AsString().empty();
    task.files = ParseNamedStringArray(value["target_files"]);
    if (task.files.empty()) {
        task.files = ParseNamedStringArray(value["files"]);
    }
    if (task.files.empty()) {
        task.files = ParseNamedStringArray(value["affected_files"]);
    }
    task.validation_requirements = ParseNamedStringArray(value["validation_requirements"]);
    if (task.validation_requirements.empty()) {
        task.validation_requirements = ParseNamedStringArray(value["validation_targets"]);
    }
    task.impacted_dependencies = ParseNamedStringArray(value["impacted_dependencies"]);
    if (task.impacted_dependencies.empty()) {
        task.impacted_dependencies = ParseNamedStringArray(value["dependencies"]);
    }
    const JsonValue& messages = value["messages"];
    if (messages.IsArray() && !messages.array_value.empty()) {
        const JsonValue& last = messages.array_value.back();
        task.last_action = FirstText(last, {"summary", "message", "type"}, "");
    }
    if (task.last_action.empty()) {
        task.last_action = task.summary;
    }
    return task;
}

std::vector<AgentSupervisionTaskInfo> ParseAgentSupervisionTasks(const JsonValue& value)
{
    std::vector<AgentSupervisionTaskInfo> tasks;
    if (!value.IsArray()) {
        return tasks;
    }
    tasks.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        AgentSupervisionTaskInfo task = ParseAgentSupervisionTask(item);
        if (!task.id.empty() || !task.title.empty()) {
            tasks.push_back(std::move(task));
        }
    }
    return tasks;
}

AgentSupervisionAgentInfo ParseAgentSupervisionAgent(const JsonValue& value)
{
    AgentSupervisionAgentInfo agent;
    if (!value.IsObject()) {
        return agent;
    }
    agent.id = value["id"].AsString(value["agent_id"].AsString());
    agent.role = value["role"].AsString(value["label"].AsString(value["name"].AsString(agent.id)));
    agent.status = value["status"].AsString("idle");
    agent.model_profile = ModelProfileText(value["model_profile"].IsObject() ? value["model_profile"] : value["preferred_model_profile"]);
    agent.risk_level = value["risk_level"].AsString(value["risk"].AsString("unknown"));
    const JsonValue& ownership = value["task_ownership"];
    if (ownership.IsArray()) {
        agent.handoff_count = static_cast<int>(ownership.array_value.size());
        if (!ownership.array_value.empty()) {
            const JsonValue& last_task = ownership.array_value.back();
            agent.assigned_task = last_task["title"].AsString(last_task["task_id"].AsString());
        }
    }
    const JsonValue& history = value["execution_history"];
    if (history.IsArray()) {
        agent.log_count = static_cast<int>(history.array_value.size());
        if (!history.array_value.empty()) {
            agent.last_action = FirstText(history.array_value.back(), {"summary", "message", "type"}, "");
        }
    }
    if (agent.assigned_task.empty()) {
        agent.assigned_task = value["assigned_task"].AsString(value["assigned_task_id"].AsString("No assigned task"));
    }
    if (agent.last_action.empty()) {
        agent.last_action = value["last_action"].AsString("No recent action");
    }
    return agent;
}

std::vector<AgentSupervisionAgentInfo> ParseAgentSupervisionAgents(const JsonValue& value)
{
    std::vector<AgentSupervisionAgentInfo> agents;
    if (!value.IsArray()) {
        return agents;
    }
    agents.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        AgentSupervisionAgentInfo agent = ParseAgentSupervisionAgent(item);
        if (!agent.id.empty() || !agent.role.empty()) {
            agents.push_back(std::move(agent));
        }
    }
    return agents;
}

AgentSupervisionInfo ParseAgentSupervisionSnapshot(
    const JsonValue& workflows_data,
    const JsonValue& dashboard_data,
    const JsonValue& coordination_data,
    const JsonValue& runtime_data,
    const std::string& workspace_root)
{
    AgentSupervisionInfo info;
    info.available = true;
    info.core_connected = true;
    info.workspace_root = workflows_data["workspace"].AsString(dashboard_data["workspace"].AsString(workspace_root));

    JsonValue empty_value;
    const JsonValue* workflow = &empty_value;
    if (dashboard_data["workflow"].IsObject()) {
        workflow = &dashboard_data["workflow"];
    } else if (workflows_data["active_workflows"].IsArray() && !workflows_data["active_workflows"].array_value.empty()) {
        workflow = &workflows_data["active_workflows"].array_value.front();
    }
    if (workflow->IsObject()) {
        info.workflow_id = (*workflow)["id"].AsString((*workflow)["workflow_id"].AsString());
        info.workflow_type = (*workflow)["workflow_type"].AsString();
        info.workflow_status = (*workflow)["status"].AsString("idle");
        info.active_task_id = (*workflow)["active_task_id"].AsString();
        info.tasks = ParseAgentSupervisionTasks((*workflow)["tasks"]);
    }

    const JsonValue* coordination = &empty_value;
    if (coordination_data.IsObject()) {
        coordination = &coordination_data;
    } else if (dashboard_data["agent_coordination"].IsObject()) {
        coordination = &dashboard_data["agent_coordination"];
    }
    if (coordination->IsObject()) {
        info.agents = ParseAgentSupervisionAgents((*coordination)["agents"]);
        info.timeline = ParseCoreTimeline((*coordination)["execution_timeline"]);
        info.safety_warnings = ParseNamedStringArray((*coordination)["safety"]["warnings"]);
    }
    if (info.agents.empty()) {
        info.agents = ParseAgentSupervisionAgents(runtime_data["agents"]);
    }
    if (info.timeline.empty()) {
        info.timeline = ParseCoreTimeline(dashboard_data["timeline"]);
    }

    for (const AgentSupervisionTaskInfo& task : info.tasks) {
        if (task.status == "queued" || task.status == "pending" || task.status == "running") {
            ++info.queued_count;
        } else if (task.status == "completed") {
            ++info.completed_count;
        } else if (task.status == "failed") {
            ++info.failed_count;
        } else if (task.status == "paused") {
            ++info.paused_count;
        }
        if (task.approval_required) {
            ++info.approval_request_count;
        }
        if (task.id == info.active_task_id || info.current_task.empty()) {
            info.current_task = task.title;
        }
        if (task.execution_mode.find("validation") != std::string::npos) {
            info.latest_validation = task.status.empty() ? task.summary : task.status;
        }
        info.rollback_available = info.rollback_available || task.rollback_available;
    }
    info.checkpoint_available = !(*workflow)["checkpoint_id"].AsString().empty() || (*workflow)["checkpoint_available"].AsBool(false);
    info.rollback_available = info.rollback_available || info.checkpoint_available;
    return info;
}

void MergeAutopilotSupervision(AgentSupervisionInfo& info, const JsonValue& data)
{
    if (!data.IsObject()) {
        return;
    }
    info.workflow_id = data["active_workflow"].AsString(info.workflow_id);
    info.current_task = data["current_task"].AsString(info.current_task);
    info.latest_validation = data["validation_status"].AsString(info.latest_validation);
    info.rollback_available = data["rollback_available"].AsBool(info.rollback_available);
    info.execution_risk_level = data["execution_risk_level"].AsString(info.execution_risk_level);
    info.confidence_score = data["confidence_score"].AsInt(info.confidence_score);
    info.validation_confidence = data["validation_confidence"].AsInt(info.validation_confidence);
    info.repair_confidence = data["repair_confidence"].AsInt(info.repair_confidence);
    info.regression_risk = data["regression_risk"].AsInt(info.regression_risk);
    info.rollback_readiness = data["rollback_readiness"].AsInt(info.rollback_readiness);
    info.autopilot_specialization = data["specialization"].AsString(info.autopilot_specialization);
    const JsonValue& execution_strategy = data["execution_strategy"];
    if (execution_strategy.IsObject()) {
        info.autopilot_execution_strategy = execution_strategy["name"].AsString(info.autopilot_execution_strategy);
    }
    const JsonValue& validation_strategy = data["validation_strategy"];
    if (validation_strategy.IsObject()) {
        info.autopilot_validation_strategy = validation_strategy["name"].AsString(info.autopilot_validation_strategy);
    }
    const JsonValue& repair_strategy = data["repair_strategy"];
    if (repair_strategy.IsObject()) {
        info.autopilot_repair_strategy = repair_strategy["name"].AsString(info.autopilot_repair_strategy);
    }
    if (data["pending_approvals"].IsArray()) {
        info.approval_request_count = std::max(info.approval_request_count, static_cast<int>(data["pending_approvals"].array_value.size()));
    }
    const JsonValue& active_run = data["active_run"];
    if (active_run.IsObject()) {
        info.workflow_type = active_run["workflow_type"].AsString(info.workflow_type);
        info.workflow_status = active_run["status"].AsString(info.workflow_status.empty() ? "idle" : info.workflow_status);
        info.autopilot_specialization = active_run["specialization"].AsString(info.autopilot_specialization);
        if (info.workflow_id.empty()) {
            info.workflow_id = active_run["workflow_id"].AsString();
        }
    }
    std::vector<ToolEvent> autopilot_events = ParseCoreTimeline(data["recent_events"]);
    if (!autopilot_events.empty()) {
        info.timeline.insert(info.timeline.end(), autopilot_events.begin(), autopilot_events.end());
        if (info.timeline.size() > 40) {
            info.timeline.erase(info.timeline.begin(), info.timeline.end() - 40);
        }
    }
    const JsonValue& scorecard = data["trust_scorecard"];
    if (scorecard.IsObject()) {
        std::vector<std::string> warnings = ParseNamedStringArray(scorecard["warnings"]);
        info.safety_warnings.insert(info.safety_warnings.end(), warnings.begin(), warnings.end());
    }
    const JsonValue& checkpoint = data["checkpoint_intelligence"];
    if (checkpoint.IsObject()) {
        const std::string health = checkpoint["checkpoint_health"].AsString();
        if (!health.empty()) {
            info.safety_warnings.push_back("Checkpoint health: " + health);
        }
    }
}

void MergeCollaborationSupervision(AgentSupervisionInfo& info, const JsonValue& data)
{
    if (!data.IsObject()) {
        return;
    }
    const JsonValue& observability = data["observability"];
    if (observability.IsObject()) {
        info.collaboration_pending_approvals = observability["pending_approval_count"].AsInt(info.collaboration_pending_approvals);
        info.collaboration_active_workflows = observability["active_workflow_count"].AsInt(info.collaboration_active_workflows);
    }
    if (data["approval_queue"].IsArray()) {
        info.collaboration_pending_approvals = std::max(
            info.collaboration_pending_approvals,
            static_cast<int>(data["approval_queue"].array_value.size()));
    }
    if (data["active_workflows"].IsArray()) {
        info.collaboration_active_workflows = std::max(
            info.collaboration_active_workflows,
            static_cast<int>(data["active_workflows"].array_value.size()));
    }
    const JsonValue& viewer = data["viewer"];
    if (viewer.IsObject()) {
        info.collaboration_role = viewer["role"].AsString(info.collaboration_role);
    }
    const JsonValue& audit = data["audit_events"];
    if (audit.IsArray() && !audit.array_value.empty() && audit.array_value.front().IsObject()) {
        info.collaboration_latest_event = audit.array_value.front()["event_type"].AsString(info.collaboration_latest_event);
    }
}

void MergeGovernanceSupervision(AgentSupervisionInfo& info, const JsonValue& data)
{
    if (!data.IsObject()) {
        return;
    }
    const JsonValue& summary = data["ui_summary"];
    if (summary.IsObject()) {
        info.governance_status = summary["status"].AsString(info.governance_status);
        info.governance_policy_violations = summary["policy_violations"].AsInt(info.governance_policy_violations);
    }
    const JsonValue& compliance = data["compliance"];
    if (compliance.IsObject()) {
        info.governance_enabled_policies = compliance["enabled_policy_count"].AsInt(info.governance_enabled_policies);
        info.governance_policy_violations = std::max(
            info.governance_policy_violations,
            compliance["recent_violation_count"].AsInt(0));
    }
    if (data["policy_violations"].IsArray()) {
        info.governance_policy_violations = std::max(
            info.governance_policy_violations,
            static_cast<int>(data["policy_violations"].array_value.size()));
    }
}

std::vector<QualityGateInfo> ParseQualityGates(const JsonValue& value)
{
    std::vector<QualityGateInfo> gates;
    if (!value.IsArray()) {
        return gates;
    }
    gates.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        QualityGateInfo gate;
        gate.id = item["id"].AsString();
        gate.label = item["label"].AsString(gate.id);
        gate.status = item["status"].AsString("skipped");
        gate.severity = item["severity"].AsString("low");
        gate.summary = item["summary"].AsString();
        gate.blocks_apply = item["blocks_apply"].AsBool(false);
        if (!gate.id.empty() || !gate.label.empty()) {
            gates.push_back(std::move(gate));
        }
    }
    return gates;
}

std::vector<std::string> ParseQualityBlockers(const JsonValue& value)
{
    std::vector<std::string> out;
    if (!value.IsArray()) {
        return out;
    }
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            const std::string text = item.AsString();
            if (!text.empty()) {
                out.push_back(text);
            }
            continue;
        }
        std::string text = item["reason"].AsString(item["summary"].AsString(item["label"].AsString(item["gate_id"].AsString())));
        if (!text.empty()) {
            out.push_back(RedactDiagnosticText(text));
        }
    }
    return out;
}

QualityGateSnapshotInfo ParseQualityGateDashboard(const JsonValue& value, const std::string& workspace_root)
{
    QualityGateSnapshotInfo info;
    info.available = true;
    info.core_connected = true;
    info.workspace_root = value["workspace"].AsString(workspace_root);

    const JsonValue& latest = value["latest"];
    if (latest.IsObject()) {
        info.latest_id = latest["id"].AsString();
        info.status = latest["status"].AsString();
        info.summary = latest["summary"].AsString();
        info.apply_allowed = latest["apply_allowed"].AsBool(false);
        info.gates = ParseQualityGates(latest["gates"]);
        info.blockers = ParseQualityBlockers(latest["blockers"]);
        info.warnings = ParseStringArray(latest["warnings"]);
        info.required_actions = ParseStringArray(latest["required_actions"]);
        const JsonValue& scorecard = latest["scorecard"];
        info.confidence_score = scorecard["confidence_score"].AsInt(0);
        info.validation_score = scorecard["validation_score"].AsInt(0);
        info.risk_score = scorecard["risk_score"].AsInt(0);
        info.completion_score = scorecard["completion_score"].AsInt(0);
        info.blocker_count = static_cast<int>(info.blockers.size());
        info.warning_count = static_cast<int>(info.warnings.size());
        info.latest_validation_command = latest["validation"]["latest_command"].AsString();
    } else {
        info.status = "not_run";
    }

    const JsonValue& benchmark_history = value["benchmark_history"];
    if (benchmark_history.IsArray() && !benchmark_history.array_value.empty()) {
        const JsonValue& latest_benchmark = benchmark_history.array_value.front();
        info.latest_benchmark_status = latest_benchmark["status"].AsString();
        info.latest_benchmark_score = latest_benchmark["score"].AsDouble(0.0);
    }
    return info;
}

ModelRegistrySnapshot ParseCoreModelRegistry(const JsonValue& value)
{
    ModelRegistrySnapshot registry;
    registry.version = 1;
    registry.router_enabled = true;
    registry.fallback_supported = true;
    registry.message = "Aegis Core model registry connected.";

    const JsonValue& selected = value["selected_model"];
    registry.active_provider_id = selected["provider_id"].AsString();
    registry.active_model = selected["model_id"].AsString(selected["display_name"].AsString());

    const JsonValue& providers = value["providers"];
    if (providers.IsArray()) {
        registry.providers.reserve(providers.array_value.size());
        for (const JsonValue& item : providers.array_value) {
            if (!item.IsObject()) {
                continue;
            }
            ModelRegistryProviderInfo provider;
            provider.id = item["id"].AsString();
            provider.label = item["label"].AsString(provider.id);
            provider.api = item["api"].AsString();
            provider.endpoint = item["endpoint"].AsString();
            provider.model_name = item["default_model"].AsString();
            provider.local = item["local"].AsBool(false);
            provider.enabled = item["enabled"].AsBool(true);
            provider.configured = item["configured"].AsBool(false);
            provider.capabilities = ParseStringArray(item["capabilities"]);
            provider.roles = ParseStringArray(item["roles"]);
            provider.cost_tier = item["cost_estimate"].AsString("unknown");
            provider.context_window = item["context_window"].AsInt(0);
            provider.health = item["availability_status"].AsString("unknown");
            provider.notes = "Sourced from Aegis Core; privacy " + item["privacy_level"].AsString("unknown") + ".";
            if (!provider.id.empty()) {
                registry.providers.push_back(std::move(provider));
            }
        }
    }

    const JsonValue& profiles = value["routing_profiles"];
    if (profiles.IsArray()) {
        registry.presets.reserve(profiles.array_value.size());
        for (const JsonValue& item : profiles.array_value) {
            if (!item.IsObject()) {
                continue;
            }
            ModelRoutingPresetInfo preset;
            preset.id = item["id"].AsString();
            preset.label = item["label"].AsString(preset.id);
            preset.description = item["description"].AsString();
            preset.role_order = ParseStringArray(item["priority"]);
            preset.privacy_mode = item["privacy_mode"].AsString("local-first");
            if (!preset.id.empty()) {
                registry.presets.push_back(std::move(preset));
            }
        }
    }
    return registry;
}

void ApplySettingsToStatus(DesktopRuntimeStatus& status, const DesktopSettings& settings)
{
    status.core_base_url = NormalizeHttpBaseUrl(settings.core_api_base_url, "http://127.0.0.1:8788");
    status.website_base_url = NormalizeHttpBaseUrl(settings.api_base_url, "http://127.0.0.1:8787");
    if (status.registered_client_id.empty()) {
        status.registered_client_id = kDesktopClientId;
    }
}

void StoreStatus(const DesktopRuntimeStatus& status, const DesktopSettings& settings)
{
    std::lock_guard<std::mutex> lock(g_runtime_status_mutex);
    g_runtime_status = status;
    ApplySettingsToStatus(g_runtime_status, settings);
}

void RecordOperation(
    const DesktopSettings& settings,
    const std::string& operation,
    const std::string& runtime,
    const std::string& state,
    const std::string& detail,
    const std::string& job_id = "",
    const std::string& workflow_id = "",
    const std::string& checkpoint_id = "")
{
    std::lock_guard<std::mutex> lock(g_runtime_status_mutex);
    ApplySettingsToStatus(g_runtime_status, settings);
    g_runtime_status.last_operation = operation;
    g_runtime_status.last_runtime = runtime;
    if (runtime.find("fallback") != std::string::npos) {
        g_runtime_status.fallback_mode = true;
    } else if (runtime == "core") {
        g_runtime_status.fallback_mode = false;
    }
    if (state == "failed" || runtime.find("fallback") != std::string::npos) {
        g_runtime_status.last_error = RedactDiagnosticText(detail);
    } else if (runtime == "core") {
        g_runtime_status.last_error.clear();
    }
    if (!workflow_id.empty()) {
        g_runtime_status.active_workflow_id = workflow_id;
    }
    RuntimeOperationLogEntry entry;
    entry.time_label = NowTimeLabel();
    entry.operation = operation;
    entry.runtime = runtime;
    entry.status = state;
    entry.detail = RedactDiagnosticText(detail);
    entry.job_id = job_id;
    entry.workflow_id = workflow_id;
    entry.checkpoint_id = checkpoint_id;
    g_runtime_status.recent_operations.insert(g_runtime_status.recent_operations.begin(), std::move(entry));
    if (g_runtime_status.recent_operations.size() > 32) {
        g_runtime_status.recent_operations.resize(32);
    }
}

void AddScanPath(std::vector<WorkspaceFile>& files, std::set<std::string>& seen, const std::string& path)
{
    const std::string trimmed = Trim(path);
    if (trimmed.empty() || seen.find(trimmed) != seen.end()) {
        return;
    }
    seen.insert(trimmed);
    WorkspaceFile file;
    file.path = trimmed;
    file.kind = "text";
    files.push_back(std::move(file));
}

std::vector<WorkspaceFile> ReadPersistedCoreFileIndex(const std::string& workspace_root, int max_files)
{
    std::filesystem::path index_path = std::filesystem::path(Utf8ToWide(workspace_root)) / ".aegis" / "file-index.json";
    std::ifstream input(index_path, std::ios::binary);
    if (!input) {
        return {};
    }
    std::ostringstream buffer;
    buffer << input.rdbuf();
    const JsonParseResult parsed = ParseJson(buffer.str());
    if (!parsed.ok || !parsed.value.IsArray()) {
        return {};
    }
    std::vector<WorkspaceFile> files;
    files.reserve(std::min(static_cast<size_t>(std::max(1, max_files)), parsed.value.array_value.size()));
    for (const JsonValue& item : parsed.value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        WorkspaceFile file;
        file.path = item["path"].AsString();
        file.size = item["size"].AsInt(0);
        file.kind = "text";
        if (!file.path.empty()) {
            files.push_back(std::move(file));
        }
        if (static_cast<int>(files.size()) >= std::max(1, max_files)) {
            break;
        }
    }
    return files;
}

}

CoreApiClient::CoreApiClient(DesktopSettings settings) : settings_(std::move(settings)) {}

DesktopRuntimeStatus CoreApiClient::ProbeRuntime(
    const std::string& workspace_root,
    const HealthStatus* website_health) const
{
    DesktopRuntimeStatus status = CachedStatus();
    ApplySettingsToStatus(status, settings_);
    status.registered_client_id = kDesktopClientId;
    status.website_connected = website_health != nullptr && (website_health->ok || website_health->engine_ready);
    status.ollama_connected = website_health != nullptr && website_health->model_ready;

    try {
        const std::string workspace = Trim(workspace_root);
        const std::vector<std::string> capabilities = DesktopRuntimeCapabilities();
        if (!workspace.empty()) {
            try {
                RegisterClient(
                    workspace,
                    kDesktopClientId,
                    "desktop-app",
                    kDesktopClientName,
                    kDesktopClientVersion,
                    capabilities,
                    status.active_workflow_id);
            } catch (const std::exception&) {
            }
        }

        std::string endpoint = "/v1/health";
        if (!Trim(workspace_root).empty()) {
            endpoint += "?workspace=" + UrlEncode(workspace_root);
        }
        const JsonValue data = ParseCoreEnvelopeBody(
            RequireJson(HttpGet(Endpoint(endpoint)), "probe Aegis Core health"),
            "health",
            true);
        status.core_connected = true;
        status.ollama_connected = data["ollama"]["reachable"].AsBool(status.ollama_connected);

        if (!Trim(workspace_root).empty()) {
            try {
                std::ostringstream body;
                body << "{";
                body << "\"workspace\":" << JsonString(workspace_root) << ",";
                body << "\"client_type\":\"desktop\",";
                body << "\"client_version\":" << JsonString(kDesktopClientVersion) << ",";
                body << "\"schema_version\":" << JsonString(kDesktopReleaseSchemaVersion) << ",";
                body << "\"capabilities\":" << JsonStringArray(capabilities);
                body << "}";
                const JsonValue compatibility = ParseCoreEnvelopeBody(
                    RequireJson(HttpPostJson(Endpoint("/v1/release/compatibility"), body.str()), "check Core release compatibility"),
                    "release.compatibility",
                    false);
                status.release_compatibility_checked = true;
                status.release_compatible = compatibility["compatible"].AsBool(false);
                status.release_compatibility_status = compatibility["status"].AsString("unknown");
                status.release_schema_version = compatibility["required_schema_version"].AsString();
                status.release_required_core_version = compatibility["required_core_version"].AsString();
                status.release_minimum_client_version = compatibility["minimum_client_version"].AsString();
                status.release_compatibility_blockers = ParseStringArray(compatibility["blockers"]);
                status.release_compatibility_warnings = ParseStringArray(compatibility["warnings"]);
                status.release_compatibility_recommendations = ParseStringArray(compatibility["recommendations"]);
                status.last_operation = "Compatibility: " + status.release_compatibility_status;
            } catch (const std::exception& error) {
                status.release_compatibility_checked = false;
                if (status.release_compatibility_status.empty()) {
                    status.release_compatibility_status = "unavailable";
                }
                status.last_error = RedactDiagnosticText(error.what());
            }
        }

        if (!Trim(workspace_root).empty()) {
            try {
                const std::string sync_body = RequireJson(
                    HttpGet(Endpoint("/v1/client-sync?workspace=" + UrlEncode(workspace_root) + "&limit=20")),
                    "load Core client sync dashboard");
                const JsonValue sync_data = ParseCoreEnvelopeBody(sync_body, "client.sync.dashboard", true);
                const JsonValue& workflows = sync_data["active_workflows"];
                if (workflows.IsArray() && !workflows.array_value.empty()) {
                    status.active_workflow_id = workflows.array_value.front()["id"].AsString();
                }
            } catch (const std::exception&) {
            }
        }

        if (!Trim(workspace_root).empty()) {
            try {
                const JsonValue distributed = ParseCoreEnvelopeBody(
                    RequireJson(
                        HttpGet(Endpoint("/v1/distributed-runtime?workspace=" + UrlEncode(workspace_root) + "&include_audit=true&limit=5")),
                        "load Core distributed runtime"),
                    "distributed.runtime",
                    true);
                const JsonValue& nodes = distributed["observability"]["nodes"];
                const JsonValue& workloads = distributed["observability"]["workloads"];
                status.distributed_node_count = nodes["total"].AsInt(status.distributed_node_count);
                status.distributed_online_node_count = nodes["online"].AsInt(status.distributed_online_node_count);
                status.distributed_active_workload_count = workloads["active"].AsInt(status.distributed_active_workload_count);
                status.distributed_queued_workload_count = workloads["queued"].AsInt(status.distributed_queued_workload_count);
                const JsonValue& audit_events = distributed["audit_events"];
                if (audit_events.IsArray() && !audit_events.array_value.empty()) {
                    status.distributed_last_event = audit_events.array_value.front()["event_type"].AsString();
                }
                status.last_operation = "Distributed runtime: " + std::to_string(status.distributed_online_node_count) + "/" +
                    std::to_string(status.distributed_node_count) + " node(s) online";
                status.last_runtime = "core";
                RecordOperation(settings_, "distributed.runtime", "core", "completed", "Loaded Core distributed runtime node status.");
            } catch (const std::exception& error) {
                if (status.last_error.empty()) {
                    status.last_error = RedactDiagnosticText(error.what());
                }
            }
        }

        if (!Trim(workspace_root).empty()) {
            try {
                const JsonValue runtime_interaction = ParseCoreEnvelopeBody(
                    RequireJson(
                        HttpGet(Endpoint("/v1/runtime/terminals?workspace=" + UrlEncode(workspace_root) + "&limit=10")),
                        "load Core runtime interaction"),
                    "runtime.interaction",
                    true);
                const JsonValue& live = runtime_interaction["observability"];
                status.runtime_terminal_count = live["terminal_count"].AsInt(status.runtime_terminal_count);
                status.runtime_terminal_job_count = live["job_count"].AsInt(status.runtime_terminal_job_count);
                status.runtime_active_terminal_job_count = live["active_jobs"].AsInt(status.runtime_active_terminal_job_count);
                status.runtime_session_count = live["session_count"].AsInt(status.runtime_session_count);
                status.runtime_active_process_count = live["active_processes"].AsInt(status.runtime_active_process_count);
                const JsonValue& events = runtime_interaction["recent_events"];
                if (events.IsArray() && !events.array_value.empty()) {
                    status.runtime_latest_event = events.array_value.front()["event_type"].AsString();
                }
                status.runtime_voice_status = runtime_interaction["voice"]["status"].AsString(status.runtime_voice_status);
                status.last_operation = "Live runtime: " + std::to_string(status.runtime_active_terminal_job_count) +
                    " active terminal job(s)";
                status.last_runtime = "core";
                RecordOperation(settings_, "runtime.interaction", "core", "completed", "Loaded Core live runtime interaction status.");
            } catch (const std::exception& error) {
                if (status.last_error.empty()) {
                    status.last_error = RedactDiagnosticText(error.what());
                }
            }
        }

        if (!Trim(workspace_root).empty()) {
            try {
                const JsonValue onboarding = ParseCoreEnvelopeBody(
                    RequireJson(
                        HttpGet(Endpoint("/v1/onboarding/status?workspace=" + UrlEncode(workspace_root))),
                        "load Core onboarding status"),
                    "onboarding.status",
                    true);
                status.onboarding_completed = onboarding["completed"].AsBool(false);
                status.onboarding_current_step = onboarding["current_step"].AsString();
                const JsonValue& summary = onboarding["diagnostics"]["summary"];
                status.onboarding_warning_count = summary["warning_count"].AsInt(0);
                status.onboarding_failure_count = summary["failure_count"].AsInt(0);
                status.last_operation = "Onboarding: " + (status.onboarding_completed ? std::string("complete") : status.onboarding_current_step);
                status.last_runtime = "core";
                RecordOperation(settings_, "onboarding.status", "core", "completed", "Loaded Core first-run setup status.");
            } catch (const std::exception& error) {
                status.onboarding_current_step = "unavailable";
                if (status.last_error.empty()) {
                    status.last_error = RedactDiagnosticText(error.what());
                }
            }
        }
    } catch (const std::exception& error) {
        status.core_connected = false;
        status.last_error = RedactDiagnosticText(error.what());
    }

    StoreStatus(status, settings_);
    return status;
}

DesktopRuntimeStatus CoreApiClient::CachedStatus() const
{
    std::lock_guard<std::mutex> lock(g_runtime_status_mutex);
    DesktopRuntimeStatus status = g_runtime_status;
    ApplySettingsToStatus(status, settings_);
    return status;
}

void CoreApiClient::RegisterClient(
    const std::string& workspace_root,
    const std::string& client_id,
    const std::string& client_type,
    const std::string& name,
    const std::string& version,
    const std::vector<std::string>& capabilities,
    const std::string& active_workflow_id) const
{
    std::ostringstream body;
    body << "{";
    body << "\"workspace\":" << JsonString(workspace_root) << ",";
    body << "\"client_id\":" << JsonString(client_id.empty() ? kDesktopClientId : client_id) << ",";
    body << "\"client_type\":" << JsonString(client_type.empty() ? "desktop-app" : client_type) << ",";
    body << "\"name\":" << JsonString(name.empty() ? kDesktopClientName : name) << ",";
    body << "\"version\":" << JsonString(version.empty() ? kDesktopClientVersion : version) << ",";
    body << "\"capabilities\":" << JsonStringArray(capabilities) << ",";
    body << "\"active_workflow_id\":" << (active_workflow_id.empty() ? "null" : JsonString(active_workflow_id)) << ",";
    body << "\"status\":\"active\",";
    body << "\"metadata\":{\"runtime\":\"native-desktop\",\"preferred_runtime\":\"core\"}";
    body << "}";

    HttpResponse response = HttpPostJson(Endpoint("/v1/clients/sync"), body.str());
    std::string expected_kind = "client.sync";
    if (response.status_code == 404 || response.status_code == 405) {
        response = HttpPostJson(Endpoint("/v1/clients/register"), body.str());
        expected_kind = "client.registered";
    }
    ParseCoreEnvelopeBody(RequireJson(response, "register Aegis Core desktop client"), expected_kind, true);

    {
        std::lock_guard<std::mutex> lock(g_runtime_status_mutex);
        ApplySettingsToStatus(g_runtime_status, settings_);
        g_runtime_status.core_connected = true;
        g_runtime_status.registered_client_id = client_id.empty() ? kDesktopClientId : client_id;
    }
    RecordOperation(settings_, "client.sync", "core", "completed", "Desktop client registered with Aegis Core.");
}

AegisCoreDashboardInfo CoreApiClient::GetDashboard(const std::string& workspace_root) const
{
    const std::string endpoint = "/v1/ecosystem/dashboard?workspace=" + UrlEncode(workspace_root);
    const JsonValue data = ParseCoreEnvelopeBody(
        RequireJson(HttpGet(Endpoint(endpoint)), "load Aegis Core dashboard"),
        "ecosystem.dashboard",
        true);
    AegisCoreDashboardInfo dashboard = ParseCoreDashboard(data, workspace_root);
    RecordOperation(settings_, "ecosystem.dashboard", "core", "completed", "Loaded Core ecosystem dashboard.");
    return dashboard;
}

AgentSupervisionInfo CoreApiClient::GetAgentSupervision(const std::string& workspace_root) const
{
    const std::string workspace = Trim(workspace_root).empty() ? "." : workspace_root;
    const JsonValue runtime_data = ParseCoreEnvelopeBody(
        RequireJson(HttpGet(Endpoint("/v1/agents/runtime?workspace=" + UrlEncode(workspace))), "load Core agent runtime"),
        "agent.runtime",
        true);
    const JsonValue workflows_data = ParseCoreEnvelopeBody(
        RequireJson(
            HttpGet(Endpoint("/v1/workflows?workspace=" + UrlEncode(workspace) + "&include_completed=false&limit=30")),
            "load Core workflow list"),
        "workflows.list",
        true);

    JsonValue dashboard_data;
    JsonValue coordination_data;
    std::string workflow_id;
    const JsonValue& active = workflows_data["active_workflows"];
    if (active.IsArray() && !active.array_value.empty() && active.array_value.front().IsObject()) {
        workflow_id = active.array_value.front()["id"].AsString(active.array_value.front()["workflow_id"].AsString());
    } else if (workflows_data["workflows"].IsArray() && !workflows_data["workflows"].array_value.empty() && workflows_data["workflows"].array_value.front().IsObject()) {
        workflow_id = workflows_data["workflows"].array_value.front()["id"].AsString(workflows_data["workflows"].array_value.front()["workflow_id"].AsString());
    }

    if (!workflow_id.empty()) {
        dashboard_data = ParseCoreEnvelopeBody(
            RequireJson(
                HttpGet(Endpoint("/v1/workflows/" + UrlEncode(workflow_id) + "?workspace=" + UrlEncode(workspace))),
                "load Core workflow dashboard"),
            "workflow.dashboard",
            true);
        coordination_data = ParseCoreEnvelopeBody(
            RequireJson(
                HttpGet(Endpoint("/v1/workflows/" + UrlEncode(workflow_id) + "/agents?workspace=" + UrlEncode(workspace))),
                "load Core agent coordination"),
            "agent.coordination",
            true);
    }

    AgentSupervisionInfo info = ParseAgentSupervisionSnapshot(workflows_data, dashboard_data, coordination_data, runtime_data, workspace);
    try {
        const JsonValue autopilot_data = ParseCoreEnvelopeBody(
            RequireJson(
                HttpGet(Endpoint("/v1/autopilot/supervision?workspace=" + UrlEncode(workspace))),
                "load Core Autopilot supervision"),
            "autopilot.supervision",
            true);
        MergeAutopilotSupervision(info, autopilot_data);
    } catch (const std::exception& error) {
        info.safety_warnings.push_back("Autopilot supervision unavailable: " + RedactDiagnosticText(error.what()));
    }
    try {
        const JsonValue collaboration_data = ParseCoreEnvelopeBody(
            RequireJson(
                HttpGet(Endpoint("/v1/collaboration?workspace=" + UrlEncode(workspace) + "&limit=50")),
                "load Core collaboration runtime"),
            "collaboration.dashboard",
            true);
        MergeCollaborationSupervision(info, collaboration_data);
    } catch (const std::exception& error) {
        info.safety_warnings.push_back("Collaboration runtime unavailable: " + RedactDiagnosticText(error.what()));
    }
    try {
        const JsonValue governance_data = ParseCoreEnvelopeBody(
            RequireJson(
                HttpGet(Endpoint("/v1/governance?workspace=" + UrlEncode(workspace) + "&limit=50")),
                "load Core governance runtime"),
            "governance.dashboard",
            true);
        MergeGovernanceSupervision(info, governance_data);
    } catch (const std::exception& error) {
        info.safety_warnings.push_back("Governance runtime unavailable: " + RedactDiagnosticText(error.what()));
    }
    RecordOperation(settings_, "agent.supervision", "core", "completed", "Loaded Core agent supervision state.", "", info.workflow_id, "");
    return info;
}

QualityGateSnapshotInfo CoreApiClient::GetQualityGates(const std::string& workspace_root) const
{
    const std::string workspace = Trim(workspace_root).empty() ? "." : workspace_root;
    const JsonValue data = ParseCoreEnvelopeBody(
        RequireJson(
            HttpGet(Endpoint("/v1/quality-gates?workspace=" + UrlEncode(workspace) + "&limit=20")),
            "load Core quality gates"),
        "quality.gates",
        true);
    QualityGateSnapshotInfo info = ParseQualityGateDashboard(data, workspace);
    RecordOperation(
        settings_,
        "quality.gates",
        "core",
        info.apply_allowed ? "passed" : (info.status.empty() ? "loaded" : info.status),
        info.summary.empty() ? "Loaded Core quality gate status." : info.summary,
        "",
        "",
        "");
    return info;
}

ModelRegistrySnapshot CoreApiClient::GetModelRegistry(const std::string& workspace_root) const
{
    const std::string workspace = Trim(workspace_root).empty() ? "." : workspace_root;
    const std::string endpoint = "/v1/models/registry?workspace=" + UrlEncode(workspace);
    const JsonValue data = ParseCoreEnvelopeBody(
        RequireJson(HttpGet(Endpoint(endpoint)), "load Aegis Core model registry"),
        "model.registry",
        true);
    ModelRegistrySnapshot registry = ParseCoreModelRegistry(data);
    RecordOperation(settings_, "model.registry", "core", "completed", "Loaded Core model registry.");
    return registry;
}

ApplyResult CoreApiClient::ApplyChanges(
    const std::string& workspace_root,
    const std::vector<FileChange>& changes,
    bool dry_run) const
{
    std::ostringstream body;
    body << "{";
    body << "\"workspace\":" << JsonString(workspace_root) << ",";
    body << "\"changes\":[";
    for (size_t i = 0; i < changes.size(); ++i) {
        const FileChange& change = changes[i];
        if (i > 0) {
            body << ",";
        }
        body << "{";
        body << "\"action\":" << JsonString(change.action.empty() ? "update" : change.action) << ",";
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
    body << "],";
    body << "\"apply_all\":true,";
    body << "\"dry_run\":" << JsonBool(dry_run) << ",";
    body << "\"summary\":\"Desktop generated changes apply\",";
    body << "\"source_client\":" << JsonString(kDesktopClientId);
    body << "}";

    const JsonValue data = ParseCoreEnvelopeBody(
        RequireJson(HttpPostJson(Endpoint("/v1/changes/apply"), body.str()), "apply Core changes"),
        "changes.apply",
        false);

    ApplyResult result;
    result.applied = ParseStringArray(data["applied"]);
    result.warnings = ParseStringArray(data["warnings"]);
    result.checkpoint = data["checkpoint_id"].AsString(data["checkpoint"]["id"].AsString());
    result.workspace_root = data["workspace"].AsString(workspace_root);
    try {
        result.workspace_files = ScanWorkspaceFiles(result.workspace_root, settings_.max_files);
    } catch (const std::exception&) {
    }
    RecordOperation(
        settings_,
        "changes.apply",
        "core",
        data["dry_run"].AsBool(false) ? "dry_run" : "completed",
        result.applied.empty() ? "Core apply completed without file writes." : "Core applied " + std::to_string(result.applied.size()) + " change(s).",
        data["job_id"].AsString(),
        "",
        result.checkpoint);
    return result;
}

CheckpointListResult CoreApiClient::ListCheckpoints(const std::string& workspace_root, int limit) const
{
    const int clamped_limit = std::max(1, std::min(200, limit));
    const std::string endpoint = "/v1/checkpoints?workspace=" + UrlEncode(workspace_root) + "&limit=" + std::to_string(clamped_limit);
    const JsonValue data = ParseCoreEnvelopeBody(
        RequireJson(HttpGet(Endpoint(endpoint)), "list Core checkpoints"),
        "checkpoints.list",
        true);
    CheckpointListResult result;
    result.workspace_root = data["workspace"].AsString(workspace_root);
    result.checkpoints = ParseCheckpoints(data["checkpoints"]);
    RecordOperation(settings_, "checkpoints.list", "core", "completed", "Loaded " + std::to_string(result.checkpoints.size()) + " Core checkpoint(s).");
    return result;
}

RestoreResult CoreApiClient::RestoreCheckpoint(
    const std::string& workspace_root,
    const std::string& checkpoint_id,
    bool dry_run) const
{
    std::ostringstream body;
    body << "{";
    body << "\"workspace\":" << JsonString(workspace_root) << ",";
    body << "\"checkpoint_id\":" << JsonString(checkpoint_id) << ",";
    body << "\"dry_run\":" << JsonBool(dry_run) << ",";
    body << "\"source_client\":" << JsonString(kDesktopClientId);
    body << "}";
    const JsonValue data = ParseCoreEnvelopeBody(
        RequireJson(HttpPostJson(Endpoint("/v1/checkpoints/restore"), body.str()), "restore Core checkpoint"),
        "checkpoints.restore",
        false);

    RestoreResult result;
    result.restored = ParseStringArray(data["restored"]);
    result.warnings = ParseStringArray(data["warnings"]);
    result.workspace_root = data["workspace"].AsString(workspace_root);
    try {
        result.workspace_files = ScanWorkspaceFiles(result.workspace_root, settings_.max_files);
    } catch (const std::exception&) {
    }
    RecordOperation(
        settings_,
        "checkpoints.restore",
        "core",
        dry_run ? "dry_run" : "completed",
        result.restored.empty() ? "Core checkpoint restore completed without file writes." : "Core restored " + std::to_string(result.restored.size()) + " file item(s).",
        data["job_id"].AsString(),
        "",
        data["checkpoint_id"].AsString(checkpoint_id));
    return result;
}

AgentResponse CoreApiClient::RunValidation(
    const std::string& workspace_root,
    const std::vector<std::string>& command,
    int timeout_seconds,
    bool dry_run) const
{
    std::ostringstream body;
    body << "{";
    body << "\"workspace\":" << JsonString(workspace_root) << ",";
    body << "\"command\":";
    if (command.empty()) {
        body << "null";
    } else {
        body << JsonStringArray(command);
    }
    body << ",";
    body << "\"timeout_seconds\":" << std::max(1, std::min(900, timeout_seconds)) << ",";
    body << "\"dry_run\":" << JsonBool(dry_run) << ",";
    body << "\"source_client\":" << JsonString(kDesktopClientId);
    body << "}";
    const JsonValue data = ParseCoreEnvelopeBody(
        RequireJson(HttpPostJson(Endpoint("/v1/validation/run"), body.str()), "run Core validation"),
        "validation.run",
        false);

    AgentResponse response;
    response.task_id = data["task_id"].AsString();
    response.workspace_root = data["workspace"].AsString(workspace_root);
    response.validation = ParseCoreValidationRun(data["validation"], &response.has_validation);
    response.warnings = ParseStringArray(data["warnings"]);
    response.engine = "aegis-core";
    response.mode = "validate";

    ToolEvent event;
    event.kind = "validation";
    event.title = "Core validation";
    event.status = data["validation"]["ok"].AsBool(false) ? "passed" : "failed";
    event.detail = response.validation.summary;
    event.created_at = data["created_at"].AsString();
    response.events.push_back(std::move(event));

    RecordOperation(
        settings_,
        "validation.run",
        "core",
        data["validation"]["ok"].AsBool(false) ? "passed" : "failed",
        response.validation.summary,
        data["job_id"].AsString(),
        "",
        "");
    return response;
}

std::string CoreApiClient::CreateWorkflow(
    const std::string& workspace_root,
    const std::string& workflow_type,
    const std::string& objective,
    const std::vector<std::string>& context_files,
    const std::string& source_task_id) const
{
    std::ostringstream body;
    body << "{";
    body << "\"workspace\":" << JsonString(workspace_root) << ",";
    body << "\"workflow_type\":" << JsonString(workflow_type.empty() ? "chat_request" : workflow_type) << ",";
    body << "\"objective\":" << JsonString(objective.empty() ? "Continue the current desktop workflow." : objective) << ",";
    body << "\"source_client\":" << JsonString(kDesktopClientId) << ",";
    body << "\"context_files\":" << JsonStringArray(context_files) << ",";
    body << "\"metadata\":{\"desktop_task_id\":" << JsonString(source_task_id) << "}";
    body << "}";
    const JsonValue data = ParseCoreEnvelopeBody(
        RequireJson(HttpPostJson(Endpoint("/v1/workflows"), body.str()), "create Core workflow"),
        "workflow.created",
        true);
    const std::string workflow_id = data["workflow"]["id"].AsString(data["id"].AsString());
    RecordOperation(settings_, "workflow." + workflow_type, "core", "queued", "Created Core workflow " + workflow_id + ".", "", workflow_id, "");
    return workflow_id;
}

bool CoreApiClient::StepWorkflow(
    const std::string& workspace_root,
    const std::string& workflow_id,
    const std::string& action,
    const std::string& task_id,
    bool approval,
    const std::string& summary) const
{
    if (Trim(workflow_id).empty()) {
        throw std::runtime_error("workflow id is required");
    }
    std::ostringstream body;
    body << "{";
    body << "\"workspace\":" << JsonString(workspace_root) << ",";
    body << "\"action\":" << JsonString(action.empty() ? "advance" : action) << ",";
    body << "\"task_id\":";
    if (Trim(task_id).empty()) {
        body << "null";
    } else {
        body << JsonString(task_id);
    }
    body << ",";
    body << "\"approval\":" << JsonBool(approval) << ",";
    body << "\"summary\":" << JsonString(summary) << ",";
    body << "\"payload\":{}";
    body << "}";
    const JsonValue data = ParseCoreEnvelopeBody(
        RequireJson(HttpPostJson(Endpoint("/v1/workflows/" + UrlEncode(workflow_id) + "/step"), body.str()), "control Core workflow"),
        "workflow.step",
        false);
    RecordOperation(settings_, "workflow." + (action.empty() ? std::string("advance") : action), "core", "completed", summary, data["event"]["id"].AsString(), workflow_id, "");
    return data["workflow"].IsObject();
}

std::vector<WorkspaceFile> CoreApiClient::ScanWorkspaceFiles(const std::string& workspace_root, int max_files) const
{
    std::ostringstream body;
    body << "{";
    body << "\"workspace\":" << JsonString(workspace_root);
    body << "}";
    const JsonValue data = ParseCoreEnvelopeBody(
        RequireJson(HttpPostJson(Endpoint("/v1/workspaces/scan"), body.str()), "scan workspace with Aegis Core"),
        "workspace.scan",
        true);

    std::vector<WorkspaceFile> files = ReadPersistedCoreFileIndex(workspace_root, max_files);
    if (files.empty()) {
        files = ParseWorkspaceFiles(data["files"]);
    }
    if (!files.empty()) {
        if (static_cast<int>(files.size()) > max_files) {
            files.resize(static_cast<size_t>(std::max(1, max_files)));
        }
        RecordOperation(settings_, "workspace.scan", "core", "completed", "Loaded workspace scan from Core.");
        return files;
    }

    std::set<std::string> seen;
    for (const char* key : {"recent_files", "build_files", "test_files", "readmes", "entry_points"}) {
        const JsonValue& values = data[key];
        if (!values.IsArray()) {
            continue;
        }
        for (const JsonValue& item : values.array_value) {
            AddScanPath(files, seen, item.AsString());
            if (static_cast<int>(files.size()) >= std::max(1, max_files)) {
                break;
            }
        }
    }
    RecordOperation(settings_, "workspace.scan", "core", "completed", "Loaded workspace scan from Core.");
    return files;
}

void CoreApiClient::RecordWebsiteFallback(const std::string& operation, const std::string& detail) const
{
    RecordOperation(settings_, operation, "website-fallback", "fallback", detail);
}

void CoreApiClient::RecordWebsiteSuccess(
    const std::string& operation,
    const std::string& detail,
    const std::string& checkpoint_id) const
{
    RecordOperation(settings_, operation, "website", "completed", detail, "", "", checkpoint_id);
}

std::string CoreApiClient::Endpoint(const std::string& path) const
{
    return JoinUrl(NormalizeHttpBaseUrl(settings_.core_api_base_url, "http://127.0.0.1:8788"), path);
}

std::string CoreApiClient::RequireJson(const HttpResponse& response, const std::string& action) const
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

}
