using System;
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
        private static readonly HttpClient Http = new HttpClient { Timeout = TimeSpan.FromSeconds(20) };
        private readonly Func<AegisSettingsSnapshot> settingsProvider;

        public AegisCoreClient(Func<AegisSettingsSnapshot> settingsProvider)
        {
            this.settingsProvider = settingsProvider ?? (() => AegisSettingsSnapshot.Default);
        }

        public async Task<JObject> HealthAsync(string workspaceRoot, CancellationToken cancellationToken = default)
        {
            var url = $"{BaseUrl}/v1/health";
            if (!string.IsNullOrWhiteSpace(workspaceRoot))
            {
                url += "?workspace=" + Uri.EscapeDataString(workspaceRoot);
            }

            using (var response = await Http.GetAsync(url, cancellationToken))
            {
                await EnsureSuccessAsync(response, "read Aegis Core health");
                var text = await response.Content.ReadAsStringAsync();
                return ParseCoreEnvelope(text, "health", "read Aegis Core health");
            }
        }

        public async Task RegisterClientAsync(SolutionContext context, CancellationToken cancellationToken = default)
        {
            var root = context?.SolutionRoot;
            if (string.IsNullOrWhiteSpace(root))
            {
                return;
            }

            var body = new JObject
            {
                ["workspace"] = root,
                ["client_id"] = "aegis-visual-studio",
                ["client_type"] = "visual-studio-extension",
                ["name"] = "Aegis Local Agent for Visual Studio",
                ["version"] = "0.1.1",
                ["capabilities"] = new JArray("solution-scan", "error-list", "build-validation", "safe-apply")
            };

            using (var content = new StringContent(body.ToString(Formatting.None), Encoding.UTF8, "application/json"))
            {
                using (var response = await Http.PostAsync($"{BaseUrl}/v1/clients/register", content, cancellationToken))
                {
                    await EnsureSuccessAsync(response, "register Visual Studio client with Aegis Core");
                    var text = await response.Content.ReadAsStringAsync();
                    ParseCoreEnvelope(text, "client.registered", "register Visual Studio client with Aegis Core", requireOk: true);
                }
            }
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

            throw new InvalidOperationException(message);
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
                throw new InvalidOperationException($"Could not {action}: Aegis Core returned an empty response.");
            }

            JObject parsed;
            try
            {
                parsed = JObject.Parse(responseText);
            }
            catch (JsonException ex)
            {
                throw new InvalidOperationException($"Could not {action}: Aegis Core returned invalid JSON - {ex.Message}", ex);
            }

            var apiVersion = parsed.Value<string>("api_version");
            if (!string.Equals(apiVersion, "v1", StringComparison.OrdinalIgnoreCase))
            {
                var safeApiVersion = string.IsNullOrWhiteSpace(apiVersion) ? "missing" : DiagnosticRedactor.RedactAndTruncate(apiVersion);
                throw new InvalidOperationException($"Could not {action}: Aegis Core response used unexpected api_version: {safeApiVersion}.");
            }

            var kind = parsed.Value<string>("kind");
            if (!string.Equals(kind, expectedKind, StringComparison.OrdinalIgnoreCase))
            {
                var safeKind = string.IsNullOrWhiteSpace(kind) ? "missing" : DiagnosticRedactor.RedactAndTruncate(kind);
                throw new InvalidOperationException($"Could not {action}: Aegis Core response kind mismatch: expected {expectedKind}, got {safeKind}.");
            }

            JToken okToken;
            if (requireOk && parsed.TryGetValue("ok", out okToken) && okToken.Type == JTokenType.Boolean && !okToken.Value<bool>())
            {
                throw new InvalidOperationException($"Could not {action}: {ExtractCoreEnvelopeError(parsed)}");
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

        private string BaseUrl
        {
            get
            {
                var settings = settingsProvider?.Invoke() ?? AegisSettingsSnapshot.Default;
                return AegisSettingsSnapshot.NormalizeHttpBaseUrl(settings.AegisCoreUrl, "http://127.0.0.1:8788");
            }
        }
    }
}
