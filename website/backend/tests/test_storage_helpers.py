import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.storage_helpers import (
    average,
    context_budget_utilization,
    fingerprint,
    float_value,
    int_value,
    memory_match_score,
    merge_json_list,
    optional_bool,
    optional_int,
    optional_positive_int,
    parse_json_list,
    parse_json_payload,
    rate,
    reliability_score,
    task_title_from_message,
    token_metadata_int,
    token_relative_error,
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

    def test_numeric_helpers_preserve_storage_defaults(self) -> None:
        self.assertEqual(int_value("7"), 7)
        self.assertEqual(int_value("", default=3), 3)
        self.assertIsNone(optional_int(""))
        self.assertEqual(optional_int("8"), 8)
        self.assertEqual(optional_positive_int("0"), 0)
        self.assertIsNone(optional_positive_int("-1"))
        self.assertEqual(float_value("2.5"), 2.5)
        self.assertIsNone(float_value("bad", None))
        self.assertEqual(average(["1", 2, "bad", None]), 1.5)
        self.assertIsNone(average(["bad", None]))
        self.assertEqual(rate(1, 3), 0.3333)
        self.assertEqual(rate(5, 0), 0.0)

    def test_optional_bool_matches_storage_metadata_coercion(self) -> None:
        self.assertIs(optional_bool(True), True)
        self.assertIs(optional_bool(0), False)
        self.assertIs(optional_bool("YES"), True)
        self.assertIs(optional_bool("n"), False)
        self.assertIsNone(optional_bool("maybe"))

    def test_reliability_score_penalizes_fallbacks_context_pressure_and_feedback(self) -> None:
        self.assertEqual(reliability_score(0.8, 0.25, 0.82, 0.5, 0.25), 71.0)
        self.assertEqual(reliability_score(2.0, 0.0, None), 100.0)
        self.assertEqual(reliability_score(0.0, 2.0, 1.0, 0.0, 1.0), 0.0)

    def test_token_metadata_helpers_keep_first_non_negative_value_and_relative_error(self) -> None:
        metadata = {"reported_input": "-1", "actual_input": "120", "fallback": "150"}
        self.assertEqual(token_metadata_int(metadata, ("reported_input", "actual_input", "fallback")), 120)
        self.assertIsNone(token_metadata_int({"bad": "nope"}, ("bad",)))
        self.assertEqual(token_relative_error(90, 100), 0.1)
        self.assertEqual(token_relative_error(3, 0), 3.0)
        self.assertIsNone(token_relative_error(None, 100))

    def test_context_budget_utilization_uses_direct_values_then_payload_fallback_and_clamps(self) -> None:
        payload = SimpleNamespace(max_context_tokens=200, estimated_context_tokens=40, reserve_response_tokens=10)
        entry = SimpleNamespace(
            max_context_tokens=100,
            estimated_context_tokens=70,
            reserve_response_tokens=20,
            payload=payload,
        )
        self.assertEqual(context_budget_utilization(entry), 0.9)

        fallback_entry = SimpleNamespace(
            max_context_tokens=0,
            estimated_context_tokens=0,
            reserve_response_tokens=0,
            payload=payload,
        )
        self.assertEqual(context_budget_utilization(fallback_entry), 0.25)

        saturated_entry = SimpleNamespace(
            max_context_tokens=100,
            estimated_context_tokens=120,
            reserve_response_tokens=30,
            payload=payload,
        )
        self.assertEqual(context_budget_utilization(saturated_entry), 1.0)

        invalid_entry = SimpleNamespace(
            max_context_tokens=0,
            estimated_context_tokens=120,
            reserve_response_tokens=30,
            payload=SimpleNamespace(max_context_tokens=0, estimated_context_tokens=0, reserve_response_tokens=0),
        )
        self.assertIsNone(context_budget_utilization(invalid_entry))

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
