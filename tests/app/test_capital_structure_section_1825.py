"""Capital-structure screening in the lender report (#1825 slice i).

The three optimizers are replaced by fakes through their own modules, so these tests check the
section's wiring and wording, not the optimizers (which have their own tests).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Mapping, Optional, Sequence

import pytest

import analytics.capital_structure_optimizer_v14 as cso
import analytics.optimization_v14 as opt
import app.reports.capital_structure_section as css
from app.models.inputs import WindFarmInputs
from app.reports.capital_structure_section import (
    DEFAULT_CAPITAL_STRUCTURE_SETTINGS,
    OBJECTIVE_KEY,
    SECTION_CAPITAL_STRUCTURE,
    CapitalStructureSettings,
    build_capital_structure_section,
    settings_from_config,
)
from app.reports.lender_report_emit import sections_not_run
from app.reports.renderer import render_report_html
from app.reports.report_model import CapitalStructureBlock
from app.reports.report_orchestration import (
    ORDINARY_REPORT_SENSITIVITY_PROFILE,
    build_report_context_from_case,
    compute_report_sensitivity,
    run_report_case,
)

ON = CapitalStructureSettings(enabled=True)
CAPEX = 150_000_000.0
LINE = 3_000_000.0


def _scenario(**constraints: Any) -> Dict[str, Any]:
    block: Dict[str, Any] = {"min_dscr_covenant": 1.3, "max_balloon_pct": 0.5}
    block.update(constraints)
    return {
        "constraints": {k: v for k, v in block.items() if v is not None},
        "capex": {"usd_total": CAPEX, "breakdown": {"contingency_usd": LINE}},
        "Financing_Terms": {
            "debt_ratio": 0.7,
            "mix": {"lkr_max": 0.45, "dfi_max": 0.1},
        },
    }


def _point(value: Any, objective: float, feasible: bool = True, **kpis: float) -> Any:
    return SimpleNamespace(
        value=value,
        objective=objective,
        constraints=kpis or {"min_dscr_period": 1.3},
        feasible=feasible,
        binding_constraints=() if feasible else tuple(kpis),
    )


class _Fakes:
    """Records what each optimizer was asked, and answers with a fixed curve."""

    def __init__(self) -> None:
        self.calls: Dict[str, Dict[str, Any]] = {}
        self.mix_feasible = True
        self.contingency_feasible_to = 0.10
        self.ceiling_binds_to: Optional[float] = 0.40
        self.base: Dict[str, float] = {
            OBJECTIVE_KEY: -90e6,
            "min_dscr_period": 1.3,
            "min_dscr": 1.22,
            "max_debt_usd": 58e6,
            "balloon_pct": 0.39,
            "llcr": 1.5,
        }
        self.shown_balloon = 0.39
        self.evaluated: List[Dict[str, Any]] = []
        self.mix_raises = False

    def debt_mix(self, path: str, **kw: Any) -> Any:
        self.calls["mix"] = kw
        if self.mix_raises:
            raise RuntimeError("engine refused the mix")
        curve = [
            _point((0.0, 0.4), -74e6, self.mix_feasible),
            _point((0.6, 0.0), -95e6, self.mix_feasible),
        ]
        violation = SimpleNamespace(
            key="min_dscr_period",
            bound_kind="minimum",
            required=1.3,
            achieved=1.21,
            shortfall=0.09,
            candidates_violating=2,
            candidates_total=2,
        )
        return SimpleNamespace(
            best=curve[0] if self.mix_feasible else None,
            curve=curve,
            feasible=self.mix_feasible,
            infeasible_reason=None if self.mix_feasible else "min_dscr_period binds",
            diagnostics=(
                None
                if self.mix_feasible
                else SimpleNamespace(binding_summary="dscr", violations=(violation,))
            ),
        )

    def contingency(self, path: str, **kw: Any) -> Any:
        self.calls["contingency"] = kw
        curve = [
            _point((f,), -90e6 - f * 1e8, f <= self.contingency_feasible_to + 1e-9)
            for f in (0.0, 0.05, 0.10, 0.15, 0.20)
        ]
        return SimpleNamespace(
            best=curve[0], curve=curve, feasible=True, diagnostics=None
        )

    def parameter(self, path: str, **kw: Any) -> Any:
        self.calls["gearing"] = kw
        curve = [
            SimpleNamespace(
                value=v, objective=self._equity_value(v), constraint=1.3, feasible=True
            )
            for v in (0.30, 0.40, 0.50, 0.60)
        ]
        return SimpleNamespace(best=curve[1], curve=curve, diagnostics=None)

    def _gearing(self, ceiling: float) -> float:
        cap = self.ceiling_binds_to
        return 0.389 if cap is None else min(ceiling, cap) * 0.97

    def _equity_value(self, ceiling: float) -> float:
        return -90e6 - (0.40 - min(ceiling, 0.40)) * 1e8

    def evaluate(self, path: str, overrides: Mapping[str, Any]) -> Mapping[str, Any]:
        self.evaluated.append(dict(overrides))
        if not overrides:
            return dict(self.base)
        if "Financing_Terms.debt_ratio" not in overrides:
            # A mix or contingency candidate read back for its shown KPIs: the headline
            # DSCR and sized debt follow the first override so each row is distinct.
            first = float(next(iter(overrides.values())))
            return {
                **self.base,
                "min_dscr": 1.2 + first / 10,
                "max_debt_usd": 50e6 + first * 1e6,
                "balloon_pct": self.shown_balloon,
            }
        ceiling = float(overrides["Financing_Terms.debt_ratio"])
        return {
            OBJECTIVE_KEY: self._equity_value(ceiling),
            "min_dscr_period": 1.3,
            "min_dscr": 1.22,
            "balloon_pct": 0.0 if ceiling < 0.35 else 0.39,
            "llcr": 1.5,
            "max_debt_usd": self._gearing(ceiling) * CAPEX,
        }


@pytest.fixture()
def fakes(monkeypatch: pytest.MonkeyPatch) -> _Fakes:
    f = _Fakes()
    monkeypatch.setattr(cso, "optimize_debt_mix", f.debt_mix)
    monkeypatch.setattr(cso, "optimize_capex_contingency", f.contingency)
    monkeypatch.setattr(opt, "optimize_parameter", f.parameter)
    return f


def _build(fakes: _Fakes, scenario: Mapping[str, Any], settings: Any = ON) -> Any:
    return build_capital_structure_section(
        "scenario.yaml", scenario, settings, evaluate=fakes.evaluate
    )


def _empty_bundle(scenario: Mapping[str, Any]) -> Any:
    return compute_report_sensitivity(
        scenario,
        profile=ORDINARY_REPORT_SENSITIVITY_PROFILE,
        tornado_computer=lambda _s: None,
        morris_computer=lambda _s, *, n_trajectories: None,
        pawn_computer=lambda _s, *, n, s: None,
    )


def _keys(constraints: Sequence[Any]) -> List[str]:
    return [c.key for c in constraints]


# ── settings ──────────────────────────────────────────────────────────────────


def test_the_section_is_off_by_default() -> None:
    assert settings_from_config(None) == DEFAULT_CAPITAL_STRUCTURE_SETTINGS
    assert settings_from_config({}).enabled is False


def test_settings_are_read_from_the_run_configuration() -> None:
    s = settings_from_config(
        {"enabled": True, "lkr_bounds": [0.1, 0.5], "gearing_steps": 5}
    )
    assert (s.enabled, s.lkr_bounds, s.gearing_steps) == (True, (0.1, 0.5), 5)
    assert s.dfi_bounds == DEFAULT_CAPITAL_STRUCTURE_SETTINGS.dfi_bounds


def test_a_malformed_bound_fails_loud() -> None:
    with pytest.raises(ValueError, match="lkr_bounds"):
        settings_from_config({"lkr_bounds": [0.1]})


# ── not run ───────────────────────────────────────────────────────────────────


def test_switched_off_is_a_stated_reason_and_runs_nothing(fakes: _Fakes) -> None:
    out = _build(fakes, _scenario(), DEFAULT_CAPITAL_STRUCTURE_SETTINGS)
    assert isinstance(out, str) and out.startswith("not run: switched off")
    assert fakes.calls == {}


@pytest.mark.parametrize(
    "scenario, missing",
    [
        ({"capex": {}}, "constraints block"),
        (_scenario(min_dscr_covenant=None), "min_dscr_covenant"),
        (_scenario(min_dscr_covenant=0), "min_dscr_covenant"),
    ],
)
def test_a_scenario_without_a_dscr_covenant_is_not_screened(
    fakes: _Fakes, scenario: Dict[str, Any], missing: str
) -> None:
    out = _build(fakes, scenario)
    assert isinstance(out, str) and out.startswith("not run:") and missing in out
    assert fakes.calls == {}


def test_a_committed_case_that_fails_every_covenant_is_not_screened(
    fakes: _Fakes,
) -> None:
    fakes.base["min_dscr_period"] = 1.1
    out = _build(fakes, _scenario(max_balloon_pct=0.1))
    assert isinstance(out, str) and "fails every declared covenant" in out
    assert "mix" not in fakes.calls


def test_the_not_run_list_names_the_section_first() -> None:
    listed = sections_not_run(
        _empty_bundle({}),
        {},
        capital_risk_not_run=None,
        capital_structure_not_run="not run: switched off",
    )
    assert listed[0].section == SECTION_CAPITAL_STRUCTURE
    assert listed[0].reason == "not run: switched off"


# ── the three searches ────────────────────────────────────────────────────────


def test_every_search_holds_the_scenario_covenants(fakes: _Fakes) -> None:
    block = _build(fakes, _scenario(min_llcr_covenant=1.2))
    assert isinstance(block, CapitalStructureBlock)
    assert _keys(fakes.calls["mix"]["constraints"]) == [
        "min_dscr_period",
        "llcr",
        "balloon_pct",
    ]
    assert fakes.calls["mix"]["objective_key"] == OBJECTIVE_KEY == "equity_npv"
    assert fakes.calls["contingency"]["base_capex_usd"] == CAPEX - LINE
    assert fakes.calls["gearing"]["constraint_min"] == 1.3
    assert block.covenants == [
        "min_dscr_period >= 1.3 (constraints.min_dscr_covenant)",
        "llcr >= 1.2 (constraints.min_llcr_covenant)",
        "balloon_pct <= 0.5 (constraints.max_balloon_pct)",
    ]
    # Shown beside the covenants, never screened on (#1859 domain D-1).
    assert block.shown_keys == ["min_dscr", "max_debt_usd"]
    assert block.committed_headline_dscr == 1.22
    assert [s.kind for s in block.searches] == [
        "Debt tranche mix",
        "Capex contingency",
        "Gearing ceiling",
    ]


def test_a_covenant_whose_kpi_is_unpublished_is_held_so_the_search_fails_loud(
    fakes: _Fakes,
) -> None:
    """#1859 assurance M06: a covenant the evaluation does not publish is not dropped."""
    del fakes.base["llcr"]
    block = _build(fakes, _scenario(min_llcr_covenant=1.2))
    assert isinstance(block, CapitalStructureBlock)
    assert "llcr" in _keys(fakes.calls["mix"]["constraints"])
    assert "llcr" in block.covenant_keys
    assert not any(line.startswith("llcr") for line in block.covenants_not_screened)


