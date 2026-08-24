"""Smoke + binding test for the two SINOHYDRO-derived CAPEX cases.

Both scenarios are variants of ``dutchbay_lendercase_2025Q4.yaml`` that change ONLY the
capex level — resource, tariff and debt structure are identical — to isolate capex
sensitivity:

  * dutchbay_capex_sinohydro_lean_2025Q4.yaml   $977/kW   (SINOHYDRO Mannar 50 MW EPC scaled)
  * dutchbay_capex_eia_prudent_2025Q4.yaml      $1,420/kW (Envision Dutch Bay EIA Sep-2025)

vs the canonical $1,000/kW. The test (a) checks each scenario's capex block sums and
$/kW, (b) checks the capex-invariant resource fields are unchanged, (c) BINDS each
scenario's financial ``expected_results`` to the live pipeline (CESSPIT pre-flight
integrity — they cannot silently drift), and (d) asserts the directional invariant:
lower capex -> higher project IRR / NPV.

Honest finding both cases guard: even the lean $977/kW deal is value-destructive
(post 2% P50 haircut: project IRR 2.73% < WACC ~9.2%, NPV -$52.20M); the prudent
$1,420/kW case is deeply so (-0.76% / -$125.01M). The flat-nominal-LKR tariff, not
capex, is the binding constraint.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config

REPO_ROOT = Path(__file__).resolve().parents[2]
SCEN_DIR = REPO_ROOT / "scenarios"

# #996 D3b: the financial-KPI oracle lives in a golden fixture, not the scenarios.
_EXPECTED_KPIS = json.loads(
    (
        REPO_ROOT / "tests" / "fixtures" / "finance" / "capex_cases_expected_kpis.json"
    ).read_text()
)

CASES = {
    "lean_977": {
        "file": SCEN_DIR / "dutchbay_capex_sinohydro_lean_2025Q4.yaml",
        "usd_total": 155_929_200,
        "per_kw": 977,
    },
    "prudent_1420": {
        "file": SCEN_DIR / "dutchbay_capex_eia_prudent_2025Q4.yaml",
        "usd_total": 226_632_000,
        "per_kw": 1420,
    },
}

# expected_results key -> (live KPI key, scale, absolute tolerance) — mirrors the lender
# binding test tolerances (absorb 4-sig-fig YAML rounding, nothing more).
FINANCIAL_TARGETS = {
    "project_irr": ("project_irr", 1.0, 0.005),
    "equity_irr": ("equity_irr", 1.0, 0.005),
    "project_npv_m_usd": ("project_npv", 1e-6, 0.10),  # KPI is USD; target is $M
    "min_dscr": ("min_dscr", 1.0, 0.02),
    "avg_dscr": ("avg_dscr", 1.0, 0.02),
    "llcr": ("llcr", 1.0, 0.02),
    "plcr": ("plcr", 1.0, 0.02),
}

# ``min_dscr`` is excluded because the debt sizer solves to its covenant target.
# Every other value KPI pinned by the fixture must remain responsive.
RESPONSIVE_KPIS = (
    "project_irr",
    "equity_irr",
    "project_npv",
    "avg_dscr",
    "llcr",
    "plcr",
)
MIN_RELATIVE_MOVE = 1e-4
DRIVERS = (
    ("tariff +10%", {"tariff.lkr_per_kwh": 22.33}),
    ("opex +25%", {"opex.usd_per_year": 3_750_000.0}),
)


@pytest.fixture(scope="module")
def kpis() -> dict[str, dict[str, float]]:
    """Run the live pipeline once per case (module-scoped) and cache the KPIs."""
    return {
        name: run_v14_pipeline(config=str(case["file"]))["kpis"]
        for name, case in CASES.items()
    }


def _evaluate_kpis(
    raw_config: Mapping[str, Any], overrides: Mapping[str, float]
) -> dict[str, Any]:
    """Evaluate one in-memory case through the canonical gateway."""
    result = evaluate_with_overrides(
        config_path=None,
        raw_config=copy.deepcopy(dict(raw_config)),
        overrides=dict(overrides),
    )
    return dict(result.get("kpis", result))


def _assert_kpis_respond(
    base_kpis: Mapping[str, Any], shocked_kpis: Mapping[str, Any], label: str
) -> None:
    """Fail with an actionable list when any fixture value remains frozen."""
    unmoved = []
    for key in RESPONSIVE_KPIS:
        base, shocked = float(base_kpis[key]), float(shocked_kpis[key])
        relative = abs(shocked - base) / max(abs(base), 1e-6)
        if relative <= MIN_RELATIVE_MOVE:
            unmoved.append(f"{key}: {base!r} -> {shocked!r} (rel {relative:.3e})")
    assert not unmoved, (
        f"{label} left fixture KPIs unresponsive — the vector may be returned rather "
        "than computed: " + "; ".join(unmoved)
    )


@pytest.mark.parametrize("name", list(CASES))
def test_capex_block_sums_and_per_kw(name: str) -> None:
    """usd_total / capex_per_kw_usd are the case values and the breakdown sums to total."""
    case = CASES[name]
    cfg = load_scenario_config(str(case["file"]))
    capex = cfg["capex"]
    assert int(capex["usd_total"]) == case["usd_total"]
    assert int(capex["capex_per_kw_usd"]) == case["per_kw"]
    # breakdown is consistent (not a decorative-config mismatch)
    assert sum(int(v) for v in capex["breakdown"].values()) == case["usd_total"]


@pytest.mark.parametrize("name", list(CASES))
def test_resource_invariant_to_capex(name: str) -> None:
    """Only capex changed — resource fields equal the canonical lender case."""
    cfg = load_scenario_config(str(CASES[name]["file"]))
    assert float(cfg["project"]["capacity_mw"]) == pytest.approx(159.6, abs=0.01)
    assert float(cfg["expected_results"]["net_aep_p50_gwh"]) == pytest.approx(
        464.3, abs=0.5
    )
    # #996 D3b: net_aep_p90_gwh stays in the scenario (a runtime input for reconciliation
    # + downside debt); only the financial-KPI oracle moved to the fixture.
    assert float(cfg["expected_results"]["net_aep_p90_gwh"]) == pytest.approx(
        404.4, abs=0.5
    )
    assert float(cfg["expected_results"]["capacity_factor"]) == pytest.approx(
        0.332, abs=0.001
    )
    # #996 D3b: the financial-KPI oracle keys must NOT be back in the scenario (locks the
    # split so the case cannot re-become its own regression oracle).
    for moved in FINANCIAL_TARGETS:
        assert moved not in cfg["expected_results"], (
            f"{name}: {moved} is back in the scenario expected_results — it must live only "
            "in tests/fixtures/finance/capex_cases_expected_kpis.json"
        )


@pytest.mark.parametrize("name", list(CASES))
def test_expected_results_bind_to_engine(
    name: str, kpis: dict[str, dict[str, float]]
) -> None:
    """The live pipeline reproduces every financial target in the golden fixture."""
    expected = _EXPECTED_KPIS[name]
    live = kpis[name]
    mismatches = []
    for er_key, (kpi_key, scale, tol) in FINANCIAL_TARGETS.items():
        target = float(expected[er_key])
        actual = float(live[kpi_key]) * scale
        if abs(actual - target) > tol:
            mismatches.append(
                f"{er_key}: expected_results={target}, engine={actual:.5f} "
                f"(|Δ|={abs(actual - target):.5f} > {tol})"
            )
    assert not mismatches, (
        f"{name}: the golden fixture no longer matches the engine — regenerate "
        "tests/fixtures/finance/capex_cases_expected_kpis.json from the canonical run "
        "(do NOT hand-edit toward a rosier number):\n  " + "\n  ".join(mismatches)
    )


@pytest.mark.parametrize("name", list(CASES))
@pytest.mark.parametrize("label,overrides", DRIVERS, ids=[item[0] for item in DRIVERS])
def test_capex_fixture_kpis_respond_to_economic_drivers(
    name: str, label: str, overrides: dict[str, float]
) -> None:
    """TEST-01: every non-solved fixture KPI responds to real drivers."""
    raw_config = yaml.safe_load(Path(CASES[name]["file"]).read_text(encoding="utf-8"))
    base = _evaluate_kpis(raw_config, {})
    shocked = _evaluate_kpis(raw_config, overrides)
    _assert_kpis_respond(base, shocked, f"{name} / {label}")
    assert shocked["min_dscr"] == pytest.approx(base["min_dscr"], abs=1e-9)


def test_capex_responsiveness_guard_rejects_frozen_output(
    kpis: dict[str, dict[str, float]],
) -> None:
    """VERIFY-01 negative control: a frozen-output stub must trip the guard."""
    frozen = kpis["lean_977"]
    with pytest.raises(AssertionError, match="returned rather than computed"):
        _assert_kpis_respond(frozen, dict(frozen), "frozen-output stub")


def test_lower_capex_is_better(kpis: dict[str, dict[str, float]]) -> None:
    """Directional invariant: lean ($977/kW) beats prudent ($1,420/kW) on IRR and NPV."""
    lean, prudent = kpis["lean_977"], kpis["prudent_1420"]
    assert lean["project_irr"] > prudent["project_irr"]
    assert lean["equity_irr"] > prudent["equity_irr"]
    assert lean["project_npv"] > prudent["project_npv"]
