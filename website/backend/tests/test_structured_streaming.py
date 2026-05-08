from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.structured_streaming import StructuredReplyDeltaExtractor


class StructuredReplyDeltaExtractorTests(unittest.TestCase):
    def test_extracts_only_top_level_reply_text(self) -> None:
        extractor = StructuredReplyDeltaExtractor()
        chunks = [
            '{"reply":"Hello',
            '\\nworld","changes":[{"path":"x.py","content":"SECRET"}]}',
        ]

        output = "".join(extractor.feed(chunk) for chunk in chunks)

        self.assertEqual(output, "Hello\nworld")
        self.assertNotIn("SECRET", output)

    def test_ignores_nested_reply_like_text_inside_changes(self) -> None:
        extractor = StructuredReplyDeltaExtractor()
        payload = (
            '{"changes":[{"path":"x.txt","content":"{\\"reply\\":\\"SECRET\\"}"}],'
            '"reply":"Safe preview"}'
        )

        output = "".join(extractor.feed(payload[index : index + 7]) for index in range(0, len(payload), 7))

        self.assertEqual(output, "Safe preview")
        self.assertNotIn("SECRET", output)

    def test_handles_unicode_escape_sequences(self) -> None:
        extractor = StructuredReplyDeltaExtractor()

        output = extractor.feed('{"reply":"Aegis \\u2713"}')

        self.assertEqual(output, "Aegis \u2713")


if __name__ == "__main__":
    unittest.main()
