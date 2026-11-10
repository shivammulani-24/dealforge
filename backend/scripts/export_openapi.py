"""Write the OpenAPI document to docs/openapi.json, or with --check fail if it is stale.

The frontend generates its TypeScript API types from this committed file (D4-08), so a backend
contract change must update it in the same commit. Run from backend/:
    python scripts/export_openapi.py          # regenerate
    python scripts/export_openapi.py --check  # CI / tests: exit 1 if out of date
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
TARGET = BACKEND.parent / "docs" / "openapi.json"


def render() -> str:
    from app.config import Settings
    from app.main import create_app

    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(Settings(database_url=f"sqlite:///{Path(tmp) / 'openapi.sqlite3'}"))
        spec = app.openapi()
        app.state.db_engine.dispose()
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != text:
            print(f"{TARGET} is out of date: run `python scripts/export_openapi.py`.")
            return 1
        print(f"{TARGET} is up to date.")
        return 0
    TARGET.write_text(text, encoding="utf-8")
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
