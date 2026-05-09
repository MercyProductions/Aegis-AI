using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Aegis.LocalAgent.VisualStudio.Models;
using EnvDTE;
using EnvDTE80;
using Microsoft.VisualStudio.Shell;
using SolutionContextModel = Aegis.LocalAgent.VisualStudio.Models.SolutionContext;

namespace Aegis.LocalAgent.VisualStudio.Services
{
    internal sealed class SolutionScanner
    {
        private static readonly HashSet<string> BlockedDirectories = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            ".git", ".vs", ".aegis", "bin", "obj", "packages", "node_modules", "vendor", "vendors", "dist", "build", "Generated",
            "Library", "Temp", "Logs", "ipch", ".vsconfig"
        };

        private static readonly Regex SecretFilePattern = new Regex(@"(^\.env(\.|$)|secret|credential|token|private|\.pfx$|\.p12$|\.pem$|\.key$)", RegexOptions.IgnoreCase | RegexOptions.Compiled);
        private static readonly Regex PackageReferencePattern = new Regex(@"<PackageReference\s+[^>]*Include\s*=\s*[""']([^""']+)[""']", RegexOptions.IgnoreCase | RegexOptions.Compiled);
        private static readonly Regex TargetFrameworkPattern = new Regex(@"<TargetFrameworks?\s*>\s*([^<]+)\s*</TargetFrameworks?>", RegexOptions.IgnoreCase | RegexOptions.Compiled);
        private static readonly Regex NamespacePattern = new Regex(@"\bnamespace\s+([A-Za-z_][A-Za-z0-9_.]*)", RegexOptions.Compiled);
        private static readonly Regex SymbolPattern = new Regex(@"\b(class|interface|struct|enum)\s+([A-Za-z_][A-Za-z0-9_]*)", RegexOptions.Compiled);
        private static readonly Regex IncludePathPattern = new Regex(@"<AdditionalIncludeDirectories>\s*([^<]+)\s*</AdditionalIncludeDirectories>", RegexOptions.IgnoreCase | RegexOptions.Compiled);
        private static readonly Regex ConfigurationPattern = new Regex(@"<ProjectConfiguration\s+Include\s*=\s*[""']([^""']+)[""']", RegexOptions.IgnoreCase | RegexOptions.Compiled);
        private readonly AsyncPackage package;

        public SolutionScanner(AsyncPackage package)
        {
            this.package = package;
        }

        public async Task<SolutionContextModel> ScanAsync()
        {
            await ThreadHelper.JoinableTaskFactory.SwitchToMainThreadAsync();
            var context = new SolutionContextModel();
            var dteObject = await package.GetServiceAsync(typeof(DTE));
            if (!(dteObject is DTE2 dte) || dte.Solution == null || !dte.Solution.IsOpen)
            {
                return context;
            }

            context.SolutionPath = dte.Solution.FullName ?? string.Empty;
            context.SolutionRoot = string.IsNullOrWhiteSpace(context.SolutionPath)
                ? string.Empty
                : Path.GetDirectoryName(context.SolutionPath);
            context.SolutionName = string.IsNullOrWhiteSpace(context.SolutionPath)
                ? "Open Folder"
                : Path.GetFileNameWithoutExtension(context.SolutionPath);
            context.ActiveDocumentPath = dte.ActiveDocument?.FullName ?? string.Empty;
            context.SelectedCode = GetSelectedCode(dte);
            context.StartupProject = GetStartupProject(dte);
            PopulateSelectedExplorerContext(dte, context);

            foreach (Project project in dte.Solution.Projects)
            {
                AddProject(project, context.Projects);
            }

            var root = context.SolutionRoot;
            if (!string.IsNullOrWhiteSpace(root) && Directory.Exists(root))
            {
                foreach (var file in EnumerateSafeFiles(root, root).Take(1200))
                {
                    var relative = MakeRelative(root, file);
                    if (IsImportantFile(relative))
                    {
                        context.ImportantFiles.Add(relative);
                    }
                }

                context.RecentFiles.AddRange(EnumerateSafeFiles(root, root)
                    .Select(path => new FileInfo(path))
                    .Where(info => info.Exists)
                    .OrderByDescending(info => info.LastWriteTimeUtc)
                    .Take(40)
                    .Select(info => MakeRelative(root, info.FullName)));
            }

            context.ValidationHints.AddRange(GetValidationHints(context));
            return context;
        }

