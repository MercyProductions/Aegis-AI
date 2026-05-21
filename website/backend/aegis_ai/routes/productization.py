from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Query

from ..schemas import (
    EnterprisePolicyProfile,
    EnterprisePolicyUpdateRequest,
    PluginActionRequest,
    PluginLifecycleActionRequest,
    PluginLifecycleActionResponse,
    PluginManifest,
    PluginRegistrationRequest,
    PluginValidationRequest,
    PluginValidationResult,
    ProductizationRefreshRequest,
    ProductizationSnapshot,
    ReliabilityMetric,
    RuntimeRecoverySnapshot,
    StableApiContract,
)


def register_productization_routes(
    app: FastAPI,
    *,
    productization_snapshot: Callable[[str | None, bool], Awaitable[ProductizationSnapshot]],
    refresh_productization_snapshot: Callable[[ProductizationRefreshRequest], Awaitable[ProductizationSnapshot]],
    productization_stable_apis: Callable[[], Awaitable[list[StableApiContract]]],
    productization_recovery: Callable[[str | None], Awaitable[RuntimeRecoverySnapshot]],
    productization_reliability: Callable[[str | None], Awaitable[list[ReliabilityMetric]]],
    list_productization_plugins: Callable[[bool], Awaitable[list[PluginManifest]]],
    validate_productization_plugin: Callable[[PluginValidationRequest], Awaitable[PluginValidationResult]],
    register_productization_plugin: Callable[[PluginRegistrationRequest], Awaitable[PluginManifest]],
    enable_productization_plugin: Callable[[str, PluginActionRequest | None], Awaitable[PluginManifest]],
    disable_productization_plugin: Callable[[str, PluginActionRequest | None], Awaitable[PluginManifest]],
    trust_productization_plugin: Callable[[str, PluginActionRequest | None], Awaitable[PluginManifest]],
    update_productization_plugin: Callable[[str, PluginLifecycleActionRequest], Awaitable[PluginLifecycleActionResponse]],
    rollback_productization_plugin: Callable[[str, PluginLifecycleActionRequest | None], Awaitable[PluginLifecycleActionResponse]],
    uninstall_productization_plugin: Callable[[str, PluginLifecycleActionRequest | None], Awaitable[PluginLifecycleActionResponse]],
    get_enterprise_policy: Callable[[], Awaitable[EnterprisePolicyProfile]],
    update_enterprise_policy: Callable[[EnterprisePolicyUpdateRequest], Awaitable[EnterprisePolicyProfile]],
) -> None:
    @app.get("/api/productization", response_model=ProductizationSnapshot)
    async def get_productization_snapshot(
        workspace_root: str | None = Query(default=None),
        refresh_metrics: bool = Query(default=False),
    ) -> ProductizationSnapshot:
        return await productization_snapshot(workspace_root, refresh_metrics)

    @app.post("/api/productization/refresh", response_model=ProductizationSnapshot)
    async def post_productization_refresh(request: ProductizationRefreshRequest) -> ProductizationSnapshot:
        return await refresh_productization_snapshot(request)

    @app.get("/api/productization/stable-apis", response_model=list[StableApiContract])
    async def get_productization_stable_apis() -> list[StableApiContract]:
        return await productization_stable_apis()

    @app.get("/api/productization/recovery", response_model=RuntimeRecoverySnapshot)
    async def get_productization_recovery(
        workspace_root: str | None = Query(default=None),
    ) -> RuntimeRecoverySnapshot:
        return await productization_recovery(workspace_root)

    @app.get("/api/productization/reliability", response_model=list[ReliabilityMetric])
    async def get_productization_reliability(
        workspace_root: str | None = Query(default=None),
    ) -> list[ReliabilityMetric]:
        return await productization_reliability(workspace_root)

    @app.get("/api/productization/plugins", response_model=list[PluginManifest])
    async def get_productization_plugins(
        include_disabled: bool = Query(default=True),
    ) -> list[PluginManifest]:
        return await list_productization_plugins(include_disabled)

    @app.post("/api/productization/plugins/validate", response_model=PluginValidationResult)
    async def post_productization_plugin_validation(
        request: PluginValidationRequest,
    ) -> PluginValidationResult:
        return await validate_productization_plugin(request)

    @app.post("/api/productization/plugins/register", response_model=PluginManifest)
    async def post_productization_plugin_registration(
        request: PluginRegistrationRequest,
    ) -> PluginManifest:
        return await register_productization_plugin(request)

    @app.post("/api/productization/plugins/{plugin_id}/enable", response_model=PluginManifest)
    async def post_productization_plugin_enable(
        plugin_id: str,
        request: PluginActionRequest | None = None,
    ) -> PluginManifest:
        return await enable_productization_plugin(plugin_id, request)

    @app.post("/api/productization/plugins/{plugin_id}/disable", response_model=PluginManifest)
    async def post_productization_plugin_disable(
        plugin_id: str,
        request: PluginActionRequest | None = None,
    ) -> PluginManifest:
        return await disable_productization_plugin(plugin_id, request)

    @app.post("/api/productization/plugins/{plugin_id}/trust", response_model=PluginManifest)
    async def post_productization_plugin_trust(
        plugin_id: str,
        request: PluginActionRequest | None = None,
    ) -> PluginManifest:
        return await trust_productization_plugin(plugin_id, request)

    @app.post("/api/productization/plugins/{plugin_id}/update", response_model=PluginLifecycleActionResponse)
    async def post_productization_plugin_update(
        plugin_id: str,
        request: PluginLifecycleActionRequest,
    ) -> PluginLifecycleActionResponse:
        return await update_productization_plugin(plugin_id, request)

    @app.post("/api/productization/plugins/{plugin_id}/rollback", response_model=PluginLifecycleActionResponse)
    async def post_productization_plugin_rollback(
        plugin_id: str,
        request: PluginLifecycleActionRequest | None = None,
    ) -> PluginLifecycleActionResponse:
        return await rollback_productization_plugin(plugin_id, request)

    @app.post("/api/productization/plugins/{plugin_id}/uninstall", response_model=PluginLifecycleActionResponse)
    async def post_productization_plugin_uninstall(
        plugin_id: str,
        request: PluginLifecycleActionRequest | None = None,
    ) -> PluginLifecycleActionResponse:
        return await uninstall_productization_plugin(plugin_id, request)

    @app.get("/api/productization/enterprise-policy", response_model=EnterprisePolicyProfile)
    async def get_productization_enterprise_policy() -> EnterprisePolicyProfile:
        return await get_enterprise_policy()

    @app.put("/api/productization/enterprise-policy", response_model=EnterprisePolicyProfile)
    async def put_productization_enterprise_policy(
        request: EnterprisePolicyUpdateRequest,
    ) -> EnterprisePolicyProfile:
        return await update_enterprise_policy(request)
