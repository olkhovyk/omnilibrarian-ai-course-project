# Entity Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a BG3 entity registry built from processed chunks and use RapidFuzz for typo-tolerant query normalization.

**Architecture:** Processed chunks remain the source for discovered entities. `entities/` owns entity models, extraction, JSON persistence, and fuzzy lookup. `rag/query_rewriting.py` can optionally use an `EntityRegistry` to normalize misspelled entity names before retrieval.

**Tech Stack:** Python, pytest, RapidFuzz, existing chunk JSONL pipeline.

---

## File Structure

- Create: `src/omnilibrarian/entities/models.py`
- Create: `src/omnilibrarian/entities/extract.py`
- Create: `src/omnilibrarian/entities/registry.py`
- Create: `src/omnilibrarian/entities/__init__.py`
- Create: `scripts/build_entities.py`
- Create: `tests/test_entity_registry.py`
- Modify: `src/omnilibrarian/rag/query_rewriting.py`
- Modify: `src/omnilibrarian/rag/retriever.py`
- Modify: `scripts/smoke_retrieval.py`
- Modify: `pyproject.toml`

## Tasks

1. Add RapidFuzz dependency.
2. Add `Entity` model and JSON serialization.
3. Extract unique entities from `ChunkDocument` titles.
4. Add `EntityRegistry.find_fuzzy()` using RapidFuzz.
5. Add `scripts/build_entities.py`.
6. Allow `rewrite_query()` to use an optional entity registry.
7. Allow `Retriever` and smoke script to load an optional entity registry path.
8. Verify tests and compile.
