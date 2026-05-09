from __future__ import annotations

from typing import Any


def branding_tokens() -> dict[str, Any]:
    return {
        "product": {
            "ecosystem": "Auralith",
            "runtime": "Aegis Core",
            "agent": "Aegis Local Agent",
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
            "project_memory": "Project Memory",
            "solution_memory": "Solution Memory",
            "safe_apply": "Safe Apply",
            "roadmap": "Roadmap",
            "validation": "Validation",
            "rollback": "Rollback",
        },
        "layout": {
            "philosophy": "dark, practical command center with clear state, explicit approval, and low visual clutter",
            "primary_panels": ["Overview", "Chat", "Plan", "Changes", "Validation", "Memory", "Diagnostics"],
        },
    }
