# OmniLibrarian Architecture Review

Date: 2026-06-02

## Executive Summary

The project is not broken. The architecture direction is strong, and the codebase already contains many serious AI Engineering pieces: FastAPI, RAG, Qdrant, LangGraph, MCP-facing tools, ingestion, evals, Redis cache, rate limiting, and Streamlit UI.

The main issue is scope drift. The project started as a vertical-slice MVP, but implementation has expanded into many stretch-goal areas before the demo-critical path is fully stabilized. For the course defense, the safest move is to stop adding broad features and harden one end-to-end flow.

## Findings

### P1: MVP Promises Two Tenants, But Only BG3 Is Really Implemented

The architecture docs and tenant config define both `bg3` and `blue_prince`, but the working data and UI path are BG3-only.

Evidence:

- `configs/tenants.yaml` registers `blue_prince`.
- `scripts/ingest.py` only accepts `--game-id bg3`.
- `apps/streamlit_app/app.py` only shows `["bg3"]` in the game selector.
- `mcp_servers/blue_prince/server.py` is only a scaffold.
- `mcp_servers/blue_prince/tools.py` returns `not_implemented`.
- `data/processed/blue_prince/` contains only `.gitkeep`.

Risk:

Tenant isolation is one of the core course-project claims. Without real Blue Prince data and retrieval, the project currently demonstrates a BG3 assistant more than a multi-tenant platform.

Recommendation:

Add a minimal Blue Prince slice: 5-10 local documents, chunks, index path, UI selector, tenant isolation tests, and one simple deterministic tool.

### P1: `stream` Exists In The API Contract But Streaming Is Not Implemented

`ChatRequest` accepts `stream: bool`, but the route ignores it and the LLM providers raise `NotImplementedError` for `stream()`.

Evidence:

- `apps/api/schemas/chat.py` defines `stream`.
- `apps/api/routes/chat.py` calls `service.answer(...)` without passing `stream`.
- `src/omnilibrarian/llm/openai_provider.py` and `src/omnilibrarian/llm/openrouter_provider.py` have unimplemented `stream()`.

Risk:

This creates a misleading public contract. A user can request streaming, but the backend always behaves as non-streaming.

Recommendation:

For MVP, either remove `stream` from the public contract or explicitly reject `stream=true` with a clear `400` response. Implement real streaming only if it is needed for the defense demo.

### P1: `/ready` Does Not Check Real Runtime Readiness

The docs say `/ready` should check dependencies such as Qdrant and the configured LLM provider, but the implementation only loads tenant config and returns `ready`.

Evidence:

- `docs/other_docs/PROJECT_STRUCTURE.md` says `/ready` should confirm dependencies are reachable.
- `apps/api/routes/health.py` returns tenant IDs only.

Risk:

The API can report `ready` while Qdrant, Redis, embeddings, or LLM provider configuration are missing or broken.

Recommendation:

Make `/ready` return separate checks:

- tenants config loaded;
- Qdrant reachable and collection available;
- Redis reachable if cache/rate-limit is enabled;
- LLM provider configured;
- entity registry/chunks files present if hybrid retrieval is enabled.

### P2: Local Defaults Are Too Fragile For Demo

The default configuration assumes CUDA, warmup on startup, Redis-enabled cache/rate limits, and OpenRouter as the default LLM provider.

Evidence:

- `EMBEDDING_DEVICE` defaults to `cuda`.
- `WARMUP_ON_STARTUP` defaults to `true`.
- `LLM_PROVIDER` defaults to `openrouter`.
- `LLM_CACHE_ENABLED` and `RATE_LIMIT_ENABLED` default to `true`.

Risk:

The app may fail before the demo starts if CUDA is unavailable, API keys are missing, Qdrant is not indexed, or Redis is not running.

Recommendation:

Create demo-safe defaults or a `.env.demo`:

```env
EMBEDDING_DEVICE=cpu
WARMUP_ON_STARTUP=false
LLM_CACHE_ENABLED=false
RATE_LIMIT_ENABLED=false
ENTITY_REGISTRY_PATH=data/processed/bg3/bg3_wiki_entities.json
BM25_CHUNKS_PATH=data/processed/bg3/bg3_wiki_seed107_chunks.jsonl
```

Then document one exact command sequence for the defense.

### P2: MCP Is Currently MCP-Shaped, Not Fully Wired

The BG3 MCP server exists and tools are tested, but LangGraph imports the BG3 tool handler directly instead of going through an MCP client/server boundary. MCP client classes are still `NotImplemented`.

