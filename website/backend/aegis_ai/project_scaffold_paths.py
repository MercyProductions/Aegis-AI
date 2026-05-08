from __future__ import annotations

import re
from pathlib import Path


WINDOWS_PATH_STOP_PHRASES = (
    " here ",
    " i want",
    " i need",
    " i'm ",
    " im ",
    " can you",
    " could you",
    " please",
    " at this path",
    " at this location",
    " in this folder",
    " in this directory",
    " and then ",
    " then ",
    " so ",
    " but ",
    " because ",
    " with ",
    " using ",
    " for me",
    " if ",
    " create ",
    " build ",
    " launch ",
    " start ",
    " execute ",
    " run ",
    " validate ",
    " verify ",
    " check ",
    " refine ",
    " optimize ",
    " clean up ",
    " cleanup ",
    " polish ",
    " modernize ",
    " improve ",
    " ensure ",
    " test ",
    " compile ",
    " make ",
    " complete ",
    " combine ",
    " finish ",
    " develop ",
    " design and ",
    " design a ",
    " design an ",
    " design the ",
    " design this ",
    " ship ",
    " merge ",
    " split ",
    " separate ",
    " extract ",
    " generate ",
    " scaffold ",
    " set up ",
    " setup ",
    " start ",
    " write ",
    " run ",
    " add ",
    " implement ",
    " update ",
    " modify ",
    " work on ",
)
WINDOWS_PATH_STRONG_STOP_PHRASES = (
    " here ",
    " i want",
    " i need",
    " i'm ",
    " im ",
    " can you",
    " could you",
    " please",
    " at this path",
    " at this location",
    " in this folder",
    " in this directory",
    " and then ",
    " then ",
    " so ",
    " but ",
    " because ",
    " with ",
    " using ",
    " for me",
    " if ",
    " create ",
    " build ",
    " make ",
    " complete ",
    " refine ",
    " optimize ",
    " clean up ",
    " cleanup ",
    " polish ",
    " modernize ",
    " improve ",
    " combine ",
    " finish ",
    " develop ",
    " design and ",
    " design a ",
    " design an ",
    " design the ",
    " design this ",
    " ship ",
    " merge ",
    " split ",
    " separate ",
    " extract ",
    " generate ",
    " scaffold ",
    " set up ",
    " setup ",
    " write ",
    " add ",
    " implement ",
    " update ",
    " modify ",
    " work on ",
)
WINDOWS_PATH_CONTEXTUAL_ACTIONS = {
    "add",
    "build",
    "check",
    "compile",
    "complete",
    "combine",
    "create",
    "clean up",
    "cleanup",
    "develop",
    "execute",
    "extract",
    "finish",
    "generate",
    "improve",
    "implement",
    "launch",
    "make",
    "merge",
    "modify",
    "modernize",
    "optimize",
    "polish",
    "refine",
    "run",
    "scaffold",
    "separate",
    "set up",
    "setup",
    "ship",
    "split",
    "start",
    "test",
    "update",
    "validate",
    "verify",
    "work on",
    "write",
}
WINDOWS_PATH_ACTION_FOLLOWERS = {
    "a",
    "an",
    "and",
    "app",
    "application",
    "build",
    "c",
    "c#",
    "c++",
    "check",
    "cli",
    "cmake",
    "code",
    "console",
    "cpp",
    "desktop",
    "dll",
    "driver",
    "exe",
    "existing",
    "file",
    "fix",
    "folder",
    "for",
    "full",
    "it",
    "library",
    "me",
    "my",
    "native",
    "new",
    "project",
    "python",
    "run",
    "script",
    "sln",
    "solution",
    "test",
    "the",
    "this",
    "typescript",
    "validate",
    "web",
    "website",
    "working",
    "your",
}


def extract_windows_path_from_prompt(prompt: str) -> str:
    match = re.search(r"[A-Za-z]:[\\/]", prompt)
    if not match:
        return ""
    start = match.start()
    end = match.end()
    while end < len(prompt):
        if prompt[end] == "'":
            previous_char = prompt[end - 1] if end > start else ""
            next_char = prompt[end + 1] if end + 1 < len(prompt) else ""
            if previous_char.isalnum() and next_char.isalnum():
                end += 1
                continue
            break
        if prompt[end] in "\r\n\"`<>|*?":
            break
        end += 1
    return clean_windows_path_fragment(prompt[start:end])


def clean_windows_path_fragment(value: str) -> str:
    candidate = (value or "").strip()
    if not candidate:
        return ""
    candidate = trim_path_fragment(candidate)
    if path_fragment_exists(candidate):
        return candidate

    separator_position = path_instruction_separator_position(candidate)
    if separator_position is not None:
        earlier_action_positions = path_action_stop_positions(candidate, before=separator_position)
        if earlier_action_positions:
            candidate = candidate[: min(earlier_action_positions)].strip()
            return trim_path_fragment(candidate)
        separator_prefix = trim_path_fragment(candidate[:separator_position])
        if separator_prefix:
            return separator_prefix

    lowered = candidate.lower()
    stop_positions: list[tuple[int, str]] = []
    for phrase in WINDOWS_PATH_STOP_PHRASES:
        search_from = 3
        while True:
            found = lowered.find(phrase, search_from)
            if found == -1:
                break
            stop_positions.append((found, phrase))
            search_from = found + 1

    if stop_positions:
        existing_prefixes = [
            prefix
            for prefix in (trim_path_fragment(candidate[:position]) for position, _ in stop_positions)
            if path_fragment_exists(prefix)
        ]
        if existing_prefixes:
            return max(existing_prefixes, key=len)
        boundary_positions = [
            position
            for position, phrase in stop_positions
            if path_stop_phrase_is_boundary(lowered, position, phrase)
        ]
        strong_positions = [
            position
            for position, phrase in stop_positions
            if phrase in WINDOWS_PATH_STRONG_STOP_PHRASES
            and path_stop_phrase_is_boundary(lowered, position, phrase)
        ]
        action_positions = [
            position
            for position, phrase in stop_positions
            if phrase.strip() in WINDOWS_PATH_CONTEXTUAL_ACTIONS
            and path_stop_phrase_is_boundary(lowered, position, phrase)
        ]
        if action_positions and path_action_boundary_preserves_leaf(candidate, min(action_positions)):
            cut_position = min(action_positions)
        elif strong_positions:
            cut_position = min(strong_positions)
        elif boundary_positions:
            cut_position = min(boundary_positions)
        else:
            cut_position = min(position for position, _ in stop_positions)
        candidate = candidate[:cut_position].strip()
    return trim_path_fragment(candidate)


