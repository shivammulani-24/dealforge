"""DealForge financial calculation engine.

Pure, deterministic, standard-library-only Python. No database, web framework, pandas or
network access is imported anywhere in this package (enforced by ``tests/engine/test_purity.py``).

Module map (spec section in brackets)::

    errors, validation, metrics   issue codes, input checks, OK / MISSING / NM values
    dates          [H.1, D-07]    statement / valuation / forecast / market-data dates
    historical     [H.2]          growth, margins, FCF, NWC, leverage, consistency checks
    ebitda         [D-03]         standardised vs reported vs adjusted EBITDA
    forecast       [H.3]          five-year driver-based operating forecast
    fcf            [H.4, D-06]    unlevered free cash flow
    wacc           [H.5, D-08]    CAPM, after-tax Kd, market-value weights, Hamada
    dcf            [H.6]          discount factors, Gordon terminal value, EV
    bridge         [H.7, D-09]    EV ↔ equity value
    shares         [H.8, D-10]    TSM, RSUs, convertibles, exact circularity solve
    valuation                     end-to-end DCF orchestrator
    comps          [H.9, D-11]    peer EV, multiples, statistics, implied valuation
    sensitivity    [H.12]         two-way grids of full re-runs
    scenarios      [H.12]         base + audited overrides
    mna            [H.11, D-13]   sources & uses, pro forma EPS, accretion/dilution
    hashing                       canonical JSON + SHA-256 input fingerprints
"""

from .version import ENGINE_VERSION

__all__ = ["ENGINE_VERSION"]
