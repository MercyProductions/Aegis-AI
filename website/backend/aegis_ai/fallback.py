from __future__ import annotations

import re
from pathlib import Path

from .schemas import ChangeAction, FileChange, ModeName, WorkspaceFile
from .settings import Settings


class FallbackEngine:
    def __init__(self, settings: Settings):
        self.settings = settings

    def respond(
        self,
        message: str,
        mode: ModeName,
        workspace_root: Path,
        files: list[WorkspaceFile],
    ) -> tuple[str, list[str], list[FileChange], list[str]]:
        text = message.strip()
        lower = text.lower()
        warnings: list[str] = []

        if self._is_greeting(lower):
            return self._greeting_response(mode, files), self._default_plan(mode, files), [], warnings
        if mode == "review":
            return self._review_response(workspace_root, files), self._review_plan(files), [], warnings
        if self._should_answer_directly(lower):
            return self._chat_response(text, files), self._chat_plan(files), [], warnings
        if mode == "chat" and not self._should_scaffold(lower, files):
            return self._chat_response(text, files), self._chat_plan(files), [], warnings
        if self._should_scaffold(lower, files):
            if self._should_preserve_existing_workspace(lower, files):
                changes = self._existing_workspace_continuation_changes(text, files)
                warnings.append(
                    "Deterministic fallback preserved the existing workspace stack instead of generating a fresh starter."
                )
                if changes:
                    reply = (
                        f"{self.settings.aegis_assistant_name} preserved the existing project shape and prepared "
                        "a stack-native validation helper for the continuation pass."
                    )
                    return reply, self._existing_workspace_continuation_plan(has_changes=True), changes, warnings
                return (
                    self._existing_workspace_continuation_response(text, files),
                    self._existing_workspace_continuation_plan(has_changes=False),
                    [],
                    warnings,
                )
            changes = self._starter_changes(text, workspace_root, files)
            reply = (
                f"{self.settings.aegis_assistant_name} prepared a local starter for the workspace. "
                "You can preview the files and apply them when you are ready."
            )
            return reply, self._starter_plan(), changes, warnings

        # Check for simple code creation requests
        code_changes = self._handle_simple_code_creation(text)
        if code_changes:
            reply = f"{self.settings.aegis_assistant_name} prepared the requested code file. You can preview and apply the changes."
            return reply, ["Create the requested code file"], code_changes, warnings

        if not files:
            reply = (
                f"The workspace is empty, so ask {self.settings.aegis_assistant_name} "
                "to build a starter, dashboard, API, tool, or site."
            )
            return reply, self._default_plan(mode, files), [], warnings
        return self._development_response(text, files), self._development_plan(), [], warnings

    def _is_greeting(self, message: str) -> bool:
        return any(message.startswith(item) for item in ("hello", "hi", "hey", "yo", "what's up", "whats up"))

    def _should_scaffold(self, message: str, files: list[WorkspaceFile]) -> bool:
        build_words = (
            "build",
            "create",
            "make",
            "start",
            "scaffold",
            "generate",
            "complete",
            "finish",
            "build out",
            "flesh out",
            "develop",
            "ship",
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
            "new app",
            "new site",
        )
        product_words = (
            "app",
            "application",
            "program",
            "site",
            "website",
            "dashboard",
            "landing",
            "api",
            "service",
            "tool",
            "bot",
            "cli",
            "desktop",
            "mobile",
            "extension",
            "module",
            "package",
            "database",
            "library",
            "shared library",
            "dynamic library",
            "c++",
            "cpp",
            "console app",
            "console project",
            "solution",
            "sln",
            "vcxproj",
            "exe",
            "executable",
            "dll",
            "driver",
            "library",
            "game",
            "game loop",
            "game engine",
            "sandbox",
            "asset",
            "asset registry",
            "analyzer",
            "file analyzer",
            "windows internals",
            "minhook",
            "hooking",
            "instrumentation",
            "solution merger",
            "solution splitter",
            "merge sln",
            "merge two sln",
            "split sln",
            "split a project",
        )
        workspace_has_known_build_stack = self._looks_like_next_workspace(files) or self._looks_like_cpp_workspace(files)
        return (
            any(word in message for word in build_words)
            and any(word in message for word in product_words)
        ) or (not files and any(word in message for word in product_words)) or (
            bool(files)
            and workspace_has_known_build_stack
            and any(word in message for word in build_words)
        )

    def _should_preserve_existing_workspace(self, message: str, files: list[WorkspaceFile]) -> bool:
        if not files:
            return False
        lower = self._message_without_explicit_paths(message).lower()
        if self._prompt_allows_fresh_scaffold(lower):
            return False

        continuation_terms = (
            "existing",
            "already made",
            "already built",
            "already have",
            "continue",
            "keep going",
            "work on",
            "refine",
            "improve",
            "improving",
            "optimize",
            "repair",
            "debug",
            "fix",
            "clean up",
            "cleanup",
            "polish",
            "modernize",
            "enhance",
            "build it",
            "run it",
            "validate",
            "you didn't",
            "you didnt",
            "do not make a website",
            "don't make a website",
            "not a website",
            "not web",
        )
        if not any(term in lower for term in continuation_terms):
            return False

        if self._looks_like_next_workspace(files) and self._request_is_same_stack_web_continuation(lower):
            return False
        return True

    def _prompt_allows_fresh_scaffold(self, message: str) -> bool:
        lower = self._message_without_explicit_paths(message).lower()
        return any(
            term in lower
            for term in (
                "new project",
                "new app",
                "fresh project",
                "fresh app",
                "fresh scaffold",
                "starter",
                "scaffold",
                "from scratch",
                "start over",
                "rebuild from scratch",
                "rewrite from scratch",
                "replace the project",
                "replace everything",
                "reset the project",
                "convert",
                "migrate",
                "switch to",
            )
        )

    def _request_is_same_stack_web_continuation(self, message: str) -> bool:
        web_terms = ("website", "web site", "web app", "frontend", "react", "vite", "next", "landing")
        native_terms = (
            "c++",
            "cpp",
            "cmake",
            "sln",
            "vcxproj",
            "dll",
            "driver",
            "exe",
            "desktop",
            "native",
            "console",
        )
        return any(term in message for term in web_terms) and not any(term in message for term in native_terms)

    def _existing_workspace_continuation_plan(self, *, has_changes: bool) -> list[str]:
        plan = [
            "Preserve the existing workspace stack and app type.",
            "Avoid fresh starter files unless the user explicitly asks to rebuild from scratch.",
        ]
        if has_changes:
            plan.append("Add only the validation support needed for the next build/repair pass.")
        else:
            plan.append("Wait for a model-backed continuation patch that edits the existing implementation directly.")
        plan.append("Run the detected validation command after applying concrete source changes.")
        return plan

    def _existing_workspace_continuation_response(self, message: str, files: list[WorkspaceFile]) -> str:
        return (
            f"{self.settings.aegis_assistant_name} preserved the existing workspace instead of creating an unrelated starter. "
            f"The workspace looks like {self._workspace_summary(files)}. "
            f"The next continuation pass should {self._focus(message)}"
        )

    def _existing_workspace_continuation_changes(self, message: str, files: list[WorkspaceFile]) -> list[FileChange]:
        lower = self._message_without_explicit_paths(message).lower()
        wants_validation = any(
            term in lower
            for term in (
                "build",
                "build it",
                "run it",
                "validate",
                "repair",
                "debug",
                "fix",
                "test",
            )
        )
        if not wants_validation:
            return []
        if self._looks_like_cpp_workspace(files) and not self._has_workspace_path(files, "build.py"):
            return [self._cpp_existing_validation_helper(files)]
        return []

    def _cpp_existing_validation_helper(self, files: list[WorkspaceFile]) -> FileChange:
        build_py = '''from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(command: list[str]) -> int:
    print("> " + " ".join(command))
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    return completed.returncode


def candidate_msbuild_paths() -> list[Path]:
    candidates: list[Path] = []
    explicit = os.environ.get("MSBUILD_EXE")
    if explicit:
        candidates.append(Path(explicit))
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)")
    program_files = os.environ.get("ProgramFiles", r"C:\\Program Files")
    vswhere = Path(program_files_x86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if vswhere.exists():
        completed = subprocess.run(
            [
                str(vswhere),
                "-latest",
                "-products",
                "*",
                "-requires",
                "Microsoft.Component.MSBuild",
                "-find",
                r"MSBuild\\**\\Bin\\MSBuild.exe",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        candidates.extend(Path(line.strip()) for line in completed.stdout.splitlines() if line.strip())
    for root in (Path(program_files), Path(program_files_x86)):
        vs2022 = root / "Microsoft Visual Studio" / "2022"
        for edition in ("Community", "Professional", "Enterprise", "BuildTools"):
            candidates.append(vs2022 / edition / "MSBuild" / "Current" / "Bin" / "MSBuild.exe")
            candidates.append(vs2022 / edition / "MSBuild" / "Current" / "Bin" / "amd64" / "MSBuild.exe")
    on_path = shutil.which("msbuild")
    if on_path:
        candidates.append(Path(on_path))
    return candidates


def find_msbuild() -> Path | None:
    seen: set[str] = set()
    for candidate in candidate_msbuild_paths():
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return candidate
    return None


def main() -> int:
    cmake_file = ROOT / "CMakeLists.txt"
    if cmake_file.exists():
        if shutil.which("cmake") is None:
            print("CMake was not found. Install CMake or add it to PATH.", file=sys.stderr)
            return 2
        configure_rc = run(["cmake", "-S", ".", "-B", "build"])
        if configure_rc != 0:
            return configure_rc
        return run(["cmake", "--build", "build", "--config", "Release"])

    solutions = sorted(ROOT.glob("*.sln"))
    if solutions:
        msbuild = find_msbuild()
        if msbuild is None:
            print("MSBuild was not found. Set MSBUILD_EXE or install Visual Studio Build Tools.", file=sys.stderr)
            return 2
        return run([str(msbuild), solutions[0].name, "/m", "/p:Configuration=Release"])

    print("No CMakeLists.txt or .sln file was found for native validation.", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
'''
        summary = "Add a stack-preserving C++ validation helper without recreating source files."
        if any(item.path.replace("\\", "/").lower().endswith(".sln") for item in files):
            summary = "Add a stack-preserving MSBuild validation helper without recreating source files."
        return FileChange(action="create", path="build.py", summary=summary, content=build_py)

    def _should_answer_directly(self, message: str) -> bool:
        implementation_terms = (
            "build",
            "create",
            "make",
            "scaffold",
            "generate",
            "implement",
            "edit",
            "refactor",
            "fix",
            "repair",
            "debug",
            "refine",
            "improve",
            "optimize",
            "work on",
            "clean up",
            "cleanup",
            "polish",
            "modernize",
            "enhance",
            "file",
            "project",
            "workspace",
            "repo",
        )
        if self._count_response(message):
            return True
        if any(term in message for term in implementation_terms):
            return False
        return any(
            term in message
            for term in (
                "what",
                "why",
                "how",
                "explain",
                "count",
                "summarize",
                "compare",
                "tell me",
            )
        )

    def _greeting_response(self, mode: ModeName, files: list[WorkspaceFile]) -> str:
        if files:
            return (
                f"{self.settings.aegis_assistant_name} is online in {mode} mode. "
                f"I can see {len(files)} file(s) in the workspace and I am ready to keep building."
            )
        return (
            f"{self.settings.aegis_assistant_name} is online in {mode} mode. "
            "The workspace is clear, so we can start with a fresh build or a review-first pass."
        )

    def _default_plan(self, mode: ModeName, files: list[WorkspaceFile]) -> list[str]:
        if not files:
            return [
                "Define the first working slice.",
                "Generate only the files needed to make that slice real.",
                "Iterate from the preview instead of overbuilding.",
            ]
        if mode == "review":
            return self._review_plan(files)
        return self._development_plan()

    def _starter_plan(self) -> list[str]:
        return [
            "Review the generated starter and confirm the direction.",
            "Apply the preview to write the first working slice.",
            "Run validation once the workspace has a build or test command.",
        ]

    def _development_plan(self) -> list[str]:
        return [
            "Read the current workspace shape.",
            "Choose one high-value implementation step.",
            "Preview edits, apply them, then validate the result.",
        ]

    def _review_plan(self, files: list[WorkspaceFile]) -> list[str]:
        if not files:
            return [
                "There is no implementation to review yet.",
                "Choose the first feature or starter.",
                "Use build or develop mode for file work.",
            ]
        return [
            "Identify what already exists.",
            "Call out gaps that block the next milestone.",
            "Turn the next step into a focused implementation task.",
        ]

    def _chat_plan(self, files: list[WorkspaceFile]) -> list[str]:
        if files:
            return [
                "Use the current workspace as context.",
                "Clarify product direction or architecture tradeoffs.",
                "Move into build or develop mode for file work.",
            ]
        return [
            "Clarify what you want to build.",
            "Choose the first slice worth making real.",
            "Switch into build mode when you want files drafted.",
        ]

    def _chat_response(self, message: str, files: list[WorkspaceFile]) -> str:
        count_response = self._count_response(message)
        if count_response:
            return count_response

        # Check for simple code creation requests
        code_changes = self._handle_simple_code_creation(message)
        if code_changes:
            return f"{self.settings.aegis_assistant_name} can create that code file for you. Try using 'develop' mode to create files."

        return (
            f"{self.settings.aegis_assistant_name} is focused on direction first. "
            f"The workspace looks like {self._workspace_summary(files)}. "
            f"The next useful move is to narrow this into one concrete deliverable: {self._focus(message)}"
        )

    def _count_response(self, message: str) -> str:
        match = re.search(
            r"\bcount\s+(?:to\s+)?(-?\d+)\s+starting\s+(?:from|at)\s+(-?\d+)",
            message.lower(),
        )
        if not match:
            return ""
        first = int(match.group(1))
        start = int(match.group(2))
        if first < start:
            values = [str(start + offset) for offset in range(max(0, min(first, 200)))]
        else:
            values = [str(value) for value in range(start, min(first, start + 199) + 1)]
        return ", ".join(values)

    def _handle_simple_code_creation(self, message: str) -> list[FileChange] | None:
        """Handle simple code creation requests by returning file changes."""
        lower = message.lower().strip()

        # Batch script requests
        if any(phrase in lower for phrase in ["batch script", "batch file", "cmd script", ".bat", ".cmd"]):
            if "hello world" in lower or "hello" in lower:
                return [
                    FileChange(
                        action="create",
                        path="hello.bat",
                        summary="Create a batch script that displays Hello World",
                        content="@echo off\necho Hello World!\npause"
                    )
                ]
            return [
                FileChange(
                    action="create",
                    path="script.bat",
                    summary="Create a basic batch script template",
                    content="@echo off\nREM Your batch script here\necho Hello from your batch script!\npause"
                )
            ]

        # Python script requests
        if any(phrase in lower for phrase in ["python script", "python file", ".py"]):
            if "hello world" in lower or "hello" in lower:
                return [
                    FileChange(
                        action="create",
                        path="hello.py",
                        summary="Create a Python script that displays Hello World",
                        content="print('Hello World!')"
                    )
                ]

        # HTML requests
        if any(phrase in lower for phrase in ["html", "webpage", "website"]):
            if "hello world" in lower or "hello" in lower:
                return [
                    FileChange(
                        action="create",
                        path="index.html",
                        summary="Create a basic HTML page that displays Hello World",
                        content="""<!DOCTYPE html>
<html>
<head>
    <title>Hello World</title>
</head>
<body>
    <h1>Hello World!</h1>
    <p>Welcome to my first webpage.</p>
</body>
</html>"""
                    )
                ]

        # JavaScript requests
        if any(phrase in lower for phrase in ["javascript", "js", ".js"]):
            if "hello world" in lower or "hello" in lower:
                return [
                    FileChange(
                        action="create",
                        path="script.js",
                        summary="Create a JavaScript file that logs Hello World",
                        content="console.log('Hello World!');"
                    )
                ]

        return None

        # General code requests - provide helpful guidance
        if any(word in lower for word in ["code", "script", "program", "function"]):
            if "hello world" in lower:
                return f"""Here are "Hello World" examples in different languages:

**Python:**
```python
print("Hello World!")
```

**JavaScript:**
```javascript
console.log("Hello World!");
```

**Batch:**
```batch
@echo off
echo Hello World!
pause
```

**HTML:**
```html
<!DOCTYPE html>
<html>
<body>
    <h1>Hello World!</h1>
</body>
</html>
```

Which language would you like to use?"""

        return None

    def _review_response(self, workspace_root: Path, files: list[WorkspaceFile]) -> str:
        if not files:
            return "There is nothing to review yet. Start with a first runnable slice before polishing."
        top_files = ", ".join(file.path for file in files[:6])
        return (
            f"I reviewed {workspace_root}. There are {len(files)} tracked file(s); "
            f"the main surface starts with {top_files}. The next smart move is one focused, verifiable change."
        )

    def _development_response(self, message: str, files: list[WorkspaceFile]) -> str:
        return (
            f"{self.settings.aegis_assistant_name} can work from the current workspace without external AI services. "
            f"The workspace looks like {self._workspace_summary(files)}. "
            f"For this request, I would {self._focus(message)}"
        )

    def _workspace_summary(self, files: list[WorkspaceFile]) -> str:
        if not files:
            return "an empty project"
        text_files = sum(1 for file in files if file.kind == "text")
        sample = ", ".join(file.path for file in files[:4])
        return f"{len(files)} file(s), including {text_files} text file(s). Leading files: {sample}"

    def _focus(self, message: str) -> str:
        lower = message.lower()
        if "fix" in lower or "bug" in lower:
            return "inspect the failing path, patch the smallest likely cause, and validate."
        if "dashboard" in lower:
            return "define the dashboard's first screen, data blocks, and primary actions."
        if "api" in lower or "backend" in lower:
            return "define the first endpoint, data shape, and validation command."
        if "ui" in lower or "style" in lower:
            return "refresh the visible interface while preserving the existing structure."
        return "turn the request into one concrete build step."

    def _starter_changes(self, message: str, workspace_root: Path, files: list[WorkspaceFile]) -> list[FileChange]:
        lower = self._message_without_explicit_paths(message).lower()
        explicit_preset = self._explicit_project_preset(lower)
        if explicit_preset:
            return self._project_scaffold_starter(explicit_preset, message, workspace_root)
        if self._looks_like_msvc_cpp_request(lower, files):
            return self._cpp_msvc_console_starter(workspace_root)
        if any(word in lower for word in ("c++", "cpp", "visual studio", "sln", "vcxproj", "console app", "console project")):
            return self._cpp_console_starter()
        if self._looks_like_cpp_workspace(files) and not any(
            word in lower for word in ("website", "web site", "web app", "landing", "frontend", "react", "vite", "next")
        ):
            return self._cpp_console_starter()
        if self._looks_like_next_workspace(files):
            return self._next_site_starter(
                message,
                workspace_root,
                files,
                include_package=not self._has_workspace_path(files, "package.json"),
            )
        python_cli_request = "python" in lower and any(
            word in lower
            for word in (
                "cli",
                "command line",
                "command-line",
                "script",
                "tool",
                "app",
                "application",
                "program",
            )
        )
        python_service_request = any(word in lower for word in ("api", "backend", "service", "fastapi", "flask"))
        if python_cli_request and not python_service_request:
            return self._python_app_starter()
        if python_service_request or ("python" in lower and not python_cli_request):
            return self._python_service_starter()
        if any(word in lower for word in ("website", "web site", "web app", "landing", "dashboard", "frontend", "react", "vite", "next")):
            if any(word in lower for word in ("full", "complete", "finish", "build out", "barber", "salon", "business")):
                return self._full_static_site_starter(message)
            return self._web_starter("dashboard" if "dashboard" in lower else "studio")
        if any(word in lower for word in ("app", "application", "program", "desktop", "mobile", "tool", "bot", "cli", "exe", "executable")):
            return self._python_app_starter()
        return self._web_starter("dashboard" if "dashboard" in lower else "studio")

    def _project_scaffold_starter(
        self,
        preset_id: str,
        message: str,
        workspace_root: Path,
    ) -> list[FileChange]:
        from .project_scaffolder import ProjectScaffolder

        project_name = self._project_title(message, workspace_root.name or "Aegis Project")
        files = ProjectScaffolder._template_for(preset_id)(project_name)
        files = ProjectScaffolder._specialize_template_for_prompt(preset_id, project_name, message, files)
        return [
            FileChange(
                action="create",
                path=path,
                summary=f"Create {preset_id} scaffold file.",
                content=content,
            )
            for path, content in files.items()
        ]

    def _explicit_project_preset(self, message: str) -> str:
        if any(
            term in message
            for term in (
                "merge sln",
                "merge two sln",
                "merge solutions",
                "combine sln",
                "combine projects",
                "combine solutions",
                "split sln",
                "split solution",
                "split a project",
                "separate project",
                "extract project",
                "into its own sln",
                "solution refactor",
                "solution merger",
                "solution splitter",
            )
        ):
            return "python-sln-refactor-tool"
        if any(
            term in message
            for term in (
                "windows internals",
                "win32 internals",
                "ntdll",
                "winapi",
                "minhook",
                "hooking",
                "function hook",
                "api hook",
                "detours",
                "instrumentation",
                "process modules",
                "module enumeration",
                "export table",
                "iat",
            )
        ):
            return "cpp-windows-internals-hooking"
        if any(
            term in message
            for term in (
                "imgui",
                "dear imgui",
                "immediate mode gui",
                "immediate-mode gui",
                "debug overlay",
                "game editor",
                "editor tool",
                "tooling gui",
            )
        ):
            return "cpp-imgui-win32-dx11"
        if any(
            term in message
            for term in (
                "game file",
                "game files",
                "asset file",
                "asset files",
                "asset bundle",
                "asset bundles",
                "file format",
                "binary format",
                "reverse engineer",
                "reverse-engineer",
                "reverse engineering",
                "pak",
                "wad",
                "hex",
                "entropy",
            )
        ):
            return "python-game-file-analyzer"
        if any(
            term in message
            for term in (
                "game loop",
                "game engine",
                "game development",
                "game dev",
                "ecs",
                "entity component",
                "simulation",
                "asset registry",
                "level system",
            )
        ):
            return "cpp-game-loop-cmake"
        if any(term in message for term in ("browser extension", "chrome extension", "edge extension", "manifest v3", " mv3")):
            return "browser-extension-mv3"
        if any(term in message for term in ("vscode extension", "vs code extension", "visual studio code extension")):
            return "vscode-extension-js"
        if "tauri" in message:
            return "tauri-react-ts"
        if "electron" in message:
            return "electron-react-ts"
        if any(term in message for term in ("react native", "expo", "ios app", "android app")) or (
            "mobile" in message and "react" in message
        ):
            return "expo-react-native-ts"
        if self._looks_like_next_request(message):
            return "nextjs-ts-tailwind"
        if self._looks_like_vite_react_request(message):
            return "vite-react-ts"
        if "fastapi" in message:
            return "fastapi-python-api"
        if "django" in message:
            return "django-python-web"
        if "express" in message and any(term in message for term in ("api", "backend", "server", "service")):
            return "express-ts-api"
        if "node" in message or "node.js" in message:
            if any(term in message for term in ("full stack", "full-stack", "crud app", "web app")):
                return "node-fullstack-js"
            if any(term in message for term in ("api", "backend", "server", "service", "rest")):
                return "node-http-api-js"
            if any(term in message for term in ("cli", "command line", "command-line", "tool")):
                return "node-cli-js"
        if any(term in message for term in ("powershell module", "ps module")):
            return "powershell-module"
        if "sqlite" in message or ("database" in message and "python" in message):
            return "sqlite-python-db"
        if "rust" in message or "cargo" in message:
            return "rust-cli"
        if "golang" in message or re.search(r"\bgo\b", message):
            return "go-http-api"
        if "kernel driver" in message or ("driver" in message and "windows" in message):
            return "windows-kernel-driver-controller"
        if "windows service" in message or "win32 service" in message:
            return "cpp-windows-service"
        if any(term in message for term in ("dll", "shared library", "dynamic library")) and any(
            term in message for term in ("c++", "cpp", "cmake", "native")
        ):
            return "cpp-cmake-dll"
        if any(term in message for term in ("dotnet", ".net", "c#")):
            if "wpf" in message or "xaml" in message:
                return "dotnet-wpf-csharp"
            if any(term in message for term in ("api", "webapi", "web api", "backend", "service")):
                return "dotnet-webapi-csharp"
            return "dotnet-console-csharp"
        return ""

    def _has_workspace_path(self, files: list[WorkspaceFile], path: str) -> bool:
        normalized = path.replace("\\", "/").lower().strip("/")
        return any(item.path.replace("\\", "/").lower().strip("/") == normalized for item in files)

    def _looks_like_next_request(self, message: str) -> bool:
        return any(term in message for term in ("next.js", "nextjs", "next app", "next website", "next project"))

    def _looks_like_vite_react_request(self, message: str) -> bool:
        explicit_vite = any(term in message for term in ("vite", "vitejs", "vite.js"))
        explicit_react = any(term in message for term in ("react", "reactjs", "react.js"))
        return explicit_vite or (explicit_react and not self._looks_like_next_request(message))

    def _looks_like_next_workspace(self, files: list[WorkspaceFile]) -> bool:
        paths = {item.path.replace("\\", "/").lower().strip("/") for item in files}
        return (
            "next.config.js" in paths
            or "next.config.mjs" in paths
            or "next.config.ts" in paths
            or any(path.startswith("app/") for path in paths)
        ) and ("package.json" in paths or "tsconfig.json" in paths)

    def _looks_like_cpp_workspace(self, files: list[WorkspaceFile]) -> bool:
        paths = {item.path.replace("\\", "/").lower().strip("/") for item in files}
        return (
            "cmakelists.txt" in paths
            or any(path.endswith(".sln") or path.endswith(".vcxproj") for path in paths)
            or any(path.endswith((".cpp", ".cc", ".cxx", ".hpp", ".h")) for path in paths)
        )

    def _looks_like_msvc_cpp_request(self, message: str, files: list[WorkspaceFile]) -> bool:
        paths = {item.path.replace("\\", "/").lower().strip("/") for item in files}
        has_msvc_workspace = any(path.endswith(".sln") or path.endswith(".vcxproj") for path in paths)
        has_msvc_prompt = any(term in message for term in ("sln", "solution", "visual studio", "vcxproj", "msbuild"))
        has_cpp_prompt = any(term in message for term in ("c++", "cpp", "console app", "console project"))
        return has_msvc_workspace or (has_msvc_prompt and has_cpp_prompt)

    _WINDOWS_PATH_STOP_PHRASES: tuple[str, ...] = (
        " here ",
        " i want",
        " i need",
        " can you",
        " could you",
        " please",
        " and then ",
        " then ",
        " so ",
        " but ",
        " because ",
        " with ",
        " using ",
        " for me",
        " if ",
        " create ",
        " build ",
        " make ",
        " complete ",
        " finish ",
        " develop ",
        " ship ",
        " generate ",
        " scaffold ",
        " set up ",
        " setup ",
        " start ",
        " write ",
    )

    def _message_without_explicit_paths(self, message: str) -> str:
        cleaned = message
        for path_fragment in self._windows_path_fragments(message):
            cleaned = cleaned.replace(path_fragment, " ", 1)
        cleaned = re.sub(
            r"\b(?:at\s+this\s+(?:path|location)|in\s+this\s+(?:folder|directory)|at\s+this\s+folder)\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        return " ".join(cleaned.split())

    def _windows_path_fragments(self, message: str) -> list[str]:
        fragments: list[str] = []
        for match in re.finditer(r"[A-Za-z]:[\\/]", message):
            start = match.start()
            end = match.end()
            while end < len(message):
                if message[end] in "\r\n\"'`<>|*?":
                    break
                end += 1
            candidate = self._clean_windows_path_fragment(message[start:end])
            if candidate and candidate not in fragments:
                fragments.append(candidate)
        return fragments

    def _clean_windows_path_fragment(self, value: str) -> str:
        candidate = (value or "").strip()
        if not candidate:
            return ""
        lowered = candidate.lower()
        stop = len(candidate)
        for phrase in self._WINDOWS_PATH_STOP_PHRASES:
            found = lowered.find(phrase, 3)
            if found != -1:
                stop = min(stop, found)
        candidate = candidate[:stop].strip()
        return re.sub(r"[\s.,;)\]}]+$", "", candidate).strip()

    def _project_title(self, message: str, fallback: str) -> str:
        cleaned = self._message_without_explicit_paths(message)
        cleaned = re.sub(
            r"\b(create|build|make|generate|complete|finish|please|for me|website|web site|web app|app|project|at this path|use whatever language you think is best)\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        words = [word.strip(" .,:;_-") for word in cleaned.split() if word.strip(" .,:;_-")]
        if "barber" in message.lower():
            return "Rick Cullers Barbershop" if "rick" in message.lower() or "culler" in message.lower() else "Prime Cut Barbershop"
        if 1 <= len(words) <= 6:
            return " ".join(word.capitalize() for word in words)
        return fallback

    def _full_static_site_starter(self, message: str) -> list[FileChange]:
        brand = self._project_title(message, "Aegis Business Website")
        lower = message.lower()
        is_barber = "barber" in lower or "salon" in lower or "cut" in lower
        industry_label = "Barbershop" if is_barber else "Business"
        headline = "Sharp cuts, calm appointments, neighborhood trust." if is_barber else "A complete local business website."
        html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="{brand} is a polished {industry_label.lower()} website generated by Aegis." />
    <title>{brand}</title>
    <link rel="stylesheet" href="./styles.css" />
  </head>
  <body>
    <header class="site-header">
      <a class="brand" href="#home">{brand}</a>
      <nav aria-label="Primary navigation">
        <a href="#services">Services</a>
        <a href="#work">Work</a>
        <a href="#pricing">Pricing</a>
        <a href="#booking">Book</a>
      </nav>
    </header>

    <main id="home">
      <section class="hero">
        <div>
          <p class="eyebrow">{industry_label} experience</p>
          <h1>{headline}</h1>
          <p class="lede">A premium first version with real sections, booking flow, service cards, testimonials, and mobile-ready styling.</p>
          <div class="hero-actions">
            <a class="button primary" href="#booking">Reserve a chair</a>
            <a class="button ghost" href="#services">Explore services</a>
          </div>
        </div>
        <aside class="hero-panel" aria-label="Business highlights">
          <span>Open today</span>
          <strong>9 AM - 7 PM</strong>
          <p>Walk-ins welcome. Appointments recommended for weekends.</p>
        </aside>
      </section>

      <section id="services" class="section">
        <div class="section-heading">
          <p class="eyebrow">Services</p>
          <h2>Everything needed for a clean first launch.</h2>
        </div>
        <div class="card-grid">
          <article><h3>Signature Cut</h3><p>Consultation, precision cut, styling, and finish.</p></article>
          <article><h3>Beard Shape</h3><p>Line work, trim, hot towel, and detail cleanup.</p></article>
          <article><h3>Kids Cut</h3><p>Fast, patient service for younger clients.</p></article>
          <article><h3>Event Ready</h3><p>Polished grooming for weddings, photos, and nights out.</p></article>
        </div>
      </section>

      <section id="work" class="split section">
        <div>
          <p class="eyebrow">Results</p>
          <h2>Built to look credible on day one.</h2>
          <p>The layout is intentionally complete: hero, service menu, pricing, gallery placeholders, proof, contact, and a booking form.</p>
        </div>
        <div class="stats">
          <div><strong>4.9</strong><span>average rating</span></div>
          <div><strong>18</strong><span>weekly openings</span></div>
          <div><strong>12+</strong><span>years experience</span></div>
        </div>
      </section>

      <section id="pricing" class="section">
        <div class="section-heading">
          <p class="eyebrow">Pricing</p>
          <h2>Clear menu, no guessing.</h2>
        </div>
        <div class="price-list">
          <div><span>Classic Cut</span><strong>$32</strong></div>
          <div><span>Cut + Beard</span><strong>$48</strong></div>
          <div><span>Hot Towel Shave</span><strong>$38</strong></div>
          <div><span>Kids Cut</span><strong>$24</strong></div>
        </div>
      </section>

      <section id="booking" class="booking section">
        <div>
          <p class="eyebrow">Booking</p>
          <h2>Reserve a time.</h2>
          <p>Use this starter form as the first step before wiring a real booking provider or backend.</p>
        </div>
        <form>
          <label>Name<input name="name" autocomplete="name" /></label>
          <label>Service<select name="service"><option>Classic Cut</option><option>Cut + Beard</option><option>Hot Towel Shave</option></select></label>
          <label>Preferred day<input name="date" type="date" /></label>
          <button type="submit">Request appointment</button>
          <p class="form-status" role="status"></p>
        </form>
      </section>
    </main>

    <footer>&copy; {brand}. Built with Aegis.</footer>
    <script src="./app.js"></script>
  </body>
</html>
"""
        css = """:root {
  color-scheme: light;
  --ink: #171312;
  --muted: #6f625c;
  --paper: #fbf7f0;
  --panel: #ffffff;
  --line: rgba(23, 19, 18, 0.12);
  --accent: #b8472c;
  --accent-dark: #7a2c1c;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Inter, "Segoe UI", Arial, sans-serif;
  color: var(--ink);
  background: var(--paper);
}
a { color: inherit; text-decoration: none; }
.site-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 18px clamp(18px, 4vw, 56px);
  background: rgba(251, 247, 240, 0.92);
  border-bottom: 1px solid var(--line);
  backdrop-filter: blur(14px);
}
.brand { font-weight: 900; letter-spacing: 0; }
nav { display: flex; gap: 18px; color: var(--muted); font-size: 0.95rem; }
.hero, .section {
  width: min(1160px, calc(100% - 36px));
  margin: 0 auto;
}
.hero {
  min-height: 72vh;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 360px);
  align-items: center;
  gap: clamp(28px, 5vw, 72px);
  padding: 72px 0 52px;
}
.eyebrow {
  margin: 0 0 12px;
  color: var(--accent-dark);
  font-weight: 800;
  text-transform: uppercase;
  font-size: 0.78rem;
}
h1, h2, h3, p { letter-spacing: 0; }
h1 {
  max-width: 13ch;
  margin: 0;
  font-size: clamp(3rem, 9vw, 7.2rem);
  line-height: 0.9;
}
h2 {
  margin: 0;
  font-size: clamp(2rem, 5vw, 4.2rem);
  line-height: 1;
}
.lede {
  max-width: 62ch;
  color: var(--muted);
  font-size: 1.1rem;
  line-height: 1.7;
}
.hero-actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 28px; }
.button, button {
  min-height: 46px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 0 18px;
  font: inherit;
  font-weight: 800;
  cursor: pointer;
}
.primary, button { background: var(--accent); color: white; border-color: var(--accent); }
.ghost { background: transparent; }
.hero-panel, article, .stats div, form {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  box-shadow: 0 18px 48px rgba(56, 42, 32, 0.08);
}
.hero-panel { padding: 28px; }
.hero-panel span { display: block; color: var(--muted); }
.hero-panel strong { display: block; margin: 8px 0; font-size: 2rem; }
.section { padding: 72px 0; }
.section-heading { display: grid; gap: 12px; margin-bottom: 28px; }
.card-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
article { padding: 24px; min-height: 160px; }
article p, .split p, .booking p, footer { color: var(--muted); line-height: 1.7; }
.split {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(300px, 1.1fr);
  gap: 28px;
  align-items: center;
}
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.stats div { padding: 24px; }
.stats strong { display: block; font-size: 2.5rem; }
.stats span { color: var(--muted); }
.price-list {
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
  background: var(--panel);
}
.price-list div {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 20px 24px;
  border-bottom: 1px solid var(--line);
}
.price-list div:last-child { border-bottom: 0; }
.booking {
  display: grid;
  grid-template-columns: minmax(0, 0.85fr) minmax(320px, 1.15fr);
  gap: 28px;
}
form { display: grid; gap: 14px; padding: 24px; }
label { display: grid; gap: 7px; font-weight: 800; color: var(--muted); }
input, select {
  width: 100%;
  min-height: 44px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 0 12px;
  font: inherit;
}
.form-status { min-height: 22px; margin: 0; color: var(--accent-dark); font-weight: 800; }
footer { width: min(1160px, calc(100% - 36px)); margin: 0 auto; padding: 36px 0 52px; }

