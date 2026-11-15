"""Blue Whale dual-currency financing, FX drift/shock, and tenor-tail screening.

Standalone screening calculator implementing the dual-currency debt sizing,
dated FX observations with evidence classification, tenor-tail validation,
and debt service coverage ratio (DSCR) screening indicators from the owner's
private research hand-off of 2026-11-14.

Governance & Scope Boundaries:
- HOLD (F-5, #1110, v15.6.1): Produces screening indicators only, NOT a lender
  verdict, bankability determination, or credit commitment. Lender interest rates
  and DSCR thresholds are illustrative screening assumptions, not terms (#1629).
- Core v14 engine path is PENDING: FX feeding the USD OPEX share is BW-5
  (L-12 D-2) work.
- Basecase capex, tariff, O&M, and FX-at-close are read from
  ``scenarios/dutchbay_basecase_2025Q4.yaml``; divergent cases are explicitly
  labeled as sensitivities.
- Does NOT modify frozen lender scenarios (scenarios/blue_whale_*.yaml) or
  substitute for the governed v14 core financial calculation pipeline (CCCDIR).
"""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOVERNED_SCENARIO_PATH = "scenarios/dutchbay_basecase_2025Q4.yaml"
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


def load_governed_basecase_inputs(
    scenario_path: Path | str = DEFAULT_GOVERNED_SCENARIO_PATH,
) -> Dict[str, Any]:
    """Load governed basecase inputs from ``scenarios/dutchbay_basecase_2025Q4.yaml``.

    Args:
        scenario_path: Path to the governed scenario YAML (relative to repo root or absolute).

    Returns:
        Dictionary of screening-compatible inputs derived from the governed scenario.

    Raises:
        FileNotFoundError: If the governed scenario file does not exist.
        KeyError: If required governed fields are absent.
        ValueError: If the loaded YAML is not a mapping or contains invalid values.
    """
    resolved = Path(scenario_path)
    if not resolved.is_absolute():
        resolved = REPO_ROOT / resolved
    if not resolved.is_file():
        raise FileNotFoundError(f"Governed scenario file not found: {resolved}")

    data = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in governed scenario YAML: {resolved}")

    return {
        "capex_usd": float(data["capex"]["usd_total"]),
        "opex_usd_equivalent_year1": float(data["opex"]["usd_per_year"]),
        "tariff_fixed_lkr_per_kwh": float(data["tariff"]["lkr_per_kwh"]),
        "tariff_om_lkr_per_kwh": 0.0,
        "fx_close_lkr_per_usd": float(data["fx"]["start_lkr_per_usd"]),
        "fx_depreciation_decimal": float(data["fx"]["annual_depr"]),
        "ppa_years": int(data["tariff"]["ppa_term_years"]),
        "construction_years": int(data["timeline"]["construction_years"]),
        "tax_rate_decimal": float(data["tax"]["corporate_tax_rate"]),
        "loss_carryforward_years": int(data["tax"]["loss_carryforward_years"]),
        "maximum_gearing_decimal": float(data["Financing_Terms"]["debt_ratio"]),
        "generation_degradation_decimal": float(data["project"]["degradation"]) / 100.0,
    }


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
    - Note: There is no measured DutchBay wind data and no measured P90; ``downside=True``
      uses ``assumed_downside_gwh`` as an assumed downside screening sensitivity.

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


