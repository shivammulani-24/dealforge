"""B3: sensitivity of a frozen run (plan §4.3). The service only loads and checks; every number
comes from ``engine.sensitivity.frozen_run_grid``, so ENGINE_VERSION governs the semantics."""

from __future__ import annotations

import json
from typing import Any

from app.db.models import ValuationRun
from app.engine.hashing import fingerprint, to_plain
from app.engine.sensitivity import (
    AxisSpec,
    BaseMismatchError,
    DcfOutput,
    FrozenBase,
    frozen_run_grid,
)
from app.engine.version import ENGINE_VERSION

from .errors import ServiceError
from .valuations import context_block, rebuild_inputs


class EngineVersionMismatch(ServiceError):
    status = 409
    code = "ENGINE_VERSION_MISMATCH"


class RunInputsCorrupt(ServiceError):
    status = 409
    code = "RUN_INPUTS_CORRUPT"


class BaseMismatch(ServiceError):
    status = 500
    code = "BASE_MISMATCH"


def run_sensitivity(
    run: ValuationRun, row: AxisSpec, col: AxisSpec, output: DcfOutput
) -> dict[str, Any]:
    # Step 2 (D4-05, R1): never compute on a different engine than the run was frozen with.
    if run.engine_version != ENGINE_VERSION:
        raise EngineVersionMismatch(
            f"Run {run.id} was frozen with engine {run.engine_version}; the current engine is "
            f"{ENGINE_VERSION}. Its stored results remain available and verifiable; re-freeze "
            "the scenario to run a sensitivity on the current engine.",
            detail={
                "run_engine_version": run.engine_version,
                "current_engine_version": ENGINE_VERSION,
            },
        )
    # Steps 3–4: frozen inputs only, and they must still hash to the stored fingerprint.
    inputs = rebuild_inputs(run)
    if fingerprint(inputs) != run.input_hash:
        raise RunInputsCorrupt(
            f"Run {run.id}'s frozen inputs no longer match their fingerprint.",
            detail={"input_hash": run.input_hash},
        )
    stored = json.loads(run.result_json)
    base = FrozenBase(
        wacc=stored["wacc"],
        enterprise_value=stored["valuation"]["enterprise_value"],
        equity_value=stored["per_share"]["equity_value_to_common"],
        value_per_share=stored["per_share"]["value_per_share"],
    )
    try:
        grid = frozen_run_grid(inputs, base, row, col, output)  # steps 5–6
    except BaseMismatchError as exc:  # pragma: no cover - impossible after steps 2 and 4
        raise BaseMismatch(str(exc)) from exc
    return {
        "run_id": run.id,
        "input_hash": run.input_hash,
        "engine_version": run.engine_version,
        "basis": "derived",
        "context": context_block(run.scenario),
        **to_plain(grid),
    }
