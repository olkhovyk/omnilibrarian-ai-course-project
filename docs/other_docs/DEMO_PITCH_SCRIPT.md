# Demo Pitch Script

## 30-Second Summary

OmniLibrarian is a multi-game AI knowledge assistant. It answers game questions using grounded RAG, source citations, LangGraph orchestration, MCP tools, local embeddings, Qdrant, BM25, evals, traces, Redis cache, and source-aware retrieval.

The main point is not the UI. The main point is the AI architecture: one reusable platform that can support multiple games with isolated knowledge, source-specific ingestion, game-specific tools, and measurable quality.

## 3-5 Minute Flow

### 1. Problem

Players search across wikis, mechanics pages, community hints, and patch notes. A plain LLM can hallucinate or mix sources. I wanted a system that answers from retrieved evidence, cites sources, and knows when to call a structured game tool.

### 2. Architecture

Show the architecture in words:

```text
UI -> FastAPI -> LangGraph -> Safety -> Retrieval or MCP -> LLM -> Answer + Sources + Trace
```

Key points:

- `game_id` scopes every retrieval call.
- Qdrant stores all chunks in one collection but filters by game.
- BM25 handles exact terms, vectors handle semantic matching.
- MCP tools handle structured operations such as spell comparison or puzzle hints.
- Evals measure retrieval, tool routing, and answer quality.

### 3. Demo: Factual RAG

Question:

```text
What damage does Fireball do?
```

Show:

- grounded answer;
- source list;
- trace with retrieval query and cache status.

Talking point:

The model is not answering from memory only. It receives retrieved context and must cite it.

### 4. Demo: MCP Tool Routing

Question:

```text
Compare Fireball and Lightning Bolt
```

Show trace:

```text
mcp_call
tool: compare_bg3_spells
transport: mcp_client
```

Talking point:

LangGraph decides when semantic search is enough and when a structured MCP tool is better.

### 5. Demo: Multi-Game And Source Policy

Question:

```text
I am stuck on Room 46, give me a spoiler-light hint
```

Show trace:

- `game_id=blue_prince`;
- `source_mix`;
- `source_policy_reasons`;
- Reddit source if available.

Talking point:

Wiki remains the authority for factual questions. Reddit is a community hint source and is promoted only for hint-style requests.

### 6. Evals

Show terminal or result files:

```powershell
python scripts/omni.py eval blue_prince retrieval
python scripts/omni.py eval blue_prince answers
```

Mention:

- Hit@k / MRR / tenant isolation.
- Source hit@5 for Reddit cases.
- Answer eval checks citations, source titles, terms, and insufficient-context behavior.

### 7. Engineering Quality

Mention:

- high-level CLI: `python scripts/omni.py ...`;
- source-scoped indexing prevents accidental deletion of another source;
- Redis LLM cache controls cost;
- rate limiting protects public demo;
- prompt injection protection treats retrieved text as untrusted context;
- AWS deployment plan is documented.

## Likely Questions And Answers

**Why not one MCP server per full RAG stack?**

Because that duplicates expensive platform logic. MCP servers should expose domain-specific tools, while shared retrieval, cache, tracing, and evals remain in the platform.

**Why use both BM25 and vectors?**

BM25 is good for exact names and terms. Vectors are good for semantic similarity and multilingual queries. Hybrid retrieval gives better robustness.

**Why use Reddit if wiki is more reliable?**

Reddit is useful for community hints and player strategies. The source policy prevents it from outranking wiki facts for normal factual questions.

**How do you know quality improved?**

The project has retrieval eval, tool-routing eval, answer eval, and trace visibility. Quality is measured instead of guessed.

**How would you add another game?**

Add a source adapter, normalizer, chunks/entities, tenant config, optional MCP tools, and eval cases. The shared API, retriever, LangGraph workflow, cache, and UI remain mostly unchanged.

## Final Closing

OmniLibrarian demonstrates a production-style AI architecture in a course-project scope: grounded answers, reusable multi-tenant RAG, MCP tools, source-aware retrieval, evals, traces, caching, and deployment planning.
