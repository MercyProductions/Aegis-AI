from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.agent_native_validation import (
    cmake_build_py_content,
    harden_native_cpp_draft,
    prefer_python_build_command,
)
from aegis_ai.agent_runtime import AgentDraft
from aegis_ai.schemas import FileChange


class AgentNativeValidationTests(unittest.TestCase):
    def test_harden_native_cpp_draft_adds_portable_build_validator(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = Path(tempdir)
            draft = AgentDraft(
                reply="Built native app.",
                changes=[
                    FileChange(action="create", path="CMakeLists.txt", content="add_executable(app src/main.cpp)\n"),
                    FileChange(action="create", path="src/main.cpp", content="int main(){return 0;}\n"),
                    FileChange(
                        action="create",
                        path="build.sh",
                        summary="Validate CMake build.",
                        content="cmake -S . -B build && cmake --build build\n",
                    ),
                ],
                proposed_commands=[
                    {"command": "cmake -S . -B build && cmake --build build", "reason": "Validate native build."},
                    {"command": "bash build.sh", "reason": "Run shell validator."},
                ],
            )

            hardened = harden_native_cpp_draft(
                draft,
                request_mentions_cpp_project=False,
                workspace_root=workspace,
                change_paths={"cmakelists.txt", "src/main.cpp", "build.sh"},
            )

        paths = [change.path for change in hardened.changes]
        self.assertIn("build.py", paths)
        self.assertNotIn("build.sh", paths)
        self.assertEqual([command["command"] for command in hardened.proposed_commands], ["python build.py"])
        build_py = next(change.content for change in hardened.changes if change.path == "build.py")
        self.assertIn("smoke_run_executable", build_py or "")
        self.assertTrue(any("Aegis added build.py" in warning for warning in hardened.warnings))
        self.assertTrue(any("Removed shell-only validation file(s): build.sh" in warning for warning in hardened.warnings))

    def test_existing_build_py_is_reused_and_shell_validator_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = Path(tempdir)
            (workspace / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.20)\nadd_executable(app src/main.cpp)\n",
                encoding="utf-8",
            )
            (workspace / "build.py").write_text("print('existing validator')\n", encoding="utf-8")
            draft = AgentDraft(
                reply="Updated native app.",
                changes=[
                    FileChange(action="update", path="src/main.cpp", content="int main(){return 0;}\n"),
                    FileChange(
                        action="create",
                        path="validate.sh",
                        summary="Validate CMake project.",
                        content="cmake -S . -B build && cmake --build build\n",
                    ),
                ],
                proposed_commands=[{"command": "sh validate.sh", "reason": ""}],
            )

            hardened = harden_native_cpp_draft(
                draft,
                request_mentions_cpp_project=True,
                workspace_root=workspace,
                change_paths={"src/main.cpp", "validate.sh"},
            )

        self.assertEqual([change.path for change in hardened.changes], ["src/main.cpp"])
        self.assertEqual([command["command"] for command in hardened.proposed_commands], ["python build.py"])
        self.assertTrue(any("kept `python build.py`" in warning for warning in hardened.warnings))

    def test_prefer_python_build_command_appends_default_when_needed(self) -> None:
        draft = AgentDraft(reply="Built.", proposed_commands=[{"command": "ctest --test-dir build", "reason": "Tests."}])

        prefer_python_build_command(draft)

        self.assertEqual(
            [command["command"] for command in draft.proposed_commands],
            ["ctest --test-dir build", "python build.py"],
        )

    def test_cmake_build_py_content_keeps_smoke_run_contract(self) -> None:
        content = cmake_build_py_content()

        self.assertIn("def target_names()", content)
        self.assertIn("def smoke_run_executable()", content)
        self.assertIn('"--aegis-validate"', content)
        self.assertIn('run(["cmake", "-S", ".", "-B", "build"])', content)


if __name__ == "__main__":
    unittest.main()
