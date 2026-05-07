from __future__ import annotations

from typing import TypedDict


class ExtractedProjectNote(TypedDict):
    category: str
    title: str
    detail: str
    confidence: float


CONSTRAINT_MARKERS = ("must", "must not", "do not", "don't", "never", "cannot", "can't", "without")
PREFERENCE_MARKERS = ("prefer", "should use", "use ", "uses ", "using ", "stick to", "keep ")
ARCHITECTURE_WORDS = (
    "react",
    "typescript",
    "javascript",
    "python",
    "fastapi",
    "sqlite",
    "postgres",
    "ollama",
    "llama.cpp",
    "vllm",
    "frontend",
    "backend",
    "api",
    "model",
)
ENVIRONMENT_WORDS = ("windows", "powershell", "batch", "cmd", "linux", "docker", "gpu", "cuda", "node", "npm")


def extract_project_notes(message: str) -> list[ExtractedProjectNote]:
    notes: list[ExtractedProjectNote] = []
    seen: set[str] = set()
    raw_segments = [segment.strip(" -\t") for segment in message.replace("\r", "\n").split("\n")]

    for segment in raw_segments:
        lowered = segment.lower()
        normalized = " ".join(segment.split())
        if len(normalized) < 18 or len(normalized) > 220:
            continue

        category: str | None = None
        confidence = 0.72

        if any(marker in lowered for marker in CONSTRAINT_MARKERS):
            category = "constraint"
            confidence = 0.86
        elif any(marker in lowered for marker in PREFERENCE_MARKERS):
            category = "preference"
            confidence = 0.78
        elif any(word in lowered for word in ARCHITECTURE_WORDS):
            category = "architecture"
            confidence = 0.68
        elif any(word in lowered for word in ENVIRONMENT_WORDS):
            category = "environment"
            confidence = 0.66

        if not category:
            continue

        if category == "preference" and len(normalized.split()) < 4:
            continue

        detail = normalized.rstrip(".")
        title = memory_title_for(category, detail)
        fingerprint = f"{category}:{title}:{detail}".lower()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        notes.append(
            {
                "category": category,
                "title": title,
                "detail": detail,
                "confidence": confidence,
            }
        )
        if len(notes) >= 4:
            break

    return notes


def memory_title_for(category: str, detail: str) -> str:
    compact = detail.replace('"', "'").strip()
    words = compact.split()
    if category == "constraint":
        return "Constraint"
    if category == "preference":
        return "Preference"
    if category == "architecture":
        return "Architecture"
    if category == "environment":
        return "Environment"
    return "Note" if not words else " ".join(words[:4])[:48]
