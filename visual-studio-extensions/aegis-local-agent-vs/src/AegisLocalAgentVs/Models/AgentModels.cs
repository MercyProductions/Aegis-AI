using System;
using System.Collections.Generic;

namespace Aegis.LocalAgent.VisualStudio.Models
{
    internal enum AgentMode
    {
        Idle,
        FixSelectedError,
        FixCurrentProject,
        ContinueCurrentSolution,
        ImplementFeature,
        RefactorSelectedCode,
        ExplainBuildFailure,
        GenerateTests,
        RepairValidation
    }

    internal enum BuildValidationTarget
    {
        None,
        Solution,
        StartupProject,
        SelectedProject
    }

    internal sealed class AgentSession
    {
        public AgentMode Mode { get; set; } = AgentMode.Idle;
        public string Objective { get; set; } = string.Empty;
        public string CurrentPlan { get; set; } = string.Empty;
        public string ApprovalStatus { get; set; } = "No pending proposal.";
        public string TargetProjectName { get; set; } = string.Empty;
        public BuildValidationTarget ValidationTarget { get; set; } = BuildValidationTarget.Solution;
        public int RepairAttemptCount { get; set; }
        public int MaxRepairAttempts { get; set; } = 3;
        public List<string> AffectedFiles { get; } = new List<string>();
        public BuildResult LastBuildResult { get; set; }
        public string CoreWorkflowId { get; set; } = string.Empty;
        public string CoreTaskId { get; set; } = string.Empty;
        public string CoreProposalId { get; set; } = string.Empty;
        public string CoreJobId { get; set; } = string.Empty;
        public string CoreCheckpointId { get; set; } = string.Empty;

        public string ModeLabel => Mode.ToString();
        public string RepairLabel => $"{RepairAttemptCount}/{MaxRepairAttempts}";
    }

    internal sealed class CoreRuntimeState
    {
        public bool CoreConnected { get; set; }
        public bool FallbackActive { get; set; } = true;
        public string CoreStatus { get; set; } = "Not checked";
        public string LastCoreError { get; set; } = string.Empty;
        public string LastOperation { get; set; } = "Startup";
        public string ReleaseCompatibilityStatus { get; set; } = "Not checked";
        public string ReleaseSchemaVersion { get; set; } = string.Empty;
        public string ActiveWorkflowId { get; set; } = string.Empty;
        public string ActiveWorkflowStatus { get; set; } = string.Empty;
        public string PendingProposalId { get; set; } = string.Empty;
        public string LastCheckpointId { get; set; } = string.Empty;
        public string LatestValidationSummary { get; set; } = string.Empty;
        public string QualityGateStatus { get; set; } = "Not checked";
        public string QualityGateSummary { get; set; } = string.Empty;
        public double QualityConfidenceScore { get; set; } = -1;
        public double QualityValidationScore { get; set; } = -1;
        public double QualityRiskScore { get; set; } = -1;
        public List<string> QualityBlockers { get; } = new List<string>();
        public string SelectedModel { get; set; } = string.Empty;
        public string RouteProfile { get; set; } = string.Empty;
        public string ModelRouteExplanation { get; set; } = string.Empty;
        public string ProviderHealthSummary { get; set; } = string.Empty;
        public string RegisteredClientId { get; set; } = "aegis-visual-studio";
        public DateTime LastUpdatedUtc { get; set; } = DateTime.UtcNow;
        public List<string> RecentOperations { get; } = new List<string>();
    }

    internal sealed class CoreCallResult
    {
        public bool Success { get; set; }
        public bool CanFallback { get; set; } = true;
        public string Kind { get; set; } = string.Empty;
        public string Error { get; set; } = string.Empty;
        public Newtonsoft.Json.Linq.JObject Envelope { get; set; }
        public Newtonsoft.Json.Linq.JObject Data { get; set; }

        public static CoreCallResult FromError(string error, bool canFallback = true)
        {
            return new CoreCallResult
            {
                Success = false,
                CanFallback = canFallback,
                Error = error ?? string.Empty
            };
        }
    }

    internal sealed class SolutionContext
    {
        public string SolutionPath { get; set; } = string.Empty;
        public string SolutionRoot { get; set; } = string.Empty;
        public string SolutionName { get; set; } = string.Empty;
        public string ActiveDocumentPath { get; set; } = string.Empty;
        public string SelectedCode { get; set; } = string.Empty;
        public string StartupProject { get; set; } = string.Empty;
        public string SelectedExplorerPath { get; set; } = string.Empty;
        public string SelectedExplorerName { get; set; } = string.Empty;
        public string SelectedProjectName { get; set; } = string.Empty;
        public string SelectedProjectPath { get; set; } = string.Empty;
        public List<ProjectContext> Projects { get; } = new List<ProjectContext>();
        public List<string> ImportantFiles { get; } = new List<string>();
        public List<string> RecentFiles { get; } = new List<string>();
        public List<string> ValidationHints { get; } = new List<string>();
        public List<SymbolEntry> SymbolIndex { get; } = new List<SymbolEntry>();
        public List<DependencyEntry> DependencyMap { get; } = new List<DependencyEntry>();
        public IntelligenceStatus IntelligenceStatus { get; } = new IntelligenceStatus();
        public string ArchitectureSummary { get; set; } = string.Empty;
    }

