// frontend/src/types.ts
export type Role = 'user' | 'assistant' | 'system';
export type Mode = 'build' | 'develop' | 'review' | 'chat';
export type ChangeAction = 'create' | 'update' | 'append' | 'delete';
export type EventStatus = 'ok' | 'warning' | 'error';

export interface ChatMessage {
  role: Role;
  content: string;
  metadata?: ChatMessageMetadata;
}

export interface ChatMessageMetadata {
  generatedChanges?: FileChange[];
  applied?: string[];
  warnings?: string[];
  checkpoint?: string | null;
  workspaceRoot?: string;
  taskId?: string;
}

export interface ModeOption {
  id: Mode;
  label: string;
  description: string;
}

export interface WorkspaceFile {
  path: string;
  size: number;
  kind: string;
}

export interface CommandRun {
  command: string;
  cwd: string;
  allowed: boolean;
  exit_code: number | null;
  stdout: string;
  stderr: string;
  timed_out: boolean;
  reason: string;
  category: string;
  summary: string;
}

export interface ToolEvent {
  kind: string;
  title: string;
  status: EventStatus;
  detail: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface RouteCandidateInfo {
  role: string;
  provider_hint: string;
  required_capabilities: string[];
  privacy_mode: string;
  reason: string;
  confidence: number;
  candidate_id: string;
}

export interface RoutingDecisionInfo {
  task_role: string;
  privacy_mode: string;
  candidates: RouteCandidateInfo[];
  fallback_roles: string[];
  requires_tools: boolean;
  requires_workspace: boolean;
  summary: string;
  confidence: number;
}

export interface TaskPlanInfo {
  intent: string;
  objective: string;
  workflow: string;
  complexity: 'focused' | 'standard' | 'large' | 'epic' | string;
  estimated_slices: number;
  pass_budget_hint: number;
  large_task_protocol: string[];
  decomposition_axes: string[];
  route_profile: Record<string, unknown>;
  steps: string[];
  context_requirements: string[];
  tool_requirements: string[];
  risks: string[];
  completion_criteria: string[];
  routing: RoutingDecisionInfo | null;
}

export interface ContextBudgetItemInfo {
  kind: string;
  ref: string;
  estimated_tokens: number;
  included: boolean;
  reason: string;
}

export interface ContextBudgetInfo {
  intent: string;
  route_role: string;
  strategy: string;
  privacy_mode: string;
  max_context_tokens: number;
  estimated_context_tokens: number;
  estimated_file_tokens: number;
  reserve_response_tokens: number;
  max_context_files: number;
  selected_file_count: number;
  workspace_file_count: number;
  selected_memory_count: number;
  selected_project_memory_count: number;
  omitted_file_count: number;
  omitted_memory_count: number;
  omitted_project_memory_count: number;
  max_file_chars: number;
  max_history_turns: number;
  notes: string[];
  items: ContextBudgetItemInfo[];
}

export interface CompletionQualityInfo {
  status: 'unknown' | 'needs_work' | 'ready' | 'blocked';
  score: number;
  reasons: string[];
  next_actions: string[];
  should_continue: boolean;
}

export interface TaskSummary {
  id: string;
  created_at: string;
  finished_at: string | null;
  mode: string;
  workspace_root: string;
  message: string;
  status: string;
}

export interface FixMemoryEntry {
  id: string;
  created_at: string;
  project_root: string;
  error_signature: string;
  fix_summary: string;
  evidence: string;
  confidence: number;
  category: string;
}

export interface ProjectMemoryEntry {
  id: string;
  created_at: string;
  updated_at: string;
  project_root: string;
  category: string;
  title: string;
  detail: string;
  source: string;
  confidence: number;
}

export type MemoryNoteCategory = 'fix' | 'pattern' | 'insight' | 'bug' | 'feature';

export interface MemoryNoteResponse {
  id: string;
  title: string;
  content: string;
  category: MemoryNoteCategory | string;
  created_at: string;
  updated_at: string;
  pinned: boolean;
  tags: string[];
  related_files: string[];
  confidence: number;
}

export interface CreateMemoryNoteRequest {
  title: string;
  content: string;
  category: MemoryNoteCategory | string;
  tags?: string[];
  related_files?: string[];
  pinned?: boolean;
  confidence?: number;
}

export interface RepairAttempt {
  attempt: number;
  category: string;
  before_signature: string;
  after_signature: string;
  outcome: string;
  checkpoint: string | null;
  summary: string;
  created_at: string;
}

export interface FileChange {
  action: ChangeAction;
  path: string;
  content: string | null;
  summary: string;
}

export interface AgentRequest {
  message: string;
  history: ChatMessage[];
  workspace_root?: string;
  mode?: Mode;
  apply_changes: boolean;
  run_validation: boolean;
  max_repair_attempts?: number;
  max_files?: number;
  context_paths?: string[];
}

export interface AgentResponse {
  task_id: string;
  reply: string;
  plan: string[];
  changes: FileChange[];
  applied: string[];
  checkpoint?: string | null;
  warnings: string[];
  events: ToolEvent[];
  validation: CommandRun | null;
  validation_profile: ValidationRecipe | null;
  task_plan?: TaskPlanInfo | null;
  context_budget?: ContextBudgetInfo | null;
  model_attempts?: Array<Record<string, unknown>>;
  assistant_name: string;
  mode: Mode;
  engine: string;
  workspace_root: string;
  workspace_files: WorkspaceFile[];
  context_files: WorkspaceFile[];
  memory_hits: FixMemoryEntry[];
  project_memory_hits: ProjectMemoryEntry[];
  recent_tasks: TaskSummary[];
  repair_attempts: RepairAttempt[];
  completion_quality?: CompletionQualityInfo | null;
}

export interface ChatStreamEventInfo {
  event: string;
  payload: string;
  description: string;
}

export interface ChatStreamContractResponse {
  schema_version: string;
  transport: string;
  endpoint: string;
  method: string;
  content_type: string;
  event_order: string[];
  events: ChatStreamEventInfo[];
  recommendations: string[];
}

export type ChatStreamEventName = 'meta' | 'status' | 'delta' | 'final' | 'error' | 'done';

export interface ChatStreamPayload {
  type: ChatStreamEventName | string;
  schema_version?: string;
  stream_mode?: string;
  workspace_root?: string;
  mode?: string;
  stage?: string;
  message?: string;
  delta?: string;
  source?: string;
  preview_action?: 'append' | 'reset' | string;
  preview_attempt?: number;
  provider_label?: string;
  provider_api?: string;
  model?: string;
  detail?: string;
  task_id?: string;
  response?: AgentResponse;
}

export interface ApplyRequest {
  workspace_root?: string;
  changes: FileChange[];
}

export interface ApplyResponse {
  applied: string[];
  warnings: string[];
  checkpoint: string | null;
  workspace_root: string;
  workspace_files: WorkspaceFile[];
}

export interface CheckpointFileInfo {
  path: string;
  state: string;
}

export interface CheckpointSummary {
  id: string;
  created_at: string;
  file_count: number;
  present_count: number;
  missing_count: number;
  files: CheckpointFileInfo[];
}

export interface CheckpointListResponse {
  workspace_root: string;
  checkpoints: CheckpointSummary[];
}

export interface RestoreCheckpointRequest {
  workspace_root?: string;
  checkpoint: string;
}

export interface RestoreCheckpointResponse {
  restored: string[];
  warnings: string[];
  workspace_root: string;
  workspace_files: WorkspaceFile[];
}

export interface ValidateRequest {
  workspace_root?: string;
}

export interface ValidateResponse {
  task_id: string;
  workspace_root: string;
  events: ToolEvent[];
  validation: CommandRun | null;
  validation_profile: ValidationRecipe | null;
  warnings: string[];
}

export interface HistoryResponse {
  workspace_root: string;
  recent_tasks: TaskSummary[];
  fix_memory: FixMemoryEntry[];
  project_memory: ProjectMemoryEntry[];
}

export interface AppConfig {
  assistant_name: string;
  assistant_mission: string;
  default_mode: Mode;
  modes: ModeOption[];
  default_workspace: string;
  engine: string;
  engine_ready: boolean;
  engine_message: string;
  model_name: string;
  model_endpoint: string;
  model_api: string;
  model_ready: boolean;
  model_message: string;
  database_path: string;
  command_allowlist: string;
  command_timeout_seconds: number;
  auto_run_validation: boolean;
  shared_workspace_mode: boolean;
  feedback_capture_excerpts: boolean;
  feedback_redaction_enabled: boolean;
  feedback_max_excerpt_chars: number;
  feedback_hash_content: boolean;
  env_exists: boolean;
}

export interface ConfigUpdateRequest {
  assistant_name?: string;
  assistant_mission?: string;
  default_mode?: Mode;
  default_workspace?: string;
  model_api?: string;
  model_endpoint?: string;
  model_name?: string;
  command_allowlist?: string;
  command_timeout_seconds?: number;
  auto_run_validation?: boolean;
  shared_workspace_mode?: boolean;
  feedback_capture_excerpts?: boolean;
  feedback_redaction_enabled?: boolean;
  feedback_max_excerpt_chars?: number;
  feedback_hash_content?: boolean;
}

export interface HealthResponse {
  ok: boolean;
  ready: boolean;
  status: string;
  app: string;
  version: string;
  engine: string;
  engine_ready: boolean;
  engine_message: string;
  model_name: string;
  model_api: string;
  model_endpoint: string;
  model_ready: boolean;
  model_message: string;
  project_root: string;
  workspace_root: string;
  database_path: string;
  env_exists: boolean;
  router_execution_enabled?: boolean;
  router_enabled?: boolean;
  fallback_supported?: boolean;
  provider_count?: number;
  configured_provider_count?: number;
  enabled_provider_count?: number;
  role_count?: number;
  recommendations?: string[];
}

export interface ModelCapabilities {
  chat: boolean;
  code: boolean;
  debug: boolean;
  refactor: boolean;
  reasoning: boolean;
  research: boolean;
  streaming: boolean;
  structured_json: boolean;
  tools: boolean;
  vision: boolean;
  audio: boolean;
  embeddings: boolean;
  image: boolean;
  video: boolean;
  realtime: boolean;
  judge: boolean;
  computer_use: boolean;
}

export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  api: string;
  endpoint: string;
  local: boolean;
  configured: boolean;
  available: boolean;
  ready: boolean;
  message: string;
  size: number | null;
  modified_at: string;
  capabilities: ModelCapabilities;
}

