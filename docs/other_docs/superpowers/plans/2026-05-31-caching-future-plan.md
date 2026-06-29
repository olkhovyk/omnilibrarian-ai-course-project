# Caching Future Plan

> **Status:** Future work. Do not implement before the current `/v1/chat` + UI slice is stable.

## Goal

Reduce repeated LLM/API cost and repeated local compute by caching deterministic
parts of the RAG pipeline.

The main motivation is cost control: if the user asks the same effective
question with the same model, prompt version, and retrieved context, the system
should be able to reuse the previous answer instead of calling the LLM again.

## Cache Layers

### 1. LLM Response Cache

Highest priority because it saves paid LLM calls.

Cache:

```text
same normalized question
+ same game_id
+ same model
+ same prompt version
+ same retrieved context
+ same generation parameters
-> same answer payload
```

Suggested MVP storage:

```text
data/cache/llm_cache.sqlite
```

Suggested key payload:

```json
{
  "question": "Яка шкода від fireballll?",
  "game_id": "bg3",
  "retrieval_query": "Яка шкода від Fireball",
  "chunk_ids": ["...", "..."],
  "chunk_text_hashes": ["...", "..."],
  "model": "openai/gpt-4.1-mini",
  "provider": "openrouter",
  "prompt_version": "answer_v1",
  "temperature": 0
}
```

Hash this structured payload with SHA256 and store:

```json
{
  "answer": "...",
  "sources": [...],
  "created_at": "...",
  "cache_key": "..."
}
```

Important: do not cache only by raw user question. Retrieval context and prompt
version must be part of the key.

### 2. Query Embedding Cache

Useful for repeated smoke tests, eval runs, and common queries.

Cache:

```text
embedding_model + retrieval_query -> vector
```

Suggested storage:

```text
data/cache/embedding_cache.sqlite
```

This avoids re-running local embedding model for identical retrieval queries.

### 3. Retrieval Cache

Useful later, but more fragile.

Cache:

```text
game_id + retrieval_query + collection/index version + top_k -> retrieved chunks
```

This requires a stable `index_version` or `corpus_hash`, otherwise stale
retrieval results can survive after reindexing.

### 4. Provider Prompt Cache

Some hosted LLM providers support prompt caching for repeated prompt prefixes.
This is useful later, but not the first MVP priority.

## Recommended Implementation Order

1. Add LLM response cache.
2. Show cache status in trace/debug output:

```text
llm_cache: hit
llm_cache: miss
```

3. Add query embedding cache.
4. Add retrieval cache only after we introduce a corpus/index version.
5. Consider provider-specific prompt caching after prompts stabilize.

## LLM Cache Placement

Best place:

```text
ChatService.answer()
  -> retrieve chunks
  -> build answer prompt / key payload
  -> cache lookup
  -> if hit: return cached answer + sources + trace
  -> if miss: call LLM
  -> save answer + sources
```

Do not hide the cache inside the LLM provider, because the provider does not know
about retrieved chunks, prompt version, source hashes, or game_id.

## Trace Fields

When observability is added, each chat run should include:

```json
{
  "step": "llm_cache",
  "status": "hit",
  "cache_key": "...",
  "provider": "openrouter",
  "model": "openai/gpt-4.1-mini"
}
```

or:

```json
{
  "step": "llm_cache",
  "status": "miss",
  "provider": "openrouter",
  "model": "openai/gpt-4.1-mini"
}
```

## Production Notes

For local MVP:

- SQLite is enough.
- Cache can live in `data/cache`.
- Manual clear is acceptable.

For production:

- Redis or Postgres is better.
- Cache keys should include tenant/game isolation.
- Add TTL for some answer types.
- Keep permanent caches only for stable source corpora.
- Never cache user-private data without considering privacy requirements.

## Current Decision

Do not implement this immediately. First stabilize:

```text
/v1/chat -> UI -> retrieval -> rerank -> LLM answer -> sources
```

Then add LLM response cache before doing heavier eval or repeated demo testing.
