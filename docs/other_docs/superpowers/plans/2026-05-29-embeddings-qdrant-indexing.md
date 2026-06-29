# Embeddings Qdrant Indexing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Index processed BG3 chunks into Qdrant with local embeddings and provide a smoke retrieval script.

**Architecture:** Keep indexing independent from FastAPI and LangGraph. Unit tests use fake embedding/store objects; real scripts use Sentence Transformers and Qdrant only when the user runs them locally.

**Tech Stack:** Python, sentence-transformers, Qdrant client, pytest.

---

### Task 1: Vector Document Contract

**Files:**
- Create: `tests/test_vector_indexing.py`
- Create: `src/omnilibrarian/rag/documents.py`

- [ ] Define `ChunkDocument` and a JSONL loader that preserves chunk metadata.

### Task 2: Embedding Provider

**Files:**
- Modify: `src/omnilibrarian/rag/embeddings.py`
- Test: `tests/test_vector_indexing.py`

- [ ] Add a deterministic fake provider for tests.
- [ ] Add `SentenceTransformerEmbeddingProvider` for local runtime.

### Task 3: Qdrant Store

**Files:**
- Modify: `src/omnilibrarian/rag/qdrant_store.py`
- Test: `tests/test_vector_indexing.py`

- [ ] Convert documents to Qdrant points with payload metadata.
- [ ] Implement collection creation, upsert, and filtered search.

### Task 4: Index And Retrieval Scripts

**Files:**
- Create: `scripts/index_chunks.py`
- Create: `scripts/smoke_retrieval.py`

- [ ] Index processed chunks from JSONL.
- [ ] Run query embedding and top-k Qdrant search.
