// frontend/src/types.ts
export type Role = 'user' | 'assistant' | 'system';
export type Mode = 'build' | 'develop' | 'review' | 'chat';
export type ChangeAction = 'create' | 'update' | 'append' | 'delete';
export type EventStatus = 'ok' | 'warning' | 'error';
export type MediaKind =
  | 'image'
  | 'image_to_image'
  | 'logo'
  | 'ui_mockup'
  | 'icon'
  | 'product_mockup'
  | 'style_transfer'
  | 'background_removal'
  | 'upscale'
  | 'variation'
  | 'video'
  | 'text_to_video'
  | 'image_to_video'
  | 'promo_video'
  | 'logo_intro'
  | 'app_showcase'
  | 'social_clip'
  | 'storyboard_video'
  | 'animation'
  | 'gif'
  | 'video_edit'
  | 'music_beat'
  | 'music'
  | 'drum_loop'
  | 'melody'
  | 'loop'
  | 'arrangement'
  | 'voice'
  | 'voiceover'
  | 'narration'
  | 'sound_effect'
  | 'audio_cleanup'
  | 'psd_template'
  | 'brand_kit'
  | 'thumbnail'
  | 'icon_set'
  | 'sticker_pack';
export type MediaJobStatus = 'queued' | 'generating' | 'failed' | 'completed' | 'canceled' | string;

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
  mediaJob?: ChatMediaJob;
}

export type ChatMediaJob = Pick<
  MediaJobResponse,
  'id' | 'kind' | 'studio' | 'status' | 'provider_name' | 'prompt' | 'theme_color' | 'assets'
> &
  Partial<MediaJobResponse>;

export interface ModeOption {
  id: Mode;
  label: string;
  description: string;
}

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  created_at: string;
  plan: string;
  role: 'user' | 'admin' | string;
  status: 'active' | 'banned' | 'disabled' | string;
}

export interface AuthRegisterRequest {
  name: string;
  email: string;
  password: string;
  confirm_password: string;
}

export interface AuthLoginRequest {
  email: string;
  password: string;
  remember_me: boolean;
}

export interface AuthForgotPasswordRequest {
  email: string;
}

export interface AuthSessionResponse {
  token: string;
  token_type: string;
  user: AuthUser;
  expires_at: string;
}