export interface ModelInventoryResponse {
  active_model: string;
  active_api: string;
  active_endpoint: string;
  router_enabled: boolean;
  fallback_supported: boolean;
  message: string;
  models: ModelInfo[];
}

export interface ModelRegistryProvider {
  id: string;
  label: string;
  api: string;
  endpoint: string;
  model_name: string;
  model_aliases: string[];
  secret_env: string;
  local: boolean;
  enabled: boolean;
  configured: boolean;
  capabilities: string[];
  roles: string[];
  cost_tier: string;
  context_window: number | null;
  rate_limit_rpm: number | null;
  input_cost_per_million: number | null;
  output_cost_per_million: number | null;
  health: string;
  notes: string;
}

export interface ModelRegistryRole {
  id: string;
  label: string;
  description: string;
  primary_model: string;
  fallback_models: string[];
  required_capabilities: string[];
  privacy_mode: string;
  cost_tier: string;
  status: string;
}

export interface ModelRoutingPreset {
  id: string;
  label: string;
  description: string;
  role_order: string[];
  privacy_mode: string;
}

export interface ModelRegistryResponse {
  version: number;
  active_provider_id: string;
  active_model: string;
  router_enabled: boolean;
  fallback_supported: boolean;
  message: string;
  providers: ModelRegistryProvider[];
  roles: ModelRegistryRole[];
  presets: ModelRoutingPreset[];
}

