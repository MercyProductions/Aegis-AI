using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Aegis.LocalAgent.VisualStudio.Models;
using EnvDTE;
using EnvDTE80;
using Microsoft.VisualStudio.Shell;

namespace Aegis.LocalAgent.VisualStudio.Services
{
    internal sealed class BuildService
    {
        private readonly AsyncPackage package;

        public BuildService(AsyncPackage package)
        {
            this.package = package;
        }

        public async Task<BuildResult> BuildSolutionAsync()
        {
            await ThreadHelper.JoinableTaskFactory.SwitchToMainThreadAsync();
            var result = new BuildResult();
            var dte = await GetDteAsync();
            if (dte?.Solution == null || !dte.Solution.IsOpen)
            {
                result.Output = "No Visual Studio solution is open.";
                return result;
            }

            dte.Solution.SolutionBuild.Build(true);
            PopulateResultFromVisualStudio(result, dte);
            result.Output = BuildResultText("Build Solution", result);
            return result;
        }

        public async Task<BuildResult> BuildProjectAsync(ProjectContext project)
        {
            await ThreadHelper.JoinableTaskFactory.SwitchToMainThreadAsync();
            var result = new BuildResult();
            var dte = await GetDteAsync();
            if (dte?.Solution == null || !dte.Solution.IsOpen)
            {
                result.Output = "No Visual Studio solution is open.";
                return result;
            }

            if (project == null || string.IsNullOrWhiteSpace(project.UniqueName))
            {
                return await BuildSolutionAsync();
            }

            var configuration = dte.Solution.SolutionBuild.ActiveConfiguration?.Name ?? "Debug";
            dte.Solution.SolutionBuild.BuildProject(configuration, project.UniqueName, true);
            result.FailedProjectName = project.Name;
            PopulateResultFromVisualStudio(result, dte, project.Name);
            result.Output = BuildResultText($"Build Project: {project.Name}", result);
            return result;
        }

        public async Task<BuildResult> CleanSolutionAsync()
        {
            await ThreadHelper.JoinableTaskFactory.SwitchToMainThreadAsync();
            var result = new BuildResult();
            var dte = await GetDteAsync();
            if (dte?.Solution == null || !dte.Solution.IsOpen)
            {
                result.Output = "No Visual Studio solution is open.";
                return result;
            }

            dte.Solution.SolutionBuild.Clean(true);
            result.Success = dte.Solution.SolutionBuild.LastBuildInfo == 0;
            result.BuildOutput = ReadBuildOutput(dte);
            result.Output = "Clean Solution completed." + Environment.NewLine + SolutionScanner.Truncate(result.BuildOutput, 12000);
            return result;
        }

        public async Task<BuildResult> RebuildSolutionAsync()
        {
            await ThreadHelper.JoinableTaskFactory.SwitchToMainThreadAsync();
            var result = new BuildResult();
            var dte = await GetDteAsync();
            if (dte?.Solution == null || !dte.Solution.IsOpen)
            {
                result.Output = "No Visual Studio solution is open.";
                return result;
            }

            dte.Solution.SolutionBuild.Clean(true);
            dte.Solution.SolutionBuild.Build(true);
            PopulateResultFromVisualStudio(result, dte);
            result.Output = BuildResultText("Rebuild Solution", result);
            return result;
        }

        public async Task<BuildSnapshot> ReadBuildSnapshotAsync()
        {
            await ThreadHelper.JoinableTaskFactory.SwitchToMainThreadAsync();
            var snapshot = new BuildSnapshot();
            var dte = await GetDteAsync();
            if (dte == null)
            {
                snapshot.Summary = "Visual Studio automation service is unavailable.";
                return snapshot;
            }

            snapshot.Diagnostics.AddRange(ReadDiagnostics(dte).Take(200));
            snapshot.BuildOutput = ReadBuildOutput(dte);
            snapshot.Summary = SummarizeDiagnostics(snapshot.Diagnostics, snapshot.BuildOutput);
            return snapshot;
        }

        public async Task<BuildDiagnostic> GetSelectedErrorAsync()
        {
            await ThreadHelper.JoinableTaskFactory.SwitchToMainThreadAsync();
            var dte = await GetDteAsync();
            if (dte == null)
            {
                return null;
            }

            var selected = TryReadSelectedError(dte);
            if (selected != null)
            {
                return selected;
            }

            var activeFile = dte.ActiveDocument?.FullName ?? string.Empty;
            return ReadDiagnostics(dte)
                .FirstOrDefault(item => !string.IsNullOrWhiteSpace(activeFile) && item.FileName.Equals(activeFile, StringComparison.OrdinalIgnoreCase))
                ?? ReadDiagnostics(dte).FirstOrDefault();
        }

