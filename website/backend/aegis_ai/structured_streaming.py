from __future__ import annotations

from collections.abc import Iterable


class StructuredReplyDeltaExtractor:
    """Extract safe user-facing text from a streamed structured JSON response.

    The model may stream a full JSON object containing file changes, commands, and
    other internal fields. This extractor only emits decoded string content from a
    top-level allowlisted reply-style field.
    """

    def __init__(self, allowed_keys: Iterable[str] | None = None):
        self.allowed_keys = {
            key.strip().lower()
            for key in (allowed_keys or ("reply", "answer", "response", "message", "content", "text", "output"))
            if key.strip()
        }
        self.depth = 0
        self.in_string = False
        self.streaming_value = False
        self.escape_pending = False
        self.unicode_remaining = 0
        self.unicode_buffer = ""
        self.string_depth = 0
        self.string_buffer: list[str] = []
        self.pending_key: str | None = None
        self.waiting_for_value = False

    def feed(self, chunk: str) -> str:
        emitted: list[str] = []
        for char in chunk:
            if self.in_string:
                self._consume_string_char(char, emitted)
                continue

            if self.waiting_for_value:
                if char.isspace():
                    continue
                if char == '"':
                    self.waiting_for_value = False
                    self._start_string(streaming_value=True)
                    continue
                self.waiting_for_value = False

            if self.pending_key is not None:
                if char.isspace():
                    continue
                key = self.pending_key.lower()
                self.pending_key = None
                if char == ":":
                    self.waiting_for_value = key in self.allowed_keys
                    continue

            if char == '"':
                self._start_string(streaming_value=False)
            elif char in "{[":
                self.depth += 1
            elif char in "}]":
                self.depth = max(0, self.depth - 1)

        return "".join(emitted)

    def _start_string(self, *, streaming_value: bool) -> None:
        self.in_string = True
        self.streaming_value = streaming_value
        self.escape_pending = False
        self.unicode_remaining = 0
        self.unicode_buffer = ""
        self.string_depth = self.depth
        self.string_buffer = []

    def _consume_string_char(self, char: str, emitted: list[str]) -> None:
        if self.unicode_remaining:
            self.unicode_buffer += char
            self.unicode_remaining -= 1
            if self.unicode_remaining == 0:
                decoded = self._decode_unicode_escape(self.unicode_buffer)
                self._append_string_char(decoded, emitted)
                self.unicode_buffer = ""
            return

        if self.escape_pending:
            self.escape_pending = False
            if char == "u":
                self.unicode_remaining = 4
                self.unicode_buffer = ""
                return
            self._append_string_char(self._decode_simple_escape(char), emitted)
            return

        if char == "\\":
            self.escape_pending = True
            return

        if char == '"':
            self._end_string()
            return

        self._append_string_char(char, emitted)

    def _append_string_char(self, char: str, emitted: list[str]) -> None:
        if self.streaming_value:
            emitted.append(char)
        else:
            self.string_buffer.append(char)

    def _end_string(self) -> None:
        if not self.streaming_value and self.string_depth == 1:
            self.pending_key = "".join(self.string_buffer).strip()
        self.in_string = False
        self.streaming_value = False
        self.escape_pending = False
        self.unicode_remaining = 0
        self.unicode_buffer = ""
        self.string_buffer = []

    def _decode_simple_escape(self, char: str) -> str:
        return {
            '"': '"',
            "\\": "\\",
            "/": "/",
            "b": "\b",
            "f": "\f",
            "n": "\n",
            "r": "\r",
            "t": "\t",
        }.get(char, char)

    def _decode_unicode_escape(self, value: str) -> str:
        try:
            return chr(int(value, 16))
        except ValueError:
            return ""
