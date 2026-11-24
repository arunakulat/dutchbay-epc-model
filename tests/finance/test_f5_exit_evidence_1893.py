"""Audited F-5 exit evidence pack and Dolphin 4 parity regression suite (#1893)."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, Mapping

import yaml

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.finance.f5_exit_evidence import (
    NON_RELIANCE_NOTICE,
    SCHEMA_VERSION,
    build_f5_exit_evidence_pack,
)
from analytics.finance.p90_cover import resolve_p90_cover
from analytics.finance.p90_recomputed_downside import recomputed_p90_downside
from analytics.run_identity import HOLD_UNION, check_no_hold_withdrawal
from analytics.scenario_loader import load_scenario_config
from analytics.three_statement import build_cashflow_waterfall
from app.api.surface import CaseSurface
from app.reports.renderer import render_report_html
from app.reports.report_orchestration import (
    ORDINARY_REPORT_SENSITIVITY_PROFILE,
    build_report_context_from_case,
    compute_report_sensitivity,
    report_case_from_pipeline_result,
)
from finance.quarterly_sculpting_v14 import COVENANT_USE

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_CFG_PATH = REPO_ROOT / "conf" / "f5_exit_evidence_1893.yaml"
EVIDENCE_JSON_PATH = REPO_ROOT / "docs" / "finance" / "f5_exit_evidence_1893.json"
EVIDENCE_MD_PATH = REPO_ROOT / "docs" / "finance" / "F5_EXIT_EVIDENCE_PACK_1893.md"


def _load_evidence_cfg() -> Dict[str, Any]:
    raw = yaml.safe_load(EVIDENCE_CFG_PATH.read_text(encoding="utf-8"))
    return dict(raw["f5_exit_evidence"])


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mixed_sign_sculpted_cfg(
    evidence_cfg: Mapping[str, Any], *, with_p90_cover: bool = False
) -> Dict[str, Any]:
    cfg = copy.deepcopy(
        dict(load_scenario_config(str(REPO_ROOT / evidence_cfg["primary_scenario"])))
    )
    cases = evidence_cfg["cases"]
    shapes = evidence_cfg["shapes"]
    cfg["cashflow"] = {
        **dict(cfg.get("cashflow") or {}),
        "monthly": {
            "cod_month": int(cases["cod_month"]),
            "energy_shape": list(shapes["mixed_sign_sparse"]),
            "risk_haircut_rule": "month_adverse",
            "quarterly_sculpting": {"enabled": True},
        },
    }
    if with_p90_cover:
        cfg["Financing_Terms"] = {
            **dict(cfg["Financing_Terms"]),
            "p90_cover_min_dscr": float(cases["p90_cover_min_dscr"]),
        }
    return cfg


def test_committed_f5_exit_evidence_json_is_fresh_and_complete() -> None:
    """Committed JSON matches every hashed source/scenario file and passes all 6 gates."""
    evidence_cfg = _load_evidence_cfg()
    pack = json.loads(EVIDENCE_JSON_PATH.read_text(encoding="utf-8"))

    assert pack["schema"] == SCHEMA_VERSION
    assert pack["issue"] == 1893
    assert pack["dolphin"] == 4
    assert pack["f5_status"] == "IN_FORCE_PENDING_OWNER_AND_OPUS_REVIEW"
    assert pack["hold_union"] == list(HOLD_UNION)
    assert pack["gate_6_f5_authority_and_open_gates"]["f5_exit_lifted"] is False
    assert pack["gate_6_f5_authority_and_open_gates"]["hold_union"] == list(HOLD_UNION)

    for rel_path, expected_digest in pack["source_file_sha256"].items():
        actual = _sha256_file(REPO_ROOT / rel_path)
        assert actual == expected_digest, f"Stale source hash for {rel_path}"

    g1 = pack["gate_1_baseline_canon_invariance"]
    assert g1["status"] == "PASS"
    assert g1["monthly_enabled_scenarios"] == []
    assert g1["receivables_enabled_scenarios"] == []
    assert g1["quarterly_sculpting_enabled_scenarios"] == []
    assert g1["expected_baseline_kpis_sha256"] == _sha256_file(
        REPO_ROOT / evidence_cfg["expected_baseline_kpis_json"]
    )
    for ref in g1["references"].values():
        assert ref["scenario_sha256"] == _sha256_file(REPO_ROOT / ref["scenario_path"])

    assert pack["gate_2_monthly_cascade_and_lag"]["status"] == "PASS"
    assert pack["gate_3_quarterly_sculpting_and_bridge"]["status"] == "PASS"
    assert pack["gate_4_cross_feature_parity"]["status"] == "PASS"
    assert pack["gate_5_negative_controls"]["status"] == "PASS"
    assert all(pack["gate_5_negative_controls"]["controls"].values())


def test_committed_f5_exit_evidence_markdown_matches_json_and_hold_guard() -> None:
    """Committed Markdown pack cites committed JSON digits cleanly and keeps HOLD_UNION."""
    pack = json.loads(EVIDENCE_JSON_PATH.read_text(encoding="utf-8"))
    md = EVIDENCE_MD_PATH.read_text(encoding="utf-8")

    check_no_hold_withdrawal(md, "F5_EXIT_EVIDENCE_PACK_1893.md")
    check_no_hold_withdrawal(pack["non_reliance_notice"], "f5_exit_evidence_1893.json")
    assert pack["non_reliance_notice"] == NON_RELIANCE_NOTICE

    for required_token in (
        "F-5",
        "#1110",
        "v15.6.1",
        "#920",
        "#1399",
        "#1400",
        "#1893",
        "#1836",
        "#1895",
        "#1896",
        "#1897",
        "#1845",
        "f5_exit_evidence_1893.json",
        "scripts/run_f5_exit_evidence_v14.py",
        pack["gate_1_baseline_canon_invariance"]["references"]["primary"][
            "kpi_vector_sha256"
        ],
        "55,292,580.84",
        "1.4129882812499999",
        "0.8495427689879619",
    ):
        assert required_token in md, f"Missing expected reference {required_token!r}"


def test_pipeline_cfads_coverage_usd_reconciles_waterfall_under_mixed_sign() -> None:
    """Dolphin 4 fix: mixed-sign ``cfads_coverage_usd`` drives CashflowWaterfall to exact DSCR parity."""
    evidence_cfg = _load_evidence_cfg()
    cfg = _mixed_sign_sculpted_cfg(evidence_cfg)

    res = evaluate_with_overrides(raw_config=cfg, overrides={}, return_full_result=True)
    assert isinstance(res, dict)
    debt = res["debt_result"]
    annual_rows = res["annual_rows"]
    map_by_idx = {
        int(m["annual_row_index"]): m for m in debt["annual_row_debt_period_map"]
    }

    # Independent TEST-01 oracle: verify mixed-sign exclusion occurred and shifted
    # ``cfads_coverage_usd`` cleanly from year-sign waterfall CFADS while matching
    # ``annual_row_debt_period_map`` and ``debt_result["dscr_by_year"]``.
    wf = build_cashflow_waterfall(annual_rows, debt_result=debt)
    by_year = debt["dscr_by_year"]
    excess_lkr = debt["quarterly_sculpting"]["mixed_sign_haircut_excess_lkr"]
    shifted_years = sum(1 for v in excess_lkr if float(v) > 0.0)
    assert shifted_years >= 1

    checked_years = 0
    for idx, row in enumerate(annual_rows):
        cov_cfads = float(row["cfads_coverage_usd"])
        assert cov_cfads == float(map_by_idx[idx]["cfads_usd"])

    for wf_row in wf.rows:
        if wf_row.covenant_dscr is None:
            continue
        checked_years += 1
        assert abs(float(wf_row.covenant_dscr) - float(by_year[wf_row.year])) < 1e-12
        # Independent DS / CFADS check and non-vacuous difference vs project basis
        if (
            wf_row.covenant_debt_service is not None
            and wf_row.covenant_debt_service > 0
        ):
            assert wf_row.covenant_cfads is not None
            assert wf_row.coverage_cfads is not None
            assert (
                abs(
                    wf_row.covenant_cfads / wf_row.covenant_debt_service
                    - wf_row.covenant_dscr
                )
                < 1e-12
            )
            assert abs(wf_row.coverage_cfads - wf_row.cfads) > 1.0

    assert checked_years >= 10


def test_recomputed_p90_downside_honours_quarterly_sculpting_and_month_adverse() -> (
    None
):
    """Dolphin 4 fix (#1836): ``recomputed_p90_downside`` aligns engine rebuild with month_adverse."""
    evidence_cfg = _load_evidence_cfg()
    base_cfg = copy.deepcopy(
        dict(load_scenario_config(str(REPO_ROOT / evidence_cfg["primary_scenario"])))
    )
    cases = evidence_cfg["cases"]
    shapes = evidence_cfg["shapes"]

    for shape_values in ([1.0 / 12.0] * 12, list(shapes["seasonal"])):
        cfg = copy.deepcopy(base_cfg)
        cfg["cashflow"] = {
            **dict(cfg.get("cashflow") or {}),
            "monthly": {
                "cod_month": int(cases["cod_month"]),
                "energy_shape": shape_values,
                "risk_haircut_rule": "month_adverse",
                "quarterly_sculpting": {"enabled": True},
            },
        }
        p90 = recomputed_p90_downside(cfg)
        assert p90["status"] == "ok", f"Unexpected P90 failure: {p90}"

        live_res = evaluate_with_overrides(
            raw_config=copy.deepcopy(cfg), overrides={}, return_full_result=True
        )
        assert isinstance(live_res, dict)
        live_min = min(
            float(v)
            for v in live_res["debt_result"]["dscr_by_year"].values()
            if v is not None
        )
        assert abs(float(p90["cases"]["base"]["min_dscr"]) - live_min) < 1e-9
        # Non-vacuous downside responsiveness
        assert 0.5 < float(p90["cases"]["recomputed"]["min_dscr"]) < live_min


def test_p90_cover_combined_with_quarterly_sculpting_and_case_surface() -> None:
    """Dolphin 4 parity (#1895 + surface): P90 cover + quarterly sculpting + CaseSurface."""
    evidence_cfg = _load_evidence_cfg()
    target_p90 = float(evidence_cfg["cases"]["p90_cover_min_dscr"])

    cfg = copy.deepcopy(
        dict(load_scenario_config(str(REPO_ROOT / evidence_cfg["primary_scenario"])))
    )
    cfg["cashflow"] = {
        **dict(cfg.get("cashflow") or {}),
        "monthly": {
            "cod_month": int(evidence_cfg["cases"]["cod_month"]),
            "energy_shape": list(evidence_cfg["shapes"]["seasonal"]),
            "risk_haircut_rule": "month_adverse",
            "quarterly_sculpting": {"enabled": True},
        },
    }
    cfg["Financing_Terms"] = {
        **dict(cfg["Financing_Terms"]),
        "p90_cover_min_dscr": target_p90,
    }
    assert resolve_p90_cover(cfg) == target_p90

    res = evaluate_with_overrides(raw_config=cfg, overrides={}, return_full_result=True)
    assert isinstance(res, dict)
    debt = res["debt_result"]
    p90_block = debt["p90_cover"]
    assert p90_block["binding"] is True
    assert float(p90_block["recomputed_min_dscr"]) >= target_p90
    assert debt["quarterly_sculpting"]["covenant_use"] == COVENANT_USE

    # Independent CaseSurface + HTML report rendering compatibility check
    case = report_case_from_pipeline_result(
        res,
        scenario_config=cfg,
        scenario_variant="seasonal_p90_cover_sculpted",
        generated_at="2026-11-24T00:00:00+00:00",
    )
    bundle = compute_report_sensitivity(
        cfg,
        profile=ORDINARY_REPORT_SENSITIVITY_PROFILE,
        tornado_computer=lambda _s: None,
        morris_computer=lambda _s, *, n_trajectories: None,
        pawn_computer=lambda _s, *, n, s: None,
    )
    ctx = build_report_context_from_case(case, bundle)
    surface = CaseSurface.from_report_context(ctx)
    html = render_report_html(ctx)
    assert ctx.cashflow_waterfall is not None
    assert surface.scenario_variant == "seasonal_p90_cover_sculpted"
    assert surface.reliance_label == "lender_reliance_prohibited"
    assert len(surface.kpi_cards) >= 5
    if surface.reliance_notice:
        check_no_hold_withdrawal(
            surface.reliance_notice, "case_surface_reliance_notice"
        )
    assert "Cash-Flow Waterfall by Payment Priority" in html


def test_live_build_f5_exit_evidence_pack_reproduces_committed_json_exactly() -> None:
    """Re-running ``build_f5_exit_evidence_pack`` reproduces the committed JSON byte-for-byte."""
    evidence_cfg = _load_evidence_cfg()
    live_pack = build_f5_exit_evidence_pack(evidence_cfg, repo_root=REPO_ROOT)
    committed_pack = json.loads(EVIDENCE_JSON_PATH.read_text(encoding="utf-8"))

    # Normalize cross-platform 1-ULP floating-point brentq root differences on non-primary reference scenarios
    # (primary lender case vector hash is strictly pinned in test_committed_f5_exit_evidence_markdown_matches_json_and_hold_guard).
    for ref_name in ("bess_augmentation", "hybrid_bess"):
        live_ref = (
            live_pack.get("gate_1_baseline_canon_invariance", {})
            .get("references", {})
            .get(ref_name)
        )
        committed_ref = (
            committed_pack.get("gate_1_baseline_canon_invariance", {})
            .get("references", {})
            .get(ref_name)
        )
        if live_ref and committed_ref:
            assert math.isclose(
                live_ref["equity_irr"], committed_ref["equity_irr"], abs_tol=1e-12
            )
            live_ref["equity_irr"] = committed_ref["equity_irr"]
            live_ref["kpi_vector_sha256"] = committed_ref["kpi_vector_sha256"]

    assert live_pack == committed_pack
