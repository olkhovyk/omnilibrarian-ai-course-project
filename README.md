# OmniLibrarian

OmniLibrarian is a course project for a multi-tenant AI gateway with RAG, LangGraph, MCP tools, evals, and traces for game knowledge bases.

The project is intentionally architecture-first:

- FastAPI gateway.
- Qdrant vector store with tenant isolation by `game_id`.
- Local multilingual embeddings.
- OpenAI/OpenRouter LLM provider.
- LangGraph workflow.
- MCP server per game.
- Streamlit demo UI.

## Current Status

Implemented:

- BG3 ingestion with raw cache, normalization, chunking, and entity registry.
- Local embeddings with Qdrant vector search.
- Hybrid retrieval with BM25 + vectors + reranking.
- Source-aware retrieval policy for stable wiki facts plus curated Reddit hints.
- LangGraph chat workflow.
- OpenAI/OpenRouter answer generation with citations.
- Redis response cache and rate limiting.
- In-memory session context for short follow-up questions.
- Retrieval and tool-routing eval golden sets.
- Streamlit chat UI.
- BG3 MCP-facing tools and MCP server entrypoint.
- Declarative tool routing for BG3 spell comparison and companion listing.

## Quick Verification

```powershell
python -m pytest tests/test_health_api.py tests/test_tenant_registry.py -v
python -m compileall apps src scripts mcp_servers tests
```

## Local Dev App

Install runtime dependencies if needed:

```powershell
python -m pip install -e .
```

## High-Level CLI

Most day-to-day commands are wrapped by `scripts/omni.py`. Defaults live in
`configs/pipelines.yaml`, so the long paths and model settings are kept in one
place instead of being repeated in every terminal command.

Preview any command without running it:

```powershell
python scripts/omni.py --dry-run pipeline blue_prince
```

Common commands:

```powershell
python scripts/omni.py dev
python scripts/omni.py ingest blue_prince wiki
python scripts/omni.py ingest blue_prince reddit
python scripts/omni.py entities blue_prince
python scripts/omni.py index blue_prince
python scripts/omni.py eval blue_prince retrieval
python scripts/omni.py eval blue_prince answers
```

The lower-level scripts still exist for debugging specific pipeline stages.

Run FastAPI, Streamlit, the BG3 MCP server, and the Blue Prince MCP server together:

```powershell
python scripts/omni.py dev
```

Then open:

```text
http://127.0.0.1:8501
```

The UI game selector is loaded from `configs/tenants.yaml`, so `bg3`,
`blue_prince`, and `Auto detect` are shown from the same tenant registry used by
the API. In `Auto detect`, the API infers the game from the user prompt and adds
that decision to the trace.

If you want to temporarily run only FastAPI + Streamlit:

```powershell
python scripts/run_dev.py --no-mcp
```

To run only one MCP server for debugging, use the backward-compatible single-game mode:

```powershell
python scripts/run_dev.py --mcp-game-id blue_prince --mcp-port 8766
```

By default, `run_dev.py` starts MCP servers over streamable HTTP at:

```text
BG3:         http://127.0.0.1:8765/mcp
Blue Prince: http://127.0.0.1:8766/mcp
```

The API reads this through:

```env
MCP_ENABLED=true
BG3_MCP_URL=http://127.0.0.1:8765/mcp
BLUE_PRINCE_MCP_URL=http://127.0.0.1:8766/mcp
```

For a tool-routed request such as `Compare Fireball and Lightning Bolt`, the trace should include `transport: mcp_client`.

The API warms the embedding/retrieval path on startup when
`WARMUP_ON_STARTUP=true` is set in `.env`. This makes startup slower, but avoids
the first real chat request paying the model/CUDA initialization cost.

For LLM response caching, start Redis before the app:

```powershell
docker compose up -d redis
```

Then keep these values in `.env`:

```env
REDIS_URL=redis://localhost:6379/0
LLM_CACHE_ENABLED=true
LLM_CACHE_TTL_SECONDS=86400
```

The same Redis instance is used for chat rate limiting:

```env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=10
RATE_LIMIT_REQUESTS_PER_DAY=100
```

When the limit is exceeded, `/v1/chat` returns `429 Too Many Requests` with a
`Retry-After` header.

Chat sessions keep a small in-memory turn history by `session_id`. This is used
only to enrich retrieval for clear follow-up questions such as `What about its
damage?`; new standalone questions continue to retrieve on their own text.

