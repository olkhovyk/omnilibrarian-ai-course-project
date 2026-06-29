# OmniLibrarian Final Submission

## Project Summary

OmniLibrarian is a multi-game AI knowledge assistant built as an AI Engineering course project. It answers questions about supported game knowledge bases using Retrieval-Augmented Generation, LangGraph orchestration, MCP tools, local embeddings, Qdrant vector search, BM25 lexical search, evals, traces, caching, and a simple Streamlit UI.

The project intentionally prioritizes AI architecture over UI complexity. The UI is lightweight, while the backend demonstrates production-style boundaries: source ingestion, chunking, embeddings, vector indexing, tenant isolation, tool routing, evaluation, caching, safety checks, and deployment planning.

Supported game tenants:

- `bg3`: Baldur's Gate 3 wiki knowledge.
- `blue_prince`: Blue Prince wiki knowledge plus curated Reddit community hint content.

## Problem

Players often need factual, source-grounded answers across large game wikis, mechanics pages, community hints, and patch discussions. Generic LLM answers can hallucinate or mix unrelated sources. OmniLibrarian solves this by retrieving game-scoped evidence, citing sources, and using game-specific MCP tools when a structured operation is more appropriate than direct semantic search.

## Key Features

- FastAPI chat API with stable `/v1/chat` endpoint.
- Streamlit browser UI for local demo.
- LangGraph workflow for request preparation, safety guard, retrieval/tool routing, and answer generation.
- RAG with Qdrant vector search filtered by `game_id`.
- BM25 lexical search and hybrid retrieval.
- Local multilingual embeddings with `BAAI/bge-m3`.
- Source-aware retrieval policy: wiki is preferred for factual questions, Reddit can be promoted for hint/community questions.
- MCP servers for BG3 and Blue Prince over streamable HTTP.
- Redis LLM response cache and rate limiting.
- Raw ingestion cache before chunking and embeddings.
- Retrieval, tool-routing, and answer-level evals.
- Trace output with retrieval query, rewrite reasons, source mix, source policy reasons, cache status, and MCP tool calls.

## Architecture

```text
Streamlit UI
  -> FastAPI /v1/chat
  -> LangGraph workflow
  -> Prompt safety guard
  -> Direct RAG or MCP tool routing
  -> Hybrid retrieval: BM25 + Qdrant vectors
  -> Source policy and reranking
  -> OpenAI/OpenRouter answer generation
  -> Answer with citations, sources, and trace
```

MCP does not own a separate RAG database. Each MCP server calls the shared knowledge platform through a scoped game boundary. This keeps retrieval, caching, evals, and observability reusable while allowing game-specific tools.

## Main Technical Decisions

- **Python/FastAPI + Streamlit**: fast to build and easy to demo locally.
- **LangGraph**: explicit orchestration instead of one large prompt.
- **Qdrant**: vector store with tenant isolation by `game_id`.
- **BM25 + vectors**: lexical exact matches plus semantic search.
- **MCP per game**: clean tool boundary for structured game operations.
- **Local embeddings**: uses available GPU locally and reduces paid API usage.
- **OpenRouter/OpenAI for LLM**: paid API is used only for answer generation.
- **Redis cache**: avoids repeated LLM cost for identical grounded prompts.
- **Eval-first quality loop**: retrieval, tool routing, and answer quality are measured.

## How To Run Locally

Install dependencies:

```powershell
python -m pip install -e .
```

Start supporting services such as Qdrant and Redis:

```powershell
docker compose up -d
```

Run the app, API, and MCP servers with one command:

```powershell
python scripts/omni.py dev
```

Open the UI:

```text
http://127.0.0.1:8501
```

Run the full Blue Prince ingestion/index/eval loop:

```powershell
python scripts/omni.py pipeline blue_prince
```

Preview planned commands without executing them:

```powershell
python scripts/omni.py --dry-run pipeline blue_prince
```

## Important Environment Variables

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=...
LLM_MODEL=openai/gpt-4.1-mini

QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=omnilibrarian_chunks

EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DEVICE=cuda

REDIS_URL=redis://localhost:6379/0
LLM_CACHE_ENABLED=true

MCP_ENABLED=true
BG3_MCP_URL=http://127.0.0.1:8765/mcp
BLUE_PRINCE_MCP_URL=http://127.0.0.1:8766/mcp
```

For Blue Prince local chat retrieval:

```env
ENTITY_REGISTRY_PATH=data/processed/blue_prince/blue_prince_wiki_entities.json
BM25_CHUNKS_PATH=data/processed/blue_prince/blue_prince_wiki_chunks.jsonl
BM25_EXTRA_CHUNKS_PATHS=data/processed/blue_prince/blue_prince_reddit_chunks.jsonl
```

## Evals

Run Blue Prince retrieval eval:

```powershell
python scripts/omni.py eval blue_prince retrieval
```

Run Blue Prince answer eval:

```powershell
python scripts/omni.py eval blue_prince answers
```

Run tests:

```powershell
python -m pytest
python -m compileall apps src scripts mcp_servers tests
```

Latest verified automated test status in development:

```text
188 passed
compileall OK
```

## Demo Questions

BG3:

- `What damage does Fireball do?`
- `Compare Fireball and Lightning Bolt`
- `List all companions`

Blue Prince:

- `What is Room 46?`
- `How do blueprints work?`
- `I am stuck on Room 46, give me a spoiler-light hint`

## What To Show In The Demo

1. Start with the Streamlit UI and ask a factual question.
2. Open the trace and show retrieval query, sources, source mix, and cache status.
3. Ask a tool-routed question such as `Compare Fireball and Lightning Bolt` and show MCP transport in trace.
4. Ask a Blue Prince hint question and show Reddit/wiki source policy behavior.
5. Show eval results JSON or terminal output.
6. Explain that adding a new game means adding source adapters, entities, data, MCP tools, and eval cases while the platform stays reusable.

## Known Limitations

- UI is intentionally simple and optimized for demonstration, not product polish.
- Reddit ingestion uses curated posts, not a full subreddit crawl.
- Cloud deployment is planned but not required for the local MVP.
- Source quality depends on the ingested corpus and eval set coverage.

## Key Documentation

- `README.md`
- `docs/MCP_ARCHITECTURE.md`
- `docs/BLUE_PRINCE_EVAL_REPORT.md`
- `docs/SCREENSHOT_SUBMISSION_CHECKLIST.md`
- `docs/other_docs/PROJECT_STRUCTURE.md`
- `docs/other_docs/DATA_SOURCES.md`
- `docs/other_docs/BLUE_PRINCE_SOURCES.md`
- `docs/other_docs/AWS_DEPLOYMENT_AND_SECURITY_PLAN.md`
- `docs/other_docs/RERANKING_READING_LIST.md`
