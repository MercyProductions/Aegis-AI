from __future__ import annotations

from collections.abc import Iterable


EXPLANATION_PREFIXES: tuple[str, ...] = (
    "how do i",
    "how can i",
    "how should i",
    "what command",
    "what is the command",
    "explain",
    "tell me how",
    "show me how",
)

EXECUTION_VALIDATION_PHRASES: tuple[str, ...] = (
    "and build it",
    "also build it",
    "then build it",
    "build and run",
    "build/run",
    "build it",
    "build this",
    "build the project",
    "build the app",
    "launch it",
    "launch this",
    "launch the app",
    "launch the project",
    "start it",
    "start this",
    "start the app",
    "start the project",
    "execute it",
    "execute this",
    "execute the app",
    "execute the project",
    "run build",
    "run the build",
    "run it",
    "run this",
    "run the app",
    "run the project",
    "run validation",
    "validate it",
    "validate this",
    "validate the project",
    "verify it",
    "verify this",
    "verify build",
    "verify the build",
    "verify the project",
    "check the build",
    "check for errors",
    "run tests",
    "run the tests",
    "test it",
    "test this",
    "compile it",
    "compile this",
    "compile the app",
    "compile the project",
    "make sure it builds",
    "make sure it compiles",
    "make sure this compiles",
    "make sure there are no errors",
    "no build errors",
    "no compilation errors",
    "no syntax errors",
    "fix any errors",
    "fix build errors",
    "repair the build",
    "repair build",
    "continue build",
    "continue the build",
    "continue validation",
    "last failed build",
    "failed build",
    "build failed",
    "rerun build",
    "rerun the build",
    "rerun validation",
    "rerun the validation",
    "try the build again",
    "try building again",
    "run it again",
    "you didn't build",
    "you didnt build",
    "didn't build",
    "didnt build",
)


def normalize_prompt_text(message: str) -> str:
    normalized_chars: list[str] = []
    for char in (message or "").strip().lower():
        if char.isalnum() or char in {"'", "+", "#"}:
            normalized_chars.append(char)
        else:
            normalized_chars.append(" ")
    return f" {' '.join(''.join(normalized_chars).split())} "


def prompt_has_explanation_prefix(message: str) -> bool:
    normalized = normalize_prompt_text(message)
    if not normalized.strip():
        return False
    return any(_contains_phrase(normalized, prefix) for prefix in EXPLANATION_PREFIXES)


def prompt_contains_any_phrase(message: str, phrases: Iterable[str]) -> bool:
    normalized = normalize_prompt_text(message)
    if not normalized.strip():
        return False
    return any(_contains_phrase(normalized, phrase) for phrase in phrases)


def prompt_requests_execution_validation(message: str, *, extra_phrases: Iterable[str] = ()) -> bool:
    normalized = normalize_prompt_text(message)
    if not normalized.strip():
        return False
    if prompt_has_explanation_prefix(normalized):
        return False
    return any(
        _contains_phrase(normalized, phrase)
        for phrase in (*EXECUTION_VALIDATION_PHRASES, *tuple(extra_phrases))
    )


def _contains_phrase(normalized: str, phrase: str) -> bool:
    clean = normalize_prompt_text(phrase).strip()
    if not clean:
        return False
    return f" {clean} " in normalized
