#include "AegisClient.h"

#include "Json.h"

#include <algorithm>
#include <sstream>
#include <stdexcept>
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

ModelCapabilities ParseModelCapabilities(const JsonValue& value)
{
    ModelCapabilities capabilities;
    if (!value.IsObject()) {
        return capabilities;
    }
    capabilities.chat = value["chat"].AsBool(true);
    capabilities.streaming = value["streaming"].AsBool(false);
    capabilities.structured_json = value["structured_json"].AsBool(false);
    capabilities.tools = value["tools"].AsBool(false);
    capabilities.vision = value["vision"].AsBool(false);
    capabilities.audio = value["audio"].AsBool(false);
    capabilities.embeddings = value["embeddings"].AsBool(false);
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
            provider.local = item["local"].AsBool(true);
            provider.enabled = item["enabled"].AsBool(true);
            provider.configured = item["configured"].AsBool(false);
            provider.capabilities = ParseStringArray(item["capabilities"]);
            provider.roles = ParseStringArray(item["roles"]);
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
    health.app = value["app"].AsString();
    health.engine = value["engine"].AsString();
    health.engine_ready = value["engine_ready"].AsBool(false);
    health.model_ready = value["model_ready"].AsBool(false);
    health.model_message = value["model_message"].AsString();
    return health;
}

AppConfig ParseConfig(const JsonValue& value)
{
    AppConfig config;
    config.assistant_name = value["assistant_name"].AsString("Aegis AI");
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
        ? "python,py,node,npm,npx,pnpm,pytest,uvicorn,tsc,vite,cargo,rustc,go,dotnet"
        : config.command_allowlist) << ",";
    body << "\"command_timeout_seconds\":" << std::max(5, std::min(3600, config.command_timeout_seconds)) << ",";
    body << "\"auto_run_validation\":" << JsonBool(config.auto_run_validation);
    body << "}";
    return body.str();
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
    const std::string& context)
{
    std::ostringstream body;
    body << "{";
    body << "\"sentiment\":" << JsonString(sentiment) << ",";
    body << "\"title\":" << JsonString("User " + sentiment + " an Aegis response") << ",";
    body << "\"content\":" << JsonString(content) << ",";
    body << "\"context\":" << JsonString(context);
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
    body << "\"local\":" << JsonBool(provider.local) << ",";
    body << "\"enabled\":" << JsonBool(provider.enabled) << ",";
    body << "\"configured\":" << JsonBool(provider.configured) << ",";
    body << "\"capabilities\":" << JsonStringArray(provider.capabilities) << ",";
    body << "\"roles\":" << JsonStringArray(provider.roles) << ",";
    body << "\"health\":" << JsonString(provider.health) << ",";
    body << "\"notes\":" << JsonString(provider.notes);
    body << "}";
    return body.str();
}

}

AegisClient::AegisClient(DesktopSettings settings) : settings_(std::move(settings)) {}

RuntimeSnapshot AegisClient::LoadRuntime(bool allow_backend_start, const std::string& preferred_workspace)
{
    RuntimeSnapshot snapshot;

    try {
        snapshot.health = GetHealth();
    } catch (const std::exception& first_error) {
        if (allow_backend_start && settings_.auto_start_backend) {
            std::string backend_error;
            if (!StartBackendProcess(settings_, backend_error)) {
                snapshot.error = std::string(first_error.what()) + " Backend start failed: " + backend_error;
                return snapshot;
            }
            snapshot.health = GetHealth();
        } else {
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
    snapshot.files = ListFiles(snapshot.workspace_root, settings_.max_files, &snapshot.workspace_root);
    snapshot.recent_tasks = GetHistory(snapshot.workspace_root, 8);
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
    return ParseHealth(parsed.value);
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
    const std::string body = RequireJson(HttpGet(Endpoint("/api/model-registry")), "load model registry");
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

std::vector<WorkspaceFile> AegisClient::ListFiles(const std::string& workspace_root, int max_files, std::string* resolved_root)
{
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
    return ParseWorkspaceFiles(parsed.value["files"]);
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

AgentResponse AegisClient::SendMessage(
    const std::string& message,
    const std::vector<ChatMessage>& history,
    const std::string& workspace_root,
    const std::string& mode,
    bool apply_changes,
    bool run_validation,
    int max_repair_attempts)
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
    body << "\"max_repair_attempts\":" << std::max(0, std::min(3, max_repair_attempts)) << ",";
    body << "\"max_files\":" << std::max(1, std::min(300, settings_.max_files));
    body << "}";

    const std::string json = RequireJson(HttpPostJson(Endpoint("/api/chat"), body.str()), "send chat message");
    const JsonParseResult parsed = ParseJson(json);
    if (!parsed.ok) {
        throw std::runtime_error(parsed.error);
    }

    const JsonValue& root = parsed.value;
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
    response.assistant_name = root["assistant_name"].AsString("Aegis AI");
    response.mode = root["mode"].AsString("build");
    response.engine = root["engine"].AsString();
    response.workspace_root = root["workspace_root"].AsString(workspace_root);
    response.workspace_files = ParseWorkspaceFiles(root["workspace_files"]);
    response.context_files = ParseWorkspaceFiles(root["context_files"]);
    response.recent_tasks = ParseTasks(root["recent_tasks"]);
    response.repair_attempts = ParseRepairAttempts(root["repair_attempts"]);
    return response;
}

ApplyResult AegisClient::ApplyChanges(const std::string& workspace_root, const std::vector<FileChange>& changes)
{
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
    return result;
}

RestoreResult AegisClient::RestoreCheckpoint(const std::string& workspace_root, const std::string& checkpoint)
{
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
    return result;
}

CheckpointListResult AegisClient::ListCheckpoints(const std::string& workspace_root, int limit)
{
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
    return result;
}

AgentResponse AegisClient::ValidateWorkspace(const std::string& workspace_root)
{
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
    return response;
}

void AegisClient::RecordFeedback(
    const std::string& workspace_root,
    const std::string& sentiment,
    const std::string& content,
    const std::string& context)
{
    std::string endpoint = "/api/feedback";
    if (!Trim(workspace_root).empty()) {
        endpoint += "?workspace_root=" + UrlEncode(workspace_root);
    }
    (void)RequireJson(HttpPostJson(Endpoint(endpoint), BuildFeedbackBody(sentiment, content, context)), "record feedback");
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
    return JoinUrl(settings_.api_base_url, path);
}

std::string AegisClient::RequireJson(const HttpResponse& response, const std::string& action) const
{
    if (!response.error.empty()) {
        throw std::runtime_error("Could not " + action + ": " + response.error);
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
