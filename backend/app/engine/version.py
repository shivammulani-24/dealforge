"""Engine version: the valuation calculation contract (Phase 4 plan §4.13, amendment A1).

ENGINE_VERSION must change if, and only if, for some valid input, any of these could change:

1. DCF results: any field of the canonical ``run_dcf`` result JSON, including issue codes,
   severities, messages and their order.
2. Input fingerprinting: the canonical serialisation of ``DcfInputs`` (``input_hash``).
3. Frozen-input reconstruction: how a run's ``inputs_json`` becomes ``DcfInputs`` again.
4. Sensitivity semantics: variables and how they are applied, axis construction, cell validity
   and codes, output selection, ``change_abs``/``change_pct`` and NM rules, the base-match rule.

Not in scope (no bump): historical-analysis metrics (including liquidity ratios), presentation
margins, LIM-12 driver warnings, API envelopes and the UI.

Bump checklist: docs/phase-4-plan.md §4.13. ``tests/engine/test_engine_version_guard.py`` fails
if any golden output changes while this value is unchanged, or if this value has no goldens.
"""

ENGINE_VERSION = "0.1.0"