def run_comprehensive_screening(raw_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Execute complete screening suite across governed and sensitivity configs.

    Reads governed basecase inputs (capex, tariff, O&M, FX-at-close, etc.) from
    ``raw_cfg["governed_scenario_path"]`` (``scenarios/dutchbay_basecase_2025Q4.yaml``).
    Uses the 14-turbine DutchBay scope (#1587) and labels any divergent case as an
    explicit sensitivity.

    Args:
        raw_cfg: Loaded and validated configuration mapping.

    Returns:
        Structured summary mapping suitable for JSON emission.
    """
    scenario_path = raw_cfg.get(
        "governed_scenario_path", DEFAULT_GOVERNED_SCENARIO_PATH
    )
    governed_inputs = load_governed_basecase_inputs(scenario_path)
    params = raw_cfg["screening_parameters"]
    cases = raw_cfg["cases"]

    # FX CAGR benchmark windows
    fx_metrics: List[Dict[str, Any]] = []
    for window in raw_cfg.get("fx_cagr_benchmark_windows", []):
        cagr_val = compute_fx_cagr(
            float(window["start"]),
            float(window["end"]),
            str(window["start_date"]),
            str(window["end_date"]),
        )
        fx_metrics.append(
            {
                "label": window["label"],
                "start": window["start"],
                "end": window["end"],
                "start_date": window["start_date"],
                "end_date": window["end_date"],
                "is_assumption": bool(window.get("is_assumption", True)),
                "evidence_status": window.get(
                    "evidence_status", "unverified_assumption_unverified_endpoint_rates"
                ),
                "annualized_quote_change_decimal": cagr_val,
            }
        )

    # Governed basecase 14-turbine screening (#1587, 15-year DFI / 20-year PPA)
    governed_15_cfg = {
        **governed_inputs,
        **params,
        **cases["14_governed_basecase"],
    }
    sized_governed_15 = size_debt_screening(governed_15_cfg)

    # Governed basecase 14-turbine screening (10-year DFI / 12-year PPA / 2-year tail)
    governed_10_cfg = {
        **governed_15_cfg,
        "dfi_tenor_years": 10,
        "ppa_years": 12,
        "lender_tail_years": 2,
    }
    sized_governed_10 = size_debt_screening(governed_10_cfg)

    # Explicit sensitivity (14 turbines, handoff PUCSL tariff / assumed O&M / 333.79 FX)
    sensitivity_15_cfg = {
        **governed_inputs,
        **params,
        **cases["14_handoff_sensitivity"],
    }
    sized_sensitivity_15 = size_debt_screening(sensitivity_15_cfg)

    # Fixed debt stress grid on governed 14-turbine basecase
    stress_cfg = raw_cfg.get("stress_grid", {})
    held_debt = float(stress_cfg.get("held_debt_usd", 87770000))
    depreciation_rates = [
        float(r)
        for r in stress_cfg.get(
            "depreciation_rates", [0.0, 0.03, 0.0589, 0.07, 0.08, 0.1068, 0.12]
        )
    ]
    shock_decimals = [
        float(s) for s in stress_cfg.get("shock_decimals", [0.0, 0.2, 0.3])
    ]
    stress_results = run_fixed_debt_stress(
        governed_15_cfg, held_debt, depreciation_rates, shock_decimals
    )

    def _format_screening_block(
        sized: Dict[str, Any], case_meta: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "case_type": case_meta.get("case_type", "governed_basecase_screening"),
            "turbine_count": int(case_meta.get("turbine_count", 14)),
            "debt_usd": sized["debt_usd"],
            "gearing_decimal": sized["gearing_decimal"],
            "equity_capex_balance_usd": sized["equity_capex_balance_usd"],
            "p50": sized["p50"],
            "assumed_downside": sized["assumed_downside"],
            "status": sized["status"],
            "lender_rates_are_assumptions": sized["lender_rates_are_assumptions"],
        }

    return {
        "schema_version": raw_cfg.get(
            "schema_version", "blue_whale_fx_tenor_screening_v1"
        ),
        "status": "complete",
        "governed_scenario_source": str(scenario_path),
        "governed_inputs_applied": governed_inputs,
        "f5_hold_caveat": raw_cfg.get("f5_hold_caveat", DEFAULT_F5_HOLD_CAVEAT),
        "engine_path_status": raw_cfg.get(
            "engine_path_status", DEFAULT_ENGINE_PATH_STATUS
        ),
        "engine_path_note": raw_cfg.get("engine_path_note", DEFAULT_ENGINE_PATH_NOTE),
        "fx_metrics": fx_metrics,
        "governed_basecase_14turbine_15year_screening": _format_screening_block(
            sized_governed_15, cases["14_governed_basecase"]
        ),
        "governed_basecase_14turbine_10year_screening": _format_screening_block(
            sized_governed_10, cases["14_governed_basecase"]
        ),
        "sensitivity_14turbine_15year_screening": _format_screening_block(
            sized_sensitivity_15, cases["14_handoff_sensitivity"]
        ),
        "fixed_debt_fx_stress_count": len(stress_results),
        "fixed_debt_fx_stress_summary": stress_results,
        "limitations_count": len(raw_cfg.get("limitations", [])),
        "disclaimer": (
            "HOLD (F-5, #1110, v15.6.1): Standalone screening indicator only; not a "
            "governed v14 lender commitment, lender verdict, or legal tax advice. "
            "The core v14 engine carries FX to the USD OPEX share (BW-5 / L-12 D-2); "
            "this screening does not call it."
        ),
    }
