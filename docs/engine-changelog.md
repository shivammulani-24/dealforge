# Engine changelog

`ENGINE_VERSION` identifies the valuation calculation contract: DCF results, input
fingerprinting, frozen-input reconstruction and sensitivity semantics. Its scope and the bump
checklist are in [`phase-4-plan.md` §4.13](phase-4-plan.md#413-engine-version-scope-and-bump-checklist-a1-a3)
and in `backend/app/engine/version.py`. Every bump adds an entry here listing each changed
known answer with its before and after values and the reason.

## 0.1.0 (Phase 2, unchanged through Phase 4 F0a)

The first contract. Goldens are pinned in `backend/tests/engine/test_engine_version_guard.py`:

| Golden | SHA-256 of canonical output |
|---|---|
| KA-DCF-02 result | `b99a08dd…46d50f8` |
| KA-DCF-03 result | `750eb893…57ae60ef` |
| STRESS-A result (loss-making ramp, negative g, unusual CAPM inputs) | `9fb5a3c5…bdbd4bec` |
| STRESS-B result (narrow spread, options and convertible, target structure) | `ea62a9d1…da17980ab` |
| KA-DCF-03 7×7 WACC × g grid | `a97bd35b…63f6f308` |

Phase 4 F0a added `frozen_run_grid` (the first sensitivity semantics for frozen runs), so there
was no earlier sensitivity contract to differ from, and no bump. The liquidity ratios and
presentation margins are outside the scope.
