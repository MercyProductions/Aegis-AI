from __future__ import annotations

import json
import textwrap

from .project_scaffold_stack_rules import preset_stack_locks, stack_family_for_preset
from .project_scaffold_targets import title_from_name
from .schemas import ProjectScaffoldPreset


def roadmap_files(
    preset: ProjectScaffoldPreset,
    project_name: str,
    *,
    prompt: str,
    install_command: str,
    validation_command: str,
    max_repair_attempts: int,
) -> dict[str, str]:
    title = title_from_name(project_name)
    requested_goal = prompt or "No original prompt was attached to this project-builder request."
    install_line = install_command or "No install command configured."
    validation_line = validation_command or "No validation command configured."
    first_pass_checklist = "\n".join(f"- [ ] {item}" for item in first_product_pass_items(preset, prompt))
    return {
        ".aegis/ROADMAP.md": strip_doc(
            f"""
            # {title} Roadmap

            ## Original Goal

            {requested_goal}

            ## Selected Stack

            - Preset: {preset.label}
            - Framework: {preset.framework}
            - Language: {preset.language}
            - Package manager: {preset.package_manager or "manual"}

            ## Visible Build Loop

            1. Read the user goal and choose the closest supported stack.
            2. Generate the project structure and Aegis handoff metadata.
            3. Save install and validation commands into the project manifest.
            4. Write files through a checkpointed workspace operation.
            5. Run the validation command when requested and capture stdout/stderr.
            6. If validation fails, continue with up to {max_repair_attempts} repair attempt(s) in the chat agent.

            ## Commands

            Install:

            ```bash
            {install_line}
            ```

            Validate:

            ```bash
            {validation_line}
            ```

            ## First Product Pass

            {first_pass_checklist}

            ## Autopilot Rules

            - Keep every major change tied to validation output.
            - Repair build, syntax, or runtime failures before expanding scope.
            - When a checklist item is completed and validated, change only that item from [ ] to [x].
            """
        )
    }


def aegis_handoff_files(
    preset: ProjectScaffoldPreset,
    project_name: str,
    *,
    prompt: str,
    install_command: str,
    validation_command: str,
) -> dict[str, str]:
    title = title_from_name(project_name)
    first_pass_items = first_product_pass_items(preset, prompt)
    manifest = {
        "schema": "aegis.project.v1",
        "project_name": project_name,
        "title": title,
        "preset_id": preset.id,
        "preset_label": preset.label,
        "framework": preset.framework,
        "language": preset.language,
        "package_manager": preset.package_manager,
        "install_command": install_command,
        "validation_command": validation_command,
        "original_prompt": prompt,
        "tags": preset.tags,
        "generated_by": "Aegis Project Builder",
        "mission_contract": mission_contract(
            preset,
            project_name,
            prompt=prompt,
            install_command=install_command,
            validation_command=validation_command,
        ),
        "agent_handoff": {
            "primary_goal": "Turn the scaffold into a polished, working product through small checkpointed passes.",
            "first_pass": first_pass_items,
            "safety": [
                "Do not run destructive commands without an explicit user request.",
                "Keep generated secrets out of source control and use environment variables.",
                "Prefer small patches with validation after each meaningful change.",
            ],
        },
    }
    tags = ", ".join(preset.tags) if preset.tags else "none"
    return {
        ".aegis/project.json": json.dumps(manifest, indent=2) + "\n",
        "AGENTS.md": strip_doc(
            f"""
            # Aegis Agent Handoff

            Project: {title}
            Preset: {preset.label}
            Stack: {preset.framework} / {preset.language}
            Tags: {tags}

            ## User Goal

            {prompt or "No original prompt was attached to this project-builder request."}

            ## Commands

            Install dependencies:

            ```bash
            {install_command or "Add an install command for this stack."}
            ```

            Validate the project:

            ```bash
            {validation_command or "Add a validation command for this stack."}
            ```

            ## First Product Pass

            {numbered_list(first_pass_items)}

            ## Safety Notes

            - Do not commit secrets, tokens, local database files, or generated build artifacts.
            - Keep file writes inside this project workspace.
            - Ask before destructive cleanup, dependency removal, or broad rewrites.
            """
        ),
    }


