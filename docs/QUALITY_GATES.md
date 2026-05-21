# Core Quality Gates

Aegis Core now owns the shared quality-gate contract for apply and workflow completion checks. Website, Desktop, VS Code, and Visual Studio can still keep their client-specific preview and fallback behavior, but Core is the source of truth for whether a proposed change is safe enough to apply.

## Runtime Ownership

Core evaluates proposed file changes before apply and stores quality history in the project `.aegis` folder. The quality system is local-first and inspectable:

- `.aegis/quality-gate-runs.json` stores gate evaluations.
- `.aegis/evaluation-reports.json` stores completed workflow reports.
- `.aegis/benchmark-history.json` stores deterministic benchmark suite runs.

The Website backend exposes compatibility `/api` routes for quality data, but those routes delegate to Core when Core is reachable. Desktop, VS Code, and Visual Studio call Core directly where possible.

## Gates

The first Core-owned gates are:

- `syntax_check`: parse-supported text syntax such as Python and JSON.
- `build_check`: records build readiness and missing build evidence.
- `test_check`: records test readiness and missing test evidence.
- `lint_check`: records lint readiness and missing lint evidence.
- `type_check`: records type-check readiness and missing type evidence.
- `security_scan`: blocks secret-like file names, secret-like content, and binary write attempts.
- `dependency_risk`: warns on package manifests, lockfiles, and project files.
- `file_change_risk`: scores file count, risky paths, and broad edits.
- `rollback_readiness`: requires a checkpoint for non-dry apply.
- `user_approval_required`: blocks risky apply when approval is missing.

## Scores

Each evaluation includes:

- `completion_score`
- `validation_score`
- `risk_score`
- `confidence_score`
- `repair_score`
- `regression_risk`
- `human_review_required`

These are deterministic operational scores, not model self-confidence. They are meant to make gate state comparable across clients and workflows.

## Blocking Rules

Core apply is blocked when:

- checkpoint creation failed or a non-dry apply has no checkpoint;
- an unsafe or restricted path is touched;
- validation is required and the latest validation failed or is missing;
- syntax checks fail for supported file types;
- file-change risk exceeds the configured file limit;
- secret-like or binary content is proposed;
- human approval is required but missing.

Clients must not bypass a Core safety rejection with local fallback. Fallback is only for Core being offline, timing out, or lacking a compatible endpoint.

## Override Rules

Core exposes `allow_quality_override` on apply for future administrator or developer tooling, but normal clients should leave it disabled. An override is only acceptable when the caller already has an explicit user approval, a checkpoint, a recorded gate result, and a written reason in workflow metadata. Overrides should never ignore unsafe paths, secret-like files, binary writes, or failed checkpoint creation.

## APIs

Core endpoints:

- `GET /v1/quality-gates`
- `POST /v1/quality-gates/evaluate`
- `GET /v1/workflows/{workflow_id}/quality`
- `GET /v1/benchmarks`
- `POST /v1/benchmarks/run`
- `GET /v1/evaluation-reports`
- `POST /v1/evaluation-reports`

Website compatibility routes:

- `GET /api/quality-gates`
- `POST /api/quality-gates/evaluate`
- `GET /api/quality-gates/workflows/{workflow_id}`
- `GET /api/benchmarks`
- `POST /api/benchmarks/run`
- `GET /api/evaluation-reports`
- `POST /api/evaluation-reports`

## Client Responsibilities

Website should keep auth, UI response compatibility, and product-specific presentation while delegating quality decisions to Core.

Desktop should show gate status, blocker details, and benchmark/report history in runtime status surfaces.

VS Code and Visual Studio should preview diffs and request approval locally, then ask Core to evaluate quality before apply. If Core explicitly blocks apply, the editor client should report the blockers and leave files unchanged.

## Benchmarks And Reports

Core benchmark suites currently cover:

- coding task quality
- repair accuracy
- validation success
- routing decisions
- model/provider performance
- agent handoff reliability

Completed workflows can produce evaluation reports with changed files, reasons, tests run, failures, repair attempts, remaining risks, and rollback instructions. Reports are designed for later UI timelines and audit export.

## Phase 12 Evidence Contract

The release-grade quality contract lives in `evals/phase12-quality-contract.json`. It is checked by:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-quality-contract.ps1
```

The script writes comparable evidence to `.aegis/quality-evidence/<timestamp>/` by default. When it runs inside `scripts\validate-ecosystem.ps1`, its evidence is nested under the current `.aegis/release-evidence/<timestamp>/quality-contract/` folder.

The contract currently locks:

- Golden workflows for chat no-write behavior, coding diffs, review quality gates, scaffold generation, validation repair, model routing, provider fallback, memory continuation, apply/rollback, and editor parity.
- Observability signals for route quality, fallback inspection, feedback, token calibration, structured preview stability, and policy diffs.
- Required Core, Website, telemetry, docs, and editor contract files.

## Performance Budgets

The first Phase 12 budgets are visible thresholds, not automatic hard blockers yet. They give future telemetry and benchmark work a stable comparison target:

| Budget | Warning | P95 | Evidence |
| --- | ---: | ---: | --- |
| Workspace scan | 6s | 10s | Core workspace scan or ecosystem evidence log |
| Model route preview | 1s | 2s | Route preview and fallback inspector telemetry |
| Chat first token | 3s | 5s | Streaming telemetry and model attempt metadata |
| Apply quality gate | 2s | 3s | Core quality gate run |
| Validation command | 60s | 120s | Validation log or release evidence gate |
| Frontend render | 2s | 4s | Frontend build/test or browser smoke timing |

## Current Limits

Syntax checks are intentionally conservative and only parse formats with reliable local parsers in this slice. Build, lint, type, dependency, and security gates record structured evidence and blockers, but deep language-specific scanners should be expanded incrementally. Benchmarks are deterministic local quality probes, not external model eval suites yet.