export interface ModelDiskInfo {
  drive_root: string;
  project_root: string;
  model_store_path: string;
  total_bytes: number;
  used_bytes: number;
  free_bytes: number;
  model_store_bytes: number;
  free_percent: number;
  low_space: boolean;
  minimum_free_bytes: number;
}

export interface ManagedModelInfo {
  provider_id: string;
  label: string;
  api: string;
  endpoint: string;
  name: string;
  local: boolean;
  enabled: boolean;
  installed: boolean;
  configured: boolean;
  active: boolean;
  pullable: boolean;
  health: string;
  roles: string[];
  capabilities: string[];
  size_bytes: number | null;
  modified_at: string;
  estimated_pull_bytes: number | null;
  notes: string;
}

export interface ModelOperationInfo {
  id: string;
  model_name: string;
  action: string;
  status: string;
  message: string;
  pid: number | null;
  started_at: string;
  finished_at: string;
  stdout_log: string;
  stderr_log: string;
  minimum_free_bytes: number;
  estimated_pull_bytes: number | null;
  free_bytes_before: number | null;
}

export interface ModelPullLogSummary {
  source: string;
  total: number;
  pulled: number;
  skipped: number;
  failed: number;
  latest_at: string;
}

export interface ModelManagerResponse {
  ok: boolean;
  message: string;
  disk: ModelDiskInfo;
  active_model: string;
  active_provider_id: string;
  providers_total: number;
  local_total: number;
  installed_total: number;
  pullable_total: number;
  cloud_total: number;
  models: ManagedModelInfo[];
  operations: ModelOperationInfo[];
  pull_logs: ModelPullLogSummary[];
}

