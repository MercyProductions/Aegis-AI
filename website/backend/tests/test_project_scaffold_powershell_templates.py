from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_powershell_templates import powershell_module_template
from aegis_ai.project_scaffolder import ProjectScaffolder


FIXED_GUID = "00000000-0000-0000-0000-000000000000"


class ProjectScaffoldPowerShellTemplatesTests(unittest.TestCase):
    def test_powershell_module_template_matches_project_scaffolder_wrapper(self) -> None:
        with patch("aegis_ai.project_scaffold_powershell_templates.uuid.uuid4", return_value=FIXED_GUID):
            files = powershell_module_template("Admin Toolkit")
            wrapper_files = ProjectScaffolder._powershell_module_template("Admin Toolkit")

        self.assertEqual(files, wrapper_files)
        self.assertIn("src/AdminToolkit.psm1", files)
        self.assertIn("src/AdminToolkit.psd1", files)
        self.assertIn("scripts/Invoke-AdminToolkit.ps1", files)
        self.assertIn("tests/Smoke.Tests.ps1", files)
        self.assertIn("build.ps1", files)
        self.assertIn("Export-ModuleMember", files["src/AdminToolkit.psm1"])
        self.assertIn("GUID = '00000000-0000-0000-0000-000000000000'", files["src/AdminToolkit.psd1"])
        self.assertIn("Test-ModuleManifest", files["build.ps1"])
        self.assertIn("PSParser", files["build.ps1"])
        self.assertIn("Test-AegisPath", files["tests/Smoke.Tests.ps1"])
        self.assertIn("powershell -NoProfile -ExecutionPolicy Bypass -File .\\build.ps1", files["README.md"])

    def test_powershell_module_template_prefixes_numeric_module_name(self) -> None:
        with patch("aegis_ai.project_scaffold_powershell_templates.uuid.uuid4", return_value=FIXED_GUID):
            files = powershell_module_template("123 Tools")

        self.assertIn("src/Aegis123Tools.psm1", files)
        self.assertIn("src/Aegis123Tools.psd1", files)
        self.assertIn("scripts/Invoke-Aegis123Tools.ps1", files)

    def test_powershell_module_template_uses_default_module_name_when_blank(self) -> None:
        with patch("aegis_ai.project_scaffold_powershell_templates.uuid.uuid4", return_value=FIXED_GUID):
            files = powershell_module_template("!!!")

        self.assertIn("src/AegisAutomation.psm1", files)
        self.assertIn("scripts/Invoke-AegisAutomation.ps1", files)


if __name__ == "__main__":
    unittest.main()
