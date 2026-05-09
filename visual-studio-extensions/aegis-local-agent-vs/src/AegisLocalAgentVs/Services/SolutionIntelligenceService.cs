using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Xml.Linq;
using Aegis.LocalAgent.VisualStudio.Models;

namespace Aegis.LocalAgent.VisualStudio.Services
{
    internal sealed class SolutionIntelligenceService
    {
        private static readonly HashSet<string> BlockedDirectories = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            ".git", ".vs", ".aegis", "bin", "obj", "packages", "node_modules", "vendor", "vendors", "dist", "build",
            "Generated", "Library", "Temp", "Logs", "ipch"
        };

        private static readonly HashSet<string> IndexedExtensions = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            ".cs", ".fs", ".fsi", ".fsx", ".vb", ".xaml",
            ".cpp", ".cc", ".cxx", ".c", ".h", ".hh", ".hpp", ".hxx", ".ixx", ".inl",
            ".csproj", ".fsproj", ".vbproj", ".vcxproj", ".props", ".targets", ".sln", ".slnx",
            ".config", ".json", ".md", ".txt"
        };

        private static readonly Regex SecretFilePattern = new Regex(@"(^\.env(\.|$)|^(id_rsa|id_dsa|id_ecdsa|id_ed25519)$|(^|[._\-\s])(secret|secrets|credential|credentials|password|passwd|token|tokens|private|private-key|api[_-]?key|auth)([._\-\s]|$)|\.(pfx|p12|pem|key|keystore|crt|cer)$)", RegexOptions.IgnoreCase | RegexOptions.Compiled);
        private static readonly Regex NamespacePattern = new Regex(@"\bnamespace\s+([A-Za-z_][A-Za-z0-9_.]*)", RegexOptions.Compiled);
        private static readonly Regex CSharpTypePattern = new Regex(@"\b(class|interface|struct|enum|record)\s+([A-Za-z_][A-Za-z0-9_]*)", RegexOptions.Compiled);
        private static readonly Regex CSharpMethodPattern = new Regex(@"^\s*(?:public|private|protected|internal|static|virtual|override|abstract|sealed|async|extern|partial|\s)+[\w<>\[\],\?\.]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", RegexOptions.Compiled);
        private static readonly Regex UsingPattern = new Regex(@"^\s*using\s+([A-Za-z_][A-Za-z0-9_.]*)\s*;", RegexOptions.Compiled);
        private static readonly Regex FSharpModulePattern = new Regex(@"^\s*module\s+([A-Za-z_][A-Za-z0-9_.]*)", RegexOptions.Compiled);
        private static readonly Regex FSharpOpenPattern = new Regex(@"^\s*open\s+([A-Za-z_][A-Za-z0-9_.]*)", RegexOptions.Compiled);
        private static readonly Regex FSharpTypePattern = new Regex(@"^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)", RegexOptions.Compiled);
        private static readonly Regex FSharpFunctionPattern = new Regex(@"^\s*let\s+(?:rec\s+)?([A-Za-z_][A-Za-z0-9_']*)", RegexOptions.Compiled);
        private static readonly Regex VisualBasicNamespacePattern = new Regex(@"^\s*Namespace\s+([A-Za-z_][A-Za-z0-9_.]*)", RegexOptions.IgnoreCase | RegexOptions.Compiled);
        private static readonly Regex VisualBasicImportsPattern = new Regex(@"^\s*Imports\s+([A-Za-z_][A-Za-z0-9_.]*)", RegexOptions.IgnoreCase | RegexOptions.Compiled);
        private static readonly Regex VisualBasicTypePattern = new Regex(@"^\s*(?:Public|Private|Friend|Protected|Partial|NotInheritable|MustInherit|\s)*(Class|Interface|Structure|Enum|Module)\s+([A-Za-z_][A-Za-z0-9_]*)", RegexOptions.IgnoreCase | RegexOptions.Compiled);
        private static readonly Regex VisualBasicMethodPattern = new Regex(@"^\s*(?:Public|Private|Friend|Protected|Shared|Overrides|Overridable|Async|\s)*(Sub|Function)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", RegexOptions.IgnoreCase | RegexOptions.Compiled);
        private static readonly Regex XamlClassPattern = new Regex(@"x:Class\s*=\s*[""']([^""']+)[""']", RegexOptions.Compiled);
        private static readonly Regex CppTypePattern = new Regex(@"\b(class|struct|enum)\s+([A-Za-z_][A-Za-z0-9_]*)", RegexOptions.Compiled);
        private static readonly Regex CppFunctionPattern = new Regex(@"^\s*(?:[\w:<>\*&~]+\s+)+([A-Za-z_][A-Za-z0-9_:~]*)\s*\([^;]*\)\s*(?:const\s*)?(?:\{|;)?", RegexOptions.Compiled);
        private static readonly Regex IncludePattern = new Regex(@"^\s*#\s*include\s+[<""]([^>""]+)[>""]", RegexOptions.Compiled);

        private readonly Dictionary<string, FileAnalysis> fileCache = new Dictionary<string, FileAnalysis>(StringComparer.OrdinalIgnoreCase);
        private string cachedRoot = string.Empty;

        public async Task UpdateAsync(SolutionContext context, bool force = false)
        {
            if (context == null || string.IsNullOrWhiteSpace(context.SolutionRoot) || !Directory.Exists(context.SolutionRoot))
            {
                return;
            }

            await Task.Run(() => UpdateCore(context, force));
        }

        public string BuildSmartContextText(SolutionContext context, string objective, int maxChars = 42000, BuildSnapshot snapshot = null)
        {
            if (context == null)
            {
                return string.Empty;
            }

            var targetProject = GetSelectedOrStartupProject(context);
            var activeRelative = SolutionScanner.MakeRelative(context.SolutionRoot, context.ActiveDocumentPath);
            var selectedRelative = SolutionScanner.MakeRelative(context.SolutionRoot, context.SelectedExplorerPath);
            var relevantFiles = SelectRelevantFiles(context, objective, snapshot).ToList();
            var relevantSymbols = SelectRelevantSymbols(context, objective, relevantFiles).ToList();
            var lines = new List<string>
            {
                "# Smart Visual Studio Context",
                $"Solution: {context.SolutionName}",
                $"Solution path: {context.SolutionPath}",
                $"Startup project: {context.StartupProject}",
                $"Active document: {activeRelative}",
                $"Selected item: {context.SelectedExplorerName} {selectedRelative}",
                $"Selected project: {context.SelectedProjectName}",
                $"Scan: {context.IntelligenceStatus.Summary}",
                string.Empty,
                "## Target Project",
                targetProject == null ? "No project selected." : ProjectSummary(targetProject, context),
                string.Empty,
                "## Project List"
            };

            lines.AddRange(context.Projects.Take(40).Select(project =>
                $"- {project.Name} ({project.DetectedType}) refs:{project.ProjectReferences.Count} packages:{project.Packages.Count} tests:{project.TestFiles.Count}"));

            lines.Add(string.Empty);
            lines.Add("## Relevant Symbols");
            lines.AddRange(relevantSymbols.Take(80).Select(symbol =>
                $"- {symbol.Kind} {symbol.Namespace}.{symbol.Name} in {symbol.File}:{symbol.Line}".Replace(" .", " ")));

            lines.Add(string.Empty);
            lines.Add("## Related Dependencies");
            lines.AddRange(context.DependencyMap
                .Where(dep => relevantFiles.Contains(dep.Source, StringComparer.OrdinalIgnoreCase)
                    || relevantFiles.Contains(dep.Target, StringComparer.OrdinalIgnoreCase)
                    || (!string.IsNullOrWhiteSpace(dep.Project) && dep.Project.Equals(targetProject?.Name, StringComparison.OrdinalIgnoreCase)))
                .Take(80)
                .Select(dep => $"- {dep.Kind}: {dep.Source} -> {dep.Target} ({dep.Detail})"));

            lines.Add(string.Empty);
            lines.Add("## Memory Files To Consider");
            lines.AddRange(new[]
            {
                "- .aegis/solution-summary.md",
                "- .aegis/architecture-map.md",
                "- .aegis/roadmap.md",
                "- .aegis/known-issues.md",
                "- .aegis/build-log.md"
            });

            if (snapshot != null && !string.IsNullOrWhiteSpace(snapshot.Summary))
            {
                lines.Add(string.Empty);
                lines.Add("## Build/Error Snapshot");
                lines.Add(SolutionScanner.Truncate(snapshot.Summary, 8000));
            }

            if (!string.IsNullOrWhiteSpace(context.SelectedCode))
            {
                lines.Add(string.Empty);
                lines.Add("## Selected Code");
                lines.Add("```");
                lines.Add(SolutionScanner.Truncate(context.SelectedCode, 12000));
                lines.Add("```");
            }

            lines.Add(string.Empty);
            lines.Add("## Relevant File Snippets");
            foreach (var relative in relevantFiles.Take(8))
            {
                var fullPath = Resolve(context, relative);
                if (!File.Exists(fullPath))
                {
                    continue;
                }

                lines.Add($"### {relative}");
                lines.Add("```");
                lines.Add(SolutionScanner.Truncate(SolutionScanner.ReadSafeText(fullPath), 9000));
                lines.Add("```");
            }

            return SolutionScanner.Truncate(string.Join(Environment.NewLine, lines), maxChars);
        }

        public string BuildRoadmapContextText(SolutionContext context, int maxChars = 52000)
        {
            if (context == null)
            {
                return string.Empty;
            }

            var lines = new List<string>
            {
                "# Roadmap Context",
                $"Solution: {context.SolutionName}",
                $"Path: {context.SolutionPath}",
                $"Startup project: {context.StartupProject}",
                $"Scan: {context.IntelligenceStatus.Summary}",
                string.Empty,
                "## Architecture Summary",
                context.ArchitectureSummary,
                string.Empty,
                "## Projects"
            };

            foreach (var project in context.Projects)
            {
                lines.Add($"- {project.Name} ({project.DetectedType})");
                lines.Add($"  Path: {SolutionScanner.MakeRelative(context.SolutionRoot, project.Path)}");
                lines.Add($"  Frameworks: {string.Join(", ", project.TargetFrameworks.Take(8))}");
                lines.Add($"  Packages: {string.Join(", ", project.Packages.Take(12))}");
                lines.Add($"  Project refs: {string.Join(", ", project.ProjectReferences.Take(12))}");
                lines.Add($"  Tests: {project.TestFiles.Count}, XAML: {project.XamlFiles.Count}, C++ headers: {project.HeaderFiles.Count}, sources: {project.SourceFiles.Count}");
                if (project.UnitySignals.Count > 0)
                {
                    lines.Add($"  Unity: {string.Join(", ", project.UnitySignals.Take(8))}");
                }
            }

            lines.Add(string.Empty);
            lines.Add("## Important Files");
            lines.AddRange(context.ImportantFiles.Take(80).Select(file => $"- {file}"));
            lines.Add(string.Empty);
            lines.Add("## Top Symbols");
            lines.AddRange(context.SymbolIndex.Take(120).Select(symbol => $"- {symbol.Kind} {symbol.Name} ({symbol.Project}) {symbol.File}:{symbol.Line}"));
            lines.Add(string.Empty);
            lines.Add("## Validation Hints");
            lines.AddRange(context.ValidationHints.Select(item => $"- {item}"));

            return SolutionScanner.Truncate(string.Join(Environment.NewLine, lines), maxChars);
        }

        private void UpdateCore(SolutionContext context, bool force)
        {
            if (!string.Equals(cachedRoot, context.SolutionRoot, StringComparison.OrdinalIgnoreCase))
            {
                fileCache.Clear();
                cachedRoot = context.SolutionRoot;
            }
            else if (force)
            {
                fileCache.Clear();
            }

            var allFiles = EnumerateSafeFiles(context.SolutionRoot).ToList();
            var currentFiles = new HashSet<string>(allFiles, StringComparer.OrdinalIgnoreCase);
            foreach (var stale in fileCache.Keys.Where(path => !currentFiles.Contains(path)).ToList())
            {
                fileCache.Remove(stale);
            }

            var indexed = 0;
            var reused = 0;
            var symbols = new List<SymbolEntry>();
            var dependencies = new List<DependencyEntry>();

            foreach (var project in context.Projects)
            {
                EnrichProjectFromProjectFile(context, project, dependencies);
            }

            foreach (var file in allFiles)
            {
                var extension = Path.GetExtension(file);
                if (!IndexedExtensions.Contains(extension))
                {
                    continue;
                }

                var project = FindOwningProject(context, file);
                var analysis = AnalyzeWithCache(context, project, file, force, ref indexed, ref reused);
                if (analysis == null)
                {
                    continue;
                }

                symbols.AddRange(analysis.Symbols);
                dependencies.AddRange(analysis.Dependencies);
                UpdateProjectFileBuckets(project, analysis);
            }

            context.SymbolIndex.Clear();
            context.SymbolIndex.AddRange(symbols
                .OrderBy(symbol => symbol.Project)
                .ThenBy(symbol => symbol.File)
                .ThenBy(symbol => symbol.Line)
                .Take(6000));

            AddHeaderSourcePairs(context, dependencies);
            AddXamlCodeBehindRelations(context, dependencies);
            AddTestRelations(context, dependencies);

            context.DependencyMap.Clear();
            context.DependencyMap.AddRange(dependencies
                .Where(dep => !string.IsNullOrWhiteSpace(dep.Source) || !string.IsNullOrWhiteSpace(dep.Target))
                .Distinct(new DependencyComparer())
                .Take(8000));

            context.ArchitectureSummary = BuildArchitectureSummary(context);
            context.IntelligenceStatus.LastScanUtc = DateTime.UtcNow;
            context.IntelligenceStatus.WasIncremental = !force && reused > 0;
            context.IntelligenceStatus.FilesSeen = allFiles.Count;
            context.IntelligenceStatus.FilesIndexed = indexed;
            context.IntelligenceStatus.FilesReused = reused;
            context.IntelligenceStatus.SymbolsIndexed = context.SymbolIndex.Count;
            context.IntelligenceStatus.DependenciesIndexed = context.DependencyMap.Count;
            context.IntelligenceStatus.Summary =
                $"{(context.IntelligenceStatus.WasIncremental ? "Incremental" : "Full")} scan, files seen {allFiles.Count}, indexed {indexed}, reused {reused}, symbols {context.SymbolIndex.Count}, dependencies {context.DependencyMap.Count}";
        }

        private static void EnrichProjectFromProjectFile(SolutionContext context, ProjectContext project, ICollection<DependencyEntry> dependencies)
        {
            if (project == null || string.IsNullOrWhiteSpace(project.Path) || !File.Exists(project.Path))
            {
                return;
            }

            var projectRelative = SolutionScanner.MakeRelative(context.SolutionRoot, project.Path);
            XDocument document;
            try
            {
                document = XDocument.Load(project.Path);
            }
            catch
            {
                return;
            }

            foreach (var item in document.Descendants().Where(element => element.Name.LocalName == "ProjectReference"))
            {
                var include = item.Attribute("Include")?.Value;
                if (string.IsNullOrWhiteSpace(include))
                {
                    continue;
                }

                var target = NormalizeProjectReference(context, project, include);
                AddUnique(project.ProjectReferences, target, 80);
                dependencies.Add(new DependencyEntry
                {
                    Project = project.Name,
                    Source = projectRelative,
                    Target = target,
                    Kind = "ProjectReference",
                    Detail = include
                });
            }

            foreach (var item in document.Descendants().Where(element => element.Name.LocalName == "Reference"))
            {
                var include = item.Attribute("Include")?.Value;
                AddUnique(project.AssemblyReferences, include, 80);
            }
        }

        private FileAnalysis AnalyzeWithCache(SolutionContext context, ProjectContext project, string file, bool force, ref int indexed, ref int reused)
        {
            try
            {
                var info = new FileInfo(file);
                if (!info.Exists || info.Length > 768000)
                {
                    return null;
                }

                if (!force && fileCache.TryGetValue(file, out var cached)
                    && cached.LastWriteTicks == info.LastWriteTimeUtc.Ticks
                    && cached.Length == info.Length)
                {
                    reused++;
                    return cached;
                }

                var analysis = AnalyzeFile(context, project, file, info);
                fileCache[file] = analysis;
                indexed++;
                return analysis;
            }
            catch
            {
                return null;
            }
        }

        private static FileAnalysis AnalyzeFile(SolutionContext context, ProjectContext project, string file, FileInfo info)
        {
            var relative = SolutionScanner.MakeRelative(context.SolutionRoot, file);
            var text = SolutionScanner.ReadSafeText(file);
            var extension = Path.GetExtension(file);
            var analysis = new FileAnalysis
            {
                File = relative,
                Project = project?.Name ?? string.Empty,
                LastWriteTicks = info.LastWriteTimeUtc.Ticks,
                Length = info.Length,
                IsTest = IsTestFile(relative, project),
                IsConfig = IsConfigFile(relative),
                IsDocumentation = IsDocumentationFile(relative)
            };

            switch (extension.ToLowerInvariant())
            {
                case ".cs":
                    AnalyzeCSharp(text, analysis);
                    break;
                case ".fs":
                case ".fsi":
                case ".fsx":
                    AnalyzeFSharp(text, analysis);
                    break;
                case ".vb":
                    AnalyzeVisualBasic(text, analysis);
                    break;
                case ".xaml":
                    AnalyzeXaml(text, analysis);
                    break;
                case ".cpp":
                case ".cc":
                case ".cxx":
                case ".c":
                case ".h":
                case ".hh":
                case ".hpp":
                case ".hxx":
                case ".ixx":
                case ".inl":
                    AnalyzeCpp(text, analysis);
                    break;
            }

            return analysis;
        }

        private static void AnalyzeCSharp(string text, FileAnalysis analysis)
        {
            var currentNamespace = NamespacePattern.Match(text).Groups.Cast<Group>().Skip(1).FirstOrDefault()?.Value ?? string.Empty;
            var lines = SplitLines(text);
            for (var i = 0; i < lines.Length; i++)
            {
                var line = lines[i];
                var usingMatch = UsingPattern.Match(line);
                if (usingMatch.Success)
                {
                    analysis.Dependencies.Add(new DependencyEntry
                    {
                        Project = analysis.Project,
                        Source = analysis.File,
                        Target = usingMatch.Groups[1].Value,
                        Kind = "Using",
                        Detail = "C# namespace import"
                    });
                }

                foreach (Match match in CSharpTypePattern.Matches(line))
                {
                    var kind = match.Groups[1].Value;
                    var name = match.Groups[2].Value;
                    analysis.Symbols.Add(NewSymbol(analysis, kind, name, currentNamespace, i + 1, line));
                    if (line.IndexOf("MonoBehaviour", StringComparison.OrdinalIgnoreCase) >= 0 || text.IndexOf($": MonoBehaviour", StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        analysis.Symbols.Add(NewSymbol(analysis, "MonoBehaviour", name, currentNamespace, i + 1, line));
                    }
                }

                var method = CSharpMethodPattern.Match(line);
                if (method.Success && !IsControlWord(method.Groups[1].Value))
                {
                    analysis.Symbols.Add(NewSymbol(analysis, "method", method.Groups[1].Value, currentNamespace, i + 1, line));
                }
            }
        }

        private static void AnalyzeFSharp(string text, FileAnalysis analysis)
        {
            var currentModule = string.Empty;
            var lines = SplitLines(text);
            for (var i = 0; i < lines.Length; i++)
            {
                var line = lines[i];
                var module = FSharpModulePattern.Match(line);
                if (module.Success)
                {
                    currentModule = module.Groups[1].Value;
                    analysis.Symbols.Add(NewSymbol(analysis, "module", module.Groups[1].Value.Split('.').Last(), NamespacePart(module.Groups[1].Value), i + 1, line));
                    continue;
                }

                var open = FSharpOpenPattern.Match(line);
                if (open.Success)
                {
                    analysis.Dependencies.Add(new DependencyEntry
                    {
                        Project = analysis.Project,
                        Source = analysis.File,
                        Target = open.Groups[1].Value,
                        Kind = "Open",
                        Detail = "F# namespace import"
                    });
                }

                var type = FSharpTypePattern.Match(line);
                if (type.Success)
                {
                    analysis.Symbols.Add(NewSymbol(analysis, "type", type.Groups[1].Value, currentModule, i + 1, line));
                }

                var function = FSharpFunctionPattern.Match(line);
                if (function.Success && !IsControlWord(function.Groups[1].Value))
                {
                    analysis.Symbols.Add(NewSymbol(analysis, "function", function.Groups[1].Value, currentModule, i + 1, line));
                }
            }
        }

        private static void AnalyzeVisualBasic(string text, FileAnalysis analysis)
        {
            var currentNamespace = string.Empty;
            var lines = SplitLines(text);
            for (var i = 0; i < lines.Length; i++)
            {
                var line = lines[i];
                var namespaceMatch = VisualBasicNamespacePattern.Match(line);
                if (namespaceMatch.Success)
                {
                    currentNamespace = namespaceMatch.Groups[1].Value;
                }

                var imports = VisualBasicImportsPattern.Match(line);
                if (imports.Success)
                {
                    analysis.Dependencies.Add(new DependencyEntry
                    {
                        Project = analysis.Project,
                        Source = analysis.File,
                        Target = imports.Groups[1].Value,
                        Kind = "Imports",
                        Detail = "Visual Basic namespace import"
                    });
                }

                var type = VisualBasicTypePattern.Match(line);
                if (type.Success)
                {
                    analysis.Symbols.Add(NewSymbol(analysis, type.Groups[1].Value.ToLowerInvariant(), type.Groups[2].Value, currentNamespace, i + 1, line));
                }

                var method = VisualBasicMethodPattern.Match(line);
                if (method.Success && !IsControlWord(method.Groups[2].Value))
                {
                    analysis.Symbols.Add(NewSymbol(analysis, "method", method.Groups[2].Value, currentNamespace, i + 1, line));
                }
            }
        }

        private static void AnalyzeXaml(string text, FileAnalysis analysis)
        {
            var match = XamlClassPattern.Match(text);
            if (match.Success)
            {
                analysis.Symbols.Add(NewSymbol(analysis, "XAML view", match.Groups[1].Value.Split('.').Last(), NamespacePart(match.Groups[1].Value), 1, match.Value));
            }
        }

        private static void AnalyzeCpp(string text, FileAnalysis analysis)
        {
            var lines = SplitLines(text);
            for (var i = 0; i < lines.Length; i++)
            {
                var line = lines[i];
                var include = IncludePattern.Match(line);
                if (include.Success)
                {
                    analysis.Dependencies.Add(new DependencyEntry
                    {
                        Project = analysis.Project,
                        Source = analysis.File,
                        Target = include.Groups[1].Value,
                        Kind = "Include",
                        Detail = "#include"
                    });
                }

                foreach (Match match in CppTypePattern.Matches(line))
                {
                    analysis.Symbols.Add(NewSymbol(analysis, match.Groups[1].Value, match.Groups[2].Value, string.Empty, i + 1, line));
                }

                var function = CppFunctionPattern.Match(line);
                if (function.Success && !IsControlWord(function.Groups[1].Value))
                {
                    analysis.Symbols.Add(NewSymbol(analysis, "function", function.Groups[1].Value, string.Empty, i + 1, line));
                }
            }
        }

        private static SymbolEntry NewSymbol(FileAnalysis analysis, string kind, string name, string ns, int line, string signature)
        {
            return new SymbolEntry
            {
                Project = analysis.Project,
                File = analysis.File,
                Kind = kind,
                Name = name,
                Namespace = ns,
                Line = line,
                Signature = SolutionScanner.Truncate((signature ?? string.Empty).Trim(), 220)
            };
        }

        private static void UpdateProjectFileBuckets(ProjectContext project, FileAnalysis analysis)
        {
            if (project == null || analysis == null)
            {
                return;
            }

            if (analysis.IsTest)
            {
                AddUnique(project.TestFiles, analysis.File, 160);
            }

            if (analysis.IsConfig)
            {
                AddUnique(project.ConfigFiles, analysis.File, 120);
            }

            if (analysis.IsDocumentation)
            {
                AddUnique(project.DocumentationFiles, analysis.File, 80);
            }
        }

        private static void AddHeaderSourcePairs(SolutionContext context, ICollection<DependencyEntry> dependencies)
        {
            foreach (var project in context.Projects)
            {
                var byStem = project.HeaderFiles.Concat(project.SourceFiles)
                    .GroupBy(file => Path.GetFileNameWithoutExtension(file), StringComparer.OrdinalIgnoreCase)
                    .Where(group => group.Count() > 1);
                foreach (var group in byStem)
                {
                    var files = group.ToList();
                    foreach (var source in files)
                    {
                        foreach (var target in files.Where(file => !file.Equals(source, StringComparison.OrdinalIgnoreCase)))
                        {
                            dependencies.Add(new DependencyEntry
                            {
                                Project = project.Name,
                                Source = ToSolutionRelative(context, project, source),
                                Target = ToSolutionRelative(context, project, target),
                                Kind = "HeaderSourcePair",
                                Detail = "C++ header/source basename match"
                            });
                        }
                    }
                }
            }
        }

        private static void AddXamlCodeBehindRelations(SolutionContext context, ICollection<DependencyEntry> dependencies)
        {
            foreach (var project in context.Projects)
            {
                foreach (var xaml in project.XamlFiles)
                {
                    var codeBehind = new[] { xaml + ".cs", xaml + ".vb" }
                        .FirstOrDefault(candidate => File.Exists(Path.Combine(project.Root, candidate)));
                    if (codeBehind == null)
                    {
                        continue;
                    }

                    dependencies.Add(new DependencyEntry
                    {
                        Project = project.Name,
                        Source = ToSolutionRelative(context, project, xaml),
                        Target = ToSolutionRelative(context, project, codeBehind),
                        Kind = "XamlCodeBehind",
                        Detail = "WPF XAML code-behind"
                    });
                }
            }
        }

        private static void AddTestRelations(SolutionContext context, ICollection<DependencyEntry> dependencies)
        {
            var sources = context.SymbolIndex
                .Where(symbol => symbol.File.EndsWith(".cs", StringComparison.OrdinalIgnoreCase)
                    || symbol.File.EndsWith(".fs", StringComparison.OrdinalIgnoreCase)
                    || symbol.File.EndsWith(".fsi", StringComparison.OrdinalIgnoreCase)
                    || symbol.File.EndsWith(".fsx", StringComparison.OrdinalIgnoreCase)
                    || symbol.File.EndsWith(".vb", StringComparison.OrdinalIgnoreCase)
                    || symbol.File.EndsWith(".cpp", StringComparison.OrdinalIgnoreCase)
                    || symbol.File.EndsWith(".cc", StringComparison.OrdinalIgnoreCase)
                    || symbol.File.EndsWith(".cxx", StringComparison.OrdinalIgnoreCase)
                    || symbol.File.EndsWith(".h", StringComparison.OrdinalIgnoreCase)
                    || symbol.File.EndsWith(".hh", StringComparison.OrdinalIgnoreCase)
                    || symbol.File.EndsWith(".hpp", StringComparison.OrdinalIgnoreCase)
                    || symbol.File.EndsWith(".hxx", StringComparison.OrdinalIgnoreCase)
                    || symbol.File.EndsWith(".ixx", StringComparison.OrdinalIgnoreCase))
                .Select(symbol => symbol.File)
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();

            foreach (var project in context.Projects)
            {
                foreach (var test in project.TestFiles)
                {
                    var stem = Path.GetFileNameWithoutExtension(test)
                        .Replace("Tests", string.Empty)
                        .Replace("Test", string.Empty)
                        .Replace("Spec", string.Empty);
                    var match = sources.FirstOrDefault(file => Path.GetFileNameWithoutExtension(file).Equals(stem, StringComparison.OrdinalIgnoreCase));
                    if (match == null)
                    {
                        continue;
                    }

                    dependencies.Add(new DependencyEntry
                    {
                        Project = project.Name,
                        Source = ProjectFileReferenceToSolutionRelative(context, project, test),
                        Target = match,
                        Kind = "TestTarget",
                        Detail = "Test/source name match"
                    });
                }
            }
        }

        private string BuildArchitectureSummary(SolutionContext context)
        {
            var lines = new List<string>
            {
                $"Solution: {context.SolutionName}",
                $"Projects: {context.Projects.Count}",
                $"Startup project: {context.StartupProject}",
                string.Empty,
                "Project roles:"
            };
            lines.AddRange(context.Projects.Select(project => $"- {project.Name}: {DescribeProjectRole(project)}"));
            lines.Add(string.Empty);
            lines.Add("Entry points:");
            lines.AddRange(context.SymbolIndex
                .Where(symbol => symbol.Name.Equals("Program", StringComparison.OrdinalIgnoreCase)
                    || symbol.Name.Equals("Main", StringComparison.OrdinalIgnoreCase)
                    || symbol.Kind.Equals("XAML view", StringComparison.OrdinalIgnoreCase)
                    || symbol.Kind.Equals("MonoBehaviour", StringComparison.OrdinalIgnoreCase))
                .Take(40)
                .Select(symbol => $"- {symbol.Project}: {symbol.Kind} {symbol.Name} ({symbol.File}:{symbol.Line})"));
            lines.Add(string.Empty);
            lines.Add("Build flow:");
            lines.AddRange(context.DependencyMap
                .Where(dep => dep.Kind.Equals("ProjectReference", StringComparison.OrdinalIgnoreCase))
                .Take(80)
                .Select(dep => $"- {dep.Source} references {dep.Target}"));
            lines.Add(string.Empty);
            lines.Add("Likely risk areas:");
            lines.AddRange(FindRiskAreas(context).DefaultIfEmpty("- No obvious high-risk areas detected from static scan."));
            return string.Join(Environment.NewLine, lines);
        }

        private static IEnumerable<string> SelectRelevantFiles(SolutionContext context, string objective, BuildSnapshot snapshot)
        {
            var files = new List<string>();
            AddFileIfSafe(files, context, context.ActiveDocumentPath);
            AddFileIfSafe(files, context, context.SelectedExplorerPath);

            var project = GetSelectedOrStartupProject(context);
            if (project != null)
            {
                AddFileIfSafe(files, context, project.Path);
                foreach (var file in project.ConfigFiles.Take(6).Concat(project.DocumentationFiles.Take(4)).Concat(project.TestFiles.Take(6)))
                {
                    AddRelative(files, context, ProjectFileReferenceToSolutionRelative(context, project, file));
                }
            }

            if (snapshot != null)
            {
                foreach (var diagnosticFile in snapshot.Diagnostics.Select(item => item.FileName).Where(file => !string.IsNullOrWhiteSpace(file)).Take(10))
                {
                    AddFileIfSafe(files, context, diagnosticFile);
                }
            }

            var tokens = ExtractTokens(objective + " " + context.SelectedCode + " " + Path.GetFileName(context.ActiveDocumentPath ?? string.Empty));
            foreach (var symbol in context.SymbolIndex.Where(symbol => tokens.Any(token =>
                         symbol.Name.IndexOf(token, StringComparison.OrdinalIgnoreCase) >= 0
                         || symbol.File.IndexOf(token, StringComparison.OrdinalIgnoreCase) >= 0)).Take(10))
            {
                AddRelative(files, context, symbol.File);
            }

            foreach (var dependency in context.DependencyMap.Where(dep => files.Contains(dep.Source, StringComparer.OrdinalIgnoreCase)
                         || files.Contains(dep.Target, StringComparer.OrdinalIgnoreCase)).Take(16))
            {
                AddRelative(files, context, dependency.Source);
                AddRelative(files, context, dependency.Target);
            }

            return files.Distinct(StringComparer.OrdinalIgnoreCase).Take(16);
        }

        private static IEnumerable<SymbolEntry> SelectRelevantSymbols(SolutionContext context, string objective, IEnumerable<string> files)
        {
            var fileSet = new HashSet<string>(files ?? Enumerable.Empty<string>(), StringComparer.OrdinalIgnoreCase);
            var tokens = ExtractTokens(objective + " " + context.SelectedCode + " " + Path.GetFileName(context.ActiveDocumentPath ?? string.Empty));
            return context.SymbolIndex
                .Where(symbol => fileSet.Contains(symbol.File)
                    || tokens.Any(token => symbol.Name.IndexOf(token, StringComparison.OrdinalIgnoreCase) >= 0
                        || symbol.Signature.IndexOf(token, StringComparison.OrdinalIgnoreCase) >= 0
                        || symbol.File.IndexOf(token, StringComparison.OrdinalIgnoreCase) >= 0))
                .Take(120);
        }

        private static string ProjectSummary(ProjectContext project, SolutionContext context)
        {
            return string.Join(Environment.NewLine, new[]
            {
                $"Name: {project.Name}",
                $"Type: {project.DetectedType}",
                $"Path: {SolutionScanner.MakeRelative(context.SolutionRoot, project.Path)}",
                $"Frameworks: {string.Join(", ", project.TargetFrameworks.Take(8))}",
                $"Packages: {string.Join(", ", project.Packages.Take(16))}",
                $"Project refs: {string.Join(", ", project.ProjectReferences.Take(16))}",
                $"Tests: {string.Join(", ", project.TestFiles.Take(12))}",
                $"Configs: {string.Join(", ", project.ConfigFiles.Take(12))}",
                $"Unity: {string.Join(", ", project.UnitySignals.Take(12))}"
            });
        }

        private static IEnumerable<string> FindRiskAreas(SolutionContext context)
        {
            foreach (var project in context.Projects.Where(project => project.DetectedType.Contains("C++") && project.Configurations.Count > 1))
            {
                yield return $"- {project.Name}: multiple C++ configurations may need platform-specific validation.";
            }

            foreach (var project in context.Projects.Where(project => project.DetectedType.Contains("Unity")))
            {
                yield return $"- {project.Name}: Unity project; avoid Library/Temp and validate scripts in Unity when possible.";
            }

            foreach (var project in context.Projects.Where(project => project.TestFiles.Count == 0 && project.Name.IndexOf("test", StringComparison.OrdinalIgnoreCase) < 0))
            {
                yield return $"- {project.Name}: no obvious tests found in static scan.";
            }
        }

        private static string DescribeProjectRole(ProjectContext project)
        {
            if (project.Name.IndexOf("test", StringComparison.OrdinalIgnoreCase) >= 0 || project.TestFiles.Count > 0)
            {
                return $"test project ({project.DetectedType})";
            }

            if (project.DetectedType.Equals("ASP.NET", StringComparison.OrdinalIgnoreCase))
            {
                return "web/API entry project";
            }

            if (project.DetectedType.Equals("WPF", StringComparison.OrdinalIgnoreCase))
            {
                return "desktop UI project";
            }

            if (project.DetectedType.Contains("Unity"))
            {
                return "Unity gameplay/editor project";
            }

            if (project.ProjectReferences.Count > 0)
            {
                return $"application/library project with {project.ProjectReferences.Count} project reference(s)";
            }

            return project.DetectedType;
        }

        private static IEnumerable<string> EnumerateSafeFiles(string root)
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
                        if (!ShouldSkipDirectory(child))
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

        private static bool ShouldSkipDirectory(string path)
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
            return !string.IsNullOrWhiteSpace(root)
                && Directory.Exists(Path.Combine(root, "Assets"))
                && Directory.Exists(Path.Combine(root, "ProjectSettings"));
        }

        private static ProjectContext FindOwningProject(SolutionContext context, string file)
        {
            return context.Projects
                .Where(project => !string.IsNullOrWhiteSpace(project.Root) && IsInside(project.Root, file))
                .OrderByDescending(project => project.Root.Length)
                .FirstOrDefault();
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

        private static string NormalizeProjectReference(SolutionContext context, ProjectContext project, string include)
        {
            try
            {
                var full = Path.GetFullPath(Path.Combine(project.Root, include));
                return SolutionScanner.MakeRelative(context.SolutionRoot, full);
            }
            catch
            {
                return include;
            }
        }

        private static string ToSolutionRelative(SolutionContext context, ProjectContext project, string projectRelative)
        {
            if (string.IsNullOrWhiteSpace(projectRelative))
            {
                return string.Empty;
            }

            if (Path.IsPathRooted(projectRelative))
            {
                return SolutionScanner.MakeRelative(context.SolutionRoot, projectRelative);
            }

            return SolutionScanner.MakeRelative(context.SolutionRoot, Path.Combine(project.Root, projectRelative));
        }

        private static string ProjectFileReferenceToSolutionRelative(SolutionContext context, ProjectContext project, string value)
        {
            if (string.IsNullOrWhiteSpace(value))
            {
                return string.Empty;
            }

            var solutionRelativePath = Resolve(context, value);
            if (File.Exists(solutionRelativePath))
            {
                return value;
            }

            return ToSolutionRelative(context, project, value);
        }

        private static void AddFileIfSafe(ICollection<string> files, SolutionContext context, string file)
        {
            if (string.IsNullOrWhiteSpace(file) || !File.Exists(file) || !IsInside(context.SolutionRoot, file))
            {
                return;
            }

            AddRelative(files, context, SolutionScanner.MakeRelative(context.SolutionRoot, file));
        }

        private static void AddRelative(ICollection<string> files, SolutionContext context, string relative)
        {
            if (string.IsNullOrWhiteSpace(relative) || relative.Contains(".."))
            {
                return;
            }

            var full = Resolve(context, relative);
            if (File.Exists(full) && IsInside(context.SolutionRoot, full) && !files.Contains(relative, StringComparer.OrdinalIgnoreCase))
            {
                files.Add(relative);
            }
        }

        private static string Resolve(SolutionContext context, string relative)
        {
            try
            {
                return Path.GetFullPath(Path.Combine(context.SolutionRoot, relative.Replace('/', Path.DirectorySeparatorChar)));
            }
            catch
            {
                return string.Empty;
            }
        }

        private static bool IsInside(string root, string path)
        {
            if (string.IsNullOrWhiteSpace(root) || string.IsNullOrWhiteSpace(path))
            {
                return false;
            }

            var fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            var fullPath = Path.GetFullPath(path);
            return fullPath.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsTestFile(string relative, ProjectContext project)
        {
            return relative.IndexOf("test", StringComparison.OrdinalIgnoreCase) >= 0
                || relative.IndexOf("spec", StringComparison.OrdinalIgnoreCase) >= 0
                || (project?.Name ?? string.Empty).IndexOf("test", StringComparison.OrdinalIgnoreCase) >= 0;
        }

        private static bool IsConfigFile(string relative)
        {
            var name = Path.GetFileName(relative);
            return IsUnityMetadataFile(relative)
                || name.EndsWith(".csproj", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".fsproj", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".vbproj", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".vcxproj", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".vcxproj.filters", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".slnx", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".props", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".targets", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".config", StringComparison.OrdinalIgnoreCase)
                || name.Equals("appsettings.json", StringComparison.OrdinalIgnoreCase)
                || name.Equals("Directory.Build.props", StringComparison.OrdinalIgnoreCase)
                || name.Equals("Directory.Build.targets", StringComparison.OrdinalIgnoreCase)
                || relative.IndexOf("ProjectSettings", StringComparison.OrdinalIgnoreCase) >= 0;
        }

        private static bool IsUnityMetadataFile(string relative)
        {
            var normalized = (relative ?? string.Empty).Replace('\\', '/').TrimStart('/');
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

        private static bool IsDocumentationFile(string relative)
        {
            var name = Path.GetFileName(relative);
            return name.Equals("README.md", StringComparison.OrdinalIgnoreCase)
                || name.Equals("CHANGELOG.md", StringComparison.OrdinalIgnoreCase)
                || name.IndexOf("TODO", StringComparison.OrdinalIgnoreCase) >= 0
                || name.EndsWith(".md", StringComparison.OrdinalIgnoreCase);
        }

        private static string NamespacePart(string fullName)
        {
            var index = fullName.LastIndexOf('.');
            return index > 0 ? fullName.Substring(0, index) : string.Empty;
        }

        private static IEnumerable<string> ExtractTokens(string text)
        {
            if (string.IsNullOrWhiteSpace(text))
            {
                return Enumerable.Empty<string>();
            }

            return Regex.Matches(text, @"[A-Za-z_][A-Za-z0-9_]{2,}")
                .Cast<Match>()
                .Select(match => match.Value)
                .Where(token => !IsControlWord(token))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .Take(40);
        }

        private static bool IsControlWord(string value)
        {
            switch ((value ?? string.Empty).ToLowerInvariant())
            {
                case "if":
                case "for":
                case "foreach":
                case "while":
                case "switch":
                case "catch":
                case "using":
                case "return":
                case "public":
                case "private":
                case "protected":
                case "internal":
                case "static":
                case "void":
                case "var":
                case "new":
                    return true;
                default:
                    return false;
            }
        }

        private static void AddUnique(ICollection<string> items, string value, int limit)
        {
            if (string.IsNullOrWhiteSpace(value) || items.Count >= limit || items.Contains(value))
            {
                return;
            }

            items.Add(value);
        }

        private static string[] SplitLines(string text)
        {
            return (text ?? string.Empty).Split(new[] { "\r\n", "\n" }, StringSplitOptions.None);
        }

        private sealed class FileAnalysis
        {
            public string File { get; set; } = string.Empty;
            public string Project { get; set; } = string.Empty;
            public long LastWriteTicks { get; set; }
            public long Length { get; set; }
            public bool IsTest { get; set; }
            public bool IsConfig { get; set; }
            public bool IsDocumentation { get; set; }
            public List<SymbolEntry> Symbols { get; } = new List<SymbolEntry>();
            public List<DependencyEntry> Dependencies { get; } = new List<DependencyEntry>();
        }

        private sealed class DependencyComparer : IEqualityComparer<DependencyEntry>
        {
            public bool Equals(DependencyEntry x, DependencyEntry y)
            {
                return string.Equals(x?.Project, y?.Project, StringComparison.OrdinalIgnoreCase)
                    && string.Equals(x?.Source, y?.Source, StringComparison.OrdinalIgnoreCase)
                    && string.Equals(x?.Target, y?.Target, StringComparison.OrdinalIgnoreCase)
                    && string.Equals(x?.Kind, y?.Kind, StringComparison.OrdinalIgnoreCase);
            }

            public int GetHashCode(DependencyEntry obj)
            {
                return string.Join("|", obj.Project, obj.Source, obj.Target, obj.Kind).ToLowerInvariant().GetHashCode();
            }
        }
    }
}