export interface ModelPullRequest {
  model_name: string;
  minimum_free_gb?: number;
}

export interface ModelDeleteRequest {
  model_name: string;
  confirm_model_name: string;
}

export interface FilesResponse {
  workspace_root: string;
  files: WorkspaceFile[];
}

export interface FileContentResponse {
  workspace_root: string;
  path: string;
  content: string;
}

export interface ValidationRecipe {
  command: string;
  label: string;
  source: string;
  updated_at: string;
  notes: string;
}

export interface ValidationSuggestion {
  command: string;
  label: string;
  category: string;
  reason: string;
}

export interface ApprovalSettingsResponse {
  approval_tier: string;
  sandbox_profile: string;
  available_tiers: string[];
  available_profiles: string[];
}

export interface UpdateApprovalSettingsRequest {
  approval_tier: string;
  sandbox_profile: string;
}

export interface ValidationProfileResponse {
  workspace_root: string;
  profile: ValidationRecipe | null;
  suggestions: ValidationSuggestion[];
}

export interface ValidationProfileUpdateRequest {
  command: string;
  label: string;
  notes: string;
}

export interface WorkspaceReadinessInfo {
  status: 'ready' | 'needs_work' | 'needs_validation' | 'needs_repair' | 'unconfigured' | string;
  score: number;
  summary: string;
  next_action: string;
  blockers: string[];
  signals: string[];
}

export interface WorkspaceDependency {
  name: string;
  version: string;
  source: string;
  group: string;
}

export interface WorkspaceScript {
  name: string;
  command: string;
  source: string;
}

export interface WorkspaceDependencyProfile {
  project_type: string;
  languages: string[];
  frameworks: string[];
  package_managers: string[];
  build_systems: string[];
  config_files: string[];
  entry_points: string[];
  test_files: string[];
  install_commands: string[];
  validation_commands: string[];
  scripts: WorkspaceScript[];
  dependencies: WorkspaceDependency[];
  dev_dependencies: WorkspaceDependency[];
  database_tools: string[];
  warnings: string[];
}

export interface WorkspaceProfileResponse {
  workspace_root: string;
  manifest: Record<string, unknown> | null;
  has_manifest: boolean;
  dependency_profile: WorkspaceDependencyProfile;
  instruction_status: Record<string, unknown>;
  has_instruction_status: boolean;
  validation_plan: Record<string, unknown>;
  has_validation_plan: boolean;
  readiness: WorkspaceReadinessInfo;
  recommendations: string[];
}

export interface WorkspaceSetupRequest {
  workspace_root?: string;
  overwrite_manifest?: boolean;
  project_name?: string;
  title?: string;
  install_command?: string;
  validation_command?: string;
  notes?: string;
}

export interface WorkspaceSetupResponse {
  workspace_root: string;
  manifest: Record<string, unknown>;
  validation_profile: ValidationRecipe | null;
  profile: WorkspaceProfileResponse;
  created_files: string[];
  updated_files: string[];
  warnings: string[];
}

export interface DiffCompareRequest {
  old_content: string | null;
  new_content: string | null;
  path: string;
  action: ChangeAction;
}

export interface DiffCompareResponse {
  path: string;
  action: ChangeAction;
  patch: string;
  added_lines: number;
  removed_lines: number;
  modified_lines: number;
}

