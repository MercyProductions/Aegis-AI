from __future__ import annotations

from typing import Any


def branding_tokens() -> dict[str, Any]:
    return {
        "product": {
            "ecosystem": "Auralith OS",
            "runtime": "Aegis Core",
            "assistant": "Auralith Prime",
            "agent": "Auralith Agent",
            "legacy_aliases": ["Auralith", "Aegis", "Aegis AI", "Aegis Local Agent"],
        },
        "colors": {
            "background": "#0b1014",
            "panel": "#111820",
            "panel_alt": "#151f28",
            "text": "#e6f1f5",
            "muted_text": "#92a6b3",
            "cyan": "#28d7e6",
            "red": "#ff4f5e",
            "green": "#62d26f",
            "amber": "#f0b84b",
        },
        "typography": {
            "font_family": "Segoe UI, Inter, system-ui, sans-serif",
            "mono_family": "Cascadia Code, Consolas, monospace",
            "density": "compact but readable",
        },
        "terminology": {
            "product": "Auralith OS",
            "assistant": "Auralith Prime",
            "core_runtime": "Aegis Core",
            "project_memory": "Project Memory",
            "solution_memory": "Solution Memory",
            "safe_apply": "Safe Apply",
            "roadmap": "Roadmap",
            "validation": "Validation",
            "rollback": "Rollback",
            "quality_gate": "Quality Gate",
            "distributed_node": "Trusted Runtime Node",
            "experimental_area": "Experimental Labs",
        },
        "layout": {
            "philosophy": "dark, practical Auralith OS command center with clear state, explicit approval, and low visual clutter",
            "primary_panels": ["Workspace", "Plan", "Changes", "Validate", "Memory", "Runtime"],
            "advanced_panels": ["Agents", "Quality", "Deployment", "Plugins", "Labs", "Diagnostics"],
        },
    }
