from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_validation_plan import (
    failed_chain_step,
    split_safe_command_chain,
    validation_plan_payload,
    validation_step_label,
    validation_step_phase,
)
from aegis_ai.schemas import CommandRun, ProjectScaffoldPreset


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
            "bun run build": "build",
            "bun test": "test",
            "bun run test": "test",
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
        self.assertEqual(validation_step_label("bun run build", index=1, total=1), "Build web project")
        self.assertEqual(validation_step_label("bun test", index=1, total=1), "Run test suite")
        self.assertEqual(validation_step_label("pytest", index=1, total=1), "Run test suite")
        self.assertEqual(validation_step_label("python verify.py", index=2, total=3), "Validation step 2")
        self.assertEqual(validation_step_label("python verify.py", index=1, total=1), "Run validation command")

    def test_failed_chain_step_prefers_explicit_step_then_reason_match(self) -> None:
        self.assertEqual(failed_chain_step(command_run(failed_step="3", reason="step 2 failed")), "3")
        self.assertEqual(failed_chain_step(command_run(reason="Validation failed at step 2.")), "2")
        self.assertEqual(failed_chain_step(command_run(reason="Validation failed.")), "")

    def test_validation_plan_payload_records_install_and_split_validation_steps(self) -> None:
        payload = validation_plan_payload(
            scaffold_preset("cpp-cmake-cli", "CMake CLI"),
            "native-tool",
            install_command="python -m pip install -e .",
            validation_command="cmake -S . -B build && cmake --build build",
            validation=None,
            build_log_path="",
        )

        self.assertEqual(payload["schema"], "aegis.validation_plan.v1")
        self.assertEqual(payload["last_run"]["status"], "not_run")
        self.assertEqual([step["phase"] for step in payload["steps"]], ["install", "configure", "build"])
        self.assertEqual(payload["steps"][1]["chain_total"], 2)
        self.assertEqual(payload["steps"][2]["source_command"], "cmake -S . -B build && cmake --build build")

    def test_validation_plan_payload_records_failed_validation_state(self) -> None:
        run = command_run(
            reason="Validation failed at step 2.",
            diagnostics=[{"path": "src/app.ts", "line": 4, "message": "boom"}],
        )
        run.failed_step_command = "npm test"
        payload = validation_plan_payload(
            scaffold_preset("vite-react-ts", "Vite React"),
            "aegis-app",
            install_command="",
            validation_command="npm run build && npm test",
            validation=run,
            build_log_path=".aegis/build_logs/failing.md",
        )

        self.assertEqual(payload["last_run"]["status"], "failed")
        self.assertEqual(payload["last_run"]["failed_step"], "2")
        self.assertEqual(payload["last_run"]["failed_step_command"], "npm test")
        self.assertEqual(payload["last_run"]["diagnostics"][0]["path"], "src/app.ts")
        self.assertEqual(payload["last_run"]["build_log_path"], ".aegis/build_logs/failing.md")


def command_run(
    *,
    failed_step: str = "",
    reason: str = "",
    diagnostics: list[dict[str, object]] | None = None,
) -> CommandRun:
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
        diagnostics=diagnostics or [],
    )


def scaffold_preset(preset_id: str, label: str) -> ProjectScaffoldPreset:
    return ProjectScaffoldPreset(
        id=preset_id,
        label=label,
        framework="test",
        language="test",
    )


if __name__ == "__main__":
    unittest.main()
