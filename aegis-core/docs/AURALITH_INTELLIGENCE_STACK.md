# Auralith Intelligence Stack

The Auralith Intelligence Stack is Core's local-first foundation for specialized engineering intelligence. It reduces dependence on third-party providers by organizing practical local systems around orchestration, planning, repair, validation, retrieval, routing, summarization, and project understanding.

This is not frontier-scale model training and it does not download or run models automatically. The stack records model lifecycle metadata, builds local retrieval indexes, refines routing decisions, prepares evaluation datasets, tracks benchmarks, and plans distributed inference through trusted runtime nodes.

## Architecture

The stack separates intelligence into specialized components:

- `orchestration`: workflow state classification, escalation timing, retry selection, and bounded-autonomy guidance.
- `planning`: roadmap decomposition, dependency ordering, milestone prediction, and architecture-aware planning.
- `repair`: root-cause classification, repair strategy selection, repeated-failure detection, and rollback recommendation.
- `retrieval`: graph-aware search, hybrid retrieval, workspace embeddings, memory embeddings, and context minimization.
- `validation_classifier`: validation command prioritization, flaky-test signals, failure classification, and confidence scoring.
- `routing`: local/cloud routing, fallback chains, capability matching, privacy-sensitive routing, and cost/latency tradeoffs.
- `summarization`: architecture summaries, workflow reports, execution summaries, and memory condensation.

Each component has a preferred local profile and capability declaration. Core can use deterministic local classifiers today and later hand off to installed local models or trusted model-worker nodes.

## Local Model Lifecycle

Core stores model metadata under:

```text
.aegis/intelligence-models.json
```

Lifecycle records include:

- model ID and provider
- version
- specialization roles
- capability metadata
- quantization format and memory estimate
- compatibility state
- benchmark scores
- install plan

`plan_install` returns commands such as `ollama pull ...`, but it does not execute them. Clients must ask the user before running installation commands.

## Retrieval And Embeddings

The retrieval stack builds an embedding-ready local index under:

```text
.aegis/intelligence-retrieval-index.json
```

Current behavior is deterministic and local:

- Regex tokenization
- Stable hash embeddings for lightweight vector scoring
- Knowledge graph search
- Hybrid graph/vector result merging
- Workspace, memory, and architecture embedding scopes

This gives Core a working local retrieval contract now while preserving a clean future interface for local embedding models or trusted embedding nodes.

## Routing Intelligence

Routing intelligence wraps the existing Core model router with workflow-specific intelligence profiles. It selects:

- the intelligence component for the workflow
- a specialized local model profile or registered local model
- a Core model route
- fallback chain
- privacy warnings
- missing capability warnings
- local/cloud explanation

Privacy-sensitive workflows force local-first behavior.

## Dataset Foundations

Dataset exports are local and redacted by default:

```text
.aegis/intelligence-datasets.json
```

Sources include workflow traces, engineering executions, validation outcomes, repair records, Autopilot memory, quality gates, and architecture summaries. These are evaluation and future adapter-training foundations; Core does not train automatically.

## Distributed Inference

The stack can create dry-run `model_inference` workloads for the distributed runtime. Local Core remains the authority for approvals, checkpoints, state, and fallback. Remote model/GPU/embedding nodes must be trusted, explicitly selected or allowed, and approval-gated when required.

## Benchmarks

Benchmark history is stored under:

```text
.aegis/intelligence-benchmarks.json
```

Initial suites cover:

- repair quality
- validation prediction
- roadmap quality
- orchestration quality
- retrieval accuracy
- context efficiency
- routing quality
- execution reliability

These scores are deterministic signal-quality checks, not claims of model correctness.

## Endpoints

```text
GET  /v1/intelligence-stack
POST /v1/intelligence-stack
GET  /v1/intelligence-stack/models
POST /v1/intelligence-stack/models
POST /v1/intelligence-stack/retrieval/index
POST /v1/intelligence-stack/route
POST /v1/intelligence-stack/predict
POST /v1/intelligence-stack/benchmarks/run
GET  /v1/intelligence-stack/benchmarks
POST /v1/intelligence-stack/datasets
POST /v1/intelligence-stack/distributed-inference/plan
```

All endpoints return standard Core envelopes. All state is project-local under `.aegis`.

## Current Limits

- No automatic model downloads.
- No automatic training.
- No real neural embeddings unless a future local embedding provider is wired in.
- Distributed inference is a scheduling and supervision contract; provider invocation still goes through Core model routing or approved runtime workers.
- Benchmarks currently measure Core intelligence signal quality rather than real-world model output quality.
