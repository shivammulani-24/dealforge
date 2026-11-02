"""The limitations register must keep every limitation the engine docs cite."""

from __future__ import annotations

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[3] / "docs"
ROW = re.compile(r"^\| (LIM-\d{2}) \|(.+)\|$", re.MULTILINE)
STATUSES = {"Open", "Planned", "Accepted", "Resolved"}


def register() -> dict[str, list[str]]:
    text = (DOCS / "limitations-register.md").read_text(encoding="utf-8")
    return {m[1]: [c.strip() for c in m[2].split("|")] for m in ROW.finditer(text)}


def test_every_cited_limitation_is_registered() -> None:
    cited = set(re.findall(r"LIM-\d{2}", (DOCS / "engine.md").read_text(encoding="utf-8")))
    assert cited, "engine.md should cite the register"
    assert cited <= set(register())


def test_register_entries_are_complete() -> None:
    reg = register()
    assert len(reg) >= 16
    ids = sorted(reg)
    assert ids == [f"LIM-{i:02d}" for i in range(1, len(ids) + 1)], "IDs must be contiguous"
    for lim, cells in reg.items():
        limitation, impact, mitigation, status, target = cells
        assert limitation and impact and mitigation and target, lim
        assert status in STATUSES, (lim, status)
