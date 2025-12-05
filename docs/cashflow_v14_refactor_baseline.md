Alright, the repo gods are clearly in a mood today, so I’ll dodge the flaky file API and give you something you can copy-paste directly.

Below is your **refactor baseline document** as markdown. You can drop it into the repo as
`docs/cashflow_v14_refactor_baseline.md` (or whatever path you prefer).

---

````markdown
# DutchBay V14 Cashflow Engine – Refactor Baseline

This document captures the **current canonical baseline** of `cashflow_v14` and
the guardrails for refactoring it with a “lender / CFA” hat on, without
breaking the v14 pipeline.

---

## 1. Purpose of `cashflow_v14`

`cashflow_v14` is the *single* source of truth for project-level CFADS for the
DutchBay v14 finance stack. Everything downstream – debt sizing, DSCR,
covenants, KPIs, Monte Carlo, dashboards – must consume CFADS from here.

**Non-negotiable contract:**

For each project year `t` (1-based in outputs, 0-based internally):

```text
cfads_final_lkr[t] =
    revenue_lkr[t]
  – total_statutory_deductions[t]
  – opex_lkr[t]
  – tax_lkr[t]          (after interest shield + depreciation)
  – risk_haircut_amount[t]
````

No other module is allowed to silently redefine CFADS.

---

## 2. Public surface (must remain stable)

The following functions are the *only* supported public API and must keep their
signatures and core semantics:

* `validate_parameters(config: dict[str, Any]) -> list[str]`
* `build_annual_cfads(p: dict[str, Any], ...) -> list[float]`
* `build_annual_rows(p: dict[str, Any], ...) -> list[dict[str, float]]`
* `calculate_single_year_cfads(params: dict[str, Any], ...) -> dict[str, float]`

These are already aligned with:

* `debt_v14.plan_debt` (uses CFADS list + annual rows)
* `contracts_v14.build_cashflow_result_from_annual_rows`
* The v14 schema guard (`analytics.config_schema` / `RequiredFieldSpec`).

Any refactor must **not**:

* Rename these functions
* Change parameter order / types
* Remove keys from the per-year row dicts (you may add *new* keys, but never
  remove or silently change meaning of existing ones).

---

## 3. Key internal helpers (ring-fenced logic)

The current engine cleanly ring-fences the following pillars inside
`cashflow_v14`:

### 3.1 Production and revenue

* `_calculate_net_production(...)`
  Computes `gross_kwh`, `net_kwh` using:

  * `capacity_mw`
  * `capacity_factor` (decimal)
  * `degradation` (decimal, per-year)
  * `grid_loss_pct` (decimal, share of gross)

* `_calculate_revenue_lkr(net_kwh, tariff_lkr_per_kwh)`
  Straight `net_kwh × tariff` conversion.

### 3.2 Statutory deductions

* `_calculate_statutory_deductions(revenue_lkr, success_fee_pct, env_surcharge_pct, social_levy_pct)`

  Returns a dict with:

  * `success_fee`
  * `environmental_surcharge`
  * `social_services_levy`
  * `total_statutory_deductions`

All of these are **decimals** (0.01 = 1%), and are **only** applied here – no
other module should be computing statutory carve-outs on revenue.

### 3.3 OPEX and FX

* `_calculate_opex_lkr(opex_usd_per_year, fx_rate)`
  Simple FX conversion – all CFADS tax and debt logic sees OPEX in LKR only.

* `_fx_curve(p, years)`
  Responsible for constructing the **entire LKR/USD curve** used by cashflow
  and debt. It supports:

  1. Explicit curve (`fx.curve` / `fx.curve_lkr_per_usd`)
  2. Parametric curve (`start_lkr_per_usd` + `annual_depr` or `annual_depr_pct`)
  3. A hard fallback (flat 375 LKR/USD) with a **warning** for legacy configs.

The refactor must keep the behaviour but can tighten:

* Error messages when an `fx` block exists but is malformed
* Test coverage around parametric vs explicit curves.

### 3.4 Tax, depreciation, and interest shield

* `_compute_depreciation_schedule(...)`
* `calculate_tax_with_interest_shield(...)`

These encode Sri Lankan-style BOI / Inland Revenue behaviour:

* Optional tax holidays (`tax_holiday_years`, `tax_holiday_start_year`)
* Enhanced capital allowance (`enhanced_capital_allowance_pct`)
* Straight-line tax depreciation on a *depreciable base* LKR value
* Interest shield on taxable income (`pretax_cfads – depreciation – interest`).

**Important:** `capex_depreciable_lkr` is deliberately separated from “headline
CAPEX” – the tax base can be different from total EPC, and the code honours
that.

### 3.5 Risk haircuts

* `_apply_risk_haircut(cfads_lkr, risk_haircut_pct)`

Applied **after tax**, so lenders see a conservative post-tax CFADS. The
haircut is fully transparent in the row output via:

* `risk_haircut_pct`
* `risk_haircut_amount`

---

## 4. Parameter extraction and schema guard

`_extract_parameters(raw)` is the **normalisation gate**. It:

1. Derives `project_life_years` via `_extract_project_life_years`
2. Resolves all CFADS drivers from a mix of legacy and v14-canonical paths
3. Converts percentages to decimals (`_pct_to_decimal`)
4. Enforces basic ranges (`capacity_mw > 0`, `0 < capacity_factor <= 1`, etc.)
5. Raises a single `ValueError` listing **all** missing/invalid fields.

`validate_parameters(config)` is the more human-readable, external guard:

* It does not depend on `_extract_parameters`; instead, it re-parses enough
  of the config to give friendly messages (“implausibly high degradation”, etc.)
* It is called inside `_prepare_cashflow_context` *before* running any
  expensive CFADS logic.

`_register_cashflow_schema()` mirrors the same expectations as structured
`RequiredFieldSpec` entries, so `schema_guard` can fail fast **before** the
engine runs.

---

## 5. What a “Guru-level” refactor should do (without breaking anything)

### 5.1 Keep

* All public functions and their signatures
* The CFADS identity (formula and sign convention)
* All row keys currently emitted by `calculate_single_year_cfads`
* The high-level structure:

  * helpers → param extraction → context → single-year → annual rows.

### 5.2 Improve

1. **Type safety / clarity**

   * Optionally introduce a `@dataclass` for `CashflowParams` and use it *internally*,
     while keeping the public `dict[str, Any]` interface for callers and tests.
   * Tighten some helper signatures (`_resolve_first`, `_fx_curve`) with types.

2. **Depreciation efficiency**

   * Pre-compute the depreciation schedule once per project and reuse it
     instead of re-computing inside `calculate_tax_with_interest_shield`
     for every year. This can be done internally without changing the public
     function signatures by introducing a small internal context object.

3. **Logging for lenders**

   * Keep the existing range log for CFADS (`min`, `max`).
   * Optionally add *debug*-level logs for:

     * First-year CFADS breakdown
     * Tax holiday window
     * Effective FX curve (P50 printout only on verbose runs).

4. **Error messaging**

   * Make FX error messages more explicit when an `fx` block is present but
     unusable.
   * Ensure all “implausible” parameter warnings clearly state units
     (e.g. “>30% per-year degradation – check if you meant 3.0 not 30.0”).

5. **Unit test hooks**

   * Add **internal** helpers (prefixed `_`) that expose just enough of the
     internal logic to be tested deterministically:

     * `_debug_build_depreciation_schedule(...)`
     * `_debug_fx_curve_from_parametric(...)`
   * Keep them out of `__all__` so the public API remains small, but tests can
     still import them explicitly if needed.

### 5.3 Explicit non-goals

* No DSCR, LLCR, PLCR, or IRR calculations live here – those stay in the
  debt and metrics modules.
* No ad-hoc adjustments for P50/P90, curtailment, or grid outages – those
  belong either in the scenario config (capacity factor layer) or a separate
  analytics layer, not in `cashflow_v14`.

---

## 6. Row dictionary (per-year CFADS breakdown)

Each year’s row currently contains at least:

* `year`
* `gross_kwh`
* `grid_loss`
* `net_kwh`
* `revenue_lkr`
* `success_fee`
* `env_surcharge`
* `social_levy`
* `total_statutory_deductions`
* `opex_usd`
* `fx_rate`
* `opex_lkr`
* `pretax_cfads`
* `total_depreciation`
* `interest_expense_lkr`
* `taxable_income`
* `tax`
* `posttax_cfads`
* `risk_haircut_amount`
* `risk_haircut_pct`
* `cfads_final_lkr`
* `revenue_usd` (added in `build_annual_rows`)
* `cfads_usd` (added in `build_annual_rows`)

For a global fund manager or DFI credit officer, this is already a
lender-grade audit trail, provided:

* The schema guard guarantees all inputs are present and sensibly scaled.
* The FX and tax regimes are clearly documented (as per this note).
* No other module silently mutates CFADS or re-interprets its sign.

---

## 7. Next steps

1. Save this document into the repo as e.g.
   `docs/cashflow_v14_refactor_baseline.md`.
2. In the next sprint, implement **internal** refactors only (dataclasses,
   pre-computed depreciation, slightly richer logging), and wire tests to
   enforce the CFADS identity and key invariants.
3. Once tests are green, freeze the updated module as the *new* canonical
   surface and let debt / analytics refactors build on top of it.

```

---

You can now:

- Paste that into a `.md` file locally and commit it, or
- Hand it to me in the next sprint as the “refactor spec” while we actually
  touch the Python.

If you want the **actual `cashflow_v14.py` code listing re-emitted with small
Guru tweaks next (same API, more comments / structure), say the word and I’ll
inline the full refactored module for copy-paste.
```
