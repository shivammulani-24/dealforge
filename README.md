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
| 4 (F0) | Backend for the frontend: liquidity ratios, frozen-run sensitivity, idempotent freezes, dashboard, runs list, samples, typed OpenAPI ([docs/phase-4-plan.md](docs/phase-4-plan.md)) | Built; awaiting review |
| 4 (F1+) | Frontend, memo | Not started |

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

- [Engine reference](docs/engine.md): architecture, every function, conventions, test catalogue, limitations
- [Interview guide](docs/interview-guide.md): the six core questions, answered with the engine's own numbers
