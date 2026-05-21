from __future__ import annotations

from fastapi.testclient import TestClient

from aegis_core.branding import branding_tokens
from aegis_core.contracts import CONTRACTS, CONTRACT_DATA_MODELS, validate_contract_envelope
from aegis_core.product_identity import feature_catalog, launch_scope, product_identity, product_modes, workflow_catalog
from aegis_core.server import create_app


def assert_contract(payload: dict, kind: str) -> None:
    envelope = validate_contract_envelope(payload)
    assert envelope.kind == kind
    assert payload["ok"] is True


def test_product_identity_defines_auralith_os_positioning() -> None:
    identity = product_identity()

    assert identity["product"]["name"] == "Auralith OS"
    assert identity["product"]["core_runtime"] == "Aegis Core"
    assert identity["product"]["assistant"] == "Auralith Prime"
    assert any("local-first" in item for item in identity["is"])
    assert any("Not an unrestricted autonomous coding system" in item for item in identity["is_not"])
    assert "deploy_production" not in identity["primary_workflows"]
    assert identity["terminology"]["distributed_node"] == "Trusted runtime node"


def test_feature_catalog_classifies_sprawl_and_deprecations() -> None:
    catalog = feature_catalog()

    assert "core_product_features" in catalog["classification"]
    assert "experimental_systems" in catalog["hidden_by_default"]
    deprecated_ids = {item["id"] for item in catalog["classification"]["deprecated_systems"]}
    assert {"website_owned_runtime", "client_owned_model_truth", "local_extension_monoliths"}.issubset(deprecated_ids)
    experimental_ids = {item["id"] for item in catalog["classification"]["experimental_systems"]}
    assert "distributed_runtime" in experimental_ids


def test_product_modes_keep_first_run_simple_and_labs_hidden() -> None:
    modes = product_modes()
    by_id = {item["id"]: item for item in modes["modes"]}

    assert modes["default_mode"] == "basic_local_assistant"
    assert modes["recommended_daily_mode"] == "engineering_workspace"
    assert by_id["basic_local_assistant"]["default_for_first_run"] is True
    assert "distributed_runtime" in by_id["basic_local_assistant"]["hidden_capabilities"]
    assert by_id["experimental_labs"]["stability"] == "experimental"


def test_workflow_catalog_defines_safe_product_path() -> None:
    catalog = workflow_catalog()
    workflow_ids = set(catalog["workflow_order"])

    assert {"open_workspace", "scan_project", "generate_roadmap", "implement_feature", "validate", "repair", "checkpoint", "deploy", "rollback"}.issubset(workflow_ids)
    implement = next(item for item in catalog["workflows"] if item["id"] == "implement_feature")
    assert "checkpoint required" in implement["safety_gates"]
    deploy = next(item for item in catalog["workflows"] if item["id"] == "deploy")
    assert "dry-run by default" in deploy["safety_gates"]


def test_launch_scope_excludes_unstable_systems_from_default() -> None:
    scope = launch_scope()

    excluded = set(scope["recommended_launch_scope"]["exclude_from_default"])
    assert "Distributed Runtime" in excluded
    assert "production deployment execution" in excluded
    assert any(item["id"] == "rollback_after_failure" for item in scope["showcase_workflows"])
    assert scope["launch_readiness_gates"]


def test_product_endpoints_are_contract_wrapped() -> None:
    client = TestClient(create_app())
    endpoints = [
        ("/v1/product/identity", "product.identity"),
        ("/v1/product/features", "product.features"),
        ("/v1/product/modes", "product.modes"),
        ("/v1/product/workflows", "product.workflows"),
        ("/v1/product/showcase", "product.showcase"),
        ("/v1/product/launch-scope", "product.launch_scope"),
        ("/v1/product/roadmap", "product.roadmap"),
    ]

    for endpoint, kind in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, endpoint
        assert_contract(response.json(), kind)


def test_product_contracts_are_registered_with_data_models() -> None:
    required = {
        "product.identity",
        "product.features",
        "product.modes",
        "product.workflows",
        "product.showcase",
        "product.launch_scope",
        "product.roadmap",
    }

    assert required.issubset(CONTRACTS)
    assert required.issubset(CONTRACT_DATA_MODELS)


def test_branding_tokens_use_auralith_os_with_compatibility_aliases() -> None:
    tokens = branding_tokens()

    assert tokens["product"]["ecosystem"] == "Auralith OS"
    assert tokens["product"]["runtime"] == "Aegis Core"
    assert tokens["product"]["assistant"] == "Auralith Prime"
    assert "Aegis Local Agent" in tokens["product"]["legacy_aliases"]
    assert tokens["layout"]["primary_panels"] == ["Workspace", "Plan", "Changes", "Validate", "Memory", "Runtime"]
