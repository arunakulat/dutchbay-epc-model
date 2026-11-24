"""Every reader of a capex amount sees the declared price date applied (#1899).

``capex.price_basis`` is applied once, by ``finance.capex_price_basis.apply_capex_price_basis``
(the pipeline and the batch path) or ``analytics.evaluation_v14.evaluated_scenario_config``
(a surface that re-loads the scenario). Before #1899, a tool that read ``capex.usd_total``
from the raw YAML used the stated price-year figure without saying so.

Three controls:

1. **Census.** Every non-test module that names a capex amount
   (``usd_total`` or a quoted ``breakdown``) is classified below. A new module fails until
   it is classified, and each classification is checked against the module's source.
2. **Guards.** Each resolver that reads capex refuses an unapplied ``price_basis`` and
   accepts the same scenario once applied.
3. **Gateways.** The tools that re-load a scenario read the escalated capex.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any, Callable, Dict

import pytest
import yaml

from finance.capex_price_basis import (
    APPLIED_KEY,
    UnappliedCapexPriceBasisError,
    apply_capex_price_basis,
    refuse_unapplied_price_basis,
)

ROOT = Path(__file__).resolve().parents[2]
WIND = ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
SOLAR_BESS = ROOT / "scenarios" / "blue_whale_solar_bess_lot5b_2026.yaml"

#: Calls a resolver of capex amounts refuses an unapplied price date through.
GUARD = "refuse_unapplied_price_basis"
#: Calls that apply the price date before capex is read.
GATEWAY = ("evaluated_scenario_config", "apply_capex_price_basis")
#: The guarded resolvers other modules delegate to.
GUARDED_RESOLVERS = (
    "_extract_capex_usd",
    "_extract_capex_base_usd",
    "_derive_capex_usd",
)

# Disposition of each module that names a capex amount.
#   guarded      reads capex and refuses an unapplied price date (calls GUARD)
#   gateway      applies the price date before it reads (calls a GATEWAY function)
#   delegates    reads only through a guarded resolver (GUARDED_RESOLVERS)
#   engine_input writes the stated amount into a config the pipeline then evaluates,
#                which applies the price date (perturbation drivers, authoring tools)
#   not_a_read   names the key in text, a schema, a label, a validation or the
#                price-basis module itself; no figure is computed from it
READERS: Dict[str, str] = {
    "analysis_tools/financing_questionnaire.py": "not_a_read",
    "analytics/capital_structure_optimizer_v14.py": "engine_input",
    "analytics/contracts_v14.py": "not_a_read",
    "analytics/core/metrics.py": "guarded",
    "analytics/core/parameter_solvers.py": "engine_input",
    "analytics/core/returns.py": "guarded",
    "analytics/core/sensitivity_runner.py": "engine_input",
    "analytics/cost/mc_capex.py": "gateway",
    "analytics/evaluate_scenario.py": "not_a_read",
    "analytics/evaluation_v14.py": "gateway",
    "analytics/feasibility_execution.py": "not_a_read",
    "analytics/feasibility_report_contract/assessment_scope.py": "not_a_read",
    "analytics/finance/fx_tenor_screening.py": "guarded",
    "analytics/mc/engine.py": "gateway",
    "analytics/pipeline_v14_enhanced.py": "gateway",
    "analytics/portfolio/multi_tech_tornado.py": "engine_input",
    "analytics/portfolio/tech_wbs.py": "delegates",
    "analytics/scenario_analytics.py": "gateway",
    "analytics/schema_guard.py": "not_a_read",
    "analytics/sensitivity/engine.py": "engine_input",
    "analytics/sensitivity/global_sa.py": "not_a_read",
    "analytics/sensitivity/interaction.py": "not_a_read",
    "analytics/storage_headline.py": "engine_input",
    "analytics/three_statement.py": "guarded",
    "analytics/what_if_cases.py": "engine_input",
    "analytics/wind/wind_bess_options.py": "engine_input",
    "analytics/wind/wind_bess_options_runner.py": "gateway",
    "api/pipeline_api.py": "gateway",
    "app/api/responses.py": "not_a_read",
    "app/models/inputs.py": "engine_input",
    "app/reports/capital_structure_section.py": "gateway",
    "app/reports/cost_storage_section.py": "gateway",
    "app/reports/report_model.py": "gateway",
    "app/reports/solar_assessment.py": "guarded",
    "finance/bess_lcos.py": "guarded",
    "finance/capex_price_basis.py": "not_a_read",
    "finance/cashflow_v14.py": "delegates",
    "finance/cashflow_v14_production.py": "not_a_read",
    "finance/cost_input_currency.py": "not_a_read",
    "finance/debt/capex.py": "guarded",
    "finance/debt/funding.py": "not_a_read",
    "finance/epc_helper_v14.py": "guarded",
    "finance/equity_distribution_v14_hydra.py": "guarded",
    "finance/native_cost_inputs.py": "not_a_read",
    "scripts/analysis/gen_scenario_yaml.py": "engine_input",
    "scripts/fix_metrics_typing.py": "not_a_read",
    "solar_resource/pv_bess_sizing.py": "engine_input",
}

_AMOUNT = re.compile(r"""usd_total|["']breakdown["']""")
_SKIP_DIRS = {"tests", ".venv", "node_modules", ".git", "outputs"}


def _readers_on_disk() -> set[str]:
    found = set()
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if rel.parts[0] in _SKIP_DIRS or any(p.startswith(".") for p in rel.parts):
            continue
        if _AMOUNT.search(path.read_text(encoding="utf-8", errors="replace")):
            found.add(rel.as_posix())
    return found


def test_every_capex_reader_is_classified() -> None:
    on_disk = _readers_on_disk()
    unclassified = sorted(on_disk - set(READERS))
    stale = sorted(set(READERS) - on_disk)
    assert (
        not unclassified
    ), f"classify these capex readers in READERS (#1899): {unclassified}"
    assert not stale, f"these READERS entries no longer read capex: {stale}"


@pytest.mark.parametrize(("module", "disposition"), sorted(READERS.items()))
def test_each_classification_matches_the_source(module: str, disposition: str) -> None:
    source = (ROOT / module).read_text(encoding="utf-8")
    if disposition == "guarded":
        assert GUARD in source
    elif disposition == "gateway":
        assert any(name in source for name in GATEWAY)
    elif disposition == "delegates":
        assert any(name in source for name in GUARDED_RESOLVERS)
    else:
        assert disposition in {"engine_input", "not_a_read"}


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def _raw(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "price_basis" in data["capex"]
    return data


def _debt(cfg: Dict[str, Any]) -> Any:
    from finance.debt.capex import _extract_capex_base_usd

    return _extract_capex_base_usd(cfg)


def _metrics(cfg: Dict[str, Any]) -> Any:
    from analytics.core.metrics import _derive_capex_usd

    return _derive_capex_usd(cfg)


def _epc(cfg: Dict[str, Any]) -> Any:
    from finance.epc_helper_v14 import _resolve_capex_usd_total

    return _resolve_capex_usd_total(cfg)


def _hydra(cfg: Dict[str, Any]) -> Any:
    from finance.equity_distribution_v14_hydra import _extract_capex_usd

    return _extract_capex_usd(cfg)


def _statements(cfg: Dict[str, Any]) -> Any:
    from analytics.three_statement import _resolve_capex_usd

    return _resolve_capex_usd(cfg)


def _returns(cfg: Dict[str, Any]) -> Any:
    from analytics.core.returns import ReturnsConfig

    return ReturnsConfig.from_yaml(cfg).capex_usd


def _screening(cfg: Dict[str, Any]) -> Any:
    from analytics.finance.fx_tenor_screening import scenario_screening_inputs

    return scenario_screening_inputs(cfg)["capex_usd"]


def _solar(cfg: Dict[str, Any]) -> Any:
    from app.reports.solar_assessment import scenario_capex

    return scenario_capex(cfg)


def _wbs(cfg: Dict[str, Any]) -> Any:
    from analytics.portfolio.tech_wbs import _resolve_financed_capex_usd

    return _resolve_financed_capex_usd(cfg)


GUARDED: Dict[str, Callable[[Dict[str, Any]], Any]] = {
    "debt": _debt,
    "kpi_metrics": _metrics,
    "epc_helper": _epc,
    "equity_distribution": _hydra,
    "three_statement": _statements,
    "returns": _returns,
    "fx_tenor_screening": _screening,
    "solar_assessment": _solar,
    "tech_wbs": _wbs,
}


@pytest.mark.parametrize("name", sorted(GUARDED))
def test_each_guarded_reader_refuses_an_unapplied_price_date(name: str) -> None:
    raw = _raw(WIND)
    with pytest.raises(UnappliedCapexPriceBasisError, match="price_basis has not been"):
        GUARDED[name](copy.deepcopy(raw))
    applied = apply_capex_price_basis(raw)
    assert GUARDED[name](applied) is not None


def test_the_lcos_resolver_refuses_an_unapplied_price_date() -> None:
    from finance.bess_lcos import resolve_lcos_specs

    raw = _raw(SOLAR_BESS)
    with pytest.raises(UnappliedCapexPriceBasisError):
        resolve_lcos_specs(copy.deepcopy(raw))
    assert resolve_lcos_specs(apply_capex_price_basis(raw))


def test_the_guard_is_case_insensitive_and_ignores_undeclared_configs() -> None:
    with pytest.raises(UnappliedCapexPriceBasisError):
        refuse_unapplied_price_basis({"Capex": {"Price_Basis": {}}}, "x")
    refuse_unapplied_price_basis({"capex": {"usd_total": 1.0}}, "x")
    refuse_unapplied_price_basis({}, "x")
    refuse_unapplied_price_basis({"capex": None}, "x")
    applied = apply_capex_price_basis(_raw(WIND))
    assert APPLIED_KEY in applied["capex"]
    refuse_unapplied_price_basis(applied, "x")


def test_the_guard_error_is_a_value_error() -> None:
    """Existing callers that catch ValueError still see the refusal."""
    assert issubclass(UnappliedCapexPriceBasisError, ValueError)


# ---------------------------------------------------------------------------
# Gateways: the re-loading tools read the escalated capex
# ---------------------------------------------------------------------------


def _escalated_usd_total(path: Path) -> float:
    from analytics.evaluation_v14 import evaluated_scenario_config

    return float(evaluated_scenario_config(_raw(path))["capex"]["usd_total"])


def test_fx_tenor_screening_reads_the_financed_capex() -> None:
    from analytics.finance.fx_tenor_screening import (
        run_fx_tenor_screening_for_scenario,
    )

    method = yaml.safe_load((ROOT / "conf" / "fx_tenor_screening.yaml").read_text())
    scenario = _raw(WIND)
    basecase = yaml.safe_load(
        (ROOT / "scenarios" / "dutchbay_basecase_2025Q4.yaml").read_text()
    )
    block = copy.deepcopy(basecase["financing_screening"])
    del block["tariff_om_escalation_decimal"]  # the scenario's om_indexation sets it
    scenario["financing_screening"] = block
    out = run_fx_tenor_screening_for_scenario(
        scenario, method["method"], scenario_label="wind"
    )
    assert out["status"] == "completed"
    assert out["scenario_inputs_applied"]["capex_usd"] == pytest.approx(
        _escalated_usd_total(WIND), rel=1e-12
    )
    stated = float(_raw(WIND)["capex"]["usd_total"])
    assert out["scenario_inputs_applied"]["capex_usd"] > stated


def test_the_solar_assessment_loads_the_financed_capex() -> None:
    from app.reports.solar_assessment import load_scenario, scenario_capex

    assert scenario_capex(load_scenario(SOLAR_BESS)) == pytest.approx(
        _escalated_usd_total(SOLAR_BESS), rel=1e-12
    )


def test_the_capex_monte_carlo_reports_the_financed_capex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trials perturb the stated capex; the pipeline escalates each; capex is reported
    on the financed basis."""
    import analytics.pipeline_v14_enhanced as pipeline
    from analytics.cost.mc_capex import run_capex_mc

    seen: list[float] = []

    def fake(*, config: Dict[str, Any]) -> Dict[str, Any]:
        assert "price_basis" in config["capex"]  # the pipeline applies it
        seen.append(float(config["capex"]["usd_total"]))
        return {
            "kpis": {
                "project_irr": 0.1,
                "equity_irr": 0.12,
                "project_npv": 1.0,
                "min_dscr": 1.3,
            }
        }

    monkeypatch.setattr(pipeline, "run_v14_pipeline", fake)
    from analytics.evaluation_v14 import evaluated_scenario_config

    raw = _raw(WIND)
    result = run_capex_mc(raw, n_samples=3, sigma_pct=10, seed=1)
    stated = float(raw["capex"]["usd_total"])
    factor = float(apply_capex_price_basis(raw)["capex"][APPLIED_KEY]["factor"])
    assert factor > 1.0
    # The financed base is the escalated capex plus the declared headline battery
    # (#1823), so it exceeds the stated capex times the price-date factor.
    assert result.base_capex_usd == pytest.approx(_escalated_usd_total(WIND), rel=1e-12)
    assert result.base_capex_usd > stated * factor

    def financed(stated_trial: float) -> float:
        trial = copy.deepcopy(raw)
        trial["capex"]["usd_total"] = stated_trial
        return float(evaluated_scenario_config(trial)["capex"]["usd_total"])

    assert result.capex_usd["p50"] == pytest.approx(
        financed(sorted(seen)[1]), rel=1e-12
    )


def test_the_solar_assessment_monte_carlo_starts_from_the_scenario_as_written(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A trial may replace capex with a draw from the price-year range; each trial's
    pipeline must then escalate it, so the MC starts from the unapplied scenario."""
    import analytics.mc.engine as engine
    import app.reports.solar_assessment as sa

    for name in (
        "_resource",
        "kpis",
        "_tariff_sweep",
        "_capex_sweep",
        "_sensitivity",
        "_gearing",
        "_dscr_targets",
    ):
        monkeypatch.setattr(sa, name, lambda *a, **k: {})
    seen: list[Dict[str, Any]] = []

    class _Captured(Exception):
        pass

    def fake_mc(*, base_config: Dict[str, Any], **_: Any) -> Any:
        seen.append(copy.deepcopy(base_config))
        raise _Captured

    monkeypatch.setattr(engine, "run_monte_carlo_analysis", fake_mc)
    sa.run_assessment(WIND, trials=2, work_dir=tmp_path)
    assert len(seen) == 1
    capex = seen[0]["capex"]
    assert "price_basis" in capex
    assert APPLIED_KEY not in capex
    assert float(capex["usd_total"]) == float(_raw(WIND)["capex"]["usd_total"])
