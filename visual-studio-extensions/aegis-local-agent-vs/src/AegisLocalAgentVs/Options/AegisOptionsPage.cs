using System;
using System.ComponentModel;
using System.Linq;
using Microsoft.VisualStudio.Shell;

namespace Aegis.LocalAgent.VisualStudio.Options
{
    public enum AegisSafetyMode
    {
        Strict,
        Balanced
    }

    public enum AegisBuildValidationPreference
    {
        Solution,
        StartupProject,
        SelectedProject,
        None
    }

    public sealed class AegisOptionsPage : DialogPage
    {
        [Category("Ollama")]
        [DisplayName("Ollama URL")]
        [Description("Base URL for the local Ollama server. Host:port and pasted API URLs are normalized before use; reverse-proxy path prefixes are preserved.")]
        public string OllamaUrl { get; set; } = "http://127.0.0.1:11434";

        [Category("Aegis Core")]
        [DisplayName("Aegis Core URL")]
        [Description("Base URL for the shared local Aegis Core runtime. Host:port and pasted API URLs are normalized before use; reverse-proxy path prefixes are preserved.")]
        public string AegisCoreUrl { get; set; } = "http://127.0.0.1:8788";

        [Category("Ollama")]
        [DisplayName("Default Model")]
        [Description("Default local model used for chat and agent proposals.")]
        public string DefaultModel { get; set; } = "qwen3-coder:30b";

        [Category("Ollama")]
        [DisplayName("Fallback Models")]
        [Description("Comma-separated fallback models used when the selected/default model fails.")]
        public string FallbackModels { get; set; } = "qwen2.5-coder:7b, granite-code:8b";

        [Category("Context")]
        [DisplayName("Max Context Size")]
        [Description("Maximum prompt context size used by Aegis before truncation.")]
        public int MaxContextSize { get; set; } = 42000;

        [Category("Safety")]
        [DisplayName("Safety Mode")]
        [Description("Strict keeps all protected path checks enabled. Balanced is reserved for future lower-friction workflows.")]
        public AegisSafetyMode SafetyMode { get; set; } = AegisSafetyMode.Strict;

        [Category("Indexing")]
        [DisplayName("Auto Scan On Solution Open")]
        [Description("Automatically index solution symbols and dependencies when a solution opens. Disabled by default to keep large solutions responsive at startup.")]
        public bool AutoScanOnSolutionOpen { get; set; } = false;

        [Category("Validation")]
        [DisplayName("Validate After Apply")]
        [Description("Run Visual Studio build validation after approved edits are applied.")]
        public bool ValidateAfterApply { get; set; } = true;

        [Category("Validation")]
        [DisplayName("Build Validation Preference")]
        [Description("Preferred validation target for manual agent workflows.")]
        public AegisBuildValidationPreference BuildValidationPreference { get; set; } = AegisBuildValidationPreference.Solution;

        [Category("Backups")]
        [DisplayName("Backup Location")]
        [Description("Relative solution path where approved-change backups are written.")]
        public string BackupLocation { get; set; } = ".aegis/backups";

