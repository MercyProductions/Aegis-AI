from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.validation_commands import (
    is_blocked_validation_launcher_command,
    is_safe_remembered_validation_command,
)


class ValidationCommandHelperTests(unittest.TestCase):
    def test_blocks_quoted_windows_launcher_install_and_destructive_commands(self) -> None:
        blocked_commands = (
            '"C:\\Program Files\\nodejs\\npm.cmd" install',
            "C:\\Tools\\nodejs\\npm.cmd install",
            ".\\npm.cmd install",
            '"C:\\Program Files\\Git\\cmd\\git.exe" reset --hard',
            '"C:\\Windows\\System32\\cmd.exe" /c npm install',
        )

        for command in blocked_commands:
            with self.subTest(command=command):
                self.assertTrue(is_blocked_validation_launcher_command(command))
                self.assertFalse(is_safe_remembered_validation_command(command))

    def test_allows_quoted_windows_launcher_validation_commands(self) -> None:
        command = '"C:\\Program Files\\nodejs\\npm.cmd" test'

        self.assertFalse(is_blocked_validation_launcher_command(command))
        self.assertTrue(is_safe_remembered_validation_command(command))


if __name__ == "__main__":
    unittest.main()