        public async Task<IReadOnlyList<BuildDiagnostic>> GetErrorListItemsAsync()
        {
            await ThreadHelper.JoinableTaskFactory.SwitchToMainThreadAsync();
            var dte = await GetDteAsync();
            if (dte == null)
            {
                return Array.Empty<BuildDiagnostic>();
            }

            return ReadDiagnostics(dte).Take(200).ToList();
        }

        public async Task<string> GetCurrentErrorsAsync()
        {
            var snapshot = await ReadBuildSnapshotAsync();
            return snapshot.Summary;
        }

        private async Task<DTE2> GetDteAsync()
        {
            var dteObject = await package.GetServiceAsync(typeof(DTE));
#pragma warning disable VSTHRD010
            return dteObject as DTE2;
#pragma warning restore VSTHRD010
        }

        private static void PopulateResultFromVisualStudio(BuildResult result, DTE2 dte, string projectName = null)
        {
            ThreadHelper.ThrowIfNotOnUIThread();
            var diagnostics = ReadDiagnostics(dte)
                .Where(item => string.IsNullOrWhiteSpace(projectName) || item.Project.Equals(projectName, StringComparison.OrdinalIgnoreCase))
                .Take(200)
                .ToList();

            result.Diagnostics.AddRange(diagnostics);
            result.Errors.AddRange(diagnostics.Where(item => item.Severity.Equals("Error", StringComparison.OrdinalIgnoreCase)).Select(item => item.ToString()));
            result.Warnings.AddRange(diagnostics.Where(item => item.Severity.Equals("Warning", StringComparison.OrdinalIgnoreCase)).Select(item => item.ToString()));
            result.BuildOutput = ReadBuildOutput(dte);
            result.Success = result.Errors.Count == 0 && dte.Solution.SolutionBuild.LastBuildInfo == 0;

            if (!result.Success && string.IsNullOrWhiteSpace(result.FailedProjectName))
            {
                result.FailedProjectName = diagnostics.Select(item => item.Project).FirstOrDefault(item => !string.IsNullOrWhiteSpace(item)) ?? string.Empty;
            }
        }

        private static string BuildResultText(string title, BuildResult result)
        {
            var lines = new List<string>
            {
                $"{title}: {(result.Success ? "passed" : "failed")}",
                $"Errors: {result.Errors.Count}",
                $"Warnings: {result.Warnings.Count}"
            };

            if (!string.IsNullOrWhiteSpace(result.FailedProjectName))
            {
                lines.Add($"Likely affected project: {result.FailedProjectName}");
            }

            if (result.Diagnostics.Count > 0)
            {
                lines.Add("");
                lines.Add("Diagnostics by file:");
                lines.AddRange(GroupDiagnosticsByFile(result.Diagnostics));
            }

            if (!string.IsNullOrWhiteSpace(result.BuildOutput))
            {
                lines.Add("");
                lines.Add("Build output:");
                lines.Add(SolutionScanner.Truncate(result.BuildOutput, 18000));
            }

            return string.Join(Environment.NewLine, lines);
        }

        private static string SummarizeDiagnostics(IReadOnlyList<BuildDiagnostic> diagnostics, string buildOutput)
        {
            var lines = new List<string>
            {
                $"Error List items: {diagnostics.Count}",
                $"Errors: {diagnostics.Count(item => item.Severity.Equals("Error", StringComparison.OrdinalIgnoreCase))}",
                $"Warnings: {diagnostics.Count(item => item.Severity.Equals("Warning", StringComparison.OrdinalIgnoreCase))}"
            };

            if (diagnostics.Count > 0)
            {
                lines.Add("");
                lines.Add("Diagnostics by file:");
                lines.AddRange(GroupDiagnosticsByFile(diagnostics));
            }

            if (!string.IsNullOrWhiteSpace(buildOutput))
            {
                lines.Add("");
                lines.Add("Recent Build output:");
                lines.Add(SolutionScanner.Truncate(buildOutput, 12000));
            }

            return string.Join(Environment.NewLine, lines);
        }

        private static IEnumerable<string> GroupDiagnosticsByFile(IEnumerable<BuildDiagnostic> diagnostics)
        {
            return diagnostics
                .GroupBy(item => string.IsNullOrWhiteSpace(item.FileName) ? "(no file)" : item.FileName)
                .OrderByDescending(group => group.Count(item => item.Severity.Equals("Error", StringComparison.OrdinalIgnoreCase)))
                .ThenBy(group => group.Key)
                .Take(30)
                .Select(group =>
                {
                    var errorCount = group.Count(item => item.Severity.Equals("Error", StringComparison.OrdinalIgnoreCase));
                    var warningCount = group.Count(item => item.Severity.Equals("Warning", StringComparison.OrdinalIgnoreCase));
                    var first = group.FirstOrDefault();
                    return $"- {group.Key}: {errorCount} error(s), {warningCount} warning(s). First: {first?.Description}";
                });
        }

