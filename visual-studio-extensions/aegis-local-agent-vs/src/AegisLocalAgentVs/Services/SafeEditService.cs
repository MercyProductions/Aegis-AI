using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Aegis.LocalAgent.VisualStudio.Models;
using Aegis.LocalAgent.VisualStudio.Options;
using Newtonsoft.Json;

namespace Aegis.LocalAgent.VisualStudio.Services
{
    internal sealed class SafeEditService
    {
        private static readonly HashSet<string> BlockedSegments = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            ".git", ".vs", ".aegis", "bin", "obj", "packages", "node_modules", "vendor", "vendors", "dist", "build", "Generated"
        };

        private static readonly Regex SecretFilePattern = new Regex(@"(^\.env(\.|$)|secret|credential|token|private|\.pfx$|\.p12$|\.pem$|\.key$)", RegexOptions.IgnoreCase | RegexOptions.Compiled);
        private readonly Func<AegisSettingsSnapshot> settingsProvider;

        public AgentProposal PendingProposal { get; private set; }
        public IReadOnlyList<string> LastValidationMessages { get; private set; } = Array.Empty<string>();

        public SafeEditService(Func<AegisSettingsSnapshot> settingsProvider = null)
        {
            this.settingsProvider = settingsProvider ?? (() => AegisSettingsSnapshot.Default);
        }

        public IReadOnlyList<string> SetPendingProposal(SolutionContext context, AgentProposal proposal)
        {
            PendingProposal = proposal;
            LastValidationMessages = ValidateProposal(context, proposal).ToList();
            WritePreviewFiles(context, proposal);
            return LastValidationMessages;
        }

        public string BuildPreviewText(SolutionContext context, AgentProposal proposal)
        {
            if (proposal?.FileEdits == null || proposal.FileEdits.Count == 0)
            {
                return "No file edits proposed.";
            }

            var lines = new List<string>();
            foreach (var edit in proposal.FileEdits.Take(20))
            {
                lines.Add($"# {edit.Path}");
                lines.Add($"Reason: {edit.Reason}");
                if (!TryNormalizeSafePath(context, edit.Path, out var normalizedPath, out var message))
                {
                    lines.Add($"Blocked: {message}");
                    lines.Add("");
                    continue;
                }

                var target = ResolvePath(context, normalizedPath);
                var before = File.Exists(target) ? File.ReadAllText(target) : string.Empty;
                lines.AddRange(BuildCompactDiff(before, edit.Content ?? string.Empty));
                lines.Add("");
            }

            return string.Join(Environment.NewLine, lines);
        }

        public async Task<IReadOnlyList<string>> ApplyPendingProposalAsync(SolutionContext context, ProjectMemoryService memory)
        {
            if (PendingProposal == null)
            {
                return new[] { "No pending Aegis proposal is available." };
            }

            if (PendingProposal.FileEdits == null || PendingProposal.FileEdits.Count == 0)
            {
                return new[] { "The pending Aegis proposal contains no file edits to apply." };
            }

            var validation = ValidateProposal(context, PendingProposal).ToList();
            if (validation.Any())
            {
                return validation;
            }

            var backupBase = ResolveBackupBase(context);
            var backupRoot = Path.Combine(backupBase, Timestamp());
            var filesRoot = Path.Combine(backupRoot, "files");
            Directory.CreateDirectory(filesRoot);

            var manifest = new
            {
                createdAt = DateTime.UtcNow,
                solutionRoot = context.SolutionRoot,
                summary = PendingProposal.Summary,
                files = PendingProposal.FileEdits.Select(edit => new
                {
                    edit.Path,
                    existed = File.Exists(ResolvePath(context, edit.Path)),
                    backupPath = edit.Path.Replace('/', Path.DirectorySeparatorChar)
                }).ToList()
            };

            foreach (var edit in PendingProposal.FileEdits)
            {
                var target = ResolvePath(context, edit.Path);
                var backup = Path.Combine(filesRoot, edit.Path.Replace('/', Path.DirectorySeparatorChar));
                Directory.CreateDirectory(Path.GetDirectoryName(backup));
                if (File.Exists(target))
                {
                    File.Copy(target, backup, true);
                }

                Directory.CreateDirectory(Path.GetDirectoryName(target));
                File.WriteAllText(target, NormalizeLineEndings(edit.Content));
            }

            File.WriteAllText(Path.Combine(backupRoot, "manifest.json"), JsonConvert.SerializeObject(manifest, Formatting.Indented));
            Directory.CreateDirectory(backupBase);
            File.WriteAllText(Path.Combine(backupBase, "last-change.json"), JsonConvert.SerializeObject(manifest, Formatting.Indented));
            await memory.AppendHistoryAsync(context, new
            {
                type = "apply",
                at = DateTime.UtcNow,
                PendingProposal.Summary,
                files = PendingProposal.FileEdits.Select(edit => edit.Path).ToList()
            });
            await memory.AppendDecisionAsync(context, $"Applied approved Aegis proposal: {PendingProposal.Summary}{Environment.NewLine}Files: {string.Join(", ", PendingProposal.FileEdits.Select(edit => edit.Path))}");
            PendingProposal = null;
            return new[] { "Applied approved Aegis proposal with backup: " + backupRoot };
        }

