# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

Stock News API — an AI-powered news aggregation system that scrapes websites/YouTube/RSS feeds, analyzes content with local LLMs (Ollama), extracts stock mentions with per-stock sentiment, and persists results to SQLite. It has a FastAPI backend and a React/TypeScript frontend.

## Commands

### Backend (run from `backend/`)
```bash
# Start dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Initialize database
python -m app.init_db

# Run tests
pytest
pytest backend/path/to/test.py -k "test_name"   # single test

# Install dependencies
pip install -r requirements.txt
playwright install chromium
```

### Frontend (run from `frontend/`)
```bash
npm install
npm run dev          # dev server on :5173
npm run build        # tsc && vite build
npm run lint         # eslint
```

### Docker (full stack)
```bash
docker compose up --build          # backend :8000, frontend :3000, ollama :11434
```

## Architecture

### LangGraph Workflow Pipeline

The core processing pipeline is a **LangGraph state machine** in `backend/app/agents/workflow.py`. A `supervisor_router` function routes between nodes based on the `stage` field in `NewsProcessingState` (defined in `state.py`):

```
scraper → article_link_extractor → article_fetcher → analyzer → ner → finalizer
                                         ↑                              |
                                         └──── (loop for each article) ←┘
```

**Key flow details:**
- The **scraper** fetches raw content. For `rss` source types, it sets `stage = 'link_extraction_complete'` directly, bypassing the LLM link extractor.
- The **article_link_extractor** uses an LLM to detect article links on listing pages. Single-article pages skip to analyzer.
- The **article_fetcher** tries a lightweight HTTP fetch (via `rss_service.fetch_entry_content()`) before falling back to Playwright. It loops through `article_links` by incrementing `current_article_index`.
- The **finalizer** either returns `article_saved_continue` (more articles) or `all_articles_finalized`/`finalized` (done), controlling the loop.
- The workflow runs with `recursion_limit: 200` to support ~20 articles per listing page.

### Layer Organization

- **`agents/`** — LangGraph nodes. Each is an async function taking and returning `NewsProcessingState`. State flows through the entire pipeline as a single TypedDict.
- **`services/`** — Stateful singletons (`web_scraper`, `ollama_service`, `rss_service`, `youtube_service`). The scraping service manages Playwright browser lifecycle, stealth injection, UA rotation, and proxy pool.
- **`models/`** — SQLAlchemy ORM models. `DataSource` has check constraints on `source_type`, `status`, `health_status`, and `last_fetch_status`.
- **`schemas/`** — Pydantic schemas. Keep `Literal` types in schemas in sync with `CheckConstraint` values in models.
- **`scheduler/`** — APScheduler with SQLite jobstore. Jobs call `process_news_article()` from `workflow.py`. Concurrency controlled by a semaphore (`MAX_CONCURRENT_FETCHES`).
- **`api/v1/`** — FastAPI routers. `process.py` triggers the workflow; `sources.py` has full CRUD; `test_scraping.py` provides test endpoints.

### Anti-Bot System (`services/stealth.py`, `user_agents.py`, `human_behavior.py`, `scraping.py`)

The scraping service initializes a Playwright browser context with:
1. Stealth JS injection via `context.add_init_script()` (hides `navigator.webdriver`, mocks plugins/languages)
2. User agent rotation matched to `BROWSER_ENGINE` setting (chromium/firefox/webkit)
3. Human behavior simulation (mouse movements, scrolling) after page load
4. Proxy pool with round-robin rotation
5. On 403: recreates the entire context (new UA + next proxy) before retry

### Content Deduplication

Articles are deduplicated by `content_hash` (MD5 of normalized text), not by URL. This is computed in the scraper/article_fetcher nodes and checked in the finalizer against the database.

### Frontend

React 18 + TypeScript, Vite, TanStack Query for server state, Zustand for client state, Tailwind CSS. The API client in `frontend/src/api/` talks to the backend at `:8000`.

## Key Conventions

- **SQLite check constraints** — When adding a new enum value to `source_type`, `status`, etc., update both the `CheckConstraint` in `models/data_source.py` AND the `Literal` type in `schemas/data_source.py`. SQLite constraint changes require Alembic migration with `batch_alter_table`.
- **Singleton services** — Services are instantiated at module level (`web_scraper = WebScraperService()`). Import from `app.services` (the `__init__.py` re-exports them).
- **NER sentiment** — Each stock mention gets its own sentiment score. The LLM prompt requires per-stock sentiment with context, not document-level sentiment.
- **Config** — All settings flow through `backend/app/config.py` (`pydantic-settings`), loaded from `.env`. Access via `from app.config import settings`.
- **LLM model config** — Models are assignable per workflow step via `utils/llm_config.py` and the `/api/v1/config/llm` endpoint. Vision models are auto-detected and trigger screenshot capture in the scraper.
