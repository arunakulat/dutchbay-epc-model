"""Cost and storage analytics for the command-line lender report (#1825 slice iii).

Six analyses that were reachable only from their own modules feed one opt-in section of the
command-line lender report:

* **Estimate class**: the scenario's AACE estimate class and its expected accuracy band
  (:func:`analytics.cost.estimate_class.resolve_accuracy_band`).
* **CAPEX Monte Carlo**: :func:`analytics.cost.mc_capex.run_capex_mc` held to the lender
  guards: at least :data:`~app.reports.capital_risk_emit.LENDER_GRADE_MIN_TRIALS` trials,
  ``monte_carlo.allow_toy_fallback`` forced off, a fixed seed, and a factor-1.0 trial that must
  reproduce the committed KPIs. The 1-sigma comes from the scenario: a declared CAPEX
  uncertainty, or else the spread the scenario's declared estimate class implies.
* **Storage dispatch**: :func:`analytics.storage_dispatch.evaluate_chronological_dispatch`, for
  a scenario that declares an enabled ``chronological_dispatch`` block.
* **LCOS**: :func:`finance.bess_lcos.compute_lcos_suite` for every ``type: bess`` technology,
  at the run's own discount rate over its operating years.
* **Battery-project economics** and **EPC margin**: the entries the pipeline already publishes
  (``bess_project_economics``, ``epc_margin``) for a scenario that declares the block.

What the section is, and is not:

* Beside the committed case, never a replacement for it. No finance logic is re-implemented,
  and the committed case, its figures and every KPI are unchanged.
* Universal: every input comes from the scenario or the run's result. A part that does not
  apply or cannot run is listed with its reason, and the rest of the section still renders.

GWTF:
    - FRAMEWORK-03: one seam; the report model holds the typed block, this module fills it.
    - FRAMEWORK-01: a part that cannot run gets a stated reason, never a default input.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Union

from app.reports.capital_risk_emit import LENDER_GRADE_MIN_TRIALS
from app.reports.report_model import (
    BessEconomicsRow,
    CapexMcBlock,
    CapexMcRow,
    CostStorageBlock,
    DispatchSummary,
    EpcMarginSummary,
    EstimateClassBand,
    LcosRow,
)

__all__ = [
    "CostStorageSettings",
    "DEFAULT_COST_STORAGE_SETTINGS",
    "SECTION_COST_STORAGE",
    "build_cost_storage_section",
    "settings_from_config",
]

#: The section's name in the report's "sections not run" list.
SECTION_COST_STORAGE = "Cost and storage"

_PREFIX = "lender_report.cost_storage"

#: KPI rows of the CAPEX Monte Carlo: (result attribute, committed KPI key, label, unit).
_MC_ROWS: Tuple[Tuple[str, Optional[str], str, str], ...] = (
    ("capex_usd", None, "CAPEX (pre-levy base)", "usd"),
    ("project_irr", "project_irr", "Project IRR", "pct"),
    ("equity_irr", "equity_irr", "Equity IRR", "pct"),
    ("project_npv_usd", "project_npv", "Project NPV", "usd"),
    ("min_dscr", "min_dscr", "Minimum DSCR", "ratio"),
)
#: KPIs a factor-1.0 trial must reproduce.
_BASE_POINT_KPIS: Tuple[str, ...] = ("project_irr", "project_npv", "min_dscr")
_BASE_POINT_RTOL = 1e-9


@dataclass(frozen=True)
class CostStorageSettings:
    """Analysis settings, not site inputs (``lender_report.cost_storage``)."""

    enabled: bool = False
    capex_mc_trials: int = LENDER_GRADE_MIN_TRIALS
    capex_mc_seed: int = 12345


#: Off by default (#1825: each analytics section is opt-in).
DEFAULT_COST_STORAGE_SETTINGS = CostStorageSettings()


def settings_from_config(raw: Optional[Mapping[str, Any]]) -> CostStorageSettings:
    """Read ``lender_report.cost_storage`` from the run configuration.

    Raises:
        ValueError: An unknown key, or fewer CAPEX Monte Carlo trials than the lender floor.
    """
    if raw is None:
        return DEFAULT_COST_STORAGE_SETTINGS
    if not isinstance(raw, Mapping):
        raise ValueError(f"{_PREFIX} must be a mapping")
    known = {"enabled", "capex_mc"}
    unknown = sorted(set(raw) - known)
    if unknown:
        raise ValueError(f"{_PREFIX}: unknown key(s) {unknown}")
    mc = raw.get("capex_mc") or {}
    if not isinstance(mc, Mapping) or set(mc) - {"trials", "seed"}:
        raise ValueError(f"{_PREFIX}.capex_mc takes only trials and seed")
    trials = int(mc.get("trials", LENDER_GRADE_MIN_TRIALS))
    if trials < LENDER_GRADE_MIN_TRIALS:
        raise ValueError(
            f"{_PREFIX}.capex_mc.trials must be at least {LENDER_GRADE_MIN_TRIALS} "
            f"(the lender-grade floor), not {trials}"
        )
    return CostStorageSettings(
        enabled=bool(raw.get("enabled", False)),
        capex_mc_trials=trials,
        capex_mc_seed=int(mc.get("seed", 12345)),
    )


# --------------------------------------------------------------------------- parts


def _estimate_class(scenario: Mapping[str, Any]) -> EstimateClassBand:
    from analytics.cost.estimate_class import resolve_accuracy_band

    band = resolve_accuracy_band(scenario)
    capex = scenario.get("capex")
    declared = isinstance(capex, Mapping) and capex.get("estimate_class") is not None
    return EstimateClassBand(
        estimate_class=band.estimate_class,
        low_pct=band.low_pct,
        high_pct=band.high_pct,
        implied_sigma_pct=band.implied_sigma_pct,
        declared=declared,
    )


def _sigma(
    scenario: Mapping[str, Any], band: EstimateClassBand
) -> Union[Tuple[Optional[float], str], str]:
    """The 1-sigma to pass (None: the module reads the declared one) and its basis."""
    from analytics.cost.mc_capex import resolve_capex_sigma_pct

    try:
        declared = resolve_capex_sigma_pct(scenario)
    except ValueError:
        declared = None
    if declared is not None:
        if declared < band.implied_sigma_pct:
            return None, (
                f"the scenario's declared CAPEX uncertainty, {declared:.2f}%, floored to "
                f"the {band.implied_sigma_pct:.2f}% that AACE Class {band.estimate_class} "
                "implies"
            )
        return None, f"the scenario's declared CAPEX uncertainty, {declared:.2f}%"
    if band.declared:
        return band.implied_sigma_pct, (
            "no CAPEX uncertainty is declared, so the spread the scenario's declared AACE "
            f"Class {band.estimate_class} implies ({band.low_pct:+.0f}% to "
            f"{band.high_pct:+.0f}%, about {band.implied_sigma_pct:.2f}% at one sigma)"
        )
    return (
        "not run: the scenario declares neither a CAPEX uncertainty "
        "(capex.contingency.base_cost_uncertainty_pct or capex.uncertainty_pct) nor "
        "capex.estimate_class"
    )


def _base_point_config(cfg: Mapping[str, Any], base: float) -> Dict[str, Any]:
    """The config a factor-1.0 trial runs (mirrors one trial of ``run_capex_mc``)."""
    run_cfg: Dict[str, Any] = copy.deepcopy(dict(cfg))
    cap = dict(run_cfg.get("capex", {}))
    if "input" not in cap:
        cap.pop("derive_from_breakdown", None)
        cap["usd_total"] = base
    run_cfg["capex"] = cap
    return run_cfg


def _base_point(
    cfg: Mapping[str, Any],
    base: float,
    committed: Mapping[str, Any],
    pipeline: Callable[..., Mapping[str, Any]],
) -> str:
    kpis = pipeline(config=_base_point_config(cfg, base))["kpis"]
    off: List[str] = []
    for key in _BASE_POINT_KPIS:
        a, b = kpis.get(key), committed.get(key)
        if a is None or b is None:
            if a is not b:
                off.append(f"{key} ({a!r} against the committed {b!r})")
            continue
        if not math.isclose(
            float(a), float(b), rel_tol=_BASE_POINT_RTOL, abs_tol=1e-12
        ):
            off.append(f"{key} ({float(a):.6g} against the committed {float(b):.6g})")
    if off:
        return (
            "A factor-1.0 trial does NOT reproduce the committed case: "
            + "; ".join(off)
            + ". Read the percentiles as a spread around that trial, not the committed case."
        )
    return (
        "A factor-1.0 trial reproduces the committed project IRR, project NPV and minimum "
        "DSCR, so the percentiles are a spread around the committed case."
    )


def _debt_sizing_note(scenario: Mapping[str, Any]) -> Optional[str]:
    """Say so when each trial re-sizes the debt, which damps the minimum DSCR's spread."""
    terms = scenario.get("Financing_Terms")
    sizing = terms.get("debt_sizing") if isinstance(terms, Mapping) else None
    if not sizing:
        return None
    return (
        f"Each trial re-sizes the debt (Financing_Terms.debt_sizing: {sizing}), so the "
        "minimum DSCR moves far less than CAPEX does: extra CAPEX is carried mostly by "
        "equity, and shows in the equity IRR and project NPV rows."
    )