@media (max-width: 820px) {
  nav { display: none; }
  .hero, .split, .booking { grid-template-columns: 1fr; }
  .card-grid { grid-template-columns: 1fr 1fr; }
  .stats { grid-template-columns: 1fr; }
}

@media (max-width: 560px) {
  .card-grid { grid-template-columns: 1fr; }
  .site-header { align-items: flex-start; }
  h1 { font-size: 3.25rem; }
}
"""
        js = """const form = document.querySelector("form");
const status = document.querySelector(".form-status");

if (form && status) {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const name = data.get("name") || "Guest";
    status.textContent = `${name}, your appointment request is ready to wire into a backend.`;
  });
}
"""
        build_js = """const fs = require("fs");
const path = require("path");

const root = __dirname;

function read(file) {
  const fullPath = path.join(root, file);
  if (!fs.existsSync(fullPath)) {
    throw new Error(`${file} is missing`);
  }
  return fs.readFileSync(fullPath, "utf8");
}

const html = read("index.html");
const css = read("styles.css");
const js = read("app.js");

const requiredHtml = [
  "<main",
  'id="services"',
  'id="booking"',
  "styles.css",
  "app.js",
];

for (const marker of requiredHtml) {
  if (!html.includes(marker)) {
    throw new Error(`index.html is missing ${marker}`);
  }
}

