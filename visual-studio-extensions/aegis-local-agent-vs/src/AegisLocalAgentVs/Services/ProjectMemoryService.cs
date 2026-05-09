using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Aegis.LocalAgent.VisualStudio.Models;
using Newtonsoft.Json;

namespace Aegis.LocalAgent.VisualStudio.Services
{
    internal sealed class ProjectMemoryService
    {
        private static readonly Regex SecretLine = new Regex(@"(x-api-key|api[_-]?key|api[_-]?token|access[_-]?token|refresh[_-]?token|id[_-]?token|client[_-]?secret|secret|token|password|passwd|credential|authorization|auth|private[_-]?key)\s*[:=]", RegexOptions.IgnoreCase | RegexOptions.Compiled);
        private readonly string[] memoryFiles =
        {
            "solution-summary.md",
            "roadmap.md",
            "architecture-map.md",
            "decisions.md",
            "known-issues.md",
            "build-log.md",
            "agent-history.json",
            "symbol-index.json",
            "dependency-map.json"
        };

        public async Task<string> EnsureMemoryAsync(SolutionContext context)
        {
            var root = GetMemoryRoot(context);
            if (string.IsNullOrWhiteSpace(root))
            {
                return string.Empty;
            }

            if (!TryEnsureDirectory(root))
            {
                return string.Empty;
            }

            foreach (var file in memoryFiles)
            {
                var path = Path.Combine(root, file);
                var content = file.Equals("agent-history.json", StringComparison.OrdinalIgnoreCase)
                    ? "[]" + Environment.NewLine
                    : file.EndsWith(".json", StringComparison.OrdinalIgnoreCase)
                        ? JsonConvert.SerializeObject(new { createdAt = DateTime.UtcNow, items = new object[0] }, Formatting.Indented) + Environment.NewLine
                        : $"# {Path.GetFileNameWithoutExtension(file)}{Environment.NewLine}";
                TryEnsureMemoryFile(path, content);
            }

            await Task.Yield();
            return root;
        }

