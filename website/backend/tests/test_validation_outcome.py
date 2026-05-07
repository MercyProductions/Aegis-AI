from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.schemas import CommandRun
from aegis_ai.validation_outcome import (
    categorize_validation_failure,
    error_signature,
    repair_outcome,
    repair_strategy_hint,
    repair_summary,
    validation_ok,
    validation_score,
)


class ValidationOutcomeTests(unittest.TestCase):
    def test_validation_ok_requires_allowed_non_timeout_zero_exit(self) -> None:
        self.assertTrue(validation_ok(command_run(exit_code=0)))
        self.assertFalse(validation_ok(command_run(exit_code=0, allowed=False)))
        self.assertFalse(validation_ok(command_run(exit_code=0, timed_out=True)))
        self.assertFalse(validation_ok(command_run(exit_code=1)))

    def test_error_signature_uses_first_relevant_output_lines(self) -> None:
        validation = command_run(stderr="\n first error \n\n second error \n" + "\n".join(f"line {index}" for index in range(20)))

        signature = error_signature(validation)

        self.assertTrue(signature.startswith("first error\nsecond error"))
        self.assertLessEqual(len(signature), 1200)

    def test_categorizes_validation_failures_by_control_state_and_output(self) -> None:
        cases = [
            (command_run(category="build", stderr="whatever"), "build"),
            (command_run(timed_out=True), "timeout"),
            (command_run(allowed=False), "permission"),
            (command_run(stderr="SyntaxError: unexpected token"), "syntax"),
            (command_run(stderr="Cannot find module './missing'"), "dependency"),
            (command_run(stderr="typescript tsc type-check failed"), "typecheck"),
            (command_run(stderr="pytest failed expected 200"), "test"),
            (command_run(command="vite build", stderr="compilation error"), "build"),
            (command_run(stderr="Traceback RuntimeError exception"), "runtime"),
            (command_run(stderr="unclassified output"), "unknown"),
        ]

        for validation, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(categorize_validation_failure(validation), expected)

    def test_validation_score_orders_failure_risk(self) -> None:
        self.assertEqual(validation_score(command_run(exit_code=0)), 0)
        self.assertEqual(validation_score(command_run(allowed=False)), 900)
        self.assertEqual(validation_score(command_run(timed_out=True)), 800)
        self.assertGreater(
            validation_score(command_run(stderr="SyntaxError")),
            validation_score(command_run(stderr="pytest failed assertion")),
        )

    def test_repair_outcome_classifies_fixed_unchanged_improved_and_worse(self) -> None:
        before = command_run(stderr="SyntaxError: unexpected token")

        self.assertEqual(repair_outcome(before, None), "worse")
        self.assertEqual(repair_outcome(before, command_run(exit_code=0)), "fixed")
        self.assertEqual(repair_outcome(before, command_run(stderr="SyntaxError: unexpected token")), "unchanged")
        self.assertEqual(repair_outcome(before, command_run(stderr="pytest failed assertion")), "improved")
        self.assertEqual(repair_outcome(command_run(stderr="pytest failed assertion"), before), "worse")
        self.assertEqual(
            repair_outcome(
                command_run(stderr="Unknown failure A"),
                command_run(stderr="Unknown failure B"),
            ),
            "sideways",
        )

    def test_repair_summary_explains_result_without_agent_runtime_dependency(self) -> None:
        before = command_run(stderr="SyntaxError: unexpected token")

        self.assertEqual(
            repair_summary(before, None, []),
            "Repair command could not be validated after applying the patch.",
        )
        self.assertEqual(
            repair_summary(before, command_run(exit_code=0), []),
            "Repair patch produced a passing validation run.",
        )
        self.assertEqual(
            repair_summary(before, command_run(stderr="pytest failed assertion"), []),
            "Repair moved validation from syntax failure to test failure.",
        )
        self.assertEqual(
            repair_summary(
                command_run(stderr="pytest failed first assertion"),
                command_run(stderr="pytest failed second assertion"),
                ["Tighten the failing assertion path."],
            ),
            "Tighten the failing assertion path.",
        )

    def test_repair_strategy_hint_matches_validation_category(self) -> None:
        self.assertIn("imports", repair_strategy_hint(command_run(stderr="Cannot find module './missing'")))
        self.assertIn("assertion", repair_strategy_hint(command_run(stderr="pytest failed expected 200")))
        self.assertIn("smallest fix", repair_strategy_hint(command_run(stderr="unclassified")))


def command_run(
    *,
    command: str = "npm run validate",
    allowed: bool = True,
    exit_code: int | None = 1,
    stdout: str = "",
    stderr: str = "",
    timed_out: bool = False,
    reason: str = "",
    category: str = "",
) -> CommandRun:
    return CommandRun(
        command=command,
        cwd="workspace",
        allowed=allowed,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        reason=reason,
        category=category,
        summary="",
    )


if __name__ == "__main__":
    unittest.main()
