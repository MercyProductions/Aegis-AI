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
            var response = await Http.GetAsync($"{NormalizeBaseUrl(settings)}/api/tags", cancellationToken);
            response.EnsureSuccessStatusCode();
            var text = await response.Content.ReadAsStringAsync();
            var json = JObject.Parse(text);
            return json["models"]?
                .Select(item => new OllamaModel
                {
                    Name = (string)item["name"] ?? (string)item["model"] ?? string.Empty
                })
                .Where(model => !string.IsNullOrWhiteSpace(model.Name))
                .ToList()
                ?? new List<OllamaModel>();
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
                var response = await Http.PostAsync($"{NormalizeBaseUrl(settings)}/api/chat", content, cancellationToken);
                response.EnsureSuccessStatusCode();
                var text = await response.Content.ReadAsStringAsync();
                var parsed = JObject.Parse(text);
                return ((string)parsed["message"]?["content"] ?? text).Trim();
            }
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

        private static string NormalizeBaseUrl(AegisSettingsSnapshot settings)
        {
            var url = settings?.OllamaUrl;
            return string.IsNullOrWhiteSpace(url)
                ? "http://127.0.0.1:11434"
                : url.Trim().TrimEnd('/');
        }
    }
}