        public async Task UpdateFromScanAsync(SolutionContext context)
        {
            var root = await EnsureMemoryAsync(context);
            if (string.IsNullOrWhiteSpace(root))
            {
                return;
            }

            var summary = new List<string>
            {
                $"Updated: {DateTime.UtcNow:o}",
                string.Empty,
                $"Solution: {context.SolutionName}",
                $"Path: {context.SolutionPath}",
                $"Startup project: {context.StartupProject}",
                $"Intelligence: {context.IntelligenceStatus.Summary}",
                string.Empty,
                "## Projects"
            };
            summary.AddRange(context.Projects.Select(project => $"- {project.Name}: {project.DetectedType}"));
            summary.AddRange(context.Projects.Select(project =>
                $"  - {project.Name} details: frameworks [{string.Join(", ", project.TargetFrameworks.Take(6))}], packages [{string.Join(", ", project.Packages.Take(10))}], project refs [{string.Join(", ", project.ProjectReferences.Take(8))}], tests [{project.TestFiles.Count}], symbols [{string.Join(", ", project.Symbols.Take(10))}]"));
            summary.Add(string.Empty);
            summary.Add("## Important Files");
            summary.AddRange(context.ImportantFiles.Take(60).Select(file => $"- {file}"));
            summary.Add(string.Empty);
            summary.Add("## Indexed Symbols");
            summary.AddRange(context.SymbolIndex.Take(80).Select(symbol => $"- {symbol.Kind} {symbol.Name} ({symbol.Project}) {symbol.File}:{symbol.Line}"));
            summary.Add(string.Empty);
            summary.Add("## Validation");
            summary.AddRange(context.ValidationHints.Select(item => $"- {item}"));

            await WriteManagedSectionAsync(Path.Combine(root, "solution-summary.md"), "Aegis Generated Summary", summary);

            var architecture = new List<string>
            {
                $"Updated: {DateTime.UtcNow:o}",
                string.Empty,
                "## Solution Overview",
                context.ArchitectureSummary,
                string.Empty,
                "## Project Map"
            };
            architecture.AddRange(context.Projects.Select(project => $"- {project.Name} ({project.DetectedType}) {SolutionScanner.MakeRelative(context.SolutionRoot, project.Path)}"));
            architecture.AddRange(context.Projects.Select(project =>
                $"  - Project signals: refs {project.ProjectReferences.Count}, packages {project.Packages.Count}, tests {project.TestFiles.Count}, configs {project.ConfigFiles.Count}, XAML {project.XamlFiles.Count}, headers {project.HeaderFiles.Count}, sources {project.SourceFiles.Count}, include paths {project.IncludePaths.Count}, Unity [{string.Join(", ", project.UnitySignals.Take(6))}]"));
            architecture.Add(string.Empty);
            architecture.Add("## Build Dependencies");
            architecture.AddRange(context.DependencyMap
                .Where(dep => dep.Kind.Equals("ProjectReference", StringComparison.OrdinalIgnoreCase))
                .Take(120)
                .Select(dep => $"- {dep.Source} -> {dep.Target}"));
            architecture.Add(string.Empty);
            architecture.Add("## Major Symbols");
            architecture.AddRange(context.SymbolIndex
                .Where(symbol => symbol.Kind.Equals("class", StringComparison.OrdinalIgnoreCase)
                    || symbol.Kind.Equals("interface", StringComparison.OrdinalIgnoreCase)
                    || symbol.Kind.Equals("XAML view", StringComparison.OrdinalIgnoreCase)
                    || symbol.Kind.Equals("MonoBehaviour", StringComparison.OrdinalIgnoreCase))
                .Take(120)
                .Select(symbol => $"- {symbol.Kind} {symbol.Name} ({symbol.Project}) {symbol.File}:{symbol.Line}"));
            architecture.Add(string.Empty);
            architecture.Add("## Recent Files");
            architecture.AddRange(context.RecentFiles.Take(40).Select(file => $"- {file}"));
            await WriteManagedSectionAsync(Path.Combine(root, "architecture-map.md"), "Aegis Architecture Map", architecture);

            await WriteJsonAsync(Path.Combine(root, "symbol-index.json"), new
            {
                updatedAt = DateTime.UtcNow,
                solution = context.SolutionName,
                status = context.IntelligenceStatus,
                symbols = context.SymbolIndex
            });

            await WriteJsonAsync(Path.Combine(root, "dependency-map.json"), new
            {
                updatedAt = DateTime.UtcNow,
                solution = context.SolutionName,
                projects = context.Projects.Select(project => new
                {
                    project.Name,
                    project.DetectedType,
                    path = SolutionScanner.MakeRelative(context.SolutionRoot, project.Path),
                    project.ProjectReferences,
                    project.AssemblyReferences,
                    project.Packages,
                    project.TestFiles,
                    project.ConfigFiles
                }),
                dependencies = context.DependencyMap
            });
        }

        public async Task<string> ReadMemoryContextAsync(SolutionContext context)
        {
            var root = await EnsureMemoryAsync(context);
            if (string.IsNullOrWhiteSpace(root))
            {
                return string.Empty;
            }

            var chunks = new List<string>();
            foreach (var file in memoryFiles.Where(file => file.EndsWith(".md", StringComparison.OrdinalIgnoreCase)))
            {
                var path = Path.Combine(root, file);
                var text = SafeReadText(path);
                if (!string.IsNullOrWhiteSpace(text))
                {
                    chunks.Add($"# Memory: {file}{Environment.NewLine}{Sanitize(text)}");
                }
            }

            return SolutionScanner.Truncate(string.Join(Environment.NewLine + Environment.NewLine, chunks), 24000);
        }

        public async Task<string> ReadArchitectureAsync(SolutionContext context)
        {
            var root = await EnsureMemoryAsync(context);
            if (string.IsNullOrWhiteSpace(root))
            {
                return string.Empty;
            }

            var path = Path.Combine(root, "architecture-map.md");
            return Sanitize(SafeReadText(path));
        }

        public async Task WriteRoadmapAsync(SolutionContext context, string roadmap)
        {
            var root = await EnsureMemoryAsync(context);
            if (string.IsNullOrWhiteSpace(root))
            {
                return;
            }

            await WriteManagedSectionAsync(Path.Combine(root, "roadmap.md"), "Aegis Generated Roadmap", Sanitize(roadmap).Split(new[] { "\r\n", "\n" }, StringSplitOptions.None));
        }

        public async Task<string> ReadRoadmapAsync(SolutionContext context)
        {
            var root = await EnsureMemoryAsync(context);
            if (string.IsNullOrWhiteSpace(root))
            {
                return string.Empty;
            }

            var path = Path.Combine(root, "roadmap.md");
            return Sanitize(SafeReadText(path));
        }

