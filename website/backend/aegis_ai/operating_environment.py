from __future__ import annotations

import os
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .schemas import (
    OperatingEnvironmentActionRequest,
    OperatingEnvironmentActionResponse,
    OperatingEnvironmentAdapter,
    OperatingEnvironmentCapability,
    OperatingEnvironmentSnapshot,
    OperatingSystemSignal,
    ToolEvent,
)


OPERATING_ENVIRONMENT_API_VERSION = "2026.05.07"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OperatingEnvironmentEngine:
    """Permission-scoped control plane for Aegis' local AI operating environment."""

    def snapshot(self, *, workspace_root: Path) -> OperatingEnvironmentSnapshot:
        capabilities = self._capabilities()
        adapters = self._adapters()
        ready = len([item for item in capabilities if item.status == "ready"])
        gated = len([item for item in capabilities if item.approval_required or item.status == "blocked"])

        return OperatingEnvironmentSnapshot(
            generated_at=utc_now(),
            api_version=OPERATING_ENVIRONMENT_API_VERSION,
            workspace_root=str(workspace_root),
            capabilities=capabilities,
            adapters=adapters,
            system_signals=self._system_signals(workspace_root),
            permissions_summary={
                "ready_capabilities": ready,
                "approval_or_adapter_gated": gated,
                "enabled_adapters": len([item for item in adapters if item.enabled]),
                "disabled_adapters": len([item for item in adapters if not item.enabled]),
                "desktop_control_default": "blocked",
                "screen_capture_default": "blocked",
            },
            safety_summary=[
                "The operating environment is a control plane first, not uncontrolled desktop automation.",
                "Desktop control, screen capture, keyboard/mouse actions, security tracing, dependency installs, and paid/cloud work are blocked or approval-gated by default.",
                "Read-only system signals can be shown without approval because they do not modify the machine.",
                "Future action adapters must be task-tracked, sandboxed where possible, permission-scoped, and audited.",
            ],
            recommended_next_actions=[
                "Use this registry to keep OS, research, learning, creative, workflow, and runtime capabilities coherent.",
                "Prefer read-only diagnostics and previews before adding executable desktop adapters.",
                "Keep risky actions behind explicit approval and a named adapter contract.",
            ],
            warnings=[],
        )

    def preview_action(self, request: OperatingEnvironmentActionRequest) -> OperatingEnvironmentActionResponse:
        capabilities = {capability.id: capability for capability in self._capabilities()}
        capability = capabilities.get(request.capability_id)
        now = utc_now()

        if capability is None:
            event = ToolEvent(
                kind="operating_environment.action_preview",
                title="Unknown operating-environment capability",
                status="error",
                detail=f"No capability is registered for '{request.capability_id}'.",
                payload={"capability_id": request.capability_id, "action": request.action},
                created_at=now,
            )
            return OperatingEnvironmentActionResponse(
                request_id=f"op-preview-{uuid4().hex[:10]}",
                capability_id=request.capability_id,
                action=request.action,
                status="blocked",
                allowed=False,
                approval_required=False,
                reason="Unknown capability.",
                summary=event.detail,
                event=event,
            )

        required_permissions = self._required_permissions(capability.permission_scope)
        approval_required = capability.approval_required
        status = "preview"
        allowed = True
        reason = "This dry-run is eligible for a read-only preview."
        event_status = "ok"

        if capability.status in {"blocked", "disabled"}:
            status = "blocked"
            allowed = False
            approval_required = True
            event_status = "warning"
            reason = "Execution is blocked until a trusted, permission-scoped adapter is installed and approved."
        elif approval_required:
            status = "needs_approval"
            allowed = False
            event_status = "warning"
            reason = "This capability can affect the machine or workspace and requires explicit approval."
        elif not request.dry_run:
            status = "blocked"
            allowed = False
            approval_required = True
            event_status = "warning"
            reason = "Only previews are implemented for this operating-environment endpoint."

        event = ToolEvent(
            kind="operating_environment.action_preview",
            title=f"{capability.name}: {request.action}",
            status=event_status,
            detail=reason,
            payload={
                "capability_id": capability.id,
                "action": request.action,
                "dry_run": request.dry_run,
                "task_id": request.task_id,
                "required_permissions": required_permissions,
                "parameters": request.parameters,
            },
            created_at=now,
        )

        return OperatingEnvironmentActionResponse(
            request_id=f"op-preview-{uuid4().hex[:10]}",
            capability_id=capability.id,
            action=request.action,
            status=status,
            allowed=allowed,
            approval_required=approval_required,
            reason=reason,
            summary=self._action_summary(capability, request.action, status),
            required_permissions=required_permissions,
            rollback_supported=capability.rollback_supported,
            safety_notes=capability.safety_notes,
            event=event,
        )

    def _capabilities(self) -> list[OperatingEnvironmentCapability]:
        return [
            OperatingEnvironmentCapability(
                id="desktop_control",
                name="AI Desktop Control Layer",
                category="desktop",
                status="blocked",
                summary="Application launch, window management, monitor layouts, clipboard actions, keyboard/mouse automation, and quick actions are registered but not executable without a trusted desktop adapter.",
                permission_scope="desktop_control",
                approval_required=True,
                sandbox_required=True,
                rollback_supported=False,
                task_tracked=True,
                adapter_ids=["desktop_automation_adapter"],
                endpoints=["/api/operating-environment/actions/preview"],
                surfaces=["Runtime"],
                safety_notes=["No keyboard, mouse, app-launch, or clipboard mutation is performed by this endpoint."],
                next_steps=["Define signed desktop adapter contract", "Add per-action approval copy", "Add reversible layout profiles before any layout mutation"],
            ),
            OperatingEnvironmentCapability(
                id="live_screen_understanding",
                name="Live Screen Understanding",
                category="vision",
                status="blocked",
                summary="Screenshot analysis, OCR, UI understanding, visual debugging, and overlay guidance are modeled but screen capture is disabled until the user approves a screen adapter.",
                permission_scope="screen_capture",
                approval_required=True,
                sandbox_required=True,
                rollback_supported=False,
                task_tracked=True,
                adapter_ids=["screen_capture_adapter"],
                endpoints=["/api/operating-environment/actions/preview"],
                surfaces=["Runtime"],
                safety_notes=["Screen capture may expose private data and must be explicit, visible, and auditable."],
                next_steps=["Add explicit capture consent", "Add local OCR adapter", "Attach captures to task artifacts with retention controls"],
            ),
            OperatingEnvironmentCapability(
                id="ai_overlay",
                name="AI Overlay System",
                category="desktop",
                status="planned",
                summary="Global command palette, quick prompts, voice activation, screenshot capture, task status, notifications, and floating widgets are planned as a thin client over existing task/runtime APIs.",
                permission_scope="overlay",
                approval_required=True,
                sandbox_required=True,
                rollback_supported=False,
                task_tracked=True,
                adapter_ids=["global_overlay_adapter"],
                endpoints=["/api/tasks", "/api/operating-environment"],
                surfaces=["Future Desktop Overlay"],
                safety_notes=["Overlay controls should call existing approval-gated APIs instead of bypassing them."],
                next_steps=["Build overlay shell", "Reuse task status and approval flows", "Keep voice/screenshot buttons visibly permissioned"],
            ),
            OperatingEnvironmentCapability(
                id="automation_studio",
                name="AI Automation Studio",
                category="workflow",
                status="partial",
                summary="Task graphs, scheduled intelligence jobs, and ecosystem workflows provide the foundation for triggers, conditions, actions, AI nodes, desktop steps, and notifications.",
                permission_scope="workflow",
                approval_required=True,
                sandbox_required=True,
                rollback_supported=True,
                task_tracked=True,
                adapter_ids=["workflow_engine_adapter"],
                endpoints=["/api/tasks", "/api/workspace-intelligence/jobs", "/api/ecosystem/workflows"],
                surfaces=["Workspace", "Ecosystem", "Runtime"],
                safety_notes=["Automation chains must stay task-tracked and cannot silently write files or run commands."],
                next_steps=["Add trigger registry", "Add condition/action node schemas", "Show approval gates inline in workflow runs"],
            ),
            OperatingEnvironmentCapability(
                id="ai_ide_engine",
                name="AI IDE And Editor Engine",
                category="coding",
                status="partial",
                summary="Project Intelligence, diffs, task timelines, validation, repair, and architecture maps already support AI-native development workflows.",
                permission_scope="workspace",
                approval_required=True,
                sandbox_required=True,
                rollback_supported=True,
                task_tracked=True,
                adapter_ids=["workspace_file_adapter", "project_graph_adapter"],
                endpoints=["/api/project-intelligence", "/api/tasks", "/api/files", "/api/apply"],
                surfaces=["Projects", "Tasks", "Intelligence"],
                safety_notes=["File changes must continue using FileChange validation, checkpoints, and rollback."],
                next_steps=["Improve semantic navigation", "Polish contextual diffing", "Add timeline replay from existing task events"],
            ),
            OperatingEnvironmentCapability(
                id="system_intelligence",
                name="AI System Intelligence",
                category="system",
                status="partial",
                summary="Read-only OS, CPU, Python runtime, and workspace disk signals are available. GPU, thermal, driver, startup, and process diagnostics need dedicated adapters.",
                permission_scope="system_read",
                approval_required=False,
                sandbox_required=False,
                rollback_supported=False,
                task_tracked=False,
                telemetry_enabled=True,
                adapter_ids=["readonly_system_probe"],
                endpoints=["/api/operating-environment"],
                surfaces=["Runtime"],
                safety_notes=["Current probes are read-only and do not inspect user files beyond workspace disk statistics."],
                next_steps=["Add optional GPU/thermal adapter", "Add process diagnostics behind approval", "Generate low-noise performance recommendations"],
            ),
            OperatingEnvironmentCapability(
                id="learning_training",
                name="AI Learning And Training System",
                category="learning",
                status="planned",
                summary="Quizzes, flashcards, study guides, mock exams, concept graphs, progress tracking, visual explanations, and voice teaching are planned on top of memory and task storage.",
                permission_scope="personal_memory",
                approval_required=False,
                sandbox_required=False,
                rollback_supported=True,
                task_tracked=True,
                adapter_ids=["learning_content_adapter"],
                endpoints=["/api/memory", "/api/tasks"],
                surfaces=["Future Learning"],
                safety_notes=["Learning progress and preferences should remain local and user-editable."],
                next_steps=["Add concept graph schema", "Create flashcard artifacts", "Reuse voice output only with user approval"],
            ),
            OperatingEnvironmentCapability(
                id="research_engine",
                name="AI Research Engine",
                category="research",
                status="planned",
                summary="Web search, source comparison, semantic summaries, citations, timelines, research sessions, and knowledge graphs are planned behind network policy controls.",
                permission_scope="network_research",
                approval_required=True,
                sandbox_required=True,
                rollback_supported=False,
                task_tracked=True,
                adapter_ids=["network_research_adapter"],
                endpoints=["/api/operating-environment/actions/preview", "/api/ecosystem/search"],
                surfaces=["Future Research"],
                safety_notes=["Live research must cite sources, record network use, and respect provider/network restrictions."],
                next_steps=["Add source retrieval adapter", "Add citation artifacts", "Attach research sessions to memory with user control"],
            ),
            OperatingEnvironmentCapability(
                id="story_world_engine",
                name="AI Story And World Engine",
                category="creative",
                status="planned",
                summary="Worldbuilding, lore tracking, branching narratives, AI characters, persistent world state, RPG systems, and cinematic scripting can reuse the knowledge graph and Creative Studio.",
                permission_scope="creative_memory",
                approval_required=False,
                sandbox_required=False,
                rollback_supported=True,
                task_tracked=True,
                adapter_ids=["narrative_state_adapter"],
                endpoints=["/api/creative-studio", "/api/ecosystem/knowledge-graph"],
                surfaces=["Creative"],
                safety_notes=["Generated worlds should be versioned assets with exportable state."],
                next_steps=["Add lore schema", "Add branching timeline artifacts", "Connect character memory to local project memory controls"],
            ),
            OperatingEnvironmentCapability(
                id="simulation_game_engine",
                name="AI Game And Simulation Engine",
                category="simulation",
                status="planned",
                summary="Persistent simulation state, faction systems, NPC memory, procedural events, economies, quests, and maps are planned as asset-backed simulations.",
                permission_scope="simulation",
                approval_required=False,
                sandbox_required=True,
                rollback_supported=True,
                task_tracked=True,
                adapter_ids=["simulation_state_adapter"],
                endpoints=["/api/tasks", "/api/creative-studio"],
                surfaces=["Creative"],
                safety_notes=["Simulation execution should be deterministic where possible and exportable as local assets."],
                next_steps=["Define simulation state snapshots", "Add deterministic seed handling", "Keep long simulations cancelable"],
            ),
            OperatingEnvironmentCapability(
                id="environment_builder",
                name="AI Environment Builder",
                category="system",
                status="partial",
                summary="Workspace setup, dependency discovery, validation profiles, and repair flows exist. SDK installs, IDE configuration, environment variable changes, and dependency installs remain approval-gated.",
                permission_scope="environment_setup",
                approval_required=True,
                sandbox_required=True,
                rollback_supported=True,
                task_tracked=True,
                adapter_ids=["workspace_setup_adapter"],
                endpoints=["/api/workspace/setup", "/api/validation-profile", "/api/validate"],
                surfaces=["Projects", "Runtime"],
                safety_notes=["Toolchain installs and environment mutations must show commands before execution."],
                next_steps=["Add dry-run environment plan", "Track installed toolchain fingerprints", "Add rollback notes for env changes"],
            ),
            OperatingEnvironmentCapability(
                id="security_analysis_workspace",
                name="AI Security And Analysis Workspace",
                category="security",
                status="blocked",
                summary="Binary analysis, PE inspection, telemetry tracing, memory maps, debugger orchestration, network inspection, and sandbox orchestration are registered as high-risk workflows only.",
                permission_scope="security_lab",
                approval_required=True,
                sandbox_required=True,
                rollback_supported=False,
                task_tracked=True,
                adapter_ids=["security_lab_adapter"],
                endpoints=["/api/operating-environment/actions/preview"],
                surfaces=["Future Security"],
                safety_notes=["Security tooling must be isolated, auditable, and never target systems without explicit authorization."],
                next_steps=["Add read-only file inspection first", "Require lab workspace trust", "Add network/process scope prompts"],
            ),
            OperatingEnvironmentCapability(
                id="personal_memory",
                name="AI Personal Memory System",
                category="memory",
                status="partial",
                summary="Project memory and fix memory are active; timeline memory, workflow memory, preference learning, semantic recall, and long-term personalization need consolidation.",
                permission_scope="personal_memory",
                approval_required=False,
                sandbox_required=False,
                rollback_supported=True,
                task_tracked=True,
                adapter_ids=["local_memory_adapter"],
                endpoints=["/api/memory", "/api/project-intelligence"],
                surfaces=["Memory Editor", "Intelligence"],
                safety_notes=["Memory should remain visible, editable, local, and exportable."],
                next_steps=["Add memory usefulness scoring", "Merge workflow memory with task outcomes", "Add preference review controls"],
            ),
            OperatingEnvironmentCapability(
                id="runtime_personality_modes",
                name="AI Runtime Personality Modes",
                category="experience",
                status="partial",
                summary="Existing modes and custom agents influence routing and response style; deeper mode-specific UI emphasis, validation behavior, and memory policy are future refinements.",
                permission_scope="profile",
                approval_required=False,
                sandbox_required=False,
                rollback_supported=True,
                task_tracked=False,
                adapter_ids=["mode_profile_adapter"],
                endpoints=["/api/config", "/api/models"],
                surfaces=["Home", "Settings"],
                safety_notes=["Mode changes should never bypass safety, validation, or approval rules."],
                next_steps=["Add mode-specific routing hints", "Expose concise personality presets", "Benchmark mode quality"],
            ),
            OperatingEnvironmentCapability(
                id="creative_studio",
                name="AI Multi-Modal Creative Studio",
                category="creative",
                status="ready",
                summary="Image, UI mockup, product mockup, storyboard/video draft, beat/music, voice, asset library, providers, prompt presets, and exports are available locally.",
                permission_scope="creative",
                approval_required=False,
                sandbox_required=True,
                rollback_supported=True,
                task_tracked=True,
                adapter_ids=["creative_local_adapter"],
                endpoints=["/api/creative-studio"],
                surfaces=["Creative"],
                safety_notes=["Paid providers, large GPU jobs, long video jobs, copyright-sensitive prompts, and voice cloning require approval."],
                next_steps=["Improve asset organization", "Add provider implementations carefully", "Keep local generation fast and predictable"],
            ),
            OperatingEnvironmentCapability(
                id="distributed_runtime",
                name="AI Distributed Runtime",
                category="runtime",
                status="ready",
                summary="Local workers, remote worker contracts, GPU/sandbox worker capability fields, queue dispatch, routing previews, sync manifests, and observability are available.",
                permission_scope="worker",
                approval_required=True,
                sandbox_required=True,
                rollback_supported=False,
                task_tracked=True,
                adapter_ids=["distributed_worker_adapter"],
                endpoints=["/api/distributed-runtime"],
                surfaces=["Runtime"],
                safety_notes=["Remote dispatch is opt-in and requires trusted worker registration."],
                next_steps=["Polish queue status", "Keep offline local-first mode reliable", "Tighten worker trust UX"],
            ),
            OperatingEnvironmentCapability(
                id="knowledge_graph",
                name="AI Knowledge Graph",
                category="knowledge",
                status="partial",
                summary="Project, task, architecture, package, workflow, and memory relationships are available through Project Intelligence and Ecosystem graph APIs.",
                permission_scope="knowledge",
                approval_required=False,
                sandbox_required=False,
                rollback_supported=True,
                task_tracked=True,
                adapter_ids=["knowledge_graph_adapter"],
                endpoints=["/api/project-intelligence", "/api/ecosystem/knowledge-graph"],
                surfaces=["Intelligence", "Ecosystem"],
                safety_notes=["Knowledge graph data is derived from local workspace and memory sources."],
                next_steps=["Improve graph relevance", "Add semantic search ranking", "Reduce duplicate relationship types"],
            ),
        ]

    def _adapters(self) -> list[OperatingEnvironmentAdapter]:
        now = utc_now()
        return [
            OperatingEnvironmentAdapter(
                id="readonly_system_probe",
                name="Read-Only System Probe",
                category="system",
                status="ready",
                enabled=True,
                permission_scope="system_read",
                capabilities=["system_intelligence"],
                approval_required=False,
                sandboxed=False,
                last_seen_at=now,
                notes=["Uses Python standard library only.", "Does not mutate files, processes, windows, clipboard, or settings."],
            ),
            OperatingEnvironmentAdapter(
                id="workspace_file_adapter",
                name="Workspace File Adapter",
                category="workspace",
                status="ready",
                enabled=True,
                permission_scope="workspace",
                capabilities=["ai_ide_engine"],
                approval_required=True,
                sandboxed=True,
                last_seen_at=now,
                notes=["Existing file changes remain checkpointed and rollbackable."],
            ),
            OperatingEnvironmentAdapter(
                id="creative_local_adapter",
                name="Local Creative Media Adapter",
                category="creative",
                status="ready",
                enabled=True,
                permission_scope="creative",
                capabilities=["creative_studio", "story_world_engine", "simulation_game_engine"],
                approval_required=False,
                sandboxed=True,
                last_seen_at=now,
                notes=["Outputs are confined to the Creative Studio asset library."],
            ),
            OperatingEnvironmentAdapter(
                id="distributed_worker_adapter",
                name="Distributed Worker Adapter",
                category="runtime",
                status="ready",
                enabled=True,
                permission_scope="worker",
                capabilities=["distributed_runtime"],
                approval_required=True,
                sandboxed=True,
                last_seen_at=now,
                notes=["Remote execution remains opt-in and audited."],
            ),
            OperatingEnvironmentAdapter(
                id="desktop_automation_adapter",
                name="Desktop Automation Adapter",
                category="desktop",
                status="blocked",
                enabled=False,
                permission_scope="desktop_control",
                capabilities=["desktop_control"],
                approval_required=True,
                sandboxed=True,
                notes=["No trusted keyboard/mouse/window adapter is enabled."],
            ),
            OperatingEnvironmentAdapter(
                id="screen_capture_adapter",
                name="Screen Capture And OCR Adapter",
                category="vision",
                status="blocked",
                enabled=False,
                permission_scope="screen_capture",
                capabilities=["live_screen_understanding"],
                approval_required=True,
                sandboxed=True,
                notes=["Screen capture requires explicit user consent and retention controls."],
            ),
            OperatingEnvironmentAdapter(
                id="network_research_adapter",
                name="Network Research Adapter",
                category="research",
                status="planned",
                enabled=False,
                permission_scope="network_research",
                capabilities=["research_engine"],
                approval_required=True,
                sandboxed=True,
                notes=["Live web retrieval must preserve citations and network policy checks."],
            ),
            OperatingEnvironmentAdapter(
                id="security_lab_adapter",
                name="Security Lab Adapter",
                category="security",
                status="blocked",
                enabled=False,
                permission_scope="security_lab",
                capabilities=["security_analysis_workspace"],
                approval_required=True,
                sandboxed=True,
                notes=["High-risk analysis requires isolated lab permissions."],
            ),
        ]

    def _system_signals(self, workspace_root: Path) -> list[OperatingSystemSignal]:
        signals = [
            OperatingSystemSignal(
                id="os",
                label="Operating System",
                category="host",
                status="ok",
                value=f"{platform.system()} {platform.release()}",
                detail=platform.version(),
                updated_at=utc_now(),
            ),
            OperatingSystemSignal(
                id="architecture",
                label="Architecture",
                category="host",
                status="ok",
                value=platform.machine() or "unknown",
                detail=platform.platform(),
                updated_at=utc_now(),
            ),
            OperatingSystemSignal(
                id="logical_cpu",
                label="Logical CPU",
                category="hardware",
                status="ok",
                value=str(os.cpu_count() or "unknown"),
                detail="Read-only standard-library probe.",
                updated_at=utc_now(),
            ),
            OperatingSystemSignal(
                id="python_runtime",
                label="Python Runtime",
                category="runtime",
                status="ok",
                value=platform.python_version(),
                detail=platform.python_implementation(),
                updated_at=utc_now(),
            ),
        ]

        try:
            usage = shutil.disk_usage(workspace_root)
            free_gb = usage.free / (1024**3)
            total_gb = usage.total / (1024**3)
            status = "warning" if usage.free / max(usage.total, 1) < 0.1 else "ok"
            signals.append(
                OperatingSystemSignal(
                    id="workspace_disk",
                    label="Workspace Disk",
                    category="storage",
                    status=status,
                    value=f"{free_gb:.1f} GB free",
                    detail=f"{total_gb:.1f} GB total at {workspace_root}",
                    updated_at=utc_now(),
                )
            )
        except OSError as exc:
            signals.append(
                OperatingSystemSignal(
                    id="workspace_disk",
                    label="Workspace Disk",
                    category="storage",
                    status="warning",
                    value="unavailable",
                    detail=str(exc),
                    updated_at=utc_now(),
                )
            )

        return signals

    def _required_permissions(self, permission_scope: str) -> list[str]:
        if not permission_scope:
            return []
        aliases = {
            "desktop_control": ["launch_apps", "window_layout", "clipboard", "keyboard_mouse"],
            "screen_capture": ["screen_capture", "ocr", "screenshot_artifacts"],
            "network_research": ["network_access", "source_retrieval", "citation_logging"],
            "security_lab": ["process_inspection", "binary_analysis", "sandbox_execution"],
            "environment_setup": ["command_execution", "dependency_install", "environment_mutation"],
            "workspace": ["workspace_read", "workspace_write", "checkpoint"],
            "worker": ["worker_dispatch", "audit_logging"],
        }
        return aliases.get(permission_scope, [permission_scope])

    def _action_summary(
        self,
        capability: OperatingEnvironmentCapability,
        action: str,
        status: str,
    ) -> str:
        if status == "preview":
            return f"'{action}' can be previewed for {capability.name}; no machine action was executed."
        if status == "needs_approval":
            return f"'{action}' for {capability.name} requires explicit approval and an adapter-specific execution path."
        return f"'{action}' for {capability.name} is blocked in the current local-first safety profile."
