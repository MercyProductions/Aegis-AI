using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Aegis.LocalAgent.VisualStudio.Models;
using Aegis.LocalAgent.VisualStudio.Options;
using Aegis.LocalAgent.VisualStudio.Services;
using Newtonsoft.Json;

namespace Aegis.LocalAgent.VisualStudio.ToolWindows
{
    public partial class AegisToolWindowControl : UserControl
    {
        public AegisToolWindowControl()
        {
            InitializeComponent();
            AegisAgentRuntime.Current?.AttachControl(this);
        }

        internal string SelectedModel => string.IsNullOrWhiteSpace(ModelSelector.Text) ? "qwen3-coder:30b" : ModelSelector.Text.Trim();

        internal void SetStatus(string status)
        {
            OnUi(() =>
            {
                var value = string.IsNullOrWhiteSpace(status) ? "Ready" : status;
                StatusText.Text = "Status: " + value;
                StatusText.Foreground = StatusBrush(value);
            });
        }

        internal void SetModels(IEnumerable<string> models)
        {
            OnUi(() =>
            {
                var modelList = (models ?? Enumerable.Empty<string>()).ToList();
                var selected = SelectedModel;
                ModelSelector.Items.Clear();
                foreach (var model in modelList)
                {
                    ModelSelector.Items.Add(model);
                }
                ModelSelector.Text = string.IsNullOrWhiteSpace(selected) ? "qwen3-coder:30b" : selected;
                ModelStatusText.Text = modelList.Count == 0
                    ? "Model status: no models detected"
                    : $"Model status: {modelList.Count} local model(s) detected";
            });
        }

        internal void SetModelStatus(string text)
        {
            OnUi(() => ModelStatusText.Text = "Model status: " + (text ?? "not checked"));
        }

        internal void SetSettingsSummary(AegisSettingsSnapshot settings)
        {
            OnUi(() =>
            {
                if (settings == null)
                {
                    SettingsSummaryBox.Text = "Settings unavailable.";
                    return;
                }

                SettingsSummaryBox.Text = string.Join(Environment.NewLine, new[]
                {
                    $"Ollama URL: {settings.OllamaUrl}",
                    $"Aegis Core URL: {settings.AegisCoreUrl}",
                    $"Default Model: {settings.DefaultModel}",
                    $"Fallback Models: {string.Join(", ", settings.FallbackModels ?? Array.Empty<string>())}",
                    $"Max Context Size: {settings.MaxContextSize}",
                    $"Safety Mode: {settings.SafetyMode}",
                    $"Auto Scan On Solution Open: {settings.AutoScanOnSolutionOpen}",
                    $"Validate After Apply: {settings.ValidateAfterApply}",
                    $"Build Validation Preference: {settings.BuildValidationPreference}",
                    $"Backup Location: {settings.BackupLocation}",
                    "",
                    "Change these under Tools > Options > Aegis Local Agent > General."
                });
            });
        }

        internal void SetSolutionInfo(SolutionContext context)
        {
            OnUi(() =>
            {
                if (context == null || string.IsNullOrWhiteSpace(context.SolutionRoot))
                {
                    SolutionInfoBox.Text = "No solution is open.";
                    ProjectInfoBox.Text = "No project is active.";
                    return;
                }

                SolutionInfoBox.Text = string.Join(Environment.NewLine, new[]
                {
                    $"Solution: {context.SolutionName}",
                    $"Path: {context.SolutionPath}",
                    $"Startup Project: {context.StartupProject}",
                    $"Active Document: {context.ActiveDocumentPath}",
                    "",
                    "Validation:",
                    string.Join(Environment.NewLine, context.ValidationHints.Select(item => $"- {item}"))
                });

                var selectedProject = context.Projects.FirstOrDefault(project => project.Path.Equals(context.SelectedProjectPath, StringComparison.OrdinalIgnoreCase))
                    ?? context.Projects.FirstOrDefault(project => project.Name.Equals(context.SelectedProjectName, StringComparison.OrdinalIgnoreCase))
                    ?? context.Projects.FirstOrDefault(project => project.UniqueName.Equals(context.StartupProject, StringComparison.OrdinalIgnoreCase))
                    ?? context.Projects.FirstOrDefault();

                ProjectInfoBox.Text = string.Join(Environment.NewLine, new[]
                {
                    $"Selected Item: {context.SelectedExplorerName}",
                    $"Selected Path: {context.SelectedExplorerPath}",
                    $"Selected Project: {context.SelectedProjectName}",
                    "",
                    "Projects:",
                    string.Join(Environment.NewLine, context.Projects.Select(project => $"- {project.Name} ({project.DetectedType})")),
                    "",
                    selectedProject == null ? "No project metadata." : $"Active Metadata: {selectedProject.Name}",
                    selectedProject == null ? string.Empty : $"Type: {selectedProject.DetectedType}",
                    selectedProject == null ? string.Empty : $"Frameworks: {string.Join(", ", selectedProject.TargetFrameworks)}",
                    selectedProject == null ? string.Empty : $"Packages: {string.Join(", ", selectedProject.Packages.Take(20))}",
                    selectedProject == null ? string.Empty : $"Symbols: {string.Join(", ", selectedProject.Symbols.Take(20))}",
                    selectedProject == null ? string.Empty : $"Unity: {string.Join(", ", selectedProject.UnitySignals.Take(20))}"
                });
            });
        }

