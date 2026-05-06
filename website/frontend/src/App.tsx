// frontend/src/App.tsx
import type { CSSProperties, FormEvent, ReactNode } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
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
  applyFileChanges,
  compareDiff,
  getConfig,
  getCheckpoints,
  getHealth,
  getModelManager,
  getModelRegistry,
  getModels,
  getValidationProfile,
  getWorkspaceHistory,
  getWorkspaceProfile,
  createMemoryNote,
  listFiles,
  deleteModel,
  pullModel,
  readFile,
  restoreCheckpoint,
  runWorkspaceValidation,
  saveConfig,
  setupWorkspace,
  streamAgentMessage,
  updateValidationProfile
} from './api';
import { MemoryEditor } from './components/MemoryEditor';
import { ApprovalSettings } from './components/ApprovalSettings';
import { ObservabilityPanel } from './components/ObservabilityPanel';
import {
  connectionStateDetail,
  connectionStateLabel,
  isLikelyConnectionError
} from './utils/connection';
import {
  buildRuntimeDiagnostics,
  type RuntimeDiagnosticActionKind,
  type RuntimeDiagnosticCheck
} from './utils/runtimeDiagnostics';
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
  AgentResponse,
  AppConfig,
  CheckpointSummary,
  ChatMessage,
  CommandRun,
  DiffCompareResponse,
  FileChange,
  FixMemoryEntry,
  HealthResponse,
  HistoryResponse,
  ManagedModelInfo,
  ModelInfo,
  ModelInventoryResponse,
  ModelManagerResponse,
  ModelRegistryResponse,
  Mode,
  ModeOption,
  ProjectMemoryEntry,
  RepairAttempt,
  TaskSummary,
  ToolEvent,
  ValidationRecipe,
  ValidateResponse,
  ValidationSuggestion,
  WorkspaceFile,
  WorkspaceProfileResponse
} from './types';

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

type Palette = ReturnType<typeof getPalette>;
type SubmitOptions = Partial<QueuedMessage> & {
  repairTrailId?: string;
};
type ValidationRepairTrailStatus = 'sent' | 'passed' | 'failed';
type ValidationRepairTrailStatusFilter = 'all' | ValidationRepairTrailStatus;
type ActivityFilter = 'all' | 'issues' | 'commands';
type ValidationRepairTrailChange = Pick<FileChange, 'action' | 'path'>;
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
type SidebarSection = 'chat' | 'projects' | 'agents' | 'models';
type SettingsTab = 'general' | 'models' | 'agents' | 'workspace' | 'advanced';
type DetailPanelSection = 'generated' | 'workspace' | 'memory';
type CustomAgent = {
  id: string;
  name: string;
  perspective: string;
  mission: string;
  mode: Mode;
  modelName: string;
  createdAt: string;
};
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
const defaultAgentId = 'aegis-default';
const customAgentsStorageKey = 'aegis.customAgents.v1';
const autoMemoryFingerprintStorageKey = 'aegis.autoMemoryFingerprints.v1';
const detailsPanelVisibleStorageKey = 'aegis.detailsPanelVisible.v1';
const detailPanelSectionsStorageKey = 'aegis.detailPanelSections.v1';
const selectedWorkspaceFileStorageKey = 'aegis.selectedWorkspaceFile.v1';
const queueAutoSendPausedStorageKey = 'aegis.queueAutoSendPaused.v1';
const detailPanelSectionOptions: DetailPanelSection[] = ['generated', 'workspace', 'memory'];
const defaultAgentPerspective =
  'Direct, practical coding agent focused on planning, building, reviewing, and repairing this workspace.';

