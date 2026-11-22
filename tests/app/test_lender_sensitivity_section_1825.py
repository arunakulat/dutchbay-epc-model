"""Lender sensitivities in the command-line lender report (#1825 slice ii).

The analysis modules are replaced by fakes, so these tests pin the section's own logic:
which parts run, what each part reads from the scenario, the coupled-input seam, the
"not run" reasons and the rendered section. The real analyses are exercised by their own
suites and by the lender-case smoke recorded on the pull request.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Mapping, Optional, Tuple

import pytest

from app.models.inputs import WindFarmInputs
from app.reports.lender_report_emit import (
    SECTION_LENDER_SENSITIVITIES,
    sections_not_run,
)
from app.reports.lender_sensitivity_section import (
    DEFAULT_SENSITIVITY_SETTINGS,
    LenderSensitivitySettings,
    ParetoAxis,
    build_lender_sensitivity_section,
    settings_from_config,
)
from app.reports.renderer import render_report_html
from app.reports.report_model import LenderSensitivityBlock
from app.reports.report_orchestration import (
    ORDINARY_REPORT_SENSITIVITY_PROFILE,
    build_report_context_from_case,
    compute_report_sensitivity,
    run_report_case,
)
from app.services.report_tornado import TornadoRow

_BASE: Dict[str, float] = {
    "equity_npv": -91_660_000.0,
    "project_irr": 0.071,
    "min_dscr_period": 1.30,
    "max_debt_usd": 59_000_000.0,
}

_ON = LenderSensitivitySettings(enabled=True)


def _scenario(**over: Any) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {
        "project": {"capacity_mw": 100.0, "capacity_factor": 0.35},
        "Financing_Terms": {"tenor_years": 15, "target_dscr": 1.3},
        "wacc": {
            "mode": "build_up",
            "drives_discount_rate": True,
            "cost_of_equity": 0.15,
        },
        "fx": {"enabled": True, "start_lkr_per_usd": 300.0},
        "monte_carlo": {"parameters": {"capacity_factor": {"min": 0.3, "max": 0.4}}},
    }
    for dotted, value in over.items():
        node = cfg
        parts = dotted.split("__")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        if value is _DROP:
            node.pop(parts[-1], None)
        else:
            node[parts[-1]] = value
    return cfg


_DROP = object()


class _Fakes:
    """Recording fakes for every analysis the section calls."""

    def __init__(self) -> None:
        self.evaluated: List[Mapping[str, Any]] = []
        self.ke_values: List[float] = []
        self.pareto_grid: List[Any] = []
        self.sobol_calls: List[Mapping[str, Any]] = []
        self.flat: Dict[str, Any] = {}
        self.tornado_base: Optional[float] = None
        self.raise_in: Optional[str] = None

    def evaluate(self, path: str, overrides: Mapping[str, Any]) -> Mapping[str, Any]:
        self.evaluated.append(dict(overrides))
        return dict(_BASE)

    def tornado(
        self, scenario: Mapping[str, Any], *, metric: str
    ) -> Tuple[Any, Mapping[str, Any]]:
        if self.raise_in == "tornado":
            raise RuntimeError("sweep broke")
        base = _BASE[metric] if self.tornado_base is None else self.tornado_base
        rows = [
            TornadoRow(
                label="Tariff",
                base=base,
                low_case=base * 0.9,
                high_case=base * 1.1,
                impact_abs=base * 0.2,
            ),
            TornadoRow(
                label="Capex",
                base=base,
                low_case=base * 0.95,
                high_case=base * 1.05,
                impact_abs=base * 0.1,
            ),
        ]
        return SimpleNamespace(rows=rows), dict(self.flat)

    def ke_band(self, path: str, values: List[float]) -> List[Mapping[str, Any]]:
        if self.raise_in == "ke":
            raise ValueError("wacc broke")
        self.ke_values = list(values)
        return [
            {
                "ke": v,
                "wacc": 0.08 + v / 10,
                "project_npv": -1e6 * v,
                "equity_npv": (
                    _BASE["equity_npv"] if abs(v - 0.15) < 1e-12 else -1e8 * v
                ),
            }
            for v in values
        ]

    def fx_analyzer(self, path: str) -> Any:
        fakes = self

        def _pt(rate: float, hedge: float, spread: float) -> Any:
            return SimpleNamespace(
                fx_rate=rate,
                hedge_ratio=hedge,
                spread_bps=spread,
                project_irr=_BASE["project_irr"],
                equity_npv=_BASE["equity_npv"],
                min_dscr=1.2,
            )

        class _Analyzer:
            def analyze_fx_sensitivity(self, **kw: Any) -> Any:
                if fakes.raise_in == "fx":
                    raise RuntimeError("fx broke")
                return SimpleNamespace(
                    base_fx_rate=300.0,
                    base_hedge_ratio=0.0,
                    base_spread_bps=0.0,
                    fx_rate_points=[_pt(r, 0.0, 0.0) for r in (270.0, 300.0, 330.0)],
                    hedge_ratio_points=[_pt(300.0, h, 0.0) for h in (0.0, 0.5, 1.0)],
                    spread_points=[_pt(300.0, 1.0, s) for s in (0.0, 50.0, 100.0)],
                    base_project_irr=_BASE["project_irr"],
                )

        return _Analyzer()

    def pareto(self, *, base_config: Any, objectives: Any, grid: Any) -> Any:
        if self.raise_in == "pareto":
            raise RuntimeError("pareto broke")
        self.pareto_grid = list(grid)
        points = []
        for t in grid[0].values:
            for d in grid[1].values:
                points.append(
                    SimpleNamespace(
                        overrides={grid[0].override_key: t, grid[1].override_key: d},
                        objectives={
                            "equity_npv": _BASE["equity_npv"]
                            + 1e6 * (t - 15)
                            - 1e7 * (d - 1.3),
                            "min_dscr_period": d,
                        },
                    )
                )
        frontier = [
            p
            for p in points
            if p.overrides[grid[0].override_key] == max(grid[0].values)
        ]
        return SimpleNamespace(points_all=points, points_pareto=frontier)

    def sobol(self, path: str, **kw: Any) -> Mapping[str, Any]:
        self.sobol_calls.append(kw)
        kw["evaluate_fn"]({"project.capacity_factor": 0.38})
        return {
            "n_runs": 384,
            "metrics": {
                "equity_npv": {
                    "drivers": {
                        "capacity_factor": {"S1": 0.5, "ST": 0.6, "ST_conf": 0.05},
                        "capex": {
                            "S1": 0.3,
                            "ST": 0.7,
                            "ST_conf": 0.04,
                            "interactive": True,
                        },
                    }
                },
                "max_debt_usd": {"flat_metric_reason": "the sized debt never moves"},
            },
        }

    def build(
        self, scenario: Mapping[str, Any], settings: LenderSensitivitySettings = _ON
    ) -> Any:
        return build_lender_sensitivity_section(
            "scenario.yaml",
            scenario,
            settings,
            evaluate=self.evaluate,
            tornado=self.tornado,
            ke_band=self.ke_band,
            fx_analyzer=self.fx_analyzer,
            pareto=self.pareto,
            sobol=self.sobol,
        )


@pytest.fixture()
def fakes() -> _Fakes:
    return _Fakes()


# ── settings ─────────────────────────────────────────────────────────────────


def test_the_section_is_off_by_default_and_sobol_has_its_own_flag() -> None:
    assert settings_from_config(None) is DEFAULT_SENSITIVITY_SETTINGS
    assert settings_from_config({}) is DEFAULT_SENSITIVITY_SETTINGS
    assert DEFAULT_SENSITIVITY_SETTINGS.enabled is False
    on = settings_from_config({"enabled": True})
    assert on.enabled is True and on.sobol_enabled is False


def test_settings_are_read_from_the_run_configuration() -> None:
    s = settings_from_config(
        {
            "enabled": True,
            "ke_values": [0.1, 0.2],
            "fx": {"variation_pct": 5, "steps": 3, "hedge_ratio_steps": [0, 1]},
            "pareto": {
                "objectives": [
                    {"metric": "equity_npv", "direction": "max"},
                    {"metric": "max_debt_usd", "direction": "min"},
                ],
                "grid": [{"key": "Financing_Terms.tenor_years", "offsets": [-1, 1]}],
            },
            "sobol": {"enabled": True, "n": 32, "metrics": ["equity_npv"]},
        }
    )
    assert s.ke_values == (0.1, 0.2)
    assert (s.fx_variation_pct, s.fx_steps, s.hedge_ratio_steps) == (5.0, 3, (0.0, 1.0))
    assert s.pareto_objectives == (("equity_npv", "max"), ("max_debt_usd", "min"))
    assert s.pareto_grid == (ParetoAxis("Financing_Terms.tenor_years", (-1.0, 1.0)),)
    assert (s.sobol_enabled, s.sobol_n, s.sobol_metrics) == (True, 32, ("equity_npv",))


@pytest.mark.parametrize(
    "raw, match",
    [
        ({"sobol": {"n": 48}}, "power of 2"),
        ({"pareto": {"objectives": [{"metric": "equity_npv"}]}}, "at least two"),
        (
            {
                "pareto": {
                    "objectives": [{"metric": "a", "direction": "up"}, {"metric": "b"}]
                }
            },
            "max or min",
        ),
        ({"ke_values": []}, "must not be empty"),
        ({"pareto": {"grid": []}}, "must not be empty"),
    ],
)
def test_bad_settings_fail_loud(raw: Mapping[str, Any], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        settings_from_config({"enabled": True, **raw})


# ── building ─────────────────────────────────────────────────────────────────


def test_switched_off_the_section_is_not_run_and_nothing_is_evaluated(
    fakes: _Fakes,
) -> None:
    out = fakes.build(_scenario(), DEFAULT_SENSITIVITY_SETTINGS)
    assert isinstance(out, str) and out.startswith("not run: switched off")
    assert fakes.evaluated == []


def test_every_part_runs_on_a_complete_scenario(fakes: _Fakes) -> None:
    block = fakes.build(_scenario())
    assert isinstance(block, LenderSensitivityBlock)
    assert block.committed_equity_npv == _BASE["equity_npv"]
    assert block.committed_min_dscr_period == 1.30
    assert block.committed_debt_usd == _BASE["max_debt_usd"]
    assert [t.metric for t in block.tornadoes] == ["min_dscr_period", "max_debt_usd"]
    assert [t.unit for t in block.tornadoes] == ["ratio", "usd"]
    assert all(
        t.reconciliation is None and t.flat_reason is None for t in block.tornadoes
    )
    assert len(block.ke_band) == 7  # six default values plus the committed 15%
    assert [r.committed for r in block.ke_band].count(True) == 1
    assert block.ke_committed == 0.15 and block.ke_reconciliation is None
    assert [s.kind for s in block.fx_sweeps] == [
        "LKR/USD start rate",
        "Hedge ratio",
        "Hedge spread",
    ]
    assert block.pareto is not None and block.pareto.n_frontier == 3
    # Sobol is off unless its own flag is on, and says so.
    assert block.sobol == []
    assert any(
        p.startswith("Sobol indices: not run: switched off")
        for p in block.parts_not_run
    )
    # The committed case is evaluated once, with no override.
    assert fakes.evaluated == [{}]


def test_the_ke_band_always_includes_the_committed_cost_of_equity(
    fakes: _Fakes,
) -> None:
    fakes.build(_scenario(wacc__cost_of_equity=0.155))
    assert 0.155 in fakes.ke_values
    assert fakes.ke_values == sorted(fakes.ke_values)


@pytest.mark.parametrize(
    "over, reason",
    [
        ({"wacc": _DROP}, "no wacc block"),
        ({"wacc__mode": "capm"}, "not the build-up WACC"),
        ({"wacc__drives_discount_rate": False}, "not the build-up WACC"),
        ({"wacc__cost_of_equity": "n/a"}, "no numeric wacc.cost_of_equity"),
    ],
)
def test_the_ke_band_names_what_it_lacks(
    fakes: _Fakes, over: Mapping[str, Any], reason: str
) -> None:
    block = fakes.build(_scenario(**over))
    assert isinstance(block, LenderSensitivityBlock)
    assert block.ke_band == []
    (line,) = [p for p in block.parts_not_run if p.startswith("Cost-of-equity band:")]
    assert reason in line


def test_a_ke_band_that_misses_the_committed_npv_says_so(fakes: _Fakes) -> None:
    real = fakes.ke_band

    def _off(path: str, values: List[float]) -> List[Mapping[str, Any]]:
        return [{**r, "equity_npv": -1.0} for r in real(path, values)]

    block = build_lender_sensitivity_section(
        "s.yaml",
        _scenario(),
        _ON,
        evaluate=fakes.evaluate,
        tornado=fakes.tornado,
        ke_band=_off,
        fx_analyzer=fakes.fx_analyzer,
        pareto=fakes.pareto,
        sobol=fakes.sobol,
    )
    assert isinstance(block, LenderSensitivityBlock)
    assert block.ke_reconciliation is not None
    assert "not the committed" in block.ke_reconciliation


@pytest.mark.parametrize(
    "over, reason",
    [
        ({"fx": _DROP}, "no enabled fx block"),
        ({"fx__enabled": False}, "no enabled fx block"),
        ({"fx__start_lkr_per_usd": None}, "no numeric fx.start_lkr_per_usd"),
    ],
)
def test_fx_names_what_it_lacks(
    fakes: _Fakes, over: Mapping[str, Any], reason: str
) -> None:
    block = fakes.build(_scenario(**over))
    assert isinstance(block, LenderSensitivityBlock)
    assert block.fx_sweeps == []
    (line,) = [p for p in block.parts_not_run if p.startswith("FX:")]
    assert reason in line


def test_fx_marks_the_scenario_point_and_reads_an_unhedged_spread_under_a_full_hedge(
    fakes: _Fakes,
) -> None:
    block = fakes.build(_scenario())
    assert isinstance(block, LenderSensitivityBlock)
    rate, hedge, spread = block.fx_sweeps
    assert [p.base for p in rate.points] == [False, True, False]
    assert [p.base for p in hedge.points] == [True, False, False]
    # Unhedged scenario: no spread point is the scenario's own.
    assert not any(p.base for p in spread.points)
    assert "reference hedge" in spread.searched
    assert "300.00 ±10%" in rate.searched


def test_the_pareto_grid_is_centred_on_the_committed_terms_without_float_noise(
    fakes: _Fakes,
) -> None:
    block = fakes.build(_scenario())
    assert isinstance(block, LenderSensitivityBlock)
    tenor, dscr = fakes.pareto_grid
    assert tenor.values == (12.0, 15.0, 18.0)
    # 1.3 + 0.1 is 1.4000000000000001 in floating point; the grid holds 1.4.
    assert dscr.values == (1.2, 1.3, 1.4)
    assert block.pareto is not None
    committed = [r for r in block.pareto.rows if r.committed]
    assert len(committed) == 1
    assert committed[0].settings == {
        "Financing_Terms.tenor_years": 15.0,
        "Financing_Terms.target_dscr": 1.3,
    }
    assert block.pareto.reconciliation is None


def test_the_pareto_screen_refuses_a_coupled_input(fakes: _Fakes) -> None:
    scenario = _scenario(
        generation={
            "technologies": {
                "wind": {"type": "wind", "capacity_mw": 100.0, "capacity_factor": 0.35}
            }
        }
    )
    settings = LenderSensitivitySettings(
        enabled=True,
        pareto_grid=(ParetoAxis("project.capacity_factor", (-0.02, 0.02)),),
    )
    block = fakes.build(scenario, settings)
    assert isinstance(block, LenderSensitivityBlock)
    assert block.pareto is None
    (line,) = [p for p in block.parts_not_run if p.startswith("Pareto screen:")]
    assert "coupled input" in line
    assert fakes.pareto_grid == []  # the search was never called


def test_the_pareto_screen_names_a_missing_term(fakes: _Fakes) -> None:
    block = fakes.build(_scenario(Financing_Terms__tenor_years=_DROP))
    assert isinstance(block, LenderSensitivityBlock)
    (line,) = [p for p in block.parts_not_run if p.startswith("Pareto screen:")]
    assert "no numeric Financing_Terms.tenor_years" in line


def test_a_flat_tornado_carries_the_engine_reason(fakes: _Fakes) -> None:
    fakes.flat = {
        "flat_metric": True,
        "flat_metric_reason": "debt is sized to the DSCR",
    }
    block = fakes.build(_scenario())
    assert isinstance(block, LenderSensitivityBlock)
    assert all(t.flat_reason == "debt is sized to the DSCR" for t in block.tornadoes)


def test_a_tornado_whose_base_misses_the_committed_figure_says_so(
    fakes: _Fakes,
) -> None:
    fakes.tornado_base = 1.25
    block = fakes.build(_scenario())
    assert isinstance(block, LenderSensitivityBlock)
    dscr = block.tornadoes[0]
    assert dscr.reconciliation is not None and "1.25" in dscr.reconciliation


@pytest.mark.parametrize(
    "part, prefix",
    [
        ("tornado", "Minimum period DSCR tornado:"),
        ("ke", "Cost-of-equity band:"),
        ("fx", "FX:"),
        ("pareto", "Pareto screen:"),
    ],
)
def test_a_part_that_raises_is_listed_and_the_others_still_run(
    fakes: _Fakes, part: str, prefix: str
) -> None:
    fakes.raise_in = part
    block = fakes.build(_scenario())
    assert isinstance(block, LenderSensitivityBlock)
    (line,) = [p for p in block.parts_not_run if p.startswith(prefix)]
    assert "not run: the part raised" in line
    ran = sum(
        bool(x) for x in (block.tornadoes, block.ke_band, block.fx_sweeps, block.pareto)
    )
    assert ran == 3


def test_sobol_runs_behind_its_own_flag_through_the_coupled_input_seam(
    fakes: _Fakes,
) -> None:
    scenario = _scenario(
        generation={
            "technologies": {
                "wind": {"type": "wind", "capacity_mw": 100.0, "capacity_factor": 0.35}
            }
        }
    )
    settings = LenderSensitivitySettings(enabled=True, sobol_enabled=True, sobol_n=16)
    block = fakes.build(scenario, settings)
    assert isinstance(block, LenderSensitivityBlock)
    (call,) = fakes.sobol_calls
    assert call["n"] == 16 and call["metrics"] == ["equity_npv", "max_debt_usd"]
    # The sample went through coherent_overrides: the technology moved with the project.
    sample = fakes.evaluated[-1]
    assert sample["project.capacity_factor"] == 0.38
    assert any(k.startswith("generation.technologies.wind") for k in sample)
    npv, debt = block.sobol
    assert [r.driver for r in npv.rows] == [
        "capex",
        "capacity_factor",
    ]  # widest ST first
    assert npv.rows[0].interactive is True and npv.rows[0].st_conf == 0.04
    assert debt.rows == [] and debt.flag_reason == "the sized debt never moves"
    assert (block.sobol_runs, block.sobol_n) == (384, 16)


def test_sobol_names_a_scenario_with_no_drivers(fakes: _Fakes) -> None:
    settings = LenderSensitivitySettings(enabled=True, sobol_enabled=True)
    block = fakes.build(_scenario(monte_carlo=_DROP), settings)
    assert isinstance(block, LenderSensitivityBlock)
    (line,) = [p for p in block.parts_not_run if p.startswith("Sobol indices:")]
    assert "no monte_carlo.parameters" in line
    assert fakes.sobol_calls == []


def test_the_section_is_not_run_when_no_part_can_run(fakes: _Fakes) -> None:
    fakes.raise_in = "tornado"
    out = fakes.build(
        _scenario(wacc=_DROP, fx=_DROP, Financing_Terms__tenor_years=_DROP)
    )
    assert isinstance(out, str)
    assert out.startswith("not run: no part could run (")
    assert "no wacc block" in out and "no enabled fx block" in out


def test_a_section_left_out_is_listed_after_pawn() -> None:
    scenario = _scenario()
    bundle = _empty_bundle(scenario)
    rows = sections_not_run(
        bundle,
        scenario,
        capital_risk_not_run=None,
        lender_sensitivities_not_run="not run: switched off",
    )
    names = [r.section for r in rows]
    assert SECTION_LENDER_SENSITIVITIES in names
    assert names.index(SECTION_LENDER_SENSITIVITIES) > names.index(
        "Global sensitivity: PAWN"
    )


# ── rendering ────────────────────────────────────────────────────────────────


def _empty_bundle(scenario: Mapping[str, Any]) -> Any:
    return compute_report_sensitivity(
        scenario,
        profile=ORDINARY_REPORT_SENSITIVITY_PROFILE,
        tornado_computer=lambda _s: None,
        morris_computer=lambda _s, *, n_trajectories: None,
        pawn_computer=lambda _s, *, n, s: None,
    )


@pytest.fixture(scope="module")
def api_case() -> Any:
    inputs = WindFarmInputs(
        site_name="Report seam",
        capacity_mw=148.9,
        capacity_factor=0.332,
        project_life_years=20,
        ppa_price_lkr_per_kwh=20.30,
        ppa_term_years=20,
        capex_total_usd=159_600_000.0,
        opex_annual_usd=5_000_000.0,
        fx_start_lkr_per_usd=333.79,
    )
    return run_report_case(inputs, generated_at="2026-11-21T00:00:00+00:00")


def _render(case: Any, block: Optional[LenderSensitivityBlock]) -> str:
    bundle = _empty_bundle(case.scenario_config)
    return render_report_html(
        build_report_context_from_case(case, bundle, lender_sensitivities=block)
    )


def test_the_section_renders_every_part_with_its_f5_caption(
    fakes: _Fakes, api_case: Any
) -> None:
    settings = LenderSensitivitySettings(enabled=True, sobol_enabled=True)
    block = fakes.build(_scenario(), settings)
    assert isinstance(block, LenderSensitivityBlock)
    html = _render(api_case, block)
    section = html.split("<h2>Lender Sensitivities</h2>", 1)[1].split("</section>", 1)[
        0
    ]
    assert "Sensitivity of the committed case, not a revised case." in section
    assert "Minimum period DSCR &mdash; one-at-a-time" in section
    assert "Debt capacity (sized debt) &mdash; one-at-a-time" in section
    assert "Cost of Equity &mdash; Build-Up WACC Band" in section
    assert "15.0% (committed)" in section or "15.00% (committed)" in section
    assert section.count("<h3>FX &mdash;") == 3
    assert "Financing Pareto Screen" in section
    assert "F-5:" in section


def test_no_block_means_no_section(api_case: Any) -> None:
    assert "<h2>Lender Sensitivities</h2>" not in _render(api_case, None)
