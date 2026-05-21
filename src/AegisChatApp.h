#pragma once

#include "AegisClient.h"

#include <array>
#include <atomic>
#include <chrono>
#include <future>
#include <functional>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

namespace aegis {

struct ToastNotification {
    std::string title;
    std::string message;
    std::string tone;
    float created_at = 0.0f;
    float duration = 4.2f;
};

struct LocalConversationSummary {
    std::string id;
    std::string title;
    std::string preview;
    std::string saved_at;
    std::string path;
    int message_count = 0;
    bool pinned = false;
    bool archived = false;
    long long sort_key = 0;
};

struct CreativePreviewTexture {
    void* shader_resource_view = nullptr;
    int width = 0;
    int height = 0;
    bool attempted = false;
    std::string error;
};

struct VerificationRepairActivity {
    std::string title;
    std::string detail;
    std::string status;
    std::string command;
    std::string created_at;
};

struct AgentActivityEvent {
    std::string timestamp;
    std::string type;
    std::string message;
    std::string file_path;
    std::string command;
    std::string status;
};

struct QueuedUserMessage {
    std::string content;
    std::vector<FileContent> attachments;
};

class AegisChatApp {
public:
    AegisChatApp();
    ~AegisChatApp();

    void Initialize();
    void Tick();
    void Render();

private:
    using Completion = std::function<void()>;

    DesktopSettings settings_;
    AegisClient client_;
    HealthStatus health_;
    AppConfig config_;
    ModelInventory models_;
    DesktopRuntimeStatus runtime_status_;
    ModelRegistrySnapshot model_registry_;
    ModelManagerSnapshot model_manager_;
    ModelBenchmarkSnapshot model_benchmarks_;
    bool has_config_ = false;
    bool backend_started_this_session_ = false;
    bool authenticated_ = false;
    bool dashboard_ready_ = false;
    bool remember_me_ = true;

    std::vector<WorkspaceFile> files_;
    std::vector<TaskSummary> recent_tasks_;
    std::vector<ChatMessage> history_;
    std::vector<ToastNotification> toasts_;
    std::vector<FileContent> attachments_;
    std::vector<LocalConversationSummary> conversations_;
    std::vector<MemoryNoteInfo> memory_notes_;
    std::vector<VerificationRepairActivity> verification_repair_activities_;
    std::unordered_map<std::string, CreativePreviewTexture> creative_texture_cache_;
    TelemetrySnapshot telemetry_;
    RouteQualitySnapshot route_quality_;
    std::vector<RouteHealthInfo> route_health_;
    FallbackInspectorSnapshot fallback_inspector_;
    RoutePolicyDiffInfo route_policy_diff_;
    ModelRegistryBenchmarkPreviewInfo route_apply_preview_;
    ModelRegistryAuditInfo model_registry_audit_;
    ModelRegistryCheckpointList model_registry_checkpoints_;
    ModelRegistryCheckpointDiffInfo selected_model_registry_checkpoint_diff_;
    ModelRegistryCheckpointInfo pending_model_registry_restore_;
    std::vector<ProjectScaffoldPresetInfo> project_scaffold_presets_;
    ProjectScaffoldPlanResult project_scaffold_plan_;
    ProjectScaffoldResult project_scaffold_result_;
    WorkspaceProfileInfo workspace_profile_;
    WorkspaceAutopilotStatusInfo workspace_autopilot_status_;
    AegisCoreDashboardInfo core_dashboard_;
    AgentSupervisionInfo agent_supervision_;
    QualityGateSnapshotInfo quality_gates_;
    AgentResponse last_response_;
    AgentResponse route_preview_;
    bool has_response_ = false;
    bool has_route_preview_ = false;
    FileContent selected_file_;
    bool has_selected_file_ = false;
    ValidationProfileInfo validation_profile_;
    bool has_validation_profile_snapshot_ = false;
    VerificationResult verification_result_;
    bool has_verification_result_ = false;
    bool has_workspace_profile_snapshot_ = false;
    bool has_workspace_autopilot_status_snapshot_ = false;
    bool core_dashboard_loaded_ = false;
    bool agent_supervision_loaded_ = false;
    bool quality_gates_loaded_ = false;
    CheckpointListResult checkpoints_;
    std::vector<MediaJobSummary> media_jobs_;
    MediaJobSummary selected_media_job_;
    bool has_selected_media_job_ = false;

