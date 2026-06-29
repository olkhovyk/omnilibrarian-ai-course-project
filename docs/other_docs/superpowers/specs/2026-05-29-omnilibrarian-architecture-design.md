# OmniLibrarian Architecture Design

## Project Direction

OmniLibrarian is a multi-tenant AI gateway for game knowledge bases. The project should demonstrate strong AI engineering architecture rather than a polished product UI.

The main goal is to show an end-to-end system that combines:

- RAG over game knowledge bases.
- Cross-lingual retrieval: Ukrainian questions over English documents.
- Tenant isolation between different games.
- LangGraph as an explicit agent workflow.
- MCP tools per game.
- Evaluation and traces for defense/demo.

The chosen implementation strategy is **Vertical Slice First**.

## Key Decisions

- Backend: Python with FastAPI.
- UI: simple Streamlit demo UI.
- Workflow orchestration: LangGraph.
- Vector database: Qdrant.
- Multi-tenancy model: one Qdrant collection with payload filter by `game_id`.
- LLM provider: OpenAI or OpenRouter.
- Embeddings: local multilingual embedding model on GPU.
- First embedding candidate: `BAAI/bge-m3`.
- Observability: LangSmith or Arize Phoenix.
- Testing: pytest plus local eval scripts.

Paid APIs are acceptable for the course project. The preferred split is to use paid LLM APIs for reasoning, routing, answer generation, and groundedness checks, while keeping embeddings local to demonstrate control over the RAG pipeline.

## MVP Scope

The MVP should include only the pieces that prove the architecture:

- Two tenants:
  - `bg3`: Baldur's Gate 3.
  - `blue_prince`: Blue Prince.
- FastAPI endpoint `/chat`.
- Qdrant collection with strict `game_id` filtering.
- Local multilingual embeddings.
- LangGraph workflow.
- MCP server per game.
- Basic evaluation suite.
- Streamlit UI with answer, sources, tool calls, and trace/debug panel.

## Non-Goals For MVP

These should stay as stretch goals unless the core system is already stable:

- Custom PyTorch router.
- Dynamic MCP discovery.
- Complex reranker.
- Auth, billing, or real user accounts.
- Kubernetes.
- Fine-tuning.
- Complex long-term memory.
- Polished production UI.

## Vertical Slice Plan

The first working slice should be built for BG3:

```text
Ukrainian BG3 question
  -> FastAPI /chat
  -> LangGraph route_request
  -> retrieve BG3 chunks from Qdrant
  -> decide whether to call a BG3 MCP tool
  -> call tool if useful
  -> generate Ukrainian answer
  -> return answer, sources, tool calls, latency, and trace
```

After the BG3 slice works, Blue Prince should be added through the same abstractions as a second tenant. This is important because the defense should show that the system is not a hardcoded single-game chatbot.

## What "Ingestion" Means

Ingestion is the process of taking raw knowledge sources and preparing them for retrieval.

For BG3, ingestion means:

1. Collect a small but clean set of BG3 documents.
2. Normalize them into a consistent internal format.
3. Split long text into searchable chunks.
4. Add metadata to every chunk, especially:
   - `game_id`
   - `source`
   - `title`
   - `doc_type`
5. Generate embeddings for each chunk using the local multilingual embedding model.
6. Upload the chunks and vectors into Qdrant.

Example normalized chunk:

```json
{
  "game_id": "bg3",
  "source": "wiki",
  "title": "Fireball",
  "doc_type": "spell",
  "text": "Fireball is a level 3 evocation spell that deals 8d6 fire damage..."
}
```

In simpler words: ingestion is how raw wiki/game data becomes searchable knowledge for RAG.

## Core Components

### FastAPI Gateway

Responsibilities:

- Expose `/chat`.
- Validate request fields.
- Pass request into the LangGraph workflow.
- Return a structured response with:
  - answer
  - detected game
  - intent
  - sources
  - tool calls
  - latency
  - trace

Expected request:

```json
{
  "message": "Яка шкода від Fireball у BG3?",
  "session_id": "demo-session-1",
  "game_id": "bg3"
}
```

Expected response:

```json
{
  "answer": "Fireball у BG3 завдає 8d6 fire damage...",
  "game_id": "bg3",
  "intent": "spell_info",
  "sources": [],
  "tool_calls": [],
  "latency_ms": 1234,
  "trace": []
}
```

### LangGraph Workflow

Recommended graph:

```text
START
  -> route_request
  -> retrieve_context
  -> decide_tool
  -> call_tool_or_skip
  -> generate_answer
  -> verify_answer
  -> END
```

State shape:

```python
class AgentState(TypedDict):
    message: str
    session_id: str
    game_id: str | None
    detected_game_id: str
    intent: str
    retrieved_chunks: list[dict]
    selected_tool: str | None
    tool_result: dict | None
    answer: str
    sources: list[dict]
    trace: list[dict]
```