export type FeedbackSentiment = 'liked' | 'disliked' | 'accepted' | 'rejected' | 'copied' | 'revised' | 'neutral';
export type FeedbackAction =
  | 'message_feedback'
  | 'response_feedback'
  | 'validation_feedback'
  | 'change_feedback'
  | 'regenerated'
  | 'accepted'
  | 'rejected'
  | 'applied'
  | 'rolled_back'
  | 'corrected'
  | 'copied'
  | 'manual';

export interface ContextBudgetTelemetryEntry {
  task_id: string;
  created_at: string;
  workspace_root: string;
  intent: string;
  route_role: string;
  strategy: string;
  privacy_mode: string;
  max_context_tokens: number;
  estimated_context_tokens: number;
  estimated_file_tokens: number;
  reserve_response_tokens: number;
  selected_file_count: number;
  omitted_file_count: number;
  payload: Record<string, unknown>;
}

export interface ModelAttemptTelemetryEntry {
  task_id: string;
  created_at: string;
  workspace_root: string;
  attempt: {
    attempt: number;
    role: string;
    provider_id: string;
    provider_label: string;
    provider_api: string;
    model: string;
    endpoint: string;
    privacy_mode: string;
    status: string;
    reason: string;
    error: string;
    retryable: boolean;
    input_tokens: number | null;
    output_tokens: number | null;
    estimated_cost_usd: number | null;
    latency_ms: number | null;
    started_at: string;
    finished_at: string;
    metadata: Record<string, unknown>;
  };
}

export interface FeedbackTelemetryEntry {
  id: string;
  created_at: string;
  workspace_root: string;
  task_id: string;
  sentiment: FeedbackSentiment;
  action: FeedbackAction;
  target: string;
  model_label: string;
  route_role: string;
  candidate_id: string;
  content_hash: string;
  context: string;
  metadata: Record<string, unknown>;
}

export interface FeedbackTelemetrySummary {
  feedback_count: number;
  positive_count: number;
  negative_count: number;
  copied_count: number;
  revised_count: number;
  regenerated_count: number;
  applied_count: number;
  rolled_back_count: number;
  corrected_count: number;
  positive_rate: number;
  negative_rate: number;
}

export interface FeedbackAttributionRollup extends FeedbackTelemetrySummary {
  dimension: string;
  key: string;
  label: string;
  task_count: number;
  latest_at: string;
}

export interface FeedbackTrendBucket extends FeedbackTelemetrySummary {
  period_start: string;
}

export interface FeedbackTelemetryResponse {
  workspace_root: string;
  limit: number;
  summary: FeedbackTelemetrySummary;
  events: FeedbackTelemetryEntry[];
  rollups: FeedbackAttributionRollup[];
  trends: FeedbackTrendBucket[];
  recommendations: string[];
}

export interface RouteQualityOverview {
  task_count: number;
  context_budget_count: number;
  model_attempt_count: number;
  succeeded_attempts: number;
  failed_attempts: number;
  planned_attempts: number;
  fallback_attempts: number;
  retryable_failures: number;
  success_rate: number;
  fallback_rate: number;
  estimated_cost_usd: number;
  input_tokens: number;
  output_tokens: number;
  average_latency_ms: number | null;
  average_context_utilization: number | null;
  average_context_tokens: number;
  average_selected_files: number;
  average_omitted_files: number;
  reliability_score: number;
  feedback_count: number;
  positive_feedback: number;
  negative_feedback: number;
  revised_feedback: number;
  regenerated_feedback: number;
  applied_feedback: number;
  rolled_back_feedback: number;
  corrected_feedback: number;
  positive_feedback_rate: number;
  negative_feedback_rate: number;
}

export interface RouteQualityProviderRollup {
  provider_id: string;
  provider_label: string;
  provider_api: string;
  model: string;
  task_count: number;
  attempts: number;
  successes: number;
  failures: number;
  planned: number;
  fallback_attempts: number;
  success_rate: number;
  fallback_rate: number;
  estimated_cost_usd: number;
  input_tokens: number;
  output_tokens: number;
  average_latency_ms: number | null;
  average_context_utilization: number | null;
  token_estimator_sources: string[];
}

