from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.providers.base import ProviderConfig, ProviderInventory, ProviderMessage, ProviderStatus
from aegis_ai.providers.registry import (
    BaseHttpProviderAdapter,
    OllamaProviderAdapter,
    OpenAICompatibleProviderAdapter,
)
from aegis_ai.schemas import AgentRequest, AgentResponse, ModelAttemptInfo
from aegis_ai.settings import Settings


class FakeStreamingAdapter(BaseHttpProviderAdapter):
    async def status(self) -> ProviderStatus:
        return ProviderStatus(True, "ready")

    async def inventory(self) -> ProviderInventory:
        return ProviderInventory(
            active_model=self.model,
            active_api=self.api,
            active_endpoint=self.endpoint,
            message="ready",
            models=[],
        )

    async def complete(self, messages: list[ProviderMessage]) -> str:
        self._record_token_usage(input_tokens=10, output_tokens=3, source="fake:usage")
        return "hello streamed world"


def collect_events(adapter: BaseHttpProviderAdapter) -> list[str]:
    async def collect() -> list[str]:
        return [event.type async for event in adapter.stream_text([{"role": "user", "content": "hello"}])]

    return asyncio.run(collect())


def event_payload(event: str) -> dict:
    return json.loads(event.split("data: ", 1)[1])