        internal void AppendChat(string speaker, string message)
        {
            OnUi(() =>
            {
                ChatHistoryBox.AppendText($"[{DateTime.Now:T}] {speaker}:{Environment.NewLine}{message}{Environment.NewLine}{Environment.NewLine}");
                ChatHistoryBox.ScrollToEnd();
            });
        }

        internal void SetValidationOutput(string text)
        {
            OnUi(() =>
            {
                ValidationBox.Text = text ?? string.Empty;
                ValidationBox.ScrollToEnd();
            });
        }

        internal void SetAgentSession(AgentSession session)
        {
            OnUi(() =>
            {
                if (session == null)
                {
                    CurrentModeText.Text = "Mode: Idle";
                    ApprovalStatusText.Text = "Approval: No pending proposal.";
                    RepairAttemptText.Text = "Repair Attempts: 0/3";
                    PlanBox.Text = string.Empty;
                    AffectedFilesBox.Text = string.Empty;
                    return;
                }

                CurrentModeText.Text = $"Mode: {session.ModeLabel}  Target: {session.ValidationTarget}  Project: {session.TargetProjectName}";
                ApprovalStatusText.Text = $"Approval: {session.ApprovalStatus}";
                RepairAttemptText.Text = $"Repair Attempts: {session.RepairLabel}";
                PlanBox.Text = session.CurrentPlan ?? string.Empty;
                AffectedFilesBox.Text = session.AffectedFiles.Count == 0
                    ? "No affected files identified yet."
                    : string.Join(Environment.NewLine, session.AffectedFiles.Select(file => "- " + file));
            });
        }

        internal void SetIntelligenceInfo(SolutionContext context, string roadmap, string architecture)
        {
            OnUi(() =>
            {
                if (context == null || string.IsNullOrWhiteSpace(context.SolutionRoot))
                {
                    ScanStatusBox.Text = "No solution is open.";
                    ArchitectureBox.Text = string.Empty;
                    RoadmapBox.Text = string.Empty;
                    SymbolsBox.Text = string.Empty;
                    DependencyMapBox.Text = string.Empty;
                    return;
                }

                ScanStatusBox.Text = string.Join(Environment.NewLine, new[]
                {
                    context.IntelligenceStatus.Summary,
                    $"Last Scan UTC: {context.IntelligenceStatus.LastScanUtc:o}",
                    $"Mode: {(context.IntelligenceStatus.WasIncremental ? "Incremental" : "Full")}",
                    $"Files Seen: {context.IntelligenceStatus.FilesSeen}",
                    $"Files Indexed: {context.IntelligenceStatus.FilesIndexed}",
                    $"Files Reused: {context.IntelligenceStatus.FilesReused}",
                    $"Symbols: {context.IntelligenceStatus.SymbolsIndexed}",
                    $"Dependencies: {context.IntelligenceStatus.DependenciesIndexed}"
                });

                ArchitectureBox.Text = string.IsNullOrWhiteSpace(architecture)
                    ? context.ArchitectureSummary ?? string.Empty
                    : architecture;
                RoadmapBox.Text = string.IsNullOrWhiteSpace(roadmap) ? "No roadmap generated yet." : roadmap;
                SymbolsBox.Text = context.SymbolIndex.Count == 0
                    ? "No symbols indexed yet."
                    : string.Join(Environment.NewLine, context.SymbolIndex
                        .Take(160)
                        .Select(symbol => $"- {symbol.Kind} {symbol.Namespace}.{symbol.Name} [{symbol.Project}] {symbol.File}:{symbol.Line}".Replace(" .", " ")));
                DependencyMapBox.Text = context.DependencyMap.Count == 0
                    ? "No dependencies indexed yet."
                    : string.Join(Environment.NewLine, context.DependencyMap
                        .Take(180)
                        .Select(dep => $"- {dep.Kind} [{dep.Project}] {dep.Source} -> {dep.Target} ({dep.Detail})"));
            });
        }

        internal void SetSelectedError(string text)
        {
            OnUi(() => SelectedErrorBox.Text = text ?? string.Empty);
        }

        internal void SetBuildStatus(string text)
        {
            OnUi(() => BuildStatusBox.Text = text ?? string.Empty);
        }

        internal void SetAgentRequest(string text)
        {
            OnUi(() =>
            {
                AgentRequestBox.Text = text ?? string.Empty;
                AgentRequestBox.Focus();
            });
        }

