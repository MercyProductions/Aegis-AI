using System;
using System.Text.RegularExpressions;

namespace Aegis.LocalAgent.VisualStudio.Services
{
    internal static class DiagnosticRedactor
    {
        private static readonly Regex UrlCredentialPattern = new Regex(
            @"\b(https?://)[^/\s:@]+:[^@\s/]+@",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        private static readonly Regex QuerySecretPattern = new Regex(
            @"([?&](?:api[_-]?key|key|token|secret|password|passwd|credential)=)[^&#\s]+",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        private static readonly Regex AssignmentSecretPattern = new Regex(
            @"\b((?:api[_-]?key|token|secret|password|passwd|credential|authorization)\s*[:=]\s*)[^\s&]+",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        private static readonly Regex AuthorizationHeaderPattern = new Regex(
            @"\b(Authorization\s*[:=]\s*)(?:Bearer|Basic|Digest)?\s*[A-Za-z0-9._~+/\-=]+",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        private static readonly Regex BearerTokenPattern = new Regex(
            @"\b(Bearer\s+)[A-Za-z0-9._~+/\-=]+",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        public static string RedactAndTruncate(string detail, int maxLength = 240)
        {
            if (string.IsNullOrWhiteSpace(detail))
            {
                return string.Empty;
            }

            var normalized = detail.Replace("\r", " ").Replace("\n", " ").Trim();
            var redacted = UrlCredentialPattern.Replace(normalized, "$1[redacted]@");
            redacted = QuerySecretPattern.Replace(redacted, "$1[redacted]");
            redacted = AuthorizationHeaderPattern.Replace(redacted, "$1[redacted]");
            redacted = BearerTokenPattern.Replace(redacted, "$1[redacted]");
            redacted = AssignmentSecretPattern.Replace(redacted, "$1[redacted]");

            if (maxLength <= 0 || redacted.Length <= maxLength)
            {
                return redacted;
            }

            return redacted.Substring(0, Math.Max(0, maxLength - 3)) + "...";
        }
    }
}
