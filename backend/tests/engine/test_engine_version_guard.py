"""Engine version guard (Phase 4 plan §4.13, amendments A1–A3).

Golden outputs are keyed by ENGINE_VERSION. If any DCF or sensitivity output, input fingerprint
or frozen-input reconstruction changes while ENGINE_VERSION stays the same, this fails. If
ENGINE_VERSION changes without golden entries for the new version, this fails too. To change
calculation semantics deliberately, follow the bump checklist in the plan: bump the version, add
a new golden entry (keep old ones) and explain every changed number in docs/engine-changelog.md.
"""

from __future__ import annotations

import hashlib
from datetime import date

from builders import bridge, cap, constant_drivers, dates, dcf_inputs, wacc_assumptions
from test_independent_verification import ka_dcf03_inputs

from app.engine.forecast import ForecastInputs, ForecastYearDrivers
from app.engine.hashing import canonical_json, fingerprint
from app.engine.sensitivity import AxisSpec, DcfOutput, DcfVariable, FrozenBase, frozen_run_grid
from app.engine.shares import ConvertibleInstrument, OptionTranche, RsuGrant
from app.engine.valuation import DcfResult, run_dcf
from app.engine.version import ENGINE_VERSION
from app.engine.wacc import DebtValueBasis
from app.schemas.dcf import DcfInputsIn

GOLDENS: dict[str, dict[str, str]] = {
    "0.1.0": {
        "KA-DCF-02 result": "b99a08ddf51b1c0c960d04830ec387981b16f1c6d1b9968df67d4bb6046d50f8",
        "KA-DCF-03 result": "750eb893f1e89c0d89010857690c88f399a4c1c13381105fa653fc5857ae60ef",
        "STRESS-A result": "9fb5a3c516ace7d0b09f34ed472c12ea2908d27b25c9c0f00fa4bd4fbdbd4bec",
        "STRESS-B result": "ea62a9d1039b288c97ef6bd087588d78d593e46fe5b31e9926e83f8da17980ab",
        "KA-DCF-03 grid 7x7 wacc x g": (
            "a97bd35b1b57036557f69c50f640ff86ac38ac19415c1179b79b739c63f6f308"
        ),
    },
}


def stress_a():  # type: ignore[no-untyped-def]
    """Loss-making ramp, negative terminal growth, unusual CAPM inputs, stale market data."""
    yrs = list(constant_drivers(0.05, 0.20, 0.06, 0.04, 0.30))
    yrs[0] = ForecastYearDrivers(0.80, -0.10, 0.06, 0.08, 0.30)
    yrs[1] = ForecastYearDrivers(0.60, -0.02, 0.06, 0.08, 0.30)
    return dcf_inputs(
        forecast=ForecastInputs(500.0, 25.0, tuple(yrs)),
        terminal_growth=-0.01,
        wacc_override=None,
        wacc_assumptions=wacc_assumptions(
            levered_beta=3.5, equity_risk_premium=0.12, size_premium=0.02, risk_free_rate=0.16
        ),
        current_share_price=10.0,
        share_capital=cap(100.0, rsus=(RsuGrant("RSU", 2.0),)),
        bridge=bridge(cash=50.0, debt=200.0, leases=30.0, include_leases=False, nci=5.0),
        dates=dates(market=date(2025, 12, 31)),
    )


def stress_b():  # type: ignore[no-untyped-def]
    """Narrow spread, g above Rf, target structure, options + convertible solved, peer check."""
    return dcf_inputs(
        terminal_growth=0.045,
        wacc_override=None,
        wacc_assumptions=wacc_assumptions(
            risk_free_rate=0.03,
            levered_beta=0.5,
            equity_risk_premium=0.06,
            pre_tax_cost_of_debt=0.05,
            debt_value_basis=DebtValueBasis.BOOK,
            target_debt_to_capital=0.3,
        ),
        current_share_price=12.0,
        peer_ev_ebitda_range=(20.0, 30.0),
        share_capital=cap(
            100.0,
            options=(OptionTranche("A", 5.0, 8.0), OptionTranche("B", 3.0, 40.0)),
            convertibles=(ConvertibleInstrument("N", 50.0, 10.0),),
        ),
        bridge=bridge(cash=100.0, debt=300.0, leases=40.0, include_leases=True, nci=20.0),
        dates=dates(market=date(2025, 4, 10)),
    )


