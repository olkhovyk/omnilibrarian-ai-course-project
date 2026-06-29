# Retrieval Reranking Design

## Context

OmniLibrarian currently uses dense vector search against Qdrant. This works for
the first BG3 vertical slice, but pure vector retrieval can return semantically
nearby chunks that are not the best final context.

Example:

```text
Query: Fireball damage
```

Good results:
- `Fireball`
- `Scroll of Fireball`

Less ideal results:
- `Lightning Bolt`
- `Eldritch Blast`
- `Initiative`, when it only mentions Fireball as an example

The next step is an explainable reranking layer that improves result order
without introducing a heavier ML reranker yet.

## Goals

- Keep Qdrant as the first-stage retriever.
- Retrieve a wider candidate set than the final answer needs.
- Apply transparent, testable reranking rules in Python.
- Improve exact entity queries such as `Fireball damage`.
- Avoid breaking comparative queries such as:

```text
Порівняй мені fireball з молнією що завдає більше шкоди
```

- Expose rerank score and reasons in smoke output for debugging and coursework
  explanation.

## Non-goals

- Do not add a cross-encoder reranker in this iteration.
- Do not change ingestion, chunking, or the Qdrant payload schema.
- Do not implement full multilingual query rewriting yet.
- Do not hard-filter candidates by title or content type.

## Architecture

The retrieval flow becomes:

```text
User query
  -> embed query
  -> Qdrant top N candidates
  -> soft reranking
  -> optional comparative diversity pass
  -> final top K chunks
```

Qdrant remains responsible for high-recall candidate retrieval. The Python
reranker is responsible for precision and explainability.

## Components

### Retriever

`Retriever.search()` should accept:
- `limit`: final number of chunks to return.
- `candidate_limit`: number of first-stage Qdrant candidates to fetch.

If `candidate_limit` is not provided, it should default to a safe multiple of
`limit`, such as `max(limit * 4, 20)`.

### Reranker

Add a small module such as:

```text
src/omnilibrarian/rag/reranking.py
```

It should expose a function or class that:
- accepts the query and candidate result dictionaries;
- returns candidates sorted by `rerank_score`;
- adds `rerank_score`;
- adds `rerank_reasons`.

### Smoke retrieval script

`scripts/smoke_retrieval.py` should show:

```text
score=<vector_score> rerank=<rerank_score>
reasons=<comma-separated reasons>
```

This is useful for debugging and for demonstrating retrieval orchestration in
the coursework.

## Scoring Rules

Reranking must be soft and additive. It must not remove candidates just because
their title does not match the query.

Suggested v1 score:

```text
rerank_score =
  vector_score
  + title_exact_match_bonus
  + title_token_match_bonus
  + text_exact_term_bonus
```

Rules:
- If a normalized candidate title appears in the normalized query, add a strong
  title exact match bonus.
- If individual title tokens appear in the query, add a smaller title token
  match bonus.
- If important query tokens appear in chunk text, add a small text term bonus.
- Do not apply large penalties in v1.
- Keep all bonus values modest so vector similarity still matters.

This should improve `Fireball damage` while still allowing related chunks to
surface when they are useful.

## Comparative Query Handling

Comparative queries need more than one entity. The reranker must not collapse
the final results into several chunks from a single title.

Detect comparative intent with simple multilingual keyword heuristics:

```text
compare, comparison, versus, vs, difference, better
порівняй, порівняти, порівняння, проти, різниця, краще
```

When comparative intent is detected:
- apply the same soft scoring;
- then apply a diversity pass over titles;
- prefer returning chunks from multiple titles when scores are close enough.

The diversity pass should not force bad candidates into the final result. It
should only prevent one title from dominating the entire top K when other
reasonably scored titles are available.

## Multilingual Notes

The BG3 source text is English, but users may ask in Ukrainian. Dense embeddings
can partially bridge this, but exact keyword reranking cannot understand that
`молнія` probably refers to `Lightning Bolt`.

This iteration should not solve full multilingual query rewriting. Instead, it
should avoid making multilingual comparative queries worse.

Future LangGraph query planning can rewrite:

```text
Порівняй мені fireball з молнією що завдає більше шкоди
```

into:

```text
Compare Fireball and Lightning Bolt damage in Baldur's Gate 3
```

That rewrite can happen before retrieval.

## Testing

Add focused unit tests for:

- Exact title match boosts `Fireball` above unrelated spell chunks.
- `Scroll of Fireball` receives a partial title/token boost.
- Candidates without title matches are not removed.
- Comparative query detection works for English and Ukrainian terms.
- Comparative diversity keeps multiple titles in the final results when scores
  are close.
- Smoke formatting includes `rerank_score` and `rerank_reasons`.

## Success Criteria

For:

```text
Fireball damage
```

expected top results should prioritize:
- `Fireball`
- `Scroll of Fireball`

and move generic damage spells lower.

For:

```text
Порівняй мені fireball з молнією що завдає більше шкоди
```

the final context should allow at least two relevant titles to appear if Qdrant
retrieved them, for example:
- `Fireball`
- `Lightning Bolt`

The system should remain explainable through printed rerank scores and reasons.
