# OmniLibrarian Project Structure

This document describes the planned repository structure for the OmniLibrarian course project.

The project should stay as one Python monorepo. FastAPI, Streamlit, shared application logic, ingestion scripts, eval scripts, and MCP servers live in the same repository, but each part has a clear boundary.

## Proposed Tree

```text
ai_course_project/
  docs/other_docs/COURSE_PROJECT_PROPOSAL.md
  README.md
  pyproject.toml
  .env.example
  docker-compose.yml

  configs/
    tenants.yaml

  data/
    cache/
      ingestion.sqlite
    raw/
      bg3/
      blue_prince/
    processed/
      bg3/
      blue_prince/
    eval/
      golden_questions.jsonl

  apps/
    api/
      main.py
      routes/
        chat.py
        health.py
      schemas/
        chat.py

    streamlit_app/
      app.py

  src/
    omnilibrarian/
      core/
        config.py
        logging.py
        timing.py

      tenants/
        models.py
        registry.py

      graph/
        state.py
        workflow.py
        nodes/
          route_request.py
          prepare_query.py
          retrieve_context.py
          decide_tool.py
          call_tool.py
          generate_answer.py
          verify_answer.py

      rag/
        embeddings.py
        chunking.py
        qdrant_store.py
        retriever.py

      ingestion/
        cache.py
        documents.py
        sources/
          base.py
          bg3_wiki.py

      llm/
        base.py
        openai_provider.py
        openrouter_provider.py
        prompts.py

      mcp_clients/
        base.py
        registry.py
        bg3_client.py
        blue_prince_client.py

      memory/
        session_store.py

      tracing/
        trace.py
        phoenix.py
        langsmith.py

      evals/
        runner.py
        metrics.py

  mcp_servers/
    bg3/
      server.py
      tools.py
      data/
        spells.json
        items.json
        classes.json

    blue_prince/
      server.py
      tools.py
      data/
        rooms.json
        items.json
        hints.json

  scripts/
    ingest.py
    eval.py
    smoke_chat.py

  tests/
    test_tenant_isolation.py
    test_router.py
    test_retriever.py
    test_mcp_tools.py
    test_chat_api.py

  docs/
    PROJECT_STRUCTURE.md
    MCP_ARCHITECTURE.md
    superpowers/
      specs/
        2026-05-29-omnilibrarian-architecture-design.md
```

## Directory Responsibilities

### `apps/`

Application entry points.

- `apps/api/` contains the FastAPI gateway.
- `apps/streamlit_app/` contains the simple demo UI.

These files should stay thin. They should call reusable logic from `src/omnilibrarian/`.

### `src/omnilibrarian/`

Main application package.

This is where most testable business logic should live:

- tenant registry
- LangGraph workflow
- RAG and retrieval
- LLM providers
- MCP clients
- tracing helpers
- eval helpers
- session memory

### `mcp_servers/`

Game-specific MCP servers.

Each game gets its own MCP server directory. For the MVP, tools can be deterministic and backed by small JSON files. This keeps the MCP layer demonstrable without making it a large data project.

See `docs/MCP_ARCHITECTURE.md` for the intended boundary between shared RAG infrastructure and domain-specific MCP tools.

### `data/`

Project data.

- `cache/`: SQLite cache metadata for fetched source pages.
- `raw/`: manually collected or scraped source documents.
- `processed/`: normalized documents/chunks ready for embedding.
- `eval/`: golden question set and expected labels.

Raw and processed data should be split by `game_id`.

### `src/omnilibrarian/ingestion/`

Source ingestion logic.

This package should own:

- source adapter interfaces;
- BG3 wiki adapter;
- fetch cache metadata;
- raw document models;
- conversion from raw documents to processed chunks.

The ingestion layer should write raw source data before chunking and embedding, so later processing can be rerun without re-fetching source pages.

### `scripts/`

Operational commands.

- `ingest.py`: prepare documents, generate embeddings, and upload vectors to Qdrant.
- `eval.py`: run local evaluation over the golden set.
- `smoke_chat.py`: send a basic chat request to the API for quick verification.

### `tests/`

Automated tests.

The most important early tests are:

- tenant isolation
- router behavior
- retriever filtering
- MCP tool behavior
- `/v1/chat` response shape

## Stable API Contract

Primary endpoint:

```text
POST /v1/chat
```

The original proposal mentions `/chat`; this can be supported as an alias, but `/v1/chat` should be the main stable API.

Request:

```json
{
  "message": "Яка шкода від Fireball у BG3?",
  "session_id": "demo-session-1",
  "game_id": "bg3",
  "stream": false
}
```

Response:

```json
{
  "answer": "Fireball у BG3 завдає 8d6 fire damage...",
  "game_id": "bg3",
  "intent": "spell_info",
  "sources": [],
  "tool_calls": [],
  "trace": [],
  "latency_ms": 1234
}
```

Health endpoints:

```text
GET /health
GET /ready
```

`/health` should confirm the API process is alive.

`/ready` should confirm required dependencies are reachable, especially Qdrant and the configured LLM provider if strict readiness is enabled.

## Internal Interfaces

Keep these boundaries explicit:

```text
GameRouter.route(message, explicit_game_id)
Retriever.search(query, game_id, limit)
LLMProvider.complete(system_prompt, user_prompt)
LLMProvider.stream(system_prompt, user_prompt)
MCPClient.call_tool(game_id, tool_name, arguments)
```

These interfaces make the architecture easier to explain and easier to change:

- OpenAI can be swapped for OpenRouter.
- The embedding model can be changed without touching FastAPI.
- Qdrant logic stays isolated from LangGraph nodes.
- MCP tool calls stay isolated from answer generation.

## LangGraph State

Recommended state shape:

```python
class AgentState(TypedDict):
    original_query: str
    detected_language: str
    search_query: str
    session_id: str
    game_id: str | None
    detected_game_id: str
    intent: str
    history: list[dict]
    retrieved_chunks: list[dict]
    selected_tool: str | None
    tool_result: dict | None
    answer: str
    sources: list[dict]
    tool_calls: list[dict]
    trace: list[dict]
```

Important: query preparation should be separate from retrieval. This gives us a clean place to add translation or query reformulation later.

## First Scaffold Order

Build only the minimum useful structure first:

1. `pyproject.toml`
2. `.env.example`
3. `docker-compose.yml`
4. `configs/tenants.yaml`
5. `apps/api/`
6. `src/omnilibrarian/rag/`
7. `src/omnilibrarian/graph/`
8. `scripts/ingest.py`
9. `data/raw/bg3/`
10. `tests/test_tenant_isolation.py`

After that, implement the BG3 vertical slice before filling out the whole tree.

## Design Principle

Do not create every file upfront just because it appears in the proposed tree.

The tree is a target shape. Files should be added when the implementation needs them. The first goal is a working BG3 vertical slice with clear boundaries, not an empty architecture shell.