export interface AuthMessageResponse {
  ok: boolean;
  message: string;
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

export interface MediaAsset {
  id: string;
  path: string;
  kind: string;
  format: string;
  role: string;
  mime_type: string;
  editable: boolean;
  derived_from: string;
  thumbnail_path: string;
  metadata: Record<string, unknown>;
}

export interface MediaProviderInfo {
  id: string;
  name: string;
  category: string;
  location: string;
  supports: MediaKind[];
  output_formats: string[];
  paid: boolean;
  gpu_intensive: boolean;
  requires_approval: boolean;
  available: boolean;
  notes: string;
}

export interface MediaPromptPreset {
  id: string;
  name: string;
  studio: string;
  kind: MediaKind;
  prompt_template: string;
  negative_prompt: string;
  default_settings: Record<string, unknown>;
  tags: string[];
}

export interface MediaCapabilitiesResponse {
  supported_kinds: MediaKind[];
  local_formats: string[];
  provider_formats: string[];
  providers: MediaProviderInfo[];
  prompt_presets: MediaPromptPreset[];
  can_iterate_from_previous: boolean;
  theme_inference: boolean;
  psd_template_strategy: string;
  local_renderers: Record<string, boolean>;
  recommendations: string[];
}

export interface MediaCreativeRequest {
  prompt: string;
  kind?: MediaKind;
  studio?: string;
  operation?: string;
  provider_id?: string;
  feedback?: string;
  previous_job_id?: string;
  source_asset_id?: string;
  theme_color?: string;
  aspect_ratio?: string;
  style?: string;
  negative_prompt?: string;
  duration_seconds?: number;
  fps?: number;
  width?: number;
  height?: number;
  seed?: number | null;
  bpm?: number | null;
  key?: string;
  genre?: string;
  voice?: string;
  paid_approved?: boolean;
  gpu_approved?: boolean;
  copyright_style_approved?: boolean;
  voice_clone_approved?: boolean;
  settings?: Record<string, unknown>;
  output_formats?: string[];
}

export interface MediaJobResponse {
  id: string;
  created_at: string;
  updated_at: string;
  completed_at: string;
  kind: MediaKind;
  studio: string;
  operation: string;
  status: MediaJobStatus;
  provider_id: string;
  provider_name: string;
  prompt: string;
  effective_prompt: string;
  negative_prompt: string;
  feedback: string;
  previous_job_id: string;
  source_asset_id: string;
  theme_color: string;
  palette: string[];
  aspect_ratio: string;
  style: string;
  seed: number | null;
  settings: Record<string, unknown>;
  output_path: string;
  cost_estimate_usd: number;
  time_taken_seconds: number;
  error: string;
  timeline: ToolEvent[];
  plan: string[];
  assets: MediaAsset[];
  warnings: string[];
  next_actions: string[];
  job_dir: string;
}

export interface MediaAssetLibraryResponse {
  generated_at: string;
  base_dir: string;
  jobs: MediaJobResponse[];
  assets: MediaAsset[];
  total_assets: number;
  formats: string[];
  kinds: string[];
}

export interface MediaExportRequest {
  format: string;
  asset_ids?: string[];
  include_metadata?: boolean;
}

export interface MediaExportResponse {
  id: string;
  created_at: string;
  job_id: string;
  format: string;
  path: string;
  assets: MediaAsset[];
  warnings: string[];
}

export type RuntimeCapabilityStatus = 'ready' | 'partial' | 'planned' | 'blocked' | 'disabled' | string;

export interface RuntimeCapabilityPillar {
  id: string;
  name: string;
  status: RuntimeCapabilityStatus;
  summary: string;
  privacy_scope: string;
  modules: string[];
  endpoints: string[];
  primary_surfaces: string[];
  active_items: number;
  signals: string[];
  next_workflows: string[];
  safety_notes: string[];
}

export interface RuntimeModalityCapability {
  id: string;
  label: string;
  status: RuntimeCapabilityStatus;
  input_supported: boolean;
  output_supported: boolean;
  analyzers: string[];
  generators: string[];
  formats: string[];
  notes: string[];
}

export interface RuntimeToolContract {
  id: string;
  name: string;
  category: string;
  status: RuntimeCapabilityStatus;
  permission_scope: string;
  approval_required: boolean;
  sandboxed: boolean;
  rollback_supported: boolean;
  timeout_seconds: number;
  tracked_by_tasks: boolean;
  endpoints: string[];
  notes: string[];
}

export interface RuntimeWorkflowEntry {
  id: string;
  name: string;
  category: string;
  status: RuntimeCapabilityStatus;
  trigger: string;
  description: string;
  endpoints: string[];
  safety_profile: string;
  task_tracked: boolean;
}

export interface UnifiedRuntimeSnapshot {
  generated_at: string;
  api_version: string;
  workspace_root: string;
  runtime_name: string;
  mode: string;
  pillars: RuntimeCapabilityPillar[];
  modalities: RuntimeModalityCapability[];
  tools: RuntimeToolContract[];
  workflows: RuntimeWorkflowEntry[];
  memory_summary: Record<string, unknown>;
  safety_summary: string[];
  active_counts: Record<string, number>;
  recommendations: string[];
  warnings: string[];
}

export type OperatingActionStatus = 'preview' | 'needs_approval' | 'blocked' | 'accepted' | 'failed';

export interface OperatingEnvironmentCapability {
  id: string;
  name: string;
  category: string;
  status: RuntimeCapabilityStatus;
  summary: string;
  permission_scope: string;
  approval_required: boolean;
  sandbox_required: boolean;
  rollback_supported: boolean;
  task_tracked: boolean;
  telemetry_enabled: boolean;
  adapter_ids: string[];
  endpoints: string[];
  surfaces: string[];
  safety_notes: string[];
  next_steps: string[];
}

export interface OperatingEnvironmentAdapter {
  id: string;
  name: string;
  category: string;
  status: RuntimeCapabilityStatus;
  provider: string;
  enabled: boolean;
  permission_scope: string;
  capabilities: string[];
  approval_required: boolean;
  sandboxed: boolean;
  reason: string;
  notes: string[];
  last_seen_at: string;
}

export interface OperatingSystemSignal {
  id: string;
  label: string;
  category: string;
  status: 'ok' | 'warning' | 'error';
  value: string;
  detail: string;
  updated_at: string;
}

export interface OperatingEnvironmentActionRequest {
  capability_id: string;
  action: string;
  workspace_root?: string | null;
  parameters?: Record<string, unknown>;
  dry_run?: boolean;
  approval_token?: string;
  requested_by?: string;
  task_id?: string;
}

export interface OperatingEnvironmentActionResponse {
  request_id: string;
  capability_id: string;
  action: string;
  status: OperatingActionStatus;
  allowed: boolean;
  approval_required: boolean;
  reason: string;
  summary: string;
  required_permissions: string[];
  rollback_supported: boolean;
  safety_notes: string[];
  event: ToolEvent | null;
}

export interface OperatingEnvironmentSnapshot {
  generated_at: string;
  api_version: string;
  workspace_root: string;
  runtime_name: string;
  mode: string;
  execution_mode: string;
  capabilities: OperatingEnvironmentCapability[];
  adapters: OperatingEnvironmentAdapter[];
  system_signals: OperatingSystemSignal[];
  permissions_summary: Record<string, unknown>;
  safety_summary: string[];
  recommended_next_actions: string[];
  warnings: string[];
}

export type UnifiedContextRecordKind =
  | 'conversation'
  | 'project'
  | 'architecture'
  | 'file'
  | 'task'
  | 'timeline_event'
  | 'memory'
  | 'fix_memory'
  | 'media_job'
  | 'media_asset'
  | 'workflow'
  | 'automation'
  | 'research'
  | 'desktop'
  | 'system'
  | 'runtime'
  | 'recommendation'
  | 'telemetry'
  | string;

export interface UnifiedContextRecord {
  id: string;
  kind: UnifiedContextRecordKind;
  title: string;
  summary: string;
  source: string;
  reference: string;
  workspace_root: string;
  created_at: string;
  updated_at: string;
  status: string;
  importance: number;
  tags: string[];
  related_files: string[];
  related_tasks: string[];
  related_assets: string[];
  metadata: Record<string, unknown>;
}

export interface UnifiedContextRelationship {
  source_id: string;
  target_id: string;
  kind: string;
  strength: number;
  summary: string;
  evidence: string[];
}

export interface UnifiedContextSourceSummary {
  source: string;
  records: number;
  ready: boolean;
  summary: string;
}

export interface UnifiedContextSnapshot {
  workspace_root: string;
  generated_at: string;
  api_version: string;
  records: UnifiedContextRecord[];
  relationships: UnifiedContextRelationship[];
  source_summaries: UnifiedContextSourceSummary[];
  timeline: UnifiedContextRecord[];
  cross_module_insights: string[];
  command_entrypoints: string[];
  recommended_focus: string[];
  warnings: string[];
}

export interface UnifiedContextSearchRequest {
  workspace_root?: string | null;
  query?: string;
  scopes?: string[];
  limit?: number;
  include_relationships?: boolean;
}

export interface UnifiedContextSearchResult {
  record: UnifiedContextRecord;
  score: number;
  matched_fields: string[];
  relationships: UnifiedContextRelationship[];
}

export interface UnifiedContextSearchResponse {
  query: string;
  workspace_root: string;
  generated_at: string;
  results: UnifiedContextSearchResult[];
  scope_summary: Record<string, number>;
  suggestions: string[];
}

export interface GlobalCommandRequest {
  workspace_root?: string | null;
  command: string;
  entrypoint?: 'chat' | 'command_palette' | 'desktop_overlay' | 'voice' | 'mobile' | 'api' | string;
  create_task?: boolean;
  dry_run?: boolean;
  metadata?: Record<string, unknown>;
}

export interface GlobalCommandRoute {
  intent: string;
  target_system: string;
  task_kind: string;
  confidence: number;
  creates_task: boolean;
  approval_required: boolean;
  rollback_supported: boolean;
  validation_required: boolean;
  endpoint: string;
  reason: string;
  safety_notes: string[];
}

export interface GlobalCommandResponse {
  workspace_root: string;
  generated_at: string;
  command: string;
  entrypoint: string;
  route: GlobalCommandRoute;
  plan: string[];
  context_results: UnifiedContextSearchResult[];
  task: TaskSummary | null;
  event: ToolEvent | null;
  warnings: string[];
}

export interface AmbientPresenceState {
  status: 'calm' | 'focused' | 'busy' | 'attention' | 'degraded' | string;
  active_focus: string;
  workload_level: 'light' | 'steady' | 'heavy' | 'overloaded' | string;
  suggestion_intensity: 'quiet' | 'normal' | 'reduced' | 'paused' | string;
  notification_style: 'silent' | 'subtle' | 'normal' | 'urgent_only' | string;
  continuity_summary: string;
  proactive_suggestions: string[];
  active_signals: string[];
  session_handoff: string[];
}

export interface OperatingTimelineEntry {
  id: string;
  kind: string;
  title: string;
  summary: string;
  source: string;
  reference: string;
  occurred_at: string;
  status: string;
  importance: number;
  related_records: string[];
  related_files: string[];
  related_tasks: string[];
  related_assets: string[];
  replay_hint: string;
  metadata: Record<string, unknown>;
}

export interface OperatingMemoryTimeline {
  workspace_root: string;
  generated_at: string;
  entries: OperatingTimelineEntry[];
  source_counts: Record<string, number>;
  reconstruction_notes: string[];
  replay_supported: boolean;
  search_supported: boolean;
}

export interface TimelineSearchRequest {
  workspace_root?: string | null;
  query?: string;
  kinds?: string[];
  limit?: number;
}

export interface TimelineSearchResponse {
  query: string;
  workspace_root: string;
  generated_at: string;
  results: OperatingTimelineEntry[];
  suggestions: string[];
}

export interface ForecastSignal {
  id: string;
  kind: string;
  severity: 'info' | 'low' | 'medium' | 'high' | 'critical' | string;
  score: number;
  title: string;
  summary: string;
  evidence: string[];
  projected_impact: string;
  recommended_action: string;
  dry_run_available: boolean;
  confidence: number;
}

export interface SimulationForecastSnapshot {
  generated_at: string;
  risk_score: number;
  signals: ForecastSignal[];
  dry_run_modes: string[];
  assumptions: string[];
}

export interface CognitiveAwarenessState {
  load_level: 'low' | 'steady' | 'high' | 'overload_risk' | string;
  detected_patterns: string[];
  pacing: 'normal' | 'slow_down' | 'pause_and_summarize' | 'focus_mode' | string;
  verbosity: 'concise' | 'balanced' | 'detailed' | string;
  notification_intensity: 'quiet' | 'normal' | 'urgent_only' | string;
  workflow_aggressiveness: 'conservative' | 'normal' | 'proactive' | string;
  recommendation_style: string;
  safeguards: string[];
}

export interface HardwareAccelerationProfile {
  status: RuntimeCapabilityStatus;
  cpu_logical: number;
  gpu_available: boolean;
  npu_available: boolean;
  accelerators: string[];
  local_model_optimizations: string[];
  routing_notes: string[];
  power_profile: 'unknown' | 'balanced' | 'performance' | 'battery_saver' | string;
  warnings: string[];
}

export interface PersistentWorkspaceState {
  workspace_root: string;
  restore_readiness: 'ready' | 'partial' | 'needs_attention' | string;
  persisted_sections: string[];
  active_task_count: number;
  active_workflow_count: number;
  memory_record_count: number;
  media_asset_count: number;
  checkpoint_references: number;
  recovery_notes: string[];
}

export interface SelfDiagnosticSignal {
  id: string;
  category: string;
  status: 'healthy' | 'watch' | 'degraded' | 'critical' | 'unknown' | string;
  title: string;
  summary: string;
  evidence: string[];
  recommendation: string;
}

export interface SkillPackInfo {
  id: string;
  name: string;
  category: string;
  status: RuntimeCapabilityStatus;
  trust_level: string;
  capabilities: string[];
  included_assets: string[];
  permission_scopes: string[];
  lifecycle: string[];
  notes: string[];
}

export interface UniversalDataSource {
  id: string;
  name: string;
  category: string;
  status: RuntimeCapabilityStatus;
  records_indexed: number;
  semantic_index_ready: boolean;
  permission_scope: string;
  connectors: string[];
  notes: string[];
}

export interface PlatformSdkCapability {
  id: string;
  name: string;
  status: RuntimeCapabilityStatus;
  api_version: string;
  permission_scoped: boolean;
  sandboxed: boolean;
  signing_supported: boolean;
  lifecycle_hooks: string[];
  docs: string[];
}

export interface DigitalTwinWorkspaceModel {
  workspace_root: string;
  model_version: string;
  confidence: number;
  modeled_entities: Record<string, number>;
  architecture_summary: string;
  workflow_summary: string;
  dependency_summary: string;
  preference_summary: string;
  recovery_uses: string[];
  predictive_uses: string[];
}

export interface ResearchLabEvaluation {
  id: string;
  name: string;
  category: string;
  status: RuntimeCapabilityStatus;
  metric: string;
  last_result: string;
  next_run_hint: string;
  controlled: boolean;
}

export interface MemoryDistillationSnapshot {
  generated_at: string;
  raw_memory_records: number;
  distilled_themes: string[];
  archive_candidates: string[];
  compression_ratio_estimate: number;
  pruning_recommendations: string[];
  continuity_preserved: boolean;
}

export interface AegisContinuitySnapshot {
  workspace_root: string;
  generated_at: string;
  api_version: string;
  presence: AmbientPresenceState;
  timeline: OperatingMemoryTimeline;
  forecasts: SimulationForecastSnapshot;
  cognitive: CognitiveAwarenessState;
  hardware: HardwareAccelerationProfile;
  workspace_state: PersistentWorkspaceState;
  self_diagnostics: SelfDiagnosticSignal[];
  skill_packs: SkillPackInfo[];
  universal_data_sources: UniversalDataSource[];
  platform_sdk: PlatformSdkCapability[];
  digital_twin: DigitalTwinWorkspaceModel;
  research_lab: ResearchLabEvaluation[];
  memory_distillation: MemoryDistillationSnapshot;
  recommendations: string[];
  warnings: string[];
}

export type PlatformDomainFocus = 'primary' | 'secondary' | 'experimental';
export type PlatformFeatureStatus = 'production_ready' | 'beta' | 'experimental' | 'internal_only' | 'deprecated';
export type PlatformStabilityTierName = 'stable_runtime' | 'experimental_runtime' | 'sandbox_features' | 'unsafe_research';
export type PlatformLayerName =
  | 'layer_1_core_runtime'
  | 'layer_2_task_memory_orchestration'
  | 'layer_3_domain_systems'
  | 'layer_4_intelligence_surfaces'
  | 'layer_5_ecosystem_distribution';

export interface PlatformDomainStrategy {
  id: string;
  name: string;
  focus: PlatformDomainFocus;
  rationale: string;
  mastery_goal: string;
  success_metrics: string[];
  active_systems: string[];
  boundaries: string[];
}

export interface PlatformRoadmapItem {
  id: string;
  title: string;
  category: 'mvp_workflow' | 'stable_core' | 'long_term' | 'experimental' | 'deprecated' | string;
  status: PlatformFeatureStatus;
  domain: string;
  summary: string;
  owner_layer: PlatformLayerName | string;
  exit_criteria: string[];
  blocked_by: string[];
  complexity_cost: 'low' | 'medium' | 'high';
  ux_impact: 'positive' | 'neutral' | 'risky';
}

export interface PlatformStabilityTier {
  id: PlatformStabilityTierName | string;
  name: string;
  description: string;
  allowed_statuses: PlatformFeatureStatus[];
  entry_requirements: string[];
  release_rules: string[];
  user_visibility: 'default' | 'visible_with_label' | 'hidden_by_default' | 'blocked';
}

export interface PlatformFeedbackLoop {
  id: string;
  name: string;
  status: RuntimeCapabilityStatus;
  signal: string;
  metric: string;
  source: string;
  cadence: string;
  improvement_rule: string;
  current_value: number | null;
  target_value: number | null;
  notes: string[];
}

export interface PlatformDesignStandard {
  id: string;
  category: string;
  rule: string;
  rationale: string;
  applies_to: string[];
  enforcement: 'documented' | 'tested' | 'review_required' | 'blocked';
}

export interface PlatformBehaviorPrinciple {
  id: string;
  principle: string;
  do: string[];
  avoid: string[];
  enforcement: string;
}

export interface PlatformPerformanceBudget {
  id: string;
  name: string;
  category: string;
  target: string;
  warning_threshold: string;
  hard_limit: string;
  measurement: string;
  status: 'healthy' | 'watch' | 'unknown' | 'exceeded';
  rationale: string;
}

export interface PlatformSecurityFoundation {
  id: string;
  name: string;
  status: RuntimeCapabilityStatus;
  policy: string;
  enforcement_points: string[];
  gaps: string[];
}

export interface PlatformLayerDefinition {
  id: PlatformLayerName | string;
  name: string;
  responsibility: string;
  systems: string[];
  allowed_dependencies: string[];
  forbidden_dependencies: string[];
  stability_expectation: PlatformStabilityTierName | string;
}

export interface MaintainabilityPractice {
  id: string;
  practice: string;
  cadence: string;
  signal: string;
  expected_outcome: string;
}

export interface PlatformStewardshipPosture {
  id: string;
  name: string;
  summary: string;
  preserve: string[];
  improve: string[];
  reduce: string[];
  product_feel: string[];
  operating_rules: string[];
  success_metric: string;
  review_cadence: string;
}

export interface PlatformFeatureAdmissionCriterion {
  id: string;
  question: string;
  pass_requirement: string;
  reject_when: string;
  protects: string[];
  required: boolean;
}

export interface PlatformFeatureAdmissionPolicy {
  id: string;
  name: string;
  default_decision: 'reject_when_unclear' | 'review_candidate' | 'allow';
  summary: string;
  criteria: PlatformFeatureAdmissionCriterion[];
  hard_no_rules: string[];
  promotion_requirements: string[];
  review_cadence: string;
}

export interface PlatformDisciplineSnapshot {
  workspace_root: string;
  generated_at: string;
  api_version: string;
  core_identity: string;
  stewardship: PlatformStewardshipPosture;
  feature_admission: PlatformFeatureAdmissionPolicy;
  primary_domains: PlatformDomainStrategy[];
  secondary_domains: PlatformDomainStrategy[];
  experimental_domains: PlatformDomainStrategy[];
  roadmap: PlatformRoadmapItem[];
  stability_tiers: PlatformStabilityTier[];
  feedback_loops: PlatformFeedbackLoop[];
  design_standards: PlatformDesignStandard[];
  behavior_principles: PlatformBehaviorPrinciple[];
  performance_budgets: PlatformPerformanceBudget[];
  security_foundations: PlatformSecurityFoundation[];
  layers: PlatformLayerDefinition[];
  maintainability_practices: MaintainabilityPractice[];
  production_ready_count: number;
  beta_count: number;
  experimental_count: number;
  deprecated_count: number;
  recommendations: string[];
  warnings: string[];
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
  task_id: string;
  project_id: string;
  parent_task_id: string | null;
  title: string;
  user_goal: string;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  finished_at: string | null;
  mode: string;
  workspace_root: string;
  message: string;
  status: string;
  priority: number;
  assigned_agent_role: string;
  related_files: string[];
  validation_commands: string[];
  checkpoints: string[];
  error_summary: string;
  final_summary: string;
}

export interface TaskCreateRequest {
  workspace_root?: string;
  project_id?: string;
  parent_task_id?: string | null;
  title: string;
  user_goal?: string;
  mode?: Mode | string;
  priority?: number;
  assigned_agent_role?: string;
  related_files?: string[];
  validation_commands?: string[];
}

export interface TaskActionRequest {
  reason?: string;
  approval_id?: string;
  approved?: boolean;
}

export interface TaskActionResponse {
  task: TaskSummary;
  event: ToolEvent | null;
}

export interface TaskListResponse {
  workspace_root: string;
  tasks: TaskSummary[];
}

export interface TaskDetailResponse {
  task: TaskSummary;
  subtasks: TaskSummary[];
}

export interface TaskTimelineResponse {
  task_id: string;
  events: ToolEvent[];
}

export interface TaskArtifactsResponse {
  task_id: string;
  related_files: string[];
  validation_commands: string[];
  checkpoints: string[];
  repair_attempts: RepairAttempt[];
  command_events: ToolEvent[];
  validation_events: ToolEvent[];
}

export type WorkerKind = 'local' | 'lan' | 'remote' | 'sandbox' | string;
export type WorkerStatus = 'available' | 'busy' | 'offline' | 'disabled' | 'untrusted' | 'revoked' | string;
export type WorkerTrustState = 'trusted' | 'untrusted' | 'revoked' | string;
export type ExecutionJobKind = 'task' | 'validation' | 'build' | 'indexing' | 'repair' | 'benchmark' | 'telemetry' | 'sync' | string;
export type ExecutionJobStatus = 'queued' | 'assigned' | 'running' | 'succeeded' | 'failed' | 'canceled' | 'retrying' | 'blocked' | string;
export type ExecutionMode = 'local' | 'remote' | 'hybrid' | 'sandbox' | string;
export type SandboxIsolationLevel = 'none' | 'process' | 'workspace_copy' | 'container' | 'remote' | string;

export interface WorkerCapabilitySet {
  installed_sdks: string[];
  build_tools: string[];
  supported_languages: string[];
  available_models: string[];
  gpu_available: boolean;
  ram_gb: number;
  cpu_cores: number;
  validation_support: boolean;
  sandbox_profiles: string[];
  supported_job_kinds: string[];
  supports_remote_sync: boolean;
  max_parallel_jobs: number;
}

export interface WorkerRuntimeInfo {
  worker_id: string;
  name: string;
  kind: WorkerKind;
  endpoint: string;
  status: WorkerStatus;
  trust_state: WorkerTrustState;
  trust_scope: string;
  registered_at: string;
  last_heartbeat_at: string;
  capabilities: WorkerCapabilitySet;
  current_jobs: number;
  total_jobs: number;
  failed_jobs: number;
  average_latency_ms: number;
  public_key_fingerprint: string;
  permission_scopes: string[];
  isolation_level: SandboxIsolationLevel;
  metadata: Record<string, unknown>;
}

export interface WorkerRegistrationRequest {
  worker_id?: string;
  name?: string;
  kind?: WorkerKind;
  endpoint?: string;
  capabilities?: Partial<WorkerCapabilitySet>;
  public_key?: string;
  registration_signature?: string;
  trust_scope?: string;
  permission_scopes?: string[];
  isolation_level?: SandboxIsolationLevel;
  metadata?: Record<string, unknown>;
}

export interface WorkerHeartbeatRequest {
  status?: WorkerStatus;
  current_jobs?: number;
  capabilities?: Partial<WorkerCapabilitySet> | null;
  metadata?: Record<string, unknown>;
}

export interface WorkerActionRequest {
  reason?: string;
}

export interface ExecutionQueueItem {
  id: string;
  task_id: string;
  workspace_root: string;
  kind: ExecutionJobKind;
  title: string;
  user_goal: string;
  status: ExecutionJobStatus;
  priority: number;
  created_at: string;
  updated_at: string;
  assigned_worker_id: string;
  attempts: number;
  max_attempts: number;
  depends_on: string[];
  required_capabilities: string[];
  permission_scope: string;
  sandbox_profile: string;
  payload: Record<string, unknown>;
  error_summary: string;
  result_summary: string;
  lease_expires_at: string;
}

export interface ExecutionQueueCreateRequest {
  workspace_root?: string;
  task_id?: string;
  kind?: ExecutionJobKind;
  title?: string;
  user_goal?: string;
  priority?: number;
  max_attempts?: number;
  depends_on?: string[];
  required_capabilities?: string[];
  permission_scope?: string;
  sandbox_profile?: string;
  payload?: Record<string, unknown>;
}

export interface ExecutionQueueActionRequest {
  reason?: string;
}

export interface ExecutionDispatchRequest {
  workspace_root?: string;
  worker_id?: string;
  limit?: number;
  allow_commands?: boolean;
  allow_remote?: boolean;
}

export interface WorkerAuditEvent {
  id: string;
  created_at: string;
  worker_id: string;
  job_id: string;
  event_type: string;
  status: string;
  detail: string;
  metadata: Record<string, unknown>;
}

export interface ExecutionDispatchResponse {
  jobs: ExecutionQueueItem[];
  workers: WorkerRuntimeInfo[];
  events: WorkerAuditEvent[];
  warnings: string[];
}

export interface HybridRouteCandidate {
  provider_id: string;
  worker_id: string;
  model: string;
  location: 'local' | 'cloud' | 'remote' | 'offline' | string;
  privacy_mode: string;
  estimated_latency_ms: number;
  estimated_cost_usd: number;
  reasoning_fit: number;
  selected: boolean;
  reason: string;
}

export interface HybridRouteRequest {
  workspace_root?: string;
  task_role?: string;
  privacy?: 'local_only' | 'local_first' | 'hybrid' | 'cloud_allowed';
  context_tokens?: number;
  reasoning_difficulty?: 'low' | 'medium' | 'high' | 'xhigh';
  latency_priority?: 'low' | 'medium' | 'high';
  cost_priority?: 'low' | 'medium' | 'high';
  workspace_sensitivity?: 'low' | 'medium' | 'high';
  required_capabilities?: string[];
}

export interface HybridRouteDecision {
  selected: HybridRouteCandidate | null;
  candidates: HybridRouteCandidate[];
  fallback_order: string[];
  privacy_mode: string;
  summary: string;
  warnings: string[];
}

export interface RemoteWorkspaceSyncRequest {
  workspace_root?: string;
  sections?: string[];
  encrypted?: boolean;
}

export interface RemoteWorkspaceSyncManifest {
  id: string;
  workspace_root: string;
  created_at: string;
  encrypted: boolean;
  encryption_label: string;
  included_sections: string[];
  manifest_hash: string;
  payload: Record<string, unknown>;
}

export interface RuntimeObservabilitySnapshot {
  generated_at: string;
  workers_total: number;
  workers_available: number;
  workers_busy: number;
  workers_offline: number;
  workers_untrusted: number;
  queued_jobs: number;
  running_jobs: number;
  failed_jobs: number;
  succeeded_jobs: number;
  task_throughput: Record<string, number>;
  token_usage: Record<string, number>;
  model_latency_ms: Record<string, number>;
  validation_success_rate: number;
  repair_loop_statistics: Record<string, number>;
  queue_latency_ms: number;
}

export interface DistributedRuntimeSnapshot {
  generated_at: string;
  execution_mode: ExecutionMode;
  workers: WorkerRuntimeInfo[];
  queue: ExecutionQueueItem[];
  observability: RuntimeObservabilitySnapshot;
  audit_events: WorkerAuditEvent[];
  routing: HybridRouteDecision | null;
  sync_manifests: RemoteWorkspaceSyncManifest[];
  security_summary: string[];
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

export interface MemoryNotesResponse {
  workspace_root: string;
  warnings: string[];
  notes: MemoryNoteResponse[];
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

export type UpdateMemoryNoteRequest = Partial<CreateMemoryNoteRequest>;

export interface DeleteMemoryNoteResponse {
  deleted: string;
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
  media_job?: MediaJobResponse | null;
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
  core_runtime_reachable?: boolean;
  core_runtime_status?: string;
  core_contract_version?: string;
  core_runtime_message?: string;
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
  core_runtime_reachable?: boolean;
  core_runtime_status?: string;
  core_contract_version?: string;
  core_runtime_message?: string;
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
  core_runtime_reachable?: boolean;
  core_runtime_status?: string;
  core_contract_version?: string;
  core_runtime_message?: string;
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

export interface ProjectProfile {
  project_name: string;
  root_path: string;
  stack: string[];
  frameworks: string[];
  package_managers: string[];
  build_commands: string[];
  test_commands: string[];
  lint_commands: string[];
  run_commands: string[];
  main_entry_files: string[];
  important_folders: string[];
  generated_ignored_folders: string[];
  risk_sensitive_files: string[];
  coding_conventions: string[];
  last_indexed_at: string;
}

export interface ProjectArchitectureModule {
  name: string;
  path: string;
  kind: string;
  summary: string;
}

export interface ProjectApiRoute {
  method: string;
  path: string;
  file: string;
  handler: string;
}

export interface ProjectDependencyEdge {
  source: string;
  target: string;
  kind: string;
}

export interface ProjectArchitectureMap {
  frontend_backend_split: string[];
  major_modules: ProjectArchitectureModule[];
  api_routes: ProjectApiRoute[];
  database_storage_layer: string[];
  config_files: string[];
  build_system: string[];
  dependency_graph: ProjectDependencyEdge[];
  important_integration_points: string[];
}

export interface ProjectFileImportance {
  path: string;
  score: number;
  reasons: string[];
  entry_point_importance: number;
  import_frequency: number;
  recent_edits: number;
  task_relevance: number;
  validation_failures: number;
  user_attention: number;
  architectural_centrality: number;
}

export interface ProjectIndexingStatus {
  status: 'not_indexed' | 'indexing' | 'ready' | 'failed' | string;
  last_indexed_at: string;
  file_count: number;
  ignored_folder_count: number;
  message: string;
}

export interface ProjectIntelligenceSnapshot {
  workspace_root: string;
  profile: ProjectProfile;
  architecture: ProjectArchitectureMap;
  file_importance: ProjectFileImportance[];
  project_memory: ProjectMemoryEntry[];
  recent_tasks: TaskSummary[];
  recent_failures: TaskSummary[];
  known_todos: string[];
  validation_commands: string[];
  indexing: ProjectIndexingStatus;
  recommendations: string[];
}

export interface ProjectIntelligenceReindexRequest {
  workspace_root?: string;
  rebuild_architecture?: boolean;
  rebuild_memory?: boolean;
  clear_memory?: boolean;
}

export interface ProjectContextSelectionRequest {
  workspace_root?: string;
  query?: string;
  max_files?: number;
}

export interface ProjectContextSelectionResponse {
  workspace_root: string;
  selected_files: ProjectFileImportance[];
  architecture_notes: string[];
  project_memory: ProjectMemoryEntry[];
  previous_task_history: TaskSummary[];
  known_pitfalls: string[];
  validation_requirements: string[];
  coding_conventions: string[];
}

export type RecommendationSeverity = 'info' | 'low' | 'medium' | 'high' | 'critical' | string;
export type RecommendationStatus = 'active' | 'dismissed' | 'completed' | string;

export interface WorkspaceFileState {
  path: string;
  size: number;
  kind: string;
  modified_at: number;
  fingerprint: string;
}

export interface WorkspaceWatchEvent {
  id: string;
  workspace_root: string;
  created_at: string;
  kind: string;
  severity: RecommendationSeverity;
  title: string;
  detail: string;
  path: string;
  related_files: string[];
  metadata: Record<string, unknown>;
}

export interface GitCommitSummary {
  sha: string;
  subject: string;
  author: string;
  created_at: string;
}

export interface GitFileChangeSummary {
  path: string;
  status: string;
  additions: number;
  deletions: number;
}

export interface GitIntelligenceSummary {
  is_repository: boolean;
  branch: string;
  upstream: string;
  branch_count: number;
  branches: string[];
  changed_files: string[];
  staged_files: string[];
  untracked_files: string[];
  deleted_files: string[];
  risky_diffs: GitFileChangeSummary[];
  change_heatmap: GitFileChangeSummary[];
  recent_commits: GitCommitSummary[];
  task_commit_links: string[];
  summary: string;
}

export interface WorkspaceWatcherSnapshot {
  workspace_root: string;
  scanned_at: string;
  file_count: number;
  fingerprint: string;
  dependency_fingerprint: string;
  file_states: WorkspaceFileState[];
  events: WorkspaceWatchEvent[];
  validation_drift: string[];
  git: GitIntelligenceSummary;
}

export interface ProjectHealthMetric {
  name: string;
  status: 'healthy' | 'warning' | 'critical' | 'unknown' | string;
  score: number;
  summary: string;
  evidence: string[];
  related_files: string[];
}

export interface ProjectHealthSnapshot {
  workspace_root: string;
  generated_at: string;
  score: number;
  status: 'healthy' | 'watch' | 'attention' | 'critical' | string;
  metrics: ProjectHealthMetric[];
  top_risks: string[];
}

export interface WorkspaceRecommendation {
  id: string;
  workspace_root: string;
  created_at: string;
  updated_at: string;
  dismissed_at: string;
  severity: RecommendationSeverity;
  category: string;
  title: string;
  detail: string;
  rationale: string;
  status: RecommendationStatus;
  related_files: string[];
  related_tasks: string[];
  evidence: Record<string, unknown>;
  fix_prompt: string;
  fix_task_id: string;
}

export interface ScheduledIntelligenceJob {
  id: string;
  name: string;
  kind: string;
  schedule_label: string;
  enabled: boolean;
  safe_by_default: boolean;
  last_run_at: string;
  next_run_hint: string;
  status: 'idle' | 'running' | 'completed' | 'failed' | 'skipped' | string;
  summary: string;
}

export interface WorkspaceOperationsSnapshot {
  workspace_root: string;
  generated_at: string;
  watcher: WorkspaceWatcherSnapshot;
  health: ProjectHealthSnapshot;
  recommendations: WorkspaceRecommendation[];
  scheduled_jobs: ScheduledIntelligenceJob[];
  git: GitIntelligenceSummary;
  long_term_memory: string[];
  recent_events: WorkspaceWatchEvent[];
}

export interface WorkspaceOperationsScanRequest {
  workspace_root?: string;
  refresh_project_intelligence?: boolean;
  generate_recommendations?: boolean;
  include_git?: boolean;
}

export interface RecommendationActionRequest {
  reason?: string;
}

export interface RecommendationFixRequest {
  reason?: string;
  create_task?: boolean;
}

export interface RecommendationFixResponse {
  recommendation: WorkspaceRecommendation;
  task: TaskSummary | null;
  event: ToolEvent | null;
  message: string;
}

export interface ScheduledJobRunRequest {
  workspace_root?: string;
  job_ids?: string[];
  allow_commands?: boolean;
}

export interface ScheduledJobRunResponse {
  workspace_root: string;
  jobs: ScheduledIntelligenceJob[];
  snapshot: WorkspaceOperationsSnapshot | null;
  warnings: string[];
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

export type AdaptiveTaskOutcomeStatus = 'success' | 'failed' | 'rolled_back' | 'canceled' | 'blocked' | 'unknown';

export interface TaskOutcomeRecord {
  id: string;
  task_id: string;
  project_id: string;
  workspace_root: string;
  title: string;
  status: string;
  outcome: AdaptiveTaskOutcomeStatus;
  success: boolean;
  repair_count: number;
  validation_runs: number;
  validation_passes: number;
  validation_failures: number;
  validation_pass_rate: number;
  retry_count: number;
  approval_count: number;
  rejection_count: number;
  rollback_count: number;
  completion_time_seconds: number | null;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  model_used: string;
  provider_id: string;
  route_role: string;
  routing_path: string[];
  context_files: string[];
  memory_refs: string[];
  checkpoints: string[];
  error_summary: string;
  final_summary: string;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  metadata: Record<string, unknown>;
}

export interface AdaptiveQualityScore {
  dimension: string;
  key: string;
  label: string;
  score: number;
  confidence: number;
  sample_size: number;
  trend: 'improving' | 'stable' | 'declining' | 'unknown' | string;
  reasons: string[];
  recommendations: string[];
  metadata: Record<string, unknown>;
}

export interface AdaptiveRouteRecommendation {
  provider_id: string;
  provider_label: string;
  model: string;
  role: string;
  profile_id: string;
  action: 'prefer' | 'hold' | 'monitor' | 'deprioritize' | string;
  score: number;
  confidence: number;
  reasons: string[];
  risks: string[];
  metadata: Record<string, unknown>;
}

export interface AdaptiveInsight {
  id: string;
  category: string;
  key: string;
  title: string;
  detail: string;
  severity: 'info' | 'low' | 'medium' | 'high' | string;
  score: number;
  evidence: string[];
  recommendations: string[];
  related_tasks: string[];
  related_files: string[];
  metadata: Record<string, unknown>;
}

export interface IntelligencePolicyProfile {
  id: string;
  name: string;
  description: string;
  privacy_mode: string;
  routing_strategy: string;
  cost_priority: number;
  latency_priority: number;
  reasoning_bias: number;
  max_context_pressure: number;
  allow_cloud: boolean;
  allow_remote_workers: boolean;
  auto_apply_policy: boolean;
  review_required: boolean;
  active: boolean;
  created_at: string;
  updated_at: string;
  score_weights: Record<string, number>;
  metadata: Record<string, unknown>;
}

export interface AdaptivePolicyCheckpoint {
  id: string;
  created_at: string;
  reason: string;
  active_profile_id: string;
  profiles: IntelligencePolicyProfile[];
}

export interface AdaptiveBenchmarkReport {
  id: string;
  workspace_root: string;
  created_at: string;
  suite_id: string;
  suite_label: string;
  status: 'passed' | 'regressed' | 'insufficient' | string;
  baseline_score: number;
  candidate_score: number;
  regression_detected: boolean;
  reproducibility_key: string;
  metrics: Record<string, number>;
  recommendations: string[];
  warnings: string[];
}

export interface EvaluationReplayResult {
  id: string;
  workspace_root: string;
  created_at: string;
  source_task_id: string;
  status: 'matched' | 'improved' | 'regressed' | 'insufficient' | string;
  previous_score: number;
  replay_score: number;
  regression_detected: boolean;
  previous_route: string[];
  replay_route: string[];
  differences: string[];
  recommendations: string[];
  metadata: Record<string, unknown>;
}

export interface AdaptiveIntelligenceSnapshot {
  workspace_root: string;
  generated_at: string;
  active_profile: IntelligencePolicyProfile;
  profiles: IntelligencePolicyProfile[];
  outcomes: TaskOutcomeRecord[];
  quality_scores: AdaptiveQualityScore[];
  route_recommendations: AdaptiveRouteRecommendation[];
  repair_insights: AdaptiveInsight[];
  context_insights: AdaptiveInsight[];
  feedback_insights: AdaptiveInsight[];
  benchmark_reports: AdaptiveBenchmarkReport[];
  replay_results: EvaluationReplayResult[];
  policy_checkpoints: AdaptivePolicyCheckpoint[];
  recommendations: string[];
  warnings: string[];
}

export interface AdaptiveIntelligenceRefreshRequest {
  workspace_root?: string;
  limit?: number;
  refresh_outcomes?: boolean;
}

export interface AdaptivePolicyProfileUpdateRequest {
  profile: IntelligencePolicyProfile;
  reason?: string;
  activate?: boolean;
}

export interface AdaptivePolicyRollbackRequest {
  checkpoint_id: string;
  reason?: string;
}

export interface AdaptiveBenchmarkRunRequest {
  workspace_root?: string;
  suite_ids?: string[];
  baseline_score?: number | null;
}

export interface AdaptiveReplayRequest {
  workspace_root?: string;
  task_ids?: string[];
  limit?: number;
}

export type PluginCapabilityKind =
  | 'agent'
  | 'validator'
  | 'provider'
  | 'scaffold_template'
  | 'telemetry_processor'
  | 'workspace_analyzer'
  | 'ui_panel'
  | string;

export type PluginPermissionScope =
  | 'read_workspace'
  | 'write_workspace'
  | 'run_validation'
  | 'run_commands'
  | 'network'
  | 'model_access'
  | 'telemetry'
  | 'ui_panel'
  | 'scaffold'
  | 'provider'
  | 'analyzer'
  | string;

export interface StableApiContract {
  id: string;
  name: string;
  version: string;
  status: 'stable' | 'beta' | 'internal' | 'deprecated' | string;
  owner: string;
  path_prefixes: string[];
  schema_refs: string[];
  compatibility_notes: string[];
  deprecation_policy: string;
}

export interface PluginLifecycleHook {
  name: 'install' | 'enable' | 'disable' | 'validate' | 'uninstall' | string;
  command: string;
  timeout_seconds: number;
  required_permissions: PluginPermissionScope[];
}

export interface PluginManifest {
  id: string;
  name: string;
  version: string;
  api_version: string;
  description: string;
  author: string;
  capabilities: PluginCapabilityKind[];
  permissions: PluginPermissionScope[];
  sandbox_profile: string;
  signature: string;
  signing_key_fingerprint: string;
  lifecycle_hooks: PluginLifecycleHook[];
  entrypoint: string;
  ui_panel_route: string;
  enabled: boolean;
  trusted: boolean;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface PluginRegistrationRequest {
  manifest: PluginManifest;
  enable?: boolean;
  trust?: boolean;
  reason?: string;
}

export interface PluginValidationRequest {
  manifest: PluginManifest;
  require_signature?: boolean;
}

export interface PluginActionRequest {
  reason?: string;
}

export interface PluginValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  normalized_manifest: PluginManifest | null;
}

export interface EnterprisePolicyProfile {
  id: string;
  name: string;
  description: string;
  active: boolean;
  audit_trails: boolean;
  permission_profile: string;
  privacy_mode: 'local_first' | 'privacy_first' | 'balanced' | 'enterprise_locked' | 'shared_workspace' | string;
  encrypted_workspace_storage: boolean;
  provider_allowlist: string[];
  provider_blocklist: string[];
  network_allowlist: string[];
  network_blocklist: string[];
  enforce_local_models: boolean;
  allow_remote_workers: boolean;
  telemetry_retention_days: number;
  plugin_signing_required: boolean;
  command_execution_default: 'deny' | 'approval_required' | 'allow_safe' | string;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface EnterprisePolicyUpdateRequest {
  profile: EnterprisePolicyProfile;
  reason?: string;
}

export interface RuntimeRecoverySnapshot {
  generated_at: string;
  database_path: string;
  database_ok: boolean;
  database_message: string;
  open_tasks: number;
  interrupted_tasks: TaskSummary[];
  recoverable_tasks: TaskSummary[];
  stale_workers: string[];
  queue_recovery_items: ExecutionQueueItem[];
  checkpoint_count: number;
  latest_checkpoint_id: string;
  safe_shutdown_ready: boolean;
  recommended_actions: string[];
}

export interface ReliabilityMetric {
  name: string;
  value: number;
  unit: string;
  status: 'healthy' | 'watch' | 'degraded' | 'unknown' | string;
  target: number | null;
  detail: string;
  trend: 'improving' | 'stable' | 'declining' | 'unknown' | string;
  metadata: Record<string, unknown>;
}

export interface ProductizationRefreshRequest {
  workspace_root?: string;
  refresh_metrics?: boolean;
}

export interface ProductizationSnapshot {
  workspace_root: string;
  generated_at: string;
  api_version: string;
  stable_apis: StableApiContract[];
  plugins: PluginManifest[];
  plugin_validation: PluginValidationResult[];
  enterprise_policy: EnterprisePolicyProfile;
  recovery: RuntimeRecoverySnapshot;
  metrics: ReliabilityMetric[];
  performance: Record<string, unknown>;
  scaling: Record<string, unknown>;
  packaging: Record<string, unknown>;
  docs: string[];
  recommendations: string[];
  warnings: string[];
}

export type EcosystemPackageKind =
  | 'agent'
  | 'validator'
  | 'scaffold_pack'
  | 'workflow'
  | 'routing_profile'
  | 'telemetry_analyzer'
  | 'workspace_intelligence_pack';
export type EcosystemTrustLevel = 'untrusted' | 'reviewed' | 'trusted' | 'organization' | 'signed';
export type EcosystemWorkflowStepKind =
  | 'inspect'
  | 'plan'
  | 'agent'
  | 'edit'
  | 'review'
  | 'validate'
  | 'repair'
  | 'approval'
  | 'memory'
  | 'summarize';
export type SharedIntelligenceProfileKind =
  | 'routing_strategy'
  | 'validation_profile'
  | 'repair_heuristics'
  | 'project_memory_pack'
  | 'architecture_pattern'
  | 'benchmark_profile';

export interface EcosystemPackageManifest {
  id: string;
  name: string;
  kind: EcosystemPackageKind;
  version: string;
  api_version: string;
  description: string;
  author: string;
  compatibility: Record<string, unknown>;
  trust_level: EcosystemTrustLevel;
  sandbox_permissions: string[];
  permission_scopes: string[];
  update_channel: 'stable' | 'beta' | 'nightly' | 'local' | string;
  signature: string;
  signing_key_fingerprint: string;
  checksum: string;
  entrypoint: string;
  homepage: string;
  enabled: boolean;
  installed: boolean;
  installed_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface EcosystemPackageValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  trust_score: number;
  normalized_manifest: EcosystemPackageManifest | null;
}

export interface EcosystemPackageValidationRequest {
  manifest: EcosystemPackageManifest;
  require_signature?: boolean;
}

export interface EcosystemPackageRegistrationRequest {
  manifest: EcosystemPackageManifest;
  enable?: boolean;
  trust_level?: EcosystemTrustLevel | null;
  reason?: string;
}

export interface EcosystemPackageActionRequest {
  reason?: string;
  trust_level?: EcosystemTrustLevel | null;
}

export interface WorkflowApprovalRequirement {
  id: string;
  title: string;
  reason: string;
  required_before_step: string;
  permission_scope: string;
}

export interface WorkflowStepDefinition {
  id: string;
  title: string;
  kind: EcosystemWorkflowStepKind;
  agent_role: string;
  description: string;
  depends_on: string[];
  validation_commands: string[];
  approval_required: boolean;
  max_attempts: number;
  metadata: Record<string, unknown>;
}

export interface EcosystemWorkflowDefinition {
  id: string;
  name: string;
  version: string;
  api_version: string;
  category: string;
  description: string;
  steps: WorkflowStepDefinition[];
  required_agents: string[];
  approvals: WorkflowApprovalRequirement[];
  validation_commands: string[];
  package_dependencies: string[];
  signed: boolean;
  signature: string;
  trust_level: EcosystemTrustLevel;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface WorkflowRunRequest {
  workspace_root?: string | null;
  user_goal?: string;
  priority?: number;
  start_immediately?: boolean;
  metadata?: Record<string, unknown>;
}

export interface WorkflowRunResponse {
  workflow: EcosystemWorkflowDefinition;
  task: TaskSummary;
  subtasks: TaskSummary[];
  events: ToolEvent[];
  message: string;
}

export interface SharedIntelligenceProfile {
  id: string;
  name: string;
  kind: SharedIntelligenceProfileKind;
  version: string;
  description: string;
  source: string;
  exported_at: string;
  imported_at: string;
  trust_level: EcosystemTrustLevel;
  payload: Record<string, unknown>;
  checksum: string;
  signature: string;
  metadata: Record<string, unknown>;
}

export interface SharedIntelligenceProfileImportRequest {
  profile: SharedIntelligenceProfile;
  reason?: string;
}

export interface SharedIntelligenceProfileExportResponse {
  profile: SharedIntelligenceProfile;
  export_format: string;
  checksum: string;
}

export interface TeamCollaborationSummary {
  mode: 'local' | 'shared' | 'organization' | string;
  shared_task_count: number;
  shared_checkpoint_count: number;
  shared_architecture_notes: number;
  pending_approvals: number;
  collaborators: string[];
  telemetry_dashboards: string[];
  status: 'ready' | 'limited' | 'disabled' | string;
  notes: string[];
}

export interface OrganizationPolicyProfile {
  id: string;
  name: string;
  active: boolean;
  provider_policies: Record<string, unknown>;
  privacy_policies: Record<string, unknown>;
  approval_requirements: Record<string, unknown>;
  validation_standards: Record<string, unknown>;
  package_restrictions: Record<string, unknown>;
  audit_requirements: Record<string, unknown>;
  require_signed_packages: boolean;
  allow_community_packages: boolean;
  collaboration_mode: 'local' | 'shared' | 'organization' | string;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface OrganizationPolicyUpdateRequest {
  profile: OrganizationPolicyProfile;
  reason?: string;
}

export interface KnowledgeGraphNode {
  id: string;
  kind: string;
  label: string;
  path: string;
  summary: string;
  importance: number;
  metadata: Record<string, unknown>;
}

export interface KnowledgeGraphEdge {
  source: string;
  target: string;
  kind: string;
  weight: number;
  summary: string;
  metadata: Record<string, unknown>;
}

export interface KnowledgeGraphSnapshot {
  workspace_root: string;
  generated_at: string;
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
  modules_total: number;
  api_routes_total: number;
  dependencies_total: number;
  decisions_total: number;
  recurring_failures_total: number;
  recommendations: string[];
}

export interface CrossProjectInsight {
  id: string;
  title: string;
  category: string;
  severity: 'low' | 'medium' | 'high' | string;
  projects: string[];
  related_files: string[];
  detail: string;
  recommendation: string;
  evidence: Record<string, unknown>;
}

export interface EcosystemSearchRequest {
  workspace_root?: string | null;
  query: string;
  scopes?: string[];
  limit?: number;
}

export interface EcosystemSearchResult {
  id: string;
  kind: string;
  title: string;
  detail: string;
  reference: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface EcosystemSearchResponse {
  query: string;
  generated_at: string;
  results: EcosystemSearchResult[];
  scope_summary: Record<string, number>;
  reconstruction: ToolEvent[];
}

export interface ReproducibilityArtifact {
  kind: string;
  reference: string;
  checksum: string;
  payload: Record<string, unknown>;
}

export interface ReproducibilityRecord {
  id: string;
  workspace_root: string;
  task_id: string;
  created_at: string;
  deterministic_hash: string;
  status: 'ready' | 'partial' | 'missing_task' | string;
  artifacts: ReproducibilityArtifact[];
  replay_notes: string[];
  metadata: Record<string, unknown>;
}

export interface ReproducibilityRequest {
  workspace_root?: string | null;
  task_id?: string;
  include_timeline?: boolean;
}

export interface EcosystemAuditEvent {
  id: string;
  created_at: string;
  actor: string;
  action: string;
  subject_id: string;
  status: EventStatus;
  detail: string;
  metadata: Record<string, unknown>;
}

export interface GovernanceTrustSignal {
  id: string;
  label: string;
  status: 'trusted' | 'review' | 'blocked' | string;
  score: number;
  detail: string;
  evidence: Record<string, unknown>;
}

export interface EcosystemRefreshRequest {
  workspace_root?: string | null;
  rebuild_graph?: boolean;
  include_search_query?: string;
}

export interface EcosystemSnapshot {
  workspace_root: string;
  generated_at: string;
  api_version: string;
  marketplace_catalog: EcosystemPackageManifest[];
  packages: EcosystemPackageManifest[];
  package_validation: EcosystemPackageValidationResult[];
  workflows: EcosystemWorkflowDefinition[];
  shared_profiles: SharedIntelligenceProfile[];
  team: TeamCollaborationSummary;
  organization_policy: OrganizationPolicyProfile;
  knowledge_graph: KnowledgeGraphSnapshot;
  cross_project_insights: CrossProjectInsight[];
  search: EcosystemSearchResponse | null;
  reproducibility: ReproducibilityRecord[];
  governance: GovernanceTrustSignal[];
  audit_events: EcosystemAuditEvent[];
  recommendations: string[];
  warnings: string[];
}

export type AutonomousObjectiveStatus =
  | 'simulating'
  | 'queued'
  | 'discovery'
  | 'planning'
  | 'running'
  | 'needs_approval'
  | 'validating'
  | 'repairing'
  | 'reviewing'
  | 'optimizing'
  | 'finalizing'
  | 'completed'
  | 'failed'
  | 'canceled'
  | 'paused';
export type AutonomousPhaseKind =
  | 'discovery'
  | 'planning'
  | 'implementation'
  | 'validation'
  | 'review'
  | 'optimization'
  | 'finalization';
export type AutonomousPhaseStatus = 'queued' | 'running' | 'needs_approval' | 'completed' | 'failed' | 'skipped' | 'paused';
export type AutonomousApprovalStatus = 'pending' | 'approved' | 'rejected' | 'canceled';

export interface AutonomousSafetyLimits {
  max_iterations: number;
  max_parallel_agents: number;
  token_budget: number;
  max_file_changes: number;
  max_dependency_changes: number;
  max_repair_attempts: number;
  approval_checkpoint_interval: number;
  rollback_required: boolean;
  protected_file_zones: string[];
  stop_on_validation_failure: boolean;
  allow_dependency_changes: boolean;
  allow_destructive_actions: boolean;
  metadata: Record<string, unknown>;
}

export interface AutonomousGoalMemory {
  objective_history: string[];
  completed_phases: string[];
  failed_approaches: string[];
  successful_patterns: string[];
  remaining_work: string[];
  user_preferences: string[];
  updated_at: string;
}

export interface AutonomousObjective {
  id: string;
  workspace_root: string;
  title: string;
  user_goal: string;
  status: AutonomousObjectiveStatus;
  priority: number;
  created_at: string;
  updated_at: string;
  completed_at: string;
  current_phase: AutonomousPhaseKind;
  iteration_count: number;
  repair_count: number;
  assigned_agent_roles: string[];
  task_ids: string[];
  phase_ids: string[];
  approval_gate_ids: string[];
  simulation_ids: string[];
  safety_limits: AutonomousSafetyLimits;
  goal_memory: AutonomousGoalMemory;
  final_summary: string;
  error_summary: string;
  metadata: Record<string, unknown>;
}

export interface AutonomousPhase {
  id: string;
  objective_id: string;
  workspace_root: string;
  kind: AutonomousPhaseKind;
  title: string;
  status: AutonomousPhaseStatus;
  summary: string;
  started_at: string;
  completed_at: string;
  task_ids: string[];
  agent_roles: string[];
  validation_commands: string[];
  approval_required: boolean;
  iteration_count: number;
  error_summary: string;
  metadata: Record<string, unknown>;
}

export interface AutonomousApprovalGate {
  id: string;
  objective_id: string;
  phase_id: string;
  kind: string;
  title: string;
  reason: string;
  status: AutonomousApprovalStatus;
  required: boolean;
  created_at: string;
  resolved_at: string;
  resolved_by: string;
  metadata: Record<string, unknown>;
}

export interface AutonomousAgentAssignment {
  id: string;
  objective_id: string;
  phase_id: string;
  role: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'blocked' | string;
  task_id: string;
  summary: string;
  started_at: string;
  completed_at: string;
  metadata: Record<string, unknown>;
}

export interface AutonomousVerificationSignal {
  id: string;
  objective_id: string;
  phase_id: string;
  kind: string;
  command: string;
  status: 'queued' | 'passed' | 'failed' | 'skipped' | 'warning' | string;
  detail: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface AutonomousSimulationEstimate {
  id: string;
  objective_id: string;
  workspace_root: string;
  created_at: string;
  estimated_impact: 'low' | 'medium' | 'high' | 'very_high' | string;
  predicted_validation_risk: number;
  projected_file_changes: string[];
  projected_dependency_changes: string[];
  projected_token_cost: number;
  projected_iterations: number;
  dry_run_plan: string[];
  approval_gates: AutonomousApprovalGate[];
  warnings: string[];
  metadata: Record<string, unknown>;
}

export interface AutonomousRefactorPlan {
  id: string;
  objective_id: string;
  kind: string;
  title: string;
  target_patterns: string[];
  projected_files: string[];
  safety_notes: string[];
  approval_required: boolean;
  status: 'draft' | 'approved' | 'running' | 'completed' | 'blocked' | string;
  metadata: Record<string, unknown>;
}

export interface AutonomousExplainabilityEntry {
  id: string;
  objective_id: string;
  created_at: string;
  category: string;
  title: string;
  detail: string;
  evidence: Record<string, unknown>;
}

export interface AutonomousAnalyticsMetric {
  name: string;
  value: number;
  unit: string;
  status: 'healthy' | 'watch' | 'degraded' | 'unknown' | string;
  detail: string;
  trend: 'improving' | 'stable' | 'declining' | 'unknown' | string;
  metadata: Record<string, unknown>;
}

export interface AutonomousObjectiveCreateRequest {
  workspace_root?: string | null;
  title: string;
  user_goal: string;
  priority?: number;
  dry_run?: boolean;
  max_iterations?: number;
  token_budget?: number;
  max_parallel_agents?: number;
  protected_file_zones?: string[];
  metadata?: Record<string, unknown>;
}

export interface AutonomousObjectiveActionRequest {
  reason?: string;
  metadata?: Record<string, unknown>;
}

export interface AutonomousObjectiveIterationRequest {
  reason?: string;
  max_steps?: number;
  allow_repairs?: boolean;
  metadata?: Record<string, unknown>;
}

export interface AutonomousApprovalActionRequest {
  reason?: string;
  resolved_by?: string;
  metadata?: Record<string, unknown>;
}

export interface AutonomousObjectiveDetail {
  objective: AutonomousObjective;
  phases: AutonomousPhase[];
  approval_gates: AutonomousApprovalGate[];
  simulations: AutonomousSimulationEstimate[];
  agents: AutonomousAgentAssignment[];
  verification: AutonomousVerificationSignal[];
  refactor_plans: AutonomousRefactorPlan[];
  explanations: AutonomousExplainabilityEntry[];
  task_events: ToolEvent[];
}

export interface AutonomousEngineeringSnapshot {
  workspace_root: string;
  generated_at: string;
  api_version: string;
  objectives: AutonomousObjective[];
  active_objectives: AutonomousObjective[];
  phases: AutonomousPhase[];
  approval_gates: AutonomousApprovalGate[];
  simulations: AutonomousSimulationEstimate[];
  agents: AutonomousAgentAssignment[];
  verification: AutonomousVerificationSignal[];
  refactor_plans: AutonomousRefactorPlan[];
  explanations: AutonomousExplainabilityEntry[];
  analytics: AutonomousAnalyticsMetric[];
  recommendations: string[];
  warnings: string[];
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