def _capex_mc(
    scenario: Mapping[str, Any],
    committed: Mapping[str, Any],
    band: EstimateClassBand,
    settings: CostStorageSettings,
    capex_mc: Callable[..., Any],
    pipeline: Callable[..., Mapping[str, Any]],
) -> Union[CapexMcBlock, str]:
    from finance.debt_v14 import _extract_capex_usd

    sigma = _sigma(scenario, band)
    if isinstance(sigma, str):
        return sigma
    sigma_pct, basis = sigma
    cfg: Dict[str, Any] = copy.deepcopy(dict(scenario))
    # The lender guard (#1825): no fabricated trials on any Monte Carlo path.
    cfg["monte_carlo"] = {
        **dict(cfg.get("monte_carlo") or {}),
        "allow_toy_fallback": False,
    }
    result = capex_mc(
        cfg,
        n_samples=settings.capex_mc_trials,
        sigma_pct=sigma_pct,
        seed=settings.capex_mc_seed,
    )
    if int(result.n_samples) < LENDER_GRADE_MIN_TRIALS:
        return (
            f"not run: {result.n_samples} trials is under the lender floor of "
            f"{LENDER_GRADE_MIN_TRIALS}"
        )
    base = float(_extract_capex_usd(cfg, include_import_levies=False))
    rows = []
    for attr, kpi, label, unit in _MC_ROWS:
        pct = getattr(result, attr)
        value = base if kpi is None else committed.get(kpi)
        rows.append(
            CapexMcRow(
                label=label,
                unit=unit,
                committed=None if value is None else float(value),
                p10=float(pct["p10"]),
                p50=float(pct["p50"]),
                p90=float(pct["p90"]),
            )
        )
    return CapexMcBlock(
        n_trials=int(result.n_samples),
        seed=int(result.seed),
        sigma_pct=float(result.sigma_pct),
        sigma_basis=basis,
        base_capex_usd=float(result.base_capex_usd),
        rows=rows,
        base_point=_base_point(cfg, base, committed, pipeline),
        debt_sizing_note=_debt_sizing_note(scenario),
    )


