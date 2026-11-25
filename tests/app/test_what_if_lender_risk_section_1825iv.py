"""What-if cases (#1403/#1523) and CASPER lender-risk blocks in the lender report (#1825 slice iv)."""

from __future__ import annotations

import copy
from html import unescape as _html_unescape
from pathlib import Path
from typing import Any, Dict, List, Mapping

import numpy as np
import pytest
import yaml

import app.reports.capital_risk_emit as cre
from analytics.contracts_v14 import MonteCarloResult
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from analytics.what_if_cases import WhatIfCaseError, load_what_if_case
from app.reports import lender_report_emit as lre
from app.reports.capital_risk_emit import (
    LENDER_GRADE_MIN_TRIALS,
    run_lender_grade_monte_carlo,
)
from app.reports.dbpl import DbplDependencyError
from app.reports.lender_report_emit import (
    emit_lender_report_from_pipeline,
    sections_not_run,
)
from app.reports.renderer import render_report_html
from app.reports.report_model import WhatIfLenderRiskBlock
from app.reports.report_orchestration import (
    ORDINARY_REPORT_SENSITIVITY_PROFILE,
    ReportSensitivityBundle,
    build_report_context_from_case,
    compute_report_sensitivity,
    report_case_from_pipeline_result,
)
from app.reports.what_if_lender_risk_section import (
    DEFAULT_WHAT_IF_LENDER_RISK_SETTINGS,
    SECTION_WHAT_IF_LENDER_RISK,
    WhatIfLenderRiskSettings,
    build_what_if_lender_risk_section,
    settings_from_config,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CFG = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
BW_WIND_CFG = REPO_ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
BW_SOLAR_BESS_CFG = REPO_ROOT / "scenarios" / "blue_whale_solar_bess_lot5b_2026.yaml"
GENERATED_AT = "2026-11-23T00:00:00+00:00"
ON = WhatIfLenderRiskSettings(enabled=True)


def _empty_bundle(
    scenario: Mapping[str, Any], *, profile: Any = ORDINARY_REPORT_SENSITIVITY_PROFILE
) -> ReportSensitivityBundle:
    return compute_report_sensitivity(
        scenario,
        profile=profile,
        tornado_computer=lambda _s: None,
        morris_computer=lambda _s, *, n_trajectories: None,
        pawn_computer=lambda _s, *, n, s: None,
    )


def _make_mc_result(
    n_trials: int = 1000,
    *,
    floor_pinned: bool = False,
    undefined_irr_count: int = 0,
    toy_fallback_count: int = 0,
    seed: int = 42,
) -> MonteCarloResult:
    rng = np.random.default_rng(seed)
    if floor_pinned:
        dscr_min = np.full(n_trials, 1.30, dtype=float)
    else:
        dscr_min = rng.uniform(0.85, 1.45, size=n_trials)
    project_irr = rng.normal(0.11, 0.02, size=n_trials)
    if undefined_irr_count > 0:
        project_irr[:undefined_irr_count] = np.nan
    equity_irr = rng.normal(0.13, 0.03, size=n_trials)
    project_npv = rng.normal(2_000_000.0, 1_500_000.0, size=n_trials)
    equity_npv = rng.normal(1_000_000.0, 1_200_000.0, size=n_trials)
    llcr = rng.uniform(1.25, 1.65, size=n_trials)
    plcr = rng.uniform(1.35, 1.85, size=n_trials)
    return MonteCarloResult(
        scenario_name="Synthetic",
        iterations=n_trials,
        failed_iterations=0,
        trials={
            "dscr_min": dscr_min.tolist(),
            "project_irr": project_irr.tolist(),
            "equity_irr": equity_irr.tolist(),
            "project_npv": project_npv.tolist(),
            "equity_npv": equity_npv.tolist(),
            "llcr": llcr.tolist(),
            "plcr": plcr.tolist(),
        },
        metadata={
            "sampler": "lhs",
            "correlation_enabled": False,
            "seed": seed,
            "toy_fallback_count": toy_fallback_count,
        },
    )


@pytest.fixture(scope="module")
def lender_scenario() -> Dict[str, Any]:
    return dict(load_scenario_config(str(LENDER_CFG)))


@pytest.fixture(scope="module")
def lender_result(lender_scenario: Dict[str, Any]) -> Mapping[str, Any]:
    return run_v14_pipeline(config=copy.deepcopy(lender_scenario))


@pytest.fixture()
def html_only(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_print(*_a: Any, **_k: Any) -> Any:
        raise DbplDependencyError("PDF print skipped in unit test")

    monkeypatch.setattr(lre, "_render_pdf", _no_print)


# ── settings & CESSPIT validation ────────────────────────────────────────────


def test_settings_default_off_at_lender_floor() -> None:
    assert DEFAULT_WHAT_IF_LENDER_RISK_SETTINGS.enabled is False
    assert DEFAULT_WHAT_IF_LENDER_RISK_SETTINGS.mc_trials == LENDER_GRADE_MIN_TRIALS
    assert settings_from_config(None) == DEFAULT_WHAT_IF_LENDER_RISK_SETTINGS
    assert settings_from_config({}) == DEFAULT_WHAT_IF_LENDER_RISK_SETTINGS


def test_shipped_run_configuration_keeps_section_off() -> None:
    cfg = yaml.safe_load(
        (REPO_ROOT / "conf" / "run_full_pipeline_v14.yaml").read_text(encoding="utf-8")
    )
    got = settings_from_config(cfg["lender_report"]["what_if_lender_risk"])
    assert got == DEFAULT_WHAT_IF_LENDER_RISK_SETTINGS
    assert got.enabled is False


def test_settings_accept_valid_overrides() -> None:
    got = settings_from_config(
        {
            "enabled": True,
            "what_if_dir": None,
            "case_files": ["scenarios/what_if/tariff_reference.yaml"],
            "mc": {"trials": 2000, "seed": 99},
        }
    )
    assert got == WhatIfLenderRiskSettings(
        enabled=True,
        what_if_dir=None,
        case_files=("scenarios/what_if/tariff_reference.yaml",),
        mc_trials=2000,
        mc_seed=99,
    )


@pytest.mark.parametrize(
    "raw, match",
    [
        ([], "must be a mapping"),
        ({"enabled": True, "bogus": 1}, "unknown key"),
        ({"enabled": "false"}, "enabled must be a boolean"),
        ({"enabled": 1}, "enabled must be a boolean"),
        ({"what_if_dir": ""}, "what_if_dir must be a non-empty string"),
        ({"case_files": []}, "case_files must be a non-empty list"),
        ({"case_files": "scenarios/what_if/a.yaml"}, "case_files must be a non-empty"),
        ({"mc": [1000]}, "mc takes only trials and seed"),
        ({"mc": {"trials": 1000, "extra": 1}}, "mc takes only trials and seed"),
        ({"mc": {"trials": True}}, "mc.trials must be an integer"),
        ({"mc": {"trials": 999}}, "at least 1000"),
        ({"mc": {"seed": "42"}}, "mc.seed must be an integer"),
    ],
)
def test_bad_settings_fail_closed(raw: Any, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        settings_from_config(raw)


# ── default-off & byte-identity ──────────────────────────────────────────────


def test_switched_off_does_nothing_and_leaves_report_unchanged(
    lender_scenario: Dict[str, Any],
) -> None:
    called: List[str] = []

    def _boom(*_a: Any, **_k: Any) -> Any:
        called.append("called")
        raise AssertionError("must not run when disabled")

    out = build_what_if_lender_risk_section(
        LENDER_CFG,
        lender_scenario,
        DEFAULT_WHAT_IF_LENDER_RISK_SETTINGS,
        what_if_runner=_boom,
        mc_runner=_boom,
    )
    assert isinstance(out, str)
    assert "switched off" in out
    assert called == []


def test_default_off_report_is_byte_identical(
    lender_scenario: Dict[str, Any], lender_result: Mapping[str, Any]
) -> None:
    case = report_case_from_pipeline_result(
        lender_result,
        scenario_config=lender_scenario,
        scenario_variant="dutchbay_lendercase_2025Q4",
        generated_at=GENERATED_AT,
    )
    bundle = _empty_bundle(lender_scenario)
    html_a = render_report_html(build_report_context_from_case(case, bundle))
    html_b = render_report_html(
        build_report_context_from_case(case, bundle, what_if_lender_risk=None)
    )
    assert html_a == html_b
    assert "What-If Cases" not in html_a


# ── #1403 what-if cases with #1523 caveats verbatim ──────────────────────────


def test_what_if_cases_run_with_1523_caveats_verbatim_and_zero_scenario_mutation(
    lender_scenario: Dict[str, Any],
) -> None:
    pristine = copy.deepcopy(lender_scenario)

    def _fake_runner(cfg: Dict[str, Any]) -> Mapping[str, Any]:
        return {
            "kpis": {
                "project_irr": 0.015,
                "project_npv": -70_000_000.0,
                "equity_irr": -0.05,
                "equity_npv": -80_000_000.0,
                "total_idc_usd": 8_500_000.0,
                "max_debt_usd": 55_000_000.0,
                "min_dscr": 1.30,
                "llcr": 1.38,
                "total_cfads_usd": 160_000_000.0,
            },
            "debt_result": {
                "funding": {
                    "sources_and_uses": {
                        "sources": {
                            "senior_debt_usd": 55_000_000.0,
                            "equity_usd": 110_000_000.0,
                        },
                        "uses_total_usd": 165_000_000.0,
                    }
                }
            },
        }

    block = build_what_if_lender_risk_section(
        LENDER_CFG,
        lender_scenario,
        ON,
        mc_result=_make_mc_result(floor_pinned=True, undefined_irr_count=52),
        what_if_runner=_fake_runner,
    )
    assert lender_scenario == pristine
    assert isinstance(block, WhatIfLenderRiskBlock)
    assert block.parts_not_run == []
    assert [c.case_id for c in block.what_if_cases] == [
        "developer_funded_connection",
        "grid_connection_delay",
        "tariff_reference_2026_wind",
    ]

    # Every #1523 limitation, source, and parameter provenance is preserved verbatim.
    for path in sorted((REPO_ROOT / "scenarios" / "what_if").glob("*.yaml")):
        committed = load_what_if_case(path, repo_root=REPO_ROOT)
        matched = next(c for c in block.what_if_cases if c.case_id == committed.case_id)
        assert matched.canonical is False
        assert matched.source == committed.source
        assert tuple(matched.limitations) == committed.limitations
        assert [p.provenance for p in matched.parameters] == [
            p.provenance for p in committed.parameters.values()
        ]

    delay_block = next(
        c for c in block.what_if_cases if c.case_id == "grid_connection_delay"
    )
    assert len(delay_block.variants) == 3
    assert [v.parameters["delay_months"] for v in delay_block.variants] == [6, 12, 24]


def test_unmatched_scenario_lists_what_if_not_run_explicitly(
    lender_result: Mapping[str, Any], tmp_path: Path, html_only: None
) -> None:
    bw_wind = dict(load_scenario_config(str(BW_WIND_CFG)))
    fake_mc = _make_mc_result(floor_pinned=False)
    block = build_what_if_lender_risk_section(
        BW_WIND_CFG,
        bw_wind,
        ON,
        mc_result=fake_mc,
    )
    assert isinstance(block, WhatIfLenderRiskBlock)
    assert block.what_if_cases == []
    assert block.casper_lender_risk is not None
    assert len(block.parts_not_run) == 1
    assert "What-if cases (#1403)" in block.parts_not_run[0]
    assert "blue_whale_wind_lot5b_2026.yaml" in block.parts_not_run[0]


def test_scenario_without_mc_parameters_lists_casper_not_run_explicitly() -> None:
    bw_solar_bess = dict(load_scenario_config(str(BW_SOLAR_BESS_CFG)))
    block = build_what_if_lender_risk_section(
        BW_SOLAR_BESS_CFG,
        bw_solar_bess,
        ON,
    )
    assert isinstance(block, WhatIfLenderRiskBlock)
    assert block.what_if_cases == []
    assert block.casper_lender_risk is None
    assert len(block.parts_not_run) == 2
    assert any("What-if cases (#1403)" in line for line in block.parts_not_run)
    assert any("monte_carlo.parameters" in line for line in block.parts_not_run)


# ── FRAMEWORK-01 CASPER lender-risk blocks & lender guards ───────────────────


def test_lender_mc_guard_forces_allow_toy_fallback_off_and_refuses_toy_trials(
    monkeypatch: pytest.MonkeyPatch, lender_scenario: Dict[str, Any]
) -> None:
    contaminated_cfg = copy.deepcopy(lender_scenario)
    contaminated_cfg["monte_carlo"]["allow_toy_fallback"] = True
    seen: List[Dict[str, Any]] = []

    def _fake_run(
        *, base_config: Mapping[str, Any], n_trials: int, seed: int
    ) -> MonteCarloResult:
        seen.append(dict(base_config["monte_carlo"]))
        return _make_mc_result(n_trials=n_trials, seed=seed, toy_fallback_count=0)

    monkeypatch.setattr(cre, "run_monte_carlo_analysis", _fake_run)
    res = run_lender_grade_monte_carlo(contaminated_cfg, n_trials=1000, seed=42)
    assert res.iterations == 1000
    assert seen[0]["allow_toy_fallback"] is False

    # Any toy_fallback_count > 0 must raise loudly.
    monkeypatch.setattr(
        cre,
        "run_monte_carlo_analysis",
        lambda **_kw: _make_mc_result(n_trials=1000, toy_fallback_count=2),
    )
    with pytest.raises(ValueError, match="toy-fallback"):
        run_lender_grade_monte_carlo(contaminated_cfg, n_trials=1000, seed=42)


def test_section_refuses_toy_fallback_and_sub_floor_trials_fail_closed(
    lender_scenario: Dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match="toy-fallback"):
        build_what_if_lender_risk_section(
            LENDER_CFG,
            lender_scenario,
            WhatIfLenderRiskSettings(enabled=True, what_if_dir=None),
            mc_result=_make_mc_result(n_trials=1000, toy_fallback_count=1),
        )

    with pytest.raises(ValueError, match="at least 1000"):
        build_what_if_lender_risk_section(
            LENDER_CFG,
            lender_scenario,
            WhatIfLenderRiskSettings(enabled=True, what_if_dir=None, mc_trials=100),
        )


def test_misconfigured_explicit_case_files_or_malformed_yaml_fails_closed(
    lender_scenario: Dict[str, Any], tmp_path: Path
) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        build_what_if_lender_risk_section(
            LENDER_CFG,
            lender_scenario,
            WhatIfLenderRiskSettings(
                enabled=True,
                what_if_dir=None,
                case_files=(str(tmp_path / "missing.yaml"),),
            ),
            mc_result=_make_mc_result(),
        )

    bad_case = tmp_path / "bad.yaml"
    bad_case.write_text("what_if_case:\n  canonical: true\n", encoding="utf-8")
    with pytest.raises(WhatIfCaseError):
        build_what_if_lender_risk_section(
            LENDER_CFG,
            lender_scenario,
            WhatIfLenderRiskSettings(
                enabled=True,
                what_if_dir=None,
                case_files=(str(bad_case),),
            ),
            mc_result=_make_mc_result(),
        )


def test_reuses_compatible_mc_result_and_skips_duplicate_run(
    lender_scenario: Dict[str, Any],
) -> None:
    calls: List[int] = []

    def _mc_runner(*_a: Any, **_k: Any) -> MonteCarloResult:
        calls.append(1)
        return _make_mc_result()

    block = build_what_if_lender_risk_section(
        LENDER_CFG,
        lender_scenario,
        WhatIfLenderRiskSettings(enabled=True, what_if_dir=None, mc_trials=1000),
        mc_result=_make_mc_result(n_trials=1000, seed=42),
        mc_runner=_mc_runner,
    )
    assert isinstance(block, WhatIfLenderRiskBlock)
    assert calls == []

    # Different explicit seed must run mc_runner with that seed.
    block2 = build_what_if_lender_risk_section(
        LENDER_CFG,
        lender_scenario,
        WhatIfLenderRiskSettings(
            enabled=True, what_if_dir=None, mc_trials=1000, mc_seed=999
        ),
        mc_result=_make_mc_result(n_trials=1000, seed=42),
        mc_runner=_mc_runner,
    )
    assert isinstance(block2, WhatIfLenderRiskBlock)
    assert calls == [1]


def test_floor_pinned_and_irr_coverage_render_into_html_without_moving_kpis(
    lender_scenario: Dict[str, Any],
    lender_result: Mapping[str, Any],
    tmp_path: Path,
    html_only: None,
) -> None:
    def _fake_what_if(cfg: Dict[str, Any]) -> Mapping[str, Any]:
        return {
            "kpis": dict(lender_result["kpis"]),
            "debt_result": lender_result["debt_result"],
        }

    baseline_out = emit_lender_report_from_pipeline(
        lender_result,
        LENDER_CFG,
        tmp_path / "off" / "lender_report.html",
        capital_risk_not_run="not run: test",
        require_pdf=False,
        sensitivity_computer=lambda s, *, profile: _empty_bundle(s, profile=profile),
        generated_at=GENERATED_AT,
    )
    baseline_html = baseline_out.html_path.read_text(encoding="utf-8")

    # Built enabled block via custom builder using our deterministic fast seams.
    def _builder(
        path: Any, scenario: Any, settings: Any, *, mc_result: Any = None
    ) -> Any:
        return build_what_if_lender_risk_section(
            path,
            scenario,
            settings,
            mc_result=_make_mc_result(floor_pinned=True, undefined_irr_count=52),
            what_if_runner=_fake_what_if,
        )

    enabled_out = emit_lender_report_from_pipeline(
        lender_result,
        LENDER_CFG,
        tmp_path / "on" / "lender_report.html",
        capital_risk_not_run="not run: test",
        require_pdf=False,
        sensitivity_computer=lambda s, *, profile: _empty_bundle(s, profile=profile),
        what_if_lender_risk=ON,
        what_if_lender_risk_builder=_builder,
        generated_at=GENERATED_AT,
    )
    enabled_html = enabled_out.html_path.read_text(encoding="utf-8")

    assert SECTION_WHAT_IF_LENDER_RISK not in {
        s.section for s in enabled_out.sections_not_run
    }
    assert "<h2>What-If Cases &amp; Lender Risk</h2>" in enabled_html
    assert "allow_toy_fallback=false" in enabled_html
    assert "DSCR floor pinned:" in enabled_html
    assert "52 of 1000 trials have no defined project_irr" in enabled_html
    assert ">undefined<" in enabled_html

    # Every #1523 limitation string from grid_connection_delay.yaml is present verbatim in HTML.
    delay_case = load_what_if_case(
        REPO_ROOT / "scenarios" / "what_if" / "grid_connection_delay.yaml",
        repo_root=REPO_ROOT,
    )
    unescaped_html = _html_unescape(enabled_html)
    for limitation in delay_case.limitations:
        assert limitation in unescaped_html

    # Executive Summary table is identical: zero committed-scenario KPI change.
    exec_off = baseline_html.split("<h2>Executive Summary</h2>", 1)[1].split(
        "</section>", 1
    )[0]
    exec_on = enabled_html.split("<h2>Executive Summary</h2>", 1)[1].split(
        "</section>", 1
    )[0]
    assert exec_off == exec_on


def test_sections_not_run_places_what_if_lender_risk_at_end(
    lender_scenario: Dict[str, Any],
) -> None:
    rows = sections_not_run(
        _empty_bundle(lender_scenario),
        lender_scenario,
        capital_risk_not_run="not run: test",
        what_if_lender_risk_not_run="not run: switched off",
    )
    assert rows[-1].section == SECTION_WHAT_IF_LENDER_RISK
    assert rows[-1].reason == "not run: switched off"
