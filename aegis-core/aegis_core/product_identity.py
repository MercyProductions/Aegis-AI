from __future__ import annotations

from typing import Any

from .memory import utc_now


PRODUCT_NAME = "Auralith OS"
CORE_RUNTIME_NAME = "Aegis Core"
ASSISTANT_NAME = "Auralith Prime"


def product_identity() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "product": {
            "name": PRODUCT_NAME,
            "category": "local-first AI engineering operating environment",
            "core_runtime": CORE_RUNTIME_NAME,
            "assistant": ASSISTANT_NAME,
            "legacy_aliases": ["Aegis", "Aegis AI", "Aegis Local Agent"],
            "one_sentence": "Auralith OS is a local-first command environment for understanding, changing, validating, and recovering real software projects.",
        },
        "is": [
            "A local-first engineering workspace centered on user-owned projects.",
            "A shared runtime authority where Website, Desktop, VS Code, and Visual Studio clients consume the same Core contracts.",
            "An approval-aware workflow system for scanning, planning, implementing, validating, repairing, checkpointing, and rolling back work.",
            "A privacy-forward environment that prefers local models and makes cloud routing explicit.",
            "A persistent project intelligence layer that keeps workspace knowledge inspectable and editable.",
        ],
        "is_not": [
            "Not a cloud-first SaaS conversion.",
            "Not an unrestricted autonomous coding system.",
            "Not a replacement for source control, CI, or human code review.",
            "Not a production deployment bot that acts without explicit approval.",
            "Not a loose collection of unrelated panels, labs, and agents.",
        ],
        "target_users": [
            {
                "segment": "solo_local_developer",
                "description": "Developers who want a private local assistant with project awareness, safe edits, checkpoints, and validation.",
            },
            {
                "segment": "power_user_engineer",
                "description": "Engineers who want structured planning, repair loops, model routing, and cross-client continuity.",
            },
            {
                "segment": "small_team_or_studio",
                "description": "Teams that want local-first workflow supervision and optional trusted runtime nodes without SaaS lock-in.",
            },
            {
                "segment": "extension_first_user",
                "description": "VS Code or Visual Studio users who want Core-backed workflows inside their existing IDE.",
            },
        ],
        "primary_workflows": [
            "open_workspace",
            "scan_project",
            "explain_architecture",
            "generate_roadmap",
            "propose_change",
            "review_diff_and_risk",
            "create_checkpoint",
            "apply_changes",
            "run_validation",
            "repair_failure",
            "rollback",
            "validate_deployment",
        ],
        "supported_environments": [
            "Aegis Core local service",
            "Website protected workspace",
            "Native Desktop app",
            "VS Code extension",
            "Visual Studio extension",
            "Ollama local models",
            "optional cloud providers through explicit routing policy",
            "optional trusted runtime nodes",
        ],
        "local_first_philosophy": {
            "default": "Local workspace authority, local state, local audit logs, and local model preference.",
            "cloud_policy": "Cloud providers are optional and must disclose provider, model, privacy risk, and fallback chain.",
            "file_policy": "All writes require normalized workspace paths, checkpoint readiness, safety gates, and rollback availability.",
            "memory_policy": "Memory is transparent, editable, exportable, deletable, and scoped by user/project controls.",
        },
        "privacy_security_positioning": [
            "Local-only mode must be obvious during onboarding and runtime.",
            "Provider keys must stay out of plaintext project state and logs.",
            "Sensitive files should be excluded from prompts unless explicitly approved.",
            "All autonomous or semi-autonomous workflows must remain inspectable, reversible, and approval-aware.",
            "Distributed runtimes are opt-in trusted nodes, not a cloud control plane.",
        ],
        "terminology": terminology(),
        "client_positioning": {
            "website": "Product shell, account/session UX, runtime gateway, supervision UI, and docs-facing experience.",
            "desktop": "Native local command center and runtime status surface.",
            "vscode": "IDE-native Core client for workspace-aware command, diff, validation, and rollback flows.",
            "visual_studio": "Solution-aware Core client with MSBuild, startup project, diagnostics, and safe-edit strengths.",
            "core": "Shared runtime authority and contract source of truth.",
        },
    }


