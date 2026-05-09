from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .ecosystem import ECOSYSTEM_API_VERSION
from .schemas import (
    AutonomousAgentAssignment,
    AutonomousAnalyticsMetric,
    AutonomousApprovalActionRequest,
    AutonomousApprovalGate,
    AutonomousEngineeringSnapshot,
    AutonomousExplainabilityEntry,
    AutonomousGoalMemory,
    AutonomousObjective,
    AutonomousObjectiveActionRequest,
    AutonomousObjectiveCreateRequest,
    AutonomousObjectiveDetail,
    AutonomousObjectiveIterationRequest,
    AutonomousPhase,
    AutonomousRefactorPlan,
    AutonomousSafetyLimits,
    AutonomousSimulationEstimate,
    AutonomousVerificationSignal,
    ProjectIntelligenceSnapshot,
)
from .storage import utc_now


AUTONOMOUS_ENGINEERING_API_VERSION = ECOSYSTEM_API_VERSION
PHASE_SPECS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("discovery", "Discovery", ("architect", "planner")),
    ("planning", "Planning", ("planner", "architect")),
    ("implementation", "Implementation", ("code", "documentation")),
    ("validation", "Validation", ("validation", "repair")),
    ("review", "Review", ("review", "security")),
    ("optimization", "Optimization", ("performance", "architect")),
    ("finalization", "Finalization", ("memory", "review")),
)
TERMINAL_OBJECTIVE_STATUSES = {"completed", "failed", "canceled"}
ACTIVE_OBJECTIVE_STATUSES = {
    "simulating",
    "queued",
    "discovery",
    "planning",
    "running",
    "needs_approval",
    "validating",
    "repairing",
    "reviewing",
    "optimizing",
    "finalizing",
    "paused",
}
RISKY_DEPENDENCY_TERMS = {"next.js", "nextjs", "dependency", "dependencies", "upgrade", "migrate", "migration", "package"}
ARCHITECTURE_TERMS = {"architecture", "auth", "authentication", "refactor", "migrate", "modernize", "next.js", "nextjs"}
PRODUCTION_TERMS = {"release", "production", "deploy", "security", "audit", "candidate"}


