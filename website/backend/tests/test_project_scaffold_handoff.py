from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_handoff import (
    aegis_handoff_files,
    first_product_pass_items,
    mission_contract,
    numbered_list,
    roadmap_files,
)
from aegis_ai.schemas import ProjectScaffoldPreset


class ProjectScaffoldHandoffTests(unittest.TestCase):
    def test_roadmap_files_capture_visible_build_loop_and_commands(self) -> None:
        files = roadmap_files(
            preset("nextjs-ts-tailwind", "Next.js TypeScript + Tailwind", "Next.js", "TypeScript", tags=["web"]),
            "aegis-portal",
            prompt="Create a premium local coding cockpit.",
            install_command="npm install",
            validation_command="npm run build",
            max_repair_attempts=2,
        )

        roadmap = files[".aegis/ROADMAP.md"]
        self.assertIn("# Aegis Portal Roadmap", roadmap)
        self.assertIn("Write files through a checkpointed workspace operation.", roadmap)
        self.assertIn("up to 2 repair attempt(s)", roadmap)
        self.assertIn("npm install", roadmap)
        self.assertIn("npm run build", roadmap)
        self.assertIn("- [ ] Build the requested website content", roadmap)

    def test_aegis_handoff_files_include_manifest_contract_and_agent_handoff(self) -> None:
        files = aegis_handoff_files(
            preset("cpp-cmake-dll", "C++ CMake DLL", "CMake", "C++", package_manager="cmake", tags=["native"]),
            "native-plugin",
            prompt="Create a native DLL for an owned test host.",
            install_command="",
            validation_command="cmake -S . -B build && cmake --build build",
        )

        manifest = json.loads(files[".aegis/project.json"])
        handoff = files["AGENTS.md"]

        self.assertEqual(manifest["schema"], "aegis.project.v1")
        self.assertEqual(manifest["mission_contract"]["schema"], "aegis.mission_contract.v1")
        self.assertEqual(manifest["mission_contract"]["stack_family"], "native")
        self.assertIn("stack-lock:native-library", manifest["mission_contract"]["stack_locks"])
        self.assertIn("small checkpointed passes", manifest["agent_handoff"]["primary_goal"])
        self.assertIn("Define the exported API surface", manifest["agent_handoff"]["first_pass"][0])
        self.assertIn("Keep file writes inside this project workspace.", handoff)
        self.assertIn("cmake -S . -B build && cmake --build build", handoff)

    def test_first_product_pass_items_are_domain_and_stack_specific(self) -> None:
        barber = first_product_pass_items(
            preset("static-html-site", "Static HTML Site", "HTML", "JavaScript", tags=["web"]),
            "Create a barber styled website with booking.",
        )
        console = first_product_pass_items(
            preset("cpp-cmake-cli", "C++ CMake CLI", "CMake", "C++", tags=["native"]),
            "Create a console app.",
        )
        fallback = first_product_pass_items(
            preset("unknown", "Unknown", "Custom", "Custom"),
            "Create something useful.",
        )

        self.assertIn("barber landing flow", barber[0])
        self.assertIn("command-line behavior", console[0])
        self.assertIn("first end-to-end workflow", fallback[1])

    def test_mission_contract_and_numbered_list_are_stable(self) -> None:
        contract = mission_contract(
            preset("python-sln-refactor-tool", "Python Solution Refactor Tool", "Python", "Python"),
            "solution-tool",
            prompt="Refactor a Visual Studio solution.",
            install_command="pip install -r requirements.txt",
            validation_command="python -m pytest",
        )

        self.assertEqual(contract["stack_family"], "solution-refactor")
        self.assertIn("stack-lock:solution-refactor", contract["stack_locks"])
        self.assertIn("Reuse this project stack", contract["continuity_policy"])
        self.assertEqual(numbered_list(["Inspect", "Plan", "Validate"]), "1. Inspect\n2. Plan\n3. Validate")


def preset(
    preset_id: str,
    label: str,
    framework: str,
    language: str,
    *,
    package_manager: str = "",
    tags: list[str] | None = None,
) -> ProjectScaffoldPreset:
    return ProjectScaffoldPreset(
        id=preset_id,
        label=label,
        framework=framework,
        language=language,
        package_manager=package_manager,
        tags=tags or [],
    )


if __name__ == "__main__":
    unittest.main()