def terminology() -> dict[str, str]:
    return {
        "product": PRODUCT_NAME,
        "assistant": ASSISTANT_NAME,
        "core_runtime": CORE_RUNTIME_NAME,
        "runtime": "Runtime",
        "workflow": "Workflow",
        "task_graph": "Workflow graph",
        "agent": "Auralith agent",
        "agents": "Auralith agents",
        "checkpoint": "Checkpoint",
        "rollback": "Rollback",
        "validation": "Validation",
        "repair": "Repair",
        "quality_gate": "Quality gate",
        "memory": "Memory",
        "workspace_intelligence": "Workspace intelligence",
        "distributed_node": "Trusted runtime node",
        "experimental_area": "Experimental Labs",
    }


def feature_catalog() -> dict[str, Any]:
    categories = {
        "core_product_features": [
            _feature("local_chat", "Local assistant chat", "stable", "Basic Local Assistant", "Local-first coding help, explanations, and workspace-aware answers."),
            _feature("workspace_scan", "Workspace scan", "stable", "Engineering Workspace", "Project files, frameworks, validation commands, and basic architecture metadata."),
            _feature("roadmap_generation", "Roadmap generation", "stable", "Engineering Workspace", "Project-aware planning with persisted roadmap memory."),
            _feature("safe_apply", "Safe Apply", "stable", "Engineering Workspace", "Preview, checkpoint, apply, validation, and rollback path for proposed file changes."),
            _feature("validation", "Validation", "stable", "Engineering Workspace", "Detected local validation commands with redacted logs and stored results."),
            _feature("core_model_registry", "Core model registry", "stable", "Engineering Workspace", "Provider/model inventory, routing profiles, health, and route explanation."),
            _feature("runtime_status", "Runtime status", "stable", "Basic Local Assistant", "Core, Website, Ollama, active workflow, fallback, and client registration visibility."),
        ],
        "advanced_features": [
            _feature("quality_gates", "Quality gates", "advanced", "Autonomous Engineering", "Pre-apply scoring, blockers, risk, validation evidence, and evaluation reports."),
            _feature("engineering_execution", "Engineering execution pipeline", "advanced", "Autonomous Engineering", "Structured intake, planning, implementation, validation, repair, approval, and summary stages."),
            _feature("agent_supervision", "Agent supervision", "advanced", "Autonomous Engineering", "Role-based agents, handoffs, approval gates, logs, and workflow timeline visibility."),
            _feature("knowledge_graph", "Workspace knowledge graph", "advanced", "Engineering Workspace", "Persistent files, symbols, relationships, impact analysis, and architecture summaries."),
            _feature("deployment_validation", "Deployment validation", "advanced", "Engineering Workspace", "CI/CD and environment analysis without automatic production deployment."),
        ],
        "experimental_systems": [
            _feature("distributed_runtime", "Distributed runtime nodes", "experimental", "Distributed Runtime", "Trusted node registration, workload scheduling, and fallback execution."),
            _feature("plugin_ecosystem", "Plugin ecosystem", "experimental", "Experimental Labs", "Plugin manifests, tools, hooks, permissions, and diagnostics."),
            _feature("system_optimization", "System optimization", "experimental", "Experimental Labs", "Benchmark-driven routing, workflow, validation, and plugin recommendations."),
            _feature("voice_interaction", "Voice interaction", "prototype", "Experimental Labs", "Provider-neutral push-to-talk and voice command contracts."),
            _feature("collaboration_sessions", "Collaboration sessions", "prototype", "Experimental Labs", "Shared local-first workflow visibility without SaaS multi-tenancy."),
        ],
        "developer_internal_systems": [
            _feature("stabilization_audit", "Stabilization audit", "internal", "Developer/Internal", "Static production-readiness, contract, monolith, recovery, and release-gate audit."),
            _feature("release_packaging", "Release packaging and updates", "internal", "Developer/Internal", "Version manifest, package outputs, update plan, rollback, and migration support."),
            _feature("security_audit", "Security hardening checks", "internal", "Developer/Internal", "Local API, credential, update, privacy, and audit-log posture."),
            _feature("benchmark_suites", "Benchmark suites", "internal", "Developer/Internal", "Quality, routing, validation, repair, and handoff measurement."),
        ],
        "deprecated_systems": [
            _feature("website_owned_runtime", "Website-owned runtime workflow ownership", "deprecated", "Compatibility Fallback", "Website should keep API compatibility while delegating apply/checkpoint/validation to Core."),
            _feature("client_owned_model_truth", "Client-owned model/provider truth", "deprecated", "Compatibility Fallback", "Clients should consume Core registry and routing explanations."),
            _feature("local_extension_monoliths", "Extension monolith runtime ownership", "deprecated", "Compatibility Fallback", "Large extension.js style logic should become command adapters around Core contracts."),
        ],
    }
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "classification": categories,
        "default_visible_categories": ["core_product_features", "advanced_features"],
        "hidden_by_default": ["experimental_systems", "developer_internal_systems", "deprecated_systems"],
        "product_rule": "Features are product-visible only when they have a clear workflow, safety story, client surface, docs, and tests.",
    }


