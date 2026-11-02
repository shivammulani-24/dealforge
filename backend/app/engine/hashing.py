"""Canonical serialisation and fingerprints for reproducibility.

``canonical_json`` turns any engine dataclass tree into a stable JSON string: keys sorted,
no whitespace, enums by value, dates in ISO format and floats via ``repr`` (shortest string
that round-trips exactly). Identical inputs therefore always produce an identical
``input_hash``, and a stored run can be re-executed and compared byte for byte.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from datetime import date
from enum import Enum
from typing import Any


def to_plain(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_plain(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(to_plain(k)): to_plain(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [to_plain(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        raise ValueError("non-finite float cannot be serialised canonically")
    return obj


def canonical_json(obj: Any) -> str:
    return json.dumps(to_plain(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()
