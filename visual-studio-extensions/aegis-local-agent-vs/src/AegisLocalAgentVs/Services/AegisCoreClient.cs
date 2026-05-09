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

            var text = await Http.GetStringAsync(url);
            return JObject.Parse(text);
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
                var response = await Http.PostAsync($"{BaseUrl}/v1/clients/register", content, cancellationToken);
                response.EnsureSuccessStatusCode();
            }
        }

        private string BaseUrl
        {
            get
            {
                var settings = settingsProvider?.Invoke() ?? AegisSettingsSnapshot.Default;
                return string.IsNullOrWhiteSpace(settings.AegisCoreUrl)
                    ? "http://127.0.0.1:8788"
                    : settings.AegisCoreUrl.Trim().TrimEnd('/');
            }
        }
    }
}
