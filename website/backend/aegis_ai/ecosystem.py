from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .productization import PRODUCTIZATION_API_VERSION
from .schemas import (
    CrossProjectInsight,
    EcosystemAuditEvent,
    EcosystemPackageManifest,
    EcosystemPackageValidationRequest,
    EcosystemPackageValidationResult,
    EcosystemRefreshRequest,
    EcosystemSearchRequest,
    EcosystemSearchResponse,
    EcosystemSearchResult,
    EcosystemSnapshot,
    EcosystemWorkflowDefinition,
    GovernanceTrustSignal,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    KnowledgeGraphSnapshot,
    OrganizationPolicyProfile,
    ProjectIntelligenceSnapshot,
    ReproducibilityArtifact,
    ReproducibilityRecord,
    SharedIntelligenceProfile,
    TeamCollaborationSummary,
    ToolEvent,
    WorkflowApprovalRequirement,
    WorkflowRunRequest,
    WorkflowRunResponse,
    WorkflowStepDefinition,
)
from .settings import Settings
from .storage import utc_now


ECOSYSTEM_API_VERSION = PRODUCTIZATION_API_VERSION
HIGH_RISK_PACKAGE_PERMISSIONS = {
    "write_workspace",
    "run_commands",
    "network",
    "model_access",
    "provider",
    "sync",
    "collaboration_write",
    "organization_policy",
}
PACKAGE_KIND_PERMISSION_HINTS: dict[str, set[str]] = {
    "agent": {"read_workspace", "model_access", "task_events"},
    "validator": {"read_workspace", "run_validation"},
    "scaffold_pack": {"scaffold", "write_workspace"},
    "workflow": {"task_graph", "approval", "run_validation"},
    "routing_profile": {"model_access", "routing"},
    "telemetry_analyzer": {"telemetry"},
    "workspace_intelligence_pack": {"read_workspace", "workspace_intelligence"},
}
TRUST_SCORE: dict[str, float] = {
    "untrusted": 0.1,
    "reviewed": 0.45,
    "trusted": 0.7,
    "organization": 0.9,
    "signed": 1.0,
}