export interface RouteQualityTokenCalibrationRollup {
  provider_id: string;
  provider_label: string;
  provider_api: string;
  model: string;
  attempts: number;
  calibrated_attempts: number;
  calibration_status: string;
  estimated_input_tokens: number;
  reported_input_tokens: number;
  estimated_output_tokens: number;
  reported_output_tokens: number;
  average_input_token_error: number | null;
  worst_input_token_error: number | null;
  average_output_token_error: number | null;
  worst_output_token_error: number | null;
  token_estimator_sources: string[];
  reported_token_sources: string[];
  recommendation: string;
}

export interface RouteQualityTokenCalibrationTrendBucket {
  provider_id: string;
  provider_label: string;
  provider_api: string;
  model: string;
  period_start: string;
  attempts: number;
  calibrated_attempts: number;
  calibration_status: string;
  trend_direction: string;
  estimated_input_tokens: number;
  reported_input_tokens: number;
  estimated_output_tokens: number;
  reported_output_tokens: number;
  average_input_token_error: number | null;
  worst_input_token_error: number | null;
  average_output_token_error: number | null;
  worst_output_token_error: number | null;
  recommendation: string;
}

export interface RouteQualityStructuredPreviewRollup {
  provider_id: string;
  provider_label: string;
  provider_api: string;
  model: string;
  attempts: number;
  previewed_attempts: number;
  final_winning_attempts: number;
  retired_attempts: number;
  reset_count: number;
  delta_count: number;
  char_count: number;
  preview_success_rate: number;
  retired_rate: number;
  average_preview_chars: number;
  preview_status: string;
  retired_reasons: string[];
  recommendation: string;
}

export interface RouteQualityRoleRollup {
  role: string;
  task_count: number;
  attempts: number;
  successes: number;
  failures: number;
  planned: number;
  fallback_attempts: number;
  success_rate: number;
  estimated_cost_usd: number;
  average_latency_ms: number | null;
}

export interface RouteQualityContextRollup {
  route_role: string;
  intent: string;
  budget_count: number;
  average_context_tokens: number;
  average_file_tokens: number;
  average_reserved_response_tokens: number;
  average_selected_files: number;
  average_omitted_files: number;
  average_budget_utilization: number | null;
}

export interface RouteQualityContextDrilldown {
  task_id: string;
  created_at: string;
  route_role: string;
  intent: string;
  strategy: string;
  privacy_mode: string;
  max_context_tokens: number;
  estimated_context_tokens: number;
  estimated_file_tokens: number;
  reserve_response_tokens: number;
  utilization: number | null;
  selected_file_count: number;
  omitted_file_count: number;
  selected_memory_count: number;
  omitted_memory_count: number;
  selected_project_memory_count: number;
  omitted_project_memory_count: number;
  selected_refs: string[];
  omitted_refs: string[];
  largest_refs: string[];
  notes: string[];
  recommendations: string[];
}

export interface RouteQualityResponse {
  workspace_root: string;
  limit: number;
  overview: RouteQualityOverview;
  providers: RouteQualityProviderRollup[];
  token_calibration: RouteQualityTokenCalibrationRollup[];
  token_calibration_trends: RouteQualityTokenCalibrationTrendBucket[];
  structured_preview: RouteQualityStructuredPreviewRollup[];
  roles: RouteQualityRoleRollup[];
  contexts: RouteQualityContextRollup[];
  context_drilldowns: RouteQualityContextDrilldown[];
  feedback_rollups: FeedbackAttributionRollup[];
  feedback_trends: FeedbackTrendBucket[];
  feedback_events: FeedbackTelemetryEntry[];
  recommendations: string[];
}

export type TelemetrySnapshotStatus = 'hit' | 'miss' | 'refreshed';

export interface TelemetrySnapshot {
  id: string;
  workspace_root: string;
  snapshot_key: string;
  created_at: string;
  updated_at: string;
  route_quality_limit: number;
  fallback_limit: number;
  feedback_limit: number;
  stale_after_seconds: number;
  age_seconds: number;
  is_stale: boolean;
  route_quality: RouteQualityResponse;
  fallback_inspector: FallbackInspectorResponse;
  feedback: FeedbackTelemetryResponse;
}

