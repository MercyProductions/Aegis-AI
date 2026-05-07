import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.storage_helpers import (
    fingerprint,
    memory_match_score,
    merge_json_list,
    parse_json_list,
    parse_json_payload,
    task_title_from_message,
    tokenize,
)


class StorageHelperTests(unittest.TestCase):
    def test_parse_json_list_keeps_truthy_stringified_items(self) -> None:
        self.assertEqual(parse_json_list(json.dumps(["alpha", "", "  ", 42, False])), ["alpha", "42", "False"])
        self.assertEqual(parse_json_list('{"not": "a list"}'), [])
        self.assertEqual(parse_json_list("not json"), [])
        self.assertEqual(parse_json_list(None), [])

    def test_merge_json_list_preserves_existing_order_and_dedupes_cleaned_additions(self) -> None:
        merged = merge_json_list(json.dumps(["src/app.py", "README.md"]), [" README.md ", "tests/test_app.py", ""])
        self.assertEqual(merged, ["src/app.py", "README.md", "tests/test_app.py"])

    def test_task_title_from_message_compacts_and_truncates_or_falls_back_to_mode(self) -> None:
        self.assertEqual(task_title_from_message("  repair   validation\nloop  ", "build"), "repair validation loop")
        self.assertEqual(task_title_from_message("", "review"), "Review task")
        self.assertEqual(len(task_title_from_message("x" * 120, "build")), 80)

    def test_parse_json_payload_returns_dict_only(self) -> None:
        self.assertEqual(parse_json_payload('{"status": "ok"}'), {"status": "ok"})
        self.assertEqual(parse_json_payload("[1, 2]"), {})
        self.assertEqual(parse_json_payload("not json"), {})

    def test_tokenize_normalizes_alphanumeric_tokens_with_minimum_length(self) -> None:
        self.assertEqual(tokenize("Fix API-route, C++ and UI"), {"fix", "apiroute", "and"})

    def test_memory_match_score_uses_query_token_overlap_ratio(self) -> None:
        self.assertEqual(memory_match_score("", "repair validation"), 0.0)
        self.assertEqual(memory_match_score("missing phrase", "repair validation"), 0.0)
        self.assertEqual(memory_match_score("repair validation route", "validation repair notes"), 2 / 3)

    def test_fingerprint_normalizes_case_whitespace_and_ignores_empty_parts(self) -> None:
        expected = hashlib.sha1("alpha\nbeta".encode("utf-8")).hexdigest()
        self.assertEqual(fingerprint(" Alpha ", "", "BETA"), expected)


if __name__ == "__main__":
    unittest.main()