Clear cached LLM responses safely:

```powershell
python scripts/clear_cache.py
```

The default mode is dry-run. To delete matched OmniLibrarian LLM cache keys:

```powershell
python scripts/clear_cache.py --apply
```

## BG3 Wiki Fetch Cache

Fetch one curated BG3 wiki page and write raw JSON plus SQLite cache metadata:

```powershell
python scripts/ingest.py --game-id bg3 --source bg3_wiki --limit 1
```

Run it a second time to verify cache reuse:

```powershell
python scripts/ingest.py --game-id bg3 --source bg3_wiki --limit 1
```

Expected second-run status:

```text
cached: bg3_wiki:Fireball -> data\raw\bg3\bg3_wiki\bg3_wiki_Fireball.json
```

Force a refresh:

```powershell
python scripts/ingest.py --game-id bg3 --source bg3_wiki --limit 1 --force-refresh
```

## Expanded BG3 Knowledge Ingestion

The curated seed corpus is intentionally small. For a broader BG3 knowledge base,
use MediaWiki category discovery:

```powershell
python scripts/ingest.py --game-id bg3 --source bg3_wiki --manifest-mode category --category-limit 100 --max-documents 800 --process --processed-path data/processed/bg3/bg3_wiki_expanded_chunks.jsonl
```

This discovers pages through `https://bg3.wiki/w/api.php`, stores raw page JSON in
`data/raw`, reuses the SQLite ingestion cache, then normalizes and chunks the
fetched pages. Without explicit `--category` arguments, the discovery profile
covers the main knowledge areas from the BG3 wiki home page: spells, classes,
races, origins, backgrounds, feats, abilities, skills, characters, companions,
NPCs, creatures, quests, locations, items, equipment, weapons, consumables, and
core mechanics. Increase `--category-limit` and `--max-documents` gradually after
retrieval quality looks healthy.

After processing, rebuild the entity registry and vector index against the
expanded chunks before testing the app.

```powershell
python scripts/build_entities.py --input data/processed/bg3/bg3_wiki_expanded_chunks.jsonl --output data/processed/bg3/bg3_wiki_expanded_entities.json --game-id bg3
```

```powershell
python scripts/index_chunks.py --input data/processed/bg3/bg3_wiki_expanded_chunks.jsonl --game-id bg3 --device cuda
```

Then point the app to the expanded entity registry:

```env
ENTITY_REGISTRY_PATH=data/processed/bg3/bg3_wiki_expanded_entities.json
BM25_CHUNKS_PATH=data/processed/bg3/bg3_wiki_expanded_chunks.jsonl
BM25_EXTRA_CHUNKS_PATHS=
```

## Blue Prince Wiki Ingestion

Blue Prince uses `wiki.gg` as the primary factual source. To fetch all public
article pages discoverable through the MediaWiki all-pages API and process them
into chunks:

```powershell
python scripts/run_blue_prince_pipeline.py --dry-run
```

After checking the planned commands, run the full loop:

```powershell
python scripts/run_blue_prince_pipeline.py
```

The Blue Prince wiki crawl is throttled and retries `429 Too Many Requests`.
If the site still stops a large run, rerun the same command; fetched pages are
reused from the raw cache.

For lower-level debugging, the individual ingestion command is:

```powershell
python scripts/ingest.py --game-id blue_prince --source blue_prince_wiki --manifest-mode all --process --processed-path data/processed/blue_prince/blue_prince_wiki_chunks.jsonl
```

For a small smoke run before fetching everything:

```powershell
python scripts/ingest.py --game-id blue_prince --source blue_prince_wiki --manifest-mode seed --limit 5 --process --processed-path data/processed/blue_prince/blue_prince_wiki_chunks.jsonl
```

After processing, build entities and index Blue Prince chunks with the same
shared pipeline:

```powershell
python scripts/build_entities.py --input data/processed/blue_prince/blue_prince_wiki_chunks.jsonl --output data/processed/blue_prince/blue_prince_wiki_entities.json --game-id blue_prince
```

```powershell
python scripts/index_chunks.py --input data/processed/blue_prince/blue_prince_wiki_chunks.jsonl --game-id blue_prince --device cuda
```