        public async Task<IReadOnlyList<string>> RollbackLastChangeAsync(SolutionContext context)
        {
            var backupBase = ResolveBackupBase(context);
            var lastPath = Path.Combine(backupBase, "last-change.json");
            if (!File.Exists(lastPath))
            {
                return new[] { "No Aegis backup is available to roll back." };
            }

            dynamic manifest = JsonConvert.DeserializeObject(File.ReadAllText(lastPath));
            string createdAt = manifest.createdAt;
            var backupRoot = Path.Combine(backupBase, TimestampFromCreatedAt(createdAt));
            if (!Directory.Exists(backupRoot))
            {
                var candidates = Directory.GetDirectories(backupBase)
                    .Where(dir => File.Exists(Path.Combine(dir, "manifest.json")))
                    .OrderByDescending(Directory.GetCreationTimeUtc)
                    .ToList();
                backupRoot = candidates.FirstOrDefault();
            }

            if (string.IsNullOrWhiteSpace(backupRoot))
            {
                return new[] { "The last Aegis backup manifest exists, but its files were not found." };
            }

            var restored = new List<string>();
            foreach (var file in manifest.files)
            {
                string relative = file.Path;
                bool existed = file.existed;
                var target = ResolvePath(context, relative);
                var backup = Path.Combine(backupRoot, "files", relative.Replace('/', Path.DirectorySeparatorChar));
                if (existed && File.Exists(backup))
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(target));
                    File.Copy(backup, target, true);
                    restored.Add(relative);
                }
                else if (!existed && File.Exists(target))
                {
                    File.Delete(target);
                    restored.Add(relative);
                }
            }

            await Task.Yield();
            return new[] { $"Rolled back {restored.Count} file(s): {string.Join(", ", restored)}" };
        }

        public string ResolveBackupBase(SolutionContext context)
        {
            var settings = GetSettings();
            var configured = string.IsNullOrWhiteSpace(settings.BackupLocation) ? ".aegis/backups" : settings.BackupLocation;
            if (Path.IsPathRooted(configured))
            {
                return configured;
            }

            var resolved = Path.GetFullPath(Path.Combine(context.SolutionRoot, configured.Replace('/', Path.DirectorySeparatorChar)));
            if (!IsInside(context.SolutionRoot, resolved))
            {
                return Path.Combine(context.SolutionRoot, ".aegis", "backups");
            }

            return resolved;
        }

        private static IEnumerable<string> ValidateProposal(SolutionContext context, AgentProposal proposal)
        {
            if (string.IsNullOrWhiteSpace(context.SolutionRoot))
            {
                yield return "No solution root was detected.";
                yield break;
            }

            foreach (var edit in proposal.FileEdits ?? new List<FileEdit>())
            {
                if (!TryNormalizeSafePath(context, edit.Path, out _, out var message))
                {
                    yield return message;
                }
            }
        }

        private static void WritePreviewFiles(SolutionContext context, AgentProposal proposal)
        {
            if (string.IsNullOrWhiteSpace(context.SolutionRoot) || proposal?.FileEdits == null)
            {
                return;
            }

            var root = Path.Combine(context.SolutionRoot, ".aegis", "visual-studio-agent", "previews", Timestamp());
            foreach (var edit in proposal.FileEdits.Take(20))
            {
                if (!TryNormalizeSafePath(context, edit.Path, out var normalizedPath, out _))
                {
                    continue;
                }

                var target = ResolvePath(context, normalizedPath);
                var relativePath = normalizedPath.Replace('/', Path.DirectorySeparatorChar);
                var original = Path.Combine(root, "original", relativePath);
                var proposed = Path.Combine(root, "proposed", relativePath);
                Directory.CreateDirectory(Path.GetDirectoryName(original));
                Directory.CreateDirectory(Path.GetDirectoryName(proposed));
                File.WriteAllText(original, File.Exists(target) ? File.ReadAllText(target) : string.Empty);
                File.WriteAllText(proposed, edit.Content ?? string.Empty);
            }
        }

        private static bool TryNormalizeSafePath(SolutionContext context, string proposedPath, out string normalizedPath, out string message)
        {
            normalizedPath = string.Empty;
            message = string.Empty;

            if (string.IsNullOrWhiteSpace(proposedPath))
            {
                message = "A proposed edit has no path.";
                return false;
            }

            if (Path.IsPathRooted(proposedPath))
            {
                message = $"Blocked absolute path: {proposedPath}";
                return false;
            }

            normalizedPath = proposedPath.Replace('\\', '/').TrimStart('/');
            var segments = normalizedPath.Split(new[] { '/' }, StringSplitOptions.RemoveEmptyEntries);
            if (segments.Length == 0 || segments.Any(segment => BlockedSegments.Contains(segment)))
            {
                message = $"Blocked unsafe path: {proposedPath}";
                return false;
            }

            if (SecretFilePattern.IsMatch(Path.GetFileName(normalizedPath)))
            {
                message = $"Blocked secret-like path: {proposedPath}";
                return false;
            }

            var target = ResolvePath(context, normalizedPath);
            if (string.IsNullOrWhiteSpace(target) || !IsInside(context.SolutionRoot, target))
            {
                message = $"Path escapes the solution root: {proposedPath}";
                return false;
            }

            return true;
        }

        private AegisSettingsSnapshot GetSettings()
        {
            try
            {
                return settingsProvider?.Invoke() ?? AegisSettingsSnapshot.Default;
            }
            catch
            {
                return AegisSettingsSnapshot.Default;
            }
        }

        private static string ResolvePath(SolutionContext context, string relativePath)
        {
            return Path.GetFullPath(Path.Combine(context.SolutionRoot, relativePath.Replace('/', Path.DirectorySeparatorChar)));
        }

        private static bool IsInside(string root, string path)
        {
            var normalizedRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            var normalizedPath = Path.GetFullPath(path);
            return normalizedPath.StartsWith(normalizedRoot, StringComparison.OrdinalIgnoreCase);
        }

        private static string NormalizeLineEndings(string text)
        {
            return (text ?? string.Empty).Replace("\r\n", "\n").Replace("\r", "\n").Replace("\n", Environment.NewLine);
        }

        private static IEnumerable<string> BuildCompactDiff(string before, string after)
        {
            var beforeLines = NormalizeLineEndings(before).Split(new[] { Environment.NewLine }, StringSplitOptions.None);
            var afterLines = NormalizeLineEndings(after).Split(new[] { Environment.NewLine }, StringSplitOptions.None);
            var output = new List<string>();
            var max = Math.Max(beforeLines.Length, afterLines.Length);
            for (var i = 0; i < max && output.Count < 180; i++)
            {
                var oldLine = i < beforeLines.Length ? beforeLines[i] : null;
                var newLine = i < afterLines.Length ? afterLines[i] : null;
                if (string.Equals(oldLine, newLine, StringComparison.Ordinal))
                {
                    continue;
                }

                output.Add($"@@ line {i + 1} @@");
                if (oldLine != null) output.Add("- " + oldLine);
                if (newLine != null) output.Add("+ " + newLine);
            }

            if (output.Count == 0)
            {
                output.Add("(no textual differences)");
            }
            else if (output.Count >= 180)
            {
                output.Add("[diff truncated]");
            }

            return output;
        }

        private static string Timestamp()
        {
            return DateTime.UtcNow.ToString("yyyy-MM-ddTHH-mm-ss-fffZ");
        }

        private static string TimestampFromCreatedAt(string value)
        {
            if (DateTime.TryParse(value, out var date))
            {
                return date.ToUniversalTime().ToString("yyyy-MM-ddTHH-mm-ss-fffZ");
            }

            return value;
        }
    }
}