def product_modes() -> dict[str, Any]:
    modes = [
        {
            "id": "basic_local_assistant",
            "name": "Basic Local Assistant",
            "stability": "stable",
            "default_for_first_run": True,
            "audience": "New local-first users.",
            "capabilities": ["local_chat", "model_setup", "workspace_open", "explain_code", "runtime_status"],
            "hidden_capabilities": ["distributed_runtime", "plugin_labs", "autonomous_apply"],
            "safety": ["local-only visible", "no automatic file writes", "clear model/provider status"],
        },
        {
            "id": "engineering_workspace",
            "name": "Engineering Workspace",
            "stability": "stable",
            "default_for_first_run": False,
            "audience": "Daily project work.",
            "capabilities": ["workspace_scan", "architecture_summary", "roadmap", "safe_apply", "validation", "checkpoint", "rollback"],
            "safety": ["checkpoint before apply", "diff preview", "validation result storage", "rollback visible"],
        },
        {
            "id": "autonomous_engineering",
            "name": "Autonomous Engineering",
            "stability": "advanced",
            "default_for_first_run": False,
            "audience": "Users who want supervised multi-step workflows.",
            "capabilities": ["workflow_graph", "agent_supervision", "quality_gates", "repair_loops", "approval_queue"],
            "safety": ["approval gates", "iteration limits", "quality blockers", "human review required for risky changes"],
        },
        {
            "id": "distributed_runtime",
            "name": "Distributed Runtime",
            "stability": "experimental",
            "default_for_first_run": False,
            "audience": "Power users with trusted worker machines.",
            "capabilities": ["node_registration", "distributed_validation", "indexing_offload", "gpu_model_node"],
            "safety": ["opt-in nodes", "trust levels", "local fallback", "permission scopes"],
        },
        {
            "id": "experimental_labs",
            "name": "Experimental Labs",
            "stability": "experimental",
            "default_for_first_run": False,
            "audience": "Developers testing future capabilities.",
            "capabilities": ["plugins", "voice", "optimization", "collaboration_sessions", "media_generation"],
            "safety": ["hidden by default", "explicit enablement", "proposal-only where possible", "not launch-critical"],
        },
    ]
    return {"schema_version": 1, "generated_at": utc_now(), "default_mode": "basic_local_assistant", "recommended_daily_mode": "engineering_workspace", "modes": modes}