def test_realised_gearing_is_read_against_the_financed_capex(
    fakes: _Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#1859 assurance F2: an escalated capex no longer makes a binding ceiling read as breached."""
    financed = CAPEX * 1.05
    monkeypatch.setattr(css, "_financed_capex", lambda _s: financed)
    fakes.ceiling_binds_to = None
    real = fakes.evaluate

    def _binding(path: str, overrides: Mapping[str, Any]) -> Mapping[str, Any]:
        out = dict(real(path, overrides))
        if "Financing_Terms.debt_ratio" in overrides:
            # The engine caps debt at the ceiling times the FINANCED capex.
            out["max_debt_usd"] = (
                float(overrides["Financing_Terms.debt_ratio"]) * financed
            )
        return out

    fakes.evaluate = _binding  # type: ignore[method-assign]
    block = _build(fakes, _scenario())
    assert isinstance(block, CapitalStructureBlock)
    gearing = next(s for s in block.searches if s.kind == "Gearing ceiling")
    for row in gearing.candidates:
        ceiling = float(row.label.split("ceiling ", 1)[1].split("%", 1)[0]) / 100
        realised = float(row.label.split("realised ", 1)[1].split("%", 1)[0]) / 100
        assert realised == pytest.approx(ceiling, abs=0.0005), row.label
    assert "financed capex $157.5M" in gearing.searched


def test_the_financed_capex_carries_the_price_basis_escalation() -> None:
    from analytics.scenario_loader import load_scenario_config

    scenario = load_scenario_config("scenarios/blue_whale_wind_lot5b_2026.yaml")
    stated = float(scenario["capex"]["usd_total"])
    assert css._financed_capex(scenario) == pytest.approx(stated * 1.05, rel=1e-9)


def test_the_financed_capex_carries_the_capitalised_import_levies() -> None:
    """#1859 review F-A: the lender case's levies are in the gearing denominator.

    The lender case declares ``taxes_indirect`` lines, so the engine sizes debt on the
    base plus the capitalised import duties and unrecoverable capex VAT (#738). Read
    against the pre-levy base, its binding 30% ceiling would show 31.5% again.
    """
    from analytics.evaluation_v14 import evaluated_scenario_config
    from analytics.scenario_loader import load_scenario_config
    from finance.import_levies import compute_capex_uplift_usd, resolve_indirect_taxes

    scenario = load_scenario_config("scenarios/dutchbay_lendercase_2025Q4.yaml")
    evaluated = evaluated_scenario_config(scenario)
    base = float(evaluated["capex"]["usd_total"])
    indirect = resolve_indirect_taxes(evaluated)
    assert indirect is not None and indirect.has_capex_lines
    uplift = compute_capex_uplift_usd(base, indirect)
    assert uplift > 0.01 * base  # non-vacuous: the levies move the denominator
    assert css._financed_capex(scenario) == pytest.approx(base + uplift, rel=1e-9)


def test_a_covenant_the_committed_case_fails_is_shown_not_screened(
    fakes: _Fakes,
) -> None:
    block = _build(fakes, _scenario(max_balloon_pct=0.1))
    assert isinstance(block, CapitalStructureBlock)
    assert _keys(fakes.calls["mix"]["constraints"]) == ["min_dscr_period"]
    assert block.covenant_keys == ["min_dscr_period"]
    assert len(block.covenants_not_screened) == 1
    line = block.covenants_not_screened[0]
    assert line.startswith("balloon_pct <= 0.1 (constraints.max_balloon_pct)")
    assert "0.39" in line
    # #1859 domain D-3: the old premise ("would name no candidate") is gone.
    assert "name no candidate" not in line
    assert "a candidate that also clears it is marked" in line
    assert block.shown_keys == ["min_dscr", "max_debt_usd", "balloon_pct"]


def test_the_mix_search_names_its_best_feasible_candidate(fakes: _Fakes) -> None:
    block = _build(fakes, _scenario())
    mix = block.searches[0]
    assert mix.best_label == "LKR 0% / DFI 40% / USD 60%"
    assert mix.current == "LKR 45% / DFI 10% / USD commercial 45%"
    assert [c.best for c in mix.candidates] == [True, False]
    assert mix.infeasibility == []


def test_an_infeasible_mix_shows_the_infeasibility_register(fakes: _Fakes) -> None:
    fakes.mix_feasible = False
    mix = _build(fakes, _scenario()).searches[0]
    assert mix.best_label is None and mix.n_feasible == 0
    assert mix.infeasibility == [
        "min_dscr_period >= 1.3: closest candidate reached 1.21, short by 0.09; "
        "violated by 2 of 2 candidates"
    ]


def test_the_contingency_search_names_nothing_and_says_the_debt_is_resized(
    fakes: _Fakes,
) -> None:
    search = _build(fakes, _scenario()).searches[1]
    # #1859 domain D-1 b: no "covenant headroom" candidate is named.
    assert search.best_label is None and search.best_objective is None
    assert not any(c.best for c in search.candidates)
    assert search.note is not None and "above that a covenant fails" in search.note
    assert "equity absorbs the overrun" in search.note
    assert "headroom" not in search.note
    assert f"{LINE / (CAPEX - LINE):.1%}" in search.note
    # The shown KPIs are read back at each candidate's own capex.
    base = CAPEX - LINE
    assert {"capex.usd_total": base * 1.2} in fakes.evaluated
    assert search.candidates[-1].constraints["max_debt_usd"] == pytest.approx(
        50e6 + base * 1.2 * 1e6
    )


def test_a_scenario_that_derives_capex_from_its_breakdown_gets_no_contingency_search(
    fakes: _Fakes,
) -> None:
    scenario = _scenario()
    scenario["capex"]["derive_from_breakdown"] = True
    # A real derived scenario reconciles its breakdown to the total.
    scenario["capex"]["breakdown"]["turbines_usd"] = CAPEX - LINE
    block = _build(fakes, scenario)
    assert "contingency" not in fakes.calls
    assert block.searches_not_run == [
        "Capex contingency: not run: the scenario derives capex from its breakdown "
        "(capex.derive_from_breakdown is true), and the contingency search moves "
        "capex.usd_total, which the engine then refuses as a breakdown mismatch"
    ]


def test_a_search_that_raises_is_listed_and_the_others_still_run(
    fakes: _Fakes,
) -> None:
    fakes.mix_raises = True
    block = _build(fakes, _scenario())
    assert [s.kind for s in block.searches] == ["Capex contingency", "Gearing ceiling"]
    assert block.searches_not_run == [
        "Debt tranche mix: not run: the search raised RuntimeError: engine refused the "
        "mix"
    ]


def test_the_refinancing_cap_is_screened_on_the_balloon(fakes: _Fakes) -> None:
    scenario = _scenario(
        max_balloon_pct=0.1,
        refinancing={"enabled": True, "max_refinance_pct": 0.5},
    )
    block = _build(fakes, scenario)
    assert _keys(fakes.calls["mix"]["constraints"]) == [
        "min_dscr_period",
        "balloon_pct",
    ]
    assert fakes.calls["mix"]["constraints"][1].maximum == 0.5
    assert block.covenants[1] == (
        "balloon_pct <= 0.5 (constraints.refinancing.max_refinance_pct, the "
        "refinancing cap)"
    )
    assert block.covenants_not_screened[0].startswith(
        "balloon_pct <= 0.1 (constraints.max_balloon_pct)"
    )
    # The balloon is screened, so it is not repeated among the shown columns.
    assert block.shown_keys == ["min_dscr", "max_debt_usd"]


def test_a_disabled_refinancing_block_adds_no_cap(fakes: _Fakes) -> None:
    scenario = _scenario(refinancing={"enabled": False, "max_refinance_pct": 0.5})
    _build(fakes, scenario)
    assert _keys(fakes.calls["mix"]["constraints"]) == [
        "min_dscr_period",
        "balloon_pct",
    ]
    assert fakes.calls["mix"]["constraints"][1].maximum == 0.5  # max_balloon_pct only


def test_a_candidate_that_also_clears_a_not_screened_covenant_is_marked(
    fakes: _Fakes,
) -> None:
    block = _build(fakes, _scenario(max_balloon_pct=0.1))
    gearing = block.searches[2]
    # The 30% ceiling reads back no balloon, so it also clears the 0.1 cap.
    assert [c.also_clears for c in gearing.candidates] == [
        ["balloon_pct <= 0.1"],
        [],
        [],
        [],
    ]


def test_a_dscr_held_by_construction_is_said_so(fakes: _Fakes) -> None:
    scenario = _scenario()
    scenario["Financing_Terms"]["debt_sizing"] = "dual_dscr"
    block = _build(fakes, scenario)
    assert block.dscr_held_note is not None
    assert block.dscr_held_note.startswith(
        "The minimum period DSCR is 1.30 on every candidate"
    )
    assert "(Financing_Terms.debt_sizing: dual_dscr)" in block.dscr_held_note
    assert "cannot fail here" in block.dscr_held_note


def test_a_dscr_that_varies_gets_no_held_note(
    fakes: _Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _mix(path: str, **kw: Any) -> Any:
        curve = [
            _point((0.0, 0.4), -74e6, True, min_dscr_period=1.35),
            _point((0.6, 0.0), -95e6, True, min_dscr_period=1.3),
        ]
        return SimpleNamespace(best=curve[0], curve=curve, feasible=True)

    monkeypatch.setattr(cso, "optimize_debt_mix", _mix)
    block = _build(fakes, _scenario())
    assert block.dscr_held_note is None


def test_contingency_headroom_at_the_top_of_the_range_says_so(fakes: _Fakes) -> None:
    fakes.contingency_feasible_to = 0.20
    search = _build(fakes, _scenario()).searches[1]
    assert search.note is not None and "the top of the searched range" in search.note


def test_a_missing_contingency_line_is_listed_not_guessed(fakes: _Fakes) -> None:
    scenario = _scenario()
    scenario["capex"] = {"usd_total": CAPEX}
    block = _build(fakes, scenario)
    assert [s.kind for s in block.searches] == ["Debt tranche mix", "Gearing ceiling"]
    assert block.searches_not_run == [
        "Capex contingency: not run: the scenario declares no "
        "capex.breakdown.contingency_usd line"
    ]


def test_the_gearing_search_shows_realised_gearing_and_the_plateau(
    fakes: _Fakes,
) -> None:
    search = _build(fakes, _scenario()).searches[2]
    assert [c.label for c in search.candidates] == [
        "ceiling 30%, realised 29.1%",
        "ceiling 40%, realised 38.8%",
        "ceiling 50%, realised 38.8%",
        "ceiling 60%, realised 38.8%",
    ]
    # First of equal objectives, as the optimizer breaks ties.
    assert search.best_label == "ceiling 40%, realised 38.8%"
    assert search.note is not None and "tops out at 38.8%" in search.note


def test_a_ceiling_that_binds_nowhere_names_no_optimum(fakes: _Fakes) -> None:
    fakes.ceiling_binds_to = None
    search = _build(fakes, _scenario()).searches[2]
    assert search.best_label is None and search.best_objective is None
    assert not any(c.best for c in search.candidates)
    assert search.note is not None and "does not bind anywhere" in search.note


def test_a_ceiling_that_binds_throughout_says_so(fakes: _Fakes) -> None:
    """#1859 domain D-5: no DSCR-sculpt claim when gearing still rises at the top."""
    fakes.ceiling_binds_to = 1.0
    search = _build(fakes, _scenario()).searches[2]
    assert search.note is not None
    assert search.note.startswith("The gearing ceiling binds throughout")
    assert "DSCR sculpt" not in search.note


def test_the_gearing_search_holds_every_covenant_not_only_dscr(
    fakes: _Fakes,
) -> None:
    fakes.base["balloon_pct"] = 0.2
    block = _build(fakes, _scenario(max_balloon_pct=0.3))
    search = block.searches[2]
    # Every ceiling from 40% up reads back a 0.39 balloon: over the 0.3 cap the committed
    # case clears, so they fail though optimize_parameter (DSCR only) passed them all. The
    # 30% ceiling reads back no balloon and is the only feasible point.
    assert search.n_feasible == 1
    assert search.best_label == "ceiling 30%, realised 29.1%"
    assert [c.binding for c in search.candidates] == [[]] + [["balloon_pct"]] * 3


# ── rendering ─────────────────────────────────────────────────────────────────


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


def _render(case: Any, block: Optional[CapitalStructureBlock]) -> str:
    bundle = _empty_bundle(case.scenario_config)
    return render_report_html(
        build_report_context_from_case(case, bundle, capital_structure=block)
    )


def test_the_section_renders_with_its_f5_caption(
    fakes: _Fakes, api_case: Any, tmp_path: Path
) -> None:
    block = _build(fakes, _scenario(max_balloon_pct=0.1))
    html = _render(api_case, block)
    section = html.split("<h2>Capital Structure Screening</h2>", 1)[1].split(
        "</section>", 1
    )[0]
    assert "Screening of alternatives, not the committed structure." in section
    assert "headline minimum DSCR 1.22x" in section
    assert '<th style="text-align:right;">min_dscr (shown)</th>' in section
    assert "also within balloon_pct &lt;= 0.1" in section
    assert section.count("<h3>") == 3
    assert "Declared covenants not screened on" in section
    assert '<th style="text-align:right;">min_dscr_period</th>' in section
    assert "<strong>LKR 0% / DFI 40% / USD 60%</strong>" in section
    assert "F-5:" in section


def test_without_the_block_the_report_has_no_such_section(api_case: Any) -> None:
    assert "Capital Structure Screening" not in _render(api_case, None)