    std::future<Completion> active_task_;
    std::future<ModelBenchmarkSnapshot> benchmark_poll_task_;
    std::atomic_bool busy_ = false;
    std::mutex status_update_mutex_;
    std::vector<std::string> pending_status_updates_;
    std::mutex stream_delta_mutex_;
    std::vector<StreamDeltaInfo> pending_stream_deltas_;
    std::mutex agent_activity_mutex_;
    std::vector<AgentActivityEvent> pending_agent_activity_;
    std::vector<AgentActivityEvent> agent_activity_;
    std::vector<QueuedUserMessage> queued_user_messages_;
    int streaming_assistant_index_ = -1;
    bool streaming_assistant_has_delta_ = false;
    size_t streaming_preview_segment_start_ = 0;
    int streaming_preview_attempt_ = 0;
    std::string busy_label_;
    std::string status_;
    std::chrono::steady_clock::time_point next_health_check_{};
    std::chrono::steady_clock::time_point next_benchmark_poll_{};
    std::chrono::steady_clock::time_point last_runtime_refresh_{};
    std::chrono::steady_clock::time_point setup_started_{};
    std::chrono::steady_clock::time_point smoke_auto_login_at_{};
    float dashboard_reveal_time_ = 0.0f;

    std::string workspace_root_;
    std::string mode_ = "build";
    std::string active_nav_ = "chat";
    std::string connection_state_ = "offline";
    std::string connection_detail_;
    std::string current_conversation_id_;
    std::string current_conversation_title_;
    std::string last_media_job_id_;
    std::string last_media_kind_;
    std::string playing_audio_path_;
    std::string pending_popup_;
    std::string last_toast_status_;
    std::string route_quality_error_;
    std::string route_health_error_;
    std::string fallback_inspector_error_;
    std::string route_policy_diff_error_;
    std::string route_apply_preview_error_;
    std::string model_registry_audit_error_;
    std::string model_registry_checkpoints_error_;
    std::string selected_model_registry_checkpoint_diff_error_;
    std::string workspace_profile_error_;
    std::string workspace_autopilot_status_error_;
    std::string core_dashboard_error_;
    std::string agent_supervision_error_;
    std::string quality_gates_error_;
    std::string next_validation_command_override_;
    std::string next_validation_label_override_;
    std::string next_validation_notes_override_;
    bool apply_changes_ = true;
    bool run_validation_ = false;
    bool verification_include_install_ = false;
    bool verification_continue_on_failure_ = false;
    bool verification_auto_repair_chain_ = false;
    bool pending_full_verify_after_repair_ = false;
    bool pending_verification_chain_repair_ = false;
    bool autopilot_enabled_ = false;
    bool autopilot_active_ = false;
    bool autopilot_stop_requested_ = false;
    bool autopilot_finishing_ = false;
    bool autopilot_waiting_for_result_ = false;
    bool autopilot_dependency_verify_attempted_ = false;
    bool next_submit_apply_override_set_ = false;
    bool next_submit_apply_override_ = false;
    bool next_submit_validation_override_set_ = false;
    bool next_submit_validation_override_ = false;
    bool auto_scroll_ = true;
    bool command_palette_focus_ = false;
    bool smoke_auto_login_ = false;
    bool smoke_auto_login_done_ = false;
    bool setup_check_auto_opened_ = false;
    bool cancel_response_requested_ = false;
    bool runtime_refresh_in_flight_ = false;
    bool current_conversation_pinned_ = false;
    bool current_conversation_archived_ = false;
    bool show_archived_conversations_ = false;
    bool show_model_provider_editor_ = false;
    bool model_provider_local_ = true;
    bool model_provider_enabled_ = true;
    bool model_provider_configured_ = false;
    bool telemetry_loaded_ = false;
    bool route_quality_loaded_ = false;
    bool route_health_loaded_ = false;
    bool fallback_inspector_loaded_ = false;
    bool route_policy_diff_loaded_ = false;
    bool route_apply_preview_loaded_ = false;
    bool model_registry_audit_loaded_ = false;
    bool model_registry_checkpoints_loaded_ = false;
    bool selected_model_registry_checkpoint_diff_loaded_ = false;
    bool has_pending_model_registry_restore_ = false;
    bool project_scaffold_presets_loaded_ = false;
    bool project_scaffold_presets_requested_ = false;
    bool project_scaffold_has_plan_ = false;
    bool project_scaffold_has_result_ = false;
    bool project_scaffold_result_preview_ = false;
    bool project_scaffold_overwrite_ = false;
    bool project_scaffold_include_gitignore_ = true;
    bool project_scaffold_run_install_ = false;
    bool project_scaffold_run_validation_ = true;
    int model_provider_context_window_ = 0;
    int model_provider_rate_limit_rpm_ = 0;
    float model_provider_input_cost_per_million_ = 0.0f;
    float model_provider_output_cost_per_million_ = 0.0f;
    bool memory_note_pinned_ = false;
    bool memory_notes_loaded_ = false;
    int max_repairs_ = 2;
    int verification_chain_repair_limit_ = 3;
    int verification_chain_repairs_remaining_ = 0;
    int autopilot_rounds_completed_ = 0;
    int autopilot_min_rounds_ = 5;
    int autopilot_max_rounds_ = 50;
    int selected_change_ = 0;
    int selected_hunk_ = 0;
    int selected_checkpoint_index_ = -1;
    int selected_file_index_ = -1;
    int selected_media_job_index_ = -1;
    int selected_media_asset_index_ = -1;
    int selected_model_provider_index_ = -1;
    int selected_provider_blueprint_index_ = 0;
    int selected_project_scaffold_preset_index_ = 0;
    int selected_memory_note_index_ = -1;
    int selected_fallback_inspector_task_index_ = -1;
    int selected_media_kind_index_ = 0;
    int media_width_ = 1280;
    int media_height_ = 720;
    int media_fps_ = 12;
    float media_duration_seconds_ = 4.0f;
    double memory_note_confidence_ = 0.8;

