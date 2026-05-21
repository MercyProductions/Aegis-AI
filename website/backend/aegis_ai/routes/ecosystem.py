from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Query

from ..schemas import (
    EcosystemAuditEvent,
    EcosystemPackageActionRequest,
    EcosystemPackageLifecycleRequest,
    EcosystemPackageLifecycleResponse,
    EcosystemPackageManifest,
    EcosystemPackageRegistrationRequest,
    EcosystemPackageValidationRequest,
    EcosystemPackageValidationResult,
    EcosystemRefreshRequest,
    EcosystemSearchRequest,
    EcosystemSearchResponse,
    EcosystemSnapshot,
    EcosystemWorkflowDefinition,
    KnowledgeGraphSnapshot,
    OrganizationPolicyProfile,
    OrganizationPolicyUpdateRequest,
    ReproducibilityRecord,
    ReproducibilityRequest,
    SharedIntelligenceProfile,
    SharedIntelligenceProfileExportResponse,
    SharedIntelligenceProfileImportRequest,
    WorkflowRunRequest,
    WorkflowRunResponse,
)


def register_ecosystem_routes(
    app: FastAPI,
    *,
    ecosystem_snapshot: Callable[[str | None, bool, str], Awaitable[EcosystemSnapshot]],
    refresh_ecosystem_snapshot: Callable[[EcosystemRefreshRequest], Awaitable[EcosystemSnapshot]],
    ecosystem_marketplace_catalog: Callable[[], Awaitable[list[EcosystemPackageManifest]]],
    list_ecosystem_packages: Callable[[bool], Awaitable[list[EcosystemPackageManifest]]],
    validate_ecosystem_package: Callable[
        [EcosystemPackageValidationRequest],
        Awaitable[EcosystemPackageValidationResult],
    ],
    register_ecosystem_package: Callable[
        [EcosystemPackageRegistrationRequest],
        Awaitable[EcosystemPackageManifest],
    ],
    enable_ecosystem_package: Callable[[str, EcosystemPackageActionRequest | None], Awaitable[EcosystemPackageManifest]],
    disable_ecosystem_package: Callable[[str, EcosystemPackageActionRequest | None], Awaitable[EcosystemPackageManifest]],
    trust_ecosystem_package: Callable[[str, EcosystemPackageActionRequest | None], Awaitable[EcosystemPackageManifest]],
    update_ecosystem_package: Callable[[str, EcosystemPackageLifecycleRequest], Awaitable[EcosystemPackageLifecycleResponse]],
    rollback_ecosystem_package: Callable[[str, EcosystemPackageLifecycleRequest | None], Awaitable[EcosystemPackageLifecycleResponse]],
    uninstall_ecosystem_package: Callable[[str, EcosystemPackageLifecycleRequest | None], Awaitable[EcosystemPackageLifecycleResponse]],
    list_ecosystem_workflows: Callable[[bool], Awaitable[list[EcosystemWorkflowDefinition]]],
    register_ecosystem_workflow: Callable[[EcosystemWorkflowDefinition], Awaitable[EcosystemWorkflowDefinition]],
    run_ecosystem_workflow: Callable[[str, WorkflowRunRequest], Awaitable[WorkflowRunResponse]],
    list_shared_intelligence_profiles: Callable[[str | None, int], Awaitable[list[SharedIntelligenceProfile]]],
    import_shared_intelligence_profile: Callable[
        [SharedIntelligenceProfileImportRequest],
        Awaitable[SharedIntelligenceProfile],
    ],
    export_shared_intelligence_profile: Callable[[str], Awaitable[SharedIntelligenceProfileExportResponse]],
    export_current_project_intelligence: Callable[[str | None], Awaitable[SharedIntelligenceProfileExportResponse]],
    get_organization_policy: Callable[[], Awaitable[OrganizationPolicyProfile]],
    update_organization_policy: Callable[[OrganizationPolicyUpdateRequest], Awaitable[OrganizationPolicyProfile]],
    ecosystem_knowledge_graph: Callable[[str | None, bool], Awaitable[KnowledgeGraphSnapshot]],
    ecosystem_search: Callable[[EcosystemSearchRequest], Awaitable[EcosystemSearchResponse]],
    create_reproducibility_record: Callable[[ReproducibilityRequest], Awaitable[ReproducibilityRecord]],
    list_reproducibility_records: Callable[[str | None, int], Awaitable[list[ReproducibilityRecord]]],
    list_ecosystem_audit_events: Callable[[int], Awaitable[list[EcosystemAuditEvent]]],
) -> None:
    @app.get("/api/ecosystem", response_model=EcosystemSnapshot)
    async def get_ecosystem_snapshot(
        workspace_root: str | None = Query(default=None),
        rebuild_graph: bool = Query(default=False),
        query: str = Query(default=""),
    ) -> EcosystemSnapshot:
        return await ecosystem_snapshot(workspace_root, rebuild_graph, query)

    @app.post("/api/ecosystem/refresh", response_model=EcosystemSnapshot)
    async def post_ecosystem_refresh(request: EcosystemRefreshRequest) -> EcosystemSnapshot:
        return await refresh_ecosystem_snapshot(request)

    @app.get("/api/ecosystem/marketplace", response_model=list[EcosystemPackageManifest])
    async def get_ecosystem_marketplace_catalog() -> list[EcosystemPackageManifest]:
        return await ecosystem_marketplace_catalog()

    @app.get("/api/ecosystem/packages", response_model=list[EcosystemPackageManifest])
    async def get_ecosystem_packages(
        include_disabled: bool = Query(default=True),
    ) -> list[EcosystemPackageManifest]:
        return await list_ecosystem_packages(include_disabled)

    @app.post("/api/ecosystem/packages/validate", response_model=EcosystemPackageValidationResult)
    async def post_ecosystem_package_validation(
        request: EcosystemPackageValidationRequest,
    ) -> EcosystemPackageValidationResult:
        return await validate_ecosystem_package(request)

    @app.post("/api/ecosystem/packages/register", response_model=EcosystemPackageManifest)
    async def post_ecosystem_package_registration(
        request: EcosystemPackageRegistrationRequest,
    ) -> EcosystemPackageManifest:
        return await register_ecosystem_package(request)

    @app.post("/api/ecosystem/packages/{package_id}/enable", response_model=EcosystemPackageManifest)
    async def post_ecosystem_package_enable(
        package_id: str,
        request: EcosystemPackageActionRequest | None = None,
    ) -> EcosystemPackageManifest:
        return await enable_ecosystem_package(package_id, request)

    @app.post("/api/ecosystem/packages/{package_id}/disable", response_model=EcosystemPackageManifest)
    async def post_ecosystem_package_disable(
        package_id: str,
        request: EcosystemPackageActionRequest | None = None,
    ) -> EcosystemPackageManifest:
        return await disable_ecosystem_package(package_id, request)

    @app.post("/api/ecosystem/packages/{package_id}/trust", response_model=EcosystemPackageManifest)
    async def post_ecosystem_package_trust(
        package_id: str,
        request: EcosystemPackageActionRequest | None = None,
    ) -> EcosystemPackageManifest:
        return await trust_ecosystem_package(package_id, request)

    @app.post("/api/ecosystem/packages/{package_id}/update", response_model=EcosystemPackageLifecycleResponse)
    async def post_ecosystem_package_update(
        package_id: str,
        request: EcosystemPackageLifecycleRequest,
    ) -> EcosystemPackageLifecycleResponse:
        return await update_ecosystem_package(package_id, request)

    @app.post("/api/ecosystem/packages/{package_id}/rollback", response_model=EcosystemPackageLifecycleResponse)
    async def post_ecosystem_package_rollback(
        package_id: str,
        request: EcosystemPackageLifecycleRequest | None = None,
    ) -> EcosystemPackageLifecycleResponse:
        return await rollback_ecosystem_package(package_id, request)

    @app.post("/api/ecosystem/packages/{package_id}/uninstall", response_model=EcosystemPackageLifecycleResponse)
    async def post_ecosystem_package_uninstall(
        package_id: str,
        request: EcosystemPackageLifecycleRequest | None = None,
    ) -> EcosystemPackageLifecycleResponse:
        return await uninstall_ecosystem_package(package_id, request)

    @app.get("/api/ecosystem/workflows", response_model=list[EcosystemWorkflowDefinition])
    async def get_ecosystem_workflows(
        include_disabled: bool = Query(default=True),
    ) -> list[EcosystemWorkflowDefinition]:
        return await list_ecosystem_workflows(include_disabled)

    @app.post("/api/ecosystem/workflows/register", response_model=EcosystemWorkflowDefinition)
    async def post_ecosystem_workflow_registration(
        workflow: EcosystemWorkflowDefinition,
    ) -> EcosystemWorkflowDefinition:
        return await register_ecosystem_workflow(workflow)

    @app.post("/api/ecosystem/workflows/{workflow_id}/run", response_model=WorkflowRunResponse)
    async def post_ecosystem_workflow_run(
        workflow_id: str,
        request: WorkflowRunRequest,
    ) -> WorkflowRunResponse:
        return await run_ecosystem_workflow(workflow_id, request)

    @app.get("/api/ecosystem/shared-profiles", response_model=list[SharedIntelligenceProfile])
    async def get_shared_intelligence_profiles(
        kind: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> list[SharedIntelligenceProfile]:
        return await list_shared_intelligence_profiles(kind, limit)

    @app.post("/api/ecosystem/shared-profiles/import", response_model=SharedIntelligenceProfile)
    async def post_shared_intelligence_profile_import(
        request: SharedIntelligenceProfileImportRequest,
    ) -> SharedIntelligenceProfile:
        return await import_shared_intelligence_profile(request)

    @app.get("/api/ecosystem/shared-profiles/{profile_id}/export", response_model=SharedIntelligenceProfileExportResponse)
    async def get_shared_intelligence_profile_export(profile_id: str) -> SharedIntelligenceProfileExportResponse:
        return await export_shared_intelligence_profile(profile_id)

    @app.post("/api/ecosystem/shared-profiles/export-current", response_model=SharedIntelligenceProfileExportResponse)
    async def post_current_project_intelligence_export(
        workspace_root: str | None = Query(default=None),
    ) -> SharedIntelligenceProfileExportResponse:
        return await export_current_project_intelligence(workspace_root)

    @app.get("/api/ecosystem/org-policy", response_model=OrganizationPolicyProfile)
    async def get_ecosystem_organization_policy() -> OrganizationPolicyProfile:
        return await get_organization_policy()

    @app.put("/api/ecosystem/org-policy", response_model=OrganizationPolicyProfile)
    async def put_ecosystem_organization_policy(
        request: OrganizationPolicyUpdateRequest,
    ) -> OrganizationPolicyProfile:
        return await update_organization_policy(request)

    @app.get("/api/ecosystem/knowledge-graph", response_model=KnowledgeGraphSnapshot)
    async def get_ecosystem_knowledge_graph(
        workspace_root: str | None = Query(default=None),
        rebuild: bool = Query(default=False),
    ) -> KnowledgeGraphSnapshot:
        return await ecosystem_knowledge_graph(workspace_root, rebuild)

    @app.post("/api/ecosystem/search", response_model=EcosystemSearchResponse)
    async def post_ecosystem_search(request: EcosystemSearchRequest) -> EcosystemSearchResponse:
        return await ecosystem_search(request)

    @app.post("/api/ecosystem/reproducibility", response_model=ReproducibilityRecord)
    async def post_reproducibility_record(request: ReproducibilityRequest) -> ReproducibilityRecord:
        return await create_reproducibility_record(request)

    @app.get("/api/ecosystem/reproducibility", response_model=list[ReproducibilityRecord])
    async def get_reproducibility_records(
        workspace_root: str | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> list[ReproducibilityRecord]:
        return await list_reproducibility_records(workspace_root, limit)

    @app.get("/api/ecosystem/audit", response_model=list[EcosystemAuditEvent])
    async def get_ecosystem_audit_events(
        limit: int = Query(default=50, ge=1, le=200),
    ) -> list[EcosystemAuditEvent]:
        return await list_ecosystem_audit_events(limit)
