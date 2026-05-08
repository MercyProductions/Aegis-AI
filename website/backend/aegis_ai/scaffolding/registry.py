from __future__ import annotations

from .cpp import CPP_TEMPLATE_METHODS
from .dotnet import DOTNET_TEMPLATE_METHODS
from .extensions import EXTENSION_TEMPLATE_METHODS
from .python_templates import PYTHON_TEMPLATE_METHODS
from .rust_go import RUST_GO_TEMPLATE_METHODS
from .web import WEB_TEMPLATE_METHODS


TEMPLATE_METHODS: dict[str, str] = {
    **WEB_TEMPLATE_METHODS,
    **EXTENSION_TEMPLATE_METHODS,
    **PYTHON_TEMPLATE_METHODS,
    **CPP_TEMPLATE_METHODS,
    **RUST_GO_TEMPLATE_METHODS,
    **DOTNET_TEMPLATE_METHODS,
}


def template_method_name(preset_id: str) -> str:
    try:
        return TEMPLATE_METHODS[preset_id]
    except KeyError as exc:
        raise ValueError(f"unknown project scaffold preset: {preset_id}") from exc
