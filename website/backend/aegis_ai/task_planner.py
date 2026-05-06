from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .routing import ModelRouter, RoutingDecision
from .schemas import ModeName, WorkspaceDependencyProfile, WorkspaceFile, WorkspaceProjectManifest


@dataclass(frozen=True)
class TaskPlan:
    intent: str
    objective: str
    workflow: str
    complexity: str = "focused"
    estimated_slices: int = 1
    pass_budget_hint: int = 0
    large_task_protocol: list[str] = field(default_factory=list)
    decomposition_axes: list[str] = field(default_factory=list)
    route_profile: dict[str, Any] = field(default_factory=dict)
    steps: list[str] = field(default_factory=list)
    context_requirements: list[str] = field(default_factory=list)
    tool_requirements: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    completion_criteria: list[str] = field(default_factory=list)
    routing: RoutingDecision | None = None

    @property
    def summary(self) -> str:
        return f"{self.intent} via {self.workflow}: {self.objective}"

    def to_event_payload(self) -> dict:
        return {
            "intent": self.intent,
            "objective": self.objective,
            "workflow": self.workflow,
            "complexity": self.complexity,
            "estimated_slices": self.estimated_slices,
            "pass_budget_hint": self.pass_budget_hint,
            "large_task_protocol": self.large_task_protocol,
            "decomposition_axes": self.decomposition_axes,
            "route_profile": self.route_profile,
            "steps": self.steps,
            "context_requirements": self.context_requirements,
            "tool_requirements": self.tool_requirements,
            "risks": self.risks,
            "completion_criteria": self.completion_criteria,
            "routing": self.routing.to_event_payload() if self.routing else None,
        }

    def to_prompt_context(self) -> str:
        def list_block(label: str, values: list[str]) -> str:
            body = "\n".join(f"- {value}" for value in values)
            return f"{label}:\n{body or '- (none)'}"

        route_context = self.routing.to_prompt_context() if self.routing else "(no routing decision)"
        route_profile_context = self._route_profile_prompt_context()
        return "\n\n".join(
            [
                f"Planner intent: {self.intent}",
                f"Planner objective: {self.objective}",
                f"Planner workflow: {self.workflow}",
                f"Planner scale: {self.complexity} ({self.estimated_slices} planned slice(s), pass hint {self.pass_budget_hint})",
                "Route profile:\n" + route_profile_context,
                list_block("Decomposition axes", self.decomposition_axes),
                list_block("Large-task protocol", self.large_task_protocol),
                list_block("Planner steps", self.steps),
                list_block("Context requirements", self.context_requirements),
                list_block("Tool requirements", self.tool_requirements),
                list_block("Risks to avoid", self.risks),
                list_block("Completion criteria", self.completion_criteria),
                "Routing decision:\n" + route_context,
            ]
        )

    def _route_profile_prompt_context(self) -> str:
        if not self.route_profile:
            return "- (none)"

        lines = [
            f"- Profile: {self.route_profile.get('label') or self.route_profile.get('id') or 'workspace'}",
        ]
        category = str(self.route_profile.get("category") or "").strip()
        if category:
            lines.append(f"- Category: {category}")
        reason = str(self.route_profile.get("reason") or "").strip()
        if reason:
            lines.append(f"- Reason: {reason}")
        for key, label in (
            ("stack_keywords", "Stack keywords"),
            ("preferred_roles", "Preferred roles"),
            ("focus_paths", "Focus paths"),
            ("dependency_languages", "Detected languages"),
            ("dependency_frameworks", "Detected frameworks"),
            ("dependency_package_managers", "Package managers"),
            ("dependency_build_systems", "Build systems"),
            ("install_commands", "Install commands"),
            ("validation_commands", "Validation commands"),
        ):
            values = self.route_profile.get(key)
            if isinstance(values, list):
                cleaned = [str(item).strip() for item in values if str(item).strip()]
                if cleaned:
                    lines.append(f"- {label}: {', '.join(cleaned[:12])}")
        return "\n".join(lines)


