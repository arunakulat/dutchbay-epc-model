"""The report gateway sees the capex the engine financed (#1569, domain lane D-2).

The out-of-band emitters (``app/reports/capital_risk_emit.py``,
``interaction_grid_emit.py`` and ``tech_comparison_emit.py``) run the pipeline and then
re-load the scenario YAML for :func:`build_report_context`. For a scenario that declares
``capex.price_basis``, the YAML states the price-year capex, while the engine financed the
capex escalated to the construction draws. Two effects followed before the fix:

* the three statements booked PP&E and paid-in equity on the stated capex. Equity is the
  plug, so every tie-out still passed and nothing flagged it;
* the FX methodology was withheld, because the re-loaded config no longer hashed to the
  run manifest's ``config_sha256``.

The gateway now applies the same ``apply_capex_price_basis`` the pipeline applies. These
tests pin that, using the two committed dated scenarios.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.run_manifest import config_sha256
from analytics.scenario_loader import load_scenario_config
from analytics.three_statement import build_three_statement_from_run
from app.api.responses import CaseResult
from app.reports.report_model import ReportContext, build_report_context
from finance.capex_price_basis import APPLIED_KEY, apply_capex_price_basis

REPO_ROOT = Path(__file__).resolve().parents[2]
WIND = REPO_ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
SOLAR_BESS = REPO_ROOT / "scenarios" / "blue_whale_solar_bess_lot5b_2026.yaml"

# Escalation years from the 2026 price year to the one-year build's single draw, written
# out from each scenario's own dates: wind COD 2028 (draw 2027), solar + BESS COD 2029
# (draw 2028), 5%/yr.
CASES = [(WIND, 2027 - 2026), (SOLAR_BESS, 2028 - 2026)]
IDS = ["wind", "solar_bess"]


def _context(
    run: Mapping[str, Any], scenario_config: Mapping[str, Any]
) -> ReportContext:
    return build_report_context(
        CaseResult.from_pipeline_result(dict(run), scenario_variant="price-basis"),
        generated_at="2026-11-08T00:00:00Z",
        scenario_config=scenario_config,
        debt_result=run.get("debt_result"),
        annual_rows=run.get("annual_rows"),
        run_result=dict(run),
    )


@pytest.fixture(scope="module")
def runs() -> Dict[Path, Dict[str, Any]]:
    return {path: run_v14_pipeline(str(path)) for path, _ in CASES}


@pytest.mark.parametrize(("path", "years"), CASES, ids=IDS)
def test_report_from_the_reloaded_yaml_matches_the_evaluated_config(
    runs: Dict[Path, Dict[str, Any]], path: Path, years: int
) -> None:
    """Statements built from the re-loaded YAML equal those built from the run's own config."""
    run = runs[path]
    evaluated = run["scenario_result"]["config"]
    assert APPLIED_KEY in evaluated["capex"]  # the run's config is the escalated one

    reloaded = dict(load_scenario_config(str(path)))
    assert (
        "price_basis" in reloaded["capex"]
    )  # the emitters' input states the price year

    from_yaml = _context(run, reloaded)
    from_run = _context(run, evaluated)
    assert from_yaml.three_statement is not None
    assert from_yaml.three_statement.tie_outs_pass
    assert from_yaml.three_statement == from_run.three_statement


@pytest.mark.parametrize(("path", "years"), CASES, ids=IDS)
def test_paid_in_equity_carries_the_escalation(
    runs: Dict[Path, Dict[str, Any]], path: Path, years: int
) -> None:
    """Against the stated capex, year-1 paid-in equity and PP&E rise by stated x (1.05**n - 1)."""
    run = runs[path]
    reloaded = dict(load_scenario_config(str(path)))
    stated = float(reloaded["capex"]["usd_total"])
    expected_delta = stated * (1.05**years - 1.0)

    statements = _context(run, reloaded).three_statement
    assert statements is not None
    year1 = statements.balance_sheet[0]

    # Negative control: the statements on the un-escalated YAML (the pre-fix behaviour).
    unescalated = build_three_statement_from_run(
        {
            "annual_rows": list(run["annual_rows"]),
            "debt_result": dict(run["debt_result"]),
        },
        reloaded,
    )
    assert unescalated is not None
    stale = unescalated.balance_sheet[0]

    assert year1["paid_in_equity"] - stale.paid_in_equity == pytest.approx(
        expected_delta, abs=0.01
    )
    assert year1["ppe_net"] - stale.ppe_net == pytest.approx(expected_delta, rel=1e-6)

    uses = run["debt_result"]["funding"]["sources_and_uses"]["uses"]
    assert uses["capex_usd"] == pytest.approx(stated * 1.05**years, abs=0.01)


@pytest.mark.parametrize(("path", "years"), CASES, ids=IDS)
def test_fx_methodology_is_not_withheld_for_a_dated_scenario(
    runs: Dict[Path, Dict[str, Any]], path: Path, years: int
) -> None:
    """The re-loaded YAML, once applied, hashes to the run manifest's config digest."""
    run = runs[path]
    reloaded = dict(load_scenario_config(str(path)))
    manifest_hash = run["run_manifest"]["config_sha256"]

    assert (
        config_sha256(reloaded) != manifest_hash
    )  # why the report used to withhold it
    assert config_sha256(apply_capex_price_basis(reloaded)) == manifest_hash

    context = _context(run, reloaded)
    assert not any(
        "FX methodology withheld" in row.mitigation for row in context.risk_register
    )