    std::array<char, 8192> message_buffer_{};
    std::array<char, 256> search_buffer_{};
    std::array<char, 512> api_base_buffer_{};
    std::array<char, 512> core_api_base_buffer_{};
    std::array<char, 1024> backend_root_buffer_{};
    std::array<char, 128> backend_script_buffer_{};
    std::array<char, 256> assistant_name_buffer_{};
    std::array<char, 2048> assistant_mission_buffer_{};
    std::array<char, 1024> workspace_buffer_{};
    std::array<char, 128> model_api_buffer_{};
    std::array<char, 512> model_endpoint_buffer_{};
    std::array<char, 256> model_name_buffer_{};
    std::array<char, 2048> command_allowlist_buffer_{};
    std::array<char, 1024> validation_command_buffer_{};
    std::array<char, 256> validation_label_buffer_{};
    std::array<char, 1024> validation_notes_buffer_{};
    std::array<char, 256> command_palette_buffer_{};
    std::array<char, 256> conversation_search_buffer_{};
    std::array<char, 2048> project_scaffold_prompt_buffer_{};
    std::array<char, 256> project_scaffold_name_buffer_{};
    std::array<char, 1024> project_scaffold_target_buffer_{};
    std::array<char, 512> project_scaffold_install_buffer_{};
    std::array<char, 512> project_scaffold_validation_buffer_{};
    std::array<char, 128> login_user_buffer_{};
    std::array<char, 128> login_password_buffer_{};
    std::array<char, 128> provider_id_buffer_{};
    std::array<char, 256> provider_label_buffer_{};
    std::array<char, 128> provider_api_buffer_{};
    std::array<char, 512> provider_endpoint_buffer_{};
    std::array<char, 256> provider_model_buffer_{};
    std::array<char, 512> provider_aliases_buffer_{};
    std::array<char, 128> provider_secret_env_buffer_{};
    std::array<char, 512> provider_capabilities_buffer_{};
    std::array<char, 512> provider_roles_buffer_{};
    std::array<char, 128> provider_cost_tier_buffer_{};
    std::array<char, 128> provider_health_buffer_{};
    std::array<char, 1024> provider_notes_buffer_{};
    std::array<char, 256> memory_search_buffer_{};
    std::array<char, 256> memory_title_buffer_{};
    std::array<char, 128> memory_category_buffer_{};
    std::array<char, 4096> memory_content_buffer_{};
    std::array<char, 512> memory_tags_buffer_{};
    std::array<char, 1024> memory_related_files_buffer_{};
    std::array<char, 2048> media_prompt_buffer_{};
    std::array<char, 2048> media_feedback_buffer_{};
    std::array<char, 64> media_theme_buffer_{};
    std::array<char, 64> media_aspect_ratio_buffer_{};
    std::array<char, 512> media_style_buffer_{};
    std::array<char, 256> media_output_formats_buffer_{};
    std::string login_status_;
    std::string autopilot_goal_;
    std::vector<std::string> autopilot_suggestions_;