### Qdrant Multi-Tenancy

Use one collection for all games. Every vector payload must include `game_id`.

All retrieval must apply a filter:

```text
game_id == detected_game_id
```

This enables a simple but strong tenant isolation demo:

- BG3 questions should not return Blue Prince chunks.
- Blue Prince questions should not return BG3 chunks.

### MCP Servers

Use one MCP server per game.

BG3 tools:

- `get_spell_info(spell_name)`
- `get_item_info(item_name)`
- `get_class_info(class_name)`
- `roll_dice(dice_formula)`

Blue Prince tools:

- `get_room_info(room_name)`
- `get_item_info(item_name)`
- `search_puzzle_hint(topic)`

For the MVP, tools can be deterministic and backed by small local JSON datasets. This keeps MCP useful for architecture without turning it into a separate data engineering project.

### Streamlit UI

The UI is intentionally simple.

It should show:

- Game selector.
- Chat input.
- Assistant answer.
- Sources panel.
- Tool calls panel.
- Trace/debug panel.
- Latency metrics.

The UI should support the defense by making the AI pipeline visible.

## Evaluation Plan

Create a golden set of 30-50 questions.

Evaluation categories:

- Game routing accuracy.
- Intent accuracy.
- Retrieval recall@k.
- Tenant isolation.
- Groundedness.
- Tool selection accuracy.
- Latency p50 and p95.

The eval output should be a small report/table that can be used during the course defense.

## Two-Week Milestones

### Days 1-3: Data And Infrastructure

- Create repo structure.
- Add Docker Compose.
- Run Qdrant.
- Implement BG3 ingestion.
- Generate local embeddings.
- Upload BG3 chunks to Qdrant.

### Days 4-5: Basic RAG

- Add FastAPI `/chat`.
- Retrieve chunks with `game_id` filter.
- Generate Ukrainian answers through OpenAI/OpenRouter.
- Return sources in response.

### Days 6-7: LangGraph Workflow

- Add graph state.
- Implement route, retrieve, answer nodes.
- Return trace/debug data.

### Days 8-9: MCP Tools

- Add BG3 MCP server.
- Add tool decision node.
- Call MCP tool from graph.
- Include tool calls/results in final response.

### Days 10-11: Second Tenant

- Add Blue Prince dataset.
- Run Blue Prince ingestion.
- Add Blue Prince MCP server.
- Add tenant isolation tests.

### Days 12-13: Eval And Observability

- Build golden set.
- Add eval scripts.
- Add LangSmith or Phoenix traces.
- Produce metrics report.

### Day 14: Demo Preparation

- Build Streamlit UI.
- Polish README.
- Prepare demo scenarios.
- Verify the end-to-end defense flow.

## Defense Scenarios

### Cross-Lingual BG3 RAG

User:

```text
Яка шкода від Fireball у BG3?
```

Expected:

- Game detected as `bg3`.
- Intent detected as `spell_info`.
- English Fireball documents retrieved.
- Ukrainian grounded answer returned.
- Sources visible.

### Tenant Isolation

User:

```text
Що робить Laboratory?
```

Expected:

- Game detected as `blue_prince`.
- Search uses only `game_id=blue_prince`.
- No BG3 chunks in sources.

### MCP Tool Call

User:

```text
Кинь d20 для persuasion check.
```

Expected:

- Game detected as `bg3`.
- Intent detected as `dice_roll`.
- MCP tool `roll_dice("1d20")` called.
- Answer includes roll result.

### Follow-Up Question

User:

```text
Яка шкода від Fireball?
```

Then:

```text
А які предмети підсилюють fire spells?
```

Expected:

- Session context remembers BG3 and fire magic topic.
- Retrieval focuses on relevant BG3 items.
- Answer is in Ukrainian.

## Risks And Mitigations

### Scope Is Too Wide

Mitigation: build vertical slice first and keep custom router, reranker, and polished UI as stretch goals.

### Data Quality Is Weak

Mitigation: use a small, curated dataset instead of a large noisy scrape.

### MCP Becomes Too Complex

Mitigation: use 2-4 deterministic tools per game backed by local JSON data.

### Cross-Lingual Retrieval Is Weak

Mitigation: start with `BAAI/bge-m3`, then test one fallback model if needed.

### Latency Is High

Mitigation: cache embeddings, keep datasets small, measure p50/p95, and use paid LLM only where it adds value.

## Open Decisions

- Final LLM provider: OpenAI directly or OpenRouter.
- Final observability tool: LangSmith or Phoenix.
- Exact source pages/datasets for BG3 and Blue Prince.
- Whether Streamlit should call FastAPI over HTTP or import a local client wrapper for demo mode.
