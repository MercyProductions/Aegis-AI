from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import (
    RuntimeCapabilityPillar,
    RuntimeModalityCapability,
    RuntimeToolContract,
    RuntimeWorkflowEntry,
    UnifiedRuntimeSnapshot,
)


UNIFIED_RUNTIME_API_VERSION = "2026.05.07"


@dataclass(frozen=True)
class RuntimeSignalCounts:
    task_count: int = 0
    active_task_count: int = 0
    project_memory_count: int = 0
    fix_memory_count: int = 0
    creative_job_count: int = 0
    creative_asset_count: int = 0
    worker_count: int = 0
    queue_job_count: int = 0
    objective_count: int = 0
    pending_approval_count: int = 0
    recommendation_count: int = 0
    project_intelligence_ready: bool = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class UnifiedRuntimeEngine:
    """Small registry that keeps Aegis' broad runtime capabilities coherent."""

    def snapshot(self, *, workspace_root: Path, counts: RuntimeSignalCounts) -> UnifiedRuntimeSnapshot:
        active_counts = {
            "tasks": counts.task_count,
            "active_tasks": counts.active_task_count,
            "project_memory": counts.project_memory_count,
            "fix_memory": counts.fix_memory_count,
            "creative_jobs": counts.creative_job_count,
            "creative_assets": counts.creative_asset_count,
            "workers": counts.worker_count,
            "queue_jobs": counts.queue_job_count,
            "objectives": counts.objective_count,
            "pending_approvals": counts.pending_approval_count,
            "recommendations": counts.recommendation_count,
        }

        return UnifiedRuntimeSnapshot(
            generated_at=utc_now(),
            api_version=UNIFIED_RUNTIME_API_VERSION,
            workspace_root=str(workspace_root),
            pillars=self._pillars(counts),
            modalities=self._modalities(),
            tools=self._tools(),
            workflows=self._workflows(),
            memory_summary={
                "project_memory_count": counts.project_memory_count,
                "fix_memory_count": counts.fix_memory_count,
                "project_intelligence_ready": counts.project_intelligence_ready,
                "continuity_status": "ready" if counts.project_memory_count or counts.project_intelligence_ready else "warming_up",
            },
            safety_summary=[
                "Local-first execution is the default.",
                "Workspace writes go through FileChange validation, checkpoints, and rollback.",
                "Commands, paid providers, voice cloning, remote workers, and long-running jobs require explicit permission.",
                "Autonomous objectives and workflows are task-tracked and approval-gated.",
            ],
            active_counts=active_counts,
            recommendations=self._recommendations(counts),
            warnings=[],
        )

    def _pillars(self, counts: RuntimeSignalCounts) -> list[RuntimeCapabilityPillar]:
        return [
            RuntimeCapabilityPillar(
                id="conversation_reasoning",
                name="Conversation And Reasoning",
                status="partial",
                summary="Chat, mission continuity, task awareness, project memory, and model routing are active; semantic conversation retrieval is the next quality layer.",
                modules=["agent.py", "prompt_intent.py", "routing.py", "memory_manager.py", "storage.py"],
                endpoints=["/api/chat", "/api/chat/stream", "/api/memory", "/api/history"],
                primary_surfaces=["Home", "Memory Editor", "Tasks"],
                active_items=counts.task_count,
                signals=[f"{counts.task_count} tracked task(s)", f"{counts.project_memory_count} project memory note(s)"],
                next_workflows=["Summarize long sessions", "Improve memory ranking", "Classify intent before tool routing"],
                safety_notes=["Conversation memory stays local in SQLite/browser storage unless exported explicitly."],
            ),
            RuntimeCapabilityPillar(
                id="multimodal_io",
                name="Multi-Modal Input And Output",
                status="partial",
                summary="Text and local creative media generation are active. Document/OCR/audio transcription and screenshot analysis remain provider/tool adapter work.",
                modules=["creative_media.py", "schemas.py"],
                endpoints=["/api/creative-studio", "/api/creative-studio/assets", "/api/creative-studio/jobs"],
                primary_surfaces=["Creative"],
                active_items=counts.creative_asset_count,
                signals=[f"{counts.creative_asset_count} creative asset(s)", f"{counts.creative_job_count} creative job(s)"],
                next_workflows=["Add document analysis adapter", "Add screenshot/OCR tool contract", "Add STT/TTS runtime contract"],
                safety_notes=["Creative assets are confined to workspace/creative_media."],
            ),
            RuntimeCapabilityPillar(
                id="operating_environment",
                name="Operating Environment",
                status="partial",
                summary="Desktop control, screen understanding, overlays, system intelligence, learning, research, environment setup, security analysis, story/simulation, and knowledge graph capabilities are registered through a permission-scoped control plane.",
                modules=["operating_environment.py", "schemas.py"],
                endpoints=["/api/operating-environment", "/api/operating-environment/actions/preview"],
                primary_surfaces=["Runtime"],
                active_items=0,
                signals=["Desktop and screen actions are blocked by default.", "Read-only system signals are available."],
                next_workflows=["Keep OS actions preview-first", "Add signed adapters only when the daily workflow needs them", "Reuse tasks, approvals, rollback, and audit events for every action"],
                safety_notes=["Keyboard/mouse control, screen capture, security tracing, dependency installs, and environment mutation require explicit approval and trusted adapters."],
            ),
            RuntimeCapabilityPillar(
                id="tool_execution",
                name="Tool Execution Framework",
                status="ready",
                summary="Filesystem, command validation, task events, checkpoints, approval settings, and distributed queue contracts are structured.",
                modules=["workspace.py", "commands.py", "validation.py", "task_engine.py", "distributed_runtime.py"],
                endpoints=["/api/files", "/api/apply", "/api/validate", "/api/tasks", "/api/distributed-runtime/queue"],
                primary_surfaces=["Projects", "Tasks", "Runtime"],
                active_items=counts.queue_job_count,
                signals=[f"{counts.queue_job_count} queued runtime job(s)"],
                next_workflows=["Unify tool contracts in plugin SDK", "Show only contextual tools per task"],
                safety_notes=["Write tools require workspace safety checks and checkpoint support."],
            ),
            RuntimeCapabilityPillar(
                id="web_research",
                name="Web And Research",
                status="planned",
                summary="Research workflows are planned. The runtime has task/workflow storage ready, but live search/source citation adapters are not yet local product features.",
                modules=["ecosystem.py", "task_engine.py"],
                endpoints=["/api/ecosystem/search"],
                primary_surfaces=["Ecosystem"],
                active_items=0,
                signals=["Knowledge graph search is available for local project intelligence."],
                next_workflows=["Add source retrieval adapter", "Add citation memory", "Add research session timeline"],
                safety_notes=["Network research should respect provider/network restrictions and citation logging."],
            ),
            RuntimeCapabilityPillar(
                id="creative_studio",
                name="Creative Studio",
                status="ready",
                summary="Image, motion/storyboard, beat, and voice draft generation are available with local assets, prompt packs, provider metadata, and exports.",
                modules=["creative_media.py"],
                endpoints=["/api/creative-studio", "/api/creative-studio/jobs", "/api/creative-studio/assets"],
                primary_surfaces=["Creative"],
                active_items=counts.creative_job_count,
                signals=[f"{counts.creative_job_count} generation job(s)", f"{counts.creative_asset_count} asset(s)"],
                next_workflows=["Improve prompt presets", "Add optional cloud provider implementations behind approvals"],
                safety_notes=["Paid, GPU-heavy, copyright-sensitive, and voice-cloning jobs require approval."],
            ),
            RuntimeCapabilityPillar(
                id="voice_assistant",
                name="Voice Assistant",
                status="planned",
                summary="Voice output drafts exist in Creative Studio. Low-latency STT/TTS streaming, interruption handling, and wake-word routing are planned.",
                modules=["creative_media.py"],
                endpoints=["/api/creative-studio/jobs"],
                primary_surfaces=["Creative"],
                active_items=0,
                signals=["Voiceover scratch WAV generation is available."],
                next_workflows=["Add STT adapter", "Add streaming TTS adapter", "Add voice interruption state machine"],
                safety_notes=["Voice cloning remains approval-gated."],
            ),
            RuntimeCapabilityPillar(
                id="agent_runtime",
                name="Agent Runtime",
                status="ready",
                summary="Tasks, subtasks, multi-agent events, validation, repair, memory, and autonomous objectives are tracked.",
                modules=["agent.py", "multi_agent.py", "task_engine.py", "autonomous_engineering.py"],
                endpoints=["/api/tasks", "/api/autonomous-engineering"],
                primary_surfaces=["Tasks", "Autonomous"],
                active_items=counts.active_task_count + counts.objective_count,
                signals=[f"{counts.active_task_count} active task(s)", f"{counts.objective_count} objective(s)"],
                next_workflows=["Reduce noisy autonomy controls", "Improve repair quality summaries"],
                safety_notes=["Long-running work is approval-gated and iteration-capped."],
            ),
            RuntimeCapabilityPillar(
                id="project_knowledge",
                name="Project And Knowledge Intelligence",
                status="ready" if counts.project_intelligence_ready else "partial",
                summary="Project profiles, architecture maps, file importance, memory notes, knowledge graph, and cross-project signals are available.",
                modules=["project_intelligence.py", "ecosystem.py", "storage.py"],
                endpoints=["/api/project-intelligence", "/api/ecosystem/knowledge-graph"],
                primary_surfaces=["Intelligence", "Ecosystem"],
                active_items=counts.project_memory_count,
                signals=[f"{counts.project_memory_count} project memory note(s)"],
                next_workflows=["Improve semantic indexing quality", "Reduce irrelevant context selection"],
                safety_notes=["Project intelligence is local and derived from allowed workspace roots."],
            ),
            RuntimeCapabilityPillar(
                id="automation_platform",
                name="Automation Platform",
                status="partial",
                summary="Scheduled intelligence jobs and reusable ecosystem workflows exist; trigger/condition/action chain editing is the future product layer.",
                modules=["workspace_operations.py", "ecosystem.py", "task_engine.py"],
                endpoints=["/api/workspace-intelligence/jobs", "/api/ecosystem/workflows"],
                primary_surfaces=["Workspace", "Ecosystem"],
                active_items=counts.recommendation_count,
                signals=[f"{counts.recommendation_count} recommendation(s)"],
                next_workflows=["Add trigger registry", "Add condition/action node contracts", "Keep automation task-tracked"],
                safety_notes=["Automation must not write files or run commands without approval."],
            ),
            RuntimeCapabilityPillar(
                id="distributed_execution",
                name="Distributed Execution",
                status="ready",
                summary="Local workers, queue state, sync manifests, routing previews, and audit events are available.",
                modules=["distributed_runtime.py"],
                endpoints=["/api/distributed-runtime"],
                primary_surfaces=["Runtime"],
                active_items=counts.worker_count,
                signals=[f"{counts.worker_count} worker(s)", f"{counts.queue_job_count} queue job(s)"],
                next_workflows=["Polish queue actions", "Keep remote execution opt-in"],
                safety_notes=["Remote workers require trust and explicit remote dispatch permission."],
            ),
            RuntimeCapabilityPillar(
                id="personal_memory",
                name="Personal AI Memory",
                status="partial",
                summary="Project memory and fix memory exist. Cross-session personal preferences and semantic timelines need consolidation.",
                modules=["memory_manager.py", "storage.py", "project_intelligence.py"],
                endpoints=["/api/memory", "/api/project-intelligence"],
                primary_surfaces=["Memory Editor", "Intelligence"],
                active_items=counts.project_memory_count + counts.fix_memory_count,
                signals=[f"{counts.fix_memory_count} fix memory item(s)"],
                next_workflows=["Preference memory", "Workflow memory", "Memory usefulness scoring"],
                safety_notes=["Memory edits are explicit and local."],
            ),
            RuntimeCapabilityPillar(
                id="security_safety",
                name="Security And Safety",
                status="ready",
                summary="Approval settings, sandbox profiles, protected workspaces, checkpoint rollback, plugin trust, and audit records are integrated.",
                modules=["workspace.py", "approval_sandbox.py", "productization.py", "ecosystem.py"],
                endpoints=["/api/approval-settings", "/api/checkpoints", "/api/productization", "/api/ecosystem/audit"],
                primary_surfaces=["Settings", "Hardening", "Ecosystem"],
                active_items=counts.pending_approval_count,
                signals=[f"{counts.pending_approval_count} pending approval(s)"],
                next_workflows=["Simplify approval copy", "Surface risk before action"],
                safety_notes=["Uncontrolled autonomy is not allowed."],
            ),
            RuntimeCapabilityPillar(
                id="clients_plugins_ux",
                name="Clients, Plugins, And UX",
                status="partial",
                summary="Browser workspace, desktop launch compatibility, plugin manifests, package lifecycle, and stable API docs exist. Mobile/remote client work is future-facing.",
                modules=["productization.py", "ecosystem.py", "main.py"],
                endpoints=["/api/productization", "/api/ecosystem/packages"],
                primary_surfaces=["Hardening", "Ecosystem"],
                active_items=0,
                signals=["Plugin metadata and stable API contracts are available."],
                next_workflows=["Reduce panel duplication", "Polish daily workflows", "Keep plugin execution sandboxed"],
                safety_notes=["Plugins are metadata until trusted and permission-scoped."],
            ),
        ]

    def _modalities(self) -> list[RuntimeModalityCapability]:
        return [
            RuntimeModalityCapability(id="text", label="Text", status="ready", input_supported=True, output_supported=True, analyzers=["intent classification", "summarization"], generators=["chat", "task plans", "docs"], formats=["md", "txt", "json"]),
            RuntimeModalityCapability(id="image", label="Images", status="partial", input_supported=False, output_supported=True, generators=["local previews", "SVG templates", "PNG/JPG exports"], formats=["png", "jpg", "svg", "gif"]),
            RuntimeModalityCapability(id="audio", label="Audio", status="partial", input_supported=False, output_supported=True, generators=["beat WAV preview", "voice scratch WAV", "MIDI sketch"], formats=["wav", "midi", "json"]),
            RuntimeModalityCapability(id="video", label="Video", status="partial", input_supported=False, output_supported=True, generators=["storyboard HTML", "GIF preview", "edit decision list"], formats=["html", "gif", "json"]),
            RuntimeModalityCapability(id="documents", label="Documents", status="planned", input_supported=False, output_supported=False, analyzers=["planned PDF/document summarization"], formats=["pdf", "docx", "md"]),
            RuntimeModalityCapability(id="screenshots", label="Screenshots And OCR", status="blocked", input_supported=False, output_supported=False, analyzers=["planned screenshot/OCR analysis"], formats=["png", "jpg", "text"], notes=["Screen capture requires an explicit approved adapter."]),
        ]

    def _tools(self) -> list[RuntimeToolContract]:
        return [
            RuntimeToolContract(id="filesystem", name="Filesystem", category="workspace", permission_scope="workspace", approval_required=True, sandboxed=True, rollback_supported=True, endpoints=["/api/files", "/api/file", "/api/apply"]),
            RuntimeToolContract(id="terminal", name="Terminal Commands", category="execution", permission_scope="command", approval_required=True, sandboxed=True, timeout_seconds=120, endpoints=["/api/validate", "/api/distributed-runtime/dispatch"]),
            RuntimeToolContract(id="validation", name="Validation", category="quality", permission_scope="validation", approval_required=False, sandboxed=True, endpoints=["/api/validate", "/api/validation-profile"]),
            RuntimeToolContract(id="task_graph", name="Task Graph", category="orchestration", permission_scope="task", approval_required=False, sandboxed=False, endpoints=["/api/tasks"]),
            RuntimeToolContract(id="creative_media", name="Creative Media", category="media", permission_scope="creative", approval_required=False, sandboxed=True, endpoints=["/api/creative-studio"], notes=["Paid/cloud providers require separate approval."]),
            RuntimeToolContract(id="desktop_control", name="Desktop Control", category="desktop", status="blocked", permission_scope="desktop_control", approval_required=True, sandboxed=True, endpoints=["/api/operating-environment/actions/preview"], notes=["Preview-only until a trusted desktop automation adapter is installed."]),
            RuntimeToolContract(id="screen_capture", name="Screen Capture And OCR", category="vision", status="blocked", permission_scope="screen_capture", approval_required=True, sandboxed=True, endpoints=["/api/operating-environment/actions/preview"], notes=["May expose private data; disabled without explicit capture consent."]),
            RuntimeToolContract(id="system_probe", name="Read-Only System Probe", category="system", status="partial", permission_scope="system_read", approval_required=False, sandboxed=False, tracked_by_tasks=False, endpoints=["/api/operating-environment"], notes=["Reports coarse host/runtime/storage signals without mutating the machine."]),
            RuntimeToolContract(id="distributed_queue", name="Distributed Queue", category="runtime", permission_scope="worker", approval_required=True, sandboxed=True, endpoints=["/api/distributed-runtime/queue"]),
            RuntimeToolContract(id="plugins", name="Plugin Packages", category="extension", permission_scope="plugin", approval_required=True, sandboxed=True, endpoints=["/api/productization/plugins", "/api/ecosystem/packages"]),
        ]

    def _workflows(self) -> list[RuntimeWorkflowEntry]:
        return [
            RuntimeWorkflowEntry(id="daily_coding", name="Daily Coding Loop", category="coding", description="Ask, plan, approve, edit, validate, repair, summarize.", endpoints=["/api/chat", "/api/tasks", "/api/validate"]),
            RuntimeWorkflowEntry(id="project_intelligence_refresh", name="Project Intelligence Refresh", category="knowledge", description="Scan project, update architecture map, rank files, refresh memory.", endpoints=["/api/project-intelligence/reindex"]),
            RuntimeWorkflowEntry(id="creative_generation", name="Creative Asset Generation", category="creative", description="Build prompt, generate local draft, preview, export, revise.", endpoints=["/api/creative-studio/jobs"]),
            RuntimeWorkflowEntry(id="workspace_health", name="Workspace Health", category="automation", description="Scan workspace, create recommendations, convert fixes into tracked tasks.", endpoints=["/api/workspace-intelligence/scan"]),
            RuntimeWorkflowEntry(id="operating_environment_preview", name="Operating Environment Preview", category="desktop", status="partial", description="Inspect OS-level capability, permission, adapter, and safety requirements before any desktop or system action is allowed.", endpoints=["/api/operating-environment", "/api/operating-environment/actions/preview"]),
            RuntimeWorkflowEntry(id="supervised_objective", name="Supervised Objective", category="autonomy", description="Dry run objective, approve gates, iterate phases, verify, summarize.", endpoints=["/api/autonomous-engineering"]),
            RuntimeWorkflowEntry(id="safe_distributed_job", name="Safe Distributed Job", category="runtime", description="Queue, assign, audit, and complete local or trusted remote execution.", endpoints=["/api/distributed-runtime/dispatch"]),
        ]

    def _recommendations(self, counts: RuntimeSignalCounts) -> list[str]:
        recommendations = [
            "Keep daily work centered on chat, tasks, approvals, validation, and clear summaries.",
            "Use the Runtime surface as the capability map instead of adding a new dashboard for every subsystem.",
        ]
        if not counts.project_intelligence_ready:
            recommendations.append("Run Project Intelligence indexing for better context selection.")
        if counts.pending_approval_count:
            recommendations.append("Resolve pending approvals before starting more autonomous or remote work.")
        if not counts.project_memory_count:
            recommendations.append("Save a few project decisions so continuity and context ranking can improve.")
        return recommendations
