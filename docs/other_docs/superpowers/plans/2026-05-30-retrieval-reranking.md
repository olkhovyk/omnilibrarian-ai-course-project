# Retrieval Reranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explainable reranking layer that improves BG3 retrieval ordering while preserving comparative-query diversity.

**Architecture:** Qdrant remains the first-stage retriever and returns a wider candidate set. A Python reranker applies soft title/text bonuses, adds `rerank_score` and `rerank_reasons`, and optionally diversifies comparative queries by title before returning the final top K.

**Tech Stack:** Python, pytest, Qdrant client, existing `Retriever`, existing `smoke_retrieval.py`.

---

## File Structure

- Create: `src/omnilibrarian/rag/reranking.py`
  - Owns query normalization, title/text bonus scoring, comparative-intent detection, and title diversity.
- Modify: `src/omnilibrarian/rag/retriever.py`
  - Fetches a larger candidate set and applies the reranker before returning final results.
- Modify: `scripts/smoke_retrieval.py`
  - Displays vector score, rerank score, and rerank reasons.
- Create: `tests/test_reranking.py`
  - Tests reranking behavior without Qdrant.
- Modify: `tests/test_vector_indexing.py`
  - Updates retriever tests for `candidate_limit` behavior.
- Modify: `tests/test_smoke_retrieval.py`
  - Verifies smoke output includes reranking details.

## Task 1: Reranking Rules

**Files:**
- Create: `src/omnilibrarian/rag/reranking.py`
- Test: `tests/test_reranking.py`

- [ ] **Step 1: Write failing tests**

Add tests for:
- exact title matches raising `Fireball`;
- partial title token match raising `Scroll of Fireball`;
- candidates without title matches staying present;
- English and Ukrainian comparative query detection;
- comparative diversity keeping multiple titles.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_reranking.py -q
```

Expected: fails because `omnilibrarian.rag.reranking` does not exist.

- [ ] **Step 3: Implement reranker**

Create:

```python
def rerank_results(query: str, results: list[dict], limit: int) -> list[dict]:
    ...

def is_comparative_query(query: str) -> bool:
    ...
```

Use additive bonuses and add:
- `rerank_score`
- `rerank_reasons`

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
python -m pytest tests/test_reranking.py -q
```

Expected: pass.

## Task 2: Retriever Integration

**Files:**
- Modify: `src/omnilibrarian/rag/retriever.py`
- Modify: `tests/test_vector_indexing.py`

- [ ] **Step 1: Write failing retriever test**

Update fake store tests so `Retriever.search(query, limit=5)` calls the vector
store with `limit=20` by default and returns reranked top 5.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_vector_indexing.py -q
```

Expected: fails because retriever still fetches only `limit`.

- [ ] **Step 3: Implement retriever integration**

Update `Retriever.search()` to accept:

```python
def search(
    self,
    query: str,
    game_id: str,
    limit: int = 5,
    candidate_limit: int | None = None,
) -> list[dict]:
```

Use:

```python
candidate_limit = candidate_limit or max(limit * 4, 20)
```

Then call `rerank_results(query, candidates, limit)`.

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
python -m pytest tests/test_vector_indexing.py tests/test_reranking.py -q
```

Expected: pass.

## Task 3: Smoke Output

**Files:**
- Modify: `scripts/smoke_retrieval.py`
- Modify: `tests/test_smoke_retrieval.py`

- [ ] **Step 1: Write failing smoke output test**

Assert formatted output includes:
- `score=...`
- `rerank=...`
- `reasons=...`
- full chunk text.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_smoke_retrieval.py -q
```

Expected: fails because smoke output does not show rerank fields yet.

- [ ] **Step 3: Implement smoke output**

Update `format_result()` to print vector score and rerank score:

```text
#1 score=0.6394 rerank=0.9394
reasons=title_exact:fireball, text_term:damage
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
python -m pytest tests/test_smoke_retrieval.py -q
```

Expected: pass.

## Task 4: Verification

**Files:**
- No new files.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m pytest tests/test_reranking.py tests/test_vector_indexing.py tests/test_smoke_retrieval.py -q
```

Expected: pass.

- [ ] **Step 2: Run compile check**

Run:

```powershell
python -m compileall src scripts tests
```

Expected: pass.

- [ ] **Step 3: User local smoke**

Ask the user to run:

```powershell
python scripts/smoke_retrieval.py --query "Fireball damage" --game-id bg3 --device cuda
python scripts/smoke_retrieval.py --query "Порівняй мені fireball з молнією що завдає більше шкоди" --game-id bg3 --device cuda
```

Expected: smoke output includes rerank scores and reasons.
