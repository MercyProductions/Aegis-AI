using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Aegis.LocalAgent.VisualStudio.Models;
using Aegis.LocalAgent.VisualStudio.Options;
using Aegis.LocalAgent.VisualStudio.ToolWindows;
using Microsoft.VisualStudio.Shell;
using Microsoft.VisualStudio.Shell.Interop;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Aegis.LocalAgent.VisualStudio.Services
{
    internal sealed class AegisAgentRuntime
    {
        private readonly AsyncPackage package;
        private readonly OllamaClient ollama;
        private readonly SolutionScanner scanner;
        private readonly SolutionIntelligenceService intelligence;
        private readonly ProjectMemoryService memory;
        private readonly SafeEditService safeEdit;
        private readonly BuildService build;
        private readonly AegisCoreClient core;
        private AegisToolWindowControl control;
        private AgentSession session = new AgentSession();
        private readonly CoreRuntimeState coreState = new CoreRuntimeState();
        private BuildResult lastFailedBuild;

        public static AegisAgentRuntime Current { get; private set; }

        public AegisAgentRuntime(AsyncPackage package)
        {
            this.package = package;
            ollama = new OllamaClient(settingsProvider: GetSettings);
            scanner = new SolutionScanner(package);
            intelligence = new SolutionIntelligenceService();
            memory = new ProjectMemoryService();
            safeEdit = new SafeEditService(GetSettings);
            build = new BuildService(package);
            core = new AegisCoreClient(GetSettings);
        }

        public static void SetCurrent(AegisAgentRuntime runtime)
        {
            Current = runtime;
        }

        public bool ShouldAutoScanSolutions()
        {
            return GetSettings().AutoScanOnSolutionOpen;
        }

        public void AttachControl(AegisToolWindowControl attachedControl)
        {
            control = attachedControl;
            control?.SetAgentSession(session);
            control?.SetSettingsSummary(GetSettings());
            control?.SetRuntimeState(coreState);
            _ = RefreshSolutionInfoAsync();
        }

        public async Task ShowToolWindowAsync()
        {
            await ThreadHelper.JoinableTaskFactory.SwitchToMainThreadAsync();
            var window = await package.ShowToolWindowAsync(typeof(AegisToolWindow), 0, true, package.DisposalToken);
            if (window?.Frame == null)
            {
                throw new InvalidOperationException("Aegis Local Agent tool window could not be created.");
            }
        }

        public async Task RunHealthCheckAsync()
        {
            await ShowToolWindowAsync();
            SetStatus("Running Health Check");
            var context = await scanner.ScanAsync();
            var result = new HealthCheckResult();
            var settings = GetSettings();
            control?.SetSettingsSummary(settings);

            result.Lines.Add(string.IsNullOrWhiteSpace(context.SolutionRoot)
                ? "FAIL - No solution is open."
                : $"PASS - Solution open: {context.SolutionPath}");
            result.Lines.Add($"INFO - Ollama URL: {settings.OllamaUrl}");
            result.Lines.Add($"INFO - Aegis Core URL: {settings.AegisCoreUrl}");
            result.Lines.Add($"INFO - Default model: {settings.DefaultModel}");
            result.Lines.Add($"INFO - Fallback models: {string.Join(", ", settings.FallbackModels)}");
            result.Lines.Add($"INFO - Safety mode: {settings.SafetyMode}");
            result.Lines.Add($"INFO - Auto-scan on solution open: {settings.AutoScanOnSolutionOpen}");

            try
            {
                var memoryRoot = await memory.EnsureMemoryAsync(context);
                result.Lines.Add(string.IsNullOrWhiteSpace(memoryRoot)
                    ? "FAIL - .aegis memory root unavailable."
                    : $"PASS - .aegis writable: {memoryRoot}");
                if (string.IsNullOrWhiteSpace(memoryRoot))
                {
                    throw new InvalidOperationException("Open a solution before checking memory, indexes, and backups.");
                }

                await intelligence.UpdateAsync(context, force: true);
                await memory.UpdateFromScanAsync(context);
                var symbolIndex = System.IO.Path.Combine(memoryRoot, "symbol-index.json");
                var dependencyMap = System.IO.Path.Combine(memoryRoot, "dependency-map.json");
                result.Lines.Add(System.IO.File.Exists(symbolIndex) && System.IO.File.Exists(dependencyMap)
                    ? "PASS - Index files writable."
                    : "FAIL - Index files were not written.");
                result.Lines.Add(context.SymbolIndex.Count > 0 || context.DependencyMap.Count > 0
                    ? $"PASS - Indexes writable. Symbols: {context.SymbolIndex.Count}, dependencies: {context.DependencyMap.Count}"
                    : "WARN - Indexes wrote successfully, but no symbols/dependencies were detected.");
                var backupRoot = safeEdit.ResolveBackupBase(context);
                System.IO.Directory.CreateDirectory(backupRoot);
                var backupProbe = System.IO.Path.Combine(backupRoot, "health-check.tmp");
                System.IO.File.WriteAllText(backupProbe, DateTime.UtcNow.ToString("o"));
                System.IO.File.Delete(backupProbe);
                result.Lines.Add($"PASS - Backup location writable: {backupRoot}");
            }
            catch (Exception ex)
            {
                result.Lines.Add($"FAIL - .aegis/index writable: {SafeDiagnostic(ex)}");
            }

            try
            {
                var coreHealth = await core.TryHealthAsync(context.SolutionRoot);
                if (coreHealth.Success)
                {
                    result.Lines.Add("PASS - Aegis Core reachable.");
                    MarkCoreSuccess("Health check connected to Core.");
                    var sync = await core.SyncClientAsync(context, session.CoreWorkflowId);
                    if (sync.Success)
                    {
                        result.Lines.Add("PASS - Visual Studio client synced with Aegis Core.");
                    }
                    else
                    {
                        result.Lines.Add($"WARN - Aegis Core reachable, but client sync used fallback registration path: {sync.Error}");
                        try
                        {
                            await core.RegisterClientAsync(context);
                            result.Lines.Add("PASS - Visual Studio client registered with legacy Core registry.");
                        }
                        catch (Exception ex)
                        {
                            result.Lines.Add($"WARN - Legacy Core client registration failed: {SafeDiagnostic(ex)}");
                        }
                    }

                    var compatibility = await core.CheckCompatibilityAsync(context);
                    if (compatibility.Success)
                    {
                        var status = compatibility.Data.Value<string>("status") ?? "unknown";
                        var schema = compatibility.Data.Value<string>("required_schema_version") ?? string.Empty;
                        coreState.ReleaseCompatibilityStatus = status;
                        coreState.ReleaseSchemaVersion = schema;
                        coreState.LastOperation = "Compatibility: " + status;
                        result.Lines.Add($"PASS - Release compatibility checked. Status: {status}, schema: {schema}.");
                    }
                    else
                    {
                        coreState.ReleaseCompatibilityStatus = "Unavailable";
                        result.Lines.Add($"WARN - Aegis Core release compatibility unavailable: {compatibility.Error}");
                    }

                    var registry = await core.ModelRegistryAsync(context);
                    if (registry.Success)
                    {
                        var models = registry.Data["models"] as JArray ?? new JArray();
                        var providers = registry.Data["provider_status"] as JArray ?? new JArray();
                        var selected = registry.Data["selected_model"] as JObject ?? new JObject();
                        var selectedModel = selected.Value<string>("model_id") ?? selected.Value<string>("display_name") ?? string.Empty;
                        coreState.SelectedModel = selectedModel;
                        coreState.RouteProfile = registry.Data.Value<string>("active_profile") ?? string.Empty;
                        coreState.ProviderHealthSummary = $"{providers.Count} provider status item(s), {models.Count} model target(s)";
                        result.Lines.Add($"PASS - Aegis Core model registry available. Providers: {providers.Count}, models: {models.Count}.");
                        if (!string.IsNullOrWhiteSpace(selectedModel))
                        {
                            result.Lines.Add($"INFO - Core selected model: {selectedModel} via {coreState.RouteProfile}.");
                        }

                        var coreModelNames = models
                            .OfType<JObject>()
                            .Where(model => string.Equals(model.Value<string>("provider_id"), "ollama", StringComparison.OrdinalIgnoreCase))
                            .Select(model => model.Value<string>("model_id") ?? model.Value<string>("display_name"))
                            .Where(name => !string.IsNullOrWhiteSpace(name))
                            .Distinct(StringComparer.OrdinalIgnoreCase)
                            .ToArray();
                        if (coreModelNames.Length > 0)
                        {
                            control?.SetModels(coreModelNames);
                            control?.SetModelStatus($"Aegis Core registry online. {coreModelNames.Length} local model target(s).");
                        }
                    }
                    else
                    {
                        result.Lines.Add($"WARN - Aegis Core model registry unavailable: {registry.Error}");
                    }

                    var route = await core.RouteModelAsync(context, "generate_feature", "best_coding", new[] { "code" });
                    if (route.Success)
                    {
                        var explanation = route.Data["explanation"] as JObject ?? new JObject();
                        coreState.ModelRouteExplanation = explanation.Value<string>("reason_selected") ?? string.Empty;
                        var selectedProvider = explanation.Value<string>("selected_provider") ?? route.Data["selected"]?["provider_id"]?.ToString();
                        var selectedRouteModel = explanation.Value<string>("selected_model") ?? route.Data["selected"]?["model"]?.ToString();
                        result.Lines.Add($"PASS - Core model routing available. Selected: {selectedProvider}/{selectedRouteModel}.");
                    }
                    else
                    {
                        result.Lines.Add($"WARN - Aegis Core model routing unavailable: {route.Error}");
                    }

                    var quality = await core.QualityGatesAsync(context);
                    if (quality.Success)
                    {
                        UpdateQualityGateState(quality);
                        result.Lines.Add("PASS - Aegis Core quality gate dashboard available.");
                    }
                    else
                    {
                        result.Lines.Add($"WARN - Aegis Core quality gate dashboard unavailable: {quality.Error}");
                    }

                    var security = await core.SecurityStatusAsync(context);
                    if (security.Success)
                    {
                        var privacy = security.Data["privacy"] as JObject ?? new JObject();
                        var localApi = security.Data["local_api"] as JObject ?? new JObject();
                        result.Lines.Add($"PASS - Core trust status available. Privacy: {privacy.Value<string>("mode") ?? "unknown"}, token enforced: {localApi.Value<bool?>("token_enforced") == true}.");
                    }
                    else
                    {
                        result.Lines.Add($"WARN - Aegis Core trust status unavailable: {security.Error}");
                    }
                    UpdateCoreStatusUi();
                }
                else
                {
                    MarkCoreFailure(coreHealth.Error, fallbackActive: true);
                    result.Lines.Add($"WARN - Aegis Core unavailable: {coreHealth.Error}");
                }
            }
            catch (Exception ex)
            {
                MarkCoreFailure(SafeDiagnostic(ex), fallbackActive: true);
                result.Lines.Add($"WARN - Aegis Core unavailable: {SafeDiagnostic(ex)}");
            }

            try
            {
                var models = await ollama.ListModelsAsync();
                result.Lines.Add($"PASS - Ollama reachable. Models: {models.Count}");
                result.Lines.Add(models.Any(model => model.Name.Equals(settings.DefaultModel, StringComparison.OrdinalIgnoreCase))
                    ? $"PASS - Default model installed: {settings.DefaultModel}"
                    : $"WARN - Default model missing: {settings.DefaultModel}");
                foreach (var fallback in settings.FallbackModels)
                {
                    result.Lines.Add(models.Any(model => model.Name.Equals(fallback, StringComparison.OrdinalIgnoreCase))
                        ? $"PASS - Fallback model installed: {fallback}"
                        : $"WARN - Fallback model missing: {fallback}");
                }
                control?.SetModels(models.Select(model => model.Name));
                control?.SetModelStatus($"Ollama online. {models.Count} model(s) detected.");
            }
            catch (Exception ex)
            {
                result.Lines.Add($"FAIL - Ollama unreachable: {SafeDiagnostic(ex)}");
                control?.SetModelStatus("Ollama offline or unreachable.");
            }

            try
            {
                var snapshot = await build.ReadBuildSnapshotAsync();
                result.Lines.Add("PASS - Build integration available through Visual Studio SolutionBuild.");
                result.Lines.Add(string.IsNullOrWhiteSpace(snapshot.Summary)
                    ? "INFO - Build output is currently empty."
                    : "PASS - Build/Error snapshot readable.");
            }
            catch (Exception ex)
            {
                result.Lines.Add($"FAIL - Build integration check failed: {SafeDiagnostic(ex)}");
            }

            result.Success = result.Lines.All(line => !line.StartsWith("FAIL", StringComparison.OrdinalIgnoreCase));
            control?.SetValidationOutput(result.ToString());
            SetStatus(result.Success ? "Ready" : "Error");
            await RefreshSolutionInfoAsync(context);
        }

        public async Task ExplainCurrentFileAsync()
        {
            await ShowToolWindowAsync();
            SetStatus("Running Agent");
            var context = await PrepareContextAsync();
            var active = string.IsNullOrWhiteSpace(context.ActiveDocumentPath)
                ? "No active document is open."
                : SolutionScanner.ReadSafeText(context.ActiveDocumentPath);
            var prompt = string.Join(Environment.NewLine, new[]
            {
                "Explain this active Visual Studio document for a developer.",
                "Cover purpose, structure, risks, and how it relates to the current solution.",
                intelligence.BuildSmartContextText(context, "Explain current file", ContextLimit(42000)),
                "# Active File Content",
                active
            });
            var response = await ollama.ChatWithFallbackAsync(prompt, false, GetSelectedModel());
            AppendChat("Aegis", response);
            SetStatus("Ready");
        }

        public async Task ReviewSelectedCodeAsync()
        {
            await ShowToolWindowAsync();
            SetStatus("Running Agent");
            var context = await PrepareContextAsync();
            var selected = string.IsNullOrWhiteSpace(context.SelectedCode)
                ? SolutionScanner.ReadSafeText(context.ActiveDocumentPath)
                : context.SelectedCode;
            if (string.IsNullOrWhiteSpace(selected))
            {
                AppendChat("Aegis", "Open a document or select code before asking for review.");
                SetStatus("Waiting for code selection");
                return;
            }

            var prompt = string.Join(Environment.NewLine, new[]
            {
                "Review this code like a senior Visual Studio engineer.",
                "Prioritize bugs, build risks, maintainability, safety, missing tests, and concrete next steps.",
                intelligence.BuildSmartContextText(context, "Review selected code", ContextLimit(30000)),
                "# Code To Review",
                "```",
                selected,
                "```"
            });
            var response = await ollama.ChatWithFallbackAsync(prompt, false, GetSelectedModel());
            AppendChat("Aegis", response);
            SetStatus("Ready");
        }

        public async Task GenerateRoadmapAsync()
        {
            await ShowToolWindowAsync();
            SetStatus("Running Agent");
            var context = await PrepareContextAsync();
            var coreRoadmap = await core.GenerateRoadmapAsync(context);
            if (coreRoadmap.Success)
            {
                var markdown = coreRoadmap.Data.Value<string>("markdown")
                    ?? coreRoadmap.Data.SelectToken("roadmap.markdown")?.Value<string>()
                    ?? string.Empty;
                if (!string.IsNullOrWhiteSpace(markdown))
                {
                    await memory.WriteRoadmapAsync(context, markdown);
                    AppendChat("Aegis", markdown);
                    MarkCoreSuccess("Roadmap generated by Aegis Core.");
                    SetStatus("Roadmap updated");
                    await RefreshSolutionInfoAsync(context);
                    return;
                }
            }
            else
            {
                MarkCoreFailure(coreRoadmap.Error, fallbackActive: coreRoadmap.CanFallback);
                if (!coreRoadmap.CanFallback)
                {
                    AppendChat("Aegis", "Aegis Core rejected roadmap generation: " + coreRoadmap.Error);
                    SetStatus("Core blocked roadmap");
                    return;
                }
                AppendChat("Aegis", "Aegis Core roadmap generation is unavailable, so Visual Studio is using the local Ollama fallback.");
            }

            var prompt = string.Join(Environment.NewLine, new[]
            {
                "Generate a practical roadmap for this Visual Studio solution.",
                "Use these sections: current state, missing features, bugs/risks, technical debt, recommended next tasks, priority order, validation commands.",
                "Prefer small safe tasks that can be built and reviewed. Do not invent broad rewrites.",
                intelligence.BuildRoadmapContextText(context, ContextLimit(52000))
            });
            var roadmap = await ollama.ChatWithFallbackAsync(prompt, false, GetSelectedModel());
            await memory.WriteRoadmapAsync(context, roadmap);
            AppendChat("Aegis", roadmap);
            MarkCoreFallback("Roadmap used local Visual Studio/Ollama fallback.");
            SetStatus("Roadmap updated");
        }

        public async Task ContinueFromRoadmapAsync()
        {
            await ShowToolWindowAsync();
            SetStatus("Running Agent");
            var context = await PrepareContextAsync();
            var roadmap = await memory.ReadRoadmapAsync(context);
            if (string.IsNullOrWhiteSpace(roadmap))
            {
                AppendChat("Aegis", "No roadmap exists yet. Run Aegis: Generate Roadmap first.");
                SetStatus("No roadmap");
                return;
            }

            var workflow = await StartCoreWorkflowAsync(context, "continue_roadmap", "Continue from Visual Studio roadmap");
            var task = await ollama.ChatWithFallbackAsync(
                "Pick one highest-value safe next task from this roadmap and current solution memory. Return one concise instruction only." +
                Environment.NewLine + intelligence.BuildSmartContextText(context, "Continue from roadmap", ContextLimit(24000)) +
                Environment.NewLine + roadmap,
                false,
                GetSelectedModel());
            StartSession(AgentMode.ContinueCurrentSolution, "Continue from roadmap: " + task, BuildValidationTarget.Solution);
            AttachWorkflowToSession(workflow);
            await ProposeChangesAsync(context, "Continue from roadmap: " + task);
        }

        public async Task ContinueCurrentSolutionAsync()
        {
            await ShowToolWindowAsync();
            SetStatus("Running Agent");
            var context = await PrepareContextAsync();
            var snapshot = await build.ReadBuildSnapshotAsync();
            control?.SetBuildStatus(snapshot.Summary);
            StartSession(AgentMode.ContinueCurrentSolution, "Continue work on this Visual Studio solution.", BuildValidationTarget.Solution);
            AttachWorkflowToSession(await StartCoreWorkflowAsync(context, "generate_feature", session.Objective));
            await ProposeChangesAsync(context,
                "Continue work on this Visual Studio solution. Pick one small, high-value, low-risk task based on solution structure, current errors, and project memory. Propose edits only after explaining impact." +
                Environment.NewLine + snapshot.Summary);
        }

        public async Task ExplainSelectedExplorerFileAsync()
        {
            await ShowToolWindowAsync();
            SetStatus("Running Agent");
            var context = await PrepareContextAsync();
            var file = GetTargetFile(context);
            if (string.IsNullOrWhiteSpace(file))
            {
                AppendChat("Aegis", "Select a file in Solution Explorer or open a document first.");
                SetStatus("No file selected");
                return;
            }

            var prompt = string.Join(Environment.NewLine, new[]
            {
                "Explain this Visual Studio Solution Explorer file.",
                "Cover purpose, project role, dependencies, likely tests, risks, and how to modify it safely.",
                intelligence.BuildSmartContextText(context, "Explain Solution Explorer file " + SolutionScanner.MakeRelative(context.SolutionRoot, file), ContextLimit(36000)),
                $"# File: {SolutionScanner.MakeRelative(context.SolutionRoot, file)}",
                "```",
                SolutionScanner.Truncate(SolutionScanner.ReadSafeText(file), 22000),
                "```"
            });
            var response = await ollama.ChatWithFallbackAsync(prompt, false, GetSelectedModel());
            AppendChat("Aegis", response);
            SetStatus("Ready");
        }

        public async Task ReviewSelectedProjectAsync()
        {
            await ShowToolWindowAsync();
            SetStatus("Running Agent");
            var context = await PrepareContextAsync();
            var project = GetSelectedOrStartupProject(context);
            if (project == null)
            {
                AppendChat("Aegis", "Select a project in Solution Explorer or set a startup project first.");
                SetStatus("No project selected");
                return;
            }

            var prompt = string.Join(Environment.NewLine, new[]
            {
                "Review this Visual Studio project as a native VS workflow.",
                "Adapt to C#, C++, WPF, ASP.NET, or Unity as detected. Focus on architecture, project files, build risks, test gaps, and safe next steps.",
                ProjectContextText(project, context),
                intelligence.BuildSmartContextText(context, "Review selected project " + project.Name, ContextLimit(42000))
            });
            var response = await ollama.ChatWithFallbackAsync(prompt, false, GetSelectedModel());
            AppendChat("Aegis", response);
            SetStatus("Ready");
        }

        public async Task ReviewStartupProjectAsync()
        {
            await ShowToolWindowAsync();
            SetStatus("Running Agent");
            var context = await PrepareContextAsync();
            var project = context.Projects.FirstOrDefault(item => item.UniqueName.Equals(context.StartupProject, StringComparison.OrdinalIgnoreCase)
                || item.Name.Equals(context.StartupProject, StringComparison.OrdinalIgnoreCase))
                ?? GetSelectedOrStartupProject(context);
            if (project == null)
            {
                AppendChat("Aegis", "No startup project was detected.");
                SetStatus("No startup project");
                return;
            }

            var prompt = "Review the startup project and identify the safest high-value improvements." + Environment.NewLine + ProjectContextText(project, context);
            var response = await ollama.ChatWithFallbackAsync(prompt, false, GetSelectedModel());
            AppendChat("Aegis", response);
            SetStatus("Ready");
        }

        public async Task GenerateTestsForSelectedExplorerFileAsync()
        {
            await ShowToolWindowAsync();
            SetStatus("Running Agent");
            var context = await PrepareContextAsync();
            var file = GetTargetFile(context);
            if (string.IsNullOrWhiteSpace(file))
            {
                AppendChat("Aegis", "Select a file in Solution Explorer or open a document first.");
                SetStatus("No file selected");
                return;
            }

            StartSession(AgentMode.GenerateTests, "Generate focused tests for selected file.", BuildValidationTarget.SelectedProject, GetSelectedOrStartupProject(context));
            await ProposeChangesAsync(context,
                "Generate or update focused tests for this file using existing project test patterns. Keep changes minimal and approval-based." +
                Environment.NewLine + $"Target file: {SolutionScanner.MakeRelative(context.SolutionRoot, file)}");
        }

        public async Task AddFeatureToSelectedProjectAsync()
        {
            await ShowToolWindowAsync();
            var context = await PrepareContextAsync();
            var project = GetSelectedOrStartupProject(context);
            var projectText = project == null ? "current solution" : $"{project.Name} ({project.DetectedType})";
            StartSession(AgentMode.ImplementFeature, $"Add feature to {projectText}.", BuildValidationTarget.SelectedProject, project);
            control?.SetAgentRequest($"Describe the feature to add to {projectText}, then click Propose Changes.");
            AppendChat("Aegis", $"Ready to add a feature to {projectText}. Describe the feature in the Agent tab so I can propose safe diffs.");
            SetStatus("Waiting for feature request");
        }

        public async Task FixSelectedErrorAsync()
        {
            await ShowToolWindowAsync();
            SetStatus("Running Agent");
            var context = await PrepareContextAsync();
            var selected = await build.GetSelectedErrorAsync();
            if (selected == null)
            {
                AppendChat("Aegis", "No Error List item was detected. Build the solution or select an error first.");
                SetStatus("No selected error");
                return;
            }

            control?.SetSelectedError(selected.ToString());
            StartSession(AgentMode.FixSelectedError, "Fix selected Visual Studio error.", BuildValidationTarget.SelectedProject, GetSelectedOrStartupProject(context));
            AttachWorkflowToSession(await StartCoreWorkflowAsync(context, "repair_project", session.Objective));
            await ProposeChangesAsync(context,
                "Fix this selected Visual Studio Error List item using the smallest safe change. Explain impacted files and require approval." +
                Environment.NewLine + selected);
        }

        public async Task FixErrorsInSelectedProjectAsync()
        {
            await ShowToolWindowAsync();
            SetStatus("Running Agent");
            var context = await PrepareContextAsync();
            var project = GetSelectedOrStartupProject(context);
            StartSession(AgentMode.FixCurrentProject, "Fix errors in selected project.", BuildValidationTarget.SelectedProject, project);
            AttachWorkflowToSession(await StartCoreWorkflowAsync(context, "repair_project", session.Objective));
            var result = await build.BuildProjectAsync(project);
            await RecordValidationAsync(context, result);
            control?.SetValidationOutput(result.Output);
            control?.SetBuildStatus(result.Output);
            if (result.Success)
            {
                AppendChat("Aegis", "Selected project build passed. No errors were detected to repair.");
                SetStatus("Build passed");
                return;
            }

            StartSession(AgentMode.FixCurrentProject, "Fix all errors in selected Visual Studio project.", BuildValidationTarget.SelectedProject, project);
            await ProposeChangesAsync(context,
                "Fix all errors in the selected Visual Studio project using the smallest safe changes. Group by file, avoid unrelated edits, and propose approved diffs only." +
                Environment.NewLine + result.Output);
        }

        public async Task ExplainBuildFailureAsync()
        {
            await ShowToolWindowAsync();
            SetStatus("Running Agent");
            StartSession(AgentMode.ExplainBuildFailure, "Explain current Visual Studio build failure.", BuildValidationTarget.None);
            var context = await PrepareContextAsync();
            var snapshot = await build.ReadBuildSnapshotAsync();
            control?.SetBuildStatus(snapshot.Summary);
            var prompt = string.Join(Environment.NewLine, new[]
            {
                "Explain this Visual Studio build failure clearly.",
                "Group compiler, linker, warnings, failed projects, likely root cause, and safest fix path. Do not propose edits unless asked.",
                intelligence.BuildSmartContextText(context, "Explain build failure", ContextLimit(30000), snapshot),
                "# Build/Error Snapshot",
                snapshot.Summary
            });
            var response = await ollama.ChatWithFallbackAsync(prompt, false, GetSelectedModel());
            AppendChat("Aegis", response);
            SetStatus("Ready");
        }

        public async Task FixBuildErrorsAsync()
        {
            await ShowToolWindowAsync();
            SetStatus("Running Agent");
            var context = await PrepareContextAsync();
            StartSession(AgentMode.FixCurrentProject, "Fix Visual Studio build errors.", BuildValidationTarget.Solution);
            AttachWorkflowToSession(await StartCoreWorkflowAsync(context, "repair_project", session.Objective));
            var result = await build.BuildSolutionAsync();
            await RecordValidationAsync(context, result);
            control?.SetValidationOutput(result.Output);
            control?.SetBuildStatus(result.Output);
            if (result.Success)
            {
                AppendChat("Aegis", "Build Solution passed. No build errors were detected to repair.");
                SetStatus("Build passed");
                return;
            }

            StartSession(AgentMode.FixCurrentProject, "Fix Visual Studio build errors.", BuildValidationTarget.Solution);
            await ProposeChangesAsync(context, "Fix the Visual Studio build errors using the smallest safe changes." + Environment.NewLine + result.Output);
        }

        public async Task SendChatAsync(string message)
        {
            await ShowToolWindowAsync();
            if (string.IsNullOrWhiteSpace(message))
            {
                return;
            }

            AppendChat("You", message);
            SetStatus("Running Agent");
            var context = await PrepareContextAsync();
            var response = await ollama.ChatWithFallbackAsync(message + Environment.NewLine + intelligence.BuildSmartContextText(context, message, ContextLimit(36000)), false, GetSelectedModel());
            AppendChat("Aegis", response);
            SetStatus("Ready");
        }

        public async Task ProposeFeatureAsync(string request)
        {
            var context = await PrepareContextAsync();
            StartSession(AgentMode.ImplementFeature, request, BuildValidationTarget.SelectedProject, GetSelectedOrStartupProject(context));
            await ProposeChangesAsync(context, request);
        }

        public async Task RefactorSelectedCodeAsync()
        {
            await ShowToolWindowAsync();
            SetStatus("Running Agent");
            var context = await PrepareContextAsync();
            if (string.IsNullOrWhiteSpace(context.SelectedCode))
            {
                AppendChat("Aegis", "Select code in the active document before using refactor mode.");
                SetStatus("No selected code");
                return;
            }

            StartSession(AgentMode.RefactorSelectedCode, "Refactor selected code safely.", BuildValidationTarget.SelectedProject, GetSelectedOrStartupProject(context));
            await ProposeChangesAsync(context,
                "Refactor the selected code using the smallest safe edit. Preserve behavior, project style, public APIs, and architecture. Propose diffs only." +
                Environment.NewLine + "# Selected code" + Environment.NewLine + context.SelectedCode);
        }

        public async Task ApplyPendingProposalAsync()
        {
            var context = await PrepareContextAsync();
            var proposal = safeEdit.PendingProposal;
            IReadOnlyList<string> messages = Array.Empty<string>();
            if (proposal != null && !string.IsNullOrWhiteSpace(proposal.CoreProposalId))
            {
                var quality = await core.EvaluateQualityGatesAsync(context, proposal, approval: true);
                if (quality.Success)
                {
                    UpdateQualityGateState(quality);
                    if (quality.Envelope?.Value<bool?>("ok") == false || quality.Data.Value<bool?>("apply_allowed") == false)
                    {
                        var reason = QualityGateBlockReason(quality);
                        MarkCoreFailure(reason, fallbackActive: false);
                        messages = new[] { "Aegis Core quality gates blocked apply. Local fallback was not used.", reason };
                        control?.SetValidationOutput(string.Join(Environment.NewLine, messages));
                        SetStatus("Quality gate blocked apply");
                        return;
                    }

                    MarkCoreSuccess("Quality gates passed before apply.");
                }
                else if (!quality.CanFallback)
                {
                    MarkCoreFailure(quality.Error, fallbackActive: false);
                    messages = new[] { "Aegis Core rejected the quality gate check and local fallback was not used: " + quality.Error };
                    control?.SetValidationOutput(string.Join(Environment.NewLine, messages));
                    SetStatus("Quality gate failed");
                    return;
                }
                else
                {
                    MarkCoreFallback("Quality gate preflight unavailable; continuing with existing Visual Studio fallback rules. " + quality.Error);
                }

                var coreApply = await core.ApplyProposalAsync(context, proposal, applyAll: true, approval: true);
                var coreApplied = coreApply.Success && coreApply.Data.Value<bool?>("ok") == true;
                if (coreApplied)
                {
                    UpdateQualityGateState(coreApply);
                    proposal.CoreCheckpointId = coreApply.Data.Value<string>("checkpoint_id") ?? string.Empty;
                    session.CoreCheckpointId = proposal.CoreCheckpointId;
                    session.CoreJobId = coreApply.Data.Value<string>("job_id") ?? session.CoreJobId;
                    coreState.LastCheckpointId = proposal.CoreCheckpointId;
                    messages = BuildCoreApplyMessages(coreApply);
                    safeEdit.ClearPendingProposal();
                    MarkCoreSuccess("Applied approved proposal through Aegis Core.");
                }
                else if (coreApply.Success)
                {
                    var warnings = coreApply.Data["warnings"] as JArray ?? new JArray();
                    var reason = warnings.Count == 0 ? QualityGateBlockReason(coreApply) : string.Join("; ", warnings.Select(item => item.ToString()));
                    MarkCoreFailure(reason, fallbackActive: false);
                    messages = new[] { "Aegis Core did not apply the proposal, and local fallback was not used: " + reason };
                    control?.SetValidationOutput(string.Join(Environment.NewLine, messages));
                    SetStatus("Core blocked apply");
                    return;
                }
                else if (!coreApply.Success && !coreApply.CanFallback)
                {
                    MarkCoreFailure(coreApply.Error, fallbackActive: false);
                    messages = new[] { "Aegis Core rejected the apply request and local fallback was not used: " + coreApply.Error };
                    control?.SetValidationOutput(string.Join(Environment.NewLine, messages));
                    SetStatus("Core blocked apply");
                    return;
                }
                else
                {
                    MarkCoreFallback("Apply used local Visual Studio fallback. " + coreApply.Error);
                    messages = await safeEdit.ApplyPendingProposalAsync(context, memory);
                }
            }
            else
            {
                MarkCoreFallback("Apply used local Visual Studio fallback because no Core proposal ID was available.");
                messages = await safeEdit.ApplyPendingProposalAsync(context, memory);
            }

            control?.SetValidationOutput(string.Join(Environment.NewLine, messages));
            if (messages.Any(line => line.StartsWith("Applied", StringComparison.OrdinalIgnoreCase)))
            {
                session.ApprovalStatus = "Applied. Validating...";
                control?.SetAgentSession(session);
                if (!GetSettings().ValidateAfterApply)
                {
                    session.ApprovalStatus = "Applied. Validation skipped by settings.";
                    control?.SetAgentSession(session);
                    SetStatus("Ready");
                    return;
                }

                var result = await ValidateSessionAsync(context);
                await RecordValidationAsync(context, result);
                control?.SetValidationOutput(string.Join(Environment.NewLine, messages) + Environment.NewLine + Environment.NewLine + result.Output);
                control?.SetBuildStatus(result.Output);
                session.LastBuildResult = result;
                session.ApprovalStatus = result.Success ? "Validation passed." : "Validation failed.";
                control?.SetAgentSession(session);
                SetStatus(result.Success ? "Ready" : "Build Failed");

                if (!result.Success)
                {
                    await ProposeRepairIfAllowedAsync(context, result);
                }
            }
        }

        public async Task RollbackLastChangeAsync()
        {
            var context = await PrepareContextAsync();
            IReadOnlyList<string> messages;
            var checkpointId = !string.IsNullOrWhiteSpace(session.CoreCheckpointId)
                ? session.CoreCheckpointId
                : coreState.LastCheckpointId;
            if (string.IsNullOrWhiteSpace(checkpointId))
            {
                var checkpoints = await core.ListCheckpointsAsync(context, limit: 1);
                checkpointId = checkpoints.Success
                    ? checkpoints.Data.SelectToken("checkpoints[0].id")?.Value<string>() ?? string.Empty
                    : string.Empty;
                if (!checkpoints.Success)
                {
                    MarkCoreFailure(checkpoints.Error, fallbackActive: checkpoints.CanFallback);
                }
            }

            if (!string.IsNullOrWhiteSpace(checkpointId))
            {
                var restore = await core.RestoreCheckpointAsync(context, checkpointId);
                if (restore.Success && restore.Data.Value<bool?>("ok") == true)
                {
                    messages = BuildCoreRestoreMessages(restore);
                    MarkCoreSuccess("Restored checkpoint through Aegis Core.");
                }
                else if (restore.Success)
                {
                    var warnings = restore.Data["warnings"] as JArray ?? new JArray();
                    var reason = warnings.Count == 0 ? "Core returned ok=false." : string.Join("; ", warnings.Select(item => item.ToString()));
                    messages = new[] { "Aegis Core did not restore the checkpoint, and local fallback was not used: " + reason };
                    MarkCoreFailure(reason, fallbackActive: false);
                }
                else if (!restore.Success && !restore.CanFallback)
                {
                    messages = new[] { "Aegis Core rejected rollback and local fallback was not used: " + restore.Error };
                    MarkCoreFailure(restore.Error, fallbackActive: false);
                }
                else
                {
                    MarkCoreFallback("Rollback used local Visual Studio fallback. " + restore.Error);
                    messages = await safeEdit.RollbackLastChangeAsync(context);
                }
            }
            else
            {
                MarkCoreFallback("Rollback used local Visual Studio fallback because no Core checkpoint was available.");
                messages = await safeEdit.RollbackLastChangeAsync(context);
            }

            control?.SetValidationOutput(string.Join(Environment.NewLine, messages));
        }

        public async Task ReportErrorAsync(Exception ex)
        {
            await ShowToolWindowAsync();
            control?.SetValidationOutput(DiagnosticRedactor.RedactAndTruncate(ex?.ToString(), 4000));
            SetStatus("Error");
        }

        public async Task AllowOneMoreRepairAttemptAsync()
        {
            await ShowToolWindowAsync();
            if (lastFailedBuild == null)
            {
                AppendChat("Aegis", "There is no failed validation result to continue repairing.");
                return;
            }

            session.MaxRepairAttempts++;
            control?.SetAgentSession(session);
            var context = await PrepareContextAsync();
            await ProposeRepairIfAllowedAsync(context, lastFailedBuild, force: true);
        }

        public async Task BuildSolutionValidationAsync()
        {
            await ShowToolWindowAsync();
            var context = await PrepareContextAsync();
            StartSession(AgentMode.Idle, "Manual Build Solution", BuildValidationTarget.Solution);
            AttachWorkflowToSession(await StartCoreWorkflowAsync(context, "build_project", session.Objective));
            var result = await build.BuildSolutionAsync();
            await RecordValidationAsync(context, result);
        }

        public async Task BuildStartupProjectValidationAsync()
        {
            await ShowToolWindowAsync();
            var context = await PrepareContextAsync();
            var project = GetStartupProject(context) ?? GetSelectedOrStartupProject(context);
            StartSession(AgentMode.Idle, "Manual Build Startup Project", BuildValidationTarget.StartupProject, project);
            AttachWorkflowToSession(await StartCoreWorkflowAsync(context, "build_project", session.Objective));
            var result = await build.BuildProjectAsync(project);
            await RecordValidationAsync(context, result);
        }

        public async Task BuildSelectedProjectValidationAsync()
        {
            await ShowToolWindowAsync();
            var context = await PrepareContextAsync();
            var project = GetSelectedOrStartupProject(context);
            StartSession(AgentMode.Idle, "Manual Build Selected Project", BuildValidationTarget.SelectedProject, project);
            AttachWorkflowToSession(await StartCoreWorkflowAsync(context, "build_project", session.Objective));
            var result = await build.BuildProjectAsync(project);
            await RecordValidationAsync(context, result);
        }

        public async Task CleanSolutionAfterConfirmationAsync()
        {
            await ShowToolWindowAsync();
            var context = await PrepareContextAsync();
            StartSession(AgentMode.Idle, "Manual Clean Solution", BuildValidationTarget.Solution);
            AttachWorkflowToSession(await StartCoreWorkflowAsync(context, "build_project", session.Objective));
            var result = await build.CleanSolutionAsync();
            await RecordValidationAsync(context, result);
        }

        public async Task RebuildSolutionAfterConfirmationAsync()
        {
            await ShowToolWindowAsync();
            var context = await PrepareContextAsync();
            StartSession(AgentMode.Idle, "Manual Rebuild Solution", BuildValidationTarget.Solution);
            AttachWorkflowToSession(await StartCoreWorkflowAsync(context, "build_project", session.Objective));
            var result = await build.RebuildSolutionAsync();
            await RecordValidationAsync(context, result);
        }

        public async Task RescanSolutionIntelligenceAsync(bool showWindow = true)
        {
            if (showWindow)
            {
                await ShowToolWindowAsync();
            }

            SetStatus("Indexing");
            var context = await scanner.ScanAsync();
            await memory.EnsureMemoryAsync(context);
            await intelligence.UpdateAsync(context, force: true);
            await memory.UpdateFromScanAsync(context);
            var coreScan = await core.WorkspaceIntelligenceAsync(context, refresh: true);
            if (coreScan.Success)
            {
                MarkCoreSuccess("Workspace intelligence refreshed through Aegis Core.");
            }
            else if (coreScan.CanFallback)
            {
                MarkCoreFallback("Solution scan used Visual Studio fallback. " + coreScan.Error);
            }
            else
            {
                MarkCoreFailure(coreScan.Error, fallbackActive: false);
            }
            await RefreshSolutionInfoAsync(context);
            SetStatus(string.IsNullOrWhiteSpace(context.SolutionRoot) ? "No Solution" : "Ready");
            if (showWindow)
            {
                AppendChat("Aegis", $"Solution intelligence updated. {context.IntelligenceStatus.Summary}");
            }
        }

        private void StartSession(AgentMode mode, string objective, BuildValidationTarget target, ProjectContext project = null)
        {
            session = new AgentSession
            {
                Mode = mode,
                Objective = objective ?? string.Empty,
                ValidationTarget = target,
                TargetProjectName = project?.Name ?? string.Empty,
                ApprovalStatus = "Planning..."
            };
            lastFailedBuild = null;
            control?.SetAgentSession(session);
        }

        private async Task ProposeChangesAsync(SolutionContext context, string objective, bool isRepair = false)
        {
            SetStatus("Creating safe proposal...");
            if (string.IsNullOrWhiteSpace(session.CoreWorkflowId))
            {
                AttachWorkflowToSession(await StartCoreWorkflowAsync(context, WorkflowTypeForMode(session.Mode), objective));
            }

            var prompt = BuildProposalPrompt(context, objective, await memory.ReadMemoryContextAsync(context));
            var raw = await ollama.ChatWithFallbackAsync(prompt, true, GetSelectedModel());
            var proposal = ParseProposal(raw, objective);
            proposal.CoreWorkflowId = session.CoreWorkflowId;
            var validation = safeEdit.SetPendingProposal(context, proposal).ToList();
            if (!validation.Any())
            {
                var coreProposal = await core.ProposeChangesAsync(context, proposal, session.CoreTaskId, isRepair, session.RepairAttemptCount);
                if (coreProposal.Success)
                {
                    var record = coreProposal.Data["proposal"] as JObject;
                    proposal.CoreProposalId = record?.Value<string>("id") ?? string.Empty;
                    proposal.CoreProjectId = coreProposal.Data.Value<string>("project_id") ?? record?.Value<string>("project_id") ?? string.Empty;
                    proposal.CoreJobId = coreProposal.Data.Value<string>("job_id") ?? record?.Value<string>("job_id") ?? string.Empty;
                    proposal.CoreTaskId = coreProposal.Data.Value<string>("task_id") ?? record?.Value<string>("source_task_id") ?? session.CoreTaskId;
                    session.CoreProposalId = proposal.CoreProposalId;
                    session.CoreTaskId = proposal.CoreTaskId;
                    session.CoreJobId = proposal.CoreJobId;
                    coreState.PendingProposalId = proposal.CoreProposalId;
                    MarkCoreSuccess("Proposal recorded in Aegis Core.");
                }
                else if (!coreProposal.CanFallback)
                {
                    validation.Add("Aegis Core rejected the proposal: " + coreProposal.Error);
                    MarkCoreFailure(coreProposal.Error, fallbackActive: false);
                }
                else
                {
                    MarkCoreFallback("Proposal is local-only until Core is available. " + coreProposal.Error);
                }
            }

            UpdateSessionFromProposal(proposal, validation, isRepair);
            control?.SetProposal(proposal, validation, safeEdit.BuildPreviewText(context, proposal));
            await memory.AppendHistoryAsync(context, new
            {
                type = "proposal",
                at = DateTime.UtcNow,
                objective,
                mode = session.ModeLabel,
                repairAttempt = session.RepairAttemptCount,
                coreWorkflowId = proposal.CoreWorkflowId,
                coreProposalId = proposal.CoreProposalId,
                coreTaskId = proposal.CoreTaskId,
                proposal.Summary,
                files = proposal.FileEdits.Select(edit => edit.Path).ToList()
            });
            control?.SetAgentSession(session);
            SetStatus(validation.Any() ? "Proposal blocked by safety rules" : "Waiting for approval");
        }

        private void UpdateSessionFromProposal(AgentProposal proposal, IReadOnlyList<string> validation, bool isRepair)
        {
            session.CurrentPlan = BuildPlanText(proposal);
            session.AffectedFiles.Clear();
            foreach (var file in (proposal.AffectedFiles ?? new List<string>())
                .Concat(proposal.FileEdits?.Select(edit => edit.Path) ?? Enumerable.Empty<string>())
                .Where(file => !string.IsNullOrWhiteSpace(file))
                .Distinct(StringComparer.OrdinalIgnoreCase))
            {
                session.AffectedFiles.Add(file);
            }

            session.ApprovalStatus = validation.Any()
                ? "Blocked by safety checks."
                : isRepair ? "Repair proposal pending approval." : "Proposal pending approval.";
        }

        private static string BuildPlanText(AgentProposal proposal)
        {
            if (proposal == null)
            {
                return "No plan.";
            }

            var lines = new List<string>
            {
                proposal.Summary ?? string.Empty,
                string.Empty,
                "Rationale:",
                proposal.Rationale ?? string.Empty,
                string.Empty,
                "Steps:"
            };
            lines.AddRange((proposal.PlanSteps ?? new List<string>()).DefaultIfEmpty("Review proposal, approve diffs, validate in Visual Studio."));
            if (proposal.Notes?.Count > 0)
            {
                lines.Add("");
                lines.Add("Notes:");
                lines.AddRange(proposal.Notes);
            }

            return string.Join(Environment.NewLine, lines.Where(line => line != null));
        }

        private async Task<BuildResult> ValidateSessionAsync(SolutionContext context)
        {
            SetStatus("Validating with Aegis Core...");
            var target = session.ValidationTarget == BuildValidationTarget.Solution
                ? ResolvePreferredValidationTarget()
                : session.ValidationTarget;
            if (target == BuildValidationTarget.Solution)
            {
                var coreValidation = await core.RunValidationAsync(context, dryRun: false, taskId: session.CoreTaskId, timeoutSeconds: 180);
                if (coreValidation.Success)
                {
                    var coreResult = BuildResultFromCoreValidation(coreValidation);
                    if (CoreValidationRanCommand(coreValidation))
                    {
                        MarkCoreSuccess("Validation ran through Aegis Core.");
                        if (coreResult.Success)
                        {
                            return coreResult;
                        }

                        SetStatus("Collecting Visual Studio build details...");
                        var detailResult = await build.BuildSolutionAsync();
                        detailResult.Output = coreResult.Output + Environment.NewLine + Environment.NewLine + "Visual Studio diagnostic detail:" + Environment.NewLine + detailResult.Output;
                        return detailResult;
                    }
                }
                else if (!coreValidation.CanFallback)
                {
                    MarkCoreFailure(coreValidation.Error, fallbackActive: false);
                    return new BuildResult
                    {
                        Success = false,
                        Output = "Aegis Core rejected validation and local fallback was not used: " + coreValidation.Error
                    };
                }

                MarkCoreFallback("Validation used Visual Studio fallback. " + coreValidation.Error);
            }

            SetStatus("Validating with Visual Studio build...");
            switch (target)
            {
                case BuildValidationTarget.SelectedProject:
                    return await build.BuildProjectAsync(FindSessionProject(context) ?? GetSelectedOrStartupProject(context));
                case BuildValidationTarget.StartupProject:
                    return await build.BuildProjectAsync(GetStartupProject(context) ?? GetSelectedOrStartupProject(context));
                case BuildValidationTarget.None:
                    return new BuildResult { Success = true, Output = "No build validation target for this mode." };
                case BuildValidationTarget.Solution:
                default:
                    return await build.BuildSolutionAsync();
            }
        }

        private async Task RecordValidationAsync(SolutionContext context, BuildResult result)
        {
            session.LastBuildResult = result;
            session.ApprovalStatus = result.Success ? "Validation passed." : "Validation failed.";
            await memory.AppendValidationAsync(context, result);
            await RecordVisualStudioValidationWithCoreAsync(context, result);
            control?.SetValidationOutput(result.Output);
            control?.SetBuildStatus(result.Output);
            control?.SetAgentSession(session);
        }

        private async Task ProposeRepairIfAllowedAsync(SolutionContext context, BuildResult result, bool force = false)
        {
            lastFailedBuild = result;
            if (!force && session.RepairAttemptCount >= session.MaxRepairAttempts)
            {
                session.ApprovalStatus = "Repair limit reached. Approve continuing before more repair proposals.";
                control?.SetAgentSession(session);
                AppendChat("Aegis", $"Validation still fails, and the repair limit is reached ({session.RepairLabel}). Review the build output, then click Allow More Repair if you want another proposal.");
                SetStatus("Repair limit reached");
                return;
            }

            session.Mode = AgentMode.RepairValidation;
            session.RepairAttemptCount++;
            session.ApprovalStatus = "Creating repair proposal...";
            control?.SetAgentSession(session);
            await ProposeChangesAsync(context,
                "Repair the remaining Visual Studio validation failure with the smallest possible approved edit. Do not broaden scope. Preserve the previous intent." +
                Environment.NewLine +
                $"Repair attempt: {session.RepairLabel}" +
                Environment.NewLine +
                "# Failed validation" +
                Environment.NewLine +
                result.Output,
                isRepair: true);
        }

        private async Task<SolutionContext> PrepareContextAsync()
        {
            var context = await scanner.ScanAsync();
            await memory.EnsureMemoryAsync(context);
            await intelligence.UpdateAsync(context);
            await memory.UpdateFromScanAsync(context);
            await SyncCoreClientAsync(context);
            await RefreshSolutionInfoAsync(context);
            await RefreshNativeStateAsync();
            return context;
        }

        private async Task RefreshSolutionInfoAsync(SolutionContext existing = null)
        {
            var context = existing ?? await scanner.ScanAsync();
            control?.SetSolutionInfo(context);
            if (!string.IsNullOrWhiteSpace(context.SolutionRoot))
            {
                var roadmap = await memory.ReadRoadmapAsync(context);
                var architecture = await memory.ReadArchitectureAsync(context);
                control?.SetIntelligenceInfo(context, roadmap, architecture);
            }
        }

        private async Task RefreshNativeStateAsync()
        {
            var selected = await build.GetSelectedErrorAsync();
            control?.SetSelectedError(selected?.ToString() ?? "No selected Error List item detected.");
            var snapshot = await build.ReadBuildSnapshotAsync();
            control?.SetBuildStatus(snapshot.Summary);
        }

        private async Task SyncCoreClientAsync(SolutionContext context)
        {
            if (context == null || string.IsNullOrWhiteSpace(context.SolutionRoot))
            {
                return;
            }

            var result = await core.SyncClientAsync(
                context,
                session.CoreWorkflowId,
                status: "active",
                metadata: new Dictionary<string, object>
                {
                    ["solution"] = context.SolutionName,
                    ["startup_project"] = context.StartupProject,
                    ["selected_project"] = context.SelectedProjectName,
                    ["mode"] = session.ModeLabel,
                    ["validation_target"] = session.ValidationTarget.ToString()
                });
            if (result.Success)
            {
                MarkCoreSuccess("Visual Studio client synced with Core.");
            }
            else if (result.CanFallback)
            {
                MarkCoreFailure(result.Error, fallbackActive: true);
            }
            else
            {
                MarkCoreFailure(result.Error, fallbackActive: false);
            }
        }

        private async Task<CoreCallResult> StartCoreWorkflowAsync(SolutionContext context, string workflowType, string objective)
        {
            var result = await core.CreateWorkflowAsync(
                context,
                workflowType,
                objective,
                ContextFilesForCore(context),
                new Dictionary<string, object>
                {
                    ["visual_studio_mode"] = session.ModeLabel,
                    ["validation_target"] = session.ValidationTarget.ToString(),
                    ["target_project"] = session.TargetProjectName,
                    ["startup_project"] = context?.StartupProject ?? string.Empty
                });
            if (result.Success)
            {
                MarkCoreSuccess("Created Core workflow for " + workflowType + ".");
            }
            else if (result.CanFallback)
            {
                MarkCoreFallback("Workflow orchestration is local until Core is available. " + result.Error);
            }
            else
            {
                MarkCoreFailure(result.Error, fallbackActive: false);
            }

            return result;
        }

        private void AttachWorkflowToSession(CoreCallResult result)
        {
            if (result == null || !result.Success)
            {
                return;
            }

            var workflow = result.Data["workflow"] as JObject ?? result.Data;
            var workflowId = workflow.Value<string>("id") ?? string.Empty;
            if (string.IsNullOrWhiteSpace(workflowId))
            {
                return;
            }

            session.CoreWorkflowId = workflowId;
            coreState.ActiveWorkflowId = workflowId;
            coreState.ActiveWorkflowStatus = workflow.Value<string>("status") ?? string.Empty;
            var firstTask = workflow["tasks"]?.FirstOrDefault() as JObject;
            session.CoreTaskId = firstTask?.Value<string>("id") ?? session.CoreTaskId;
            control?.SetAgentSession(session);
            UpdateCoreStatusUi();
        }

        private static string WorkflowTypeForMode(AgentMode mode)
        {
            switch (mode)
            {
                case AgentMode.FixSelectedError:
                case AgentMode.FixCurrentProject:
                case AgentMode.RepairValidation:
                    return "repair_project";
                case AgentMode.ContinueCurrentSolution:
                case AgentMode.ImplementFeature:
                case AgentMode.RefactorSelectedCode:
                case AgentMode.GenerateTests:
                    return "generate_feature";
                case AgentMode.ExplainBuildFailure:
                    return "validate_project";
                case AgentMode.Idle:
                default:
                    return "chat_request";
            }
        }

        private static IEnumerable<string> ContextFilesForCore(SolutionContext context)
        {
            if (context == null || string.IsNullOrWhiteSpace(context.SolutionRoot))
            {
                return Enumerable.Empty<string>();
            }

            var files = new List<string>();
            if (!string.IsNullOrWhiteSpace(context.ActiveDocumentPath))
            {
                files.Add(SolutionScanner.MakeRelative(context.SolutionRoot, context.ActiveDocumentPath));
            }
            if (!string.IsNullOrWhiteSpace(context.SelectedExplorerPath))
            {
                files.Add(SolutionScanner.MakeRelative(context.SolutionRoot, context.SelectedExplorerPath));
            }
            files.AddRange(context.ImportantFiles.Take(8));
            return files
                .Where(file => !string.IsNullOrWhiteSpace(file) && !file.StartsWith("..", StringComparison.Ordinal))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .Take(20);
        }

        private async Task RecordVisualStudioValidationWithCoreAsync(SolutionContext context, BuildResult result)
        {
            var metadata = new JObject
            {
                ["source"] = "visual_studio",
                ["ok"] = result?.Success ?? false,
                ["errors"] = result?.Errors?.Count ?? 0,
                ["warnings"] = result?.Warnings?.Count ?? 0,
                ["failed_project"] = result?.FailedProjectName ?? string.Empty,
                ["mode"] = session.ModeLabel,
                ["validation_target"] = session.ValidationTarget.ToString(),
                ["summary"] = SolutionScanner.Truncate(result?.Output ?? string.Empty, 3000)
            };

            var validation = await core.RunValidationAsync(context, dryRun: true, taskId: session.CoreTaskId, repairAttempt: metadata, timeoutSeconds: 30);
            if (validation.Success)
            {
                session.CoreJobId = validation.Data.Value<string>("job_id") ?? session.CoreJobId;
                coreState.LatestValidationSummary = result.Success ? "Visual Studio validation passed" : "Visual Studio validation failed";
                MarkCoreSuccess("Visual Studio validation result recorded in Core.");
            }
            else if (validation.CanFallback)
            {
                MarkCoreFallback("Visual Studio validation was stored locally only. " + validation.Error);
            }
            else
            {
                MarkCoreFailure(validation.Error, fallbackActive: false);
            }

            if (!string.IsNullOrWhiteSpace(session.CoreWorkflowId))
            {
                await core.RecordWorkflowLogAsync(
                    context,
                    session.CoreWorkflowId,
                    result.Success ? "Visual Studio validation passed" : "Visual Studio validation failed",
                    metadata);
            }
        }

        private void UpdateQualityGateState(CoreCallResult result)
        {
            var data = result?.Data ?? new JObject();
            var evaluation = data["quality_gate"] as JObject
                ?? data["current_evaluation"] as JObject
                ?? (data["apply_allowed"] != null ? data : null);
            if (evaluation == null || evaluation.Count == 0)
            {
                return;
            }

            var scorecard = evaluation["scorecard"] as JObject ?? new JObject();
            var blockers = evaluation["blockers"] as JArray ?? new JArray();
            coreState.QualityGateStatus = evaluation.Value<bool?>("apply_allowed") == false ? "Blocked" : "Clear";
            coreState.QualityGateSummary = evaluation.Value<string>("summary") ?? string.Empty;
            coreState.QualityConfidenceScore = scorecard.Value<double?>("confidence_score") ?? 0;
            coreState.QualityValidationScore = scorecard.Value<double?>("validation_score") ?? 0;
            coreState.QualityRiskScore = scorecard.Value<double?>("risk_score") ?? 0;
            coreState.QualityBlockers.Clear();
            foreach (var blocker in blockers.Take(8))
            {
                var text = blocker.ToString();
                if (!string.IsNullOrWhiteSpace(text))
                {
                    coreState.QualityBlockers.Add(DiagnosticRedactor.RedactAndTruncate(text));
                }
            }

            UpdateCoreStatusUi();
        }

        private static string QualityGateBlockReason(CoreCallResult result)
        {
            var data = result?.Data ?? new JObject();
            var evaluation = data["quality_gate"] as JObject
                ?? data["current_evaluation"] as JObject
                ?? (data["apply_allowed"] != null ? data : new JObject());
            var blockers = evaluation["blockers"] as JArray ?? new JArray();
            if (blockers.Count > 0)
            {
                return DiagnosticRedactor.RedactAndTruncate(string.Join("; ", blockers.Select(item => item.ToString()).Take(5)));
            }

            var warnings = data["warnings"] as JArray ?? new JArray();
            if (warnings.Count > 0)
            {
                return DiagnosticRedactor.RedactAndTruncate(string.Join("; ", warnings.Select(item => item.ToString()).Take(5)));
            }

            return DiagnosticRedactor.RedactAndTruncate(evaluation.Value<string>("summary") ?? "Core quality gate did not allow apply.");
        }

        private static IReadOnlyList<string> BuildCoreApplyMessages(CoreCallResult result)
        {
            var applied = result.Data["applied"] as JArray ?? new JArray();
            var warnings = result.Data["warnings"] as JArray ?? new JArray();
            var lines = new List<string>
            {
                $"Applied approved Aegis proposal through Core. Files: {applied.Count}",
                "Core checkpoint: " + (result.Data.Value<string>("checkpoint_id") ?? "(none)"),
                "Core job: " + (result.Data.Value<string>("job_id") ?? "(none)")
            };
            lines.AddRange(applied.Select(item => "- " + item));
            if (warnings.Count > 0)
            {
                lines.Add("Warnings:");
                lines.AddRange(warnings.Select(item => "- " + item));
            }

            return lines;
        }

        private static IReadOnlyList<string> BuildCoreRestoreMessages(CoreCallResult result)
        {
            var restored = result.Data["restored"] as JArray ?? new JArray();
            var warnings = result.Data["warnings"] as JArray ?? new JArray();
            var lines = new List<string>
            {
                $"Rolled back {restored.Count} file(s) through Core checkpoint {result.Data.Value<string>("checkpoint_id")}.",
                "Pre-restore checkpoint: " + (result.Data.Value<string>("pre_restore_checkpoint_id") ?? "(none)"),
                "Core job: " + (result.Data.Value<string>("job_id") ?? "(none)")
            };
            lines.AddRange(restored.Select(item => "- " + item));
            if (warnings.Count > 0)
            {
                lines.Add("Warnings:");
                lines.AddRange(warnings.Select(item => "- " + item));
            }

            return lines;
        }

        private static BuildResult BuildResultFromCoreValidation(CoreCallResult result)
        {
            var validation = result.Data["validation"] as JObject ?? new JObject();
            var ok = validation.Value<bool?>("ok") == true;
            var stdout = validation.Value<string>("stdout") ?? string.Empty;
            var stderr = validation.Value<string>("stderr") ?? string.Empty;
            var command = validation["command"] is JArray commandArray
                ? string.Join(" ", commandArray.Select(item => item.ToString()))
                : validation.Value<string>("command") ?? string.Empty;
            var output = string.Join(Environment.NewLine, new[]
            {
                "Aegis Core validation: " + (ok ? "passed" : "failed"),
                "Command: " + (string.IsNullOrWhiteSpace(command) ? "(none detected)" : command),
                "Return code: " + (validation["returncode"]?.ToString() ?? "(none)"),
                string.Empty,
                "stdout:",
                stdout,
                string.Empty,
                "stderr:",
                stderr
            });
            var build = new BuildResult
            {
                Success = ok,
                Output = output,
                BuildOutput = stdout + Environment.NewLine + stderr
            };
            if (!ok)
            {
                build.Errors.Add(string.IsNullOrWhiteSpace(stderr) ? "Aegis Core validation failed." : stderr);
            }
            return build;
        }

        private static bool CoreValidationRanCommand(CoreCallResult result)
        {
            var validation = result.Data["validation"] as JObject;
            if (validation == null)
            {
                return false;
            }

            return validation["command"] != null
                && validation["command"].Type != JTokenType.Null
                && validation.Value<bool?>("dry_run") != true
                && validation.Value<bool?>("blocked") != true;
        }

        private void MarkCoreSuccess(string operation)
        {
            coreState.CoreConnected = true;
            coreState.FallbackActive = false;
            coreState.CoreStatus = "Connected";
            coreState.LastCoreError = string.Empty;
            AddCoreOperation(operation);
        }

        private void MarkCoreFailure(string error, bool fallbackActive)
        {
            coreState.CoreConnected = false;
            coreState.FallbackActive = fallbackActive;
            coreState.CoreStatus = fallbackActive ? "Disconnected - fallback active" : "Error - fallback blocked";
            coreState.LastCoreError = DiagnosticRedactor.RedactAndTruncate(error);
            AddCoreOperation(coreState.CoreStatus + ": " + coreState.LastCoreError);
        }

        private void MarkCoreFallback(string operation)
        {
            coreState.FallbackActive = true;
            coreState.LastCoreError = DiagnosticRedactor.RedactAndTruncate(operation);
            if (!coreState.CoreConnected)
            {
                coreState.CoreStatus = "Disconnected - fallback active";
            }
            AddCoreOperation(operation);
        }

        private void AddCoreOperation(string operation)
        {
            coreState.LastOperation = operation ?? string.Empty;
            coreState.LastUpdatedUtc = DateTime.UtcNow;
            if (!string.IsNullOrWhiteSpace(operation))
            {
                coreState.RecentOperations.Insert(0, $"{DateTime.Now:T} {operation}");
                if (coreState.RecentOperations.Count > 8)
                {
                    coreState.RecentOperations.RemoveRange(8, coreState.RecentOperations.Count - 8);
                }
            }
            UpdateCoreStatusUi();
        }

        private void UpdateCoreStatusUi()
        {
            control?.SetRuntimeState(coreState);
        }

        private string BuildProposalPrompt(SolutionContext context, string objective, string memoryContext)
        {
            return string.Join(Environment.NewLine, new[]
            {
                "You are Aegis Local Agent inside Visual Studio.",
                "Follow this loop: inspect context, create a clear plan, identify affected files, propose minimal diffs, wait for approval, then validate after approved application.",
                "Never rewrite the whole solution. Do not touch secrets, .env files, private keys, bin, obj, packages, .vs, generated files, or vendor folders.",
                "For C# respect namespaces, project files, NuGet packages, WPF XAML, and existing test patterns.",
                "For C++ respect header/source pairs, include paths, project configurations, linker settings, and x64/x86 differences.",
                "For Unity avoid Library, Temp, generated metadata churn, and prefer Unity-safe MonoBehaviour edits.",
                "Only include fileEdits when the complete replacement content is small and you are confident.",
                "Always explain impacted files, why each file changes, and the validation command to run.",
                "Return strict JSON only with this schema:",
                "{",
                "  \"summary\": \"short summary\",",
                "  \"risk\": \"low|medium|high\",",
                "  \"rationale\": \"why this approach was chosen\",",
                "  \"planSteps\": [\"step 1\", \"step 2\"],",
                "  \"affectedFiles\": [\"relative/path.cs\"],",
                "  \"notes\": [\"notes\"],",
                "  \"fileEdits\": [{\"path\":\"relative/path.cs\",\"reason\":\"why this file changes\",\"content\":\"complete replacement file content\"}],",
                "  \"commands\": [{\"command\":\"Build Solution\",\"reason\":\"why\"}],",
                "  \"tests\": [\"validation notes\"]",
                "}",
                "",
                "Objective:",
                objective,
                "",
                "Project memory:",
                memoryContext,
                "",
                "Solution context:",
                intelligence.BuildSmartContextText(context, objective, ContextLimit(52000))
            });
        }

        private static ProjectContext GetSelectedOrStartupProject(SolutionContext context)
        {
            if (context == null)
            {
                return null;
            }

            return context.Projects.FirstOrDefault(project => !string.IsNullOrWhiteSpace(context.SelectedProjectPath)
                    && project.Path.Equals(context.SelectedProjectPath, StringComparison.OrdinalIgnoreCase))
                ?? context.Projects.FirstOrDefault(project => !string.IsNullOrWhiteSpace(context.SelectedProjectName)
                    && project.Name.Equals(context.SelectedProjectName, StringComparison.OrdinalIgnoreCase))
                ?? context.Projects.FirstOrDefault(project => !string.IsNullOrWhiteSpace(context.StartupProject)
                    && (project.UniqueName.Equals(context.StartupProject, StringComparison.OrdinalIgnoreCase)
                        || project.Name.Equals(context.StartupProject, StringComparison.OrdinalIgnoreCase)))
                ?? context.Projects.FirstOrDefault();
        }

        private ProjectContext FindSessionProject(SolutionContext context)
        {
            return context?.Projects.FirstOrDefault(project => !string.IsNullOrWhiteSpace(session.TargetProjectName)
                    && project.Name.Equals(session.TargetProjectName, StringComparison.OrdinalIgnoreCase));
        }

        private static ProjectContext GetStartupProject(SolutionContext context)
        {
            return context?.Projects.FirstOrDefault(project => !string.IsNullOrWhiteSpace(context.StartupProject)
                && (project.UniqueName.Equals(context.StartupProject, StringComparison.OrdinalIgnoreCase)
                    || project.Name.Equals(context.StartupProject, StringComparison.OrdinalIgnoreCase)));
        }

        private static string GetTargetFile(SolutionContext context)
        {
            if (!string.IsNullOrWhiteSpace(context.SelectedExplorerPath) && System.IO.File.Exists(context.SelectedExplorerPath))
            {
                return context.SelectedExplorerPath;
            }

            if (!string.IsNullOrWhiteSpace(context.ActiveDocumentPath) && System.IO.File.Exists(context.ActiveDocumentPath))
            {
                return context.ActiveDocumentPath;
            }

            return string.Empty;
        }

        private static string ProjectContextText(ProjectContext project, SolutionContext context)
        {
            if (project == null)
            {
                return string.Empty;
            }

            return string.Join(Environment.NewLine, new[]
            {
                "# Target Project",
                $"Name: {project.Name}",
                $"Type: {project.DetectedType}",
                $"Path: {SolutionScanner.MakeRelative(context.SolutionRoot, project.Path)}",
                $"Root: {SolutionScanner.MakeRelative(context.SolutionRoot, project.Root)}",
                $"Frameworks: {string.Join(", ", project.TargetFrameworks)}",
                $"Packages: {string.Join(", ", project.Packages.Take(40))}",
                $"Namespaces: {string.Join(", ", project.Namespaces.Take(30))}",
                $"Symbols: {string.Join(", ", project.Symbols.Take(40))}",
                $"XAML: {string.Join(", ", project.XamlFiles.Take(20))}",
                $"Headers: {string.Join(", ", project.HeaderFiles.Take(20))}",
                $"Sources: {string.Join(", ", project.SourceFiles.Take(20))}",
                $"Include paths: {string.Join(", ", project.IncludePaths.Take(20))}",
                $"Configurations: {string.Join(", ", project.Configurations.Take(20))}",
                $"Unity: {string.Join(", ", project.UnitySignals.Take(20))}"
            });
        }

        private static AgentProposal ParseProposal(string raw, string objective)
        {
            try
            {
                var json = ExtractJson(raw);
                var proposal = JsonConvert.DeserializeObject<AgentProposal>(json) ?? new AgentProposal();
                proposal.Objective = objective;
                proposal.FileEdits = proposal.FileEdits ?? new System.Collections.Generic.List<FileEdit>();
                proposal.Commands = proposal.Commands ?? new System.Collections.Generic.List<AgentCommand>();
                proposal.PlanSteps = proposal.PlanSteps ?? new System.Collections.Generic.List<string>();
                proposal.AffectedFiles = proposal.AffectedFiles ?? new System.Collections.Generic.List<string>();
                proposal.Notes = proposal.Notes ?? new System.Collections.Generic.List<string>();
                proposal.Tests = proposal.Tests ?? new System.Collections.Generic.List<string>();
                return proposal;
            }
            catch
            {
                return new AgentProposal
                {
                    Objective = objective,
                    Summary = "Model returned non-JSON output; no edits will be applied.",
                    Risk = "medium",
                    Notes = { raw }
                };
            }
        }

        private static string ExtractJson(string raw)
        {
            if (string.IsNullOrWhiteSpace(raw))
            {
                return "{}";
            }

            var first = raw.IndexOf('{');
            var last = raw.LastIndexOf('}');
            return first >= 0 && last > first ? raw.Substring(first, last - first + 1) : raw;
        }

        private string GetSelectedModel()
        {
            return control?.SelectedModel;
        }

        private static string SafeDiagnostic(Exception ex)
        {
            return DiagnosticRedactor.RedactAndTruncate(ex?.Message);
        }

        private void AppendChat(string speaker, string message)
        {
            control?.AppendChat(speaker, message);
        }

        private void SetStatus(string status)
        {
            control?.SetStatus(status);
#pragma warning disable VSSDK007
            ThreadHelper.JoinableTaskFactory.RunAsync(async () =>
            {
                await ThreadHelper.JoinableTaskFactory.SwitchToMainThreadAsync();
                var statusBar = await package.GetServiceAsync(typeof(SVsStatusbar)) as IVsStatusbar;
                statusBar?.SetText("Aegis: " + (status ?? "Ready"));
            }).FileAndForget("AegisLocalAgent/StatusBar");
#pragma warning restore VSSDK007
        }

        private AegisSettingsSnapshot GetSettings()
        {
            try
            {
                AegisSettingsSnapshot snapshot = null;
                ThreadHelper.JoinableTaskFactory.Run(async () =>
                {
                    await ThreadHelper.JoinableTaskFactory.SwitchToMainThreadAsync();
                    if (package is Package shellPackage)
                    {
                        snapshot = (shellPackage.GetDialogPage(typeof(AegisOptionsPage)) as AegisOptionsPage)?.ToSnapshot();
                    }
                });

                return snapshot ?? AegisSettingsSnapshot.Default;
            }
            catch
            {
                return AegisSettingsSnapshot.Default;
            }
        }

        private int ContextLimit(int fallback)
        {
            var max = GetSettings().MaxContextSize;
            return Math.Max(8000, Math.Min(fallback, max));
        }

        private BuildValidationTarget ResolvePreferredValidationTarget()
        {
            switch (GetSettings().BuildValidationPreference)
            {
                case AegisBuildValidationPreference.StartupProject:
                    return BuildValidationTarget.StartupProject;
                case AegisBuildValidationPreference.SelectedProject:
                    return BuildValidationTarget.SelectedProject;
                case AegisBuildValidationPreference.None:
                    return BuildValidationTarget.None;
                case AegisBuildValidationPreference.Solution:
                default:
                    return BuildValidationTarget.Solution;
            }
        }
    }
}