        public string BuildContextText(SolutionContextModel context, int maxChars = 60000)
        {
            var lines = new List<string>
            {
                "# Visual Studio Solution",
                $"Solution: {context.SolutionName}",
                $"Path: {context.SolutionPath}",
                $"Startup project: {context.StartupProject}",
                $"Selected Solution Explorer item: {context.SelectedExplorerName} {MakeRelative(context.SolutionRoot, context.SelectedExplorerPath)}",
                $"Selected project: {context.SelectedProjectName} {MakeRelative(context.SolutionRoot, context.SelectedProjectPath)}",
                $"Active document: {MakeRelative(context.SolutionRoot, context.ActiveDocumentPath)}",
                "",
                "## Projects"
            };

            foreach (var project in context.Projects)
            {
                lines.Add($"- {project.Name} ({project.DetectedType}) {MakeRelative(context.SolutionRoot, project.Path)}");
                if (project.TargetFrameworks.Count > 0) lines.Add($"  Frameworks: {string.Join(", ", project.TargetFrameworks.Take(6))}");
                if (project.Packages.Count > 0) lines.Add($"  Packages: {string.Join(", ", project.Packages.Take(12))}");
                if (project.Namespaces.Count > 0) lines.Add($"  Namespaces: {string.Join(", ", project.Namespaces.Take(8))}");
                if (project.Symbols.Count > 0) lines.Add($"  Symbols: {string.Join(", ", project.Symbols.Take(12))}");
                if (project.IncludePaths.Count > 0) lines.Add($"  Include paths: {string.Join(", ", project.IncludePaths.Take(8))}");
                if (project.UnitySignals.Count > 0) lines.Add($"  Unity: {string.Join(", ", project.UnitySignals.Take(8))}");
            }

            lines.Add("");
            lines.Add("## Important Files");
            lines.AddRange(context.ImportantFiles.Take(60).Select(file => $"- {file}"));
            lines.Add("");
            lines.Add("## Recent Files");
            lines.AddRange(context.RecentFiles.Take(40).Select(file => $"- {file}"));
            lines.Add("");
            lines.Add("## Validation Hints");
            lines.AddRange(context.ValidationHints.Select(command => $"- {command}"));

            if (!string.IsNullOrWhiteSpace(context.ActiveDocumentPath) && File.Exists(context.ActiveDocumentPath))
            {
                lines.Add("");
                lines.Add($"## Active Document: {MakeRelative(context.SolutionRoot, context.ActiveDocumentPath)}");
                lines.Add("```");
                lines.Add(Truncate(ReadSafeText(context.ActiveDocumentPath), 16000));
                lines.Add("```");
            }

            if (!string.IsNullOrWhiteSpace(context.SelectedCode))
            {
                lines.Add("");
                lines.Add("## Selected Code");
                lines.Add("```");
                lines.Add(Truncate(context.SelectedCode, 12000));
                lines.Add("```");
            }

            return Truncate(string.Join(Environment.NewLine, lines), maxChars);
        }

        private static string GetSelectedCode(DTE2 dte)
        {
            ThreadHelper.ThrowIfNotOnUIThread();
            if (dte.ActiveDocument?.Selection is TextSelection selection && !selection.IsEmpty)
            {
                return selection.Text ?? string.Empty;
            }

            return string.Empty;
        }

        private static string GetStartupProject(DTE2 dte)
        {
            ThreadHelper.ThrowIfNotOnUIThread();
            try
            {
                var startupProjects = dte.Solution.SolutionBuild.StartupProjects as Array;
                return startupProjects?.Cast<object>().Select(item => item?.ToString()).FirstOrDefault() ?? string.Empty;
            }
            catch
            {
                return string.Empty;
            }
        }

        private static void PopulateSelectedExplorerContext(DTE2 dte, SolutionContextModel context)
        {
            ThreadHelper.ThrowIfNotOnUIThread();
            try
            {
                if (dte.SelectedItems == null || dte.SelectedItems.Count == 0)
                {
                    return;
                }

                var selected = dte.SelectedItems.Item(1);
                if (selected == null)
                {
                    return;
                }

                context.SelectedExplorerName = selected.Name ?? string.Empty;
                if (selected.ProjectItem != null)
                {
                    context.SelectedExplorerPath = GetProjectItemPath(selected.ProjectItem);
                    var containing = selected.ProjectItem.ContainingProject;
                    if (containing != null)
                    {
                        context.SelectedProjectName = containing.Name ?? string.Empty;
                        context.SelectedProjectPath = GetProjectPath(containing);
                    }
                    return;
                }

                if (selected.Project != null)
                {
                    context.SelectedProjectName = selected.Project.Name ?? string.Empty;
                    context.SelectedProjectPath = GetProjectPath(selected.Project);
                    context.SelectedExplorerPath = context.SelectedProjectPath;
                }
            }
            catch
            {
                // Solution Explorer selection is best-effort; some virtual nodes do not expose files.
            }
        }

