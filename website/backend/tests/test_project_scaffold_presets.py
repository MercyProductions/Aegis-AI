from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_presets import scaffold_presets
from aegis_ai.project_scaffolder import ProjectScaffolder


class ProjectScaffoldPresetsTests(unittest.TestCase):
    def test_scaffold_presets_have_unique_ids_and_core_workflow_targets(self) -> None:
        presets = scaffold_presets()
        preset_ids = [preset.id for preset in presets]

        self.assertEqual(len(preset_ids), len(set(preset_ids)))
        self.assertIn("nextjs-ts-tailwind", preset_ids)
        self.assertIn("python-cli", preset_ids)
        self.assertIn("cpp-cmake-cli", preset_ids)
        self.assertIn("electron-react-ts", preset_ids)
        self.assertIn("windows-kernel-driver-controller", preset_ids)

    def test_scaffold_presets_keep_validation_commands_for_key_stacks(self) -> None:
        by_id = {preset.id: preset for preset in scaffold_presets()}

        self.assertEqual(by_id["nextjs-ts-tailwind"].validation_command, "npm run build")
        self.assertEqual(by_id["static-html-site"].validation_command, "node build.js")
        self.assertEqual(by_id["python-cli"].install_command, "python -m pip install -e .[dev]")
        self.assertEqual(by_id["cpp-cmake-dll"].validation_command, "python build.py")
        self.assertIn("desktop", by_id["tauri-react-ts"].tags)

    def test_project_scaffolder_presets_delegates_to_catalog_without_sharing_list_instances(self) -> None:
        first = scaffold_presets()
        second = scaffold_presets()
        via_scaffolder = ProjectScaffolder.presets()

        self.assertIsNot(first, second)
        self.assertEqual([preset.id for preset in first], [preset.id for preset in via_scaffolder])
        first.pop()
        self.assertEqual(len(second), len(via_scaffolder))


if __name__ == "__main__":
    unittest.main()