def _dispatch(scenario: Mapping[str, Any]) -> Union[DispatchSummary, str]:
    from analytics.storage_dispatch import evaluate_chronological_dispatch

    ledger = evaluate_chronological_dispatch(scenario)
    if ledger is None:
        return (
            "not run: the scenario declares no enabled chronological_dispatch block "
            "(its storage is not dispatched hour by hour)"
        )
    steps = ledger.steps
    return DispatchSummary(
        hours=len(steps),
        charged_mwh=sum(
            s.wind_to_bess_mwh + s.solar_to_bess_mwh + s.grid_to_bess_mwh for s in steps
        ),
        discharged_mwh=sum(s.bess_to_poc_mwh for s in steps),
        exported_mwh=sum(
            s.wind_to_poc_mwh + s.solar_to_poc_mwh + s.bess_to_poc_mwh for s in steps
        ),
        curtailed_mwh=sum(s.wind_curtailed_mwh + s.solar_curtailed_mwh for s in steps),
        losses_mwh=sum(s.charge_loss_mwh + s.discharge_loss_mwh for s in steps),
        unmet_mwh=sum(s.unmet_charge_mwh + s.unmet_discharge_mwh for s in steps),
    )


def _lcos(
    scenario: Mapping[str, Any], result: Mapping[str, Any]
) -> Union[Tuple[List[LcosRow], float], str]:
    from analytics.cost.benchmark import lcos_benchmark
    from finance.bess_lcos import compute_lcos_suite

    rate = (result.get("kpis") or {}).get("discount_rate_used")
    rows_in = result.get("annual_rows") or []
    if rate is None or not rows_in:
        return "not run: the run publishes no discount rate or no operating years"
    suite = compute_lcos_suite(scenario, wacc=float(rate), project_years=len(rows_in))
    if not suite:
        return "not run: the scenario has no battery (no type: bess technology)"
    rows = []
    for res in suite:
        try:
            note: Optional[str] = str(lcos_benchmark(res.lcos_usd_per_mwh)["note"])
        except Exception:  # noqa: BLE001 - the benchmark is advisory only
            note = None
        rows.append(
            LcosRow(
                technology=res.technology,
                lcos_usd_per_mwh=res.lcos_usd_per_mwh,
                pv_costs_usd=res.pv_costs_usd,
                pv_discharged_mwh=res.pv_discharged_mwh,
                cycles_per_year=res.cycles_per_year,
                depth_of_discharge=res.depth_of_discharge,
                round_trip_efficiency=res.round_trip_efficiency,
                benchmark_note=note,
                notes=list(res.notes),
            )
        )
    return rows, float(rate)


def _published(
    result: Mapping[str, Any], key: str, block: str
) -> Union[Mapping[str, Any], str]:
    entry = result.get(key)
    if entry is None:
        return f"not run: the scenario declares no {block} block"
    if not isinstance(entry, Mapping):
        return f"not run: the run's {key} entry is not a mapping"
    status = entry.get("status")
    if status != "run":
        return f"not run: {entry.get('reason') or status}"
    return entry


