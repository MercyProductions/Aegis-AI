from __future__ import annotations

from typing import Any

from .commands import CommandResult
from .diagnostic_redaction import redact_inline
from .schemas import CommandRun
from .validation_diagnostics import failed_step_parts_from_steps


def validation_ok(validation: CommandRun) -> bool:
    return validation.allowed and not validation.timed_out and validation.exit_code == 0


def error_signature(validation: CommandRun) -> str:
    text = redact_inline(validation.stderr or validation.stdout or validation.reason).strip()
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


def categorize_command_result(result: CommandResult, *, recipe: Any = None) -> str:
    if result.timed_out:
        return "timeout"
    if not result.allowed:
        return "permission"
    if result.exit_code == 0:
        return "success"

    text = "\n".join(
        [
            result.command,
            result.reason,
            result.stdout[-4000:],
            result.stderr[-4000:],
        ]
    ).lower()

    if any(token in text for token in ("syntaxerror", "parseerror", "unexpected token", "expected ':'", "expected ')'", "eof while scanning")):
        return "syntax"
    if any(token in text for token in ("module not found", "cannot find module", "no module named", "importerror", "modulenotfounderror", "could not resolve")):
        return "dependency"
    if any(token in text for token in ("type error", "typeerror", "typescript", "tsc", "mypy", "pyright", "typecheck", "type-check")):
        return "typecheck"
    if any(token in text for token in ("assertionerror", "failed", "expected", "pytest", "jest", "vitest", "failing test", "test suite")):
        return "test"
    if any(token in text for token in ("permission denied", "access is denied", "not permitted")):
        return "permission"
    if any(token in text for token in ("traceback", "exception", "runtimeerror", "referenceerror", "valueerror", "nullreferenceexception")):
        return "runtime"
    if any(token in text for token in ("build", "compile", "compilation", "error ts", "vite", "webpack", "cargo", "dotnet build")):
        return "build"
    if getattr(recipe, "source", "") == "detected" and getattr(recipe, "notes", ""):
        return "build"
    return "unknown"


def summarize_command_result(result: CommandResult, *, category: str, recipe: Any = None) -> str:
    label = redact_inline(getattr(recipe, "label", "") or result.command)

    if result.timed_out:
        return f"{label} timed out before finishing."
    if not result.allowed:
        return redact_inline(result.reason) or f"{label} was blocked by the current control settings."
    if result.exit_code == 0:
        return f"{label} completed successfully."

    failed_step, failed_step_command = failed_step_parts_from_steps(list(result.steps))
    if failed_step_command:
        step_label = f"step {failed_step}" if failed_step else "a chained validation step"
        return f"{label} failed at {step_label}: {failed_step_command}."

    summaries = {
        "syntax": "Validation failed with a syntax or parse error.",
        "dependency": "Validation failed because a dependency, import, or module could not be resolved.",
        "typecheck": "Validation failed with a type-checking error.",
        "test": "Validation failed because the test suite reported failing assertions.",
        "build": "Validation failed during build or compilation.",
        "runtime": "Validation failed because the code raised a runtime exception.",
        "permission": "Validation could not run because the current control settings blocked it.",
        "unknown": "Validation failed, but the root cause was not classified cleanly.",
    }
    return summaries.get(category, "Validation failed.")


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
