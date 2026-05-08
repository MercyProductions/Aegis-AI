# Adaptive Intelligence

Aegis Adaptive Intelligence is a controlled optimization layer over task, routing, validation, feedback, context, and benchmark telemetry. It does not rewrite runtime code, mutate core policies, or silently change workspace files. It records outcomes, scores route quality, creates replay and benchmark reports, and stores reviewable policy profile selections with rollback checkpoints.

## Data Flow

1. Task Engine records task state, timeline events, validation events, checkpoints, repair attempts, and final summaries.
2. Model routing records model attempts, token counts, cost estimates, latency, provider identity, and role.
3. Context building records selected files, omitted files, memories, token estimates, and context strategy.
4. Feedback telemetry records accepted, rejected, copied, revised, rolled back, and neutral signals with privacy-preserving hashes.
5. Adaptive Intelligence turns those signals into task outcomes, quality scores, route recommendations, repair insights, context insights, feedback insights, replay reports, and benchmark reports.
6. The frontend Adaptive page displays the active policy profile, quality scores, routing analytics, recent outcomes, repair/context/feedback insights, benchmarks, replays, and rollback controls.

## Backend Modules

- `website/backend/aegis_ai/adaptive_intelligence.py` computes outcome records, route recommendations, quality scores, replay results, deterministic benchmark reports, and policy profile operations.
- `website/backend/aegis_ai/storage.py` persists adaptive task outcomes, policy profiles, policy checkpoints, benchmark reports, and replay results in SQLite.
- `website/backend/aegis_ai/schemas.py` defines the Adaptive API contracts.
- `website/backend/aegis_ai/main.py` exposes `/api/adaptive-intelligence` endpoints.

## Policy Profiles

Profiles describe routing preferences rather than executable code. Built-in profiles are:

- Local Privacy-First
- Balanced Hybrid
- Maximum Reasoning
- Fast Iterative
- Low-Cost
- Autonomous Engineering
- Safe Review-Only

Activating a profile creates an SQLite checkpoint first. Rollback restores a previous checkpoint. Profile activation does not modify source code, model registry files, or runtime implementation logic.

## Replay And Benchmarks

Replay compares historical task outcomes with the current active profile and route recommendations. Benchmarks produce reproducible report keys for project scaffolding, debugging, repair quality, reasoning, code review, architecture planning, and validation success. Regressions are flagged when a candidate score falls below the saved or requested baseline.

## Safety Rules

- No autonomous code mutation of Aegis runtime logic.
- No silent file edits.
- No self-rewriting policies.
- All profile changes are auditable through checkpoints.
- Learned guidance is observable in the UI and reversible through rollback.
