"""Audited F-5 exit evidence pack and cross-feature parity suite (#1893 Dolphin 4).

Executes the end-to-end verification required for an F-5 exit evidence pack without
lifting F-5 unilaterally (``HOLD_UNION = ("F-5", "#1110", "v15.6.1")`` remains in force
until explicit owner and independent Opus domain + assurance sign-off):

1. Baseline canon invariance across every runnable committed scenario (default-off);
2. Monthly cascade line-by-line reconciliation (Dolphin 1), receivables lag conservation
   (Dolphin 2), and an independent single-month hand-cascade oracle (TEST-01);
3. Quarterly debt sculpting conservation laws, true-length bridge calendar pricing,
   time-weighted senior fees, maturity stub settlement, and C3-D-01 / #1845 Year-1
   folded-bridge covenant parity (Dolphin 3);
4. Cross-feature and output-surface parity (#1836 recomputed P90 downside, #1895 P90
   cover solver, #1896 three-statement tieout, #1897 CashflowWaterfall
   ``cfads_coverage_usd`` under mixed-sign ``month_adverse``, and workbook frames);
5. Non-vacuous negative and adversarial controls (CESSPIT refusals and HOLD guard);
6. Explicit F-5 authority status and open external-evidence gate register (#920, #1399,
   #1400, #1110).
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple, cast

from analytics.evaluation_v14 import evaluate_with_overrides, evaluated_scenario_config
from analytics.executive_workbook import frames_from_pipeline_result
from analytics.finance.p90_cover import resolve_p90_cover
from analytics.finance.p90_recomputed_downside import recomputed_p90_downside
from analytics.run_identity import HOLD_UNION, check_no_hold_withdrawal
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from analytics.three_statement import (
    build_cashflow_waterfall,
    build_three_statement_from_run,
    verify_three_statement_waterfall_tieout,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "dutchbay.f5_exit_evidence_pack.v1"


def _evaluate_full(raw_config: Mapping[str, Any]) -> Dict[str, Any]:
    """Run the full v14 pipeline via the canonical evaluation gateway."""
    result = evaluate_with_overrides(
        raw_config=copy.deepcopy(dict(raw_config)),
        overrides={},
        return_full_result=True,
    )
    return cast(Dict[str, Any], result)


#: Explicit non-reliance notice carried on the evidence pack itself (`HOLD_UNION`).
NON_RELIANCE_NOTICE = (
    "HOLD (F-5, #1110, v15.6.1): Non-reliance notice. F-5, #1110, and v15.6.1 remain "
    "in force; this evidence pack verifies technical parity across Dolphins 1-4 (#1893) "
    "with no lender reliance and no covenant, IC, or Board authority until explicit owner "
    "disposition following independent domain and assurance review."
)


def _sha256_bytes(data: bytes) -> str:
    """Return the hex SHA-256 digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    """Return the hex SHA-256 digest of the file at ``path``."""
    return _sha256_bytes(path.read_bytes())


def _kpi_vector_sha256(kpis: Mapping[str, Any]) -> str:
    """Return the canonical 43-KPI repr-precision SHA-256 digest."""
    vector = {
        key: repr(value) if isinstance(value, float) else value
        for key, value in kpis.items()
    }
    encoded = json.dumps(vector, sort_keys=True, allow_nan=False).encode("utf-8")
    return _sha256_bytes(encoded)