        internal AegisSettingsSnapshot ToSnapshot()
        {
            var fallbacks = (FallbackModels ?? string.Empty)
                .Split(new[] { ',', ';', '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(item => item.Trim())
                .Where(item => !string.IsNullOrWhiteSpace(item))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToArray();

            return new AegisSettingsSnapshot
            {
                OllamaUrl = AegisSettingsSnapshot.NormalizeHttpBaseUrl(OllamaUrl, "http://127.0.0.1:11434"),
                AegisCoreUrl = AegisSettingsSnapshot.NormalizeHttpBaseUrl(AegisCoreUrl, "http://127.0.0.1:8788"),
                DefaultModel = string.IsNullOrWhiteSpace(DefaultModel) ? "qwen3-coder:30b" : DefaultModel.Trim(),
                FallbackModels = fallbacks.Length == 0 ? new[] { "qwen2.5-coder:7b", "granite-code:8b" } : fallbacks,
                MaxContextSize = Math.Max(8000, Math.Min(MaxContextSize, 160000)),
                SafetyMode = SafetyMode,
                AutoScanOnSolutionOpen = AutoScanOnSolutionOpen,
                ValidateAfterApply = ValidateAfterApply,
                BuildValidationPreference = BuildValidationPreference,
                BackupLocation = string.IsNullOrWhiteSpace(BackupLocation) ? ".aegis/backups" : BackupLocation.Trim()
            };
        }
    }

    internal sealed class AegisSettingsSnapshot
    {
        public string OllamaUrl { get; set; } = "http://127.0.0.1:11434";
        public string AegisCoreUrl { get; set; } = "http://127.0.0.1:8788";
        public string DefaultModel { get; set; } = "qwen3-coder:30b";
        public string[] FallbackModels { get; set; } = new[] { "qwen2.5-coder:7b", "granite-code:8b" };
        public int MaxContextSize { get; set; } = 42000;
        public AegisSafetyMode SafetyMode { get; set; } = AegisSafetyMode.Strict;
        public bool AutoScanOnSolutionOpen { get; set; } = false;
        public bool ValidateAfterApply { get; set; } = true;
        public AegisBuildValidationPreference BuildValidationPreference { get; set; } = AegisBuildValidationPreference.Solution;
        public string BackupLocation { get; set; } = ".aegis/backups";

        public static AegisSettingsSnapshot Default { get; } = new AegisSettingsSnapshot();

        internal static string NormalizeHttpBaseUrl(string value, string fallback)
        {
            var defaultBase = (fallback ?? string.Empty).Trim().TrimEnd('/');
            var raw = (value ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(raw) || raw.Any(char.IsWhiteSpace))
            {
                return defaultBase;
            }

            var candidate = raw;
            if (!candidate.StartsWith("http://", StringComparison.OrdinalIgnoreCase) &&
                !candidate.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
            {
                if (candidate.Contains("://"))
                {
                    return defaultBase;
                }

                candidate = "http://" + candidate;
            }

            if (!Uri.TryCreate(candidate, UriKind.Absolute, out var uri) ||
                (uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps) ||
                string.IsNullOrWhiteSpace(uri.Host) ||
                !string.IsNullOrEmpty(uri.UserInfo))
            {
                return defaultBase;
            }

            var builder = new UriBuilder(uri.Scheme, uri.Host, uri.IsDefaultPort ? -1 : uri.Port);
            var authority = builder.Uri.GetLeftPart(UriPartial.Authority).TrimEnd('/');
            return authority + StripKnownServiceEndpointPath(uri.AbsolutePath);
        }

        internal static string BuildServiceUrl(string value, string fallback, string path)
        {
            var baseUrl = NormalizeHttpBaseUrl(value, fallback).TrimEnd('/');
            var suffix = (path ?? string.Empty).TrimStart('/');
            return string.IsNullOrWhiteSpace(suffix) ? baseUrl : baseUrl + "/" + suffix;
        }

        private static string StripKnownServiceEndpointPath(string path)
        {
            var cleaned = (path ?? string.Empty).TrimEnd('/');
            if (string.IsNullOrWhiteSpace(cleaned) || cleaned == "/")
            {
                return string.Empty;
            }

            var segments = cleaned
                .Split(new[] { '/' }, StringSplitOptions.RemoveEmptyEntries)
                .ToArray();
            var lowered = segments.Select(segment => segment.ToLowerInvariant()).ToArray();

            var v1Index = Array.IndexOf(lowered, "v1");
            if (v1Index >= 0)
            {
                return v1Index == 0 ? string.Empty : "/" + string.Join("/", segments.Take(v1Index));
            }

            var apiIndex = Array.IndexOf(lowered, "api");
            var ollamaEndpoint = apiIndex >= 0 && apiIndex + 1 < lowered.Length ? lowered[apiIndex + 1] : string.Empty;
            var ollamaEndpointPaths = new[] { "chat", "embeddings", "generate", "ps", "show", "tags", "version" };
            if (apiIndex >= 0 && ollamaEndpointPaths.Contains(ollamaEndpoint))
            {
                return apiIndex == 0 ? string.Empty : "/" + string.Join("/", segments.Take(apiIndex));
            }

            var lastSegment = lowered.LastOrDefault();
            if (lastSegment == "health" || lastSegment == "models")
            {
                return segments.Length <= 1 ? string.Empty : "/" + string.Join("/", segments.Take(segments.Length - 1));
            }

            return cleaned;
        }
    }
}