        private static void AddProject(Project project, IList<ProjectContext> projects)
        {
            ThreadHelper.ThrowIfNotOnUIThread();
            if (project == null)
            {
                return;
            }

            if (project.Kind == ProjectKinds.vsProjectKindSolutionFolder)
            {
                foreach (ProjectItem item in project.ProjectItems)
                {
                    if (item.SubProject != null)
                    {
                        AddProject(item.SubProject, projects);
                    }
                }
                return;
            }

            var path = GetProjectPath(project);
            var root = string.IsNullOrWhiteSpace(path) ? string.Empty : Path.GetDirectoryName(path);
            var context = new ProjectContext
            {
                Name = project.Name ?? string.Empty,
                UniqueName = GetProjectUniqueName(project),
                Kind = project.Kind ?? string.Empty,
                Path = path,
                Root = root,
                DetectedType = DetectProjectType(path, project.Name, project.Kind)
            };

            if (!string.IsNullOrWhiteSpace(root) && Directory.Exists(root))
            {
                context.Files.AddRange(EnumerateSafeFiles(root, root).Take(180).Select(file => MakeRelative(root, file)));
                EnrichProjectContext(context);
            }

            projects.Add(context);
        }

        private static string GetProjectItemPath(ProjectItem item)
        {
            ThreadHelper.ThrowIfNotOnUIThread();
            try
            {
                return item.FileCount > 0 ? item.FileNames[1] ?? string.Empty : string.Empty;
            }
            catch
            {
                return string.Empty;
            }
        }

        private static string GetProjectPath(Project project)
        {
            ThreadHelper.ThrowIfNotOnUIThread();
            try
            {
                return project.FullName ?? string.Empty;
            }
            catch
            {
                return string.Empty;
            }
        }

        private static string GetProjectUniqueName(Project project)
        {
            ThreadHelper.ThrowIfNotOnUIThread();
            try
            {
                return project.UniqueName ?? string.Empty;
            }
            catch
            {
                return string.Empty;
            }
        }

        private static string DetectProjectType(string projectPath, string name, string kind)
        {
            var extension = Path.GetExtension(projectPath ?? string.Empty).ToLowerInvariant();
            var root = string.IsNullOrWhiteSpace(projectPath) ? string.Empty : Path.GetDirectoryName(projectPath);
            if (IsUnityProjectRoot(root))
            {
                return extension == ".vcxproj" ? "Unity/C++" : "Unity/C#";
            }

            if (extension == ".csproj")
            {
                var text = ReadSafeText(projectPath);
                if (text.IndexOf("Microsoft.NET.Sdk.Web", StringComparison.OrdinalIgnoreCase) >= 0) return "ASP.NET";
                if (text.IndexOf("UseWPF", StringComparison.OrdinalIgnoreCase) >= 0) return "WPF";
                if (text.IndexOf("Unity", StringComparison.OrdinalIgnoreCase) >= 0 || (name ?? string.Empty).IndexOf("Unity", StringComparison.OrdinalIgnoreCase) >= 0) return "Unity/C#";
                return "C#";
            }
            if (extension == ".vcxproj") return "C++";
            if (extension == ".fsproj") return "F#";
            if (extension == ".vbproj") return "Visual Basic";
            if (extension == ".pyproj") return "Python";
            return string.IsNullOrWhiteSpace(extension) ? (kind ?? "Project") : extension.TrimStart('.').ToUpperInvariant();
        }

