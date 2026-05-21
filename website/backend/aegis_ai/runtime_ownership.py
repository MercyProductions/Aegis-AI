from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


RuntimeOwner = Literal["aegis-core", "website", "compatibility"]

OWNERSHIP_SCHEMA_VERSION = "2026.05.21"


@dataclass(frozen=True)
class RuntimeOwnershipRecord:
    """Source-of-truth ownership for a runtime domain exposed through Website /api."""

    domain: str
    owner: RuntimeOwner
    summary: str
    core_routes: tuple[str, ...]
    website_routes: tuple[str, ...]
    delegated_workflows: tuple[str, ...] = ()
    fallback: str = ""
    migration_rule: str = ""

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["core_routes"] = list(self.core_routes)
        data["website_routes"] = list(self.website_routes)
        data["delegated_workflows"] = list(self.delegated_workflows)
        return data


RUNTIME_OWNERSHIP: tuple[RuntimeOwnershipRecord, ...] = (
    RuntimeOwnershipRecord(
        domain="health-readiness",
        owner="compatibility",
        summary="Website owns app readiness; Core owns shared runtime readiness. Website surfaces both without merging the meanings.",
        core_routes=("/v1/health", "/v1/security/status", "/v1/release/compatibility"),
        website_routes=("/api/health", "/api/ready", "/api/core-runtime", "/api/runtime/delegation"),
        delegated_workflows=("release.compatibility", "security.status"),
        fallback="Website health remains available when Core is offline and marks shared runtime state as degraded.",
        migration_rule="Do not replace Website app health with Core health; expose Core state as an adapter field.",
    ),
    RuntimeOwnershipRecord(
        domain="settings-config",
        owner="compatibility",
        summary="Core owns cross-client settings; Website owns app configuration and preserves /api/config shape.",
        core_routes=("/v1/settings", "/v1/settings/export", "/v1/settings/import"),
        website_routes=("/api/config", "/api/settings/export", "/api/settings/import"),
        delegated_workflows=("settings.export", "settings.import"),
        fallback="Website saves local app settings even if Core sync fails.",
        migration_rule="New shared settings start in Core; Website may keep app-only fields in /api/config.",
    ),
    RuntimeOwnershipRecord(
        domain="memory",
        owner="compatibility",
        summary="Core owns shared project/personal memory; Website owns existing memory CRUD and UI compatibility.",
        core_routes=("/v1/memory", "/v1/personal-memory", "/v1/engineering/memory"),
        website_routes=("/api/memory",),
        delegated_workflows=("personal.memory", "personal.memory.record", "personal.memory.deleted", "personal.memory.export", "engineering.memory"),
        fallback="Website memory CRUD stays local while shared Core memory is unavailable.",
        migration_rule="New cross-client memory belongs in Core; Website-specific notes can remain Website-owned until migrated.",
    ),
    RuntimeOwnershipRecord(
        domain="changes-apply",
        owner="aegis-core",
        summary="Core owns approved file-change application, checkpoint links, and write safety for shared clients.",
        core_routes=("/v1/changes/propose", "/v1/changes/apply"),
        website_routes=("/api/apply", "/api/diff/apply"),
        delegated_workflows=("changes.apply",),
        fallback="Website may use its existing safe apply path only when Core is unreachable or does not expose the delegated route.",
        migration_rule="New write workflows must be implemented in Core first, then exposed through Website compatibility wrappers.",
    ),
    RuntimeOwnershipRecord(
        domain="checkpoints",
        owner="aegis-core",
        summary="Core owns checkpoint creation, listing, and restore contracts for shared clients.",
        core_routes=("/v1/checkpoints/create", "/v1/checkpoints", "/v1/checkpoints/restore"),
        website_routes=("/api/checkpoints", "/api/restore-checkpoint"),
        delegated_workflows=("checkpoints.create", "checkpoints.list", "checkpoints.restore"),
        fallback="Website checkpoint manager remains a compatibility fallback until all clients use Core directly.",
        migration_rule="Do not add a new Website-only checkpoint format; extend Core and map back to Website responses.",
    ),
    RuntimeOwnershipRecord(
        domain="validation",
        owner="aegis-core",
        summary="Core owns safe validation command detection/run storage; Website owns advanced repair UX and compatibility responses.",
        core_routes=("/v1/validation/run", "/v1/validation"),
        website_routes=("/api/validate", "/api/verify", "/api/validation/profile"),
        delegated_workflows=("validation.run",),
        fallback="Website validation manager can run when Core is offline; repair orchestration should record Core fallback mode.",
        migration_rule="New reusable validation primitives go into Core; Website can add app-specific orchestration around them.",
    ),
    RuntimeOwnershipRecord(
        domain="model-routing",
        owner="aegis-core",
        summary="Core owns shared provider capability, route selection, and route explanation contracts.",
        core_routes=("/v1/models", "/v1/providers", "/v1/models/route", "/v1/models/registry"),
        website_routes=("/api/models", "/api/routing/preview", "/api/model-registry"),
        delegated_workflows=("model.route", "model.registry"),
        fallback="Website local model inventory and route preview remain available when Core is unavailable.",
        migration_rule="New route decision logic belongs in Core; Website may keep provider management UI and telemetry projections.",
    ),
    RuntimeOwnershipRecord(
        domain="provider-accounts",
        owner="website",
        summary="Website owns provider-account setup UX, secure linking flows, source-drop jobs, and local CLI bridge probing.",
        core_routes=("/v1/providers", "/v1/providers/{provider_id}/key"),
        website_routes=("/api/provider-accounts", "/api/provider-accounts/{provider_id}/api-key", "/api/provider-accounts/cli-bridges/probe"),
        fallback="Provider-account management remains Website-local; Core consumes normalized provider status and routing inputs.",
        migration_rule="Do not move app account UX into Core unless a non-Website client needs the same workflow contract.",
    ),
    RuntimeOwnershipRecord(
        domain="model-registry",
        owner="compatibility",
        summary="Core owns shared registry reads and route profiles; Website owns provider CRUD, benchmarks, and product policy application for now.",
        core_routes=("/v1/models/registry", "/v1/models/routing-profiles"),
        website_routes=("/api/model-registry", "/api/model-benchmarks", "/api/model-manager"),
        delegated_workflows=("model.registry",),
        fallback="Website registry snapshots and benchmark data remain available if Core is offline.",
        migration_rule="Move shared registry mutation to Core only after compatibility tests cover Website policy and benchmark behavior.",
    ),
    RuntimeOwnershipRecord(
        domain="diagnostics",
        owner="compatibility",
        summary="Core owns shared diagnostics summaries; Website owns app telemetry, route health, and product dashboards.",
        core_routes=("/v1/diagnostics", "/v1/ecosystem/dashboard", "/v1/quality", "/v1/quality-gates"),
        website_routes=("/api/core-runtime", "/api/telemetry", "/api/quality-gates", "/api/productization"),
        delegated_workflows=("quality.gates", "quality.gates.evaluate"),
        fallback="Website telemetry remains local and annotates Core adapter status.",
        migration_rule="Shared runtime diagnostics belong in Core; product analytics and UI dashboards stay Website-owned.",
    ),
    RuntimeOwnershipRecord(
        domain="tasks-workflows",
        owner="compatibility",
        summary="Core owns cross-client tasks and workflow state; Website owns rich task graph, artifacts, approvals, and legacy timeline responses.",
        core_routes=("/v1/tasks", "/v1/workflows", "/v1/workflows/{workflow_id}/step", "/v1/engineering/executions"),
        website_routes=("/api/tasks", "/api/agent-supervision", "/api/autonomous-engineering/objectives"),
        delegated_workflows=("workflows.list", "workflow.dashboard", "workflow.step", "engineering.execution"),
        fallback="Website task graph remains active and records Core fallback mode.",
        migration_rule="New cross-client workflow state goes to Core; Website adapters preserve existing response models.",
    ),
    RuntimeOwnershipRecord(
        domain="agent-runtime",
        owner="aegis-core",
        summary="Core owns agent runtime, supervision, delegation, handoff, and approval-gated workflow execution.",
        core_routes=("/v1/agents/runtime", "/v1/workflows/{workflow_id}/agents", "/v1/workflows/{workflow_id}/agents/delegate"),
        website_routes=("/api/agent-supervision", "/api/agent-supervision/workflows/{workflow_id}/agents/delegate"),
        delegated_workflows=("agent.runtime", "agent.coordination", "agent.delegation"),
        fallback="Website shows degraded supervision if Core is unavailable rather than inventing separate agent state.",
        migration_rule="New agent lifecycle behavior must be Core-owned before Website adds controls for it.",
    ),
    RuntimeOwnershipRecord(
        domain="workspace-intelligence",
        owner="compatibility",
        summary="Core owns shared workspace scan, roadmap, and knowledge graph primitives; Website owns rich operations recommendations and UI state.",
        core_routes=("/v1/workspaces/scan", "/v1/workspaces/roadmap", "/v1/workspaces/intelligence", "/v1/knowledge/search"),
        website_routes=("/api/workspace/profile", "/api/workspace-intelligence", "/api/project-intelligence"),
        delegated_workflows=("knowledge.search", "knowledge.relationships", "knowledge.impact_analysis", "knowledge.architecture_summary"),
        fallback="Website operations scans continue locally while Core knowledge adapters are unavailable.",
        migration_rule="New reusable indexing/knowledge behavior belongs in Core; Website-specific recommendation workflows can remain app-owned.",
    ),
)


def ownership_records() -> tuple[RuntimeOwnershipRecord, ...]:
    return RUNTIME_OWNERSHIP


def ownership_matrix() -> list[dict[str, object]]:
    return [record.to_dict() for record in RUNTIME_OWNERSHIP]


def ownership_for_domain(domain: str) -> RuntimeOwnershipRecord | None:
    normalized = domain.strip().lower()
    for record in RUNTIME_OWNERSHIP:
        if record.domain == normalized:
            return record
    return None