#: Issue codes the golden cases must exercise, so a change to any of these messages, severities
#: or conditions is caught. The set may grow; it must not shrink without review.
COVERED_CODES = {
    "CAPEX_BELOW_DA_TERMINAL",
    "CONVERTIBLE_CONVERTED",
    "DEBT_AT_BOOK",
    "DILUTION_SOLVED",
    "ENTERPRISE_VALUE_NON_POSITIVE",
    "EQUITY_VALUE_NON_POSITIVE",
    "EXTREME_GROWTH",
    "EXTREME_WACC",
    "LEASES_EXCLUDED",
    "MARKET_DATA_DATE_DIFFERS",
    "MARKET_DATA_STALE",
    "NEGATIVE_EBITDA_MARGIN",
    "NEGATIVE_EBIT_NO_TAX_CREDIT",
    "NEGATIVE_UFCF",
    "NWC_STEP_CHANGE",
    "SIZE_PREMIUM_APPLIED",
    "TARGET_STRUCTURE_USED",
    "TERMINAL_GROWTH_ABOVE_RF",
    "TERMINAL_GROWTH_HIGH",
    "TERMINAL_GROWTH_NEGATIVE",
    "TV_MULTIPLE_INCONSISTENT",
    "TV_SHARE_HIGH",
    "TV_SPREAD_NARROW",
    "UNUSUAL_BETA",
    "UNUSUAL_ERP",
    "UNUSUAL_RISK_FREE",
    "WACC_OVERRIDDEN",
}


def sha(obj: object) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def frozen_base(r: DcfResult) -> FrozenBase:
    return FrozenBase(r.wacc, r.enterprise_value, r.equity_value, r.value_per_share)


def current_outputs() -> dict[str, str]:
    r3 = run_dcf(ka_dcf03_inputs())
    grid = frozen_run_grid(
        ka_dcf03_inputs(),
        frozen_base(r3),
        AxisSpec(DcfVariable.WACC, 0.005, 3),
        AxisSpec(DcfVariable.TERMINAL_GROWTH, 0.005, 3),
        DcfOutput.VALUE_PER_SHARE,
    )
    return {
        "KA-DCF-02 result": sha(run_dcf(dcf_inputs())),
        "KA-DCF-03 result": sha(r3),
        "STRESS-A result": sha(run_dcf(stress_a())),
        "STRESS-B result": sha(run_dcf(stress_b())),
        "KA-DCF-03 grid 7x7 wacc x g": sha(grid),
    }


def test_current_engine_version_has_goldens() -> None:
    assert ENGINE_VERSION in GOLDENS, (
        f"ENGINE_VERSION {ENGINE_VERSION} has no golden entry: follow the bump checklist "
        "(docs/phase-4-plan.md §4.13)."
    )


def test_outputs_match_goldens_for_this_engine_version() -> None:
    assert current_outputs() == GOLDENS[ENGINE_VERSION], (
        "DCF or sensitivity output changed without an ENGINE_VERSION bump. If intentional, "
        "follow the bump checklist (docs/phase-4-plan.md §4.13)."
    )


def test_frozen_input_reconstruction_is_exact() -> None:
    """Scope item 3: inputs_json → DcfInputsIn → DcfInputs must round-trip byte for byte."""
    for inp in (dcf_inputs(), ka_dcf03_inputs()):
        rebuilt = DcfInputsIn.model_validate_json(canonical_json(inp)).to_engine()
        assert canonical_json(rebuilt) == canonical_json(inp)
        assert fingerprint(rebuilt) == fingerprint(inp)


def test_golden_cases_cover_the_issue_codes() -> None:
    emitted = set()
    for inp in (dcf_inputs(), ka_dcf03_inputs(), stress_a(), stress_b()):
        emitted |= {i.code for i in run_dcf(inp).issues}
    assert emitted >= COVERED_CODES, COVERED_CODES - emitted