        internal void SetProposal(AgentProposal proposal, IReadOnlyList<string> safetyMessages, string diffPreview)
        {
            OnUi(() =>
            {
                ProposalSummaryText.Text = proposal == null
                    ? "No pending proposal."
                    : $"{proposal.Summary}  Risk: {proposal.Risk}  Files: {proposal.FileEdits.Count}";
                ProposalBox.Text = proposal == null
                    ? string.Empty
                    : JsonConvert.SerializeObject(new
                    {
                        proposal.Objective,
                        proposal.Summary,
                        proposal.Risk,
                        proposal.Rationale,
                        proposal.Notes,
                        Safety = safetyMessages,
                        Files = proposal.FileEdits.Select(edit => new { edit.Path, edit.Reason, ContentLength = edit.Content?.Length ?? 0 }),
                        proposal.Commands,
                        proposal.Tests
                    }, Formatting.Indented);
                DiffBox.Text = diffPreview ?? string.Empty;
            });
        }

        private void OnUi(Action action)
        {
            if (Dispatcher.CheckAccess())
            {
                action();
                return;
            }

#pragma warning disable VSTHRD001
            _ = Dispatcher.BeginInvoke(action);
#pragma warning restore VSTHRD001
        }

        private static Brush StatusBrush(string status)
        {
            var value = status ?? string.Empty;
            if (value.IndexOf("Ready", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                return new SolidColorBrush(Color.FromRgb(105, 224, 154));
            }

            if (value.IndexOf("No Solution", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                return new SolidColorBrush(Color.FromRgb(255, 184, 108));
            }

            if (value.IndexOf("Offline", StringComparison.OrdinalIgnoreCase) >= 0
                || value.IndexOf("Failed", StringComparison.OrdinalIgnoreCase) >= 0
                || value.IndexOf("Error", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                return new SolidColorBrush(Color.FromRgb(255, 90, 102));
            }

            if (value.IndexOf("Indexing", StringComparison.OrdinalIgnoreCase) >= 0
                || value.IndexOf("Running", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                return new SolidColorBrush(Color.FromRgb(41, 211, 255));
            }

            return new SolidColorBrush(Color.FromRgb(255, 184, 108));
        }

        private void SendChat_Click(object sender, System.Windows.RoutedEventArgs e)
        {
            var text = ChatInputBox.Text;
            ChatInputBox.Clear();
            _ = AegisAgentRuntime.Current?.SendChatAsync(text);
        }

        private void HealthCheck_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.RunHealthCheckAsync();
        private void ExplainFile_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.ExplainCurrentFileAsync();
        private void ReviewSelection_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.ReviewSelectedCodeAsync();
        private void RefactorSelection_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.RefactorSelectedCodeAsync();
        private void ReviewStartupProject_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.ReviewStartupProjectAsync();
        private void FixBuildErrors_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.FixBuildErrorsAsync();
        private void FixSelectedError_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.FixSelectedErrorAsync();
        private void ExplainBuildFailure_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.ExplainBuildFailureAsync();
        private void GenerateRoadmap_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.GenerateRoadmapAsync();
        private void ContinueRoadmap_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.ContinueFromRoadmapAsync();
        private void ContinueSolution_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.ContinueCurrentSolutionAsync();
        private void GenerateTests_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.GenerateTestsForSelectedExplorerFileAsync();
        private void RescanIntelligence_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.RescanSolutionIntelligenceAsync();
        private void ApplyApproved_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.ApplyPendingProposalAsync();
        private void RollbackLast_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.RollbackLastChangeAsync();
        private void BuildSolution_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.BuildSolutionValidationAsync();
        private void BuildStartupProject_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.BuildStartupProjectValidationAsync();
        private void BuildSelectedProject_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.BuildSelectedProjectValidationAsync();
        private void AllowMoreRepair_Click(object sender, System.Windows.RoutedEventArgs e) => _ = AegisAgentRuntime.Current?.AllowOneMoreRepairAttemptAsync();

        private void CleanSolution_Click(object sender, System.Windows.RoutedEventArgs e)
        {
            if (MessageBox.Show("Clean the current Visual Studio solution?", "Aegis Local Agent", MessageBoxButton.YesNo, MessageBoxImage.Warning) == MessageBoxResult.Yes)
            {
                _ = AegisAgentRuntime.Current?.CleanSolutionAfterConfirmationAsync();
            }
        }

        private void RebuildSolution_Click(object sender, System.Windows.RoutedEventArgs e)
        {
            if (MessageBox.Show("Rebuild the current Visual Studio solution?", "Aegis Local Agent", MessageBoxButton.YesNo, MessageBoxImage.Warning) == MessageBoxResult.Yes)
            {
                _ = AegisAgentRuntime.Current?.RebuildSolutionAfterConfirmationAsync();
            }
        }

        private void ProposeChanges_Click(object sender, System.Windows.RoutedEventArgs e)
        {
            var request = string.IsNullOrWhiteSpace(AgentRequestBox.Text)
                ? "Continue work on this solution with one safe, small change."
                : AgentRequestBox.Text;
            _ = AegisAgentRuntime.Current?.ProposeFeatureAsync(request);
        }
    }
}