        public async Task AppendDecisionAsync(SolutionContext context, string text)
        {
            var root = await EnsureMemoryAsync(context);
            if (string.IsNullOrWhiteSpace(root))
            {
                return;
            }

            SafeAppendAllText(Path.Combine(root, "decisions.md"), Environment.NewLine + $"## {DateTime.UtcNow:o}{Environment.NewLine}{Sanitize(text)}{Environment.NewLine}");
        }

        public async Task AppendValidationAsync(SolutionContext context, BuildResult result)
        {
            var root = await EnsureMemoryAsync(context);
            if (string.IsNullOrWhiteSpace(root))
            {
                return;
            }

            SafeAppendAllText(Path.Combine(root, "build-log.md"),
                Environment.NewLine +
                $"## {DateTime.UtcNow:o} - {(result.Success ? "PASS" : "FAIL")}{Environment.NewLine}" +
                "```text" + Environment.NewLine +
                Sanitize(result.Output) +
                Environment.NewLine + "```" + Environment.NewLine);
        }

        public async Task AppendHistoryAsync(SolutionContext context, object entry)
        {
            var root = await EnsureMemoryAsync(context);
            if (string.IsNullOrWhiteSpace(root))
            {
                return;
            }

            var path = Path.Combine(root, "agent-history.json");
            var history = new List<object>();
            try
            {
                history = JsonConvert.DeserializeObject<List<object>>(SafeReadText(path)) ?? history;
            }
            catch
            {
                history = new List<object>();
            }

            history.Insert(0, entry);
            SafeWriteAllText(path, JsonConvert.SerializeObject(history.Take(100).ToList(), Formatting.Indented));
        }

        public string GetMemoryRoot(SolutionContext context)
        {
            return string.IsNullOrWhiteSpace(context.SolutionRoot) ? string.Empty : Path.Combine(context.SolutionRoot, ".aegis");
        }

        private static async Task WriteManagedSectionAsync(string path, string title, IEnumerable<string> lines)
        {
            var start = $"<!-- BEGIN {title} -->";
            var end = $"<!-- END {title} -->";
            var section = start + Environment.NewLine + string.Join(Environment.NewLine, lines.Select(Sanitize)) + Environment.NewLine + end;
            var existing = SafeReadText(path);
            if (string.IsNullOrWhiteSpace(existing))
            {
                existing = $"# {Path.GetFileNameWithoutExtension(path)}{Environment.NewLine}";
            }

            var startIndex = existing.IndexOf(start, StringComparison.Ordinal);
            var endIndex = existing.IndexOf(end, StringComparison.Ordinal);
            string next;
            if (startIndex >= 0 && endIndex > startIndex)
            {
                next = existing.Substring(0, startIndex) + section + existing.Substring(endIndex + end.Length);
            }
            else
            {
                next = existing.TrimEnd() + Environment.NewLine + Environment.NewLine + section + Environment.NewLine;
            }

            SafeWriteAllText(path, next);
            await Task.Yield();
        }

        private static async Task WriteJsonAsync(string path, object value)
        {
            SafeWriteAllText(path, JsonConvert.SerializeObject(value, Formatting.Indented));
            await Task.Yield();
        }

        private static bool TryEnsureDirectory(string root)
        {
            try
            {
                Directory.CreateDirectory(root);
                return true;
            }
            catch
            {
                return false;
            }
        }

        private static void TryEnsureMemoryFile(string path, string content)
        {
            try
            {
                if (File.Exists(path) || Directory.Exists(path))
                {
                    return;
                }

                File.WriteAllText(path, content);
            }
            catch
            {
            }
        }

        private static string SafeReadText(string path)
        {
            try
            {
                return File.Exists(path) ? File.ReadAllText(path) : string.Empty;
            }
            catch
            {
                return string.Empty;
            }
        }

        private static void SafeWriteAllText(string path, string content)
        {
            try
            {
                File.WriteAllText(path, content);
            }
            catch
            {
            }
        }

        private static void SafeAppendAllText(string path, string content)
        {
            try
            {
                File.AppendAllText(path, content);
            }
            catch
            {
            }
        }

        private static string Sanitize(string text)
        {
            if (string.IsNullOrEmpty(text))
            {
                return string.Empty;
            }

            return string.Join(Environment.NewLine, text
                .Split(new[] { "\r\n", "\n" }, StringSplitOptions.None)
                .Where(line => !SecretLine.IsMatch(line)));
        }
    }
}
