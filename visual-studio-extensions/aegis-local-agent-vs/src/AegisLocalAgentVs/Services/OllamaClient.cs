using System;
using System.Collections.Generic;
using System.Linq;
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
    internal sealed class OllamaClient
    {
        private static readonly HttpClient Http = new HttpClient { Timeout = TimeSpan.FromMinutes(10) };
        private readonly Func<AegisSettingsSnapshot> settingsProvider;

        public OllamaClient(
            string baseUrl = "http://127.0.0.1:11434",
            string defaultModel = "qwen3-coder:30b",
            IReadOnlyList<string> fallbacks = null,
            Func<AegisSettingsSnapshot> settingsProvider = null)
        {
            this.settingsProvider = settingsProvider ?? (() => new AegisSettingsSnapshot
            {
                OllamaUrl = baseUrl,
                DefaultModel = defaultModel,
                FallbackModels = (fallbacks ?? new[] { "qwen2.5-coder:7b", "granite-code:8b" }).ToArray()
            });
        }

        public async Task<IReadOnlyList<OllamaModel>> ListModelsAsync(CancellationToken cancellationToken = default)
        {
            var settings = GetSettings();
            using (var response = await Http.GetAsync(OllamaUrl(settings, "/api/tags"), cancellationToken))
            {
                await EnsureSuccessAsync(response, "list Ollama models");
                var text = await response.Content.ReadAsStringAsync();
                var json = ParseJsonObject(text, "list Ollama models");
                return json["models"]?
                    .Select(item => new OllamaModel
                    {
                        Name = (string)item["name"] ?? (string)item["model"] ?? string.Empty
                    })
                    .Where(model => !string.IsNullOrWhiteSpace(model.Name))
                    .ToList()
                    ?? new List<OllamaModel>();
            }
        }

        public async Task<string> ChatWithFallbackAsync(string prompt, bool json = false, string preferredModel = null, CancellationToken cancellationToken = default)
        {
            Exception lastError = null;
            var settings = GetSettings();
            var candidates = new[] { preferredModel, settings.DefaultModel }
                .Concat(settings.FallbackModels ?? Array.Empty<string>())
                .Where(name => !string.IsNullOrWhiteSpace(name))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();

            foreach (var model in candidates)
            {
                try
                {
                    return await ChatAsync(model, prompt, json, settings, cancellationToken);
                }
                catch (Exception ex)
                {
                    lastError = ex;
                }
            }

            throw lastError ?? new InvalidOperationException("No Ollama model was available.");
        }

        private async Task<string> ChatAsync(string model, string prompt, bool json, AegisSettingsSnapshot settings, CancellationToken cancellationToken)
        {
            var body = new JObject
            {
                ["model"] = model,
                ["stream"] = false,
                ["messages"] = new JArray
                {
                    new JObject
                    {
                        ["role"] = "system",
                        ["content"] = "You are Aegis Local Agent, a precise local coding assistant inside Visual Studio."
                    },
                    new JObject
                    {
                        ["role"] = "user",
                        ["content"] = prompt
                    }
                },
                ["options"] = new JObject
                {
                    ["temperature"] = json ? 0.12 : 0.2,
                    ["num_ctx"] = Math.Max(4096, Math.Min(settings.MaxContextSize, 131072))
                }
            };

            if (json)
            {
                body["format"] = "json";
            }

            using (var content = new StringContent(body.ToString(Formatting.None), Encoding.UTF8, "application/json"))
            {
                using (var response = await Http.PostAsync(OllamaUrl(settings, "/api/chat"), content, cancellationToken))
                {
                    await EnsureSuccessAsync(response, $"chat with Ollama model '{model}'");
                    var text = await response.Content.ReadAsStringAsync();
                    var parsed = ParseJsonObject(text, $"chat with Ollama model '{model}'");
                    return ((string)parsed["message"]?["content"] ?? text).Trim();
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
            var message = $"Could not {action}: Ollama returned HTTP {(int)response.StatusCode}";
            var detail = ExtractErrorDetail(text);
            if (!string.IsNullOrWhiteSpace(detail))
            {
                message += $" - {detail}";
            }

            throw new InvalidOperationException(message);
        }

        private static JObject ParseJsonObject(string responseText, string action)
        {
            if (string.IsNullOrWhiteSpace(responseText))
            {
                throw new InvalidOperationException($"Could not {action}: Ollama returned an empty response.");
            }

            try
            {
                return JObject.Parse(responseText);
            }
            catch (JsonException ex)
            {
                throw new InvalidOperationException($"Could not {action}: Ollama returned invalid JSON - {ex.Message}", ex);
            }
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
                var detail = parsed.Value<string>("error")
                    ?? parsed.Value<string>("message")
                    ?? parsed.Value<string>("detail");
                return TruncateDetail(detail);
            }
            catch (JsonException)
            {
                return TruncateDetail(responseText.Trim());
            }
        }

        private static string TruncateDetail(string detail)
        {
            return DiagnosticRedactor.RedactAndTruncate(detail);
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

        private static string OllamaUrl(AegisSettingsSnapshot settings, string path)
        {
            return AegisSettingsSnapshot.BuildServiceUrl(settings?.OllamaUrl, "http://127.0.0.1:11434", path);
        }
    }
}