    void StartTask(const std::string& label, std::function<Completion()> work);
    void QueueStatusUpdate(const std::string& status);
    void DrainStatusUpdates();
    void QueueStreamDelta(const StreamDeltaInfo& delta);
    void DrainStreamDeltas();
    void QueueAgentActivity(
        const std::string& type,
        const std::string& message,
        const std::string& status = "running",
        const std::string& file_path = "",
        const std::string& command = "");
    void DrainAgentActivity();
    void QueueUserMessageForRetry(
        const std::string& content,
        const std::vector<FileContent>& attachments,
        const std::string& reason);
    void TrySendQueuedUserMessage();
    void TickModelBenchmarkPolling(std::chrono::steady_clock::time_point now);
    void HandleKeyboardShortcuts();
    void SyncStatusToast();
    void PushToast(const std::string& title, const std::string& message, const std::string& tone = "info", float duration = 4.2f);
    void AttemptLogin(bool demo_mode = false);
    void RefreshRuntime(bool allow_backend_start);
    void StartNewChat();
    void LoadConversationSnapshot();
    void SaveConversationSnapshot();
    void RefreshConversationLibrary();
    void LoadConversationFromLibrary(int index);
    void DeleteConversationFromLibrary(int index);
    void ToggleConversationPinned(int index);
    void ToggleConversationArchived(int index);
    void ExportConversationMarkdown();
    void CopyPatchToClipboard();
    void ExportPatchFile();
    void ExportVerificationReport();
    void OpenVerificationReportsFolder();
    void AttachVerificationReport(const std::string& path);
    void PruneVerificationReports(int keep_count = 25);
    void SaveDesktopSettingsFromUi();
    void SaveRemoteConfigFromUi();
    void SelectModelFromInventory(const ModelInfo& model);
    void RefreshModelManager();
    void RefreshModelBenchmarks();
    void RunQuickModelBenchmarks();
    void RunModelBenchmarkPreset(
        const std::string& label,
        const std::vector<std::string>& suite_ids,
        int max_models,
        double timeout_seconds,
        const std::vector<std::string>& provider_ids = {});
    void RunManagedModelBenchmark(const ManagedModelInfo& model);
    void CancelModelBenchmarkJob(const ModelBenchmarkJobInfo& job);
    void ApplyBenchmarkWinnersToRoutes();
    void ApplyRoutePolicyDiffToRoutes();
    void PullManagedModel(const ManagedModelInfo& model);
    void DeleteManagedModel(const ManagedModelInfo& model);
    void HydrateModelProviderBlueprint(int index);
    void HydrateModelProviderEditor(const ModelRegistryProviderInfo* provider, int index);
    void SaveModelProviderFromEditor();
    void DeleteSelectedModelProvider();
    void CreateModelRegistryCheckpoint();
    void LoadModelRegistryCheckpointDiff(const ModelRegistryCheckpointInfo& checkpoint);
    void RequestModelRegistryCheckpointRestore(const ModelRegistryCheckpointInfo& checkpoint);
    void RestoreModelRegistryCheckpoint(const ModelRegistryCheckpointInfo& checkpoint);
    void UseValidationSuggestion(const ValidationSuggestionInfo& suggestion);
    void RenderValidationSuggestionTable(
        const char* table_id,
        const std::vector<ValidationSuggestionInfo>& suggestions,
        int max_count);
    void SubmitMessage(const std::string& override_message = "", bool append_user_message = true);
    void BeginAutopilotSession(const std::string& goal);
    void RequestAutopilotWrapUp();
    void AdvanceAutopilotIfReady();
    void FinishAutopilotSession(const std::string& reason);
    void SubmitAutopilotPrompt(const std::string& prompt, bool apply, bool validate, const std::string& label);
    void StartAutopilotFromCurrentContext();
    const CommandRun* AutopilotCurrentFailure() const;
    bool AutopilotHasValidationFailure() const;
    bool AutopilotFailureLooksDependency() const;
    bool AutopilotHasCleanValidation() const;
    bool AutopilotRecentPassHadNoWork() const;
    bool AutopilotShouldContinueForQuality() const;
    std::string AutopilotQualityReason() const;
    std::string BuildAutopilotContinuationPrompt(const std::string& reason) const;
    std::string BuildAutopilotFinalPrompt(const std::string& reason) const;
    void RefreshAutopilotSuggestions();
    void PreviewComposerRoute();
    void RegenerateLastResponse();
    void CancelActiveResponse();
    void AttachSelectedFile();
    void RemoveAttachment(size_t index);
    void ApplyPendingChanges();
    void ApplySelectedChange();
    void ApplySelectedHunk();
    void RollbackLastApply();
    void RefreshCheckpoints();
    void RestoreCheckpointFromBrowser();
    void ValidateWorkspace();
    void VerifyWorkspace();
    void RepairLastValidationFailure(bool continue_until_clean = false);
    void TrackVerificationRepairActivity(
        const std::string& title,
        const std::string& detail,
        const std::string& status,
        const std::string& command = "");
    void RecordFeedback(
        const std::string& sentiment,
        const std::string& content,
        const std::string& context,
        const std::string& action = "manual",
        const std::string& target = "assistant_response",
        const std::string& model_label = "",
        const std::string& task_id = "");
    void RecordMessageFeedback(const ChatMessage& message, const std::string& sentiment);
    void RefreshMemoryNotes();
    void RefreshTelemetry();
    void HydrateMemoryEditor(const MemoryNoteInfo* note, int index);
    void SaveMemoryNoteFromEditor();
    void DeleteSelectedMemoryNote();
    void RefreshValidationProfile();
    void SaveValidationProfile(bool clear_profile = false);
    void RefreshWorkspaceProfile();
    void RefreshCoreDashboard();
    void RefreshAgentSupervision();
    void RefreshQualityGates();
    void StepAgentSupervisionWorkflow(const std::string& action, const std::string& task_id = "", bool approval = false);
    void StartCodingRoute(const std::string& route);
    void HydrateProjectBuilderDefaults();
    void RefreshProjectBuilderPresets();
    void PlanProjectFromPrompt();
    void PreviewProjectFromBuilder();
    void ScaffoldProjectFromBuilder();
    void UseScaffoldedProjectAsWorkspace();
    MediaGenerationOptions BuildMediaGenerationOptionsFromUi() const;
    void CreateMediaJob(const std::string& kind, const std::string& prompt, const std::string& feedback = "");
    void RefreshMediaJobs();
    void LoadMediaJob(const std::string& job_id, int index);
    void ExportSelectedMediaJob();
    void ExportCreativeAsset(const MediaAssetInfo& asset);
    const CreativePreviewTexture* GetCreativePreviewTexture(const MediaAssetInfo& asset);
    void ClearCreativeTextureCache();
    void OpenWorkspaceFile(const WorkspaceFile& file, int index);
    void OpenBackendFolder();

