# Screenshot Submission Checklist

This checklist is for the final course submission when a live demo is not required.
The goal is to show that OmniLibrarian is a working AI Engineering project with RAG, LangGraph, MCP, evals, traces, caching, safety, and multi-game support.

## Before Screenshots

Run the app:

```powershell
python scripts/omni.py dev
```

Run the final Blue Prince pipeline/evals if needed:

```powershell
python scripts/omni.py pipeline blue_prince
```

Keep the browser open at:

```text
http://127.0.0.1:8501
```

## Screenshot Set

### 1. Main UI

Show the Streamlit chat UI with the sidebar settings visible.

Good evidence:
- `OmniLibrarian` title
- selected game
- session id
- debug toggle
- clean chat layout

### 2. BG3 Factual RAG Answer

Query:

```text
Who is Astarion?
```

Good evidence:
- answer about Astarion
- source citations from `bg3.wiki`
- source list visible

### 3. BG3 Comparison Query

Query:

```text
Compare Fireball and Lightning Bolt
```

Good evidence:
- answer compares two entities
- citations for both spells
- demonstrates multi-document retrieval

### 4. Typo / Entity Normalization

Query:

```text
Яка шкода від fireballll?
```

Good evidence:
- answer understands `fireballll` as `Fireball`
- answer in Ukrainian
- citations visible

### 5. Blue Prince Factual RAG Answer

Query:

```text
What are Blueprints in Blue Prince?
```

Good evidence:
- game-specific Blue Prince answer
- wiki source citations
- proves multi-game support

### 6. Blue Prince Room Query

Query:

```text
What is Room 46?
```

Good evidence:
- answer uses Blue Prince context
- source list references Blue Prince wiki pages

### 7. Puzzle Hint / Tool Routing

Query:

```text
Give me a spoiler-light hint for Room 46
```

Good evidence:
- answer is hint-like, not a full spoiler
- trace/debug panel shows tool routing or puzzle-hint behavior

### 8. Trace / Observability Panel

Open the trace/debug panel for one strong query.

Good evidence:
- `prepare_request`
- `safety_guard`
- `retrieve_context`
- `llm_cache`
- `generate_answer`
- source mix or source policy fields if visible

### 9. Retrieval Eval Metrics

Screenshot terminal output or result file for:

```powershell
python scripts/omni.py eval blue_prince retrieval
```

Good evidence:
- `hit_at_1`
- `hit_at_3`
- `hit_at_5`
- `mrr`
- `tenant_isolation`
- category metrics

### 10. Answer / Tool Routing Eval Metrics

Screenshot terminal output or result file for:

```powershell
python scripts/omni.py eval blue_prince answers
python scripts/omni.py eval blue_prince tools
```

Good evidence:
- answer grounding metrics
- citation/source metrics
- tool routing accuracy
- latency metrics

## Optional Extra Screenshots

Use these if one of the main screenshots looks weak.

### Redis Cache Evidence

Ask the same question twice and show trace/debug where cache status changes to hit.

### Rate Limit / Safety Evidence

Use a harmless blocked/suspicious prompt and show that the safety guard appears in trace.

### Architecture Evidence

Screenshot the project structure or architecture diagram from documentation.

Recommended files:

- `docs/FINAL_SUBMISSION.md`
- `docs/MCP_ARCHITECTURE.md`
- `docs/other_docs/PROJECT_STRUCTURE.md`

## Suggested Submission Order

1. Main UI
2. BG3 factual answer
3. BG3 comparison answer
4. typo normalization / Ukrainian answer
5. Blue Prince factual answer
6. Blue Prince room answer
7. puzzle hint/tool behavior
8. trace/debug evidence
9. retrieval eval metrics
10. answer/tool eval metrics
