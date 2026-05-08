from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffold_dotnet_templates import (
    dotnet_console_template,
    dotnet_webapi_template,
    dotnet_wpf_template,
)
from aegis_ai.project_scaffolder import ProjectScaffolder


class ProjectScaffoldDotnetTemplatesTests(unittest.TestCase):
    def test_dotnet_webapi_template_matches_project_scaffolder_wrapper(self) -> None:
        files = dotnet_webapi_template("billing-gateway")

        self.assertEqual(files, ProjectScaffolder._dotnet_webapi_template("billing-gateway"))
        self.assertIn("BillingGateway.sln", files)
        self.assertIn("src/BillingGateway.Api/Program.cs", files)
        self.assertIn("tests/BillingGateway.Tests/HealthTests.cs", files)
        self.assertIn('app.MapGet("/health"', files["src/BillingGateway.Api/Program.cs"])
        self.assertIn("dotnet test", files["README.md"])

    def test_dotnet_console_template_matches_project_scaffolder_wrapper(self) -> None:
        files = dotnet_console_template("log-cutter")

        self.assertEqual(files, ProjectScaffolder._dotnet_console_template("log-cutter"))
        self.assertIn("src/LogCutter/LogCutter.csproj", files)
        self.assertIn("src/LogCutter/ToolEngine.cs", files)
        self.assertIn("BuildOutput", files["src/LogCutter/ToolEngine.cs"])
        self.assertIn("--self-test", files["build.py"])
        self.assertIn("dotnet publish", files["README.md"])

    def test_dotnet_wpf_template_matches_project_scaffolder_wrapper(self) -> None:
        files = dotnet_wpf_template("task-board")

        self.assertEqual(files, ProjectScaffolder._dotnet_wpf_template("task-board"))
        self.assertIn("src/TaskBoard/TaskBoard.csproj", files)
        self.assertIn("src/TaskBoard/MainWindow.xaml", files)
        self.assertIn("tests/TaskBoard.Smoke/Program.cs", files)
        self.assertIn("<UseWPF>true</UseWPF>", files["src/TaskBoard/TaskBoard.csproj"])
        self.assertIn("DashboardState", files["tests/TaskBoard.Smoke/Program.cs"])
        self.assertIn("without opening the WPF window", files["README.md"])


if __name__ == "__main__":
    unittest.main()