def workflow_catalog() -> dict[str, Any]:
    workflows = [
        _workflow("open_workspace", "Open Workspace", "Basic Local Assistant", [("select_workspace", "Choose a local project root."), ("check_permissions", "Confirm read/write permissions."), ("show_runtime_status", "Display Core, Website, Ollama, and fallback status.")], ["workspace path must be local", "Core state remains under .aegis"]),
        _workflow("scan_project", "Scan Project", "Engineering Workspace", [("index_files", "Detect files, frameworks, build systems, and validation commands."), ("summarize_architecture", "Generate architecture and entry-point summary."), ("store_memory", "Persist reusable project intelligence.")], ["no file writes outside .aegis", "unsupported languages reported clearly"]),
        _workflow("generate_roadmap", "Generate Roadmap", "Engineering Workspace", [("read_scan", "Use workspace intelligence."), ("create_phases", "Create phases with status and validation expectations."), ("persist_roadmap", "Store roadmap memory.")], ["roadmap is advisory", "execution requires separate approval"]),
        _workflow("implement_feature", "Implement Feature", "Autonomous Engineering", [("intake", "Capture goal, constraints, target files, and risk."), ("plan", "Create execution plan and subtasks."), ("propose_changes", "Create diff preview without applying."), ("quality_gate", "Evaluate risk and validation requirements."), ("approve_apply", "User approves before checkpoint/apply.")], ["checkpoint required", "diff/risk review required", "quality blockers respected"]),
        _workflow("validate", "Validate", "Engineering Workspace", [("detect_command", "Choose local validation command."), ("run_command", "Stream and store output."), ("summarize_result", "Record pass/fail and next repair target.")], ["safe command allowlist", "timeout", "secret redaction"]),
        _workflow("repair", "Repair", "Autonomous Engineering", [("inspect_failure", "Read validation/build errors."), ("target_scope", "Find likely files and dependencies."), ("propose_repair", "Generate repair proposal."), ("revalidate", "Run focused validation after approval.")], ["retry limits", "approval before apply", "rollback available"]),
        _workflow("checkpoint", "Checkpoint", "Engineering Workspace", [("normalize_paths", "Resolve target files inside workspace."), ("capture_files", "Copy current file state."), ("write_manifest", "Persist checkpoint metadata.")], ["reject outside workspace", "keep backups", "operation audit"]),
        _workflow("deploy", "Deployment Validation", "Engineering Workspace", [("detect_pipeline", "Detect CI/CD and runtime configs."), ("evaluate_risk", "Check secrets, missing gates, rollback readiness."), ("dry_run_plan", "Create deployment plan without production action.")], ["dry-run by default", "production approval required", "rollback strategy required"]),
        _workflow("rollback", "Rollback", "Engineering Workspace", [("select_checkpoint", "Choose restore point."), ("preview_restore", "Show affected files."), ("restore", "Restore from checkpoint with pre-restore backup."), ("validate", "Run validation after restore.")], ["checkpoint required", "pre-restore backup", "operation audit"]),
    ]
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "workflows": workflows,
        "workflow_order": [item["id"] for item in workflows],
        "simplification_rule": "Expose the happy path first: Workspace, Plan, Changes, Validate, Memory, Runtime. Move labs and governance behind advanced surfaces.",
    }


def launch_scope() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "recommended_launch_scope": {
            "include": ["Basic Local Assistant", "Engineering Workspace", "supervised subset of Autonomous Engineering"],
            "exclude_from_default": ["Distributed Runtime", "Experimental Labs", "voice interaction", "untrusted plugin execution", "production deployment execution"],
            "positioning": "Launch as a safe local-first engineering operating environment, not a fully autonomous platform.",
        },
        "showcase_workflows": showcase_workflows()["showcase_workflows"],
        "known_limitations": [
            "Large monoliths still need extraction before aggressive UI expansion.",
            "Distributed runtime should remain opt-in and experimental.",
            "Plugin execution should remain permission-gated and mostly proposal-oriented until isolation is hardened.",
            "Deployment workflows validate and plan; production deploy must remain explicit and gated.",
            "Website, Desktop, VS Code, and Visual Studio still contain compatibility fallback logic.",
        ],
        "launch_readiness_gates": [
            "Core, Website backend, frontend, Desktop, VS Code, and Visual Studio smoke tests pass.",
            "Onboarding local-only setup is understandable without reading docs.",
            "Safe Apply, checkpoint, validation, repair, and rollback are visibly connected.",
            "Stable/advanced/experimental modes are visible and respected by UI navigation.",
            "Known limitations and recovery steps are documented.",
        ],
    }