Evidence:

- `src/omnilibrarian/graph/workflow.py` imports `compare_bg3_spells` directly from `mcp_servers.bg3.tools`.
- `src/omnilibrarian/mcp_clients/bg3_client.py` raises `NotImplementedError`.

Risk:

The project can demonstrate a local structured tool path, but it cannot honestly claim a complete gateway-to-MCP-client-to-MCP-server integration yet.

Recommendation:

Choose one:

- complete one real MCP client path for BG3; or
- describe the current state as a local tool adapter with MCP-compatible server scaffolding.

For defense credibility, one real MCP call path is better than many scaffolded tools.

### P2: Follow-Up Memory Is Claimed But Not Implemented

The architecture docs include a follow-up question scenario where session context remembers the topic, but `SessionStore` currently returns an empty history and does not persist turns.

Evidence:

- `docs/other_docs/superpowers/specs/2026-05-29-omnilibrarian-architecture-design.md` expects follow-up context.
- `src/omnilibrarian/memory/session_store.py` is a stub.

Risk:

Follow-up demo scenarios may fail or behave like independent questions.

Recommendation:

Either remove follow-up memory from MVP claims or implement a small in-memory session store and pass recent history into query preparation.

### P3: Eval Is Useful But Too Small For The Claimed Scope

The current retrieval golden set has 10 BG3 cases. That is fine for a smoke test, but not enough to prove the full architecture.

Evidence:

- `data/evals/bg3_retrieval_golden.jsonl` contains 10 cases.
- There are no Blue Prince, tenant isolation, groundedness, tool accuracy, or latency eval cases.

Risk:

The project claims eval and observability as a major AI Engineering feature, but the current eval evidence is still thin.

Recommendation:

Expand evals to 30-50 cases:

- BG3 factual retrieval;
- Blue Prince factual retrieval;
- cross-lingual Ukrainian queries;
- tenant isolation cases;
- tool-routing cases;
- answer groundedness checks;
- latency p50/p95 report.

## Strengths

- The project has a clear architecture-first goal.
- Entry points are mostly thin.
- `Retriever`, `HybridRetriever`, `KnowledgeService`, and `AnswerGenerator` are useful boundaries.
- Ingestion has raw cache, normalization, chunking, and processed data layers.
- RAG has dense vector retrieval, BM25, query rewriting, and reranking.
- LangGraph is present and testable.
- Tests are broad for the current implementation level.
- Streamlit UI is simple and appropriate for a course demo.

## Verification Performed

Commands run:

```powershell
python -m pytest -q
python -m compileall apps src scripts mcp_servers tests
```

Result:

- `pytest`: 96 passed, 1 warning.
- `compileall`: completed successfully.

This means the current codebase is internally consistent at the unit-test and import/compile level. It does not prove that the full runtime demo path is ready, because the tests mostly use fakes and do not validate a real Qdrant + embedding + LLM + UI flow.

## Recommended Defense-Focused Plan

### 1. Freeze Scope

Do not add new broad features until the demo path is stable.

### 2. Stabilize BG3 End-To-End

Make sure this works repeatedly:

```text
Streamlit UI
  -> FastAPI /v1/chat
  -> LangGraph
  -> BG3 retrieval
  -> answer generation
  -> sources + trace
```

### 3. Add Minimal Blue Prince

Only enough to prove multi-tenancy:

- small local dataset;
- processed chunks;
- indexed vectors;
- UI game selector;
- tenant isolation test;
- one basic tool or retrieval-only flow.

### 4. Make Readiness Honest

Update `/ready` so it exposes real dependency status. This helps debugging and gives a strong production-engineering talking point.

### 5. Clarify Streaming And MCP Claims

Either implement them or explicitly mark them as stretch goals. Do not leave public contracts half-promising behavior.

### 6. Strengthen Eval

Create a small report that can be shown during defense:

- retrieval hit@k;
- tenant isolation pass/fail;
- tool routing accuracy;
- latency numbers;
- a few grounded answer examples.

## Bottom Line

OmniLibrarian is a strong course-project idea and the codebase already has real engineering substance. The biggest risk is not technical weakness; it is presenting an architecture that is wider than the stable demo path.

The next best move is to make the project narrower, more honest, and more repeatable:

```text
One polished BG3 vertical slice
+ one minimal Blue Prince tenant
+ honest readiness
+ visible evals
= strong AI Engineering course defense
```