class StreamingContractTests(unittest.TestCase):
    def settings(self) -> Settings:
        return Settings(
            _env_file=None,
            aegis_model_api="ollama",
            aegis_model_endpoint="http://127.0.0.1:11434",
            aegis_model_name="test-model",
            aegis_database_path="data/test.sqlite3",
        )

    def config(self, api: str = "ollama") -> ProviderConfig:
        return ProviderConfig(
            provider_id=f"{api}:test",
            label="Test Provider",
            api=api,
            endpoint="http://127.0.0.1:11434",
            model="test-model",
            local=True,
            configured=True,
            capabilities=["chat", "streaming"],
        )

    def test_base_adapter_stream_text_emits_lifecycle_events(self) -> None:
        adapter = FakeStreamingAdapter(self.settings(), self.config())

        self.assertEqual(collect_events(adapter), ["start", "delta", "metadata", "done"])
        self.assertEqual(adapter.completion_metadata()["reported_input_tokens"], 10)

    def test_openai_stream_delta_parser_handles_sse_chunks(self) -> None:
        adapter = OpenAICompatibleProviderAdapter(self.settings(), self.config("openai-compatible"))

        self.assertEqual(
            adapter._openai_stream_delta('data: {"choices":[{"delta":{"content":"hi"}}]}'),
            "hi",
        )
        self.assertEqual(adapter._openai_stream_delta("data: [DONE]"), "[DONE]")

    def test_ollama_stream_payload_parser_handles_json_lines(self) -> None:
        adapter = OllamaProviderAdapter(self.settings(), self.config())

        payload = adapter._ollama_stream_payload('{"message":{"content":"hi"},"done":false}')

        self.assertIsNotNone(payload)
        self.assertEqual(payload["message"]["content"], "hi")

    def test_chat_stream_contract_documents_final_response_event(self) -> None:
        contract = asyncio.run(main.chat_stream_contract())

        self.assertEqual(contract.schema_version, "aegis.chat.stream.v1")
        self.assertIn("final", contract.event_order)
        self.assertTrue(any(event.event == "delta" for event in contract.events))

    def test_chat_stream_events_emit_direct_chat_deltas_when_available(self) -> None:
        class FakeDirectStreamAgent:
            async def can_stream_direct_chat(self, request: AgentRequest) -> bool:
                return True

            async def stream_direct_chat_events(self, request: AgentRequest):
                response = AgentResponse(
                    task_id="stream-test",
                    reply="hello from stream",
                    assistant_name="Auralith Prime",
                    mode="chat",
                    engine="fake-stream",
                    workspace_root="",
                )
                yield "status", {"type": "status", "stage": "model_stream", "task_id": response.task_id}
                yield "delta", {"type": "delta", "delta": "hello ", "task_id": response.task_id}
                yield "delta", {"type": "delta", "delta": "from stream", "task_id": response.task_id}
                yield "final", {
                    "type": "final",
                    "task_id": response.task_id,
                    "response": response.model_dump(mode="json"),
                }

        original_agent = main.agent
        main.agent = FakeDirectStreamAgent()  # type: ignore[assignment]
        try:
            async def collect() -> list[str]:
                return [event async for event in main._chat_stream_events(AgentRequest(message="hello", mode="chat"))]

            events = asyncio.run(collect())
        finally:
            main.agent = original_agent

        self.assertTrue(any("event: meta" in event and "chat-delta-final" in event for event in events))
        self.assertEqual(sum(1 for event in events if event.startswith("event: delta")), 2)
        self.assertTrue(any("event: final" in event and "hello from stream" in event for event in events))

    def test_chat_stream_meta_uses_agent_effective_workspace_root(self) -> None:
        selected_workspace = "C:\\Aegis\\Selected Workspace"
        prompt_workspace = "C:\\Aegis\\Prompt Workspace"

        class FakePathAwareStructuredAgent:
            def stream_meta_workspace_root(self, request: AgentRequest) -> str:
                self.seen_request = request
                return prompt_workspace

            async def can_stream_direct_chat(self, request: AgentRequest) -> bool:
                return False

            async def run(self, request: AgentRequest, stream_delta_callback=None) -> AgentResponse:
                return AgentResponse(
                    task_id="prompt-workspace-stream-test",
                    reply="Prepared files in the prompt-selected workspace.",
                    assistant_name="Auralith Prime",
                    mode="build",
                    engine="fake-structured",
                    workspace_root=prompt_workspace,
                )

        fake_agent = FakePathAwareStructuredAgent()
        original_agent = main.agent
        main.agent = fake_agent  # type: ignore[assignment]
        try:
            async def collect() -> list[str]:
                return [
                    event
                    async for event in main._chat_stream_events(
                        AgentRequest(
                            message=f"at this path {prompt_workspace} create a C++ console app and build it",
                            mode="build",
                            workspace_root=selected_workspace,
                        )
                    )
                ]

            events = asyncio.run(collect())
        finally:
            main.agent = original_agent

        meta_event = next(event for event in events if event.startswith("event: meta"))
        meta_payload = event_payload(meta_event)
        self.assertEqual(meta_payload["workspace_root"], prompt_workspace)
        self.assertNotEqual(meta_payload["workspace_root"], selected_workspace)

    def test_chat_stream_events_emit_safe_structured_deltas_without_raw_json(self) -> None:
        class FakeStructuredAgent:
            async def can_stream_direct_chat(self, request: AgentRequest) -> bool:
                return False

            async def run(self, request: AgentRequest, stream_delta_callback=None) -> AgentResponse:
                if stream_delta_callback is not None:
                    stream_delta_callback("Prepared preview text.")
                return AgentResponse(
                    task_id="structured-test",
                    reply="Prepared the structured response.",
                    assistant_name="Auralith Prime",
                    mode="build",
                    engine="fake-structured",
                    workspace_root="",
                )

        original_agent = main.agent
        main.agent = FakeStructuredAgent()  # type: ignore[assignment]
        try:
            async def collect() -> list[str]:
                return [
                    event
                    async for event in main._chat_stream_events(
                        AgentRequest(message="create a tiny app", mode="build")
                    )
                ]

            events = asyncio.run(collect())
        finally:
            main.agent = original_agent

        deltas = [event for event in events if event.startswith("event: delta")]

        self.assertTrue(any("event: meta" in event and "structured-delta-final" in event for event in events))
        self.assertGreaterEqual(len(deltas), 2)
        self.assertTrue(any("provider JSON internal" in event for event in deltas))
        self.assertTrue(any("Prepared preview text." in event for event in deltas))
        self.assertFalse(any('"changes":' in event for event in deltas))
        self.assertTrue(any("event: final" in event and "Prepared the structured response." in event for event in events))

    def test_chat_stream_events_reconcile_preview_when_fallback_replaces_draft(self) -> None:
        class FakeFallbackStructuredAgent:
            async def can_stream_direct_chat(self, request: AgentRequest) -> bool:
                return False

            async def run(self, request: AgentRequest, stream_delta_callback=None) -> AgentResponse:
                if stream_delta_callback is not None:
                    stream_delta_callback("Model draft preview.")
                return AgentResponse(
                    task_id="fallback-structured-test",
                    reply="Prepared safer workspace files.",
                    warnings=[
                        "The model returned no file changes for a create/build request, so Aegis used the deterministic starter generator."
                    ],
                    assistant_name="Auralith Prime",
                    mode="build",
                    engine="fake-structured",
                    workspace_root="",
                )

        original_agent = main.agent
        main.agent = FakeFallbackStructuredAgent()  # type: ignore[assignment]
        try:
            async def collect() -> list[str]:
                return [
                    event
                    async for event in main._chat_stream_events(
                        AgentRequest(message="create a tiny app", mode="build")
                    )
                ]

            events = asyncio.run(collect())
        finally:
            main.agent = original_agent

        self.assertTrue(any("structured_preview_reconciliation" in event for event in events))
        self.assertTrue(any("did not produce usable workspace changes" in event for event in events))
        self.assertTrue(any("event: final" in event and "Note:" in event for event in events))

    def test_chat_stream_events_reconcile_preview_when_later_provider_wins(self) -> None:
        class FakeLaterProviderStructuredAgent:
            async def can_stream_direct_chat(self, request: AgentRequest) -> bool:
                return False

            async def run(self, request: AgentRequest, stream_delta_callback=None) -> AgentResponse:
                if stream_delta_callback is not None:
                    stream_delta_callback("Earlier provider preview.")
                return AgentResponse(
                    task_id="later-provider-test",
                    reply="Prepared the later provider response.",
                    model_attempts=[
                        ModelAttemptInfo(attempt=1, role="code", status="failed", provider_label="Provider A"),
                        ModelAttemptInfo(attempt=2, role="code", status="succeeded", provider_label="Provider B"),
                    ],
                    assistant_name="Auralith Prime",
                    mode="build",
                    engine="fake-structured",
                    workspace_root="",
                )

        original_agent = main.agent
        main.agent = FakeLaterProviderStructuredAgent()  # type: ignore[assignment]
        try:
            async def collect() -> list[str]:
                return [
                    event
                    async for event in main._chat_stream_events(
                        AgentRequest(message="create a tiny app", mode="build")
                    )
                ]

            events = asyncio.run(collect())
        finally:
            main.agent = original_agent

        self.assertTrue(any("structured_preview_reconciliation" in event for event in events))
        self.assertTrue(any("later successful provider response" in event for event in events))
        self.assertTrue(any("event: final" in event and "Note:" in event for event in events))

    def test_chat_stream_events_emit_attempt_reset_for_failed_preview(self) -> None:
        class FakeAttemptResetStructuredAgent:
            async def can_stream_direct_chat(self, request: AgentRequest) -> bool:
                return False

            async def run(self, request: AgentRequest, stream_delta_callback=None) -> AgentResponse:
                if stream_delta_callback is not None:
                    stream_delta_callback(
                        {
                            "preview_action": "append",
                            "preview_attempt": 1,
                            "provider_label": "Provider A",
                            "model": "model-a",
                            "delta": "Old preview.",
                        }
                    )
                    stream_delta_callback(
                        {
                            "preview_action": "reset",
                            "preview_attempt": 1,
                            "provider_label": "Provider A",
                            "model": "model-a",
                            "delta": "",
                            "message": "Provider A preview was retired because the attempt failed.",
                        }
                    )
                    stream_delta_callback(
                        {
                            "preview_action": "append",
                            "preview_attempt": 2,
                            "provider_label": "Provider B",
                            "model": "model-b",
                            "delta": "New preview.",
                        }
                    )
                return AgentResponse(
                    task_id="attempt-reset-test",
                    reply="Prepared the final structured response.",
                    assistant_name="Auralith Prime",
                    mode="build",
                    engine="fake-structured",
                    workspace_root="",
                )

        original_agent = main.agent
        main.agent = FakeAttemptResetStructuredAgent()  # type: ignore[assignment]
        try:
            async def collect() -> list[str]:
                return [
                    event
                    async for event in main._chat_stream_events(
                        AgentRequest(message="create a tiny app", mode="build")
                    )
                ]

            events = asyncio.run(collect())
        finally:
            main.agent = original_agent

        self.assertTrue(any('"preview_action": "reset"' in event for event in events))
        self.assertTrue(any('"preview_attempt": 1' in event and "Provider A" in event for event in events))
        self.assertTrue(any('"preview_attempt": 2' in event and "New preview." in event for event in events))


if __name__ == "__main__":
    unittest.main()