def path_action_stop_positions(candidate: str, *, before: int | None = None) -> list[int]:
    lowered = candidate.lower()
    positions: list[int] = []
    for phrase in WINDOWS_PATH_STOP_PHRASES:
        if phrase.strip() not in WINDOWS_PATH_CONTEXTUAL_ACTIONS:
            continue
        search_from = 3
        while True:
            found = lowered.find(phrase, search_from)
            if found == -1:
                break
            if before is not None and found >= before:
                break
            if (
                path_stop_phrase_is_boundary(lowered, found, phrase)
                and path_action_boundary_preserves_leaf(candidate, found)
            ):
                positions.append(found)
            search_from = found + 1
    return positions


def path_stop_phrase_is_boundary(lowered_candidate: str, position: int, phrase: str) -> bool:
    normalized_phrase = phrase.strip()
    if normalized_phrase not in WINDOWS_PATH_CONTEXTUAL_ACTIONS:
        return True
    after = lowered_candidate[position + len(phrase) :].lstrip(" \t")
    if not after:
        return True
    match = re.match(r"([a-z0-9_+#.-]+)", after)
    if not match:
        return True
    next_word = match.group(1).strip(".,;:!?()[]{}")
    if normalized_phrase in {"combine", "merge", "split", "separate", "extract"}:
        return next_word in {
            "a",
            "an",
            "another",
            "one",
            "project",
            "projects",
            "sln",
            "solution",
            "solutions",
            "the",
            "this",
            "two",
            "vcxproj",
            "visual",
        }
    return next_word in WINDOWS_PATH_ACTION_FOLLOWERS


def path_action_boundary_preserves_leaf(candidate: str, action_position: int) -> bool:
    leaf = re.split(r"[\\/]", candidate[:action_position].rstrip())[-1].strip()
    if not leaf:
        return False
    normalized_leaf = f" {' '.join(leaf.lower().split())} "
    location_markers = (
        " at this path ",
        " at this location ",
        " in this folder ",
        " in this directory ",
    )
    if any(marker in normalized_leaf for marker in location_markers):
        return False
    words = re.findall(r"[a-zA-Z0-9_+#.-]+", leaf)
    if not words or len(words) > 8:
        return False
    trailing_connector_words = {"and", "because", "but", "for", "if", "please", "so", "then", "to", "using", "with"}
    return words[-1].lower() not in trailing_connector_words


def path_instruction_separator_position(candidate: str) -> int | None:
    action_phrases = sorted(
        {phrase.strip() for phrase in WINDOWS_PATH_STOP_PHRASES if phrase.strip()}
        | WINDOWS_PATH_CONTEXTUAL_ACTIONS,
        key=len,
        reverse=True,
    )
    for match in re.finditer(r"\s+-\s+|[;:,]\s+", candidate[3:]):
        position = match.start() + 3
        leaf = re.split(r"[\\/]", candidate[:position].rstrip())[-1]
        if len(re.findall(r"[a-zA-Z0-9_+#.-]+", leaf)) > 8:
            continue
        after = candidate[position + len(match.group(0)) :].lstrip().lower()
        if not after:
            continue
        for phrase in action_phrases:
            if after == phrase or after.startswith(f"{phrase} "):
                return position
    return None


def trim_path_fragment(candidate: str) -> str:
    trimmed = re.sub(r"[\s.,;:]+$", "", candidate).strip()
    trimmed = re.sub(r"\s+-+$", "", trimmed).strip()
    while trimmed and trimmed[-1] in ")]}'\"`":
        if trailing_wrapper_belongs_to_path(trimmed):
            break
        trimmed = trimmed[:-1].rstrip()
        trimmed = re.sub(r"[\s.,;:]+$", "", trimmed).strip()
    return trimmed


def trailing_wrapper_belongs_to_path(candidate: str) -> bool:
    if not candidate:
        return False
    closer = candidate[-1]
    pairs = {")": "(", "]": "[", "}": "{"}
    opener = pairs.get(closer)
    if not opener:
        return False
    depth = 0
    for char in reversed(candidate):
        if char == closer:
            depth += 1
        elif char == opener:
            depth -= 1
            if depth == 0:
                return True
    return False


def path_fragment_exists(candidate: str) -> bool:
    if not candidate:
        return False
    try:
        return Path(candidate).exists()
    except OSError:
        return False


def prompt_without_windows_paths(prompt: str, *, target_path: str = "") -> str:
    cleaned = prompt
    extracted_path = extract_windows_path_from_prompt(prompt)
    for path in dict.fromkeys([target_path, extracted_path]):
        if path and path in cleaned:
            cleaned = cleaned.replace(path, " ", 1)
    cleaned = re.sub(
        r"\b(?:at\s+this\s+(?:path|location)|in\s+this\s+(?:folder|directory))\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    return " ".join(cleaned.split())