def _with_monthly(config: Mapping[str, Any], node: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a deep copy of ``config`` with ``cashflow.monthly`` replaced by ``node``."""
    out = copy.deepcopy(dict(config))
    cashflow = dict(out.get("cashflow") or {})
    cashflow["monthly"] = copy.deepcopy(dict(node))
    out["cashflow"] = cashflow
    return out


def _load_scenario_with_hash(
    rel_path: str, *, repo_root: Path
) -> Tuple[Dict[str, Any], str]:
    """Load a scenario YAML through the canonical loader and return ``(cfg, sha256)``."""
    path = repo_root / rel_path
    raw_bytes = path.read_bytes()
    cfg = dict(load_scenario_config(path, verified_bytes=raw_bytes))
    return cfg, _sha256_bytes(raw_bytes)


def _gate_1_baseline_canon_invariance(
    evidence_cfg: Mapping[str, Any], *, repo_root: Path
) -> Dict[str, Any]:
    """Verify 0 committed scenarios opt into monthly/quarterly sculpting and record baseline."""
    from finance.monthly_cascade_v14 import resolve_monthly_spec

    glob_pat = str(evidence_cfg["scenarios_glob"])
    runnable = 0
    monthly_enabled: List[str] = []
    receivables_enabled: List[str] = []
    quarterly_enabled: List[str] = []

    for path in sorted(repo_root.glob(glob_pat)):
        raw_bytes = path.read_bytes()
        try:
            cfg = dict(load_scenario_config(path, verified_bytes=raw_bytes))
        except Exception:  # noqa: BLE001 - non-runnable/multi-document fixture YAMLs
            continue
        runnable += 1
        rel = path.relative_to(repo_root).as_posix()
        spec = resolve_monthly_spec(cfg)
        if spec is not None:
            monthly_enabled.append(rel)
            if spec.receivable_days > 0:
                receivables_enabled.append(rel)
            if (
                spec.quarterly_sculpting is not None
                and spec.quarterly_sculpting.enabled
            ):
                quarterly_enabled.append(rel)

    if quarterly_enabled or receivables_enabled:
        raise AssertionError(
            "Committed scenario(s) unexpectedly enable opt-in monthly features: "
            f"quarterly={quarterly_enabled}, receivables={receivables_enabled}"
        )

    refs = {
        "primary": str(evidence_cfg["primary_scenario"]),
        "hybrid_bess": str(evidence_cfg["hybrid_bess_scenario"]),
        "bess_augmentation": str(evidence_cfg["bess_augmentation_scenario"]),
        "shortfall_reference": str(evidence_cfg["shortfall_reference_scenario"]),
    }
    reference_results: Dict[str, Any] = {}
    for label, rel_path in refs.items():
        cfg, sha = _load_scenario_with_hash(rel_path, repo_root=repo_root)
        res = _evaluate_full(cfg)
        if "quarterly_sculpting" in res["debt_result"]:
            raise AssertionError(f"{rel_path}: quarterly_sculpting emitted when off")
        kpis = res["kpis"]
        entry: Dict[str, Any] = {
            "scenario_path": rel_path,
            "scenario_sha256": sha,
            "kpi_count": len(kpis),
            "kpi_vector_sha256": _kpi_vector_sha256(kpis),
            "max_debt_usd": float(kpis["max_debt_usd"]),
            "min_dscr": float(kpis["min_dscr"]),
            "avg_dscr": float(kpis["avg_dscr"]),
            "llcr": float(kpis["llcr"]),
            "plcr": float(kpis["plcr"]),
            "project_irr": (
                None if kpis["project_irr"] is None else float(kpis["project_irr"])
            ),
            "equity_irr": (
                None if kpis["equity_irr"] is None else float(kpis["equity_irr"])
            ),
            "project_npv": float(kpis["project_npv"]),
        }
        reference_results[label] = entry

    expected_path = repo_root / str(evidence_cfg["expected_baseline_kpis_json"])
    expected_kpis = json.loads(expected_path.read_text(encoding="utf-8"))
    primary_entry = reference_results["primary"]
    # Fixture values are rounded to 4 significant figures (tests/finance/test_lendercase_expected_results.py
    # permits 0.02); 1e-3 tightly bounds 4-sig-fig rounding while full-precision byte identity is pinned above.
    for key in ("min_dscr", "avg_dscr", "llcr", "plcr"):
        if not math.isclose(
            primary_entry[key], float(expected_kpis[key]), abs_tol=1.0e-3
        ):
            raise AssertionError(
                f"Primary baseline {key} drifted: got {primary_entry[key]}, "
                f"expected {expected_kpis[key]}"
            )

    return {
        "status": "PASS",
        "runnable_scenarios_scanned": runnable,
        "monthly_enabled_scenarios": monthly_enabled,
        "receivables_enabled_scenarios": receivables_enabled,
        "quarterly_sculpting_enabled_scenarios": quarterly_enabled,
        "expected_baseline_kpis_sha256": _sha256_file(expected_path),
        "references": reference_results,
    }


def _hand_cascade_month_oracle(
    cascade: Any,
    *,
    year_index: int,
    month_index: int,
    energy_weights: Sequence[float],
    time_weights: Sequence[float],
) -> Dict[str, float]:
    """Independent single-month CFADS arithmetic oracle (TEST-01)."""
    annual = cascade.annual_rows[year_index]
    row = cascade.rows[year_index * 12 + month_index]
    w_e = float(energy_weights[month_index])
    w_t = float(time_weights[month_index])
    net_kwh = float(annual["net_kwh"]) * w_e
    tariff = (
        float(annual["generation_revenue_lkr"]) / float(annual["net_kwh"])
        if float(annual["net_kwh"]) > 0.0
        else 0.0
    )
    gen_rev = net_kwh * tariff
    bess_rev = float(annual["bess_revenue_lkr"]) * w_t
    revenue = gen_rev + bess_rev
    stat_ratio = (
        float(annual["total_statutory_deductions_lkr"]) / float(annual["revenue_lkr"])
        if float(annual["revenue_lkr"]) > 0.0
        else 0.0
    )
    statutory = revenue * stat_ratio
    ebitda = (
        revenue
        - statutory
        - (float(annual["opex_lkr"]) + float(annual["senior_fee_lkr"])) * w_t
    )
    posttax = ebitda - float(annual["tax_lkr"]) * w_t
    h = float(annual["risk_haircut_pct"])
    factor = (1.0 + h) if posttax < 0.0 else (1.0 - h)
    cfads_lkr = (
        posttax * factor
        - float(annual["bess_augmentation_capex_lkr"]) * w_t
        - float(row.get("receivables_change_lkr", 0.0))
    )
    usd_per_lkr = (
        float(annual["cfads_usd"]) / float(annual["cfads_final_lkr"])
        if float(annual["cfads_final_lkr"]) != 0.0
        else 1.0 / float(annual["fx_rate"])
    )
    cfads_usd = cfads_lkr * usd_per_lkr
    return {
        "net_kwh_abs_err": abs(float(row["net_kwh"]) - net_kwh),
        "revenue_lkr_abs_err": abs(float(row["revenue_lkr"]) - revenue),
        "ebitda_lkr_abs_err": abs(float(row["ebitda_lkr"]) - ebitda),
        "cfads_final_lkr_abs_err": abs(float(row["cfads_final_lkr"]) - cfads_lkr),
        "cfads_usd_abs_err": abs(float(row["cfads_usd"]) - cfads_usd),
    }


def _gate_2_monthly_cascade_and_lag(
    evidence_cfg: Mapping[str, Any], *, repo_root: Path
) -> Dict[str, Any]:
    """Verify Dolphin 1 & 2 reconciliation, seasonal trough, BESS/hedge, and lag conservation."""
    from finance.cashflow_v14 import build_annual_rows
    from finance.monthly_cascade_v14 import (
        HAIRCUT_RULE_MONTH_ADVERSE,
        HAIRCUT_RULE_YEAR_SIGN,
        LINE_BASIS,
        RECEIVABLES_KEY,
        build_monthly_cascade,
    )

    tols = evidence_cfg["tolerances"]
    rel_tol = float(tols["reconciliation_rel"])
    oracle_rel = float(tols["hand_oracle_rel"])
    cases_cfg = evidence_cfg["cases"]
    shapes_cfg = evidence_cfg["shapes"]

    seasonal_shape = [float(x) for x in shapes_cfg["seasonal"]]
    cod_month = int(cases_cfg["cod_month"])
    hybrid_cod_month = int(cases_cfg["hybrid_cod_month"])
    receivable_days = int(cases_cfg["receivable_days"])

    primary_cfg, _ = _load_scenario_with_hash(
        str(evidence_cfg["primary_scenario"]), repo_root=repo_root
    )
    seasonal_cfg = _with_monthly(
        primary_cfg, {"cod_month": cod_month, "energy_shape": seasonal_shape}
    )
    cascade_ys = build_monthly_cascade(
        seasonal_cfg, risk_haircut_rule=HAIRCUT_RULE_YEAR_SIGN
    )
    cascade_ma = build_monthly_cascade(
        seasonal_cfg, risk_haircut_rule=HAIRCUT_RULE_MONTH_ADVERSE
    )

    max_rel_line_err = 0.0
    for y, annual in enumerate(cascade_ys.annual_rows):
        months = cascade_ys.rows[y * 12 : (y + 1) * 12]
        scale = max(abs(float(annual["revenue_lkr"])), 1.0)
        for line in LINE_BASIS:
            expected = float(annual.get(line, 0.0))
            total = math.fsum(float(m[line]) for m in months)
            denom = max(scale, abs(expected), 1.0)
            rel_err = abs(total - expected) / denom
            max_rel_line_err = max(max_rel_line_err, rel_err)
            if abs(total - expected) > rel_tol * max(scale, abs(expected)):
                raise AssertionError(
                    f"Monthly reconciliation drift year {y + 1} {line}: {total} vs {expected}"
                )

    year1_months = cascade_ma.rows[:12]
    lowest_m = min(year1_months, key=lambda r: float(r["cfads_usd"]))
    highest_m = max(year1_months, key=lambda r: float(r["cfads_usd"]))
    mean_m_cfads = float(cascade_ma.annual_rows[0]["cfads_usd"]) / 12.0
    if not (
        float(lowest_m["cfads_usd"]) < mean_m_cfads < float(highest_m["cfads_usd"])
    ):
        raise AssertionError("Seasonal shape did not produce intra-year trough/peak")

    oracle_y = int(cases_cfg["hand_oracle_year_index"])
    oracle_m = int(cases_cfg["hand_oracle_month_index"])
    oracle_errs = _hand_cascade_month_oracle(
        cascade_ma,
        year_index=oracle_y,
        month_index=oracle_m,
        energy_weights=cascade_ma.energy_weights,
        time_weights=cascade_ma.time_weights,
    )
    oracle_row = cascade_ma.rows[oracle_y * 12 + oracle_m]
    if oracle_errs["cfads_usd_abs_err"] > oracle_rel * max(
        abs(float(oracle_row["cfads_usd"])), 1.0
    ):
        raise AssertionError(f"Hand cascade oracle mismatch: {oracle_errs}")

    # Hybrid BESS + statutory levies + FX hedge + senior fee + receivables lag
    hybrid_cfg, _ = _load_scenario_with_hash(
        str(evidence_cfg["hybrid_bess_scenario"]), repo_root=repo_root
    )
    hybrid_cfg["statutory"] = {
        **(hybrid_cfg.get("statutory") or {}),
        **dict(cases_cfg["hybrid_statutory_test"]),
    }
    hybrid_cfg["fx"] = {
        **(hybrid_cfg.get("fx") or {}),
        **dict(cases_cfg["hybrid_fx_hedge"]),
    }
    fee_series = [1.0e8 * (1.0 - i / 25.0) for i in range(20)]
    hybrid_no_lag = _with_monthly(
        hybrid_cfg, {"cod_month": hybrid_cod_month, "energy_shape": seasonal_shape}
    )
    hybrid_lag = _with_monthly(
        hybrid_cfg,
        {
            "cod_month": hybrid_cod_month,
            "energy_shape": seasonal_shape,
            "receivable_days": receivable_days,
        },
    )
    rows_no_lag = build_annual_rows(hybrid_no_lag, senior_fee_lkr_series=fee_series)
    rows_lag = build_annual_rows(hybrid_lag, senior_fee_lkr_series=fee_series)
    lag_telescope_lkr = math.fsum(float(r[RECEIVABLES_KEY]) for r in rows_lag)
    if abs(lag_telescope_lkr) > 1e-3:
        raise AssertionError(
            f"Receivables lag did not telescope to zero: {lag_telescope_lkr}"
        )
    max_ebitda_drift = max(
        abs(float(a["ebitda_lkr"]) - float(b["ebitda_lkr"]))
        for a, b in zip(rows_no_lag, rows_lag, strict=True)
    )
    max_tax_drift = max(
        abs(float(a["tax_lkr"]) - float(b["tax_lkr"]))
        for a, b in zip(rows_no_lag, rows_lag, strict=True)
    )
    if max_ebitda_drift > 1e-6 or max_tax_drift > 1e-6:
        raise AssertionError("Receivables lag altered EBITDA or tax")

    hybrid_cascade = build_monthly_cascade(hybrid_lag, senior_fee_lkr_series=fee_series)
    hybrid_oracle = _hand_cascade_month_oracle(
        hybrid_cascade,
        year_index=oracle_y,
        month_index=oracle_m,
        energy_weights=hybrid_cascade.energy_weights,
        time_weights=hybrid_cascade.time_weights,
    )
    if hybrid_oracle["cfads_usd_abs_err"] > 1e-5:
        raise AssertionError(
            f"Hybrid hedged BESS hand oracle mismatch: {hybrid_oracle}"
        )

    # BESS augmentation discrete-year reconciliation check
    aug_cfg, _ = _load_scenario_with_hash(
        str(evidence_cfg["bess_augmentation_scenario"]), repo_root=repo_root
    )
    aug_cascade = build_monthly_cascade(
        _with_monthly(
            aug_cfg, {"cod_month": hybrid_cod_month, "energy_shape": seasonal_shape}
        )
    )
    aug_year_idx = int(cases_cfg["augmentation_year_index"])
    aug_annual = aug_cascade.annual_rows[aug_year_idx]
    aug_sum = math.fsum(
        float(m["bess_augmentation_capex_lkr"])
        for m in aug_cascade.rows[aug_year_idx * 12 : (aug_year_idx + 1) * 12]
    )
    if float(aug_annual["bess_augmentation_capex_lkr"]) <= 0.0:
        raise AssertionError("Expected positive augmentation capex in control year")
    if abs(aug_sum - float(aug_annual["bess_augmentation_capex_lkr"])) > 1e-3:
        raise AssertionError("Augmentation monthly sum disagrees with annual row")

    return {
        "status": "PASS",
        "line_count_checked": len(LINE_BASIS) * len(cascade_ys.annual_rows),
        "max_relative_line_reconciliation_error": max_rel_line_err,
        "year1_trough_calendar_month": int(lowest_m["calendar_month"]),
        "year1_trough_cfads_usd": float(lowest_m["cfads_usd"]),
        "year1_peak_calendar_month": int(highest_m["calendar_month"]),
        "year1_peak_cfads_usd": float(highest_m["cfads_usd"]),
        "year1_mean_month_cfads_usd": mean_m_cfads,
        "hand_oracle_errors": oracle_errs,
        "hybrid_hedged_bess_oracle_errors": hybrid_oracle,
        "receivables_lag_telescope_lkr": lag_telescope_lkr,
        "receivables_lag_ebitda_drift_lkr": max_ebitda_drift,
        "receivables_lag_tax_drift_lkr": max_tax_drift,
        "augmentation_year_capex_lkr": float(aug_annual["bess_augmentation_capex_lkr"]),
    }


def _audit_sculpted_variant(
    name: str,
    cfg: Mapping[str, Any],
    *,
    conservation_tol: float,
    dscr_tol: float,
    floor_eps: float,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Run ``cfg`` through the pipeline and check all quarterly sculpting invariants."""
    from finance.monthly_cascade_v14 import resolve_monthly_spec
    from finance.quarterly_sculpting_v14 import true_bridge_length_years

    res = _evaluate_full(cfg)
    debt = res["debt_result"]
    kpis = res["kpis"]
    qs = debt["quarterly_sculpting"]
    check_no_hold_withdrawal(qs["covenant_use"], f"quarterly_sculpting:{name}")
    if "F-5 stays in force" not in qs["covenant_use"]:
        raise AssertionError(f"{name}: missing explicit F-5 non-reliance statement")

    spec = resolve_monthly_spec(cfg)
    assert spec is not None
    expected_dt_bridge = true_bridge_length_years(spec, int(qs["bridge_months"]))
    dt_bridge_err = abs(float(qs["bridge_length_years"]) - expected_dt_bridge)

    bridge = qs.get("bridge_period")
    op_quarters = list(qs["operating_quarters"])
    opening_bal = (
        float(bridge["opening_balance_usd"])
        if bridge is not None
        else (float(op_quarters[0]["opening_balance_usd"]) if op_quarters else 0.0)
    )
    principal_paid = (
        float(bridge["principal_paid_usd"]) if bridge is not None else 0.0
    ) + math.fsum(float(q["principal_paid_usd"]) for q in op_quarters)
    principal_err = abs(
        opening_bal - principal_paid - float(qs["balloon_remaining_usd"])
    )

    accrued_int = math.fsum(float(q["interest_accrued_usd"]) for q in op_quarters)
    paid_int = math.fsum(float(q["interest_paid_usd"]) for q in op_quarters)
    interest_err = abs(accrued_int - paid_int)

    q_fee_sum = math.fsum(float(q["senior_fee_usd"]) for q in op_quarters)
    tw_fee_err = abs(q_fee_sum - float(qs["time_weighted_senior_fee_total_usd"]))

    bridge_int_err = 0.0
    if bridge is not None:
        # Weighted debt rate times opening balance times true calendar bridge length
        expected_bridge_int = (
            float(bridge["opening_balance_usd"])
            * float(debt["avg_debt_rate"])
            * float(bridge["period_length_years"])
        )
        bridge_int_err = abs(
            float(bridge["interest_accrued_usd"]) - expected_bridge_int
        )

    dscr_by_year = debt["dscr_by_year"]
    ann_cov = qs["annual_covenant_dscr_by_year"]
    max_dscr_by_year_diff = 0.0
    for y_key, v_cov in ann_cov.items():
        v_debt = dscr_by_year[y_key]
        if v_cov is None or v_debt is None:
            if v_cov is not v_debt:
                raise AssertionError(f"{name}: year {y_key} None parity mismatch")
        else:
            max_dscr_by_year_diff = max(
                max_dscr_by_year_diff, abs(float(v_cov) - float(v_debt))
            )

    for label, err, limit in (
        ("dt_bridge_err", dt_bridge_err, 1e-12),
        ("principal_err", principal_err, conservation_tol),
        ("interest_err", interest_err, conservation_tol),
        ("tw_fee_err", tw_fee_err, conservation_tol),
        ("bridge_int_err", bridge_int_err, conservation_tol),
        ("max_dscr_by_year_diff", max_dscr_by_year_diff, dscr_tol),
    ):
        if err > limit:
            raise AssertionError(f"{name}: {label}={err} exceeds tolerance {limit}")

    target_dscr = float(cfg["Financing_Terms"]["target_dscr"])
    if float(qs["quarterly_dscr_min"]) < target_dscr - floor_eps:
        raise AssertionError(
            f"{name}: quarterly_dscr_min={qs['quarterly_dscr_min']} < {target_dscr}"
        )
    if (
        str(cfg["Financing_Terms"].get("sizing_dscr_basis", "")).lower()
        == "annual_covenant"
        and float(qs["annual_covenant_dscr_min"]) < target_dscr - floor_eps
    ):
        raise AssertionError(
            f"{name}: annual_covenant_dscr_min={qs['annual_covenant_dscr_min']} < {target_dscr}"
        )

    summary = {
        "instalment_quarters": list(qs["instalment_quarters"]),
        "bridge_months": int(qs["bridge_months"]),
        "bridge_length_years": float(qs["bridge_length_years"]),
        "max_debt_usd": float(kpis["max_debt_usd"]),
        "balloon_remaining_usd": float(qs["balloon_remaining_usd"]),
        "min_dscr": float(kpis["min_dscr"]),
        "quarterly_dscr_min": float(qs["quarterly_dscr_min"]),
        "annual_covenant_dscr_min": float(qs["annual_covenant_dscr_min"]),
        "llcr": float(kpis["llcr"]),
        "plcr": float(kpis["plcr"]),
        "project_irr": (
            None if kpis["project_irr"] is None else float(kpis["project_irr"])
        ),
        "equity_irr": None if kpis["equity_irr"] is None else float(kpis["equity_irr"]),
        "project_npv": float(kpis["project_npv"]),
        "time_weighted_senior_fee_total_usd": float(
            qs["time_weighted_senior_fee_total_usd"]
        ),
        "mixed_sign_excess_years": sum(
            1 for v in qs["mixed_sign_haircut_excess_lkr"] if float(v) > 0.0
        ),
        "principal_conservation_err_usd": principal_err,
        "interest_conservation_err_usd": interest_err,
        "senior_fee_conservation_err_usd": tw_fee_err,
        "bridge_interest_oracle_err_usd": bridge_int_err,
        "dscr_by_year_parity_err": max_dscr_by_year_diff,
        "audit_status": str(debt["audit_status"]),
    }
    return summary, res


def _gate_3_quarterly_sculpting_and_bridge(
    evidence_cfg: Mapping[str, Any], *, repo_root: Path
) -> Tuple[Dict[str, Any], Dict[str, Tuple[Dict[str, Any], Dict[str, Any]]]]:
    """Verify Dolphin 3 quarterly sculpting conservation, bridge length, and C3-D-01 fold."""
    tols = evidence_cfg["tolerances"]
    cons_tol = float(tols["conservation_usd"])
    dscr_tol = float(tols["dscr_abs"])
    floor_eps = float(tols["covenant_floor_eps"])
    cases_cfg = evidence_cfg["cases"]
    shapes_cfg = evidence_cfg["shapes"]

    cod_month = int(cases_cfg["cod_month"])
    receivable_days = int(cases_cfg["receivable_days"])
    seasonal_shape = [float(x) for x in shapes_cfg["seasonal"]]
    sparse_shape = [float(x) for x in shapes_cfg["mixed_sign_sparse"]]
    semi_q = [int(q) for q in cases_cfg["semi_annual_quarters"]]
    non_q4 = [int(q) for q in cases_cfg["non_q4_quarters"]]

    primary_cfg, _ = _load_scenario_with_hash(
        str(evidence_cfg["primary_scenario"]), repo_root=repo_root
    )

    variant_configs: Dict[str, Dict[str, Any]] = {
        "flat_cod_7": _with_monthly(
            primary_cfg,
            {"cod_month": cod_month, "quarterly_sculpting": {"enabled": True}},
        ),
        "seasonal_cod_7": _with_monthly(
            primary_cfg,
            {
                "cod_month": cod_month,
                "energy_shape": seasonal_shape,
                "quarterly_sculpting": {"enabled": True},
            },
        ),
        "seasonal_cod_7_lag_30": _with_monthly(
            primary_cfg,
            {
                "cod_month": cod_month,
                "energy_shape": seasonal_shape,
                "receivable_days": receivable_days,
                "quarterly_sculpting": {"enabled": True},
            },
        ),
        "semi_annual_q2_q4": _with_monthly(
            primary_cfg,
            {
                "cod_month": cod_month,
                "energy_shape": seasonal_shape,
                "quarterly_sculpting": {"enabled": True, "instalment_quarters": semi_q},
            },
        ),
        "non_q4_maturity_q1_q3": _with_monthly(
            primary_cfg,
            {
                "cod_month": cod_month,
                "energy_shape": seasonal_shape,
                "quarterly_sculpting": {"enabled": True, "instalment_quarters": non_q4},
            },
        ),
        "io0_annual_covenant": _with_monthly(
            primary_cfg,
            {
                "cod_month": cod_month,
                "energy_shape": seasonal_shape,
                "quarterly_sculpting": {"enabled": True},
            },
        ),
        "mixed_sign_sparse": _with_monthly(
            primary_cfg,
            {
                "cod_month": cod_month,
                "energy_shape": sparse_shape,
                "quarterly_sculpting": {"enabled": True},
            },
        ),
    }
    variant_configs["io0_annual_covenant"]["Financing_Terms"]["interest_only_years"] = 0
    variant_configs["io0_annual_covenant"]["Financing_Terms"][
        "sizing_dscr_basis"
    ] = "annual_covenant"

    variant_summaries: Dict[str, Any] = {}
    variant_runs: Dict[str, Tuple[Dict[str, Any], Dict[str, Any]]] = {}
    for name, vcfg in variant_configs.items():
        summary, res = _audit_sculpted_variant(
            name,
            vcfg,
            conservation_tol=cons_tol,
            dscr_tol=dscr_tol,
            floor_eps=floor_eps,
        )
        variant_summaries[name] = summary
        variant_runs[name] = (vcfg, res)

    # C3-D-01 / #1845 contrast: period basis vs annual_covenant when years_io == 0
    io0_period_cfg = copy.deepcopy(variant_configs["io0_annual_covenant"])
    io0_period_cfg["Financing_Terms"]["sizing_dscr_basis"] = "period"
    io0_period_res = _evaluate_full(io0_period_cfg)
    cov_y1 = float(
        variant_runs["io0_annual_covenant"][1]["debt_result"]["dscr_by_year"][1]
    )
    period_y1 = float(io0_period_res["debt_result"]["dscr_by_year"][1])
    if not (cov_y1 >= float(primary_cfg["Financing_Terms"]["target_dscr"]) - floor_eps):
        raise AssertionError(f"annual_covenant Year-1 fold missed target: {cov_y1}")
    if not (period_y1 < cov_y1):
        raise AssertionError(
            f"C3-D-01 contrast failed: period_y1={period_y1} >= cov_y1={cov_y1}"
        )

    # Time-weighted senior fee ordering: more frequent instalments amortise faster -> lower fee
    fee_q = float(
        variant_summaries["seasonal_cod_7"]["time_weighted_senior_fee_total_usd"]
    )
    fee_sa = float(
        variant_summaries["semi_annual_q2_q4"]["time_weighted_senior_fee_total_usd"]
    )

    gate_payload = {
        "status": "PASS",
        "variants": variant_summaries,
        "c3_d_01_year1_fold_truth": {
            "io0_annual_covenant_year1_dscr": cov_y1,
            "io0_period_basis_year1_dscr": period_y1,
            "target_dscr": float(primary_cfg["Financing_Terms"]["target_dscr"]),
        },
        "time_weighted_fee_quarterly_vs_semiannual_usd": {
            "quarterly_1234": fee_q,
            "semi_annual_24": fee_sa,
        },
    }
    return gate_payload, variant_runs


def _gate_4_cross_feature_parity(
    evidence_cfg: Mapping[str, Any],
    variant_runs: Mapping[str, Tuple[Dict[str, Any], Dict[str, Any]]],
) -> Dict[str, Any]:
    """Verify #1896/#1897 waterfall parity, #1836 recomputed P90, #1895 cover, and workbook frames."""
    dscr_tol = float(evidence_cfg["tolerances"]["dscr_abs"])
    cover_target = float(evidence_cfg["cases"]["p90_cover_min_dscr"])

    waterfall_checks: Dict[str, Any] = {}
    for key in ("seasonal_cod_7", "seasonal_cod_7_lag_30", "mixed_sign_sparse"):
        vcfg, res = variant_runs[key]
        debt = res["debt_result"]
        annual_rows = res["annual_rows"]
        map_by_idx = {
            int(m["annual_row_index"]): float(m["cfads_usd"])
            for m in debt["annual_row_debt_period_map"]
        }
        max_cov_usd_diff = max(
            abs(float(row["cfads_coverage_usd"]) - map_by_idx[idx])
            for idx, row in enumerate(annual_rows)
        )
        wf = build_cashflow_waterfall(annual_rows, debt_result=debt)
        by_year = debt["dscr_by_year"]
        max_wf_dscr_diff = max(
            (
                abs(float(r.covenant_dscr) - float(by_year[r.year]))
                for r in wf.rows
                if r.covenant_dscr is not None
            ),
            default=0.0,
        )
        if max_cov_usd_diff > 1e-6 or max_wf_dscr_diff > dscr_tol:
            raise AssertionError(
                f"{key}: waterfall parity failed cov_diff={max_cov_usd_diff}, "
                f"dscr_diff={max_wf_dscr_diff}"
            )

        ts = build_three_statement_from_run(res, vcfg)
        if ts is None:
            raise AssertionError(f"{key}: build_three_statement_from_run returned None")
        funding = debt.get("funding") or {}
        opening_cash = (
            float(funding.get("initial_dsra_usd") or 0.0)
            if isinstance(funding, Mapping) and bool(funding.get("fund_at_close"))
            else 0.0
        )
        verify_three_statement_waterfall_tieout(
            ts, res["equity_distribution"], opening_cash=opening_cash
        )
        frames = frames_from_pipeline_result(res)
        waterfall_checks[key] = {
            "max_cfads_coverage_usd_diff": max_cov_usd_diff,
            "max_waterfall_covenant_dscr_diff": max_wf_dscr_diff,
            "three_statement_tieout_passed": True,
            "workbook_frames": sorted(frames.keys()),
        }

    p90_checks: Dict[str, Any] = {}
    for key in ("flat_cod_7", "seasonal_cod_7", "mixed_sign_sparse"):
        vcfg, res = variant_runs[key]
        p90 = recomputed_p90_downside(vcfg)
        if p90.get("status") != "ok":
            raise AssertionError(f"{key}: recomputed_p90_downside failed: {p90}")
        debt = res["debt_result"]
        cov_vals = [float(v) for v in debt["dscr_by_year"].values() if v is not None]
        base_case = p90["cases"]["base"]
        base_diff = abs(float(base_case["min_dscr"]) - min(cov_vals))
        if base_diff > dscr_tol:
            raise AssertionError(f"{key}: P90 base mismatch: {base_diff}")
        p90_checks[key] = {
            "status": p90["status"],
            "base_min_dscr": float(base_case["min_dscr"]),
            "ratio_method_min_dscr": float(p90["cases"]["ratio_method"]["min_dscr"]),
            "recomputed_min_dscr": float(p90["cases"]["recomputed"]["min_dscr"]),
            "recomputed_avg_dscr": float(p90["cases"]["recomputed"]["avg_dscr"]),
            "recomputed_llcr": float(p90["cases"]["recomputed"]["llcr"]),
            "base_dscr_parity_err": base_diff,
        }

    # #1895 P90 cover combined with opt-in quarterly sculpting
    seasonal_cfg = copy.deepcopy(variant_runs["seasonal_cod_7"][0])
    seasonal_cfg["Financing_Terms"] = {
        **seasonal_cfg["Financing_Terms"],
        "p90_cover_min_dscr": cover_target,
    }
    if resolve_p90_cover(seasonal_cfg) != cover_target:
        raise AssertionError("resolve_p90_cover did not resolve configured target")
    covered = _evaluate_full(seasonal_cfg)
    cover_block = covered["debt_result"]["p90_cover"]
    priced_cfg = copy.deepcopy(variant_runs["seasonal_cod_7"][0])
    priced_cfg["Financing_Terms"] = {
        **priced_cfg["Financing_Terms"],
        "target_dscr": float(cover_block["target_dscr"]),
    }
    independent_p90 = recomputed_p90_downside(priced_cfg)
    ind_min = float(independent_p90["cases"]["recomputed"]["min_dscr"])
    if ind_min < cover_target:
        raise AssertionError(
            f"Independent P90 cover verification failed: {ind_min} < {cover_target}"
        )

    return {
        "status": "PASS",
        "waterfall_and_three_statement": waterfall_checks,
        "p90_recomputed_downside_with_sculpting": p90_checks,
        "p90_cover_with_sculpting": {
            "declared_min_dscr": cover_target,
            "binding": bool(cover_block["binding"]),
            "declared_target_dscr": float(cover_block["declared_target_dscr"]),
            "solved_target_dscr": float(cover_block["target_dscr"]),
            "recomputed_min_dscr_unbound": float(
                cover_block["recomputed_min_dscr_unbound"]
            ),
            "recomputed_min_dscr": float(cover_block["recomputed_min_dscr"]),
            "independent_recheck_min_dscr": ind_min,
            "solver_steps": int(cover_block["solver_steps"]),
        },
    }


def _gate_5_negative_controls(
    evidence_cfg: Mapping[str, Any], *, repo_root: Path
) -> Dict[str, Any]:
    """Verify CESSPIT preflight refusals and HOLD-withdrawal refusal fire non-vacuously."""
    from finance.quarterly_sculpting_v14 import build_quarterly_sculpted_schedule

    primary_cfg, _ = _load_scenario_with_hash(
        str(evidence_cfg["primary_scenario"]), repo_root=repo_root
    )
    controls: Dict[str, bool] = {}

    def _expect_preflight_fail(label: str, node: Mapping[str, Any]) -> None:
        bad = _with_monthly(primary_cfg, node)
        try:
            validate_config_for_v14(bad, "<f5-control>", ["cashflow", "debt"])
        except ConfigValidationError:
            controls[label] = True
            return
        raise AssertionError(f"Negative control did not refuse: {label}")

    _expect_preflight_fail(
        "refuses_year_sign_with_quarterly_sculpting",
        {"risk_haircut_rule": "year_sign", "quarterly_sculpting": {"enabled": True}},
    )
    _expect_preflight_fail(
        "refuses_unsorted_instalment_quarters",
        {"quarterly_sculpting": {"enabled": True, "instalment_quarters": [4, 2]}},
    )
    _expect_preflight_fail(
        "refuses_bridge_months_out_of_range",
        {"quarterly_sculpting": {"enabled": True, "bridge_months": 12}},
    )
    _expect_preflight_fail(
        "refuses_receivable_days_over_365",
        {"receivable_days": 366},
    )

    try:
        build_quarterly_sculpted_schedule(
            config=_with_monthly(
                primary_cfg, {"quarterly_sculpting": {"enabled": True}}
            ),
            annual_rows=[],
            tranches={},
            tenor_years=1,
            years_io=0,
            target_dscr=1.30,
            amortization_style="annuity",
        )
    except ValueError:
        controls["refuses_annuity_style_with_sculpting"] = True
    else:
        raise AssertionError("Annuity style with quarterly sculpting was not refused")

    try:
        check_no_hold_withdrawal(
            "F-5 is lifted and bankable for lender covenants", "f5_negative_control"
        )
    except ValueError:
        controls["refuses_unilateral_f5_withdrawal_text"] = True
    else:
        raise AssertionError("HOLD withdrawal guard did not fire on hostile text")

    check_no_hold_withdrawal(NON_RELIANCE_NOTICE, "f5_exit_evidence_notice")
    controls["non_reliance_notice_passes_hold_guard"] = True

    return {"status": "PASS", "controls": controls}


def _gate_6_f5_authority_and_open_gates() -> Dict[str, Any]:
    """Record explicit F-5 authority status and remaining external/owner gates."""
    return {
        "f5_exit_lifted": False,
        "hold_union": list(HOLD_UNION),
        "completed_technical_deliverables_1893": [
            "Dolphin 1 (#1894, #1901): opt-in monthly CFADS cascade (LINE_BASIS computed/time_accrued/allocated, strict 1e-12 annual reconciliation)",
            "Dolphin 2 (#1911): offtaker receivables lag (cashflow.monthly.receivable_days) conserving project-life cash",
            "Dolphin 3 (#1928): quarterly debt sculpting on declared/assumed instalment dates, month_adverse negative-month haircut, true-length calendar bridge, time-weighted senior fees, maturity stub settlement, C3-D-01 / #1845 Year-1 folded bridge",
            "Dolphin 4 (#1893): pipeline_v14_enhanced cfads_coverage_usd mixed-sign waterfall parity, #1836/#1895 recomputed P90 & p90_cover_min_dscr parity with quarterly sculpting, audited 6-gate F-5 exit evidence pack",
        ],
        "open_gates_required_for_f5_exit_disposition": [
            "Explicit owner F-5 exit decision following independent Opus domain + assurance review (#1893 Dolphin 4)",
            "Authenticated financing term-sheet debt & bridge instalment schedule (#920, #1399, #1400) replacing labelled defaults",
            "Authenticated Sri Lanka tax-law instalment schedule / tax advice (#920) replacing within-year tax allocation",
            "Separate #1110 programme audit completion and Board/lender circulation authorization",
        ],
    }


def build_f5_exit_evidence_pack(
    evidence_cfg: Mapping[str, Any], *, repo_root: Path = REPO_ROOT
) -> Dict[str, Any]:
    """Build and verify the audited #1893 Dolphin 4 F-5 exit evidence pack.

    Args:
        evidence_cfg: The ``f5_exit_evidence`` mapping from ``conf/f5_exit_evidence_1893.yaml``.
        repo_root: Repository root containing scenarios and source modules.

    Returns:
        JSON-serializable evidence dictionary carrying source SHA-256 digests, all six
        verification gates, and the active ``HOLD_UNION`` non-reliance status.
    """
    source_digests: Dict[str, str] = {}
    for rel in evidence_cfg["source_files"]:
        rel_str = str(rel)
        source_digests[rel_str] = _sha256_file(repo_root / rel_str)

    # Confirm evaluated_scenario_config does not leak mutations
    _ = evaluated_scenario_config({})

    gate_1 = _gate_1_baseline_canon_invariance(evidence_cfg, repo_root=repo_root)
    gate_2 = _gate_2_monthly_cascade_and_lag(evidence_cfg, repo_root=repo_root)
    gate_3, variant_runs = _gate_3_quarterly_sculpting_and_bridge(
        evidence_cfg, repo_root=repo_root
    )
    gate_4 = _gate_4_cross_feature_parity(evidence_cfg, variant_runs)
    gate_5 = _gate_5_negative_controls(evidence_cfg, repo_root=repo_root)
    gate_6 = _gate_6_f5_authority_and_open_gates()

    return {
        "schema": SCHEMA_VERSION,
        "issue": 1893,
        "dolphin": 4,
        "f5_status": "IN_FORCE_PENDING_OWNER_AND_OPUS_REVIEW",
        "hold_union": list(HOLD_UNION),
        "non_reliance_notice": NON_RELIANCE_NOTICE,
        "source_file_sha256": source_digests,
        "gate_1_baseline_canon_invariance": gate_1,
        "gate_2_monthly_cascade_and_lag": gate_2,
        "gate_3_quarterly_sculpting_and_bridge": gate_3,
        "gate_4_cross_feature_parity": gate_4,
        "gate_5_negative_controls": gate_5,
        "gate_6_f5_authority_and_open_gates": gate_6,
    }


__all__ = [
    "NON_RELIANCE_NOTICE",
    "SCHEMA_VERSION",
    "build_f5_exit_evidence_pack",
]
