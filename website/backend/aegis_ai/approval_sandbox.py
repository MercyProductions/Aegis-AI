"""Approval tiers and execution sandbox profiles for safer autonomous operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import fnmatch
from pathlib import PurePosixPath

from .schemas import FileChange


class ApprovalTier(str, Enum):
    """Approval levels for autonomous operations."""

    MANUAL = "manual"
    PROMPT = "prompt"
    GUIDED = "guided"
    AUTONOMOUS = "autonomous"


class SandboxProfileName(str, Enum):
    """Execution sandbox profiles for command safety."""

    RESTRICTED = "restricted"
    SAFE = "safe"
    STANDARD = "standard"
    PERMISSIVE = "permissive"


@dataclass(frozen=True)
class ApprovalRule:
    """Rule for determining approval requirements."""

    pattern: str
    reason: str
    risk_level: int


@dataclass(frozen=True)
class SandboxProfile:
    """Configuration for command execution sandbox."""

    name: str
    description: str
    allowed_commands: tuple[str, ...]
    blocked_commands: tuple[str, ...]
    max_execution_time: int
    max_output_size: int
    allow_file_deletion: bool
    allow_network: bool
    resource_limits: dict[str, int]


@dataclass(frozen=True)
class ChangeDecision:
    path: str
    action: str
    risk_level: int
    reason: str
    requires_manual_approval: bool


class ApprovalManager:
    """Manages approval rules and decision-making."""

    def __init__(self, tier: str = "prompt", sandbox: str = "standard"):
        self.rules = self._initialize_default_rules()
        self.tier = self._parse_tier(tier)
        self.sandbox = SandboxProfileManager.normalize_name(sandbox)

    def review_change(self, path: str, action: str) -> ChangeDecision:
        normalized = PurePosixPath(path.replace("\\", "/")).as_posix()
        risk_level, reason = self._assess_risk(normalized, action)
        return ChangeDecision(
            path=normalized,
            action=action,
            risk_level=risk_level,
            reason=reason,
            requires_manual_approval=self._requires_manual_confirmation(risk_level),
        )

    def partition_auto_apply_changes(
        self,
        changes: list[FileChange],
    ) -> tuple[list[FileChange], list[tuple[FileChange, ChangeDecision]]]:
        approved: list[FileChange] = []
        blocked: list[tuple[FileChange, ChangeDecision]] = []

        for change in changes:
            decision = self.review_change(change.path, change.action)
            if decision.requires_manual_approval:
                blocked.append((change, decision))
            else:
                approved.append(change)

        return approved, blocked

    def should_auto_run_command(self, command: str, *, manual: bool) -> tuple[bool, str]:
        if manual:
            return True, ""

        if self.tier == ApprovalTier.MANUAL:
            return False, "Manual approval tier requires an explicit validation action."
        if self.tier == ApprovalTier.PROMPT:
            return False, "Prompt approval tier keeps validation manual unless you run it yourself."

        return True, ""

    def _requires_manual_confirmation(self, risk_level: int) -> bool:
        if self.tier == ApprovalTier.AUTONOMOUS:
            return False
        if self.tier in {ApprovalTier.MANUAL, ApprovalTier.PROMPT}:
            return True
        return risk_level >= 5

    def _assess_risk(self, path: str, action: str) -> tuple[int, str]:
        for rule in self.rules:
            patterns = [item.strip() for item in rule.pattern.split(",") if item.strip()]
            if any(fnmatch.fnmatch(path, pattern) for pattern in patterns):
                return rule.risk_level, rule.reason

        suffix = PurePosixPath(path).suffix.lower()
        name = PurePosixPath(path).name.lower()

        if action == "delete":
            return 8, "Deleting files is treated as a high-risk change."
        if suffix in {".sh", ".bat", ".cmd", ".ps1"}:
            return 7, "Script files can execute commands and require manual confirmation."
        if name in {
            ".env",
            ".env.local",
            "docker-compose.yml",
            "package-lock.json",
            "pnpm-lock.yaml",
            "yarn.lock",
            "bun.lock",
            "bun.lockb",
            "uv.lock",
            "poetry.lock",
            "pdm.lock",
            "cargo.lock",
            "go.sum",
        }:
            return 6, "Environment and lockfile changes can affect the whole workspace."
        if action == "create" and name in {
            "package.json",
            "manifest.json",
            "app.json",
            "cmakepresets.json",
            "launch.json",
            "tasks.json",
            "pyproject.toml",
            "setup.cfg",
            "setup.py",
            "tsconfig.json",
            "jsconfig.json",
            "vite.config.js",
            "vite.config.ts",
            "next.config.js",
            "next.config.mjs",
            "postcss.config.js",
            "postcss.config.mjs",
            "tailwind.config.js",
            "tailwind.config.ts",
            "cmakelists.txt",
            "go.mod",
            "cargo.toml",
        }:
            return 4, "Creating standard project metadata is allowed during scaffold generation."
        if suffix in {".json", ".yaml", ".yml", ".toml", ".ini"}:
            return 5, "Configuration changes can impact builds and runtime behavior."
        if action == "update":
            return 4, "Updating an existing file may require review."
        if action == "create":
            return 2, "Creating a new source file is generally low risk."

        return 3, "This change should be reviewed before automatic application."

    def _initialize_default_rules(self) -> list[ApprovalRule]:
        return [
            ApprovalRule(
                pattern="**/node_modules/*, **/.venv/*, **/__pycache__/*, node_modules/*, .venv/*, __pycache__/*",
                reason="Dependency and cache directories are never auto-applied.",
                risk_level=9,
            ),
            ApprovalRule(
                pattern="**/.git/*, .git/*",
                reason="Git metadata should not be modified automatically.",
                risk_level=9,
            ),
            ApprovalRule(
                pattern="*.ps1, *.bat, *.cmd, *.sh",
                reason="Executable scripts require manual review.",
                risk_level=7,
            ),
        ]

    def _parse_tier(self, value: str) -> ApprovalTier:
        normalized = (value or "").strip().lower() or ApprovalTier.PROMPT.value
        try:
            return ApprovalTier(normalized)
        except ValueError as exc:
            valid = ", ".join(item.value for item in ApprovalTier)
            raise ValueError(f"Unknown approval tier '{value}'. Expected one of: {valid}.") from exc


class SandboxProfileManager:
    """Manages execution sandbox profiles."""

    PROFILES: dict[str, SandboxProfile] = {
        SandboxProfileName.RESTRICTED.value: SandboxProfile(
            name=SandboxProfileName.RESTRICTED.value,
            description="No command execution, read-only posture.",
            allowed_commands=(),
            blocked_commands=("*",),
            max_execution_time=0,
            max_output_size=0,
            allow_file_deletion=False,
            allow_network=False,
            resource_limits={"cpu": 0, "memory": 0},
        ),
        SandboxProfileName.SAFE.value: SandboxProfile(
            name=SandboxProfileName.SAFE.value,
            description="Build and validation commands only, with tighter limits.",
            allowed_commands=(
                "python",
                "py",
                "node",
                "npm",
                "npx",
                "pnpm",
                "yarn",
                "bun",
                "pytest",
                "tsc",
                "vite",
                "cargo",
                "rustc",
                "go",
                "dotnet",
                "cmake",
                "ctest",
                "msbuild",
                "ninja",
                "make",
                "gradle",
                "gradlew",
                "mvn",
                "mvnw",
                "javac",
                "java",
                "flutter",
                "swift",
                "powershell",
                "pwsh",
                "ruff",
                "mypy",
                "sqlfluff",
            ),
            blocked_commands=("curl", "wget"),
            max_execution_time=60,
            max_output_size=8000,
            allow_file_deletion=False,
            allow_network=False,
            resource_limits={"cpu": 50, "memory": 256},
        ),
        SandboxProfileName.STANDARD.value: SandboxProfile(
            name=SandboxProfileName.STANDARD.value,
            description="Allowlisted commands with normal time and output limits.",
            allowed_commands=(),
            blocked_commands=("curl", "wget"),
            max_execution_time=120,
            max_output_size=12000,
            allow_file_deletion=False,
            allow_network=True,
            resource_limits={"cpu": 75, "memory": 512},
        ),
        SandboxProfileName.PERMISSIVE.value: SandboxProfile(
            name=SandboxProfileName.PERMISSIVE.value,
            description="Most allowlisted commands with extended limits.",
            allowed_commands=(),
            blocked_commands=(),
            max_execution_time=300,
            max_output_size=20000,
            allow_file_deletion=True,
            allow_network=True,
            resource_limits={"cpu": 100, "memory": 1024},
        ),
    }

    @classmethod
    def normalize_name(cls, name: str) -> str:
        normalized = (name or "").strip().lower() or SandboxProfileName.STANDARD.value
        if normalized not in cls.PROFILES:
            valid = ", ".join(cls.PROFILES)
            raise ValueError(f"Unknown sandbox profile '{name}'. Expected one of: {valid}.")
        return normalized

    @classmethod
    def get_profile(cls, name: str) -> SandboxProfile:
        return cls.PROFILES[cls.normalize_name(name)]

    @classmethod
    def is_command_allowed(cls, *, executable: str, command: str, profile_name: str) -> bool:
        profile = cls.get_profile(profile_name)
        lowered = command.strip().lower()

        if any(blocked == "*" or lowered.startswith(blocked) for blocked in profile.blocked_commands):
            return False

        if not profile.allowed_commands:
            return True

        return executable.lower() in {item.lower() for item in profile.allowed_commands}