if (!/addEventListener\\s*\\(/.test(js)) {
  throw new Error("app.js is missing an interaction listener");
}

if (!/@media\\s*\\(/.test(css)) {
  throw new Error("styles.css is missing responsive media queries");
}

console.log("Static site validation passed.");
"""
        readme = f"""# {brand}

A complete static first version generated by Aegis.

## Files

- `index.html` contains the full page structure.
- `styles.css` contains responsive production-style layout.
- `app.js` contains the starter booking interaction.
- `build.js` validates the generated static site without external packages.

## Validate

```powershell
node build.js
```

Open `index.html` in a browser or serve this folder with any static file server.
"""
        return [
            FileChange(action="create", path="README.md", summary="Document the complete static site.", content=readme),
            FileChange(action="create", path="index.html", summary="Create the complete landing website.", content=html),
            FileChange(action="create", path="styles.css", summary="Add responsive full-site styling.", content=css),
            FileChange(action="create", path="app.js", summary="Add booking form interaction.", content=js),
            FileChange(action="create", path="build.js", summary="Add dependency-free static site validation.", content=build_js),
        ]

    def _next_site_starter(
        self,
        message: str,
        workspace_root: Path,
        files: list[WorkspaceFile],
        *,
        include_package: bool,
    ) -> list[FileChange]:
        brand = self._project_title(message, "Aegis Next App")
        lower = message.lower()
        is_barber = "barber" in lower or "salon" in lower
        service_label = "barbershop" if is_barber else "business"
        known_paths = {file.path.replace("\\", "/").strip().lstrip("/").lower() for file in files}

        def action_for(path: str) -> ChangeAction:
            normalized = path.replace("\\", "/").strip().lstrip("/").lower()
            if normalized in known_paths or (workspace_root / path).exists():
                return "update"
            return "create"

        page_tsx = """import { AppShell } from "../components/app-shell";

export default function Home() {
  return <AppShell />;
}
"""
        layout_tsx = f"""import type {{ Metadata }} from "next";
import type {{ ReactNode }} from "react";
import "./globals.css";

export const metadata: Metadata = {{
  title: "{brand}",
  description: "A complete {service_label} website generated by Aegis."
}};

export default function RootLayout({{ children }}: {{ children: ReactNode }}) {{
  return (
    <html lang="en">
      <body>{{children}}</body>
    </html>
  );
}}
"""
        app_shell = f"""const services = [
  ["Signature Cut", "Precision cut, styling, and finish."],
  ["Beard Shape", "Line work, trim, hot towel, and detail cleanup."],
  ["Kids Cut", "Fast, patient service for younger clients."],
  ["Event Ready", "Polished grooming for important dates."]
];

const prices = [
  ["Classic Cut", "$32"],
  ["Cut + Beard", "$48"],
  ["Hot Towel Shave", "$38"],
  ["Kids Cut", "$24"]
];

export function AppShell() {{
  return (
    <>
      <header className="siteHeader">
        <a className="brand" href="#home">{brand}</a>
        <nav aria-label="Primary navigation">
          <a href="#services">Services</a>
          <a href="#proof">Proof</a>
          <a href="#pricing">Pricing</a>
          <a href="#booking">Book</a>
        </nav>
      </header>

      <main id="home">
        <section className="hero">
          <div>
            <p className="eyebrow">Neighborhood {service_label}</p>
            <h1>Sharp cuts, calm appointments, real local trust.</h1>
            <p className="lede">
              A complete first version with services, pricing, proof, booking intent,
              and responsive styling ready for the next backend or CMS pass.
            </p>
            <div className="actions">
              <a className="button primary" href="#booking">Reserve a chair</a>
              <a className="button ghost" href="#services">View services</a>
            </div>
          </div>
          <aside className="heroCard">
            <span>Open today</span>
            <strong>9 AM - 7 PM</strong>
            <p>Walk-ins welcome. Appointments recommended for weekends.</p>
          </aside>
        </section>

        <section id="services" className="section">
          <div className="sectionHeading">
            <p className="eyebrow">Services</p>
            <h2>Built beyond a placeholder.</h2>
          </div>
          <div className="grid">
            {{services.map(([title, body]) => (
              <article key={{title}}>
                <h3>{{title}}</h3>
                <p>{{body}}</p>
              </article>
            ))}}
          </div>
        </section>

        <section id="proof" className="split section">
          <div>
            <p className="eyebrow">Proof</p>
            <h2>A launch-ready shape with room to grow.</h2>
            <p>
              This pass gives the site credible structure: hero, service menu,
              pricing, trust metrics, booking call-to-action, and consistent visual language.
            </p>
          </div>
          <div className="stats">
            <div><strong>4.9</strong><span>average rating</span></div>
            <div><strong>18</strong><span>weekly openings</span></div>
            <div><strong>12+</strong><span>years experience</span></div>
          </div>
        </section>

        <section id="pricing" className="section">
          <div className="sectionHeading">
            <p className="eyebrow">Pricing</p>
            <h2>Clear menu, no guessing.</h2>
          </div>
          <div className="priceList">
            {{prices.map(([name, price]) => (
              <div key={{name}}><span>{{name}}</span><strong>{{price}}</strong></div>
            ))}}
          </div>
        </section>

        <section id="booking" className="booking section">
          <div>
            <p className="eyebrow">Booking</p>
            <h2>Ready for real scheduling.</h2>
            <p>Wire this call-to-action into a backend, booking provider, or CRM during the next pass.</p>
          </div>
          <a className="button primary" href="mailto:hello@example.com">Request appointment</a>
        </section>
      </main>
    </>
  );
}}
"""
        globals_css = """:root {
  color-scheme: dark;
  --bg: #06080a;
  --panel: #10151b;
  --ink: #f8f4ed;
  --muted: #a89f96;
  --line: rgba(248, 244, 237, 0.13);
  --accent: #d45f39;
  --accent-2: #e6b451;
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  min-height: 100vh;
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: Arial, Helvetica, sans-serif;
}
a { color: inherit; text-decoration: none; }
.siteHeader {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px clamp(18px, 4vw, 56px);
  border-bottom: 1px solid var(--line);
  background: rgba(6, 8, 10, 0.9);
  backdrop-filter: blur(14px);
}
.brand { font-weight: 900; }
nav { display: flex; gap: 18px; color: var(--muted); }
.hero, .section {
  width: min(1160px, calc(100% - 36px));
  margin: 0 auto;
}
.hero {
  min-height: 72vh;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(270px, 360px);
  align-items: center;
  gap: clamp(28px, 5vw, 72px);
  padding: 72px 0 52px;
}
.eyebrow {
  margin: 0 0 12px;
  color: var(--accent-2);
  font-weight: 800;
  text-transform: uppercase;
  font-size: 0.78rem;
}
h1, h2, h3, p { letter-spacing: 0; }
h1 {
  max-width: 13ch;
  margin: 0;
  font-size: clamp(3rem, 9vw, 7rem);
  line-height: 0.9;
}
h2 {
  margin: 0;
  font-size: clamp(2rem, 5vw, 4rem);
  line-height: 1;
}
.lede, article p, .split p, .booking p {
  color: var(--muted);
  line-height: 1.7;
}
.actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 28px; }
.button {
  display: inline-flex;
  min-height: 46px;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 0 18px;
  font-weight: 800;
}
.primary { background: var(--accent); border-color: var(--accent); color: white; }
.ghost { background: transparent; }
.heroCard, article, .stats div, .priceList, .booking {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
}
.heroCard { padding: 28px; }
.heroCard span { color: var(--muted); }
.heroCard strong { display: block; margin: 8px 0; font-size: 2rem; }
.section { padding: 72px 0; }
.sectionHeading { display: grid; gap: 12px; margin-bottom: 28px; }
.grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
article { padding: 24px; min-height: 160px; }
.split, .booking {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(300px, 1.1fr);
  gap: 28px;
  align-items: center;
}
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.stats div { padding: 24px; }
.stats strong { display: block; font-size: 2.5rem; }
.stats span { color: var(--muted); }
.priceList { overflow: hidden; }
.priceList div {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 20px 24px;
  border-bottom: 1px solid var(--line);
}
.priceList div:last-child { border-bottom: 0; }
.booking { padding: 28px; }

@media (max-width: 840px) {
  nav { display: none; }
  .hero, .split, .booking { grid-template-columns: 1fr; }
  .grid { grid-template-columns: 1fr 1fr; }
  .stats { grid-template-columns: 1fr; }
}

@media (max-width: 560px) {
  .grid { grid-template-columns: 1fr; }
  h1 { font-size: 3.25rem; }
}
"""
        readme = f"""# {brand}

Next.js first complete pass generated by Aegis.

## Validate

```bash
npm install
npm run build
```
"""
        changes = [
            FileChange(action=action_for("app/page.tsx"), path="app/page.tsx", summary="Render the complete app shell from the Next page.", content=page_tsx),
            FileChange(action=action_for("app/layout.tsx"), path="app/layout.tsx", summary="Add metadata and a typed root layout.", content=layout_tsx),
            FileChange(action=action_for("app/globals.css"), path="app/globals.css", summary="Replace placeholder styles with complete responsive site styling.", content=globals_css),
            FileChange(action=action_for("components/app-shell.tsx"), path="components/app-shell.tsx", summary="Add the complete reusable site shell component.", content=app_shell),
            FileChange(action=action_for("README.md"), path="README.md", summary="Document install and validation commands.", content=readme),
        ]
        if include_package:
            package_json = f"""{{
  "scripts": {{
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  }},
  "dependencies": {{
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  }},
  "devDependencies": {{
    "@types/node": "^20.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "typescript": "^5.5.0"
  }}
}}
"""
            changes.insert(0, FileChange(action=action_for("package.json"), path="package.json", summary="Add Next.js package scripts and dependencies.", content=package_json))
        return changes

    def _cpp_console_starter(self) -> list[FileChange]:
        main_cpp = """#include <iostream>
#include <string>

int main(int argc, char** argv) {
    std::cout << "Hello, world!" << std::endl;

    if (argc > 1 && std::string(argv[1]) == "--no-wait") {
        return 0;
    }

    std::cout << "Press Enter to close...";
    std::string line;
    std::getline(std::cin, line);
    return 0;
}
"""
        cmake = """cmake_minimum_required(VERSION 3.20)
project(AegisConsoleApp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(AegisConsoleApp src/main.cpp)
"""
        build_py = '''from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    print(f"> {' '.join(command)}")
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
        **kwargs,
    )


def executable_candidates() -> list[Path]:
    names = ["AegisConsoleApp.exe", "AegisConsoleApp"]
    folders = [
        BUILD_DIR,
        BUILD_DIR / "Debug",
        BUILD_DIR / "Release",
        BUILD_DIR / "RelWithDebInfo",
    ]
    return [folder / name for folder in folders for name in names]


def main() -> int:
    if shutil.which("cmake") is None:
        print("CMake is required to build this project.", file=sys.stderr)
        return 2

    run(["cmake", "-S", ".", "-B", "build"])
    run(["cmake", "--build", "build", "--config", "Release"])

    executable = next((path for path in executable_candidates() if path.exists()), None)
    if executable is None:
        print("Build completed, but the generated executable was not found.", file=sys.stderr)
        return 3

    result = run([str(executable), "--no-wait"])
    print(result.stdout)
    if "Hello, world!" not in result.stdout:
        print("Executable did not print the expected hello-world output.", file=sys.stderr)
        return 4

    print("Build and smoke run passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
        readme = """# Aegis C++ Console App

A minimal C++17 console project generated by Aegis.

## Build And Smoke Test

Use the generated validator so Aegis can build and run the app with one safe command:

```powershell
python build.py
```

## Manual CMake Build

```powershell
cmake -S . -B build
cmake --build build --config Release
```

## Visual Studio

Open this folder with Visual Studio or generate a solution:

```powershell
cmake -S . -B build -G "Visual Studio 17 2022" -A x64
```
"""
        return [
            FileChange(action="create", path="README.md", summary="Document the C++ console project.", content=readme),
            FileChange(action="create", path="CMakeLists.txt", summary="Add CMake build configuration.", content=cmake),
            FileChange(action="create", path="src/main.cpp", summary="Create the C++ console entry point.", content=main_cpp),
            FileChange(action="create", path="build.py", summary="Add a safe one-command CMake build and smoke-run validator.", content=build_py),
            FileChange(action="create", path=".gitignore", summary="Ignore generated build outputs.", content="build/\n.vs/\nx64/\n"),
        ]

    def _cpp_msvc_console_starter(self, workspace_root: Path) -> list[FileChange]:
        from .project_scaffolder import ProjectScaffolder

        project_name = workspace_root.name.strip() or "aegis-console"
        files = ProjectScaffolder._cpp_msvc_console_template(project_name)
        summaries = {
            ".sln": "Create the Visual Studio solution file.",
            ".vcxproj": "Create the Visual Studio C++ project file.",
            ".filters": "Create Visual Studio source filters.",
            "src/main.cpp": "Create the C++ console entry point.",
            "build.py": "Add one-command MSBuild validation and smoke run.",
            ".gitignore": "Ignore generated Visual Studio build outputs.",
            "README.md": "Document the Visual Studio build and run flow.",
        }
        changes: list[FileChange] = []
        for path, content in files.items():
            summary = next((text for suffix, text in summaries.items() if path.endswith(suffix)), "Create Visual Studio console scaffold file.")
            changes.append(FileChange(action="create", path=path, summary=summary, content=content))
        return changes

    def _web_starter(self, kind: str) -> list[FileChange]:
        title = "Aegis Operations Dashboard" if kind == "dashboard" else "Aegis Project Studio"
        headline = "A grounded dashboard starter." if kind == "dashboard" else "Start the build with a strong first slice."
        html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
    <link rel="stylesheet" href="./styles.css" />
  </head>
  <body>
    <main class="shell">
      <section class="hero">
        <p>Aegis Starter</p>
        <h1>{headline}</h1>
        <button>Ready</button>
      </section>
    </main>
    <script src="./app.js"></script>
  </body>
</html>
"""
        css = """body {
  margin: 0;
  min-height: 100vh;
  font-family: "Segoe UI", system-ui, sans-serif;
  color: #171411;
  background: #f4f1ea;
}

.shell {
  width: min(960px, calc(100% - 32px));
  margin: 0 auto;
  padding: 72px 0;
}

.hero {
  border: 1px solid rgba(23, 20, 17, 0.1);
  border-radius: 8px;
  background: white;
  padding: 40px;
  box-shadow: 0 18px 42px rgba(23, 20, 17, 0.08);
}

p {
  color: #0c6b68;
  font-weight: 800;
  text-transform: uppercase;
}

h1 {
  max-width: 12ch;
  margin: 0 0 24px;
  font-size: clamp(2.5rem, 7vw, 5rem);
  line-height: 0.95;
}

button {
  min-height: 44px;
  border: 0;
  border-radius: 8px;
  padding: 0 18px;
  color: white;
  background: #0c6b68;
  font: inherit;
}
"""
        js = """const button = document.querySelector("button");

if (button) {
  button.addEventListener("click", () => {
    button.textContent = "Next feature queued";
  });
}
"""
        build_js = """const fs = require("fs");

for (const file of ["index.html", "styles.css", "app.js"]) {
  if (!fs.existsSync(file)) {
    throw new Error(`${file} is missing`);
  }
}

const html = fs.readFileSync("index.html", "utf8");
const css = fs.readFileSync("styles.css", "utf8");
const js = fs.readFileSync("app.js", "utf8");

if (!html.includes("styles.css") || !html.includes("app.js")) {
  throw new Error("index.html must reference styles.css and app.js");
}

if (!css.includes("@media") && !css.includes("clamp(")) {
  throw new Error("styles.css should include responsive styling");
}

if (!js.includes("addEventListener")) {
  throw new Error("app.js should include an interaction listener");
}

console.log("Static starter validation passed.");
"""
        readme = f"""# {title}

Generated by Aegis Core as a local starter.

## Validate

```powershell
node build.js
```
"""
        return [
            FileChange(action="create", path="README.md", summary="Describe the generated starter.", content=readme),
            FileChange(action="create", path="index.html", summary="Create the first page shell.", content=html),
            FileChange(action="create", path="styles.css", summary="Add the responsive visual base.", content=css),
            FileChange(action="create", path="app.js", summary="Wire a small interaction.", content=js),
            FileChange(action="create", path="build.js", summary="Add dependency-free static starter validation.", content=build_js),
        ]

    def _python_service_starter(self) -> list[FileChange]:
        main_py = """from fastapi import FastAPI

app = FastAPI(title="Aegis Service")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"ok": "true"}


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Aegis service starter is running."}
"""
        return [
            FileChange(action="create", path="README.md", summary="Document the service starter.", content="# Aegis Python Service Starter\n"),
            FileChange(action="create", path="requirements.txt", summary="Add backend dependencies.", content="fastapi\nuvicorn[standard]\n"),
            FileChange(action="create", path="app/main.py", summary="Create the starter FastAPI app.", content=main_py),
        ]

    def _python_app_starter(self) -> list[FileChange]:
        main_py = '''"""Small local application entrypoint generated by Aegis."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aegis-app")
    parser.add_argument("--name", default="Aegis App", help="Name to print in the startup message.")
    return parser


def run(name: str) -> str:
    return f"{name} is ready."


def main() -> None:
    args = build_parser().parse_args()
    print(run(args.name))


if __name__ == "__main__":
    main()
'''
        smoke_test = '''from aegis_app.main import run


def test_run_returns_ready_message() -> None:
    assert run("Demo App") == "Demo App is ready."
'''
        pyproject = '''[project]
name = "aegis-app"
version = "0.1.0"
description = "Local application starter generated by Aegis."
requires-python = ">=3.11"

[project.scripts]
aegis-app = "aegis_app.main:main"

[project.optional-dependencies]
dev = ["pytest"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
'''
        build_py = '''"""Dependency-light validation runner generated by Aegis."""

from __future__ import annotations

import compileall
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
ENTRY = SRC / "aegis_app" / "main.py"


def main() -> int:
    if not ENTRY.exists():
        print(f"Missing entrypoint: {ENTRY}", file=sys.stderr)
        return 1

    if not compileall.compile_dir(SRC, quiet=1):
        print("Python compile validation failed.", file=sys.stderr)
        return 1

    result = subprocess.run(
        [sys.executable, str(ENTRY), "--name", "Demo App"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=20,
    )
    print(result.stdout, end="")
    if result.returncode != 0:
        return result.returncode
    if "Demo App is ready." not in result.stdout:
        print("Smoke validation failed: expected greeting was not printed.", file=sys.stderr)
        return 1

    print("Python app validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
        readme = """# Aegis Application Starter

Generated by Aegis Core as a local application starter.

## Validate

```bash
python build.py
```
"""
        return [
            FileChange(action="create", path="README.md", summary="Document the local app starter.", content=readme),
            FileChange(action="create", path="pyproject.toml", summary="Add installable Python app metadata.", content=pyproject),
            FileChange(action="create", path="build.py", summary="Add dependency-free Python compile and smoke validation.", content=build_py),
            FileChange(action="create", path="src/aegis_app/__init__.py", summary="Create the package marker.", content=""),
            FileChange(action="create", path="src/aegis_app/main.py", summary="Create the local app entrypoint.", content=main_py),
            FileChange(action="create", path="tests/test_smoke.py", summary="Add a smoke test for the app entrypoint.", content=smoke_test),
        ]