Reddit is intentionally not a full subreddit crawl. The first pass is a curated
manifest of high-value posts, such as the puzzle hints megathread and patch/news
posts, so community content does not drown out wiki facts.

Fetch curated Blue Prince Reddit posts into a separate chunks file:

```powershell
python scripts/ingest.py --game-id blue_prince --source blue_prince_reddit --process --processed-path data/processed/blue_prince/blue_prince_reddit_chunks.jsonl
```

Append Reddit chunks to the existing Blue Prince Qdrant index without deleting
the wiki vectors:

```powershell
python scripts/omni.py index blue_prince reddit
```

The indexer is source-scoped by default. Re-indexing `blue_prince reddit`
deletes and rebuilds only vectors where `game_id=blue_prince` and
`source_id=blue_prince_reddit`; it does not touch wiki vectors. The lower-level
equivalent is:

```powershell
python scripts/index_chunks.py --input data/processed/blue_prince/blue_prince_reddit_chunks.jsonl --game-id blue_prince --source-id blue_prince_reddit --mode rebuild-source --device cuda
```

For local chat retrieval, include Reddit as an extra BM25 source while keeping
the wiki as the primary factual source:

```env
BM25_CHUNKS_PATH=data/processed/blue_prince/blue_prince_wiki_chunks.jsonl
BM25_EXTRA_CHUNKS_PATHS=data/processed/blue_prince/blue_prince_reddit_chunks.jsonl
```

The source policy prefers wiki results for factual questions and can promote
Reddit results for hint/community-style questions.

Chat traces include `source_mix`, per-chunk `source_id`, and
`source_policy_reasons`, so the demo can show why a wiki or Reddit result was
used.

## Local Evals

Run retrieval quality eval after indexing Qdrant. It measures `hit_at_1`,
`hit_at_5`, expected term coverage, tenant isolation, latency, and per-category
quality:

```powershell
python scripts/eval_retrieval.py --entities-path data/processed/bg3/bg3_wiki_expanded_entities.json --bm25-chunks-path data/processed/bg3/bg3_wiki_expanded_chunks.jsonl --device cuda --output data/evals/bg3_retrieval_results.json
```

Run the same retrieval eval for Blue Prince after indexing its wiki chunks:

```powershell
python scripts/omni.py eval blue_prince retrieval
```

The Blue Prince retrieval golden set includes community hint cases that expect
`blue_prince_reddit` in the top results. The report includes `source_hit_at_5`
for these source-aware checks.

Run tool-routing eval without Qdrant or LLM calls. It checks whether plain
questions stay in direct RAG and structured requests select the expected MCP
tool:

```powershell
python scripts/eval_tool_routing.py --output data/evals/bg3_tool_routing_results.json
```

After rebuilding the expanded entity registry, you can run the same check
against the larger corpus:

```powershell
python scripts/eval_tool_routing.py --entities-path data/processed/bg3/bg3_wiki_expanded_entities.json --output data/evals/bg3_tool_routing_results.json
```

Blue Prince has a separate tool-routing golden set for puzzle/hint routing:

```powershell
python scripts/eval_tool_routing.py --golden data/evals/blue_prince_tool_routing_golden.jsonl --entities-path data/processed/blue_prince/blue_prince_wiki_entities.json --output data/evals/blue_prince_tool_routing_results.json
```

Run answer-level eval after retrieval quality is stable. This uses the real LLM
once per case, then checks sources, inline citations, expected source titles,
answer terms, and insufficient-context false positives. Expected answer terms
can include multilingual alternatives such as `["puzzle", "головолом"]`:

```powershell
python scripts/omni.py eval blue_prince answers
```

The eval files are game-scoped through `game_id`. To add another game, create
that game's chunks, entities, vector index, and golden JSONL files, then reuse
the same eval runners with different paths.

## Key Docs

- `docs/README.md`
- `docs/FINAL_SUBMISSION.md`
- `docs/SCREENSHOT_SUBMISSION_CHECKLIST.md`
- `docs/BLUE_PRINCE_EVAL_REPORT.md`
- `docs/MCP_ARCHITECTURE.md`
- `docs/other_docs/PROJECT_STRUCTURE.md`
- `docs/other_docs/DATA_SOURCES.md`
- `docs/other_docs/BLUE_PRINCE_SOURCES.md`
- `docs/other_docs/COURSE_PROJECT_PROPOSAL.md`
