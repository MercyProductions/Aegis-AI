from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.agent_runtime import MissionAnchor
from aegis_ai.mission_continuity import (
    MISSION_ANCHOR_PREFIX,
    mission_anchor_context,
    mission_anchor_from_history,
    mission_aware_message,
    parse_mission_anchor,
    request_is_broad_mission_followup,
)


class MissionContinuityTests(unittest.TestCase):
    def test_parse_mission_anchor_extracts_core_fields(self) -> None:
        anchor = parse_mission_anchor(
            "\n".join(
                [
                    MISSION_ANCHOR_PREFIX,
                    "- Original user mission: Build the local-first coding workspace",
                    "- Active workspace root: C:/Projects/Auralith",
                    "- Continuity rule: Keep validating after each change",
                ]
            )
        )

        self.assertEqual(
            anchor,
            MissionAnchor(
                original_user_mission="Build the local-first coding workspace",
                active_workspace_root="C:/Projects/Auralith",
                continuity_rule="Keep validating after each change",
            ),
        )

    def test_parse_mission_anchor_requires_mission_or_workspace(self) -> None:
        self.assertIsNone(parse_mission_anchor(f"{MISSION_ANCHOR_PREFIX}\n- Continuity rule: Keep going"))
        self.assertIsNone(parse_mission_anchor("normal system prompt"))

    def test_mission_anchor_from_history_uses_latest_valid_system_anchor(self) -> None:
        history = [
            SimpleNamespace(role="system", content=f"{MISSION_ANCHOR_PREFIX}\n- Active workspace root: C:/old"),
            SimpleNamespace(role="user", content=f"{MISSION_ANCHOR_PREFIX}\n- Active workspace root: C:/ignored"),
            SimpleNamespace(
                role="system",
                content=f"{MISSION_ANCHOR_PREFIX}\n- Original user mission: Finish the repair loop\n- Active workspace root: C:/new",
            ),
        ]

        anchor = mission_anchor_from_history(history)

        self.assertIsNotNone(anchor)
        self.assertEqual(anchor.active_workspace_root, "C:/new")
        self.assertEqual(anchor.original_user_mission, "Finish the repair loop")

    def test_broad_followup_detection_accepts_short_continuation_prompts(self) -> None:
        true_cases = [
            "go ahead",
            "continue with fixing",
            "yes please go ahead",
            "build it",
            "repair the project",
            "use the existing project and continue validation",
            "if there's an error",
            "you didn't build it",
        ]

        for prompt in true_cases:
            with self.subTest(prompt=prompt):
                self.assertTrue(request_is_broad_mission_followup(prompt))

    def test_broad_followup_detection_rejects_specific_or_long_requests(self) -> None:
        self.assertFalse(request_is_broad_mission_followup(""))
        self.assertFalse(request_is_broad_mission_followup("go ahead", has_explicit_workspace=True))
        self.assertFalse(
            request_is_broad_mission_followup(
                "please carefully analyze this entire unrelated request with many extra words that should not be treated as continuation"
            )
        )
        self.assertFalse(request_is_broad_mission_followup("create a new Vite app called LaunchPad"))

    def test_mission_anchor_context_formats_only_present_fields(self) -> None:
        self.assertEqual(mission_anchor_context(None), "")
        self.assertEqual(
            mission_anchor_context(
                MissionAnchor(
                    original_user_mission="Finish validation",
                    active_workspace_root="C:/Auralith",
                )
            ),
            "\n".join(
                [
                    "Mission continuity anchor:",
                    "- Original user mission: Finish validation",
                    "- Active workspace root: C:/Auralith",
                    "- Vague follow-ups must preserve that target path, stack, artifact type, and validation intent.",
                ]
            ),
        )

    def test_mission_aware_message_wraps_only_broad_followups_with_anchor_context(self) -> None:
        anchor = MissionAnchor(
            original_user_mission="Repair the failing build",
            active_workspace_root="C:/Auralith",
            continuity_rule="Validate before summarizing",
        )

        self.assertEqual(mission_aware_message("create a new app", anchor, is_broad_followup=False), "create a new app")
        self.assertEqual(mission_aware_message("go ahead", None, is_broad_followup=True), "go ahead")

        wrapped = mission_aware_message("go ahead", anchor, is_broad_followup=True)

        self.assertTrue(wrapped.startswith("go ahead\n\nMission continuity anchor:"))
        self.assertIn("- Original user mission: Repair the failing build", wrapped)
        self.assertIn("- Active workspace root: C:/Auralith", wrapped)
        self.assertIn("- Continuity rule: Validate before summarizing", wrapped)
        self.assertTrue(wrapped.endswith("- Treat this user text as a continuation of the original mission, not a new project request."))


if __name__ == "__main__":
    unittest.main()
