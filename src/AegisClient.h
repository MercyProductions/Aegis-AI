#pragma once

#include "Platform.h"

#include <string>
#include <utility>
#include <vector>

namespace aegis {

struct ModeOption {
    std::string id;
    std::string label;
    std::string description;
};

struct ChatMessage {
    std::string role;
    std::string content;
    std::string time_label;
    std::string model_label;
};

struct WorkspaceFile {
    std::string path;
    long long size = 0;
    std::string kind;
};

struct FileChange {
    std::string action;
    std::string path;
    std::string content;
    bool has_content = false;
    std::string summary;
};

struct ToolEvent {
    std::string kind;
    std::string title;
    std::string status;
    std::string detail;
    std::string created_at;
};

struct CommandRun {
    std::string command;
    std::string cwd;
    bool allowed = false;
    int exit_code = 0;
    bool has_exit_code = false;
    std::string stdout_text;
    std::string stderr_text;
    bool timed_out = false;
    std::string reason;
    std::string category;
    std::string summary;
};

struct ValidationRecipeInfo {
    std::string command;
    std::string label;
    std::string source;
    std::string updated_at;
    std::string notes;
};

struct ValidationSuggestionInfo {
    std::string command;
    std::string label;
    std::string category;
    std::string reason;
};

struct ValidationProfileInfo {
    std::string workspace_root;
    ValidationRecipeInfo profile;
    bool has_profile = false;
    std::vector<ValidationSuggestionInfo> suggestions;
};

struct TaskSummary {
    std::string id;
    std::string created_at;
    std::string finished_at;
    std::string mode;
    std::string workspace_root;
    std::string message;
    std::string status;
};

struct AppConfig {
    std::string assistant_name = "Aegis AI";
    std::string assistant_mission;
    std::string default_mode = "build";
    std::vector<ModeOption> modes;
    std::string default_workspace;
    std::string engine;
    bool engine_ready = false;
    std::string engine_message;
    std::string model_name;
    std::string model_endpoint;
    std::string model_api = "ollama";
    bool model_ready = false;
    std::string model_message;
    std::string database_path;
    std::string command_allowlist;
    int command_timeout_seconds = 120;
    bool auto_run_validation = false;
    bool env_exists = false;
};

struct ModelCapabilities {
    bool chat = true;
    bool streaming = false;
    bool structured_json = false;
    bool tools = false;
    bool vision = false;
    bool audio = false;
    bool embeddings = false;
    bool computer_use = false;
};

struct ModelInfo {
    std::string id;
    std::string name;
    std::string provider;
    std::string api;
    std::string endpoint;
    bool local = true;
    bool configured = false;
    bool available = false;
    bool ready = false;
    std::string message;
    long long size = 0;
    std::string modified_at;
    ModelCapabilities capabilities;
};

struct ModelInventory {
    std::string active_model;
    std::string active_api;
    std::string active_endpoint;
    bool router_enabled = false;
    bool fallback_supported = false;
    std::string message;
    std::vector<ModelInfo> models;
};

struct ModelRegistryProviderInfo {
    std::string id;
    std::string label;
    std::string api;
    std::string endpoint;
    bool local = true;
    bool enabled = true;
    bool configured = false;
    std::vector<std::string> capabilities;
    std::vector<std::string> roles;
    std::string health;
    std::string notes;
};

struct ModelRegistryRoleInfo {
    std::string id;
    std::string label;
    std::string description;
    std::string primary_model;
    std::vector<std::string> fallback_models;
    std::vector<std::string> required_capabilities;
    std::string privacy_mode;
    std::string cost_tier;
    std::string status;
};

struct ModelRoutingPresetInfo {
    std::string id;
    std::string label;
    std::string description;
    std::vector<std::string> role_order;
    std::string privacy_mode;
};

struct ModelRegistrySnapshot {
    int version = 1;
    std::string active_provider_id;
    std::string active_model;
    bool router_enabled = false;
    bool fallback_supported = false;
    std::string message;
    std::vector<ModelRegistryProviderInfo> providers;
    std::vector<ModelRegistryRoleInfo> roles;
    std::vector<ModelRoutingPresetInfo> presets;
};

struct HealthStatus {
    bool ok = false;
    std::string app;
    std::string engine;
    bool engine_ready = false;
    bool model_ready = false;
    std::string model_message;
};

struct RuntimeSnapshot {
    bool ok = false;
    HealthStatus health;
    AppConfig config;
    std::vector<WorkspaceFile> files;
    std::vector<TaskSummary> recent_tasks;
    ModelInventory model_inventory;
    ModelRegistrySnapshot model_registry;
    std::string workspace_root;
    std::string error;
};

struct RepairAttemptInfo {
    int attempt = 0;
    std::string category;
    std::string before_signature;
    std::string after_signature;
    std::string outcome;
    std::string checkpoint;
    std::string summary;
    std::string created_at;
};

struct AgentResponse {
    std::string task_id;
    std::string reply;
    std::vector<std::string> plan;
    std::vector<FileChange> changes;
    std::vector<std::string> applied;
    std::string checkpoint;
    std::vector<std::string> warnings;
    std::vector<ToolEvent> events;
    CommandRun validation;
    bool has_validation = false;
    ValidationRecipeInfo validation_profile;
    bool has_validation_profile = false;
    std::string assistant_name;
    std::string mode;
    std::string engine;
    std::string workspace_root;
    std::vector<WorkspaceFile> workspace_files;
    std::vector<WorkspaceFile> context_files;
    std::vector<TaskSummary> recent_tasks;
    std::vector<RepairAttemptInfo> repair_attempts;
};

struct ApplyResult {
    std::vector<std::string> applied;
    std::vector<std::string> warnings;
    std::string checkpoint;
    std::string workspace_root;
    std::vector<WorkspaceFile> workspace_files;
};

struct RestoreResult {
    std::vector<std::string> restored;
    std::vector<std::string> warnings;
    std::string workspace_root;
    std::vector<WorkspaceFile> workspace_files;
};

struct CheckpointFileInfo {
    std::string path;
    std::string state;
};

struct CheckpointSummaryInfo {
    std::string id;
    std::string created_at;
    int file_count = 0;
    int present_count = 0;
    int missing_count = 0;
    std::vector<CheckpointFileInfo> files;
};

struct CheckpointListResult {
    std::string workspace_root;
    std::vector<CheckpointSummaryInfo> checkpoints;
};

struct FileContent {
    std::string workspace_root;
    std::string path;
    std::string content;
};

struct MediaAssetInfo {
    std::string path;
    std::string kind;
    std::string format;
    std::string role;
    std::string mime_type;
    bool editable = false;
    std::string derived_from;
};

struct MediaGenerationOptions {
    std::string theme_color;
    std::string aspect_ratio = "16:9";
    std::string style = "premium native desktop product";
    double duration_seconds = 4.0;
    int fps = 12;
    int width = 1280;
    int height = 720;
    std::vector<std::string> output_formats;
};

struct MediaJobSummary {
    std::string id;
    std::string created_at;
    std::string kind;
    std::string status;
    std::string prompt;
    std::string feedback;
    std::string previous_job_id;
    std::string theme_color;
    std::vector<std::string> palette;
    std::string aspect_ratio;
    std::string style;
    std::string job_dir;
    std::string message;
    std::vector<std::string> plan;
    std::vector<MediaAssetInfo> assets;
    std::vector<std::string> warnings;
    std::vector<std::string> next_actions;
};

struct MemoryNoteInfo {
    std::string id;
    std::string title;
    std::string content;
    std::string category;
    std::string created_at;
    std::string updated_at;
    bool pinned = false;
    std::vector<std::string> tags;
    std::vector<std::string> related_files;
    double confidence = 0.8;
};

struct MemoryListResult {
    std::string workspace_root;
    std::vector<MemoryNoteInfo> notes;
};

class AegisClient {
public:
    explicit AegisClient(DesktopSettings settings);

