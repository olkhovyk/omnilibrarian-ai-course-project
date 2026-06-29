# Project Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable scaffold for OmniLibrarian with a FastAPI health surface, tenant config, shared package, scripts, and smoke tests.

**Architecture:** Keep entry points thin and put reusable logic under `src/omnilibrarian`. The first scaffold proves that configuration, tenant registry, and API wiring work before adding RAG, LangGraph, Qdrant, or MCP behavior.

**Tech Stack:** Python, FastAPI, Pydantic, pytest, Docker Compose, Streamlit placeholder.

---

### Task 1: Scaffold Tests

**Files:**
- Create: `tests/test_health_api.py`
- Create: `tests/test_tenant_registry.py`

- [ ] **Step 1: Write failing tests for API health**

```python
from fastapi.testclient import TestClient

from apps.api.main import create_app


def test_health_endpoint_returns_ok():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_endpoint_reports_tenant_config():
    client = TestClient(create_app())

    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["tenants"] == ["bg3", "blue_prince"]
```

- [ ] **Step 2: Write failing tests for tenant registry**

```python
from omnilibrarian.tenants.registry import load_tenant_registry


def test_registry_loads_default_tenants():
    registry = load_tenant_registry("configs/tenants.yaml")

    assert registry.game_ids() == ["bg3", "blue_prince"]
    assert registry.get("bg3").display_name == "Baldur's Gate 3"
    assert registry.get("blue_prince").display_name == "Blue Prince"
```

- [ ] **Step 3: Run tests and confirm they fail because modules do not exist**

Run: `python -m pytest tests/test_health_api.py tests/test_tenant_registry.py -v`

Expected: fail with import errors for missing scaffold modules.

### Task 2: Minimal Project Files

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `configs/tenants.yaml`
- Create package marker files under `apps/`, `src/`, and tests target directories.

- [ ] **Step 1: Add packaging and dependency metadata**

Create `pyproject.toml` with FastAPI, Pydantic, pytest, Qdrant, sentence-transformers, LangGraph, MCP, and Streamlit dependencies.

- [ ] **Step 2: Add environment example**

Create `.env.example` with API, provider, Qdrant, embedding, and observability settings.

- [ ] **Step 3: Add Docker Compose**

Create `docker-compose.yml` with Qdrant as the first required service and reserved profiles for API/Streamlit later.

- [ ] **Step 4: Add tenant config**

Create `configs/tenants.yaml` containing `bg3` and `blue_prince`.

### Task 3: Tenant Registry

**Files:**
- Create: `src/omnilibrarian/tenants/models.py`
- Create: `src/omnilibrarian/tenants/registry.py`

- [ ] **Step 1: Implement tenant model**

Create a `TenantConfig` dataclass with `game_id`, `display_name`, `description`, and `mcp_server`.

- [ ] **Step 2: Implement registry loader**

Load `configs/tenants.yaml` with Python's standard-library TOML alternative unavailable, so use a small safe YAML parser if PyYAML is installed by dependency. Keep the public API as `load_tenant_registry(path)`.

- [ ] **Step 3: Run tenant registry test**

Run: `python -m pytest tests/test_tenant_registry.py -v`

Expected: pass.

### Task 4: FastAPI Health Surface

**Files:**
- Create: `apps/api/main.py`
- Create: `apps/api/routes/health.py`
- Create: `apps/api/routes/chat.py`
- Create: `apps/api/schemas/chat.py`

- [ ] **Step 1: Implement app factory**

Create `create_app()` in `apps/api/main.py` and include health and chat routers.

- [ ] **Step 2: Implement health routes**

`GET /health` returns `{"status": "ok"}`.

`GET /ready` loads tenant config and returns `{"status": "ready", "checks": {"tenants": ["bg3", "blue_prince"]}}`.

- [ ] **Step 3: Implement chat placeholder**

`POST /v1/chat` returns HTTP 501 with a clear message that the LangGraph chat workflow is not implemented yet.

- [ ] **Step 4: Run API tests**

Run: `python -m pytest tests/test_health_api.py -v`

Expected: pass.

### Task 5: Operational Placeholders

**Files:**
- Create: `scripts/ingest.py`
- Create: `scripts/eval.py`
- Create: `scripts/smoke_chat.py`
- Create: `apps/streamlit_app/app.py`

- [ ] **Step 1: Add explicit placeholders**

Each operational file should be runnable and print a clear message describing what will be implemented in the next milestone.

- [ ] **Step 2: Compile project**

Run: `python -m compileall apps src scripts tests`

Expected: all files compile.

### Task 6: Verification

**Files:**
- All scaffold files.

- [ ] **Step 1: Run focused tests**

Run: `python -m pytest tests/test_health_api.py tests/test_tenant_registry.py -v`

Expected: pass.

- [ ] **Step 2: Run syntax verification**

Run: `python -m compileall apps src scripts tests`

Expected: pass.
