# LangGraph V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the existing RAG chat chain in a minimal LangGraph workflow without changing the public `/v1/chat` API or Streamlit UI.

**Architecture:** Keep `Retriever` and `AnswerGenerator` as separate service contracts. LangGraph coordinates request preparation, retrieval, answer generation, and response formatting through `AgentState`.

**Tech Stack:** Python, LangGraph, pytest, existing FastAPI and RAG modules.

---

## Flow

```text
START
  -> prepare_request
  -> retrieve_context
  -> generate_answer
  -> END
```

## Files

- Modify: `src/omnilibrarian/graph/state.py`
- Modify: `src/omnilibrarian/graph/workflow.py`
- Modify: `apps/api/services/chat_service.py`
- Create: `tests/test_langgraph_workflow.py`

## Notes

- Do not add MCP yet.
- Do not change the API response schema.
- Keep graph construction testable with fake retriever and fake answer generator.
- Preserve existing trace fields so the UI debug panel still works.
