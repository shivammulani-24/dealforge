# DealForge

An M&A valuation and deal-analysis platform: historical analysis, five-year forecast, DCF,
comparable companies, sensitivity and scenarios, accretion/dilution, and an analyst-style deal
memo. It is built to be financially correct, transparent and testable.

> **Data:** all sample companies in this project are **synthetic**. No figure in this repository
> is a real company's reported data.

## Status

| Phase | Scope | State |
|---|---|---|
| 1 | Product definition, financial spec, architecture ([docs/phase-1-plan.md](docs/phase-1-plan.md)) | Approved |
| 2 | Financial calculation engine and tests ([docs/engine.md](docs/engine.md)) | Approved |
| 2.5 | Verification and readiness: [independent verification](docs/verification/independent-verification.md), [API contract](docs/api-contract.md), [limitations register](docs/limitations-register.md) | Complete |
| 3 | Data layer and API ([docs/phase-3-design.md](docs/phase-3-design.md)) | Built; awaiting review |
| 4 (F0) | Backend for the frontend: liquidity ratios, frozen-run sensitivity, idempotent freezes, dashboard, runs list, samples, typed OpenAPI ([docs/phase-4-plan.md](docs/phase-4-plan.md)) | Approved |
| 4 (F1) | Frontend foundation: React + TypeScript + Vite, design system, typed client, auth, app shell ([screenshots](docs/screenshots/f1/)) | Built; awaiting visual review |
| 4 (F2+) | Application screens, memo | Not started |

## The engine

`backend/app/engine/` is pure, standard-library Python. It has no database, web framework, pandas
or network dependency, and a test enforces this. Every formula is a small function with a
hand-verified known-answer test.

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest --cov          # tests + coverage
ruff check . && mypy  # lint + strict typing
```

## The API (Phase 3)

```bash
cd backend
DEALFORGE_DATABASE_URL=sqlite:///./dealforge.sqlite3 uvicorn app.main:create_app --factory --port 8000
# interactive API docs: http://127.0.0.1:8000/docs
python scripts/demo_workflow.py http://127.0.0.1:8000   # create → import → validate → DCF → save → verify
```

Migrations run automatically at start-up (`alembic upgrade head`). Authentication uses bearer
tokens from `POST /api/v1/auth/token`.

## The frontend (Phase 4, F1)

React 18 + TypeScript (strict) + Vite, Tailwind CSS, React Router, TanStack Query and a typed
client generated from the committed [`docs/openapi.json`](docs/openapi.json). F1 delivers the
foundation, authentication, the application shell and a design-system page at `/style-guide`;
the application screens start in F2.

```bash
cd frontend
npm ci
npm run dev            # http://127.0.0.1:5173, proxies /api to the backend on :8000
npm run check:api      # generated API types match docs/openapi.json
npm run lint && npm run format:check && npm run typecheck
npm run test:coverage  # unit + component tests (Vitest, Testing Library, MSW)
npm run build          # production build in frontend/dist
PYTHON=python npm run e2e   # Playwright against the real backend, 1440 and 1024 px
```

Production-style serving (same origin, strict CSP): build the frontend, then start the backend
with `DEALFORGE_FRONTEND_DIST=../frontend/dist`. No arithmetic is allowed in UI code: numbers are
formatted for display by `src/lib/format.ts` only (lint-enforced).

- [Engine reference](docs/engine.md): architecture, every function, conventions, test catalogue, limitations
- [Interview guide](docs/interview-guide.md): the six core questions, answered with the engine's own numbers