def mission_contract(
    preset: ProjectScaffoldPreset,
    project_name: str,
    *,
    prompt: str,
    install_command: str,
    validation_command: str,
) -> dict[str, object]:
    return {
        "schema": "aegis.mission_contract.v1",
        "project_name": project_name,
        "preset_id": preset.id,
        "preset_label": preset.label,
        "stack_family": stack_family_for_preset(preset.id),
        "stack_locks": sorted(preset_stack_locks(preset.id)),
        "framework": preset.framework,
        "language": preset.language,
        "package_manager": preset.package_manager,
        "original_prompt": prompt,
        "install_command": install_command,
        "validation_command": validation_command,
        "continuity_policy": (
            "Reuse this project stack for follow-up prompts unless the user clearly asks for a new project, "
            "migration, rewrite, or stack conversion."
        ),
    }


def numbered_list(items: list[str]) -> str:
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))


def first_product_pass_items(preset: ProjectScaffoldPreset, prompt: str) -> list[str]:
    lowered = f"{preset.id} {' '.join(preset.tags)} {prompt}".lower()

    if any(term in lowered for term in ("barber", "barbershop", "haircut", "fade", "beard", "shave")):
        return [
            "Turn the first screen into a complete barber landing flow with services, trust signals, hours, and clear booking calls to action.",
            "Wire the booking/contact interaction so name, service, time, and contact fields give visible validation or confirmation feedback.",
            "Add realistic barber-specific copy for services, pricing, testimonials, location, and appointment expectations.",
            "Validate the site and fix layout, TypeScript, CSS, or asset errors before marking the page ready.",
        ]

    if preset.id in {"nextjs-ts-tailwind", "vite-react-ts", "static-html-site"}:
        return [
            "Build the requested website content into full responsive sections instead of leaving generic placeholder copy.",
            "Add one working user interaction such as contact, booking, filtering, navigation, or form feedback.",
            "Polish mobile and desktop spacing, empty states, hover states, and accessible labels around the primary workflow.",
            "Run the saved validation command and repair any syntax, type, or stylesheet issues.",
        ]

    if preset.id in {"node-fullstack-js", "express-ts-api", "fastapi-python-api", "go-http-api", "dotnet-webapi-csharp", "django-python-web"}:
        return [
            "Implement the first real API or full-stack workflow with route handlers, input validation, and realistic sample data.",
            "Connect the workflow to storage, in-memory state, or the scaffolded persistence layer with clear error responses.",
            "Add a smoke test or self-test that exercises the main happy path and one invalid-input path.",
            "Run install and validation commands, then repair failing imports, scripts, schema, or server startup errors.",
        ]

    if preset.id in {"sqlite-python-db"}:
        return [
            "Expand the schema around the requested domain with primary keys, indexes, seed data, and a practical report query.",
            "Add a migration or reset script that can rebuild the local database from source files.",
            "Add a validation script that runs schema creation, seed loading, and at least one report query.",
            "Document safe backup, restore, and destructive reset expectations before broader data work.",
        ]

    if preset.id in {"cpp-cmake-cli", "cpp-msvc-console-sln", "dotnet-console-csharp", "rust-cli", "node-cli-js", "python-cli", "powershell-module"}:
        return [
            "Complete the requested command-line behavior with argument handling, console output, and a deterministic smoke path.",
            "Add or update the build/self-test script so validation compiles or runs the tool without manual steps.",
            "Document how to build, run, and verify the executable from a clean terminal.",
            "Run validation and repair compiler, script, path, or missing-entry-point errors.",
        ]

    if preset.id in {"cpp-cmake-dll"}:
        return [
            "Define the exported API surface with headers, versioning notes, and a small host-side smoke test.",
            "Implement safe input validation and predictable error returns for the first exported function.",
            "Add a build/test path that compiles the DLL and verifies exports or the smoke host.",
            "Document ABI, architecture, and runtime dependency expectations before adding more exports.",
        ]

    if preset.id in {"cpp-imgui-win32-dx11"}:
        return [
            "Build the first real ImGui tool panel with state, controls, status output, and a clear game/tooling workflow.",
            "Separate UI state, rendering, and backend logic so future panels can be added without a rewrite.",
            "Add a smoke build path and document required Windows SDK, compiler, and graphics dependencies.",
            "Validate the project and repair CMake, Win32, DirectX, or entry-point errors before adding visual polish.",
        ]

    if preset.id in {"cpp-game-loop-cmake"}:
        return [
            "Implement the first playable or inspectable game loop slice with update, render, input, timing, and shutdown paths.",
            "Add simple entity/state data that proves the loop can evolve into a larger game or simulation.",
            "Create a smoke test around deterministic engine state or frame-step behavior.",
            "Run validation and repair compiler, CMake, or platform errors before adding more systems.",
        ]

    if preset.id in {"python-game-file-analyzer"}:
        return [
            "Implement file inspection for the requested game or asset format with safe reads, metadata extraction, and clear reports.",
            "Add sample fixtures or generated binary test data that can validate parser behavior without private game files.",
            "Report offsets, sizes, signatures, entropy, and suspected structures without modifying source assets.",
            "Run validation and repair parser, CLI, fixture, or report-generation errors.",
        ]

    if preset.id in {"cpp-windows-internals-hooking"}:
        return [
            "Build the authorized Windows internals diagnostics workflow with process/module enumeration and clear status output.",
            "Keep any MinHook or hooking examples limited to owned test processes and documented diagnostic use cases.",
            "Add build-time checks and a smoke test or dry-run mode that avoids modifying unrelated processes.",
            "Validate the project and repair compiler, linker, architecture, or Windows SDK errors.",
        ]

    if preset.id in {"python-sln-refactor-tool"}:
        return [
            "Implement solution/project discovery for .sln, .vcxproj, .csproj, and shared property files.",
            "Add dry-run merge, split, and extraction reports that list exact files and references before any write.",
            "Add fixtures covering two-project merge and single-project extraction scenarios.",
            "Run validation and repair parser, path, or project-reference errors before enabling write mode.",
        ]

    if preset.id in {"windows-kernel-driver-controller"}:
        return [
            "Complete the safe controller/driver sample handshake with explicit IOCTL definitions and user-mode validation.",
            "Keep driver behavior limited to owned sample communication, diagnostics, and documented development flows.",
            "Add build, signing, deployment, and test-mode notes without hiding or bypassing platform protections.",
            "Validate what can be built locally and capture any missing WDK, SDK, signing, or configuration blockers.",
        ]

    if preset.id in {"electron-react-ts", "tauri-react-ts", "python-tkinter-desktop", "dotnet-wpf-csharp"}:
        return [
            "Implement the first complete desktop workflow with navigation, state, error feedback, and saved settings or sample data.",
            "Wire the native/backend bridge or local service boundary with typed request and response handling.",
            "Polish default and fullscreen layouts so the app feels usable before adding secondary features.",
            "Run validation and repair packaging, bridge, build, or UI type errors.",
        ]

    if preset.id in {"expo-react-native-ts"}:
        return [
            "Implement the first mobile workflow with navigation, state, form validation, and platform-safe styling.",
            "Add realistic sample data and empty/loading/error states for the main screen.",
            "Check small-screen layout constraints before broad visual polish.",
            "Run validation and repair Metro, TypeScript, package, or platform configuration errors.",
        ]

    return [
        "Replace starter copy, placeholder state, and sample data with the user's requested product behavior.",
        "Add the first end-to-end workflow before broad visual polish.",
        "Add or update validation coverage around the first real feature.",
        "Run validation and repair build, syntax, or runtime errors before expanding scope.",
    ]


def strip_doc(value: str) -> str:
    return textwrap.dedent(value).strip() + "\n"
