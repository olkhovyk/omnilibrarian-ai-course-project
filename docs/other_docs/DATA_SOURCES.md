# OmniLibrarian Data Sources

This document defines how OmniLibrarian should collect and normalize source data.

The ingestion pipeline should be source-adapter based. BG3 wiki is the first source, but the architecture should support adding Reddit, Fandom, Steam guides, or other sources later.

## Source Strategy

Use one common ingestion pipeline:

```text
Source adapter
  -> fetch cache check
  -> raw document
  -> normalized document
  -> chunks
  -> embeddings
  -> Qdrant
```

Each source adapter is responsible for fetching raw source content. Everything after that should be shared.

## Fetch Cache

The ingestion pipeline should cache fetched pages before chunking and embedding.

This solves two problems:

- rerunning ingestion does not repeatedly hit source websites;
- the system can decide whether a page needs to be re-read or can be reused from local cache.

Recommended MVP storage:

```text
data/cache/ingestion.sqlite
data/raw/<game_id>/<source_id>/<doc_id>.json
```

SQLite stores fetch metadata and freshness state. Raw JSON files store the actual extracted page data before chunking.

### Cache Metadata

Each fetched source item should have a cache row:

```json
{
  "doc_id": "bg3_wiki:Fireball",
  "game_id": "bg3",
  "source_id": "bg3_wiki",
  "source_url": "https://bg3.wiki/wiki/Fireball",
  "raw_path": "data/raw/bg3/bg3_wiki/bg3_wiki_Fireball.json",
  "content_hash": "sha256:...",
  "etag": "\"abc123\"",
  "last_modified": "Wed, 29 May 2026 09:45:00 GMT",
  "fetched_at": "2026-05-29T09:45:00Z",
  "checked_at": "2026-05-29T09:45:00Z",
  "status_code": 200
}
```

`etag` and `last_modified` may be empty if the source does not provide them.

`content_hash` is always computed from the normalized raw text or raw HTML body. It lets the pipeline detect whether content changed even when the source does not expose good cache headers.

### Refresh Rules

When ingestion sees a page URL:

1. If there is no cache row, fetch the page.
2. If the cache row exists and is fresh enough, reuse the raw JSON file.
3. If the cache row exists but is stale, make a conditional request when possible:
   - send `If-None-Match` when `etag` exists;
   - send `If-Modified-Since` when `last_modified` exists.
4. If the source returns `304 Not Modified`, update `checked_at` and reuse local raw data.
5. If the source returns `200 OK`, extract text again and compute a new `content_hash`.
6. If `content_hash` is unchanged, update cache metadata but skip re-chunking and re-embedding.
7. If `content_hash` changed, write a new raw JSON snapshot and mark the document for chunking and embedding.

For the MVP, use a simple freshness window:

```text
default_ttl_hours = 168
```

That means cached pages are considered fresh for 7 days unless ingestion is run with a force refresh flag.

### Ingestion Modes

The ingestion script should eventually support:

```powershell
python scripts/ingest.py --game-id bg3 --source bg3_wiki
python scripts/ingest.py --game-id bg3 --source bg3_wiki --force-refresh
python scripts/ingest.py --game-id bg3 --source bg3_wiki --limit 5
```

Modes:

- default: reuse fresh cache, refresh stale pages, process changed pages;
- `--force-refresh`: fetch pages even when local cache is fresh;
- `--limit`: useful for smoke tests while building the pipeline.

### Why Raw Cache Comes Before Chunking

Raw cache should happen before chunking and embeddings because those later steps are derived data.

If chunking rules change, we can rebuild chunks from cached raw documents without touching the original website.

If the embedding model changes, we can rebuild vectors from processed chunks without touching the original website.

This gives the pipeline three reusable layers:

```text
source website
  -> raw cache
  -> processed chunks
  -> vector index
```

Each layer can be rebuilt independently.

## Canonical Source Adapter Interface

Target interface:

```python
class SourceAdapter(Protocol):
    source_id: str

    def fetch_manifest(self) -> list[SourceRef]:
        ...

    def fetch_document(self, ref: SourceRef) -> RawDocument:
        ...
```

`fetch_manifest()` returns a list of pages/posts/guides that should be fetched.

`fetch_document()` fetches one item and returns raw text plus metadata.

## Canonical Raw Document

Every adapter should produce the same raw document shape:

```json
{
  "doc_id": "bg3_wiki:Fireball",
  "game_id": "bg3",
  "source_id": "bg3_wiki",
  "source_url": "https://bg3.wiki/wiki/Fireball",
  "title": "Fireball",
  "text_en": "Fireball is a level 3 evocation spell...",
  "content_type": "spell",
  "fetched_at": "2026-05-29T09:45:00Z",
  "license": "CC BY-NC-SA 4.0 or CC BY-SA 4.0 where applicable"
}
```

