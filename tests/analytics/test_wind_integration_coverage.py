#!/usr/bin/env python
"""Coverage suite for analytics.wind.wind_integration.

Exercises the wind-to-EPC integration bridge end to end:
- AEP loading wrapper (modules-available and disabled branches)
- Monte Carlo wrapper + P-value extraction (exceedance convention)
- Capacity-factor reverse derivation (valid, warn, and raise paths)
- Config integration across all three documented modes

All wind-analytics dependencies (``load_aep_from_summary``,
``run_monte_carlo_aep``) are monkeypatched on the module namespace, so no
network, file I/O, or heavy simulation runs here. Deterministic.

Run:
    pytest tests/analytics/test_wind_integration_coverage.py -q \
        --cov=analytics.wind.wind_integration
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

import analytics.wind.wind_integration as wi

REPO_ROOT = Path(__file__).resolve().parents[2]


# ═════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def aep_data() -> Dict[str, Any]:
    """Synthetic AEP summary as returned by the loader."""
    return {
        "net_site_aep_gwh": 473.8,
        "capacity_factor": 0.339,
        "n_turbines": 15,
        "rated_power_kw": 10000,
        "source_id": "ECMWF_ERA5_2020_2024_DUTCHBAY",
        "source_type": "ECMWF",
        "provenance": {"iec_standard_version": "61400-12-1:2022"},
    }


@pytest.fixture
def mc_results() -> Dict[str, Any]:
    """Synthetic Monte Carlo result block.

    Percentiles follow the AEP *exceedance* convention: higher P-value means
    a more conservative (lower) energy estimate, so P90 < P75 < P50.
    """
    return {
        "percentiles": {"p50": 473.8, "p75": 455.0, "p90": 431.18, "p99": 400.0},
        "confidence_intervals": {"ci95_lower": 410.0, "ci95_upper": 540.0},
        "statistics": {"mean": 473.0, "std": 28.0, "cv": 0.059},
        "n_scenarios": 100000,
    }


@pytest.fixture
def base_config() -> Dict[str, Any]:
    """Minimal finance config with project capacity."""
    return {"project": {"capacity_mw": 150.0}, "tariff": {"usd_per_mwh": 80.0}}


# ═════════════════════════════════════════════════════════════════════════════
# load_aep_for_project
# ═════════════════════════════════════════════════════════════════════════════


def test_load_aep_for_project_happy_path(
    monkeypatch: pytest.MonkeyPatch, aep_data: Dict[str, Any]
) -> None:
    captured: Dict[str, Any] = {}

    def fake_loader(path: str, validate_manifest: bool) -> Dict[str, Any]:
        captured["path"] = path
        captured["validate_manifest"] = validate_manifest
        return aep_data

    monkeypatch.setattr(wi, "WIND_MODULES_AVAILABLE", True)
    monkeypatch.setattr(wi, "load_aep_from_summary", fake_loader, raising=False)

    result = wi.load_aep_for_project("some/aep_summary.json", validate_manifest=False)

    assert result is aep_data
    assert captured["path"] == "some/aep_summary.json"
    assert captured["validate_manifest"] is False


def test_load_aep_for_project_raises_when_modules_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(wi, "WIND_MODULES_AVAILABLE", False)
    with pytest.raises(ImportError, match="Wind analytics modules not available"):
        wi.load_aep_for_project("anything.json")


# ═════════════════════════════════════════════════════════════════════════════
# run_aep_monte_carlo
# ═════════════════════════════════════════════════════════════════════════════


def test_run_aep_monte_carlo_happy_path(
    monkeypatch: pytest.MonkeyPatch, mc_results: Dict[str, Any]
) -> None:
    captured: Dict[str, Any] = {}

    def fake_mc(**kwargs: Any) -> Dict[str, Any]:
        captured.update(kwargs)
        return mc_results

    monkeypatch.setattr(wi, "WIND_MODULES_AVAILABLE", True)
    monkeypatch.setattr(wi, "run_monte_carlo_aep", fake_mc, raising=False)

    result = wi.run_aep_monte_carlo(
        aep_summary_path="aep.json",
        n_scenarios=2000,
        export_scenarios=True,
        output_path="out.parquet",
        seed=7,
    )

    assert result is mc_results
    assert captured["aep_summary_path"] == "aep.json"
    assert captured["n_scenarios"] == 2000
    assert captured["export_scenarios"] is True
    assert captured["output_path"] == "out.parquet"
    assert captured["seed"] == 7
    # Exceedance convention: P90 is more conservative (lower) than P50.
    assert result["percentiles"]["p90"] < result["percentiles"]["p50"]


def test_run_aep_monte_carlo_raises_when_modules_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(wi, "WIND_MODULES_AVAILABLE", False)
    with pytest.raises(ImportError, match="Cannot run Monte Carlo"):
        wi.run_aep_monte_carlo("aep.json")


# ═════════════════════════════════════════════════════════════════════════════
# compute_aep_p_values
# ═════════════════════════════════════════════════════════════════════════════


def test_compute_aep_p_values_defaults(mc_results: Dict[str, Any]) -> None:
    p_vals = wi.compute_aep_p_values(mc_results)
    assert set(p_vals) == {"p50", "p75", "p90", "p99"}
    # Exceedance ordering preserved across the default percentile set.
    assert p_vals["p99"] < p_vals["p90"] < p_vals["p50"]


def test_compute_aep_p_values_custom_and_missing(mc_results: Dict[str, Any]) -> None:
    # p10 is absent from the result block and must be silently skipped.
    p_vals = wi.compute_aep_p_values(mc_results, p_values=[50, 90, 10])
    assert p_vals == {"p50": 473.8, "p90": 431.18}
    assert "p10" not in p_vals


# ═════════════════════════════════════════════════════════════════════════════
# derive_capacity_factor_from_aep
# ═════════════════════════════════════════════════════════════════════════════


def test_derive_capacity_factor_typical() -> None:
    cf = wi.derive_capacity_factor_from_aep(net_aep_gwh=473.8, capacity_mw=150.0)
    # 473.8 / (150 * 8.760) == 0.3606...
    assert cf == pytest.approx(473.8 / (150.0 * 8.760))
    assert 0.15 <= cf <= 0.60


def test_derive_capacity_factor_zero_capacity_raises() -> None:
    with pytest.raises(ValueError, match="capacity_mw must be positive"):
        wi.derive_capacity_factor_from_aep(net_aep_gwh=100.0, capacity_mw=0.0)


def test_derive_capacity_factor_negative_aep_raises() -> None:
    with pytest.raises(ValueError, match="net_aep_gwh cannot be negative"):
        wi.derive_capacity_factor_from_aep(net_aep_gwh=-1.0, capacity_mw=150.0)


def test_derive_capacity_factor_above_one_raises() -> None:
    # AEP far exceeds the 100%-CF ceiling -> CF > 1 -> raise.
    with pytest.raises(ValueError, match="outside valid range"):
        wi.derive_capacity_factor_from_aep(net_aep_gwh=10_000.0, capacity_mw=1.0)


def test_derive_capacity_factor_low_cf_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # CF ~= 0.076, below the typical 15% floor -> warning, no raise.
    with caplog.at_level("WARNING", logger=wi.logger.name):
        cf = wi.derive_capacity_factor_from_aep(net_aep_gwh=100.0, capacity_mw=150.0)
    assert cf < 0.15
    assert any("outside typical wind range" in r.message for r in caplog.records)


# ═════════════════════════════════════════════════════════════════════════════
# integrate_aep_into_config
# ═════════════════════════════════════════════════════════════════════════════


def test_integrate_mode1_direct_injection(
    base_config: Dict[str, Any], aep_data: Dict[str, Any]
) -> None:
    out = wi.integrate_aep_into_config(config=base_config, aep_data=aep_data)

    assert "aep" not in base_config  # input not mutated
    block = out["aep"]
    assert block["net_aep_gwh"] == 473.8
    assert block["source_id"] == aep_data["source_id"]
    assert block["source_type"] == aep_data["source_type"]
    assert block["provenance"] == aep_data["provenance"]
    assert "monte_carlo_results" not in block
    assert block["capacity_factor_derived"] == pytest.approx(
        473.8 / (150.0 * 8.760)
    )


def test_integrate_mode2_load_from_data_lake(
    monkeypatch: pytest.MonkeyPatch,
    base_config: Dict[str, Any],
    aep_data: Dict[str, Any],
) -> None:
    monkeypatch.setattr(wi, "WIND_MODULES_AVAILABLE", True)
    monkeypatch.setattr(
        wi, "load_aep_from_summary", lambda path, validate_manifest: aep_data,
        raising=False,
    )
    out = wi.integrate_aep_into_config(
        config=base_config, aep_summary_path="aep.json"
    )
    assert out["aep"]["net_aep_gwh"] == 473.8
    assert out["aep"]["source_id"] == aep_data["source_id"]


def test_integrate_mode3_monte_carlo_p90(
    monkeypatch: pytest.MonkeyPatch,
    base_config: Dict[str, Any],
    aep_data: Dict[str, Any],
    mc_results: Dict[str, Any],
) -> None:
    monkeypatch.setattr(wi, "WIND_MODULES_AVAILABLE", True)
    monkeypatch.setattr(
        wi, "load_aep_from_summary", lambda path, validate_manifest: aep_data,
        raising=False,
    )
    monkeypatch.setattr(
        wi, "run_monte_carlo_aep", lambda **kw: mc_results, raising=False
    )

    out = wi.integrate_aep_into_config(
        config=base_config,
        aep_summary_path="aep.json",
        monte_carlo_config={"n_scenarios": 5000, "use_p_value": 90},
    )

    block = out["aep"]
    # P90 (conservative) value selected for revenue.
    assert block["net_aep_gwh"] == mc_results["percentiles"]["p90"]
    assert block["net_aep_gwh"] < mc_results["percentiles"]["p50"]
    mc_block = block["monte_carlo_results"]
    assert mc_block["percentiles"] == mc_results["percentiles"]
    assert mc_block["confidence_intervals"] == mc_results["confidence_intervals"]
    assert mc_block["statistics"] == mc_results["statistics"]
    assert mc_block["n_scenarios"] == 100000


def test_integrate_mode3_missing_p_value_falls_back_to_p50(
    monkeypatch: pytest.MonkeyPatch,
    base_config: Dict[str, Any],
    aep_data: Dict[str, Any],
    mc_results: Dict[str, Any],
) -> None:
    monkeypatch.setattr(wi, "WIND_MODULES_AVAILABLE", True)
    monkeypatch.setattr(
        wi, "run_monte_carlo_aep", lambda **kw: mc_results, raising=False
    )
    out = wi.integrate_aep_into_config(
        config=base_config,
        aep_data=aep_data,
        aep_summary_path="aep.json",
        monte_carlo_config={"use_p_value": 42},  # not present -> fallback
    )
    assert out["aep"]["net_aep_gwh"] == mc_results["percentiles"]["p50"]


def test_integrate_no_aep_returns_config_unchanged(
    base_config: Dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING", logger=wi.logger.name):
        out = wi.integrate_aep_into_config(config=base_config)
    assert "aep" not in out
    assert out == base_config
    assert any("No AEP data provided" in r.message for r in caplog.records)


def test_integrate_mc_without_summary_path_raises(
    base_config: Dict[str, Any], aep_data: Dict[str, Any]
) -> None:
    with pytest.raises(ValueError, match="requires aep_summary_path"):
        wi.integrate_aep_into_config(
            config=base_config,
            aep_data=aep_data,
            monte_carlo_config={"use_p_value": 90},
        )


def test_integrate_capacity_from_parameters_path(aep_data: Dict[str, Any]) -> None:
    # Capacity resolved from the parameters.capacity_mw fallback path.
    config = {"parameters": {"capacity_mw": 149.5}}
    out = wi.integrate_aep_into_config(config=config, aep_data=aep_data)
    assert out["aep"]["capacity_factor_derived"] == pytest.approx(
        473.8 / (149.5 * 8.760)
    )


def test_integrate_missing_capacity_raises(aep_data: Dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="capacity_mw not found"):
        wi.integrate_aep_into_config(config={"project": {}}, aep_data=aep_data)


# ═════════════════════════════════════════════════════════════════════════════
# Module-level import-fallback (graceful degradation)
# ═════════════════════════════════════════════════════════════════════════════


def test_import_fallback_disables_wind_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reimport the module with its wind deps broken to hit the except branch.

    Forces ``ImportError`` on the two optional submodules the module pulls in at
    load time, then reloads it: ``WIND_MODULES_AVAILABLE`` must flip to ``False``
    and a warning is emitted. The original module object is restored afterwards
    so other tests keep their live wind dependencies.
    """
    broken = "analytics.loader.aep_loader"
    original = sys.modules.get(broken)
    # A module object lacking ``load_aep_from_summary`` triggers the ImportError
    # raised by ``from ... import load_aep_from_summary``.
    monkeypatch.setitem(
        sys.modules, broken, importlib.util.module_from_spec(
            importlib.machinery.ModuleSpec(broken, loader=None)
        ),
    )
    try:
        reloaded = importlib.reload(wi)
        assert reloaded.WIND_MODULES_AVAILABLE is False
    finally:
        if original is not None:
            sys.modules[broken] = original
        importlib.reload(wi)

    # Sanity: after restoration the live module is healthy again.
    assert wi.WIND_MODULES_AVAILABLE is True
