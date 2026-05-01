#pragma once

#include "Platform.h"

#include <functional>
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

struct StreamDeltaInfo {
    std::string delta;
    std::string source;
    std::string preview_action = "append";
    int preview_attempt = 0;
    std::string provider_label;
    std::string provider_api;
    std::string model;
    std::string message;
};

struct ValidationProfileInfo {
    std::string workspace_root;
    ValidationRecipeInfo profile;
    bool has_profile = false;
    std::vector<ValidationSuggestionInfo> suggestions;
};

struct VerificationStepInfo {
    std::string id;
    std::string phase;
    std::string command;
    std::string label;
    std::string category;
    bool required = true;
    std::string reason;
    std::string status;
    CommandRun run;
    bool has_run = false;
};

struct VerificationResult {
    std::string task_id;
    std::string workspace_root;
    std::string status;
    std::vector<VerificationStepInfo> steps;
    std::vector<ToolEvent> events;
    ValidationRecipeInfo validation_profile;
    bool has_validation_profile = false;
    CommandRun first_failure;
    bool has_first_failure = false;
    std::vector<std::string> warnings;
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

struct RouteCandidateInfo {
    std::string candidate_id;
    std::string role;
    std::string provider_hint;
    std::vector<std::string> required_capabilities;
    std::string privacy_mode;
    std::string reason;
    double confidence = 0.0;
};

struct RoutingDecisionInfo {
    std::string task_role;
    std::string provider_hint;
    std::string privacy_mode;
    std::vector<RouteCandidateInfo> candidates;
    std::vector<std::string> fallback_roles;
    bool requires_tools = false;
    bool requires_workspace = false;
    std::string summary;
    double confidence = 0.0;
};

struct RouteProfileInfo {
    std::string id;
    std::string label;
    std::string category;
    std::string reason;
    std::vector<std::string> preferred_roles;
    std::vector<std::string> stack_keywords;
    std::vector<std::string> focus_paths;
};

struct TaskPlanInfo {
    std::string intent;
    std::string objective;
    std::string workflow;
    RouteProfileInfo route_profile;
    std::vector<std::string> steps;
    std::vector<std::string> context_requirements;
    std::vector<std::string> tool_requirements;
    std::vector<std::string> risks;
    std::vector<std::string> completion_criteria;
    RoutingDecisionInfo routing;
    bool has_routing = false;
};

struct ContextBudgetItemInfo {
    std::string kind;
    std::string ref;
    int estimated_tokens = 0;
    bool included = true;
    std::string reason;
};

struct ContextBudgetInfo {
    std::string intent;
    std::string route_role;
    std::string strategy;
    std::string privacy_mode = "local-first";
    int max_context_tokens = 0;
    int estimated_context_tokens = 0;
    int estimated_file_tokens = 0;
    int reserve_response_tokens = 0;
    int max_context_files = 0;
    int selected_file_count = 0;
    int workspace_file_count = 0;
    int selected_memory_count = 0;
    int selected_project_memory_count = 0;
    int omitted_file_count = 0;
    int omitted_memory_count = 0;
    int omitted_project_memory_count = 0;
    int max_file_chars = 0;
    int max_history_turns = 0;
    std::vector<std::string> notes;
    std::vector<ContextBudgetItemInfo> items;
};

struct ModelAttemptInfo {
    int attempt = 0;
    std::string role;
    std::string provider_id;
    std::string provider_label;
    std::string provider_api;
    std::string model;
    std::string endpoint;
    std::string privacy_mode = "local-first";
    std::string status = "planned";
    std::string reason;
    std::string error;
    bool retryable = true;
    int input_tokens = 0;
    bool has_input_tokens = false;
    int output_tokens = 0;
    bool has_output_tokens = false;
    double estimated_cost_usd = 0.0;
    bool has_estimated_cost = false;
    int latency_ms = 0;
    bool has_latency = false;
    std::string candidate_id;
    std::string candidate_source;
    std::string candidate_provider_hint;
    RouteProfileInfo route_profile;
    std::string token_estimator_source;
    std::string benchmark_suite;
    double benchmark_suite_score = 0.0;
    bool has_benchmark_suite_score = false;
    double benchmark_overall_score = 0.0;
    bool has_benchmark_overall_score = false;
    int benchmark_avg_latency_ms = 0;
    bool has_benchmark_avg_latency_ms = false;
    int benchmark_run_count = 0;
    std::string benchmark_recommendation;
    int route_health_attempts = 0;
    int route_health_terminal_attempts = 0;
    double route_health_success_rate = 0.0;
    bool has_route_health_success_rate = false;
    double route_health_failure_rate = 0.0;
    bool has_route_health_failure_rate = false;
    double route_health_penalty = 0.0;
    bool has_route_health_penalty = false;
    bool route_health_cooldown = false;
    std::string route_health_recommendation;
    int context_window = 0;
    bool has_context_window = false;
    double context_window_utilization = 0.0;
    bool has_context_window_utilization = false;
    int structured_preview_delta_count = 0;
    int structured_preview_char_count = 0;
    int structured_preview_reset_count = 0;
    bool structured_preview_emitted = false;
    bool structured_preview_retired = false;
    bool structured_preview_final_winner = false;
    std::string structured_preview_retired_reason;
};

struct ContextBudgetTelemetryEntryInfo {
    std::string task_id;
    std::string created_at;
    std::string workspace_root;
    std::string intent;
    std::string route_role;
    std::string strategy;
    std::string privacy_mode = "local-first";
    int max_context_tokens = 0;
    int estimated_context_tokens = 0;
    int estimated_file_tokens = 0;
    int reserve_response_tokens = 0;
    int selected_file_count = 0;
    int omitted_file_count = 0;
    ContextBudgetInfo payload;
};

struct ModelAttemptTelemetryEntryInfo {
    std::string task_id;
    std::string created_at;
    std::string workspace_root;
    ModelAttemptInfo attempt;
};

struct TelemetrySnapshot {
    std::string workspace_root;
    std::vector<ContextBudgetTelemetryEntryInfo> context_budgets;
    std::vector<ModelAttemptTelemetryEntryInfo> model_attempts;
};

struct RouteQualityOverviewInfo {
    int task_count = 0;
    int context_budget_count = 0;
    int model_attempt_count = 0;
    int succeeded_attempts = 0;
    int failed_attempts = 0;
    int planned_attempts = 0;
    int fallback_attempts = 0;
    int retryable_failures = 0;
    double success_rate = 0.0;
    double fallback_rate = 0.0;
    double estimated_cost_usd = 0.0;
    int input_tokens = 0;
    int output_tokens = 0;
    double average_latency_ms = 0.0;
    bool has_average_latency = false;
    double average_context_utilization = 0.0;
    bool has_average_context_utilization = false;
    double average_context_tokens = 0.0;
    double average_selected_files = 0.0;
    double average_omitted_files = 0.0;
    double reliability_score = 0.0;
    int feedback_count = 0;
    int positive_feedback = 0;
    int negative_feedback = 0;
    int revised_feedback = 0;
    int regenerated_feedback = 0;
    int applied_feedback = 0;
    int rolled_back_feedback = 0;
    int corrected_feedback = 0;
    double positive_feedback_rate = 0.0;
    double negative_feedback_rate = 0.0;
};

struct RouteQualityProviderRollupInfo {
    std::string provider_id;
    std::string provider_label;
    std::string provider_api;
    std::string model;
    int task_count = 0;
    int attempts = 0;
    int successes = 0;
    int failures = 0;
    int planned = 0;
    int fallback_attempts = 0;
    double success_rate = 0.0;
    double fallback_rate = 0.0;
    double estimated_cost_usd = 0.0;
    int input_tokens = 0;
    int output_tokens = 0;
    double average_latency_ms = 0.0;
    bool has_average_latency = false;
    double average_context_utilization = 0.0;
    bool has_average_context_utilization = false;
    std::vector<std::string> token_estimator_sources;
};

struct RouteQualityTokenCalibrationInfo {
    std::string provider_id;
    std::string provider_label;
    std::string provider_api;
    std::string model;
    int attempts = 0;
    int calibrated_attempts = 0;
    std::string calibration_status = "insufficient";
    int estimated_input_tokens = 0;
    int reported_input_tokens = 0;
    int estimated_output_tokens = 0;
    int reported_output_tokens = 0;
    double average_input_token_error = 0.0;
    bool has_average_input_token_error = false;
    double worst_input_token_error = 0.0;
    bool has_worst_input_token_error = false;
    double average_output_token_error = 0.0;
    bool has_average_output_token_error = false;
    double worst_output_token_error = 0.0;
    bool has_worst_output_token_error = false;
    std::vector<std::string> token_estimator_sources;
    std::vector<std::string> reported_token_sources;
    std::string recommendation;
};

struct RouteQualityTokenCalibrationTrendInfo {
    std::string provider_id;
    std::string provider_label;
    std::string provider_api;
    std::string model;
    std::string period_start;
    int attempts = 0;
    int calibrated_attempts = 0;
    std::string calibration_status = "insufficient";
    std::string trend_direction = "baseline";
    int estimated_input_tokens = 0;
    int reported_input_tokens = 0;
    int estimated_output_tokens = 0;
    int reported_output_tokens = 0;
    double average_input_token_error = 0.0;
    bool has_average_input_token_error = false;
    double worst_input_token_error = 0.0;
    bool has_worst_input_token_error = false;
    double average_output_token_error = 0.0;
    bool has_average_output_token_error = false;
    double worst_output_token_error = 0.0;
    bool has_worst_output_token_error = false;
    std::string recommendation;
};

struct RouteQualityStructuredPreviewInfo {
    std::string provider_id;
    std::string provider_label;
    std::string provider_api;
    std::string model;
    int attempts = 0;
    int previewed_attempts = 0;
    int final_winning_attempts = 0;
    int retired_attempts = 0;
    int reset_count = 0;
    int delta_count = 0;
    int char_count = 0;
    double preview_success_rate = 0.0;
    double retired_rate = 0.0;
    double average_preview_chars = 0.0;
    std::string preview_status = "insufficient";
    std::vector<std::string> retired_reasons;
    std::string recommendation;
};

struct RouteQualityRoleRollupInfo {
    std::string role;
    int task_count = 0;
    int attempts = 0;
    int successes = 0;
    int failures = 0;
    int planned = 0;
    int fallback_attempts = 0;
    double success_rate = 0.0;
    double estimated_cost_usd = 0.0;
    double average_latency_ms = 0.0;
    bool has_average_latency = false;
};

struct RouteHealthInfo {
    std::string provider_id;
    std::string provider_label;
    std::string model;
    std::string role;
    int attempts = 0;
    int terminal_attempts = 0;
    int successes = 0;
    int failures = 0;
    int fallback_attempts = 0;
    double success_rate = 0.0;
    double failure_rate = 0.0;
    double average_latency_ms = 0.0;
    bool has_average_latency = false;
    int structured_preview_attempts = 0;
    int structured_preview_retired_attempts = 0;
    int structured_preview_reset_count = 0;
    int structured_preview_final_winners = 0;
    double structured_preview_retired_rate = 0.0;
    double penalty = 0.0;
    bool cooldown = false;
    std::string latest_error;
    std::string latest_at;
    std::string recommendation;
};

struct RouteQualityContextRollupInfo {
    std::string route_role;
    std::string intent;
    int budget_count = 0;
    double average_context_tokens = 0.0;
    double average_file_tokens = 0.0;
    double average_reserved_response_tokens = 0.0;
    double average_selected_files = 0.0;
    double average_omitted_files = 0.0;
    double average_budget_utilization = 0.0;
    bool has_average_budget_utilization = false;
};

struct RouteQualityContextDrilldownInfo {
    std::string task_id;
    std::string created_at;
    std::string route_role;
    std::string intent;
    std::string strategy;
    std::string privacy_mode = "local-first";
    int max_context_tokens = 0;
    int estimated_context_tokens = 0;
    int estimated_file_tokens = 0;
    int reserve_response_tokens = 0;
    double utilization = 0.0;
    bool has_utilization = false;
    int selected_file_count = 0;
    int omitted_file_count = 0;
    int selected_memory_count = 0;
    int omitted_memory_count = 0;
    int selected_project_memory_count = 0;
    int omitted_project_memory_count = 0;
    std::vector<std::string> selected_refs;
    std::vector<std::string> omitted_refs;
    std::vector<std::string> largest_refs;
    std::vector<std::string> notes;
    std::vector<std::string> recommendations;
};

struct FeedbackAttributionRollupInfo {
    std::string dimension;
    std::string key;
    std::string label;
    int feedback_count = 0;
    int task_count = 0;
    int positive_count = 0;
    int negative_count = 0;
    int copied_count = 0;
    int revised_count = 0;
    int regenerated_count = 0;
    int applied_count = 0;
    int rolled_back_count = 0;
    int corrected_count = 0;
    double positive_rate = 0.0;
    double negative_rate = 0.0;
    std::string latest_at;
};

struct FeedbackTrendBucketInfo {
    std::string period_start;
    int feedback_count = 0;
    int positive_count = 0;
    int negative_count = 0;
    int copied_count = 0;
    int revised_count = 0;
    int regenerated_count = 0;
    int applied_count = 0;
    int rolled_back_count = 0;
    int corrected_count = 0;
    double positive_rate = 0.0;
    double negative_rate = 0.0;
};

struct FeedbackTelemetryEntryInfo {
    std::string id;
    std::string created_at;
    std::string task_id;
    std::string sentiment;
    std::string action;
    std::string target;
    std::string model_label;
    std::string route_role;
    std::string candidate_id;
    std::string content_hash;
    std::string context;
};

struct RouteQualitySnapshot {
    std::string workspace_root;
    int limit = 0;
    RouteQualityOverviewInfo overview;
    std::vector<RouteQualityProviderRollupInfo> providers;
    std::vector<RouteQualityTokenCalibrationInfo> token_calibration;
    std::vector<RouteQualityTokenCalibrationTrendInfo> token_calibration_trends;
    std::vector<RouteQualityStructuredPreviewInfo> structured_preview;
    std::vector<RouteQualityRoleRollupInfo> roles;
    std::vector<RouteQualityContextRollupInfo> contexts;
    std::vector<RouteQualityContextDrilldownInfo> context_drilldowns;
    std::vector<FeedbackAttributionRollupInfo> feedback_rollups;
    std::vector<FeedbackTrendBucketInfo> feedback_trends;
    std::vector<FeedbackTelemetryEntryInfo> feedback_events;
    std::vector<std::string> recommendations;
};

struct FallbackInspectorCandidateInfo {
    int index = 0;
    std::string candidate_id;
    std::string role;
    std::string provider_hint;
    std::vector<std::string> required_capabilities;
    std::string privacy_mode = "local-first";
    std::string reason;
    double confidence = 0.0;
    std::string status = "not-planned";
    int matched_attempt_number = 0;
    bool has_matched_attempt_number = false;
    std::string provider_id;
    std::string provider_label;
    std::string provider_api;
    std::string model;
    bool registry_resolved = false;
    bool has_registry_resolved = false;
    bool retryable = false;
    bool has_retryable = false;
    int input_tokens = 0;
    bool has_input_tokens = false;
    int output_tokens = 0;
    bool has_output_tokens = false;
    double estimated_cost_usd = 0.0;
    bool has_estimated_cost = false;
    int latency_ms = 0;
    bool has_latency = false;
    std::string token_estimator_source;
    int context_window = 0;
    bool has_context_window = false;
    double context_window_utilization = 0.0;
    bool has_context_window_utilization = false;
    std::string error;
};

struct FallbackInspectorTaskInfo {
    std::string task_id;
    std::string created_at;
    std::string finished_at;
    std::string mode;
    std::string workspace_root;
    std::string message;
    std::string status;
    TaskPlanInfo task_plan;
    bool has_task_plan = false;
    ContextBudgetTelemetryEntryInfo context_budget;
    bool has_context_budget = false;
    std::vector<ModelAttemptTelemetryEntryInfo> attempts;
    std::vector<FallbackInspectorCandidateInfo> candidates;
    std::vector<std::string> fallback_roles;
    std::string summary;
    std::vector<std::string> recommendations;
};

struct FallbackInspectorSnapshot {
    std::string workspace_root;
    int limit = 0;
    int task_count = 0;
    std::vector<FallbackInspectorTaskInfo> tasks;
    std::vector<std::string> recommendations;
};

struct RoutePolicyProviderProposalInfo {
    std::string provider_id;
    std::string provider_label;
    std::string provider_api;
    std::string model;
    int observed_rank = 0;
    int proposed_rank = 0;
    std::string action = "hold";
    std::string risk_level = "low";
    double confidence = 0.0;
    double score = 0.0;
    int attempts = 0;
    int successes = 0;
    int failures = 0;
    double fallback_rate = 0.0;
    double success_rate = 0.0;
    double positive_feedback_rate = 0.0;
    double negative_feedback_rate = 0.0;
    double average_latency_ms = 0.0;
    bool has_average_latency = false;
    double average_context_utilization = 0.0;
    bool has_average_context_utilization = false;
    double estimated_cost_usd = 0.0;
    std::vector<std::string> reasons;
    std::vector<std::string> risks;
};

struct RoutePolicyRoleProposalInfo {
    std::string role;
    std::string action = "keep";
    std::string observed_primary_provider;
    std::string proposed_primary_provider;
    double confidence = 0.0;
    int task_count = 0;
    int attempts = 0;
    double success_rate = 0.0;
    int fallback_attempts = 0;
    double score_delta = 0.0;
    std::vector<std::string> candidate_provider_ids;
    std::vector<std::string> reasons;
    std::vector<std::string> risks;
};

struct RoutePolicyDiffInfo {
    std::string workspace_root;
    std::string generated_at;
    int limit = 0;
    std::string source = "live";
    std::string source_snapshot_id;
    int source_snapshot_age_seconds = 0;
    bool source_snapshot_stale = false;
    int min_attempts = 3;
    std::vector<RoutePolicyProviderProposalInfo> provider_proposals;
    std::vector<RoutePolicyRoleProposalInfo> role_proposals;
    std::vector<std::string> recommendations;
    std::vector<std::string> warnings;
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
    bool router_execution_enabled = false;
    bool shared_workspace_mode = false;
    bool feedback_capture_excerpts = true;
    bool feedback_redaction_enabled = true;
    int feedback_max_excerpt_chars = 320;
    bool feedback_hash_content = true;
    bool env_exists = false;
};

struct ModelCapabilities {
    bool chat = true;
    bool code = false;
    bool debug = false;
    bool refactor = false;
    bool reasoning = false;
    bool research = false;
    bool streaming = false;
    bool structured_json = false;
    bool tools = false;
    bool vision = false;
    bool audio = false;
    bool embeddings = false;
    bool image = false;
    bool video = false;
    bool realtime = false;
    bool judge = false;
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
    std::string model_name;
    std::vector<std::string> model_aliases;
    std::string secret_env;
    bool local = true;
    bool enabled = true;
    bool configured = false;
    std::vector<std::string> capabilities;
    std::vector<std::string> roles;
    std::string cost_tier;
    int context_window = 0;
    int rate_limit_rpm = 0;
    double input_cost_per_million = 0.0;
    double output_cost_per_million = 0.0;
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

struct ModelRegistryAuditIssueInfo {
    std::string severity;
    std::string category;
    std::string provider_id;
    std::string role;
    std::string message;
    std::string recommendation;
};

struct ModelRegistrySetupActionInfo {
    std::string id;
    std::string kind;
    std::string priority;
    std::string title;
    std::string detail;
    std::string recommendation;
    std::string env_var;
    std::string role;
    std::vector<std::string> provider_ids;
    std::string command;
};

struct ModelRegistryRouteCoverageInfo {
    std::string role;
    std::string label;
    std::string status;
    std::string primary_model;
    std::string primary_provider_id;
    bool primary_configured = false;
    std::vector<std::string> required_capabilities;
    int eligible_provider_count = 0;
    int configured_provider_count = 0;
    int enabled_provider_count = 0;
    int fallback_configured_count = 0;
    std::vector<std::string> candidate_provider_ids;
    std::vector<std::string> recommendations;
};

struct ModelAdapterHealthInfo {
    std::string provider_id;
    std::string provider_label;
    std::string api;
    std::string endpoint;
    std::string model;
    bool local = true;
    bool enabled = true;
    bool configured = false;
    std::string status;
    std::string error_code;
    std::string message;
    std::string secret_env;
    bool secret_present = false;
    std::vector<std::string> capabilities;
    std::vector<std::string> roles;
    int recent_attempts = 0;
    int recent_successes = 0;
    int recent_failures = 0;
    int recent_skips = 0;
    int preflight_skips = 0;
    bool cooldown = false;
    std::string latest_error;
    std::string latest_at;
    std::string recommendation;
};

struct ModelTokenizerDiagnosticInfo {
    std::string provider_id;
    std::string provider_label;
    std::string api;
    std::string model;
    bool local = true;
    bool enabled = true;
    bool configured = false;
    int context_window = 0;
    bool has_context_window = false;
    std::string status = "unobserved";
    int recent_attempts = 0;
    int exact_attempts = 0;
    int profiled_attempts = 0;
    int heuristic_attempts = 0;
    int missing_attempts = 0;
    std::vector<std::string> estimator_sources;
    std::string primary_estimator_source;
    double average_context_utilization = 0.0;
    bool has_average_context_utilization = false;
    int calibrated_attempts = 0;
    double average_input_token_error = 0.0;
    bool has_average_input_token_error = false;
    double worst_input_token_error = 0.0;
    bool has_worst_input_token_error = false;
    double average_output_token_error = 0.0;
    bool has_average_output_token_error = false;
    double worst_output_token_error = 0.0;
    bool has_worst_output_token_error = false;
    std::vector<std::string> reported_token_sources;
    std::string calibration_status = "insufficient";
    std::string calibration_recommendation;
    std::string recommendation;
};

struct ModelRegistryAuditInfo {
    std::string generated_at;
    int readiness_score = 0;
    std::string status;
    int provider_count = 0;
    int enabled_provider_count = 0;
    int configured_provider_count = 0;
    int disabled_provider_count = 0;
    int local_provider_count = 0;
    int cloud_provider_count = 0;
    int role_count = 0;
    std::vector<ModelRegistryRouteCoverageInfo> route_coverages;
    std::vector<ModelRegistryAuditIssueInfo> issues;
    std::vector<ModelRegistrySetupActionInfo> setup_actions;
    std::vector<ModelAdapterHealthInfo> adapter_health;
    std::vector<ModelTokenizerDiagnosticInfo> tokenizer_diagnostics;
    std::vector<std::string> warnings;
    std::vector<std::string> recommendations;
};

struct ModelRegistryRoleDiffInfo {
    std::string role;
    std::string action = "keep";
    std::string current_primary_model;
    std::string proposed_primary_model;
    std::vector<std::string> current_fallback_models;
    std::vector<std::string> proposed_fallback_models;
    std::string winner_provider_id;
    std::string winner_provider_label;
    std::string winner_model;
    double winner_score = 0.0;
    double health_penalty = 0.0;
    bool health_cooldown = false;
    std::string health_recommendation;
    std::vector<std::string> reasons;
};

struct ModelRegistryBenchmarkPreviewInfo {
    bool applicable = false;
    std::string message;
    std::vector<ModelRegistryRoleDiffInfo> role_diffs;
    std::vector<std::string> warnings;
    std::vector<std::string> recommendations;
};

struct ModelRegistryCheckpointInfo {
    std::string id;
    std::string created_at;
    std::string reason;
    int provider_count = 0;
    int role_count = 0;
    bool router_enabled = false;
    std::string active_provider_id;
    std::string message;
    int restore_provider_add_count = 0;
    int restore_provider_remove_count = 0;
    int restore_provider_change_count = 0;
    int restore_role_add_count = 0;
    int restore_role_remove_count = 0;
    int restore_role_change_count = 0;
    int restore_settings_change_count = 0;
    int restore_total_change_count = 0;
    std::string restore_summary;
};

struct ModelRegistryCheckpointList {
    std::vector<ModelRegistryCheckpointInfo> checkpoints;
};

struct ModelRegistryCheckpointEntityDiffInfo {
    std::string id;
    std::string label;
    std::string action = "unchanged";
    std::string current_summary;
    std::string checkpoint_summary;
};

struct ModelRegistryCheckpointSettingDiffInfo {
    std::string key;
    std::string current_value;
    std::string checkpoint_value;
};

struct ModelRegistryCheckpointDiffInfo {
    ModelRegistryCheckpointInfo checkpoint;
    std::vector<ModelRegistryCheckpointEntityDiffInfo> provider_diffs;
    std::vector<ModelRegistryCheckpointEntityDiffInfo> role_diffs;
    std::vector<ModelRegistryCheckpointSettingDiffInfo> setting_diffs;
    std::vector<std::string> recommendations;
};

struct ModelDiskInfo {
    std::string drive_root;
    std::string project_root;
    std::string model_store_path;
    long long total_bytes = 0;
    long long used_bytes = 0;
    long long free_bytes = 0;
    long long model_store_bytes = 0;
    double free_percent = 0.0;
    bool low_space = false;
    long long minimum_free_bytes = 0;
};

struct ManagedModelInfo {
    std::string provider_id;
    std::string label;
    std::string api;
    std::string endpoint;
    std::string name;
    bool local = true;
    bool enabled = true;
    bool installed = false;
    bool configured = false;
    bool active = false;
    bool pullable = false;
    std::string health;
    std::vector<std::string> roles;
    std::vector<std::string> capabilities;
    long long size_bytes = 0;
    bool has_size_bytes = false;
    long long estimated_pull_bytes = 0;
    bool has_estimated_pull_bytes = false;
    std::string modified_at;
    std::string notes;
};

struct ModelOperationInfo {
    std::string id;
    std::string model_name;
    std::string action;
    std::string status;
    std::string message;
    int pid = 0;
    bool has_pid = false;
    std::string started_at;
    std::string finished_at;
    std::string stdout_log;
    std::string stderr_log;
    long long minimum_free_bytes = 0;
    long long estimated_pull_bytes = 0;
    bool has_estimated_pull_bytes = false;
    long long free_bytes_before = 0;
    bool has_free_bytes_before = false;
};

struct ModelPullLogSummaryInfo {
    std::string source;
    int total = 0;
    int pulled = 0;
    int skipped = 0;
    int failed = 0;
    std::string latest_at;
};

struct ModelManagerSnapshot {
    bool ok = false;
    std::string message;
    ModelDiskInfo disk;
    std::string active_model;
    std::string active_provider_id;
    int providers_total = 0;
    int local_total = 0;
    int installed_total = 0;
    int pullable_total = 0;
    int cloud_total = 0;
    std::vector<ManagedModelInfo> models;
    std::vector<ModelOperationInfo> operations;
    std::vector<ModelPullLogSummaryInfo> pull_logs;
};

struct ModelBenchmarkSuiteInfo {
    std::string id;
    std::string label;
    std::string description;
};

struct ModelBenchmarkResultInfo {
    std::string id;
    std::string created_at;
    std::string provider_id;
    std::string provider_label;
    std::string api;
    std::string endpoint;
    std::string model_name;
    std::string suite_id;
    std::string suite_label;
    std::string status;
    double score = 0.0;
    int latency_ms = 0;
    bool has_latency_ms = false;
    std::string error;
    std::string answer_excerpt;
    std::string expected;
};

struct ModelBenchmarkProviderScoreInfo {
    std::string provider_id;
    std::string provider_label;
    std::string api;
    std::string model_name;
    bool local = true;
    bool enabled = true;
    bool configured = false;
    double overall_score = 0.0;
    double chat_score = 0.0;
    bool has_chat_score = false;
    double code_score = 0.0;
    bool has_code_score = false;
    double reasoning_score = 0.0;
    bool has_reasoning_score = false;
    int avg_latency_ms = 0;
    bool has_avg_latency_ms = false;
    int run_count = 0;
    std::string latest_at;
    std::string recommendation;
};

struct ModelBenchmarkSuiteSummaryInfo {
    std::string suite_id;
    std::string suite_label;
    std::string best_provider_id;
    std::string best_provider_label;
    std::string best_model_name;
    double best_score = 0.0;
    int best_latency_ms = 0;
    bool has_best_latency_ms = false;
    int run_count = 0;
};

struct ModelBenchmarkJobInfo {
    std::string id;
    std::string status;
    std::string message;
    std::string created_at;
    std::string started_at;
    std::string finished_at;
    std::vector<std::string> suite_ids;
    std::vector<std::string> provider_ids;
    int max_models = 0;
    bool local_only = true;
    double timeout_seconds = 45.0;
    int total_runs = 0;
    int completed_runs = 0;
    int failed_runs = 0;
    std::string current_provider_id;
    std::string current_model_name;
    std::string current_suite_id;
    std::string error;
};

struct ModelBenchmarkSnapshot {
    bool ok = false;
    std::string message;
    std::vector<ModelBenchmarkSuiteInfo> suites;
    std::vector<ModelBenchmarkProviderScoreInfo> provider_scores;
    std::vector<ModelBenchmarkSuiteSummaryInfo> suite_summaries;
    std::vector<ModelBenchmarkResultInfo> recent_results;
    std::vector<ModelBenchmarkJobInfo> jobs;
    std::vector<std::string> recommendations;
    int results_total = 0;
    std::string latest_at;
};

struct HealthStatus {
    bool ok = false;
    bool ready = false;
    std::string status;
    std::string app;
    std::string version;
    std::string engine;
    bool engine_ready = false;
    std::string engine_message;
    std::string model_name;
    std::string model_api;
    std::string model_endpoint;
    bool model_ready = false;
    std::string model_message;
    std::string project_root;
    std::string workspace_root;
    std::string database_path;
    bool env_exists = false;
    bool router_execution_enabled = false;
    bool router_enabled = false;
    bool fallback_supported = false;
    int provider_count = 0;
    int configured_provider_count = 0;
    int enabled_provider_count = 0;
    int role_count = 0;
    std::vector<std::string> recommendations;
};

struct WorkspaceProjectManifestInfo {
    std::string schema;
    std::string project_name;
    std::string title;
    std::string preset_id;
    std::string preset_label;
    std::string framework;
    std::string language;
    std::string package_manager;
    std::string install_command;
    std::string validation_command;
    std::vector<std::string> tags;
    std::string generated_by;
    std::string handoff_goal;
    std::vector<std::string> first_pass;
    std::vector<std::string> safety;
};

struct WorkspaceDependencyInfo {
    std::string name;
    std::string version;
    std::string source;
    std::string group;
};

struct WorkspaceScriptInfo {
    std::string name;
    std::string command;
    std::string source;
};

struct WorkspaceDependencyProfileInfo {
    std::string project_type;
    std::vector<std::string> languages;
    std::vector<std::string> frameworks;
    std::vector<std::string> package_managers;
    std::vector<std::string> build_systems;
    std::vector<std::string> config_files;
    std::vector<std::string> entry_points;
    std::vector<std::string> test_files;
    std::vector<std::string> install_commands;
    std::vector<std::string> validation_commands;
    std::vector<WorkspaceScriptInfo> scripts;
    std::vector<WorkspaceDependencyInfo> dependencies;
    std::vector<WorkspaceDependencyInfo> dev_dependencies;
    std::vector<std::string> database_tools;
    std::vector<std::string> warnings;
};

struct WorkspaceInstructionStatusFileInfo {
    std::string path;
    std::string title;
    std::string kind;
    double score = 0.0;
    int open_items = 0;
    int completed_items = 0;
    int total_items = 0;
    std::vector<std::string> pending_items;
    std::string summary;
};

struct WorkspaceInstructionStatusInfo {
    std::string schema;
    std::string updated_at;
    std::string source_message;
    int instruction_file_count = 0;
    int open_items = 0;
    int completed_items = 0;
    int total_items = 0;
    std::vector<WorkspaceInstructionStatusFileInfo> files;
    std::string validation_status;
    std::string validation_command;
    std::string validation_summary;
    std::string completion_status;
    double completion_score = 0.0;
    bool has_completion_score = false;
    bool should_continue = false;
    std::vector<std::string> completion_reasons;
    std::vector<std::string> completion_next_actions;
    std::vector<std::string> applied;
    std::string recommendation;
};

struct WorkspaceValidationPlanStepInfo {
    std::string id;
    std::string phase;
    std::string command;
    std::string label;
    bool required = true;
    std::string source_command;
    int chain_index = 0;
    int chain_total = 0;
};

struct WorkspaceValidationPlanInfo {
    std::string schema;
    std::string updated_at;
    std::string project_name;
    std::string preset_id;
    std::string preset_label;
    std::string install_command;
    std::string validation_command;
    std::vector<WorkspaceValidationPlanStepInfo> steps;
    std::string last_run_status;
    std::string last_run_command;
    std::string last_run_summary;
    std::string last_run_failed_step;
    std::string last_run_build_log_path;
    std::vector<std::string> notes;
};

struct WorkspaceReadinessInfo {
    std::string status;
    int score = 0;
    std::string summary;
    std::string next_action;
    std::vector<std::string> blockers;
    std::vector<std::string> signals;
};

struct WorkspaceProfileInfo {
    std::string workspace_root;
    bool has_manifest = false;
    WorkspaceProjectManifestInfo manifest;
    WorkspaceDependencyProfileInfo dependency_profile;
    bool has_instruction_status = false;
    WorkspaceInstructionStatusInfo instruction_status;
    bool has_validation_plan = false;
    WorkspaceValidationPlanInfo validation_plan;
    WorkspaceReadinessInfo readiness;
    std::vector<std::string> recommendations;
};

struct WorkspaceAutopilotStatusInfo {
    std::string workspace_root;
    std::string phase = "unconfigured";
    bool should_continue = false;
    std::string recommended_mode = "build";
    std::string suggested_prompt;
    std::string next_action;
    std::string stop_reason;
    int pass_budget = 0;
    bool run_validation = false;
    int max_repair_attempts = 0;
    WorkspaceReadinessInfo readiness;
    int open_items = 0;
    int completed_items = 0;
    int total_items = 0;
    std::string validation_command;
    std::string latest_validation_status;
    std::string failed_step;
    std::string failed_step_command;
    std::string first_diagnostic;
    std::string repair_brief;
    std::vector<std::string> blockers;
    std::vector<std::string> signals;
    std::vector<std::string> recommendations;
    std::vector<WorkspaceInstructionStatusFileInfo> instruction_files;
    std::vector<std::string> next_open_items;
    std::string instruction_source;
};

struct RuntimeSnapshot {
    bool ok = false;
    HealthStatus health;
    AppConfig config;
    std::vector<WorkspaceFile> files;
    std::vector<TaskSummary> recent_tasks;
    ModelInventory model_inventory;
    ModelRegistrySnapshot model_registry;
    ModelRegistryAuditInfo model_registry_audit;
    bool has_model_registry_audit = false;
    std::string model_registry_audit_error;
    ModelManagerSnapshot model_manager;
    ModelBenchmarkSnapshot model_benchmarks;
    ModelRegistryBenchmarkPreviewInfo route_apply_preview;
    bool has_route_apply_preview = false;
    std::string route_apply_preview_error;
    ModelRegistryCheckpointList model_registry_checkpoints;
    bool has_model_registry_checkpoints = false;
    std::string model_registry_checkpoints_error;
    WorkspaceProfileInfo workspace_profile;
    bool has_workspace_profile = false;
    std::string workspace_profile_error;
    WorkspaceAutopilotStatusInfo workspace_autopilot_status;
    bool has_workspace_autopilot_status = false;
    std::string workspace_autopilot_status_error;
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

struct CompletionQualityInfo {
    std::string status = "unknown";
    double score = 0.0;
    std::vector<std::string> reasons;
    std::vector<std::string> next_actions;
    bool should_continue = false;
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
    TaskPlanInfo task_plan;
    bool has_task_plan = false;
    ContextBudgetInfo context_budget;
    bool has_context_budget = false;
    std::vector<ModelAttemptInfo> model_attempts;
    std::string assistant_name;
    std::string mode;
    std::string engine;
    std::string registry_message;
    std::string benchmark_message;
    std::vector<std::string> routing_recommendations;
    std::string workspace_root;
    std::vector<WorkspaceFile> workspace_files;
    std::vector<WorkspaceFile> context_files;
    std::vector<TaskSummary> recent_tasks;
    std::vector<RepairAttemptInfo> repair_attempts;
    CompletionQualityInfo completion_quality;
};

struct ApplyResult {
    std::vector<std::string> applied;
    std::vector<std::string> warnings;
    std::string checkpoint;
    std::string workspace_root;
    std::vector<WorkspaceFile> workspace_files;
};

struct ProjectScaffoldPresetInfo {
    std::string id;
    std::string label;
    std::string framework;
    std::string language;
    std::string package_manager;
    std::string install_command;
    std::string validation_command;
    std::string description;
    std::vector<std::string> tags;
};

struct ProjectScaffoldFileInfo {
    std::string path;
    std::string action;
    std::string summary;
    long long size = 0;
};

struct ProjectBuildStageInfo {
    std::string id;
    std::string label;
    std::string status;
    std::string detail;
    std::string command;
    std::string output_excerpt;
    std::string error;
};

struct ProjectScaffoldResult {
    bool ok = false;
    std::string message;
    std::string execution_mode;
    std::string primary_action;
    std::string target_path;
    ProjectScaffoldPresetInfo preset;
    std::vector<std::string> plan_steps;
    std::vector<std::string> risk_warnings;
    std::vector<std::string> diff_summary;
    std::vector<std::string> memory_paths;
    std::vector<ProjectScaffoldFileInfo> files;
    int file_change_count = 0;
    std::vector<std::string> applied;
    std::vector<std::string> warnings;
    std::string checkpoint;
    std::string install_command;
    std::string validation_command;
    std::string roadmap_path;
    std::string build_log_path;
    std::vector<ProjectBuildStageInfo> stages;
    CommandRun validation;
    bool has_validation = false;
    std::vector<std::string> next_steps;
    std::vector<WorkspaceFile> workspace_files;
};

struct ProjectScaffoldPlanResult {
    bool ok = false;
    std::string message;
    std::string prompt;
    std::string execution_mode;
    std::string primary_action;
    double confidence = 0.0;
    ProjectScaffoldPresetInfo preset;
    std::string project_name;
    std::string target_path;
    std::string install_command;
    std::string validation_command;
    bool overwrite = false;
    bool include_gitignore = true;
    std::vector<std::string> plan_steps;
    std::vector<std::string> risk_warnings;
    std::vector<std::string> reasons;
    std::vector<std::string> assumptions;
    std::vector<std::string> detected_keywords;
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
    ModelRegistryAuditInfo GetModelRegistryAudit(const std::string& workspace_root = "");
    ModelManagerSnapshot GetModelManager(double minimum_free_gb = 24.0);
    ModelBenchmarkSnapshot GetModelBenchmarks();
    ModelBenchmarkSnapshot RunModelBenchmarks(
        const std::vector<std::string>& suite_ids = {},
        int max_models = 4,
        bool local_only = true,
        double timeout_seconds = 45.0,
        const std::vector<std::string>& provider_ids = {});
    ModelBenchmarkJobInfo StartModelBenchmarkJob(
        const std::vector<std::string>& suite_ids = {},
        int max_models = 4,
        bool local_only = true,
        double timeout_seconds = 45.0,
        const std::vector<std::string>& provider_ids = {});
    ModelBenchmarkJobInfo CancelModelBenchmarkJob(const std::string& job_id);
    ModelOperationInfo PullModel(const std::string& model_name, double minimum_free_gb = 24.0);
    ModelOperationInfo DeleteLocalModel(const std::string& model_name);
    ModelRegistryBenchmarkPreviewInfo GetBenchmarkRoutePreview(const std::string& workspace_root = "");
    ModelRegistryCheckpointList GetModelRegistryCheckpoints(int limit = 20);
    ModelRegistryCheckpointInfo CreateModelRegistryCheckpoint(const std::string& reason = "");
    ModelRegistryCheckpointDiffInfo GetModelRegistryCheckpointDiff(const std::string& checkpoint_id);
    ModelRegistrySnapshot RestoreModelRegistryCheckpoint(const std::string& checkpoint_id);
    ModelRegistrySnapshot ApplyBenchmarkWinnersToRegistry(const std::string& workspace_root = "");
    ModelRegistrySnapshot ApplyRoutePolicyDiffToRegistry(
        const std::string& workspace_root = "",
        int limit = 200,
        int min_attempts = 3,
        double min_confidence = 0.55,
        bool allow_high_risk = false);
    ModelRegistrySnapshot SaveModelRegistryProvider(const ModelRegistryProviderInfo& provider);
    ModelRegistrySnapshot DeleteModelRegistryProvider(const std::string& provider_id);
    AppConfig SaveConfig(const AppConfig& config);
    WorkspaceProfileInfo GetWorkspaceProfile(const std::string& workspace_root);
    WorkspaceAutopilotStatusInfo GetWorkspaceAutopilotStatus(const std::string& workspace_root);
    std::vector<WorkspaceFile> ListFiles(const std::string& workspace_root, int max_files, std::string* resolved_root = nullptr);
    std::vector<TaskSummary> GetHistory(const std::string& workspace_root, int limit);
    TelemetrySnapshot GetTelemetry(const std::string& workspace_root, int limit = 20);
    RouteQualitySnapshot GetRouteQuality(const std::string& workspace_root, int limit = 200);
    std::vector<RouteHealthInfo> GetRouteHealth(const std::string& workspace_root, int limit = 200);
    FallbackInspectorSnapshot GetFallbackInspector(const std::string& workspace_root, int limit = 20);
    RoutePolicyDiffInfo GetRoutePolicyDiff(const std::string& workspace_root, int limit = 200, int min_attempts = 3);
    AgentResponse SendMessage(
        const std::string& message,
        const std::vector<ChatMessage>& history,
        const std::string& workspace_root,
        const std::string& mode,
        bool apply_changes,
        bool run_validation,
        int max_repair_attempts,
        const std::string& validation_command_override = "",
        const std::string& validation_label_override = "",
        const std::string& validation_notes_override = "");
    AgentResponse SendMessageStream(
        const std::string& message,
        const std::vector<ChatMessage>& history,
        const std::string& workspace_root,
        const std::string& mode,
        bool apply_changes,
        bool run_validation,
        int max_repair_attempts,
        const std::function<void(const std::string&)>& on_status,
        const std::string& validation_command_override = "",
        const std::string& validation_label_override = "",
        const std::string& validation_notes_override = "",
        const std::function<void(const StreamDeltaInfo&)>& on_delta = {});
    AgentResponse PreviewRoute(
        const std::string& message,
        const std::vector<ChatMessage>& history,
        const std::string& workspace_root,
        const std::string& mode);
    ApplyResult ApplyChanges(const std::string& workspace_root, const std::vector<FileChange>& changes);
    std::vector<ProjectScaffoldPresetInfo> GetProjectScaffoldPresets();
    ProjectScaffoldPlanResult PlanProjectScaffold(
        const std::string& prompt,
        const std::string& workspace_root,
        const std::string& preferred_target_path = "");
    ProjectScaffoldResult PreviewProjectScaffold(
        const std::string& target_path,
        const std::string& preset_id,
        const std::string& project_name,
        const std::string& install_command,
        const std::string& validation_command,
        bool overwrite,
        bool include_gitignore,
        const std::string& prompt = "",
        bool run_install = false,
        bool run_validation = false,
        int max_repair_attempts = 1);
    ProjectScaffoldResult ScaffoldProject(
        const std::string& target_path,
        const std::string& preset_id,
        const std::string& project_name,
        const std::string& install_command,
        const std::string& validation_command,
        bool overwrite,
        bool include_gitignore,
        const std::string& prompt = "",
        bool run_install = false,
        bool run_validation = false,
        int max_repair_attempts = 1);
    RestoreResult RestoreCheckpoint(const std::string& workspace_root, const std::string& checkpoint);
    CheckpointListResult ListCheckpoints(const std::string& workspace_root, int limit = 50);
    AgentResponse ValidateWorkspace(const std::string& workspace_root);
    VerificationResult VerifyWorkspace(
        const std::string& workspace_root,
        bool include_install = false,
        bool continue_on_failure = false,
        int max_steps = 8);
    void RecordFeedback(
        const std::string& workspace_root,
        const std::string& sentiment,
        const std::string& content,
        const std::string& context,
        const std::string& task_id = "",
        const std::string& action = "manual",
        const std::string& target = "assistant_response",
        const std::string& model_label = "",
        const std::string& route_role = "",
        const std::string& candidate_id = "");
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
