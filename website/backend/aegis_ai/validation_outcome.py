from __future__ import annotations

from .schemas import CommandRun


def validation_ok(validation: CommandRun) -> bool:
    return validation.allowed and not validation.timed_out and validation.exit_code == 0


def error_signature(validation: CommandRun) -> str:
    text = (validation.stderr or validation.stdout or validation.reason).strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines[:8])[:1200]


def categorize_validation_failure(validation: CommandRun) -> str:
    if validation.category:
        return validation.category

    text = "\n".join(
        [
            validation.command,
            validation.reason,
            validation.stdout[-3000:],
            validation.stderr[-3000:],
        ]
    ).lower()

    if validation.timed_out:
        return "timeout"
    if not validation.allowed:
        return "permission"
    if any(token in text for token in ("syntaxerror", "parseerror", "unexpected token", "expected ':'", "expected ')'")):
        return "syntax"
    if any(token in text for token in ("module not found", "cannot find module", "no module named", "importerror", "modulenotfounderror")):
        return "dependency"
    if any(token in text for token in ("type error", "typescript", "tsc", "mypy", "pyright", "typecheck", "type-check")):
        return "typecheck"
    if any(token in text for token in ("failed", "assert", "expected", "pytest", "jest", "vitest", "test")):
        return "test"
    if any(token in text for token in ("build", "compile", "compilation", "error ts", "vite", "webpack", "cargo")):
        return "build"
    if any(token in text for token in ("traceback", "exception", "runtimeerror", "referenceerror", "valueerror")):
        return "runtime"
    return "unknown"


def validation_score(validation: CommandRun) -> int:
    if validation_ok(validation):
        return 0
    if not validation.allowed:
        return 900
    if validation.timed_out:
        return 800

    category_weights = {
        "syntax": 700,
        "build": 620,
        "typecheck": 580,
        "dependency": 540,
        "runtime": 500,
        "test": 420,
        "unknown": 600,
    }
    return category_weights.get(categorize_validation_failure(validation), 600)


def repair_outcome(before: CommandRun, after: CommandRun | None) -> str:
    if after is None:
        return "worse"
    if validation_ok(after):
        return "fixed"
    if error_signature(before) == error_signature(after):
        return "unchanged"

    before_score = validation_score(before)
    after_score = validation_score(after)
    if after_score < before_score:
        return "improved"
    if after_score > before_score:
        return "worse"
    return "sideways"


def repair_summary(before: CommandRun, after: CommandRun | None, repair_plan: list[str]) -> str:
    if after is None:
        return "Repair command could not be validated after applying the patch."
    if validation_ok(after):
        return "Repair patch produced a passing validation run."

    before_category = categorize_validation_failure(before)
    after_category = categorize_validation_failure(after)
    if before_category != after_category:
        return f"Repair moved validation from {before_category} failure to {after_category} failure."
    if repair_plan:
        return repair_plan[0]
    return "Repair patch changed the workspace but did not fully clear validation."


def repair_strategy_hint(validation: CommandRun) -> str:
    category = categorize_validation_failure(validation)
    hints = {
        "syntax": "Fix parser or syntax issues first and avoid unrelated refactors.",
        "dependency": "Focus on imports, dependency manifests, package availability, or missing modules before changing application logic.",
        "typecheck": "Prefer the smallest signature, annotation, or shape fix that satisfies the current types.",
        "test": "Target the behavior behind the failing assertion and avoid broad rewrites unless the tests point there.",
        "build": "Check compilation inputs, config files, module paths, and generated-code assumptions before changing runtime behavior.",
        "runtime": "Focus on null handling, bad assumptions, edge cases, and exception sites reported by the stack trace.",
        "timeout": "Look for hangs, infinite loops, or overly broad validation commands before changing the main feature code.",
        "permission": "Do not change code to work around approval or sandbox restrictions; keep the repair in preview or ask for a safer validation path.",
        "unknown": "Prefer the smallest fix nearest the reported failure and preserve unrelated working code.",
    }
    return hints.get(category, hints["unknown"])
