# Workspace Knowledge Graph

Last updated: 2026-05-11

## Purpose

Aegis Core maintains a persistent workspace knowledge graph so clients can reason from project structure, dependencies, symbols, history, validation outcomes, and architecture memory instead of relying only on the current prompt.

The graph is local-first and stored under `.aegis`. It is intended to support roadmap generation, architecture reasoning, safer edits, dependency-aware execution planning, repair scoping, project navigation, and multi-session continuity.

## Graph Model

Core models:

- files and folders
- modules and runtime boundaries
- classes, functions, methods, services, UI components, and APIs
- imports/includes, dependencies, calls, references, inheritance, ownership, and containment
- route bindings and API consumers/providers
- build systems, configs, databases, validation targets, workflows, roadmap items, decisions, known issues, and repair history

Graph records are stored in:

- `.aegis/knowledge-graph.json`
- `.aegis/knowledge-summary.md`
- `.aegis/knowledge-index-state.json`
- `.aegis/semantic-index.json`
- `.aegis/project-memory.json`

## Indexing Lifecycle

Indexing uses the workspace scanner, then enriches scan output with language-specific analyzers and memory sources.

Current analyzer foundations:

- TypeScript/JavaScript: imports, functions, components, classes, API consumers, calls
- Python: imports, classes, methods/functions, FastAPI routes, calls
- C/C++: includes, classes/structs, functions/methods, calls
- C#: using directives, classes/interfaces/records/structs, methods, inheritance
- JSON/YAML/TOML/configs: config/build-system nodes and package dependencies

The index records:

- indexing duration
- graph size
- files indexed
- language coverage
- symbol counts
- stale/invalidated nodes
- changed/removed files
- indexing failures
- unsupported language areas

## Incremental Updates

Core writes file fingerprints to `.aegis/knowledge-index-state.json`.

When the graph is requested with persistence enabled:

- if fingerprints are unchanged, Core returns the persisted graph with `cache_hit: true`
- if files changed or disappeared, Core records `incremental.changed_files`, `removed_files`, and `invalidated_nodes`
- clients can use these fields to refresh only affected views

The current implementation still rebuilds the graph when files changed, but the persistent invalidation contract is now in place for narrower per-file graph updates.

## APIs

- `GET /v1/knowledge/graph`
- `POST /v1/knowledge/graph`
- `POST /v1/knowledge/query`
- `POST /v1/knowledge/search`
- `POST /v1/knowledge/relationships`
- `POST /v1/knowledge/symbol`
- `POST /v1/knowledge/impact-analysis`
- `GET /v1/knowledge/architecture-summary`

## Impact Analysis

`POST /v1/knowledge/impact-analysis` accepts a file, symbol, route, system, or node focus and returns:

- affected files
- likely breakage areas
- modification risk
- validation targets
- related workflows
- relationship edges used for the analysis

Engineering execution plans consume this output to raise risk, prioritize validation targets, and choose smaller repair scope.

## Semantic Retrieval Direction

Core does not require embeddings yet. Graph records include stable IDs, file purpose summaries, architecture summaries, and retrieval metadata so future embedding providers can be added without changing the client-facing contracts.

Planned optional interfaces:

- local embedding model
- hybrid graph/vector search
- provider-neutral semantic retrieval