def _bess_economics(result: Mapping[str, Any]) -> Union[List[BessEconomicsRow], str]:
    entry = _published(result, "bess_project_economics", "bess_economics")
    if isinstance(entry, str):
        return entry
    rows = []
    for p in entry.get("projects") or []:
        landed = p.get("landed_capex") or {}
        rows.append(
            BessEconomicsRow(
                technology=str(p["technology"]),
                landed_capex_usd=landed.get("landed_capex_usd"),
                npv_usd=float(p["npv_usd"]),
                irr_usd=p.get("irr_usd"),
                discount_rate=float(p["discount_rate"]),
                horizon_years=int(p["horizon_years"]),
                currency_basis=str(p["currency_basis"]),
            )
        )
    if not rows:
        return "not run: the run's battery-project economics list no project"
    return rows


def _epc_margin(result: Mapping[str, Any]) -> Union[EpcMarginSummary, str]:
    entry = _published(result, "epc_margin", "epc")
    if isinstance(entry, str):
        return entry
    return EpcMarginSummary(
        contract_value=float(entry["contract_value"]),
        total_cost=float(entry["total_cost"]),
        gross_margin=float(entry["gross_margin"]),
        gross_margin_pct=float(entry["gross_margin_pct"]),
        return_on_cost_pct=float(entry["return_on_cost_pct"]),
        construction_months=int(entry["construction_months"]),
        peak_working_capital=float(entry["peak_working_capital"]),
        annualized_irr=entry.get("annualized_irr"),
        irr_note=entry.get("irr_note"),
    )


def _guarded(label: str, part: Callable[[], Any], not_run: List[str]) -> Any:
    """Run one part; a failure or a 'not run' reason is listed under the part's label."""
    try:
        out = part()
    except Exception as exc:  # noqa: BLE001 - one part never sinks the section
        not_run.append(f"{label}: not run: {type(exc).__name__}: {exc}")
        return None
    if isinstance(out, str):
        not_run.append(f"{label}: {out}")
        return None
    return out


def _default_capex_mc(*args: Any, **kwargs: Any) -> Any:
    from analytics.cost.mc_capex import run_capex_mc

    return run_capex_mc(*args, **kwargs)


def _default_pipeline(**kwargs: Any) -> Mapping[str, Any]:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    return run_v14_pipeline(**kwargs)


def build_cost_storage_section(
    scenario_config_path: Union[str, Path],
    scenario: Mapping[str, Any],
    result: Mapping[str, Any],
    settings: CostStorageSettings,
    *,
    capex_mc: Callable[..., Any] = _default_capex_mc,
    pipeline: Callable[..., Mapping[str, Any]] = _default_pipeline,
) -> Union[CostStorageBlock, str]:
    """Build the cost and storage block, or say why it was not built.

    Args:
        scenario_config_path: The effective scenario the run used (for the record only).
        scenario: The parsed scenario, as authored (the CAPEX Monte Carlo scales its CAPEX).
        result: The finance result the committed case came from.
        settings: ``lender_report.cost_storage``.
        capex_mc, pipeline: Seams for tests; production uses ``run_capex_mc`` and
            ``run_v14_pipeline``.

    Returns:
        The typed block, or a ``"not run: ..."`` reason for "Sections not run". A part that
        cannot run is listed inside the block; the section is not run only when it is
        switched off.
    """
    del scenario_config_path
    if not settings.enabled:
        return (
            f"not run: switched off ({_PREFIX}.enabled is false; the section is opt-in, "
            "#1825)"
        )
    not_run: List[str] = []
    committed = result.get("kpis") or {}
    band = _guarded("Estimate class", lambda: _estimate_class(scenario), not_run)
    mc = None
    if band is not None:
        mc = _guarded(
            "CAPEX Monte Carlo",
            lambda: _capex_mc(scenario, committed, band, settings, capex_mc, pipeline),
            not_run,
        )
    else:
        not_run.append("CAPEX Monte Carlo: not run: no estimate class resolved")
    dispatch = _guarded("Storage dispatch", lambda: _dispatch(scenario), not_run)
    lcos = _guarded("LCOS", lambda: _lcos(scenario, result), not_run)
    bess = _guarded(
        "Battery-project economics", lambda: _bess_economics(result), not_run
    )
    epc = _guarded("EPC margin", lambda: _epc_margin(result), not_run)
    return CostStorageBlock(
        estimate_class=band,
        capex_mc=mc,
        dispatch=dispatch,
        lcos=lcos[0] if lcos else [],
        lcos_discount_rate=lcos[1] if lcos else None,
        bess_economics=bess or [],
        epc_margin=epc,
        parts_not_run=not_run,
    )
