# Observability Future Plan

> **Status:** Future work. Do not implement before the LLM chat smoke and basic API flow are working.

## Goal

Add RAG/LLM observability so we can understand why answers are good or bad,
measure retrieval quality, inspect prompts, and improve the system with evidence.

## Recommended Direction

Start with an internal trace contract, then export to Arize Phoenix first.
Keep the abstraction small enough that LangSmith can be added later without
rewriting the application flow.

## Why Phoenix First

Phoenix is a good fit for this project because:

- it is open-source and friendly for local development;
- it supports LLM/RAG traces;
- it can show retrieval, reranking, prompts, LLM calls, and custom spans;
- it has eval-oriented workflows for retrieval relevance and groundedness;
- it is easy to demonstrate during coursework defense.

LangSmith remains a strong later option, especially after the LangGraph workflow
is implemented.

## Trace Contract

Introduce an internal trace model before wiring any vendor SDK directly into
business logic.

Suggested shape:

```python
TraceRun(
    name="rag_chat",
    input={"message": "...", "game_id": "bg3"},
    spans=[
        TraceSpan(
            name="query_rewrite",
            input={"original_query": "..."},
            output={
                "retrieval_query": "...",
                "rewrite_reasons": [...],
            },
            latency_ms=...
        ),
        TraceSpan(
            name="retrieval",
            input={"game_id": "bg3", "candidate_limit": 20, "final_limit": 5},
            output={"top_titles": [...], "scores": [...]},
            latency_ms=...
        ),
        TraceSpan(
            name="rerank",
            output={"rerank_scores": [...], "rerank_reasons": [...]},
            latency_ms=...
        ),
        TraceSpan(
            name="llm_answer",
            input={"provider": "openrouter", "model": "..."},
            output={"answer": "...", "sources": [...]},
            latency_ms=...
        ),
    ],
)
```

## Adapter Boundary

Keep vendor-specific code behind a small interface:

```python
class TraceExporter(Protocol):
    def export(self, run: TraceRun) -> None:
        ...
```

Planned exporters:

- `NoopTraceExporter`
- `ConsoleTraceExporter`
- `PhoenixTraceExporter`
- `LangSmithTraceExporter` later

Application code should create `TraceRun` / `TraceSpan` objects and pass them to
an exporter. It should not call Phoenix or LangSmith SDKs directly from
retrieval, reranking, or answer generation modules.

## Metrics To Track

### Retrieval

- `candidate_limit`
- `final_limit`
- top titles
- vector scores
- rerank scores
- source URLs

### Query Rewriting

- original query
- retrieval query
- rewrite reasons
- whether entity fuzzy matching was used

### Reranking

- rerank reasons
- title diversity for comparative queries
- movement from vector rank to rerank rank

### LLM Answer

- provider
- model
- prompt preview or prompt hash
- answer
- sources
- latency
- token usage when available

### Eval Later

- recall@k
- top-1 accuracy
- groundedness
- answer faithfulness
- tenant isolation
- latency p50/p95

## Implementation Order Later

1. Add `TraceRun`, `TraceSpan`, and `TraceExporter` models.
2. Add `ConsoleTraceExporter` and show trace summary in `smoke_chat.py`.
3. Add trace collection to query rewrite, retrieval, rerank, and answer generation.
4. Add Phoenix exporter.
5. Add eval runner that can export experiment traces.
6. Add LangSmith exporter only after LangGraph workflow exists.

## Current Decision

Do not implement this now. First, run and validate the new LLM smoke chain:

```text
query normalization -> retrieval -> rerank -> LLM answer -> sources
```

After that works locally, observability becomes the next architecture layer.
