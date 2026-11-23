"""Dual-currency financing, FX drift and shock, and tenor-tail screening for any scenario.

A standalone screening calculator: dual-currency debt sizing, dated FX observations with their
evidence status, tenor-tail validation and debt service coverage ratio (DSCR) screening
indicators. It runs for any scenario that declares a ``financing_screening`` block
(:mod:`analytics.site_analysis_blocks`, #1754); a scenario without one is reported as not
applicable. The project's capex, tariff, O&M, FX at close, timeline, tax and gearing cap are
read from the scenario itself (:func:`scenario_screening_inputs`); the block holds the
screening assumptions, the reference generation, the named sensitivities, the fixed-debt stress
grid and the dated FX history. No site name, path or figure is held here (``ARCH-01``, #1759).

Governance and scope:

- HOLD (F-5, #1110, v15.6.1): screening indicators only, NOT a lender verdict, bankability
  determination or credit commitment. Lender interest rates and DSCR thresholds are
  illustrative screening assumptions, not terms (#1629).
- The core v14 engine carries an FX drift override to the USD OPEX share (BW-5, L-12 D-2).
  This screening does not call the engine and is no substitute for it (``FRAMEWORK-03``).
- Moved here from the single-site screening module (#1578 U4), which now re-exports these
  names and keeps its single-site entry point.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_F5_HOLD_CAVEAT = (
    "HOLD (F-5, #1110, v15.6.1): Standalone screening indicator only — not a lender "
    "verdict, bankability determination, or credit commitment. Lender interest rates and "
    "DSCR thresholds are illustrative screening assumptions, not executed term-sheet terms (#1629)."
)
DEFAULT_ENGINE_PATH_STATUS = "delivered_bw5_l12_d2"
DEFAULT_ENGINE_PATH_NOTE = (
    "The core v14 engine carries an FX override to the USD OPEX share: a drift stress or a "
    "Monte Carlo drift draw replaces its own FX path (BW-5, L-12 D-2); this module is a "
    "standalone screening utility and does not call the engine."
)


def annuity(principal: float, rate: float, years: int) -> float:
    """Return annual end-period level debt service; reject invalid inputs.

    Args:
        principal: Non-negative initial principal amount.
        rate: Non-negative periodic interest rate in decimal form.
        years: Positive loan amortization tenor in years.

    Returns:
        Annual level payment amount.

    Raises:
        ValueError: If principal or rate is non-finite or negative, or years < 1.
    """
    if not math.isfinite(principal) or not math.isfinite(rate):
        raise ValueError("Nonfinite loan input")
    if principal < 0 or rate < 0 or years < 1:
        raise ValueError("Loan requires nonnegative principal/rate and positive tenor")
    if rate == 0:
        return principal / years
    return principal * rate / (1.0 - (1.0 + rate) ** (-years))


def amortize_tranche(
    principal: float, rate: float, years: int
) -> List[Dict[str, float]]:
    """Return annual level amortization schedule in the loan tranche's native currency.

    Ensures principal conservation, non-negative closing balances, and zero closing
    balance at final maturity.

    Args:
        principal: Non-negative initial principal.
        rate: Non-negative periodic rate decimal.
        years: Positive loan tenor in years.

    Returns:
        List of dicts per operating year with keys:
        'year', 'opening', 'interest', 'principal', 'service', 'closing'.
    """
    payment = annuity(principal, rate, years)
    balance = float(principal)
    rows: List[Dict[str, float]] = []
    for year in range(1, years + 1):
        opening = balance
        interest = opening * rate
        repayment = min(opening, payment - interest)
        balance = max(0.0, opening - repayment)
        if year == years:
            repayment, balance = opening, 0.0
        rows.append(
            {
                "year": float(year),
                "opening": opening,
                "interest": interest,
                "principal": repayment,
                "service": interest + repayment,
                "closing": balance,
            }
        )
    return rows


# Backward-compatible alias matching reconstructed script naming
amortize = amortize_tranche


def compute_fx_cagr(
    start_rate: float, end_rate: float, start_date: str, end_date: str
) -> float:
    """Annualize positive LKR-per-USD change using exact days / 365.25.

    Args:
        start_rate: Positive initial exchange rate (LKR per USD).
        end_rate: Positive terminal exchange rate (LKR per USD).
        start_date: ISO-formatted start date ('YYYY-MM-DD').
        end_date: ISO-formatted end date ('YYYY-MM-DD').

    Returns:
        Annualized compound growth rate (CAGR) in decimal form.

    Raises:
        ValueError: If rates are non-positive or dates are not chronological.
    """
    d_start = date.fromisoformat(start_date)
    d_end = date.fromisoformat(end_date)
    elapsed = (d_end - d_start).days / 365.25
    if min(start_rate, end_rate) <= 0 or elapsed <= 0:
        raise ValueError("Positive FX observations and chronological dates required")
    return float((end_rate / start_rate) ** (1.0 / elapsed) - 1.0)


# Backward-compatible alias matching reconstructed script naming
cagr = compute_fx_cagr


def validate_debt_tenor_against_ppa(
    dfi_tenor_years: int,
    local_tenor_years: int,
    ppa_years: int,
    lender_tail_years: int,
) -> int:
    """Validate that debt maturity does not exceed contracted revenue less lender tail.

    Args:
        dfi_tenor_years: Operating repayment tenor of DFI tranche in years.
        local_tenor_years: Operating repayment tenor of domestic tranche in years.
        ppa_years: Contracted PPA duration in years.
        lender_tail_years: Minimum tail required by lenders before PPA expiry.

    Returns:
        The maximum debt maturity in years.

    Raises:
        ValueError: If debt maturity exceeds contracted revenue less lender tail,
            or if parameters are non-positive.
    """
    if dfi_tenor_years < 1 or local_tenor_years < 1 or ppa_years < 1:
        raise ValueError("Tenor and PPA years must be positive integers")
    if lender_tail_years < 0:
        raise ValueError("Lender tail years must be non-negative")
    debt_end = max(dfi_tenor_years, local_tenor_years)
    if debt_end > ppa_years - lender_tail_years:
        raise ValueError("Debt maturity exceeds contracted revenue less lender tail")
    return debt_end


def evaluate_dual_currency_screening(
    cfg: Dict[str, Any], debt_usd_equivalent: float, downside: bool = False
) -> List[Dict[str, Any]]:
    """Return annual dual-currency screening cash flows under one generation and FX path.

    - Debt is committed at financial close; fully drawn without IDC capitalization.
    - USD DFI tranche stays in USD; service is translated at operating-year scenario FX.
    - Domestic LKR tranche is fixed in LKR at closing FX; service is paid in fixed LKR.
    - Year 1 FX is COD FX (2-year construction compounding from close).
    - Straight-line tax allowance is an illustrative screening proxy with loss carryforward.
    - Annual credit fee applies to opening translated debt balances.
    - ``downside=True`` uses ``assumed_downside_gwh``: an assumed downside screening
      sensitivity, never a measured P90.

    Args:
        cfg: Configuration dictionary containing screening assumptions.
        debt_usd_equivalent: Total debt commitment in USD equivalent.
        downside: Whether to evaluate ``assumed_downside_gwh`` instead of ``p50_gwh``.

    Returns:
        List of annual cash flow row dicts across the PPA operating life.

    Raises:
        ValueError: On invalid allocation, negative debt, or tenor-tail violation.
    """
    share = float(cfg["dfi_share"])
    if not 0.0 <= share <= 1.0 or debt_usd_equivalent < 0:
        raise ValueError("Invalid debt allocation")

    validate_debt_tenor_against_ppa(
        int(cfg["dfi_tenor_years"]),
        int(cfg["local_tenor_years"]),
        int(cfg["ppa_years"]),
        int(cfg["lender_tail_years"]),
    )

    usd = amortize_tranche(
        debt_usd_equivalent * share,
        float(cfg["dfi_rate_decimal"]),
        int(cfg["dfi_tenor_years"]),
    )
    lkr = amortize_tranche(
        debt_usd_equivalent * (1.0 - share) * float(cfg["fx_close_lkr_per_usd"]),
        float(cfg["local_rate_decimal"]),
        int(cfg["local_tenor_years"]),
    )

    generation = float(cfg["assumed_downside_gwh"] if downside else cfg["p50_gwh"])
    fx_close = float(cfg["fx_close_lkr_per_usd"])
    opex_base_lkr = float(cfg["opex_usd_equivalent_year1"]) * fx_close
    basis = float(cfg["capex_usd"]) * fx_close
    losses: List[List[float]] = []
    rows: List[Dict[str, Any]] = []
    zero: Dict[str, float] = {
        "opening": 0.0,
        "interest": 0.0,
        "principal": 0.0,
        "service": 0.0,
        "closing": 0.0,
    }

    ppa_years = int(cfg["ppa_years"])
    construction_years = int(cfg["construction_years"])
    fx_depreciation = float(cfg["fx_depreciation_decimal"])
    fx_shock = float(cfg["fx_shock_decimal"])
    shock_year = int(cfg["shock_operating_year"])
    gen_degradation = float(cfg["generation_degradation_decimal"])
    tariff_fixed = float(cfg["tariff_fixed_lkr_per_kwh"])
    tariff_om = float(cfg["tariff_om_lkr_per_kwh"])
    tariff_om_escalation = float(cfg["tariff_om_escalation_decimal"])
    opex_usd_equiv = float(cfg["opex_usd_equivalent_year1"])
    opex_usd_share = float(cfg["opex_usd_share"])
    usd_opex_escalation = float(cfg["usd_opex_escalation_decimal"])
    lkr_opex_escalation = float(cfg["lkr_opex_escalation_decimal"])
    credit_fee_rate = float(cfg["annual_credit_fee_decimal"])
    allowance_years = int(cfg["allowance_years"])
    loss_carryforward_years = int(cfg["loss_carryforward_years"])
    tax_rate = float(cfg["tax_rate_decimal"])

    for year in range(1, ppa_years + 1):
        fx = fx_close * (1.0 + fx_depreciation) ** (construction_years + year - 1)
        if year >= shock_year:
            fx *= 1.0 + fx_shock

        energy = generation * 1e6 * (1.0 - gen_degradation) ** (year - 1)
        tariff = tariff_fixed + tariff_om * (1.0 + tariff_om_escalation) ** (year - 1)
        revenue = energy * tariff
        opex = opex_usd_equiv * opex_usd_share * fx * (1.0 + usd_opex_escalation) ** (
            year - 1
        ) + opex_base_lkr * (1.0 - opex_usd_share) * (1.0 + lkr_opex_escalation) ** (
            year - 1
        )

        row_usd = usd[year - 1] if year <= len(usd) else zero
        row_lkr = lkr[year - 1] if year <= len(lkr) else zero

        interest = row_usd["interest"] * fx + row_lkr["interest"]
        fees = (row_usd["opening"] * fx + row_lkr["opening"]) * credit_fee_rate
        allowance = basis / allowance_years if year <= allowance_years else 0.0

        taxable = revenue - opex - fees - interest - allowance
        losses = [x for x in losses if year - x[0] <= loss_carryforward_years]
        if taxable < 0:
            losses.append([float(year), -taxable])
            taxable = 0.0
        else:
            for loss in losses:
                used = min(taxable, loss[1])
                taxable -= used
                loss[1] -= used

        tax = max(0.0, taxable) * tax_rate
        cfads = revenue - opex - fees - tax
        service = row_usd["service"] * fx + row_lkr["service"]
        dscr = cfads / service if service > 0 else None

        rows.append(
            {
                "year": year,
                "fx_lkr_per_usd": fx,
                "energy_kwh": energy,
                "tariff_lkr_per_kwh": tariff,
                "revenue_lkr": revenue,
                "opex_lkr": opex,
                "allowance_lkr": allowance,
                "interest_lkr": interest,
                "credit_fee_lkr": fees,
                "tax_lkr": tax,
                "cfads_lkr": cfads,
                "debt_service_lkr": service,
                "dscr": dscr,
                "dfi_closing_usd": row_usd["closing"],
                "local_closing_lkr": row_lkr["closing"],
            }
        )
    return rows


# Backward-compatible alias matching reconstructed script naming
evaluate = evaluate_dual_currency_screening


def compute_coverage_metrics(
    rows: List[Dict[str, Any]], local_years: int
) -> Dict[str, Any]:
    """Summarize debt-life and first-local-tenor coverage without zero-service years.

    Args:
        rows: Annual cash flow rows from ``evaluate_dual_currency_screening``.
        local_years: Tenor of local debt tranche in years.

    Returns:
        Dict with min_dscr, average_dscr, first_local_average_dscr, binding_year.
    """
    active = [r for r in rows if r["dscr"] is not None]
    if not active:
        return {
            "min_dscr": math.inf,
            "average_dscr": math.inf,
            "first_local_average_dscr": math.inf,
            "binding_year": None,
        }
    binding = min(active, key=lambda r: float(r["dscr"]))
    return {
        "min_dscr": float(binding["dscr"]),
        "average_dscr": float(mean(r["dscr"] for r in active)),
        "first_local_average_dscr": float(
            mean(r["dscr"] for r in active if r["year"] <= local_years)
        ),
        "binding_year": int(binding["year"]),
    }


# Backward-compatible alias matching reconstructed script naming
metrics = compute_coverage_metrics


def size_debt_screening(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Bisect debt from zero to gearing cap under P50 and assumed-downside screening thresholds.

    Produces a standalone screening indicator only (HOLD F-5, #1110, v15.6.1);
    does not represent a lender verdict or executed financing terms (#1629).

    Args:
        cfg: Screening configuration mapping.

    Returns:
        Dict containing sized debt_usd, gearing_decimal, equity_capex_balance_usd,
        p50 coverage metrics, assumed_downside coverage metrics, screening status
        indicator, and F-5 HOLD caveat.
    """
    local_years = int(cfg["local_tenor_years"])
    min_downside_threshold = float(cfg["min_downside_dscr"])

    def meets_screening_dscr_thresholds(debt: float) -> bool:
        p50 = compute_coverage_metrics(
            evaluate_dual_currency_screening(cfg, debt, downside=False), local_years
        )
        downside = compute_coverage_metrics(
            evaluate_dual_currency_screening(cfg, debt, downside=True), local_years
        )
        return bool(
            float(p50["min_dscr"]) >= float(cfg["min_p50_dscr"])
            and float(downside["min_dscr"]) >= min_downside_threshold
            and float(p50["first_local_average_dscr"]) >= float(cfg["average_p50_dscr"])
        )

    debt_end = max(int(cfg["dfi_tenor_years"]), local_years)
    unlevered_downside = evaluate_dual_currency_screening(cfg, 0.0, downside=True)[
        :debt_end
    ]
    if min(r["cfads_lkr"] for r in unlevered_downside) < 0:
        return {
            "debt_usd": 0.0,
            "gearing_decimal": 0.0,
            "equity_capex_balance_usd": float(cfg["capex_usd"]),
            "p50": compute_coverage_metrics(
                evaluate_dual_currency_screening(cfg, 0.0, downside=False), local_years
            ),
            "assumed_downside": {
                "generation_basis": "assumed_downside_not_measured_p90",
                **compute_coverage_metrics(
                    evaluate_dual_currency_screening(cfg, 0.0, downside=True),
                    local_years,
                ),
            },
            "status": "screening_indicator_negative_unlevered_cfads",
            "lender_rates_are_assumptions": True,
            "f5_hold_caveat": DEFAULT_F5_HOLD_CAVEAT,
        }

    low = 0.0
    high = float(cfg["capex_usd"]) * float(cfg["maximum_gearing_decimal"])
    for _ in range(70):
        mid = (low + high) / 2.0
        if meets_screening_dscr_thresholds(mid):
            low = mid
        else:
            high = mid

    sized_debt = low
    return {
        "debt_usd": sized_debt,
        "gearing_decimal": sized_debt / float(cfg["capex_usd"]),
        "equity_capex_balance_usd": float(cfg["capex_usd"]) - sized_debt,
        "p50": compute_coverage_metrics(
            evaluate_dual_currency_screening(cfg, sized_debt, downside=False),
            local_years,
        ),
        "assumed_downside": {
            "generation_basis": "assumed_downside_not_measured_p90",
            **compute_coverage_metrics(
                evaluate_dual_currency_screening(cfg, sized_debt, downside=True),
                local_years,
            ),
        },
        "status": "screening_indicator_only",
        "lender_rates_are_assumptions": True,
        "f5_hold_caveat": DEFAULT_F5_HOLD_CAVEAT,
    }


