from __future__ import annotations

import re


SENSITIVE_FIELD = (
    r"x-api-key|api[_-]?key|api[_-]?token|access[_-]?token|refresh[_-]?token|id[_-]?token|token|"
    r"client[_-]?secret|secret|private[_-]?key|password|passwd|credential"
)
SENSITIVE_QUERY_RE = re.compile(
    rf"([?&](?:key|signature|{SENSITIVE_FIELD})=)[^&#\s]+",
    re.IGNORECASE,
)
SENSITIVE_ASSIGNMENT_RE = re.compile(
    rf"\b({SENSITIVE_FIELD})(\s*[:=]\s*)([^\s&]+)",
    re.IGNORECASE,
)
SENSITIVE_JSON_RE = re.compile(
    rf"""(["'](?:{SENSITIVE_FIELD}|authorization)["']\s*:\s*["'])[^"']+""",
    re.IGNORECASE,
)
AUTHORIZATION_HEADER_RE = re.compile(
    r"\b(Authorization\s*[:=]\s*)(?:Bearer|Basic|Digest)?\s*[A-Za-z0-9._~+/\-=]+",
    re.IGNORECASE,
)
BEARER_TOKEN_RE = re.compile(r"\b(Bearer\s+)[A-Za-z0-9._~+/\-=]+", re.IGNORECASE)
URL_CREDENTIAL_RE = re.compile(r"\b([a-z][a-z0-9+.-]*://)[^:/@\s]+:[^/@\s]+@", re.IGNORECASE)


def redact_inline(text: str) -> str:
    return "\n".join(_redact_inline_secrets(line) for line in str(text).splitlines())


def _redact_inline_secrets(line: str) -> str:
    redacted = URL_CREDENTIAL_RE.sub(r"\1[redacted]@", line)
    redacted = SENSITIVE_QUERY_RE.sub(r"\1[redacted]", redacted)
    redacted = SENSITIVE_JSON_RE.sub(r"\1[redacted]", redacted)
    redacted = AUTHORIZATION_HEADER_RE.sub(r"\1[redacted]", redacted)
    redacted = SENSITIVE_ASSIGNMENT_RE.sub(_redact_assignment, redacted)
    return BEARER_TOKEN_RE.sub(r"\1[redacted]", redacted)


def _redact_assignment(match: re.Match[str]) -> str:
    field = match.group(1)
    separator = match.group(2)
    value = match.group(3)
    if field.lower() == "token" and not _looks_like_secret_value(value):
        return match.group(0)
    return f"{field}{separator}[redacted]"


def _looks_like_secret_value(value: str) -> bool:
    text = value.strip().strip("\"'`.,;)]}")
    lowered = text.lower()
    if lowered.startswith(("sk-", "ghp_", "gho_", "ghu_", "github_pat_", "xox", "ya29.", "eyj")):
        return True
    if len(text) >= 20 and re.search(r"[A-Za-z]", text) and re.search(r"\d", text):
        return True
    return len(text) >= 12 and any(char in text for char in "-_.") and bool(re.search(r"[A-Za-z]", text))
