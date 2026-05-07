from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.chat_streaming import (
    chat_stream_contract_response,
    preview_delta_counts_as_streamed,
    preview_delta_payload,
    response_with_reconciliation,
    sse_event,
    structured_stream_intro,
    structured_stream_reconciliation,
    structured_stream_summary,
)
from aegis_ai.schemas import AgentRequest, AgentResponse, CommandRun, FileChange, ModelAttemptInfo


def response(**updates) -> AgentResponse:
    values = {
        "task_id": "stream-test",
        "reply": "Prepared the final answer.",
        "assistant_name": "Auralith Prime",
        "mode": "build",
        "engine": "test",
        "workspace_root": "",
    }
    values.update(updates)
    return AgentResponse(**values)


class ChatStreamingHelperTests(unittest.TestCase):
    def test_sse_event_serializes_payload_as_single_event_frame(self) -> None:
        event = sse_event("status", {"type": "status", "message": "ready"})

        self.assertTrue(event.startswith("event: status\n"))
        self.assertTrue(event.endswith("\n\n"))
        payload = json.loads(event.split("data: ", 1)[1])
        self.assertEqual(payload["message"], "ready")

    def test_structured_stream_intro_reflects_enabled_workflow_guards(self) -> None:
        intro = structured_stream_intro(
            AgentRequest(message="build the app", mode="build", apply_changes=True, run_validation=True)
        )

        self.assertIn("structured build task", intro)
        self.assertIn("Auto Apply is enabled", intro)
        self.assertIn("Validation is enabled", intro)
        self.assertIn("provider JSON internal", intro)

    def test_structured_stream_summary_reports_workflow_outcome(self) -> None:
        summary = structured_stream_summary(
            response(
                changes=[FileChange(action="update", path="src/app.ts", content="")],
                applied=["src/app.ts"],
                validation=CommandRun(command="npm test", cwd="", allowed=True, exit_code=1),
                warnings=["Validation failed."],
            )
        )

        self.assertIn("prepared 1 file change(s)", summary)
        self.assertIn("applied 1 file change(s)", summary)
        self.assertIn("validation needs attention", summary)
        self.assertIn("1 warning(s)", summary)

    def test_structured_stream_summary_has_empty_state_text(self) -> None:
        self.assertIn("prepared a structured response", structured_stream_summary(response()))

    def test_reconciliation_is_empty_without_streamed_preview(self) -> None:
        self.assertEqual(structured_stream_reconciliation(response(), preview_was_streamed=False), "")

    def test_reconciliation_explains_fallback_final_answer(self) -> None:
        notice = structured_stream_reconciliation(
            response(warnings=["The model returned no usable answer, so Aegis used the deterministic fallback."]),
            preview_was_streamed=True,
        )

        self.assertIn("safer final response", notice)
        self.assertIn("did not produce usable workspace changes", notice)

    def test_reconciliation_explains_later_successful_provider(self) -> None:
        notice = structured_stream_reconciliation(
            response(
                model_attempts=[
                    ModelAttemptInfo(attempt=1, role="code", status="failed", provider_label="Provider A"),
                    ModelAttemptInfo(attempt=2, role="code", status="succeeded", provider_label="Provider B"),
                ]
            ),
            preview_was_streamed=True,
        )

        self.assertIn("later successful provider response", notice)

    def test_response_with_reconciliation_adds_note_and_warning_once(self) -> None:
        notice = "The live preview was reconciled with the final response."
        updated = response_with_reconciliation(response(), notice)
        updated_again = response_with_reconciliation(updated, notice)

        self.assertIn(f"Note: {notice}", updated.reply)
        self.assertEqual(updated.warnings.count(notice), 1)
        self.assertEqual(updated_again.reply.count(notice), 1)
        self.assertEqual(updated_again.warnings.count(notice), 1)

    def test_preview_delta_payload_normalizes_string_events(self) -> None:
        payload = preview_delta_payload("hello", stream_mode="structured-delta-final")

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["type"], "delta")
        self.assertEqual(payload["delta"], "hello")
        self.assertEqual(payload["source"], "structured_reply_preview")
        self.assertTrue(preview_delta_counts_as_streamed(payload))

    def test_preview_delta_payload_skips_empty_append_and_preserves_reset(self) -> None:
        self.assertIsNone(preview_delta_payload({"delta": ""}, stream_mode="structured-delta-final"))

        payload = preview_delta_payload(
            {"preview_action": "reset", "message": "Attempt retired.", "provider_label": "Provider A"},
            stream_mode="structured-delta-final",
        )

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["preview_action"], "reset")
        self.assertEqual(payload["message"], "Attempt retired.")
        self.assertFalse(preview_delta_counts_as_streamed(payload))

    def test_chat_stream_contract_response_documents_stable_stream_events(self) -> None:
        contract = chat_stream_contract_response()

        self.assertEqual(contract.schema_version, "aegis.chat.stream.v1")
        self.assertEqual(contract.event_order, ["meta", "status", "delta", "final", "error", "done"])
        self.assertTrue(any(event.event == "final" and "matching /api/chat" in event.description for event in contract.events))
        self.assertTrue(any("ReadableStream" in recommendation for recommendation in contract.recommendations))


if __name__ == "__main__":
    unittest.main()