        private static void EnrichProjectContext(ProjectContext context)
        {
            var projectText = ReadSafeText(context.Path);
            foreach (Match match in TargetFrameworkPattern.Matches(projectText))
            {
                context.TargetFrameworks.AddRange(match.Groups[1].Value.Split(new[] { ';', ',' }, StringSplitOptions.RemoveEmptyEntries).Select(item => item.Trim()));
            }

            foreach (Match match in PackageReferencePattern.Matches(projectText))
            {
                context.Packages.Add(match.Groups[1].Value.Trim());
            }

            if (context.DetectedType.Contains("C++"))
            {
                foreach (Match match in IncludePathPattern.Matches(projectText))
                {
                    context.IncludePaths.AddRange(match.Groups[1].Value.Split(new[] { ';' }, StringSplitOptions.RemoveEmptyEntries).Select(item => item.Trim()).Where(item => !item.StartsWith("$", StringComparison.Ordinal)));
                }

                foreach (Match match in ConfigurationPattern.Matches(projectText))
                {
                    context.Configurations.Add(match.Groups[1].Value.Trim());
                }
            }

            foreach (var file in context.Files)
            {
                var extension = Path.GetExtension(file);
                if (extension.Equals(".xaml", StringComparison.OrdinalIgnoreCase))
                {
                    context.XamlFiles.Add(file);
                }
                else if (extension.Equals(".h", StringComparison.OrdinalIgnoreCase)
                    || extension.Equals(".hh", StringComparison.OrdinalIgnoreCase)
                    || extension.Equals(".hpp", StringComparison.OrdinalIgnoreCase)
                    || extension.Equals(".hxx", StringComparison.OrdinalIgnoreCase))
                {
                    context.HeaderFiles.Add(file);
                }
                else if (extension.Equals(".cpp", StringComparison.OrdinalIgnoreCase)
                    || extension.Equals(".cc", StringComparison.OrdinalIgnoreCase)
                    || extension.Equals(".cxx", StringComparison.OrdinalIgnoreCase)
                    || extension.Equals(".c", StringComparison.OrdinalIgnoreCase))
                {
                    context.SourceFiles.Add(file);
                }
            }

            foreach (var file in context.Files.Where(file => file.EndsWith(".cs", StringComparison.OrdinalIgnoreCase)).Take(80))
            {
                var fullPath = Path.Combine(context.Root, file);
                var text = ReadSafeText(fullPath);
                foreach (Match match in NamespacePattern.Matches(text))
                {
                    AddUnique(context.Namespaces, match.Groups[1].Value, 40);
                }

                foreach (Match match in SymbolPattern.Matches(text))
                {
                    AddUnique(context.Symbols, $"{match.Groups[1].Value} {match.Groups[2].Value}", 80);
                }

                if (text.IndexOf("MonoBehaviour", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    AddUnique(context.UnitySignals, $"MonoBehaviour: {file}", 40);
                }
            }

            if (IsUnityProjectRoot(context.Root))
            {
                AddUnique(context.UnitySignals, "Assets/", 40);
                AddUnique(context.UnitySignals, "Packages/", 40);
                AddUnique(context.UnitySignals, "ProjectSettings/", 40);
            }
        }

        private static IEnumerable<string> EnumerateSafeFiles(string root, string solutionRoot)
        {
            var pending = new Queue<string>();
            pending.Enqueue(root);
            while (pending.Count > 0)
            {
                var directory = pending.Dequeue();
                IEnumerable<string> children;
                try
                {
                    children = Directory.EnumerateFileSystemEntries(directory);
                }
                catch
                {
                    continue;
                }

                foreach (var child in children)
                {
                    var name = Path.GetFileName(child);
                    if (Directory.Exists(child))
                    {
                        if (!ShouldSkipDirectory(child, solutionRoot))
                        {
                            pending.Enqueue(child);
                        }
                    }
                    else if (!SecretFilePattern.IsMatch(name ?? string.Empty))
                    {
                        yield return child;
                    }
                }
            }
        }

        private static bool ShouldSkipDirectory(string path, string solutionRoot)
        {
            var name = Path.GetFileName(path);
            if (name.Equals("Packages", StringComparison.OrdinalIgnoreCase) && IsUnityProjectRoot(Path.GetDirectoryName(path)))
            {
                return false;
            }

            return BlockedDirectories.Contains(name);
        }

        private static bool IsUnityProjectRoot(string root)
        {
            if (string.IsNullOrWhiteSpace(root) || !Directory.Exists(root))
            {
                return false;
            }

            return Directory.Exists(Path.Combine(root, "Assets"))
                && Directory.Exists(Path.Combine(root, "ProjectSettings"));
        }

        private static void AddUnique(ICollection<string> items, string value, int limit)
        {
            if (string.IsNullOrWhiteSpace(value) || items.Count >= limit || items.Contains(value))
            {
                return;
            }

            items.Add(value);
        }

        private static IEnumerable<string> GetValidationHints(SolutionContextModel context)
        {
            if (!string.IsNullOrWhiteSpace(context.SolutionPath))
            {
                yield return "Build Solution";
            }

            foreach (var project in context.Projects)
            {
                if (project.DetectedType == "C#"
                    || project.DetectedType == "F#"
                    || project.DetectedType == "Visual Basic"
                    || project.DetectedType == "ASP.NET"
                    || project.DetectedType == "WPF"
                    || project.DetectedType == "Unity/C#")
                {
                    yield return $"Build {project.Name}";
                }
            }
        }

        private static bool IsImportantFile(string relativePath)
        {
            var name = Path.GetFileName(relativePath);
            return IsUnityMetadataFile(relativePath)
                || name.Equals("README.md", StringComparison.OrdinalIgnoreCase)
                || name.Equals("CHANGELOG.md", StringComparison.OrdinalIgnoreCase)
                || name.Equals("Directory.Build.props", StringComparison.OrdinalIgnoreCase)
                || name.Equals("Directory.Build.targets", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".sln", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".slnx", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".csproj", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".fsproj", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".vbproj", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".vcxproj", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".vcxproj.filters", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".props", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".targets", StringComparison.OrdinalIgnoreCase)
                || name.Equals("packages.config", StringComparison.OrdinalIgnoreCase)
                || name.Equals("appsettings.json", StringComparison.OrdinalIgnoreCase)
                || name.Equals("manifest.json", StringComparison.OrdinalIgnoreCase)
                || name.Equals("packages.lock.json", StringComparison.OrdinalIgnoreCase)
                || relativePath.IndexOf("ProjectSettings", StringComparison.OrdinalIgnoreCase) >= 0;
        }

        private static bool IsUnityMetadataFile(string relativePath)
        {
            var normalized = (relativePath ?? string.Empty).Replace('\\', '/').TrimStart('/');
            return normalized.Equals("Packages/manifest.json", StringComparison.OrdinalIgnoreCase)
                || normalized.Equals("Packages/packages-lock.json", StringComparison.OrdinalIgnoreCase)
                || normalized.Equals("ProjectSettings/ProjectVersion.txt", StringComparison.OrdinalIgnoreCase)
                || normalized.Equals("ProjectSettings/ProjectSettings.asset", StringComparison.OrdinalIgnoreCase)
                || normalized.Equals("ProjectSettings/EditorBuildSettings.asset", StringComparison.OrdinalIgnoreCase)
                || normalized.Equals("ProjectSettings/EditorSettings.asset", StringComparison.OrdinalIgnoreCase)
                || normalized.Equals("ProjectSettings/InputManager.asset", StringComparison.OrdinalIgnoreCase)
                || normalized.Equals("ProjectSettings/TagsManager.asset", StringComparison.OrdinalIgnoreCase)
                || normalized.EndsWith(".asmdef", StringComparison.OrdinalIgnoreCase)
                || normalized.EndsWith(".asmref", StringComparison.OrdinalIgnoreCase);
        }

        internal static string MakeRelative(string root, string file)
        {
            if (string.IsNullOrWhiteSpace(root) || string.IsNullOrWhiteSpace(file))
            {
                return file ?? string.Empty;
            }

            try
            {
                var rootUri = new Uri(AppendSlash(root));
                var fileUri = new Uri(file);
                return Uri.UnescapeDataString(rootUri.MakeRelativeUri(fileUri).ToString()).Replace('/', Path.DirectorySeparatorChar);
            }
            catch
            {
                return file;
            }
        }

        internal static string ReadSafeText(string path)
        {
            try
            {
                var info = new FileInfo(path);
                if (!info.Exists || info.Length > 512000)
                {
                    return string.Empty;
                }

                return File.ReadAllText(path);
            }
            catch
            {
                return string.Empty;
            }
        }

        internal static string Truncate(string text, int maxChars)
        {
            if (string.IsNullOrEmpty(text) || text.Length <= maxChars)
            {
                return text ?? string.Empty;
            }

            var half = maxChars / 2;
            return text.Substring(0, half) + Environment.NewLine + "[...truncated...]" + Environment.NewLine + text.Substring(text.Length - half);
        }

        private static string AppendSlash(string value)
        {
            return value.EndsWith(Path.DirectorySeparatorChar.ToString(), StringComparison.Ordinal) ? value : value + Path.DirectorySeparatorChar;
        }
    }
}