export interface TelemetrySnapshotPruneInfo {
  retention_max_snapshots: number;
  retention_days: number;
  deleted_count: number;
  retained_count: number;
  oldest_retained_at: string;
  newest_retained_at: string;
  recommendation: string;
}

export interface TelemetrySnapshotResponse {
  workspace_root: string;
  cache_status: TelemetrySnapshotStatus;
  snapshot: TelemetrySnapshot | null;
  prune: TelemetrySnapshotPruneInfo;
  recommendations: string[];
}

export interface TelemetrySnapshotOptions {
  routeQualityLimit?: number;
  fallbackLimit?: number;
  feedbackLimit?: number;
  staleAfterSeconds?: number;
  refresh?: boolean;
  prune?: boolean;
  maxSnapshots?: number;
  retentionDays?: number;
}

export type RoutePolicyProviderAction = 'promote' | 'hold' | 'monitor' | 'deprioritize';
export type RoutePolicyRoleAction = 'keep' | 'switch_primary' | 'strengthen_fallback' | 'rebalance';
export type RoutePolicyRiskLevel = 'low' | 'medium' | 'high';

export interface RoutePolicyProviderProposal {
  provider_id: string;
  provider_label: string;
  provider_api: string;
  model: string;
  observed_rank: number;
  proposed_rank: number;
  action: RoutePolicyProviderAction;
  risk_level: RoutePolicyRiskLevel;
  confidence: number;
  score: number;
  attempts: number;
  successes: number;
  failures: number;
  fallback_rate: number;
  success_rate: number;
  positive_feedback_rate: number;
  negative_feedback_rate: number;
  average_latency_ms: number | null;
  average_context_utilization: number | null;
  estimated_cost_usd: number;
  reasons: string[];
  risks: string[];
}

export interface RoutePolicyRoleProposal {
  role: string;
  action: RoutePolicyRoleAction;
  observed_primary_provider: string;
  proposed_primary_provider: string;
  confidence: number;
  task_count: number;
  attempts: number;
  success_rate: number;
  fallback_attempts: number;
  score_delta: number;
  candidate_provider_ids: string[];
  reasons: string[];
  risks: string[];
}

export interface RoutePolicyDiffResponse {
  workspace_root: string;
  generated_at: string;
  limit: number;
  source: string;
  source_snapshot_id: string;
  source_snapshot_age_seconds: number;
  source_snapshot_stale: boolean;
  min_attempts: number;
  provider_proposals: RoutePolicyProviderProposal[];
  role_proposals: RoutePolicyRoleProposal[];
  recommendations: string[];
  warnings: string[];
}

export interface RoutePolicyDiffOptions {
  limit?: number;
  useSnapshot?: boolean;
  staleAfterSeconds?: number;
  minAttempts?: number;
}

export interface FallbackInspectorCandidate {
  index: number;
  candidate_id: string;
  role: string;
  provider_hint: string;
  required_capabilities: string[];
  privacy_mode: string;
  reason: string;
  confidence: number;
  status: string;
  matched_attempt_number: number | null;
  provider_id: string;
  provider_label: string;
  provider_api: string;
  model: string;
  registry_resolved: boolean | null;
  retryable: boolean | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: number | null;
  latency_ms: number | null;
  token_estimator_source: string;
  context_window: number | null;
  context_window_utilization: number | null;
  error: string;
  adapter_status: string;
  adapter_message: string;
  adapter_recommendation: string;
  adapter_secret_env: string;
  adapter_secret_present: boolean;
  adapter_cooldown: boolean;
  adapter_preflight_skips: number;
  adapter_recent_failures: number;
  adapter_latest_error: string;
}

export interface FallbackInspectorTask {
  task_id: string;
  created_at: string;
  finished_at: string | null;
  mode: string;
  workspace_root: string;
  message: string;
  status: string;
  context_budget: ContextBudgetTelemetryEntry | null;
  attempts: ModelAttemptTelemetryEntry[];
  candidates: FallbackInspectorCandidate[];
  fallback_roles: string[];
  summary: string;
  recommendations: string[];
}

export interface FallbackInspectorResponse {
  workspace_root: string;
  limit: number;
  task_count: number;
  tasks: FallbackInspectorTask[];
  recommendations: string[];
}