## Canonical Chunk

Processed chunks should keep source attribution:

```json
{
  "chunk_id": "bg3_wiki:Fireball:0001",
  "game_id": "bg3",
  "source_id": "bg3_wiki",
  "source_url": "https://bg3.wiki/wiki/Fireball",
  "title": "Fireball",
  "content_type": "spell",
  "language": "en",
  "text": "Fireball is a level 3 evocation spell...",
  "token_count": 137
}
```

## BG3 Wiki Source

Primary source:

```text
https://bg3.wiki/
```

Recommended MVP approach:

1. Start with a curated URL manifest for a small number of high-value pages.
2. Fetch normal wiki article pages.
3. Extract the main article text.
4. Remove navigation, sidebars, edit links, boilerplate, and empty sections.
5. Keep `source_url` for every document and chunk.
6. Store raw fetched pages separately from processed chunks.

Initial BG3 content groups:

- spells: Fireball, Magic Missile, Eldritch Blast, Haste
- classes: Wizard, Warlock, Fighter
- items: selected fire/spellcasting items
- mechanics: Dice rolls, Advantage, Spellcasting

Important access rule:

- Do not use blocked API endpoints as the default ingestion method.
- Prefer curated page URLs and normal public article pages for MVP.
- Keep request rate low and cache raw pages locally.

## Reddit Source

Reddit should be an optional source, not the first authority for factual game
data.

Potential value:

- community builds
- strategy discussions
- item recommendations
- practical tips

Recommended approach:

1. Use a small curated list of posts or official API access.
2. Store permalink, subreddit, author when available, and fetched timestamp.
3. Treat Reddit as lower-authority than wiki pages.
4. Mark `source_id` as `reddit`.
5. Use content types such as `community_tip`, `build_discussion`, or `strategy`.

Retrieval should be able to down-rank or label Reddit content separately from wiki content.

## Blue Prince Sources

Primary structured source:

```text
https://blueprince.wiki.gg/
```

Community source:

```text
https://www.reddit.com/r/BluePrince/
```

Blue Prince should use both sources, but they should not be treated equally.

### Blue Prince Wiki

The wiki.gg source should be the first authority for factual game data:

- rooms;
- room types and mechanics;
- items;
- puzzles;
- progression concepts;
- lore pages.

Use source id:

```text
blue_prince_wiki
```

Recommended first pass:

1. Start with a curated seed manifest for high-value pages such as `Rooms`,
   `Category:Rooms`, `Parlor`, `Blueprints`, `Mechanical Rooms`, and `Room 46`.
2. Prefer MediaWiki category/API discovery if `wiki.gg` exposes a usable API in
   local runs.
3. Fall back to public article/category HTML pages if API access is blocked or
   unstable.
4. Keep spoiler metadata from the page where possible.
5. Store raw documents before chunking, exactly like BG3.

### Blue Prince Reddit

Reddit should be used for community hints and practical discussion, not as the
primary factual source.

Use source id:

```text
blue_prince_reddit
```

Recommended first pass:

1. Ingest only curated post permalinks or official API results.
2. Store subreddit, permalink, title, author when available, score/comment
   counts when available, and fetched timestamp.
3. Mark content as `community_tip`, `puzzle_discussion`, or `strategy`.
4. Treat Reddit chunks as lower authority than wiki chunks in reranking.
5. Prefer Reddit only when the user asks for hints, community solutions,
   practical strategies, or ambiguity that the wiki does not cover.

### Blue Prince Source Priority

For direct factual questions:

1. `blue_prince_wiki`
2. deterministic local tool data
3. `blue_prince_reddit`

For community/hint questions:

1. `blue_prince_wiki`
2. `blue_prince_reddit`
3. deterministic local tool data where relevant

## Fandom Or Other Wikis

Fandom or other fan wikis should also be adapter-based.

Recommended approach:

1. Check the site's robots and licensing before ingestion.
2. Prefer official export/API methods only when allowed.
3. Keep source attribution and license metadata.
4. Avoid mixing Fandom content into the BG3 MVP unless we need coverage that `bg3.wiki` does not provide.

## Source Priority

For BG3 MVP:

1. `bg3_wiki`: authoritative project source for curated factual game data.
2. local JSON tool data: deterministic MCP facts.
3. Reddit/Fandom: stretch goal sources after the core architecture works.

## Why This Design Matters

This keeps ingestion extensible without making the first milestone too large.

The retrieval layer should not care whether a chunk came from BG3 wiki, Reddit, or Fandom. It should only rely on stable metadata:

- `game_id`
- `source_id`
- `source_url`
- `title`
- `content_type`
- `language`
- `text`

That means new sources can be added by writing new adapters, while Qdrant filtering, LangGraph retrieval, answer generation, and source display stay the same.
