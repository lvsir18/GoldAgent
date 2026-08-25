# Phase 14 Legacy Removal Decision

## Decision

The Phase 14 deletion gate passed on 2026-08-21. GoldAgent now has one runtime
architecture: Next.js 15 → FastAPI `/api/v1` → LangGraph/services/providers →
SQLAlchemy persistence. The 1.x Web app, keyword rule router, and JSON writers
have been removed.

Historical JSON files under `data/chat_sessions/` and `data/chat_profiles.json`
are retained as read-only migration inputs. They are not read or written by the
application runtime.

## Verified Gates

| Gate | Result |
|---|---|
| Python backend/API/agent/RAG tests | 16 passed |
| Node runtime | 22.23.2 |
| TypeScript | passed |
| Vitest | 2 passed |
| Next.js production build | passed; 15 static pages generated |
| Playwright primary workbench flow | passed in Chrome |
| Live production smoke | `/health`, `/ready`, Settings identity and Chat navigation passed |
| Legacy JSON migration | 26 sessions and 120 messages imported; importer is idempotent |

## Removed Runtime

- `run_web.py`, `web_app.py`, and `web/`
- `src/chat_service.py` and `src/agent_brain.py`
- legacy-only `src/rag_engine.py`, `src/tavily_search.py`, and `src/visualizer.py`
- JSON session/profile configuration and all runtime JSON writers

`main.py` is now a thin GoldAgent API launcher. The canonical entry point is
still `python run_backend.py`; the Web workbench lives in `frontend/`.

## Rollback and Data Safety

No historical JSON data was deleted. To repeat an import, run
`python scripts/migrate_legacy_json.py`; existing session IDs are skipped. The
old source implementation can only be recovered from repository history and is
not an available production fallback.