    const DesktopSettings& Settings() const { return settings_; }
    void SetSettings(DesktopSettings settings) { settings_ = std::move(settings); }

    RuntimeSnapshot LoadRuntime(bool allow_backend_start, const std::string& preferred_workspace = "");
    HealthStatus GetHealth();
    AppConfig GetConfig();
    ModelInventory GetModels();
    ModelRegistrySnapshot GetModelRegistry();
    ModelRegistrySnapshot SaveModelRegistryProvider(const ModelRegistryProviderInfo& provider);
    ModelRegistrySnapshot DeleteModelRegistryProvider(const std::string& provider_id);
    AppConfig SaveConfig(const AppConfig& config);
    std::vector<WorkspaceFile> ListFiles(const std::string& workspace_root, int max_files, std::string* resolved_root = nullptr);
    std::vector<TaskSummary> GetHistory(const std::string& workspace_root, int limit);
    AgentResponse SendMessage(
        const std::string& message,
        const std::vector<ChatMessage>& history,
        const std::string& workspace_root,
        const std::string& mode,
        bool apply_changes,
        bool run_validation,
        int max_repair_attempts);
    ApplyResult ApplyChanges(const std::string& workspace_root, const std::vector<FileChange>& changes);
    RestoreResult RestoreCheckpoint(const std::string& workspace_root, const std::string& checkpoint);
    CheckpointListResult ListCheckpoints(const std::string& workspace_root, int limit = 50);
    AgentResponse ValidateWorkspace(const std::string& workspace_root);
    void RecordFeedback(
        const std::string& workspace_root,
        const std::string& sentiment,
        const std::string& content,
        const std::string& context);
    MemoryListResult ListMemoryNotes(const std::string& workspace_root, const std::string& category = "");
    MemoryNoteInfo SaveMemoryNote(const std::string& workspace_root, const MemoryNoteInfo& note);
    void DeleteMemoryNote(const std::string& workspace_root, const std::string& note_id);
    ValidationProfileInfo GetValidationProfile(const std::string& workspace_root);
    ValidationProfileInfo SaveValidationProfile(
        const std::string& workspace_root,
        const std::string& command,
        const std::string& label,
        const std::string& notes);
    FileContent ReadFile(const std::string& workspace_root, const std::string& path);
    std::vector<MediaJobSummary> ListMediaJobs(int limit = 50, const std::string& kind = "");
    MediaJobSummary GetMediaJob(const std::string& job_id);
    MediaJobSummary CreateMediaJob(
        const std::string& kind,
        const std::string& prompt,
        const std::string& feedback,
        const std::string& previous_job_id,
        const MediaGenerationOptions& options);

private:
    DesktopSettings settings_;

    std::string Endpoint(const std::string& path) const;
    std::string RequireJson(const HttpResponse& response, const std::string& action) const;
};

std::string BuildAssistantSummary(const AgentResponse& response);

}