# Backward-compatible alias matching reconstructed script naming
size_debt = size_debt_screening


def complete_total(lines: Dict[str, Optional[float]]) -> Optional[float]:
    """Return None when any package remains unpriced; never coerce unknown to zero.

    Args:
        lines: Mapping of package names to quoted amounts or None.

    Returns:
        Sum of amounts if all are priced, or None if any package is None.

    Raises:
        ValueError: If any priced amount is non-finite or negative.
    """
    if not lines or any(value is None for value in lines.values()):
        return None
    values = [float(value) for value in lines.values() if value is not None]
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("Costs must be finite nonnegative amounts or None")
    return sum(values)


def energy_scaled_price(
    reference_cost: float, reference_aep: float, target_aep: float
) -> float:
    """Return hypothetical proportional-AEP arithmetic, never an OEM price estimator.

    Args:
        reference_cost: Reference equipment cost.
        reference_aep: Reference AEP.
        target_aep: Target AEP.

    Returns:
        Arithmetic proportional scaled amount.

    Raises:
        ValueError: On negative cost or non-positive AEP.
    """
    if reference_cost < 0 or min(reference_aep, target_aep) <= 0:
        raise ValueError("Invalid hypothetical scaling input")
    return reference_cost * target_aep / reference_aep


def compute_fx_history_metrics(
    observations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Compute periodic quote change and rupee depreciation from dated observations.

    Args:
        observations: Chronological list of exchange-rate observations.

    Returns:
        List of enriched observation dicts with quote change and currency depreciation.
    """
    fxrows: List[Dict[str, Any]] = []
    for i, r in enumerate(observations):
        rate = float(r["lkr_per_usd"])
        if i:
            prev_rate = float(observations[i - 1]["lkr_per_usd"])
            change = rate / prev_rate - 1.0
            depreciation = 1.0 - prev_rate / rate
        else:
            change = None
            depreciation = None
        fxrows.append(
            {
                **r,
                "quote_change_decimal": change,
                "lkr_value_depreciation_decimal": depreciation,
            }
        )
    return fxrows


def run_fixed_debt_stress(
    cfg: Dict[str, Any],
    held_debt_usd: float,
    depreciation_rates: List[float],
    shock_decimals: List[float],
    shock_operating_year: int = 5,
) -> List[Dict[str, Any]]:
    """Evaluate DSCR coverage under a 2D grid of FX depreciation rates and level shocks.

    Args:
        cfg: Baseline screening configuration.
        held_debt_usd: Fixed debt commitment amount held constant across stress tests.
        depreciation_rates: Annual depreciation rates to evaluate.
        shock_decimals: One-time permanent level shocks applied from shock_operating_year.
        shock_operating_year: Operating year from which shock applies.

    Returns:
        List of stress result dicts.
    """
    local_years = int(cfg["local_tenor_years"])
    stress: List[Dict[str, Any]] = []
    for g in depreciation_rates:
        for shock in shock_decimals:
            c = {
                **cfg,
                "fx_depreciation_decimal": g,
                "fx_shock_decimal": shock,
                "shock_operating_year": shock_operating_year,
            }
            m = compute_coverage_metrics(
                evaluate_dual_currency_screening(c, held_debt_usd), local_years
            )
            stress.append(
                {
                    "fx_depreciation_decimal": g,
                    "shock_decimal": shock,
                    "shock_operating_year": shock_operating_year,
                    "held_debt_usd": held_debt_usd,
                    **m,
                }
            )
    return stress


# ---------------------------------------------------------------------------
# Scenario-driven entry point (#1578 U4)
# ---------------------------------------------------------------------------

#: The block this analysis reads (:mod:`analytics.site_analysis_blocks`).
BLOCK = "financing_screening"
SUMMARY_SCHEMA = "dutchbay.fx_tenor_screening.v1"

#: Inputs read from the scenario itself; a named sensitivity may override any of them.
SCENARIO_INPUT_KEYS = (
    "capex_usd",
    "opex_usd_equivalent_year1",
    "tariff_fixed_lkr_per_kwh",
    "tariff_om_lkr_per_kwh",
    "fx_close_lkr_per_usd",
    "fx_depreciation_decimal",
    "ppa_years",
    "construction_years",
    "tax_rate_decimal",
    "loss_carryforward_years",
    "maximum_gearing_decimal",
    "generation_degradation_decimal",
)


def _required(scenario: Mapping[str, Any], dotted: str) -> Any:
    node: Any = scenario
    for part in dotted.split("."):
        if not isinstance(node, Mapping) or part not in node:
            raise KeyError(
                f"the {BLOCK} analysis reads scenario key {dotted!r}, which is missing"
            )
        node = node[part]
    return node


def scenario_screening_inputs(scenario: Mapping[str, Any]) -> Dict[str, Any]:
    """Return the screening inputs a scenario itself carries.

    A scenario without ``tariff.om_indexation`` has a flat tariff: the whole contracted
    tariff (``tariff.lkr_per_kwh``) is the fixed part, so the escalable O&M part is zero
    unless a named sensitivity sets it. A scenario that declares ``tariff.om_indexation``
    (L-9) is read the way the engine reads it (``finance.tariff_indexation``): the fixed part
    is ``lkr_per_kwh`` less ``escalable_om_lkr_per_kwh``, and the O&M part is that component
    at operating year 1, after the block's ``pre_operation_years`` steps, escalating at the
    scenario's own yearly rate (returned as ``tariff_om_escalation_decimal``). Year by year
    the screening tariff then equals the engine's (#1796 domain R1).

    Raises:
        KeyError: A scenario key the screening reads is missing; the message names it.
        ValueError: ``tariff.om_indexation`` is malformed (``resolve_om_indexation``).
    """
    from finance.capex_price_basis import refuse_unapplied_price_basis
    from finance.tariff_indexation import resolve_om_indexation

    refuse_unapplied_price_basis(scenario, "the FX and tenor screening")
    tariff_lkr = float(_required(scenario, "tariff.lkr_per_kwh"))
    inputs: Dict[str, Any] = {
        "capex_usd": float(_required(scenario, "capex.usd_total")),
        "opex_usd_equivalent_year1": float(_required(scenario, "opex.usd_per_year")),
        "tariff_fixed_lkr_per_kwh": tariff_lkr,
        "tariff_om_lkr_per_kwh": 0.0,
        "fx_close_lkr_per_usd": float(_required(scenario, "fx.start_lkr_per_usd")),
        "fx_depreciation_decimal": float(_required(scenario, "fx.annual_depr")),
        "ppa_years": int(_required(scenario, "tariff.ppa_term_years")),
        "construction_years": int(_required(scenario, "timeline.construction_years")),
        "tax_rate_decimal": float(_required(scenario, "tax.corporate_tax_rate")),
        "loss_carryforward_years": int(
            _required(scenario, "tax.loss_carryforward_years")
        ),
        "maximum_gearing_decimal": float(
            _required(scenario, "Financing_Terms.debt_ratio")
        ),
        "generation_degradation_decimal": float(
            _required(scenario, "project.degradation")
        )
        / 100.0,
    }
    indexation = resolve_om_indexation(scenario, base_tariff_lkr_per_kwh=tariff_lkr)
    if indexation is not None:
        escalable = indexation.escalable_om_lkr_per_kwh
        inputs["tariff_fixed_lkr_per_kwh"] = tariff_lkr - escalable
        inputs["tariff_om_lkr_per_kwh"] = escalable * indexation.index(0)
        inputs["tariff_om_escalation_decimal"] = indexation.annual_rate
    return inputs


def _tariff_om_escalation(inputs: Mapping[str, Any], block: Mapping[str, Any]) -> float:
    """The O&M tariff part's yearly escalation: the scenario's own rate, or the block's.

    A scenario that indexes its O&M part (``tariff.om_indexation``) sets the rate, and the
    block must then leave ``tariff_om_escalation_decimal`` out; a scenario with a flat tariff
    takes it from the block, which must then state it. Either way exactly one source names
    the rate, so neither can silently override the other.

    Raises:
        ValueError: Both the scenario and the block state the rate, or neither does.
    """
    in_scenario = "tariff_om_escalation_decimal" in inputs
    in_block = "tariff_om_escalation_decimal" in block
    if in_scenario and in_block:
        raise ValueError(
            f"{BLOCK}.tariff_om_escalation_decimal: the scenario's tariff.om_indexation "
            "already sets the O&M part's escalation; leave the block's key out"
        )
    if not in_scenario and not in_block:
        raise ValueError(
            f"{BLOCK}.tariff_om_escalation_decimal: required when the scenario declares "
            "no tariff.om_indexation"
        )
    source = inputs if in_scenario else block
    return float(source["tariff_om_escalation_decimal"])


def screening_config_from_block(
    inputs: Mapping[str, Any], block: Mapping[str, Any]
) -> Dict[str, Any]:
    """Merge a scenario's own inputs with its block into the flat screening config.

    Raises:
        ValueError: The O&M tariff escalation is stated twice or not at all
            (:func:`_tariff_om_escalation`).
    """
    debt = block["debt"]
    opex = block["opex"]
    shock = block["fx_shock"]
    generation = block["generation"]
    return {
        **inputs,
        "lender_tail_years": int(debt["lender_tail_years"]),
        "dfi_share": float(debt["dfi_share"]),
        "dfi_rate_decimal": float(debt["dfi_rate_decimal"]),
        "local_rate_decimal": float(debt["local_rate_decimal"]),
        "dfi_tenor_years": int(debt["dfi_tenor_years"]),
        "local_tenor_years": int(debt["local_tenor_years"]),
        "annual_credit_fee_decimal": float(debt.get("annual_credit_fee_decimal", 0.0)),
        "min_p50_dscr": float(block["min_p50_dscr"]),
        "min_downside_dscr": float(block["min_downside_dscr"]),
        "average_p50_dscr": float(block["average_p50_dscr"]),
        "tariff_om_escalation_decimal": _tariff_om_escalation(inputs, block),
        "opex_usd_share": float(opex["usd_share"]),
        "usd_opex_escalation_decimal": float(opex["usd_escalation_decimal"]),
        "lkr_opex_escalation_decimal": float(opex["local_escalation_decimal"]),
        "allowance_years": int(block["allowance_years"]),
        "fx_shock_decimal": float(shock["shock_decimal"]),
        "shock_operating_year": int(shock["operating_year"]),
        "p50_gwh": float(generation["p50_gwh"]),
        "assumed_downside_gwh": float(generation["assumed_downside_gwh"]),
    }


def _screening_result(sized: Mapping[str, Any], case_type: str) -> Dict[str, Any]:
    return {
        "case_type": case_type,
        "debt_usd": sized["debt_usd"],
        "gearing_decimal": sized["gearing_decimal"],
        "equity_capex_balance_usd": sized["equity_capex_balance_usd"],
        "p50": sized["p50"],
        "assumed_downside": sized["assumed_downside"],
        "status": sized["status"],
        "lender_rates_are_assumptions": sized["lender_rates_are_assumptions"],
    }


def _fx_cagr_windows(windows: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "label": w["label"],
            "start": w["start"],
            "end": w["end"],
            "start_date": w["start_date"],
            "end_date": w["end_date"],
            "is_assumption": bool(w["is_assumption"]),
            "evidence_status": w["evidence_status"],
            "annualized_quote_change_decimal": compute_fx_cagr(
                float(w["start"]),
                float(w["end"]),
                str(w["start_date"]),
                str(w["end_date"]),
            ),
        }
        for w in windows
    ]


def _digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, default=str, allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_fx_tenor_screening_from_block(
    scenario: Mapping[str, Any], block: Mapping[str, Any]
) -> Dict[str, Any]:
    """Run every screening the block asks for, on the scenario's own inputs.

    Returns the base case, each tenor variant, each named sensitivity, the fixed-debt FX
    stress grid and the FX history metrics, keyed by the ids the block gives them.
    """
    inputs = scenario_screening_inputs(scenario)
    base_cfg = screening_config_from_block(inputs, block)
    out: Dict[str, Any] = {
        "scenario_inputs_applied": inputs,
        "base_case": _screening_result(size_debt_screening(base_cfg), "base_case"),
    }
    variants: Dict[str, Any] = {}
    for variant in block.get("tenor_variants", []):
        cfg = {
            **base_cfg,
            "dfi_tenor_years": int(variant["dfi_tenor_years"]),
            "ppa_years": int(variant["ppa_years"]),
            "lender_tail_years": int(variant["lender_tail_years"]),
        }
        variants[str(variant["id"])] = _screening_result(
            size_debt_screening(cfg), "tenor_variant"
        )
    out["tenor_variants"] = variants
    sensitivities: Dict[str, Any] = {}
    for sens in block.get("sensitivities", []):
        overrides = {k: sens[k] for k in SCENARIO_INPUT_KEYS if k in sens}
        result = _screening_result(
            size_debt_screening({**base_cfg, **overrides}), "sensitivity"
        )
        result["description"] = sens["description"]
        result["overrides"] = overrides
        sensitivities[str(sens["id"])] = result
    out["sensitivities"] = sensitivities
    stress = block.get("fixed_debt_stress")
    out["fixed_debt_fx_stress"] = (
        run_fixed_debt_stress(
            base_cfg,
            float(stress["held_debt_usd"]),
            [float(r) for r in stress["depreciation_rates"]],
            [float(s) for s in stress["shock_decimals"]],
            int(stress["operating_year"]),
        )
        if stress is not None
        else []
    )
    history = block.get("fx_history", {})
    out["fx_history"] = compute_fx_history_metrics(
        [dict(o) for o in history.get("observations", [])]
    )
    out["fx_cagr_windows"] = _fx_cagr_windows(list(history.get("cagr_windows", [])))
    return out


def run_fx_tenor_screening_for_scenario(
    scenario: Mapping[str, Any],
    method: Mapping[str, Any],
    *,
    scenario_label: str,
) -> Dict[str, Any]:
    """Run the screening for one scenario, or report it as not applicable.

    A scenario with the block gets ``"status": "completed"`` and every screening result; one
    without it gets ``"status": "not_applicable"`` and the reason, never an error.

    Args:
        scenario: The scenario mapping.
        method: The method configuration's ``method`` mapping: ``hold_caveat``,
            ``engine_path_status``, ``engine_path_note`` and ``limitations``.
        scenario_label: How the scenario is named in the result (its path).

    Raises:
        ValueError: The block is present but malformed (every problem is listed).
        KeyError: A scenario key the screening reads is missing.
    """
    from analytics.evaluation_v14 import evaluated_scenario_config
    from analytics.site_analysis_blocks import (
        STATUS_NOT_APPLICABLE,
        resolve_site_analysis_block,
    )

    # #1899: screen the capex the engine finances. A declared capex.price_basis is
    # applied here (idempotent), as the pipeline applies it.
    scenario = evaluated_scenario_config(scenario)
    common: Dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "analysis": "FX and tenor screening",
        "scenario": scenario_label,
        "hold_caveat": str(method["hold_caveat"]),
    }
    block = resolve_site_analysis_block(scenario, BLOCK)
    if block is None:
        return {
            **common,
            "status": STATUS_NOT_APPLICABLE,
            "reason": f"the scenario declares no {BLOCK} block",
        }
    return {
        **common,
        "status": "completed",
        "label": block["label"],
        "site": dict(block["site"]),
        "block_sha256": _digest(block),
        "engine_path_status": str(method["engine_path_status"]),
        "engine_path_note": str(method["engine_path_note"]),
        "limitations": [str(x) for x in method["limitations"]],
        "generation_basis_note": block["generation"]["basis_note"],
        **compute_fx_tenor_screening_from_block(scenario, block),
    }
