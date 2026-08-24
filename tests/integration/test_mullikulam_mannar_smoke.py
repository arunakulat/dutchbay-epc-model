"""Smoke test for the config-driven Mullikulam 2x50 MW (Mannar) scenario.

A NEW project/location opened from JSON: Musali DS, Mannar (8.82N / 79.96E), Vestas
V150-5.6 proxy for the EN-156/5.0 spec turbine, hub 125 m (tip 200 <= 220, clearance
50 >= 25), Weibull FITTED from live ERA5 2020-2024 @125 m (the "hub YAML-sourced +
Weibull optimized" lesson), USD 3.96 c/kWh tariff (= 13.22 LKR at 333.79 FX).

Guards the reference scenario against rot and against a silent revert of any of these
config-sourced identity fields to a hand-set or Kalpitiya-inherited value.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any, Mapping

import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import validate_config_for_v14

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO = REPO_ROOT / "scenarios" / "mullikulam_2x50mw_mannar.yaml"
# #996 D3b: the financial-KPI oracle lives in a golden fixture, not the scenario.
EXPECTED_KPIS = (
    REPO_ROOT / "tests" / "fixtures" / "finance" / "mullikulam_expected_kpis.json"
)

# ``min_dscr`` is excluded because the debt sizer solves to its covenant target.
# Every other value KPI pinned by the fixture must remain responsive.
RESPONSIVE_KPIS = (
    "project_irr",
    "equity_irr",
    "project_npv",
    "equity_npv",
    "equity_moic",
    "avg_dscr",
    "llcr",
    "plcr",
)
MIN_RELATIVE_MOVE = 1e-4
DRIVERS = (
    ("tariff +10%", {"tariff.lkr_per_kwh": 14.542}),
    ("opex +25%", {"opex.usd_per_year": 1_400_000.0}),
)
FINANCIAL_TARGETS = {
    "project_irr": ("project_irr", 1.0, 0.002),
    "equity_irr": ("equity_irr", 1.0, 0.002),
    "project_npv_m_usd": ("project_npv", 1e-6, 0.1),
    "equity_npv_m_usd": ("equity_npv", 1e-6, 0.1),
    "equity_moic": ("equity_moic", 1.0, 0.002),
    "min_dscr": ("min_dscr", 1.0, 0.01),
    "avg_dscr": ("avg_dscr", 1.0, 0.002),
    "llcr": ("llcr", 1.0, 0.002),
    "plcr": ("plcr", 1.0, 0.002),
}


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_scenario_config(str(SCENARIO))


@pytest.fixture(scope="module")
def raw_config() -> dict[str, Any]:
    """Return the unvalidated YAML mapping for canonical-gateway perturbations."""
    loaded: dict[str, Any] = yaml.safe_load(SCENARIO.read_text(encoding="utf-8"))
    return loaded


def _evaluate_kpis(
    config: Mapping[str, Any], overrides: Mapping[str, float]
) -> dict[str, Any]:
    """Evaluate one in-memory case through the canonical gateway."""
    result = evaluate_with_overrides(
        config_path=None,
        raw_config=copy.deepcopy(dict(config)),
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
        if not math.isfinite(base) or not math.isfinite(shocked):
            unmoved.append(f"{key}: non-finite value {base!r} -> {shocked!r}")
            continue
        relative = abs(shocked - base) / max(abs(base), 1e-6)
        if relative <= MIN_RELATIVE_MOVE:
            unmoved.append(f"{key}: {base!r} -> {shocked!r} (rel {relative:.3e})")
    assert not unmoved, (
        f"{label} left fixture KPIs unresponsive — the vector may be returned rather "
        "than computed: " + "; ".join(unmoved)
    )


def _assert_debt_resized(
    base_kpis: Mapping[str, Any], shocked_kpis: Mapping[str, Any], label: str
) -> None:
    """Require a finite, material debt move from the dual-DSCR re-solve."""
    base_debt = float(base_kpis["max_debt_usd"])
    shocked_debt = float(shocked_kpis["max_debt_usd"])
    if not (math.isfinite(base_debt) and math.isfinite(shocked_debt)):
        raise AssertionError(
            f"{label} produced non-finite max_debt_usd: "
            f"{base_debt!r} -> {shocked_debt!r}"
        )
    relative = abs(shocked_debt - base_debt) / max(abs(base_debt), 1e-6)
    assert relative > MIN_RELATIVE_MOVE, (
        f"{label} did not materially resize debt: {base_debt!r} -> {shocked_debt!r} "
        f"(rel {relative:.3e})"
    )


@pytest.fixture(scope="module")
def gateway_kpis(raw_config: dict[str, Any]) -> dict[str, Any]:
    """Return the unperturbed vector from the canonical evaluation gateway."""
    return _evaluate_kpis(raw_config, {})


@pytest.fixture(scope="module")
def path_kpis() -> dict[str, Any]:
    """Return the authored-path vector for direct raw-gateway reconciliation."""
    result = evaluate_with_overrides(
        config_path=SCENARIO,
        raw_config=None,
        overrides={},
    )
    return dict(result.get("kpis", result))


def _assert_matches_fixture(kpis: Mapping[str, Any]) -> None:
    """Assert that every financial target remains bound to a live KPI."""
    expected = json.loads(EXPECTED_KPIS.read_text())
    for fixture_key, (kpi_key, scale, tolerance) in FINANCIAL_TARGETS.items():
        actual = float(kpis[kpi_key]) * scale
        assert actual == pytest.approx(float(expected[fixture_key]), abs=tolerance)


def test_location_and_turbine_are_yaml_sourced(cfg: dict) -> None:
    """Mannar location + Vestas V150-5.6 identity comes from config, consistently."""
    assert cfg["resource"]["era5"]["latitude"] == pytest.approx(8.82, abs=0.001)
    assert cfg["resource"]["era5"]["longitude"] == pytest.approx(79.96, abs=0.001)
    assert cfg["turbine"]["n_turbines"] == 10
    assert cfg["turbine"]["rotor_diameter_m"] == 150  # <= 160 m spec cap
    assert cfg["turbine"]["rated_power_mw"] == pytest.approx(5.6, abs=0.01)
    # Identity must be Mannar/56 MW, NOT a Kalpitiya/159.6 MW lender inheritance.
    # (capacity_mw drives revenue: capacity x CF x 8760, so a stale 159.6 silently
    # inflated generation ~3x — this guards against that regression recurring.)
    assert "Mannar" in cfg["project"]["location"]
    assert "Kalpitiya" not in cfg["project"]["location"]
    assert cfg["project"]["capacity_mw"] == pytest.approx(56.0, abs=0.01)


def test_hub_height_is_yaml_sourced_and_consistent(cfg: dict) -> None:
    """125 m comes from config, consistently across turbine / turbines / era5."""
    assert cfg["turbine"]["hub_height_m"] == 125
    assert cfg["resource"]["turbines"]["hub_height_m"] == 125
    assert cfg["resource"]["era5"]["hub_height_m"] == 125  # cross-asserted by adapter
    # tip = hub + rotor/2 = 200 m <= 220 m; clearance = hub - rotor/2 = 50 m >= 25 m
    tip = cfg["turbine"]["hub_height_m"] + cfg["turbine"]["rotor_diameter_m"] / 2
    clearance = cfg["turbine"]["hub_height_m"] - cfg["turbine"]["rotor_diameter_m"] / 2
    assert tip <= 220
    assert clearance >= 25


def test_weibull_is_the_era5_fitted_optimum(cfg: dict) -> None:
    """The Weibull is the ERA5-fitted Mannar shape, NOT a Kalpitiya-inherited value."""
    a = float(cfg["wind_resource"]["weibull_a"])
    k = float(cfg["wind_resource"]["weibull_k"])
    assert a == pytest.approx(7.97, abs=0.05)
    assert k == pytest.approx(2.506, abs=0.05)
    assert float(cfg["wind_resource"]["mean_wind_speed_ms"]) == pytest.approx(
        7.07, abs=0.1
    )


def test_tariff_is_the_usd_bid_in_lkr(cfg: dict) -> None:
    """3.96 USD c/kWh bid carried as 13.22 LKR/kWh at the corrected FX 333.79.

    (Was 11.88 = 0.0396 x the stale 300; the USD bid is preserved at the real rate.)
    """
    assert float(cfg["tariff"]["lkr_per_kwh"]) == pytest.approx(13.22, abs=0.001)


def test_curve_is_the_registered_approved_source(cfg: dict) -> None:
    """The Vestas curve resolves to its approved-source manifest id (global-reuse)."""
    from analytics.loader.aep_loader import APPROVED_SOURCES

    pc = cfg["resource"]["power_curve"]
    assert pc["curve_key"] == "vestas_v150_5p6"
    assert pc["source_id"] == "OEM_VESTAS_V150_56_PC"
    assert APPROVED_SOURCES[pc["source_id"]]["curve_key"] == "vestas_v150_5p6"


def test_scenario_passes_schemas(cfg: dict) -> None:
    validate_config_for_v14(cfg, str(SCENARIO), ["era5", "wind"])  # must not raise


def test_pipeline_runs_config_driven(cfg: dict) -> None:
    """The finance pipeline runs straight from the YAML (no Python overrides)."""
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    kpis = run_v14_pipeline(config=str(SCENARIO))["kpis"]
    # HONEST economics for one 56 MW Lot at Mannar (CF ~0.27) at the real 3.96 USc/kWh
    # WindForce bid: the project is uneconomic (LCOE ~5.5c > tariff). The earlier
    # project_irr~0.108 / equity_irr>0 asserts were an artifact of a 3x-inflated
    # capacity_mw (159.6 vs the real 56) — see the scenario's expected_results note.
    # M3e: degradation 0.005 -> 0.5 (honest 0.5%/yr aging) deepened it, and the IRR-floor
    # fix lets the project IRR report its true NEGATIVE value rather than 0.0.
    # TLCF-EXPIRY re-baseline (Wave-1 audit) deepened the already-negative economics
    # (losses now expire after the SL 6-year window, raising later-year cash tax). The
    # round-5 #5 interest-tax-shield fix then lifted equity slightly (the deal has little
    # taxable income to shield). The 5.9% FX-drift re-baseline (fx.annual_depr 0.03 -> 0.0589,
    # data-derived BIS 2005-2026 LKR depreciation) deepened it further as the flat-LKR
    # revenue erodes faster in USD terms. F5-01 then aligns the first operating row to
    # COD after construction: current projIRR -8.16%, eqIRR -18.59%.
    assert kpis["project_irr"] == pytest.approx(-0.0816, abs=0.005)
    assert kpis["project_irr"] < 0.0  # below break-even even undiscounted
    assert kpis["equity_irr"] == pytest.approx(
        -0.1859, abs=0.01
    )  # PR-B UIP LKR rate deepens it
    assert kpis["equity_irr"] < 0.0  # equity-destroying at the 3.96c bid
    assert kpis["project_npv"] < 0.0
    assert kpis["min_dscr"] == pytest.approx(
        1.30, abs=0.02
    )  # sizer holds DSCR, sizes debt down


def test_financial_fixture_matches_live_engine(cfg: dict) -> None:
    """Bind every golden financial KPI to the live engine so it cannot silently drift."""
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    kpis = run_v14_pipeline(config=str(SCENARIO))["kpis"]
    _assert_matches_fixture(kpis)
    # #996 D3b: financial KPIs come from the fixture; the scenario keeps net_aep (runtime).
    scen_er = cfg["expected_results"]
    assert "net_aep_p50_gwh" in scen_er and "net_aep_p90_gwh" in scen_er
    assert "project_irr" not in scen_er and "equity_moic" not in scen_er


def test_gateway_base_reconciles_with_the_pinned_fixture(
    gateway_kpis: dict[str, Any],
) -> None:
    """The responsiveness baseline must be the same vector the fixture pins."""
    _assert_matches_fixture(gateway_kpis)


def test_raw_gateway_base_matches_authored_path_exactly(
    gateway_kpis: dict[str, Any], path_kpis: dict[str, Any]
) -> None:
    """The perturbation baseline must equal the authored-path financial vector."""
    for kpi_key, _, _ in FINANCIAL_TARGETS.values():
        assert float(gateway_kpis[kpi_key]) == pytest.approx(
            float(path_kpis[kpi_key]), rel=0.0, abs=1e-12
        )


@pytest.mark.parametrize("label,overrides", DRIVERS, ids=[item[0] for item in DRIVERS])
def test_mullikulam_fixture_kpis_respond_to_economic_drivers(
    raw_config: dict[str, Any],
    gateway_kpis: dict[str, Any],
    label: str,
    overrides: dict[str, float],
) -> None:
    """TEST-01: every non-solved fixture KPI responds to a real driver."""
    shocked = _evaluate_kpis(raw_config, overrides)
    _assert_kpis_respond(gateway_kpis, shocked, label)
    financing = raw_config["Financing_Terms"]
    target_dscr = float(financing["target_dscr"])
    assert financing["debt_sizing"] == "dual_dscr"
    assert target_dscr == pytest.approx(1.30, abs=1e-12)
    for kpis in (gateway_kpis, shocked):
        assert kpis["min_dscr"] == pytest.approx(target_dscr, abs=1e-9)
        assert kpis["min_dscr_period"] == pytest.approx(target_dscr, abs=1e-9)
    _assert_debt_resized(gateway_kpis, shocked, label)


def test_mullikulam_responsiveness_guard_rejects_frozen_output(
    gateway_kpis: dict[str, Any],
) -> None:
    """VERIFY-01 negative control: a frozen-output stub must trip the guard."""
    with pytest.raises(AssertionError, match="returned rather than computed"):
        _assert_kpis_respond(gateway_kpis, dict(gateway_kpis), "frozen-output stub")


@pytest.mark.parametrize("bad_value", [math.nan, math.inf], ids=["nan", "infinity"])
def test_mullikulam_responsiveness_guard_rejects_non_finite_output(
    gateway_kpis: dict[str, Any], bad_value: float
) -> None:
    """VERIFY-01 negative control: non-finite KPIs cannot count as movement."""
    corrupted = dict(gateway_kpis)
    for key in RESPONSIVE_KPIS:
        corrupted[key] = bad_value
    with pytest.raises(AssertionError, match="non-finite value"):
        _assert_kpis_respond(gateway_kpis, corrupted, "non-finite stub")


@pytest.mark.parametrize("bad_value", [math.nan, math.inf], ids=["nan", "infinity"])
def test_mullikulam_debt_resize_guard_rejects_non_finite_output(
    gateway_kpis: dict[str, Any], bad_value: float
) -> None:
    """VERIFY-01 negative control: non-finite debt cannot prove resizing."""
    corrupted = dict(gateway_kpis)
    corrupted["max_debt_usd"] = bad_value
    with pytest.raises(AssertionError, match="non-finite max_debt_usd"):
        _assert_debt_resized(gateway_kpis, corrupted, "non-finite debt stub")
