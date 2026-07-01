#!/usr/bin/env python
"""Coverage suite for analytics.wind.pipeline_aep_v14.

Exercises the AEP pipeline wrapper end to end:
- ``validate_turbine_specs``: pass, the three documented mismatch raises, and
  the skip-when-absent branches.
- ``integrate_aep_pipeline``: missing-path raise, the no-Monte-Carlo path, the
  ``run_monte_carlo=True`` forced path (default losses), the config-driven MC
  path with custom losses/parameters/output, and the ``resource``-bootstrap
  branch.

Both heavy wind dependencies (``load_aep_from_summary``, ``run_monte_carlo_aep``)
are monkeypatched on the module namespace, so no network, file I/O, or heavy
simulation runs here. Deterministic.

Run:
    pytest tests/analytics/test_pipeline_aep_v14_coverage.py -q \
        --cov=analytics.wind.pipeline_aep_v14
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

import analytics.wind.pipeline_aep_v14 as pipe

REPO_ROOT = Path(__file__).resolve().parents[2]


# ═════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def aep_data() -> Dict[str, Any]:
    """Synthetic AEP summary as returned by the loader (consistent with config)."""
    return {
        "net_site_aep_gwh": 473.8,
        "capacity_factor": 0.339,
        "n_turbines": 15,
        "rated_power_mw": 10.0,
        "source_id": "ECMWF_ERA5_2020_2024_DUTCHBAY",
        "source_type": "ECMWF",
    }


@pytest.fixture
def consistent_config() -> Dict[str, Any]:
    """Config whose turbine specs agree with ``aep_data`` (15 x 10 MW = 150 MW)."""
    return {
        "project": {"capacity_mw": 150.0},
        "resource": {
            "aep_summary_path": "tests/mocks/aep_summary_dutchbay.json",
            "turbines": {"count": 15, "rated_power_mw": 10.0},
        },
    }


@pytest.fixture
def mc_results() -> Dict[str, Any]:
    """Synthetic Monte Carlo result block (exceedance convention: P90 < P50)."""
    return {
        "percentiles": {"p50": 473.8, "p75": 455.0, "p90": 431.18, "p99": 400.0},
        "statistics": {"mean": 473.0, "std": 28.0, "cv": 0.059},
        "n_scenarios": 100000,
    }


# ═════════════════════════════════════════════════════════════════════════════
# validate_turbine_specs
# ═════════════════════════════════════════════════════════════════════════════


def test_validate_turbine_specs_happy_path(
    consistent_config: Dict[str, Any], aep_data: Dict[str, Any]
) -> None:
    # All three checks pass; returns None without raising.
    assert pipe.validate_turbine_specs(consistent_config, aep_data) is None


def test_validate_turbine_specs_count_mismatch_raises(
    consistent_config: Dict[str, Any], aep_data: Dict[str, Any]
) -> None:
    aep_data["n_turbines"] = 16  # config says 15
    with pytest.raises(ValueError, match="Turbine count mismatch"):
        pipe.validate_turbine_specs(consistent_config, aep_data)


def test_validate_turbine_specs_rated_power_mismatch_raises(
    consistent_config: Dict[str, Any], aep_data: Dict[str, Any]
) -> None:
    # >0.1 MW tolerance breach (config 10.0 vs AEP 9.0).
    aep_data["rated_power_mw"] = 9.0
    with pytest.raises(ValueError, match="rated power mismatch"):
        pipe.validate_turbine_specs(consistent_config, aep_data)


def test_validate_turbine_specs_capacity_mismatch_raises(
    consistent_config: Dict[str, Any], aep_data: Dict[str, Any]
) -> None:
    # Turbine count/power agree but project capacity is inconsistent (>1 MW).
    consistent_config["project"]["capacity_mw"] = 200.0
    with pytest.raises(ValueError, match="Total capacity mismatch"):
        pipe.validate_turbine_specs(consistent_config, aep_data)


def test_validate_turbine_specs_absent_specs_skips_checks() -> None:
    # No config turbine specs and no project capacity: every guard is skipped and
    # the final log uses the '?' fallback because the AEP block is also empty.
    config: Dict[str, Any] = {}
    aep_data: Dict[str, Any] = {}
    assert pipe.validate_turbine_specs(config, aep_data) is None


def test_validate_turbine_specs_aep_specs_present_no_project_capacity(
    aep_data: Dict[str, Any],
) -> None:
    # AEP specs present, but config has no turbine specs and no project capacity:
    # count/power guards skipped, capacity block computes but project_capacity_mw
    # is falsy so no raise; final log uses the real product.
    config: Dict[str, Any] = {}
    assert pipe.validate_turbine_specs(config, aep_data) is None


# ═════════════════════════════════════════════════════════════════════════════
# integrate_aep_pipeline
# ═════════════════════════════════════════════════════════════════════════════


def test_integrate_aep_pipeline_missing_path_raises() -> None:
    with pytest.raises(ValueError, match="Missing resource.aep_summary_path"):
        pipe.integrate_aep_pipeline({"resource": {}})


def test_integrate_aep_pipeline_no_monte_carlo(
    monkeypatch: pytest.MonkeyPatch,
    consistent_config: Dict[str, Any],
    aep_data: Dict[str, Any],
) -> None:
    captured: Dict[str, Any] = {}

    def fake_loader(path: str, validate_manifest: bool) -> Dict[str, Any]:
        captured["path"] = path
        captured["validate_manifest"] = validate_manifest
        return aep_data

    def fake_mc(**kwargs: Any) -> Dict[str, Any]:  # pragma: no cover - must not run
        raise AssertionError("Monte Carlo should be disabled")

    monkeypatch.setattr(pipe, "load_aep_from_summary", fake_loader)
    monkeypatch.setattr(pipe, "run_monte_carlo_aep", fake_mc)

    result = pipe.integrate_aep_pipeline(consistent_config, validate_manifest=False)

    assert result is consistent_config
    assert result["resource"]["aep_normalized"] is aep_data
    assert "aep_mc_results" not in result["resource"]
    assert captured["path"] == "tests/mocks/aep_summary_dutchbay.json"
    assert captured["validate_manifest"] is False


def test_integrate_aep_pipeline_bootstraps_resource_block(
    monkeypatch: pytest.MonkeyPatch, aep_data: Dict[str, Any]
) -> None:
    # The loader is patched, so a config whose only resource content is the path
    # still exercises the "resource not in config" defensive bootstrap by having
    # the loader (not the config) supply turbine specs. We delete the resource
    # block right before attach to drive line 169-170.
    config: Dict[str, Any] = {
        "project": {"capacity_mw": 150.0},
        "resource": {"aep_summary_path": "x.json"},
        "monte_carlo": {"enabled": False},
    }

    def fake_loader(path: str, validate_manifest: bool) -> Dict[str, Any]:
        # Drop the resource block so the attach step must recreate it.
        config.pop("resource")
        return aep_data

    monkeypatch.setattr(pipe, "load_aep_from_summary", fake_loader)

    result = pipe.integrate_aep_pipeline(config)

    assert result["resource"]["aep_normalized"] is aep_data


def test_integrate_aep_pipeline_force_monte_carlo_default_losses(
    monkeypatch: pytest.MonkeyPatch,
    consistent_config: Dict[str, Any],
    aep_data: Dict[str, Any],
    mc_results: Dict[str, Any],
) -> None:
    captured: Dict[str, Any] = {}

    monkeypatch.setattr(
        pipe, "load_aep_from_summary", lambda path, validate_manifest: aep_data
    )

    def fake_mc(**kwargs: Any) -> Dict[str, Any]:
        captured.update(kwargs)
        return mc_results

    monkeypatch.setattr(pipe, "run_monte_carlo_aep", fake_mc)

    result = pipe.integrate_aep_pipeline(consistent_config, run_monte_carlo=True)

    assert result["resource"]["aep_mc_results"] is mc_results
    # No monte_carlo block in config -> defaults flow through.
    assert captured["n_scenarios"] == 100000
    assert captured["seed"] is None
    assert captured["export_scenarios"] is False
    assert captured["output_path"] is None
    # Loss means fall back to the centralised DEFAULT_WIND_LOSSES.
    assert captured["wake_loss_mean_pct"] == pipe.DEFAULT_WIND_LOSSES["wake_loss_pct"]
    assert (
        captured["availability_mean_pct"]
        == pipe.DEFAULT_WIND_LOSSES["availability_pct"]
    )
    assert (
        captured["electrical_loss_mean_pct"]
        == pipe.DEFAULT_WIND_LOSSES["electrical_loss_pct"]
    )
    # MC uncertainty std defaults.
    assert captured["wake_loss_std_pct"] == 2.0
    assert captured["availability_std_pct"] == 1.0
    assert captured["electrical_loss_std_pct"] == 0.5


def test_integrate_aep_pipeline_config_driven_mc_custom_params(
    monkeypatch: pytest.MonkeyPatch,
    aep_data: Dict[str, Any],
    mc_results: Dict[str, Any],
    tmp_path: Path,
) -> None:
    captured: Dict[str, Any] = {}
    out_path = str(tmp_path / "mc_scenarios.parquet")
    config: Dict[str, Any] = {
        "project": {"capacity_mw": 150.0},
        "resource": {
            "aep_summary_path": "aep.json",
            "turbines": {"count": 15, "rated_power_mw": 10.0},
            "losses": {
                "wake_loss_pct": 9.5,
                "availability_pct": 96.0,
                "electrical_loss_pct": 1.5,
            },
        },
        "monte_carlo": {
            "enabled": True,
            "n_scenarios": 2500,
            "seed": 42,
            "output_path": out_path,
            "parameters": {
                "wake_loss_std_pct": 3.0,
                "availability_std_pct": 0.75,
                "electrical_loss_std_pct": 0.25,
            },
        },
    }

    monkeypatch.setattr(
        pipe, "load_aep_from_summary", lambda path, validate_manifest: aep_data
    )

    def fake_mc(**kwargs: Any) -> Dict[str, Any]:
        captured.update(kwargs)
        return mc_results

    monkeypatch.setattr(pipe, "run_monte_carlo_aep", fake_mc)

    result = pipe.integrate_aep_pipeline(config)

    assert result["resource"]["aep_mc_results"] is mc_results
    # Custom config losses override the defaults.
    assert captured["wake_loss_mean_pct"] == 9.5
    assert captured["availability_mean_pct"] == 96.0
    assert captured["electrical_loss_mean_pct"] == 1.5
    # Custom MC params and run controls.
    assert captured["n_scenarios"] == 2500
    assert captured["seed"] == 42
    assert captured["wake_loss_std_pct"] == 3.0
    assert captured["availability_std_pct"] == 0.75
    assert captured["electrical_loss_std_pct"] == 0.25
    # output_path is set, so export_scenarios is enabled.
    assert captured["export_scenarios"] is True
    assert captured["output_path"] == out_path
