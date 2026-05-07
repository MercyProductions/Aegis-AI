from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_validation_plan import (
    failed_chain_step,
    split_safe_command_chain,
    validation_step_label,
    validation_step_phase,
)
from aegis_ai.schemas import CommandRun


class ProjectScaffoldValidationPlanTests(unittest.TestCase):
    def test_split_safe_command_chain_splits_only_plain_and_chains(self) -> None:
        self.assertEqual(split_safe_command_chain("npm install && npm test"), ["npm install", "npm test"])
        self.assertEqual(
            split_safe_command_chain('"C:\\Program Files\\CMake\\bin\\cmake.exe" -S . -B build && cmake --build build'),
            ['"C:\\Program Files\\CMake\\bin\\cmake.exe" -S . -B build', "cmake --build build"],
        )
        self.assertEqual(split_safe_command_chain("npm test | tee test.log"), ["npm test | tee test.log"])
        self.assertEqual(split_safe_command_chain("npm test && "), ["npm test &&"])
        self.assertEqual(split_safe_command_chain(""), [])

    def test_validation_step_phase_classifies_core_validation_work(self) -> None:
        cases = {
            "cmake -S . -B build": "configure",
            "cmake --build build": "build",
            "npm run build": "build",
            "pytest": "test",
            "npx tsc --noEmit": "typecheck",
            "ruff check .": "lint",
            "prisma migrate diff": "database",
            "python scripts/verify.py": "validation",
        }
        for command, phase in cases.items():
            with self.subTest(command=command):
                self.assertEqual(validation_step_phase(command), phase)

    def test_validation_step_label_names_common_steps(self) -> None:
        self.assertEqual(validation_step_label("cmake -S . -B build", index=1, total=2), "Configure CMake build directory")
        self.assertEqual(validation_step_label("cmake --build build", index=2, total=2), "Build CMake project")
        self.assertEqual(validation_step_label("ctest --test-dir build", index=3, total=3), "Run CTest suite")
        self.assertEqual(validation_step_label("npm run build", index=1, total=1), "Build web project")
        self.assertEqual(validation_step_label("pytest", index=1, total=1), "Run test suite")
        self.assertEqual(validation_step_label("python verify.py", index=2, total=3), "Validation step 2")
        self.assertEqual(validation_step_label("python verify.py", index=1, total=1), "Run validation command")

    def test_failed_chain_step_prefers_explicit_step_then_reason_match(self) -> None:
        self.assertEqual(failed_chain_step(command_run(failed_step="3", reason="step 2 failed")), "3")
        self.assertEqual(failed_chain_step(command_run(reason="Validation failed at step 2.")), "2")
        self.assertEqual(failed_chain_step(command_run(reason="Validation failed.")), "")


def command_run(*, failed_step: str = "", reason: str = "") -> CommandRun:
    return CommandRun(
        command="npm test",
        cwd="workspace",
        allowed=True,
        exit_code=1,
        stdout="",
        stderr="",
        timed_out=False,
        reason=reason,
        category="test",
        summary=reason,
        steps=[],
        failed_step=failed_step,
        failed_step_command="",
        diagnostics=[],
    )


if __name__ == "__main__":
    unittest.main()