class TaskPlanner:
    def __init__(self, router: ModelRouter):
        self.router = router

    def build_plan(
        self,
        *,
        message: str,
        mode: ModeName,
        workspace_files: list[WorkspaceFile],
        context_files: list[WorkspaceFile],
        project_manifest: WorkspaceProjectManifest | None = None,
        dependency_profile: WorkspaceDependencyProfile | None = None,
    ) -> TaskPlan:
        lowered = message.lower()
        route_profile = self._route_profile(project_manifest, message, workspace_files)
        route_profile = self._with_dependency_profile(route_profile, dependency_profile)
        intent = self._intent(lowered, mode, has_project_manifest=project_manifest is not None)
        if intent == "conversation" and project_manifest is None:
            route_profile = {}
        elif intent == "research_and_synthesize" and not self._looks_like_workspace_bound_research(lowered):
            route_profile = {}
        workflow = self._workflow(intent, mode)
        objective = self._objective(message, intent)
        routing = self.router.recommend(
            self._routing_message(message, intent, project_manifest, route_profile),
            mode,
            has_workspace_context=bool(workspace_files),
        )
        steps = self._steps(intent, workflow, bool(context_files), project_manifest, route_profile, dependency_profile)
        context_requirements = self._context_requirements(
            intent, workspace_files, context_files, project_manifest, route_profile, dependency_profile
        )
        tool_requirements = self._tool_requirements(intent, lowered, mode, project_manifest, route_profile, dependency_profile)
        risks = self._risks(intent, routing.privacy_mode, lowered, project_manifest, route_profile, dependency_profile)
        completion_criteria = self._completion_criteria(intent, mode, project_manifest, route_profile, dependency_profile)
        scale = self._task_scale(
            message=message,
            intent=intent,
            workspace_files=workspace_files,
            project_manifest=project_manifest,
            route_profile=route_profile,
            dependency_profile=dependency_profile,
        )
        if scale["complexity"] in {"large", "epic"}:
            steps = [
                *steps,
                "Decompose the request into vertical slices and complete the highest-value slice first.",
                "Update or create project instructions/roadmap state so autopilot can continue without losing direction.",
                "After each slice, summarize changed files, validation status, remaining work, and the next slice.",
            ]
            context_requirements = [
                *context_requirements,
                "large-task roadmap or TODO state",
                "cross-slice architectural decisions",
            ]
            tool_requirements = [*tool_requirements, "large-task checkpoint cadence"]
            risks = [
                *risks,
                "Do not switch project type, stack, or target path while continuing a large task unless explicitly requested.",
            ]
            completion_criteria = [
                *completion_criteria,
                "Large tasks end with a stable handoff: validation status, known blockers, and next slice.",
            ]
        return TaskPlan(
            intent=intent,
            objective=objective,
            workflow=workflow,
            complexity=scale["complexity"],
            estimated_slices=scale["estimated_slices"],
            pass_budget_hint=scale["pass_budget_hint"],
            large_task_protocol=scale["large_task_protocol"],
            decomposition_axes=scale["decomposition_axes"],
            route_profile=route_profile,
            steps=steps,
            context_requirements=context_requirements,
            tool_requirements=tool_requirements,
            risks=risks,
            completion_criteria=completion_criteria,
            routing=routing,
        )

    def _task_scale(
        self,
        *,
        message: str,
        intent: str,
        workspace_files: list[WorkspaceFile],
        project_manifest: WorkspaceProjectManifest | None,
        route_profile: dict[str, Any],
        dependency_profile: WorkspaceDependencyProfile | None,
    ) -> dict[str, Any]:
        if intent not in {"implementation", "debug_and_repair", "architecture_planning", "review_and_assess"}:
            return {
                "complexity": "focused",
                "estimated_slices": 1,
                "pass_budget_hint": 0,
                "large_task_protocol": [],
                "decomposition_axes": ["answer"],
            }

        lowered = message.lower()
        score = 0
        if any(
            term in lowered
            for term in (
                "full blown",
                "full-blown",
                "production-grade",
                "production ready",
                "complete app",
                "complete application",
                "entire app",
                "full app",
                "full website",
                "from scratch",
                "single prompt",
                "longer / bigger",
                "longer/bigger",
                "complex task",
                "complex coding",
                "500,000",
                "500000",
                "500k",
                "million line",
                "large file",
                "huge file",
                "single file",
            )
        ):
            score += 3
        if any(
            term in lowered
            for term in (
                "auth",
                "database",
                "backend",
                "frontend",
                "tests",
                "ci",
                "deployment",
                "installer",
                "driver",
                "kernel",
                "dll",
                "exe",
                "multiple sln",
                "combine projects",
                "separate project",
            )
        ):
            score += 1
        open_item_mentions = len(re.findall(r"(?m)^\s*(?:[-*]|\d+\.)\s+\S", message))
        if open_item_mentions >= 12:
            score += 2
        elif open_item_mentions >= 6:
            score += 1

        workspace_file_count = len(workspace_files)
        if workspace_file_count >= 250:
            score += 2
        elif workspace_file_count >= 60:
            score += 1
        large_workspace_files = [
            item
            for item in workspace_files
            if bool(getattr(item, "is_large", False)) or int(getattr(item, "size", 0) or 0) >= 1_000_000
        ]
        if large_workspace_files:
            score += 2
        if any(int(getattr(item, "estimated_lines", 0) or 0) >= 100_000 for item in large_workspace_files):
            score += 2

        category = str(route_profile.get("category") or "").lower()
        if category in {"driver", "reverse-engineering", "native", "database"}:
            score += 1

        dependency_signals: set[str] = set()
        if dependency_profile is not None:
            for values in (
                dependency_profile.languages,
                dependency_profile.frameworks,
                dependency_profile.package_managers,
                dependency_profile.build_systems,
                dependency_profile.database_tools,
            ):
                dependency_signals.update(str(value).lower() for value in values if str(value).strip())
            if len(dependency_signals) >= 8:
                score += 2
            elif len(dependency_signals) >= 4:
                score += 1
            if len(dependency_profile.package_managers) > 1 or len(dependency_profile.build_systems) > 1:
                score += 1

        if project_manifest is not None:
            manifest_bits = " ".join(
                bit
                for bit in (
                    project_manifest.framework,
                    project_manifest.language,
                    project_manifest.package_manager,
                    " ".join(project_manifest.tags),
                )
                if bit
            ).lower()
            if any(term in manifest_bits for term in ("electron", "tauri", "desktop", "native", "driver", "database")):
                score += 1

        if score >= 7:
            complexity = "epic"
            estimated_slices = 9
            pass_budget_hint = 36
        elif score >= 4:
            complexity = "large"
            estimated_slices = 5
            pass_budget_hint = 22
        elif score >= 2:
            complexity = "standard"
            estimated_slices = 2
            pass_budget_hint = 8
        else:
            complexity = "focused"
            estimated_slices = 1
            pass_budget_hint = 4 if intent in {"implementation", "debug_and_repair"} else 2

        axes = self._decomposition_axes(route_profile, dependency_profile)
        protocol: list[str] = []
        if complexity in {"large", "epic"}:
            protocol = [
                "Keep the requested target path, language, and stack pinned for the whole run.",
                "Split the request into vertical slices with source, integration, validation, and handoff notes.",
                "Prefer completing one usable project slice over creating placeholder-only scaffolds.",
                "Run or capture the known validation command after implementation slices when allowed.",
                "If validation is blocked by missing tools or dependencies, record the exact blocker and continue source-level repair.",
                "Update TODO/roadmap/checklist state as items are completed so autopilot can resume accurately.",
            ]
            if large_workspace_files:
                protocol.extend(
                    [
                        "Treat million-byte or 100k+ line files as chunked assets: inspect summaries first, then request/read targeted line slices.",
                        "Avoid rewriting giant files wholesale; patch the smallest stable region or extract helper modules with clear integration points.",
                        "Maintain a large-file map with target symbols, line ranges, validation notes, and remaining slices.",
                    ]
                )

        return {
            "complexity": complexity,
            "estimated_slices": estimated_slices,
            "pass_budget_hint": pass_budget_hint,
            "large_task_protocol": protocol,
            "decomposition_axes": axes,
        }

    def _decomposition_axes(
        self,
        route_profile: dict[str, Any],
        dependency_profile: WorkspaceDependencyProfile | None,
    ) -> list[str]:
        category = str(route_profile.get("category") or "").lower()
        if category == "web":
            axes = ["routing/pages", "components", "state/API", "styling", "validation"]
        elif category == "full-stack":
            axes = ["frontend UI", "backend/API", "data/auth", "integration", "tests", "validation"]
        elif category == "desktop":
            axes = ["shell", "frontend UI", "backend bridge", "packaging", "validation"]
        elif category in {"native", "driver", "systems"}:
            axes = ["project files", "source", "build configuration", "runtime validation", "docs"]
        elif category == "database":
            axes = ["schema", "migrations", "data access", "tests", "rollback notes"]
        elif category == "reverse-engineering":
            axes = ["inventory", "static analysis", "symbol/import mapping", "findings", "defensive notes"]
        else:
            axes = ["structure", "core implementation", "integration", "validation", "handoff"]

        if dependency_profile is not None:
            if dependency_profile.validation_commands:
                self._append_unique(axes, "validation commands")
            if dependency_profile.install_commands:
                self._append_unique(axes, "dependency install")
            if dependency_profile.database_tools:
                self._append_unique(axes, "database")
        return axes[:8]

    def _intent(self, lowered: str, mode: ModeName, *, has_project_manifest: bool = False) -> str:
        if (
            "autopilot continuation context" in lowered
            or "open project instruction file tasks" in lowered
            or "open tasks:" in lowered
        ):
            if any(term in lowered for term in ("fix", "bug", "error", "failing", "debug")):
                return "debug_and_repair"
            return "implementation"
        if "workspace readiness continuation context" in lowered:
            if any(term in lowered for term in ("needs_repair", "repair", "failed", "failure", "error", "debug")):
                return "debug_and_repair"
            return "implementation"
        if any(term in lowered for term in ("fix", "bug", "error", "failing", "debug")):
            return "debug_and_repair"
        if any(term in lowered for term in ("review", "audit", "risk", "security")) or mode == "review":
            return "review_and_assess"
        if self._looks_like_implementation(lowered):
            return "implementation"
        if self._looks_like_external_research(lowered):
            return "research_and_synthesize"
        if has_project_manifest and mode in {"build", "develop"} and self._looks_like_project_continuation(lowered):
            return "implementation"
        if any(term in lowered for term in ("todo", "roadmap", "plan", "architecture", "design")):
            return "architecture_planning"
        return "conversation"

    def _looks_like_external_research(self, lowered: str) -> bool:
        explicit_research_terms = (
            "research",
            "citation",
            "citations",
            "cite",
            "sources",
            "web search",
            "search web",
            "search the web",
            "look up",
        )
        if any(term in lowered for term in explicit_research_terms):
            return True
        if "latest" in lowered:
            return True
        if re.search(r"\bsource\b", lowered) and not re.search(
            r"\bsource\s+(?:code|file|files|tree|layout|root|folder|map)\b",
            lowered,
        ):
            return True
        return False

    def _looks_like_workspace_bound_research(self, lowered: str) -> bool:
        return any(
            term in lowered
            for term in (
                "this project",
                "this repo",
                "this repository",
                "this codebase",
                "this workspace",
                "this app",
                "this site",
                "this website",
                "this desktop",
                "our project",
                "our repo",
                "our codebase",
                "my project",
                "my repo",
                "my codebase",
                "my app",
                "workspace dependency",
                "project dependency",
                "package version",
                "framework version",
                "sdk version",
                "api docs for this",
                "docs for this",
            )
        )

    def _looks_like_implementation(self, lowered: str) -> bool:
        action_terms = (
            "create",
            "build",
            "implement",
            "complete",
            "finish",
            "build out",
            "flesh out",
            "develop",
            "ship",
            "add",
            "edit",
            "refactor",
            "scaffold",
            "generate",
            "write file",
            "make file",
            "set up",
            "setup",
            "refine",
            "improve",
            "optimize",
            "repair",
            "debug",
            "fix",
            "work on",
            "clean up",
            "cleanup",
            "polish",
            "modernize",
            "enhance",
            "analyze",
            "inspect",
            "reverse engineer",
            "reverse-engineer",
            "disassemble",
            "decompile",
        )
        code_terms = (
            "code",
            "function",
            "component",
            "api",
            "script",
            "class",
            "module",
            "app",
            "site",
            "website",
            "dashboard",
            "tool",
            "file",
            "folder",
            "workspace",
            "project",
            "repo",
            "repository",
            "path",
            "database",
            "sql",
            "migration",
            "schema",
            "kernel",
            "driver",
            "dll",
            "exe",
            "binary",
            "firmware",
            "reverse engineering",
        )
        if any(term in lowered for term in ("at this path", "in this file", "inside this project", "in the repo")):
            return True
        source_context = bool(
            re.search(
                r"\bsource\s+(?:code|file|files|tree|layout|root|folder|map)\b",
                lowered,
            )
        )
        return any(term in lowered for term in action_terms) and (
            any(term in lowered for term in code_terms) or source_context
        )

    def _looks_like_project_continuation(self, lowered: str) -> bool:
        continuation_terms = (
            "continue",
            "keep going",
            "next step",
            "next useful",
            "your suggestions",
            "go ahead",
            "move forward",
            "carry on",
        )
        return any(term in lowered for term in continuation_terms)

    @staticmethod
    def _prompt_negates_web_stack(message: str) -> bool:
        normalized = re.sub(r"[^a-z0-9'\s]+", " ", message.lower())
        lowered = f" {' '.join(normalized.split())} "
        negated_phrases = (
            " without turning it into a website ",
            " without turning into a website ",
            " without turning this into a website ",
            " without converting it to a website ",
            " without converting into a website ",
            " without converting this to a website ",
            " without converting it into a website ",
            " without converting this into a website ",
            " do not turn it into a website ",
            " do not convert it to a website ",
            " do not convert it into a website ",
            " do not make a website ",
            " do not make a web app ",
            " do not make this a web app ",
            " don't turn it into a website ",
            " don't convert it to a website ",
            " don't convert it into a website ",
            " don't make a website ",
            " don't make a web app ",
            " don't make this a web app ",
            " dont turn it into a website ",
            " dont convert it to a website ",
            " dont convert it into a website ",
            " dont make a website ",
            " dont make a web app ",
            " dont make this a web app ",
            " do not make it a website ",
            " do not make this a website ",
            " do not make it into a website ",
            " do not make this into a website ",
            " don't make it a website ",
            " don't make this a website ",
            " don't make it into a website ",
            " don't make this into a website ",
            " dont make it a website ",
            " dont make this a website ",
            " dont make it into a website ",
            " dont make this into a website ",
            " not a website ",
            " not a web app ",
            " not web app ",
            " no website ",
            " no web app ",
            " not web ",
            " instead of a website ",
        )
        return any(phrase in lowered for phrase in negated_phrases)

    def _routing_message(
        self,
        message: str,
        intent: str,
        project_manifest: WorkspaceProjectManifest | None,
        route_profile: dict[str, Any],
    ) -> str:
        if intent in {"conversation", "research_and_synthesize"}:
            return message
        if project_manifest is None and not route_profile:
            return message

        stack_bits: list[str] = []
        if project_manifest is not None:
            stack_bits = [
                project_manifest.preset_label or project_manifest.preset_id,
                project_manifest.framework,
                project_manifest.language,
                project_manifest.package_manager,
                " ".join(project_manifest.tags[:12]),
            ]
        stack_context = " ".join(bit for bit in stack_bits if bit).strip()
        if not stack_context and not route_profile:
            return message

        profile_label = str(route_profile.get("label") or route_profile.get("id") or "").strip()
        profile_bits = f" Route profile: {profile_label}." if profile_label else ""
        action_hint = {
            "implementation": "Treat this as workspace project code when the task asks to continue, implement, validate, or evolve the scaffold.",
            "debug_and_repair": "Treat this as workspace project debugging and repair.",
            "review_and_assess": "Treat this as workspace project review.",
            "architecture_planning": "Treat this as workspace project architecture planning.",
        }.get(intent, "Use this scaffold metadata when selecting the route.")

        return (
            f"{message}\n\n"
            "Aegis workspace context for routing: "
            f"{stack_context}.{profile_bits} {action_hint}"
        )

    def _route_profile(
        self,
        project_manifest: WorkspaceProjectManifest | None,
        message: str = "",
        workspace_files: list[WorkspaceFile] | None = None,
    ) -> dict[str, Any]:
        parts = [
            message,
            " ".join(self._route_profile_file_paths(workspace_files or [])),
        ]
        tags: list[str] = []
        install_command = ""
        validation_command = ""
        if project_manifest is not None:
            parts.extend(
                [
                    project_manifest.preset_id,
                    project_manifest.preset_label,
                    project_manifest.framework,
                    project_manifest.language,
                    project_manifest.package_manager,
                    " ".join(project_manifest.tags),
                ]
            )
            tags = [item.strip().lower() for item in project_manifest.tags if item.strip()]
            install_command = project_manifest.install_command
            validation_command = project_manifest.validation_command

        text = " ".join(part for part in parts if part).lower()
        message_text = message.lower()
        web_negated = self._prompt_negates_web_stack(message)

        def contains_term(source: str, term: str) -> bool:
            if " " not in term and term.isalnum() and len(term) <= 3:
                return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", source) is not None
            return term in source

        def has_any(*terms: str) -> bool:
            return any(contains_term(text, term) for term in terms)

        def message_has_any(*terms: str) -> bool:
            return any(contains_term(message_text, term) for term in terms)

        def with_context(profile: dict[str, Any]) -> dict[str, Any]:
            return {
                **profile,
                "manifest_tags": tags,
                "validation_command": validation_command,
                "install_command": install_command,
            }

        if (
            (
                message_has_any("full stack", "full-stack", "full app", "complete app", "production-grade", "saas")
                or (
                    message_has_any("app", "web app", "website", "frontend", "react", "next.js", "nextjs", "vite")
                    and message_has_any("backend", "api", "database", "auth", "login", "server")
                )
            )
            and message_has_any("frontend", "react", "next.js", "nextjs", "vite", "web app", "website", "browser")
            and not web_negated
        ):
            return with_context(
                {
                    "id": "full-stack-app",
                    "label": "Full Stack App",
                    "category": "full-stack",
                    "reason": "The user requested a multi-layer application spanning UI, backend, data, auth, or validation.",
                    "preferred_roles": ["code", "debug", "reasoning", "judge"],
                    "stack_keywords": ["full-stack", "frontend", "backend", "api", "database", "auth", "tests", "validation"],
                    "focus_paths": ["package.json", "src/", "app/", "pages/", "components/", "server/", "api/", "db/"],
                }
            )

        if message_has_any("kernel driver", "kmdf", "wdf", "wdm", "minifilter", "ioctl", ".sys", "driver.inf"):
            return with_context(
                {
                    "id": "kernel-driver",
                    "label": "Kernel Driver",
                    "category": "driver",
                    "reason": "The user explicitly requested kernel, driver, firmware, or device-interface work.",
                    "preferred_roles": ["code", "security", "judge"],
                    "stack_keywords": ["kernel", "driver", "kmdf", "wdf", "wdm", "ioctl", "firmware", "c", "cpp"],
                    "focus_paths": ["*.inf", "*.vcxproj", "CMakeLists.txt", "src/", "driver/"],
                }
            )

        if message_has_any(
            "reverse engineer",
            "reverse-engineer",
            "reverse engineering",
            "disassemble",
            "decompile",
            "binary analysis",
            "pe header",
        ):
            return with_context(
                {
                    "id": "reverse-engineering",
                    "label": "Reverse Engineering",
                    "category": "reverse-engineering",
                    "reason": "The user explicitly requested authorized static/dynamic analysis.",
                    "preferred_roles": ["review", "security", "judge"],
                    "stack_keywords": ["reverse-engineering", "static-analysis", "binary-analysis", "pe", "imports", "symbols"],
                    "focus_paths": ["docs/", "analysis/", "tools/", "reports/"],
                }
            )

        if message_has_any("database", "sql", "postgres", "postgresql", "mysql", "sqlite", "schema", "migration", "orm"):
            return with_context(
                {
                    "id": "database",
                    "label": "Database",
                    "category": "database",
                    "reason": "The user explicitly requested schema, query, migration, or ORM work.",
                    "preferred_roles": ["code", "debug", "security", "judge"],
                    "stack_keywords": ["database", "sql", "migration", "schema", "orm", "postgres", "mysql", "sqlite"],
                    "focus_paths": ["migrations/", "schema.sql", "prisma/schema.prisma", "db/", "database/"],
                }
            )

        if (
            message_has_any("website", "web site", "web app", "landing page", "frontend", "next.js", "nextjs", "vite", "react")
            and not web_negated
        ):
            return with_context(
                {
                    "id": "web-app",
                    "label": "Web App",
                    "category": "web",
                    "reason": "The user explicitly requested a browser UI, website, or frontend build.",
                    "preferred_roles": ["code", "reasoning", "judge"],
                    "stack_keywords": ["web", "frontend", "react", "nextjs", "vite", "typescript", "css"],
                    "focus_paths": ["package.json", "src/", "app/", "pages/", "components/"],
                }
            )

        if message_has_any("c++", "cpp", "cmake", "visual studio", "sln", "vcxproj", ".exe", "executable", "dll"):
            return with_context(
                {
                    "id": "native-binary",
                    "label": "Native Binary",
                    "category": "native",
                    "reason": "The user explicitly requested native C/C++/DLL/EXE style work.",
                    "preferred_roles": ["code", "debug", "security", "judge"],
                    "stack_keywords": ["native", "dll", "exe", "win32", "msvc", "cpp", "cmake", "pe"],
                    "focus_paths": ["CMakeLists.txt", "*.sln", "*.vcxproj", "src/", "include/"],
                }
            )

        profiles: list[tuple[bool, dict[str, Any]]] = [
            (
                has_any("kernel driver", "kmdf", "wdf", "wdm", "minifilter", "ioctl", "driver.inf", ".sys", "firmware"),
                {
                    "id": "kernel-driver",
                    "label": "Kernel Driver",
                    "category": "driver",
                    "reason": "Prompt or workspace suggests privileged kernel, driver, firmware, or device-interface work.",
                    "preferred_roles": ["code", "security", "judge"],
                    "stack_keywords": ["kernel", "driver", "kmdf", "wdf", "wdm", "ioctl", "firmware", "c", "cpp"],
                    "focus_paths": ["*.inf", "*.vcxproj", "CMakeLists.txt", "src/", "driver/"],
                },
            ),
            (
                has_any(
                    "reverse engineer",
                    "reverse-engineer",
                    "reverse engineering",
                    "disassemble",
                    "disassembler",
                    "decompile",
                    "decompiler",
                    "binary analysis",
                    "pe header",
                    "import table",
                    "ida",
                    "ghidra",
                    "x64dbg",
                ),
                {
                    "id": "reverse-engineering",
                    "label": "Reverse Engineering",
                    "category": "reverse-engineering",
                    "reason": "Prompt suggests authorized static/dynamic analysis for interoperability, debugging, or security review.",
                    "preferred_roles": ["review", "security", "judge"],
                    "stack_keywords": ["reverse-engineering", "static-analysis", "binary-analysis", "pe", "imports", "symbols"],
                    "focus_paths": ["docs/", "analysis/", "tools/", "reports/"],
                },
            ),
            (
                has_any(
                    "dll",
                    ".dll",
                    ".exe",
                    "executable",
                    "shared library",
                    "native binary",
                    "pe file",
                    "win32",
                    "msvc",
                    "cmake",
                    "cmakelists.txt",
                    "c++",
                    "cpp",
                    "vcxproj",
                    "sln",
                ),
                {
                    "id": "native-binary",
                    "label": "Native Binary",
                    "category": "native",
                    "reason": "Prompt or workspace suggests native DLL/EXE/shared-library work.",
                    "preferred_roles": ["code", "debug", "security", "judge"],
                    "stack_keywords": ["native", "dll", "exe", "win32", "msvc", "cpp", "cmake", "pe"],
                    "focus_paths": ["CMakeLists.txt", "*.sln", "*.vcxproj", "src/", "include/"],
                },
            ),
            (
                (
                    not web_negated
                    and (
                    has_any("full stack", "full-stack")
                    or (
                        has_any("react", "next.js", "nextjs", "vite", "frontend", "site", "website")
                        and has_any("fastapi", "express", "django", "api", "server", "database", "auth", "login")
                    )
                    )
                ),
                {
                    "id": "full-stack-app",
                    "label": "Full Stack App",
                    "category": "full-stack",
                    "reason": "Prompt or workspace suggests a multi-layer application with frontend, backend, data, auth, or validation.",
                    "preferred_roles": ["code", "debug", "reasoning", "judge"],
                    "stack_keywords": ["full-stack", "frontend", "backend", "api", "database", "auth", "tests", "validation"],
                    "focus_paths": ["package.json", "src/", "app/", "pages/", "components/", "server/", "api/", "db/"],
                },
            ),
            (
                has_any(
                    "database",
                    "sql",
                    "postgres",
                    "postgresql",
                    "mysql",
                    "sqlite",
                    "mssql",
                    "schema",
                    "migration",
                    "orm",
                    "prisma",
                    "drizzle",
                    "sequelize",
                    "typeorm",
                ),
                {
                    "id": "database",
                    "label": "Database",
                    "category": "database",
                    "reason": "Prompt or workspace suggests schema, query, migration, or ORM work.",
                    "preferred_roles": ["code", "debug", "security", "judge"],
                    "stack_keywords": ["database", "sql", "migration", "schema", "orm", "postgres", "mysql", "sqlite"],
                    "focus_paths": ["migrations/", "schema.sql", "prisma/schema.prisma", "db/", "database/"],
                },
            ),
            (
                has_any("tauri", "electron", "desktop", "win32", "wpf", "qt", "cmake"),
                {
                    "id": "desktop-app",
                    "label": "Desktop App",
                    "category": "desktop",
                    "reason": "Manifest stack targets a packaged desktop experience.",
                    "preferred_roles": ["code", "reasoning", "judge"],
                    "stack_keywords": ["desktop", "electron", "tauri", "typescript", "rust", "cpp", "cmake"],
                    "focus_paths": ["package.json", "src/", "src-tauri/", "CMakeLists.txt"],
                },
            ),
            (
                has_any("expo", "react native", "mobile", "android", "ios"),
                {
                    "id": "mobile-app",
                    "label": "Mobile App",
                    "category": "mobile",
                    "reason": "Manifest stack targets mobile app delivery.",
                    "preferred_roles": ["code", "reasoning", "judge"],
                    "stack_keywords": ["mobile", "expo", "react-native", "typescript", "android", "ios"],
                    "focus_paths": ["app.json", "package.json", "src/", "app/"],
                },
            ),
            (
                has_any("fastapi", "express", "django", "asp.net", "web api", "http api", "api", "server"),
                {
                    "id": "api-service",
                    "label": "API Service",
                    "category": "api",
                    "reason": "Manifest stack exposes backend routes or service endpoints.",
                    "preferred_roles": ["code", "debug", "security", "judge"],
                    "stack_keywords": ["api", "backend", "server", "fastapi", "express", "django", "go", "csharp"],
                    "focus_paths": ["main.py", "src/", "routes/", "controllers/", "Program.cs"],
                },
            ),
            (
                not web_negated and has_any("next.js", "nextjs", "vite", "react", "vue", "frontend", "site", "website"),
                {
                    "id": "web-app",
                    "label": "Web App",
                    "category": "web",
                    "reason": "Manifest stack targets a browser UI or frontend app.",
                    "preferred_roles": ["code", "reasoning", "judge"],
                    "stack_keywords": ["web", "frontend", "react", "nextjs", "vite", "typescript", "tailwind"],
                    "focus_paths": ["package.json", "src/", "app/", "pages/", "components/"],
                },
            ),
            (
                has_any("data", "pandas", "notebook", "analytics", "etl"),
                {
                    "id": "data-tool",
                    "label": "Data Tool",
                    "category": "data",
                    "reason": "Manifest stack suggests analysis, ETL, or data workflows.",
                    "preferred_roles": ["code", "reasoning", "judge"],
                    "stack_keywords": ["data", "python", "pandas", "notebook", "analytics"],
                    "focus_paths": ["pyproject.toml", "requirements.txt", "notebooks/", "src/"],
                },
            ),
            (
                has_any("rust", "go", "c++", "cpp", "cmake", "cli", "command line"),
                {
                    "id": "systems-cli",
                    "label": "Systems / CLI",
                    "category": "systems",
                    "reason": "Manifest stack targets a compiled tool, script, or command-line workflow.",
                    "preferred_roles": ["code", "debug", "judge"],
                    "stack_keywords": ["systems", "cli", "rust", "go", "cpp", "cmake", "python"],
                    "focus_paths": ["Cargo.toml", "go.mod", "CMakeLists.txt", "src/", "main.py"],
                },
            ),
        ]

        for matched, profile in profiles:
            if matched:
                return {
                    **profile,
                    "manifest_tags": tags,
                    "validation_command": validation_command,
                    "install_command": install_command,
                }

        if project_manifest is None:
            return {}

        return {
            "id": "manifest-project",
            "label": "Manifest Project",
            "category": "project",
            "reason": "Manifest metadata is available, but no specialist stack profile matched.",
            "preferred_roles": ["code", "reasoning", "judge"],
            "stack_keywords": tags,
            "focus_paths": ["README.md", "package.json", "pyproject.toml", "src/"],
            "manifest_tags": tags,
            "validation_command": validation_command,
            "install_command": install_command,
        }

    def _with_dependency_profile(
        self,
        route_profile: dict[str, Any],
        dependency_profile: WorkspaceDependencyProfile | None,
    ) -> dict[str, Any]:
        if dependency_profile is None:
            return route_profile

        has_dependency_context = any(
            (
                dependency_profile.languages,
                dependency_profile.frameworks,
                dependency_profile.package_managers,
                dependency_profile.build_systems,
                dependency_profile.config_files,
                dependency_profile.validation_commands,
                dependency_profile.install_commands,
                dependency_profile.database_tools,
            )
        )
        if not has_dependency_context:
            return route_profile

        merged = dict(route_profile)
        if not merged:
            merged = {
                "id": "dependency-profile",
                "label": "Dependency Profile",
                "category": self._dependency_category(dependency_profile),
                "reason": "Workspace dependency and build manifests were detected.",
                "preferred_roles": ["code", "debug", "judge"],
                "stack_keywords": [],
                "focus_paths": [],
            }

        merged["dependency_languages"] = list(dependency_profile.languages)
        merged["dependency_frameworks"] = list(dependency_profile.frameworks)
        merged["dependency_package_managers"] = list(dependency_profile.package_managers)
        merged["dependency_build_systems"] = list(dependency_profile.build_systems)
        merged["dependency_database_tools"] = list(dependency_profile.database_tools)
        merged["install_commands"] = list(dependency_profile.install_commands)
        merged["validation_commands"] = list(dependency_profile.validation_commands)

        stack_keywords = list(merged.get("stack_keywords") or [])
        for value in [
            *dependency_profile.languages,
            *dependency_profile.frameworks,
            *dependency_profile.package_managers,
            *dependency_profile.build_systems,
            *dependency_profile.database_tools,
        ]:
            self._append_unique(stack_keywords, value.lower())
        merged["stack_keywords"] = stack_keywords[:32]

        focus_paths = list(merged.get("focus_paths") or [])
        for value in dependency_profile.config_files[:16]:
            self._append_unique(focus_paths, value)
        merged["focus_paths"] = focus_paths[:24]

        if dependency_profile.validation_commands and not merged.get("validation_command"):
            merged["validation_command"] = dependency_profile.validation_commands[0]
        if dependency_profile.install_commands and not merged.get("install_command"):
            merged["install_command"] = dependency_profile.install_commands[0]
        return merged

    def _dependency_category(self, dependency_profile: WorkspaceDependencyProfile) -> str:
        frameworks = {item.lower() for item in dependency_profile.frameworks}
        languages = {item.lower() for item in dependency_profile.languages}
        if frameworks.intersection({"react", "next.js", "vite", "vue", "svelte", "astro", "angular"}):
            if dependency_profile.database_tools:
                return "full-stack"
            return "web"
        if dependency_profile.database_tools:
            return "database"
        if frameworks.intersection({"electron", "tauri"}):
            return "desktop"
        if languages.intersection({"c", "c++", "rust", "go"}):
            return "systems"
        if languages.intersection({"python"}):
            return "python"
        return "project"

    @staticmethod
    def _append_unique(values: list[str], value: str) -> None:
        cleaned = str(value).strip()
        if cleaned and cleaned not in values:
            values.append(cleaned)

    def _route_profile_file_paths(self, workspace_files: list[WorkspaceFile]) -> list[str]:
        excluded_prefixes = ("data/", "logs/", ".aegis/", ".git/", "node_modules/", ".venv/", "__pycache__/")
        paths: list[str] = []
        for item in workspace_files:
            normalized = item.path.replace("\\", "/").lower()
            if normalized.startswith(excluded_prefixes):
                continue
            paths.append(item.path)
            if len(paths) >= 80:
                break
        return paths

    def _workflow(self, intent: str, mode: ModeName) -> str:
        workflows = {
            "architecture_planning": "inspect-plan-structure",
            "debug_and_repair": "inspect-diagnose-propose-repair",
            "review_and_assess": "inspect-rank-risks",
            "research_and_synthesize": "retrieve-crosscheck-summarize",
            "implementation": "inspect-plan-patch",
            "conversation": "answer-clarify",
        }
        if mode == "chat" and intent == "implementation":
            return "discuss-then-stage"
        return workflows.get(intent, "answer-clarify")

    def _objective(self, message: str, intent: str) -> str:
        repair_brief = re.search(r"Repair brief:\s*(.+?)(?:\n|$)", message, re.IGNORECASE | re.DOTALL)
        if repair_brief:
            compact_brief = " ".join(repair_brief.group(1).split())
            if compact_brief:
                return f"Continue workspace readiness: {compact_brief[:170].rstrip()}"

        readiness_action = re.search(r"Readiness next action:\s*(.+?)(?:\.\s*(?:Known blockers|Useful signals|Continue from)|\n|$)", message, re.IGNORECASE | re.DOTALL)
        if readiness_action:
            compact_action = " ".join(readiness_action.group(1).split())
            if compact_action:
                return f"Continue workspace readiness: {compact_action[:148].rstrip()}"

        compact = " ".join(message.split())
        if len(compact) > 180:
            compact = compact[:177].rstrip() + "..."
        if compact:
            return compact
        return {
            "architecture_planning": "Create a structured system plan.",
            "implementation": "Implement the requested project change.",
            "review_and_assess": "Find risks and high-impact improvements.",
        }.get(intent, "Respond to the user request.")

    def _steps(
        self,
        intent: str,
        workflow: str,
        has_context: bool,
        project_manifest: WorkspaceProjectManifest | None = None,
        route_profile: dict[str, Any] | None = None,
        dependency_profile: WorkspaceDependencyProfile | None = None,
    ) -> list[str]:
        common = ["Classify the task and choose a privacy-aware route."]
        if project_manifest is not None:
            common.append("Use the Aegis project manifest to stay aligned with the scaffolded stack.")
        if route_profile:
            common.append(f"Apply the {route_profile.get('label', 'workspace')} route profile when choosing files, tools, and validation.")
        if dependency_profile is not None and dependency_profile.config_files:
            common.append("Use detected dependency manifests to choose install, build, test, and lint commands.")
        if has_context:
            common.append("Use selected project context before proposing changes.")
        else:
            common.append("Identify what context is missing before assuming details.")

        intent_steps = {
            "architecture_planning": [
                "Break systems into bounded modules and contracts.",
                "Prioritize work by dependency order and production risk.",
                "Emit actionable implementation slices.",
            ],
            "implementation": [
                "Inspect relevant files and existing patterns.",
                "Decide whether this is a focused patch or a full-build pass.",
                "For full-build requests, prepare a coherent multi-file implementation instead of a placeholder.",
                "Keep validation commands as proposed actions unless explicitly allowed.",
            ],
            "debug_and_repair": [
                "Locate the failure surface and affected files.",
                "Prefer the smallest repair nearest the reported failure.",
                "Preserve rollback checkpoints for any write path.",
            ],
            "review_and_assess": [
                "Rank findings by severity and blast radius.",
                "Ground every recommendation in concrete code or architecture evidence.",
            ],
            "research_and_synthesize": [
                "Separate project facts from external facts.",
                "Cite or mark source requirements in the response metadata.",
            ],
            "conversation": [
                "Answer directly and ask only for missing high-risk details.",
            ],
        }
        return common + intent_steps.get(intent, [f"Follow workflow: {workflow}."])

    def _context_requirements(
        self,
        intent: str,
        workspace_files: list[WorkspaceFile],
        context_files: list[WorkspaceFile],
        project_manifest: WorkspaceProjectManifest | None = None,
        route_profile: dict[str, Any] | None = None,
        dependency_profile: WorkspaceDependencyProfile | None = None,
    ) -> list[str]:
        requirements = ["recent conversation", "project memory"]
        if project_manifest is not None:
            requirements.append("Aegis project manifest")
        if route_profile:
            requirements.append("route profile metadata")
        if dependency_profile is not None and dependency_profile.config_files:
            requirements.append("dependency profile")
        if workspace_files:
            requirements.append("workspace file inventory")
        if context_files:
            requirements.append("focused file snippets")
        if intent in {"implementation", "debug_and_repair", "review_and_assess"}:
            requirements.append("validation profile")
            requirements.append("recent task history")
        if intent == "architecture_planning":
            requirements.append("current architecture and roadmap documents")
        return requirements

    def _tool_requirements(
        self,
        intent: str,
        lowered: str,
        mode: ModeName,
        project_manifest: WorkspaceProjectManifest | None = None,
        route_profile: dict[str, Any] | None = None,
        dependency_profile: WorkspaceDependencyProfile | None = None,
    ) -> list[str]:
        tools: list[str] = []
        if intent in {"implementation", "debug_and_repair", "review_and_assess", "architecture_planning"}:
            tools.append("project search")
            tools.append("file read")
        if route_profile and intent in {"implementation", "debug_and_repair", "review_and_assess", "architecture_planning"}:
            tools.append(f"{route_profile.get('category', 'project')} route profile")
            category = str(route_profile.get("category") or "")
            if category == "database":
                tools.append("migration and rollback review")
            elif category == "full-stack":
                tools.append("full-stack slice planner")
                tools.append("cross-layer validation plan")
            elif category == "native":
                tools.append("native build and binary compatibility checks")
            elif category == "driver":
                tools.append("driver safety and signing checklist")
            elif category == "reverse-engineering":
                tools.append("authorized static-analysis checklist")
        if intent in {"implementation", "debug_and_repair"} or mode in {"build", "develop"}:
            tools.append("patch generation")
            tools.append("checkpointed write")
        if "install" in lowered or "dependency" in lowered:
            tools.append("dependency manager")
        if "run" in lowered or "validate" in lowered or "test" in lowered:
            tools.append("sandboxed command proposal")
        if project_manifest is not None:
            if project_manifest.install_command and intent in {"implementation", "debug_and_repair"}:
                tools.append("manifest install command")
            if project_manifest.validation_command and intent in {"implementation", "debug_and_repair", "review_and_assess"}:
                tools.append("manifest validation command")
        if dependency_profile is not None:
            if dependency_profile.install_commands and intent in {"implementation", "debug_and_repair"}:
                tools.append("dependency-aware install command")
            if dependency_profile.validation_commands and intent in {"implementation", "debug_and_repair", "review_and_assess"}:
                tools.append("dependency-aware validation command")
        return tools

    def _risks(
        self,
        intent: str,
        privacy_mode: str,
        lowered: str,
        project_manifest: WorkspaceProjectManifest | None = None,
        route_profile: dict[str, Any] | None = None,
        dependency_profile: WorkspaceDependencyProfile | None = None,
    ) -> list[str]:
        risks: list[str] = []
        if privacy_mode != "local-only":
            risks.append("Cloud routes must not receive secrets or unapproved private context.")
        if intent in {"implementation", "debug_and_repair"}:
            risks.append("Generated file paths must stay inside the workspace.")
            risks.append("Avoid unrelated refactors while preparing patches.")
        if project_manifest is not None and intent in {"implementation", "debug_and_repair", "architecture_planning"}:
            risks.append("Do not replace the manifest stack or package manager unless the user asks for a migration.")
        if route_profile and route_profile.get("category") in {"desktop", "mobile"}:
            risks.append("Keep platform-specific packaging files and native bridge code consistent with the route profile.")
        if route_profile and route_profile.get("category") == "database":
            risks.append("Database migrations need rollback notes, data-loss checks, and environment separation before execution.")
        if route_profile and route_profile.get("category") == "native":
            risks.append("Native binary changes need source-backed builds, symbol/debug info awareness, and architecture compatibility checks.")
        if route_profile and route_profile.get("category") == "driver":
            risks.append("Kernel, driver, and firmware work is high-risk; avoid stealth, bypass, exploit, or persistence behavior and require explicit validation gates.")
        if route_profile and route_profile.get("category") == "reverse-engineering":
            risks.append("Reverse-engineering guidance must stay limited to owned or authorized binaries, interoperability, debugging, and defensive analysis.")
            risks.append("Do not assist with DRM bypass, anti-cheat evasion, credential extraction, malware behavior, or unauthorized access.")
        if dependency_profile is not None and len(dependency_profile.package_managers) > 1:
            risks.append("Multiple package managers were detected; preserve the lockfile and manager already used by the project.")
        if "install" in lowered:
            risks.append("Dependency installation requires explicit approval and manifest review.")
        if intent == "research_and_synthesize":
            risks.append("Fresh external claims require source attribution.")
        return risks

    def _completion_criteria(
        self,
        intent: str,
        mode: ModeName,
        project_manifest: WorkspaceProjectManifest | None = None,
        route_profile: dict[str, Any] | None = None,
        dependency_profile: WorkspaceDependencyProfile | None = None,
    ) -> list[str]:
        criteria = {
            "architecture_planning": [
                "Todo list is ordered by priority and dependency.",
                "Each task has an expected outcome.",
                "Next implementation slice is clear.",
            ],
            "implementation": [
                "Patch is modular and scoped to the requested project.",
                "Full-build requests include enough files to be usable, runnable, and understandable.",
                "Generated changes are reviewable before apply.",
                "Validation command is proposed or known.",
            ],
            "debug_and_repair": [
                "Root cause hypothesis is explicit.",
                "Repair is minimal and rollback-safe.",
            ],
            "review_and_assess": [
                "Risks are ranked by severity.",
                "Open questions and residual risk are named.",
            ],
        }
        selected = list(criteria.get(intent, ["User receives a useful response."]))
        if project_manifest is not None and intent in {"implementation", "debug_and_repair", "review_and_assess"}:
            selected.append("Result stays compatible with the Aegis project manifest.")
        if route_profile and intent in {"implementation", "debug_and_repair", "review_and_assess"}:
            selected.append(f"Result matches the {route_profile.get('label', 'workspace')} route profile.")
        if dependency_profile is not None and dependency_profile.validation_commands and intent in {"implementation", "debug_and_repair", "review_and_assess"}:
            selected.append("Known dependency-aware validation commands are considered before completion.")
        return selected + [f"Mode remains {mode}."]