    internal sealed class ProjectContext
    {
        public string Name { get; set; } = string.Empty;
        public string UniqueName { get; set; } = string.Empty;
        public string Path { get; set; } = string.Empty;
        public string Root { get; set; } = string.Empty;
        public string Kind { get; set; } = string.Empty;
        public string DetectedType { get; set; } = string.Empty;
        public List<string> Files { get; } = new List<string>();
        public List<string> TargetFrameworks { get; } = new List<string>();
        public List<string> Packages { get; } = new List<string>();
        public List<string> Namespaces { get; } = new List<string>();
        public List<string> Symbols { get; } = new List<string>();
        public List<string> XamlFiles { get; } = new List<string>();
        public List<string> HeaderFiles { get; } = new List<string>();
        public List<string> SourceFiles { get; } = new List<string>();
        public List<string> IncludePaths { get; } = new List<string>();
        public List<string> Configurations { get; } = new List<string>();
        public List<string> UnitySignals { get; } = new List<string>();
        public List<string> ProjectReferences { get; } = new List<string>();
        public List<string> AssemblyReferences { get; } = new List<string>();
        public List<string> ConfigFiles { get; } = new List<string>();
        public List<string> TestFiles { get; } = new List<string>();
        public List<string> DocumentationFiles { get; } = new List<string>();
    }

    internal sealed class SymbolEntry
    {
        public string Project { get; set; } = string.Empty;
        public string File { get; set; } = string.Empty;
        public string Kind { get; set; } = string.Empty;
        public string Name { get; set; } = string.Empty;
        public string Namespace { get; set; } = string.Empty;
        public int Line { get; set; }
        public string Signature { get; set; } = string.Empty;
    }

    internal sealed class DependencyEntry
    {
        public string Project { get; set; } = string.Empty;
        public string Source { get; set; } = string.Empty;
        public string Target { get; set; } = string.Empty;
        public string Kind { get; set; } = string.Empty;
        public string Detail { get; set; } = string.Empty;
    }

    internal sealed class IntelligenceStatus
    {
        public DateTime LastScanUtc { get; set; }
        public bool WasIncremental { get; set; }
        public int FilesSeen { get; set; }
        public int FilesIndexed { get; set; }
        public int FilesReused { get; set; }
        public int SymbolsIndexed { get; set; }
        public int DependenciesIndexed { get; set; }
        public string Summary { get; set; } = "Not scanned yet.";
    }

    internal sealed class OllamaModel
    {
        public string Name { get; set; } = string.Empty;
    }

    internal sealed class AgentProposal
    {
        public string Objective { get; set; } = string.Empty;
        public string Summary { get; set; } = string.Empty;
        public string Risk { get; set; } = "medium";
        public string Rationale { get; set; } = string.Empty;
        public List<string> PlanSteps { get; set; } = new List<string>();
        public List<string> AffectedFiles { get; set; } = new List<string>();
        public List<string> Notes { get; set; } = new List<string>();
        public List<FileEdit> FileEdits { get; set; } = new List<FileEdit>();
        public List<AgentCommand> Commands { get; set; } = new List<AgentCommand>();
        public List<string> Tests { get; set; } = new List<string>();
        public string CoreWorkflowId { get; set; } = string.Empty;
        public string CoreProposalId { get; set; } = string.Empty;
        public string CoreTaskId { get; set; } = string.Empty;
        public string CoreJobId { get; set; } = string.Empty;
        public string CoreProjectId { get; set; } = string.Empty;
        public string CoreCheckpointId { get; set; } = string.Empty;
    }

    internal sealed class FileEdit
    {
        public string Id { get; set; } = string.Empty;
        public string Path { get; set; } = string.Empty;
        public string Reason { get; set; } = string.Empty;
        public string Content { get; set; } = string.Empty;
    }

    internal sealed class AgentCommand
    {
        public string Command { get; set; } = string.Empty;
        public string Reason { get; set; } = string.Empty;
    }

    internal sealed class BuildResult
    {
        public bool Success { get; set; }
        public string Output { get; set; } = string.Empty;
        public string BuildOutput { get; set; } = string.Empty;
        public string FailedProjectName { get; set; } = string.Empty;
        public List<BuildDiagnostic> Diagnostics { get; } = new List<BuildDiagnostic>();
        public List<string> Errors { get; } = new List<string>();
        public List<string> Warnings { get; } = new List<string>();
    }

    internal sealed class BuildDiagnostic
    {
        public string Severity { get; set; } = string.Empty;
        public string Project { get; set; } = string.Empty;
        public string FileName { get; set; } = string.Empty;
        public int Line { get; set; }
        public int Column { get; set; }
        public string Code { get; set; } = string.Empty;
        public string Description { get; set; } = string.Empty;

        public override string ToString()
        {
            var location = string.IsNullOrWhiteSpace(FileName) ? "(no file)" : FileName;
            var line = Line > 0 ? $":{Line}" : string.Empty;
            var code = string.IsNullOrWhiteSpace(Code) ? string.Empty : $" {Code}";
            var project = string.IsNullOrWhiteSpace(Project) ? string.Empty : $" [{Project}]";
            return $"{Severity}{code}{project} {location}{line}: {Description}".Trim();
        }
    }

    internal sealed class BuildSnapshot
    {
        public List<BuildDiagnostic> Diagnostics { get; } = new List<BuildDiagnostic>();
        public string BuildOutput { get; set; } = string.Empty;
        public string Summary { get; set; } = string.Empty;
    }

    internal sealed class HealthCheckResult
    {
        public DateTime CheckedAt { get; set; } = DateTime.UtcNow;
        public List<string> Lines { get; } = new List<string>();
        public bool Success { get; set; }

        public override string ToString()
        {
            return string.Join(Environment.NewLine, Lines);
        }
    }
}