def _fingerprint(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _node_id(kind: str, value: str) -> str:
    return f"{kind}:{hashlib.sha1(value.encode('utf-8')).hexdigest()[:16]}"


def _tokens(text: str) -> set[str]:
    cleaned = "".join(char.lower() if char.isalnum() else " " for char in text)
    return {part for part in cleaned.split() if len(part) >= 2}


class EcosystemEngine:
    """Reusable marketplace, workflow, shared intelligence, graph, and governance infrastructure."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def marketplace_catalog(self) -> list[EcosystemPackageManifest]:
        return [
            EcosystemPackageManifest(
                id="aegis-planner-agent-pack",
                name="Aegis Planner Agent Pack",
                kind="agent",
                version="1.0.0",
                api_version=ECOSYSTEM_API_VERSION,
                description="Reusable planning and risk decomposition agent profile pack.",
                author="Aegis",
                trust_level="signed",
                sandbox_permissions=["isolated"],
                permission_scopes=["read_workspace", "model_access", "task_events"],
                update_channel="stable",
                signature="builtin",
                signing_key_fingerprint="aegis-builtin",
                checksum="builtin",
                metadata={"agents": ["planner", "architect", "review"]},
            ),
            EcosystemPackageManifest(
                id="aegis-release-workflows",
                name="Aegis Release Workflow Pack",
                kind="workflow",
                version="1.0.0",
                api_version=ECOSYSTEM_API_VERSION,
                description="Release preparation, validation, and deployment readiness workflows.",
                author="Aegis",
                trust_level="signed",
                sandbox_permissions=["isolated"],
                permission_scopes=["task_graph", "approval", "run_validation"],
                update_channel="stable",
                signature="builtin",
                signing_key_fingerprint="aegis-builtin",
                checksum="builtin",
            ),
            EcosystemPackageManifest(
                id="aegis-architecture-intelligence-pack",
                name="Aegis Architecture Intelligence Pack",
                kind="workspace_intelligence_pack",
                version="1.0.0",
                api_version=ECOSYSTEM_API_VERSION,
                description="Architecture map, duplication, TODO, and drift analysis heuristics.",
                author="Aegis",
                trust_level="signed",
                sandbox_permissions=["isolated"],
                permission_scopes=["read_workspace", "workspace_intelligence"],
                update_channel="stable",
                signature="builtin",
                signing_key_fingerprint="aegis-builtin",
                checksum="builtin",
            ),
            EcosystemPackageManifest(
                id="aegis-validation-profile-pack",
                name="Aegis Validation Profile Pack",
                kind="validator",
                version="1.0.0",
                api_version=ECOSYSTEM_API_VERSION,
                description="Reusable validation standards for Python, TypeScript, and mixed workspaces.",
                author="Aegis",
                trust_level="signed",
                sandbox_permissions=["isolated"],
                permission_scopes=["read_workspace", "run_validation"],
                update_channel="stable",
                signature="builtin",
                signing_key_fingerprint="aegis-builtin",
                checksum="builtin",
            ),
        ]

    def workflow_templates(self) -> list[EcosystemWorkflowDefinition]:
        return [
            EcosystemWorkflowDefinition(
                id="full_stack_bootstrap",
                name="Full-Stack Project Bootstrap",
                version="1.0.0",
                api_version=ECOSYSTEM_API_VERSION,
                category="bootstrap",
                description="Create a structured full-stack project with checkpoints and validation gates.",
                required_agents=["planner", "architect", "code", "review", "validation", "memory"],
                validation_commands=["npm run validate"],
                approvals=[
                    WorkflowApprovalRequirement(
                        id="approve-scaffold",
                        title="Approve generated project scaffold",
                        reason="Creating a project writes multiple files.",
                        required_before_step="edit-files",
                    )
                ],
                steps=[
                    WorkflowStepDefinition(id="inspect", title="Inspect workspace", kind="inspect", agent_role="architect"),
                    WorkflowStepDefinition(id="plan", title="Plan scaffold", kind="plan", agent_role="planner", depends_on=["inspect"]),
                    WorkflowStepDefinition(
                        id="edit-files",
                        title="Generate project files",
                        kind="edit",
                        agent_role="code",
                        depends_on=["plan"],
                        approval_required=True,
                    ),
                    WorkflowStepDefinition(id="review", title="Review scaffold", kind="review", agent_role="review", depends_on=["edit-files"]),
                    WorkflowStepDefinition(
                        id="validate",
                        title="Validate project",
                        kind="validate",
                        agent_role="validation",
                        depends_on=["review"],
                        validation_commands=["npm run validate"],
                        max_attempts=2,
                    ),
                    WorkflowStepDefinition(id="memory", title="Record project decisions", kind="memory", agent_role="memory", depends_on=["validate"]),
                ],
            ),
            EcosystemWorkflowDefinition(
                id="release_preparation",
                name="Release Preparation",
                version="1.0.0",
                api_version=ECOSYSTEM_API_VERSION,
                category="release",
                description="Prepare a release by scanning risks, running validation, summarizing changes, and requiring approval.",
                required_agents=["planner", "review", "validation", "memory"],
                validation_commands=["npm run validate"],
                approvals=[
                    WorkflowApprovalRequirement(
                        id="approve-release",
                        title="Approve release readiness",
                        reason="Release tasks may trigger builds and packaging checks.",
                        required_before_step="summarize",
                        permission_scope="release",
                    )
                ],
                steps=[
                    WorkflowStepDefinition(id="inspect", title="Inspect release state", kind="inspect", agent_role="review"),
                    WorkflowStepDefinition(id="security", title="Review security-sensitive changes", kind="review", agent_role="review", depends_on=["inspect"]),
                    WorkflowStepDefinition(
                        id="validate",
                        title="Run release validation",
                        kind="validate",
                        agent_role="validation",
                        depends_on=["security"],
                        validation_commands=["npm run validate"],
                    ),
                    WorkflowStepDefinition(id="summarize", title="Summarize release outcome", kind="summarize", agent_role="memory", depends_on=["validate"], approval_required=True),
                ],
            ),
            EcosystemWorkflowDefinition(
                id="debugging_pipeline",
                name="Debugging Pipeline",
                version="1.0.0",
                api_version=ECOSYSTEM_API_VERSION,
                category="debugging",
                description="Reproduce a failure, inspect likely modules, repair, validate, and save the fix memory.",
                required_agents=["planner", "code", "validation", "repair", "memory"],
                steps=[
                    WorkflowStepDefinition(id="inspect", title="Inspect failure context", kind="inspect", agent_role="planner"),
                    WorkflowStepDefinition(id="repair", title="Repair suspected issue", kind="repair", agent_role="repair", depends_on=["inspect"], max_attempts=2),
                    WorkflowStepDefinition(id="validate", title="Validate repair", kind="validate", agent_role="validation", depends_on=["repair"], max_attempts=2),
                    WorkflowStepDefinition(id="memory", title="Persist repair memory", kind="memory", agent_role="memory", depends_on=["validate"]),
                ],
            ),
            EcosystemWorkflowDefinition(
                id="migration_workflow",
                name="Migration Workflow",
                version="1.0.0",
                api_version=ECOSYSTEM_API_VERSION,
                category="migration",
                description="Plan a dependency or framework migration with review, approval, validation, and rollback readiness.",
                required_agents=["planner", "architect", "code", "review", "validation"],
                approvals=[
                    WorkflowApprovalRequirement(
                        id="approve-migration",
                        title="Approve migration edits",
                        reason="Migration work can touch broad architectural surfaces.",
                        required_before_step="edit",
                    )
                ],
                steps=[
                    WorkflowStepDefinition(id="inspect", title="Map migration blast radius", kind="inspect", agent_role="architect"),
                    WorkflowStepDefinition(id="plan", title="Plan migration slices", kind="plan", agent_role="planner", depends_on=["inspect"]),
                    WorkflowStepDefinition(id="edit", title="Apply migration slice", kind="edit", agent_role="code", depends_on=["plan"], approval_required=True),
                    WorkflowStepDefinition(id="review", title="Review migration", kind="review", agent_role="review", depends_on=["edit"]),
                    WorkflowStepDefinition(id="validate", title="Validate migration", kind="validate", agent_role="validation", depends_on=["review"]),
                ],
            ),
            EcosystemWorkflowDefinition(
                id="security_review",
                name="Security Review",
                version="1.0.0",
                api_version=ECOSYSTEM_API_VERSION,
                category="security",
                description="Analyze risky files, policies, providers, dependencies, and permission surfaces.",
                required_agents=["architect", "review", "validation"],
                steps=[
                    WorkflowStepDefinition(id="inspect", title="Inspect risk-sensitive files", kind="inspect", agent_role="architect"),
                    WorkflowStepDefinition(id="review", title="Review security controls", kind="review", agent_role="review", depends_on=["inspect"]),
                    WorkflowStepDefinition(id="validate", title="Run security validation", kind="validate", agent_role="validation", depends_on=["review"]),
                    WorkflowStepDefinition(id="summarize", title="Summarize risks", kind="summarize", agent_role="review", depends_on=["validate"]),
                ],
            ),
        ]

    def ensure_baseline(self, store: Any) -> None:
        if not store.ecosystem_workflows(include_disabled=True):
            for workflow in self.workflow_templates():
                store.upsert_ecosystem_workflow(workflow)
        if store.active_organization_policy() is None:
            store.save_organization_policy(self.default_organization_policy())

    def default_organization_policy(self) -> OrganizationPolicyProfile:
        return OrganizationPolicyProfile(
            id="local_organization_policy",
            name="Local Organization Policy",
            provider_policies={"default": "local-first", "remote_models": "approval_required"},
            privacy_policies={"workspace_sync": "opt_in", "shared_intelligence": "local_export_only"},
            approval_requirements={"write_workspace": True, "run_commands": True, "community_packages": True},
            validation_standards={"minimum": ["known project validation command"], "before_completion": True},
            package_restrictions={"allowed_update_channels": ["stable", "local"], "high_risk_requires_trust": True},
            audit_requirements={"ecosystem_events": True, "workflow_runs": True, "package_lifecycle": True},
            require_signed_packages=False,
            allow_community_packages=True,
            collaboration_mode="local",
            metadata={
                "approval_tier": self.settings.approval_tier,
                "sandbox_profile": self.settings.sandbox_profile,
            },
        )

    def validate_package(
        self,
        request: EcosystemPackageValidationRequest | EcosystemPackageManifest,
        *,
        policy: OrganizationPolicyProfile | None = None,
    ) -> EcosystemPackageValidationResult:
        manifest = request.manifest if isinstance(request, EcosystemPackageValidationRequest) else request
        require_signature = request.require_signature if isinstance(request, EcosystemPackageValidationRequest) else False
        if policy and policy.require_signed_packages:
            require_signature = True
        normalized = self._normalized_package(manifest)
        errors: list[str] = []
        warnings: list[str] = []

        if normalized.api_version != ECOSYSTEM_API_VERSION:
            errors.append(f"Package API version {normalized.api_version or '[missing]'} does not match {ECOSYSTEM_API_VERSION}.")
        if not normalized.version:
            errors.append("Package version is required.")
        if not normalized.name:
            errors.append("Package name is required.")
        if not normalized.sandbox_permissions:
            warnings.append("Package should declare sandbox_permissions for reviewable isolation.")
        if normalized.update_channel not in {"stable", "local"} and policy:
            allowed = set(policy.package_restrictions.get("allowed_update_channels") or ["stable", "local"])
            if normalized.update_channel not in allowed:
                errors.append(f"Update channel {normalized.update_channel} is blocked by organization policy.")

        permission_set = set(normalized.permission_scopes)
        expected = PACKAGE_KIND_PERMISSION_HINTS.get(normalized.kind, set())
        extra = permission_set - expected
        if extra:
            warnings.append("Package asks for broader permissions than its kind usually needs: " + ", ".join(sorted(extra)) + ".")

        risky_permissions = permission_set & HIGH_RISK_PACKAGE_PERMISSIONS
        if risky_permissions and not ({"isolated", "sandbox", "restricted"} & set(normalized.sandbox_permissions)):
            errors.append("High-risk package permissions require isolated, sandbox, or restricted sandbox_permissions.")
        if risky_permissions and normalized.enabled and normalized.trust_level not in {"trusted", "organization", "signed"}:
            errors.append("Enabled high-risk ecosystem packages must be trusted, organization-approved, or signed.")
        if require_signature and not (normalized.signature and normalized.signing_key_fingerprint):
            errors.append("Package signature and signing_key_fingerprint are required by organization policy.")
        elif not normalized.signature:
            warnings.append("Package signing metadata is missing; keep trust low outside local workspaces.")
        expected_checksum = self._package_checksum(manifest)
        if manifest.checksum and manifest.checksum not in {"builtin", expected_checksum}:
            errors.append("Package checksum does not match manifest payload.")

        compatibility_api = normalized.compatibility.get("api_version")
        if compatibility_api and compatibility_api != ECOSYSTEM_API_VERSION:
            warnings.append(f"Compatibility metadata references API {compatibility_api}; current ecosystem API is {ECOSYSTEM_API_VERSION}.")

        trust_score = TRUST_SCORE.get(normalized.trust_level, 0.0)
        if normalized.signature:
            trust_score = min(1.0, trust_score + 0.15)
        if normalized.checksum:
            trust_score = min(1.0, trust_score + 0.05)
        if errors:
            trust_score = min(trust_score, 0.25)

        return EcosystemPackageValidationResult(
            valid=not errors,
            errors=errors,
            warnings=warnings,
            trust_score=trust_score,
            normalized_manifest=normalized,
        )

    def snapshot(
        self,
        store: Any,
        *,
        project_root: Path,
        project_intelligence: ProjectIntelligenceSnapshot | None = None,
        refresh: EcosystemRefreshRequest | None = None,
    ) -> EcosystemSnapshot:
        self.ensure_baseline(store)
        root = project_root.resolve()
        policy = store.active_organization_policy() or self.default_organization_policy()
        packages = store.ecosystem_packages(include_disabled=True)
        workflows = store.ecosystem_workflows(include_disabled=True)
        graph = self.knowledge_graph(project_root=root, project_intelligence=project_intelligence, store=store)
        store.save_knowledge_graph_snapshot(graph)
        query = (refresh.include_search_query if refresh else "").strip()
        search = (
            self.search(
                EcosystemSearchRequest(workspace_root=str(root), query=query, scopes=[], limit=20),
                store=store,
                project_root=root,
                graph=graph,
            )
            if query
            else None
        )
        package_validation = [self.validate_package(item, policy=policy) for item in packages]
        governance = self.governance_signals(packages=packages, validation=package_validation, policy=policy)
        recommendations, warnings = self.recommendations(packages, workflows, graph, governance, policy)
        return EcosystemSnapshot(
            workspace_root=str(root),
            generated_at=utc_now(),
            api_version=ECOSYSTEM_API_VERSION,
            marketplace_catalog=self.marketplace_catalog(),
            packages=packages,
            package_validation=package_validation,
            workflows=workflows,
            shared_profiles=store.shared_intelligence_profiles(limit=50),
            team=self.team_summary(store=store, project_root=root, policy=policy),
            organization_policy=policy,
            knowledge_graph=graph,
            cross_project_insights=self.cross_project_insights(store=store, current=project_intelligence),
            search=search,
            reproducibility=store.reproducibility_records(project_root=root, limit=12),
            governance=governance,
            audit_events=store.ecosystem_audit_events(limit=30),
            recommendations=recommendations,
            warnings=warnings,
        )

    def run_workflow(
        self,
        store: Any,
        *,
        workflow: EcosystemWorkflowDefinition,
        project_root: Path,
        request: WorkflowRunRequest,
    ) -> WorkflowRunResponse:
        if not workflow.enabled:
            raise ValueError("workflow is disabled")
        goal = request.user_goal.strip() or workflow.description or workflow.name
        task_id = store.create_task(
            mode="develop",
            workspace_root=project_root,
            message=goal,
            title=workflow.name,
            user_goal=goal,
            status="needs_approval" if workflow.approvals and not request.start_immediately else "queued",
            priority=request.priority,
            assigned_agent_role="workflow",
            validation_commands=workflow.validation_commands,
        )
        parent_events: list[ToolEvent] = []
        parent_events.append(
            store.record_event(
                task_id,
                kind="workflow.created",
                title=f"Workflow created: {workflow.name}",
                status="warning" if workflow.approvals and not request.start_immediately else "ok",
                detail=goal,
                payload={
                    "workflow_id": workflow.id,
                    "workflow_version": workflow.version,
                    "approval_count": len(workflow.approvals),
                    "step_count": len(workflow.steps),
                    "metadata": request.metadata,
                },
            )
        )
        subtasks = []
        for index, step in enumerate(workflow.steps, start=1):
            subtask_id = store.create_task(
                mode="develop",
                workspace_root=project_root,
                message=goal,
                parent_task_id=task_id,
                title=step.title,
                user_goal=step.description or goal,
                status="needs_approval" if step.approval_required and not request.start_immediately else "queued",
                priority=index,
                assigned_agent_role=step.agent_role or step.kind,
                validation_commands=step.validation_commands,
            )
            subtask = store.task(subtask_id)
            subtasks.append(subtask)
            parent_events.append(
                store.record_event(
                    task_id,
                    kind="workflow.step.created",
                    title=step.title,
                    status="warning" if step.approval_required else "ok",
                    detail=step.description,
                    payload={
                        "step_id": step.id,
                        "kind": step.kind,
                        "agent_role": step.agent_role,
                        "depends_on": step.depends_on,
                        "subtask_id": subtask_id,
                    },
                )
            )
        store.record_ecosystem_audit_event(
            EcosystemAuditEvent(
                id=str(uuid4()),
                created_at=utc_now(),
                action="workflow.run",
                subject_id=workflow.id,
                status="ok",
                detail=f"Workflow {workflow.name} created task {task_id}.",
                metadata={"task_id": task_id, "subtask_count": len(subtasks)},
            )
        )
        return WorkflowRunResponse(
            workflow=workflow,
            task=store.task(task_id),
            subtasks=subtasks,
            events=parent_events,
            message=f"Workflow {workflow.name} created task {task_id}.",
        )

    def knowledge_graph(
        self,
        *,
        project_root: Path,
        project_intelligence: ProjectIntelligenceSnapshot | None,
        store: Any,
    ) -> KnowledgeGraphSnapshot:
        now = utc_now()
        root = project_root.resolve()
        nodes: dict[str, KnowledgeGraphNode] = {}
        edges: list[KnowledgeGraphEdge] = []
        project_id = _node_id("project", str(root))
        project_name = root.name
        if project_intelligence:
            project_name = project_intelligence.profile.project_name or project_name
        nodes[project_id] = KnowledgeGraphNode(
            id=project_id,
            kind="project",
            label=project_name,
            path=str(root),
            summary="Workspace project root.",
            importance=1.0,
        )

        if project_intelligence:
            for module in project_intelligence.architecture.major_modules[:80]:
                node_id = _node_id("module", f"{root}:{module.path}:{module.name}")
                nodes[node_id] = KnowledgeGraphNode(
                    id=node_id,
                    kind="module",
                    label=module.name,
                    path=module.path,
                    summary=module.summary,
                    importance=0.78,
                    metadata={"kind": module.kind},
                )
                edges.append(KnowledgeGraphEdge(source=project_id, target=node_id, kind="contains", summary="Project contains module."))
            for item in project_intelligence.file_importance[:120]:
                node_id = _node_id("file", f"{root}:{item.path}")
                nodes[node_id] = KnowledgeGraphNode(
                    id=node_id,
                    kind="file",
                    label=Path(item.path).name,
                    path=item.path,
                    summary="Important project file.",
                    importance=min(1.0, item.score / 100.0),
                    metadata={"reasons": item.reasons},
                )
                edges.append(KnowledgeGraphEdge(source=project_id, target=node_id, kind="contains", weight=item.score, summary="Project contains important file."))
            for route in project_intelligence.architecture.api_routes[:120]:
                node_id = _node_id("api", f"{root}:{route.method}:{route.path}:{route.file}")
                file_id = _node_id("file", f"{root}:{route.file}")
                nodes[node_id] = KnowledgeGraphNode(
                    id=node_id,
                    kind="api",
                    label=f"{route.method} {route.path}",
                    path=route.file,
                    summary="Detected API route.",
                    importance=0.72,
                )
                edges.append(KnowledgeGraphEdge(source=file_id, target=node_id, kind="exposes", summary="File exposes API route."))
            for dependency in project_intelligence.architecture.dependency_graph[:160]:
                node_id = _node_id("dependency", f"{dependency.kind}:{dependency.target}")
                nodes[node_id] = KnowledgeGraphNode(
                    id=node_id,
                    kind="dependency",
                    label=dependency.target,
                    summary=f"{dependency.kind} dependency from {dependency.source}.",
                    importance=0.5,
                    metadata={"source": dependency.source, "group": dependency.kind},
                )
                edges.append(KnowledgeGraphEdge(source=project_id, target=node_id, kind="depends_on", summary="Project declares dependency."))

        memories = store.project_memory(project_root=root, limit=80)
        for memory in memories:
            kind = "decision" if memory.category in {"decision", "preference", "architecture"} else "task"
            node_id = _node_id(kind, f"{memory.id}:{memory.title}")
            nodes[node_id] = KnowledgeGraphNode(
                id=node_id,
                kind=kind,
                label=memory.title,
                summary=memory.detail,
                importance=max(0.2, min(1.0, memory.confidence)),
                metadata={"category": memory.category, "source": memory.source},
            )
            edges.append(KnowledgeGraphEdge(source=project_id, target=node_id, kind="decided" if kind == "decision" else "related_to"))

        fix_history = store.fix_history(project_root=root, limit=80)
        for fix in fix_history:
            node_id = _node_id("failure", f"{fix.error_signature}:{fix.fix_summary}")
            nodes[node_id] = KnowledgeGraphNode(
                id=node_id,
                kind="failure",
                label=fix.error_signature[:80] or "Validation failure",
                summary=fix.fix_summary,
                importance=max(0.3, min(1.0, fix.confidence)),
                metadata={"category": fix.category, "evidence": fix.evidence},
            )
            edges.append(KnowledgeGraphEdge(source=project_id, target=node_id, kind="failed_in", summary="Failure observed in project history."))

        tasks = store.list_tasks(project_root=root, limit=50, include_subtasks=False)
        for task in tasks[:40]:
            node_id = _node_id("task", f"{task.id}:{task.title}")
            nodes[node_id] = KnowledgeGraphNode(
                id=node_id,
                kind="task",
                label=task.title or task.message[:80],
                summary=task.final_summary or task.error_summary or task.user_goal,
                importance=0.58 if task.status in {"completed", "failed"} else 0.72,
                metadata={"status": task.status, "task_id": task.id},
            )
            edges.append(KnowledgeGraphEdge(source=project_id, target=node_id, kind="related_to", summary="Task belongs to project."))

        graph = KnowledgeGraphSnapshot(
            workspace_root=str(root),
            generated_at=now,
            nodes=sorted(nodes.values(), key=lambda item: (-item.importance, item.kind, item.label))[:500],
            edges=edges[:900],
            modules_total=sum(1 for item in nodes.values() if item.kind == "module"),
            api_routes_total=sum(1 for item in nodes.values() if item.kind == "api"),
            dependencies_total=sum(1 for item in nodes.values() if item.kind == "dependency"),
            decisions_total=sum(1 for item in nodes.values() if item.kind == "decision"),
            recurring_failures_total=sum(1 for item in nodes.values() if item.kind == "failure"),
            recommendations=[],
        )
        graph.recommendations.extend(self._graph_recommendations(graph))
        return graph

    def search(
        self,
        request: EcosystemSearchRequest,
        *,
        store: Any,
        project_root: Path,
        graph: KnowledgeGraphSnapshot | None = None,
    ) -> EcosystemSearchResponse:
        graph = graph or store.knowledge_graph_snapshot(project_root=project_root)
        terms = _tokens(request.query)
        scopes = set(request.scopes or [])
        results: list[EcosystemSearchResult] = []

        def score(text: str, base: float = 0.0) -> float:
            lowered = text.lower()
            return base + sum(1.0 for term in terms if term in lowered)

        if not scopes or "knowledge_graph" in scopes:
            for node in (graph.nodes if graph else []):
                value = score(" ".join([node.label, node.path, node.summary, node.kind]), node.importance)
                if value > node.importance:
                    results.append(
                        EcosystemSearchResult(
                            id=node.id,
                            kind=f"graph.{node.kind}",
                            title=node.label,
                            detail=node.summary,
                            reference=node.path,
                            score=value,
                            metadata=node.metadata,
                        )
                    )
        if not scopes or "tasks" in scopes:
            for task in store.list_tasks(project_root=project_root, limit=120, include_subtasks=True):
                value = score(" ".join([task.title, task.message, task.user_goal, task.error_summary, task.final_summary]), 0.2)
                if value > 0.2:
                    results.append(
                        EcosystemSearchResult(
                            id=task.id,
                            kind="task",
                            title=task.title,
                            detail=task.final_summary or task.error_summary or task.user_goal,
                            reference=task.id,
                            score=value,
                            metadata={"status": task.status, "related_files": task.related_files},
                        )
                    )
        if not scopes or "memory" in scopes:
            for memory in store.project_memory(project_root=project_root, limit=120):
                value = score(" ".join([memory.title, memory.detail, memory.category]), memory.confidence)
                if value > memory.confidence:
                    results.append(
                        EcosystemSearchResult(
                            id=memory.id,
                            kind=f"memory.{memory.category}",
                            title=memory.title,
                            detail=memory.detail,
                            reference=memory.source,
                            score=value,
                        )
                    )
        if not scopes or "workflows" in scopes:
            for workflow in store.ecosystem_workflows(include_disabled=True):
                value = score(" ".join([workflow.name, workflow.category, workflow.description]), 0.4)
                if value > 0.4:
                    results.append(
                        EcosystemSearchResult(
                            id=workflow.id,
                            kind="workflow",
                            title=workflow.name,
                            detail=workflow.description,
                            reference=workflow.id,
                            score=value,
                            metadata={"steps": len(workflow.steps), "category": workflow.category},
                        )
                    )
        if not scopes or "packages" in scopes:
            for package in [*store.ecosystem_packages(include_disabled=True), *self.marketplace_catalog()]:
                value = score(" ".join([package.name, package.kind, package.description]), TRUST_SCORE.get(package.trust_level, 0.0))
                if value > TRUST_SCORE.get(package.trust_level, 0.0):
                    results.append(
                        EcosystemSearchResult(
                            id=package.id,
                            kind=f"package.{package.kind}",
                            title=package.name,
                            detail=package.description,
                            reference=package.entrypoint or package.homepage or package.id,
                            score=value,
                            metadata={"trust_level": package.trust_level, "installed": package.installed},
                        )
                    )

        results = sorted(results, key=lambda item: (-item.score, item.kind, item.title))[: request.limit]
        scope_summary: dict[str, int] = {}
        for result in results:
            root_scope = result.kind.split(".", 1)[0]
            scope_summary[root_scope] = scope_summary.get(root_scope, 0) + 1
        reconstruction: list[ToolEvent] = []
        if request.query.lower().strip().startswith("timeline ") and results:
            task_id = results[0].metadata.get("task_id") if results[0].metadata else ""
            if isinstance(task_id, str) and task_id:
                reconstruction = store.task_events(task_id)
        return EcosystemSearchResponse(
            query=request.query,
            generated_at=utc_now(),
            results=results,
            scope_summary=scope_summary,
            reconstruction=reconstruction,
        )

    def create_reproducibility_record(
        self,
        *,
        store: Any,
        project_root: Path,
        task_id: str,
        include_timeline: bool = True,
    ) -> ReproducibilityRecord:
        root = project_root.resolve()
        artifacts: list[ReproducibilityArtifact] = []
        notes: list[str] = []
        status = "ready"
        try:
            task = store.task(task_id)
            artifacts.append(
                ReproducibilityArtifact(
                    kind="task",
                    reference=task.id,
                    payload=task.model_dump(mode="json"),
                )
            )
            artifacts.append(
                ReproducibilityArtifact(
                    kind="validation",
                    reference=task.id,
                    payload={"commands": task.validation_commands, "status": task.status, "error_summary": task.error_summary},
                )
            )
            if include_timeline:
                events = store.task_events(task_id)
                artifacts.append(
                    ReproducibilityArtifact(
                        kind="timeline",
                        reference=task.id,
                        payload={"events": [event.model_dump(mode="json") for event in events]},
                    )
                )
            subtasks = store.subtasks(task_id)
            if subtasks:
                artifacts.append(
                    ReproducibilityArtifact(
                        kind="context",
                        reference=task.id,
                        payload={"subtasks": [subtask.model_dump(mode="json") for subtask in subtasks]},
                    )
                )
        except KeyError:
            status = "missing_task"
            notes.append("Task was not found; record captures only workspace-level reproducibility metadata.")
        for artifact in artifacts:
            artifact.checksum = _fingerprint(artifact.payload)
        payload = {
            "workspace_root": str(root),
            "task_id": task_id,
            "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts],
            "notes": notes,
        }
        record = ReproducibilityRecord(
            id=str(uuid4()),
            workspace_root=str(root),
            task_id=task_id,
            created_at=utc_now(),
            deterministic_hash=_fingerprint(payload),
            status=status,
            artifacts=artifacts,
            replay_notes=notes
            or [
                "Replay should use the captured task payload, timeline events, validation commands, routing profile, and checkpoint metadata.",
                "Validation snapshots are deterministic when command, cwd, environment profile, and dependency lockfiles match.",
            ],
            metadata={"artifact_count": len(artifacts)},
        )
        return store.save_reproducibility_record(record)

    def shared_profile_from_project(
        self,
        *,
        project_root: Path,
        project_intelligence: ProjectIntelligenceSnapshot | None,
        kind: str = "architecture_pattern",
    ) -> SharedIntelligenceProfile:
        now = utc_now()
        payload: dict[str, Any] = {"workspace_root": str(project_root.resolve())}
        name = f"{project_root.name} Intelligence Profile"
        if project_intelligence:
            name = f"{project_intelligence.profile.project_name or project_root.name} Intelligence Profile"
            payload.update(
                {
                    "stack": project_intelligence.profile.stack,
                    "frameworks": project_intelligence.profile.frameworks,
                    "validation_commands": project_intelligence.validation_commands,
                    "coding_conventions": project_intelligence.profile.coding_conventions,
                    "architecture": project_intelligence.architecture.model_dump(mode="json"),
                    "memory": [item.model_dump(mode="json") for item in project_intelligence.project_memory[:20]],
                }
            )
        checksum = _fingerprint(payload)
        return SharedIntelligenceProfile(
            id=f"profile-{checksum[:12]}",
            name=name,
            kind=kind,  # type: ignore[arg-type]
            version="1.0.0",
            description="Portable project intelligence profile generated from the current workspace.",
            source=str(project_root.resolve()),
            exported_at=now,
            trust_level="reviewed",
            payload=payload,
            checksum=checksum,
        )

    def team_summary(self, *, store: Any, project_root: Path, policy: OrganizationPolicyProfile) -> TeamCollaborationSummary:
        tasks = store.list_tasks(project_root=project_root, limit=200, include_subtasks=False)
        pending_approvals = sum(1 for task in tasks if task.status == "needs_approval")
        checkpoint_count = 0
        try:
            checkpoint_count = len(store.reproducibility_records(project_root=project_root, limit=100))
        except Exception:
            checkpoint_count = 0
        shared = policy.collaboration_mode in {"shared", "organization"}
        return TeamCollaborationSummary(
            mode=policy.collaboration_mode,
            shared_task_count=len(tasks) if shared else 0,
            shared_checkpoint_count=checkpoint_count if shared else 0,
            shared_architecture_notes=len(store.project_memory(project_root=project_root, limit=100)) if shared else 0,
            pending_approvals=pending_approvals,
            collaborators=["local-user"] if shared else [],
            telemetry_dashboards=["task outcomes", "validation trends", "package governance"] if shared else [],
            status="ready" if shared else "disabled",
            notes=[
                "Collaboration is local-only until an organization policy enables shared or organization mode.",
                "Approvals remain explicit and auditable even when task boards are shared.",
            ],
        )

    def cross_project_insights(
        self,
        *,
        store: Any,
        current: ProjectIntelligenceSnapshot | None,
    ) -> list[CrossProjectInsight]:
        snapshots = store.project_intelligence_snapshots(limit=50)
        if current and all(item.workspace_root != current.workspace_root for item in snapshots):
            snapshots.insert(0, current)
        insights: list[CrossProjectInsight] = []
        framework_projects: dict[str, list[str]] = {}
        validation_commands: dict[str, list[str]] = {}
        module_names: dict[str, list[str]] = {}
        for snapshot in snapshots:
            project = snapshot.profile.project_name or Path(snapshot.workspace_root).name
            for framework in snapshot.profile.frameworks:
                framework_projects.setdefault(framework, []).append(project)
            for command in snapshot.validation_commands:
                validation_commands.setdefault(command, []).append(project)
            for module in snapshot.architecture.major_modules:
                module_names.setdefault(module.name.lower(), []).append(project)
        for framework, projects in framework_projects.items():
            if len(set(projects)) > 1:
                insights.append(
                    CrossProjectInsight(
                        id=f"framework-{framework.lower()}",
                        title=f"{framework} appears across projects",
                        category="architecture_pattern",
                        projects=sorted(set(projects)),
                        detail=f"{framework} is a reusable architecture pattern across {len(set(projects))} projects.",
                        recommendation="Consider exporting shared validation, routing, and architecture profiles for this stack.",
                    )
                )
        for command, projects in validation_commands.items():
            if len(set(projects)) > 1:
                insights.append(
                    CrossProjectInsight(
                        id=f"validation-{hashlib.sha1(command.encode('utf-8')).hexdigest()[:10]}",
                        title="Validation command reused across projects",
                        category="reuse",
                        projects=sorted(set(projects)),
                        detail=command,
                        recommendation="Promote this validation command into a shared intelligence profile.",
                    )
                )
        for module, projects in module_names.items():
            if len(set(projects)) > 1 and module not in {"src", "tests", "docs"}:
                insights.append(
                    CrossProjectInsight(
                        id=f"module-{module}",
                        title=f"Repeated module boundary: {module}",
                        category="duplicate",
                        severity="medium",
                        projects=sorted(set(projects)),
                        detail=f"The module name {module} appears in multiple projects.",
                        recommendation="Check whether shared scaffolding, utilities, or architecture notes should be extracted.",
                    )
                )
        if not insights and current:
            insights.append(
                CrossProjectInsight(
                    id="single-project-baseline",
                    title="Cross-project baseline pending",
                    category="reuse",
                    projects=[current.profile.project_name or Path(current.workspace_root).name],
                    detail="Aegis has a current project graph; more saved project profiles will unlock stronger cross-project insights.",
                    recommendation="Export or index additional workspaces to compare shared patterns and recurring failures.",
                )
            )
        return insights[:24]

    def governance_signals(
        self,
        *,
        packages: list[EcosystemPackageManifest],
        validation: list[EcosystemPackageValidationResult],
        policy: OrganizationPolicyProfile,
    ) -> list[GovernanceTrustSignal]:
        invalid_count = sum(1 for item in validation if not item.valid)
        unsigned_enabled = [item for item in packages if item.enabled and not item.signature]
        high_risk = [
            item
            for item in packages
            if item.enabled and set(item.permission_scopes) & HIGH_RISK_PACKAGE_PERMISSIONS
        ]
        return [
            GovernanceTrustSignal(
                id="package-validation",
                label="Package Validation",
                status="blocked" if invalid_count else "trusted",
                score=1.0 if not invalid_count else 0.3,
                detail=f"{invalid_count} invalid package(s)." if invalid_count else "All installed package manifests validate.",
            ),
            GovernanceTrustSignal(
                id="signature-policy",
                label="Signature Policy",
                status="blocked" if policy.require_signed_packages and unsigned_enabled else "trusted" if policy.require_signed_packages else "review",
                score=1.0 if policy.require_signed_packages and not unsigned_enabled else 0.65,
                detail="Signed packages are required by organization policy."
                if policy.require_signed_packages
                else "Package signatures are recommended but optional in the current policy.",
                evidence={"unsigned_enabled": [item.id for item in unsigned_enabled]},
            ),
            GovernanceTrustSignal(
                id="sandbox-permissions",
                label="Sandbox Permissions",
                status="review" if high_risk else "trusted",
                score=0.7 if high_risk else 1.0,
                detail=f"{len(high_risk)} enabled package(s) have high-risk permission scopes." if high_risk else "No enabled package currently uses high-risk ecosystem permissions.",
                evidence={"high_risk_packages": [item.id for item in high_risk]},
            ),
            GovernanceTrustSignal(
                id="audit-log",
                label="Audit Logging",
                status="trusted" if policy.audit_requirements.get("ecosystem_events", True) else "review",
                score=1.0 if policy.audit_requirements.get("ecosystem_events", True) else 0.45,
                detail="Ecosystem lifecycle events are written to the local audit trail.",
            ),
        ]

    def recommendations(
        self,
        packages: list[EcosystemPackageManifest],
        workflows: list[EcosystemWorkflowDefinition],
        graph: KnowledgeGraphSnapshot,
        governance: list[GovernanceTrustSignal],
        policy: OrganizationPolicyProfile,
    ) -> tuple[list[str], list[str]]:
        recommendations: list[str] = []
        warnings: list[str] = []
        if not packages:
            recommendations.append("Install or register trusted ecosystem packages before sharing workflows across projects.")
        if not workflows:
            recommendations.append("Register reusable workflows for bootstrap, release, debugging, migration, and security review.")
        if graph.nodes and graph.decisions_total == 0:
            recommendations.append("Capture architecture decisions as project memory so the knowledge graph can explain why the system changed.")
        if any(signal.status == "blocked" for signal in governance):
            warnings.append("Governance has blocked trust signals that should be resolved before organization sharing.")
        if not policy.require_signed_packages:
            recommendations.append("Enable signed package requirements for shared or organization workspaces.")
        return recommendations[:10], warnings[:10]

    def _graph_recommendations(self, graph: KnowledgeGraphSnapshot) -> list[str]:
        items: list[str] = []
        if graph.modules_total == 0:
            items.append("Run Project Intelligence indexing to populate module relationships.")
        if graph.api_routes_total == 0:
            items.append("No API routes are mapped yet; backend route discovery may need project-specific adapters.")
        if graph.recurring_failures_total:
            items.append("Recurring failure nodes are present; link repair heuristics to shared intelligence profiles.")
        return items

    def _normalized_package(self, manifest: EcosystemPackageManifest) -> EcosystemPackageManifest:
        checksum = manifest.checksum or self._package_checksum(manifest)
        return manifest.model_copy(
            update={
                "id": manifest.id.strip(),
                "name": manifest.name.strip(),
                "version": manifest.version.strip(),
                "api_version": manifest.api_version.strip(),
                "permission_scopes": sorted(set(manifest.permission_scopes)),
                "sandbox_permissions": sorted(set(manifest.sandbox_permissions)),
                "checksum": checksum,
            }
        )

    def _package_checksum(self, manifest: EcosystemPackageManifest) -> str:
        return _fingerprint(
            {
                "id": manifest.id.strip(),
                "kind": manifest.kind,
                "version": manifest.version.strip(),
                "api_version": manifest.api_version.strip(),
                "entrypoint": manifest.entrypoint,
                "permission_scopes": sorted(set(manifest.permission_scopes)),
                "sandbox_permissions": sorted(set(manifest.sandbox_permissions)),
                "update_channel": manifest.update_channel,
            }
        )[:24]
