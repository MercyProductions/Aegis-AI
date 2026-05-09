from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .agent import continue_from_roadmap, repair_from_last_validation
from .config import load_config, write_default_config
from .ecosystem import dashboard_summary, diagnostics_summary, shared_memory_summary
from .jobs import jobs_dashboard, run_job
from .knowledge import knowledge_graph, query_knowledge_graph
from .model_router import provider_inventory, route_model
from .multi_agent import agent_roster
from .ollama import OllamaClient
from .orchestration import advance_orchestration_step, create_orchestration_plan, orchestration_dashboard
from .quality import quality_dashboard, record_quality_snapshot
from .roadmap import generate_roadmap
from .simulation import compare_scenarios, simulate_change
from .tasks import TaskStorePersistenceError, create_task, list_tasks
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

    for name in (
        "health",
        "scan",
        "roadmap",
        "validate",
        "continue",
        "repair",
        "config",
        "dashboard",
        "memory",
        "diagnostics",
        "tasks",
        "providers",
        "agents",
        "jobs",
        "quality",
        "knowledge",
        "simulate",
        "route",
        "orchestrate",
    ):
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
        if name == "route":
            sub.add_argument("--task-type", default="chat", help="Task role such as simple_explanation, code_completion, repo_wide_planning, hard_debugging, or embeddings_search.")
            sub.add_argument("--difficulty", default=None, help="Optional difficulty label: simple, medium, or hard.")
            sub.add_argument("--allow-cloud", action="store_true", help="Allow a cloud route to be considered after visible approval.")
            sub.add_argument("--cloud-approved", action="store_true", help="Confirm the user approved sending sanitized context to cloud.")
        if name == "orchestrate":
            sub.add_argument("--goal", help="Create a new approval-gated orchestration goal.")
            sub.add_argument("--source-client", default="cli", help="Client creating the orchestration goal.")
            sub.add_argument("--step", help="Advance the active orchestration task with an action such as inspect, plan, propose, approve, apply, validate, or complete.")
            sub.add_argument("--task-id", help="Optional orchestration task id to advance.")
            sub.add_argument("--approval", action="store_true", help="Confirm approval for an approval-gated orchestration step.")
            sub.add_argument("--summary", help="Optional step summary.")
        if name == "jobs":
            sub.add_argument("--run", dest="job_id", help="Run one maintenance job by id.")
            sub.add_argument("--trigger", help="Run all maintenance jobs for a trigger such as project_opened or build_failed.")
            sub.add_argument("--due", action="store_true", help="Run all due scheduled maintenance jobs.")
            sub.add_argument("--approval", action="store_true", help="Approve risky job actions such as build/test commands.")
        if name == "quality":
            sub.add_argument("--record", action="store_true", help="Record a health snapshot and update quality reports.")
        if name == "knowledge":
            sub.add_argument("--record", action="store_true", help="Persist the knowledge graph and generated summary.")
            sub.add_argument("--query", help="Ask a rule-based question against the knowledge graph.")
            sub.add_argument("--focus", help="Optional file path, API route, or system focus for a knowledge query.")
        if name == "simulate":
            sub.add_argument("--objective", required=True, help="Planned change or roadmap item to simulate.")
            sub.add_argument("--file", dest="files", action="append", default=[], help="Optional focus file. Can be supplied more than once.")
            sub.add_argument("--approach", action="append", default=[], help="Implementation approach. Supply more than once to compare scenarios.")

    args = parser.parse_args(raw_args)
    args.json = args.json or json_requested
    workspace = Path(args.workspace).resolve()

    try:
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
        elif args.command == "providers":
            result = provider_inventory(workspace)
        elif args.command == "agents":
            result = agent_roster()
        elif args.command == "jobs":
            if args.job_id or args.trigger or args.due:
                result = run_job(
                    workspace,
                    job_id=args.job_id,
                    trigger=args.trigger,
                    approval=args.approval,
                    run_due=args.due,
                )
            else:
                result = jobs_dashboard(workspace)
        elif args.command == "quality":
            result = record_quality_snapshot(workspace) if args.record else quality_dashboard(workspace)
        elif args.command == "knowledge":
            if args.query:
                result = query_knowledge_graph(workspace, args.query, focus=args.focus)
            else:
                result = knowledge_graph(workspace, persist=args.record)
        elif args.command == "simulate":
            if len(args.approach) > 1:
                result = compare_scenarios(workspace, args.objective, args.approach, files=args.files)
            else:
                result = simulate_change(workspace, args.objective, files=args.files, approach=args.approach[0] if args.approach else None)
        elif args.command == "route":
            result = route_model(
                workspace,
                args.task_type,
                args.difficulty,
                allow_cloud=args.allow_cloud,
                cloud_approved=args.cloud_approved,
            )
        elif args.command == "orchestrate":
            if args.goal:
                result = create_orchestration_plan(workspace, args.goal, source_client=args.source_client)
            elif args.step:
                result = advance_orchestration_step(
                    workspace,
                    task_id=args.task_id,
                    action=args.step,
                    approval=args.approval,
                    summary=args.summary,
                )
            else:
                result = orchestration_dashboard(workspace)
        else:
            parser.error(f"Unknown command {args.command}")
            return 2
    except (TaskStorePersistenceError, ValueError) as exc:
        print_error(str(exc), command=args.command, workspace=workspace, as_json=args.json)
        return 1

    print_result(result, command=args.command, as_json=args.json)
    return 0


def print_error(message: str, command: str, workspace: Path, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps({"ok": False, "command": command, "workspace": str(workspace), "error": message}, indent=2, sort_keys=True))
        return
    print(f"error: {message}", file=sys.stderr)


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
