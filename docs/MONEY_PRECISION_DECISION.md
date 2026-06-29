# Money precision: float64 vs Decimal (ADR, #480 / audit §8)

Status: **Accepted** (2026-06). Decision: **keep `float` (IEEE-754 float64) on the money
path**, with an explicit presentation/rounding policy. Do **not** migrate the cashflow/debt
engine to `decimal.Decimal`.

## Context

The audit (§8) flagged that money is carried as `float` throughout the cashflow/debt engine
(`finance/cashflow_v14*.py`, `finance/debt_v14.py`, `finance/irr.py`) and asked whether
`Decimal` (or a documented rounding policy) is warranted to avoid accumulation error and to
present lender-grade rounding.

Two distinct concerns are often conflated:

1. **Accumulation error** — does float64 round-off, summed/discounted over a 20–25-year
   schedule at LKR-billion magnitudes, materially move a reported KPI?
2. **Presentation** — are outputs rounded sensibly for a lender pack?

## Evidence (measured, not asserted)

Measured on the **real** canonical lender scenario
(`scenarios/dutchbay_lendercase_2025Q4.yaml`), 20 operating years, comparing the float64
NPV against an exact `Decimal` (50-digit) NPV of the identical CFADS at the project WACC
(~0.0983):

| quantity | value |
|---|---|
| Σ CFADS | 101,869,357,189.94 LKR |
| NPV (float64) | 54,584,199,062.877449 LKR |
| NPV (Decimal, exact) | 54,584,199,062.877464 LKR |
| **absolute error** | **1.31e-5 LKR ≈ 3.9e-8 USD** |
| **relative error** | **2.4e-16** (≈ float64 machine epsilon) |

The float64 NPV is correct to **~16 significant figures**: the absolute error on a
~54.6-billion-LKR (~$163M) NPV is a few hundredths of a **micro-cent**. This is ~10 orders
of magnitude below any lender-relevant threshold (IRR reported to basis points; NPV to whole
dollars; DSCR to two decimals). The plain undiscounted sum error is similar (6.1e-6 LKR).

## Decision

**Keep float64 on the money path.** Rationale:

- The measured accumulation error is immaterial (2.4e-16 relative) — `Decimal` would buy no
  decision-relevant accuracy.
- A `Decimal` migration would touch every arithmetic site in the cashflow/debt/IRR engine,
  interact badly with the vectorised `numpy`/`scipy` numerics (Monte-Carlo, sculpting, IRR
  bisection — none of which accept `Decimal`), and be a large, **KPI-moving** change (the
  last-ULP differences would re-pin many regression tests) for zero economic benefit.
- Float64 is the lingua franca of the scientific-Python stack the model is built on; staying
  in it keeps the engine simple, fast, and `numpy`-native.

## Presentation / rounding policy

Money is **computed** in float64 and **presented** rounded at the reporting boundary, never
mid-calculation (no intermediate rounding that could bias a sum):

- KPIs: IRR/WACC as decimals (e.g. `0.0268`); DSCR/LLCR/PLCR to 2 dp; NPV/CFADS to whole
  currency units in lender-facing tables (the report formatters in `app/reports/` —
  `fmt_usd`/`fmt_gwh`/`fmt_x`/`fmt_ratio_pct` — own this).
- Equality comparisons in the engine and tests use tolerances (`math.isclose`,
  `pytest.approx`, the FP-tolerant covenant epsilons), never exact `==` on computed money.
- Any future genuinely cash-exact requirement (e.g. a rounded invoice/settlement amount) is
  a **local** rounding at that boundary, not a global numeric-type change.

## Consequences

- No code change: this ADR records the keep-float decision and the existing presentation
  policy (KPI-neutral).
- Revisit only if a future requirement needs cash-exact (sub-cent, deterministic-rounding)
  settlement figures — and then scope it to that boundary, not the engine.

## Reproducing the evidence

```python
from decimal import Decimal, getcontext
from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.scenario_loader import load_scenario_config
from finance.irr import npv

getcontext().prec = 50
rows = evaluate_with_overrides(
    raw_config=load_scenario_config("scenarios/dutchbay_lendercase_2025Q4.yaml"),
    overrides={}, return_full_result=True,
)["annual_rows"]
cfads = [float(r.get("cfads_final_lkr", 0.0)) for r in rows]
r = 0.0983
npv_float = npv(r, cfads)
npv_dec = sum(Decimal(repr(c)) / (Decimal(1) + Decimal(repr(r))) ** i
              for i, c in enumerate(cfads))
print(npv_float, float(npv_dec), abs(Decimal(repr(npv_float)) - npv_dec))
```

Related: [`CURRENCY_NUMERAIRE_DECISION.md`](CURRENCY_NUMERAIRE_DECISION.md) (the LKR/USD
numéraire decision).
