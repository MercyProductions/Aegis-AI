from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .agent import continue_from_roadmap, repair_from_last_validation
from .config import load_config, write_default_config
from .ecosystem import dashboard_summary, diagnostics_summary, shared_memory_summary
from .ollama import OllamaClient
from .roadmap import generate_roadmap
from .tasks import create_task, list_tasks
from .validation import run_validation, validation_summary
from .workspace import WorkspaceScanner


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    json_requested = "--json" in raw_args
    if json_requested:
        raw_args = [arg for arg in raw_args if arg != "--json"]

    parser = argparse.ArgumentParser(prog="aegis", description="Aegis Core local-first runtime CLI")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    for name in ("health", "scan", "roadmap", "validate", "continue", "repair", "config", "dashboard", "memory", "diagnostics", "tasks"):
        sub = subcommands.add_parser(name)
        sub.add_argument("--workspace", default=".", help="Workspace/project root.")
        if name == "validate":
            sub.add_argument("--run", action="store_true", help="Run the first detected validation command.")
        if name == "continue":
            sub.add_argument("request", nargs="?", help="Optional task request.")
        if name == "tasks":
            sub.add_argument("--create", help="Create a shared task visible to every Aegis client.")
            sub.add_argument("--kind", default="general", help="Task kind.")
            sub.add_argument("--source-client", default="cli", help="Client that created the task.")

    args = parser.parse_args(raw_args)
    args.json = args.json or json_requested
    workspace = Path(args.workspace).resolve()

    if args.command == "health":
        config = load_config(workspace)
        result = {"workspace": str(workspace), "config": config.to_dict(), "ollama": OllamaClient(config).health().__dict__}
    elif args.command == "scan":
        result = WorkspaceScanner(workspace).scan(persist=True)
    elif args.command == "roadmap":
        result = generate_roadmap(workspace, persist=True)
    elif args.command == "validate":
        result = run_validation(workspace) if args.run else validation_summary(workspace)
    elif args.command == "continue":
        result = continue_from_roadmap(workspace, args.request)
    elif args.command == "repair":
        result = repair_from_last_validation(workspace)
    elif args.command == "config":
        result = {"path": str(write_default_config(workspace))}
    elif args.command == "dashboard":
        result = dashboard_summary(workspace)
    elif args.command == "memory":
        result = shared_memory_summary(workspace)
    elif args.command == "diagnostics":
        result = diagnostics_summary(workspace)
    elif args.command == "tasks":
        if args.create:
            result = create_task(workspace, args.create, kind=args.kind, source_client=args.source_client)
        else:
            result = {"tasks": list_tasks(workspace)}
    else:
        parser.error(f"Unknown command {args.command}")
        return 2

    print_result(result, command=args.command, as_json=args.json)
    return 0


def print_result(result: dict[str, Any], command: str, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    if command == "scan":
        print(f"workspace: {result.get('workspace')}")
        print(f"frameworks: {', '.join(result.get('frameworks', []))}")
        print(f"file_count: {result.get('file_count')}")
        print("build_files:")
        for item in result.get("build_files", [])[:15]:
            print(f"  - {item}")
        print("memory: .aegis/project-summary.md, .aegis/architecture-map.md, .aegis/file-index.json")
        return

    if command == "roadmap":
        print(result.get("markdown", "").rstrip())
        if result.get("roadmap_path"):
            print(f"\nroadmap_path: {result['roadmap_path']}")
        return

    for key, value in result.items():
        if isinstance(value, (dict, list)):
            print(f"{key}:")
            print(json.dumps(value, indent=2, sort_keys=True))
        else:
            print(f"{key}: {value}")


if __name__ == "__main__":
    raise SystemExit(main())
