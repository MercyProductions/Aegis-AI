using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Aegis.LocalAgent.VisualStudio.Models;
using Aegis.LocalAgent.VisualStudio.Options;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Aegis.LocalAgent.VisualStudio.Services
{
    internal sealed class AegisCoreClient
    {
        public const string ClientId = "aegis-visual-studio";
        public const string SourceClient = "visual-studio";
        public const string ClientVersion = "0.1.1";
        public const string CoreContractVersion = "2026.05.12";

        private static readonly HttpClient Http = new HttpClient { Timeout = TimeSpan.FromSeconds(180) };
        private readonly Func<AegisSettingsSnapshot> settingsProvider;

        public AegisCoreClient(Func<AegisSettingsSnapshot> settingsProvider)
        {
            this.settingsProvider = settingsProvider ?? (() => AegisSettingsSnapshot.Default);
        }

        public async Task<JObject> HealthAsync(string workspaceRoot, CancellationToken cancellationToken = default)
        {
            var url = CoreUrl("/v1/health");
            if (!string.IsNullOrWhiteSpace(workspaceRoot))
            {
                url += "?workspace=" + Uri.EscapeDataString(workspaceRoot);
            }

            return await GetEnvelopeAsync(url, "health", "read Aegis Core health", cancellationToken, timeoutSeconds: 5);
        }

        public Task<CoreCallResult> TryHealthAsync(string workspaceRoot, CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(() => HealthAsync(workspaceRoot, cancellationToken));
        }

        public Task<CoreCallResult> ReleaseManifestAsync(SolutionContext context, CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var url = CoreUrl("/v1/release/manifest") + "?workspace=" + Uri.EscapeDataString(context?.SolutionRoot ?? string.Empty);
                return await GetEnvelopeAsync(url, "release.manifest", "read Aegis Core release manifest", cancellationToken, timeoutSeconds: 5);
            });
        }

        public Task<CoreCallResult> CheckCompatibilityAsync(SolutionContext context, CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var body = WorkspaceBody(context);
                body["client_type"] = "visual-studio-extension";
                body["client_version"] = ClientVersion;
                body["schema_version"] = CoreContractVersion;
                body["capabilities"] = BuildClientCapabilities();
                return await PostEnvelopeAsync("/v1/release/compatibility", body, "release.compatibility", "check Visual Studio/Core release compatibility", cancellationToken, timeoutSeconds: 5);
            });
        }

        public Task<CoreCallResult> SecurityStatusAsync(SolutionContext context, CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var url = CoreUrl("/v1/security/status") + "?workspace=" + Uri.EscapeDataString(context?.SolutionRoot ?? string.Empty);
                return await GetEnvelopeAsync(url, "security.status", "read Aegis Core security status", cancellationToken, timeoutSeconds: 5);
            });
        }

        public async Task RegisterClientAsync(SolutionContext context, CancellationToken cancellationToken = default)
        {
            var root = context?.SolutionRoot;
            if (string.IsNullOrWhiteSpace(root))
            {
                return;
            }

            var body = BuildClientBody(context, activeWorkflowId: null, status: "active", metadata: null);

            using (var content = JsonContent(body))
            {
                using (var request = new HttpRequestMessage(HttpMethod.Post, CoreUrl("/v1/clients/register")))
                {
                    request.Content = content;
                    ApplyCoreAuthHeaders(request);
                using (var response = await SendWithTimeoutAsync(
                    token => Http.SendAsync(request, token),
                    cancellationToken,
                    timeoutSeconds: 5))
                {
                    await EnsureSuccessAsync(response, "register Visual Studio client with Aegis Core");
                    var text = await response.Content.ReadAsStringAsync();
                    ParseCoreEnvelope(text, "client.registered", "register Visual Studio client with Aegis Core", requireOk: true);
                }
                }
            }
        }

        public Task<CoreCallResult> SyncClientAsync(
            SolutionContext context,
            string activeWorkflowId = null,
            string status = "active",
            IDictionary<string, object> metadata = null,
            CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var body = BuildClientBody(context, activeWorkflowId, status, metadata);
                return await PostEnvelopeAsync("/v1/clients/sync", body, "client.sync", "sync Visual Studio client with Aegis Core", cancellationToken, timeoutSeconds: 5);
            });
        }

        public Task<CoreCallResult> WorkspaceScanAsync(SolutionContext context, CancellationToken cancellationToken = default)
        {
            return TryWorkspacePostAsync(context, "/v1/workspaces/scan", "workspace.scan", "scan workspace through Aegis Core", cancellationToken, timeoutSeconds: 30);
        }

        public Task<CoreCallResult> WorkspaceIntelligenceAsync(SolutionContext context, bool refresh, CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var body = WorkspaceBody(context);
                body["refresh"] = refresh;
                body["persist"] = true;
                return await PostEnvelopeAsync("/v1/workspaces/intelligence", body, "workspace.intelligence", "refresh Aegis Core workspace intelligence", cancellationToken, timeoutSeconds: 45);
            });
        }

        public Task<CoreCallResult> ModelRegistryAsync(SolutionContext context, CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var url = CoreUrl("/v1/models/registry") + "?workspace=" + Uri.EscapeDataString(context?.SolutionRoot ?? string.Empty);
                return await GetEnvelopeAsync(url, "model.registry", "read Aegis Core model registry", cancellationToken, timeoutSeconds: 10);
            });
        }

        public Task<CoreCallResult> RouteModelAsync(
            SolutionContext context,
            string workflowType,
            string routeProfile = "best_coding",
            IEnumerable<string> requiredCapabilities = null,
            bool privacySensitive = false,
            CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var body = WorkspaceBody(context);
                body["task_type"] = string.IsNullOrWhiteSpace(workflowType) ? "chat" : workflowType;
                body["workflow_type"] = string.IsNullOrWhiteSpace(workflowType) ? null : workflowType;
                body["route_profile"] = string.IsNullOrWhiteSpace(routeProfile) ? null : routeProfile;
                body["required_capabilities"] = new JArray((requiredCapabilities ?? Enumerable.Empty<string>()).Where(item => !string.IsNullOrWhiteSpace(item)));
                body["privacy_sensitive"] = privacySensitive;
                body["allow_cloud"] = false;
                body["cloud_approved"] = false;
                body["context_files"] = new JArray(ContextFilesForRouting(context));
                return await PostEnvelopeAsync("/v1/models/route", body, "model.route", "route Visual Studio workflow through Aegis Core", cancellationToken, timeoutSeconds: 10);
            });
        }

        public Task<CoreCallResult> GenerateRoadmapAsync(SolutionContext context, CancellationToken cancellationToken = default)
        {
            return TryWorkspacePostAsync(context, "/v1/workspaces/roadmap", "workspace.roadmap", "generate roadmap through Aegis Core", cancellationToken, timeoutSeconds: 45);
        }

        public Task<CoreCallResult> CreateWorkflowAsync(
            SolutionContext context,
            string workflowType,
            string objective,
            IEnumerable<string> contextFiles = null,
            IDictionary<string, object> metadata = null,
            CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var body = WorkspaceBody(context);
                body["workflow_type"] = string.IsNullOrWhiteSpace(workflowType) ? "generate_feature" : workflowType;
                body["objective"] = objective ?? string.Empty;
                body["source_client"] = SourceClient;
                body["context_files"] = new JArray((contextFiles ?? Enumerable.Empty<string>())
                    .Where(item => !string.IsNullOrWhiteSpace(item))
                    .Take(20));
                body["metadata"] = MetadataObject(metadata);
                return await PostEnvelopeAsync("/v1/workflows", body, "workflow.created", "create Aegis Core workflow", cancellationToken, timeoutSeconds: 10);
            });
        }

        public Task<CoreCallResult> RecordWorkflowLogAsync(
            SolutionContext context,
            string workflowId,
            string summary,
            JObject payload = null,
            CancellationToken cancellationToken = default)
        {
            if (string.IsNullOrWhiteSpace(workflowId))
            {
                return Task.FromResult(CoreCallResult.FromError("No active Core workflow is available.", canFallback: true));
            }

            return TryCoreCallAsync(async () =>
            {
                var body = WorkspaceBody(context);
                body["action"] = "record_log";
                body["summary"] = summary ?? string.Empty;
                body["payload"] = payload ?? new JObject();
                var path = "/v1/workflows/" + Uri.EscapeDataString(workflowId) + "/step";
                return await PostEnvelopeAsync(path, body, "workflow.step", "record Aegis Core workflow log", cancellationToken, timeoutSeconds: 10);
            });
        }

        public Task<CoreCallResult> ProposeChangesAsync(
            SolutionContext context,
            AgentProposal proposal,
            string sourceTaskId,
            bool isRepair,
            int repairAttempt,
            CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var body = WorkspaceBody(context);
                body["summary"] = proposal?.Summary ?? string.Empty;
                body["source_client"] = SourceClient;
                body["source_task_id"] = string.IsNullOrWhiteSpace(sourceTaskId) ? null : sourceTaskId;
                body["risk"] = proposal?.Risk ?? "unknown";
                body["changes"] = BuildCoreChanges(proposal);
                if (isRepair)
                {
                    body["repair_attempt"] = new JObject
                    {
                        ["attempt"] = repairAttempt,
                        ["category"] = "visual_studio_validation_failure"
                    };
                }

                return await PostEnvelopeAsync("/v1/changes/propose", body, "changes.proposal", "record proposed changes in Aegis Core", cancellationToken, timeoutSeconds: 20);
            });
        }

        public Task<CoreCallResult> ApplyProposalAsync(
            SolutionContext context,
            AgentProposal proposal,
            bool applyAll,
            bool approval = true,
            bool dryRun = false,
            CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var body = WorkspaceBody(context);
                body["proposal_id"] = proposal?.CoreProposalId;
                body["apply_all"] = applyAll;
                body["dry_run"] = dryRun;
                body["source_client"] = SourceClient;
                body["task_id"] = string.IsNullOrWhiteSpace(proposal?.CoreTaskId) ? null : proposal.CoreTaskId;
                body["summary"] = proposal?.Summary ?? string.Empty;
                body["approval"] = approval;
                body["quality_gate_required"] = true;
                body["max_files_changed"] = 25;
                if (!string.IsNullOrWhiteSpace(proposal?.CoreProposalId))
                {
                    body["change_ids"] = new JArray();
                    body["paths"] = new JArray();
                }
                else
                {
                    body["changes"] = BuildCoreChanges(proposal);
                }

                return await PostEnvelopeAsync("/v1/changes/apply", body, "changes.apply", "apply approved changes through Aegis Core", cancellationToken, timeoutSeconds: 45);
            });
        }

        public Task<CoreCallResult> QualityGatesAsync(SolutionContext context, int limit = 20, CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var url = CoreUrl("/v1/quality-gates") + "?workspace=" + Uri.EscapeDataString(context?.SolutionRoot ?? string.Empty) + "&limit=" + Math.Max(1, Math.Min(200, limit));
                return await GetEnvelopeAsync(url, "quality.gates", "read Aegis Core quality gates", cancellationToken, timeoutSeconds: 10);
            });
        }

        public Task<CoreCallResult> EvaluateQualityGatesAsync(
            SolutionContext context,
            AgentProposal proposal,
            bool approval,
            bool validationRequired = false,
            CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var body = WorkspaceBody(context);
                body["workflow_id"] = string.IsNullOrWhiteSpace(proposal?.CoreWorkflowId) ? null : proposal.CoreWorkflowId;
                body["proposal_id"] = string.IsNullOrWhiteSpace(proposal?.CoreProposalId) ? null : proposal.CoreProposalId;
                body["changes"] = BuildCoreChanges(proposal);
                body["approval"] = approval;
                body["dry_run"] = true;
                body["persist"] = true;
                body["max_files_changed"] = 25;
                body["validation_required"] = validationRequired;
                body["metadata"] = new JObject
                {
                    ["source"] = SourceClient,
                    ["summary"] = proposal?.Summary ?? string.Empty,
                    ["risk"] = proposal?.Risk ?? string.Empty
                };
                return await PostEnvelopeAsync("/v1/quality-gates/evaluate", body, "quality.gates.evaluate", "evaluate proposal quality gates through Aegis Core", cancellationToken, timeoutSeconds: 30);
            });
        }

        public Task<CoreCallResult> ListCheckpointsAsync(SolutionContext context, int limit = 20, CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var url = CoreUrl("/v1/checkpoints") + "?workspace=" + Uri.EscapeDataString(context?.SolutionRoot ?? string.Empty) + "&limit=" + Math.Max(1, Math.Min(200, limit));
                return await GetEnvelopeAsync(url, "checkpoints.list", "list Aegis Core checkpoints", cancellationToken, timeoutSeconds: 10);
            });
        }

        public Task<CoreCallResult> RestoreCheckpointAsync(SolutionContext context, string checkpointId, bool dryRun = false, CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var body = WorkspaceBody(context);
                body["checkpoint_id"] = checkpointId ?? string.Empty;
                body["dry_run"] = dryRun;
                body["source_client"] = SourceClient;
                return await PostEnvelopeAsync("/v1/checkpoints/restore", body, "checkpoints.restore", "restore Aegis Core checkpoint", cancellationToken, timeoutSeconds: 45);
            });
        }

        public Task<CoreCallResult> RunValidationAsync(
            SolutionContext context,
            bool dryRun,
            string taskId = null,
            JObject repairAttempt = null,
            int timeoutSeconds = 120,
            CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var body = WorkspaceBody(context);
                body["command"] = null;
                body["timeout_seconds"] = Math.Max(1, Math.Min(900, timeoutSeconds));
                body["dry_run"] = dryRun;
                body["source_client"] = SourceClient;
                body["task_id"] = string.IsNullOrWhiteSpace(taskId) ? null : taskId;
                body["repair_attempt"] = repairAttempt;
                return await PostEnvelopeAsync("/v1/validation/run", body, "validation.run", "run validation through Aegis Core", cancellationToken, timeoutSeconds: Math.Max(10, timeoutSeconds + 10));
            });
        }

        public Task<CoreCallResult> StartAutopilotAsync(
            SolutionContext context,
            string objective,
            string mode = "semi_autonomous",
            string workflowType = "generate_feature",
            IEnumerable<string> targetFiles = null,
            CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var body = WorkspaceBody(context);
                var normalizedWorkflowType = string.IsNullOrWhiteSpace(workflowType) ? "generate_feature" : workflowType;
                var scopedFiles = (targetFiles ?? Enumerable.Empty<string>())
                    .Where(item => !string.IsNullOrWhiteSpace(item))
                    .Take(40)
                    .ToList();
                body["objective"] = objective ?? string.Empty;
                body["mode"] = string.IsNullOrWhiteSpace(mode) ? "semi_autonomous" : mode;
                body["workflow_type"] = normalizedWorkflowType;
                body["specialization"] = InferAutopilotSpecialization(normalizedWorkflowType, scopedFiles);
                body["target_files"] = new JArray(scopedFiles);
                body["constraints"] = new JArray("Preserve Visual Studio solution/project context.", "Require checkpoint before apply.");
                body["validation_commands"] = new JArray();
                body["execution_plan"] = new JObject();
                body["client_id"] = ClientId;
                body["approval"] = false;
                body["metadata"] = new JObject
                {
                    ["source"] = SourceClient,
                    ["solution_path"] = context?.SolutionPath ?? string.Empty,
                    ["startup_project"] = context?.StartupProject ?? string.Empty
                };
                return await PostEnvelopeAsync("/v1/autopilot/start", body, "autopilot.run", "start Auralith Autopilot through Aegis Core", cancellationToken, timeoutSeconds: 20);
            });
        }

        public Task<CoreCallResult> AutopilotSupervisionAsync(SolutionContext context, string autopilotId = null, CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var url = CoreUrl("/v1/autopilot/supervision") + "?workspace=" + Uri.EscapeDataString(context?.SolutionRoot ?? string.Empty);
                if (!string.IsNullOrWhiteSpace(autopilotId))
                {
                    url += "&autopilot_id=" + Uri.EscapeDataString(autopilotId);
                }
                return await GetEnvelopeAsync(url, "autopilot.supervision", "read Auralith Autopilot supervision", cancellationToken, timeoutSeconds: 10);
            });
        }

        public Task<CoreCallResult> AutopilotActionAsync(
            SolutionContext context,
            string autopilotId,
            string action,
            bool approval = false,
            string summary = "",
            JObject payload = null,
            CancellationToken cancellationToken = default)
        {
            if (string.IsNullOrWhiteSpace(autopilotId))
            {
                return Task.FromResult(CoreCallResult.FromError("No active Autopilot run is available.", canFallback: true));
            }

            return TryCoreCallAsync(async () =>
            {
                var body = WorkspaceBody(context);
                body["action"] = string.IsNullOrWhiteSpace(action) ? "advance" : action;
                body["approval"] = approval;
                body["summary"] = summary ?? string.Empty;
                body["payload"] = payload ?? new JObject();
                body["client_id"] = ClientId;
                var path = "/v1/autopilot/runs/" + Uri.EscapeDataString(autopilotId) + "/action";
                return await PostEnvelopeAsync(path, body, "autopilot.action", "send Auralith Autopilot action through Aegis Core", cancellationToken, timeoutSeconds: 20);
            });
        }

        public Task<CoreCallResult> AutopilotClientHooksAsync(CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                return await GetEnvelopeAsync(CoreUrl("/v1/autopilot/client-hooks"), "autopilot.client_hooks", "read Auralith Autopilot client hooks", cancellationToken, timeoutSeconds: 10);
            });
        }

        public Task<CoreCallResult> ClientSyncDashboardAsync(SolutionContext context, int limit = 20, CancellationToken cancellationToken = default)
        {
            return TryCoreCallAsync(async () =>
            {
                var url = CoreUrl("/v1/client-sync") + "?workspace=" + Uri.EscapeDataString(context?.SolutionRoot ?? string.Empty) + "&limit=" + Math.Max(1, Math.Min(200, limit));
                return await GetEnvelopeAsync(url, "client.sync.dashboard", "read Aegis Core client sync dashboard", cancellationToken, timeoutSeconds: 10);
            });
        }

        private Task<CoreCallResult> TryWorkspacePostAsync(
            SolutionContext context,
            string path,
            string expectedKind,
            string action,
            CancellationToken cancellationToken,
            int timeoutSeconds)
        {
            return TryCoreCallAsync(async () =>
            {
                return await PostEnvelopeAsync(path, WorkspaceBody(context), expectedKind, action, cancellationToken, timeoutSeconds);
            });
        }

        private async Task<CoreCallResult> TryCoreCallAsync(Func<Task<JObject>> action)
        {
            try
            {
                var envelope = await action();
                return new CoreCallResult
                {
                    Success = true,
                    CanFallback = true,
                    Kind = envelope.Value<string>("kind") ?? string.Empty,
                    Envelope = envelope,
                    Data = envelope["data"] as JObject ?? new JObject()
                };
            }
            catch (CoreRequestException ex)
            {
                return CoreCallResult.FromError(ex.Message, ex.CanFallback);
            }
            catch (TaskCanceledException ex)
            {
                return CoreCallResult.FromError("Aegis Core request timed out: " + DiagnosticRedactor.RedactAndTruncate(ex.Message));
            }
            catch (HttpRequestException ex)
            {
                return CoreCallResult.FromError("Aegis Core is unreachable: " + DiagnosticRedactor.RedactAndTruncate(ex.Message));
            }
            catch (Exception ex)
            {
                return CoreCallResult.FromError(DiagnosticRedactor.RedactAndTruncate(ex.Message));
            }
        }

        private async Task<JObject> PostEnvelopeAsync(
            string path,
            JObject body,
            string expectedKind,
            string action,
            CancellationToken cancellationToken,
            int timeoutSeconds)
        {
            using (var content = JsonContent(body))
            {
                using (var request = new HttpRequestMessage(HttpMethod.Post, CoreUrl(path)))
                {
                    request.Content = content;
                    ApplyCoreAuthHeaders(request);
                using (var response = await SendWithTimeoutAsync(
                    token => Http.SendAsync(request, token),
                    cancellationToken,
                    timeoutSeconds))
                {
                    await EnsureSuccessAsync(response, action);
                    var text = await response.Content.ReadAsStringAsync();
                    return ParseCoreEnvelope(text, expectedKind, action);
                }
                }
            }
        }

        private async Task<JObject> GetEnvelopeAsync(string url, string expectedKind, string action, CancellationToken cancellationToken, int timeoutSeconds)
        {
            using (var request = new HttpRequestMessage(HttpMethod.Get, url))
            {
                ApplyCoreAuthHeaders(request);
            using (var response = await SendWithTimeoutAsync(token => Http.SendAsync(request, token), cancellationToken, timeoutSeconds))
            {
                await EnsureSuccessAsync(response, action);
                var text = await response.Content.ReadAsStringAsync();
                return ParseCoreEnvelope(text, expectedKind, action);
            }
            }
        }

        private static void ApplyCoreAuthHeaders(HttpRequestMessage request)
        {
            var token = (Environment.GetEnvironmentVariable("AEGIS_CORE_LOCAL_TOKEN")
                ?? Environment.GetEnvironmentVariable("AEGIS_LOCAL_AUTH_TOKEN")
                ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(token))
            {
                return;
            }

            request.Headers.TryAddWithoutValidation("Authorization", "Bearer " + token);
            request.Headers.TryAddWithoutValidation("X-Aegis-Local-Token", token);
        }

        private static async Task<HttpResponseMessage> SendWithTimeoutAsync(
            Func<CancellationToken, Task<HttpResponseMessage>> send,
            CancellationToken cancellationToken,
            int timeoutSeconds)
        {
            using (var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken))
            {
                timeout.CancelAfter(TimeSpan.FromSeconds(Math.Max(1, timeoutSeconds)));
                return await send(timeout.Token);
            }
        }

        private static JObject WorkspaceBody(SolutionContext context)
        {
            if (string.IsNullOrWhiteSpace(context?.SolutionRoot))
            {
                throw new CoreRequestException("No Visual Studio solution root is available for Aegis Core.", canFallback: true);
            }

            return new JObject
            {
                ["workspace"] = context?.SolutionRoot ?? string.Empty
            };
        }

        private static JObject BuildClientBody(SolutionContext context, string activeWorkflowId, string status, IDictionary<string, object> metadata)
        {
            var body = WorkspaceBody(context);
            body["client_id"] = ClientId;
            body["client_type"] = "visual-studio-extension";
            body["name"] = "Aegis Local Agent for Visual Studio";
            body["version"] = ClientVersion;
            body["capabilities"] = BuildClientCapabilities();
            body["active_workflow_id"] = string.IsNullOrWhiteSpace(activeWorkflowId) ? null : activeWorkflowId;
            body["status"] = string.IsNullOrWhiteSpace(status) ? "active" : status;
            body["metadata"] = MetadataObject(metadata);
            return body;
        }

        private static JArray BuildClientCapabilities()
        {
            return new JArray(
                "core_health",
                "client_sync",
                "workflow_runtime",
                "solution_scan",
                "roadmap",
                "proposal_preview",
                "editing_runtime",
                "checkpoint_restore",
                "validation_tracking",
                "core_quality_gates",
                "quality_gate_preview",
                "core_autopilot_runtime",
                "autopilot_specializations",
                "autopilot_supervision",
                "autopilot_approval_hooks",
                "autopilot_replay",
                "release_compatibility",
                "release_manifest",
                "core_security_status",
                "visual_studio_build",
                "error_list",
                "repair_workflow");
        }

        private static string InferAutopilotSpecialization(string workflowType, IEnumerable<string> targetFiles)
        {
            var normalizedWorkflow = (workflowType ?? string.Empty).ToLowerInvariant();
            if (normalizedWorkflow.Contains("repair"))
            {
                return "repair_autopilot";
            }

            if (normalizedWorkflow.Contains("build") || normalizedWorkflow.Contains("deploy"))
            {
                return "deployment_autopilot";
            }

            if (normalizedWorkflow.Contains("scan") || normalizedWorkflow.Contains("research"))
            {
                return "workspace_intelligence_autopilot";
            }

            foreach (var file in targetFiles ?? Enumerable.Empty<string>())
            {
                var normalizedPath = (file ?? string.Empty).Replace('\\', '/').ToLowerInvariant();
                if (normalizedPath.EndsWith(".sln") ||
                    normalizedPath.EndsWith(".csproj") ||
                    normalizedPath.EndsWith(".vbproj") ||
                    normalizedPath.EndsWith(".vcxproj") ||
                    normalizedPath.EndsWith(".yml") ||
                    normalizedPath.EndsWith(".yaml") ||
                    normalizedPath.Contains("dockerfile") ||
                    normalizedPath.Contains("directory.build."))
                {
                    return "deployment_autopilot";
                }
            }

            return "feature_autopilot";
        }

        private static JArray BuildCoreChanges(AgentProposal proposal)
        {
            var changes = new JArray();
            if (proposal?.FileEdits == null)
            {
                return changes;
            }

            var index = 1;
            foreach (var edit in proposal.FileEdits)
            {
                var id = string.IsNullOrWhiteSpace(edit.Id) ? "vs-change-" + index.ToString("D3") : edit.Id;
                changes.Add(new JObject
                {
                    ["id"] = id,
                    ["action"] = "update",
                    ["path"] = edit.Path ?? string.Empty,
                    ["content"] = edit.Content ?? string.Empty,
                    ["summary"] = edit.Reason ?? proposal.Summary ?? string.Empty,
                    ["selected"] = true
                });
                index++;
            }

            return changes;
        }

        private static IEnumerable<string> ContextFilesForRouting(SolutionContext context)
        {
            if (context == null)
            {
                return Enumerable.Empty<string>();
            }

            return context.ImportantFiles
                .Concat(context.RecentFiles)
                .Concat((context.Projects ?? new List<ProjectContext>()).SelectMany(project => project.Files ?? new List<string>()))
                .Where(item => !string.IsNullOrWhiteSpace(item))
                .Take(20)
                .ToArray();
        }

        private static JObject MetadataObject(IDictionary<string, object> metadata)
        {
            var result = new JObject();
            if (metadata == null)
            {
                return result;
            }

            foreach (var item in metadata)
            {
                result[item.Key] = item.Value == null ? JValue.CreateNull() : JToken.FromObject(item.Value);
            }

            return result;
        }

        private static StringContent JsonContent(JObject body)
        {
            return new StringContent((body ?? new JObject()).ToString(Formatting.None), Encoding.UTF8, "application/json");
        }

        private static async Task EnsureSuccessAsync(HttpResponseMessage response, string action)
        {
            if (response.IsSuccessStatusCode)
            {
                return;
            }

            var text = await response.Content.ReadAsStringAsync();
            var detail = ExtractErrorDetail(text);
            var message = $"Could not {action}: HTTP {(int)response.StatusCode}";
            if (!string.IsNullOrWhiteSpace(detail))
            {
                message += $" - {detail}";
            }

            throw new CoreRequestException(message, CanFallbackFromStatus(response.StatusCode));
        }

        private static bool CanFallbackFromStatus(HttpStatusCode statusCode)
        {
            return statusCode == HttpStatusCode.NotFound
                || statusCode == HttpStatusCode.RequestTimeout
                || statusCode == HttpStatusCode.InternalServerError
                || statusCode == HttpStatusCode.BadGateway
                || statusCode == HttpStatusCode.ServiceUnavailable
                || statusCode == HttpStatusCode.GatewayTimeout
                || (int)statusCode == 501;
        }

        private static string ExtractErrorDetail(string responseText)
        {
            if (string.IsNullOrWhiteSpace(responseText))
            {
                return string.Empty;
            }

            try
            {
                var parsed = JObject.Parse(responseText);
                return DiagnosticRedactor.RedactAndTruncate(parsed.Value<string>("detail"));
            }
            catch (JsonException)
            {
                return DiagnosticRedactor.RedactAndTruncate(responseText);
            }
        }

        private static JObject ParseCoreEnvelope(string responseText, string expectedKind, string action, bool requireOk = false)
        {
            if (string.IsNullOrWhiteSpace(responseText))
            {
                throw new CoreRequestException($"Could not {action}: Aegis Core returned an empty response.");
            }

            JObject parsed;
            try
            {
                parsed = JObject.Parse(responseText);
            }
            catch (JsonException ex)
            {
                throw new CoreRequestException($"Could not {action}: Aegis Core returned invalid JSON - {ex.Message}", canFallback: true, innerException: ex);
            }

            var apiVersion = parsed.Value<string>("api_version");
            if (!string.Equals(apiVersion, "v1", StringComparison.OrdinalIgnoreCase))
            {
                var safeApiVersion = string.IsNullOrWhiteSpace(apiVersion) ? "missing" : DiagnosticRedactor.RedactAndTruncate(apiVersion);
                throw new CoreRequestException($"Could not {action}: Aegis Core response used unexpected api_version: {safeApiVersion}.");
            }

            var kind = parsed.Value<string>("kind");
            if (!string.Equals(kind, expectedKind, StringComparison.OrdinalIgnoreCase))
            {
                var safeKind = string.IsNullOrWhiteSpace(kind) ? "missing" : DiagnosticRedactor.RedactAndTruncate(kind);
                throw new CoreRequestException($"Could not {action}: Aegis Core response kind mismatch: expected {expectedKind}, got {safeKind}.");
            }

            JToken okToken;
            if (requireOk && parsed.TryGetValue("ok", out okToken) && okToken.Type == JTokenType.Boolean && !okToken.Value<bool>())
            {
                throw new CoreRequestException($"Could not {action}: {ExtractCoreEnvelopeError(parsed)}", canFallback: false);
            }

            return parsed;
        }

        private static string ExtractCoreEnvelopeError(JObject envelope)
        {
            var data = envelope["data"] as JObject;
            var detail = data?.Value<string>("error")
                ?? data?.Value<string>("message")
                ?? envelope.Value<string>("detail");
            if (!string.IsNullOrWhiteSpace(detail))
            {
                return DiagnosticRedactor.RedactAndTruncate(detail);
            }

            var deprecations = envelope["deprecations"] as JArray;
            if (deprecations != null && deprecations.Count > 0)
            {
                return DiagnosticRedactor.RedactAndTruncate(string.Join("; ", deprecations));
            }

            return "Core returned ok=false.";
        }

        private string CoreUrl(string path)
        {
            var settings = settingsProvider?.Invoke() ?? AegisSettingsSnapshot.Default;
            return AegisSettingsSnapshot.BuildServiceUrl(settings.AegisCoreUrl, "http://127.0.0.1:8788", path);
        }

        private sealed class CoreRequestException : InvalidOperationException
        {
            public CoreRequestException(string message, bool canFallback = true, Exception innerException = null)
                : base(message, innerException)
            {
                CanFallback = canFallback;
            }

            public bool CanFallback { get; }
        }
    }
}
