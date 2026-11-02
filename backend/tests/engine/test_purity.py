"""Architecture guards: the engine imports only the standard library, and contains no pattern
that silently turns missing data into zero."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parents[2] / "app" / "engine"
FILES = sorted(ENGINE.glob("*.py"))

ALLOWED_STDLIB = {
    "__future__",
    "calendar",
    "collections",
    "dataclasses",
    "datetime",
    "enum",
    "hashlib",
    "itertools",
    "json",
    "math",
    "re",
    "statistics",
    "typing",
}


def test_engine_files_found() -> None:
    assert len(FILES) >= 15


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_engine_imports_only_stdlib_and_itself(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in ALLOWED_STDLIB, f"{path.name}: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:  # relative import inside the engine
                continue
            assert (node.module or "").split(".")[0] in ALLOWED_STDLIB, (
                f"{path.name}: {node.module}"
            )


FORBIDDEN = [
    (re.compile(r"fillna\s*\("), "pandas fillna"),
    (re.compile(r"nan_to_num"), "numpy nan_to_num"),
    (re.compile(r"\bor\s+0(\.0)?\b"), "`x or 0` turns None into zero"),
    (re.compile(r"if\s+\w+\s+is\s+None\s+else\s+0"), "None → 0 conditional"),
    (re.compile(r"\brandom\b|\btime\.time\b|datetime\.now|date\.today"), "non-determinism"),
]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_no_silent_zero_or_nondeterminism(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for pattern, why in FORBIDDEN:
        assert not pattern.search(text), f"{path.name}: {why}"
