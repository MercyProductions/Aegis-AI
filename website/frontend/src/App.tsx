// frontend/src/App.tsx
import type { CSSProperties, FormEvent, ReactNode } from 'react';
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Bot,
  ChevronDown,
  CheckCircle2,
  Code,
  Copy,
  Download,
  FileCode2,
  FolderOpen,
  Loader2,
  MessageSquarePlus,
  Moon,
  Pause,
  Play,
  Save,
  Search,
  Send,
  Settings,
  Sparkles,
  Square,
  Sun,
  Trash2,
  User,
  Wrench,
  X,
  Zap,
  Brain
} from 'lucide-react';
import {
  activateAdaptivePolicyProfile,
  approveAutonomousGate,
  applyFileChanges,
  cancelAutonomousObjective,
  cancelCreativeJob,
  compareDiff,
  createAutonomousObjective,
  createCreativeJob,
  getCurrentAccount,
  getConfig,
  getCheckpoints,
  getAdaptiveIntelligence,
  getAutonomousEngineering,
  getAutonomousObjective,
  getContinuity,
  getCreativeAssetLibrary,
  getCreativeJob,
  getCreativeStudio,
  getDistributedRuntime,
  getOperatingEnvironment,
  getPlatformDiscipline,
  getUnifiedContext,
  getUnifiedRuntime,
  getHealth,
  getModelManager,
  getModelRegistry,
  getModels,
  getValidationProfile,
  getWorkspaceHistory,
  getWorkspaceIntelligence,
  getWorkspaceProfile,
  approveTaskAction,
  cancelTask,
  createMemoryNote,
  getProjectIntelligence,
  getTaskArtifacts,
  getTaskTimeline,
  listCreativeJobs,
  listTasks,
  listFiles,
  loginAccount,
  logoutAccount,
  deleteModel,
  pullModel,
  readFile,
  reindexProjectIntelligence,
  dismissWorkspaceRecommendation,
  fixWorkspaceRecommendation,
  retryTask,
  replayAdaptiveTasks,
  rollbackAdaptivePolicy,
  restoreCheckpoint,
  dispatchExecutionQueue,
  createRemoteSyncManifest,
  disableEcosystemPackage,
  disablePlugin,
  enableEcosystemPackage,
  enablePlugin,
  exportCurrentProjectIntelligence,
  exportCreativeJob,
  runAdaptiveBenchmarks,
  runEcosystemWorkflow,
  runWorkspaceValidation,
  runWorkspaceIntelligenceJobs,
  registerAccount,
  saveConfig,
  scanWorkspaceIntelligence,
  searchEcosystem,
  setupWorkspace,
  streamAgentMessage,
  requestPasswordReset,
  refreshAdaptiveIntelligence,
  refreshEcosystem,
  refreshProductization,
  getEcosystem,
  getProductization,
  trustEcosystemPackage,
  trustPlugin,
  iterateAutonomousObjective,
  pauseAutonomousObjective,
  previewGlobalCommand,
  rejectAutonomousGate,
  simulateAutonomousObjective,
  startAutonomousObjective,
  validateEcosystemPackage,
  validatePlugin,
  updateValidationProfile
} from './api';
import { brandAssets } from './brandAssets';
import { LazyPanelBoundary } from './components/LazyPanelBoundary';
import {
  connectionStateDetail,
  connectionStateLabel,
  isLikelyConnectionError
} from './utils/connection';
import {
  buildRuntimeDiagnostics,
  type RuntimeDiagnosticCheck
} from './utils/runtimeDiagnostics';
import {
  buildAssistantSummary,
  delay,
  diagnosticStatusToEventStatus,
  findManagedModelByName,
  formatBytes,
  formatDateTime,
  formatEventTime,
  formatStatusLabel,
  isAbortError,
  managedModelFromConfig,
  mergeById,
  modelInventoryToManagedModels,
  modelOptionKey,
  readinessStatusToEventStatus,
  routeProfileLabel,
  runtimeDiagnosticActionIcon,
  shouldOfferReadinessValidation,
  shouldOfferWorkspaceSetup,
  taskStatusToEventStatus
} from './utils/appUi';
import {
  defaultAgentId,
  defaultAgentPerspective,
  detailPanelSectionOptions,
  loadAutoMemoryFingerprints,
  loadCollapsedDetailSections,
  loadCustomAgents,
  loadDetailsPanelVisible,
  loadQueueAutoSendPaused,
  loadSelectedWorkspaceFile,
  normalizeProjectRootKey,
  saveAutoMemoryFingerprints,
  saveCollapsedDetailSections,
  saveCustomAgents,
  saveDetailsPanelVisible,
  saveQueueAutoSendPaused,
  saveSelectedWorkspaceFile,
  type CustomAgent,
  type DetailPanelSection
} from './utils/appStorage';
import {
  clearStoredAuthSession,
  currentBrowserRoute,
  currentViewportSize,
  isProtectedAppRoute,
  loadStoredAuthSession,
  normalizeRoutePath,
  routeToSidebarSection,
  saveStoredAuthSession,
  sidebarSectionToRoute,
  type SidebarSection
} from './utils/appRouting';
import {
  buildConversationPreview,
  buildConversationMarkdown,
  conversationMarkdownFilename,
  createConversationId,
  deleteSavedConversation,
  loadSavedConversations,
  saveSavedConversations,
  upsertSavedConversation
} from './utils/conversations';
import {
  appendQueuedMessage,
  clearQueuedMessages,
  createQueuedMessage,
  loadQueuedMessages,
  moveQueuedMessage,
  removeQueuedMessage,
  saveQueuedMessages,
  shouldQueueOutboundMessage
} from './utils/messageQueue';
import { clearComposerDraft, loadComposerDraft, saveComposerDraft } from './utils/composerDraft';
import { addPinnedContextPath, removePinnedContextPath } from './utils/contextPins';
import {
  appliedChangeStatus,
  applyStatusWithWarnings,
  changesForApply,
  generatedChangeApplyIntent,
  generatedChangeId as changeId,
  generatedValidationContextStatus,
  isGeneratedChangeApplied,
  mergeAppliedChangeRefs,
  mergeApplyWarnings,
  parseGeneratedChangeTranscript,
  previewPathForApplyResult,
  remainingGeneratedChanges,
  summarizeGeneratedDiffStats,
  summarizeGeneratedChangeReview,
  unresolvedGeneratedChangeWarnings,
  warningsForGeneratedChange,
  type ApplyChangeScope,
  type GeneratedChangeValidationContext
} from './utils/generatedChanges';
import { buildAgentRequestHistory, createMissionAnchorMessage } from './utils/missionAnchor';
import { autoMemoryFingerprint, buildAutoMemoryNote } from './utils/autoMemory';
import { parseChatContentBlocks } from './utils/chatBlocks';
import { filterWorkspaceFiles } from './utils/workspaceFiles';
import {
  combinedApplyValidationStatus,
  validationRepairBriefClipboardText,
  validationRepairFollowUpPromptText,
  validationRepairPromptText,
  validationResultStatus,
  validationRunClipboardText
} from './utils/validationStatus';
import type { ConnectionState } from './utils/connection';
import type { ChatThreadPreview, SavedConversation } from './utils/conversations';
import type { QueuedMessage } from './utils/messageQueue';
import type {
  AdaptiveInsight,
  AdaptiveIntelligenceSnapshot,
  AdaptiveQualityScore,
  AdaptiveRouteRecommendation,
  AegisContinuitySnapshot,
  AgentResponse,
  AppConfig,
  AuthLoginRequest,
  AuthRegisterRequest,
  AuthSessionResponse,
  CheckpointSummary,
  ChatMessage,
  CommandRun,
  DiffCompareResponse,
  DistributedRuntimeSnapshot,
  AutonomousEngineeringSnapshot,
  AutonomousObjectiveDetail,
  EcosystemPackageManifest,
  EcosystemSearchResponse,
  EcosystemSnapshot,
  FileChange,
  FixMemoryEntry,
  HealthResponse,
  HistoryResponse,
  MediaAssetLibraryResponse,
  MediaCapabilitiesResponse,
  MediaJobResponse,
  MediaKind,
  ManagedModelInfo,
  ModelInventoryResponse,
  ModelManagerResponse,
  ModelRegistryResponse,
  Mode,
  ModeOption,
  OperatingEnvironmentSnapshot,
  PlatformDisciplineSnapshot,
  PluginManifest,
  ProductizationSnapshot,
  ProjectIntelligenceSnapshot,
  ProjectMemoryEntry,
  RepairAttempt,
  WorkspaceOperationsSnapshot,
  WorkspaceRecommendation,
  TaskArtifactsResponse,
  TaskSummary,
  ToolEvent,
  GlobalCommandResponse,
  UnifiedContextSnapshot,
  UnifiedRuntimeSnapshot,
  ValidationRecipe,
  ValidateResponse,
  ValidationSuggestion,
  WorkspaceFile,
  WorkspaceProfileResponse
} from './types';

const ApprovalSettings = lazy(() =>
  import('./components/ApprovalSettings').then((module) => ({ default: module.ApprovalSettings }))
);
const MemoryEditor = lazy(() =>
  import('./components/MemoryEditor').then((module) => ({ default: module.MemoryEditor }))
);
const ObservabilityPanel = lazy(() =>
  import('./components/ObservabilityPanel').then((module) => ({ default: module.ObservabilityPanel }))
);
const PublicSite = lazy(() =>
  import('./components/PublicSite').then((module) => ({ default: module.PublicSite }))
);
const ProductizationSurface = lazy(() =>
  import('./components/ProductizationSurface').then((module) => ({ default: module.ProductizationSurface }))
);
const CreativeStudioSurface = lazy(() =>
  import('./components/CreativeStudioSurface').then((module) => ({ default: module.CreativeStudioSurface }))
);
const ModelSelector = lazy(() =>
  import('./components/ModelSelector').then((module) => ({ default: module.ModelSelector }))
);
const TaskStatusSummary = lazy(() =>
  import('./components/TaskStatusSummary').then((module) => ({ default: module.TaskStatusSummary }))
);

const starterPrompts = [
  'Help me debug this error',
  'Write a function to parse JSON safely in TypeScript',
  'Refactor this code to be more efficient',
  'Explain how this code works',
  'Create a batch script that prints hello world to the console',
  'Create a project from scratch in this directory'
];

const thinkingStates = [
  'Analyzing your request',
  'Generating a solution',
  'Preparing file changes',
  'Checking the workspace',
  'Finalizing the response'
];
const fallbackModeOptions: ModeOption[] = [
  { id: 'build', label: 'Build', description: 'Plan and make workspace changes.' },
  { id: 'develop', label: 'Develop', description: 'Iterate on code and repair issues.' },
  { id: 'review', label: 'Review', description: 'Inspect code, risks, and tests.' },
  { id: 'chat', label: 'Chat', description: 'Answer questions without a build bias.' }
];
const productName = 'Auralith OS';
const assistantIdentity = 'Auralith Prime';
const runtimeIdentity = 'Aegis Core';
const defaultAssistantMission =
  'A local-first AI operating environment for coding, automation, research, orchestration, creative workflows, and intelligent task execution.';

type Palette = ReturnType<typeof getPalette>;
type SubmitOptions = Partial<QueuedMessage> & {
  repairTrailId?: string;
};
type ValidationRepairTrailStatus = 'sent' | 'passed' | 'failed';
type ValidationRepairTrailStatusFilter = 'all' | ValidationRepairTrailStatus;
type ActivityFilter = 'all' | 'issues' | 'commands';
type ValidationRepairTrailChange = Pick<FileChange, 'action' | 'path'>;
type TaskBoardFilter = 'active' | 'completed' | 'failed' | 'all';
type ValidationRepairTrailItem = {
  id: string;
  createdAt: string;
  command: string;
  prompt: string;
  followUpPrompt: string;
  sourceSummary: string;
  sourceReason: string;
  sourceExitCode: number | null;
  contextChanges: ValidationRepairTrailChange[];
  contextPaths: string[];
  status: ValidationRepairTrailStatus;
  resultSummary: string;
  resultExitCode: number | null;
  responseTaskId: string;
};
const validationRepairTrailStatusFilters: Array<{ value: ValidationRepairTrailStatusFilter; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'sent', label: 'Sent' },
  { value: 'failed', label: 'Failed' },
  { value: 'passed', label: 'Passed' }
];
const activityFilterOptions: Array<{ value: ActivityFilter; label: string; ariaLabel: string }> = [
  { value: 'all', label: 'All', ariaLabel: 'Show all activity events' },
  { value: 'issues', label: 'Issues', ariaLabel: 'Show issue activity events' },
  { value: 'commands', label: 'Commands', ariaLabel: 'Show command activity events' }
];
const taskFilterOptions: Array<{ value: TaskBoardFilter; label: string }> = [
  { value: 'active', label: 'Active' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'all', label: 'All' }
];
const terminalTaskStatuses = new Set(['completed', 'failed', 'canceled']);
function severityToEventStatus(severity: string): ToolEvent['status'] {
  if (severity === 'critical' || severity === 'high') return 'error';
  if (severity === 'medium' || severity === 'low') return 'warning';
  return 'ok';
}
function healthStatusToEventStatus(status: string): ToolEvent['status'] {
  if (status === 'critical' || status === 'failed' || status === 'error') return 'error';
  if (
    status === 'attention' ||
    status === 'watch' ||
    status === 'warning' ||
    status === 'unknown' ||
    status === 'skipped'
  ) {
    return 'warning';
  }
  return 'ok';
}
function reliabilityStatusToEventStatus(status: string): ToolEvent['status'] {
  if (status === 'degraded' || status === 'critical' || status === 'failed') return 'error';
  if (status === 'watch' || status === 'unknown' || status === 'warning') return 'warning';
  return 'ok';
}
type SettingsTab = 'general' | 'models' | 'agents' | 'workspace' | 'advanced';

type ProjectRootSummary = {
  root: string;
  title: string;
  count: number;
  active: boolean;
  latestThread: SavedConversation | null;
  latestUpdatedAt: string;
  threads: SavedConversation[];
};
type GeneratedReviewSource = {
  changes: FileChange[];
  applied: string[];
  warnings: string[];
  checkpoint?: string | null;
  workspaceRoot: string;
  taskId?: string;
  restored: boolean;
};

function App() {
  const [routePath, setRoutePath] = useState(() => currentBrowserRoute());
  const [authSession, setAuthSession] = useState<AuthSessionResponse | null>(() => loadStoredAuthSession());
  const [authLoading, setAuthLoading] = useState(false);
  const [authStatus, setAuthStatus] = useState('');
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [assistantName, setAssistantName] = useState(assistantIdentity);
  const [assistantMission, setAssistantMission] = useState('');
  const [mode, setMode] = useState<Mode>('build');
  const [workspaceRoot, setWorkspaceRoot] = useState('');
  const [applyChanges, setApplyChanges] = useState(true);
  const [message, setMessage] = useState(() => loadComposerDraft()?.content ?? '');
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [files, setFiles] = useState<WorkspaceFile[]>([]);
  const [lastResponse, setLastResponse] = useState<AgentResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeChatRequest, setActiveChatRequest] = useState(false);
  const [status, setStatus] = useState('');
  const [saveStatus, setSaveStatus] = useState('');
  const [engineReady, setEngineReady] = useState(false);
  const [engineLabel, setEngineLabel] = useState(runtimeIdentity);
  const [lastHealth, setLastHealth] = useState<HealthResponse | null>(null);
  const [modelReady, setModelReady] = useState(false);
  const [modelMessage, setModelMessage] = useState('');
  const [modelApi, setModelApi] = useState('ollama');
  const [modelEndpoint, setModelEndpoint] = useState('http://127.0.0.1:11434');
  const [modelName, setModelName] = useState('qwen2.5-coder:7b');
  const [commandAllowlist, setCommandAllowlist] = useState('');
  const [commandTimeout, setCommandTimeout] = useState(120);
  const [autoRunValidation, setAutoRunValidation] = useState(false);
  const [runValidation, setRunValidation] = useState(false);
  const [thinkingIndex, setThinkingIndex] = useState(0);
  const [selectedChangeId, setSelectedChangeId] = useState('');
  const [selectedPreviewTab, setSelectedPreviewTab] = useState<'diff' | 'content'>('diff');
  const [selectedChangeDiff, setSelectedChangeDiff] = useState<DiffCompareResponse | null>(null);
  const [selectedChangeDiffStatus, setSelectedChangeDiffStatus] = useState('');
  const [changeDiffs, setChangeDiffs] = useState<Record<string, DiffCompareResponse>>({});
  const [changeDiffSummaryStatus, setChangeDiffSummaryStatus] = useState('');
  const [restoredReviewSource, setRestoredReviewSource] = useState<GeneratedReviewSource | null>(null);
  const [selectedFilePath, setSelectedFilePath] = useState('');
  const [selectedFileContent, setSelectedFileContent] = useState('');
  const [fileStatus, setFileStatus] = useState('');
  const [fileSearch, setFileSearch] = useState('');
  const [pinnedContextPaths, setPinnedContextPaths] = useState<string[]>([]);
  const [manualEvents, setManualEvents] = useState<ToolEvent[]>([]);
  const [manualValidation, setManualValidation] = useState<CommandRun | null>(null);
  const [validationContext, setValidationContext] = useState<GeneratedChangeValidationContext | null>(null);
  const [validationRepairTrail, setValidationRepairTrail] = useState<ValidationRepairTrailItem[]>([]);
  const [validationRepairSearch, setValidationRepairSearch] = useState('');
  const [validationRepairStatusFilter, setValidationRepairStatusFilter] = useState<ValidationRepairTrailStatusFilter>('all');
  const [showDetailsPanel, setShowDetailsPanel] = useState(() => loadDetailsPanelVisible());
  const [collapsedDetailSections, setCollapsedDetailSections] = useState<DetailPanelSection[]>(() =>
    loadCollapsedDetailSections()
  );
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [showMemoryEditor, setShowMemoryEditor] = useState(false);
  const [showApprovalSettings, setShowApprovalSettings] = useState(false);
  const [viewportSize, setViewportSize] = useState(currentViewportSize);
  const [retryCount, setRetryCount] = useState(0);
  const [maxRetries, setMaxRetries] = useState(3);
  const [chatSearch, setChatSearch] = useState('');
  const [connectionState, setConnectionState] = useState<ConnectionState>('checking');
  const [queuedMessages, setQueuedMessages] = useState<QueuedMessage[]>(() => loadQueuedMessages());
  const [showQueueTray, setShowQueueTray] = useState(false);
  const [queueAutoSendPaused, setQueueAutoSendPaused] = useState(() => loadQueueAutoSendPaused());
  const [savedThreads, setSavedThreads] = useState<SavedConversation[]>(() => loadSavedConversations());
  const [currentThreadId, setCurrentThreadId] = useState(() => createConversationId());
  const [activeThreadId, setActiveThreadId] = useState(() => currentThreadId);
  const [workspaceHistory, setWorkspaceHistory] = useState<HistoryResponse | null>(null);
  const [workspaceProfile, setWorkspaceProfile] = useState<WorkspaceProfileResponse | null>(null);
  const [workspaceProfileStatus, setWorkspaceProfileStatus] = useState('');
  const [projectIntelligence, setProjectIntelligence] = useState<ProjectIntelligenceSnapshot | null>(null);
  const [projectIntelligenceStatus, setProjectIntelligenceStatus] = useState('');
  const [projectIntelligenceLoading, setProjectIntelligenceLoading] = useState(false);
  const [workspaceOperations, setWorkspaceOperations] = useState<WorkspaceOperationsSnapshot | null>(null);
  const [workspaceOperationsStatus, setWorkspaceOperationsStatus] = useState('');
  const [workspaceOperationsLoading, setWorkspaceOperationsLoading] = useState(false);
  const [workspaceOperationsActionId, setWorkspaceOperationsActionId] = useState('');
  const [unifiedRuntime, setUnifiedRuntime] = useState<UnifiedRuntimeSnapshot | null>(null);
  const [unifiedContext, setUnifiedContext] = useState<UnifiedContextSnapshot | null>(null);
  const [continuity, setContinuity] = useState<AegisContinuitySnapshot | null>(null);
  const [platformDiscipline, setPlatformDiscipline] = useState<PlatformDisciplineSnapshot | null>(null);
  const [globalCommandDraft, setGlobalCommandDraft] = useState('Refactor the UI using the latest mockup assets');
  const [globalCommandPreview, setGlobalCommandPreview] = useState<GlobalCommandResponse | null>(null);
  const [operatingEnvironment, setOperatingEnvironment] = useState<OperatingEnvironmentSnapshot | null>(null);
  const [distributedRuntime, setDistributedRuntime] = useState<DistributedRuntimeSnapshot | null>(null);
  const [distributedRuntimeStatus, setDistributedRuntimeStatus] = useState('');
  const [distributedRuntimeLoading, setDistributedRuntimeLoading] = useState(false);
  const [distributedRuntimeAction, setDistributedRuntimeAction] = useState('');
  const [adaptiveIntelligence, setAdaptiveIntelligence] = useState<AdaptiveIntelligenceSnapshot | null>(null);
  const [adaptiveIntelligenceStatus, setAdaptiveIntelligenceStatus] = useState('');
  const [adaptiveIntelligenceLoading, setAdaptiveIntelligenceLoading] = useState(false);
  const [adaptiveIntelligenceAction, setAdaptiveIntelligenceAction] = useState('');
  const [productization, setProductization] = useState<ProductizationSnapshot | null>(null);
  const [productizationStatus, setProductizationStatus] = useState('');
  const [productizationLoading, setProductizationLoading] = useState(false);
  const [productizationAction, setProductizationAction] = useState('');
  const [ecosystemSnapshot, setEcosystemSnapshot] = useState<EcosystemSnapshot | null>(null);
  const [ecosystemSearch, setEcosystemSearch] = useState<EcosystemSearchResponse | null>(null);
  const [ecosystemSearchQuery, setEcosystemSearchQuery] = useState('api route');
  const [ecosystemStatus, setEcosystemStatus] = useState('');
  const [ecosystemLoading, setEcosystemLoading] = useState(false);
  const [ecosystemAction, setEcosystemAction] = useState('');
  const [autonomousSnapshot, setAutonomousSnapshot] = useState<AutonomousEngineeringSnapshot | null>(null);
  const [selectedAutonomousObjective, setSelectedAutonomousObjective] = useState<AutonomousObjectiveDetail | null>(null);
  const [autonomousObjectiveTitle, setAutonomousObjectiveTitle] = useState('Improve test coverage');
  const [autonomousObjectiveGoal, setAutonomousObjectiveGoal] = useState('Improve test coverage for the most important project modules.');
  const [autonomousStatus, setAutonomousStatus] = useState('');
  const [autonomousLoading, setAutonomousLoading] = useState(false);
  const [autonomousAction, setAutonomousAction] = useState('');
  const [creativeCapabilities, setCreativeCapabilities] = useState<MediaCapabilitiesResponse | null>(null);
  const [creativeLibrary, setCreativeLibrary] = useState<MediaAssetLibraryResponse | null>(null);
  const [creativeJobs, setCreativeJobs] = useState<MediaJobResponse[]>([]);
  const [selectedCreativeJob, setSelectedCreativeJob] = useState<MediaJobResponse | null>(null);
  const [creativeStudioTab, setCreativeStudioTab] = useState<'image' | 'video' | 'beat' | 'voice' | 'library'>('image');
  const [creativePrompt, setCreativePrompt] = useState('Create a premium product mockup for Auralith Creative Studio');
  const [creativeStyle, setCreativeStyle] = useState('premium, calm, polished');
  const [creativeProviderId, setCreativeProviderId] = useState('local_creative_renderer');
  const [creativeStatus, setCreativeStatus] = useState('');
  const [creativeLoading, setCreativeLoading] = useState(false);
  const [creativeAction, setCreativeAction] = useState('');
  const [workspaceSetupLoading, setWorkspaceSetupLoading] = useState(false);
  const [checkpoints, setCheckpoints] = useState<CheckpointSummary[]>([]);
  const [checkpointStatus, setCheckpointStatus] = useState('');
  const [checkpointLoading, setCheckpointLoading] = useState(false);
  const [restoringCheckpointId, setRestoringCheckpointId] = useState('');
  const [validationRecipe, setValidationRecipe] = useState<ValidationRecipe | null>(null);
  const [validationSuggestions, setValidationSuggestions] = useState<ValidationSuggestion[]>([]);
  const [validationCommandDraft, setValidationCommandDraft] = useState('');
  const [validationNotesDraft, setValidationNotesDraft] = useState('');
  const [validationRecipeStatus, setValidationRecipeStatus] = useState('');
  const [activeSection, setActiveSection] = useState<SidebarSection>('chat');
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState('');
  const [taskTimeline, setTaskTimeline] = useState<ToolEvent[]>([]);
  const [taskArtifacts, setTaskArtifacts] = useState<TaskArtifactsResponse | null>(null);
  const [taskStatusFilter, setTaskStatusFilter] = useState<TaskBoardFilter>('active');
  const [taskStatusMessage, setTaskStatusMessage] = useState('');
  const [taskActionId, setTaskActionId] = useState('');
  const [settingsTab, setSettingsTab] = useState<SettingsTab>('general');
  const [expandedActivityEventIds, setExpandedActivityEventIds] = useState<string[]>([]);
  const [showAllActivityEvents, setShowAllActivityEvents] = useState(false);
  const [activityFilter, setActivityFilter] = useState<ActivityFilter>('all');
  const [expandedInlineReviewIds, setExpandedInlineReviewIds] = useState<string[]>([]);
  const [modelInventory, setModelInventory] = useState<ModelInventoryResponse | null>(null);
  const [modelRegistry, setModelRegistry] = useState<ModelRegistryResponse | null>(null);
  const [modelManager, setModelManager] = useState<ModelManagerResponse | null>(null);
  const [modelCatalogLoading, setModelCatalogLoading] = useState(false);
  const [modelCatalogStatus, setModelCatalogStatus] = useState('');
  const [modelSearch, setModelSearch] = useState('');
  const [projectSearch, setProjectSearch] = useState('');
  const [agentSearch, setAgentSearch] = useState('');
  const [modelPullName, setModelPullName] = useState('');
  const [modelActionName, setModelActionName] = useState('');
  const [showModelSwitcher, setShowModelSwitcher] = useState(false);
  const [customAgents, setCustomAgents] = useState<CustomAgent[]>(() => loadCustomAgents());
  const [activeAgentId, setActiveAgentId] = useState(defaultAgentId);
  const [editingAgentId, setEditingAgentId] = useState('');
  const [agentFormName, setAgentFormName] = useState('Focused Reviewer');
  const [agentFormPerspective, setAgentFormPerspective] = useState(
    'Reviews code with a conservative, security-minded perspective before changes are applied.'
  );
  const [agentFormMission, setAgentFormMission] = useState(
    'Review proposed changes, call out risks, then implement the smallest reliable fix.'
  );
  const [agentFormMode, setAgentFormMode] = useState<Mode>('review');
  const [agentFormModelName, setAgentFormModelName] = useState('qwen2.5-coder:7b');
  const activeChatAbortController = useRef<AbortController | null>(null);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const workspaceRootRef = useRef(workspaceRoot);
  const workspaceOpenRequestRef = useRef(0);
  const sectionNavigationVersionRef = useRef(0);
  const autoMemoryFingerprints = useRef<Set<string>>(new Set(loadAutoMemoryFingerprints()));

  function navigateTo(path: string, replace = false) {
    const nextRoute = normalizeRoutePath(path);
    if (typeof window !== 'undefined' && window.location.pathname !== nextRoute) {
      if (replace) {
        window.history.replaceState({}, '', nextRoute);
      } else {
        window.history.pushState({}, '', nextRoute);
      }
    }
    setRoutePath(nextRoute);
  }

  function openAppSection(section: SidebarSection) {
    sectionNavigationVersionRef.current += 1;
    setActiveSection(section);
    navigateTo(sidebarSectionToRoute(section));
  }

  function updateAuthSession(session: AuthSessionResponse) {
    saveStoredAuthSession(session);
    setAuthSession(session);
  }

  async function handleLogin(request: AuthLoginRequest) {
    setAuthLoading(true);
    setAuthStatus('');
    try {
      const session = await loginAccount(request);
      updateAuthSession(session);
      navigateTo('/app', true);
    } catch (error) {
      setAuthStatus(error instanceof Error ? error.message : 'Could not sign in.');
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleRegister(request: AuthRegisterRequest) {
    setAuthLoading(true);
    setAuthStatus('');
    try {
      const session = await registerAccount(request);
      updateAuthSession(session);
      navigateTo('/app', true);
    } catch (error) {
      setAuthStatus(error instanceof Error ? error.message : 'Could not create account.');
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleForgotPassword(email: string) {
    setAuthLoading(true);
    setAuthStatus('');
    try {
      const response = await requestPasswordReset({ email });
      setAuthStatus(response.message);
    } catch (error) {
      setAuthStatus(error instanceof Error ? error.message : 'Could not start password recovery.');
    } finally {
      setAuthLoading(false);
    }
  }

  function handleLogout() {
    const token = authSession?.token;
    clearStoredAuthSession();
    setAuthSession(null);
    setAuthStatus('Signed out.');
    navigateTo('/login', true);
    if (token) {
      void logoutAccount(token).catch(() => undefined);
    }
  }

  useEffect(() => {
    function handleRouteChange() {
      setRoutePath(currentBrowserRoute());
    }
    window.addEventListener('popstate', handleRouteChange);
    return () => window.removeEventListener('popstate', handleRouteChange);
  }, []);

  useEffect(() => {
    function handleViewportResize() {
      setViewportSize(currentViewportSize());
    }

    handleViewportResize();
    window.addEventListener('resize', handleViewportResize);
    return () => window.removeEventListener('resize', handleViewportResize);
  }, []);

  useEffect(() => {
    if (!authSession?.token) return;
    let isCurrent = true;
    void getCurrentAccount(authSession.token)
      .then((session) => {
        if (!isCurrent) return;
        const verifiedSession = { ...session, token: authSession.token };
        saveStoredAuthSession(verifiedSession);
        setAuthSession(verifiedSession);
      })
      .catch(() => {
        if (!isCurrent) return;
        clearStoredAuthSession();
        setAuthSession(null);
        if (isProtectedAppRoute(routePath)) {
          setAuthStatus(`Please log in to open the ${productName} workspace.`);
          navigateTo('/login', true);
        }
      });
    return () => {
      isCurrent = false;
    };
  }, [authSession?.token]);

  useEffect(() => {
    if (isProtectedAppRoute(routePath) && !authSession) {
      setAuthStatus(`Please log in to open the ${productName} workspace.`);
      navigateTo('/login', true);
      return;
    }
    if (authSession && (routePath === '/login' || routePath === '/register')) {
      navigateTo('/app', true);
    }
  }, [routePath, authSession]);

  useEffect(() => {
    if (!authSession || !isProtectedAppRoute(routePath)) return;
    const nextSection = routeToSidebarSection(routePath);
    setActiveSection(nextSection);

    if (routePath === '/app/settings') {
      setSettingsTab((current) => (showSettings ? current : 'general'));
      setShowSettings(true);
    }
    if (routePath === '/app/memory') {
      setShowMemoryEditor(true);
    }

    if (nextSection === 'intelligence') {
      void refreshProjectIntelligence();
    } else if (nextSection === 'workspace-intelligence') {
      void refreshWorkspaceOperations();
    } else if (nextSection === 'tasks') {
      void refreshTasks();
    } else if (nextSection === 'runtime') {
      void refreshDistributedRuntime();
    } else if (nextSection === 'adaptive') {
      void refreshAdaptiveSignals();
    } else if (nextSection === 'hardening') {
      void refreshProductizationSignals();
    } else if (nextSection === 'ecosystem') {
      void refreshEcosystemSignals();
    } else if (nextSection === 'autonomous') {
      void refreshAutonomousSignals();
    } else if (nextSection === 'creative') {
      void refreshCreativeStudio();
    } else if (nextSection === 'models') {
      void refreshModelCatalog();
    }
  }, [routePath, authSession?.token]);

  useEffect(() => {
    if (!authSession) return;
    async function bootstrap() {
      try {
        const [health, nextConfig] = await Promise.all([getHealth(), getConfig()]);
        applyHealthSnapshot(health, nextConfig.engine);
        hydrateConfig(nextConfig);

        const result = await listFiles(nextConfig.default_workspace);
        if (workspaceRequestIsCurrent(nextConfig.default_workspace)) {
          setActiveWorkspaceRoot(result.workspace_root);
          setFiles(result.files);
          await restoreSelectedWorkspaceFile(result.workspace_root, result.files);
          await Promise.all([
            refreshWorkspaceHistory(result.workspace_root),
            refreshWorkspaceProfile(result.workspace_root),
            refreshProjectIntelligence(result.workspace_root),
            refreshWorkspaceOperations(result.workspace_root),
            refreshDistributedRuntime(result.workspace_root),
            refreshAdaptiveSignals(result.workspace_root),
            refreshProductizationSignals(result.workspace_root),
            refreshEcosystemSignals(result.workspace_root),
            refreshAutonomousSignals(result.workspace_root),
            refreshCreativeStudio(),
            refreshValidationRecipe(result.workspace_root),
            refreshCheckpoints(result.workspace_root),
            refreshTasks(result.workspace_root)
          ]);
        }
        await refreshModelCatalog();
      } catch (error) {
        setEngineReady(false);
        setLastHealth(null);
        setConnectionState('offline');
        setStatus(error instanceof Error ? error.message : `Failed to load ${productName}`);
      }
    }

    void bootstrap();
  }, [authSession?.token]);

  useEffect(() => {
    workspaceRootRef.current = workspaceRoot;
  }, [workspaceRoot]);

  useEffect(() => {
    if (!authSession) return;
    const timer = window.setInterval(() => {
      void getHealth()
        .then((health) => {
          applyHealthSnapshot(health);
        })
        .catch(() => {
          setEngineReady(false);
          setLastHealth(null);
          setModelReady(false);
          setConnectionState((current) => (current === 'connected' ? 'reconnecting' : 'offline'));
        });
    }, 10000);

    return () => window.clearInterval(timer);
  }, [authSession?.token]);

  useEffect(() => {
    if (!loading) {
      setThinkingIndex(0);
      return;
    }

    const timer = window.setInterval(() => {
      setThinkingIndex((current) => (current + 1) % thinkingStates.length);
    }, 1200);

    return () => window.clearInterval(timer);
  }, [loading]);

  const activeReviewSource = useMemo<GeneratedReviewSource | null>(() => {
    if (lastResponse) {
      return {
        changes: lastResponse.changes,
        applied: lastResponse.applied,
        warnings: lastResponse.warnings,
        checkpoint: lastResponse.checkpoint,
        workspaceRoot: lastResponse.workspace_root,
        taskId: lastResponse.task_id,
        restored: false
      };
    }
    return restoredReviewSource;
  }, [lastResponse, restoredReviewSource]);
  const pendingChanges = useMemo(() => activeReviewSource?.changes ?? [], [activeReviewSource]);
  const appliedChanges = useMemo(() => activeReviewSource?.applied ?? [], [activeReviewSource]);
  const rawApplyWarnings = useMemo(() => activeReviewSource?.warnings ?? [], [activeReviewSource]);
  const applyWarnings = useMemo(
    () => unresolvedGeneratedChangeWarnings(pendingChanges, appliedChanges, rawApplyWarnings),
    [appliedChanges, pendingChanges, rawApplyWarnings]
  );
  const remainingChanges = useMemo(
    () => remainingGeneratedChanges(pendingChanges, appliedChanges, applyWarnings),
    [appliedChanges, applyWarnings, pendingChanges]
  );
  const generatedChangeSummary = useMemo(
    () => summarizeGeneratedChangeReview(pendingChanges, appliedChanges, applyWarnings),
    [appliedChanges, applyWarnings, pendingChanges]
  );
  const generatedDiffStats = useMemo(
    () => summarizeGeneratedDiffStats(pendingChanges, changeDiffs),
    [changeDiffs, pendingChanges]
  );

  useEffect(() => {
    if (!pendingChanges.length) {
      setSelectedChangeId('');
      return;
    }

    const exists = pendingChanges.some((change) => changeId(change) === selectedChangeId);
    if (!exists) {
      setSelectedChangeId(changeId(pendingChanges[0]));
    }
  }, [pendingChanges, selectedChangeId]);

  useEffect(() => {
    setSelectedPreviewTab('diff');
  }, [selectedChangeId]);

  const selectedChange = useMemo(
    () => pendingChanges.find((change) => changeId(change) === selectedChangeId) ?? pendingChanges[0] ?? null,
    [pendingChanges, selectedChangeId]
  );
  const selectedChangeApplied = selectedChange ? isGeneratedChangeApplied(selectedChange, appliedChanges) : false;
  const selectedChangeWarnings = useMemo(
    () => (selectedChange ? warningsForGeneratedChange(selectedChange, applyWarnings) : []),
    [applyWarnings, selectedChange]
  );
  const selectedChangeApplyIntent = useMemo(
    () => (selectedChange ? generatedChangeApplyIntent(selectedChange, appliedChanges, applyWarnings) : 'apply'),
    [appliedChanges, applyWarnings, selectedChange]
  );
  const selectedChangeApplyLabel =
    selectedChangeApplyIntent === 'applied'
      ? 'Applied'
      : selectedChangeApplyIntent === 'retry'
        ? 'Retry selected'
        : 'Apply selected';

  useEffect(() => {
    let cancelled = false;

    async function loadChangeDiffSummaries() {
      if (!pendingChanges.length) {
        setChangeDiffs({});
        setChangeDiffSummaryStatus('');
        return;
      }

      setChangeDiffSummaryStatus('Calculating line changes...');

      const entries = await Promise.all(
        pendingChanges.map(async (change) => {
          const oldContent = await readOldContentForGeneratedChange(change, activeReviewSource);

          try {
            const diff = await compareDiff({
              old_content: oldContent,
              new_content: change.action === 'delete' ? null : change.content,
              path: change.path,
              action: change.action
            });
            return [changeId(change), diff] as const;
          } catch {
            return null;
          }
        })
      );

      if (cancelled) return;

      const nextDiffs: Record<string, DiffCompareResponse> = {};
      for (const entry of entries) {
        if (entry) {
          nextDiffs[entry[0]] = entry[1];
        }
      }

      setChangeDiffs(nextDiffs);
      setChangeDiffSummaryStatus(
        entries.some((entry) => !entry) ? 'Some line counts could not be calculated.' : ''
      );
    }

    void loadChangeDiffSummaries();

    return () => {
      cancelled = true;
    };
  }, [activeReviewSource, pendingChanges, workspaceRoot]);

  useEffect(() => {
    let cancelled = false;

    async function loadSelectedChangeDiff() {
      if (!selectedChange) {
        setSelectedChangeDiff(null);
        setSelectedChangeDiffStatus('');
        return;
      }

      const cachedDiff = changeDiffs[changeId(selectedChange)];
      if (cachedDiff) {
        setSelectedChangeDiff(cachedDiff);
        setSelectedChangeDiffStatus(cachedDiff.patch.trim() ? '' : 'No textual diff was generated for this change.');
        return;
      }

      setSelectedChangeDiffStatus('Building diff...');

      const oldContent = await readOldContentForGeneratedChange(selectedChange, activeReviewSource);

      try {
        const diff = await compareDiff({
          old_content: oldContent,
          new_content: selectedChange.action === 'delete' ? null : selectedChange.content,
          path: selectedChange.path,
          action: selectedChange.action
        });

        if (cancelled) return;
        setSelectedChangeDiff(diff);
        setSelectedChangeDiffStatus(diff.patch.trim() ? '' : 'No textual diff was generated for this change.');
      } catch (error) {
        if (cancelled) return;
        setSelectedChangeDiff(null);
        setSelectedChangeDiffStatus(error instanceof Error ? error.message : 'Could not generate a diff preview');
      }
    }

    void loadSelectedChangeDiff();

    return () => {
      cancelled = true;
    };
  }, [activeReviewSource, changeDiffs, selectedChange, workspaceRoot]);

  const eventLog = manualEvents.length ? manualEvents : lastResponse?.events ?? [];
  const validation = manualValidation ?? lastResponse?.validation ?? null;
  const activeValidationContext = manualValidation ? validationContext : null;
  const validationNeedsRepair = Boolean(
    validation && (validation.timed_out || !validation.allowed || validation.exit_code !== 0)
  );
  const repairAttempts = lastResponse?.repair_attempts ?? [];
  const visibleMemory = useMemo(() => mergeById<FixMemoryEntry>(lastResponse?.memory_hits ?? [], workspaceHistory?.fix_memory ?? []), [
    lastResponse?.memory_hits,
    workspaceHistory?.fix_memory
  ]);
  const visibleProjectMemory = useMemo(
    () => mergeById<ProjectMemoryEntry>(lastResponse?.project_memory_hits ?? [], workspaceHistory?.project_memory ?? []),
    [lastResponse?.project_memory_hits, workspaceHistory?.project_memory]
  );
  const visibleTasks = useMemo(() => mergeById<TaskSummary>(lastResponse?.recent_tasks ?? [], workspaceHistory?.recent_tasks ?? []), [
    lastResponse?.recent_tasks,
    workspaceHistory?.recent_tasks
  ]);
  const taskBoardTasks = useMemo(() => mergeById<TaskSummary>(tasks, visibleTasks), [tasks, visibleTasks]);
  const selectedTask = useMemo(
    () => taskBoardTasks.find((item) => item.id === selectedTaskId || item.task_id === selectedTaskId) ?? null,
    [selectedTaskId, taskBoardTasks]
  );
  const filteredTaskBoardTasks = useMemo(
    () =>
      taskBoardTasks.filter((item) => {
        if (taskStatusFilter === 'all') return true;
        if (taskStatusFilter === 'active') return !terminalTaskStatuses.has(item.status);
        if (taskStatusFilter === 'completed') return item.status === 'completed';
        return item.status === 'failed' || item.status === 'canceled';
      }),
    [taskBoardTasks, taskStatusFilter]
  );
  const visibleFiles = useMemo(() => filterWorkspaceFiles(files, fileSearch), [fileSearch, files]);
  const visibleValidationRepairTrail = useMemo(
    () => filterValidationRepairTrail(validationRepairTrail, validationRepairSearch, validationRepairStatusFilter),
    [validationRepairSearch, validationRepairStatusFilter, validationRepairTrail]
  );
  const filteredActivityEvents = useMemo(
    () => filterActivityEvents(eventLog, activityFilter),
    [activityFilter, eventLog]
  );
  const visibleActivityEvents = useMemo(
    () => (showAllActivityEvents ? filteredActivityEvents : filteredActivityEvents.slice(0, 7)),
    [filteredActivityEvents, showAllActivityEvents]
  );
  const activityCounterLabel =
    activityFilter === 'all'
      ? showAllActivityEvents
        ? String(eventLog.length)
        : `${visibleActivityEvents.length}/${eventLog.length}`
      : `${filteredActivityEvents.length}/${eventLog.length}`;
  const shouldOpenDetailsPanel = Boolean(
    pendingChanges.length ||
      validation ||
      eventLog.length ||
      repairAttempts.length ||
      manualEvents.length ||
      manualValidation ||
      validationRepairTrail.length
  );
  useEffect(() => {
    if (!taskBoardTasks.length) {
      if (selectedTaskId) setSelectedTaskId('');
      return;
    }

    if (!selectedTaskId || !taskBoardTasks.some((item) => item.id === selectedTaskId || item.task_id === selectedTaskId)) {
      setSelectedTaskId(taskBoardTasks[0].id);
    }
  }, [selectedTaskId, taskBoardTasks]);

  useEffect(() => {
    const taskId = selectedTaskId.trim();
    if (!taskId) {
      setTaskTimeline([]);
      setTaskArtifacts(null);
      return;
    }

    let cancelled = false;
    setTaskStatusMessage('Loading task timeline...');

    async function loadSelectedTask() {
      try {
        const [timeline, artifacts] = await Promise.all([getTaskTimeline(taskId), getTaskArtifacts(taskId)]);
        if (cancelled) return;
        setTaskTimeline(timeline.events);
        setTaskArtifacts(artifacts);
        setTaskStatusMessage('');
      } catch (error) {
        if (cancelled) return;
        setTaskTimeline([]);
        setTaskArtifacts(null);
        setTaskStatusMessage(error instanceof Error ? error.message : 'Could not load task details');
      }
    }

    void loadSelectedTask();

    return () => {
      cancelled = true;
    };
  }, [selectedTaskId]);

  const detailsPanelVisible = showDetailsPanel;
  const compactLayout = viewportSize.width < 1180;
  const narrowLayout = viewportSize.width < 720;
  const effectiveDetailsPanelVisible = detailsPanelVisible && !compactLayout;
  const composerWillQueue = loading || connectionState !== 'connected';
  const runtimeDiagnostics = useMemo(
    () =>
      buildRuntimeDiagnostics({
        health: lastHealth,
        config,
        workspaceProfile,
        validationRecipe,
        connectionState,
        workspaceRoot
      }),
    [config, connectionState, lastHealth, validationRecipe, workspaceProfile, workspaceRoot]
  );

  const currentThreadPreview = useMemo<ChatThreadPreview>(() => {
    const draft = buildConversationPreview(currentThreadId, history, workspaceRoot);
    return draft ?? {
      id: currentThreadId,
      title: 'Current session',
      preview: 'No messages yet',
      count: 0
    };
  }, [currentThreadId, history, workspaceRoot]);
  const latestAssistantMessageIndex = useMemo(() => {
    for (let index = history.length - 1; index >= 0; index -= 1) {
      if (history[index].role === 'assistant') return index;
    }
    return -1;
  }, [history]);

  const visibleSavedThreads = useMemo(
    () => savedThreads.filter((thread) => thread.id !== currentThreadId),
    [currentThreadId, savedThreads]
  );

  const filteredThreads = useMemo(() => {
    const term = chatSearch.trim().toLowerCase();
    if (!term) return visibleSavedThreads;
    return visibleSavedThreads.filter(
      (item) => item.title.toLowerCase().includes(term) || item.preview.toLowerCase().includes(term)
    );
  }, [chatSearch, visibleSavedThreads]);

  const managedModels = useMemo(() => modelManager?.models ?? [], [modelManager]);
  const installedManagedModels = useMemo(
    () => managedModels.filter((item) => item.installed || item.active),
    [managedModels]
  );
  const activeModelOption = useMemo(
    () => managedModelFromConfig(modelApi, modelEndpoint, modelName, modelReady, modelMessage),
    [modelApi, modelEndpoint, modelName, modelMessage, modelReady]
  );
  const visibleManagedModels = useMemo(() => {
    const term = modelSearch.trim().toLowerCase();
    const source = managedModels.length ? managedModels : modelInventoryToManagedModels(modelInventory?.models ?? []);
    if (!term) return source;
    return source.filter((item) =>
      [item.name, item.label, item.api, item.health, ...item.roles, ...item.capabilities]
        .join(' ')
        .toLowerCase()
        .includes(term)
    );
  }, [managedModels, modelInventory?.models, modelSearch]);
  const selectableModelOptions = useMemo(() => {
    const map = new Map<string, ManagedModelInfo>();
    for (const item of [...installedManagedModels, ...visibleManagedModels, activeModelOption]) {
      if (item.name) map.set(`${item.api}:${item.endpoint}:${item.name}`, item);
    }
    return Array.from(map.values()).sort((a, b) => {
      if (a.active !== b.active) return a.active ? -1 : 1;
      if (a.installed !== b.installed) return a.installed ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
  }, [activeModelOption, installedManagedModels, visibleManagedModels]);
  const activeModelKey = modelOptionKey({ api: modelApi, endpoint: modelEndpoint, name: modelName });
  const quickModelOptions = useMemo(() => {
    const preferred = selectableModelOptions.filter((item) => item.active || item.installed || item.configured);
    return (preferred.length ? preferred : selectableModelOptions).slice(0, 8);
  }, [selectableModelOptions]);
  const visibleCustomAgents = useMemo(() => {
    const term = agentSearch.trim().toLowerCase();
    if (!term) return customAgents;
    return customAgents.filter((agent) =>
      [agent.name, agent.perspective, agent.mission, agent.mode, agent.modelName]
        .join(' ')
        .toLowerCase()
        .includes(term)
    );
  }, [agentSearch, customAgents]);
  const projectRoots = useMemo<ProjectRootSummary[]>(() => {
    const roots = new Map<string, ProjectRootSummary>();
    const activeRootKey = normalizeProjectRootKey(workspaceRoot);

    const addRoot = (root: string, title: string, thread: SavedConversation | null = null) => {
      const trimmed = root.trim();
      if (!trimmed) return;
      const key = normalizeProjectRootKey(trimmed);
      const existing = roots.get(key);
      const threads = thread ? [...(existing?.threads ?? []), thread] : existing?.threads ?? [];
      const latestThread = latestProjectThread(existing?.latestThread ?? null, thread);
      roots.set(key, {
        root: existing?.root || trimmed,
        title: latestThread?.title || existing?.title || title,
        count: (existing?.count ?? 0) + (thread ? 1 : 0),
        active: key === activeRootKey,
        latestThread,
        latestUpdatedAt: latestThread?.updatedAt || existing?.latestUpdatedAt || '',
        threads
      });
    };

    addRoot(workspaceRoot, 'Current workspace');
    for (const thread of savedThreads) {
      addRoot(thread.workspaceRoot, thread.title || 'Saved session workspace', thread);
    }
    return Array.from(roots.values()).sort((left, right) => {
      if (left.active !== right.active) return left.active ? -1 : 1;
      const leftTime = new Date(left.latestUpdatedAt || 0).getTime();
      const rightTime = new Date(right.latestUpdatedAt || 0).getTime();
      if (leftTime !== rightTime) return rightTime - leftTime;
      return left.title.localeCompare(right.title);
    });
  }, [savedThreads, workspaceRoot]);
  const visibleProjectRoots = useMemo(() => {
    const term = projectSearch.trim().toLowerCase();
    if (!term) return projectRoots;
    return projectRoots.filter((project) =>
      [
        project.title,
        project.root,
        project.latestThread?.title ?? '',
        project.latestThread?.preview ?? '',
        ...project.threads.flatMap((thread) => [thread.title, thread.preview])
      ]
        .join(' ')
        .toLowerCase()
        .includes(term)
    );
  }, [projectRoots, projectSearch]);

  useEffect(() => {
    saveQueuedMessages(queuedMessages);
  }, [queuedMessages]);

  useEffect(() => {
    saveQueueAutoSendPaused(queueAutoSendPaused);
  }, [queueAutoSendPaused]);

  useEffect(() => {
    saveComposerDraft(message);
  }, [message]);

  useEffect(() => {
    saveCustomAgents(customAgents);
  }, [customAgents]);

  useEffect(() => {
    saveDetailsPanelVisible(showDetailsPanel);
  }, [showDetailsPanel]);

  useEffect(() => {
    saveCollapsedDetailSections(collapsedDetailSections);
  }, [collapsedDetailSections]);

  useEffect(() => {
    if (modelName && agentFormModelName === 'qwen2.5-coder:7b') {
      setAgentFormModelName(modelName);
    }
  }, [agentFormModelName, modelName]);

  useEffect(() => {
    if (!queuedMessages.length) {
      setShowQueueTray(false);
    }
  }, [queuedMessages.length]);

  useEffect(() => {
    if (!showModelSwitcher) return;

    function closeOnOutsideClick(event: MouseEvent) {
      const target = event.target;
      if (target instanceof Element && target.closest('[data-model-switcher]')) return;
      setShowModelSwitcher(false);
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setShowModelSwitcher(false);
    }

    document.addEventListener('mousedown', closeOnOutsideClick);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('mousedown', closeOnOutsideClick);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [showModelSwitcher]);

  useEffect(() => {
    if (shouldOpenDetailsPanel) {
      setShowDetailsPanel(true);
    }
  }, [shouldOpenDetailsPanel]);

  useEffect(() => {
    const chatScroll = chatScrollRef.current;
    if (!chatScroll) return;

    const frame = window.requestAnimationFrame(() => {
      chatScroll.scrollTo({
        top: chatScroll.scrollHeight,
        behavior: 'auto'
      });
    });

    return () => window.cancelAnimationFrame(frame);
  }, [activeChatRequest, history, lastResponse, loading, status]);

  useEffect(() => {
    if (queueAutoSendPaused || connectionState !== 'connected' || loading || !queuedMessages.length) return;

    const [nextQueuedMessage] = queuedMessages;
    setQueuedMessages((current) => current.slice(1));
    setStatus(`Sending queued message from ${formatEventTime(nextQueuedMessage.createdAt)}...`);
    void submit(undefined, nextQueuedMessage.content, nextQueuedMessage);
  }, [connectionState, loading, queueAutoSendPaused, queuedMessages]);

  function setActiveWorkspaceRoot(nextRoot: string) {
    workspaceRootRef.current = nextRoot;
    setWorkspaceRoot(nextRoot);
  }

  function workspaceRequestIsCurrent(requestedRoot: string) {
    const currentRootKey = normalizeProjectRootKey(workspaceRootRef.current);
    const requestedRootKey = normalizeProjectRootKey(requestedRoot);
    return !currentRootKey || currentRootKey === requestedRootKey;
  }

  function hydrateConfig(nextConfig: AppConfig) {
    setConfig(nextConfig);
    setAssistantName(nextConfig.assistant_name);
    setAssistantMission(nextConfig.assistant_mission);
    setMode(nextConfig.default_mode);
    setActiveWorkspaceRoot(nextConfig.default_workspace);
    setEngineReady(nextConfig.engine_ready);
    setModelReady(nextConfig.model_ready);
    setModelMessage(nextConfig.model_message);
    setModelApi(nextConfig.model_api);
    setModelEndpoint(nextConfig.model_endpoint);
    setModelName(nextConfig.model_name);
    setCommandAllowlist(nextConfig.command_allowlist);
    setCommandTimeout(nextConfig.command_timeout_seconds);
    setAutoRunValidation(nextConfig.auto_run_validation);
    setEngineLabel(nextConfig.engine);
  }

  function applyHealthSnapshot(health: HealthResponse, fallbackEngine = runtimeIdentity) {
    setLastHealth(health);
    setEngineReady(Boolean(health.ok && health.engine_ready));
    setModelReady(Boolean(health.model_ready));
    setModelMessage(health.model_message);
    setEngineLabel(health.engine || fallbackEngine);
    setConnectionState(Boolean(health.ok && health.engine_ready) ? 'connected' : 'failed');
  }

  async function refreshRuntimeDiagnostics() {
    setSaveStatus('Refreshing runtime diagnostics...');
    try {
      const health = await getHealth();
      applyHealthSnapshot(health, config?.engine || runtimeIdentity);
      await refreshWorkspaceProfile(workspaceRoot || health.workspace_root);
      setSaveStatus('Runtime diagnostics refreshed.');
    } catch (error) {
      setLastHealth(null);
      setEngineReady(false);
      setModelReady(false);
      setConnectionState('offline');
      setSaveStatus(error instanceof Error ? error.message : 'Could not refresh runtime diagnostics');
    }
  }

  async function refreshModelCatalog() {
    setModelCatalogLoading(true);
    setModelCatalogStatus('');

    try {
      const [inventory, registry, manager] = await Promise.all([
        getModels(),
        getModelRegistry(),
        getModelManager()
      ]);
      setModelInventory(inventory);
      setModelRegistry(registry);
      setModelManager(manager);
      setModelCatalogStatus(inventory.message || manager.message || 'Model catalog refreshed.');
      if (!modelPullName) {
        setModelPullName(manager.models.find((item) => item.pullable)?.name ?? '');
      }
    } catch (error) {
      setModelCatalogStatus(error instanceof Error ? error.message : 'Could not load model catalog');
    } finally {
      setModelCatalogLoading(false);
    }
  }

  function openSettings(tab: SettingsTab = 'general') {
    setSettingsTab(tab);
    setShowSettings(true);
    if (isProtectedAppRoute(routePath) && routePath !== '/app/settings') {
      navigateTo('/app/settings');
    }
    if (tab === 'models') {
      void refreshModelCatalog();
    }
  }

  function closeSettings() {
    setShowSettings(false);
    if (routePath === '/app/settings') {
      navigateTo('/app', true);
    }
  }

  async function activateModelTarget(target: Pick<ManagedModelInfo, 'api' | 'endpoint' | 'name' | 'label'>) {
    const nextName = target.name.trim();
    const nextApi = target.api.trim() || 'ollama';
    const nextEndpoint = target.endpoint.trim() || 'http://127.0.0.1:11434';
    if (!nextName) return;

    setModelActionName(nextName);
    setModelCatalogStatus(`Switching active model to ${nextName}...`);
    setModelApi(nextApi);
    setModelEndpoint(nextEndpoint);
    setModelName(nextName);

    try {
      const nextConfig = await saveConfig({
        assistant_name: assistantName.trim() || assistantIdentity,
        assistant_mission:
          assistantMission.trim() ||
          defaultAssistantMission,
        default_mode: mode,
        default_workspace: workspaceRoot.trim() || 'workspace',
        model_api: nextApi,
        model_endpoint: nextEndpoint,
        model_name: nextName,
        command_allowlist:
          commandAllowlist.trim() ||
          'python,py,node,npm,npx,pnpm,pytest,uvicorn,tsc,vite,cargo,rustc,go,dotnet',
        command_timeout_seconds: commandTimeout,
        auto_run_validation: autoRunValidation
      });
      hydrateConfig(nextConfig);
      const health = await getHealth();
      applyHealthSnapshot(health, nextConfig.engine);
      await refreshModelCatalog();
      setModelCatalogStatus(`Active model set to ${nextName}.`);
      setSaveStatus(`Active model set to ${nextName}.`);
      setShowModelSwitcher(false);
    } catch (error) {
      setModelCatalogStatus(error instanceof Error ? error.message : 'Could not switch active model');
    } finally {
      setModelActionName('');
    }
  }

  function toggleModelSwitcher() {
    setShowModelSwitcher((current) => {
      const next = !current;
      if (next) void refreshModelCatalog();
      return next;
    });
  }

  function selectModelDraft(target: Pick<ManagedModelInfo, 'api' | 'endpoint' | 'name'>) {
    setModelApi(target.api || 'ollama');
    setModelEndpoint(target.endpoint || 'http://127.0.0.1:11434');
    setModelName(target.name);
  }

  async function pullManagedModel(target: ManagedModelInfo) {
    if (!target.pullable || modelActionName) return;
    const confirmed = window.confirm(`Pull ${target.name}? This can download several GB through Ollama.`);
    if (!confirmed) return;

    setModelActionName(target.name);
    setModelCatalogStatus(`Starting pull for ${target.name}...`);
    try {
      const operation = await pullModel({ model_name: target.name, minimum_free_gb: 24 });
      setModelCatalogStatus(operation.message || `Started pull for ${target.name}.`);
      await refreshModelCatalog();
    } catch (error) {
      setModelCatalogStatus(error instanceof Error ? error.message : `Could not pull ${target.name}`);
    } finally {
      setModelActionName('');
    }
  }

  async function deleteManagedModel(target: ManagedModelInfo) {
    if (!target.installed || target.active || !target.local || modelActionName) return;
    const confirmed = window.confirm(`Remove local Ollama model ${target.name}?`);
    if (!confirmed) return;

    setModelActionName(target.name);
    setModelCatalogStatus(`Removing ${target.name}...`);
    try {
      const operation = await deleteModel({
        model_name: target.name,
        confirm_model_name: target.name
      });
      setModelCatalogStatus(operation.message || `Started removal for ${target.name}.`);
      await refreshModelCatalog();
    } catch (error) {
      setModelCatalogStatus(error instanceof Error ? error.message : `Could not remove ${target.name}`);
    } finally {
      setModelActionName('');
    }
  }

  function renderRuntimeDiagnosticAction(check: RuntimeDiagnosticCheck) {
    if (!check.action) return null;

    const isSetupAction = check.action.kind === 'setup_workspace';
    const isValidationAction = check.action.kind === 'run_validation';
    const isBusy = (isSetupAction && workspaceSetupLoading) || (isValidationAction && loading);
    const isDisabled = isSetupAction
      ? loading || workspaceSetupLoading || !workspaceRoot.trim()
      : isValidationAction
        ? loading || !workspaceRoot.trim()
        : false;

    return (
      <button
        type="button"
        style={styles.iconTextButton(palette)}
        onClick={() => void runRuntimeDiagnosticAction(check)}
        disabled={isDisabled}
        aria-label={`${check.action.label} for ${check.label}`}
      >
        {isBusy ? <Loader2 size={14} className="spin" /> : runtimeDiagnosticActionIcon(check.action.kind)}
        {check.action.label}
      </button>
    );
  }

  async function runRuntimeDiagnosticAction(check: RuntimeDiagnosticCheck) {
    if (!check.action) return;

    if (check.action.kind === 'setup_workspace') {
      await setupCurrentWorkspace();
      return;
    }
    if (check.action.kind === 'run_validation') {
      await validateNow();
      return;
    }
    await refreshRuntimeDiagnostics();
  }

  function renderActivityEvent(item: ToolEvent, index: number) {
    const eventId = activityEventId(item, index);
    const hasDetails = activityEventHasDetails(item);
    const expanded = expandedActivityEventIds.includes(eventId);
    const detailsId = `activity-event-details-${index}`;

    return (
      <div
        key={`${item.kind}-${item.created_at}-${index}`}
        style={styles.activityRow(palette, item.status)}
        data-testid={`activity-event-${index}`}
      >
        <span style={styles.activityTime(palette)}>{formatEventTime(item.created_at)}</span>
        <div style={styles.activityContent}>
          {hasDetails ? (
            <button
              type="button"
              style={styles.activityToggleButton(palette)}
              onClick={() => toggleActivityEvent(eventId)}
              aria-expanded={expanded}
              aria-controls={detailsId}
              aria-label={`${expanded ? 'Hide' : 'Show'} activity details ${item.title}`}
            >
              <span style={styles.activityTextStack}>
                <strong style={styles.eventTitle(palette)}>{item.title}</strong>
                <span style={styles.eventDetail(palette)}>{item.detail || item.kind}</span>
              </span>
              <ChevronDown size={14} style={styles.activityChevron(expanded)} />
            </button>
          ) : (
            <div>
              <strong style={styles.eventTitle(palette)}>{item.title}</strong>
              <div style={styles.eventDetail(palette)}>{item.detail || item.kind}</div>
            </div>
          )}

          {hasDetails && expanded ? renderActivityEventDetails(item, index, detailsId) : null}
        </div>
      </div>
    );
  }

  function renderActivityEventDetails(item: ToolEvent, index: number, detailsId: string) {
    const command = payloadValueText(item.payload, 'command');
    const cwd = payloadValueText(item.payload, 'cwd');
    const exitCode = payloadValueText(item.payload, 'exit_code');
    const category = payloadValueText(item.payload, 'category');
    const buildLogPath = payloadValueText(item.payload, 'build_log_path');
    const stdout = payloadValueText(item.payload, 'stdout');
    const stderr = payloadValueText(item.payload, 'stderr');
    const reason = payloadValueText(item.payload, 'reason');
    const summary = payloadValueText(item.payload, 'summary');
    const output = activityOutputText({ stdout, stderr, reason });
    const hasCommandShape = Boolean(command || cwd || exitCode || category || buildLogPath || output || summary);

    return (
      <div id={detailsId} style={styles.activityDetails(palette)} data-testid={`activity-event-details-${index}`}>
        {hasCommandShape ? (
          <>
            <div style={styles.activityDetailGrid}>
              {command ? renderActivityDetail('Command', command) : null}
              {cwd ? renderActivityDetail('CWD', cwd) : null}
              {exitCode ? renderActivityDetail('Exit', exitCode) : null}
              {category ? renderActivityDetail('Category', category) : null}
              {buildLogPath ? renderActivityDetail('Build log', buildLogPath) : null}
            </div>
            {summary ? <div style={styles.eventDetail(palette)}>{summary}</div> : null}
            {output ? <pre style={styles.activityOutputBlock(palette)}>{clipActivityText(output)}</pre> : null}
          </>
        ) : (
          <pre style={styles.activityOutputBlock(palette)}>{clipActivityText(JSON.stringify(item.payload, null, 2))}</pre>
        )}
      </div>
    );
  }

  function renderActivityDetail(label: string, value: string) {
    return (
      <div style={styles.activityDetailItem(palette)}>
        <span style={styles.activityDetailLabel(palette)}>{label}</span>
        <strong style={styles.activityDetailValue(palette)}>{value}</strong>
      </div>
    );
  }

  function activityEventId(item: ToolEvent, index: number) {
    return `${item.created_at || 'event'}|${item.kind}|${item.title}|${index}`;
  }

  function activityEventHasDetails(item: ToolEvent) {
    return Object.keys(item.payload || {}).length > 0;
  }

  function toggleActivityEvent(eventId: string) {
    setExpandedActivityEventIds((current) =>
      current.includes(eventId) ? current.filter((item) => item !== eventId) : [...current, eventId]
    );
  }

  function selectActivityFilter(nextFilter: ActivityFilter) {
    setActivityFilter(nextFilter);
    setShowAllActivityEvents(false);
    setExpandedActivityEventIds([]);
  }

  function filterActivityEvents(events: ToolEvent[], filter: ActivityFilter) {
    if (filter === 'issues') {
      return events.filter((item) => item.status !== 'ok');
    }
    if (filter === 'commands') {
      return events.filter((item) => item.kind === 'command' || Boolean(payloadValueText(item.payload, 'command')));
    }
    return events;
  }

  function payloadValueText(payload: Record<string, unknown>, key: string) {
    const value = payload[key];
    if (value === null) return 'n/a';
    if (typeof value === 'string') return value;
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    return '';
  }

  function activityOutputText(parts: { stdout: string; stderr: string; reason: string }) {
    return [
      parts.stderr ? `Stderr:\n${parts.stderr}` : '',
      parts.stdout ? `Stdout:\n${parts.stdout}` : '',
      parts.reason ? `Reason:\n${parts.reason}` : ''
    ]
      .filter(Boolean)
      .join('\n\n');
  }

  function clipActivityText(text: string, limit = 5000) {
    return text.length > limit ? `${text.slice(0, limit)}\n... output truncated ...` : text;
  }

  async function refreshFiles() {
    const targetRoot = workspaceRoot.trim();
    if (!targetRoot) return;

    try {
      const result = await listFiles(targetRoot);
      if (!workspaceRequestIsCurrent(targetRoot)) return;
      setActiveWorkspaceRoot(result.workspace_root);
      setFiles(result.files);
      void refreshWorkspaceHistory(result.workspace_root);
      void refreshWorkspaceProfile(result.workspace_root);
      void refreshProjectIntelligence(result.workspace_root);
      void refreshWorkspaceOperations(result.workspace_root);
      void refreshDistributedRuntime(result.workspace_root);
      void refreshAdaptiveSignals(result.workspace_root);
      void refreshProductizationSignals(result.workspace_root);
      void refreshEcosystemSignals(result.workspace_root);
      void refreshAutonomousSignals(result.workspace_root);
      void refreshValidationRecipe(result.workspace_root);
      void refreshTasks(result.workspace_root);

      if (selectedFilePath && !result.files.some((file) => file.path === selectedFilePath)) {
        setSelectedFilePath('');
        setSelectedFileContent('');
        saveSelectedWorkspaceFile(result.workspace_root, '');
      }

      if (!selectedFilePath) {
        await restoreSelectedWorkspaceFile(result.workspace_root, result.files);
      }

      setStatus('');
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Could not refresh workspace');
    }
  }

  async function refreshWorkspaceHistory(rootOverride?: string) {
    const targetRoot = (rootOverride ?? workspaceRoot).trim();
    if (!targetRoot) return;

    try {
      const result = await getWorkspaceHistory(targetRoot);
      setWorkspaceHistory(result);
    } catch {
      // Keep the most recent successful history snapshot.
    }
  }

  async function refreshTasks(rootOverride?: string) {
    const targetRoot = (rootOverride ?? workspaceRoot).trim();
    if (!targetRoot) return;

    try {
      const result = await listTasks(targetRoot, { includeSubtasks: false, limit: 80 });
      if (!workspaceRequestIsCurrent(result.workspace_root)) return;
      setTasks(result.tasks);
      setTaskStatusMessage('');
    } catch (error) {
      setTaskStatusMessage(error instanceof Error ? error.message : 'Could not refresh tasks');
    }
  }

  async function runTaskAction(action: 'cancel' | 'retry' | 'approve', task: TaskSummary | null = selectedTask) {
    if (!task || taskActionId) return;

    setTaskActionId(`${action}:${task.id}`);
    setTaskStatusMessage(
      action === 'cancel'
        ? 'Canceling task...'
        : action === 'retry'
          ? 'Queueing task retry...'
          : 'Approving task action...'
    );

    try {
      const result =
        action === 'cancel'
          ? await cancelTask(task.id, { reason: 'Canceled from workspace Tasks panel.' })
          : action === 'retry'
            ? await retryTask(task.id, { reason: 'Retried from workspace Tasks panel.' })
            : await approveTaskAction(task.id, {
                reason: 'Approved from workspace Tasks panel.',
                approved: true
              });

      setTasks((current) => mergeById<TaskSummary>([result.task], current));
      setSelectedTaskId(result.task.id);
      const [timeline, artifacts] = await Promise.all([
        getTaskTimeline(result.task.id),
        getTaskArtifacts(result.task.id)
      ]);
      setTaskTimeline(timeline.events);
      setTaskArtifacts(artifacts);
      setTaskStatusMessage(
        action === 'cancel'
          ? 'Task canceled.'
          : action === 'retry'
            ? 'Task retry queued.'
            : 'Task approved.'
      );
      await refreshTasks(result.task.workspace_root);
    } catch (error) {
      setTaskStatusMessage(error instanceof Error ? error.message : `Could not ${action} task`);
    } finally {
      setTaskActionId('');
    }
  }

  async function refreshValidationRecipe(rootOverride?: string) {
    const targetRoot = (rootOverride ?? workspaceRoot).trim();
    if (!targetRoot) return;

    try {
      const result = await getValidationProfile(targetRoot);
      setValidationRecipe(result.profile);
      setValidationSuggestions(result.suggestions);
      setValidationCommandDraft(result.profile?.command ?? result.suggestions[0]?.command ?? '');
      setValidationNotesDraft(result.profile?.notes ?? '');
      setValidationRecipeStatus('');
    } catch (error) {
      setValidationRecipeStatus(error instanceof Error ? error.message : 'Could not load validation recipe');
    }
  }

  async function refreshWorkspaceProfile(rootOverride?: string) {
    const targetRoot = (rootOverride ?? workspaceRoot).trim();
    if (!targetRoot) return;

    try {
      const result = await getWorkspaceProfile(targetRoot);
      setWorkspaceProfile(result);
      setWorkspaceProfileStatus('');
    } catch (error) {
      setWorkspaceProfileStatus(error instanceof Error ? error.message : 'Could not load workspace readiness');
    }
  }

  async function refreshProjectIntelligence(rootOverride?: string) {
    const targetRoot = (rootOverride ?? workspaceRoot).trim();
    if (!targetRoot) return;

    try {
      const result = await getProjectIntelligence(targetRoot);
      if (!workspaceRequestIsCurrent(result.workspace_root)) return;
      setProjectIntelligence(result);
      setProjectIntelligenceStatus('');
    } catch (error) {
      setProjectIntelligenceStatus(error instanceof Error ? error.message : 'Could not load project intelligence');
    }
  }

  async function rebuildProjectIntelligence(options: { clearMemory?: boolean; rebuildMemory?: boolean } = {}) {
    const targetRoot = workspaceRoot.trim();
    if (!targetRoot || projectIntelligenceLoading) return;

    setProjectIntelligenceLoading(true);
    setProjectIntelligenceStatus(
      options.clearMemory
        ? 'Clearing and rebuilding project intelligence...'
        : options.rebuildMemory
          ? 'Rebuilding project memory from intelligence...'
          : 'Scanning project intelligence...'
    );

    try {
      const result = await reindexProjectIntelligence({
        workspace_root: targetRoot,
        rebuild_architecture: true,
        rebuild_memory: Boolean(options.rebuildMemory),
        clear_memory: Boolean(options.clearMemory)
      });
      setProjectIntelligence(result);
      setProjectIntelligenceStatus(result.indexing.message || 'Project intelligence refreshed.');
      await refreshWorkspaceHistory(result.workspace_root);
    } catch (error) {
      setProjectIntelligenceStatus(error instanceof Error ? error.message : 'Could not rebuild project intelligence');
    } finally {
      setProjectIntelligenceLoading(false);
    }
  }

  async function refreshWorkspaceOperations(rootOverride?: string) {
    const targetRoot = (rootOverride ?? workspaceRoot).trim();
    if (!targetRoot) return;

    try {
      const result = await getWorkspaceIntelligence(targetRoot);
      if (!workspaceRequestIsCurrent(result.workspace_root)) return;
      setWorkspaceOperations(result);
      setWorkspaceOperationsStatus('');
    } catch (error) {
      setWorkspaceOperationsStatus(error instanceof Error ? error.message : 'Could not load workspace intelligence');
    }
  }

  async function refreshDistributedRuntime(rootOverride?: string) {
    const targetRoot = (rootOverride ?? workspaceRoot).trim();
    if (!targetRoot) return;

    setDistributedRuntimeLoading(true);
    try {
      const [runtimeResult, unifiedResult, contextResult, continuityResult, disciplineResult, operatingResult] = await Promise.all([
        getDistributedRuntime(targetRoot),
        getUnifiedRuntime(targetRoot),
        getUnifiedContext(targetRoot),
        getContinuity(targetRoot),
        getPlatformDiscipline(targetRoot),
        getOperatingEnvironment(targetRoot)
      ]);
      setDistributedRuntime(runtimeResult);
      setUnifiedRuntime(unifiedResult);
      setUnifiedContext(contextResult);
      setContinuity(continuityResult);
      setPlatformDiscipline(disciplineResult);
      setOperatingEnvironment(operatingResult);
      setDistributedRuntimeStatus('');
    } catch (error) {
      setDistributedRuntimeStatus(error instanceof Error ? error.message : 'Could not load distributed runtime');
    } finally {
      setDistributedRuntimeLoading(false);
    }
  }

  async function previewRuntimeCommand() {
    const targetRoot = workspaceRoot.trim();
    const command = globalCommandDraft.trim();
    if (!targetRoot || !command || distributedRuntimeAction) return;

    setDistributedRuntimeAction('command-preview');
    setDistributedRuntimeStatus('Routing command through unified context...');
    try {
      const result = await previewGlobalCommand({
        workspace_root: targetRoot,
        command,
        entrypoint: 'command_palette',
        dry_run: true
      });
      setGlobalCommandPreview(result);
      setDistributedRuntimeStatus(
        `${formatStatusLabel(result.route.intent)} -> ${formatStatusLabel(result.route.target_system)}${
          result.route.approval_required ? ' / approval needed' : ''
        }`
      );
    } catch (error) {
      setDistributedRuntimeStatus(error instanceof Error ? error.message : 'Could not preview global command');
    } finally {
      setDistributedRuntimeAction('');
    }
  }

  async function refreshAdaptiveSignals(rootOverride?: string, forceRefresh = false) {
    const targetRoot = (rootOverride ?? workspaceRoot).trim();
    if (!targetRoot) return;

    setAdaptiveIntelligenceLoading(true);
    try {
      const result = forceRefresh
        ? await refreshAdaptiveIntelligence({ workspace_root: targetRoot, limit: 240, refresh_outcomes: true })
        : await getAdaptiveIntelligence(targetRoot, { limit: 240, refresh: false });
      if (!workspaceRequestIsCurrent(result.workspace_root)) return;
      setAdaptiveIntelligence(result);
      setAdaptiveIntelligenceStatus('');
    } catch (error) {
      setAdaptiveIntelligenceStatus(error instanceof Error ? error.message : 'Could not load adaptive intelligence');
    } finally {
      setAdaptiveIntelligenceLoading(false);
    }
  }

  async function activateAdaptiveProfile(profileId: string) {
    const targetRoot = workspaceRoot.trim();
    if (!targetRoot || adaptiveIntelligenceAction) return;

    setAdaptiveIntelligenceAction(`profile:${profileId}`);
    setAdaptiveIntelligenceStatus('Activating adaptive policy profile...');
    try {
      const result = await activateAdaptivePolicyProfile(
        profileId,
        { reason: 'Activated from Adaptive Intelligence.' },
        targetRoot
      );
      setAdaptiveIntelligence(result);
      setAdaptiveIntelligenceStatus(`Active profile: ${result.active_profile.name}.`);
    } catch (error) {
      setAdaptiveIntelligenceStatus(error instanceof Error ? error.message : 'Could not activate adaptive profile');
    } finally {
      setAdaptiveIntelligenceAction('');
    }
  }

  async function runAdaptiveBenchmarkSweep() {
    const targetRoot = workspaceRoot.trim();
    if (!targetRoot || adaptiveIntelligenceAction) return;

    setAdaptiveIntelligenceAction('benchmark');
    setAdaptiveIntelligenceStatus('Running adaptive benchmark report...');
    try {
      const reports = await runAdaptiveBenchmarks({ workspace_root: targetRoot });
      setAdaptiveIntelligenceStatus(`${reports.length} adaptive benchmark report(s) recorded.`);
      await refreshAdaptiveSignals(targetRoot, false);
    } catch (error) {
      setAdaptiveIntelligenceStatus(error instanceof Error ? error.message : 'Could not run adaptive benchmarks');
    } finally {
      setAdaptiveIntelligenceAction('');
    }
  }

  async function replayAdaptiveOutcomeWindow() {
    const targetRoot = workspaceRoot.trim();
    if (!targetRoot || adaptiveIntelligenceAction) return;

    setAdaptiveIntelligenceAction('replay');
    setAdaptiveIntelligenceStatus('Replaying recent adaptive task outcomes...');
    try {
      const results = await replayAdaptiveTasks({ workspace_root: targetRoot, limit: 8 });
      setAdaptiveIntelligenceStatus(`${results.length} replay result(s) recorded.`);
      await refreshAdaptiveSignals(targetRoot, false);
    } catch (error) {
      setAdaptiveIntelligenceStatus(error instanceof Error ? error.message : 'Could not replay adaptive outcomes');
    } finally {
      setAdaptiveIntelligenceAction('');
    }
  }

  async function rollbackLatestAdaptivePolicy() {
    const latestCheckpoint = adaptiveIntelligence?.policy_checkpoints[0];
    if (!latestCheckpoint || adaptiveIntelligenceAction) return;

    setAdaptiveIntelligenceAction(`rollback:${latestCheckpoint.id}`);
    setAdaptiveIntelligenceStatus('Rolling back adaptive policy profile selection...');
    try {
      const result = await rollbackAdaptivePolicy({
        checkpoint_id: latestCheckpoint.id,
        reason: 'Rollback requested from Adaptive Intelligence.'
      });
      setAdaptiveIntelligence(result);
      setAdaptiveIntelligenceStatus(`Policy profile restored from ${latestCheckpoint.id}.`);
    } catch (error) {
      setAdaptiveIntelligenceStatus(error instanceof Error ? error.message : 'Could not roll back adaptive policy');
    } finally {
      setAdaptiveIntelligenceAction('');
    }
  }

  async function refreshProductizationSignals(rootOverride?: string, forceMetrics = false) {
    const targetRoot = (rootOverride ?? workspaceRoot).trim();
    if (!targetRoot) return;

    setProductizationLoading(true);
    try {
      const result = forceMetrics
        ? await refreshProductization({ workspace_root: targetRoot, refresh_metrics: true })
        : await getProductization(targetRoot, { refreshMetrics: false });
      if (!workspaceRequestIsCurrent(result.workspace_root)) return;
      setProductization(result);
      setProductizationStatus('');
    } catch (error) {
      setProductizationStatus(error instanceof Error ? error.message : 'Could not load productization hardening');
    } finally {
      setProductizationLoading(false);
    }
  }

  async function validateSamplePluginManifest() {
    if (productizationAction) return;
    const apiVersion = productization?.api_version || '2026.05.07';
    const sample: PluginManifest = {
      id: 'sample-observability-panel',
      name: 'Sample Observability Panel',
      version: '0.1.0',
      api_version: apiVersion,
      description: 'Read-only sample manifest used to verify SDK validation.',
      author: 'Aegis',
      capabilities: ['ui_panel', 'telemetry_processor'],
      permissions: ['ui_panel', 'telemetry'],
      sandbox_profile: 'isolated',
      signature: '',
      signing_key_fingerprint: '',
      lifecycle_hooks: [],
      entrypoint: '',
      ui_panel_route: '/plugins/sample-observability-panel',
      enabled: false,
      trusted: false,
      created_at: '',
      updated_at: '',
      metadata: { sample: true }
    };

    setProductizationAction('validate-sample');
    setProductizationStatus('Validating sample plugin manifest...');
    try {
      const result = await validatePlugin({ manifest: sample });
      setProductization((current) =>
        current
          ? {
              ...current,
              plugin_validation: [result, ...current.plugin_validation.filter((item) => item.normalized_manifest?.id !== sample.id)]
            }
          : current
      );
      setProductizationStatus(
        result.valid
          ? `Sample plugin manifest is valid with ${result.warnings.length} warning(s).`
          : result.errors.join('; ')
      );
    } catch (error) {
      setProductizationStatus(error instanceof Error ? error.message : 'Could not validate sample plugin');
    } finally {
      setProductizationAction('');
    }
  }

  async function updatePluginState(plugin: PluginManifest, action: 'enable' | 'disable' | 'trust') {
    if (productizationAction) return;
    setProductizationAction(`${action}:${plugin.id}`);
    setProductizationStatus(`${formatStatusLabel(action)} plugin ${plugin.name}...`);
    try {
      const request = { reason: `Plugin ${action} requested from Hardening.` };
      const saved =
        action === 'enable'
          ? await enablePlugin(plugin.id, request)
          : action === 'disable'
            ? await disablePlugin(plugin.id, request)
            : await trustPlugin(plugin.id, request);
      setProductization((current) =>
        current
          ? {
              ...current,
              plugins: mergeById<PluginManifest>(
                current.plugins.filter((item) => item.id !== saved.id),
                [saved]
              )
            }
          : current
      );
      setProductizationStatus(`${saved.name} is ${saved.enabled ? 'enabled' : 'disabled'}${saved.trusted ? ' and trusted' : ''}.`);
      await refreshProductizationSignals(workspaceRoot, false);
    } catch (error) {
      setProductizationStatus(error instanceof Error ? error.message : `Could not ${action} plugin`);
    } finally {
      setProductizationAction('');
    }
  }

  async function refreshEcosystemSignals(rootOverride?: string, rebuildGraph = false) {
    const targetRoot = (rootOverride ?? workspaceRoot).trim();
    if (!targetRoot) return;

    setEcosystemLoading(true);
    try {
      const result = rebuildGraph
        ? await refreshEcosystem({ workspace_root: targetRoot, rebuild_graph: true, include_search_query: ecosystemSearchQuery })
        : await getEcosystem(targetRoot, { rebuildGraph: false });
      if (!workspaceRequestIsCurrent(result.workspace_root)) return;
      setEcosystemSnapshot(result);
      if (result.search) setEcosystemSearch(result.search);
      setEcosystemStatus('');
    } catch (error) {
      setEcosystemStatus(error instanceof Error ? error.message : 'Could not load ecosystem intelligence');
    } finally {
      setEcosystemLoading(false);
    }
  }

  async function validateSampleEcosystemPackage() {
    if (ecosystemAction) return;
    const apiVersion = ecosystemSnapshot?.api_version || '2026.05.07';
    const sample: EcosystemPackageManifest = {
      id: 'sample-debug-workflow-pack',
      name: 'Sample Debug Workflow Pack',
      kind: 'workflow',
      version: '0.1.0',
      api_version: apiVersion,
      description: 'A reusable debugging workflow pack for task-graph execution.',
      author: 'Aegis',
      compatibility: { api_version: apiVersion },
      trust_level: 'reviewed',
      sandbox_permissions: ['isolated'],
      permission_scopes: ['task_graph', 'approval', 'run_validation'],
      update_channel: 'stable',
      signature: 'signed',
      signing_key_fingerprint: 'sample-key',
      checksum: '',
      entrypoint: '',
      homepage: '',
      enabled: false,
      installed: false,
      installed_at: '',
      updated_at: '',
      metadata: {}
    };

    setEcosystemAction('validate-sample');
    setEcosystemStatus('Validating sample ecosystem package...');
    try {
      const result = await validateEcosystemPackage({ manifest: sample });
      setEcosystemSnapshot((current) =>
        current
          ? {
              ...current,
              package_validation: [
                result,
                ...current.package_validation.filter((item) => item.normalized_manifest?.id !== sample.id)
              ]
            }
          : current
      );
      setEcosystemStatus(
        result.valid
          ? `Sample package validates with trust score ${Math.round(result.trust_score * 100)}.`
          : result.errors.join('; ')
      );
    } catch (error) {
      setEcosystemStatus(error instanceof Error ? error.message : 'Could not validate sample ecosystem package');
    } finally {
      setEcosystemAction('');
    }
  }

  async function updateEcosystemPackageState(
    item: EcosystemPackageManifest,
    action: 'enable' | 'disable' | 'trust'
  ) {
    if (ecosystemAction) return;
    setEcosystemAction(`${action}:${item.id}`);
    setEcosystemStatus(`${formatStatusLabel(action)} package ${item.name}...`);
    try {
      const request = { reason: `Package ${action} requested from Ecosystem.` };
      const saved =
        action === 'enable'
          ? await enableEcosystemPackage(item.id, request)
          : action === 'disable'
            ? await disableEcosystemPackage(item.id, request)
            : await trustEcosystemPackage(item.id, { ...request, trust_level: 'trusted' });
      setEcosystemSnapshot((current) =>
        current
          ? {
              ...current,
              packages: mergeById<EcosystemPackageManifest>(
                current.packages.filter((packageItem) => packageItem.id !== saved.id),
                [saved]
              )
            }
          : current
      );
      setEcosystemStatus(`${saved.name} is ${saved.enabled ? 'enabled' : 'disabled'} with ${saved.trust_level} trust.`);
      await refreshEcosystemSignals(workspaceRoot, false);
    } catch (error) {
      setEcosystemStatus(error instanceof Error ? error.message : `Could not ${action} ecosystem package`);
    } finally {
      setEcosystemAction('');
    }
  }

  async function runReusableWorkflow(workflowId: string) {
    if (ecosystemAction) return;
    setEcosystemAction(`workflow:${workflowId}`);
    setEcosystemStatus(`Creating task graph for ${formatStatusLabel(workflowId)}...`);
    try {
      const result = await runEcosystemWorkflow(workflowId, {
        workspace_root: workspaceRoot,
        user_goal: `Run ${resultTitleFromWorkflow(workflowId)} from the Ecosystem workflow manager.`,
        start_immediately: false
      });
      setTasks((current) => mergeById<TaskSummary>(current, [result.task, ...result.subtasks]));
      setSelectedTaskId(result.task.id);
      setActiveSection('tasks');
      setEcosystemStatus(result.message);
    } catch (error) {
      setEcosystemStatus(error instanceof Error ? error.message : 'Could not run workflow');
    } finally {
      setEcosystemAction('');
    }
  }

  async function runEcosystemSearch() {
    const targetRoot = workspaceRoot.trim();
    const query = ecosystemSearchQuery.trim();
    if (!targetRoot || !query || ecosystemAction) return;
    setEcosystemAction('search');
    setEcosystemStatus(`Searching ecosystem intelligence for "${query}"...`);
    try {
      const result = await searchEcosystem({ workspace_root: targetRoot, query, limit: 20 });
      setEcosystemSearch(result);
      setEcosystemStatus(`${result.results.length} ecosystem result(s) found.`);
    } catch (error) {
      setEcosystemStatus(error instanceof Error ? error.message : 'Could not search ecosystem intelligence');
    } finally {
      setEcosystemAction('');
    }
  }

  async function exportProjectIntelligenceProfile() {
    if (ecosystemAction) return;
    setEcosystemAction('export-profile');
    setEcosystemStatus('Exporting current project intelligence profile...');
    try {
      const result = await exportCurrentProjectIntelligence(workspaceRoot);
      setEcosystemSnapshot((current) =>
        current
          ? {
              ...current,
              shared_profiles: mergeById(current.shared_profiles, [result.profile])
            }
          : current
      );
      setEcosystemStatus(`Exported ${result.profile.name}.`);
      await refreshEcosystemSignals(workspaceRoot, false);
    } catch (error) {
      setEcosystemStatus(error instanceof Error ? error.message : 'Could not export project intelligence');
    } finally {
      setEcosystemAction('');
    }
  }

  function resultTitleFromWorkflow(workflowId: string) {
    return ecosystemSnapshot?.workflows.find((workflow) => workflow.id === workflowId)?.name ?? formatStatusLabel(workflowId);
  }

  async function refreshAutonomousSignals(rootOverride?: string) {
    const targetRoot = (rootOverride ?? workspaceRoot).trim();
    if (!targetRoot) return;

    setAutonomousLoading(true);
    try {
      const result = await getAutonomousEngineering(targetRoot);
      if (!workspaceRequestIsCurrent(result.workspace_root)) return;
      setAutonomousSnapshot(result);
      if (selectedAutonomousObjective?.objective.id) {
        try {
          setSelectedAutonomousObjective(await getAutonomousObjective(selectedAutonomousObjective.objective.id));
        } catch {
          setSelectedAutonomousObjective(null);
        }
      }
      setAutonomousStatus('');
    } catch (error) {
      setAutonomousStatus(error instanceof Error ? error.message : 'Could not load autonomous engineering');
    } finally {
      setAutonomousLoading(false);
    }
  }

  async function createDryRunAutonomousObjective() {
    const title = autonomousObjectiveTitle.trim();
    const goal = autonomousObjectiveGoal.trim();
    if (!title || !goal || autonomousAction) return;
    setAutonomousAction('create');
    setAutonomousStatus('Creating supervised dry-run objective...');
    try {
      const detail = await createAutonomousObjective({
        workspace_root: workspaceRoot,
        title,
        user_goal: goal,
        dry_run: true,
        max_iterations: 6,
        token_budget: 160000,
        max_parallel_agents: 4
      });
      setSelectedAutonomousObjective(detail);
      setAutonomousStatus(`${detail.objective.title} created with ${detail.approval_gates.length} approval gate(s).`);
      await refreshAutonomousSignals(workspaceRoot);
    } catch (error) {
      setAutonomousStatus(error instanceof Error ? error.message : 'Could not create autonomous objective');
    } finally {
      setAutonomousAction('');
    }
  }

  async function updateAutonomousObjective(action: 'start' | 'pause' | 'cancel' | 'iterate' | 'simulate') {
    const objectiveId = selectedAutonomousObjective?.objective.id;
    if (!objectiveId || autonomousAction) return;
    setAutonomousAction(action);
    setAutonomousStatus(`${formatStatusLabel(action)} objective...`);
    try {
      if (action === 'start') {
        setSelectedAutonomousObjective(await startAutonomousObjective(objectiveId, { reason: 'Started from Autonomous workspace.' }));
      } else if (action === 'pause') {
        setSelectedAutonomousObjective(await pauseAutonomousObjective(objectiveId, { reason: 'Paused from Autonomous workspace.' }));
      } else if (action === 'cancel') {
        setSelectedAutonomousObjective(await cancelAutonomousObjective(objectiveId, { reason: 'Canceled from Autonomous workspace.' }));
      } else if (action === 'iterate') {
        setSelectedAutonomousObjective(
          await iterateAutonomousObjective(objectiveId, {
            reason: 'Advanced from Autonomous workspace.',
            max_steps: 1,
            allow_repairs: true
          })
        );
      } else {
        const simulation = await simulateAutonomousObjective(objectiveId);
        setSelectedAutonomousObjective((current) =>
          current
            ? {
                ...current,
                simulations: [simulation, ...current.simulations.filter((item) => item.id !== simulation.id)]
              }
            : current
        );
      }
      setAutonomousStatus(`${formatStatusLabel(action)} completed.`);
      await refreshAutonomousSignals(workspaceRoot);
    } catch (error) {
      setAutonomousStatus(error instanceof Error ? error.message : `Could not ${action} objective`);
    } finally {
      setAutonomousAction('');
    }
  }

  async function resolveAutonomousGate(gateId: string, action: 'approve' | 'reject') {
    if (autonomousAction) return;
    setAutonomousAction(`${action}:${gateId}`);
    setAutonomousStatus(`${formatStatusLabel(action)} approval gate...`);
    try {
      const detail =
        action === 'approve'
          ? await approveAutonomousGate(gateId, { reason: 'Resolved from Autonomous workspace.' })
          : await rejectAutonomousGate(gateId, { reason: 'Rejected from Autonomous workspace.' });
      setSelectedAutonomousObjective(detail);
      setAutonomousStatus(`Approval gate ${action}d.`);
      await refreshAutonomousSignals(workspaceRoot);
    } catch (error) {
      setAutonomousStatus(error instanceof Error ? error.message : `Could not ${action} gate`);
    } finally {
      setAutonomousAction('');
    }
  }

  async function refreshCreativeStudio() {
    if (creativeLoading) return;
    setCreativeLoading(true);
    try {
      const [capabilities, jobs, library] = await Promise.all([
        getCreativeStudio(),
        listCreativeJobs({ limit: 40 }),
        getCreativeAssetLibrary({ limit: 120 })
      ]);
      setCreativeCapabilities(capabilities);
      setCreativeJobs(jobs);
      setCreativeLibrary(library);
      if (selectedCreativeJob?.id) {
        try {
          setSelectedCreativeJob(await getCreativeJob(selectedCreativeJob.id));
        } catch {
          setSelectedCreativeJob(null);
        }
      }
      setCreativeStatus('');
    } catch (error) {
      setCreativeStatus(error instanceof Error ? error.message : 'Could not load Creative Studio');
    } finally {
      setCreativeLoading(false);
    }
  }

  function creativeKindForTab(tab = creativeStudioTab): MediaKind {
    if (tab === 'video') return 'app_showcase';
    if (tab === 'beat') return 'music_beat';
    if (tab === 'voice') return 'voiceover';
    return 'product_mockup';
  }

  function creativeProviderForTab(tab = creativeStudioTab) {
    const kind = creativeKindForTab(tab);
    const selected = creativeCapabilities?.providers.find((item) => item.id === creativeProviderId);
    if (selected?.supports.includes(kind)) return selected.id;
    if (tab === 'video') return 'local_motion_storyboard';
    if (tab === 'beat' || tab === 'voice') return 'local_audio_synth';
    return 'local_creative_renderer';
  }

  async function generateCreativeAsset() {
    const prompt = creativePrompt.trim();
    if (!prompt || creativeAction) return;
    const actionId = `generate:${creativeStudioTab}`;
    const providerId = creativeProviderForTab();
    const provider = creativeCapabilities?.providers.find((item) => item.id === providerId);
    setCreativeAction(actionId);
    setCreativeStatus('Generating local creative asset package...');
    try {
      const job = await createCreativeJob({
        prompt,
        kind: creativeKindForTab(),
        studio: creativeStudioTab,
        provider_id: providerId,
        style: creativeStyle,
        output_formats:
          creativeStudioTab === 'beat' || creativeStudioTab === 'voice'
            ? ['wav', 'midi', 'json', 'zip']
            : creativeStudioTab === 'video'
              ? ['html', 'gif', 'json', 'zip']
              : ['png', 'svg', 'jpg', 'zip'],
        duration_seconds: creativeStudioTab === 'video' ? 8 : creativeStudioTab === 'voice' ? 4 : 3,
        bpm: creativeStudioTab === 'beat' ? 96 : undefined,
        key: creativeStudioTab === 'beat' ? 'A minor' : undefined,
        voice: creativeStudioTab === 'voice' ? 'calm narrator' : undefined,
        paid_approved: Boolean(provider?.paid === false),
        gpu_approved: Boolean(provider?.gpu_intensive === false),
        settings: { source: 'creative_studio_ui' }
      });
      setSelectedCreativeJob(job);
      setCreativeJobs((current) => mergeById<MediaJobResponse>([job], current));
      setCreativeStatus(`Generated ${job.assets.length} asset(s) in ${job.time_taken_seconds.toFixed(2)}s.`);
      await refreshCreativeStudio();
    } catch (error) {
      setCreativeStatus(error instanceof Error ? error.message : 'Could not generate creative asset');
    } finally {
      setCreativeAction('');
    }
  }

  async function exportSelectedCreativeJob(format: string) {
    const jobId = selectedCreativeJob?.id;
    if (!jobId || creativeAction) return;
    setCreativeAction(`export:${format}`);
    setCreativeStatus(`Exporting ${format.toUpperCase()}...`);
    try {
      const result = await exportCreativeJob(jobId, { format, include_metadata: true });
      setCreativeStatus(`Exported ${result.format.toUpperCase()} to ${result.path}.`);
      await refreshCreativeStudio();
    } catch (error) {
      setCreativeStatus(error instanceof Error ? error.message : 'Could not export creative asset');
    } finally {
      setCreativeAction('');
    }
  }

  async function cancelSelectedCreativeJob() {
    const jobId = selectedCreativeJob?.id;
    if (!jobId || creativeAction) return;
    setCreativeAction('cancel');
    setCreativeStatus('Canceling media job...');
    try {
      const job = await cancelCreativeJob(jobId);
      setSelectedCreativeJob(job);
      setCreativeStatus(job.status === 'canceled' ? 'Media job canceled.' : job.warnings.at(-1) || 'Media job is already complete.');
      await refreshCreativeStudio();
    } catch (error) {
      setCreativeStatus(error instanceof Error ? error.message : 'Could not cancel media job');
    } finally {
      setCreativeAction('');
    }
  }

  async function dispatchNextRuntimeJob() {
    const targetRoot = workspaceRoot.trim();
    if (!targetRoot || distributedRuntimeAction) return;

    setDistributedRuntimeAction('dispatch');
    setDistributedRuntimeStatus('Dispatching the next local-safe queue job...');
    try {
      const result = await dispatchExecutionQueue({
        workspace_root: targetRoot,
        limit: 1,
        allow_commands: false,
        allow_remote: false
      });
      const warning = result.warnings[0];
      const job = result.jobs[0];
      setDistributedRuntimeStatus(
        warning || (job ? `${job.title || job.id} is ${formatStatusLabel(job.status)}.` : 'No runnable jobs were dispatched.')
      );
      await Promise.all([refreshDistributedRuntime(targetRoot), refreshTasks(targetRoot)]);
    } catch (error) {
      setDistributedRuntimeStatus(error instanceof Error ? error.message : 'Could not dispatch runtime job');
    } finally {
      setDistributedRuntimeAction('');
    }
  }

  async function exportRuntimeSyncManifest() {
    const targetRoot = workspaceRoot.trim();
    if (!targetRoot || distributedRuntimeAction) return;

    setDistributedRuntimeAction('sync');
    setDistributedRuntimeStatus('Creating workspace sync manifest...');
    try {
      const manifest = await createRemoteSyncManifest({
        workspace_root: targetRoot,
        sections: ['task_history', 'checkpoints', 'project_memory', 'architecture_maps', 'validation_profiles', 'settings'],
        encrypted: true
      });
      setDistributedRuntimeStatus(`Sync manifest ${manifest.id} recorded.`);
      await refreshDistributedRuntime(targetRoot);
    } catch (error) {
      setDistributedRuntimeStatus(error instanceof Error ? error.message : 'Could not create sync manifest');
    } finally {
      setDistributedRuntimeAction('');
    }
  }

  async function scanWorkspaceOperations() {
    const targetRoot = workspaceRoot.trim();
    if (!targetRoot || workspaceOperationsLoading) return;

    setWorkspaceOperationsLoading(true);
    setWorkspaceOperationsStatus('Scanning workspace operations...');

    try {
      const result = await scanWorkspaceIntelligence({
        workspace_root: targetRoot,
        refresh_project_intelligence: true,
        generate_recommendations: true,
        include_git: true
      });
      if (!workspaceRequestIsCurrent(result.workspace_root)) return;
      setWorkspaceOperations(result);
      setWorkspaceOperationsStatus('Workspace intelligence refreshed.');
      await Promise.all([
        refreshWorkspaceHistory(result.workspace_root),
        refreshProjectIntelligence(result.workspace_root),
        refreshTasks(result.workspace_root)
      ]);
    } catch (error) {
      setWorkspaceOperationsStatus(error instanceof Error ? error.message : 'Could not scan workspace intelligence');
    } finally {
      setWorkspaceOperationsLoading(false);
    }
  }

  async function runWorkspaceOperationsJobs(jobId?: string) {
    const targetRoot = workspaceRoot.trim();
    if (!targetRoot || workspaceOperationsActionId) return;

    const actionId = `job:${jobId ?? 'all'}`;
    setWorkspaceOperationsActionId(actionId);
    setWorkspaceOperationsStatus(jobId ? 'Running scheduled intelligence job...' : 'Running safe scheduled intelligence jobs...');

    try {
      const result = await runWorkspaceIntelligenceJobs({
        workspace_root: targetRoot,
        job_ids: jobId ? [jobId] : [],
        allow_commands: false
      });
      if (result.snapshot && workspaceRequestIsCurrent(result.snapshot.workspace_root)) {
        setWorkspaceOperations(result.snapshot);
      }
      const summaries = result.jobs.map((job) => `${job.name}: ${formatStatusLabel(job.status)}`);
      setWorkspaceOperationsStatus(
        [summaries.join(' / ') || 'Scheduled intelligence jobs recorded.', ...result.warnings].filter(Boolean).join(' ')
      );
      await Promise.all([
        refreshWorkspaceHistory(result.workspace_root),
        refreshProjectIntelligence(result.workspace_root),
        refreshTasks(result.workspace_root)
      ]);
    } catch (error) {
      setWorkspaceOperationsStatus(error instanceof Error ? error.message : 'Could not run scheduled intelligence jobs');
    } finally {
      setWorkspaceOperationsActionId('');
    }
  }

  async function dismissWorkspaceOperationRecommendation(recommendation: WorkspaceRecommendation) {
    if (workspaceOperationsActionId) return;

    setWorkspaceOperationsActionId(`dismiss:${recommendation.id}`);
    setWorkspaceOperationsStatus('Dismissing recommendation...');

    try {
      const result = await dismissWorkspaceRecommendation(recommendation.id, {
        reason: 'Dismissed from Workspace Intelligence.'
      });
      setWorkspaceOperations((current) =>
        current
          ? {
              ...current,
              recommendations: current.recommendations.filter((item) => item.id !== recommendation.id)
            }
          : current
      );
      setWorkspaceOperationsStatus(result.message || 'Recommendation dismissed.');
      await refreshWorkspaceOperations(result.recommendation.workspace_root);
    } catch (error) {
      setWorkspaceOperationsStatus(error instanceof Error ? error.message : 'Could not dismiss recommendation');
    } finally {
      setWorkspaceOperationsActionId('');
    }
  }

  async function fixWorkspaceOperationRecommendation(recommendation: WorkspaceRecommendation) {
    if (workspaceOperationsActionId) return;

    setWorkspaceOperationsActionId(`fix:${recommendation.id}`);
    setWorkspaceOperationsStatus('Creating a tracked task for this recommendation...');

    try {
      const result = await fixWorkspaceRecommendation(recommendation.id, {
        reason: 'Fix requested from Workspace Intelligence.',
        create_task: true
      });
      const task = result.task;
      if (task) {
        setTasks((current) => mergeById<TaskSummary>([task], current));
        setSelectedTaskId(task.id);
        await refreshTasks(task.workspace_root);
      }
      setWorkspaceOperations((current) =>
        current
          ? {
              ...current,
              recommendations: current.recommendations.map((item) =>
                item.id === recommendation.id ? result.recommendation : item
              )
            }
          : current
      );
      setWorkspaceOperationsStatus(result.message || 'Recommendation task created.');
      await refreshWorkspaceOperations(result.recommendation.workspace_root);
    } catch (error) {
      setWorkspaceOperationsStatus(error instanceof Error ? error.message : 'Could not create recommendation task');
    } finally {
      setWorkspaceOperationsActionId('');
    }
  }

  async function refreshCheckpoints(rootOverride?: string) {
    const targetRoot = (rootOverride ?? workspaceRoot).trim();
    if (!targetRoot) return;

    setCheckpointLoading(true);
    try {
      const result = await getCheckpoints(targetRoot, 8);
      setCheckpoints(result.checkpoints);
      setCheckpointStatus('');
    } catch (error) {
      setCheckpoints([]);
      setCheckpointStatus(error instanceof Error ? error.message : 'Could not load workspace checkpoints');
    } finally {
      setCheckpointLoading(false);
    }
  }

  async function setupCurrentWorkspace() {
    const targetRoot = workspaceRoot.trim();
    if (!targetRoot || loading || workspaceSetupLoading) return;

    setWorkspaceSetupLoading(true);
    setWorkspaceProfileStatus('');
    setSaveStatus('Setting up workspace...');

    try {
      const result = await setupWorkspace({ workspace_root: targetRoot });
      setActiveWorkspaceRoot(result.workspace_root);
      setWorkspaceProfile(result.profile);
      if (result.validation_profile) {
        setValidationRecipe(result.validation_profile);
        setValidationCommandDraft(result.validation_profile.command);
        setValidationNotesDraft(result.validation_profile.notes);
      }
      await Promise.all([
        refreshFiles(),
        refreshWorkspaceHistory(result.workspace_root),
        refreshValidationRecipe(result.workspace_root)
      ]);
      const changedCount = result.created_files.length + result.updated_files.length;
      const setupStatus = result.warnings.length
        ? result.warnings.join(' ')
        : changedCount
          ? `Workspace setup saved ${changedCount} file${changedCount === 1 ? '' : 's'}.`
          : 'Workspace setup is already current.';
      setWorkspaceProfileStatus(setupStatus);
      setSaveStatus(setupStatus);
    } catch (error) {
      const setupError = error instanceof Error ? error.message : 'Could not set up workspace';
      setWorkspaceProfileStatus(setupError);
      setSaveStatus(setupError);
    } finally {
      setWorkspaceSetupLoading(false);
    }
  }

  async function useProjectRoot(root: string) {
    const targetRoot = root.trim();
    if (!targetRoot || loading) return;

    const openRequestId = workspaceOpenRequestRef.current + 1;
    const navigationVersionAtOpen = sectionNavigationVersionRef.current;
    workspaceOpenRequestRef.current = openRequestId;
    setStatus(`Opening workspace ${targetRoot}...`);
    setActiveWorkspaceRoot(targetRoot);
    setFileSearch('');
    setSelectedFilePath('');
    setSelectedFileContent('');
    setFileStatus('');
    try {
      const result = await listFiles(targetRoot);
      if (workspaceOpenRequestRef.current !== openRequestId) return;
      setActiveWorkspaceRoot(result.workspace_root);
      setFiles(result.files);
      await restoreSelectedWorkspaceFile(result.workspace_root, result.files);
      await Promise.all([
        refreshWorkspaceHistory(result.workspace_root),
        refreshWorkspaceProfile(result.workspace_root),
        refreshProjectIntelligence(result.workspace_root),
        refreshWorkspaceOperations(result.workspace_root),
        refreshDistributedRuntime(result.workspace_root),
        refreshAdaptiveSignals(result.workspace_root),
        refreshProductizationSignals(result.workspace_root),
        refreshEcosystemSignals(result.workspace_root),
        refreshAutonomousSignals(result.workspace_root),
        refreshValidationRecipe(result.workspace_root),
        refreshTasks(result.workspace_root),
        refreshCheckpoints(result.workspace_root)
      ]);
      if (sectionNavigationVersionRef.current === navigationVersionAtOpen) {
        setActiveSection('chat');
      }
      setStatus(`Workspace set to ${result.workspace_root}.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Could not open project workspace');
    }
  }

  function saveAgentForm() {
    const name = agentFormName.trim();
    if (!name) {
      setSaveStatus('Agent name is required.');
      return;
    }
    const existingAgent = editingAgentId ? customAgents.find((agent) => agent.id === editingAgentId) : null;

    const nextAgent: CustomAgent = {
      id: existingAgent?.id ?? `agent-${Date.now().toString(36)}`,
      name,
      perspective: agentFormPerspective.trim() || defaultAgentPerspective,
      mission:
        agentFormMission.trim() ||
        `You are ${name}. Work from this perspective: ${agentFormPerspective.trim() || defaultAgentPerspective}`,
      mode: agentFormMode,
      modelName: agentFormModelName.trim() || modelName,
      createdAt: existingAgent?.createdAt ?? new Date().toISOString()
    };

    setCustomAgents((current) => {
      if (existingAgent) {
        return current.map((agent) => (agent.id === nextAgent.id ? nextAgent : agent));
      }
      return [nextAgent, ...current];
    });
    setActiveAgentId(nextAgent.id);
    setEditingAgentId('');
    setSaveStatus(`${existingAgent ? 'Updated' : 'Created'} agent ${nextAgent.name}.`);
    void activateCustomAgent(nextAgent);
  }

  function editCustomAgent(agent: CustomAgent) {
    setEditingAgentId(agent.id);
    setAgentFormName(agent.name);
    setAgentFormPerspective(agent.perspective);
    setAgentFormMission(agent.mission);
    setAgentFormMode(agent.mode);
    setAgentFormModelName(agent.modelName || modelName);
    setActiveSection('agents');
    setSaveStatus(`Editing agent ${agent.name}.`);
  }

  function cancelAgentEdit() {
    setEditingAgentId('');
    setAgentFormName('Focused Reviewer');
    setAgentFormPerspective('Reviews code with a conservative, security-minded perspective before changes are applied.');
    setAgentFormMission('Review proposed changes, call out risks, then implement the smallest reliable fix.');
    setAgentFormMode('review');
    setAgentFormModelName(modelName);
    setSaveStatus('Agent edit cancelled.');
  }

  async function activateCustomAgent(agent: CustomAgent) {
    const modelTarget =
      findManagedModelByName(managedModels, agent.modelName) ||
      findManagedModelByName(selectableModelOptions, agent.modelName) ||
      {
        api: modelApi,
        endpoint: modelEndpoint,
        name: agent.modelName || modelName,
        label: agent.modelName || modelName
      };
    const nextMission =
      agent.mission.trim() ||
      `You are ${agent.name}. Work from this perspective: ${agent.perspective.trim() || defaultAgentPerspective}.`;

    setActiveAgentId(agent.id);
    setAssistantName(agent.name);
    setAssistantMission(nextMission);
    setMode(agent.mode);
    setModelApi(modelTarget.api || modelApi);
    setModelEndpoint(modelTarget.endpoint || modelEndpoint);
    setModelName(modelTarget.name || modelName);
    setSaveStatus(`Activating ${agent.name}...`);

    try {
      const nextConfig = await saveConfig({
        assistant_name: agent.name,
        assistant_mission: nextMission,
        default_mode: agent.mode,
        default_workspace: workspaceRoot.trim() || 'workspace',
        model_api: modelTarget.api || modelApi,
        model_endpoint: modelTarget.endpoint || modelEndpoint,
        model_name: modelTarget.name || modelName,
        command_allowlist:
          commandAllowlist.trim() ||
          'python,py,node,npm,npx,pnpm,pytest,uvicorn,tsc,vite,cargo,rustc,go,dotnet',
        command_timeout_seconds: commandTimeout,
        auto_run_validation: autoRunValidation
      });
      hydrateConfig(nextConfig);
      setSaveStatus(`${agent.name} is active.`);
      await refreshModelCatalog();
    } catch (error) {
      setSaveStatus(error instanceof Error ? error.message : `Could not activate ${agent.name}`);
    }
  }

  async function activateDefaultAgent() {
    setActiveAgentId(defaultAgentId);
    setAssistantName(assistantIdentity);
    setAssistantMission(defaultAssistantMission);
    setMode('build');
    setSaveStatus(`Activating ${assistantIdentity}...`);

    try {
      const nextConfig = await saveConfig({
        assistant_name: assistantIdentity,
        assistant_mission: defaultAssistantMission,
        default_mode: 'build',
        default_workspace: workspaceRoot.trim() || 'workspace',
        model_api: modelApi.trim() || 'ollama',
        model_endpoint: modelEndpoint.trim() || 'http://127.0.0.1:11434',
        model_name: modelName.trim() || 'qwen2.5-coder:7b',
        command_allowlist:
          commandAllowlist.trim() ||
          'python,py,node,npm,npx,pnpm,pytest,uvicorn,tsc,vite,cargo,rustc,go,dotnet',
        command_timeout_seconds: commandTimeout,
        auto_run_validation: autoRunValidation
      });
      hydrateConfig(nextConfig);
      setSaveStatus(`${assistantIdentity} is active.`);
    } catch (error) {
      setSaveStatus(error instanceof Error ? error.message : `Could not activate ${assistantIdentity}`);
    }
  }

  function deleteCustomAgent(agent: CustomAgent) {
    setCustomAgents((current) => current.filter((item) => item.id !== agent.id));
    if (activeAgentId === agent.id) {
      setActiveAgentId(defaultAgentId);
    }
    if (editingAgentId === agent.id) {
      setEditingAgentId('');
    }
    setSaveStatus(`Deleted agent ${agent.name}.`);
  }

  function persistConversation(threadId: string, messages: ChatMessage[], rootOverride?: string) {
    const nextThread = buildConversationPreview(threadId, messages, rootOverride ?? workspaceRoot);
    if (!nextThread) return;

    setSavedThreads((current) => {
      const next = upsertSavedConversation(current, nextThread);
      saveSavedConversations(next);
      return next;
    });
  }

  async function captureConversationMemory(userMessage: string, response: AgentResponse, nextHistory: ChatMessage[]) {
    const note = buildAutoMemoryNote(userMessage, response, nextHistory);
    if (!note) return;

    const fingerprint = autoMemoryFingerprint(userMessage, response);
    if (!fingerprint || autoMemoryFingerprints.current.has(fingerprint)) return;

    autoMemoryFingerprints.current.add(fingerprint);
    saveAutoMemoryFingerprints(Array.from(autoMemoryFingerprints.current));

    try {
      await createMemoryNote(response.workspace_root || workspaceRoot, note);
      await refreshWorkspaceHistory(response.workspace_root || workspaceRoot);
    } catch {
      autoMemoryFingerprints.current.delete(fingerprint);
      saveAutoMemoryFingerprints(Array.from(autoMemoryFingerprints.current));
    }
  }

  function openConversation(thread: SavedConversation) {
    if (loading) return;

    setCurrentThreadId(thread.id);
    setActiveThreadId(thread.id);
    setHistory(thread.messages);
    setLastResponse(null);
    setRestoredReviewSource(reviewSourceFromMessages(thread.messages, thread.workspaceRoot));
    setManualEvents([]);
    setManualValidation(null);
    setValidationContext(null);
    setValidationRepairTrail([]);
    setSelectedChangeId('');
    setPinnedContextPaths([]);
    setChatSearch('');

    if (thread.workspaceRoot) {
      setActiveWorkspaceRoot(thread.workspaceRoot);
      setFileSearch('');
      void listFiles(thread.workspaceRoot)
        .then((result) => {
          if (!workspaceRequestIsCurrent(thread.workspaceRoot)) return;
          setActiveWorkspaceRoot(result.workspace_root);
          setFiles(result.files);
          void refreshWorkspaceHistory(result.workspace_root);
          void refreshWorkspaceProfile(result.workspace_root);
          void refreshProjectIntelligence(result.workspace_root);
          void refreshWorkspaceOperations(result.workspace_root);
          void refreshValidationRecipe(result.workspace_root);
          void refreshTasks(result.workspace_root);
          void refreshCheckpoints(result.workspace_root);
        })
        .catch(() => {
          // Keep the conversation loaded even if its old workspace is unavailable.
        });
    }
  }

  function openProjectConversation(thread: SavedConversation) {
    openConversation(thread);
    setActiveSection('chat');
    setStatus(`Opened saved session "${thread.title}".`);
  }

  function deleteSavedThread(thread: SavedConversation) {
    if (loading) return;

    const confirmed = window.confirm(
      `Delete saved session "${thread.title}"? This removes it from this browser only.`
    );
    if (!confirmed) return;

    setSavedThreads((current) => {
      const next = deleteSavedConversation(current, thread.id);
      saveSavedConversations(next);
      return next;
    });
    setStatus('Saved session deleted.');
  }

  async function saveAegisSettings() {
    setSaveStatus('');

    try {
      const nextConfig = await saveConfig({
        assistant_name: assistantName.trim() || assistantIdentity,
        assistant_mission:
          assistantMission.trim() ||
          defaultAssistantMission,
        default_mode: mode,
        default_workspace: workspaceRoot.trim() || 'workspace',
        model_api: modelApi.trim() || 'ollama',
        model_endpoint: modelEndpoint.trim() || 'http://127.0.0.1:11434',
        model_name: modelName.trim() || 'qwen2.5-coder:7b',
        command_allowlist:
          commandAllowlist.trim() ||
          'python,py,node,npm,npx,pnpm,pytest,uvicorn,tsc,vite,cargo,rustc,go,dotnet',
        command_timeout_seconds: commandTimeout,
        auto_run_validation: autoRunValidation
      });

      hydrateConfig(nextConfig);
      setSaveStatus(`${productName} settings saved.`);

      const result = await listFiles(nextConfig.default_workspace);
      if (!workspaceRequestIsCurrent(nextConfig.default_workspace)) return;
      setActiveWorkspaceRoot(result.workspace_root);
      setFiles(result.files);
      await refreshWorkspaceHistory(result.workspace_root);
      await refreshWorkspaceProfile(result.workspace_root);
      await refreshProjectIntelligence(result.workspace_root);
      await refreshWorkspaceOperations(result.workspace_root);
      await refreshValidationRecipe(result.workspace_root);
      await refreshTasks(result.workspace_root);
      await refreshCheckpoints(result.workspace_root);
    } catch (error) {
      setSaveStatus(error instanceof Error ? error.message : `Could not save ${productName} settings`);
    }
  }

  async function saveValidationRecipeDraft(commandOverride?: string, notesOverride?: string) {
    if (!workspaceRoot.trim()) return;

    const command = (commandOverride ?? validationCommandDraft).trim();
    const notes = (notesOverride ?? validationNotesDraft).trim();

    try {
      const result = await updateValidationProfile(workspaceRoot, {
        command,
        label: command,
        notes
      });
      setValidationRecipe(result.profile);
      setValidationSuggestions(result.suggestions);
      setValidationCommandDraft(result.profile?.command ?? result.suggestions[0]?.command ?? '');
      setValidationNotesDraft(result.profile?.notes ?? '');
      setValidationRecipeStatus(
        result.profile ? 'Validation recipe saved for this workspace.' : 'Validation recipe cleared for this workspace.'
      );
      await refreshWorkspaceProfile(workspaceRoot);
    } catch (error) {
      setValidationRecipeStatus(error instanceof Error ? error.message : 'Could not save validation recipe');
    }
  }

  function queueMessage(content: string, options?: Partial<QueuedMessage>) {
    const queueWorkspaceRoot = options?.workspaceRoot ?? workspaceRoot;
    const queueHistory = options?.history ?? history;
    const queuedMessage = createQueuedMessage(content, {
      ...options,
      threadId: options?.threadId ?? currentThreadId,
      workspaceRoot: queueWorkspaceRoot,
      mode: options?.mode ?? mode,
      applyChanges: options?.applyChanges ?? applyChanges,
      runValidation: options?.runValidation ?? runValidation,
      contextPaths: options?.contextPaths ?? pinnedContextPaths,
      historyRecorded: options?.historyRecorded ?? false,
      missionAnchor: options?.missionAnchor ?? createMissionAnchorMessage(queueHistory, content, queueWorkspaceRoot),
      history: queueHistory
    });
    if (!queuedMessage) return;

    setQueuedMessages((current) => appendQueuedMessage(current, queuedMessage));
    setStatus(
      connectionState === 'connected'
        ? `${assistantIdentity} is focused. Your message is queued for the next available turn.`
        : `Backend ${connectionStateLabel(connectionState).toLowerCase()}. Your message is queued and will send automatically.`
    );
  }

  function discardQueuedMessage(id: string) {
    setQueuedMessages((current) => removeQueuedMessage(current, id));
    setStatus('Queued message discarded.');
  }

  function reorderQueuedMessage(id: string, direction: 'up' | 'down') {
    setQueuedMessages((current) => moveQueuedMessage(current, id, direction));
    setStatus(direction === 'up' ? 'Queued message moved earlier.' : 'Queued message moved later.');
  }

  function toggleQueueAutoSendPaused() {
    const nextPaused = !queueAutoSendPaused;
    setQueueAutoSendPaused(nextPaused);
    setStatus(nextPaused ? 'Queued prompts paused.' : 'Queued prompts will send automatically.');
  }

  function clearQueuedMessageBacklog() {
    setQueuedMessages(clearQueuedMessages());
    setStatus('Queued messages cleared.');
  }

  async function readOldContentForGeneratedChange(
    change: FileChange,
    source: GeneratedReviewSource | null = activeReviewSource
  ): Promise<string | null> {
    if (change.action === 'create') return null;

    const sourceWorkspaceRoot = source?.workspaceRoot || workspaceRoot;
    if (source?.checkpoint) {
      try {
        const checkpointFile = await readFile(
          sourceWorkspaceRoot,
          `.aegis/checkpoints/${source.checkpoint}/files/${change.path}`
        );
        return checkpointFile.content;
      } catch {
        // Fall back to the live file below when a checkpoint did not store a prior version.
      }
    }

    try {
      const existing = await readFile(sourceWorkspaceRoot, change.path);
      return existing.content;
    } catch {
      return '';
    }
  }

  function pinWorkspaceFile(path: string) {
    setPinnedContextPaths((current) => addPinnedContextPath(current, path));
    setStatus(`Pinned ${path} for the next prompt.`);
  }

  function unpinWorkspaceFile(path: string) {
    setPinnedContextPaths((current) => removePinnedContextPath(current, path));
    setStatus(`Removed ${path} from pinned context.`);
  }

  function stopActiveChatRequest() {
    if (!activeChatAbortController.current || !activeChatRequest) return;

    activeChatAbortController.current.abort();
    setStatus('Stopping current response...');
  }

  async function submit(
    event?: FormEvent<HTMLFormElement>,
    override?: string,
    queuedMessage?: QueuedMessage,
    submitOptions: SubmitOptions = {}
  ) {
    event?.preventDefault();

    const content = (override ?? message).trim();
    if (!content) return;

    const activeContextPaths = queuedMessage?.contextPaths ?? submitOptions.contextPaths ?? pinnedContextPaths;

    if (shouldQueueOutboundMessage(loading, connectionState, queuedMessage)) {
      queueMessage(
        content,
        queuedMessage
          ? { ...queuedMessage, contextPaths: activeContextPaths }
          : { ...submitOptions, contextPaths: activeContextPaths }
      );
      clearComposerDraft();
      setMessage('');
      setPinnedContextPaths([]);
      return;
    }

    setLoading(true);
    setActiveChatRequest(true);
    setStatus('');
    clearComposerDraft();
    setMessage('');
    setManualEvents([]);
    setManualValidation(null);
    setValidationContext(null);
    setRetryCount(0);
    setPinnedContextPaths([]);
    const abortController = new AbortController();
    activeChatAbortController.current = abortController;

    const threadIdForSubmit = queuedMessage?.threadId || submitOptions.threadId || currentThreadId;
    const requestWorkspaceRoot = queuedMessage?.workspaceRoot ?? submitOptions.workspaceRoot ?? workspaceRoot;
    const baseHistory = queuedMessage?.history?.length
      ? queuedMessage.history
      : submitOptions.history?.length
        ? submitOptions.history
        : history;
    const historyRecorded = queuedMessage?.historyRecorded ?? submitOptions.historyRecorded ?? false;
    const queuedHistoryAlreadyHasPrompt =
      Boolean(historyRecorded) &&
      baseHistory.some((item) => item.role === 'user' && item.content.trim() === content);
    const nextHistory: ChatMessage[] = queuedHistoryAlreadyHasPrompt
      ? baseHistory
      : [...baseHistory, { role: 'user', content }];
    if ((queuedMessage?.threadId || submitOptions.threadId) && threadIdForSubmit !== currentThreadId) {
      setCurrentThreadId(threadIdForSubmit);
    }
    if (!historyRecorded) {
      setHistory(nextHistory);
    }
    if (historyRecorded || queuedMessage?.threadId || submitOptions.threadId) {
      setHistory(nextHistory);
    }
    setActiveThreadId(threadIdForSubmit);
    persistConversation(threadIdForSubmit, nextHistory, requestWorkspaceRoot);

    const attemptSubmit = async (attempt: number): Promise<void> => {
      let streamedAssistant = '';
      let previewSegmentStart = -1;
      let activePreviewAttempt: number | undefined;
      try {
        const response = await streamAgentMessage({
          message: content,
          history: buildAgentRequestHistory(
            nextHistory,
            content,
            requestWorkspaceRoot,
            queuedMessage?.missionAnchor ?? submitOptions.missionAnchor
          ),
          workspace_root: requestWorkspaceRoot,
          mode: queuedMessage?.mode ?? submitOptions.mode ?? mode,
          apply_changes: queuedMessage?.applyChanges ?? submitOptions.applyChanges ?? applyChanges,
          run_validation: queuedMessage?.runValidation ?? submitOptions.runValidation ?? runValidation,
          context_paths: activeContextPaths,
          max_repair_attempts: Math.max(0, maxRetries - attempt)
        }, {
          signal: abortController.signal,
          onMeta: (payload) => {
            const streamMode = payload.stream_mode ? ` (${payload.stream_mode})` : '';
            setStatus(`Streaming response started${streamMode}.`);
          },
          onStatus: (payload) => {
            setStatus(payload.message || payload.stage || `${assistantIdentity} is working...`);
          },
          onDelta: (payload) => {
            const isPreview = payload.source === 'structured_reply_preview';
            const previewAction = payload.preview_action || 'append';

            if (isPreview && previewAction === 'reset') {
              if (previewSegmentStart >= 0) {
                streamedAssistant = streamedAssistant.slice(0, previewSegmentStart);
              }
              previewSegmentStart = -1;
              activePreviewAttempt = undefined;
              setStatus(
                payload.message ||
                  (payload.provider_label
                    ? `Retiring ${payload.provider_label} preview before trying the next route...`
                    : 'Retiring failed provider preview before trying the next route...')
              );
              setHistory([
                ...nextHistory,
                {
                  role: 'assistant',
                  content: streamedAssistant
                }
              ]);
              return;
            }

            if (payload.delta) {
              if (isPreview) {
                if (activePreviewAttempt !== payload.preview_attempt || previewSegmentStart < 0) {
                  previewSegmentStart = streamedAssistant.length;
                  activePreviewAttempt = payload.preview_attempt;
                }
              }
              streamedAssistant += payload.delta;
              const providerLabel = [payload.provider_label, payload.model]
                .filter(Boolean)
                .join(' / ');
              setStatus(
                payload.source === 'structured_preview_reconciliation'
                  ? 'Reconciling streamed preview with final response...'
                  : isPreview && providerLabel
                    ? `Receiving streamed preview from ${providerLabel}...`
                  : 'Receiving streamed response...'
              );
              setHistory([
                ...nextHistory,
                {
                  role: 'assistant',
                  content: streamedAssistant
                }
              ]);
            }
          },
          onFinal: () => {
            setStatus('Final response received.');
          }
        });

        setLastResponse(response);
        if (submitOptions.repairTrailId) {
          recordValidationRepairResult(submitOptions.repairTrailId, response);
        }
        setConnectionState('connected');
        setValidationRecipe(response.validation_profile ?? validationRecipe);
        setFiles(response.workspace_files);
        setActiveWorkspaceRoot(response.workspace_root);
        await refreshWorkspaceHistory(response.workspace_root);
        await refreshTasks(response.workspace_root);
        await refreshWorkspaceProfile(response.workspace_root);
        await refreshProjectIntelligence(response.workspace_root);
        await refreshWorkspaceOperations(response.workspace_root);
        await refreshValidationRecipe(response.workspace_root);
        await refreshCheckpoints(response.workspace_root);
        const finalHistory: ChatMessage[] = [
          ...nextHistory,
          {
            role: 'assistant',
            content: buildAssistantSummary(response),
            metadata: response.changes.length
              ? {
                  generatedChanges: response.changes,
                  applied: response.applied,
                  warnings: response.warnings,
                  checkpoint: response.checkpoint ?? null,
                  workspaceRoot: response.workspace_root,
                  taskId: response.task_id
                }
              : undefined
          }
        ];
        setHistory(finalHistory);
        persistConversation(threadIdForSubmit, finalHistory, response.workspace_root);
        void captureConversationMemory(content, response, finalHistory);
        setRetryCount(0);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : `${assistantIdentity} could not complete the request`;

        if (isAbortError(error) || abortController.signal.aborted) {
          const stoppedHistory: ChatMessage[] = streamedAssistant.trim()
            ? [
                ...nextHistory,
                {
                  role: 'assistant',
                  content: `${streamedAssistant.trim()}\n\n[Stopped by user]`
                }
              ]
            : nextHistory;
          setHistory(stoppedHistory);
          persistConversation(threadIdForSubmit, stoppedHistory, requestWorkspaceRoot);
          setStatus('Session request stopped.');
          setRetryCount(0);
          return;
        }

        if (attempt < maxRetries) {
          const nextRetry = attempt + 1;
          setRetryCount(nextRetry);
          setHistory(nextHistory);
          persistConversation(threadIdForSubmit, nextHistory, requestWorkspaceRoot);
          setStatus(`Attempt ${nextRetry} failed: ${errorMessage}. Retrying...`);
          await delay(1000 * nextRetry);
          if (abortController.signal.aborted) {
            throw new DOMException('Session request stopped.', 'AbortError');
          }
          return attemptSubmit(nextRetry);
        }

        setHistory(nextHistory);
        persistConversation(threadIdForSubmit, nextHistory, requestWorkspaceRoot);
        if (isLikelyConnectionError(errorMessage)) {
          setConnectionState('reconnecting');
          queueMessage(content, {
            ...submitOptions,
            ...queuedMessage,
            threadId: threadIdForSubmit,
            workspaceRoot: requestWorkspaceRoot,
            historyRecorded: true,
            missionAnchor:
              queuedMessage?.missionAnchor ??
              submitOptions.missionAnchor ??
              createMissionAnchorMessage(nextHistory, content, requestWorkspaceRoot),
            contextPaths: activeContextPaths,
            history: nextHistory
          });
          setStatus(`Backend connection failed after ${maxRetries} attempts. Message re-queued automatically.`);
        } else {
          setStatus(`Failed after ${maxRetries} attempts: ${errorMessage}`);
        }
        setEngineReady(false);
        setRetryCount(0);
      }
    };

    try {
      await attemptSubmit(0);
    } finally {
      if (activeChatAbortController.current === abortController) {
        activeChatAbortController.current = null;
      }
      setActiveChatRequest(false);
      setLoading(false);
    }
  }

  async function applyGeneratedChanges(scope: ApplyChangeScope) {
    const changesToApply = changesForApply(pendingChanges, selectedChangeId, scope, appliedChanges, applyWarnings);
    if (!changesToApply.length || loading) return;
    const nextValidationContext: GeneratedChangeValidationContext = {
      scope,
      changes: changesToApply.map((change) => ({ action: change.action, path: change.path }))
    };

    setLoading(true);
    setStatus(scope === 'selected' ? 'Applying selected generated change...' : 'Applying remaining generated changes...');
    setValidationContext(null);

    try {
      const result = await applyFileChanges({ workspace_root: workspaceRoot, changes: changesToApply });
      setFiles(result.workspace_files);
      const applyStatus = applyStatusWithWarnings(appliedChangeStatus(result.applied.length, scope), result.warnings);

      setLastResponse((current) =>
        current
          ? {
              ...current,
              applied: mergeAppliedChangeRefs(current.applied, result.applied),
              warnings: mergeApplyWarnings(current.warnings, result.warnings),
              workspace_files: result.workspace_files
            }
          : current
      );

      await refreshFiles();
      await refreshCheckpoints(result.workspace_root);
      await refreshTasks(result.workspace_root);
      await refreshWorkspaceOperations(result.workspace_root);

      const previewPath = previewPathForApplyResult(changesToApply, result.applied);
      if (previewPath) {
        await openWorkspaceFile(
          {
            path: previewPath,
            size: 0,
            kind: 'text'
          },
          { allowWhileLoading: true, workspaceRootOverride: result.workspace_root }
        );
      }

      if ((runValidation || autoRunValidation) && result.applied.length) {
        setStatus(`${applyStatus} Running validation...`);
        setSaveStatus('Running workspace validation after applying generated changes...');

        try {
          const validationResult = await runWorkspaceValidation({ workspace_root: result.workspace_root });
          await syncValidationResult(validationResult);
          setValidationContext(nextValidationContext);
          const validationStatus = validationResultStatus(validationResult);
          const combinedStatus = combinedApplyValidationStatus(applyStatus, validationStatus);
          setStatus(combinedStatus);
          setSaveStatus(combinedStatus);
        } catch (validationError) {
          const validationStatus =
            validationError instanceof Error ? validationError.message : 'Validation failed to run';
          const combinedStatus = combinedApplyValidationStatus(
            applyStatus,
            `Validation failed to run: ${validationStatus}`
          );
          setStatus(combinedStatus);
          setSaveStatus(combinedStatus);
        }
      } else {
        setValidationContext(null);
        setStatus(applyStatus);
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Could not apply the preview');
    } finally {
      setLoading(false);
    }
  }

  async function restoreWorkspaceCheckpoint(checkpoint: CheckpointSummary) {
    if (loading || restoringCheckpointId || !workspaceRoot.trim()) return;

    const fileList = checkpoint.files.slice(0, 4).map((item) => item.path).join(', ');
    const suffix = checkpoint.file_count > 4 ? ` and ${checkpoint.file_count - 4} more` : '';
    const confirmed = window.confirm(
      `Restore checkpoint ${checkpoint.id}? This will replace tracked files${fileList ? `: ${fileList}${suffix}` : '.'}`
    );
    if (!confirmed) return;

    setRestoringCheckpointId(checkpoint.id);
    setCheckpointStatus(`Restoring checkpoint ${checkpoint.id}...`);
    setSaveStatus(`Restoring checkpoint ${checkpoint.id}...`);

    try {
      const result = await restoreCheckpoint({ workspace_root: workspaceRoot, checkpoint: checkpoint.id });
      setActiveWorkspaceRoot(result.workspace_root);
      setFiles(result.workspace_files);
      setSelectedFilePath('');
      setSelectedFileContent('');
      setFileStatus('');
      await Promise.all([
        refreshWorkspaceHistory(result.workspace_root),
        refreshWorkspaceProfile(result.workspace_root),
        refreshValidationRecipe(result.workspace_root),
        refreshCheckpoints(result.workspace_root)
      ]);

      const restoreStatus = result.warnings.length
        ? result.warnings.join(' ')
        : result.restored.length
          ? `Restored ${result.restored.length} file${result.restored.length === 1 ? '' : 's'} from checkpoint.`
          : 'Checkpoint restore finished with no file changes.';
      setCheckpointStatus(restoreStatus);
      setSaveStatus(restoreStatus);
      setStatus(restoreStatus);
    } catch (error) {
      const restoreError = error instanceof Error ? error.message : 'Could not restore checkpoint';
      setCheckpointStatus(restoreError);
      setSaveStatus(restoreError);
    } finally {
      setRestoringCheckpointId('');
    }
  }

  function saveFileToDisk() {
    if (!selectedChange) return;

    const content = selectedChange.content ?? '';
    const filename = selectedChange.path.split('/').pop() || 'file.txt';
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
    setStatus(`Saved ${filename} to your downloads`);
  }

  async function copySelectedGeneratedChangePath() {
    if (!selectedChange) return;
    await copyTextToClipboard(selectedChange.path, 'generated file path');
  }

  async function copySelectedGeneratedChangeContent() {
    if (!selectedChange || selectedChange.content === null) return;
    await copyTextToClipboard(selectedChange.content, 'generated file content');
  }

  async function copySelectedGeneratedChangeDiff() {
    const patch = selectedChangeDiff?.patch ?? '';
    if (!selectedChange || !patch.trim()) return;
    await copyTextToClipboard(patch, 'generated diff');
  }

  async function copySelectedWorkspaceFilePath() {
    if (!selectedFilePath) return;
    await copyTextToClipboard(selectedFilePath, 'workspace file path');
  }

  async function copySelectedWorkspaceFileContent() {
    if (!selectedFilePath) return;
    await copyTextToClipboard(selectedFileContent, 'workspace file content');
  }

  async function copyValidationOutput() {
    if (!validation) return;
    await copyTextToClipboard(
      validationRunClipboardText(validation, activeValidationContext ? { changes: activeValidationContext.changes } : undefined),
      'validation output'
    );
  }

  function buildValidationRepairSubmission() {
    if (!validation || !validationNeedsRepair) return null;

    const contextChanges =
      activeValidationContext?.changes.map((change) => ({
        action: change.action,
        path: change.path
      })) ?? [];
    const context = contextChanges.length ? { changes: contextChanges } : undefined;
    return {
      prompt: validationRepairPromptText(validation, context),
      contextChanges,
      contextPaths: contextChanges.map((change) => change.path)
    };
  }

  function draftValidationRepairPrompt() {
    const repair = buildValidationRepairSubmission();
    if (!repair) return;

    setMessage(repair.prompt);

    if (repair.contextPaths.length) {
      setPinnedContextPaths((current) =>
        repair.contextPaths.reduce(
          (next, path) => addPinnedContextPath(next, path),
          current
        )
      );
      const targetCount = repair.contextPaths.length;
      setStatus(`Drafted repair prompt with ${targetCount} validation target${targetCount === 1 ? '' : 's'} pinned.`);
    } else {
      setStatus('Drafted repair prompt from the validation output.');
    }
  }

  async function sendValidationRepairPrompt() {
    const repair = buildValidationRepairSubmission();
    if (!repair || !validation || loading) return;

    const repairTrailId = createValidationRepairTrailId();
    setValidationRepairTrail((current) => [
      {
        id: repairTrailId,
        createdAt: new Date().toISOString(),
        command: validation.command || 'validation',
        prompt: repair.prompt,
        followUpPrompt: '',
        sourceSummary: validation.summary || 'Validation failed.',
        sourceReason: validation.reason,
        sourceExitCode: validation.exit_code,
        contextChanges: repair.contextChanges,
        contextPaths: repair.contextPaths,
        status: 'sent',
        resultSummary: 'Repair request sent. Waiting for follow-up validation.',
        resultExitCode: null,
        responseTaskId: ''
      },
      ...current
    ]);

    await submit(undefined, repair.prompt, undefined, {
      applyChanges: false,
      contextPaths: repair.contextPaths,
      mode: 'develop',
      repairTrailId,
      runValidation: true
    });
  }

  function recordValidationRepairResult(repairTrailId: string, response: AgentResponse) {
    setValidationRepairTrail((current) =>
      current.map((item) => {
        if (item.id !== repairTrailId) return item;

        const validationResult = response.validation;
        if (!validationResult) {
          return {
            ...item,
            resultSummary: 'Repair response finished without follow-up validation.',
            responseTaskId: response.task_id
          };
        }

        const passed = validationResult.allowed && !validationResult.timed_out && validationResult.exit_code === 0;
        const followUpPrompt = passed
          ? ''
          : validationRepairFollowUpPromptText(
              item.prompt,
              validationResult,
              item.contextChanges.length ? { changes: item.contextChanges } : undefined
            );
        return {
          ...item,
          status: passed ? 'passed' : 'failed',
          resultSummary: validationResult.summary || validationResult.reason || validationResult.stderr || validationResult.stdout || 'Validation result available.',
          resultExitCode: validationResult.exit_code,
          followUpPrompt,
          responseTaskId: response.task_id
        };
      })
    );
  }

  function draftValidationRepairFollowUp(item: ValidationRepairTrailItem) {
    if (!item.followUpPrompt) return;

    setMessage(item.followUpPrompt);
    if (item.contextPaths.length) {
      setPinnedContextPaths((current) =>
        item.contextPaths.reduce((next, path) => addPinnedContextPath(next, path), current)
      );
      const targetCount = item.contextPaths.length;
      setStatus(`Drafted follow-up repair prompt with ${targetCount} validation target${targetCount === 1 ? '' : 's'} pinned.`);
    } else {
      setStatus('Drafted follow-up repair prompt.');
    }
  }

  async function sendValidationRepairFollowUp(item: ValidationRepairTrailItem) {
    if (!item.followUpPrompt || loading) return;

    setValidationRepairTrail((current) =>
      current.map((candidate) =>
        candidate.id === item.id
          ? {
              ...candidate,
              prompt: item.followUpPrompt,
              followUpPrompt: '',
              status: 'sent',
              resultSummary: 'Follow-up repair request sent. Waiting for validation.',
              resultExitCode: null,
              responseTaskId: ''
            }
          : candidate
      )
    );

    await submit(undefined, item.followUpPrompt, undefined, {
      applyChanges: false,
      contextPaths: item.contextPaths,
      mode: 'develop',
      repairTrailId: item.id,
      runValidation: true
    });
  }

  function reopenValidationRepairPrompt(item: ValidationRepairTrailItem) {
    setMessage(item.prompt);

    if (item.contextPaths.length) {
      setPinnedContextPaths((current) =>
        item.contextPaths.reduce((next, path) => addPinnedContextPath(next, path), current)
      );
      const targetCount = item.contextPaths.length;
      setStatus(`Reopened repair prompt with ${targetCount} validation target${targetCount === 1 ? '' : 's'} pinned.`);
    } else {
      setStatus('Reopened repair prompt.');
    }
  }

  async function copyValidationRepairTargets(item: ValidationRepairTrailItem) {
    const targetList = item.contextPaths.length ? `${item.contextPaths.join('\n')}\n` : '(no validation targets)';
    await copyTextToClipboard(targetList, 'repair target files');
  }

  async function copyValidationRepairBrief(item: ValidationRepairTrailItem) {
    await copyTextToClipboard(validationRepairBriefClipboardText(item), 'repair brief');
  }

  async function copyTextToClipboard(text: string, label: string) {
    try {
      await navigator.clipboard.writeText(text);
      setStatus(`Copied ${label} to clipboard.`);
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'Clipboard permission is unavailable';
      setStatus(`Could not copy ${label}: ${detail}`);
    }
  }

  function reviewValidatedGeneratedChange(change: Pick<FileChange, 'action' | 'path'>) {
    setSelectedChangeId(changeId(change));
    setSelectedPreviewTab('diff');
    setStatus(`Reviewing validation target ${change.path}.`);
  }

  function reviewRepairTrailTarget(change: Pick<FileChange, 'action' | 'path'>) {
    setSelectedChangeId(changeId(change));
    setSelectedPreviewTab('diff');
    setStatus(`Reviewing repair target ${change.path}.`);
  }

  function exportCurrentChatTranscript() {
    if (!history.length) return;

    const title = currentThreadPreview.title || `${productName} session`;
    const content = buildConversationMarkdown(title, history, workspaceRoot);
    const filename = conversationMarkdownFilename(title);
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
    setStatus(`Exported transcript ${filename}.`);
  }

  async function openWorkspaceFile(
    file: WorkspaceFile,
    options: { allowWhileLoading?: boolean; workspaceRootOverride?: string } = {}
  ) {
    if (file.kind !== 'text' || (loading && !options.allowWhileLoading)) return;

    setSelectedFilePath(file.path);
    saveSelectedWorkspaceFile(options.workspaceRootOverride ?? workspaceRoot, file.path);
    setFileStatus('Loading file...');

    try {
      const result = await readFile(options.workspaceRootOverride ?? workspaceRoot, file.path);
      setSelectedFileContent(result.content);
      setFileStatus('');
    } catch (error) {
      setSelectedFileContent('');
      setFileStatus(error instanceof Error ? error.message : 'Could not read file');
    }
  }

  async function restoreSelectedWorkspaceFile(targetRoot: string, nextFiles: WorkspaceFile[]) {
    const persistedPath = loadSelectedWorkspaceFile(targetRoot);
    if (!persistedPath) return;

    const persistedFile = nextFiles.find((file) => file.kind === 'text' && file.path === persistedPath);
    if (!persistedFile) {
      saveSelectedWorkspaceFile(targetRoot, '');
      return;
    }

    await openWorkspaceFile(persistedFile, {
      allowWhileLoading: true,
      workspaceRootOverride: targetRoot
    });
  }

  async function validateNow() {
    if (loading || !workspaceRoot) return;

    setLoading(true);
    setStatus('');
    setSaveStatus('Running workspace validation...');
    setValidationContext(null);

    try {
      const result = await runWorkspaceValidation({ workspace_root: workspaceRoot });
      await syncValidationResult(result);
      const validationStatus = validationResultStatus(result);
      setStatus(validationStatus);
      setSaveStatus(validationStatus);
    } catch (error) {
      const validationError = error instanceof Error ? error.message : 'Validation failed to run';
      setStatus(validationError);
      setSaveStatus(validationError);
    } finally {
      setLoading(false);
    }
  }

  async function syncValidationResult(result: ValidateResponse) {
    setManualEvents(result.events);
    setManualValidation(result.validation ?? null);
    setValidationRecipe(result.validation_profile ?? validationRecipe);
    setActiveWorkspaceRoot(result.workspace_root);
    await refreshWorkspaceHistory(result.workspace_root);
    await refreshWorkspaceProfile(result.workspace_root);
    await refreshValidationRecipe(result.workspace_root);
  }

  function startNewChat() {
    if (loading) return;

    persistConversation(currentThreadId, history, workspaceRoot);
    const nextThreadId = createConversationId();
    setCurrentThreadId(nextThreadId);
    setActiveThreadId(nextThreadId);
    setHistory([]);
    setLastResponse(null);
    setRestoredReviewSource(null);
    setManualEvents([]);
    setManualValidation(null);
    setValidationContext(null);
    setValidationRepairTrail([]);
    setSelectedChangeId('');
    setSelectedFilePath('');
    setSelectedFileContent('');
    setFileStatus('');
    setStatus('');
    setPinnedContextPaths([]);
    clearComposerDraft();
    setMessage('');
    setChatSearch('');
    setShowDetailsPanel(true);
  }

  const palette = getPalette(isDarkMode);
  const modeChoices = config?.modes?.length ? config.modes : fallbackModeOptions;

  function renderChatMessage(item: ChatMessage, index: number) {
    const isUser = item.role === 'user';
    const messageReviewSource = item.role === 'assistant' ? reviewSourceFromMessage(item, workspaceRoot) : null;
    const liveReviewSource =
      item.role === 'assistant' && index === latestAssistantMessageIndex && lastResponse ? activeReviewSource : null;
    const inlineReviewSource = liveReviewSource ?? messageReviewSource;
    const inlineDiffs =
      inlineReviewSource && activeReviewSource && sameReviewSource(inlineReviewSource, activeReviewSource)
        ? changeDiffs
        : {};

    return (
      <div key={`${item.role}-${index}`} style={styles.messageRow(isUser)}>
        <div style={styles.avatar(palette, isUser)}>
          {isUser ? <User size={16} /> : <Bot size={16} />}
        </div>

        <div style={styles.messageBubble(palette, isUser)}>
          <div style={styles.messageRole(palette)}>
            {isUser ? 'You' : assistantName}
          </div>
          <div style={styles.messageContentStack}>
            {parseChatContentBlocks(item.content).map((block, blockIndex) =>
              block.type === 'code' ? (
                <div key={`code-${blockIndex}`} style={styles.chatCodeFrame(palette)}>
                  <div style={styles.chatCodeHeader(palette)}>
                    <Code size={14} />
                    <span>{block.language || 'code'}</span>
                    <button
                      type="button"
                      style={styles.chatCodeCopyButton(palette)}
                      onClick={() => void copyTextToClipboard(block.content, 'code block')}
                    >
                      <Copy size={13} />
                      Copy
                    </button>
                  </div>
                  <pre style={styles.chatCodeBlock(palette)}>
                    <code>{block.content}</code>
                  </pre>
                </div>
              ) : (
                <div key={`text-${blockIndex}`} style={styles.messageText(palette)}>
                  {block.content}
                </div>
              )
            )}
          </div>

          {inlineReviewSource ? renderInlineChangeReview(inlineReviewSource, inlineDiffs) : null}
        </div>
      </div>
    );
  }

  function renderInlineChangeReview(source: GeneratedReviewSource, diffs: Record<string, DiffCompareResponse>) {
    if (!source.changes.length) return null;

    const stats = summarizeGeneratedDiffStats(source.changes, diffs);
    const filesLabel = `${stats.total} file${stats.total === 1 ? '' : 's'} changed`;
    const statsReady = stats.ready === stats.total;
    const reviewId = inlineReviewId(source);
    const expanded = expandedInlineReviewIds.includes(reviewId);

    return (
      <div style={styles.inlineChangeReview(palette)} data-testid="inline-change-review">
        <div style={styles.inlineChangeHeader}>
          <div style={styles.inlineChangeTitle(palette)}>
            <FileCode2 size={16} />
            <span>{filesLabel}</span>
            <span style={styles.addedLines}>+{stats.added}</span>
            <span style={styles.removedLines}>-{stats.removed}</span>
          </div>
          <div style={styles.inlineChangeActions}>
            <button
              type="button"
              style={styles.reviewChangesButton(palette)}
              onClick={() => toggleInlineReview(reviewId)}
              aria-expanded={expanded}
              aria-label={expanded ? 'Hide generated file list' : 'Show generated file list'}
            >
              {expanded ? 'Hide files' : 'Show files'}
            </button>
            <button
              type="button"
              style={styles.reviewChangesButton(palette)}
              onClick={() => openGeneratedChangeReview(undefined, source)}
              aria-label="Review generated file changes"
            >
              Review changes
            </button>
          </div>
        </div>

        {!statsReady || changeDiffSummaryStatus ? (
          <div style={styles.inlineChangeStatus(palette)}>
            {sameReviewSource(source, activeReviewSource)
              ? changeDiffSummaryStatus || `Line counts ready for ${stats.ready}/${stats.total}.`
              : 'Open this review to calculate exact line counts.'}
          </div>
        ) : null}

        {expanded ? (
          <div style={styles.inlineChangeList} data-testid="inline-change-list">
            {source.changes.slice(0, 6).map((change) => {
              const id = changeId(change);
              const diff = diffs[id];
              return (
                <button
                  key={id}
                  type="button"
                  style={styles.inlineChangeItem(palette)}
                  onClick={() => openGeneratedChangeReview(id, source)}
                  aria-label={`Open inline file change ${change.path}`}
                >
                  <span style={styles.inlineChangePath(palette)}>{change.path}</span>
                  <span style={styles.inlineChangeAction(palette)}>{change.action}</span>
                  <span style={styles.inlineChangeDelta} data-testid={`inline-change-stat-${id}`}>
                    {diff ? (
                      <>
                        <span style={styles.addedLines}>+{diff.added_lines}</span>
                        <span style={styles.removedLines}>-{diff.removed_lines}</span>
                      </>
                    ) : (
                      <span style={styles.inlineChangePending(palette)}>...</span>
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        ) : null}
      </div>
    );
  }

  function inlineReviewId(source: GeneratedReviewSource) {
    return source.taskId || `${source.workspaceRoot}|${source.checkpoint ?? ''}|${source.changes.map(changeId).join('|')}`;
  }

  function toggleInlineReview(reviewId: string) {
    setExpandedInlineReviewIds((current) =>
      current.includes(reviewId) ? current.filter((item) => item !== reviewId) : [...current, reviewId]
    );
  }

  function renderQueuedPromptStack() {
    if (!queuedMessages.length) return null;

    return (
      <div style={styles.inlineQueuePanel(palette)} data-testid="inline-queue-panel">
        <div style={styles.inlineQueueHeader(palette)}>
          <div style={styles.inlineQueueTitle(palette)}>
            <MessageSquarePlus size={15} />
            <span>Next prompts</span>
          </div>
          <span>{queuedMessages.length}</span>
        </div>
        <div style={styles.inlineQueueList}>
          {queuedMessages.slice(0, 4).map((queued, index) => (
            <div key={queued.id} style={styles.inlineQueueItem(palette)}>
              <span style={styles.inlineQueueIndex(palette)}>{index + 1}</span>
              <span style={styles.inlineQueueText(palette)}>{queued.content}</span>
              <button
                type="button"
                style={styles.inlineQueueDiscard(palette)}
                onClick={() => discardQueuedMessage(queued.id)}
                aria-label={`Remove inline queued prompt ${index + 1}`}
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>
      </div>
    );
  }

  function openGeneratedChangeReview(targetId?: string, source: GeneratedReviewSource | null = activeReviewSource) {
    if (source?.restored || (!lastResponse && source)) {
      setRestoredReviewSource(source);
    } else if (lastResponse) {
      setRestoredReviewSource(null);
    }
    setActiveSection('chat');
    setShowDetailsPanel(true);
    const sourceChanges = source?.changes ?? pendingChanges;
    if (targetId) {
      setSelectedChangeId(targetId);
    } else if (sourceChanges.length) {
      setSelectedChangeId(changeId(sourceChanges[0]));
    }
    setSelectedPreviewTab('diff');
  }

  function reviewSourceFromMessages(messages: ChatMessage[], root: string): GeneratedReviewSource | null {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const source = reviewSourceFromMessage(messages[index], root);
      if (source) return source;
    }
    return null;
  }

  function reviewSourceFromMessage(message: ChatMessage, root: string): GeneratedReviewSource | null {
    if (message.role !== 'assistant') return null;

    if (message.metadata?.generatedChanges?.length) {
      return {
        changes: message.metadata.generatedChanges,
        applied: message.metadata.applied ?? [],
        warnings: message.metadata.warnings ?? [],
        checkpoint: message.metadata.checkpoint,
        workspaceRoot: message.metadata.workspaceRoot || root,
        taskId: message.metadata.taskId,
        restored: true
      };
    }

    const parsed = parseGeneratedChangeTranscript(message.content);
    if (!parsed) return null;
    return {
      changes: parsed.changes,
      applied: parsed.applied,
      warnings: [],
      checkpoint: null,
      workspaceRoot: root,
      restored: true
    };
  }

  function sameReviewSource(left: GeneratedReviewSource | null | undefined, right: GeneratedReviewSource | null | undefined) {
    if (!left || !right) return false;
    if (left.taskId && right.taskId) return left.taskId === right.taskId;
    return (
      left.workspaceRoot === right.workspaceRoot &&
      (left.checkpoint ?? '') === (right.checkpoint ?? '') &&
      left.changes.map(changeId).join('|') === right.changes.map(changeId).join('|')
    );
  }

  function renderProductizationRoute() {
    return (
      <LazyPanelBoundary
        title="Hardening surface could not load"
        detail="The workspace remains active. Retry the hardening route or return to another section."
        resetKey={`${workspaceRoot}:hardening`}
      >
        <Suspense fallback={<div style={styles.routeFallback(palette)}>Opening hardening controls...</div>}>
          <ProductizationSurface
            productization={productization}
            productizationLoading={productizationLoading}
            productizationStatus={productizationStatus}
            productizationAction={productizationAction}
            palette={palette}
            styles={styles}
            renderSurfaceHeader={renderSurfaceHeader}
            refreshProductizationSignals={refreshProductizationSignals}
            validateSamplePluginManifest={validateSamplePluginManifest}
            updatePluginState={updatePluginState}
          />
        </Suspense>
      </LazyPanelBoundary>
    );
  }

  function renderCreativeStudioRoute() {
    return (
      <LazyPanelBoundary
        title="Creative Studio could not load"
        detail="The workspace remains active. Retry the creative route or return to another section."
        resetKey={`${workspaceRoot}:creative`}
      >
        <Suspense fallback={<div style={styles.routeFallback(palette)}>Opening Creative Studio...</div>}>
          <CreativeStudioSurface
            creativeStudioTab={creativeStudioTab}
            creativePrompt={creativePrompt}
            creativeStyle={creativeStyle}
            creativeCapabilities={creativeCapabilities}
            creativeLibrary={creativeLibrary}
            creativeJobs={creativeJobs}
            selectedCreativeJob={selectedCreativeJob}
            creativeStatus={creativeStatus}
            creativeLoading={creativeLoading}
            creativeAction={creativeAction}
            palette={palette}
            styles={styles}
            renderSurfaceHeader={renderSurfaceHeader}
            creativeKindForTab={creativeKindForTab}
            creativeProviderForTab={creativeProviderForTab}
            setCreativeStudioTab={setCreativeStudioTab}
            setCreativePrompt={setCreativePrompt}
            setCreativeStyle={setCreativeStyle}
            setCreativeProviderId={setCreativeProviderId}
            setSelectedCreativeJob={setSelectedCreativeJob}
            setCreativeStatus={setCreativeStatus}
            refreshCreativeStudio={refreshCreativeStudio}
            generateCreativeAsset={generateCreativeAsset}
            exportSelectedCreativeJob={exportSelectedCreativeJob}
            cancelSelectedCreativeJob={cancelSelectedCreativeJob}
          />
        </Suspense>
      </LazyPanelBoundary>
    );
  }

  function renderWorkspaceSurface() {
    if (activeSection === 'projects') return renderProjectsSurface();
    if (activeSection === 'intelligence') return renderProjectIntelligenceSurface();
    if (activeSection === 'workspace-intelligence') return renderWorkspaceIntelligenceSurface();
    if (activeSection === 'runtime') return renderDistributedRuntimeSurface();
    if (activeSection === 'adaptive') return renderAdaptiveIntelligenceSurface();
    if (activeSection === 'hardening') return renderProductizationRoute();
    if (activeSection === 'ecosystem') return renderEcosystemSurface();
    if (activeSection === 'autonomous') return renderAutonomousEngineeringSurface();
    if (activeSection === 'creative') return renderCreativeStudioRoute();
    if (activeSection === 'tasks') return renderTasksSurface();
    if (activeSection === 'agents') return renderAgentsSurface();
    return renderModelsSurface();
  }

  function renderSurfaceHeader(
    icon: ReactNode,
    title: string,
    subtitle: string,
    actions?: ReactNode
  ) {
    return (
      <div style={styles.surfaceHeader(palette)}>
        <div style={styles.surfaceTitleWrap}>
          <div style={styles.surfaceIcon(palette)}>{icon}</div>
          <div>
            <h2 style={styles.surfaceTitle(palette)}>{title}</h2>
            <p style={styles.surfaceSubtitle(palette)}>{subtitle}</p>
          </div>
        </div>
        {actions ? <div style={styles.surfaceActions}>{actions}</div> : null}
      </div>
    );
  }

  function detailPanelCollapsed(section: DetailPanelSection) {
    return collapsedDetailSections.includes(section);
  }

  function toggleDetailPanelSection(section: DetailPanelSection) {
    setCollapsedDetailSections((current) =>
      current.includes(section) ? current.filter((item) => item !== section) : [...current, section]
    );
  }

  function renderPanelCollapseButton(section: DetailPanelSection, label: string) {
    const collapsed = detailPanelCollapsed(section);
    return (
      <button
        type="button"
        style={styles.panelCollapseButton(palette, collapsed)}
        onClick={() => toggleDetailPanelSection(section)}
        aria-label={`${collapsed ? 'Expand' : 'Collapse'} ${label} panel`}
        title={`${collapsed ? 'Expand' : 'Collapse'} ${label}`}
      >
        <ChevronDown size={15} />
      </button>
    );
  }

  function renderProjectsSurface() {
    const dependency = workspaceProfile?.dependency_profile;
    const readiness = workspaceProfile?.readiness;

    return (
      <div style={styles.surfacePage}>
        {renderSurfaceHeader(
          <FolderOpen size={22} />,
          'Projects',
          `${productName} workspaces are persistent roots ${assistantIdentity} can inspect, edit, validate, and remember between sessions.`,
          <button type="button" style={styles.primaryButton(palette)} onClick={() => openSettings('workspace')}>
            <Settings size={16} />
            Workspace settings
          </button>
        )}

        <div style={styles.metricGrid}>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Current root</span>
            <strong style={styles.metricValue(palette)}>{workspaceRoot || 'workspace'}</strong>
          </div>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Files indexed</span>
            <strong style={styles.metricValue(palette)}>{files.length}</strong>
          </div>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Readiness</span>
            <strong style={styles.metricValue(palette)}>{readiness?.status || 'checking'}</strong>
          </div>
        </div>

        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>Current Workspace</h3>
            <div style={styles.tagWrap}>
              <button type="button" style={styles.secondaryButton(palette)} onClick={() => void refreshFiles()}>
                <FolderOpen size={16} />
                Refresh files
              </button>
              <button
                type="button"
                style={styles.secondaryButton(palette)}
                onClick={() => void validateNow()}
                disabled={loading || !workspaceRoot}
              >
                {loading ? <Loader2 size={16} className="spin" /> : <Play size={16} />}
                Validate
              </button>
              <button
                type="button"
                style={styles.secondaryButton(palette)}
                onClick={() => void setupCurrentWorkspace()}
                disabled={workspaceSetupLoading || !workspaceRoot}
              >
                {workspaceSetupLoading ? <Loader2 size={16} className="spin" /> : <Wrench size={16} />}
                Set up
              </button>
            </div>
          </div>

          <div style={styles.workspaceMeta(palette)}>
            <strong>Root</strong>
            <span>{workspaceRoot || 'workspace'}</span>
            <strong>Type</strong>
            <span>{dependency?.project_type || 'Unknown'}</span>
            <strong>Validation</strong>
            <span>{validationRecipe?.command || dependency?.validation_commands?.[0] || 'No recipe saved yet'}</span>
          </div>

          <div style={styles.tagWrap}>
            {(dependency?.languages ?? []).slice(0, 6).map((item) => (
              <span key={`project-lang-${item}`} style={styles.contextTag(palette)}>
                {item}
              </span>
            ))}
            {(dependency?.frameworks ?? []).slice(0, 6).map((item) => (
              <span key={`project-framework-${item}`} style={styles.contextTag(palette)}>
                {item}
              </span>
            ))}
          </div>

          {workspaceProfileStatus ? <div style={styles.inlineStatus(palette)}>{workspaceProfileStatus}</div> : null}
        </section>

        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>Project History</h3>
            <div style={styles.searchWrap(palette)}>
              <Search size={16} />
              <input
                value={projectSearch}
                onChange={(event) => setProjectSearch(event.target.value)}
                placeholder="Search projects or sessions"
                aria-label="Search projects or sessions"
                style={styles.searchInput(palette)}
              />
            </div>
          </div>
          <div style={styles.modelList}>
            {visibleProjectRoots.map((project) => (
              <div key={project.root} style={styles.compactCard(palette)}>
                <div style={styles.modelRowMain}>
                  <div style={styles.modelRowTop}>
                    <div style={styles.cardTitle(palette)}>{project.title}</div>
                    <div style={styles.tagWrap}>
                      {project.active ? <span style={styles.goodTag(palette)}>Current</span> : null}
                      <span style={styles.contextTag(palette)}>
                        {project.count} session{project.count === 1 ? '' : 's'}
                      </span>
                    </div>
                  </div>
                  <div style={styles.eventDetail(palette)}>{project.root}</div>
                  {project.latestThread ? (
                    <>
                      <div style={styles.previewMeta(palette)}>
                        Latest: {project.latestThread.preview}
                      </div>
                      <div style={styles.eventTime(palette)}>{formatDateTime(project.latestUpdatedAt)}</div>
                    </>
                  ) : (
                    <div style={styles.previewMeta(palette)}>No saved sessions for this root yet.</div>
                  )}
                </div>
                <div style={styles.rowActions}>
                  <button
                    type="button"
                    style={styles.iconTextButton(palette)}
                    onClick={() => void useProjectRoot(project.root)}
                    aria-label={`Open workspace ${project.title}`}
                  >
                    <FolderOpen size={14} />
                    Workspace
                  </button>
                  {project.latestThread ? (
                    <button
                      type="button"
                      style={styles.iconTextButton(palette)}
                      onClick={() => openProjectConversation(project.latestThread as SavedConversation)}
                      aria-label={`Open latest session for ${project.title}`}
                    >
                      <MessageSquarePlus size={14} />
                      Latest session
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
            {!visibleProjectRoots.length ? (
              <div style={styles.emptyPanel(palette)}>
                No projects or saved sessions matched that filter.
              </div>
            ) : null}
          </div>
        </section>
      </div>
    );
  }

  function renderProjectIntelligenceSurface() {
    const snapshot = projectIntelligence;
    const profile = snapshot?.profile;
    const architecture = snapshot?.architecture;

    return (
      <div style={styles.surfacePage}>
        {renderSurfaceHeader(
          <Brain size={22} />,
          'Project Intelligence',
          'Persistent project profile, architecture map, file importance, validation memory, and known project signals.',
          <div style={styles.tagWrap}>
            <button
              type="button"
              style={styles.primaryButton(palette)}
              onClick={() => void rebuildProjectIntelligence()}
              disabled={projectIntelligenceLoading || !workspaceRoot}
            >
              {projectIntelligenceLoading ? <Loader2 size={16} className="spin" /> : <Search size={16} />}
              Scan project
            </button>
            <button
              type="button"
              style={styles.secondaryButton(palette)}
              onClick={() => void rebuildProjectIntelligence({ rebuildMemory: true })}
              disabled={projectIntelligenceLoading || !workspaceRoot}
            >
              <Brain size={16} />
              Rebuild memory
            </button>
            <button
              type="button"
              style={styles.secondaryButton(palette)}
              onClick={() => void rebuildProjectIntelligence({ clearMemory: true, rebuildMemory: true })}
              disabled={projectIntelligenceLoading || !workspaceRoot}
            >
              <Trash2 size={16} />
              Clear/rebuild
            </button>
          </div>
        )}

        <div style={styles.metricGrid}>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Indexed files</span>
            <strong style={styles.metricValue(palette)}>{snapshot?.indexing.file_count ?? files.length}</strong>
          </div>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Important files</span>
            <strong style={styles.metricValue(palette)}>{snapshot?.file_importance.length ?? 0}</strong>
          </div>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>API routes</span>
            <strong style={styles.metricValue(palette)}>{architecture?.api_routes.length ?? 0}</strong>
          </div>
        </div>

        {projectIntelligenceStatus ? <div style={styles.inlineStatus(palette)}>{projectIntelligenceStatus}</div> : null}

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <h3 style={styles.settingsHeading(palette)}>Profile</h3>
            {snapshot ? (
              <>
                <div style={styles.workspaceMeta(palette)}>
                  <strong>Name</strong>
                  <span>{profile?.project_name || workspaceRoot}</span>
                  <strong>Root</strong>
                  <span>{profile?.root_path || snapshot.workspace_root}</span>
                  <strong>Last indexed</strong>
                  <span>{formatDateTime(profile?.last_indexed_at || snapshot.indexing.last_indexed_at)}</span>
                  <strong>Status</strong>
                  <span>{formatStatusLabel(snapshot.indexing.status)}</span>
                </div>
                <div style={styles.tagWrap}>
                  {(profile?.stack ?? []).slice(0, 12).map((item) => (
                    <span key={`pi-stack-${item}`} style={styles.contextTag(palette)}>
                      {item}
                    </span>
                  ))}
                  {(profile?.package_managers ?? []).slice(0, 4).map((item) => (
                    <span key={`pi-pm-${item}`} style={styles.contextTag(palette)}>
                      {item}
                    </span>
                  ))}
                </div>
                <div style={styles.sectionBlock}>
                  <div style={styles.sectionLabel(palette)}>Coding Conventions</div>
                  <div style={styles.eventList}>
                    {(profile?.coding_conventions ?? []).slice(0, 8).map((item) => (
                      <div key={item} style={styles.eventRow(palette, 'ok')}>
                        <div>
                          <strong style={styles.eventTitle(palette)}>Convention</strong>
                          <div style={styles.eventDetail(palette)}>{item}</div>
                        </div>
                      </div>
                    ))}
                    {!profile?.coding_conventions.length ? (
                      <div style={styles.emptyPanel(palette)}>No coding conventions inferred yet.</div>
                    ) : null}
                  </div>
                </div>
              </>
            ) : (
              <div style={styles.emptyPanel(palette)}>
                {projectIntelligenceStatus || 'Scan the project to build its persistent intelligence profile.'}
              </div>
            )}
          </section>

          <section style={styles.settingsSection(palette)}>
            <h3 style={styles.settingsHeading(palette)}>Architecture Map</h3>
            {architecture ? (
              <div style={styles.eventList}>
                {architecture.frontend_backend_split.slice(0, 4).map((item) => (
                  <div key={`split-${item}`} style={styles.eventRow(palette, 'ok')}>
                    <div>
                      <strong style={styles.eventTitle(palette)}>Split</strong>
                      <div style={styles.eventDetail(palette)}>{item}</div>
                    </div>
                  </div>
                ))}
                {architecture.major_modules.slice(0, 10).map((item) => (
                  <div key={`module-${item.path}-${item.kind}`} style={styles.eventRow(palette, 'ok')}>
                    <div>
                      <strong style={styles.eventTitle(palette)}>
                        {item.name} / {item.kind || 'module'}
                      </strong>
                      <div style={styles.eventDetail(palette)}>{item.summary || item.path}</div>
                    </div>
                    <span style={styles.eventTime(palette)}>{item.path}</span>
                  </div>
                ))}
                {architecture.api_routes.slice(0, 8).map((route) => (
                  <div key={`route-${route.method}-${route.path}-${route.file}`} style={styles.eventRow(palette, 'warning')}>
                    <div>
                      <strong style={styles.eventTitle(palette)}>
                        {route.method} {route.path}
                      </strong>
                      <div style={styles.eventDetail(palette)}>{route.file}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={styles.emptyPanel(palette)}>No architecture map has been generated yet.</div>
            )}
          </section>
        </div>

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <h3 style={styles.settingsHeading(palette)}>Important Files</h3>
            <div style={styles.eventList}>
              {(snapshot?.file_importance ?? []).slice(0, 12).map((item) => (
                <div key={`importance-${item.path}`} style={styles.eventRow(palette, 'ok')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{item.path}</strong>
                    <div style={styles.eventDetail(palette)}>{item.reasons.join(' / ') || 'Important project file'}</div>
                  </div>
                  <span style={styles.eventTime(palette)}>{item.score.toFixed(1)}</span>
                </div>
              ))}
              {!snapshot?.file_importance.length ? (
                <div style={styles.emptyPanel(palette)}>No file importance scores have been recorded yet.</div>
              ) : null}
            </div>
          </section>

          <section style={styles.settingsSection(palette)}>
            <h3 style={styles.settingsHeading(palette)}>Memory And Validation</h3>
            <div style={styles.sectionBlock}>
              <div style={styles.sectionLabel(palette)}>Validation Commands</div>
              <div style={styles.tagWrap}>
                {(snapshot?.validation_commands ?? []).slice(0, 10).map((item) => (
                  <span key={`pi-validation-${item}`} style={styles.contextTag(palette)}>
                    {item}
                  </span>
                ))}
                {!snapshot?.validation_commands.length ? (
                  <span style={styles.previewMeta(palette)}>No validation commands detected yet.</span>
                ) : null}
              </div>
            </div>
            <div style={styles.sectionBlock}>
              <div style={styles.sectionLabel(palette)}>Recent Failures</div>
              <div style={styles.eventList}>
                {(snapshot?.recent_failures ?? []).slice(0, 5).map((item) => (
                  <div key={`pi-failure-${item.id}`} style={styles.eventRow(palette, 'error')}>
                    <div>
                      <strong style={styles.eventTitle(palette)}>{item.title || item.message}</strong>
                      <div style={styles.eventDetail(palette)}>{item.error_summary || item.final_summary || item.message}</div>
                    </div>
                    <span style={styles.eventTime(palette)}>{formatDateTime(item.updated_at || item.created_at)}</span>
                  </div>
                ))}
                {!snapshot?.recent_failures.length ? (
                  <div style={styles.emptyPanel(palette)}>No recent project failures are tracked.</div>
                ) : null}
              </div>
            </div>
            <div style={styles.sectionBlock}>
              <div style={styles.sectionLabel(palette)}>Known TODOs</div>
              <div style={styles.eventList}>
                {(snapshot?.known_todos ?? []).slice(0, 6).map((item) => (
                  <div key={`pi-todo-${item}`} style={styles.eventRow(palette, 'warning')}>
                    <div>
                      <strong style={styles.eventTitle(palette)}>TODO</strong>
                      <div style={styles.eventDetail(palette)}>{item}</div>
                    </div>
                  </div>
                ))}
                {!snapshot?.known_todos.length ? <div style={styles.emptyPanel(palette)}>No TODOs found in the indexed files.</div> : null}
              </div>
            </div>
          </section>
        </div>
      </div>
    );
  }

  function renderWorkspaceIntelligenceSurface() {
    const snapshot = workspaceOperations;
    const health = snapshot?.health;
    const watcher = snapshot?.watcher;
    const git = snapshot?.git;
    const activeRecommendations = (snapshot?.recommendations ?? []).filter((item) => item.status === 'active');
    const architectureMetric = health?.metrics.find((item) => item.name === 'Architecture drift');
    const validationMetric = health?.metrics.find((item) => item.name === 'Validation instability');
    const dependencyMetric = health?.metrics.find((item) => item.name === 'Dependency freshness');
    const activeTaskCount = taskBoardTasks.filter((item) => !terminalTaskStatuses.has(item.status)).length;
    const completedTaskCount = taskBoardTasks.filter((item) => item.status === 'completed').length;
    const failedTaskCount = taskBoardTasks.filter((item) => item.status === 'failed' || item.status === 'canceled').length;

    return (
      <div style={styles.surfacePage}>
        {renderSurfaceHeader(
          <Zap size={22} />,
          'Workspace Intelligence',
          'Permission-aware watcher, health analysis, recommendations, scheduled intelligence, git signals, and long-term project memory.',
          <div style={styles.tagWrap}>
            <button
              type="button"
              style={styles.primaryButton(palette)}
              onClick={() => void scanWorkspaceOperations()}
              disabled={workspaceOperationsLoading || !workspaceRoot}
            >
              {workspaceOperationsLoading ? <Loader2 size={16} className="spin" /> : <Search size={16} />}
              Scan workspace
            </button>
            <button
              type="button"
              style={styles.secondaryButton(palette)}
              onClick={() => void runWorkspaceOperationsJobs()}
              disabled={Boolean(workspaceOperationsActionId) || !workspaceRoot}
            >
              {workspaceOperationsActionId === 'job:all' ? <Loader2 size={16} className="spin" /> : <Play size={16} />}
              Run safe jobs
            </button>
          </div>
        )}

        <div style={styles.metricGrid}>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Health score</span>
            <strong style={styles.metricValue(palette)}>
              {health ? `${health.score}/100` : 'No scan'}
            </strong>
          </div>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Recommendations</span>
            <strong style={styles.metricValue(palette)}>{activeRecommendations.length}</strong>
          </div>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Workspace events</span>
            <strong style={styles.metricValue(palette)}>{snapshot?.recent_events.length ?? 0}</strong>
          </div>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Git changes</span>
            <strong style={styles.metricValue(palette)}>{git?.changed_files.length ?? 0}</strong>
          </div>
        </div>

        {workspaceOperationsStatus ? <div style={styles.inlineStatus(palette)}>{workspaceOperationsStatus}</div> : null}

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Project Health</h3>
              <span style={styles.diagnosticChip(palette, healthStatusToEventStatus(health?.status ?? 'unknown'))}>
                {formatStatusLabel(health?.status ?? 'unknown')}
              </span>
            </div>

            <div style={styles.eventList}>
              {(health?.metrics ?? []).map((metric) => (
                <div key={`workspace-health-${metric.name}`} style={styles.eventRow(palette, healthStatusToEventStatus(metric.status))}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{metric.name}</strong>
                    <div style={styles.eventDetail(palette)}>{metric.summary}</div>
                    {metric.evidence.length || metric.related_files.length ? (
                      <div style={{ ...styles.tagWrap, marginTop: 10 }}>
                        {metric.evidence.slice(0, 3).map((item) => (
                          <span key={`${metric.name}-evidence-${item}`} style={styles.contextTag(palette)}>
                            {item}
                          </span>
                        ))}
                        {metric.related_files.slice(0, 4).map((item) => (
                          <span key={`${metric.name}-file-${item}`} style={styles.contextTag(palette)}>
                            {item}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  <span style={styles.eventTime(palette)}>{metric.score}/100</span>
                </div>
              ))}
              {!health?.metrics.length ? (
                <div style={styles.emptyPanel(palette)}>No workspace health scan has been recorded yet.</div>
              ) : null}
            </div>
          </section>

          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Active Recommendations</h3>
              <span style={styles.contextTag(palette)}>{activeRecommendations.length} active</span>
            </div>

            <div style={styles.eventList}>
              {activeRecommendations.slice(0, 10).map((recommendation) => {
                const fixing = workspaceOperationsActionId === `fix:${recommendation.id}`;
                const dismissing = workspaceOperationsActionId === `dismiss:${recommendation.id}`;

                return (
                  <div
                    key={`workspace-rec-${recommendation.id}`}
                    style={styles.eventRow(palette, severityToEventStatus(recommendation.severity))}
                  >
                    <div>
                      <strong style={styles.eventTitle(palette)}>{recommendation.title}</strong>
                      <div style={styles.eventDetail(palette)}>{recommendation.detail || recommendation.rationale}</div>
                      <div style={{ ...styles.tagWrap, marginTop: 10 }}>
                        <span style={styles.contextTag(palette)}>{formatStatusLabel(recommendation.severity)}</span>
                        {recommendation.category ? (
                          <span style={styles.contextTag(palette)}>{recommendation.category}</span>
                        ) : null}
                        {recommendation.related_files.slice(0, 4).map((item) => (
                          <span key={`${recommendation.id}-file-${item}`} style={styles.contextTag(palette)}>
                            {item}
                          </span>
                        ))}
                        {recommendation.fix_task_id ? (
                          <span style={styles.goodTag(palette)}>Task {recommendation.fix_task_id}</span>
                        ) : null}
                      </div>
                    </div>
                    <div style={styles.eventActions}>
                      <button
                        type="button"
                        style={styles.secondaryButton(palette)}
                        onClick={() => void fixWorkspaceOperationRecommendation(recommendation)}
                        disabled={Boolean(workspaceOperationsActionId)}
                      >
                        {fixing ? <Loader2 size={16} className="spin" /> : <Play size={16} />}
                        Fix now
                      </button>
                      <button
                        type="button"
                        style={styles.secondaryButton(palette)}
                        onClick={() => void dismissWorkspaceOperationRecommendation(recommendation)}
                        disabled={Boolean(workspaceOperationsActionId)}
                      >
                        {dismissing ? <Loader2 size={16} className="spin" /> : <X size={16} />}
                        Dismiss
                      </button>
                    </div>
                  </div>
                );
              })}
              {!activeRecommendations.length ? (
                <div style={styles.emptyPanel(palette)}>No active recommendations are waiting on this workspace.</div>
              ) : null}
            </div>
          </section>
        </div>

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <h3 style={styles.settingsHeading(palette)}>Workspace Watcher</h3>
            <div style={styles.workspaceMeta(palette)}>
              <strong>Last scan</strong>
              <span>{watcher?.scanned_at ? formatDateTime(watcher.scanned_at) : 'Not scanned'}</span>
              <strong>Files tracked</strong>
              <span>{watcher?.file_count ?? 0}</span>
              <strong>Dependency fingerprint</strong>
              <span>{watcher?.dependency_fingerprint ? watcher.dependency_fingerprint.slice(0, 12) : 'none'}</span>
              <strong>Validation drift</strong>
              <span>{watcher?.validation_drift.length ?? 0}</span>
            </div>
            <div style={styles.sectionBlock}>
              <div style={styles.sectionLabel(palette)}>Recent Workspace Events</div>
              <div style={styles.eventList}>
                {(snapshot?.recent_events ?? []).slice(0, 8).map((event) => (
                  <div key={`workspace-event-${event.id}`} style={styles.eventRow(palette, severityToEventStatus(event.severity))}>
                    <div>
                      <strong style={styles.eventTitle(palette)}>{event.title}</strong>
                      <div style={styles.eventDetail(palette)}>{event.detail || event.path || event.kind}</div>
                    </div>
                    <span style={styles.eventTime(palette)}>{formatEventTime(event.created_at)}</span>
                  </div>
                ))}
                {!snapshot?.recent_events.length ? (
                  <div style={styles.emptyPanel(palette)}>No watcher events have been recorded since the last baseline.</div>
                ) : null}
              </div>
            </div>
          </section>

          <section style={styles.settingsSection(palette)}>
            <h3 style={styles.settingsHeading(palette)}>Git Intelligence</h3>
            <div style={styles.workspaceMeta(palette)}>
              <strong>Repository</strong>
              <span>{git?.is_repository ? 'Detected' : 'Not detected'}</span>
              <strong>Branch</strong>
              <span>{git?.branch || 'none'}</span>
              <strong>Upstream</strong>
              <span>{git?.upstream || 'none'}</span>
              <strong>Branches</strong>
              <span>{git?.branch_count ?? 0}</span>
            </div>
            <div style={styles.sectionBlock}>
              <div style={styles.sectionLabel(palette)}>Risky Diffs And Heatmap</div>
              <div style={styles.eventList}>
                {(git?.risky_diffs.length ? git.risky_diffs : git?.change_heatmap ?? []).slice(0, 8).map((item) => (
                  <div key={`git-diff-${item.path}-${item.status}`} style={styles.eventRow(palette, 'warning')}>
                    <div>
                      <strong style={styles.eventTitle(palette)}>{item.path}</strong>
                      <div style={styles.eventDetail(palette)}>
                        {item.status || 'changed'} / +{item.additions} / -{item.deletions}
                      </div>
                    </div>
                  </div>
                ))}
                {!git?.risky_diffs.length && !git?.change_heatmap.length ? (
                  <div style={styles.emptyPanel(palette)}>{git?.summary || 'No git changes are currently tracked.'}</div>
                ) : null}
              </div>
            </div>
            <div style={styles.sectionBlock}>
              <div style={styles.sectionLabel(palette)}>Recent Commits</div>
              <div style={styles.eventList}>
                {(git?.recent_commits ?? []).slice(0, 5).map((commit) => (
                  <div key={`git-commit-${commit.sha}`} style={styles.eventRow(palette, 'ok')}>
                    <div>
                      <strong style={styles.eventTitle(palette)}>{commit.subject}</strong>
                      <div style={styles.eventDetail(palette)}>
                        {commit.sha} / {commit.author}
                      </div>
                    </div>
                    <span style={styles.eventTime(palette)}>{formatDateTime(commit.created_at)}</span>
                  </div>
                ))}
                {!git?.recent_commits.length ? (
                  <div style={styles.emptyPanel(palette)}>No recent commits are available for this workspace.</div>
                ) : null}
              </div>
            </div>
          </section>
        </div>

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Scheduled Intelligence Jobs</h3>
              <span style={styles.contextTag(palette)}>{snapshot?.scheduled_jobs.length ?? 0} jobs</span>
            </div>
            <div style={styles.eventList}>
              {(snapshot?.scheduled_jobs ?? []).map((job) => {
                const running = workspaceOperationsActionId === `job:${job.id}`;
                return (
                  <div key={`workspace-job-${job.id}`} style={styles.eventRow(palette, healthStatusToEventStatus(job.status))}>
                    <div>
                      <strong style={styles.eventTitle(palette)}>{job.name}</strong>
                      <div style={styles.eventDetail(palette)}>{job.summary || job.next_run_hint || job.schedule_label}</div>
                      <div style={{ ...styles.tagWrap, marginTop: 10 }}>
                        <span style={styles.contextTag(palette)}>{job.kind}</span>
                        <span style={styles.contextTag(palette)}>{job.schedule_label}</span>
                        <span style={styles.contextTag(palette)}>{formatStatusLabel(job.status)}</span>
                        {job.safe_by_default ? <span style={styles.goodTag(palette)}>Safe</span> : null}
                      </div>
                    </div>
                    <div style={styles.eventActions}>
                      <span style={styles.eventTime(palette)}>
                        {job.last_run_at ? formatDateTime(job.last_run_at) : 'Not run'}
                      </span>
                      <button
                        type="button"
                        style={styles.secondaryButton(palette)}
                        onClick={() => void runWorkspaceOperationsJobs(job.id)}
                        disabled={Boolean(workspaceOperationsActionId) || !workspaceRoot}
                      >
                        {running ? <Loader2 size={16} className="spin" /> : <Play size={16} />}
                        Run
                      </button>
                    </div>
                  </div>
                );
              })}
              {!snapshot?.scheduled_jobs.length ? (
                <div style={styles.emptyPanel(palette)}>No scheduled intelligence jobs have been loaded yet.</div>
              ) : null}
            </div>
          </section>

          <section style={styles.settingsSection(palette)}>
            <h3 style={styles.settingsHeading(palette)}>Trends And Memory</h3>
            <div style={styles.metricGrid}>
              <div style={styles.metricCard(palette)}>
                <span style={styles.metricLabel(palette)}>Active tasks</span>
                <strong style={styles.metricValue(palette)}>{activeTaskCount}</strong>
              </div>
              <div style={styles.metricCard(palette)}>
                <span style={styles.metricLabel(palette)}>Completed</span>
                <strong style={styles.metricValue(palette)}>{completedTaskCount}</strong>
              </div>
              <div style={styles.metricCard(palette)}>
                <span style={styles.metricLabel(palette)}>Failed</span>
                <strong style={styles.metricValue(palette)}>{failedTaskCount}</strong>
              </div>
            </div>
            <div style={styles.sectionBlock}>
              <div style={styles.sectionLabel(palette)}>Focused Signals</div>
              <div style={styles.eventList}>
                {[architectureMetric, validationMetric, dependencyMetric]
                  .filter(Boolean)
                  .map((metric) => (
                    <div key={`workspace-focus-${metric!.name}`} style={styles.eventRow(palette, healthStatusToEventStatus(metric!.status))}>
                      <div>
                        <strong style={styles.eventTitle(palette)}>{metric!.name}</strong>
                        <div style={styles.eventDetail(palette)}>{metric!.summary}</div>
                      </div>
                      <span style={styles.eventTime(palette)}>{metric!.score}/100</span>
                    </div>
                  ))}
                {!architectureMetric && !validationMetric && !dependencyMetric ? (
                  <div style={styles.emptyPanel(palette)}>No focused health signals have been generated yet.</div>
                ) : null}
              </div>
            </div>
            <div style={styles.sectionBlock}>
              <div style={styles.sectionLabel(palette)}>Long-Term Project Memory</div>
              <div style={styles.eventList}>
                {(snapshot?.long_term_memory ?? []).slice(0, 8).map((item) => (
                  <div key={`workspace-memory-${item}`} style={styles.eventRow(palette, 'ok')}>
                    <div>
                      <strong style={styles.eventTitle(palette)}>Memory</strong>
                      <div style={styles.eventDetail(palette)}>{item}</div>
                    </div>
                  </div>
                ))}
                {!snapshot?.long_term_memory.length ? (
                  <div style={styles.emptyPanel(palette)}>No long-term workspace memory signals have been summarized yet.</div>
                ) : null}
              </div>
            </div>
          </section>
        </div>
      </div>
    );
  }

  function renderTasksSurface() {
    const relatedFiles = Array.from(
      new Set([...(selectedTask?.related_files ?? []), ...(taskArtifacts?.related_files ?? [])])
    );
    const validationCommands = Array.from(
      new Set([...(selectedTask?.validation_commands ?? []), ...(taskArtifacts?.validation_commands ?? [])])
    );
    const checkpointIds = Array.from(
      new Set([...(selectedTask?.checkpoints ?? []), ...(taskArtifacts?.checkpoints ?? [])])
    );
    const selectedTaskTerminal = selectedTask ? terminalTaskStatuses.has(selectedTask.status) : true;

    return (
      <div style={styles.surfacePage}>
        {renderSurfaceHeader(
          <CheckCircle2 size={22} />,
          'Tasks',
          'Tracked coding work with state, subtasks, validation, approvals, checkpoints, and repair history.',
          <button type="button" style={styles.primaryButton(palette)} onClick={() => void refreshTasks()}>
            <Zap size={16} />
            Refresh tasks
          </button>
        )}

        <Suspense fallback={<div style={styles.emptyPanel(palette)}>Loading task summary...</div>}>
          <TaskStatusSummary
            tasks={taskBoardTasks}
            style={styles.metricGrid}
            renderMetric={(metric) => (
              <div style={styles.metricCard(palette)}>
                <span style={styles.metricLabel(palette)}>{metric.label}</span>
                <strong style={styles.metricValue(palette)}>{metric.value}</strong>
              </div>
            )}
          />
        </Suspense>

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Task Graph</h3>
              <div style={styles.segmentedControl(palette)} role="group" aria-label="Filter task list">
                {taskFilterOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    style={styles.segmentedButton(palette, taskStatusFilter === option.value)}
                    onClick={() => setTaskStatusFilter(option.value)}
                    aria-pressed={taskStatusFilter === option.value}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            <div style={styles.modelList}>
              {filteredTaskBoardTasks.map((item) => {
                const active = selectedTask?.id === item.id;
                const title = item.title || item.message || item.id;
                const isSubtask = Boolean(item.parent_task_id);

                return (
                  <button
                    key={item.id}
                    type="button"
                    style={styles.taskListItem(palette, active)}
                    onClick={() => setSelectedTaskId(item.id)}
                    aria-pressed={active}
                  >
                    <div style={styles.modelRowMain}>
                      <div style={styles.modelRowTop}>
                        <div style={styles.cardTitle(palette)}>{title}</div>
                        <span style={styles.contextTag(palette)}>{formatStatusLabel(item.status)}</span>
                      </div>
                      <div style={styles.eventDetail(palette)}>{item.user_goal || item.message}</div>
                      <div style={styles.tagWrap}>
                        {isSubtask ? <span style={styles.contextTag(palette)}>Subtask</span> : null}
                        {item.assigned_agent_role ? (
                          <span style={styles.contextTag(palette)}>{item.assigned_agent_role}</span>
                        ) : null}
                        {item.related_files.length ? (
                          <span style={styles.contextTag(palette)}>{item.related_files.length} file(s)</span>
                        ) : null}
                        {item.checkpoints.length ? (
                          <span style={styles.contextTag(palette)}>{item.checkpoints.length} checkpoint(s)</span>
                        ) : null}
                      </div>
                    </div>
                    <span style={styles.eventTime(palette)}>{formatDateTime(item.updated_at || item.created_at)}</span>
                  </button>
                );
              })}
              {!filteredTaskBoardTasks.length ? (
                <div style={styles.emptyPanel(palette)}>
                  {taskStatusMessage || 'No tasks match this filter yet.'}
                </div>
              ) : null}
            </div>
          </section>

          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Selected Task</h3>
              <div style={styles.tagWrap}>
                <button
                  type="button"
                  style={styles.secondaryButton(palette)}
                  onClick={() => void runTaskAction('approve')}
                  disabled={!selectedTask || selectedTask.status !== 'needs_approval' || Boolean(taskActionId)}
                >
                  {taskActionId === `approve:${selectedTask?.id}` ? (
                    <Loader2 size={16} className="spin" />
                  ) : (
                    <CheckCircle2 size={16} />
                  )}
                  Approve
                </button>
                <button
                  type="button"
                  style={styles.secondaryButton(palette)}
                  onClick={() => void runTaskAction('retry')}
                  disabled={!selectedTask || !['failed', 'canceled'].includes(selectedTask.status) || Boolean(taskActionId)}
                >
                  {taskActionId === `retry:${selectedTask?.id}` ? <Loader2 size={16} className="spin" /> : <Play size={16} />}
                  Retry
                </button>
                <button
                  type="button"
                  style={styles.secondaryButton(palette)}
                  onClick={() => void runTaskAction('cancel')}
                  disabled={!selectedTask || selectedTaskTerminal || Boolean(taskActionId)}
                >
                  {taskActionId === `cancel:${selectedTask?.id}` ? (
                    <Loader2 size={16} className="spin" />
                  ) : (
                    <Square size={16} />
                  )}
                  Cancel
                </button>
              </div>
            </div>

            {selectedTask ? (
              <div style={styles.sectionBlock}>
                <div style={styles.modelRowTop}>
                  <div>
                    <div style={styles.cardTitle(palette)}>{selectedTask.title || selectedTask.message}</div>
                    <div style={styles.eventDetail(palette)}>{selectedTask.user_goal || selectedTask.message}</div>
                  </div>
                  <span style={styles.diagnosticChip(palette, taskStatusToEventStatus(selectedTask.status))}>
                    {formatStatusLabel(selectedTask.status)}
                  </span>
                </div>

                <div style={styles.workspaceMeta(palette)}>
                  <strong>Task ID</strong>
                  <span>{selectedTask.id}</span>
                  <strong>Project</strong>
                  <span>{selectedTask.project_id || selectedTask.workspace_root}</span>
                  <strong>Priority</strong>
                  <span>{selectedTask.priority}</span>
                  <strong>Created</strong>
                  <span>{formatDateTime(selectedTask.created_at)}</span>
                  <strong>Updated</strong>
                  <span>{formatDateTime(selectedTask.updated_at || selectedTask.created_at)}</span>
                  <strong>Completed</strong>
                  <span>{selectedTask.completed_at ? formatDateTime(selectedTask.completed_at) : 'Not completed'}</span>
                </div>

                {selectedTask.error_summary ? (
                  <div style={styles.eventRow(palette, 'error')}>
                    <div>
                      <strong style={styles.eventTitle(palette)}>Error Summary</strong>
                      <div style={styles.eventDetail(palette)}>{selectedTask.error_summary}</div>
                    </div>
                  </div>
                ) : null}

                {selectedTask.final_summary ? (
                  <div style={styles.eventRow(palette, 'ok')}>
                    <div>
                      <strong style={styles.eventTitle(palette)}>Final Summary</strong>
                      <div style={styles.eventDetail(palette)}>{selectedTask.final_summary}</div>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <div style={styles.emptyPanel(palette)}>Select a task to inspect its timeline and artifacts.</div>
            )}

            {selectedTask ? (
              <div style={styles.sectionBlock}>
                <div style={styles.sectionLabel(palette)}>Artifacts</div>
                <div style={styles.tagWrap}>
                  {relatedFiles.map((item) => (
                    <span key={`task-file-${item}`} style={styles.contextTag(palette)}>
                      {item}
                    </span>
                  ))}
                  {validationCommands.map((item) => (
                    <span key={`task-command-${item}`} style={styles.contextTag(palette)}>
                      {item}
                    </span>
                  ))}
                  {checkpointIds.map((item) => (
                    <span key={`task-checkpoint-${item}`} style={styles.goodTag(palette)}>
                      {item}
                    </span>
                  ))}
                  {!relatedFiles.length && !validationCommands.length && !checkpointIds.length ? (
                    <span style={styles.previewMeta(palette)}>No task artifacts recorded yet.</span>
                  ) : null}
                </div>
              </div>
            ) : null}

            {selectedTask ? (
              <div style={styles.sectionBlock}>
                <div style={styles.sectionLabel(palette)}>Timeline</div>
                <div style={styles.eventList}>
                  {taskTimeline.map((item, index) => (
                    <div key={`${item.kind}-${item.created_at}-${index}`} style={styles.eventRow(palette, item.status)}>
                      <div>
                        <strong style={styles.eventTitle(palette)}>{item.title}</strong>
                        <div style={styles.eventDetail(palette)}>{item.detail}</div>
                      </div>
                      <span style={styles.eventTime(palette)}>{formatEventTime(item.created_at)}</span>
                    </div>
                  ))}
                  {!taskTimeline.length ? (
                    <div style={styles.emptyPanel(palette)}>
                      {taskStatusMessage || 'No timeline events recorded for this task yet.'}
                    </div>
                  ) : null}
                </div>
              </div>
            ) : null}

            {selectedTask && taskArtifacts?.repair_attempts.length ? (
              <div style={styles.sectionBlock}>
                <div style={styles.sectionLabel(palette)}>Repair Attempts</div>
                <div style={styles.eventList}>
                  {taskArtifacts.repair_attempts.map((item) => (
                    <div
                      key={`${item.attempt}-${item.created_at}`}
                      style={styles.eventRow(
                        palette,
                        item.outcome === 'fixed' || item.outcome === 'improved' ? 'ok' : 'warning'
                      )}
                    >
                      <div>
                        <strong style={styles.eventTitle(palette)}>
                          Attempt {item.attempt} / {item.outcome}
                        </strong>
                        <div style={styles.eventDetail(palette)}>{item.summary || item.before_signature}</div>
                      </div>
                      <span style={styles.eventTime(palette)}>{formatDateTime(item.created_at)}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </section>
        </div>
      </div>
    );
  }

  function adaptiveScoreLabel(value: number) {
    if (!Number.isFinite(value)) return '0%';
    return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`;
  }

  function adaptiveScoreStatus(value: number): ToolEvent['status'] {
    if (value < 0.45) return 'error';
    if (value < 0.68) return 'warning';
    return 'ok';
  }

  function renderAdaptiveInsightList(title: string, insights: AdaptiveInsight[]) {
    return (
      <section style={styles.settingsSection(palette)}>
        <div style={styles.sectionHeaderInline}>
          <h3 style={styles.settingsHeading(palette)}>{title}</h3>
          <span style={styles.contextTag(palette)}>{insights.length} signal(s)</span>
        </div>
        <div style={styles.eventList}>
          {insights.slice(0, 6).map((insight) => (
            <div
              key={insight.id || `${insight.category}-${insight.key}`}
              style={styles.eventRow(
                palette,
                insight.severity === 'high' ? 'error' : insight.severity === 'medium' ? 'warning' : 'ok'
              )}
            >
              <div>
                <strong style={styles.eventTitle(palette)}>{insight.title}</strong>
                <div style={styles.eventDetail(palette)}>{insight.detail}</div>
                {insight.recommendations[0] ? (
                  <div style={styles.previewMeta(palette)}>{insight.recommendations[0]}</div>
                ) : null}
              </div>
              <span style={styles.eventTime(palette)}>{adaptiveScoreLabel(insight.score)}</span>
            </div>
          ))}
          {!insights.length ? <div style={styles.emptyPanel(palette)}>No adaptive insight has been recorded yet.</div> : null}
        </div>
      </section>
    );
  }

  function renderAdaptiveQualityScore(score: AdaptiveQualityScore) {
    return (
      <div key={score.dimension} style={styles.eventRow(palette, adaptiveScoreStatus(score.score))}>
        <div>
          <strong style={styles.eventTitle(palette)}>{score.label}</strong>
          <div style={styles.eventDetail(palette)}>{score.reasons[0] || `${score.sample_size} sample(s).`}</div>
          {score.recommendations[0] ? <div style={styles.previewMeta(palette)}>{score.recommendations[0]}</div> : null}
        </div>
        <div style={styles.rowActions}>
          <span style={styles.contextTag(palette)}>{formatStatusLabel(score.trend)}</span>
          <strong style={styles.eventTime(palette)}>{adaptiveScoreLabel(score.score)}</strong>
        </div>
      </div>
    );
  }

  function renderAdaptiveRoute(route: AdaptiveRouteRecommendation) {
    return (
      <div key={`${route.provider_id}-${route.model}-${route.role}`} style={styles.modelRow(palette, route.action === 'prefer')}>
        <div style={styles.modelRowMain}>
          <div style={styles.modelRowTop}>
            <div style={styles.cardTitle(palette)}>{route.provider_label || route.provider_id || route.model}</div>
            <span style={styles.diagnosticChip(palette, adaptiveScoreStatus(route.score))}>{formatStatusLabel(route.action)}</span>
          </div>
          <div style={styles.eventDetail(palette)}>{route.reasons[0] || 'No route reasoning recorded.'}</div>
          <div style={styles.tagWrap}>
            {route.model ? <span style={styles.contextTag(palette)}>{route.model}</span> : null}
            <span style={styles.contextTag(palette)}>{adaptiveScoreLabel(route.score)} score</span>
            <span style={styles.contextTag(palette)}>{adaptiveScoreLabel(route.confidence)} confidence</span>
            {route.risks[0] ? <span style={styles.contextTag(palette)}>{route.risks[0]}</span> : null}
          </div>
        </div>
      </div>
    );
  }

  function renderAdaptiveIntelligenceSurface() {
    const snapshot = adaptiveIntelligence;
    const activeProfile = snapshot?.active_profile;
    const outcomes = snapshot?.outcomes ?? [];
    const qualityScores = snapshot?.quality_scores ?? [];
    const routes = snapshot?.route_recommendations ?? [];
    const terminalOutcomes = outcomes.filter((item) => ['success', 'failed', 'rolled_back', 'canceled'].includes(item.outcome));
    const successCount = terminalOutcomes.filter((item) => item.success).length;
    const regressionReports = snapshot?.benchmark_reports.filter((item) => item.regression_detected).length ?? 0;
    const replayRegressions = snapshot?.replay_results.filter((item) => item.regression_detected).length ?? 0;
    const metrics = [
      { label: 'Task Success', value: adaptiveScoreLabel(successCount / Math.max(1, terminalOutcomes.length)) },
      { label: 'Outcomes', value: outcomes.length },
      { label: 'Routes', value: routes.length },
      { label: 'Regressions', value: regressionReports + replayRegressions }
    ];

    return (
      <div style={styles.surfacePage}>
        {renderSurfaceHeader(
          <Brain size={22} />,
          'Adaptive',
          'Outcome tracking, routing quality, repair learning, context efficiency, feedback, replay, and benchmark reports.',
          <div style={styles.surfaceActions}>
            <button
              type="button"
              style={styles.secondaryButton(palette)}
              onClick={() => void refreshAdaptiveSignals(undefined, true)}
              disabled={adaptiveIntelligenceLoading}
            >
              {adaptiveIntelligenceLoading ? <Loader2 size={16} className="spin" /> : <Zap size={16} />}
              Refresh
            </button>
            <button
              type="button"
              style={styles.secondaryButton(palette)}
              onClick={() => void replayAdaptiveOutcomeWindow()}
              disabled={!workspaceRoot.trim() || Boolean(adaptiveIntelligenceAction)}
            >
              {adaptiveIntelligenceAction === 'replay' ? <Loader2 size={16} className="spin" /> : <Play size={16} />}
              Replay
            </button>
            <button
              type="button"
              style={styles.primaryButton(palette)}
              onClick={() => void runAdaptiveBenchmarkSweep()}
              disabled={!workspaceRoot.trim() || Boolean(adaptiveIntelligenceAction)}
            >
              {adaptiveIntelligenceAction === 'benchmark' ? <Loader2 size={16} className="spin" /> : <CheckCircle2 size={16} />}
              Benchmark
            </button>
          </div>
        )}

        <div style={styles.metricGrid}>
          {metrics.map((metric) => (
            <div key={metric.label} style={styles.metricCard(palette)}>
              <span style={styles.metricLabel(palette)}>{metric.label}</span>
              <strong style={styles.metricValue(palette)}>{metric.value}</strong>
            </div>
          ))}
        </div>

        {adaptiveIntelligenceStatus ? (
          <div style={styles.eventRow(palette, adaptiveIntelligenceStatus.includes('Could not') ? 'error' : 'ok')}>
            <div>
              <strong style={styles.eventTitle(palette)}>Adaptive Status</strong>
              <div style={styles.eventDetail(palette)}>{adaptiveIntelligenceStatus}</div>
            </div>
          </div>
        ) : null}

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Policy Profiles</h3>
              {activeProfile ? <span style={styles.goodTag(palette)}>{activeProfile.name}</span> : null}
            </div>
            <div style={styles.modelList}>
              {(snapshot?.profiles ?? []).map((profile) => (
                <div key={profile.id} style={styles.modelRow(palette, profile.active)}>
                  <div style={styles.modelRowMain}>
                    <div style={styles.modelRowTop}>
                      <div style={styles.cardTitle(palette)}>{profile.name}</div>
                      {profile.active ? <span style={styles.goodTag(palette)}>Active</span> : null}
                    </div>
                    <div style={styles.eventDetail(palette)}>{profile.description}</div>
                    <div style={styles.tagWrap}>
                      <span style={styles.contextTag(palette)}>{profile.routing_strategy}</span>
                      <span style={styles.contextTag(palette)}>{profile.privacy_mode}</span>
                      <span style={styles.contextTag(palette)}>{profile.allow_cloud ? 'cloud allowed' : 'local first'}</span>
                      {profile.review_required ? <span style={styles.contextTag(palette)}>review required</span> : null}
                    </div>
                  </div>
                  <button
                    type="button"
                    style={styles.iconTextButton(palette)}
                    onClick={() => void activateAdaptiveProfile(profile.id)}
                    disabled={profile.active || Boolean(adaptiveIntelligenceAction)}
                  >
                    <CheckCircle2 size={14} />
                    Activate
                  </button>
                </div>
              ))}
              {!snapshot?.profiles.length ? <div style={styles.emptyPanel(palette)}>Adaptive policy profiles will appear after refresh.</div> : null}
            </div>
            <button
              type="button"
              style={styles.secondaryButton(palette)}
              onClick={() => void rollbackLatestAdaptivePolicy()}
              disabled={!snapshot?.policy_checkpoints.length || Boolean(adaptiveIntelligenceAction)}
            >
              <ArrowDown size={16} />
              Roll back profile
            </button>
          </section>

          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Quality Scores</h3>
              <span style={styles.contextTag(palette)}>{qualityScores.length} score(s)</span>
            </div>
            <div style={styles.eventList}>
              {qualityScores.map(renderAdaptiveQualityScore)}
              {!qualityScores.length ? <div style={styles.emptyPanel(palette)}>No adaptive quality scores recorded yet.</div> : null}
            </div>
          </section>
        </div>

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Routing Analytics</h3>
              <span style={styles.contextTag(palette)}>{routes.length} route(s)</span>
            </div>
            <div style={styles.modelList}>
              {routes.slice(0, 8).map(renderAdaptiveRoute)}
              {!routes.length ? <div style={styles.emptyPanel(palette)}>No route recommendation has enough signal yet.</div> : null}
            </div>
          </section>

          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Recent Outcomes</h3>
              <span style={styles.contextTag(palette)}>{outcomes.length} tracked</span>
            </div>
            <div style={styles.eventList}>
              {outcomes.slice(0, 8).map((outcome) => (
                <div key={outcome.task_id} style={styles.eventRow(palette, outcome.success ? 'ok' : outcome.outcome === 'unknown' ? 'warning' : 'error')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{outcome.title || outcome.task_id}</strong>
                    <div style={styles.eventDetail(palette)}>
                      {formatStatusLabel(outcome.outcome)} / {outcome.validation_passes}/{outcome.validation_runs} validation pass(es)
                    </div>
                  </div>
                  <span style={styles.eventTime(palette)}>{formatDateTime(outcome.updated_at || outcome.created_at)}</span>
                </div>
              ))}
              {!outcomes.length ? <div style={styles.emptyPanel(palette)}>Task outcomes will appear after tracked work completes.</div> : null}
            </div>
          </section>
        </div>

        <div style={styles.surfaceColumns}>
          {renderAdaptiveInsightList('Repair Analytics', snapshot?.repair_insights ?? [])}
          {renderAdaptiveInsightList('Context Efficiency', snapshot?.context_insights ?? [])}
        </div>
        <div style={styles.surfaceColumns}>
          {renderAdaptiveInsightList('Feedback Learning', snapshot?.feedback_insights ?? [])}
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Benchmark And Replay</h3>
              <span style={styles.contextTag(palette)}>
                {(snapshot?.benchmark_reports.length ?? 0) + (snapshot?.replay_results.length ?? 0)} report(s)
              </span>
            </div>
            <div style={styles.eventList}>
              {(snapshot?.benchmark_reports ?? []).slice(0, 5).map((report) => (
                <div key={report.id} style={styles.eventRow(palette, report.regression_detected ? 'error' : 'ok')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{report.suite_label}</strong>
                    <div style={styles.eventDetail(palette)}>
                      {adaptiveScoreLabel(report.candidate_score)} candidate / {adaptiveScoreLabel(report.baseline_score)} baseline
                    </div>
                  </div>
                  <span style={styles.eventTime(palette)}>{formatDateTime(report.created_at)}</span>
                </div>
              ))}
              {(snapshot?.replay_results ?? []).slice(0, 5).map((result) => (
                <div key={result.id} style={styles.eventRow(palette, result.regression_detected ? 'error' : result.status === 'improved' ? 'ok' : 'warning')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{result.source_task_id}</strong>
                    <div style={styles.eventDetail(palette)}>
                      Replay {formatStatusLabel(result.status)} from {adaptiveScoreLabel(result.previous_score)} to {adaptiveScoreLabel(result.replay_score)}
                    </div>
                  </div>
                  <span style={styles.eventTime(palette)}>{formatDateTime(result.created_at)}</span>
                </div>
              ))}
              {!snapshot?.benchmark_reports.length && !snapshot?.replay_results.length ? (
                <div style={styles.emptyPanel(palette)}>Run a benchmark or replay to create adaptive regression reports.</div>
              ) : null}
            </div>
          </section>
        </div>

        {snapshot?.warnings.length ? (
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionLabel(palette)}>Safety Notes</div>
            <div style={styles.tagWrap}>
              {snapshot.warnings.map((warning) => (
                <span key={warning} style={styles.contextTag(palette)}>
                  {warning}
                </span>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    );
  }

  function renderDistributedRuntimeSurface() {
    const unified = unifiedRuntime;
    const context = unifiedContext;
    const continuityState = continuity;
    const discipline = platformDiscipline;
    const operating = operatingEnvironment;
    const runtime = distributedRuntime;
    const observability = runtime?.observability;
    const workers = runtime?.workers ?? [];
    const queue = runtime?.queue ?? [];
    const auditEvents = runtime?.audit_events ?? [];
    const syncManifests = runtime?.sync_manifests ?? [];
    const activeJobs = queue.filter((item) => ['queued', 'retrying', 'assigned', 'running'].includes(item.status));
    const failedJobs = queue.filter((item) => ['failed', 'blocked'].includes(item.status));
    const readyPillars = unified?.pillars.filter((pillar) => pillar.status === 'ready').length ?? 0;
    const readyOperatingCapabilities = operating?.capabilities.filter((capability) => capability.status === 'ready').length ?? 0;
    const gatedOperatingCapabilities =
      operating?.capabilities.filter((capability) => capability.approval_required || capability.status === 'blocked').length ?? 0;
    const metrics = [
      { label: 'Pillars', value: unified?.pillars.length ?? 0 },
      { label: 'Primary', value: discipline?.primary_domains.length ?? 0 },
      { label: 'Beta', value: discipline?.beta_count ?? 0 },
      { label: 'Deprecated', value: discipline?.deprecated_count ?? 0 },
      { label: 'Context', value: context?.records.length ?? 0 },
      { label: 'Links', value: context?.relationships.length ?? 0 },
      { label: 'Timeline', value: continuityState?.timeline.entries.length ?? 0 },
      { label: 'Ready', value: readyPillars },
      { label: 'OS Caps', value: operating?.capabilities.length ?? 0 },
      { label: 'Gated', value: gatedOperatingCapabilities },
      { label: 'Workers', value: observability?.workers_total ?? workers.length },
      { label: 'Available', value: observability?.workers_available ?? workers.filter((item) => item.status === 'available').length },
      { label: 'Queued', value: observability?.queued_jobs ?? activeJobs.length },
      { label: 'Failed', value: observability?.failed_jobs ?? failedJobs.length }
    ];

    return (
      <div style={styles.surfacePage}>
        {renderSurfaceHeader(
          <Code size={22} />,
          'Runtime',
          'Local-first distributed execution with workers, queue state, model routing, sync manifests, and audit events.',
          <div style={styles.surfaceActions}>
            <button
              type="button"
              style={styles.secondaryButton(palette)}
              onClick={() => void refreshDistributedRuntime()}
              disabled={distributedRuntimeLoading}
            >
              {distributedRuntimeLoading ? <Loader2 size={16} className="spin" /> : <Zap size={16} />}
              Refresh
            </button>
            <button
              type="button"
              style={styles.secondaryButton(palette)}
              onClick={() => void dispatchNextRuntimeJob()}
              disabled={!workspaceRoot.trim() || Boolean(distributedRuntimeAction)}
            >
              {distributedRuntimeAction === 'dispatch' ? <Loader2 size={16} className="spin" /> : <Play size={16} />}
              Dispatch
            </button>
            <button
              type="button"
              style={styles.primaryButton(palette)}
              onClick={() => void exportRuntimeSyncManifest()}
              disabled={!workspaceRoot.trim() || Boolean(distributedRuntimeAction)}
            >
              {distributedRuntimeAction === 'sync' ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
              Sync manifest
            </button>
          </div>
        )}

        <div style={styles.metricGrid}>
          {metrics.map((metric) => (
            <div key={metric.label} style={styles.metricCard(palette)}>
              <span style={styles.metricLabel(palette)}>{metric.label}</span>
              <strong style={styles.metricValue(palette)}>{metric.value}</strong>
            </div>
          ))}
        </div>

        {distributedRuntimeStatus ? (
          <div style={styles.eventRow(palette, distributedRuntimeStatus.includes('Could not') ? 'error' : 'ok')}>
            <div>
              <strong style={styles.eventTitle(palette)}>Runtime Status</strong>
              <div style={styles.eventDetail(palette)}>{distributedRuntimeStatus}</div>
            </div>
          </div>
        ) : null}

        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>Platform Discipline</h3>
            <span style={styles.contextTag(palette)}>
              {discipline?.production_ready_count ?? 0} stable / {discipline?.experimental_count ?? 0} experimental
            </span>
          </div>
          <div style={styles.eventRow(palette, 'ok')}>
            <div>
              <strong style={styles.eventTitle(palette)}>Core Identity</strong>
              <div style={styles.eventDetail(palette)}>
                {discipline?.core_identity || `${productName} platform focus will appear after refresh.`}
              </div>
              <div style={styles.tagWrap}>
                {(discipline?.primary_domains ?? []).map((domain) => (
                  <span key={`primary-domain-${domain.id}`} style={styles.contextTag(palette)}>
                    primary: {domain.name}
                  </span>
                ))}
              </div>
            </div>
          </div>
          <div style={styles.eventRow(palette, 'ok')}>
            <div>
              <div style={styles.sectionHeaderInline}>
                <strong style={styles.eventTitle(palette)}>
                  {discipline?.stewardship.name ?? 'Platform Stewardship'}
                </strong>
                <span style={styles.contextTag(palette)}>primary responsibility</span>
              </div>
              <div style={styles.eventDetail(palette)}>
                {discipline?.stewardship.summary || `Stewardship keeps ${productName} calm, reliable, coherent, and trusted.`}
              </div>
              <div style={styles.tagWrap}>
                {(discipline?.stewardship.preserve ?? []).slice(0, 5).map((item) => (
                  <span key={`steward-preserve-${item}`} style={styles.contextTag(palette)}>
                    preserve: {item}
                  </span>
                ))}
                {(discipline?.stewardship.reduce ?? []).slice(0, 4).map((item) => (
                  <span key={`steward-reduce-${item}`} style={styles.contextTag(palette)}>
                    reduce: {item}
                  </span>
                ))}
              </div>
            </div>
          </div>
          <div style={styles.eventRow(palette, 'warning')}>
            <div>
              <div style={styles.sectionHeaderInline}>
                <strong style={styles.eventTitle(palette)}>
                  {discipline?.feature_admission.name ?? 'Feature Admission Gate'}
                </strong>
                <span style={styles.contextTag(palette)}>
                  {formatStatusLabel(discipline?.feature_admission.default_decision ?? 'reject_when_unclear')}
                </span>
              </div>
              <div style={styles.eventDetail(palette)}>
                {discipline?.feature_admission.summary || 'Unclear feature value defaults to no.'}
              </div>
              <div style={styles.tagWrap}>
                {(discipline?.feature_admission.hard_no_rules ?? []).slice(0, 4).map((rule) => (
                  <span key={`feature-hard-no-${rule}`} style={styles.contextTag(palette)}>
                    {rule}
                  </span>
                ))}
              </div>
            </div>
          </div>
          <div style={styles.surfaceColumns}>
            <div style={styles.eventList}>
              {(discipline?.feature_admission.criteria ?? []).slice(0, 5).map((criterion) => (
                <div key={`admission-${criterion.id}`} style={styles.eventRow(palette, 'warning')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{criterion.question}</strong>
                    <div style={styles.eventDetail(palette)}>{criterion.reject_when}</div>
                  </div>
                  <span style={styles.eventTime(palette)}>gate</span>
                </div>
              ))}
              {(discipline?.secondary_domains ?? []).slice(0, 3).map((domain) => (
                <div key={`secondary-domain-${domain.id}`} style={styles.eventRow(palette, 'warning')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{domain.name}</strong>
                    <div style={styles.eventDetail(palette)}>{domain.mastery_goal || domain.rationale}</div>
                  </div>
                  <span style={styles.eventTime(palette)}>secondary</span>
                </div>
              ))}
              {(discipline?.experimental_domains ?? []).slice(0, 3).map((domain) => (
                <div key={`experimental-domain-${domain.id}`} style={styles.eventRow(palette, 'warning')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{domain.name}</strong>
                    <div style={styles.eventDetail(palette)}>{domain.boundaries[0] || domain.rationale}</div>
                  </div>
                  <span style={styles.eventTime(palette)}>experimental</span>
                </div>
              ))}
              {!discipline?.primary_domains.length ? <div style={styles.emptyPanel(palette)}>Refresh Runtime to load platform focus.</div> : null}
            </div>
            <div style={styles.eventList}>
              {(discipline?.stability_tiers ?? []).slice(0, 4).map((tier) => (
                <div key={`stability-${tier.id}`} style={styles.eventRow(palette, tier.user_visibility === 'blocked' ? 'error' : tier.user_visibility === 'default' ? 'ok' : 'warning')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{tier.name}</strong>
                    <div style={styles.eventDetail(palette)}>{tier.description}</div>
                  </div>
                  <span style={styles.eventTime(palette)}>{formatStatusLabel(tier.user_visibility)}</span>
                </div>
              ))}
              {(discipline?.performance_budgets ?? []).slice(0, 4).map((budget) => (
                <div
                  key={`budget-${budget.id}`}
                  style={styles.eventRow(palette, budget.status === 'exceeded' ? 'error' : budget.status === 'healthy' ? 'ok' : 'warning')}
                >
                  <div>
                    <strong style={styles.eventTitle(palette)}>{budget.name}</strong>
                    <div style={styles.eventDetail(palette)}>{budget.target}</div>
                  </div>
                  <span style={styles.eventTime(palette)}>{formatStatusLabel(budget.status)}</span>
                </div>
              ))}
            </div>
          </div>
          <div style={{ ...styles.tagWrap, marginTop: 12 }}>
            {(discipline?.behavior_principles ?? []).slice(0, 4).map((principle) => (
              <span key={`principle-${principle.id}`} style={styles.contextTag(palette)}>
                {principle.principle}
              </span>
            ))}
            {(discipline?.design_standards ?? []).slice(0, 3).map((standard) => (
              <span key={`standard-${standard.id}`} style={styles.contextTag(palette)}>
                {standard.category}: {standard.enforcement}
              </span>
            ))}
          </div>
        </section>

        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>Unified Context Engine</h3>
            <span style={styles.contextTag(palette)}>
              {context?.source_summaries.length ?? 0} sources / {context?.relationships.length ?? 0} relationship(s)
            </span>
          </div>
          <div style={styles.surfaceColumns}>
            <div style={styles.eventList}>
              {(context?.source_summaries ?? []).slice(0, 8).map((source) => (
                <div key={source.source} style={styles.eventRow(palette, source.ready ? 'ok' : 'warning')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{formatStatusLabel(source.source)}</strong>
                    <div style={styles.eventDetail(palette)}>{source.summary}</div>
                  </div>
                  <span style={styles.eventTime(palette)}>{source.records}</span>
                </div>
              ))}
              {!context?.source_summaries.length ? <div style={styles.emptyPanel(palette)}>Unified context will appear after refresh.</div> : null}
            </div>
            <div style={styles.eventList}>
              {(context?.cross_module_insights ?? []).slice(0, 5).map((insight) => (
                <div key={insight} style={styles.eventRow(palette, 'ok')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>Context Insight</strong>
                    <div style={styles.eventDetail(palette)}>{insight}</div>
                  </div>
                </div>
              ))}
              {(context?.recommended_focus ?? []).slice(0, 4).map((focus) => (
                <div key={focus} style={styles.eventRow(palette, 'warning')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>Recommended Focus</strong>
                    <div style={styles.eventDetail(palette)}>{focus}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ ...styles.surfaceActions, justifyContent: 'stretch', marginTop: 12 }}>
            <input
              value={globalCommandDraft}
              onChange={(event) => setGlobalCommandDraft(event.target.value)}
              placeholder={`Route any ${productName} request through one command interface`}
              aria-label="Global command preview"
              style={{ ...styles.fieldInput(palette), flex: 1 }}
            />
            <button
              type="button"
              style={styles.secondaryButton(palette)}
              onClick={() => void previewRuntimeCommand()}
              disabled={!workspaceRoot.trim() || !globalCommandDraft.trim() || Boolean(distributedRuntimeAction)}
            >
              {distributedRuntimeAction === 'command-preview' ? <Loader2 size={16} className="spin" /> : <Search size={16} />}
              Preview route
            </button>
          </div>

          {globalCommandPreview ? (
            <div style={styles.eventRow(palette, globalCommandPreview.route.approval_required ? 'warning' : 'ok')}>
              <div>
                <div style={styles.sectionHeaderInline}>
                  <strong style={styles.eventTitle(palette)}>
                    {formatStatusLabel(globalCommandPreview.route.intent)} {'->'} {formatStatusLabel(globalCommandPreview.route.target_system)}
                  </strong>
                  <span style={styles.contextTag(palette)}>{Math.round(globalCommandPreview.route.confidence * 100)}% confidence</span>
                </div>
                <div style={styles.eventDetail(palette)}>{globalCommandPreview.route.reason}</div>
                <div style={styles.tagWrap}>
                  {globalCommandPreview.route.creates_task ? <span style={styles.contextTag(palette)}>task tracked</span> : <span style={styles.contextTag(palette)}>chat-safe</span>}
                  {globalCommandPreview.route.approval_required ? <span style={styles.contextTag(palette)}>approval</span> : null}
                  {globalCommandPreview.route.rollback_supported ? <span style={styles.contextTag(palette)}>rollback</span> : null}
                  {globalCommandPreview.route.validation_required ? <span style={styles.contextTag(palette)}>validation</span> : null}
                  {globalCommandPreview.context_results.slice(0, 3).map((result) => (
                    <span key={result.record.id} style={styles.contextTag(palette)}>
                      {result.record.kind}: {result.record.title}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ) : null}
        </section>

        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>Presence And Continuity</h3>
            <span style={styles.contextTag(palette)}>
              {formatStatusLabel(continuityState?.presence.status ?? 'calm')} / risk {Math.round((continuityState?.forecasts.risk_score ?? 0) * 100)}%
            </span>
          </div>
          <div style={styles.surfaceColumns}>
            <div style={styles.eventList}>
              <div style={styles.eventRow(palette, continuityState?.presence.status === 'attention' || continuityState?.presence.status === 'degraded' ? 'warning' : 'ok')}>
                <div>
                  <strong style={styles.eventTitle(palette)}>{continuityState?.presence.active_focus || 'Workspace continuity'}</strong>
                  <div style={styles.eventDetail(palette)}>
                    {continuityState?.presence.continuity_summary || 'Presence signals will appear after refresh.'}
                  </div>
                  <div style={styles.tagWrap}>
                    <span style={styles.contextTag(palette)}>{continuityState?.presence.workload_level ?? 'light'} workload</span>
                    <span style={styles.contextTag(palette)}>{continuityState?.cognitive.pacing ?? 'normal'} pacing</span>
                    <span style={styles.contextTag(palette)}>{continuityState?.cognitive.verbosity ?? 'balanced'} replies</span>
                  </div>
                </div>
              </div>
              {(continuityState?.presence.proactive_suggestions ?? []).slice(0, 4).map((suggestion) => (
                <div key={suggestion} style={styles.eventRow(palette, 'ok')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>Quiet Suggestion</strong>
                    <div style={styles.eventDetail(palette)}>{suggestion}</div>
                  </div>
                </div>
              ))}
              {(continuityState?.forecasts.signals ?? []).slice(0, 3).map((signal) => (
                <div key={signal.id} style={styles.eventRow(palette, signal.severity === 'high' || signal.severity === 'critical' ? 'error' : signal.severity === 'medium' ? 'warning' : 'ok')}>
                  <div>
                    <div style={styles.sectionHeaderInline}>
                      <strong style={styles.eventTitle(palette)}>{signal.title}</strong>
                      <span style={styles.contextTag(palette)}>{Math.round(signal.score * 100)}%</span>
                    </div>
                    <div style={styles.eventDetail(palette)}>{signal.summary}</div>
                  </div>
                </div>
              ))}
            </div>
            <div style={styles.eventList}>
              <div style={styles.eventRow(palette, continuityState?.workspace_state.restore_readiness === 'ready' ? 'ok' : 'warning')}>
                <div>
                  <strong style={styles.eventTitle(palette)}>Persistent Workspace</strong>
                  <div style={styles.eventDetail(palette)}>
                    {(continuityState?.workspace_state.persisted_sections ?? []).slice(0, 6).join(', ') || 'Persisted sections will appear after refresh.'}
                  </div>
                </div>
                <span style={styles.eventTime(palette)}>{formatStatusLabel(continuityState?.workspace_state.restore_readiness ?? 'partial')}</span>
              </div>
              <div style={styles.eventRow(palette, continuityState?.hardware.gpu_available || continuityState?.hardware.npu_available ? 'ok' : 'warning')}>
                <div>
                  <strong style={styles.eventTitle(palette)}>Hardware Routing</strong>
                  <div style={styles.eventDetail(palette)}>
                    {(continuityState?.hardware.accelerators ?? ['CPU']).join(', ')} / {continuityState?.hardware.cpu_logical ?? 0} logical CPU(s)
                  </div>
                </div>
                <span style={styles.eventTime(palette)}>{formatStatusLabel(continuityState?.hardware.status ?? 'partial')}</span>
              </div>
              {(continuityState?.self_diagnostics ?? []).slice(0, 4).map((diagnostic) => (
                <div key={diagnostic.id} style={styles.eventRow(palette, diagnostic.status === 'healthy' ? 'ok' : diagnostic.status === 'critical' || diagnostic.status === 'degraded' ? 'error' : 'warning')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{diagnostic.title}</strong>
                    <div style={styles.eventDetail(palette)}>{diagnostic.summary}</div>
                  </div>
                  <span style={styles.eventTime(palette)}>{formatStatusLabel(diagnostic.status)}</span>
                </div>
              ))}
              <div style={styles.eventRow(palette, 'ok')}>
                <div>
                  <strong style={styles.eventTitle(palette)}>Digital Twin</strong>
                  <div style={styles.eventDetail(palette)}>{continuityState?.digital_twin.workflow_summary || 'Workspace model will appear after refresh.'}</div>
                  <div style={styles.tagWrap}>
                    <span style={styles.contextTag(palette)}>{Math.round((continuityState?.digital_twin.confidence ?? 0) * 100)}% modeled</span>
                    <span style={styles.contextTag(palette)}>{continuityState?.skill_packs.length ?? 0} skill pack(s)</span>
                    <span style={styles.contextTag(palette)}>{continuityState?.universal_data_sources.length ?? 0} data source(s)</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>Unified AI Runtime</h3>
            <span style={styles.contextTag(palette)}>{unified?.mode ?? 'local-first'}</span>
          </div>
          <div style={styles.modelList}>
            {(unified?.pillars ?? []).slice(0, 8).map((pillar) => (
              <div key={pillar.id} style={styles.eventRow(palette, pillar.status === 'ready' ? 'ok' : pillar.status === 'planned' ? 'warning' : 'ok')}>
                <div>
                  <div style={styles.sectionHeaderInline}>
                    <strong style={styles.eventTitle(palette)}>{pillar.name}</strong>
                    <span style={styles.diagnosticChip(palette, pillar.status === 'ready' ? 'ok' : 'warning')}>
                      {formatStatusLabel(pillar.status)}
                    </span>
                  </div>
                  <div style={styles.eventDetail(palette)}>{pillar.summary}</div>
                  <div style={styles.tagWrap}>
                    {pillar.primary_surfaces.slice(0, 4).map((surface) => (
                      <span key={`${pillar.id}-${surface}`} style={styles.contextTag(palette)}>
                        {surface}
                      </span>
                    ))}
                    {pillar.signals.slice(0, 3).map((signal) => (
                      <span key={`${pillar.id}-${signal}`} style={styles.contextTag(palette)}>
                        {signal}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
            {!unified?.pillars.length ? <div style={styles.emptyPanel(palette)}>Unified runtime map will appear after refresh.</div> : null}
          </div>
        </section>

        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>AI Operating Environment</h3>
            <span style={styles.contextTag(palette)}>
              {readyOperatingCapabilities} ready / {gatedOperatingCapabilities} gated
            </span>
          </div>
          <div style={styles.modelList}>
            {(operating?.capabilities ?? []).map((capability) => (
              <div
                key={capability.id}
                style={styles.eventRow(
                  palette,
                  capability.status === 'ready' ? 'ok' : capability.status === 'blocked' || capability.status === 'disabled' ? 'error' : 'warning'
                )}
              >
                <div>
                  <div style={styles.sectionHeaderInline}>
                    <strong style={styles.eventTitle(palette)}>{capability.name}</strong>
                    <span
                      style={styles.diagnosticChip(
                        palette,
                        capability.status === 'ready' ? 'ok' : capability.status === 'blocked' || capability.status === 'disabled' ? 'error' : 'warning'
                      )}
                    >
                      {formatStatusLabel(capability.status)}
                    </span>
                  </div>
                  <div style={styles.eventDetail(palette)}>{capability.summary}</div>
                  <div style={styles.tagWrap}>
                    <span style={styles.contextTag(palette)}>{capability.permission_scope || capability.category}</span>
                    {capability.approval_required ? <span style={styles.contextTag(palette)}>approval</span> : null}
                    {capability.sandbox_required ? <span style={styles.contextTag(palette)}>sandbox</span> : null}
                    {capability.rollback_supported ? <span style={styles.contextTag(palette)}>rollback</span> : null}
                  </div>
                </div>
              </div>
            ))}
            {!operating?.capabilities.length ? <div style={styles.emptyPanel(palette)}>Operating environment map will appear after refresh.</div> : null}
          </div>
        </section>

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>OS Adapters</h3>
              <span style={styles.contextTag(palette)}>
                {operating?.adapters.filter((adapter) => adapter.enabled).length ?? 0} enabled
              </span>
            </div>
            <div style={styles.eventList}>
              {(operating?.adapters ?? []).slice(0, 8).map((adapter) => (
                <div
                  key={adapter.id}
                  style={styles.eventRow(
                    palette,
                    adapter.enabled && adapter.status === 'ready' ? 'ok' : adapter.status === 'blocked' || adapter.status === 'disabled' ? 'error' : 'warning'
                  )}
                >
                  <div>
                    <strong style={styles.eventTitle(palette)}>{adapter.name}</strong>
                    <div style={styles.eventDetail(palette)}>
                      {adapter.permission_scope || adapter.category} / {adapter.sandboxed ? 'sandboxed' : 'read-only'} /{' '}
                      {adapter.enabled ? 'enabled' : 'disabled'}
                    </div>
                  </div>
                  <span style={styles.eventTime(palette)}>{formatStatusLabel(adapter.status)}</span>
                </div>
              ))}
            </div>
          </section>

          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>System Signals</h3>
              <span style={styles.contextTag(palette)}>{operating?.execution_mode ?? 'control-plane'}</span>
            </div>
            <div style={styles.eventList}>
              {(operating?.system_signals ?? []).map((signal) => (
                <div key={signal.id} style={styles.eventRow(palette, signal.status === 'ok' ? 'ok' : signal.status === 'error' ? 'error' : 'warning')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{signal.label}</strong>
                    <div style={styles.eventDetail(palette)}>{signal.detail}</div>
                  </div>
                  <span style={styles.eventTime(palette)}>{signal.value}</span>
                </div>
              ))}
            </div>
          </section>
        </div>

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Modalities</h3>
              <span style={styles.contextTag(palette)}>{unified?.modalities.length ?? 0} registered</span>
            </div>
            <div style={styles.eventList}>
              {(unified?.modalities ?? []).map((modality) => (
                <div key={modality.id} style={styles.eventRow(palette, modality.status === 'ready' ? 'ok' : 'warning')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{modality.label}</strong>
                    <div style={styles.eventDetail(palette)}>
                      {modality.input_supported ? 'Input' : 'Input planned'} / {modality.output_supported ? 'Output' : 'Output planned'}
                    </div>
                    <div style={styles.tagWrap}>
                      {modality.formats.slice(0, 6).map((format) => (
                        <span key={`${modality.id}-${format}`} style={styles.contextTag(palette)}>
                          {format}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Tool Contracts</h3>
              <span style={styles.contextTag(palette)}>{unified?.tools.length ?? 0} tool(s)</span>
            </div>
            <div style={styles.eventList}>
              {(unified?.tools ?? []).slice(0, 8).map((tool) => (
                <div key={tool.id} style={styles.eventRow(palette, tool.approval_required ? 'warning' : 'ok')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{tool.name}</strong>
                    <div style={styles.eventDetail(palette)}>
                      {tool.permission_scope || tool.category} / {tool.sandboxed ? 'sandboxed' : 'direct'} / {tool.rollback_supported ? 'rollback' : 'no rollback'}
                    </div>
                  </div>
                  <span style={styles.eventTime(palette)}>{tool.tracked_by_tasks ? 'tracked' : 'untracked'}</span>
                </div>
              ))}
            </div>
          </section>
        </div>

        {unified?.recommendations.length ? (
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionLabel(palette)}>Runtime Guidance</div>
            <div style={styles.tagWrap}>
              {unified.recommendations.map((item) => (
                <span key={item} style={styles.contextTag(palette)}>
                  {item}
                </span>
              ))}
            </div>
          </section>
        ) : null}

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Workers</h3>
              <span style={styles.contextTag(palette)}>{runtime?.execution_mode ?? 'local'} mode</span>
            </div>
            <div style={styles.modelList}>
              {workers.map((worker) => (
                <div key={worker.worker_id} style={styles.modelRow(palette, false)}>
                  <div style={styles.modelRowMain}>
                    <div style={styles.modelRowTop}>
                      <div style={styles.cardTitle(palette)}>{worker.name}</div>
                      <span style={styles.diagnosticChip(palette, healthStatusToEventStatus(worker.status))}>
                        {formatStatusLabel(worker.status)}
                      </span>
                    </div>
                    <div style={styles.eventDetail(palette)}>{worker.endpoint || worker.worker_id}</div>
                    <div style={styles.tagWrap}>
                      <span style={styles.contextTag(palette)}>{worker.kind}</span>
                      <span style={styles.contextTag(palette)}>{worker.trust_state}</span>
                      <span style={styles.contextTag(palette)}>{worker.capabilities.supported_languages.length} language(s)</span>
                      <span style={styles.contextTag(palette)}>{worker.capabilities.available_models.length} model(s)</span>
                      {worker.capabilities.validation_support ? <span style={styles.goodTag(palette)}>validation</span> : null}
                    </div>
                  </div>
                  <span style={styles.eventTime(palette)}>{formatDateTime(worker.last_heartbeat_at)}</span>
                </div>
              ))}
              {!workers.length ? <div style={styles.emptyPanel(palette)}>No runtime workers reported yet.</div> : null}
            </div>
          </section>

          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Execution Queue</h3>
              <span style={styles.contextTag(palette)}>{queue.length} job(s)</span>
            </div>
            <div style={styles.modelList}>
              {queue.slice(0, 12).map((job) => (
                <div key={job.id} style={styles.modelRow(palette, false)}>
                  <div style={styles.modelRowMain}>
                    <div style={styles.modelRowTop}>
                      <div style={styles.cardTitle(palette)}>{job.title || job.id}</div>
                      <span style={styles.diagnosticChip(palette, healthStatusToEventStatus(job.status))}>
                        {formatStatusLabel(job.status)}
                      </span>
                    </div>
                    <div style={styles.eventDetail(palette)}>{job.result_summary || job.error_summary || job.user_goal}</div>
                    <div style={styles.tagWrap}>
                      <span style={styles.contextTag(palette)}>{job.kind}</span>
                      <span style={styles.contextTag(palette)}>{job.permission_scope}</span>
                      <span style={styles.contextTag(palette)}>
                        {job.attempts}/{job.max_attempts} attempt(s)
                      </span>
                      {job.assigned_worker_id ? <span style={styles.goodTag(palette)}>{job.assigned_worker_id}</span> : null}
                    </div>
                  </div>
                  <span style={styles.eventTime(palette)}>{formatDateTime(job.updated_at || job.created_at)}</span>
                </div>
              ))}
              {!queue.length ? <div style={styles.emptyPanel(palette)}>No execution jobs have been queued.</div> : null}
            </div>
          </section>
        </div>

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Audit Events</h3>
              <span style={styles.contextTag(palette)}>{auditEvents.length} event(s)</span>
            </div>
            <div style={styles.eventList}>
              {auditEvents.slice(0, 10).map((event) => (
                <div key={event.id} style={styles.eventRow(palette, event.status === 'error' ? 'error' : event.status === 'warning' ? 'warning' : 'ok')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{event.event_type}</strong>
                    <div style={styles.eventDetail(palette)}>{event.detail || event.job_id || event.worker_id}</div>
                  </div>
                  <span style={styles.eventTime(palette)}>{formatEventTime(event.created_at)}</span>
                </div>
              ))}
              {!auditEvents.length ? <div style={styles.emptyPanel(palette)}>No runtime audit events recorded yet.</div> : null}
            </div>
          </section>

          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Sync And Safety</h3>
              <span style={styles.contextTag(palette)}>{syncManifests.length} manifest(s)</span>
            </div>
            <div style={styles.sectionBlock}>
              <div style={styles.tagWrap}>
                {(runtime?.security_summary ?? []).map((item) => (
                  <span key={item} style={styles.contextTag(palette)}>
                    {item}
                  </span>
                ))}
                {!runtime?.security_summary.length ? (
                  <span style={styles.previewMeta(palette)}>Local-first safety summary will appear after refresh.</span>
                ) : null}
              </div>
            </div>
            <div style={styles.eventList}>
              {syncManifests.slice(0, 5).map((manifest) => (
                <div key={manifest.id} style={styles.eventRow(palette, 'ok')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{manifest.id}</strong>
                    <div style={styles.eventDetail(palette)}>
                      {manifest.included_sections.join(', ')} / {manifest.manifest_hash.slice(0, 12)}
                    </div>
                  </div>
                  <span style={styles.eventTime(palette)}>{formatDateTime(manifest.created_at)}</span>
                </div>
              ))}
              {!syncManifests.length ? <div style={styles.emptyPanel(palette)}>No sync manifests recorded yet.</div> : null}
            </div>
          </section>
        </div>
      </div>
    );
  }

  function renderEcosystemSurface() {
    const snapshot = ecosystemSnapshot;
    const packages = snapshot?.packages ?? [];
    const catalog = snapshot?.marketplace_catalog ?? [];
    const workflows = snapshot?.workflows ?? [];
    const graph = snapshot?.knowledge_graph;
    const policy = snapshot?.organization_policy;
    const governance = snapshot?.governance ?? [];
    const search = ecosystemSearch ?? snapshot?.search ?? null;
    const invalidPackages = (snapshot?.package_validation ?? []).filter((item) => !item.valid);
    const governanceStatus = (status: string) => (status === 'blocked' ? 'error' : status === 'trusted' ? 'ok' : 'warning');

    return (
      <div style={styles.surfacePage}>
        {renderSurfaceHeader(
          <Brain size={22} />,
          'Ecosystem',
          'Reusable agents, workflows, shared intelligence, organization policy, knowledge graph, search, and reproducibility.',
          <div style={styles.surfaceActions}>
            <button
              type="button"
              style={styles.secondaryButton(palette)}
              onClick={() => void refreshEcosystemSignals(undefined, false)}
              disabled={ecosystemLoading}
            >
              {ecosystemLoading ? <Loader2 size={16} className="spin" /> : <Zap size={16} />}
              Refresh
            </button>
            <button
              type="button"
              style={styles.primaryButton(palette)}
              onClick={() => void refreshEcosystemSignals(undefined, true)}
              disabled={ecosystemLoading}
            >
              {ecosystemLoading ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
              Rebuild graph
            </button>
          </div>
        )}

        <div style={styles.metricGrid}>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Marketplace</span>
            <strong style={styles.metricValue(palette)}>{catalog.length}</strong>
          </div>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Workflows</span>
            <strong style={styles.metricValue(palette)}>{workflows.length}</strong>
          </div>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Graph Nodes</span>
            <strong style={styles.metricValue(palette)}>{graph?.nodes.length ?? 0}</strong>
          </div>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Governance</span>
            <strong style={styles.metricValue(palette)}>
              {governance.some((item) => item.status === 'blocked') ? 'Blocked' : 'Ready'}
            </strong>
          </div>
        </div>

        {ecosystemStatus ? (
          <div
            style={styles.eventRow(
              palette,
              ecosystemStatus.includes('Could not') || ecosystemStatus.includes('invalid') ? 'error' : 'ok'
            )}
          >
            <div>
              <strong style={styles.eventTitle(palette)}>Ecosystem Status</strong>
              <div style={styles.eventDetail(palette)}>{ecosystemStatus}</div>
            </div>
          </div>
        ) : null}

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Agent Marketplace</h3>
              <div style={styles.tagWrap}>
                <span style={styles.contextTag(palette)}>{invalidPackages.length} invalid</span>
                <button
                  type="button"
                  style={styles.iconTextButton(palette)}
                  onClick={() => void validateSampleEcosystemPackage()}
                  disabled={Boolean(ecosystemAction)}
                >
                  {ecosystemAction === 'validate-sample' ? <Loader2 size={14} className="spin" /> : <CheckCircle2 size={14} />}
                  Validate sample
                </button>
              </div>
            </div>
            <div style={styles.modelList}>
              {packages.map((item) => {
                const busy = ecosystemAction.endsWith(`:${item.id}`);
                return (
                  <div key={item.id} style={styles.modelRow(palette, item.enabled)}>
                    <div style={styles.modelRowMain}>
                      <div style={styles.modelRowTop}>
                        <div style={styles.cardTitle(palette)}>{item.name}</div>
                        <span style={styles.diagnosticChip(palette, item.enabled ? 'ok' : 'warning')}>
                          {item.enabled ? 'enabled' : 'disabled'}
                        </span>
                      </div>
                      <div style={styles.eventDetail(palette)}>{item.description || item.id}</div>
                      <div style={styles.tagWrap}>
                        <span style={styles.contextTag(palette)}>{formatStatusLabel(item.kind)}</span>
                        <span style={styles.contextTag(palette)}>{item.version}</span>
                        <span style={item.trust_level === 'trusted' || item.trust_level === 'signed' ? styles.goodTag(palette) : styles.contextTag(palette)}>
                          {item.trust_level}
                        </span>
                        <span style={styles.contextTag(palette)}>{item.update_channel}</span>
                      </div>
                    </div>
                    <div style={styles.rowActions}>
                      <button
                        type="button"
                        style={styles.iconTextButton(palette)}
                        onClick={() => void updateEcosystemPackageState(item, item.enabled ? 'disable' : 'enable')}
                        disabled={busy}
                      >
                        {busy ? <Loader2 size={14} className="spin" /> : item.enabled ? <Pause size={14} /> : <Play size={14} />}
                        {item.enabled ? 'Disable' : 'Enable'}
                      </button>
                      <button
                        type="button"
                        style={styles.iconTextButton(palette)}
                        onClick={() => void updateEcosystemPackageState(item, 'trust')}
                        disabled={item.trust_level === 'trusted' || item.trust_level === 'signed' || busy}
                      >
                        <CheckCircle2 size={14} />
                        Trust
                      </button>
                    </div>
                  </div>
                );
              })}
              {!packages.length ? <div style={styles.emptyPanel(palette)}>No ecosystem packages are installed yet.</div> : null}
            </div>
            <div style={styles.tagWrap}>
              {catalog.slice(0, 6).map((item) => (
                <span key={item.id} style={styles.contextTag(palette)}>
                  {item.name}
                </span>
              ))}
            </div>
          </section>

          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Workflow Manager</h3>
              <span style={styles.contextTag(palette)}>{workflows.length} reusable</span>
            </div>
            <div style={styles.eventList}>
              {workflows.slice(0, 8).map((workflow) => {
                const busy = ecosystemAction === `workflow:${workflow.id}`;
                return (
                  <div key={workflow.id} style={styles.eventRow(palette, workflow.enabled ? 'ok' : 'warning')}>
                    <div>
                      <strong style={styles.eventTitle(palette)}>{workflow.name}</strong>
                      <div style={styles.eventDetail(palette)}>{workflow.description}</div>
                      <div style={styles.tagWrap}>
                        <span style={styles.contextTag(palette)}>{workflow.category}</span>
                        <span style={styles.contextTag(palette)}>{workflow.steps.length} steps</span>
                        <span style={styles.contextTag(palette)}>{workflow.approvals.length} approvals</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      style={styles.iconTextButton(palette)}
                      onClick={() => void runReusableWorkflow(workflow.id)}
                      disabled={!workflow.enabled || busy}
                    >
                      {busy ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
                      Run
                    </button>
                  </div>
                );
              })}
              {!workflows.length ? <div style={styles.emptyPanel(palette)}>Workflow templates will appear after refresh.</div> : null}
            </div>
          </section>
        </div>

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Knowledge Graph</h3>
              <span style={styles.contextTag(palette)}>{graph?.edges.length ?? 0} relationships</span>
            </div>
            <div style={styles.workspaceMeta(palette)}>
              <strong>Modules</strong>
              <span>{graph?.modules_total ?? 0}</span>
              <strong>APIs</strong>
              <span>{graph?.api_routes_total ?? 0}</span>
              <strong>Dependencies</strong>
              <span>{graph?.dependencies_total ?? 0}</span>
              <strong>Decisions</strong>
              <span>{graph?.decisions_total ?? 0}</span>
            </div>
            <div style={styles.eventList}>
              {(graph?.nodes ?? []).slice(0, 8).map((node) => (
                <div key={node.id} style={styles.eventRow(palette, node.kind === 'failure' ? 'warning' : 'ok')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{node.label}</strong>
                    <div style={styles.eventDetail(palette)}>{node.summary || node.path}</div>
                    <span style={styles.contextTag(palette)}>{node.kind}</span>
                  </div>
                </div>
              ))}
              {!graph?.nodes.length ? <div style={styles.emptyPanel(palette)}>No graph has been generated yet.</div> : null}
            </div>
          </section>

          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Advanced Search</h3>
              <button
                type="button"
                style={styles.iconTextButton(palette)}
                onClick={() => void runEcosystemSearch()}
                disabled={ecosystemAction === 'search'}
              >
                {ecosystemAction === 'search' ? <Loader2 size={14} className="spin" /> : <Search size={14} />}
                Search
              </button>
            </div>
            <div style={styles.searchWrap(palette)}>
              <Search size={16} />
              <input
                value={ecosystemSearchQuery}
                onChange={(event) => setEcosystemSearchQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void runEcosystemSearch();
                }}
                placeholder="Search architecture, tasks, memory, workflows..."
                style={styles.searchInput(palette)}
              />
            </div>
            <div style={styles.eventList}>
              {(search?.results ?? []).slice(0, 8).map((result) => (
                <div key={`${result.kind}-${result.id}`} style={styles.eventRow(palette, 'ok')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{result.title}</strong>
                    <div style={styles.eventDetail(palette)}>{result.detail || result.reference}</div>
                    <div style={styles.tagWrap}>
                      <span style={styles.contextTag(palette)}>{result.kind}</span>
                      <span style={styles.contextTag(palette)}>{Math.round(result.score * 10) / 10}</span>
                    </div>
                  </div>
                </div>
              ))}
              {!search?.results.length ? <div style={styles.emptyPanel(palette)}>Search results will appear here.</div> : null}
            </div>
          </section>
        </div>

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Organization Dashboard</h3>
              <span style={styles.contextTag(palette)}>{policy?.collaboration_mode ?? 'local'}</span>
            </div>
            <div style={styles.workspaceMeta(palette)}>
              <strong>Signed packages</strong>
              <span>{policy?.require_signed_packages ? 'required' : 'optional'}</span>
              <strong>Community</strong>
              <span>{policy?.allow_community_packages ? 'allowed' : 'blocked'}</span>
              <strong>Shared tasks</strong>
              <span>{snapshot?.team.shared_task_count ?? 0}</span>
              <strong>Approvals</strong>
              <span>{snapshot?.team.pending_approvals ?? 0}</span>
            </div>
            <div style={styles.eventList}>
              {governance.map((signal) => (
                <div key={signal.id} style={styles.eventRow(palette, governanceStatus(signal.status))}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{signal.label}</strong>
                    <div style={styles.eventDetail(palette)}>{signal.detail}</div>
                  </div>
                  <span style={styles.eventTime(palette)}>{Math.round(signal.score * 100)}%</span>
                </div>
              ))}
            </div>
          </section>

          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Shared Intelligence</h3>
              <button
                type="button"
                style={styles.iconTextButton(palette)}
                onClick={() => void exportProjectIntelligenceProfile()}
                disabled={ecosystemAction === 'export-profile'}
              >
                {ecosystemAction === 'export-profile' ? <Loader2 size={14} className="spin" /> : <Download size={14} />}
                Export current
              </button>
            </div>
            <div style={styles.eventList}>
              {(snapshot?.shared_profiles ?? []).slice(0, 8).map((profile) => (
                <div key={profile.id} style={styles.eventRow(palette, 'ok')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{profile.name}</strong>
                    <div style={styles.eventDetail(palette)}>{profile.description || profile.id}</div>
                    <div style={styles.tagWrap}>
                      <span style={styles.contextTag(palette)}>{formatStatusLabel(profile.kind)}</span>
                      <span style={styles.contextTag(palette)}>{profile.version}</span>
                      <span style={styles.contextTag(palette)}>{profile.trust_level}</span>
                    </div>
                  </div>
                </div>
              ))}
              {!snapshot?.shared_profiles.length ? <div style={styles.emptyPanel(palette)}>No shared intelligence profiles have been imported or exported.</div> : null}
            </div>
          </section>
        </div>

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Cross-Project Intelligence</h3>
              <span style={styles.contextTag(palette)}>{snapshot?.cross_project_insights.length ?? 0} insight(s)</span>
            </div>
            <div style={styles.eventList}>
              {(snapshot?.cross_project_insights ?? []).slice(0, 8).map((insight) => (
                <div key={insight.id} style={styles.eventRow(palette, insight.severity === 'high' ? 'error' : insight.severity === 'medium' ? 'warning' : 'ok')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{insight.title}</strong>
                    <div style={styles.eventDetail(palette)}>{insight.recommendation || insight.detail}</div>
                    <div style={styles.tagWrap}>
                      <span style={styles.contextTag(palette)}>{formatStatusLabel(insight.category)}</span>
                      <span style={styles.contextTag(palette)}>{insight.projects.length} projects</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Reproducibility & Audit</h3>
              <span style={styles.contextTag(palette)}>{snapshot?.reproducibility.length ?? 0} records</span>
            </div>
            <div style={styles.eventList}>
              {(snapshot?.reproducibility ?? []).slice(0, 5).map((record) => (
                <div key={record.id} style={styles.eventRow(palette, record.status === 'ready' ? 'ok' : 'warning')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{record.deterministic_hash.slice(0, 12)}</strong>
                    <div style={styles.eventDetail(palette)}>{record.replay_notes[0] || record.task_id}</div>
                  </div>
                  <span style={styles.eventTime(palette)}>{record.artifacts.length} artifacts</span>
                </div>
              ))}
              {(snapshot?.audit_events ?? []).slice(0, 5).map((event) => (
                <div key={event.id} style={styles.eventRow(palette, event.status)}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{formatStatusLabel(event.action)}</strong>
                    <div style={styles.eventDetail(palette)}>{event.detail}</div>
                  </div>
                </div>
              ))}
              {!snapshot?.audit_events.length && !snapshot?.reproducibility.length ? (
                <div style={styles.emptyPanel(palette)}>Audit and reproducibility events will appear after ecosystem actions.</div>
              ) : null}
            </div>
          </section>
        </div>
      </div>
    );
  }

  function renderAutonomousEngineeringSurface() {
    const snapshot = autonomousSnapshot;
    const detail = selectedAutonomousObjective;
    const objective = detail?.objective;
    const pendingGates = (snapshot?.approval_gates ?? []).filter((gate) => gate.status === 'pending');
    const latestSimulation = detail?.simulations[0] ?? snapshot?.simulations[0] ?? null;
    const metricLabel = (metric: { value: number; unit: string }) => {
      if (metric.unit === 'ratio') return `${Math.round(metric.value * 100)}%`;
      return `${Math.round(metric.value * 10) / 10} ${metric.unit}`;
    };
    const verificationStatus = (status: string) =>
      status === 'failed' ? 'error' : status === 'passed' ? 'ok' : status === 'warning' ? 'warning' : 'ok';

    return (
      <div style={styles.surfacePage}>
        {renderSurfaceHeader(
          <Zap size={22} />,
          'Autonomous',
          'Supervised long-running engineering objectives with dry runs, approval gates, verification, explainability, and rollback-oriented limits.',
          <div style={styles.surfaceActions}>
            <button
              type="button"
              style={styles.secondaryButton(palette)}
              onClick={() => void refreshAutonomousSignals()}
              disabled={autonomousLoading}
            >
              {autonomousLoading ? <Loader2 size={16} className="spin" /> : <Zap size={16} />}
              Refresh
            </button>
            <button
              type="button"
              style={styles.primaryButton(palette)}
              onClick={() => void createDryRunAutonomousObjective()}
              disabled={Boolean(autonomousAction)}
            >
              {autonomousAction === 'create' ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
              Dry run
            </button>
          </div>
        )}

        <div style={styles.metricGrid}>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Objectives</span>
            <strong style={styles.metricValue(palette)}>{snapshot?.objectives.length ?? 0}</strong>
          </div>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Active</span>
            <strong style={styles.metricValue(palette)}>{snapshot?.active_objectives.length ?? 0}</strong>
          </div>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Pending Gates</span>
            <strong style={styles.metricValue(palette)}>{pendingGates.length}</strong>
          </div>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Risk</span>
            <strong style={styles.metricValue(palette)}>
              {latestSimulation ? `${Math.round(latestSimulation.predicted_validation_risk * 100)}%` : 'n/a'}
            </strong>
          </div>
        </div>

        {autonomousStatus ? (
          <div style={styles.eventRow(palette, autonomousStatus.includes('Could not') ? 'error' : 'ok')}>
            <div>
              <strong style={styles.eventTitle(palette)}>Autonomous Status</strong>
              <div style={styles.eventDetail(palette)}>{autonomousStatus}</div>
            </div>
          </div>
        ) : null}

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <h3 style={styles.settingsHeading(palette)}>Create Objective</h3>
            <label style={styles.fieldLabel(palette)}>
              <span>Title</span>
              <input
                value={autonomousObjectiveTitle}
                onChange={(event) => setAutonomousObjectiveTitle(event.target.value)}
                style={styles.fieldInput(palette)}
              />
            </label>
            <label style={styles.fieldLabel(palette)}>
              <span>Goal</span>
              <textarea
                value={autonomousObjectiveGoal}
                onChange={(event) => setAutonomousObjectiveGoal(event.target.value)}
                style={styles.fieldTextarea(palette)}
                rows={4}
              />
            </label>
            <div style={styles.tagWrap}>
              <span style={styles.contextTag(palette)}>dry-run first</span>
              <span style={styles.contextTag(palette)}>approval gated</span>
              <span style={styles.contextTag(palette)}>checkpoint required</span>
            </div>
          </section>

          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Objectives</h3>
              <span style={styles.contextTag(palette)}>{snapshot?.objectives.length ?? 0} total</span>
            </div>
            <div style={styles.modelList}>
              {(snapshot?.objectives ?? []).slice(0, 10).map((item) => (
                <button
                  key={item.id}
                  type="button"
                  style={styles.modelRow(palette, selectedAutonomousObjective?.objective.id === item.id)}
                  onClick={() => {
                    setSelectedAutonomousObjective(null);
                    void getAutonomousObjective(item.id).then(setSelectedAutonomousObjective).catch((error) => {
                      setAutonomousStatus(error instanceof Error ? error.message : 'Could not open objective');
                    });
                  }}
                >
                  <div style={styles.modelRowMain}>
                    <div style={styles.modelRowTop}>
                      <div style={styles.cardTitle(palette)}>{item.title}</div>
                      <span style={styles.diagnosticChip(palette, taskStatusToEventStatus(item.status))}>{formatStatusLabel(item.status)}</span>
                    </div>
                    <div style={styles.eventDetail(palette)}>{item.user_goal}</div>
                    <div style={styles.tagWrap}>
                      <span style={styles.contextTag(palette)}>{item.iteration_count}/{item.safety_limits.max_iterations} iterations</span>
                      <span style={styles.contextTag(palette)}>{item.assigned_agent_roles.length} agents</span>
                      <span style={styles.contextTag(palette)}>{item.approval_gate_ids.length} gates</span>
                    </div>
                  </div>
                </button>
              ))}
              {!snapshot?.objectives.length ? <div style={styles.emptyPanel(palette)}>No autonomous objectives have been created yet.</div> : null}
            </div>
          </section>
        </div>

        {objective ? (
          <>
            <div style={styles.surfaceColumns}>
              <section style={styles.settingsSection(palette)}>
                <div style={styles.sectionHeaderInline}>
                  <h3 style={styles.settingsHeading(palette)}>{objective.title}</h3>
                  <span style={styles.diagnosticChip(palette, taskStatusToEventStatus(objective.status))}>
                    {formatStatusLabel(objective.status)}
                  </span>
                </div>
                <div style={styles.workspaceMeta(palette)}>
                  <strong>Current phase</strong>
                  <span>{formatStatusLabel(objective.current_phase)}</span>
                  <strong>Token budget</strong>
                  <span>{objective.safety_limits.token_budget.toLocaleString()}</span>
                  <strong>Parallel agents</strong>
                  <span>{objective.safety_limits.max_parallel_agents}</span>
                  <strong>Rollback</strong>
                  <span>{objective.safety_limits.rollback_required ? 'required' : 'optional'}</span>
                </div>
                <div style={styles.rowActions}>
                  <button type="button" style={styles.iconTextButton(palette)} onClick={() => void updateAutonomousObjective('start')} disabled={Boolean(autonomousAction)}>
                    <Play size={14} />
                    Start
                  </button>
                  <button type="button" style={styles.iconTextButton(palette)} onClick={() => void updateAutonomousObjective('iterate')} disabled={Boolean(autonomousAction)}>
                    <Zap size={14} />
                    Iterate
                  </button>
                  <button type="button" style={styles.iconTextButton(palette)} onClick={() => void updateAutonomousObjective('simulate')} disabled={Boolean(autonomousAction)}>
                    <Search size={14} />
                    Simulate
                  </button>
                  <button type="button" style={styles.iconTextButton(palette)} onClick={() => void updateAutonomousObjective('pause')} disabled={Boolean(autonomousAction)}>
                    <Pause size={14} />
                    Pause
                  </button>
                  <button type="button" style={styles.iconTextButton(palette)} onClick={() => void updateAutonomousObjective('cancel')} disabled={Boolean(autonomousAction)}>
                    <Square size={14} />
                    Cancel
                  </button>
                </div>
              </section>

              <section style={styles.settingsSection(palette)}>
                <div style={styles.sectionHeaderInline}>
                  <h3 style={styles.settingsHeading(palette)}>Simulation</h3>
                  <span style={styles.contextTag(palette)}>{latestSimulation?.estimated_impact ?? 'pending'}</span>
                </div>
                {latestSimulation ? (
                  <>
                    <div style={styles.workspaceMeta(palette)}>
                      <strong>Validation risk</strong>
                      <span>{Math.round(latestSimulation.predicted_validation_risk * 100)}%</span>
                      <strong>Projected tokens</strong>
                      <span>{latestSimulation.projected_token_cost.toLocaleString()}</span>
                      <strong>Iterations</strong>
                      <span>{latestSimulation.projected_iterations}</span>
                      <strong>Dependencies</strong>
                      <span>{latestSimulation.projected_dependency_changes.length}</span>
                    </div>
                    <div style={styles.tagWrap}>
                      {latestSimulation.projected_file_changes.slice(0, 8).map((file) => (
                        <span key={file} style={styles.contextTag(palette)}>{file}</span>
                      ))}
                    </div>
                  </>
                ) : (
                  <div style={styles.emptyPanel(palette)}>No dry-run simulation has been recorded.</div>
                )}
              </section>
            </div>

            <div style={styles.surfaceColumns}>
              <section style={styles.settingsSection(palette)}>
                <div style={styles.sectionHeaderInline}>
                  <h3 style={styles.settingsHeading(palette)}>Phases</h3>
                  <span style={styles.contextTag(palette)}>{detail.phases.length} phase(s)</span>
                </div>
                <div style={styles.eventList}>
                  {detail.phases.map((phase) => (
                    <div key={phase.id} style={styles.eventRow(palette, taskStatusToEventStatus(phase.status))}>
                      <div>
                        <strong style={styles.eventTitle(palette)}>{phase.title}</strong>
                        <div style={styles.eventDetail(palette)}>{phase.summary || phase.agent_roles.join(', ')}</div>
                        <div style={styles.tagWrap}>
                          <span style={styles.contextTag(palette)}>{formatStatusLabel(phase.kind)}</span>
                          <span style={styles.contextTag(palette)}>{formatStatusLabel(phase.status)}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <section style={styles.settingsSection(palette)}>
                <div style={styles.sectionHeaderInline}>
                  <h3 style={styles.settingsHeading(palette)}>Approval Gates</h3>
                  <span style={styles.contextTag(palette)}>{detail.approval_gates.filter((gate) => gate.status === 'pending').length} pending</span>
                </div>
                <div style={styles.eventList}>
                  {detail.approval_gates.map((gate) => {
                    const busy = autonomousAction.endsWith(`:${gate.id}`);
                    return (
                      <div key={gate.id} style={styles.eventRow(palette, gate.status === 'approved' ? 'ok' : gate.status === 'rejected' ? 'error' : 'warning')}>
                        <div>
                          <strong style={styles.eventTitle(palette)}>{gate.title}</strong>
                          <div style={styles.eventDetail(palette)}>{gate.reason}</div>
                          <span style={styles.contextTag(palette)}>{formatStatusLabel(gate.kind)}</span>
                        </div>
                        {gate.status === 'pending' ? (
                          <div style={styles.rowActions}>
                            <button type="button" style={styles.iconTextButton(palette)} onClick={() => void resolveAutonomousGate(gate.id, 'approve')} disabled={busy}>
                              <CheckCircle2 size={14} />
                              Approve
                            </button>
                            <button type="button" style={styles.iconTextButton(palette)} onClick={() => void resolveAutonomousGate(gate.id, 'reject')} disabled={busy}>
                              <X size={14} />
                              Reject
                            </button>
                          </div>
                        ) : (
                          <span style={styles.eventTime(palette)}>{formatStatusLabel(gate.status)}</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>
            </div>

            <div style={styles.surfaceColumns}>
              <section style={styles.settingsSection(palette)}>
                <div style={styles.sectionHeaderInline}>
                  <h3 style={styles.settingsHeading(palette)}>Verification</h3>
                  <span style={styles.contextTag(palette)}>{detail.verification.length} signal(s)</span>
                </div>
                <div style={styles.eventList}>
                  {detail.verification.slice(0, 10).map((signal) => (
                    <div key={signal.id} style={styles.eventRow(palette, verificationStatus(signal.status))}>
                      <div>
                        <strong style={styles.eventTitle(palette)}>{formatStatusLabel(signal.kind)}</strong>
                        <div style={styles.eventDetail(palette)}>{signal.detail || signal.command}</div>
                      </div>
                      <span style={styles.eventTime(palette)}>{formatStatusLabel(signal.status)}</span>
                    </div>
                  ))}
                  {!detail.verification.length ? <div style={styles.emptyPanel(palette)}>Verification signals will appear after validation and review phases.</div> : null}
                </div>
              </section>

              <section style={styles.settingsSection(palette)}>
                <div style={styles.sectionHeaderInline}>
                  <h3 style={styles.settingsHeading(palette)}>Explainability</h3>
                  <span style={styles.contextTag(palette)}>{detail.explanations.length} note(s)</span>
                </div>
                <div style={styles.eventList}>
                  {detail.explanations.slice(0, 10).map((entry) => (
                    <div key={entry.id} style={styles.eventRow(palette, 'ok')}>
                      <div>
                        <strong style={styles.eventTitle(palette)}>{entry.title}</strong>
                        <div style={styles.eventDetail(palette)}>{entry.detail}</div>
                        <span style={styles.contextTag(palette)}>{formatStatusLabel(entry.category)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          </>
        ) : null}

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Engineering Analytics</h3>
              <span style={styles.contextTag(palette)}>{snapshot?.analytics.length ?? 0} metric(s)</span>
            </div>
            <div style={styles.eventList}>
              {(snapshot?.analytics ?? []).map((metric) => (
                <div key={metric.name} style={styles.eventRow(palette, reliabilityStatusToEventStatus(metric.status))}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{formatStatusLabel(metric.name)}</strong>
                    <div style={styles.eventDetail(palette)}>{metric.detail}</div>
                  </div>
                  <span style={styles.eventTime(palette)}>{metricLabel(metric)}</span>
                </div>
              ))}
            </div>
          </section>

          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Goal Memory</h3>
              <span style={styles.contextTag(palette)}>{objective?.goal_memory.remaining_work.length ?? 0} remaining</span>
            </div>
            <div style={styles.eventList}>
              {(objective?.goal_memory.successful_patterns ?? []).slice(0, 6).map((item) => (
                <div key={item} style={styles.eventRow(palette, 'ok')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>Successful pattern</strong>
                    <div style={styles.eventDetail(palette)}>{item}</div>
                  </div>
                </div>
              ))}
              {(objective?.goal_memory.remaining_work ?? snapshot?.recommendations ?? []).slice(0, 6).map((item) => (
                <div key={item} style={styles.eventRow(palette, 'warning')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>Remaining work</strong>
                    <div style={styles.eventDetail(palette)}>{item}</div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    );
  }

  function renderAgentsSurface() {
    return (
      <div style={styles.surfacePage}>
        {renderSurfaceHeader(
          <Bot size={22} />,
          'Agents',
          'Use the default coding agent or create focused agent perspectives for review, architecture, repair, and planning.',
          <button type="button" style={styles.primaryButton(palette)} onClick={() => openSettings('agents')}>
            <Settings size={16} />
            Agent settings
          </button>
        )}

        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <h3 style={styles.settingsHeading(palette)}>Current Agent</h3>
            <div style={styles.agentHero(palette)}>
              <div style={styles.avatar(palette, false)}>
                <Bot size={16} />
              </div>
              <div>
                <div style={styles.cardTitle(palette)}>{assistantName}</div>
                <div style={styles.eventDetail(palette)}>{assistantMission || defaultAgentPerspective}</div>
                <div style={styles.tagWrap}>
                  <span style={styles.contextTag(palette)}>{formatStatusLabel(mode)}</span>
                  <span style={styles.contextTag(palette)}>{modelName}</span>
                  <span style={styles.contextTag(palette)}>{applyChanges ? 'Auto-apply on' : 'Manual apply'}</span>
                </div>
              </div>
            </div>

            <button
              type="button"
              style={styles.secondaryButton(palette)}
              onClick={() => void activateDefaultAgent()}
              disabled={activeAgentId === defaultAgentId && assistantName === assistantIdentity}
            >
              <Bot size={16} />
              Use {assistantIdentity}
            </button>
            {saveStatus ? <div style={styles.inlineStatus(palette)}>{saveStatus}</div> : null}
          </section>

          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>{editingAgentId ? 'Edit Agent' : 'Create Agent'}</h3>
              {editingAgentId ? (
                <button type="button" style={styles.iconTextButton(palette)} onClick={cancelAgentEdit}>
                  <X size={14} />
                  Cancel edit
                </button>
              ) : null}
            </div>
            <label style={styles.fieldLabel(palette)}>
              <span>Name</span>
              <input
                value={agentFormName}
                onChange={(event) => setAgentFormName(event.target.value)}
                style={styles.fieldInput(palette)}
                aria-label="Agent name"
              />
            </label>
            <label style={styles.fieldLabel(palette)}>
              <span>Perspective</span>
              <textarea
                value={agentFormPerspective}
                onChange={(event) => setAgentFormPerspective(event.target.value)}
                rows={3}
                style={styles.fieldTextarea(palette)}
                aria-label="Agent perspective"
              />
            </label>
            <label style={styles.fieldLabel(palette)}>
              <span>Mission</span>
              <textarea
                value={agentFormMission}
                onChange={(event) => setAgentFormMission(event.target.value)}
                rows={3}
                style={styles.fieldTextarea(palette)}
                aria-label="Agent mission"
              />
            </label>
            <div style={styles.formGridTwo}>
              <label style={styles.fieldLabel(palette)}>
                <span>Mode</span>
                <select
                  value={agentFormMode}
                  onChange={(event) => setAgentFormMode(event.target.value as Mode)}
                  style={styles.fieldInput(palette)}
                  aria-label="Agent mode"
                >
                  {modeChoices.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label style={styles.fieldLabel(palette)}>
                <span>Preferred Model</span>
                <select
                  value={agentFormModelName}
                  onChange={(event) => setAgentFormModelName(event.target.value)}
                  style={styles.fieldInput(palette)}
                  aria-label="Agent preferred model"
                >
                  <option value={modelName}>{modelName}</option>
                  {selectableModelOptions.map((item) => (
                    <option key={`agent-model-${modelOptionKey(item)}`} value={item.name}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <button type="button" style={styles.primaryButton(palette)} onClick={saveAgentForm}>
              <MessageSquarePlus size={16} />
              {editingAgentId ? 'Save and activate' : 'Create and activate'}
            </button>
          </section>
        </div>

        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>Saved Agents</h3>
            <div style={styles.searchWrap(palette)}>
              <Search size={16} />
              <input
                value={agentSearch}
                onChange={(event) => setAgentSearch(event.target.value)}
                placeholder="Search agents"
                aria-label="Search agents"
                style={styles.searchInput(palette)}
              />
            </div>
          </div>
          {customAgents.length ? (
            <div style={styles.modelList}>
              {visibleCustomAgents.map((agent) => (
                <div key={agent.id} style={styles.modelRow(palette, activeAgentId === agent.id)}>
                  <div style={styles.modelRowMain}>
                    <div style={styles.modelRowTop}>
                      <div style={styles.cardTitle(palette)}>{agent.name}</div>
                      {activeAgentId === agent.id ? <span style={styles.goodTag(palette)}>Active</span> : null}
                    </div>
                    <div style={styles.eventDetail(palette)}>{agent.perspective}</div>
                    <div style={styles.tagWrap}>
                      <span style={styles.contextTag(palette)}>{formatStatusLabel(agent.mode)}</span>
                      <span style={styles.contextTag(palette)}>{agent.modelName || modelName}</span>
                      <span style={styles.contextTag(palette)}>{formatDateTime(agent.createdAt)}</span>
                    </div>
                  </div>
                  <div style={styles.rowActions}>
                    <button
                      type="button"
                      style={styles.iconTextButton(palette)}
                      onClick={() => void activateCustomAgent(agent)}
                      disabled={activeAgentId === agent.id}
                    >
                      <CheckCircle2 size={14} />
                      {activeAgentId === agent.id ? 'Active' : 'Activate'}
                    </button>
                    <button
                      type="button"
                      style={styles.iconTextButton(palette)}
                      onClick={() => editCustomAgent(agent)}
                      aria-label={`Edit agent ${agent.name}`}
                    >
                      <Settings size={14} />
                      Edit
                    </button>
                    <button type="button" style={styles.iconTextButton(palette)} onClick={() => deleteCustomAgent(agent)}>
                      <Trash2 size={14} />
                      Delete
                    </button>
                  </div>
                </div>
              ))}
              {!visibleCustomAgents.length ? (
                <div style={styles.emptyPanel(palette)}>No saved agents matched that filter.</div>
              ) : null}
            </div>
          ) : (
            <div style={styles.emptyPanel(palette)}>No custom agents yet.</div>
          )}
        </section>
      </div>
    );
  }

  function renderModelsSurface() {
    const installedCount = modelManager?.installed_total ?? modelInventory?.models.filter((item) => item.available).length ?? 0;
    const localCount = modelManager?.local_total ?? modelInventory?.models.filter((item) => item.local).length ?? 0;
    const cloudCount = modelManager?.cloud_total ?? 0;
    const pullableCount = modelManager?.pullable_total ?? 0;

    return (
      <div style={styles.surfacePage}>
        {renderSurfaceHeader(
          <Brain size={22} />,
          'Models',
          modelInventory?.message || modelManager?.message || 'Local and configured model targets will appear here.',
          <div style={styles.tagWrap}>
            <button type="button" style={styles.secondaryButton(palette)} onClick={() => void refreshModelCatalog()}>
              {modelCatalogLoading ? <Loader2 size={16} className="spin" /> : <Zap size={16} />}
              Refresh
            </button>
            <button type="button" style={styles.primaryButton(palette)} onClick={() => openSettings('models')}>
              <Settings size={16} />
              Model settings
            </button>
          </div>
        )}

        <div style={styles.metricGrid}>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Installed</span>
            <strong style={styles.metricValue(palette)}>{installedCount}</strong>
          </div>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Local targets</span>
            <strong style={styles.metricValue(palette)}>{localCount}</strong>
          </div>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Cloud targets</span>
            <strong style={styles.metricValue(palette)}>{cloudCount}</strong>
          </div>
          <div style={styles.metricCard(palette)}>
            <span style={styles.metricLabel(palette)}>Pullable</span>
            <strong style={styles.metricValue(palette)}>{pullableCount}</strong>
          </div>
        </div>

        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>Active Model</h3>
            <span style={styles.goodTag(palette)}>{modelReady ? 'Ready' : 'Needs attention'}</span>
          </div>
          <div style={styles.workspaceMeta(palette)}>
            <strong>Name</strong>
            <span>{modelName}</span>
            <strong>API</strong>
            <span>{modelApi}</span>
            <strong>Endpoint</strong>
            <span>{modelEndpoint}</span>
          </div>
          <div style={styles.formGridTwo}>
            <Suspense fallback={<div style={styles.emptyPanel(palette)}>Loading model selector...</div>}>
              <ModelSelector
                label="Switch Model"
                value={{ api: modelApi, endpoint: modelEndpoint, name: modelName }}
                options={selectableModelOptions}
                onSelect={selectModelDraft}
                labelStyle={styles.fieldLabel(palette)}
                selectStyle={styles.fieldInput(palette)}
                optionKeyPrefix="surface-model"
                renderOptionLabel={(item) => `${item.name} ${item.active ? '(active)' : ''}`}
              />
            </Suspense>
            <div style={styles.fieldButtonSlot}>
              <button
                type="button"
                style={styles.primaryButton(palette)}
                onClick={() => void activateModelTarget({ api: modelApi, endpoint: modelEndpoint, name: modelName, label: modelName })}
                disabled={Boolean(modelActionName)}
              >
                {modelActionName === modelName ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
                Save active model
              </button>
            </div>
          </div>
          {modelCatalogStatus ? <div style={styles.inlineStatus(palette)}>{modelCatalogStatus}</div> : null}
        </section>

        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>Model Catalog</h3>
            <div style={styles.searchWrap(palette)}>
              <Search size={16} />
              <input
                value={modelSearch}
                onChange={(event) => setModelSearch(event.target.value)}
                placeholder="Search models"
                style={styles.searchInput(palette)}
              />
            </div>
          </div>
          <div style={styles.modelList}>
            {visibleManagedModels.slice(0, 80).map((item) => renderModelRow(item))}
            {!visibleManagedModels.length ? (
              <div style={styles.emptyPanel(palette)}>
                {modelCatalogLoading ? 'Loading models...' : modelCatalogStatus || 'No models matched this filter.'}
              </div>
            ) : null}
          </div>
        </section>

        {modelManager?.operations.length ? (
          <section style={styles.settingsSection(palette)}>
            <h3 style={styles.settingsHeading(palette)}>Recent Model Operations</h3>
            <div style={styles.eventList}>
              {modelManager.operations.slice(0, 6).map((operation) => (
                <div key={operation.id || `${operation.action}-${operation.model_name}`} style={styles.eventRow(palette, operation.status === 'failed' ? 'error' : 'ok')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{operation.action} / {operation.model_name}</strong>
                    <div style={styles.eventDetail(palette)}>{operation.message || operation.status}</div>
                  </div>
                  <span style={styles.eventTime(palette)}>{formatDateTime(operation.started_at)}</span>
                </div>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    );
  }

  function renderModelRow(item: ManagedModelInfo) {
    const active = item.active || item.name === modelName;
    const canActivate = active || item.installed || item.configured;
    const busy = modelActionName === item.name;
    const statusLabel = active
      ? 'Active'
      : item.installed
        ? 'Installed'
        : item.pullable
          ? 'Pullable'
          : item.configured
            ? 'Configured'
            : item.health || 'Unavailable';

    return (
      <div key={`${item.provider_id}-${item.name}`} style={styles.modelRow(palette, active)}>
        <div style={styles.modelRowMain}>
          <div style={styles.modelRowTop}>
            <div style={styles.cardTitle(palette)}>{item.name}</div>
            <span style={active ? styles.goodTag(palette) : styles.contextTag(palette)}>{statusLabel}</span>
          </div>
          <div style={styles.eventDetail(palette)}>{item.label || item.provider_id}</div>
          <div style={styles.tagWrap}>
            <span style={styles.contextTag(palette)}>{item.local ? 'Local' : 'Cloud'}</span>
            <span style={styles.contextTag(palette)}>{item.api}</span>
            {item.size_bytes ? <span style={styles.contextTag(palette)}>{formatBytes(item.size_bytes)}</span> : null}
            {item.roles.slice(0, 4).map((role) => (
              <span key={`${item.provider_id}-${item.name}-role-${role}`} style={styles.contextTag(palette)}>
                {role}
              </span>
            ))}
            {item.capabilities.slice(0, 4).map((capability) => (
              <span key={`${item.provider_id}-${item.name}-cap-${capability}`} style={styles.contextTag(palette)}>
                {capability}
              </span>
            ))}
          </div>
          {item.notes ? <div style={styles.previewMeta(palette)}>{item.notes}</div> : null}
        </div>
        <div style={styles.rowActions}>
          <button
            type="button"
            style={styles.iconTextButton(palette)}
            onClick={() => void activateModelTarget(item)}
            disabled={!canActivate || active || busy}
            title={canActivate ? `Use ${item.name}` : item.health || 'Model is not ready'}
          >
            {busy ? <Loader2 size={14} className="spin" /> : <CheckCircle2 size={14} />}
            {active ? 'Active' : 'Use'}
          </button>
          {item.pullable ? (
            <button
              type="button"
              style={styles.iconTextButton(palette)}
              onClick={() => void pullManagedModel(item)}
              disabled={busy}
            >
              {busy ? <Loader2 size={14} className="spin" /> : <Download size={14} />}
              Pull
            </button>
          ) : null}
          {item.local && item.installed && !active ? (
            <button
              type="button"
              style={styles.iconTextButton(palette)}
              onClick={() => void deleteManagedModel(item)}
              disabled={busy}
            >
              {busy ? <Loader2 size={14} className="spin" /> : <Trash2 size={14} />}
              Remove
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  function renderHeaderModelSwitcher() {
    const installedCount = modelManager?.installed_total ?? modelInventory?.models.filter((item) => item.available).length ?? 0;

    return (
      <div style={styles.modelSwitcher} data-model-switcher>
        <button
          type="button"
          style={styles.modelPill(palette, showModelSwitcher)}
          onClick={toggleModelSwitcher}
          aria-label="Open model switcher"
          aria-expanded={showModelSwitcher}
        >
          <Zap size={14} />
          <span style={styles.modelPillLabel}>{modelName || 'Model'}</span>
          <ChevronDown size={14} />
        </button>

        {showModelSwitcher ? (
          <div style={styles.modelMenu(palette)} data-testid="model-switcher-menu">
            <div style={styles.modelMenuHeader(palette)}>
              <div>
                <strong>Models</strong>
                <div style={styles.eventDetail(palette)}>
                  {modelCatalogLoading
                    ? 'Refreshing installed models...'
                    : `${installedCount} installed / ${selectableModelOptions.length} available`}
                </div>
              </div>
              <button
                type="button"
                style={styles.iconTextButton(palette)}
                onClick={() => void refreshModelCatalog()}
                aria-label="Refresh header model catalog"
              >
                {modelCatalogLoading ? <Loader2 size={14} className="spin" /> : <Zap size={14} />}
                Refresh
              </button>
            </div>

            <div style={styles.modelMenuList}>
              {quickModelOptions.map((item) => {
                const active = modelOptionKey(item) === activeModelKey || item.active;
                const busy = modelActionName === item.name;
                const canActivate = active || item.installed || item.configured;
                return (
                  <button
                    key={`header-model-${modelOptionKey(item)}`}
                    type="button"
                    style={styles.modelMenuRow(palette, active)}
                    onClick={() => void activateModelTarget(item)}
                    disabled={active || busy || !canActivate}
                    aria-label={active ? `Active model ${item.name}` : `Use model ${item.name}`}
                    data-testid={`quick-model-${item.name}`}
                  >
                    <div>
                      <div style={styles.modelMenuName(palette)}>
                        {item.name}
                        {active ? <span style={styles.goodTag(palette)}>Active</span> : null}
                      </div>
                      <div style={styles.eventDetail(palette)}>
                        {item.local ? 'Local' : 'Cloud'} / {item.api}
                        {item.size_bytes ? ` / ${formatBytes(item.size_bytes)}` : ''}
                      </div>
                    </div>
                    {busy ? <Loader2 size={16} className="spin" /> : <CheckCircle2 size={16} />}
                  </button>
                );
              })}
              {!quickModelOptions.length ? (
                <div style={styles.emptyPanel(palette)}>
                  {modelCatalogLoading ? 'Loading models...' : 'No installed or configured models found yet.'}
                </div>
              ) : null}
            </div>

            <div style={styles.modelMenuFooter(palette)}>
              <button
                type="button"
                style={styles.secondaryButton(palette)}
                onClick={() => {
                  setShowModelSwitcher(false);
                  openSettings('models');
                }}
              >
                <Settings size={16} />
                Model settings
              </button>
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  function renderSettingsModal() {
    const tabs: Array<{ id: SettingsTab; label: string; icon: ReactNode }> = [
      { id: 'general', label: 'General', icon: <Settings size={18} /> },
      { id: 'models', label: 'Models', icon: <Brain size={18} /> },
      { id: 'agents', label: 'Agents', icon: <Bot size={18} /> },
      { id: 'workspace', label: 'Workspace', icon: <FolderOpen size={18} /> },
      { id: 'advanced', label: 'Advanced', icon: <Wrench size={18} /> }
    ];

    return (
      <div style={styles.modalOverlay} onClick={closeSettings}>
        <div style={styles.modalCard(palette)} onClick={(event) => event.stopPropagation()}>
          <div style={styles.modalHeader(palette)}>
            <h3 style={styles.modalTitle(palette)}>Settings</h3>
            <button type="button" style={styles.closeButton(palette)} onClick={closeSettings} aria-label="Close settings">
              <X size={18} />
            </button>
          </div>

          <div style={styles.settingsShell(narrowLayout)}>
            <aside style={styles.settingsRail(palette, narrowLayout)} aria-label="Settings sections">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  style={styles.settingsTabButton(palette, settingsTab === tab.id, narrowLayout)}
                  onClick={() => {
                    setSettingsTab(tab.id);
                    if (tab.id === 'models') void refreshModelCatalog();
                  }}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </aside>
            <div style={styles.settingsPane}>
              {renderSettingsTabContent()}
            </div>
          </div>

          <div style={styles.modalFooter}>
            <button type="button" style={styles.secondaryButton(palette)} onClick={closeSettings}>
              Cancel
            </button>
            <button type="button" style={styles.primaryButton(palette)} onClick={() => void saveAegisSettings()}>
              <Save size={16} />
              Save Settings
            </button>
          </div>

          {saveStatus || modelCatalogStatus ? (
            <div style={styles.saveStatus(palette)}>{saveStatus || modelCatalogStatus}</div>
          ) : null}
        </div>
      </div>
    );
  }

  function renderSettingsTabContent() {
    if (settingsTab === 'models') return renderModelSettings();
    if (settingsTab === 'agents') return renderAgentSettings();
    if (settingsTab === 'workspace') return renderWorkspaceSettings();
    if (settingsTab === 'advanced') return renderAdvancedSettings();
    return renderGeneralSettings();
  }

  function renderGeneralSettings() {
    return (
      <>
        <section style={styles.settingsSection(palette)}>
          <h4 style={styles.settingsHeading(palette)}>General</h4>
          <div style={styles.settingsRow(palette)}>
            <div>
              <div style={styles.cardTitle(palette)}>Appearance</div>
              <div style={styles.eventDetail(palette)}>Controls the app theme.</div>
            </div>
            <button type="button" style={styles.secondaryButton(palette)} onClick={() => setIsDarkMode((current) => !current)}>
              {isDarkMode ? <Moon size={16} /> : <Sun size={16} />}
              {isDarkMode ? 'Dark' : 'Light'}
            </button>
          </div>
          <div style={styles.settingsRow(palette)}>
            <div>
              <div style={styles.cardTitle(palette)}>Default Mode</div>
              <div style={styles.eventDetail(palette)}>Build and repair work now runs from chat prompts automatically.</div>
            </div>
            <select value={mode} onChange={(event) => setMode(event.target.value as Mode)} style={styles.fieldInput(palette)}>
              {modeChoices.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
        </section>

        <section style={styles.settingsSection(palette)}>
          <h4 style={styles.settingsHeading(palette)}>Assistant</h4>
          <label style={styles.fieldLabel(palette)}>
            <span>Name</span>
            <input value={assistantName} onChange={(event) => setAssistantName(event.target.value)} style={styles.fieldInput(palette)} />
          </label>
          <label style={styles.fieldLabel(palette)}>
            <span>Mission</span>
            <textarea
              value={assistantMission}
              onChange={(event) => setAssistantMission(event.target.value)}
              rows={4}
              style={styles.fieldTextarea(palette)}
            />
          </label>
        </section>

        {config ? (
          <section style={styles.settingsSection(palette)}>
            <h4 style={styles.settingsHeading(palette)}>Runtime Diagnostics</h4>
            <div style={styles.workspaceMeta(palette)}>
              <strong>Engine</strong>
              <span>{config.engine}</span>
              <strong>Database</strong>
              <span>{config.database_path}</span>
              <strong>Project</strong>
              <span>{lastHealth?.project_root || 'Health check pending'}</span>
            </div>
            <div style={styles.eventList}>
              {runtimeDiagnostics.checks.map((check) => (
                <div key={check.id} style={styles.eventRow(palette, diagnosticStatusToEventStatus(check.status))}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>{check.label}</strong>
                    <div style={styles.eventDetail(palette)}>{check.detail}</div>
                  </div>
                  {renderRuntimeDiagnosticAction(check)}
                </div>
              ))}
            </div>
          </section>
        ) : null}

        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h4 style={styles.settingsHeading(palette)}>Checkpoints</h4>
            <button
              type="button"
              style={styles.iconTextButton(palette)}
              onClick={() => void refreshCheckpoints()}
              disabled={checkpointLoading || !workspaceRoot.trim()}
              aria-label="Refresh checkpoints"
            >
              {checkpointLoading ? <Loader2 size={14} className="spin" /> : <Zap size={14} />}
              Refresh
            </button>
          </div>
          {checkpoints.length ? (
            <div style={styles.eventList}>
              {checkpoints.slice(0, 5).map((checkpoint) => (
                <div key={`general-${checkpoint.id}`} style={styles.eventRow(palette, 'warning')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>
                      {checkpoint.created_at ? formatDateTime(checkpoint.created_at) : checkpoint.id}
                    </strong>
                    <div style={styles.eventDetail(palette)}>
                      {checkpoint.file_count} tracked / {checkpoint.present_count} saved / {checkpoint.missing_count} new
                    </div>
                  </div>
                  <button
                    type="button"
                    style={styles.iconTextButton(palette)}
                    onClick={() => void restoreWorkspaceCheckpoint(checkpoint)}
                    disabled={loading || Boolean(restoringCheckpointId)}
                    aria-label={`Restore checkpoint ${checkpoint.id}`}
                  >
                    {restoringCheckpointId === checkpoint.id ? <Loader2 size={14} className="spin" /> : <Wrench size={14} />}
                    Restore
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div style={styles.emptyPanel(palette)}>{checkpointStatus || 'No checkpoints have been created for this workspace yet.'}</div>
          )}
        </section>
      </>
    );
  }

  function renderModelSettings() {
    return (
      <>
        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h4 style={styles.settingsHeading(palette)}>Model Selection</h4>
            <button type="button" style={styles.iconTextButton(palette)} onClick={() => void refreshModelCatalog()}>
              {modelCatalogLoading ? <Loader2 size={14} className="spin" /> : <Zap size={14} />}
              Refresh
            </button>
          </div>
          <Suspense fallback={<div style={styles.emptyPanel(palette)}>Loading model selector...</div>}>
            <ModelSelector
              label="Installed / Configured Model"
              value={{ api: modelApi, endpoint: modelEndpoint, name: modelName }}
              options={selectableModelOptions}
              onSelect={selectModelDraft}
              labelStyle={styles.fieldLabel(palette)}
              selectStyle={styles.fieldInput(palette)}
              optionKeyPrefix="settings-model"
              renderOptionLabel={(item) => `${item.name} / ${item.api}`}
            />
          </Suspense>
          <div style={styles.formGridTwo}>
            <label style={styles.fieldLabel(palette)}>
              <span>API Type</span>
              <select value={modelApi} onChange={(event) => setModelApi(event.target.value)} style={styles.fieldInput(palette)}>
                <option value="ollama">Ollama (Local)</option>
                <option value="openai">OpenAI Compatible</option>
                <option value="lmstudio">LM Studio</option>
                <option value="openai-compatible">Generic OpenAI-compatible</option>
              </select>
            </label>
            <label style={styles.fieldLabel(palette)}>
              <span>Model Name</span>
              <input value={modelName} onChange={(event) => setModelName(event.target.value)} style={styles.fieldInput(palette)} />
            </label>
          </div>
          <label style={styles.fieldLabel(palette)}>
            <span>Endpoint</span>
            <input value={modelEndpoint} onChange={(event) => setModelEndpoint(event.target.value)} style={styles.fieldInput(palette)} />
          </label>
          <div style={styles.tagWrap}>
            <span style={styles.contextTag(palette)}>{modelInventory?.models.length ?? 0} discovered</span>
            <span style={styles.contextTag(palette)}>{modelManager?.installed_total ?? 0} installed</span>
            <span style={styles.contextTag(palette)}>{modelManager?.pullable_total ?? 0} pullable</span>
            {modelManager?.disk ? <span style={styles.contextTag(palette)}>{formatBytes(modelManager.disk.free_bytes)} free</span> : null}
          </div>
        </section>

        <section style={styles.settingsSection(palette)}>
          <h4 style={styles.settingsHeading(palette)}>Available Models</h4>
          <div style={styles.searchWrap(palette)}>
            <Search size={16} />
            <input value={modelSearch} onChange={(event) => setModelSearch(event.target.value)} placeholder="Search models" style={styles.searchInput(palette)} />
          </div>
          <div style={styles.modelList}>
            {visibleManagedModels.slice(0, 20).map((item) => renderModelRow(item))}
            {!visibleManagedModels.length ? <div style={styles.emptyPanel(palette)}>No models loaded yet.</div> : null}
          </div>
        </section>
      </>
    );
  }

  function renderAgentSettings() {
    return (
      <>
        <section style={styles.settingsSection(palette)}>
          <h4 style={styles.settingsHeading(palette)}>Active Agent</h4>
          <div style={styles.agentHero(palette)}>
            <div style={styles.avatar(palette, false)}>
              <Bot size={16} />
            </div>
            <div>
              <div style={styles.cardTitle(palette)}>{assistantName}</div>
              <div style={styles.eventDetail(palette)}>{assistantMission || defaultAgentPerspective}</div>
            </div>
          </div>
          <button type="button" style={styles.secondaryButton(palette)} onClick={() => setActiveSection('agents')}>
            <Bot size={16} />
            Open agent workspace
          </button>
        </section>
        <section style={styles.settingsSection(palette)}>
          <h4 style={styles.settingsHeading(palette)}>Saved Agents</h4>
          {customAgents.length ? (
            <div style={styles.modelList}>
              {customAgents.map((agent) => (
                <div key={`settings-${agent.id}`} style={styles.compactCard(palette)}>
                  <div>
                    <div style={styles.cardTitle(palette)}>{agent.name}</div>
                    <div style={styles.eventDetail(palette)}>{agent.perspective}</div>
                  </div>
                  <button type="button" style={styles.iconTextButton(palette)} onClick={() => void activateCustomAgent(agent)}>
                    <CheckCircle2 size={14} />
                    Activate
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div style={styles.emptyPanel(palette)}>Create agents from the Agents section.</div>
          )}
        </section>
      </>
    );
  }

  function renderWorkspaceSettings() {
    return (
      <>
        <section style={styles.settingsSection(palette)}>
          <h4 style={styles.settingsHeading(palette)}>Workspace</h4>
          <label style={styles.fieldLabel(palette)}>
            <span>Root Directory</span>
            <input value={workspaceRoot} onChange={(event) => setActiveWorkspaceRoot(event.target.value)} style={styles.fieldInput(palette)} />
          </label>
          <label style={styles.checkboxLabel(palette)}>
            <input type="checkbox" checked={autoRunValidation} onChange={(event) => setAutoRunValidation(event.target.checked)} />
            <span>Auto-run validation after file changes</span>
          </label>
          <div style={styles.tagWrap}>
            <button type="button" style={styles.secondaryButton(palette)} onClick={() => void setupCurrentWorkspace()} disabled={workspaceSetupLoading || !workspaceRoot}>
              {workspaceSetupLoading ? <Loader2 size={16} className="spin" /> : <Wrench size={16} />}
              Set up workspace
            </button>
            <button type="button" style={styles.secondaryButton(palette)} onClick={() => void refreshFiles()}>
              <FolderOpen size={16} />
              Refresh files
            </button>
            <button type="button" style={styles.secondaryButton(palette)} onClick={() => void validateNow()} disabled={loading || !workspaceRoot}>
              {loading ? <Loader2 size={16} className="spin" /> : <Play size={16} />}
              Validate
            </button>
          </div>
        </section>

        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h4 style={styles.settingsHeading(palette)}>Checkpoints</h4>
            <button
              type="button"
              style={styles.iconTextButton(palette)}
              onClick={() => void refreshCheckpoints()}
              disabled={checkpointLoading || !workspaceRoot.trim()}
              aria-label="Refresh checkpoints"
            >
              {checkpointLoading ? <Loader2 size={14} className="spin" /> : <Zap size={14} />}
              Refresh
            </button>
          </div>
          {checkpoints.length ? (
            <div style={styles.eventList}>
              {checkpoints.slice(0, 6).map((checkpoint) => (
                <div key={checkpoint.id} style={styles.eventRow(palette, 'warning')}>
                  <div>
                    <strong style={styles.eventTitle(palette)}>
                      {checkpoint.created_at ? formatDateTime(checkpoint.created_at) : checkpoint.id}
                    </strong>
                    <div style={styles.eventDetail(palette)}>
                      {checkpoint.file_count} tracked / {checkpoint.present_count} saved / {checkpoint.missing_count} new
                    </div>
                  </div>
                  <button
                    type="button"
                    style={styles.iconTextButton(palette)}
                    onClick={() => void restoreWorkspaceCheckpoint(checkpoint)}
                    disabled={loading || Boolean(restoringCheckpointId)}
                    aria-label={`Restore checkpoint ${checkpoint.id}`}
                  >
                    {restoringCheckpointId === checkpoint.id ? <Loader2 size={14} className="spin" /> : <Wrench size={14} />}
                    Restore
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div style={styles.emptyPanel(palette)}>{checkpointStatus || 'No checkpoints have been created for this workspace yet.'}</div>
          )}
        </section>
      </>
    );
  }

  function renderAdvancedSettings() {
    return (
      <>
        <section style={styles.settingsSection(palette)}>
          <h4 style={styles.settingsHeading(palette)}>Command Runner</h4>
          <label style={styles.fieldLabel(palette)}>
            <span>Command Allowlist</span>
            <input value={commandAllowlist} onChange={(event) => setCommandAllowlist(event.target.value)} style={styles.fieldInput(palette)} />
          </label>
          <div style={styles.formGridTwo}>
            <label style={styles.fieldLabel(palette)}>
              <span>Command Timeout (seconds)</span>
              <input
                type="number"
                min={5}
                value={commandTimeout}
                onChange={(event) => setCommandTimeout(Number(event.target.value) || 120)}
                style={styles.fieldInput(palette)}
              />
            </label>
            <label style={styles.fieldLabel(palette)}>
              <span>Max Repair Retries</span>
              <input
                type="number"
                min={0}
                max={5}
                value={maxRetries}
                onChange={(event) => setMaxRetries(Number(event.target.value) || 0)}
                style={styles.fieldInput(palette)}
              />
            </label>
          </div>
          <button type="button" style={styles.secondaryButton(palette)} onClick={() => setShowApprovalSettings(true)}>
            <Wrench size={16} />
            Approval settings
          </button>
        </section>

        <section style={styles.settingsSection(palette)}>
          <h4 style={styles.settingsHeading(palette)}>Backend</h4>
          <div style={styles.workspaceMeta(palette)}>
            <strong>Engine</strong>
            <span>{config?.engine || engineLabel}</span>
            <strong>Database</strong>
            <span>{config?.database_path || 'Unknown'}</span>
            <strong>Project</strong>
            <span>{lastHealth?.project_root || 'Health check pending'}</span>
          </div>
          <button type="button" style={styles.secondaryButton(palette)} onClick={() => void refreshRuntimeDiagnostics()}>
            <Zap size={16} />
            Refresh diagnostics
          </button>
        </section>
      </>
    );
  }

  const routeIsProtected = isProtectedAppRoute(routePath);
  if (!routeIsProtected) {
    return (
      <LazyPanelBoundary
        title={`${productName} website could not load`}
        detail="The public site surface failed to initialize. Retry or reload when the runtime settles."
        resetKey={routePath}
        style={styles.routeBoundary}
      >
        <Suspense fallback={<div style={styles.routeFallback(palette)}>Loading {productName}...</div>}>
          <PublicSite
            routePath={routePath}
            authLoading={authLoading}
            authStatus={authStatus}
            onNavigate={navigateTo}
            onLogin={handleLogin}
            onRegister={handleRegister}
            onForgotPassword={handleForgotPassword}
          />
        </Suspense>
      </LazyPanelBoundary>
    );
  }

  if (!authSession) {
    return (
      <LazyPanelBoundary
        title="Secure access could not load"
        detail="The login surface failed to initialize. Retry or reload before opening the workspace."
        resetKey={routePath}
        style={styles.routeBoundary}
      >
        <Suspense fallback={<div style={styles.routeFallback(palette)}>Loading secure access...</div>}>
          <PublicSite
            routePath="/login"
            authLoading={authLoading}
            authStatus={authStatus}
            onNavigate={navigateTo}
            onLogin={handleLogin}
            onRegister={handleRegister}
            onForgotPassword={handleForgotPassword}
          />
        </Suspense>
      </LazyPanelBoundary>
    );
  }

  const accountName = authSession.user.name || 'Auralith User';
  const accountPlan = `${authSession.user.plan || 'Local'} Plan`;

  return (
    <div style={styles.appShell(palette)}>
      <div style={styles.backdrop(palette)} />
      <div style={styles.frame(compactLayout)}>
        <header style={styles.header(palette, compactLayout, narrowLayout)}>
          <div style={styles.topSearch(palette, compactLayout)} className="aegis-search-surface">
            <Search size={17} />
            <input
              value={chatSearch}
              onChange={(event) => setChatSearch(event.target.value)}
              placeholder={`Search ${productName}... (Ctrl + K)`}
              aria-label={`Search ${productName}`}
              style={styles.searchInput(palette)}
            />
          </div>

          <div style={styles.headerActions(narrowLayout)}>
            <span style={styles.topStatusPill(palette, connectionState === 'connected')}>
              <span style={styles.statusDot(palette, connectionState === 'connected')} />
              {connectionStateLabel(connectionState)}
            </span>
            {renderHeaderModelSwitcher()}
            <button
              type="button"
              style={styles.iconButton(palette)}
              onClick={() => setIsDarkMode((current) => !current)}
              title={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {isDarkMode ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <button
              type="button"
              style={styles.iconButton(palette)}
              onClick={() => setShowMemoryEditor(true)}
              title="Memory Editor"
            >
              <Brain size={18} />
            </button>
            <button
              type="button"
              style={styles.iconButton(palette)}
              onClick={() => setShowApprovalSettings(true)}
              title="Approval Settings"
            >
              <Wrench size={18} />
            </button>
            <button
              type="button"
              style={styles.iconButton(palette)}
              onClick={() => openSettings('general')}
              title="Settings"
            >
              <Settings size={18} />
            </button>
            <button
              type="button"
              style={styles.accountPill(palette)}
              onClick={handleLogout}
              title="Sign out"
            >
              <User size={16} />
              <span>{accountName}</span>
              <small style={styles.accountPlanText(palette)}>{accountPlan}</small>
            </button>
          </div>
        </header>

        <div style={styles.utilityBar(palette, compactLayout)}>
          <div style={styles.sidebarBrand}>
            <div style={styles.brandIcon(palette)}>
              <img style={styles.brandIconImage} src={brandAssets.mark} alt="" aria-hidden="true" />
            </div>
            <div>
              <div style={styles.brandTitle(palette)}>{productName}</div>
              <div style={styles.brandSubtitle(palette)}>Powered by {runtimeIdentity}</div>
            </div>
          </div>

          <div style={styles.utilityActions(compactLayout)}>
            <button
              type="button"
              className="aegis-primary-action"
              style={styles.primaryUtilityButton(palette)}
              onClick={startNewChat}
              disabled={loading}
            >
              <MessageSquarePlus size={16} />
              <span>New session</span>
            </button>
            <button
              type="button"
              style={styles.utilityActionButton(palette)}
              onClick={exportCurrentChatTranscript}
              disabled={!history.length}
              aria-label="Export session transcript"
              title="Export current session as Markdown"
            >
              <Download size={16} />
            </button>
            <button
              type="button"
              style={styles.utilityActionButton(palette)}
              onClick={() => setShowDetailsPanel((current) => !current)}
              aria-label={detailsPanelVisible ? 'Hide details panel' : 'Show details panel'}
              title={detailsPanelVisible ? 'Hide details panel' : 'Show details panel'}
            >
              <FolderOpen size={16} />
            </button>
          </div>

          <div style={styles.sidebarNav(compactLayout)}>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, activeSection === 'chat', compactLayout)}
              onClick={() => openAppSection('chat')}
              aria-label="Home"
            >
              <FolderOpen size={16} />
              Home
            </button>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, activeSection === 'projects', compactLayout)}
              onClick={() => openAppSection('projects')}
              aria-label="Projects"
            >
              <FolderOpen size={16} />
              Projects
            </button>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, activeSection === 'intelligence', compactLayout)}
              onClick={() => {
                openAppSection('intelligence');
                void refreshProjectIntelligence();
              }}
              aria-label="Project Intelligence"
            >
              <Brain size={16} />
              Intelligence
            </button>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, activeSection === 'workspace-intelligence', compactLayout)}
              onClick={() => {
                openAppSection('workspace-intelligence');
                void refreshWorkspaceOperations();
              }}
              aria-label="Workspace Intelligence"
            >
              <Zap size={16} />
              Workspace
            </button>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, activeSection === 'tasks', compactLayout)}
              onClick={() => {
                openAppSection('tasks');
                void refreshTasks();
              }}
              aria-label="Tasks"
            >
              <CheckCircle2 size={16} />
              Tasks
            </button>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, activeSection === 'runtime', compactLayout)}
              onClick={() => {
                openAppSection('runtime');
                void refreshDistributedRuntime();
              }}
              aria-label="Distributed runtime"
            >
              <Code size={16} />
              Runtime
            </button>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, activeSection === 'adaptive', compactLayout)}
              onClick={() => {
                openAppSection('adaptive');
                void refreshAdaptiveSignals();
              }}
              aria-label="Adaptive Intelligence"
            >
              <Brain size={16} />
              Adaptive
            </button>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, activeSection === 'hardening', compactLayout)}
              onClick={() => {
                openAppSection('hardening');
                void refreshProductizationSignals();
              }}
              aria-label="Productization and runtime hardening"
            >
              <Wrench size={16} />
              Hardening
            </button>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, activeSection === 'ecosystem', compactLayout)}
              onClick={() => {
                openAppSection('ecosystem');
                void refreshEcosystemSignals();
              }}
              aria-label="Ecosystem and shared intelligence"
            >
              <Brain size={16} />
              Ecosystem
            </button>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, activeSection === 'autonomous', compactLayout)}
              onClick={() => {
                openAppSection('autonomous');
                void refreshAutonomousSignals();
              }}
              aria-label="Autonomous engineering"
            >
              <Zap size={16} />
              Autonomous
            </button>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, activeSection === 'creative', compactLayout)}
              onClick={() => {
                openAppSection('creative');
                void refreshCreativeStudio();
              }}
              aria-label="Creative Studio"
            >
              <Download size={16} />
              Creative
            </button>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, activeSection === 'agents', compactLayout)}
              onClick={() => openAppSection('agents')}
              aria-label="Agents"
            >
              <Bot size={16} />
              Agents
            </button>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, activeSection === 'models', compactLayout)}
              onClick={() => {
                openAppSection('models');
                void refreshModelCatalog();
              }}
              aria-label="Models"
            >
              <Brain size={16} />
              Models
            </button>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, false, compactLayout)}
              onClick={() => openSettings('general')}
              aria-label="Open settings from sidebar"
            >
              <Settings size={16} />
              Settings
            </button>
          </div>

          <div style={styles.searchWrap(palette)}>
            <Search size={16} />
            <input
              value={chatSearch}
              onChange={(event) => setChatSearch(event.target.value)}
              placeholder="Search sessions"
              style={styles.searchInput(palette)}
            />
          </div>

          <div style={styles.sidebarSectionLabel(palette)}>Recent Sessions</div>
          <div style={styles.historyRail}>
            <button
              type="button"
              style={styles.threadPill(palette, activeThreadId === currentThreadId)}
              onClick={() => setActiveThreadId(currentThreadId)}
              title={currentThreadPreview.preview}
            >
              {currentThreadPreview.title}
            </button>

            {filteredThreads.map((thread) => (
              <div key={thread.id} style={styles.threadGroup(palette)}>
                <button
                  type="button"
                  style={styles.threadPill(palette, activeThreadId === thread.id)}
                  onClick={() => openConversation(thread)}
                  title={thread.preview}
                >
                  {thread.title}
                </button>
                <button
                  type="button"
                  style={styles.threadDeleteButton(palette)}
                  onClick={() => deleteSavedThread(thread)}
                  title={`Delete saved session ${thread.title}`}
                  aria-label={`Delete saved session ${thread.title}`}
                  disabled={loading}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>

          <div style={styles.sidebarUserCard(palette)}>
            <div style={styles.brandIcon(palette)}>
              <User size={18} />
            </div>
            <div>
              <div style={styles.sidebarUserName(palette)}>{accountName}</div>
              <div style={styles.sidebarUserPlan(palette)}>{accountPlan}</div>
            </div>
          </div>
        </div>

        <div style={styles.mainGrid(effectiveDetailsPanelVisible, compactLayout)}>
          <section style={styles.chatCard(palette)}>
            <div ref={chatScrollRef} style={styles.chatScroll} data-testid="chat-scroll">
              {activeSection === 'chat' ? (
                <>
              {history.length === 0 ? (
                <div style={styles.emptyState}>
                  <div style={styles.emptyLogo(palette)}>
                    <img style={styles.emptyLogoImage} src={brandAssets.mark} alt="" aria-hidden="true" />
                  </div>
                  <h2 style={styles.emptyTitle(palette)}>Welcome to {productName}</h2>
                  <p style={styles.emptyText(palette)}>
                    {assistantIdentity} is ready to code, automate, research, create, and orchestrate through one local-first workspace.
                  </p>

                  <div style={styles.promptGrid}>
                    {starterPrompts.map((prompt) => (
                      <button
                        key={prompt}
                        type="button"
                        className="aegis-prompt-card"
                        onClick={() => void submit(undefined, prompt)}
                        style={styles.promptCard(palette)}
                        disabled={loading}
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>

                  <div style={styles.workspaceSignalGrid} aria-label="Workspace signals">
                    <div style={styles.workspaceSignalCard(palette)}>
                      <div style={styles.workspaceSignalTop}>
                        <span style={styles.workspaceSignalIcon(palette, 'purple')}>
                          <FolderOpen size={16} />
                        </span>
                        <span style={styles.workspaceSignalLabel(palette)}>Workspace</span>
                      </div>
                      <strong style={styles.workspaceSignalValue(palette)}>
                        {workspaceRoot
                          ? workspaceRoot.split(/[\\/]/).filter(Boolean).slice(-1)[0] || workspaceRoot
                          : 'No workspace selected'}
                      </strong>
                      <span style={styles.workspaceSignalMeta(palette)}>
                        {workspaceProfile
                          ? `${formatStatusLabel(workspaceProfile.readiness.status)} / ${workspaceProfile.readiness.score}/100`
                          : workspaceProfileStatus || 'Runtime context will lock in when a workspace is active.'}
                      </span>
                    </div>

                    <div style={styles.workspaceSignalCard(palette)}>
                      <div style={styles.workspaceSignalTop}>
                        <span style={styles.workspaceSignalIcon(palette, 'blue')}>
                          <Brain size={16} />
                        </span>
                        <span style={styles.workspaceSignalLabel(palette)}>Project Context</span>
                      </div>
                      <strong style={styles.workspaceSignalValue(palette)}>
                        {projectIntelligence?.profile?.stack?.slice(0, 2).join(' / ') ||
                          workspaceProfile?.dependency_profile?.project_type ||
                          'Context map pending'}
                      </strong>
                      <span style={styles.workspaceSignalMeta(palette)}>
                        {projectIntelligence?.architecture?.major_modules?.length
                          ? `${projectIntelligence.architecture.major_modules.length} mapped modules`
                          : projectIntelligenceStatus || 'Project intelligence is ready to scan.'}
                      </span>
                    </div>

                    <div style={styles.workspaceSignalCard(palette)}>
                      <div style={styles.workspaceSignalTop}>
                        <span style={styles.workspaceSignalIcon(palette, 'green')}>
                          <CheckCircle2 size={16} />
                        </span>
                        <span style={styles.workspaceSignalLabel(palette)}>Active Flow</span>
                      </div>
                      <strong style={styles.workspaceSignalValue(palette)}>
                        {selectedTask?.title ||
                          selectedTask?.message ||
                          `${taskBoardTasks.filter((item) => !terminalTaskStatuses.has(item.status)).length} active task(s)`}
                      </strong>
                      <span style={styles.workspaceSignalMeta(palette)}>
                        {taskBoardTasks.length
                          ? `${taskBoardTasks.length} tracked workflow${taskBoardTasks.length === 1 ? '' : 's'}`
                          : 'New project work will appear as tracked tasks.'}
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                history.map((item, index) => renderChatMessage(item, index))
              )}

              {loading && (
                <div style={styles.messageRow(false)}>
                  <div style={styles.avatar(palette, false)}>
                    <Bot size={16} />
                  </div>

                  <div style={styles.messageBubble(palette, false)}>
                    <div style={styles.messageRole(palette)}>{assistantName}</div>
                    <div style={styles.thinkingInline(palette)}>
                      <Loader2 size={16} className="spin" />
                      <span>{thinkingStates[thinkingIndex]}</span>
                      {retryCount > 0 ? (
                        <span style={styles.retryBadge(palette)}>
                          Retry {retryCount}/{maxRetries}
                        </span>
                      ) : null}
                    </div>
                  </div>
                </div>
              )}
              {renderQueuedPromptStack()}
                </>
              ) : (
                renderWorkspaceSurface()
              )}
            </div>

            <div style={styles.statusRow(palette)}>
              <div style={styles.statusCluster}>
                <span style={styles.statusChip(palette, connectionState === 'connected')}>
                  <Zap size={14} />
                  Backend {connectionStateLabel(connectionState)}
                </span>
                <span style={styles.statusChip(palette, modelReady)}>
                  <Bot size={14} />
                  Model {modelReady ? 'Ready' : 'Offline'}
                </span>
                <span style={styles.diagnosticChip(palette, runtimeDiagnostics.status)}>
                  {runtimeDiagnostics.status === 'ok' ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
                  {runtimeDiagnostics.label}
                </span>
                {queuedMessages.length ? (
                  <button
                    type="button"
                    style={styles.queueButton(palette, showQueueTray)}
                    onClick={() => setShowQueueTray((current) => !current)}
                    aria-expanded={showQueueTray}
                    aria-controls="queued-message-tray"
                  >
                    <MessageSquarePlus size={14} />
                    {queuedMessages.length} queued
                  </button>
                ) : null}
              </div>

              {status ? (
                <div style={styles.errorStatus(palette)}>
                  <AlertTriangle size={14} />
                  <span>{status}</span>
                </div>
              ) : (
                <div style={styles.metaStatus(palette)}>
                  {engineLabel}
                  {queuedMessages.length ? ` - ${connectionStateDetail(connectionState)}` : ''}
                  {modelMessage ? ` - ${modelMessage}` : ''}
                </div>
              )}
            </div>

            {showQueueTray && queuedMessages.length ? (
              <div id="queued-message-tray" style={styles.queueTray(palette)} aria-label="Queued messages">
                <div style={styles.queueTrayHeader}>
                  <div>
                    <div style={styles.queueTrayTitle(palette)}>Queued prompts</div>
                    <div style={styles.queueTrayMeta(palette)}>
                      {queueAutoSendPaused ? 'Auto-send paused. Resume when you are ready.' : connectionStateDetail(connectionState)}
                    </div>
                  </div>
                  <div style={styles.queueTrayActions}>
                    <button
                      type="button"
                      style={styles.iconTextButton(palette)}
                      onClick={toggleQueueAutoSendPaused}
                      aria-label={queueAutoSendPaused ? 'Resume queued prompts' : 'Pause queued prompts'}
                    >
                      {queueAutoSendPaused ? <Play size={14} /> : <Pause size={14} />}
                      {queueAutoSendPaused ? 'Resume queue' : 'Pause queue'}
                    </button>
                    <button
                      type="button"
                      style={styles.iconTextButton(palette)}
                      onClick={clearQueuedMessageBacklog}
                      aria-label="Clear all queued messages"
                    >
                      <Trash2 size={14} />
                      Clear all
                    </button>
                    <button
                      type="button"
                      style={styles.iconButton(palette)}
                      onClick={() => setShowQueueTray(false)}
                      title="Close queued prompts"
                      aria-label="Close queued prompts"
                    >
                      <X size={16} />
                    </button>
                  </div>
                </div>

                <div style={styles.queueList}>
                  {queuedMessages.map((queued, index) => (
                    <div key={queued.id} style={styles.queueItem(palette)} data-testid={`queued-message-${index + 1}`}>
                      <div style={styles.queueItemMain}>
                        <div style={styles.queueItemTop(palette)}>
                          <span>{index + 1}</span>
                          <span>{formatEventTime(queued.createdAt)}</span>
                          <span>{formatStatusLabel(queued.mode)}</span>
                          {queued.runValidation ? <span>Validation</span> : null}
                          {queued.applyChanges ? <span>Auto-apply</span> : null}
                          {queued.contextPaths.length ? <span>{queued.contextPaths.length} context</span> : null}
                        </div>
                        <div style={styles.queueItemText(palette)}>{queued.content}</div>
                      </div>
                      <div style={styles.queueItemActions}>
                        <button
                          type="button"
                          style={styles.queueMoveButton(palette, index === 0)}
                          onClick={() => reorderQueuedMessage(queued.id, 'up')}
                          disabled={index === 0}
                          aria-label={`Move queued message ${index + 1} earlier`}
                          title="Move earlier"
                        >
                          <ArrowUp size={14} />
                        </button>
                        <button
                          type="button"
                          style={styles.queueMoveButton(palette, index === queuedMessages.length - 1)}
                          onClick={() => reorderQueuedMessage(queued.id, 'down')}
                          disabled={index === queuedMessages.length - 1}
                          aria-label={`Move queued message ${index + 1} later`}
                          title="Move later"
                        >
                          <ArrowDown size={14} />
                        </button>
                        <button
                          type="button"
                          style={styles.iconTextButton(palette)}
                          onClick={() => discardQueuedMessage(queued.id)}
                          aria-label={`Discard queued message ${index + 1}`}
                        >
                          <Trash2 size={14} />
                          Discard
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <div style={styles.composerWrap(palette)}>
              {pinnedContextPaths.length ? (
                <div style={styles.contextPinBar(palette)} aria-label="Pinned context files">
                  <div style={styles.contextPinLead(palette)}>
                    <FileCode2 size={14} />
                    Context
                  </div>
                  {pinnedContextPaths.map((path) => (
                    <span key={path} style={styles.contextPin(palette)}>
                      {path}
                      <button
                        type="button"
                        style={styles.contextPinRemove(palette)}
                        onClick={() => unpinWorkspaceFile(path)}
                        aria-label={`Remove pinned context file ${path}`}
                      >
                        <X size={12} />
                      </button>
                    </span>
                  ))}
                </div>
              ) : null}

              <div style={styles.composerOptions(palette)}>
                <div style={styles.optionGroup}>
                  <label style={styles.checkboxLabel(palette)}>
                    <input
                      type="checkbox"
                      checked={applyChanges}
                      onChange={(event) => setApplyChanges(event.target.checked)}
                    />
                    <span>Apply changes automatically</span>
                  </label>

                  <label style={styles.checkboxLabel(palette)}>
                    <input
                      type="checkbox"
                      checked={runValidation}
                      onChange={(event) => setRunValidation(event.target.checked)}
                    />
                    <span>Run validation</span>
                  </label>
                </div>

                <div style={styles.optionGroup}>
                  <button type="button" style={styles.secondaryButton(palette)} onClick={() => void refreshFiles()}>
                    <FolderOpen size={16} />
                    Refresh files
                  </button>
                  <button type="button" style={styles.secondaryButton(palette)} onClick={() => void validateNow()}>
                    <Play size={16} />
                    Validate
                  </button>
                  {activeChatRequest ? (
                    <button
                      type="button"
                      style={styles.secondaryButton(palette)}
                      onClick={stopActiveChatRequest}
                      aria-label="Stop current response"
                    >
                      <Square size={16} />
                      Stop
                    </button>
                  ) : null}
                </div>
              </div>

              <form onSubmit={submit} style={styles.composerForm}>
                <textarea
                  className="aegis-command-input"
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  placeholder={
                    composerWillQueue
                      ? `Message ${assistantIdentity}... next prompt will be queued`
                      : `Message ${assistantIdentity}...`
                  }
                  rows={2}
                  style={styles.composerInput(palette)}
                />
                <button
                  type="submit"
                  className="aegis-command-send"
                  style={styles.sendButton(palette, !message.trim())}
                  disabled={!message.trim()}
                  title={composerWillQueue ? 'Queue this prompt for the next available turn' : 'Send prompt'}
                  aria-label={composerWillQueue ? 'Queue prompt' : 'Send prompt'}
                >
                  {composerWillQueue ? <MessageSquarePlus size={18} /> : <Send size={18} />}
                </button>
              </form>
            </div>
          </section>

          {effectiveDetailsPanelVisible ? (
          <aside style={styles.sidebar} data-testid="details-panel">
            <section style={styles.panelCard(palette)}>
              <div style={styles.panelHeader(palette)}>
                <div style={styles.panelTitleWrap}>
                  <Zap size={16} />
                  <h3 style={styles.panelTitle(palette)}>Agent Activity</h3>
                </div>
                <div style={styles.panelHeaderActions}>
                  {eventLog.length > 7 || activityFilter !== 'all' ? (
                    <span style={styles.counterBadge(palette)}>{activityCounterLabel}</span>
                  ) : null}
                  <span style={styles.liveBadge(palette)}>Live</span>
                </div>
              </div>
              <div style={styles.panelBody}>
                {eventLog.length ? (
                  <div style={styles.activityFilterBar(palette)} aria-label="Activity filters">
                    {activityFilterOptions.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        style={styles.activityFilterButton(palette, activityFilter === option.value)}
                        onClick={() => selectActivityFilter(option.value)}
                        aria-label={option.ariaLabel}
                        aria-pressed={activityFilter === option.value}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                ) : null}
                <div style={styles.eventList}>
                  {eventLog.length ? (
                    visibleActivityEvents.length ? (
                      visibleActivityEvents.map((item, index) => renderActivityEvent(item, index))
                    ) : (
                      <div style={styles.emptyPanel(palette)}>No activity events match this filter.</div>
                    )
                  ) : (
                    runtimeDiagnostics.checks.slice(0, 5).map((check) => (
                      <div key={check.id} style={styles.activityRow(palette, diagnosticStatusToEventStatus(check.status))}>
                        <span style={styles.activityTime(palette)}>Now</span>
                        <div>
                          <strong style={styles.eventTitle(palette)}>{check.label}</strong>
                          <div style={styles.eventDetail(palette)}>{check.detail}</div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
                {filteredActivityEvents.length > 7 ? (
                  <button
                    type="button"
                    style={styles.activityLogToggle(palette)}
                    onClick={() => setShowAllActivityEvents((current) => !current)}
                    aria-label={showAllActivityEvents ? 'Show latest activity logs' : 'View full activity logs'}
                  >
                    {showAllActivityEvents ? 'Show latest' : `View full logs (${filteredActivityEvents.length})`}
                  </button>
                ) : null}
              </div>
            </section>

            <section style={styles.panelCard(palette)}>
              <div style={styles.panelHeader(palette)}>
                <div style={styles.panelTitleWrap}>
                  <FileCode2 size={16} />
                  <h3 style={styles.panelTitle(palette)}>Generated answer</h3>
                </div>

                <div style={styles.panelHeaderActions}>
                  {pendingChanges.length ? (
                    <span style={styles.counterBadge(palette)}>{pendingChanges.length} file(s)</span>
                  ) : null}
                  {renderPanelCollapseButton('generated', 'Generated answer')}
                </div>
              </div>

              {detailPanelCollapsed('generated') ? null : lastResponse || activeReviewSource ? (
                <div style={styles.panelBody}>
                  <div style={styles.replyCard(palette)}>
                    <div style={styles.replyText(palette)}>
                      {lastResponse?.reply ||
                        'Restored file review from this saved session. Exact line counts are rebuilt from available checkpoints and workspace files.'}
                    </div>
                  </div>

                  {lastResponse?.plan.length ? (
                    <div style={styles.sectionBlock}>
                      <div style={styles.sectionLabel(palette)}>Plan</div>
                      <ol style={styles.planList(palette)}>
                        {lastResponse.plan.map((item, index) => (
                          <li key={`${item}-${index}`}>{item}</li>
                        ))}
                      </ol>
                    </div>
                  ) : null}

                  {lastResponse?.task_plan || lastResponse?.context_budget || lastResponse?.completion_quality ? (
                    <div style={styles.sectionBlock}>
                      <div style={styles.sectionLabel(palette)}>Planning Intelligence</div>
                      <div style={styles.tagWrap}>
                        {lastResponse?.task_plan ? (
                          <>
                            <span style={styles.contextTag(palette)}>
                              scale: {lastResponse.task_plan.complexity}
                            </span>
                            <span style={styles.contextTag(palette)}>
                              slices: {lastResponse.task_plan.estimated_slices}
                            </span>
                            <span style={styles.contextTag(palette)}>
                              pass hint: {lastResponse.task_plan.pass_budget_hint}
                            </span>
                            <span style={styles.contextTag(palette)}>
                              route: {routeProfileLabel(lastResponse.task_plan)}
                            </span>
                          </>
                        ) : null}
                        {lastResponse?.context_budget ? (
                          <>
                            <span style={styles.contextTag(palette)}>
                              context: {lastResponse.context_budget.estimated_context_tokens}/
                              {lastResponse.context_budget.max_context_tokens} tokens
                            </span>
                            <span style={styles.contextTag(palette)}>
                              files: {lastResponse.context_budget.selected_file_count}/
                              {lastResponse.context_budget.max_context_files}
                            </span>
                          </>
                        ) : null}
                        {lastResponse?.completion_quality ? (
                          <span style={styles.contextTag(palette)}>
                            quality: {lastResponse.completion_quality.status} (
                            {Math.round(lastResponse.completion_quality.score * 100)}%)
                          </span>
                        ) : null}
                      </div>

                      {lastResponse?.task_plan?.decomposition_axes?.length ? (
                        <div style={styles.eventDetail(palette)}>
                          Lanes: {lastResponse.task_plan.decomposition_axes.join(' / ')}
                        </div>
                      ) : null}

                      {lastResponse?.task_plan?.large_task_protocol?.length ? (
                        <ul style={styles.warningList(palette)}>
                          {lastResponse.task_plan.large_task_protocol.slice(0, 4).map((item) => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  ) : null}

                  {pendingChanges.length ? (
                    <>
                      <div style={styles.sectionBlock}>
                        <div style={styles.sectionHeaderInline}>
                          <div style={styles.sectionLabel(palette)}>File changes</div>
                          <div style={styles.reviewSummary} data-testid="generated-change-summary">
                            <span style={styles.contextTag(palette)}>
                              {generatedChangeSummary.total} file{generatedChangeSummary.total === 1 ? '' : 's'}
                            </span>
                            <span style={styles.goodTag(palette)}>{generatedChangeSummary.applied} applied</span>
                            <span style={styles.contextTag(palette)}>
                              {generatedChangeSummary.remaining} remaining
                            </span>
                            <span style={styles.warningTag(palette)}>
                              {generatedChangeSummary.skipped} skipped
                            </span>
                          </div>
                        </div>
                        <div style={styles.changeList}>
                          {pendingChanges.map((change) => {
                            const id = changeId(change);
                            const active = id === changeId(selectedChange ?? pendingChanges[0]);
                            const applied = isGeneratedChangeApplied(change, appliedChanges);
                            const changeWarnings = warningsForGeneratedChange(change, applyWarnings);

                            return (
                              <button
                                key={id}
                                type="button"
                                style={styles.changeButton(palette, active)}
                                onClick={() => setSelectedChangeId(id)}
                                data-testid={`generated-change-${id}`}
                              >
                                <div style={styles.changeHeader}>
                                  <span style={styles.changeActionBadge(palette, change.action)}>
                                    {change.action}
                                  </span>
                                  <strong style={styles.changePath(palette)}>{change.path}</strong>
                                </div>
                                <span style={styles.changeSummary(palette)}>
                                  {change.summary || 'Generated file change preview'}
                                </span>
                                {applied ? <span style={styles.goodTag(palette)}>Applied</span> : null}
                                {!applied && changeWarnings.length ? (
                                  <span
                                    style={styles.warningTag(palette)}
                                    title={changeWarnings[0]}
                                    data-testid={`generated-change-warning-${id}`}
                                  >
                                    <AlertTriangle size={13} />
                                    Skipped
                                  </span>
                                ) : null}
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      {selectedChange ? (
                        <div style={styles.previewCard(palette)}>
                          <div style={styles.previewHeader(palette)}>
                            <div>
                              <div style={styles.previewTitle(palette)}>{selectedChange.path}</div>
                              <div style={styles.previewMeta(palette)}>
                                {selectedChange.action} / {formatBytes((selectedChange.content ?? '').length)}
                              </div>
                            </div>

                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                              {!applyChanges ? (
                                <>
                                  <button
                                    type="button"
                                    style={
                                      selectedChangeApplyIntent === 'retry'
                                        ? styles.warningActionButton(palette)
                                        : styles.primaryButton(palette)
                                    }
                                    onClick={() => void applyGeneratedChanges('selected')}
                                    disabled={loading || selectedChangeApplied}
                                    aria-label={`${
                                      selectedChangeApplyIntent === 'retry'
                                        ? 'Retry selected generated change'
                                        : 'Apply selected generated change'
                                    } ${selectedChange.path}`}
                                  >
                                    {selectedChangeApplyIntent === 'applied' ? (
                                      <CheckCircle2 size={16} />
                                    ) : selectedChangeApplyIntent === 'retry' ? (
                                      <AlertTriangle size={16} />
                                    ) : (
                                      <Wrench size={16} />
                                    )}
                                    {selectedChangeApplyLabel}
                                  </button>
                                  {remainingChanges.length ? (
                                    <button
                                      type="button"
                                      style={styles.secondaryButton(palette)}
                                      onClick={() => void applyGeneratedChanges('remaining')}
                                      disabled={loading}
                                      aria-label={`Apply remaining ${remainingChanges.length} generated changes`}
                                    >
                                      <Wrench size={16} />
                                      Apply remaining
                                    </button>
                                  ) : null}
                                </>
                              ) : null}
                              <button
                                type="button"
                                style={styles.secondaryButton(palette)}
                                onClick={() => void copySelectedGeneratedChangePath()}
                                disabled={loading}
                                aria-label={`Copy generated change path ${selectedChange.path}`}
                                title="Copy generated file path"
                              >
                                <Copy size={16} />
                                Copy path
                              </button>
                              <button
                                type="button"
                                style={styles.secondaryButton(palette)}
                                onClick={() => void copySelectedGeneratedChangeContent()}
                                disabled={loading || selectedChange.content === null}
                                aria-label={`Copy generated change content ${selectedChange.path}`}
                                title="Copy generated file content"
                              >
                                <Copy size={16} />
                                Copy content
                              </button>
                              <button
                                type="button"
                                style={styles.secondaryButton(palette)}
                                onClick={() => void copySelectedGeneratedChangeDiff()}
                                disabled={loading || !selectedChangeDiff?.patch?.trim()}
                                aria-label={`Copy generated change diff ${selectedChange.path}`}
                                title="Copy generated diff"
                              >
                                <Copy size={16} />
                                Copy diff
                              </button>
                              <button
                                type="button"
                                style={styles.secondaryButton(palette)}
                                onClick={() => saveFileToDisk()}
                                disabled={loading}
                                title="Download this file to your computer"
                              >
                                <Save size={16} />
                                Save
                              </button>
                            </div>
                          </div>

                          {selectedChangeWarnings.length ? (
                            <div style={styles.inlineWarning(palette)} data-testid="selected-change-warning">
                              <AlertTriangle size={14} />
                              <span>{selectedChangeWarnings[0]}</span>
                            </div>
                          ) : null}

                          <div style={styles.previewTabs}>
                            <button
                              type="button"
                              style={styles.previewTab(palette, selectedPreviewTab === 'diff')}
                              onClick={() => setSelectedPreviewTab('diff')}
                            >
                              Diff
                            </button>
                            <button
                              type="button"
                              style={styles.previewTab(palette, selectedPreviewTab === 'content')}
                              onClick={() => setSelectedPreviewTab('content')}
                            >
                              Full Content
                            </button>
                            {selectedChangeDiff ? (
                              <span style={styles.diffMeta(palette)}>
                                +{selectedChangeDiff.added_lines} / -{selectedChangeDiff.removed_lines}
                                {selectedChangeDiff.modified_lines ? ` / ~${selectedChangeDiff.modified_lines}` : ''}
                              </span>
                            ) : null}
                          </div>

                          {selectedPreviewTab === 'diff' ? (
                            selectedChangeDiff?.patch?.trim() ? (
                              <pre style={styles.diffBlock(palette)}>
                                <code>{selectedChangeDiff.patch}</code>
                              </pre>
                            ) : (
                              <div style={styles.emptyPanel(palette)}>
                                {selectedChangeDiffStatus || 'No diff preview available for this change.'}
                              </div>
                            )
                          ) : (
                            <pre style={styles.codeBlock(palette)}>
                              <code>{selectedChange.content ?? '(no file content)'}</code>
                            </pre>
                          )}
                        </div>
                      ) : null}
                    </>
                  ) : (
                    <div style={styles.emptyPanel(palette)}>
                      Ask {assistantIdentity} to create or update files and the preview will appear here.
                    </div>
                  )}

                  {appliedChanges.length ? (
                    <div style={styles.sectionBlock}>
                      <div style={styles.sectionLabel(palette)}>Applied</div>
                      <div style={styles.tagWrap}>
                        {appliedChanges.map((item) => (
                          <span key={item} style={styles.goodTag(palette)}>
                            <CheckCircle2 size={13} />
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {applyWarnings.length ? (
                    <div style={styles.warningBox(palette)}>
                      <div style={styles.warningTitle(palette)}>
                        <AlertTriangle size={16} />
                        Warnings
                      </div>
                      <ul style={styles.warningList(palette)}>
                        {applyWarnings.map((warning, index) => (
                          <li key={`${warning}-${index}`}>{warning}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {lastResponse?.context_files.length ? (
                    <div style={styles.sectionBlock}>
                      <div style={styles.sectionLabel(palette)}>Model Context</div>
                      <div style={styles.tagWrap}>
                        {lastResponse.context_files.map((item) => (
                          <span key={item.path} style={styles.contextTag(palette)}>
                            {item.path}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {validation ? (
                    <div style={styles.sectionBlock}>
                      <div style={styles.sectionLabel(palette)}>Validation</div>
                      <div style={styles.validationCard(palette, validation.exit_code === 0)}>
                        <div style={styles.validationMeta(palette)}>
                          <div style={{ display: 'flex', gap: 8, justifyContent: 'space-between', flexWrap: 'wrap' }}>
                            <div style={{ display: 'grid', gap: 4 }}>
                              <strong>{validation.command}</strong>
                              <span>
                                exit {validation.exit_code ?? 'n/a'}
                                {validation.timed_out ? ' / timed out' : ''}
                                {!validation.allowed ? ' / blocked' : ''}
                              </span>
                            </div>
                            <button
                              type="button"
                              style={styles.secondaryButton(palette)}
                              onClick={() => void copyValidationOutput()}
                              disabled={loading}
                              aria-label={`Copy validation output ${validation.command || 'result'}`}
                              title="Copy validation output"
                            >
                              <Copy size={16} />
                              Copy output
                            </button>
                            {validationNeedsRepair ? (
                              <>
                                <button
                                  type="button"
                                  style={styles.warningActionButton(palette)}
                                  onClick={draftValidationRepairPrompt}
                                  disabled={loading}
                                  aria-label={`Draft repair prompt for ${validation.command || 'validation result'}`}
                                  title="Draft repair prompt"
                                >
                                  <Wrench size={16} />
                                  Draft repair
                                </button>
                                <button
                                  type="button"
                                  style={styles.primaryButton(palette)}
                                  onClick={() => void sendValidationRepairPrompt()}
                                  disabled={loading}
                                  aria-label={`Send repair prompt for ${validation.command || 'validation result'}`}
                                  title="Send repair prompt"
                                >
                                  <Send size={16} />
                                  Send repair
                                </button>
                              </>
                            ) : null}
                          </div>
                        </div>
                        <div style={styles.validationSummary(palette)}>
                          {validation.summary || validation.reason || 'Validation result available.'}
                        </div>
                        <div style={styles.tagWrap}>
                          <span style={styles.contextTag(palette)}>{validation.category || 'unknown'}</span>
                          {lastResponse?.validation_profile ? (
                            <span style={styles.contextTag(palette)}>
                              recipe: {lastResponse.validation_profile.source || 'detected'}
                            </span>
                          ) : validationRecipe ? (
                            <span style={styles.contextTag(palette)}>
                              recipe: {validationRecipe.source || 'detected'}
                            </span>
                          ) : null}
                        </div>
                        {activeValidationContext?.changes.length ? (
                          <div style={styles.validationContext(palette)} data-testid="validation-generated-change-context">
                            <span>{generatedValidationContextStatus(activeValidationContext)}</span>
                            <div style={styles.tagWrap}>
                              {activeValidationContext.changes.map((change) => {
                                const id = changeId(change);
                                return (
                                  <button
                                    key={id}
                                    type="button"
                                    style={styles.contextButton(palette)}
                                    onClick={() => reviewValidatedGeneratedChange(change)}
                                    aria-label={`Review generated change ${change.path}`}
                                    data-testid={`review-validation-change-${id}`}
                                  >
                                    <FileCode2 size={13} />
                                    {change.action}: {change.path}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        ) : null}
                        <pre style={styles.consoleBlock(palette)}>
                          <code>{validation.stderr || validation.stdout || validation.reason || 'No output'}</code>
                        </pre>
                      </div>
                    </div>
                  ) : null}

                  {validationRepairTrail.length ? (
                    <div style={styles.sectionBlock} data-testid="validation-repair-trail">
                      <div style={styles.sectionHeaderInline}>
                        <div style={styles.sectionLabel(palette)}>Repair Requests</div>
                        <span style={styles.counterBadge(palette)}>
                          {visibleValidationRepairTrail.length === validationRepairTrail.length
                            ? validationRepairTrail.length
                            : `${visibleValidationRepairTrail.length}/${validationRepairTrail.length}`}
                        </span>
                      </div>
                      <div style={styles.repairTrailControls}>
                        <div style={{ ...styles.searchWrap(palette), ...styles.repairTrailSearch }}>
                          <Search size={16} />
                          <input
                            value={validationRepairSearch}
                            onChange={(event) => setValidationRepairSearch(event.target.value)}
                            placeholder="Search repair requests"
                            aria-label="Search repair requests"
                            style={styles.searchInput(palette)}
                          />
                          {validationRepairSearch ? (
                            <button
                              type="button"
                              style={styles.inlineIconButton(palette)}
                              onClick={() => setValidationRepairSearch('')}
                              aria-label="Clear repair request search"
                              title="Clear repair request search"
                            >
                              <X size={14} />
                            </button>
                          ) : null}
                        </div>
                        <div
                          style={styles.segmentedControl(palette)}
                          role="group"
                          aria-label="Filter repair requests by status"
                          data-testid="repair-status-filter"
                        >
                          {validationRepairTrailStatusFilters.map((filter) => (
                            <button
                              key={filter.value}
                              type="button"
                              style={styles.segmentedButton(palette, validationRepairStatusFilter === filter.value)}
                              onClick={() => setValidationRepairStatusFilter(filter.value)}
                              aria-label={`Show ${filter.label.toLowerCase()} repair requests`}
                              data-testid={`repair-status-filter-${filter.value}`}
                            >
                              {filter.label}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div style={styles.eventList}>
                        {visibleValidationRepairTrail.length ? (
                          visibleValidationRepairTrail.map((item) => (
                            <div
                              key={item.id}
                              style={styles.eventRow(palette, validationRepairTrailEventStatus(item.status))}
                              data-testid={`validation-repair-trail-${item.id}`}
                            >
                              <div>
                                <strong style={styles.eventTitle(palette)}>
                                  {item.command} / {validationRepairTrailStatusLabel(item.status)}
                                </strong>
                                <div style={styles.eventDetail(palette)}>
                                  Failed validation: exit {item.sourceExitCode ?? 'n/a'} / {item.sourceSummary}
                                </div>
                                {item.sourceReason ? (
                                  <div style={styles.eventDetail(palette)}>Reason: {item.sourceReason}</div>
                                ) : null}
                                {item.contextPaths.length ? (
                                  <div style={styles.tagWrap}>
                                    {item.contextChanges.length
                                      ? item.contextChanges.map((change) => {
                                          const id = changeId(change);
                                          return (
                                            <button
                                              key={id}
                                              type="button"
                                              style={styles.contextButton(palette)}
                                              onClick={() => reviewRepairTrailTarget(change)}
                                              aria-label={`Review repair target ${change.path}`}
                                              data-testid={`review-repair-target-${id}`}
                                            >
                                              <FileCode2 size={13} />
                                              {change.action}: {change.path}
                                            </button>
                                          );
                                        })
                                      : item.contextPaths.map((path) => (
                                          <span key={path} style={styles.contextTag(palette)}>
                                            {path}
                                          </span>
                                        ))}
                                  </div>
                                ) : null}
                                <div style={styles.eventDetail(palette)}>
                                  Follow-up: {item.resultExitCode === null ? '' : `exit ${item.resultExitCode} / `}
                                  {item.resultSummary}
                                </div>
                              </div>
                              <div style={styles.eventActions}>
                                <span style={styles.eventTime(palette)}>{formatEventTime(item.createdAt)}</span>
                                <button
                                  type="button"
                                  style={styles.iconTextButton(palette)}
                                  onClick={() => reopenValidationRepairPrompt(item)}
                                  disabled={loading}
                                  aria-label={`Reopen repair prompt ${item.command}`}
                                  title="Reopen repair prompt"
                                >
                                  <Wrench size={14} />
                                  Reopen
                                </button>
                                {item.status === 'failed' && item.followUpPrompt ? (
                                  <>
                                    <button
                                      type="button"
                                      style={styles.iconTextButton(palette)}
                                      onClick={() => draftValidationRepairFollowUp(item)}
                                      disabled={loading}
                                      aria-label={`Draft follow-up repair prompt ${item.command}`}
                                      title="Draft follow-up repair prompt"
                                    >
                                      <Wrench size={14} />
                                      Draft follow-up
                                    </button>
                                    <button
                                      type="button"
                                      style={styles.iconTextButton(palette)}
                                      onClick={() => void sendValidationRepairFollowUp(item)}
                                      disabled={loading}
                                      aria-label={`Send follow-up repair prompt ${item.command}`}
                                      title="Send follow-up repair prompt"
                                    >
                                      <Send size={14} />
                                      Send follow-up
                                    </button>
                                  </>
                                ) : null}
                                <button
                                  type="button"
                                  style={styles.iconTextButton(palette)}
                                  onClick={() => void copyValidationRepairTargets(item)}
                                  disabled={loading}
                                  aria-label={`Copy repair target files ${item.command}`}
                                  title="Copy repair target files"
                                >
                                  <Copy size={14} />
                                  Copy targets
                                </button>
                                <button
                                  type="button"
                                  style={styles.iconTextButton(palette)}
                                  onClick={() => void copyValidationRepairBrief(item)}
                                  disabled={loading}
                                  aria-label={`Copy repair brief ${item.command}`}
                                  title="Copy repair brief"
                                >
                                  <Copy size={14} />
                                  Copy brief
                                </button>
                              </div>
                            </div>
                          ))
                        ) : (
                          <div style={styles.emptyPanel(palette)}>No repair requests match this filter.</div>
                        )}
                      </div>
                    </div>
                  ) : null}

                  {repairAttempts.length ? (
                    <div style={styles.sectionBlock}>
                      <div style={styles.sectionLabel(palette)}>Repair Loop</div>
                      <div style={styles.eventList}>
                        {repairAttempts.map((item) => (
                          <div
                            key={`${item.attempt}-${item.created_at}`}
                            style={styles.eventRow(
                              palette,
                              item.outcome === 'fixed' || item.outcome === 'improved'
                                ? 'ok'
                                : item.outcome === 'rolled_back' || item.outcome === 'worse'
                                  ? 'warning'
                                  : 'error'
                            )}
                          >
                            <div>
                              <strong style={styles.eventTitle(palette)}>
                                Attempt {item.attempt} / {item.category} / {item.outcome}
                              </strong>
                              <div style={styles.eventDetail(palette)}>{item.summary}</div>
                              {item.checkpoint ? (
                                <div style={styles.eventDetail(palette)}>Checkpoint {item.checkpoint}</div>
                              ) : null}
                            </div>
                            <span style={styles.eventTime(palette)}>{formatEventTime(item.created_at)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {eventLog.length ? (
                    <div style={styles.sectionBlock}>
                      <div style={styles.sectionLabel(palette)}>Events</div>
                      <div style={styles.eventList}>
                        {eventLog.map((item, index) => (
                          <div key={`${item.kind}-${item.created_at}-${index}`} style={styles.eventRow(palette, item.status)}>
                            <div>
                              <strong style={styles.eventTitle(palette)}>{item.title}</strong>
                              <div style={styles.eventDetail(palette)}>{item.detail || item.kind}</div>
                            </div>
                            <span style={styles.eventTime(palette)}>{formatEventTime(item.created_at)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div style={styles.emptyPanel(palette)}>
                  The generated files, validation output, and event log will appear here after a reply.
                </div>
              )}
            </section>

            <LazyPanelBoundary
              title="Observability panel could not load"
              detail="Core workspace controls are still available. Retry the panel after telemetry settles."
              resetKey={workspaceRoot}
            >
              <Suspense fallback={<div style={styles.emptyPanel(palette)}>Loading observability...</div>}>
                <ObservabilityPanel workspaceRoot={workspaceRoot} palette={palette} />
              </Suspense>
            </LazyPanelBoundary>

            <section style={styles.panelCard(palette)}>
              <div style={styles.panelHeader(palette)}>
                <div style={styles.panelTitleWrap}>
                  <FolderOpen size={16} />
                  <h3 style={styles.panelTitle(palette)}>Workspace</h3>
                </div>
                <div style={styles.panelHeaderActions}>
                  <span style={styles.counterBadge(palette)}>
                    {visibleFiles.length === files.length ? files.length : `${visibleFiles.length}/${files.length}`}
                  </span>
                  {renderPanelCollapseButton('workspace', 'Workspace')}
                </div>
              </div>

              {detailPanelCollapsed('workspace') ? null : (
              <div style={styles.panelBody} data-testid="workspace-panel-body">
                <div style={styles.workspaceMeta(palette)}>
                  <strong>Root</strong>
                  <span>{workspaceRoot || '(not set)'}</span>
                </div>

                <div style={styles.searchWrap(palette)}>
                  <Search size={16} />
                  <input
                    value={fileSearch}
                    onChange={(event) => setFileSearch(event.target.value)}
                    placeholder="Filter workspace files"
                    aria-label="Filter workspace files"
                    style={styles.searchInput(palette)}
                  />
                </div>

                <div style={styles.sectionBlock}>
                  <div style={styles.sectionLabel(palette)}>Readiness</div>
                  {workspaceProfile ? (
                    <>
                      <div
                        style={styles.eventRow(
                          palette,
                          readinessStatusToEventStatus(workspaceProfile.readiness.status)
                        )}
                      >
                        <div>
                          <strong style={styles.eventTitle(palette)}>
                            {formatStatusLabel(workspaceProfile.readiness.status)} / {workspaceProfile.readiness.score}/100
                          </strong>
                          <div style={styles.eventDetail(palette)}>
                            {workspaceProfile.readiness.summary || 'No readiness summary available.'}
                          </div>
                          {workspaceProfile.readiness.next_action ? (
                            <div style={styles.eventDetail(palette)}>
                              Next: {workspaceProfile.readiness.next_action}
                            </div>
                          ) : null}
                        </div>
                        <span style={styles.eventTime(palette)}>
                          {workspaceProfile.has_manifest ? 'manifest' : 'no manifest'}
                        </span>
                      </div>

                      {workspaceProfile.readiness.blockers.length ? (
                        <div style={styles.changeList}>
                          {workspaceProfile.readiness.blockers.slice(0, 4).map((item) => (
                            <div key={item} style={styles.eventRow(palette, 'warning')}>
                              <div>
                                <strong style={styles.eventTitle(palette)}>Blocker</strong>
                                <div style={styles.eventDetail(palette)}>{item}</div>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : null}

                      <div style={styles.tagWrap}>
                        {workspaceProfile.dependency_profile.project_type ? (
                          <span style={styles.contextTag(palette)}>
                            {workspaceProfile.dependency_profile.project_type}
                          </span>
                        ) : null}
                        {workspaceProfile.dependency_profile.languages.slice(0, 3).map((item) => (
                          <span key={`lang-${item}`} style={styles.contextTag(palette)}>
                            {item}
                          </span>
                        ))}
                        {workspaceProfile.dependency_profile.frameworks.slice(0, 3).map((item) => (
                          <span key={`framework-${item}`} style={styles.contextTag(palette)}>
                            {item}
                          </span>
                        ))}
                        {workspaceProfile.dependency_profile.package_managers.slice(0, 2).map((item) => (
                          <span key={`pm-${item}`} style={styles.contextTag(palette)}>
                            {item}
                          </span>
                        ))}
                        {workspaceProfile.has_validation_plan ? (
                          <span style={styles.contextTag(palette)}>validation plan</span>
                        ) : null}
                        {workspaceProfile.has_instruction_status ? (
                          <span style={styles.contextTag(palette)}>instruction state</span>
                        ) : null}
                      </div>

                      {workspaceProfile.readiness.signals.length ? (
                        <div style={styles.eventDetail(palette)}>
                          Signals: {workspaceProfile.readiness.signals.slice(0, 3).join(' ')}
                        </div>
                      ) : null}

                      {workspaceProfile.recommendations.length ? (
                        <div style={styles.eventDetail(palette)}>
                          Priority: {workspaceProfile.recommendations.slice(0, 2).join(' ')}
                        </div>
                      ) : null}

                      {shouldOfferWorkspaceSetup(workspaceProfile, validationRecipe) ? (
                        <div style={styles.tagWrap}>
                          <button
                            type="button"
                            style={styles.secondaryButton(palette)}
                            onClick={() => void setupCurrentWorkspace()}
                            disabled={loading || workspaceSetupLoading}
                          >
                            {workspaceSetupLoading ? <Loader2 size={16} className="spin" /> : <Wrench size={16} />}
                            Set up workspace
                          </button>
                        </div>
                      ) : null}

                      {shouldOfferReadinessValidation(workspaceProfile, validationRecipe) ? (
                        <div style={styles.tagWrap}>
                          <button
                            type="button"
                            style={styles.secondaryButton(palette)}
                            onClick={() => void validateNow()}
                            disabled={loading || !workspaceRoot}
                          >
                            {loading ? <Loader2 size={16} className="spin" /> : <Play size={16} />}
                            Run validation
                          </button>
                        </div>
                      ) : null}
                    </>
                  ) : (
                    <div style={styles.emptyPanel(palette)}>
                      {workspaceProfileStatus || 'Loading workspace readiness...'}
                    </div>
                  )}
                  {workspaceProfileStatus && workspaceProfile ? (
                    <div style={styles.inlineStatus(palette)}>{workspaceProfileStatus}</div>
                  ) : null}
                </div>

                <div style={styles.sectionBlock}>
                  <div style={styles.sectionLabel(palette)}>Validation Recipe</div>
                  <label style={styles.fieldLabel(palette)}>
                    <span>Command</span>
                    <input
                      value={validationCommandDraft}
                      onChange={(event) => setValidationCommandDraft(event.target.value)}
                      placeholder="python -m pytest"
                      style={styles.fieldInput(palette)}
                    />
                  </label>
                  <label style={styles.fieldLabel(palette)}>
                    <span>Notes</span>
                    <textarea
                      value={validationNotesDraft}
                      onChange={(event) => setValidationNotesDraft(event.target.value)}
                      rows={2}
                      placeholder="Optional notes about why this recipe is the right validator."
                      style={styles.fieldTextarea(palette)}
                    />
                  </label>
                  <div style={styles.workspaceMeta(palette)}>
                    <strong>Source</strong>
                    <span>{validationRecipe?.source || 'detected'}</span>
                    <strong>Updated</strong>
                    <span>{validationRecipe?.updated_at ? formatDateTime(validationRecipe.updated_at) : 'Not saved yet'}</span>
                  </div>
                  <div style={styles.tagWrap}>
                    <button type="button" style={styles.secondaryButton(palette)} onClick={() => void saveValidationRecipeDraft()}>
                      <Save size={16} />
                      Save recipe
                    </button>
                    <button
                      type="button"
                      style={styles.secondaryButton(palette)}
                      onClick={() => {
                        setValidationCommandDraft('');
                        setValidationNotesDraft('');
                        void saveValidationRecipeDraft('', '');
                      }}
                    >
                      Clear recipe
                    </button>
                  </div>
                  {validationSuggestions.length ? (
                    <div style={styles.changeList}>
                      {validationSuggestions.slice(0, 4).map((item) => (
                        <button
                          key={item.command}
                          type="button"
                          style={styles.changeButton(palette, validationCommandDraft.trim() === item.command)}
                          onClick={() => {
                            setValidationCommandDraft(item.command);
                            setValidationNotesDraft(item.reason);
                          }}
                        >
                          <div style={styles.changeHeader}>
                            <span style={styles.changeActionBadge(palette, 'update')}>{item.category}</span>
                            <strong style={styles.changePath(palette)}>{item.command}</strong>
                          </div>
                          <span style={styles.changeSummary(palette)}>{item.reason}</span>
                        </button>
                      ))}
                    </div>
                  ) : null}
                  {validationRecipeStatus ? <div style={styles.inlineStatus(palette)}>{validationRecipeStatus}</div> : null}
                </div>

                <div style={styles.fileList}>
                  {visibleFiles.length ? (
                    visibleFiles.map((file) => (
                      <button
                        key={file.path}
                        type="button"
                        style={styles.fileButton(palette, selectedFilePath === file.path)}
                        onClick={() => void openWorkspaceFile(file)}
                        disabled={file.kind !== 'text'}
                        aria-label={`Open workspace file ${file.path}`}
                        title={file.kind !== 'text' ? 'Binary file preview is disabled' : file.path}
                      >
                        <div style={styles.fileButtonTop}>
                          <strong style={styles.filePath(palette)}>{file.path}</strong>
                          <span style={styles.fileSize(palette)}>{formatBytes(file.size)}</span>
                        </div>
                        <span style={styles.fileKind(palette)}>{file.kind}</span>
                      </button>
                    ))
                  ) : (
                    <div style={styles.emptyPanel(palette)}>
                      {files.length ? 'No files match this filter.' : 'No files found for this workspace.'}
                    </div>
                  )}
                </div>

                {selectedFilePath ? (
                  <div style={styles.previewCard(palette)} data-testid="workspace-file-preview">
                    <div style={styles.previewHeader(palette)}>
                      <div>
                        <div style={styles.previewTitle(palette)}>{selectedFilePath}</div>
                        <div style={styles.previewMeta(palette)}>
                          {fileStatus || 'Workspace file preview'}
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        <button
                          type="button"
                          style={styles.secondaryButton(palette)}
                          onClick={() => void copySelectedWorkspaceFilePath()}
                          disabled={loading}
                          aria-label={`Copy workspace file path ${selectedFilePath}`}
                          title="Copy workspace file path"
                        >
                          <Copy size={16} />
                          Copy path
                        </button>
                        <button
                          type="button"
                          style={styles.secondaryButton(palette)}
                          onClick={() => void copySelectedWorkspaceFileContent()}
                          disabled={loading}
                          aria-label={`Copy workspace file content ${selectedFilePath}`}
                          title="Copy workspace file content"
                        >
                          <Copy size={16} />
                          Copy content
                        </button>
                        <button
                          type="button"
                          style={styles.secondaryButton(palette)}
                          onClick={() => pinWorkspaceFile(selectedFilePath)}
                          disabled={loading || pinnedContextPaths.includes(selectedFilePath)}
                          aria-label={`Pin ${selectedFilePath} to next prompt`}
                        >
                          <FileCode2 size={16} />
                          {pinnedContextPaths.includes(selectedFilePath) ? 'Pinned' : 'Pin'}
                        </button>
                      </div>
                    </div>

                    <pre style={styles.codeBlock(palette)} data-testid="workspace-file-preview-content">
                      <code>{selectedFileContent || '(empty file)'}</code>
                    </pre>
                  </div>
                ) : null}
              </div>
              )}
            </section>

            <section style={styles.panelCard(palette)}>
              <div style={styles.panelHeader(palette)}>
                <div style={styles.panelTitleWrap}>
                  <Bot size={16} />
                  <h3 style={styles.panelTitle(palette)}>History &amp; Memory</h3>
                </div>
                <div style={styles.panelHeaderActions}>
                  <span style={styles.counterBadge(palette)}>
                    {visibleMemory.length + visibleProjectMemory.length + visibleTasks.length}
                  </span>
                  {renderPanelCollapseButton('memory', 'History and Memory')}
                </div>
              </div>

              {detailPanelCollapsed('memory') ? null : (
              <div style={styles.panelBody}>
                {visibleProjectMemory.length ? (
                  <div style={styles.sectionBlock}>
                    <div style={styles.sectionLabel(palette)}>Project Notes</div>
                    <div style={styles.changeList}>
                      {visibleProjectMemory.map((item) => (
                        <div key={item.id} style={styles.replyCard(palette)}>
                          <div style={styles.previewMeta(palette)}>
                            {item.category} / confidence {item.confidence.toFixed(2)} / {formatDateTime(item.updated_at)}
                          </div>
                          <div style={{ ...styles.replyText(palette), marginTop: 8, fontWeight: 700 }}>{item.title}</div>
                          <div style={{ ...styles.replyText(palette), marginTop: 8 }}>{item.detail}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {visibleMemory.length ? (
                  <div style={styles.sectionBlock}>
                    <div style={styles.sectionLabel(palette)}>Reusable Fixes</div>
                    <div style={styles.changeList}>
                      {visibleMemory.map((item) => (
                        <div key={item.id} style={styles.replyCard(palette)}>
                          <div style={styles.previewMeta(palette)}>
                            {item.category} / confidence {item.confidence.toFixed(2)} / {formatDateTime(item.created_at)}
                          </div>
                          <div style={{ ...styles.replyText(palette), marginTop: 8 }}>{item.fix_summary}</div>
                          <div style={{ ...styles.eventDetail(palette), marginTop: 8 }}>{item.error_signature}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {visibleTasks.length ? (
                  <div style={styles.sectionBlock}>
                    <div style={styles.sectionLabel(palette)}>Recent Tasks</div>
                    <div style={styles.eventList}>
                      {visibleTasks.map((item) => (
                        <div key={item.id} style={styles.eventRow(palette, taskStatusToEventStatus(item.status))}>
                          <div>
                            <strong style={styles.eventTitle(palette)}>
                              {item.mode} / {item.status}
                            </strong>
                            <div style={styles.eventDetail(palette)}>{item.message}</div>
                          </div>
                          <span style={styles.eventTime(palette)}>{formatDateTime(item.created_at)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {!visibleProjectMemory.length && !visibleMemory.length && !visibleTasks.length ? (
                  <div style={styles.emptyPanel(palette)}>
                    Workspace memory will appear here after {assistantIdentity} has validated repairs and completed a few tasks.
                  </div>
                ) : null}
              </div>
              )}
            </section>
          </aside>
          ) : null}
        </div>
      </div>

      {showSettings ? renderSettingsModal() : null}
      {showMemoryEditor && workspaceRoot ? (
        <LazyPanelBoundary
          title="Memory Center could not load"
          detail="The workspace remains active. Retry the memory surface or reopen it from the header."
          resetKey={workspaceRoot}
          style={styles.routeBoundary}
        >
          <Suspense fallback={<div style={styles.routeFallback(palette)}>Opening Memory Center...</div>}>
            <MemoryEditor
              workspaceRoot={workspaceRoot}
              onClose={() => setShowMemoryEditor(false)}
              palette={palette}
            />
          </Suspense>
        </LazyPanelBoundary>
      ) : null}

      {showApprovalSettings && workspaceRoot ? (
        <LazyPanelBoundary
          title="Approval controls could not load"
          detail="Approval policy did not change. Retry the panel or reopen it from the header."
          resetKey={workspaceRoot}
          style={styles.routeBoundary}
        >
          <Suspense fallback={<div style={styles.routeFallback(palette)}>Opening approval controls...</div>}>
            <ApprovalSettings
              workspaceRoot={workspaceRoot}
              onClose={() => setShowApprovalSettings(false)}
              palette={palette}
            />
          </Suspense>
        </LazyPanelBoundary>
      ) : null}
    </div>
  );
}

function getPalette(isDarkMode: boolean) {
  if (isDarkMode) {
    return {
      bgGlow:
        'radial-gradient(circle at 18% 8%, rgba(124,58,237,0.24), transparent 28%), radial-gradient(circle at 78% 2%, rgba(59,130,246,0.18), transparent 30%), radial-gradient(circle at 52% 96%, rgba(34,197,94,0.05), transparent 24%), linear-gradient(180deg, #080B17 0%, #070A14 58%, #050712 100%)',
      bg: '#080B17',
      shell: 'rgba(17,24,39,0.82)',
      shellBorder: 'rgba(255,255,255,0.06)',
      card: 'rgba(17,24,39,0.72)',
      cardAlt: 'rgba(21,26,36,0.78)',
      control: 'rgba(26,32,48,0.72)',
      sidebar: 'linear-gradient(180deg, rgba(17,24,39,0.86), rgba(8,11,23,0.94))',
      navActive: 'linear-gradient(135deg, rgba(124,58,237,0.24), rgba(59,130,246,0.12))',
      settingsRail: 'rgba(8,11,23,0.68)',
      settingsActive: 'rgba(124,58,237,0.16)',
      muted: '#8C98AD',
      text: '#F8FAFC',
      textSoft: '#CBD5E1',
      input: 'rgba(8,11,23,0.76)',
      inputBorder: 'rgba(255,255,255,0.06)',
      accent: '#7C3AED',
      accentSoft: 'rgba(124,58,237,0.14)',
      accentAlt: '#3B82F6',
      userBubble: 'rgba(26,32,48,0.88)',
      assistantBubble: 'rgba(17,24,39,0.86)',
      good: '#22c55e',
      bad: '#ef4444',
      warning: '#f59e0b',
      codeBg: 'rgba(5,7,18,0.92)'
    };
  }

  return {
    bgGlow:
      'radial-gradient(circle at 80% -10%, rgba(124,58,237,0.12), transparent 25%), linear-gradient(135deg, #f8fafc 0%, #eef2ff 58%, #f5f3ff 100%)',
    bg: '#f8fafc',
    shell: 'rgba(255,255,255,0.94)',
    shellBorder: 'rgba(15,23,42,0.12)',
    card: '#ffffff',
    cardAlt: '#f8fafc',
    control: '#ffffff',
    sidebar: 'rgba(255,255,255,0.96)',
    navActive: 'rgba(124,58,237,0.10)',
    settingsRail: 'rgba(248,250,252,0.92)',
    settingsActive: 'rgba(124,58,237,0.10)',
    muted: '#64748b',
    text: '#111827',
    textSoft: '#334155',
    input: '#ffffff',
    inputBorder: 'rgba(15,23,42,0.14)',
    accent: '#7c3aed',
    accentSoft: 'rgba(124,58,237,0.10)',
    accentAlt: '#3b82f6',
    userBubble: 'rgba(255,247,247,0.98)',
    assistantBubble: 'rgba(248,250,252,0.98)',
    good: '#16a34a',
    bad: '#dc2626',
    warning: '#b45309',
    codeBg: '#f8fafc'
  };
}

function isDarkPalette(p: Palette): boolean {
  return p.bg === '#080B17';
}

const styles = {
  appShell: (p: Palette): CSSProperties => ({
    minHeight: '100vh',
    position: 'relative',
    overflow: 'hidden',
    background: p.bgGlow,
    color: p.text,
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    padding: 12
  }),

  routeFallback: (p: Palette): CSSProperties => ({
    minHeight: '100vh',
    display: 'grid',
    placeItems: 'center',
    padding: 24,
    background: p.bgGlow,
    color: p.text,
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    fontSize: 14,
    fontWeight: 800
  }),

  routeBoundary: {
    minHeight: '100vh',
    borderRadius: 0,
    padding: 24
  } as CSSProperties,

  backdrop: (p: Palette): CSSProperties => ({
    position: 'absolute',
    inset: 0,
    background:
      `${p.bgGlow}, radial-gradient(circle at 50% 42%, rgba(255,255,255,0.035), transparent 42%), radial-gradient(circle at 50% 115%, rgba(0,0,0,0.55), transparent 42%)`,
    zIndex: 0
  }),

  frame: (compact: boolean): CSSProperties => ({
    position: 'relative',
    zIndex: 1,
    maxWidth: 'none',
    margin: '0 auto',
    height: 'calc(100vh - 24px)',
    display: 'grid',
    gridTemplateColumns: compact ? 'minmax(0, 1fr)' : '260px minmax(0, 1fr)',
    gridTemplateRows: compact ? 'auto minmax(112px, 220px) minmax(0, 1fr)' : '54px minmax(0, 1fr)',
    gap: compact ? 10 : 12
  }),

  header: (p: Palette, compact = false, narrow = false): CSSProperties => ({
    gridColumn: compact ? '1 / 2' : '2 / 3',
    gridRow: '1 / 2',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: narrow ? 'stretch' : 'center',
    gap: 16,
    flexWrap: narrow ? 'wrap' : 'nowrap',
    padding: 0,
    borderRadius: 0,
    background: 'transparent',
    border: 'none',
    boxShadow: 'none'
  }),

  topSearch: (p: Palette, compact = false): CSSProperties => ({
    width: compact ? '100%' : 'min(620px, 52vw)',
    flex: compact ? '1 1 320px' : '0 1 auto',
    height: 46,
    borderRadius: 999,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'rgba(17,24,39,0.58)' : 'rgba(255,255,255,0.82)',
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '0 16px',
    color: p.muted,
    backdropFilter: 'blur(24px)',
    boxShadow: isDarkPalette(p)
      ? '0 18px 48px rgba(2,6,23,0.26), inset 0 1px 0 rgba(255,255,255,0.04)'
      : '0 18px 48px rgba(15,23,42,0.08), inset 0 1px 0 rgba(255,255,255,0.82)',
    transition: 'border-color 180ms ease, box-shadow 180ms ease, background 180ms ease'
  }),

  brandWrap: {
    display: 'flex',
    alignItems: 'center',
    gap: 14,
    minWidth: 0
  } as CSSProperties,

  brandIcon: (p: Palette): CSSProperties => ({
    width: 40,
    height: 40,
    borderRadius: 14,
    display: 'grid',
    placeItems: 'center',
    background: `linear-gradient(135deg, rgba(8,11,23,0.92), rgba(26,32,48,0.76))`,
    border: `1px solid rgba(139,92,246,0.28)`,
    color: p.text,
    flexShrink: 0,
    overflow: 'hidden',
    boxShadow: '0 16px 42px rgba(124,58,237,0.24), 0 0 34px rgba(59,130,246,0.10), inset 0 1px 0 rgba(255,255,255,0.10)'
  }),

  brandIconImage: {
    width: '84%',
    height: '84%',
    objectFit: 'contain',
    objectPosition: '50% 50%',
    filter: 'saturate(1.18) contrast(1.05)'
  } as CSSProperties,

  brandTitle: (p: Palette): CSSProperties => ({
    fontSize: 19,
    fontWeight: 900,
    letterSpacing: 1.2,
    color: p.text,
    lineHeight: 1.1
  }),

  brandSubtitle: (p: Palette): CSSProperties => ({
    marginTop: 4,
    fontSize: 13,
    color: p.muted,
    maxWidth: 800,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis'
  }),

  headerActions: (narrow = false): CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: narrow ? 'flex-start' : 'flex-end',
    gap: 8,
    flexWrap: 'wrap',
    minWidth: 0
  }),

  topStatusPill: (p: Palette, ok: boolean): CSSProperties => ({
    height: 40,
    padding: '0 14px',
    borderRadius: 999,
    border: `1px solid ${p.inputBorder}`,
    background: ok ? 'rgba(34,197,94,0.10)' : p.card,
    color: p.text,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 9,
    fontSize: 13,
    fontWeight: 800,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  accountPill: (p: Palette): CSSProperties => ({
    minHeight: 40,
    maxWidth: 230,
    padding: '0 14px',
    borderRadius: 999,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'rgba(17,24,39,0.66)' : p.card,
    color: p.text,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    cursor: 'pointer',
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)',
    transition: 'transform 180ms ease, border-color 180ms ease, background 180ms ease'
  }),

  accountPlanText: (p: Palette): CSSProperties => ({
    color: p.accent,
    fontSize: 11,
    fontWeight: 850,
    whiteSpace: 'nowrap'
  }),

  statusDot: (p: Palette, ok: boolean): CSSProperties => ({
    width: 9,
    height: 9,
    borderRadius: 999,
    background: ok ? p.good : p.bad,
    boxShadow: `0 0 18px ${ok ? 'rgba(34,197,94,0.5)' : 'rgba(239,68,68,0.5)'}`
  }),

  modelSwitcher: {
    position: 'relative',
    display: 'inline-flex'
  } as CSSProperties,

  modelPill: (p: Palette, active = false): CSSProperties => ({
    height: 40,
    padding: '0 14px',
    borderRadius: 999,
    border: `1px solid ${p.inputBorder}`,
    background: active ? p.settingsActive : isDarkPalette(p) ? 'rgba(17,24,39,0.62)' : p.card,
    color: p.text,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 13,
    fontWeight: 800,
    cursor: 'pointer',
    maxWidth: 240,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  modelPillLabel: {
    maxWidth: 160,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap'
  } as CSSProperties,

  modelMenu: (p: Palette): CSSProperties => ({
    position: 'absolute',
    top: 48,
    right: 0,
    zIndex: 70,
    width: 380,
    maxWidth: 'calc(100vw - 32px)',
    border: `1px solid ${p.shellBorder}`,
    borderRadius: 14,
    background: p.shell,
    boxShadow: '0 24px 70px rgba(0,0,0,0.36)',
    padding: 12,
    display: 'grid',
    gap: 10
  }),

  modelMenuHeader: (p: Palette): CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    padding: '4px 4px 10px',
    borderBottom: `1px solid ${p.shellBorder}`
  }),

  modelMenuList: {
    display: 'grid',
    gap: 8,
    maxHeight: 360,
    overflowY: 'auto'
  } as CSSProperties,

  modelMenuRow: (p: Palette, active: boolean): CSSProperties => ({
    width: '100%',
    border: `1px solid ${active ? p.accent : p.inputBorder}`,
    borderRadius: 12,
    background: active ? p.settingsActive : p.card,
    color: p.text,
    cursor: active ? 'default' : 'pointer',
    padding: '10px 12px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    textAlign: 'left'
  }),

  modelMenuName: (p: Palette): CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
    color: p.text,
    fontWeight: 800,
    overflowWrap: 'anywhere'
  }),

  modelMenuFooter: (p: Palette): CSSProperties => ({
    paddingTop: 10,
    borderTop: `1px solid ${p.shellBorder}`,
    display: 'flex',
    justifyContent: 'flex-end'
  }),

  iconButton: (p: Palette): CSSProperties => ({
    width: 40,
    height: 40,
    borderRadius: 14,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'rgba(17,24,39,0.64)' : p.card,
    color: p.text,
    display: 'grid',
    placeItems: 'center',
    cursor: 'pointer',
    transition: 'transform 180ms ease, border-color 180ms ease, background 180ms ease',
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  utilityBar: (p: Palette, compact = false): CSSProperties => ({
    gridColumn: '1 / 2',
    gridRow: compact ? '2 / 3' : '1 / 3',
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
    alignItems: 'stretch',
    minHeight: 0,
    maxHeight: compact ? 220 : undefined,
    padding: 12,
    borderRadius: 18,
    background: p.sidebar,
    border: `1px solid ${p.shellBorder}`,
    boxShadow: '0 28px 80px rgba(2,6,23,0.34), inset 0 1px 0 rgba(255,255,255,0.04)',
    overflowX: 'hidden',
    overflowY: 'auto',
    scrollbarWidth: 'thin',
    backdropFilter: 'blur(28px)'
  }),

  utilityActions: (compact = false): CSSProperties => ({
    display: 'flex',
    flexDirection: compact ? 'row' : 'column',
    alignItems: 'center',
    gap: 8
  }),

  sidebarBrand: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    minHeight: 54,
    padding: '4px 4px 10px'
  } as CSSProperties,

  primaryUtilityButton: (p: Palette): CSSProperties => ({
    width: '100%',
    height: 48,
    padding: '0 16px',
    borderRadius: 14,
    border: 'none',
    background: `linear-gradient(135deg, ${p.accent}, ${p.accentAlt})`,
    color: '#fff',
    fontWeight: 850,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 10,
    cursor: 'pointer',
    boxShadow: '0 18px 42px rgba(124,58,237,0.30), inset 0 1px 0 rgba(255,255,255,0.18)',
    transition: 'transform 180ms ease, box-shadow 180ms ease, filter 180ms ease'
  }),

  utilityActionButton: (p: Palette): CSSProperties => ({
    width: '100%',
    height: 40,
    borderRadius: 12,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'rgba(21,26,36,0.72)' : p.cardAlt,
    color: p.text,
    display: 'grid',
    placeItems: 'center',
    cursor: 'pointer',
    transition: 'transform 180ms ease, border-color 180ms ease, background 180ms ease'
  }),

  sidebarNav: (compact = false): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: compact ? 'repeat(auto-fit, minmax(132px, 1fr))' : undefined,
    gap: 6
  }),

  sidebarNavItem: (p: Palette, active: boolean, compact = false): CSSProperties => ({
    width: '100%',
    minHeight: 42,
    borderRadius: 12,
    border: active ? '1px solid rgba(139,92,246,0.20)' : '1px solid transparent',
    background: active ? p.navActive : 'transparent',
    color: p.text,
    display: 'flex',
    alignItems: 'center',
    justifyContent: compact ? 'center' : 'flex-start',
    gap: 12,
    padding: '0 12px',
    cursor: 'pointer',
    fontSize: 14,
    fontWeight: active ? 800 : 650,
    textAlign: 'left',
    boxShadow: active ? '0 12px 30px rgba(124,58,237,0.13), inset 0 1px 0 rgba(255,255,255,0.05)' : 'none',
    transition: 'background 180ms ease, border-color 180ms ease, transform 180ms ease, box-shadow 180ms ease'
  }),

  sidebarSectionLabel: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    fontWeight: 800,
    padding: '8px 8px 0'
  }),

  searchWrap: (p: Palette): CSSProperties => ({
    minHeight: 40,
    borderRadius: 999,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'rgba(17,24,39,0.56)' : p.cardAlt,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '0 14px',
    color: p.muted,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)',
    transition: 'border-color 180ms ease, box-shadow 180ms ease, background 180ms ease'
  }),

  searchInput: (p: Palette): CSSProperties => ({
    width: '100%',
    border: 'none',
    outline: 'none',
    background: 'transparent',
    color: p.text,
    fontSize: 14
  }),

  inlineIconButton: (p: Palette): CSSProperties => ({
    width: 28,
    height: 28,
    borderRadius: 10,
    border: 'none',
    background: 'transparent',
    color: p.muted,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    flex: '0 0 auto'
  }),

  historyRail: {
    display: 'grid',
    gap: 4,
    flex: '0 0 auto',
    alignContent: 'start',
    overflowY: 'visible',
    minHeight: 'auto',
    paddingRight: 2,
    scrollbarWidth: 'thin'
  } as CSSProperties,

  threadPill: (p: Palette, active: boolean): CSSProperties => ({
    width: '100%',
    minHeight: 36,
    padding: '0 10px',
    borderRadius: 10,
    border: active ? '1px solid rgba(139,92,246,0.18)' : '1px solid transparent',
    background: active ? 'rgba(124,58,237,0.14)' : 'transparent',
    color: p.text,
    whiteSpace: 'normal',
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: active ? 750 : 500,
    transition: 'background 180ms ease, border-color 180ms ease'
  }),

  threadGroup: (p: Palette): CSSProperties => ({
    minHeight: 36,
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    alignItems: 'center',
    gap: 4,
    padding: '0 4px 0 0',
    borderRadius: 6,
    border: 'none',
    background: 'transparent',
    flex: '0 0 auto',
    width: '100%'
  }),

  sidebarUserCard: (p: Palette): CSSProperties => ({
    marginTop: 8,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: 12,
    borderRadius: 16,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p)
      ? 'linear-gradient(135deg, rgba(26,32,48,0.72), rgba(17,24,39,0.58))'
      : p.card,
    boxShadow: isDarkPalette(p)
      ? '0 18px 44px rgba(2,6,23,0.22), inset 0 1px 0 rgba(255,255,255,0.04)'
      : '0 18px 44px rgba(15,23,42,0.08)'
  }),

  sidebarUserName: (p: Palette): CSSProperties => ({
    color: p.text,
    fontWeight: 800,
    fontSize: 13
  }),

  sidebarUserPlan: (p: Palette): CSSProperties => ({
    color: p.accent,
    fontWeight: 800,
    fontSize: 12,
    marginTop: 2
  }),

  threadDeleteButton: (p: Palette): CSSProperties => ({
    width: 30,
    height: 30,
    borderRadius: 999,
    border: 'none',
    background: 'transparent',
    color: p.muted,
    display: 'grid',
    placeItems: 'center',
    cursor: 'pointer',
    position: 'relative',
    zIndex: 1
  }),

  mainGrid: (detailsVisible: boolean, compact = false): CSSProperties => ({
    gridColumn: compact ? '1 / 2' : '2 / 3',
    gridRow: compact ? '3 / 4' : '2 / 3',
    display: 'grid',
    gridTemplateColumns: detailsVisible && !compact ? 'minmax(0, 1fr) 360px' : 'minmax(0, 1fr)',
    gap: 12,
    height: '100%',
    minHeight: 0
  }),

  chatCard: (p: Palette): CSSProperties => ({
    display: 'grid',
    gridTemplateRows: '1fr auto auto auto',
    minHeight: 0,
    borderRadius: 18,
    background: isDarkPalette(p)
      ? 'linear-gradient(180deg, rgba(17,24,39,0.84), rgba(8,11,23,0.96)), radial-gradient(circle at 50% 4%, rgba(124,58,237,0.16), transparent 38%)'
      : p.shell,
    border: `1px solid ${p.shellBorder}`,
    boxShadow: '0 32px 100px rgba(2,6,23,0.42), inset 0 1px 0 rgba(255,255,255,0.05)',
    overflow: 'hidden',
    backdropFilter: 'blur(28px)'
  }),

  chatScroll: {
    overflowY: 'auto',
    padding: '22px',
    minHeight: 0,
    background:
      'radial-gradient(circle at 50% 18%, rgba(124,58,237,0.10), transparent 34%), radial-gradient(circle at 78% 42%, rgba(59,130,246,0.06), transparent 26%), linear-gradient(180deg, rgba(255,255,255,0.015), transparent 34%)'
  } as CSSProperties,

  surfacePage: {
    display: 'grid',
    gap: 16,
    alignContent: 'start',
    minHeight: '100%'
  } as CSSProperties,

  surfaceHeader: (p: Palette): CSSProperties => ({
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 16,
    padding: 18,
    borderRadius: 18,
    background: isDarkPalette(p)
      ? 'linear-gradient(135deg, rgba(26,32,48,0.72), rgba(17,24,39,0.64))'
      : p.card,
    border: `1px solid ${p.inputBorder}`,
    boxShadow: '0 18px 48px rgba(2,6,23,0.18), inset 0 1px 0 rgba(255,255,255,0.05)'
  }),

  surfaceTitleWrap: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 14,
    minWidth: 0
  } as CSSProperties,

  surfaceIcon: (p: Palette): CSSProperties => ({
    width: 44,
    height: 44,
    borderRadius: 14,
    display: 'grid',
    placeItems: 'center',
    background: `linear-gradient(135deg, rgba(124,58,237,0.22), rgba(59,130,246,0.12))`,
    border: `1px solid rgba(139,92,246,0.20)`,
    color: p.text,
    flexShrink: 0,
    boxShadow: '0 14px 32px rgba(124,58,237,0.12)'
  }),

  surfaceTitle: (p: Palette): CSSProperties => ({
    margin: 0,
    color: p.text,
    fontSize: 24,
    lineHeight: 1.2
  }),

  surfaceSubtitle: (p: Palette): CSSProperties => ({
    margin: '6px 0 0',
    color: p.muted,
    lineHeight: 1.5,
    maxWidth: 760
  }),

  surfaceActions: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
    justifyContent: 'flex-end'
  } as CSSProperties,

  surfaceColumns: {
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 0.9fr) minmax(320px, 1.1fr)',
    gap: 16,
    alignItems: 'start'
  } as CSSProperties,

  metricGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
    gap: 12
  } as CSSProperties,

  metricCard: (p: Palette): CSSProperties => ({
    minHeight: 88,
    display: 'grid',
    gap: 8,
    alignContent: 'center',
    padding: 14,
    borderRadius: 16,
    background: isDarkPalette(p)
      ? 'linear-gradient(180deg, rgba(26,32,48,0.66), rgba(17,24,39,0.62))'
      : p.card,
    border: `1px solid ${p.inputBorder}`,
    boxShadow: '0 14px 34px rgba(2,6,23,0.16), inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  metricLabel: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    fontWeight: 800,
    textTransform: 'uppercase',
    letterSpacing: 0.4
  }),

  metricValue: (p: Palette): CSSProperties => ({
    color: p.text,
    fontSize: 18,
    lineHeight: 1.25,
    overflowWrap: 'anywhere'
  }),

  emptyState: {
    minHeight: '100%',
    display: 'grid',
    alignContent: 'center',
    justifyItems: 'center',
    textAlign: 'center',
    padding: '32px 12px',
    position: 'relative'
  } as CSSProperties,

  emptyLogo: (p: Palette): CSSProperties => ({
    width: 76,
    height: 76,
    borderRadius: 24,
    display: 'grid',
    placeItems: 'center',
    marginBottom: 22,
    background: `linear-gradient(135deg, rgba(8,11,23,0.96), rgba(26,32,48,0.74))`,
    color: p.text,
    border: '1px solid rgba(139,92,246,0.22)',
    overflow: 'hidden',
    boxShadow: '0 28px 70px rgba(124,58,237,0.22), 0 0 80px rgba(59,130,246,0.10), inset 0 1px 0 rgba(255,255,255,0.12)'
  }),

  emptyLogoImage: {
    width: '86%',
    height: '86%',
    objectFit: 'contain',
    objectPosition: '50% 50%',
    filter: 'saturate(1.18) contrast(1.06)'
  } as CSSProperties,

  emptyTitle: (p: Palette): CSSProperties => ({
    margin: 0,
    fontSize: 34,
    lineHeight: 1.1,
    color: p.text,
    textShadow: '0 18px 50px rgba(124,58,237,0.22)'
  }),

  emptyText: (p: Palette): CSSProperties => ({
    maxWidth: 700,
    margin: '12px auto 0',
    fontSize: 15,
    lineHeight: 1.7,
    color: p.muted
  }),

  promptGrid: {
    marginTop: 30,
    width: '100%',
    maxWidth: 860,
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: 12
  } as CSSProperties,

  promptCard: (p: Palette): CSSProperties => ({
    borderRadius: 16,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p)
      ? 'linear-gradient(145deg, rgba(26,32,48,0.78), rgba(17,24,39,0.58)), radial-gradient(circle at 0% 0%, rgba(124,58,237,0.12), transparent 38%)'
      : p.card,
    color: p.text,
    padding: '18px 18px',
    textAlign: 'left',
    fontSize: 14,
    lineHeight: 1.5,
    cursor: 'pointer',
    boxShadow: '0 18px 42px rgba(2,6,23,0.20), inset 0 1px 0 rgba(255,255,255,0.05)',
    transition: 'transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease, background 180ms ease'
  }),

  workspaceSignalGrid: {
    marginTop: 22,
    width: '100%',
    maxWidth: 860,
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
    gap: 12
  } as CSSProperties,

  workspaceSignalCard: (p: Palette): CSSProperties => ({
    minHeight: 122,
    display: 'grid',
    gap: 10,
    alignContent: 'start',
    padding: 16,
    borderRadius: 18,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p)
      ? 'linear-gradient(180deg, rgba(17,24,39,0.58), rgba(8,11,23,0.52)), radial-gradient(circle at 16% 0%, rgba(59,130,246,0.08), transparent 42%)'
      : p.cardAlt,
    textAlign: 'left',
    boxShadow: '0 18px 44px rgba(2,6,23,0.18), inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  workspaceSignalTop: {
    display: 'flex',
    alignItems: 'center',
    gap: 10
  } as CSSProperties,

  workspaceSignalIcon: (p: Palette, tone: 'purple' | 'blue' | 'green'): CSSProperties => {
    const color = tone === 'green' ? p.good : tone === 'blue' ? '#3B82F6' : p.accent;
    return {
      width: 34,
      height: 34,
      borderRadius: 12,
      display: 'grid',
      placeItems: 'center',
      background: `${color}1F`,
      color,
      border: `1px solid ${color}33`,
      boxShadow: `0 10px 28px ${color}1F`
    };
  },

  workspaceSignalLabel: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    fontWeight: 850,
    textTransform: 'uppercase'
  }),

  workspaceSignalValue: (p: Palette): CSSProperties => ({
    color: p.text,
    fontSize: 15,
    lineHeight: 1.35,
    overflowWrap: 'anywhere'
  }),

  workspaceSignalMeta: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    lineHeight: 1.5,
    overflowWrap: 'anywhere'
  }),

  messageRow: (isUser: boolean): CSSProperties => ({
    display: 'flex',
    justifyContent: isUser ? 'flex-end' : 'flex-start',
    gap: 12,
    marginBottom: 18,
    alignItems: 'flex-start'
  }),

  avatar: (p: Palette, isUser: boolean): CSSProperties => ({
    width: 36,
    height: 36,
    minWidth: 36,
    borderRadius: 14,
    display: 'grid',
    placeItems: 'center',
    background: isUser ? p.accentSoft : p.cardAlt,
    border: `1px solid ${p.inputBorder}`,
    color: p.text,
    order: isUser ? 2 : 0
  }),

  messageBubble: (p: Palette, isUser: boolean): CSSProperties => ({
    maxWidth: 'min(820px, 84%)',
    padding: '14px 16px',
    borderRadius: 22,
    border: `1px solid ${p.inputBorder}`,
    background: isUser ? p.userBubble : p.assistantBubble,
    color: p.text,
    boxShadow: isUser
      ? '0 18px 48px rgba(124,58,237,0.12), inset 0 1px 0 rgba(255,255,255,0.05)'
      : '0 18px 48px rgba(2,6,23,0.20), inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  messageRole: (p: Palette): CSSProperties => ({
    fontSize: 12,
    fontWeight: 700,
    color: p.muted,
    marginBottom: 8,
    letterSpacing: 0.2
  }),

  messageText: (p: Palette): CSSProperties => ({
    whiteSpace: 'pre-wrap',
    lineHeight: 1.7,
    fontSize: 15,
    color: p.text
  }),

  messageContentStack: {
    display: 'grid',
    gap: 12
  } as CSSProperties,

  chatCodeFrame: (p: Palette): CSSProperties => ({
    border: `1px solid ${p.inputBorder}`,
    borderRadius: 12,
    overflow: 'hidden',
    background: p.codeBg
  }),

  chatCodeHeader: (p: Palette): CSSProperties => ({
    minHeight: 34,
    padding: '0 10px',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    borderBottom: `1px solid ${p.inputBorder}`,
    background: p.cardAlt,
    color: p.muted,
    fontSize: 12,
    fontWeight: 800
  }),

  chatCodeCopyButton: (p: Palette): CSSProperties => ({
    marginLeft: 'auto',
    minHeight: 26,
    padding: '0 8px',
    borderRadius: 8,
    border: `1px solid ${p.inputBorder}`,
    background: p.card,
    color: p.text,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 800
  }),

  chatCodeBlock: (p: Palette): CSSProperties => ({
    margin: 0,
    padding: 14,
    maxHeight: 360,
    overflow: 'auto',
    color: p.text,
    fontSize: 13,
    lineHeight: 1.6,
    whiteSpace: 'pre',
    tabSize: 2
  }),

  inlineChangeReview: (p: Palette): CSSProperties => ({
    marginTop: 14,
    border: `1px solid ${p.inputBorder}`,
    borderRadius: 14,
    overflow: 'hidden',
    background: p.cardAlt
  }),

  inlineChangeHeader: {
    minHeight: 48,
    padding: '0 14px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12
  } as CSSProperties,

  inlineChangeTitle: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    minWidth: 0,
    color: p.text,
    fontWeight: 850,
    fontSize: 14
  }),

  inlineChangeActions: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    flexShrink: 0,
    flexWrap: 'wrap',
    justifyContent: 'flex-end'
  } as CSSProperties,

  reviewChangesButton: (p: Palette): CSSProperties => ({
    minHeight: 32,
    padding: '0 10px',
    borderRadius: 10,
    border: `1px solid ${p.inputBorder}`,
    background: p.card,
    color: p.text,
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 850,
    whiteSpace: 'nowrap'
  }),

  addedLines: {
    color: '#22c55e',
    fontWeight: 900
  } as CSSProperties,

  removedLines: {
    color: '#ef4444',
    fontWeight: 900
  } as CSSProperties,

  inlineChangeStatus: (p: Palette): CSSProperties => ({
    padding: '0 14px 10px',
    color: p.muted,
    fontSize: 12,
    fontWeight: 650
  }),

  inlineChangeList: {
    display: 'grid'
  } as CSSProperties,

  inlineChangeItem: (p: Palette): CSSProperties => ({
    width: '100%',
    minHeight: 42,
    padding: '8px 14px',
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto auto',
    alignItems: 'center',
    gap: 10,
    border: 'none',
    borderTop: `1px solid ${p.inputBorder}`,
    background: 'transparent',
    color: p.text,
    cursor: 'pointer',
    textAlign: 'left'
  }),

  inlineChangePath: (p: Palette): CSSProperties => ({
    minWidth: 0,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    color: p.textSoft,
    fontSize: 13,
    fontWeight: 750
  }),

  inlineChangeAction: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    fontWeight: 800,
    textTransform: 'uppercase'
  }),

  inlineChangeDelta: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    minWidth: 58,
    justifyContent: 'flex-end',
    fontSize: 12
  } as CSSProperties,

  inlineChangePending: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontWeight: 800
  }),

  thinkingInline: (p: Palette): CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    color: p.textSoft,
    fontSize: 14,
    flexWrap: 'wrap'
  }),

  retryBadge: (p: Palette): CSSProperties => ({
    marginLeft: 6,
    padding: '4px 8px',
    borderRadius: 999,
    background: p.accentSoft,
    color: p.text,
    fontSize: 12,
    fontWeight: 700
  }),

  inlineQueuePanel: (p: Palette): CSSProperties => ({
    width: 'min(820px, 88%)',
    margin: '0 0 18px 48px',
    borderRadius: 14,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt,
    overflow: 'hidden'
  }),

  inlineQueueHeader: (p: Palette): CSSProperties => ({
    minHeight: 42,
    padding: '0 12px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 10,
    borderBottom: `1px solid ${p.inputBorder}`,
    color: p.muted,
    fontSize: 12,
    fontWeight: 850
  }),

  inlineQueueTitle: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    color: p.text
  }),

  inlineQueueList: {
    display: 'grid'
  } as CSSProperties,

  inlineQueueItem: (p: Palette): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: '28px minmax(0, 1fr) 34px',
    gap: 10,
    alignItems: 'center',
    minHeight: 42,
    padding: '8px 10px',
    borderTop: `1px solid ${p.inputBorder}`
  }),

  inlineQueueIndex: (p: Palette): CSSProperties => ({
    width: 24,
    height: 24,
    borderRadius: 999,
    display: 'grid',
    placeItems: 'center',
    background: p.accentSoft,
    color: p.text,
    fontSize: 12,
    fontWeight: 900
  }),

  inlineQueueText: (p: Palette): CSSProperties => ({
    minWidth: 0,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    color: p.textSoft,
    fontSize: 13,
    fontWeight: 700
  }),

  inlineQueueDiscard: (p: Palette): CSSProperties => ({
    width: 30,
    height: 30,
    borderRadius: 8,
    border: `1px solid ${p.inputBorder}`,
    background: p.card,
    color: p.muted,
    display: 'grid',
    placeItems: 'center',
    cursor: 'pointer'
  }),

  queueButton: (p: Palette, active: boolean): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    height: 34,
    padding: '0 12px',
    borderRadius: 999,
    background: active ? 'rgba(251,191,36,0.18)' : 'rgba(251,191,36,0.12)',
    color: p.warning,
    border: '1px solid rgba(251,191,36,0.22)',
    fontSize: 13,
    fontWeight: 700,
    cursor: 'pointer'
  }),

  queueTray: (p: Palette): CSSProperties => ({
    borderTop: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'linear-gradient(180deg, rgba(17,24,39,0.88), rgba(8,11,23,0.94))' : p.shell,
    padding: '14px 20px',
    display: 'grid',
    gap: 12
  }),

  queueTrayHeader: {
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    alignItems: 'center',
    gap: 12
  } as CSSProperties,

  queueTrayTitle: (p: Palette): CSSProperties => ({
    color: p.text,
    fontWeight: 800,
    fontSize: 14
  }),

  queueTrayMeta: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    marginTop: 3
  }),

  queueTrayActions: {
    display: 'flex',
    gap: 8,
    alignItems: 'center'
  } as CSSProperties,

  queueList: {
    display: 'grid',
    gap: 10,
    maxHeight: 250,
    overflowY: 'auto'
  } as CSSProperties,

  queueItem: (p: Palette): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    gap: 12,
    alignItems: 'center',
    padding: 12,
    borderRadius: 16,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt
  }),

  queueItemActions: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
    justifyContent: 'flex-end'
  } as CSSProperties,

  queueMoveButton: (p: Palette, disabled: boolean): CSSProperties => ({
    width: 32,
    height: 32,
    borderRadius: 10,
    border: `1px solid ${p.inputBorder}`,
    background: disabled ? p.shell : p.card,
    color: disabled ? p.muted : p.text,
    display: 'grid',
    placeItems: 'center',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.45 : 1
  }),

  queueItemMain: {
    display: 'grid',
    gap: 7,
    minWidth: 0
  } as CSSProperties,

  queueItemTop: (p: Palette): CSSProperties => ({
    display: 'flex',
    gap: 8,
    flexWrap: 'wrap',
    color: p.muted,
    fontSize: 11,
    fontWeight: 700,
    textTransform: 'uppercase'
  }),

  queueItemText: (p: Palette): CSSProperties => ({
    color: p.text,
    fontSize: 13,
    lineHeight: 1.45,
    overflow: 'hidden',
    display: '-webkit-box',
    WebkitLineClamp: 2,
    WebkitBoxOrient: 'vertical',
    overflowWrap: 'anywhere'
  }),

  statusRow: (p: Palette): CSSProperties => ({
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
    padding: '14px 20px',
    borderTop: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'linear-gradient(180deg, rgba(17,24,39,0.58), rgba(8,11,23,0.64))' : p.cardAlt,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.03)'
  }),

  statusCluster: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    flexWrap: 'wrap'
  } as CSSProperties,

  statusChip: (p: Palette, ok: boolean): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    height: 34,
    padding: '0 12px',
    borderRadius: 999,
    background: ok ? 'rgba(34,197,94,0.12)' : 'rgba(248,113,113,0.12)',
    color: ok ? p.good : p.bad,
    border: `1px solid ${ok ? 'rgba(34,197,94,0.18)' : 'rgba(248,113,113,0.18)'}`,
    fontSize: 13,
    fontWeight: 700,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  diagnosticChip: (p: Palette, status: 'ok' | 'warning' | 'error'): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    minHeight: 34,
    padding: '0 12px',
    borderRadius: 999,
    background:
      status === 'ok'
        ? 'rgba(34,197,94,0.12)'
        : status === 'warning'
          ? 'rgba(251,191,36,0.12)'
          : 'rgba(248,113,113,0.12)',
    color: status === 'ok' ? p.good : status === 'warning' ? p.warning : p.bad,
    border: `1px solid ${
      status === 'ok'
        ? 'rgba(34,197,94,0.18)'
        : status === 'warning'
          ? 'rgba(251,191,36,0.22)'
          : 'rgba(248,113,113,0.18)'
    }`,
    fontSize: 13,
    fontWeight: 700
  }),

  errorStatus: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    color: p.bad,
    fontSize: 13,
    fontWeight: 600,
    textAlign: 'right'
  }),

  metaStatus: (p: Palette): CSSProperties => ({
    fontSize: 13,
    color: p.muted,
    textAlign: 'right'
  }),

  composerWrap: (p: Palette): CSSProperties => ({
    padding: 16,
    borderTop: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p)
      ? 'linear-gradient(180deg, rgba(8,11,23,0.76), rgba(8,11,23,0.94)), radial-gradient(circle at 50% 0%, rgba(124,58,237,0.12), transparent 45%)'
      : p.card,
    boxShadow: '0 -20px 70px rgba(2,6,23,0.34), inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  contextPinBar: (p: Palette): CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
    marginBottom: 14,
    padding: 10,
    borderRadius: 14,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'rgba(21,26,36,0.68)' : p.cardAlt,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  contextPinLead: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    color: p.muted,
    fontSize: 12,
    fontWeight: 800,
    textTransform: 'uppercase',
    letterSpacing: 0.4
  }),

  contextPin: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    minHeight: 28,
    maxWidth: '100%',
    padding: '0 8px 0 10px',
    borderRadius: 999,
    background: p.accentSoft,
    color: p.text,
    fontSize: 12,
    fontWeight: 700,
    overflowWrap: 'anywhere'
  }),

  contextPinRemove: (p: Palette): CSSProperties => ({
    width: 20,
    height: 20,
    borderRadius: 999,
    border: 'none',
    background: 'transparent',
    color: p.text,
    cursor: 'pointer',
    display: 'grid',
    placeItems: 'center',
    padding: 0
  }),

  composerOptions: (p: Palette): CSSProperties => ({
    display: 'flex',
    justifyContent: 'space-between',
    gap: 12,
    flexWrap: 'wrap',
    marginBottom: 12,
    padding: '0 2px',
    color: p.muted
  }),

  optionGroup: {
    display: 'flex',
    gap: 10,
    flexWrap: 'wrap',
    alignItems: 'center'
  } as CSSProperties,

  checkboxLabel: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 13,
    color: p.textSoft
  }),

  composerForm: {
    display: 'grid',
    gridTemplateColumns: '1fr auto',
    gap: 14,
    alignItems: 'end'
  } as CSSProperties,

  composerInput: (p: Palette): CSSProperties => ({
    minHeight: 76,
    maxHeight: 180,
    resize: 'vertical',
    width: '100%',
    borderRadius: 20,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'rgba(8,11,23,0.72)' : p.input,
    color: p.text,
    padding: '18px 20px',
    outline: 'none',
    fontSize: 15,
    lineHeight: 1.5,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04), 0 18px 50px rgba(2,6,23,0.18)',
    transition: 'border-color 180ms ease, box-shadow 180ms ease, background 180ms ease'
  }),

  sendButton: (p: Palette, disabled: boolean): CSSProperties => ({
    width: 58,
    height: 58,
    borderRadius: 18,
    border: 'none',
    background: disabled ? p.cardAlt : `linear-gradient(135deg, ${p.accent}, ${p.accentAlt})`,
    color: disabled ? p.muted : '#fff',
    display: 'grid',
    placeItems: 'center',
    cursor: disabled ? 'not-allowed' : 'pointer',
    boxShadow: disabled ? 'inset 0 1px 0 rgba(255,255,255,0.04)' : '0 18px 42px rgba(124,58,237,0.28), inset 0 1px 0 rgba(255,255,255,0.16)',
    transition: 'transform 180ms ease, box-shadow 180ms ease, filter 180ms ease'
  }),

  sidebar: {
    display: 'grid',
    gap: 12,
    minHeight: 0,
    overflowY: 'auto',
    alignContent: 'start',
    paddingRight: 2,
    scrollbarWidth: 'thin'
  } as CSSProperties,

  panelCard: (p: Palette): CSSProperties => ({
    minHeight: 0,
    borderRadius: 18,
    background: isDarkPalette(p) ? 'linear-gradient(180deg, rgba(17,24,39,0.74), rgba(8,11,23,0.86))' : p.shell,
    border: `1px solid ${p.shellBorder}`,
    boxShadow: '0 22px 64px rgba(2,6,23,0.26), inset 0 1px 0 rgba(255,255,255,0.04)',
    overflow: 'hidden',
    display: 'grid',
    gridTemplateRows: 'auto 1fr',
    backdropFilter: 'blur(22px)'
  }),

  panelHeader: (p: Palette): CSSProperties => ({
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 10,
    padding: '15px 16px',
    borderBottom: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'linear-gradient(180deg, rgba(26,32,48,0.58), rgba(17,24,39,0.42))' : p.cardAlt,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  panelTitleWrap: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8
  } as CSSProperties,

  panelTitle: (p: Palette): CSSProperties => ({
    margin: 0,
    fontSize: 15,
    color: p.text,
    fontWeight: 850
  }),

  panelHeaderActions: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: 8,
    flexShrink: 0
  } as CSSProperties,

  panelCollapseButton: (p: Palette, collapsed: boolean): CSSProperties => ({
    width: 30,
    height: 30,
    borderRadius: 10,
    border: `1px solid ${p.inputBorder}`,
    background: collapsed ? p.accentSoft : p.card,
    color: p.text,
    cursor: 'pointer',
    display: 'inline-grid',
    placeItems: 'center',
    transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)',
    transition: 'background 160ms ease, transform 160ms ease'
  }),

  counterBadge: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: 28,
    height: 28,
    padding: '0 10px',
    borderRadius: 999,
    background: p.accentSoft,
    color: p.text,
    fontSize: 12,
    fontWeight: 700
  }),

  panelBody: {
    padding: 16,
    overflow: 'visible',
    display: 'grid',
    gap: 16,
    alignContent: 'start'
  } as CSSProperties,

  replyCard: (p: Palette): CSSProperties => ({
    padding: 16,
    borderRadius: 18,
    background: isDarkPalette(p) ? 'rgba(21,26,36,0.62)' : p.cardAlt,
    border: `1px solid ${p.inputBorder}`,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  replyText: (p: Palette): CSSProperties => ({
    color: p.text,
    lineHeight: 1.65,
    whiteSpace: 'pre-wrap'
  }),

  sectionBlock: {
    display: 'grid',
    gap: 10
  } as CSSProperties,

  sectionHeaderInline: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    flexWrap: 'wrap'
  } as CSSProperties,

  repairTrailControls: {
    display: 'flex',
    gap: 10,
    alignItems: 'center',
    flexWrap: 'wrap'
  } as CSSProperties,

  repairTrailSearch: {
    flex: '1 1 240px',
    minWidth: 220
  } as CSSProperties,

  segmentedControl: (p: Palette): CSSProperties => ({
    minHeight: 40,
    padding: 4,
    borderRadius: 14,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    flexWrap: 'wrap'
  }),

  segmentedButton: (p: Palette, active: boolean): CSSProperties => ({
    minHeight: 30,
    padding: '0 10px',
    borderRadius: 10,
    border: 'none',
    background: active ? p.accent : 'transparent',
    color: active ? '#fff' : p.text,
    cursor: 'pointer',
    fontWeight: 700,
    fontSize: 12
  }),

  reviewSummary: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: 8,
    flexWrap: 'wrap'
  } as CSSProperties,

  sectionLabel: (p: Palette): CSSProperties => ({
    fontSize: 12,
    fontWeight: 800,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    color: p.muted
  }),

  planList: (p: Palette): CSSProperties => ({
    margin: 0,
    paddingLeft: 18,
    color: p.text,
    lineHeight: 1.7
  }),

  changeList: {
    display: 'grid',
    gap: 10
  } as CSSProperties,

  changeButton: (p: Palette, active: boolean): CSSProperties => ({
    width: '100%',
    textAlign: 'left',
    padding: 12,
    borderRadius: 16,
    border: `1px solid ${active ? p.accent : p.inputBorder}`,
    background: active ? p.accentSoft : p.cardAlt,
    cursor: 'pointer',
    display: 'grid',
    gap: 8
  }),

  changeHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    minWidth: 0
  } as CSSProperties,

  changeActionBadge: (p: Palette, action: FileChange['action']): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: 64,
    height: 24,
    padding: '0 8px',
    borderRadius: 999,
    fontSize: 11,
    fontWeight: 800,
    textTransform: 'uppercase',
    color: action === 'create' ? p.good : action === 'update' ? p.warning : p.bad,
    background:
      action === 'create'
        ? 'rgba(34,197,94,0.12)'
        : action === 'update'
          ? 'rgba(251,191,36,0.16)'
          : 'rgba(248,113,113,0.12)'
  }),

  changePath: (p: Palette): CSSProperties => ({
    color: p.text,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap'
  }),

  changeSummary: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 13,
    lineHeight: 1.5
  }),

  previewCard: (p: Palette): CSSProperties => ({
    borderRadius: 18,
    overflow: 'hidden',
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt
  }),

  previewHeader: (p: Palette): CSSProperties => ({
    padding: 14,
    borderBottom: `1px solid ${p.inputBorder}`,
    display: 'flex',
    justifyContent: 'space-between',
    gap: 12,
    alignItems: 'center',
    flexWrap: 'wrap'
  }),

  previewTitle: (p: Palette): CSSProperties => ({
    fontSize: 14,
    fontWeight: 700,
    color: p.text
  }),

  previewMeta: (p: Palette): CSSProperties => ({
    marginTop: 4,
    fontSize: 12,
    color: p.muted
  }),

  previewTabs: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '12px 14px 0',
    flexWrap: 'wrap'
  } as CSSProperties,

  previewTab: (p: Palette, active: boolean): CSSProperties => ({
    height: 32,
    padding: '0 12px',
    borderRadius: 999,
    border: `1px solid ${active ? p.accent : p.inputBorder}`,
    background: active ? p.accentSoft : p.cardAlt,
    color: active ? p.text : p.muted,
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 700
  }),

  diffMeta: (p: Palette): CSSProperties => ({
    marginLeft: 'auto',
    color: p.muted,
    fontSize: 12,
    fontWeight: 700
  }),

  codeBlock: (p: Palette): CSSProperties => ({
    margin: 0,
    padding: 16,
    maxHeight: 360,
    overflow: 'auto',
    background: p.codeBg,
    color: p.text,
    fontSize: 13,
    lineHeight: 1.6,
    whiteSpace: 'pre-wrap',
    overflowWrap: 'anywhere'
  }),

  diffBlock: (p: Palette): CSSProperties => ({
    margin: 0,
    padding: 16,
    maxHeight: 360,
    overflow: 'auto',
    background: `linear-gradient(180deg, ${p.codeBg}, ${p.cardAlt})`,
    color: p.text,
    fontSize: 13,
    lineHeight: 1.6,
    whiteSpace: 'pre-wrap',
    overflowWrap: 'anywhere',
    borderTop: `1px solid ${p.inputBorder}`
  }),

  tagWrap: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 8
  } as CSSProperties,

  goodTag: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    minHeight: 32,
    padding: '0 10px',
    borderRadius: 999,
    background: 'rgba(34,197,94,0.12)',
    color: p.good,
    fontSize: 12,
    fontWeight: 700
  }),

  warningTag: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    minHeight: 32,
    padding: '0 10px',
    borderRadius: 999,
    background: 'rgba(251,191,36,0.14)',
    color: p.warning,
    fontSize: 12,
    fontWeight: 700
  }),

  contextTag: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    minHeight: 30,
    padding: '0 10px',
    borderRadius: 999,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt,
    color: p.textSoft,
    fontSize: 12,
    fontWeight: 600
  }),

  warningBox: (p: Palette): CSSProperties => ({
    display: 'grid',
    gap: 10,
    padding: 14,
    borderRadius: 18,
    background: 'rgba(251,191,36,0.10)',
    border: `1px solid ${p.inputBorder}`
  }),

  inlineWarning: (p: Palette): CSSProperties => ({
    display: 'flex',
    alignItems: 'flex-start',
    gap: 8,
    padding: '10px 14px',
    borderBottom: `1px solid ${p.inputBorder}`,
    background: 'rgba(251,191,36,0.10)',
    color: p.text,
    fontSize: 12,
    lineHeight: 1.5
  }),

  warningTitle: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    color: p.warning,
    fontWeight: 700
  }),

  warningList: (p: Palette): CSSProperties => ({
    margin: 0,
    paddingLeft: 18,
    color: p.text,
    lineHeight: 1.6
  }),

  validationCard: (p: Palette, ok: boolean): CSSProperties => ({
    borderRadius: 18,
    border: `1px solid ${ok ? 'rgba(34,197,94,0.2)' : p.inputBorder}`,
    background: p.cardAlt,
    overflow: 'hidden'
  }),

  validationMeta: (p: Palette): CSSProperties => ({
    display: 'grid',
    gap: 4,
    padding: 14,
    borderBottom: `1px solid ${p.inputBorder}`,
    color: p.text
  }),

  validationSummary: (p: Palette): CSSProperties => ({
    padding: '14px 14px 0',
    color: p.textSoft,
    fontSize: 13,
    lineHeight: 1.5
  }),

  validationContext: (p: Palette): CSSProperties => ({
    display: 'grid',
    gap: 10,
    margin: '12px 14px 0',
    padding: 12,
    borderRadius: 12,
    border: `1px solid ${p.inputBorder}`,
    background: p.card,
    color: p.textSoft,
    fontSize: 12,
    lineHeight: 1.4
  }),

  contextButton: (p: Palette): CSSProperties => ({
    minHeight: 32,
    padding: '0 10px',
    borderRadius: 12,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt,
    color: p.text,
    cursor: 'pointer',
    fontWeight: 700,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6
  }),

  consoleBlock: (p: Palette): CSSProperties => ({
    margin: 0,
    padding: 16,
    maxHeight: 280,
    overflow: 'auto',
    background: p.codeBg,
    color: p.text,
    fontSize: 13,
    lineHeight: 1.6,
    whiteSpace: 'pre-wrap',
    overflowWrap: 'anywhere'
  }),

  eventList: {
    display: 'grid',
    gap: 8
  } as CSSProperties,

  activityFilterBar: (p: Palette): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
    gap: 4,
    padding: 4,
    borderRadius: 14,
    border: `1px solid ${p.inputBorder}`,
    background: isDarkPalette(p) ? 'rgba(21,26,36,0.54)' : p.cardAlt,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  activityFilterButton: (p: Palette, active: boolean): CSSProperties => ({
    minHeight: 30,
    borderRadius: 10,
    border: 'none',
    background: active ? `linear-gradient(135deg, ${p.accent}, ${p.accentAlt})` : 'transparent',
    color: active ? '#fff' : p.textSoft,
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 850,
    transition: 'background 160ms ease, color 160ms ease'
  }),

  eventRow: (p: Palette, status: ToolEvent['status']): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: '1fr auto',
    gap: 12,
    alignItems: 'start',
    padding: 12,
    borderRadius: 14,
    background: isDarkPalette(p) ? 'rgba(21,26,36,0.56)' : p.cardAlt,
    borderLeft: `3px solid ${status === 'ok' ? p.good : status === 'warning' ? p.warning : p.bad}`,
    borderTop: `1px solid ${p.inputBorder}`,
    borderRight: `1px solid ${p.inputBorder}`,
    borderBottom: `1px solid ${p.inputBorder}`,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.03)'
  }),

  eventTitle: (p: Palette): CSSProperties => ({
    color: p.text
  }),

  eventDetail: (p: Palette): CSSProperties => ({
    marginTop: 4,
    color: p.muted,
    fontSize: 13,
    lineHeight: 1.5
  }),

  eventTime: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    whiteSpace: 'nowrap'
  }),

  eventActions: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
    gap: 8
  } as CSSProperties,

  liveBadge: (p: Palette): CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    minHeight: 24,
    padding: '0 9px',
    borderRadius: 999,
    color: p.good,
    background: 'rgba(34,197,94,0.10)',
    border: '1px solid rgba(34,197,94,0.18)',
    fontSize: 12,
    fontWeight: 900
  }),

  activityRow: (p: Palette, status: 'ok' | 'warning' | 'error'): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: '54px 1fr',
    gap: 10,
    padding: '10px 10px 10px 12px',
    borderLeft: `2px solid ${status === 'ok' ? p.good : status === 'warning' ? p.warning : p.bad}`,
    color: p.text,
    borderRadius: 12,
    background: isDarkPalette(p) ? 'rgba(21,26,36,0.34)' : p.card
  }),

  activityContent: {
    display: 'grid',
    gap: 8,
    minWidth: 0
  } as CSSProperties,

  activityToggleButton: (p: Palette): CSSProperties => ({
    width: '100%',
    border: 'none',
    background: 'transparent',
    color: p.text,
    padding: 0,
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    gap: 8,
    alignItems: 'start',
    textAlign: 'left',
    cursor: 'pointer'
  }),

  activityTextStack: {
    display: 'grid',
    gap: 2,
    minWidth: 0
  } as CSSProperties,

  activityChevron: (expanded: boolean): CSSProperties => ({
    marginTop: 2,
    transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
    transition: 'transform 160ms ease'
  }),

  activityDetails: (p: Palette): CSSProperties => ({
    display: 'grid',
    gap: 8,
    padding: 10,
    borderRadius: 10,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt
  }),

  activityDetailGrid: {
    display: 'grid',
    gap: 6
  } as CSSProperties,

  activityDetailItem: (p: Palette): CSSProperties => ({
    display: 'grid',
    gap: 2,
    minWidth: 0,
    color: p.text,
    fontSize: 12
  }),

  activityDetailLabel: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 11,
    textTransform: 'uppercase',
    fontWeight: 800
  }),

  activityDetailValue: (p: Palette): CSSProperties => ({
    color: p.text,
    fontSize: 12,
    overflowWrap: 'anywhere'
  }),

  activityOutputBlock: (p: Palette): CSSProperties => ({
    margin: 0,
    padding: 10,
    maxHeight: 220,
    overflow: 'auto',
    borderRadius: 8,
    border: `1px solid ${p.inputBorder}`,
    background: p.codeBg,
    color: p.text,
    fontSize: 12,
    lineHeight: 1.55,
    whiteSpace: 'pre-wrap',
    overflowWrap: 'anywhere'
  }),

  activityLogToggle: (p: Palette): CSSProperties => ({
    width: '100%',
    minHeight: 36,
    borderRadius: 10,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt,
    color: p.text,
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 850
  }),

  activityTime: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    lineHeight: 1.5
  }),

  emptyPanel: (p: Palette): CSSProperties => ({
    padding: 14,
    borderRadius: 18,
    border: `1px dashed ${p.inputBorder}`,
    color: p.muted,
    background: isDarkPalette(p) ? 'rgba(21,26,36,0.48)' : p.cardAlt,
    lineHeight: 1.6,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.03)'
  }),

  workspaceMeta: (p: Palette): CSSProperties => ({
    display: 'grid',
    gap: 6,
    padding: 12,
    borderRadius: 16,
    background: isDarkPalette(p) ? 'rgba(21,26,36,0.52)' : p.cardAlt,
    border: `1px solid ${p.inputBorder}`,
    color: p.text
  }),

  modelList: {
    display: 'grid',
    gap: 10,
    minWidth: 0
  } as CSSProperties,

  modelRow: (p: Palette, active: boolean): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    gap: 14,
    alignItems: 'center',
    padding: 14,
    borderRadius: 12,
    background: active ? p.accentSoft : p.card,
    border: `1px solid ${active ? p.accent : p.inputBorder}`,
    minWidth: 0
  }),

  taskListItem: (p: Palette, active: boolean): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    gap: 14,
    alignItems: 'center',
    width: '100%',
    padding: 14,
    borderRadius: 12,
    background: active ? p.accentSoft : p.card,
    border: `1px solid ${active ? p.accent : p.inputBorder}`,
    color: p.text,
    textAlign: 'left',
    cursor: 'pointer',
    minWidth: 0
  }),

  modelRowMain: {
    display: 'grid',
    gap: 8,
    minWidth: 0
  } as CSSProperties,

  modelRowTop: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 10,
    minWidth: 0
  } as CSSProperties,

  rowActions: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
    justifyContent: 'flex-end'
  } as CSSProperties,

  compactCard: (p: Palette): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    gap: 12,
    alignItems: 'center',
    padding: 14,
    borderRadius: 12,
    background: p.card,
    border: `1px solid ${p.inputBorder}`,
    minWidth: 0
  }),

  cardTitle: (p: Palette): CSSProperties => ({
    color: p.text,
    fontWeight: 800,
    fontSize: 14,
    overflowWrap: 'anywhere'
  }),

  agentHero: (p: Palette): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'auto minmax(0, 1fr)',
    gap: 12,
    padding: 14,
    borderRadius: 12,
    background: p.card,
    border: `1px solid ${p.inputBorder}`
  }),

  formGridTwo: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
    gap: 12
  } as CSSProperties,

  fieldButtonSlot: {
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'flex-start'
  } as CSSProperties,

  fileList: {
    display: 'grid',
    gap: 10
  } as CSSProperties,

  fileButton: (p: Palette, active: boolean): CSSProperties => ({
    width: '100%',
    textAlign: 'left',
    padding: 12,
    borderRadius: 16,
    border: `1px solid ${active ? p.accent : p.inputBorder}`,
    background: active ? p.accentSoft : p.cardAlt,
    cursor: 'pointer',
    display: 'grid',
    gap: 8
  }),

  fileButtonTop: {
    display: 'grid',
    gridTemplateColumns: '1fr auto',
    gap: 10,
    alignItems: 'center'
  } as CSSProperties,

  filePath: (p: Palette): CSSProperties => ({
    color: p.text,
    overflowWrap: 'anywhere'
  }),

  fileSize: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12
  }),

  fileKind: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.4
  }),

  modalOverlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(2,6,23,0.52)',
    display: 'grid',
    placeItems: 'center',
    padding: 24,
    zIndex: 20
  } as CSSProperties,

  modalCard: (p: Palette): CSSProperties => ({
    width: 'min(1060px, 100%)',
    maxHeight: '86vh',
    overflow: 'hidden',
    borderRadius: 20,
    background: p.shell,
    border: `1px solid ${p.shellBorder}`,
    backdropFilter: 'blur(28px)',
    boxShadow: '0 30px 100px rgba(2,6,23,0.30)',
    display: 'grid',
    gridTemplateRows: 'auto minmax(0, 1fr) auto auto'
  }),

  modalHeader: (p: Palette): CSSProperties => ({
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '20px 22px',
    borderBottom: `1px solid ${p.inputBorder}`
  }),

  modalTitle: (p: Palette): CSSProperties => ({
    margin: 0,
    color: p.text,
    fontSize: 20
  }),

  closeButton: (p: Palette): CSSProperties => ({
    width: 38,
    height: 38,
    borderRadius: 12,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt,
    color: p.text,
    cursor: 'pointer',
    display: 'grid',
    placeItems: 'center'
  }),

  modalBody: {
    display: 'grid',
    gap: 16,
    padding: 22
  } as CSSProperties,

  settingsShell: (narrow = false): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: narrow ? 'minmax(0, 1fr)' : '220px minmax(0, 1fr)',
    gridTemplateRows: narrow ? 'auto minmax(0, 1fr)' : undefined,
    minHeight: 0,
    overflow: 'hidden'
  }),

  settingsRail: (p: Palette, narrow = false): CSSProperties => ({
    display: narrow ? 'flex' : 'grid',
    alignContent: 'start',
    flexWrap: narrow ? 'wrap' : undefined,
    gap: 6,
    padding: narrow ? 12 : 18,
    borderRight: narrow ? 'none' : `1px solid ${p.inputBorder}`,
    borderBottom: narrow ? `1px solid ${p.inputBorder}` : 'none',
    background: p.settingsRail,
    overflowX: narrow ? 'auto' : undefined
  }),

  settingsTabButton: (p: Palette, active: boolean, narrow = false): CSSProperties => ({
    width: narrow ? 'auto' : '100%',
    minHeight: 46,
    flex: narrow ? '1 1 120px' : undefined,
    borderRadius: 10,
    border: 'none',
    background: active ? p.settingsActive : 'transparent',
    color: p.text,
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '0 12px',
    cursor: 'pointer',
    fontWeight: active ? 800 : 650,
    fontSize: 14,
    textAlign: 'left'
  }),

  settingsPane: {
    display: 'grid',
    gap: 16,
    alignContent: 'start',
    padding: 20,
    overflowY: 'auto',
    minHeight: 0,
    scrollbarWidth: 'thin'
  } as CSSProperties,

  settingsSection: (p: Palette): CSSProperties => ({
    borderRadius: 18,
    padding: 18,
    background: isDarkPalette(p) ? 'linear-gradient(180deg, rgba(21,26,36,0.70), rgba(17,24,39,0.58))' : p.cardAlt,
    border: `1px solid ${p.inputBorder}`,
    display: 'grid',
    gap: 14,
    boxShadow: '0 14px 36px rgba(2,6,23,0.14), inset 0 1px 0 rgba(255,255,255,0.04)'
  }),

  settingsHeading: (p: Palette): CSSProperties => ({
    margin: 0,
    fontSize: 15,
    color: p.text
  }),

  fieldLabel: (p: Palette): CSSProperties => ({
    display: 'grid',
    gap: 8,
    fontSize: 13,
    color: p.muted
  }),

  fieldInput: (p: Palette): CSSProperties => ({
    width: '100%',
    height: 44,
    borderRadius: 14,
    border: `1px solid ${p.inputBorder}`,
    background: p.input,
    color: p.text,
    padding: '0 14px',
    outline: 'none',
    fontSize: 14
  }),

  fieldTextarea: (p: Palette): CSSProperties => ({
    width: '100%',
    borderRadius: 14,
    border: `1px solid ${p.inputBorder}`,
    background: p.input,
    color: p.text,
    padding: '12px 14px',
    outline: 'none',
    fontSize: 14,
    lineHeight: 1.5,
    resize: 'vertical'
  }),

  settingsRow: (p: Palette): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) minmax(180px, auto)',
    gap: 12,
    alignItems: 'center',
    padding: '12px 0',
    borderTop: `1px solid ${p.inputBorder}`
  }),

  modalFooter: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: 12,
    padding: '0 22px 22px'
  } as CSSProperties,

  primaryButton: (p: Palette): CSSProperties => ({
    height: 40,
    padding: '0 14px',
    borderRadius: 14,
    border: 'none',
    background: `linear-gradient(135deg, ${p.accent}, ${p.accentAlt})`,
    color: '#fff',
    cursor: 'pointer',
    fontWeight: 700,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    boxShadow: '0 14px 34px rgba(124,58,237,0.22), inset 0 1px 0 rgba(255,255,255,0.14)',
    transition: 'transform 180ms ease, box-shadow 180ms ease, filter 180ms ease'
  }),

  warningActionButton: (p: Palette): CSSProperties => ({
    height: 40,
    padding: '0 14px',
    borderRadius: 14,
    border: 'none',
    background: 'linear-gradient(135deg, #b45309, #d97706)',
    color: '#fff',
    cursor: 'pointer',
    fontWeight: 700,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    boxShadow: `0 0 0 1px ${p.inputBorder}`
  }),

  secondaryButton: (p: Palette): CSSProperties => ({
    height: 40,
    padding: '0 14px',
    borderRadius: 14,
    border: `1px solid ${p.shellBorder}`,
    background: isDarkPalette(p) ? 'rgba(17,24,39,0.56)' : p.shell,
    color: p.text,
    cursor: 'pointer',
    fontWeight: 600,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)',
    transition: 'transform 180ms ease, border-color 180ms ease, background 180ms ease'
  }),

  iconTextButton: (p: Palette): CSSProperties => ({
    minHeight: 32,
    padding: '0 10px',
    borderRadius: 12,
    border: `1px solid ${p.inputBorder}`,
    background: p.card,
    color: p.text,
    cursor: 'pointer',
    fontWeight: 700,
    fontSize: 12,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6
  }),

  saveStatus: (p: Palette): CSSProperties => ({
    padding: '0 22px 22px',
    fontSize: 13,
    color: p.muted
  }),

  inlineStatus: (p: Palette): CSSProperties => ({
    fontSize: 13,
    color: p.muted
  })
};

function latestProjectThread(
  current: SavedConversation | null,
  candidate: SavedConversation | null
): SavedConversation | null {
  if (!candidate) return current;
  if (!current) return candidate;
  return new Date(candidate.updatedAt).getTime() > new Date(current.updatedAt).getTime() ? candidate : current;
}

function validationRepairTrailStatusLabel(status: ValidationRepairTrailStatus): string {
  if (status === 'passed') return 'Passed';
  if (status === 'failed') return 'Failed';
  return 'Sent';
}

function validationRepairTrailEventStatus(status: ValidationRepairTrailStatus): 'ok' | 'warning' | 'error' {
  if (status === 'passed') return 'ok';
  if (status === 'failed') return 'error';
  return 'warning';
}

function filterValidationRepairTrail(
  items: ValidationRepairTrailItem[],
  search: string,
  statusFilter: ValidationRepairTrailStatusFilter
): ValidationRepairTrailItem[] {
  const term = search.trim().toLowerCase();

  return items.filter((item) => {
    if (statusFilter !== 'all' && item.status !== statusFilter) return false;
    if (!term) return true;
    return validationRepairTrailSearchText(item).includes(term);
  });
}

function validationRepairTrailSearchText(item: ValidationRepairTrailItem): string {
  return [
    item.command,
    validationRepairTrailStatusLabel(item.status),
    item.prompt,
    item.followUpPrompt,
    item.sourceSummary,
    item.sourceReason,
    item.resultSummary,
    item.resultExitCode === null ? '' : `exit ${item.resultExitCode}`,
    item.sourceExitCode === null ? '' : `exit ${item.sourceExitCode}`,
    item.responseTaskId,
    ...item.contextPaths,
    ...item.contextChanges.map((change) => `${change.action} ${change.path}`)
  ]
    .filter(Boolean)
    .join('\n')
    .toLowerCase();
}

function createValidationRepairTrailId(): string {
  return `repair-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export default App;