    void ApplyRuntimeSnapshot(const RuntimeSnapshot& snapshot);
    void HydrateConfigBuffers();
    void HydrateDesktopBuffers();
    AppConfig BuildConfigFromBuffers() const;
    DesktopSettings BuildDesktopSettingsFromBuffers() const;

    void RenderTopBar();
    void RenderRuntimeBanner();
    void RenderLogin();
    void RenderSetupLoading();
    void RenderLeftPanel();
    void RenderConversationSidebar();
    void RenderChatPanel();
    void RenderRightPanel();
    void RenderRuntimeStatusPanel();
    void RenderEcosystemDashboardCard();
    void RenderAgentSupervisionPanel();
    void RenderQualityGatePanel();
    void RenderAgentActivityPanel();
    void RenderResponseTab();
    void RenderChangesTab();
    void RenderRouteTimelineCard(const AgentResponse& response, bool preview_mode);
    void RenderWorkspaceTab();
    void RenderEventsTab();
    void RenderSettingsTab();
    void RenderValidationProfilePanel();
    void RenderVerificationResultPanel();
    void RenderSetupCheckModal();
    void RenderContextPreviewModal();
    void RenderConversationBrowserModal();
    void RenderMemoryCenterModal();
    void RenderPlanningHistoryModal();
    void RenderPolicyApplyConfirmModal();
    void RenderCheckpointBrowserModal();
    void RenderModelStackModal();
    void RenderRoadmapModal();
    void RenderCreativeStudioModal();
    void RenderCodingRoutesModal();
    void RenderProjectBuilderModal();
    void RenderCommandPaletteModal();
    void RenderToasts();
    void RenderMessage(const ChatMessage& message);

    bool ModeButton(const char* id, const char* label);
};

}