function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [assistantName, setAssistantName] = useState('Aegis AI');
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
  const [engineLabel, setEngineLabel] = useState('Aegis Core');
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
  const autoMemoryFingerprints = useRef<Set<string>>(new Set(loadAutoMemoryFingerprints()));

  useEffect(() => {
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
            refreshValidationRecipe(result.workspace_root),
            refreshCheckpoints(result.workspace_root)
          ]);
        }
        await refreshModelCatalog();
      } catch (error) {
        setEngineReady(false);
        setLastHealth(null);
        setConnectionState('offline');
        setStatus(error instanceof Error ? error.message : 'Failed to load Aegis');
      }
    }

    void bootstrap();
  }, []);

  useEffect(() => {
    workspaceRootRef.current = workspaceRoot;
  }, [workspaceRoot]);

  useEffect(() => {
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
  }, []);

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
  const detailsPanelVisible = showDetailsPanel;
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
      title: 'Current chat',
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
      addRoot(thread.workspaceRoot, thread.title || 'Saved chat workspace', thread);
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

  function applyHealthSnapshot(health: HealthResponse, fallbackEngine = 'Aegis Core') {
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
      applyHealthSnapshot(health, config?.engine || 'Aegis Core');
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
    if (tab === 'models') {
      void refreshModelCatalog();
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
        assistant_name: assistantName.trim() || 'Aegis AI',
        assistant_mission:
          assistantMission.trim() ||
          'Your personal coding AI for planning, building, reviewing, and shipping work inside this workspace.',
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
      void refreshValidationRecipe(result.workspace_root);

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

    setStatus(`Opening workspace ${targetRoot}...`);
    setActiveWorkspaceRoot(targetRoot);
    setFileSearch('');
    setSelectedFilePath('');
    setSelectedFileContent('');
    setFileStatus('');
    try {
      const result = await listFiles(targetRoot);
      if (!workspaceRequestIsCurrent(targetRoot)) return;
      setActiveWorkspaceRoot(result.workspace_root);
      setFiles(result.files);
      await restoreSelectedWorkspaceFile(result.workspace_root, result.files);
      await Promise.all([
        refreshWorkspaceHistory(result.workspace_root),
        refreshWorkspaceProfile(result.workspace_root),
        refreshValidationRecipe(result.workspace_root),
        refreshCheckpoints(result.workspace_root)
      ]);
      setActiveSection('chat');
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
    setAssistantName('Aegis AI');
    setAssistantMission('Your personal coding AI for planning, building, reviewing, and shipping work inside this workspace.');
    setMode('build');
    setSaveStatus('Activating default Aegis agent...');

    try {
      const nextConfig = await saveConfig({
        assistant_name: 'Aegis AI',
        assistant_mission: 'Your personal coding AI for planning, building, reviewing, and shipping work inside this workspace.',
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
      setSaveStatus('Default Aegis agent is active.');
    } catch (error) {
      setSaveStatus(error instanceof Error ? error.message : 'Could not activate default agent');
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
          void refreshValidationRecipe(result.workspace_root);
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
    setStatus(`Opened saved chat "${thread.title}".`);
  }

  function deleteSavedThread(thread: SavedConversation) {
    if (loading) return;

    const confirmed = window.confirm(
      `Delete saved chat "${thread.title}"? This removes it from this browser only.`
    );
    if (!confirmed) return;

    setSavedThreads((current) => {
      const next = deleteSavedConversation(current, thread.id);
      saveSavedConversations(next);
      return next;
    });
    setStatus('Saved chat deleted.');
  }

  async function saveAegisSettings() {
    setSaveStatus('');

    try {
      const nextConfig = await saveConfig({
        assistant_name: assistantName.trim() || 'Aegis AI',
        assistant_mission:
          assistantMission.trim() ||
          'Your personal coding AI for planning, building, reviewing, and shipping work inside this workspace.',
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
      setSaveStatus('Aegis settings saved.');

      const result = await listFiles(nextConfig.default_workspace);
      if (!workspaceRequestIsCurrent(nextConfig.default_workspace)) return;
      setActiveWorkspaceRoot(result.workspace_root);
      setFiles(result.files);
      await refreshWorkspaceHistory(result.workspace_root);
      await refreshWorkspaceProfile(result.workspace_root);
      await refreshValidationRecipe(result.workspace_root);
      await refreshCheckpoints(result.workspace_root);
    } catch (error) {
      setSaveStatus(error instanceof Error ? error.message : 'Could not save Aegis settings');
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
        ? 'Aegis is busy. Your message is queued for the next available turn.'
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
            setStatus(payload.message || payload.stage || 'Aegis is working...');
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
        await refreshWorkspaceProfile(response.workspace_root);
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
        const errorMessage = error instanceof Error ? error.message : 'Aegis could not answer the request';

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
          setStatus('Chat request stopped.');
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
            throw new DOMException('Chat request stopped.', 'AbortError');
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

    const title = currentThreadPreview.title || 'Aegis chat';
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

  function renderWorkspaceSurface() {
    if (activeSection === 'projects') return renderProjectsSurface();
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
          'Workspaces are the roots Aegis can inspect, edit, validate, and remember between chats.',
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
                placeholder="Search projects or chats"
                aria-label="Search projects or chats"
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
                        {project.count} chat{project.count === 1 ? '' : 's'}
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
                    <div style={styles.previewMeta(palette)}>No saved chats for this root yet.</div>
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
                      aria-label={`Open latest chat for ${project.title}`}
                    >
                      <MessageSquarePlus size={14} />
                      Latest chat
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
            {!visibleProjectRoots.length ? (
              <div style={styles.emptyPanel(palette)}>
                No projects or saved chats matched that filter.
              </div>
            ) : null}
          </div>
        </section>
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
              disabled={activeAgentId === defaultAgentId && assistantName === 'Aegis AI'}
            >
              <Bot size={16} />
              Use default Aegis
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
            <label style={styles.fieldLabel(palette)}>
              <span>Switch Model</span>
              <select
                value={modelOptionKey({ api: modelApi, endpoint: modelEndpoint, name: modelName })}
                onChange={(event) => {
                  const target = selectableModelOptions.find((item) => modelOptionKey(item) === event.target.value);
                  if (target) selectModelDraft(target);
                }}
                style={styles.fieldInput(palette)}
              >
                {selectableModelOptions.map((item) => (
                  <option key={`surface-model-${modelOptionKey(item)}`} value={modelOptionKey(item)}>
                    {item.name} {item.active ? '(active)' : ''}
                  </option>
                ))}
              </select>
            </label>
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
      <div style={styles.modalOverlay} onClick={() => setShowSettings(false)}>
        <div style={styles.modalCard(palette)} onClick={(event) => event.stopPropagation()}>
          <div style={styles.modalHeader(palette)}>
            <h3 style={styles.modalTitle(palette)}>Settings</h3>
            <button type="button" style={styles.closeButton(palette)} onClick={() => setShowSettings(false)} aria-label="Close settings">
              <X size={18} />
            </button>
          </div>

          <div style={styles.settingsShell}>
            <aside style={styles.settingsRail(palette)} aria-label="Settings sections">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  style={styles.settingsTabButton(palette, settingsTab === tab.id)}
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
            <button type="button" style={styles.secondaryButton(palette)} onClick={() => setShowSettings(false)}>
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
          <label style={styles.fieldLabel(palette)}>
            <span>Installed / Configured Model</span>
            <select
              value={modelOptionKey({ api: modelApi, endpoint: modelEndpoint, name: modelName })}
              onChange={(event) => {
                const target = selectableModelOptions.find((item) => modelOptionKey(item) === event.target.value);
                if (target) selectModelDraft(target);
              }}
              style={styles.fieldInput(palette)}
            >
              {selectableModelOptions.map((item) => (
                <option key={`settings-model-${modelOptionKey(item)}`} value={modelOptionKey(item)}>
                  {item.name} / {item.api}
                </option>
              ))}
            </select>
          </label>
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

  return (
    <div style={styles.appShell(palette)}>
      <div style={styles.backdrop(palette)} />
      <div style={styles.frame}>
        <header style={styles.header(palette)}>
          <div style={styles.topSearch(palette)}>
            <Search size={17} />
            <input
              value={chatSearch}
              onChange={(event) => setChatSearch(event.target.value)}
              placeholder="Search Aegis... (Ctrl + K)"
              aria-label="Search Aegis"
              style={styles.searchInput(palette)}
            />
          </div>

          <div style={styles.headerActions}>
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
          </div>
        </header>

        <div style={styles.utilityBar(palette)}>
          <div style={styles.sidebarBrand}>
            <div style={styles.brandIcon(palette)}>
              <Code size={20} />
            </div>
            <div>
              <div style={styles.brandTitle(palette)}>AEGIS</div>
              <div style={styles.brandSubtitle(palette)}>Coding AI</div>
            </div>
          </div>

          <div style={styles.utilityActions}>
            <button
              type="button"
              style={styles.primaryUtilityButton(palette)}
              onClick={startNewChat}
              disabled={loading}
            >
              <MessageSquarePlus size={16} />
              <span>New chat</span>
            </button>
            <button
              type="button"
              style={styles.utilityActionButton(palette)}
              onClick={exportCurrentChatTranscript}
              disabled={!history.length}
              aria-label="Export chat transcript"
              title="Export current chat as Markdown"
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

          <div style={styles.sidebarNav}>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, activeSection === 'chat')}
              onClick={() => setActiveSection('chat')}
              aria-label="Home"
            >
              <FolderOpen size={16} />
              Home
            </button>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, activeSection === 'projects')}
              onClick={() => setActiveSection('projects')}
              aria-label="Projects"
            >
              <FolderOpen size={16} />
              Projects
            </button>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, activeSection === 'agents')}
              onClick={() => setActiveSection('agents')}
              aria-label="Agents"
            >
              <Bot size={16} />
              Agents
            </button>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, activeSection === 'models')}
              onClick={() => {
                setActiveSection('models');
                void refreshModelCatalog();
              }}
              aria-label="Models"
            >
              <Brain size={16} />
              Models
            </button>
            <button
              type="button"
              style={styles.sidebarNavItem(palette, false)}
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
              placeholder="Search chats"
              style={styles.searchInput(palette)}
            />
          </div>

          <div style={styles.sidebarSectionLabel(palette)}>Recent Chats</div>
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
                  title={`Delete saved chat ${thread.title}`}
                  aria-label={`Delete saved chat ${thread.title}`}
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
              <div style={styles.sidebarUserName(palette)}>Aegis User</div>
              <div style={styles.sidebarUserPlan(palette)}>Pro Plan</div>
            </div>
          </div>
        </div>

        <div style={styles.mainGrid(detailsPanelVisible)}>
          <section style={styles.chatCard(palette)}>
            <div ref={chatScrollRef} style={styles.chatScroll} data-testid="chat-scroll">
              {activeSection === 'chat' ? (
                <>
              {history.length === 0 ? (
                <div style={styles.emptyState}>
                  <div style={styles.emptyLogo(palette)}>
                    <Code size={30} />
                  </div>
                  <h2 style={styles.emptyTitle(palette)}>Welcome to {assistantName}</h2>
                  <p style={styles.emptyText(palette)}>
                    Ask for code, fixes, explanations, file generation, or workspace changes.
                  </p>

                  <div style={styles.promptGrid}>
                    {starterPrompts.map((prompt) => (
                      <button
                        key={prompt}
                        type="button"
                        onClick={() => void submit(undefined, prompt)}
                        style={styles.promptCard(palette)}
                        disabled={loading}
                      >
                        {prompt}
                      </button>
                    ))}
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
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  placeholder={composerWillQueue ? 'Message Aegis... next prompt will be queued' : 'Message Aegis...'}
                  rows={2}
                  style={styles.composerInput(palette)}
                />
                <button
                  type="submit"
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

          {detailsPanelVisible ? (
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
                        'Restored file review from this saved chat. Exact line counts are rebuilt from available checkpoints and workspace files.'}
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
                      Ask Aegis to create or update files and the preview will appear here.
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

            <ObservabilityPanel workspaceRoot={workspaceRoot} palette={palette} />

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
                    Workspace memory will appear here after Aegis has validated repairs and completed a few tasks.
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
      {false && showSettings ? (
        <div style={styles.modalOverlay} onClick={() => setShowSettings(false)}>
          <div style={styles.modalCard(palette)} onClick={(event) => event.stopPropagation()}>
            <div style={styles.modalHeader(palette)}>
              <h3 style={styles.modalTitle(palette)}>Settings</h3>
              <button type="button" style={styles.closeButton(palette)} onClick={() => setShowSettings(false)}>
                ×
              </button>
            </div>

            <div style={styles.modalBody}>
              <section style={styles.settingsSection(palette)}>
                <h4 style={styles.settingsHeading(palette)}>Assistant</h4>

                <label style={styles.fieldLabel(palette)}>
                  <span>Name</span>
                  <input
                    value={assistantName}
                    onChange={(event) => setAssistantName(event.target.value)}
                    style={styles.fieldInput(palette)}
                  />
                </label>

                <label style={styles.fieldLabel(palette)}>
                  <span>Mission</span>
                  <textarea
                    value={assistantMission}
                    onChange={(event) => setAssistantMission(event.target.value)}
                    rows={3}
                    style={styles.fieldTextarea(palette)}
                  />
                </label>
              </section>

              <section style={styles.settingsSection(palette)}>
                <h4 style={styles.settingsHeading(palette)}>AI Model</h4>

                <label style={styles.fieldLabel(palette)}>
                  <span>API Type</span>
                  <select
                    value={modelApi}
                    onChange={(event) => setModelApi(event.target.value)}
                    style={styles.fieldInput(palette)}
                  >
                    <option value="ollama">Ollama (Local)</option>
                    <option value="openai">OpenAI Compatible</option>
                  </select>
                </label>

                <label style={styles.fieldLabel(palette)}>
                  <span>Endpoint</span>
                  <input
                    value={modelEndpoint}
                    onChange={(event) => setModelEndpoint(event.target.value)}
                    style={styles.fieldInput(palette)}
                  />
                </label>

                <label style={styles.fieldLabel(palette)}>
                  <span>Model Name</span>
                  <input
                    value={modelName}
                    onChange={(event) => setModelName(event.target.value)}
                    style={styles.fieldInput(palette)}
                  />
                </label>
              </section>

              <section style={styles.settingsSection(palette)}>
                <h4 style={styles.settingsHeading(palette)}>Workspace</h4>

                <label style={styles.fieldLabel(palette)}>
                  <span>Root Directory</span>
                  <input
                    value={workspaceRoot}
                    onChange={(event) => setActiveWorkspaceRoot(event.target.value)}
                    style={styles.fieldInput(palette)}
                  />
                </label>

                <label style={styles.checkboxLabel(palette)}>
                  <input
                    type="checkbox"
                    checked={autoRunValidation}
                    onChange={(event) => setAutoRunValidation(event.target.checked)}
                  />
                  <span>Auto-run validation after file changes</span>
                </label>

                <div style={styles.sectionBlock}>
                  <div style={styles.sectionHeaderInline}>
                    <div style={styles.sectionLabel(palette)}>Checkpoints</div>
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
                        <div key={checkpoint.id} style={styles.eventRow(palette, 'warning')}>
                          <div>
                            <strong style={styles.eventTitle(palette)}>
                              {checkpoint.created_at ? formatDateTime(checkpoint.created_at) : checkpoint.id}
                            </strong>
                            <div style={styles.eventDetail(palette)}>
                              {checkpoint.file_count} tracked file{checkpoint.file_count === 1 ? '' : 's'} / {checkpoint.present_count} saved / {checkpoint.missing_count} new
                            </div>
                            {checkpoint.files.length ? (
                              <div style={styles.eventDetail(palette)}>
                                {checkpoint.files.slice(0, 3).map((item) => item.path).join(', ')}
                                {checkpoint.files.length > 3 ? `, +${checkpoint.files.length - 3} more` : ''}
                              </div>
                            ) : null}
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
                    <div style={styles.emptyPanel(palette)}>
                      {checkpointStatus || 'No checkpoints have been created for this workspace yet.'}
                    </div>
                  )}
                  {checkpointStatus && checkpoints.length ? (
                    <div style={styles.inlineStatus(palette)}>{checkpointStatus}</div>
                  ) : null}
                </div>
              </section>

              <section style={styles.settingsSection(palette)}>
                <h4 style={styles.settingsHeading(palette)}>Advanced</h4>

                <label style={styles.fieldLabel(palette)}>
                  <span>Command Allowlist</span>
                  <input
                    value={commandAllowlist}
                    onChange={(event) => setCommandAllowlist(event.target.value)}
                    style={styles.fieldInput(palette)}
                  />
                </label>

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
                  <span>Max Retries</span>
                  <input
                    type="number"
                    min={0}
                    max={5}
                    value={maxRetries}
                    onChange={(event) => setMaxRetries(Number(event.target.value) || 0)}
                    style={styles.fieldInput(palette)}
                  />
                </label>
              </section>

              {config ? (
                <section style={styles.settingsSection(palette)}>
                  <h4 style={styles.settingsHeading(palette)}>Backend</h4>
                  <div style={styles.workspaceMeta(palette)}>
                    <strong>Engine</strong>
                    <span>{config?.engine}</span>
                    <strong>Database</strong>
                    <span>{config?.database_path}</span>
                    <strong>Project</strong>
                    <span>{lastHealth?.project_root || 'Health check pending'}</span>
                  </div>
                  <div style={styles.sectionBlock}>
                    <div style={styles.sectionHeaderInline}>
                      <div style={styles.sectionLabel(palette)}>Runtime Diagnostics</div>
                      <button
                        type="button"
                        style={styles.iconTextButton(palette)}
                        onClick={() => void refreshRuntimeDiagnostics()}
                      >
                        <Zap size={14} />
                        Refresh
                      </button>
                    </div>
                    <div style={styles.eventList}>
                      {runtimeDiagnostics.checks.map((check) => (
                        <div
                          key={check.id}
                          style={styles.eventRow(palette, diagnosticStatusToEventStatus(check.status))}
                        >
                          <div>
                            <strong style={styles.eventTitle(palette)}>{check.label}</strong>
                            <div style={styles.eventDetail(palette)}>{check.detail}</div>
                          </div>
                          {renderRuntimeDiagnosticAction(check)}
                        </div>
                      ))}
                    </div>
                  </div>
                </section>
              ) : null}
            </div>

            <div style={styles.modalFooter}>
              <button type="button" style={styles.secondaryButton(palette)} onClick={() => setShowSettings(false)}>
                Cancel
              </button>
              <button type="button" style={styles.primaryButton(palette)} onClick={() => void saveAegisSettings()}>
                <Save size={16} />
                Save Settings
              </button>
            </div>

            {saveStatus ? <div style={styles.saveStatus(palette)}>{saveStatus}</div> : null}
          </div>
        </div>
      ) : null}

      {showMemoryEditor && workspaceRoot ? (
        <MemoryEditor
          workspaceRoot={workspaceRoot}
          onClose={() => setShowMemoryEditor(false)}
          palette={palette}
        />
      ) : null}

      {showApprovalSettings && workspaceRoot ? (
        <ApprovalSettings
          workspaceRoot={workspaceRoot}
          onClose={() => setShowApprovalSettings(false)}
          palette={palette}
        />
      ) : null}
    </div>
  );
}

function getPalette(isDarkMode: boolean) {
  if (isDarkMode) {
    return {
      bgGlow:
        'radial-gradient(circle at 72% 0%, rgba(220,38,38,0.18), transparent 24%), radial-gradient(circle at 45% -12%, rgba(59,130,246,0.10), transparent 32%), #05080d',
      bg: '#05080d',
      shell: 'rgba(9,13,20,0.88)',
      shellBorder: 'rgba(148,163,184,0.14)',
      card: 'rgba(12,17,25,0.94)',
      cardAlt: 'rgba(17,24,34,0.92)',
      control: 'rgba(12,17,25,0.86)',
      sidebar: 'rgba(5,8,13,0.92)',
      navActive: 'rgba(255,255,255,0.08)',
      settingsRail: 'rgba(0,0,0,0.10)',
      settingsActive: 'rgba(255,255,255,0.10)',
      muted: '#9ca3af',
      text: '#f4f7fb',
      textSoft: '#cbd5e1',
      input: '#0b1018',
      inputBorder: 'rgba(148,163,184,0.16)',
      accent: '#ef4444',
      accentSoft: 'rgba(239,68,68,0.16)',
      accentAlt: '#b91c1c',
      userBubble: 'rgba(17,24,34,0.96)',
      assistantBubble: 'rgba(11,16,24,0.96)',
      good: '#22c55e',
      bad: '#ef4444',
      warning: '#f59e0b',
      codeBg: '#060a10'
    };
  }

  return {
    bgGlow:
      'radial-gradient(circle at 80% -10%, rgba(220,38,38,0.12), transparent 25%), linear-gradient(135deg, #f8fafc 0%, #eef2f7 58%, #fff1f2 100%)',
    bg: '#f8fafc',
    shell: 'rgba(255,255,255,0.94)',
    shellBorder: 'rgba(15,23,42,0.12)',
    card: '#ffffff',
    cardAlt: '#f8fafc',
    control: '#ffffff',
    sidebar: 'rgba(255,255,255,0.96)',
    navActive: 'rgba(220,38,38,0.10)',
    settingsRail: 'rgba(248,250,252,0.92)',
    settingsActive: 'rgba(220,38,38,0.10)',
    muted: '#64748b',
    text: '#111827',
    textSoft: '#334155',
    input: '#ffffff',
    inputBorder: 'rgba(15,23,42,0.14)',
    accent: '#dc2626',
    accentSoft: 'rgba(220,38,38,0.10)',
    accentAlt: '#991b1b',
    userBubble: 'rgba(255,247,247,0.98)',
    assistantBubble: 'rgba(248,250,252,0.98)',
    good: '#16a34a',
    bad: '#dc2626',
    warning: '#b45309',
    codeBg: '#f8fafc'
  };
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
    padding: 10
  }),

  backdrop: (p: Palette): CSSProperties => ({
    position: 'absolute',
    inset: 0,
    background: p.bgGlow,
    zIndex: 0
  }),

  frame: {
    position: 'relative',
    zIndex: 1,
    maxWidth: 'none',
    margin: '0 auto',
    height: 'calc(100vh - 20px)',
    display: 'grid',
    gridTemplateColumns: '260px minmax(0, 1fr)',
    gridTemplateRows: '54px minmax(0, 1fr)',
    gap: 10
  } as CSSProperties,

  header: (p: Palette): CSSProperties => ({
    gridColumn: '2 / 3',
    gridRow: '1 / 2',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 16,
    padding: 0,
    borderRadius: 0,
    background: 'transparent',
    border: 'none',
    boxShadow: 'none'
  }),

  topSearch: (p: Palette): CSSProperties => ({
    width: 'min(620px, 52vw)',
    height: 44,
    borderRadius: 14,
    border: `1px solid ${p.inputBorder}`,
    background: p.control,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '0 14px',
    color: p.muted
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
    borderRadius: 10,
    display: 'grid',
    placeItems: 'center',
    background: 'linear-gradient(135deg, rgba(239,68,68,0.26), rgba(127,29,29,0.28))',
    border: `1px solid rgba(239,68,68,0.44)`,
    color: p.text,
    flexShrink: 0
  }),

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

  headerActions: {
    display: 'flex',
    alignItems: 'center',
    gap: 8
  } as CSSProperties,

  topStatusPill: (p: Palette, ok: boolean): CSSProperties => ({
    height: 40,
    padding: '0 14px',
    borderRadius: 10,
    border: `1px solid ${p.inputBorder}`,
    background: p.card,
    color: p.text,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 9,
    fontSize: 13,
    fontWeight: 800
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
    borderRadius: 10,
    border: `1px solid ${p.inputBorder}`,
    background: active ? p.settingsActive : p.card,
    color: p.text,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 13,
    fontWeight: 800,
    cursor: 'pointer',
    maxWidth: 240
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
    borderRadius: 10,
    border: `1px solid ${p.inputBorder}`,
    background: p.card,
    color: p.text,
    display: 'grid',
    placeItems: 'center',
    cursor: 'pointer'
  }),

  utilityBar: (p: Palette): CSSProperties => ({
    gridColumn: '1 / 2',
    gridRow: '1 / 3',
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
    alignItems: 'stretch',
    minHeight: 0,
    padding: 10,
    borderRadius: 14,
    background: p.sidebar,
    border: `1px solid ${p.shellBorder}`,
    boxShadow: 'none',
    overflow: 'hidden'
  }),

  utilityActions: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 8
  } as CSSProperties,

  sidebarBrand: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    minHeight: 54,
    padding: '4px 4px 10px'
  } as CSSProperties,

  primaryUtilityButton: (p: Palette): CSSProperties => ({
    width: '100%',
    height: 44,
    padding: '0 16px',
    borderRadius: 8,
    border: 'none',
    background: `linear-gradient(135deg, ${p.accent}, ${p.accentAlt})`,
    color: '#fff',
    fontWeight: 700,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 10,
    cursor: 'pointer'
  }),

  utilityActionButton: (p: Palette): CSSProperties => ({
    width: '100%',
    height: 38,
    borderRadius: 8,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt,
    color: p.text,
    display: 'grid',
    placeItems: 'center',
    cursor: 'pointer'
  }),

  sidebarNav: {
    display: 'grid',
    gap: 4
  } as CSSProperties,

  sidebarNavItem: (p: Palette, active: boolean): CSSProperties => ({
    width: '100%',
    minHeight: 42,
    borderRadius: 8,
    border: 'none',
    background: active ? p.navActive : 'transparent',
    color: p.text,
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '0 12px',
    cursor: 'pointer',
    fontSize: 14,
    fontWeight: active ? 800 : 650,
    textAlign: 'left'
  }),

  sidebarSectionLabel: (p: Palette): CSSProperties => ({
    color: p.muted,
    fontSize: 12,
    fontWeight: 800,
    padding: '8px 8px 0'
  }),

  searchWrap: (p: Palette): CSSProperties => ({
    height: 38,
    borderRadius: 8,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '0 14px',
    color: p.muted
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
    overflowY: 'auto',
    minHeight: 0,
    paddingRight: 2,
    scrollbarWidth: 'thin'
  } as CSSProperties,

  threadPill: (p: Palette, active: boolean): CSSProperties => ({
    width: '100%',
    minHeight: 36,
    padding: '0 10px',
    borderRadius: 6,
    border: 'none',
    background: active ? 'rgba(239,68,68,0.18)' : 'transparent',
    color: p.text,
    whiteSpace: 'normal',
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: active ? 700 : 500
  }),

  threadGroup: (p: Palette): CSSProperties => ({
    minHeight: 36,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    padding: '0 4px 0 0',
    borderRadius: 6,
    border: 'none',
    background: 'transparent',
    flex: '0 0 auto'
  }),

  sidebarUserCard: (p: Palette): CSSProperties => ({
    marginTop: 'auto',
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: 10,
    borderRadius: 10,
    border: `1px solid ${p.inputBorder}`,
    background: p.card
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
    cursor: 'pointer'
  }),

  mainGrid: (detailsVisible: boolean): CSSProperties => ({
    gridColumn: '2 / 3',
    gridRow: '2 / 3',
    display: 'grid',
    gridTemplateColumns: detailsVisible ? 'minmax(0, 1fr) 360px' : 'minmax(0, 1fr)',
    gap: 10,
    height: '100%',
    minHeight: 0
  }),

  chatCard: (p: Palette): CSSProperties => ({
    display: 'grid',
    gridTemplateRows: '1fr auto auto auto',
    minHeight: 0,
    borderRadius: 12,
    background: p.shell,
    border: `1px solid ${p.shellBorder}`,
    boxShadow: 'none',
    overflow: 'hidden'
  }),

  chatScroll: {
    overflowY: 'auto',
    padding: '18px',
    minHeight: 0
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
    padding: 16,
    borderRadius: 12,
    background: p.card,
    border: `1px solid ${p.inputBorder}`
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
    borderRadius: 12,
    display: 'grid',
    placeItems: 'center',
    background: p.accentSoft,
    border: `1px solid ${p.inputBorder}`,
    color: p.text,
    flexShrink: 0
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
    borderRadius: 12,
    background: p.card,
    border: `1px solid ${p.inputBorder}`
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
    padding: '24px 12px'
  } as CSSProperties,

  emptyLogo: (p: Palette): CSSProperties => ({
    width: 64,
    height: 64,
    borderRadius: 20,
    display: 'grid',
    placeItems: 'center',
    marginBottom: 18,
    background: p.accentSoft,
    color: p.text
  }),

  emptyTitle: (p: Palette): CSSProperties => ({
    margin: 0,
    fontSize: 30,
    lineHeight: 1.1,
    color: p.text
  }),

  emptyText: (p: Palette): CSSProperties => ({
    maxWidth: 700,
    margin: '12px auto 0',
    fontSize: 15,
    lineHeight: 1.7,
    color: p.muted
  }),

  promptGrid: {
    marginTop: 28,
    width: '100%',
    maxWidth: 860,
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: 12
  } as CSSProperties,

  promptCard: (p: Palette): CSSProperties => ({
    borderRadius: 18,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt,
    color: p.text,
    padding: '16px 18px',
    textAlign: 'left',
    fontSize: 14,
    lineHeight: 1.5,
    cursor: 'pointer'
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
    boxShadow: '0 10px 30px rgba(2,6,23,0.08)'
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
    background: p.shell,
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
    background: p.cardAlt
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
    fontWeight: 700
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
    padding: 12,
    borderTop: `1px solid ${p.inputBorder}`,
    background: p.card
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
    background: p.cardAlt
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
    marginBottom: 10,
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
    gap: 12,
    alignItems: 'end'
  } as CSSProperties,

  composerInput: (p: Palette): CSSProperties => ({
    minHeight: 64,
    maxHeight: 180,
    resize: 'vertical',
    width: '100%',
    borderRadius: 10,
    border: `1px solid ${p.inputBorder}`,
    background: p.input,
    color: p.text,
    padding: '16px 18px',
    outline: 'none',
    fontSize: 15,
    lineHeight: 1.5
  }),

  sendButton: (p: Palette, disabled: boolean): CSSProperties => ({
    width: 52,
    height: 52,
    borderRadius: 10,
    border: 'none',
    background: disabled ? p.cardAlt : `linear-gradient(135deg, ${p.accent}, ${p.accentAlt})`,
    color: disabled ? p.muted : '#fff',
    display: 'grid',
    placeItems: 'center',
    cursor: disabled ? 'not-allowed' : 'pointer'
  }),

  sidebar: {
    display: 'grid',
    gap: 10,
    minHeight: 0,
    overflowY: 'auto',
    alignContent: 'start',
    paddingRight: 2,
    scrollbarWidth: 'thin'
  } as CSSProperties,

  panelCard: (p: Palette): CSSProperties => ({
    minHeight: 0,
    borderRadius: 12,
    background: p.shell,
    border: `1px solid ${p.shellBorder}`,
    boxShadow: 'none',
    overflow: 'hidden',
    display: 'grid',
    gridTemplateRows: 'auto 1fr'
  }),

  panelHeader: (p: Palette): CSSProperties => ({
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 10,
    padding: '14px 16px',
    borderBottom: `1px solid ${p.inputBorder}`,
    background: p.cardAlt
  }),

  panelTitleWrap: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8
  } as CSSProperties,

  panelTitle: (p: Palette): CSSProperties => ({
    margin: 0,
    fontSize: 15,
    color: p.text
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
    padding: 14,
    overflow: 'visible',
    display: 'grid',
    gap: 14,
    alignContent: 'start'
  } as CSSProperties,

  replyCard: (p: Palette): CSSProperties => ({
    padding: 14,
    borderRadius: 18,
    background: p.cardAlt,
    border: `1px solid ${p.inputBorder}`
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
    borderRadius: 10,
    border: `1px solid ${p.inputBorder}`,
    background: p.cardAlt
  }),

  activityFilterButton: (p: Palette, active: boolean): CSSProperties => ({
    minHeight: 30,
    borderRadius: 8,
    border: 'none',
    background: active ? p.accent : 'transparent',
    color: active ? '#fff' : p.textSoft,
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 850
  }),

  eventRow: (p: Palette, status: ToolEvent['status']): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: '1fr auto',
    gap: 12,
    alignItems: 'start',
    padding: 11,
    borderRadius: 9,
    background: p.cardAlt,
    borderLeft: `4px solid ${status === 'ok' ? p.good : status === 'warning' ? p.warning : p.bad}`,
    borderTop: `1px solid ${p.inputBorder}`,
    borderRight: `1px solid ${p.inputBorder}`,
    borderBottom: `1px solid ${p.inputBorder}`
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
    color: p.accent,
    background: 'rgba(239,68,68,0.12)',
    border: '1px solid rgba(239,68,68,0.22)',
    fontSize: 12,
    fontWeight: 900
  }),

  activityRow: (p: Palette, status: 'ok' | 'warning' | 'error'): CSSProperties => ({
    display: 'grid',
    gridTemplateColumns: '54px 1fr',
    gap: 10,
    padding: '8px 0 8px 10px',
    borderLeft: `2px solid ${status === 'ok' ? p.good : status === 'warning' ? p.warning : p.bad}`,
    color: p.text
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
    background: p.cardAlt,
    lineHeight: 1.6
  }),

  workspaceMeta: (p: Palette): CSSProperties => ({
    display: 'grid',
    gap: 6,
    padding: 12,
    borderRadius: 16,
    background: p.cardAlt,
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

  settingsShell: {
    display: 'grid',
    gridTemplateColumns: '220px minmax(0, 1fr)',
    minHeight: 0,
    overflow: 'hidden'
  } as CSSProperties,

  settingsRail: (p: Palette): CSSProperties => ({
    display: 'grid',
    alignContent: 'start',
    gap: 6,
    padding: 18,
    borderRight: `1px solid ${p.inputBorder}`,
    background: p.settingsRail
  }),

  settingsTabButton: (p: Palette, active: boolean): CSSProperties => ({
    width: '100%',
    minHeight: 46,
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
    borderRadius: 12,
    padding: 18,
    background: p.cardAlt,
    border: `1px solid ${p.inputBorder}`,
    display: 'grid',
    gap: 14
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
    gap: 8
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
    background: p.shell,
    color: p.text,
    cursor: 'pointer',
    fontWeight: 600,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8
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

function buildAssistantSummary(response: AgentResponse): string {
  const parts: string[] = [];

  if (response.reply.trim()) {
    parts.push(response.reply.trim());
  }

  if (response.changes.length) {
    const pendingCount = response.changes.filter((change) => !isGeneratedChangeApplied(change, response.applied)).length;
    const generatedLabel = pendingCount
      ? 'Pending generated file changes (not written yet):'
      : 'Generated file changes:';
    parts.push(
      [
        generatedLabel,
        ...response.changes.map((change) => {
          const state = isGeneratedChangeApplied(change, response.applied) ? 'applied' : 'pending';
          return `- ${change.path} (${change.action}, ${state})`;
        })
      ].join('\n')
    );
  }

  if (response.applied.length) {
    parts.push(['Applied changes:', ...response.applied.map((item) => `- ${item}`)].join('\n'));
  }

  if (response.validation) {
    const validationOutput = [response.validation.stdout, response.validation.stderr]
      .map((item) => item.trim())
      .filter(Boolean)
      .join('\n');
    const validationLines = [
      `Validation: ${response.validation.exit_code === 0 ? 'passed' : 'needs attention'}`,
      response.validation.summary,
      response.validation.command ? `Command: ${response.validation.command}` : '',
      validationOutput ? ['Output:', '```shell', validationOutput, '```'].join('\n') : ''
    ].filter(Boolean);
    parts.push(validationLines.join('\n'));
  }

  if (response.task_plan) {
    parts.push(
      [
        'Planning intelligence:',
        `- route: ${routeProfileLabel(response.task_plan)}`,
        `- scale: ${response.task_plan.complexity}`,
        `- estimated slices: ${response.task_plan.estimated_slices}`,
        `- pass budget hint: ${response.task_plan.pass_budget_hint}`
      ].join('\n')
    );
  }

  if (response.completion_quality) {
    const qualityLines = [
      `Completion quality: ${response.completion_quality.status} (${Math.round(response.completion_quality.score * 100)}%)`,
      ...response.completion_quality.reasons.slice(0, 3).map((reason) => `- ${reason}`)
    ];
    parts.push(qualityLines.join('\n'));
  }

  return parts.join('\n\n');
}

function routeProfileLabel(plan: { route_profile?: Record<string, unknown> } | null | undefined): string {
  const profile = plan?.route_profile ?? {};
  const label = profile.label;
  const id = profile.id;
  if (typeof label === 'string' && label.trim()) return label;
  if (typeof id === 'string' && id.trim()) return id;
  return 'auto';
}

function formatEventTime(value: string): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatDateTime(value: string): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  return `${(size / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

function normalizeProjectRootKey(value: string): string {
  return value.trim().replace(/[\\/]+$/, '').toLowerCase();
}

function latestProjectThread(
  current: SavedConversation | null,
  candidate: SavedConversation | null
): SavedConversation | null {
  if (!candidate) return current;
  if (!current) return candidate;
  return new Date(candidate.updatedAt).getTime() > new Date(current.updatedAt).getTime() ? candidate : current;
}

function modelOptionKey(item: Pick<ManagedModelInfo, 'api' | 'endpoint' | 'name'>): string {
  return `${item.api || 'ollama'}::${item.endpoint || ''}::${item.name || ''}`;
}

function managedModelFromConfig(
  api: string,
  endpoint: string,
  name: string,
  ready: boolean,
  message: string
): ManagedModelInfo {
  const nextApi = api.trim() || 'ollama';
  const nextEndpoint = endpoint.trim() || (nextApi === 'ollama' ? 'http://127.0.0.1:11434' : '');
  const nextName = name.trim() || 'qwen2.5-coder:7b';

  return {
    provider_id: `active-${nextApi}-${nextName}`,
    label: 'Active configuration',
    api: nextApi,
    endpoint: nextEndpoint,
    name: nextName,
    local: ['ollama', 'lmstudio'].includes(nextApi),
    enabled: true,
    installed: ready,
    configured: true,
    active: true,
    pullable: false,
    health: ready ? 'available' : message || 'configured',
    roles: [],
    capabilities: [],
    size_bytes: null,
    modified_at: '',
    estimated_pull_bytes: null,
    notes: message || 'Current configured model target'
  };
}

function findManagedModelByName(models: ManagedModelInfo[], modelName: string): ManagedModelInfo | null {
  const normalized = modelName.trim().toLowerCase();
  if (!normalized) return null;
  return (
    models.find((item) => item.name.toLowerCase() === normalized) ||
    models.find((item) => `${item.name}:latest`.toLowerCase() === normalized) ||
    models.find((item) => item.name.replace(/:latest$/i, '').toLowerCase() === normalized.replace(/:latest$/i, '')) ||
    null
  );
}

function modelInventoryToManagedModels(models: ModelInfo[]): ManagedModelInfo[] {
  return models.map((item) => ({
    provider_id: item.id,
    label: item.provider,
    api: item.api,
    endpoint: item.endpoint,
    name: item.name,
    local: item.local,
    enabled: true,
    installed: item.available,
    configured: item.configured,
    active: item.configured,
    pullable: false,
    health: item.ready ? 'available' : item.message || 'unavailable',
    roles: capabilityNames(item.capabilities),
    capabilities: capabilityNames(item.capabilities),
    size_bytes: item.size,
    modified_at: item.modified_at,
    estimated_pull_bytes: null,
    notes: item.message
  }));
}

function capabilityNames(capabilities: ModelInfo['capabilities']): string[] {
  return Object.entries(capabilities)
    .filter(([, enabled]) => Boolean(enabled))
    .map(([name]) => name);
}

function loadDetailsPanelVisible(): boolean {
  try {
    const raw = window.localStorage.getItem(detailsPanelVisibleStorageKey);
    if (!raw) return true;
    return JSON.parse(raw) !== false;
  } catch {
    return true;
  }
}

function saveDetailsPanelVisible(visible: boolean) {
  try {
    window.localStorage.setItem(detailsPanelVisibleStorageKey, JSON.stringify(visible));
  } catch {
    // Layout preferences should never keep the app from opening.
  }
}

function loadQueueAutoSendPaused(): boolean {
  try {
    const raw = window.localStorage.getItem(queueAutoSendPausedStorageKey);
    return raw ? JSON.parse(raw) === true : false;
  } catch {
    return false;
  }
}

function saveQueueAutoSendPaused(paused: boolean) {
  try {
    window.localStorage.setItem(queueAutoSendPausedStorageKey, JSON.stringify(paused));
  } catch {
    // Queue preferences should never block chatting.
  }
}

function loadCollapsedDetailSections(): DetailPanelSection[] {
  try {
    const raw = window.localStorage.getItem(detailPanelSectionsStorageKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is DetailPanelSection =>
      detailPanelSectionOptions.includes(item as DetailPanelSection)
    );
  } catch {
    return [];
  }
}

function saveCollapsedDetailSections(sections: DetailPanelSection[]) {
  try {
    const validSections = detailPanelSectionOptions.filter((section) => sections.includes(section));
    window.localStorage.setItem(detailPanelSectionsStorageKey, JSON.stringify(validSections));
  } catch {
    // Layout preferences are nice to keep, but should never block the app.
  }
}

function loadSelectedWorkspaceFile(root: string): string {
  try {
    const rootKey = normalizeProjectRootKey(root);
    if (!rootKey) return '';
    const raw = window.localStorage.getItem(selectedWorkspaceFileStorageKey);
    if (!raw) return '';
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return '';
    const value = (parsed as Record<string, unknown>)[rootKey];
    return typeof value === 'string' ? value : '';
  } catch {
    return '';
  }
}

function saveSelectedWorkspaceFile(root: string, filePath: string) {
  try {
    const rootKey = normalizeProjectRootKey(root);
    if (!rootKey) return;
    const raw = window.localStorage.getItem(selectedWorkspaceFileStorageKey);
    const parsed = raw ? JSON.parse(raw) : {};
    const selections = parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};

    if (filePath.trim()) {
      (selections as Record<string, string>)[rootKey] = filePath;
    } else {
      delete (selections as Record<string, string>)[rootKey];
    }

    window.localStorage.setItem(selectedWorkspaceFileStorageKey, JSON.stringify(selections));
  } catch {
    // File preview memory should stay invisible if storage is unavailable.
  }
}

function loadCustomAgents(): CustomAgent[] {
  try {
    const raw = window.localStorage.getItem(customAgentsStorageKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Partial<CustomAgent>[];
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item): item is CustomAgent => Boolean(item?.id && item.name))
      .map((item) => {
        const nextMode =
          typeof item.mode === 'string' && ['build', 'develop', 'review', 'chat'].includes(item.mode)
            ? (item.mode as Mode)
            : 'build';
        return {
          id: item.id,
          name: item.name,
          perspective: item.perspective || defaultAgentPerspective,
          mission: item.mission || defaultAgentPerspective,
          mode: nextMode,
          modelName: item.modelName || '',
          createdAt: item.createdAt || new Date().toISOString()
        };
      });
  } catch {
    return [];
  }
}

function saveCustomAgents(agents: CustomAgent[]) {
  try {
    window.localStorage.setItem(customAgentsStorageKey, JSON.stringify(agents));
  } catch {
    // Browser storage can be unavailable in private contexts.
  }
}

function loadAutoMemoryFingerprints(): string[] {
  try {
    if (typeof window === 'undefined') return [];
    const raw = window.localStorage.getItem(autoMemoryFingerprintStorageKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is string => typeof item === 'string' && Boolean(item.trim())).slice(0, 120);
  } catch {
    return [];
  }
}

function saveAutoMemoryFingerprints(fingerprints: string[]) {
  try {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(autoMemoryFingerprintStorageKey, JSON.stringify(fingerprints.slice(-120)));
  } catch {
    // Conversation memory is helpful, but storage failures should never block chat.
  }
}

function mergeById<T extends { id: string }>(priority: T[], fallback: T[]): T[] {
  const merged = new Map<string, T>();

  for (const item of priority) {
    merged.set(item.id, item);
  }

  for (const item of fallback) {
    if (!merged.has(item.id)) {
      merged.set(item.id, item);
    }
  }

  return Array.from(merged.values());
}

function taskStatusToEventStatus(status: string): 'ok' | 'warning' | 'error' {
  if (status.includes('error') || status.includes('failure')) return 'error';
  if (status.includes('running') || status.includes('warning')) return 'warning';
  return 'ok';
}

function readinessStatusToEventStatus(status: string): 'ok' | 'warning' | 'error' {
  if (status === 'ready') return 'ok';
  if (status === 'needs_repair') return 'error';
  return 'warning';
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

function diagnosticStatusToEventStatus(status: 'ok' | 'warning' | 'error'): 'ok' | 'warning' | 'error' {
  return status;
}

function runtimeDiagnosticActionIcon(kind: RuntimeDiagnosticActionKind) {
  if (kind === 'setup_workspace') return <Wrench size={14} />;
  if (kind === 'run_validation') return <Play size={14} />;
  return <Zap size={14} />;
}

function formatStatusLabel(value: string): string {
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(' ');
}

function createValidationRepairTrailId(): string {
  return `repair-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function shouldOfferWorkspaceSetup(
  profile: WorkspaceProfileResponse | null,
  recipe: ValidationRecipe | null
): boolean {
  if (!profile) return false;
  if (!profile.has_manifest) return true;
  return !recipe?.command && profile.dependency_profile.validation_commands.length === 0;
}

function shouldOfferReadinessValidation(
  profile: WorkspaceProfileResponse | null,
  recipe: ValidationRecipe | null
): boolean {
  if (!profile) return false;
  if (!['needs_validation', 'needs_repair'].includes(profile.readiness.status)) return false;
  return Boolean(recipe?.command || profile.dependency_profile.validation_commands.length);
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function isAbortError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false;
  const candidate = error as { name?: unknown; message?: unknown };
  return candidate.name === 'AbortError' || candidate.message === 'Chat request stopped.';
}

export default App;
