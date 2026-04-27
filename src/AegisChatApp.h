#pragma once

#include "AegisClient.h"

#include <array>
#include <atomic>
#include <chrono>
#include <future>
#include <functional>
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
    ModelRegistrySnapshot model_registry_;
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
    std::unordered_map<std::string, CreativePreviewTexture> creative_texture_cache_;
    AgentResponse last_response_;
    bool has_response_ = false;
    FileContent selected_file_;
    bool has_selected_file_ = false;
    ValidationProfileInfo validation_profile_;
    bool has_validation_profile_snapshot_ = false;
    CheckpointListResult checkpoints_;
    std::vector<MediaJobSummary> media_jobs_;
    MediaJobSummary selected_media_job_;
    bool has_selected_media_job_ = false;

    std::future<Completion> active_task_;
    std::atomic_bool busy_ = false;
    std::string busy_label_;
    std::string status_;
    std::chrono::steady_clock::time_point next_health_check_{};
    std::chrono::steady_clock::time_point setup_started_{};
    std::chrono::steady_clock::time_point smoke_auto_login_at_{};
    float dashboard_reveal_time_ = 0.0f;

    std::string workspace_root_;
    std::string mode_ = "build";
    std::string current_conversation_id_;
    std::string current_conversation_title_;
    std::string last_media_job_id_;
    std::string last_media_kind_;
    std::string playing_audio_path_;
    std::string pending_popup_;
    std::string last_toast_status_;
    bool apply_changes_ = true;
    bool run_validation_ = false;
    bool auto_scroll_ = true;
    bool command_palette_focus_ = false;
    bool smoke_auto_login_ = false;
    bool smoke_auto_login_done_ = false;
    bool setup_check_auto_opened_ = false;
    bool cancel_response_requested_ = false;
    bool current_conversation_pinned_ = false;
    bool current_conversation_archived_ = false;
    bool show_archived_conversations_ = false;
    bool show_model_provider_editor_ = false;
    bool model_provider_local_ = true;
    bool model_provider_enabled_ = true;
    bool model_provider_configured_ = false;
    bool memory_note_pinned_ = false;
    bool memory_notes_loaded_ = false;
    int max_repairs_ = 1;
    int selected_change_ = 0;
    int selected_hunk_ = 0;
    int selected_checkpoint_index_ = -1;
    int selected_file_index_ = -1;
    int selected_media_job_index_ = -1;
    int selected_media_asset_index_ = -1;
    int selected_model_provider_index_ = -1;
    int selected_memory_note_index_ = -1;
    int selected_media_kind_index_ = 0;
    int media_width_ = 1280;
    int media_height_ = 720;
    int media_fps_ = 12;
    float media_duration_seconds_ = 4.0f;
    double memory_note_confidence_ = 0.8;

    std::array<char, 8192> message_buffer_{};
    std::array<char, 256> search_buffer_{};
    std::array<char, 512> api_base_buffer_{};
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
    std::array<char, 128> login_user_buffer_{};
    std::array<char, 128> login_password_buffer_{};
    std::array<char, 128> provider_id_buffer_{};
    std::array<char, 256> provider_label_buffer_{};
    std::array<char, 128> provider_api_buffer_{};
    std::array<char, 512> provider_endpoint_buffer_{};
    std::array<char, 512> provider_capabilities_buffer_{};
    std::array<char, 512> provider_roles_buffer_{};
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

    void StartTask(const std::string& label, std::function<Completion()> work);
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
    void SaveDesktopSettingsFromUi();
    void SaveRemoteConfigFromUi();
    void SelectModelFromInventory(const ModelInfo& model);
    void HydrateModelProviderEditor(const ModelRegistryProviderInfo* provider, int index);
    void SaveModelProviderFromEditor();
    void DeleteSelectedModelProvider();
    void UseValidationSuggestion(const ValidationSuggestionInfo& suggestion);
    void RenderValidationSuggestionTable(
        const char* table_id,
        const std::vector<ValidationSuggestionInfo>& suggestions,
        int max_count);
    void SubmitMessage(const std::string& override_message = "", bool append_user_message = true);
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
    void RepairLastValidationFailure();
    void RecordFeedback(const std::string& sentiment, const std::string& content, const std::string& context);
    void RecordMessageFeedback(const ChatMessage& message, const std::string& sentiment);
    void RefreshMemoryNotes();
    void HydrateMemoryEditor(const MemoryNoteInfo* note, int index);
    void SaveMemoryNoteFromEditor();
    void DeleteSelectedMemoryNote();
    void RefreshValidationProfile();
    void SaveValidationProfile(bool clear_profile = false);
    void StartCodingRoute(const std::string& route);
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
    void RenderChatPanel();
    void RenderRightPanel();
    void RenderResponseTab();
    void RenderChangesTab();
    void RenderWorkspaceTab();
    void RenderEventsTab();
    void RenderSettingsTab();
    void RenderValidationProfilePanel();
    void RenderSetupCheckModal();
    void RenderContextPreviewModal();
    void RenderConversationBrowserModal();
    void RenderMemoryCenterModal();
    void RenderCheckpointBrowserModal();
    void RenderModelStackModal();
    void RenderRoadmapModal();
    void RenderCreativeStudioModal();
    void RenderCodingRoutesModal();
    void RenderCommandPaletteModal();
    void RenderToasts();
    void RenderMessage(const ChatMessage& message);

    bool ModeButton(const char* id, const char* label);
};

}