def _fingerprint(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _contains_any(text: str, terms: set[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


class AutonomousEngineeringEngine:
    """Supervised long-running engineering objective orchestration."""

    def create_objective(
        self,
        store: Any,
        *,
        project_root: Path,
        request: AutonomousObjectiveCreateRequest,
        project_intelligence: ProjectIntelligenceSnapshot | None = None,
    ) -> AutonomousObjectiveDetail:
        now = utc_now()
        objective_id = str(uuid4())
        protected = request.protected_file_zones or [".env", "secrets", "production", "deploy", "infra"]
        safety_limits = AutonomousSafetyLimits(
            max_iterations=request.max_iterations,
            max_parallel_agents=request.max_parallel_agents,
            token_budget=request.token_budget,
            protected_file_zones=protected,
            allow_dependency_changes=False,
            allow_destructive_actions=False,
        )
        roles = self._roles_for_goal(request.user_goal)
        objective = AutonomousObjective(
            id=objective_id,
            workspace_root=str(project_root.resolve()),
            title=request.title.strip(),
            user_goal=request.user_goal.strip(),
            status="simulating" if request.dry_run else "queued",
            priority=request.priority,
            created_at=now,
            updated_at=now,
            current_phase="discovery",
            assigned_agent_roles=roles,
            safety_limits=safety_limits,
            goal_memory=AutonomousGoalMemory(
                objective_history=[request.user_goal.strip()],
                remaining_work=[spec[1] for spec in PHASE_SPECS],
                updated_at=now,
            ),
            metadata=request.metadata,
        )
        phases = self._phase_plan(objective, project_intelligence=project_intelligence)
        gates = self._approval_gates(objective, phases, project_intelligence=project_intelligence)
        simulation = self.simulate(objective, phases, gates, project_intelligence=project_intelligence)
        refactor_plans = self._refactor_plans(objective, simulation)
        agents = self._agent_assignments(objective, phases)
        objective = objective.model_copy(
            update={
                "phase_ids": [phase.id for phase in phases],
                "approval_gate_ids": [gate.id for gate in gates],
                "simulation_ids": [simulation.id],
            }
        )
        store.upsert_autonomous_objective(objective)
        for phase in phases:
            store.upsert_autonomous_phase(phase)
        for gate in gates:
            store.upsert_autonomous_approval_gate(gate)
        store.save_autonomous_simulation(simulation)
        for plan in refactor_plans:
            store.upsert_autonomous_refactor_plan(plan)
        for agent in agents:
            store.upsert_autonomous_agent(agent)
        explanation = self._explain(
            objective.id,
            "simulation",
            "Objective created in dry-run mode" if request.dry_run else "Objective created",
            "Aegis created a supervised multi-phase program with explicit approval gates and rollback-oriented safety limits.",
            evidence={
                "phase_count": len(phases),
                "gate_count": len(gates),
                "assigned_agent_roles": roles,
                "dry_run": request.dry_run,
            },
        )
        store.record_autonomous_explanation(explanation)
        return store.autonomous_objective_detail(objective.id)

    def snapshot(self, store: Any, *, project_root: Path) -> AutonomousEngineeringSnapshot:
        root = project_root.resolve()
        objectives = store.autonomous_objectives(project_root=root, limit=80)
        active = [item for item in objectives if item.status in ACTIVE_OBJECTIVE_STATUSES and item.status not in TERMINAL_OBJECTIVE_STATUSES]
        phases = [phase for objective in objectives[:20] for phase in store.autonomous_phases(objective_id=objective.id)]
        gates = store.autonomous_approval_gates(project_root=root, limit=120)
        simulations = [simulation for objective in objectives[:20] for simulation in store.autonomous_simulations(objective_id=objective.id)]
        agents = [agent for objective in objectives[:20] for agent in store.autonomous_agents(objective_id=objective.id)]
        verification = [signal for objective in objectives[:20] for signal in store.autonomous_verification(objective_id=objective.id)]
        refactor_plans = [plan for objective in objectives[:20] for plan in store.autonomous_refactor_plans(objective_id=objective.id)]
        explanations = [entry for objective in objectives[:20] for entry in store.autonomous_explanations(objective_id=objective.id, limit=8)]
        analytics = self.analytics(objectives=objectives, gates=gates, verification=verification)
        recommendations, warnings = self.recommendations(objectives, gates, verification)
        return AutonomousEngineeringSnapshot(
            workspace_root=str(root),
            generated_at=utc_now(),
            api_version=AUTONOMOUS_ENGINEERING_API_VERSION,
            objectives=objectives,
            active_objectives=active,
            phases=phases[:200],
            approval_gates=gates,
            simulations=simulations[:80],
            agents=agents[:200],
            verification=verification[:200],
            refactor_plans=refactor_plans[:100],
            explanations=explanations[:120],
            analytics=analytics,
            recommendations=recommendations,
            warnings=warnings,
        )

    def start_objective(self, store: Any, objective_id: str, request: AutonomousObjectiveActionRequest) -> AutonomousObjectiveDetail:
        detail = store.autonomous_objective_detail(objective_id)
        objective = detail.objective
        if objective.status in TERMINAL_OBJECTIVE_STATUSES:
            raise ValueError("terminal objectives cannot be started")
        pending_required = [gate for gate in detail.approval_gates if gate.required and gate.status == "pending"]
        status = "needs_approval" if pending_required else "discovery"
        objective = objective.model_copy(update={"status": status, "updated_at": utc_now()})
        if not objective.task_ids:
            objective = self._create_task_graph(store, objective, detail.phases)
        store.upsert_autonomous_objective(objective)
        store.record_autonomous_explanation(
            self._explain(
                objective.id,
                "approval" if pending_required else "planning",
                "Objective start requested",
                "Aegis moved the objective to approval review before execution." if pending_required else "Aegis started the supervised execution program.",
                evidence={"pending_gate_ids": [gate.id for gate in pending_required], "reason": request.reason},
            )
        )
        return store.autonomous_objective_detail(objective.id)

    def pause_objective(self, store: Any, objective_id: str, request: AutonomousObjectiveActionRequest) -> AutonomousObjectiveDetail:
        detail = store.autonomous_objective_detail(objective_id)
        objective = detail.objective.model_copy(update={"status": "paused", "updated_at": utc_now()})
        store.upsert_autonomous_objective(objective)
        store.record_autonomous_explanation(
            self._explain(objective.id, "policy", "Objective paused", request.reason or "Objective execution paused by user.")
        )
        return store.autonomous_objective_detail(objective.id)

    def cancel_objective(self, store: Any, objective_id: str, request: AutonomousObjectiveActionRequest) -> AutonomousObjectiveDetail:
        detail = store.autonomous_objective_detail(objective_id)
        now = utc_now()
        objective = detail.objective.model_copy(
            update={"status": "canceled", "updated_at": now, "completed_at": now, "error_summary": request.reason or "Canceled by user."}
        )
        store.upsert_autonomous_objective(objective)
        for phase in detail.phases:
            if phase.status not in {"completed", "failed", "skipped"}:
                store.upsert_autonomous_phase(phase.model_copy(update={"status": "skipped", "completed_at": now}))
        store.record_autonomous_explanation(
            self._explain(objective.id, "policy", "Objective canceled", request.reason or "Objective execution canceled safely.")
        )
        return store.autonomous_objective_detail(objective.id)

    def iterate_objective(
        self,
        store: Any,
        objective_id: str,
        request: AutonomousObjectiveIterationRequest,
    ) -> AutonomousObjectiveDetail:
        detail = store.autonomous_objective_detail(objective_id)
        objective = detail.objective
        if objective.status in TERMINAL_OBJECTIVE_STATUSES:
            raise ValueError("terminal objectives cannot iterate")
        if objective.status == "paused":
            raise ValueError("paused objectives must be started before iteration")
        pending_required = [gate for gate in detail.approval_gates if gate.required and gate.status == "pending"]
        if pending_required:
            objective = objective.model_copy(update={"status": "needs_approval", "updated_at": utc_now()})
            store.upsert_autonomous_objective(objective)
            store.record_autonomous_explanation(
                self._explain(
                    objective.id,
                    "approval",
                    "Iteration paused for approval",
                    "Aegis stopped before modifying high-risk surfaces because approval gates are still pending.",
                    evidence={"pending_gate_ids": [gate.id for gate in pending_required]},
                )
            )
            return store.autonomous_objective_detail(objective.id)
        if objective.iteration_count >= objective.safety_limits.max_iterations:
            objective = objective.model_copy(
                update={
                    "status": "failed",
                    "updated_at": utc_now(),
                    "completed_at": utc_now(),
                    "error_summary": "Iteration cap reached before objective completed.",
                }
            )
            store.upsert_autonomous_objective(objective)
            return store.autonomous_objective_detail(objective.id)

        detail = self._ensure_task_graph(store, detail)
        objective = detail.objective
        phases = detail.phases
        steps = min(request.max_steps, max(1, objective.safety_limits.max_iterations - objective.iteration_count))
        for _ in range(steps):
            next_phase = self._next_phase(phases)
            if next_phase is None:
                objective = self._complete_objective(store, objective, phases)
                break
            now = utc_now()
            running = next_phase.model_copy(
                update={
                    "status": "completed",
                    "started_at": next_phase.started_at or now,
                    "completed_at": now,
                    "iteration_count": next_phase.iteration_count + 1,
                    "summary": self._phase_summary(next_phase),
                }
            )
            store.upsert_autonomous_phase(running)
            objective = self._advance_objective_after_phase(store, objective, running)
            self._record_phase_verification(store, objective, running)
            store.record_autonomous_explanation(
                self._explain(
                    objective.id,
                    "planning" if running.kind in {"discovery", "planning"} else "validation" if running.kind == "validation" else "change",
                    f"{running.title} completed",
                    self._phase_explanation(running),
                    evidence={
                        "phase_id": running.id,
                        "kind": running.kind,
                        "agent_roles": running.agent_roles,
                        "reason": request.reason,
                    },
                )
            )
            phases = [running if phase.id == running.id else phase for phase in phases]
        objective = objective.model_copy(update={"iteration_count": objective.iteration_count + 1, "updated_at": utc_now()})
        store.upsert_autonomous_objective(objective)
        return store.autonomous_objective_detail(objective.id)

    def approve_gate(self, store: Any, gate_id: str, request: AutonomousApprovalActionRequest) -> AutonomousObjectiveDetail:
        gate = store.autonomous_approval_gate(gate_id)
        updated = gate.model_copy(
            update={
                "status": "approved",
                "resolved_at": utc_now(),
                "resolved_by": request.resolved_by,
                "metadata": {**gate.metadata, **request.metadata, "reason": request.reason},
            }
        )
        store.upsert_autonomous_approval_gate(updated)
        detail = store.autonomous_objective_detail(updated.objective_id)
        pending = [item for item in detail.approval_gates if item.required and item.status == "pending" and item.id != gate_id]
        objective = detail.objective
        if objective.status == "needs_approval" and not pending:
            objective = objective.model_copy(update={"status": "discovery", "updated_at": utc_now()})
            store.upsert_autonomous_objective(objective)
        store.record_autonomous_explanation(
            self._explain(
                updated.objective_id,
                "approval",
                f"Approval gate approved: {updated.title}",
                request.reason or updated.reason,
                evidence={"gate_id": gate_id, "resolved_by": request.resolved_by},
            )
        )
        return store.autonomous_objective_detail(updated.objective_id)

    def reject_gate(self, store: Any, gate_id: str, request: AutonomousApprovalActionRequest) -> AutonomousObjectiveDetail:
        gate = store.autonomous_approval_gate(gate_id)
        updated = gate.model_copy(
            update={
                "status": "rejected",
                "resolved_at": utc_now(),
                "resolved_by": request.resolved_by,
                "metadata": {**gate.metadata, **request.metadata, "reason": request.reason},
            }
        )
        store.upsert_autonomous_approval_gate(updated)
        detail = store.autonomous_objective_detail(updated.objective_id)
        objective = detail.objective.model_copy(
            update={
                "status": "paused",
                "updated_at": utc_now(),
                "error_summary": f"Approval gate rejected: {updated.title}.",
            }
        )
        store.upsert_autonomous_objective(objective)
        store.record_autonomous_explanation(
            self._explain(
                updated.objective_id,
                "approval",
                f"Approval gate rejected: {updated.title}",
                request.reason or "The objective paused because a required gate was rejected.",
                evidence={"gate_id": gate_id, "resolved_by": request.resolved_by},
            )
        )
        return store.autonomous_objective_detail(updated.objective_id)

    def simulate_existing(
        self,
        store: Any,
        objective_id: str,
        project_intelligence: ProjectIntelligenceSnapshot | None = None,
    ) -> AutonomousSimulationEstimate:
        detail = store.autonomous_objective_detail(objective_id)
        simulation = self.simulate(detail.objective, detail.phases, detail.approval_gates, project_intelligence=project_intelligence)
        store.save_autonomous_simulation(simulation)
        objective = detail.objective.model_copy(
            update={"simulation_ids": [*detail.objective.simulation_ids, simulation.id], "updated_at": utc_now()}
        )
        store.upsert_autonomous_objective(objective)
        store.record_autonomous_explanation(
            self._explain(
                objective.id,
                "simulation",
                "Dry-run simulation refreshed",
                "Aegis recalculated estimated impact, validation risk, projected file changes, and approval gates.",
                evidence={"simulation_id": simulation.id, "risk": simulation.predicted_validation_risk},
            )
        )
        return simulation

    def analytics(
        self,
        *,
        objectives: list[AutonomousObjective],
        gates: list[AutonomousApprovalGate],
        verification: list[AutonomousVerificationSignal],
    ) -> list[AutonomousAnalyticsMetric]:
        completed = [item for item in objectives if item.status == "completed"]
        failed = [item for item in objectives if item.status == "failed"]
        total = len(objectives)
        passed = [item for item in verification if item.status == "passed"]
        failed_checks = [item for item in verification if item.status == "failed"]
        approved = [item for item in gates if item.status == "approved"]
        pending = [item for item in gates if item.status == "pending"]
        completion_rate = len(completed) / total if total else 0.0
        validation_rate = len(passed) / (len(passed) + len(failed_checks)) if (passed or failed_checks) else 1.0
        approval_rate = len(approved) / (len(approved) + len(pending)) if (approved or pending) else 1.0
        avg_iterations = sum(item.iteration_count for item in objectives) / total if total else 0.0
        return [
            AutonomousAnalyticsMetric(
                name="objective_completion_rate",
                value=completion_rate,
                unit="ratio",
                status="healthy" if completion_rate >= 0.8 or total == 0 else "watch",
                detail=f"{len(completed)} completed, {len(failed)} failed, {total} total objectives.",
                trend="stable",
            ),
            AutonomousAnalyticsMetric(
                name="validation_reliability",
                value=validation_rate,
                unit="ratio",
                status="healthy" if validation_rate >= 0.85 else "watch",
                detail=f"{len(passed)} verification signal(s) passed and {len(failed_checks)} failed.",
                trend="stable",
            ),
            AutonomousAnalyticsMetric(
                name="approval_gate_clearance",
                value=approval_rate,
                unit="ratio",
                status="healthy" if not pending else "watch",
                detail=f"{len(approved)} approval gate(s) approved and {len(pending)} pending.",
                trend="stable",
            ),
            AutonomousAnalyticsMetric(
                name="average_iteration_count",
                value=avg_iterations,
                unit="count",
                status="healthy" if avg_iterations <= 5 else "watch",
                detail="Average supervised iteration count across objectives.",
                trend="stable",
            ),
        ]

    def recommendations(
        self,
        objectives: list[AutonomousObjective],
        gates: list[AutonomousApprovalGate],
        verification: list[AutonomousVerificationSignal],
    ) -> tuple[list[str], list[str]]:
        recommendations: list[str] = []
        warnings: list[str] = []
        if not objectives:
            recommendations.append("Create a dry-run objective before starting long-running autonomous engineering work.")
        if any(gate.status == "pending" for gate in gates):
            recommendations.append("Resolve pending approval gates before allowing objective iteration.")
        if any(signal.status == "failed" for signal in verification):
            warnings.append("Verification failures exist; keep objectives paused or in repair until failures are summarized.")
        if any(item.status == "running" and item.iteration_count >= item.safety_limits.max_iterations for item in objectives):
            warnings.append("At least one objective is near its iteration cap.")
        return recommendations[:8], warnings[:8]

    def simulate(
        self,
        objective: AutonomousObjective,
        phases: list[AutonomousPhase],
        gates: list[AutonomousApprovalGate],
        *,
        project_intelligence: ProjectIntelligenceSnapshot | None = None,
    ) -> AutonomousSimulationEstimate:
        goal = objective.user_goal
        important_files = [item.path for item in (project_intelligence.file_importance if project_intelligence else [])[:12]]
        stack = project_intelligence.profile.stack if project_intelligence else []
        projected_files = important_files[:8]
        if _contains_any(goal, {"ui", "frontend", "next.js", "nextjs"}):
            projected_files.extend([path for path in important_files if "frontend" in path.lower() or "src" in path.lower()][:4])
        projected_files = list(dict.fromkeys(projected_files))[:12]
        dependency_changes = []
        if _contains_any(goal, RISKY_DEPENDENCY_TERMS):
            dependency_changes = [
                "package.json",
                "package-lock.json",
                "pnpm-lock.yaml",
                "yarn.lock",
                "bun.lock",
                "bun.lockb",
                "uv.lock",
                "poetry.lock",
                "pdm.lock",
                "Cargo.lock",
                "go.sum",
                "packages.lock.json",
                "packages.config",
                "Directory.Packages.props",
            ]
        risk = 0.25
        if _contains_any(goal, ARCHITECTURE_TERMS):
            risk += 0.2
        if dependency_changes:
            risk += 0.2
        if _contains_any(goal, PRODUCTION_TERMS):
            risk += 0.15
        if len(projected_files) > 8:
            risk += 0.1
        risk = min(1.0, risk)
        impact = "very_high" if risk >= 0.75 else "high" if risk >= 0.55 else "medium" if risk >= 0.3 else "low"
        projected_iterations = min(objective.safety_limits.max_iterations, max(1, len(phases) // 2))
        token_cost = min(
            objective.safety_limits.token_budget,
            4000 + len(projected_files) * 1400 + len(stack) * 600 + projected_iterations * 2500,
        )
        warnings = []
        if dependency_changes and not objective.safety_limits.allow_dependency_changes:
            warnings.append("Dependency changes are projected but disabled until approval explicitly allows them.")
        if gates:
            warnings.append("Approval gates must clear before autonomous iteration can modify risky surfaces.")
        return AutonomousSimulationEstimate(
            id=str(uuid4()),
            objective_id=objective.id,
            workspace_root=objective.workspace_root,
            created_at=utc_now(),
            estimated_impact=impact,
            predicted_validation_risk=risk,
            projected_file_changes=projected_files,
            projected_dependency_changes=dependency_changes,
            projected_token_cost=token_cost,
            projected_iterations=projected_iterations,
            dry_run_plan=[phase.title for phase in phases],
            approval_gates=gates,
            warnings=warnings,
            metadata={"stack": stack, "goal_fingerprint": _fingerprint(goal)[:16]},
        )

    def _phase_plan(
        self,
        objective: AutonomousObjective,
        *,
        project_intelligence: ProjectIntelligenceSnapshot | None,
    ) -> list[AutonomousPhase]:
        validation_commands = project_intelligence.validation_commands[:8] if project_intelligence else []
        phases: list[AutonomousPhase] = []
        for kind, title, roles in PHASE_SPECS:
            phase_id = str(uuid4())
            phases.append(
                AutonomousPhase(
                    id=phase_id,
                    objective_id=objective.id,
                    workspace_root=objective.workspace_root,
                    kind=kind,  # type: ignore[arg-type]
                    title=title,
                    agent_roles=list(roles),  # type: ignore[list-item]
                    validation_commands=validation_commands if kind == "validation" else [],
                    approval_required=kind in {"implementation", "optimization"} and bool(objective.approval_gate_ids),
                    metadata={"goal": objective.user_goal},
                )
            )
        return phases

    def _approval_gates(
        self,
        objective: AutonomousObjective,
        phases: list[AutonomousPhase],
        *,
        project_intelligence: ProjectIntelligenceSnapshot | None,
    ) -> list[AutonomousApprovalGate]:
        goal = objective.user_goal
        now = utc_now()
        phase_by_kind = {phase.kind: phase.id for phase in phases}
        gates: list[AutonomousApprovalGate] = [
            AutonomousApprovalGate(
                id=str(uuid4()),
                objective_id=objective.id,
                phase_id=phase_by_kind.get("implementation", ""),
                kind="large_file_change",
                title="Approve large file-change batches",
                reason="Long-running engineering objectives may touch many files; changes must remain checkpointed and reviewable.",
                created_at=now,
            )
        ]
        if _contains_any(goal, RISKY_DEPENDENCY_TERMS):
            gates.append(
                AutonomousApprovalGate(
                    id=str(uuid4()),
                    objective_id=objective.id,
                    phase_id=phase_by_kind.get("implementation", ""),
                    kind="dependency_change",
                    title="Approve dependency changes",
                    reason="The objective appears to require package or dependency changes.",
                    created_at=now,
                )
            )
        if _contains_any(goal, ARCHITECTURE_TERMS):
            gates.append(
                AutonomousApprovalGate(
                    id=str(uuid4()),
                    objective_id=objective.id,
                    phase_id=phase_by_kind.get("planning", ""),
                    kind="architecture_change",
                    title="Approve architecture changes",
                    reason="The objective may alter module boundaries or framework architecture.",
                    created_at=now,
                )
            )
        if _contains_any(goal, PRODUCTION_TERMS):
            gates.append(
                AutonomousApprovalGate(
                    id=str(uuid4()),
                    objective_id=objective.id,
                    phase_id=phase_by_kind.get("review", ""),
                    kind="production_impact",
                    title="Approve production-impacting actions",
                    reason="The objective references release, deployment, production, or security posture.",
                    created_at=now,
                )
            )
        sensitive = project_intelligence.profile.risk_sensitive_files[:8] if project_intelligence else []
        if sensitive:
            gates.append(
                AutonomousApprovalGate(
                    id=str(uuid4()),
                    objective_id=objective.id,
                    phase_id=phase_by_kind.get("implementation", ""),
                    kind="protected_file",
                    title="Approve protected file zones",
                    reason="Project Intelligence detected risk-sensitive files that require explicit review before edits.",
                    created_at=now,
                    metadata={"risk_sensitive_files": sensitive},
                )
            )
        return gates

    def _refactor_plans(self, objective: AutonomousObjective, simulation: AutonomousSimulationEstimate) -> list[AutonomousRefactorPlan]:
        goal = objective.user_goal.lower()
        kind = "architecture_reorg"
        if "import" in goal:
            kind = "import_migration"
        elif "api" in goal:
            kind = "api_migration"
        elif "dependency" in goal or "upgrade" in goal or "next" in goal:
            kind = "dependency_upgrade"
        elif "ui" in goal:
            kind = "ui_modernization"
        elif "test" in goal or "coverage" in goal:
            kind = "test_coverage"
        return [
            AutonomousRefactorPlan(
                id=str(uuid4()),
                objective_id=objective.id,
                kind=kind,  # type: ignore[arg-type]
                title=f"Structured {kind.replace('_', ' ')} plan",
                target_patterns=[objective.title, objective.user_goal],
                projected_files=simulation.projected_file_changes,
                safety_notes=[
                    "Run as small checkpointed task slices.",
                    "Stop on validation failures and summarize repair attempts.",
                    "Require approval before dependency, architecture, destructive, or protected-file changes.",
                ],
                approval_required=True,
                metadata={"simulation_id": simulation.id},
            )
        ]

    def _agent_assignments(self, objective: AutonomousObjective, phases: list[AutonomousPhase]) -> list[AutonomousAgentAssignment]:
        agents: list[AutonomousAgentAssignment] = []
        for phase in phases:
            for role in phase.agent_roles[: objective.safety_limits.max_parallel_agents]:
                agents.append(
                    AutonomousAgentAssignment(
                        id=str(uuid4()),
                        objective_id=objective.id,
                        phase_id=phase.id,
                        role=role,
                        summary=f"{role} agent assigned to {phase.title}.",
                    )
                )
        return agents

    def _create_task_graph(self, store: Any, objective: AutonomousObjective, phases: list[AutonomousPhase]) -> AutonomousObjective:
        parent_task_id = store.create_task(
            mode="develop",
            workspace_root=Path(objective.workspace_root),
            message=objective.user_goal,
            title=objective.title,
            user_goal=objective.user_goal,
            status="needs_approval" if any(phase.approval_required for phase in phases) else "queued",
            priority=objective.priority,
            assigned_agent_role="autonomous",
        )
        task_ids = [parent_task_id]
        for index, phase in enumerate(phases, start=1):
            subtask_id = store.create_task(
                mode="develop",
                workspace_root=Path(objective.workspace_root),
                message=objective.user_goal,
                parent_task_id=parent_task_id,
                title=f"{objective.title}: {phase.title}",
                user_goal=f"{phase.title} for objective: {objective.user_goal}",
                status="needs_approval" if phase.approval_required else "queued",
                priority=index,
                assigned_agent_role=",".join(phase.agent_roles),
                validation_commands=phase.validation_commands,
            )
            task_ids.append(subtask_id)
            store.upsert_autonomous_phase(phase.model_copy(update={"task_ids": [subtask_id]}))
        store.record_event(
            parent_task_id,
            kind="autonomous.objective.created",
            title=f"Autonomous objective: {objective.title}",
            status="warning" if objective.status == "needs_approval" else "ok",
            detail=objective.user_goal,
            payload={
                "objective_id": objective.id,
                "phase_ids": objective.phase_ids,
                "approval_gate_ids": objective.approval_gate_ids,
                "max_iterations": objective.safety_limits.max_iterations,
            },
        )
        return objective.model_copy(update={"task_ids": task_ids, "updated_at": utc_now()})

    def _ensure_task_graph(self, store: Any, detail: AutonomousObjectiveDetail) -> AutonomousObjectiveDetail:
        if detail.objective.task_ids:
            return detail
        objective = self._create_task_graph(store, detail.objective, detail.phases)
        store.upsert_autonomous_objective(objective)
        return store.autonomous_objective_detail(objective.id)

    def _next_phase(self, phases: list[AutonomousPhase]) -> AutonomousPhase | None:
        for phase in phases:
            if phase.status in {"queued", "paused"}:
                return phase
        return None

    def _advance_objective_after_phase(
        self,
        store: Any,
        objective: AutonomousObjective,
        phase: AutonomousPhase,
    ) -> AutonomousObjective:
        next_status: str = {
            "discovery": "planning",
            "planning": "running",
            "implementation": "validating",
            "validation": "reviewing",
            "review": "optimizing",
            "optimization": "finalizing",
            "finalization": "completed",
        }.get(phase.kind, "running")
        memory = objective.goal_memory.model_copy(
            update={
                "completed_phases": [*objective.goal_memory.completed_phases, phase.title],
                "remaining_work": [item for item in objective.goal_memory.remaining_work if item != phase.title],
                "successful_patterns": [*objective.goal_memory.successful_patterns, f"{phase.title} completed with {', '.join(phase.agent_roles)}"],
                "updated_at": utc_now(),
            }
        )
        update: dict[str, Any] = {
            "status": next_status,
            "current_phase": phase.kind,
            "updated_at": utc_now(),
            "goal_memory": memory,
        }
        if next_status == "completed":
            update["completed_at"] = utc_now()
            update["final_summary"] = "All autonomous engineering phases completed under supervised controls."
        saved = objective.model_copy(update=update)
        store.upsert_autonomous_objective(saved)
        return saved

    def _complete_objective(self, store: Any, objective: AutonomousObjective, phases: list[AutonomousPhase]) -> AutonomousObjective:
        now = utc_now()
        saved = objective.model_copy(
            update={
                "status": "completed",
                "updated_at": now,
                "completed_at": now,
                "final_summary": f"Completed {len([phase for phase in phases if phase.status == 'completed'])} supervised phase(s).",
            }
        )
        store.upsert_autonomous_objective(saved)
        return saved

    def _record_phase_verification(self, store: Any, objective: AutonomousObjective, phase: AutonomousPhase) -> None:
        if phase.kind == "validation":
            commands = phase.validation_commands or ["known project validation command"]
            for command in commands[:5]:
                store.record_autonomous_verification(
                    AutonomousVerificationSignal(
                        id=str(uuid4()),
                        objective_id=objective.id,
                        phase_id=phase.id,
                        kind="test",
                        command=command,
                        status="skipped" if command == "known project validation command" else "queued",
                        detail="Validation is queued for controlled execution." if command != "known project validation command" else "No concrete validation command is saved yet.",
                        created_at=utc_now(),
                    )
                )
        elif phase.kind == "review":
            store.record_autonomous_verification(
                AutonomousVerificationSignal(
                    id=str(uuid4()),
                    objective_id=objective.id,
                    phase_id=phase.id,
                    kind="architecture",
                    status="warning",
                    detail="Architecture consistency review is required before finalization.",
                    created_at=utc_now(),
                )
            )

    def _roles_for_goal(self, goal: str) -> list[str]:
        roles = ["planner", "architect", "code", "review", "validation", "memory"]
        lowered = goal.lower()
        if "security" in lowered or "audit" in lowered:
            roles.append("security")
        if "performance" in lowered or "optimiz" in lowered:
            roles.append("performance")
        if "doc" in lowered or "release" in lowered:
            roles.append("documentation")
        return list(dict.fromkeys(roles))

    def _phase_summary(self, phase: AutonomousPhase) -> str:
        return f"{phase.title} completed by {', '.join(phase.agent_roles)} agent role(s) with controlled supervision."

    def _phase_explanation(self, phase: AutonomousPhase) -> str:
        if phase.kind == "discovery":
            return "Aegis inspected existing project intelligence and task history before planning changes."
        if phase.kind == "planning":
            return "Aegis decomposed the objective into checkpointed, approval-gated work slices."
        if phase.kind == "implementation":
            return "Aegis prepared implementation work as tracked tasks; file edits still require normal approval and checkpoint handling."
        if phase.kind == "validation":
            return "Aegis queued validation signals and will stop safely if verification fails."
        if phase.kind == "review":
            return "Aegis recorded review requirements for architecture consistency, policy compliance, and edge-case checks."
        if phase.kind == "optimization":
            return "Aegis limited optimization work to bounded, reversible follow-up slices."
        return "Aegis finalized the objective by summarizing outcomes, remaining work, and memory updates."

    def _explain(
        self,
        objective_id: str,
        category: str,
        title: str,
        detail: str,
        *,
        evidence: dict[str, Any] | None = None,
    ) -> AutonomousExplainabilityEntry:
        return AutonomousExplainabilityEntry(
            id=str(uuid4()),
            objective_id=objective_id,
            created_at=utc_now(),
            category=category,  # type: ignore[arg-type]
            title=title,
            detail=detail,
            evidence=evidence or {},
        )