        private static BuildDiagnostic TryReadSelectedError(DTE2 dte)
        {
            ThreadHelper.ThrowIfNotOnUIThread();
            try
            {
                dynamic selectedItems = dte.ToolWindows.ErrorList.SelectedItems;
                if (selectedItems != null && selectedItems.Count > 0)
                {
                    dynamic selected = selectedItems.Item(1);
                    return FromDynamicErrorItem(selected);
                }
            }
            catch
            {
                // DTE does not expose selected errors consistently across VS versions.
            }

            return null;
        }

        private static IEnumerable<BuildDiagnostic> ReadDiagnostics(DTE2 dte)
        {
            ThreadHelper.ThrowIfNotOnUIThread();
            ErrorItems items;
            try
            {
                items = dte.ToolWindows.ErrorList.ErrorItems;
            }
            catch
            {
                yield break;
            }

            if (items == null)
            {
                yield break;
            }

            for (var i = 1; i <= items.Count; i++)
            {
                ErrorItem item;
                try
                {
                    item = items.Item(i);
                }
                catch
                {
                    continue;
                }

                if (item == null)
                {
                    continue;
                }

                yield return FromErrorItem(item);
            }
        }

        private static BuildDiagnostic FromErrorItem(ErrorItem item)
        {
            ThreadHelper.ThrowIfNotOnUIThread();
            return new BuildDiagnostic
            {
                Severity = SeverityFromErrorItem(item),
                Project = ReadDynamicString(item, "Project"),
                FileName = item.FileName ?? string.Empty,
                Line = item.Line,
                Column = item.Column,
                Code = ReadDynamicString(item, "ErrorCode"),
                Description = item.Description ?? string.Empty
            };
        }

        private static BuildDiagnostic FromDynamicErrorItem(dynamic item)
        {
            try
            {
                return new BuildDiagnostic
                {
                    Severity = NormalizeSeverity(ReadDynamicString(item, "ErrorLevel")),
                    Project = ReadDynamicString(item, "Project"),
                    FileName = ReadDynamicString(item, "FileName"),
                    Line = ReadDynamicInt(item, "Line"),
                    Column = ReadDynamicInt(item, "Column"),
                    Code = ReadDynamicString(item, "ErrorCode"),
                    Description = ReadDynamicString(item, "Description")
                };
            }
            catch
            {
                return null;
            }
        }

        private static string SeverityFromErrorItem(ErrorItem item)
        {
            ThreadHelper.ThrowIfNotOnUIThread();
            try
            {
                return NormalizeSeverity(item.ErrorLevel.ToString());
            }
            catch
            {
                return "Error";
            }
        }

        private static string NormalizeSeverity(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
            {
                return "Error";
            }

            if (value.IndexOf("Warning", StringComparison.OrdinalIgnoreCase) >= 0
                || value.IndexOf("Medium", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                return "Warning";
            }

            if (value.IndexOf("Message", StringComparison.OrdinalIgnoreCase) >= 0
                || value.IndexOf("Low", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                return "Message";
            }

            return "Error";
        }

        private static string ReadBuildOutput(DTE2 dte)
        {
            ThreadHelper.ThrowIfNotOnUIThread();
            try
            {
                var panes = dte.ToolWindows.OutputWindow.OutputWindowPanes;
                for (var i = 1; i <= panes.Count; i++)
                {
                    var pane = panes.Item(i);
                    if (pane.Name.IndexOf("Build", StringComparison.OrdinalIgnoreCase) < 0)
                    {
                        continue;
                    }

                    var document = pane.TextDocument;
                    var start = document.StartPoint.CreateEditPoint();
                    return start.GetText(document.EndPoint) ?? string.Empty;
                }
            }
            catch
            {
                // Output panes may not be available until Visual Studio has built once.
            }

            return string.Empty;
        }

        private static string ReadDynamicString(dynamic value, string propertyName)
        {
            try
            {
                var property = value.GetType().GetProperty(propertyName);
                var propertyValue = property?.GetValue(value, null);
                return propertyValue?.ToString() ?? string.Empty;
            }
            catch
            {
                return string.Empty;
            }
        }

        private static int ReadDynamicInt(dynamic value, string propertyName)
        {
            try
            {
                var property = value.GetType().GetProperty(propertyName);
                var propertyValue = property?.GetValue(value, null);
                return propertyValue == null ? 0 : Convert.ToInt32(propertyValue);
            }
            catch
            {
                return 0;
            }
        }
    }
}
