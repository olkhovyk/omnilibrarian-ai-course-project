# Blue Prince Source Plan

Blue Prince will use two sources:

- `blue_prince_wiki`: `https://blueprince.wiki.gg/`
- `blue_prince_reddit`: `https://www.reddit.com/r/BluePrince/`

## Why Two Sources

The wiki is better for stable facts: rooms, mechanics, items, puzzle pages,
progression concepts, and lore.

Reddit is better for community hints, lived playthrough questions, unclear edge
cases, and practical strategies. It should be lower-authority unless the user
explicitly asks for community advice or hints.

## Ingestion Order

1. Build `blue_prince_wiki` first.
2. Create chunks and entities for rooms, mechanics, items, puzzles, and lore.
3. Index those chunks with `game_id=blue_prince`.
4. Add retrieval eval cases for Blue Prince.
5. Add curated Reddit post ingestion after the wiki path is stable.
6. Use source-aware retrieval so Reddit helps hint questions without outranking
   wiki facts for direct factual questions.

## Wiki Command

Recommended full loop after Qdrant is running:

```powershell
python scripts/run_blue_prince_pipeline.py
```

The full wiki crawl uses request throttling and retries because `wiki.gg` can
return `429 Too Many Requests` during large runs. If a run stops halfway, rerun
the same command: already fetched pages are reused from `data/raw` and the
SQLite ingestion cache.

Preview the exact commands without fetching, indexing, or evaluating:

```powershell
python scripts/run_blue_prince_pipeline.py --dry-run
```

Fast smoke loop with only the seed manifest, no Qdrant indexing, and no retrieval eval:

```powershell
python scripts/run_blue_prince_pipeline.py --manifest-mode seed --max-documents 5 --skip-index --skip-retrieval-eval
```

Fetch all discoverable public wiki article pages and process them into chunks:

```powershell
python scripts/ingest.py --game-id blue_prince --source blue_prince_wiki --manifest-mode all --process --processed-path data/processed/blue_prince/blue_prince_wiki_chunks.jsonl
```

Smoke test with a small seed first:

```powershell
python scripts/ingest.py --game-id blue_prince --source blue_prince_wiki --manifest-mode seed --limit 5 --process --processed-path data/processed/blue_prince/blue_prince_wiki_chunks.jsonl
```

## Initial Wiki Seed

Start with:

- `Rooms`
- `Category:Rooms`
- `Parlor`
- `Billiard Room`
- `Bedroom`
- `Drafting Studio`
- `Vault`
- `Room 46`
- `Blueprints`
- `Room shape`
- `Mechanical Rooms`
- `Entry Rooms`
- `Spread Rooms`
- `Outer Rooms`

These give coverage across room facts, room categories, puzzle mechanics, and
progression-sensitive topics.

## Reddit Rules

Do not crawl the whole subreddit as a first pass.

Use curated permalinks or official API results. The first curated set should
start with:

- puzzle hints megathread:
  `https://www.reddit.com/r/BluePrince/comments/1n0wdv6/megathread_v3_post_and_ask_hints_for_puzzles_here/`
- patch/news posts that clarify current mechanics or accessibility changes.

Store Reddit as:

```text
game_id=blue_prince
source_id=blue_prince_reddit
content_type=community_tip | puzzle_discussion | strategy
```

Reddit chunks should be visibly attributed in answers and down-ranked for direct
factual questions.

## Reddit Command

Fetch the curated Reddit manifest and process it into a separate chunks file:

```powershell
python scripts/ingest.py --game-id blue_prince --source blue_prince_reddit --process --processed-path data/processed/blue_prince/blue_prince_reddit_chunks.jsonl
```

Index Reddit after the wiki index without deleting existing Blue Prince wiki
vectors:

```powershell
python scripts/omni.py index blue_prince reddit
```

The lower-level equivalent rebuilds only the Reddit source slice:

```powershell
python scripts/index_chunks.py --input data/processed/blue_prince/blue_prince_reddit_chunks.jsonl --game-id blue_prince --source-id blue_prince_reddit --mode rebuild-source --device cuda
```

Use both wiki and Reddit in retrieval/evals through the high-level CLI:

```powershell
python scripts/omni.py eval blue_prince retrieval
python scripts/omni.py eval blue_prince answers
```

For the local API, configure:

```env
BM25_CHUNKS_PATH=data/processed/blue_prince/blue_prince_wiki_chunks.jsonl
BM25_EXTRA_CHUNKS_PATHS=data/processed/blue_prince/blue_prince_reddit_chunks.jsonl
```

The retrieval policy keeps wiki as the authority for factual questions and
promotes Reddit for hint/community-style wording such as `hint`, `stuck`, or
spoiler-aware help.

Retrieval reports now include `source_hit_at_5` for source-aware eval cases, and
chat traces include `source_mix` plus source policy reasons. This makes Reddit
usage visible during demos instead of being hidden inside the merged context.

To add a hand-picked thread, pass a permalink explicitly:

```powershell
python scripts/ingest.py --game-id blue_prince --source blue_prince_reddit --reddit-url https://www.reddit.com/r/BluePrince/comments/abc123/example_thread/ --process --processed-path data/processed/blue_prince/blue_prince_reddit_chunks.jsonl
```

## Blue Prince Extension Contract

Adding Blue Prince should reuse the existing shared platform:

- raw cache;
- normalizers;
- paragraph chunking;
- local embeddings;
- Qdrant with `game_id` filtering;
- entity registry;
- eval runners;
- MCP server boundary.

Only the source adapters, normalizer rules, entities, golden eval files, and
game-specific MCP tools should be Blue-Prince-specific.
