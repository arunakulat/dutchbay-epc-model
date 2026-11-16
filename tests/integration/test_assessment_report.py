"""The solar assessment report runs on any solar scenario (#1784).

``app/reports/solar_assessment.py`` is the shared form of a report first written for one
site. It reads every input from the scenario it is given, lists any analysis that cannot run
("write figures, list failure"), and renders a DBPL PDF.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

pytest.importorskip("pvlib")
pytest.importorskip("matplotlib")

from app.reports import solar_assessment as sa  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SOLAR = REPO / "scenarios" / "dutchbay_solar_only_2025Q4.yaml"


def _single_tech_copy(tmp_path: Path) -> Path:
    """The committed solar scenario without its per-technology block.

    The one-way sensitivity runner shocks ``project.capacity_factor``, which a scenario with a
    per-technology ``generation`` block refuses to reconcile; this copy lets every analysis run.
    """
    raw: Dict[str, Any] = yaml.safe_load(SOLAR.read_text(encoding="utf-8"))
    raw.pop("generation", None)
    path = tmp_path / "solar_single_tech.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def results(tmp_path_factory: pytest.TempPathFactory) -> Dict[str, Any]:
    tmp = tmp_path_factory.mktemp("solar")
    return sa.run_assessment(_single_tech_copy(tmp), trials=20, work_dir=tmp / "work")


def test_every_analysis_runs_on_a_solar_scenario(results: Dict[str, Any]) -> None:
    assert results["not_run"] == []
    for key, _ in sa._ANALYSES:
        assert key in results, key


def test_inputs_come_from_the_scenario(results: Dict[str, Any]) -> None:
    raw = yaml.safe_load(SOLAR.read_text(encoding="utf-8"))
    solar = raw["resource"]["solar"]
    assert results["resource"]["latitude"] == pytest.approx(solar["latitude"])
    assert results["resource"]["longitude"] == pytest.approx(solar["longitude"])
    tariff = raw["tariff"]["lkr_per_kwh"]
    base_row = next(r for r in results["tariff_sweep"] if r["factor"] == 1.0)
    assert base_row["tariff"] == pytest.approx(tariff)
    assert base_row["projIRR"] == pytest.approx(results["base"]["project_irr"])
    capex_row = next(r for r in results["capex_sweep"] if r["factor"] == 1.0)
    assert capex_row["capex_usd"] == pytest.approx(raw["capex"]["usd_total"])
    assert results["optimization"]["covenant"] == raw["Financing_Terms"]["target_dscr"]
    assert results["mc"]["parameters"] == [
        p["name"] for p in raw["monte_carlo"]["parameters"]
    ]


def test_breakevens_come_from_the_shared_solver(results: Dict[str, Any]) -> None:
    from analytics.core.parameter_solvers import solve_tariff_breakeven

    be = results["breakeven"]["project_npv"]
    assert be["status"] == "converged"
    again = solve_tariff_breakeven(
        results["scenario_path"],
        metric="project_npv",
        target_value=0.0,
        bounds=tuple(be["bracket"]),
    )
    assert again.breakeven_value == pytest.approx(be["tariff_lkr"])
    source = (REPO / "app" / "reports" / "solar_assessment.py").read_text()
    assert "_breakeven_tariff" not in source


def test_the_monte_carlo_ran_without_the_toy_engine(results: Dict[str, Any]) -> None:
    assert results["mc"]["n"] == 20 and results["mc"]["failed"] == 0


def test_project_irr_does_not_move_with_the_dscr_target(
    results: Dict[str, Any],
) -> None:
    irrs = {round(d["projIRR"], 6) for d in results["dscr"]["sweep"]}
    assert len(irrs) == 1


def test_a_per_technology_scenario_lists_the_sensitivity_and_still_reports(
    tmp_path: Path,
) -> None:
    R = sa.run_assessment(SOLAR, trials=5, work_dir=tmp_path)
    assert [n["analysis"] for n in R["not_run"]] == ["One-way sensitivity"]
    assert "reconcile" in R["not_run"][0]["reason"]
    assert R["base"]["min_dscr"] is not None


def test_a_scenario_without_inputs_lists_each_missing_analysis(tmp_path: Path) -> None:
    raw = yaml.safe_load(SOLAR.read_text(encoding="utf-8"))
    raw.pop("generation", None)
    del raw["resource"]["solar"]
    raw["monte_carlo"]["parameters"] = []
    path = tmp_path / "bare.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    R = sa.run_assessment(path, trials=5, work_dir=tmp_path / "work")
    missing = {n["analysis"]: n["reason"] for n in R["not_run"]}
    assert set(missing) == {"Solar resource (pvlib producer)", "Monte Carlo"}
    assert "monte_carlo.parameters" in missing["Monte Carlo"]
    assert "tariff_sweep" in R and "base" in R


def test_the_document_lists_what_did_not_run(results: Dict[str, Any]) -> None:
    R = copy.deepcopy(results)
    R["not_run"].append({"analysis": "Regional GHI map", "reason": "offline"})
    doc = sa.as_dbpl_document(R, {}, issue_date="2026-11-16")
    headings = [s["heading"] for s in doc["sections"]]
    assert headings[0] == "Scope and basis"
    assert headings[-1] == "Analyses not run"
    assert doc["sections"][-1]["table"]["rows"][0]["cells"] == [
        "Regional GHI map",
        "offline",
    ]
    html = sa.render_html(doc)
    assert "Analyses not run" in html and "{{" not in html


def test_the_location_map_is_drawn_from_the_scenario_coordinate(tmp_path: Path) -> None:
    pytest.importorskip("rasterio")
    calls = []

    def fake(lat: float, lon: float) -> float:
        calls.append((lat, lon))
        return 1800.0 + lat

    out = sa.make_location_map(1.0, 2.0, tmp_path, fetch=fake)
    assert out.exists() and (tmp_path / "site_region_ghi.tif").exists()
    lats = sorted({c[0] for c in calls})
    lons = sorted({c[1] for c in calls})
    assert lats[0] == pytest.approx(1.0 - sa.MAP_HALF_WIDTH_DEG)
    assert lons[-1] == pytest.approx(2.0 + sa.MAP_HALF_WIDTH_DEG)


def test_the_cli_writes_a_dbpl_pdf(tmp_path: Path) -> None:
    pytest.importorskip("weasyprint")
    import importlib.util

    from app.reports.dbpl import DbplDependencyError

    spec = importlib.util.spec_from_file_location(
        "gen_solar_report", REPO / "scripts" / "generate_solar_assessment_report.py"
    )
    assert spec and spec.loader
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    out = tmp_path / "out"
    try:
        rc = cli.main(
            [
                "--scenario",
                str(_single_tech_copy(tmp_path)),
                "--out",
                str(out),
                "--trials",
                "5",
                "--no-maps",
            ]
        )
    except DbplDependencyError as exc:  # pragma: no cover - incomplete [report] extra
        pytest.skip(str(exc))
    assert rc == 0
    pdf = next(out.glob("solar_assessment_*.pdf"))
    assert pdf.read_bytes().startswith(b"%PDF")
    results = json.loads((out / "results.json").read_text())
    assert {"analysis": "Maps", "reason": "not requested"} in results["not_run"]
    html = (out / "report.html").read_text()
    assert "MODEL-DERIVED SCREENING" in html