def showcase_workflows() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "showcase_workflows": [
            _showcase("generate_feature", "Generate a small feature safely", "Add a narrow UI or backend improvement with diff preview, checkpoint, validation, and completion summary."),
            _showcase("repair_failing_build", "Repair a failing build", "Read build output, propose targeted fix, apply after approval, rerun validation, and store repair history."),
            _showcase("explain_architecture", "Explain architecture", "Scan the workspace and present runtime boundaries, entry points, dependencies, and risk areas."),
            _showcase("roadmap_execution", "Execute one roadmap item", "Select a roadmap phase, create an execution plan, propose changes, validate, and mark status."),
            _showcase("deployment_validation", "Validate deployment readiness", "Inspect CI/CD and environment config, detect missing gates or secret risks, and generate a dry-run release plan."),
            _showcase("rollback_after_failure", "Rollback after failure", "Restore from checkpoint, preserve pre-restore backup, rerun validation, and summarize the recovery."),
        ],
    }


def roadmap_governance() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "stable_roadmap": [
            "Polish first-run local-only setup.",
            "Make Workspace, Plan, Changes, Validate, Memory, and Runtime the primary navigation spine.",
            "Finish monolith extraction for Website App.tsx, Desktop AegisChatApp.cpp, VS Code extension.js, and Website backend route/services.",
            "Lock Core contract snapshots for stable launch workflows.",
        ],
        "experimental_roadmap": [
            "Keep Distributed Runtime, Plugin Ecosystem, System Optimization, Voice, and Collaboration in Experimental Labs.",
            "Require explicit enablement and visible risk labels.",
            "Prefer proposal-only behavior until validation and isolation are stronger.",
        ],
        "research_ideas": [
            "Hybrid graph/vector search.",
            "Richer workflow replay visualization.",
            "Team approval delegation.",
            "Provider-neutral local voice stack.",
        ],
        "future_concepts": [
            "Organization policy packs.",
            "Signed plugin marketplace.",
            "Remote trusted GPU worker bundles.",
            "Long-running roadmap execution with scheduled validation windows.",
        ],
        "governance_rule": "A feature moves toward stable only when it has a named workflow, safety gates, tests, docs, recovery behavior, and clear client ownership.",
    }


def product_catalog() -> dict[str, Any]:
    return {
        "identity": product_identity(),
        "features": feature_catalog(),
        "modes": product_modes(),
        "workflows": workflow_catalog(),
        "showcase": showcase_workflows(),
        "launch_scope": launch_scope(),
        "roadmap": roadmap_governance(),
    }


def _feature(feature_id: str, name: str, stability: str, mode: str, description: str) -> dict[str, str]:
    return {"id": feature_id, "name": name, "stability": stability, "mode": mode, "description": description}


def _workflow(workflow_id: str, name: str, mode: str, steps: list[tuple[str, str]], safety: list[str]) -> dict[str, Any]:
    return {
        "id": workflow_id,
        "name": name,
        "mode": mode,
        "steps": [{"id": step_id, "description": description} for step_id, description in steps],
        "safety_gates": safety,
        "completion_signal": "User can see status, artifacts, validation result, and rollback/recovery path.",
    }


def _showcase(showcase_id: str, title: str, description: str) -> dict[str, Any]:
    return {
        "id": showcase_id,
        "title": title,
        "description": description,
        "demo_requirements": ["local workspace", "Core running", "model route available", "approval controls visible"],
        "success_criteria": ["clear plan", "visible safety state", "validation evidence", "recovery path"],
    }
