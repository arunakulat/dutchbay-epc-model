# API Contract: `casper_result_v1`

**Status**: Frozen (additive keys permitted, see versioning rules below)
**Contract version string**: `casper_result_v1`
**Producer**: `analytics/casper/casper_payload.py` (`build_casper_payload()` -> `_casper_to_dict()`)
**Freeze pins**: `tests/api/test_casper_contract_freeze.py`, `tests/analytics/test_casper_payload_coverage.py`

This document is the compliance record for the CASPER JSON payload contract
(CCCDIR: contracts centralized, compliance documented). It is the doc referenced
by the comment above `CASPER_CONTRACT_VERSION` in
`analytics/casper/casper_payload.py` and by
`docs/analytics_restructure_migration_plan.md`.

---

## Versioning rules

- The constant `CASPER_CONTRACT_VERSION = "casper_result_v1"` is defined in
  `analytics/casper/casper_payload.py` and mirrored in `analytics/contracts_v14`
  (as `CasperResult.contract_version`). The two constants MUST remain equal;
  `tests/api/test_casper_contract_freeze.py` pins this.
- **Additive posture**: adding a new top-level key is a non-breaking change and
  does NOT bump the version, provided the key degrades to `None` when its
  upstream input is absent. Precedents: `generation`, `technology_breakdown`,
  `multi_tech_wbs` (#475), `mc_risk` (#637).
- **Breaking changes** — removing, renaming, or re-typing an existing key, or
  changing the meaning of its values — REQUIRE a version bump to
  `casper_result_v2` plus updated freeze tests and a successor to this document.

## Top-level payload shape

`_casper_to_dict()` is the single place that defines what CASPER returns to the
outside world. It emits exactly these top-level keys:

| Key | Type | `None` when |
| --- | --- | --- |
| `contract_version` | `str` | never (always `"casper_result_v1"`) |
| `scenario` | `dict` | scenario input absent |
| `baseline_kpis` | `dict[str, float]` | never (may be empty; numeric scalars only) |
| `sensitivity` | `dict` | no `SensitivitySuite` supplied |
| `monte_carlo` | `dict` | no `MonteCarloResult` supplied |
| `mc_risk` | `dict` | see degradation semantics below |
| `generation` | `dict` | no `MultiTechGenerationResult` supplied |
| `technology_breakdown` | `list[dict]` | no per-technology breakdown supplied |
| `multi_tech_wbs` | `dict` | no `MultiTechWBS` supplied |
| `tail_risk` | `dict` | `metadata["tail_risk_summary"]` absent or empty |
| `metadata` | `dict` | never (may be empty) |

Key-by-key notes:

- **`scenario`** — slender JSON-safe descriptor (`scenario_name`, `config_path`,
  `validation_mode`, `discount_rate_used`, WACC label/flags, `min_dscr`,
  `max_debt_usd`), plus optional `wacc`, `debt_profile`, `debt_covenants`, and
  `equity_performance` blocks when attached to the `ScenarioResult`. Full
  `config` / `annual_rows` are deliberately NOT shipped. When the producer only
  has a scenario name string, the descriptor is `{"scenario_name": <str>}`.
- **`baseline_kpis`** — numeric scalars only, filtered from
  `ScenarioResult.kpis` (non-numeric entries such as `scenario_name`,
  `wacc_label`, `dscr_series` are skipped; `bool` is excluded).
- **`sensitivity`** — `{"metric", "base_metric", "base_config_path", "tornado"}`
  where `tornado` is a flat list of per-variable shock rows
  (`variable`, `base_irr`, `low_irr`, `high_irr`, `impact_abs`, `impact_pct`).
- **`monte_carlo`** — lean summary: `scenario_name`, `iterations`,
  `failed_iterations`, `success_rate_pct`, and `irr` / `npv` / `dscr_min`
  percentile blocks. Raw per-draw arrays are NOT emitted here.
- **`mc_risk`** — lender-grade MC risk block, detailed below.
- **`tail_risk`** — snapshot mapping surfaced from
  `metadata["tail_risk_summary"]` (metric name -> VaR/CVaR/percentile snapshot).
- **`metadata`** — free-form small JSON-safe fields; must not carry large blobs
  or raw engine tables.

## The `mc_risk` block (#637)

Auto-wired into the payload since #637 — callers do NOT insert the lender risk
table by hand (the manual `payload["tables"]["lender_risk_table"]` pattern in
older examples is legacy; see `docs/CASPER_MC_INTEGRATION.md`). The producer
calls `analytics.mc.exports.build_casper_risk_blocks()` on the raw MC trial
arrays and emits:

```json
{
  "mc_risk": {
    "lender_risk_table": [
      {"metric": "DSCR (min)", "P50": 1.45, "P90": 1.32, "P95": 1.28,
       "mean": 1.42, "std": 0.08},
      {"metric": "Prob(DSCR < 1.30)", "P50": null, "P90": null, "P95": null,
       "mean": 0.12, "std": null}
    ],
    "covenant": {
      "dscr_floor": 1.30,
      "prob_breach": 0.12,
      "worst_year_dscr_p95_downside": 1.22,
      "n_trials": 1000
    }
  }
}
```

Semantics:

- **Downside (exceedance) convention**: for higher-is-better metrics (DSCR,
  IRR, NPV, LLCR, PLCR) the `P90`/`P95` columns report the value exceeded
  90%/95% of the time — i.e. the 10th/5th percentile — consistent with the
  AEP P90 convention. They are NOT the favourable 90th/95th percentiles.
- **Covenant floor is config-first (CESSPIT)**: resolved from the scenario's
  `debt_covenants.dscr_threshold`; falls back to the `CovenantSpec` default
  (1.30) only when no structured covenant is attached. The floor actually used
  is always surfaced in `covenant.dscr_floor`.
- **JSON safety**: non-finite floats (the `NaN` placeholders in covenant rows)
  are mapped to `null`; the payload is valid under a strict encoder
  (`allow_nan=False`). Integer fields such as `n_trials` stay integers.

### Degradation semantics (CASPER: graceful call-time failure)

`mc_risk` is `None` — the payload never crashes — when any of these hold:

1. Monte Carlo was not run (`monte_carlo=None`).
2. The `MonteCarloResult` is summary-only, i.e. carries no raw `dscr_min`
   trial array (`KeyError` path).
3. The optional `pandas` export dependency is absent (`RuntimeError` path) or
   the export module is unavailable (`ImportError` path).

Any other exception is a genuine bug and propagates (fail-loud); the sanctioned
degradation paths above are the ONLY swallowed ones.

---

## Related documents

- `docs/CASPER_MC_INTEGRATION.md` — how to produce and consume the MC risk
  analytics, including the legacy manual-insertion pattern.
- `docs/analytics_restructure_migration_plan.md` — migration history that
  references this contract.

**Last updated**: 2026-07-02 (#638; records the #637 `mc_risk` auto-wiring)
