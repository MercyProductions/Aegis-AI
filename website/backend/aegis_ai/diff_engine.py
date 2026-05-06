"""Diff and patch generation engine for intelligent file changes."""

from __future__ import annotations

from dataclasses import dataclass
import difflib
import re


@dataclass
class FileDiff:
    """Represents a diff between two file versions."""

    path: str
    action: str
    old_content: str | None
    new_content: str | None
    added_lines: int
    removed_lines: int
    modified_lines: int

    def get_patch(self) -> str:
        """Generate a unified diff patch format."""

        old_lines = (self.old_content or "").splitlines(keepends=True)
        new_lines = (self.new_content or "").splitlines(keepends=True)
        fromfile = "/dev/null" if self.action == "create" else f"a/{self.path}"
        tofile = "/dev/null" if self.action == "delete" else f"b/{self.path}"

        return "".join(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=fromfile,
                tofile=tofile,
                lineterm="\n",
            )
        )


class DiffEngine:
    """Engine for generating and applying diffs."""

    @staticmethod
    def compare_files(old_content: str | None, new_content: str | None, path: str, action: str) -> FileDiff:
        """Compare two file contents and generate a diff."""

        old_lines = (old_content or "").splitlines()
        new_lines = (new_content or "").splitlines()

        added_lines = 0
        removed_lines = 0
        modified_lines = 0

        matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "insert":
                added_lines += j2 - j1
            elif tag == "delete":
                removed_lines += i2 - i1
            elif tag == "replace":
                removed_lines += i2 - i1
                added_lines += j2 - j1
                modified_lines += max(i2 - i1, j2 - j1)

        return FileDiff(
            path=path,
            action=action,
            old_content=old_content,
            new_content=new_content,
            added_lines=added_lines,
            removed_lines=removed_lines,
            modified_lines=modified_lines,
        )

    @staticmethod
    def apply_patch(original_content: str, patch: str) -> str | None:
        """Apply a unified diff patch to content for a single file."""

        try:
            patch_lines = patch.splitlines()
            if not patch_lines:
                return original_content

            original_lines = original_content.splitlines(keepends=False)
            result: list[str] = []
            source_index = 0
            line_index = 0

            while line_index < len(patch_lines):
                line = patch_lines[line_index]

                if line.startswith("--- ") or line.startswith("+++ "):
                    line_index += 1
                    continue

                if not line.startswith("@@"):
                    line_index += 1
                    continue

                match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
                if not match:
                    return None

                start_old = max(int(match.group(1)) - 1, 0)
                while source_index < start_old and source_index < len(original_lines):
                    result.append(original_lines[source_index])
                    source_index += 1

                line_index += 1
                while line_index < len(patch_lines) and not patch_lines[line_index].startswith("@@"):
                    hunk_line = patch_lines[line_index]

                    if not hunk_line:
                        marker = " "
                        payload = ""
                    else:
                        marker = hunk_line[0]
                        payload = hunk_line[1:]

                    if marker == " ":
                        if source_index >= len(original_lines) or original_lines[source_index] != payload:
                            return None
                        result.append(original_lines[source_index])
                        source_index += 1
                    elif marker == "-":
                        if source_index >= len(original_lines) or original_lines[source_index] != payload:
                            return None
                        source_index += 1
                    elif marker == "+":
                        result.append(payload)
                    elif marker == "\\":
                        pass
                    else:
                        return None

                    line_index += 1

            while source_index < len(original_lines):
                result.append(original_lines[source_index])
                source_index += 1

            return "\n".join(result)
        except Exception:
            return None

    @staticmethod
    def summarize_diff(diff: FileDiff) -> str:
        """Generate a human-readable summary of changes."""

        if diff.action == "create":
            return f"Create {diff.path} ({len(diff.new_content or '')} bytes)"
        if diff.action == "append":
            return f"Append to {diff.path} (+{diff.added_lines} lines)"
        if diff.action == "delete":
            return f"Delete {diff.path}"
        return f"Update {diff.path} (+{diff.added_lines}/-{diff.removed_lines} lines)"
