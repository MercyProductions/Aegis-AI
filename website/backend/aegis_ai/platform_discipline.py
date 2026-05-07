from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .schemas import (
    AegisContinuitySnapshot,
    MaintainabilityPractice,
    PlatformBehaviorPrinciple,
    PlatformDesignStandard,
    PlatformDisciplineSnapshot,
    PlatformDomainStrategy,
    PlatformFeatureAdmissionCriterion,
    PlatformFeatureAdmissionPolicy,
    PlatformFeedbackLoop,
    PlatformLayerDefinition,
    PlatformPerformanceBudget,
    PlatformRoadmapItem,
    PlatformSecurityFoundation,
    PlatformStabilityTier,
    PlatformStewardshipPosture,
    UnifiedRuntimeSnapshot,
)


PLATFORM_DISCIPLINE_API_VERSION = "2026.05.07"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PlatformDisciplineEngine:
    """Codifies Aegis' product focus, stability tiers, budgets, and operating rules."""

    def snapshot(
        self,
        *,
        workspace_root: Path,
        runtime: UnifiedRuntimeSnapshot | None = None,
        continuity: AegisContinuitySnapshot | None = None,
    ) -> PlatformDisciplineSnapshot:
        domains = self._domains()
        roadmap = self._roadmap()
        counts = Counter(item.status for item in roadmap)
        warnings = self._warnings(runtime, continuity)

        return PlatformDisciplineSnapshot(
            workspace_root=str(workspace_root),
            generated_at=utc_now(),
            api_version=PLATFORM_DISCIPLINE_API_VERSION,
            core_identity=(
                "Aegis is a unified local-first AI operating environment for real daily work: "
                "coding, orchestration, memory, validation, selective automation, and contextual creative/research support."
            ),
            stewardship=self._stewardship(),
            feature_admission=self._feature_admission(),
            primary_domains=[domain for domain in domains if domain.focus == "primary"],
            secondary_domains=[domain for domain in domains if domain.focus == "secondary"],
            experimental_domains=[domain for domain in domains if domain.focus == "experimental"],
            roadmap=roadmap,
            stability_tiers=self._stability_tiers(),
            feedback_loops=self._feedback_loops(runtime, continuity),
            design_standards=self._design_standards(),
            behavior_principles=self._behavior_principles(),
            performance_budgets=self._performance_budgets(continuity),
            security_foundations=self._security_foundations(),
            layers=self._layers(),
            maintainability_practices=self._maintainability_practices(),
            production_ready_count=counts.get("production_ready", 0),
            beta_count=counts.get("beta", 0),
            experimental_count=counts.get("experimental", 0),
            deprecated_count=counts.get("deprecated", 0),
            recommendations=self._recommendations(runtime, continuity),
            warnings=warnings,
        )

    def _stewardship(self) -> PlatformStewardshipPosture:
        return PlatformStewardshipPosture(
            summary=(
                "Aegis now evolves by stewardship: preserve quality, clarity, maintainability, trust, "
                "performance, and cohesion before adding breadth."
            ),
            preserve=[
                "quality",
                "clarity",
                "maintainability",
                "trust",
                "performance",
                "cohesion",
                "rollback capability",
                "user control",
            ],
            improve=[
                "intelligence quality",
                "workflow quality",
                "context accuracy",
                "repair quality",
                "memory usefulness",
                "responsiveness",
                "explainability",
                "stability",
            ],
            reduce=[
                "friction",
                "clutter",
                "redundancy",
                "latency",
                "instability",
                "architectural drift",
                "feature sprawl",
                "telemetry noise",
            ],
            product_feel=[
                "calm",
                "premium",
                "reliable",
                "deeply integrated",
                "explainable",
                "trustworthy",
                "powerful without feeling chaotic",
            ],
            operating_rules=[
                "Do not chase trends blindly.",
                "Do not overload the user with complexity.",
                "Prefer improving existing workflows over adding new surfaces.",
                "Protect responsiveness before background intelligence.",
                "Protect explainability before autonomy.",
                "Treat pruning, simplification, and latency reduction as product work.",
            ],
            success_metric=(
                "Users choose Aegis daily because it consistently improves their workflows, thinking, creativity, "
                "and productivity without feeling chaotic."
            ),
            review_cadence="Review during every roadmap change, beta promotion, and large refactor.",
        )

    def _feature_admission(self) -> PlatformFeatureAdmissionPolicy:
        criteria = [
            PlatformFeatureAdmissionCriterion(
                id="core_identity",
                question="Does this strengthen the core identity?",
                pass_requirement="The proposal clearly improves coding, orchestration, memory/knowledge continuity, or a proven secondary workflow.",
                reject_when="The proposal mainly broadens scope, imitates competitors, or creates a disconnected surface.",
                protects=["cohesion", "identity", "maintainability"],
            ),
            PlatformFeatureAdmissionCriterion(
                id="real_workflow",
                question="Does this improve a real workflow users rely on regularly?",
                pass_requirement="There is a named daily or recurring workflow with a measurable before/after improvement.",
                reject_when="The workflow is hypothetical, novelty-driven, or useful only as a demo.",
                protects=["usability", "workflow quality"],
            ),
            PlatformFeatureAdmissionCriterion(
                id="friction",
                question="Does this reduce friction?",
                pass_requirement="It removes steps, reduces uncertainty, improves clarity, or shortens time to a trusted result.",
                reject_when="It adds settings, panels, approvals, notifications, or choices without reducing a larger pain.",
                protects=["calm UX", "responsiveness", "clarity"],
            ),
            PlatformFeatureAdmissionCriterion(
                id="intelligence_quality",
                question="Does this improve intelligence quality?",
                pass_requirement="It improves planning, routing, context selection, repair quality, memory usefulness, or hallucination resistance.",
                reject_when="It only adds another capability surface without improving decisions or outcomes.",
                protects=["task success", "context accuracy", "repair quality"],
            ),
            PlatformFeatureAdmissionCriterion(
                id="trust",
                question="Does this improve user trust?",
                pass_requirement="It is transparent, permission-aware, reversible, observable, and explainable.",
                reject_when="It hides decisions, weakens approvals, weakens rollback, or makes autonomy more aggressive.",
                protects=["trust", "safety", "explainability"],
            ),
            PlatformFeatureAdmissionCriterion(
                id="maintainability",
                question="Is this maintainable long-term?",
                pass_requirement="It has a clear owner layer, bounded API, tests, docs, and no giant-file or duplicate-system pressure.",
                reject_when="It introduces hidden dependencies, duplicated logic, telemetry sprawl, or unstable abstractions.",
                protects=["maintainability", "architecture"],
            ),
            PlatformFeatureAdmissionCriterion(
                id="runtime_fit",
                question="Does this integrate cleanly with the runtime?",
                pass_requirement="Executable work routes through tasks, approvals, telemetry, rollback, validation, and the owning module boundary.",
                reject_when="It bypasses task tracking, creates parallel execution paths, or couples stable layers to experimental adapters.",
                protects=["runtime integrity", "observability", "rollback"],
            ),
            PlatformFeatureAdmissionCriterion(
                id="complexity_cost",
                question="Does this avoid harmful architectural complexity?",
                pass_requirement="The complexity cost is smaller than the workflow value and performance cost.",
                reject_when="The proposal adds workers, providers, plugins, UI surfaces, indexes, or background jobs without a proven payoff.",
                protects=["performance", "scalability", "reliability"],
            ),
            PlatformFeatureAdmissionCriterion(
                id="duplication",
                question="Does this avoid duplicating an existing capability?",
                pass_requirement="It extends or simplifies an existing subsystem instead of creating another way to do the same thing.",
                reject_when="The same user outcome already exists in Runtime, Tasks, Workspace, Intelligence, Creative, Hardening, Ecosystem, or Settings.",
                protects=["cohesion", "low clutter"],
            ),
            PlatformFeatureAdmissionCriterion(
                id="regular_reliance",
                question="Will users genuinely rely on this regularly?",
                pass_requirement="It has a believable path to repeated use and measurable retention or completion signals.",
                reject_when="The value is occasional, unclear, speculative, or mostly impressive in theory.",
                protects=["depth over width", "product focus"],
            ),
        ]
        return PlatformFeatureAdmissionPolicy(
            summary="New features are rejected by default when workflow value, runtime fit, safety, performance, or long-term maintenance cost is unclear.",
            criteria=criteria,
            hard_no_rules=[
                "Say no to unclear value.",
                "Say no to dashboard sprawl.",
                "Say no to uncontrolled autonomy.",
                "Say no to bypassing tasks, approvals, rollback, validation, telemetry, or audit.",
                "Say no to duplicated systems and hidden dependencies.",
                "Say no to background work that can degrade active user workflows.",
                "Say no to plugin, provider, desktop, or worker behavior without permission scopes and trust boundaries.",
            ],
            promotion_requirements=[
                "Named workflow and user value.",
                "Clear owner layer and module boundary.",
                "No duplicate capability path.",
                "Performance budget impact reviewed.",
                "Security and rollback behavior documented.",
                "Backend/frontend contract tests added when APIs change.",
                "Docs updated before promotion out of experimental status.",
            ],
            review_cadence="Apply before implementation and again before promoting beta or experimental work.",
        )

    def _domains(self) -> list[PlatformDomainStrategy]:
        return [
            PlatformDomainStrategy(
                id="coding_workspace",
                name="AI Coding Workspace",
                focus="primary",
                rationale="This is Aegis' origin and strongest daily workflow.",
                mastery_goal="Make project understanding, code changes, validation, repair, checkpoints, and rollback feel fast and trustworthy.",
                success_metrics=["task completion rate", "validation pass rate", "repair success rate", "time to safe diff", "rollback reliability"],
                active_systems=["Task Engine", "Project Intelligence", "Validation", "Repair", "Workspace Safety", "Unified Context"],
                boundaries=["No file write outside approved workspace paths.", "No redesign during stabilization work unless explicitly requested."],
            ),
            PlatformDomainStrategy(
                id="orchestration_runtime",
                name="AI Orchestration Runtime",
                focus="primary",
                rationale="Every serious capability depends on task tracking, approvals, telemetry, workers, and observable state.",
                mastery_goal="Make all work route through clear tasks, timelines, approvals, validation, telemetry, and recovery.",
                success_metrics=["task latency", "approval clarity", "queue reliability", "timeline completeness", "recovery success"],
                active_systems=["Task Engine", "Multi-Agent", "Distributed Runtime", "Unified Runtime", "Continuity"],
                boundaries=["No uncontrolled autonomy.", "No background mutation without explicit task and approval state."],
            ),
            PlatformDomainStrategy(
                id="memory_knowledge_os",
                name="AI Memory And Knowledge OS",
                focus="primary",
                rationale="Continuity is the differentiator that makes Aegis feel coherent instead of tool-shaped.",
                mastery_goal="Make memory, project intelligence, unified context, search, and timeline recall useful without becoming noisy.",
                success_metrics=["context relevance", "memory usefulness", "search success", "timeline reconstruction quality", "low-noise suggestions"],
                active_systems=["Project Intelligence", "Unified Context", "Presence And Continuity", "Memory Manager", "Ecosystem Knowledge Graph"],
                boundaries=["Memory remains local, inspectable, and user-reviewable.", "No hidden personalization that changes safety behavior."],
            ),
            PlatformDomainStrategy(
                id="automation_platform",
                name="AI Automation Platform",
                focus="secondary",
                rationale="Automation is valuable when it extends real workflows, but should not outrun trust or clarity.",
                mastery_goal="Turn repeated user workflows into task-tracked, approval-gated automations.",
                success_metrics=["automation completion rate", "manual steps saved", "approval friction", "failure recovery"],
                active_systems=["Workspace Operations", "Ecosystem Workflows", "Scheduled Jobs", "Global Command Router"],
                boundaries=["Automation cannot silently write files, run commands, or dispatch remote workers."],
            ),
            PlatformDomainStrategy(
                id="creative_studio",
                name="AI Creative Studio",
                focus="secondary",
                rationale="Creative generation is useful when it connects to projects, assets, docs, and workflows.",
                mastery_goal="Keep local creative assets organized, exportable, and visible to coding/project workflows.",
                success_metrics=["asset reuse in tasks", "export success", "generation failure clarity", "approval correctness"],
                active_systems=["Creative Studio", "Asset Library", "Unified Context", "Global Command Router"],
                boundaries=["Paid, GPU-heavy, copyright-sensitive, and voice-cloning flows remain approval-gated."],
            ),
            PlatformDomainStrategy(
                id="research_environment",
                name="AI Research Environment",
                focus="secondary",
                rationale="Research supports projects and decisions, but should mature after source/citation quality is solid.",
                mastery_goal="Create source-backed research sessions that attach to tasks, memory, and knowledge graphs.",
                success_metrics=["citation coverage", "source quality", "research-to-task conversion", "retrieval accuracy"],
                active_systems=["Unified Context", "Ecosystem Search", "Task Engine"],
                boundaries=["Live network access is policy-gated and citation-backed."],
            ),
            PlatformDomainStrategy(
                id="desktop_operating_layer",
                name="AI Desktop Operating Layer",
                focus="experimental",
                rationale="Desktop control is powerful and risky; keep it preview-first until adapters and consent UX are excellent.",
                mastery_goal="Provide safe screen/context assistance before executable desktop control.",
                success_metrics=["permission clarity", "adapter trust", "false action rate", "user cancellation rate"],
                active_systems=["Operating Environment", "Global Command Router"],
                boundaries=["No keyboard/mouse, clipboard, app launch, or screen capture without trusted adapter and explicit approval."],
            ),
            PlatformDomainStrategy(
                id="security_workspace",
                name="AI Security Workspace",
                focus="experimental",
                rationale="Security workflows require strict sandboxing, authorization, and audit before deeper productization.",
                mastery_goal="Build read-only inspection and lab-safe workflows first.",
                success_metrics=["audit completeness", "sandbox isolation", "permission correctness", "false-positive rate"],
                active_systems=["Operating Environment", "Productization", "Ecosystem"],
                boundaries=["No process/network/security tracing outside approved lab scopes."],
            ),
        ]

    def _roadmap(self) -> list[PlatformRoadmapItem]:
        return [
            PlatformRoadmapItem(
                id="daily_coding_loop",
                title="Daily Coding Loop",
                category="mvp_workflow",
                status="production_ready",
                domain="coding_workspace",
                summary="Ask, plan, inspect, edit, approve, checkpoint, validate, repair, summarize.",
                owner_layer="layer_3_domain_systems",
                exit_criteria=["validation passes", "checkpoint created before writes", "task timeline complete"],
                complexity_cost="medium",
                ux_impact="positive",
            ),
            PlatformRoadmapItem(
                id="workspace_safety",
                title="Workspace Safety And Rollback",
                category="stable_core",
                status="production_ready",
                domain="orchestration_runtime",
                summary="Allowed roots, FileChange validation, checkpoints, restore, skipped unsafe writes.",
                owner_layer="layer_1_core_runtime",
                exit_criteria=["unsafe paths rejected", "rollback tested", "warnings preserved"],
                complexity_cost="medium",
                ux_impact="positive",
            ),
            PlatformRoadmapItem(
                id="task_memory_orchestration",
                title="Task Engine, Memory, And Timeline",
                category="stable_core",
                status="production_ready",
                domain="orchestration_runtime",
                summary="Persistent tasks, subtasks, approvals, events, artifacts, memory, and continuity recall.",
                owner_layer="layer_2_task_memory_orchestration",
                exit_criteria=["state transitions tested", "timeline searchable", "memory visible and editable"],
                complexity_cost="medium",
                ux_impact="positive",
            ),
            PlatformRoadmapItem(
                id="project_intelligence_context",
                title="Project Intelligence And Unified Context",
                category="stable_core",
                status="beta",
                domain="memory_knowledge_os",
                summary="Project profiles, architecture map, file importance, unified context graph, global command routing.",
                owner_layer="layer_2_task_memory_orchestration",
                exit_criteria=["context relevance benchmarked", "search quality measured", "irrelevant context reduced"],
                complexity_cost="high",
                ux_impact="positive",
            ),
            PlatformRoadmapItem(
                id="presence_continuity",
                title="Presence And Continuity",
                category="long_term",
                status="beta",
                domain="memory_knowledge_os",
                summary="Ambient presence, operating timeline, forecasts, cognitive pacing, self-diagnostics, memory distillation.",
                owner_layer="layer_4_intelligence_surfaces",
                exit_criteria=["suggestions remain low-noise", "forecasts are explainable", "no fake emotion inference"],
                complexity_cost="medium",
                ux_impact="positive",
            ),
            PlatformRoadmapItem(
                id="creative_asset_loop",
                title="Creative Asset Loop",
                category="mvp_workflow",
                status="beta",
                domain="creative_studio",
                summary="Generate local assets, organize library, export, and attach assets to project tasks.",
                owner_layer="layer_3_domain_systems",
                exit_criteria=["exports work", "assets appear in unified context", "paid/GPU/voice risks gated"],
                complexity_cost="medium",
                ux_impact="positive",
            ),
            PlatformRoadmapItem(
                id="automation_workflows",
                title="Task-Tracked Automation Workflows",
                category="long_term",
                status="beta",
                domain="automation_platform",
                summary="Reusable workflows, scheduled jobs, recommendation-to-task flow, approval gates.",
                owner_layer="layer_3_domain_systems",
                exit_criteria=["no silent writes", "workflow failures recoverable", "task timeline complete"],
                complexity_cost="high",
                ux_impact="positive",
            ),
            PlatformRoadmapItem(
                id="desktop_control",
                title="Desktop Control And Screen Understanding",
                category="experimental",
                status="experimental",
                domain="desktop_operating_layer",
                summary="Preview-first OS/screen capability registry; executable adapters blocked until trust is mature.",
                owner_layer="layer_4_intelligence_surfaces",
                exit_criteria=["adapter signing", "capture consent", "visible audit", "per-action approvals"],
                blocked_by=["trusted desktop adapter", "screen capture consent UX"],
                complexity_cost="high",
                ux_impact="risky",
            ),
            PlatformRoadmapItem(
                id="security_lab",
                title="Security Analysis Workspace",
                category="experimental",
                status="internal_only",
                domain="security_workspace",
                summary="Security analysis remains lab-scoped until sandboxing and authorization are first-class.",
                owner_layer="layer_4_intelligence_surfaces",
                exit_criteria=["isolated lab policy", "audit logs", "permission scopes", "no external targets by default"],
                blocked_by=["lab sandbox adapter"],
                complexity_cost="high",
                ux_impact="risky",
            ),
            PlatformRoadmapItem(
                id="dashboard_sprawl",
                title="Dashboard Sprawl",
                category="deprecated",
                status="deprecated",
                domain="all",
                summary="Avoid adding a new dashboard for every new idea; converge inside Runtime, Tasks, Workspace, Creative, and Intelligence.",
                owner_layer="layer_4_intelligence_surfaces",
                exit_criteria=["new surfaces justify workflow value", "duplicate panels removed"],
                complexity_cost="high",
                ux_impact="risky",
            ),
            PlatformRoadmapItem(
                id="uncontrolled_autonomy",
                title="Uncontrolled Autonomy",
                category="deprecated",
                status="deprecated",
                domain="all",
                summary="No silent code changes, unbounded loops, hidden desktop control, or background mutation.",
                owner_layer="layer_1_core_runtime",
                exit_criteria=["blocked by policy and tests"],
                complexity_cost="high",
                ux_impact="risky",
            ),
        ]

    def _stability_tiers(self) -> list[PlatformStabilityTier]:
        return [
            PlatformStabilityTier(
                id="stable_runtime",
                name="Stable Runtime",
                description="Default user experience. Must preserve contracts and pass validation.",
                allowed_statuses=["production_ready", "beta"],
                entry_requirements=["regression tests", "documented endpoint/type contracts", "clear rollback behavior", "no silent unsafe action"],
                release_rules=["visible by default", "must not degrade daily coding workflow", "must pass npm run validate"],
                user_visibility="default",
            ),
            PlatformStabilityTier(
                id="experimental_runtime",
                name="Experimental Runtime",
                description="Promising but not yet proven features with explicit labels and narrow scope.",
                allowed_statuses=["beta", "experimental"],
                entry_requirements=["feature labeled beta/experimental", "approval gates for risky work", "escape hatch or disable path"],
                release_rules=["visible with label", "must not block stable workflows", "must collect feedback before promotion"],
                user_visibility="visible_with_label",
            ),
            PlatformStabilityTier(
                id="sandbox_features",
                name="Sandbox Features",
                description="Adapters and plugins that can affect files, commands, providers, desktop, workers, or network.",
                allowed_statuses=["experimental", "internal_only"],
                entry_requirements=["permission scopes", "sandbox profile", "audit trail", "trust level"],
                release_rules=["hidden by default unless enabled", "must route through task/tool contracts"],
                user_visibility="hidden_by_default",
            ),
            PlatformStabilityTier(
                id="unsafe_research",
                name="Unsafe Or Research-Only",
                description="Capabilities that remain blocked until safety foundations are mature.",
                allowed_statuses=["internal_only", "deprecated"],
                entry_requirements=["threat model", "explicit authorization", "isolated environment"],
                release_rules=["blocked in normal product", "no production UX entrypoint"],
                user_visibility="blocked",
            ),
        ]

    def _feedback_loops(self, runtime: UnifiedRuntimeSnapshot | None, continuity: AegisContinuitySnapshot | None) -> list[PlatformFeedbackLoop]:
        active_counts = runtime.active_counts if runtime else {}
        return [
            PlatformFeedbackLoop(id="workflow_success", name="Workflow Success Tracking", status="partial", signal="completed tasks and final summaries", metric="task completion rate", source="Task Engine", cadence="per task", improvement_rule="Improve the workflows users actually complete.", current_value=float(active_counts.get("tasks", 0)), notes=["Use outcomes before roadmap assumptions."]),
            PlatformFeedbackLoop(id="validation_quality", name="Validation And Repair Quality", status="partial", signal="validation events and repair attempts", metric="validation pass and repair success rate", source="Task timelines", cadence="per validation", improvement_rule="Prioritize recurring failures with high user impact."),
            PlatformFeedbackLoop(id="latency", name="Latency And Responsiveness", status="partial", signal="routing, queue, model, and UI timings", metric="time to first useful response", source="Telemetry snapshots", cadence="rolling", improvement_rule="Cut latency where daily workflows stall."),
            PlatformFeedbackLoop(id="context_relevance", name="Context Relevance", status="partial", signal="unified context search and task outcome", metric="useful context ratio", source="Unified Context", cadence="per task", improvement_rule="Remove context that does not affect successful outcomes."),
            PlatformFeedbackLoop(id="presence_noise", name="Presence Noise Control", status="partial", signal="suggestion intensity and dismissed recommendations", metric="suggestion acceptance/dismissal ratio", source="Continuity", cadence="session", improvement_rule="Reduce proactive suggestions when they are not acted on.", current_value=float(len(continuity.presence.proactive_suggestions)) if continuity else None, target_value=4),
            PlatformFeedbackLoop(id="failure_analytics", name="Failure Analytics", status="partial", signal="failed tasks, blocked queue jobs, degraded diagnostics", metric="failure recurrence", source="Continuity diagnostics", cadence="daily", improvement_rule="Fix high-frequency failures before expanding features."),
        ]

    def _design_standards(self) -> list[PlatformDesignStandard]:
        return [
            PlatformDesignStandard(id="surface_convergence", category="ui", rule="New intelligence appears in existing workflow surfaces unless it creates a genuinely new daily workflow.", rationale="Prevents dashboard sprawl.", applies_to=["Runtime", "Tasks", "Workspace", "Intelligence", "Creative"], enforcement="review_required"),
            PlatformDesignStandard(id="task_pattern", category="workflow", rule="Executable work becomes a task with timeline, approval state, validation, telemetry, and recovery path.", rationale="Makes work observable and recoverable.", applies_to=["coding", "automation", "research", "desktop", "creative"], enforcement="tested"),
            PlatformDesignStandard(id="approval_copy", category="safety", rule="Approval prompts must say what will happen, what can go wrong, and whether rollback exists.", rationale="Trust depends on understandable risk.", applies_to=["file writes", "commands", "providers", "desktop", "remote workers"], enforcement="review_required"),
            PlatformDesignStandard(id="memory_schema", category="memory", rule="Memory must include source, confidence, category, user visibility, and update path.", rationale="Prevents hidden or stale personalization.", applies_to=["project memory", "personal memory", "fix memory"], enforcement="documented"),
            PlatformDesignStandard(id="telemetry_shape", category="telemetry", rule="Telemetry must be low-overhead, local-first, actionable, and tied to workflow improvement.", rationale="Avoids noisy metrics.", applies_to=["tasks", "routing", "validation", "latency", "feedback"], enforcement="documented"),
            PlatformDesignStandard(id="agent_events", category="agents", rule="Agents communicate through structured task events, not loose invisible chatter.", rationale="Keeps multi-agent behavior inspectable.", applies_to=["planner", "code", "review", "validation", "repair", "memory"], enforcement="tested"),
        ]

    def _behavior_principles(self) -> list[PlatformBehaviorPrinciple]:
        return [
            PlatformBehaviorPrinciple(id="calm", principle="Calm By Default", do=["Use concise updates.", "Offer one next best action.", "Keep suggestions quiet."], avoid=["noisy autonomy", "notification floods", "performative urgency"], enforcement="Presence suggestions are intensity-capped."),
            PlatformBehaviorPrinciple(id="stewardship", principle="Stewardship Over Expansion", do=["Preserve quality.", "Reduce friction.", "Improve trusted workflows."], avoid=["trend chasing", "complexity overload", "expansion as success"], enforcement="Stewardship posture is part of the platform discipline snapshot."),
            PlatformBehaviorPrinciple(id="say_no", principle="Say No By Default", do=["Reject unclear value.", "Require workflow evidence.", "Prefer deepening existing systems."], avoid=["scope creep", "trend chasing", "capability count as a goal"], enforcement="Feature Admission Gate defaults to reject_when_unclear."),
            PlatformBehaviorPrinciple(id="explainable", principle="Explainable Autonomy", do=["Say why a route/action/repair was chosen.", "Show risk and rollback state."], avoid=["hidden routing changes", "silent background mutation"], enforcement="Global command previews and task timelines expose reasoning."),
            PlatformBehaviorPrinciple(id="focused", principle="Focused Scope", do=["Master primary domains first.", "Promote secondary systems only when usage proves value."], avoid=["feature chasing", "equal-depth investment everywhere"], enforcement="Domain strategy classifies primary/secondary/experimental areas."),
            PlatformBehaviorPrinciple(id="trust", principle="Trust Over Aggression", do=["Ask before risky actions.", "Prefer previews and dry-runs.", "Respect protected zones."], avoid=["unbounded agents", "desktop control without consent", "provider spend without approval"], enforcement="Approval, sandbox, and rollback rules remain mandatory."),
            PlatformBehaviorPrinciple(id="human_centered", principle="Human-Centered Continuity", do=["Adapt pacing from observable workflow load.", "Summarize after repeated failures."], avoid=["fake emotion inference", "robotic repetition"], enforcement="Cognitive awareness records safeguards."),
        ]

    def _performance_budgets(self, continuity: AegisContinuitySnapshot | None) -> list[PlatformPerformanceBudget]:
        timeline_count = len(continuity.timeline.entries) if continuity else 0
        warning_status = "watch" if timeline_count > 250 else "healthy"
        return [
            PlatformPerformanceBudget(id="startup", name="Startup Readiness", category="startup", target="Backend health and frontend shell usable within 3 seconds on a normal local workspace.", warning_threshold="5 seconds", hard_limit="8 seconds", measurement="/api/health plus frontend load smoke", status="unknown", rationale="Aegis should feel fast before it feels powerful."),
            PlatformPerformanceBudget(id="indexing", name="Indexing Time", category="indexing", target="Refresh project intelligence for a medium project in under 30 seconds.", warning_threshold="60 seconds", hard_limit="120 seconds", measurement="Project Intelligence reindex duration", status="unknown", rationale="Context quality must not stall daily work."),
            PlatformPerformanceBudget(id="task_latency", name="Task Latency", category="task", target="Create task and first plan/event in under 2 seconds before model execution.", warning_threshold="5 seconds", hard_limit="10 seconds", measurement="task created_at to first event", status="unknown", rationale="Tasks should feel immediate and concrete."),
            PlatformPerformanceBudget(id="telemetry_overhead", name="Telemetry Overhead", category="telemetry", target="Telemetry writes stay under 5% of workflow time and avoid chat/render stalls.", warning_threshold="10%", hard_limit="15%", measurement="telemetry write timing and UI responsiveness", status="unknown", rationale="Observability should not make the product feel heavy."),
            PlatformPerformanceBudget(id="background_work", name="Background Work", category="runtime", target="Background jobs stay idle or low-priority unless user starts them.", warning_threshold="sustained CPU or queue contention", hard_limit="background work blocking active task", measurement="runtime queue and worker utilization", status="unknown", rationale="Autonomy should never steal focus from active work."),
            PlatformPerformanceBudget(id="context_growth", name="Context Size Growth", category="context", target="Default selected context remains bounded and relevance-ranked.", warning_threshold="timeline over 250 entries or context over 500 records", hard_limit="unbounded context injection", measurement="Unified Context record and timeline counts", status=warning_status, rationale="Memory and context should deepen intelligence without bloat."),
            PlatformPerformanceBudget(id="frontend_bundle", name="Frontend Bundle", category="frontend", target="Keep initial bundle under 500 kB minified or split large surfaces.", warning_threshold="500 kB", hard_limit="750 kB without code-splitting plan", measurement="Vite build output", status="watch", rationale="Runtime surface growth is now pressuring bundle size."),
        ]

    def _security_foundations(self) -> list[PlatformSecurityFoundation]:
        return [
            PlatformSecurityFoundation(id="permissions", name="Permission Model", status="partial", policy="Every tool/adapter/plugin declares permission scope and approval behavior.", enforcement_points=["FileChange", "Operating Environment", "Plugin manifests", "Distributed workers"], gaps=["Unify permission display copy across UI surfaces."]),
            PlatformSecurityFoundation(id="audit", name="Audit Systems", status="partial", policy="Risky actions produce timeline/audit events with actor, action, subject, and result.", enforcement_points=["Task timeline", "Worker audit", "Ecosystem audit", "Global command event"], gaps=["Consolidate audit search into Unified Context."]),
            PlatformSecurityFoundation(id="sandbox", name="Sandbox Isolation", status="partial", policy="Commands, plugins, desktop, security, providers, and remote workers require sandbox/trust boundaries.", enforcement_points=["Approval sandbox", "Distributed runtime", "Plugin validation", "Operating Environment"], gaps=["Desktop and security adapters remain blocked until sandboxed."]),
            PlatformSecurityFoundation(id="encrypted_storage", name="Encrypted Storage", status="planned", policy="Sensitive sync/export/profile data should support encryption and local key control.", enforcement_points=["Remote sync manifests", "future memory exports"], gaps=["SQLite encryption is not yet enforced by default."]),
            PlatformSecurityFoundation(id="trust_levels", name="Trust Levels", status="partial", policy="Plugins, ecosystem packages, workers, and adapters use explicit trust levels.", enforcement_points=["Productization", "Ecosystem", "Distributed Runtime", "Operating Environment"], gaps=["Skill pack install path remains metadata-only."]),
            PlatformSecurityFoundation(id="rollback", name="Rollback Guarantees", status="ready", policy="Workspace writes checkpoint before mutation and restore through manifest-bound rollback.", enforcement_points=["WorkspaceManager", "Task Engine", "Checkpoints"], gaps=["Non-file actions need adapter-specific rollback notes before enablement."]),
        ]

    def _layers(self) -> list[PlatformLayerDefinition]:
        return [
            PlatformLayerDefinition(id="layer_1_core_runtime", name="Layer 1: Core Runtime", responsibility="Settings, FastAPI contracts, provider registry, workspace safety, filesystem, validation, storage, health.", systems=["main.py", "settings.py", "workspace.py", "storage.py", "validation.py", "providers"], allowed_dependencies=[], forbidden_dependencies=["UI surfaces depending on experimental adapters"], stability_expectation="stable_runtime"),
            PlatformLayerDefinition(id="layer_2_task_memory_orchestration", name="Layer 2: Task Engine, Memory, Orchestration", responsibility="Tasks, timelines, memory, context, routing, multi-agent coordination, checkpoints, approvals.", systems=["task_engine.py", "agent_runtime", "memory_manager.py", "unified_context.py", "continuity.py"], allowed_dependencies=["layer_1_core_runtime"], forbidden_dependencies=["direct UI-only state"], stability_expectation="stable_runtime"),
            PlatformLayerDefinition(id="layer_3_domain_systems", name="Layer 3: Coding, Automation, Creative", responsibility="Daily workflows that users actively perform.", systems=["agent.py", "project_intelligence.py", "workspace_operations.py", "creative_media.py"], allowed_dependencies=["layer_1_core_runtime", "layer_2_task_memory_orchestration"], forbidden_dependencies=["desktop/security adapters as hard dependencies"], stability_expectation="stable_runtime"),
            PlatformLayerDefinition(id="layer_4_intelligence_surfaces", name="Layer 4: Desktop, Research, Workflow Intelligence", responsibility="Advanced assistance and contextual surfaces that must remain preview-first or beta until proven.", systems=["operating_environment.py", "ecosystem search", "global command", "presence/continuity"], allowed_dependencies=["layer_1_core_runtime", "layer_2_task_memory_orchestration", "layer_3_domain_systems"], forbidden_dependencies=["direct write/command execution"], stability_expectation="experimental_runtime"),
            PlatformLayerDefinition(id="layer_5_ecosystem_distribution", name="Layer 5: Distributed Runtime, Ecosystem, SDK", responsibility="Workers, plugins, packages, reusable workflows, skill packs, organization policy, distribution.", systems=["distributed_runtime.py", "productization.py", "ecosystem.py"], allowed_dependencies=["layer_1_core_runtime", "layer_2_task_memory_orchestration"], forbidden_dependencies=["bypassing permission/trust policy"], stability_expectation="sandbox_features"),
        ]

    def _maintainability_practices(self) -> list[MaintainabilityPractice]:
        return [
            MaintainabilityPractice(id="large_file_control", practice="Keep large files shrinking through modular components and engine modules.", cadence="each feature slice", signal="App.tsx/backend module size", expected_outcome="Reduced cognitive load and faster reviews."),
            MaintainabilityPractice(id="dead_code", practice="Remove dead telemetry, duplicate panels, and unused abstractions before adding equivalents.", cadence="monthly", signal="unused exports, duplicate UI sections", expected_outcome="Less surface area to maintain."),
            MaintainabilityPractice(id="benchmark_quality", practice="Benchmark planning, routing, repair, validation, and context quality on golden workflows.", cadence="release gate", signal="benchmark regressions", expected_outcome="Intelligence improves from actual workflows."),
            MaintainabilityPractice(id="contract_tests", practice="Every endpoint/type change gets backend and frontend contract coverage.", cadence="every API change", signal="pytest and api.test.ts", expected_outcome="Stable clients and desktop compatibility."),
            MaintainabilityPractice(id="observability_review", practice="Telemetry must answer a product question or be removed.", cadence="quarterly", signal="dashboard clutter and unused metrics", expected_outcome="Actionable observability."),
        ]

    def _recommendations(self, runtime: UnifiedRuntimeSnapshot | None, continuity: AegisContinuitySnapshot | None) -> list[str]:
        recommendations = [
            "Use stewardship as the primary responsibility: preserve trust, performance, cohesion, clarity, and maintainability.",
            "Use the feature admission gate before any new subsystem, workflow, plugin, provider, agent, or UI surface.",
            "Invest first in AI coding workspace, orchestration runtime, and memory/knowledge OS quality.",
            "Keep desktop and security capabilities experimental until adapters, consent UX, sandboxing, and audits are mature.",
            "Treat new features as roadmap candidates that must justify complexity, UX, runtime, and safety cost.",
        ]
        if runtime and runtime.active_counts.get("pending_approvals", 0):
            recommendations.append("Resolve pending approvals before adding more autonomous or remote work.")
        if continuity and continuity.forecasts.risk_score >= 0.65:
            recommendations.append("Use dry-run simulation and conservative pacing for the next risky workflow.")
        return recommendations

    def _warnings(self, runtime: UnifiedRuntimeSnapshot | None, continuity: AegisContinuitySnapshot | None) -> list[str]:
        warnings: list[str] = []
        if runtime and len(runtime.pillars) > 14:
            warnings.append("Capability map is growing; prefer convergence and pruning over more pillars.")
        if continuity and continuity.presence.workload_level in {"heavy", "overloaded"}:
            warnings.append("High workload detected; reduce suggestions and avoid starting more parallel work.")
        return warnings
