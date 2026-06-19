#!/usr/bin/env python
"""Tests for AEP tornado sensitivities (#25).

Confirms the tornado runs end-to-end, reproduces the canonical base AEP, ranks
drivers by absolute swing, behaves directionally, and writes a CSV.

Context:
    Sprint 10 - Issue #25 (AEP tornado sensitivities).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from analytics.wind.aep_tornado import (
    AEPTornadoConfig,
    run_aep_tornado,
    tornado_from_config,
    write_tornado_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

EXPECTED_DRIVERS = {"wind_speed_bias", "shear_exponent", "losses", "power_curve"}
EXPECTED_COLUMNS = {
    "driver",
    "minus_label",
    "plus_label",
    "aep_minus_gwh",
    "aep_plus_gwh",
    "base_aep_gwh",
    "swing_gwh",
    "abs_swing_gwh",
    "swing_pct",
}


@pytest.fixture
def lender_cfg() -> dict:
    return yaml.safe_load(LENDER_CONFIG.read_text())


def test_base_reproduces_canonical(lender_cfg: dict) -> None:
    df = tornado_from_config(lender_cfg)
    assert df["base_aep_gwh"].iloc[0] == pytest.approx(402.6, abs=1.0)


def test_all_drivers_present(lender_cfg: dict) -> None:
    df = tornado_from_config(lender_cfg)
    assert set(df["driver"]) == EXPECTED_DRIVERS


def test_expected_columns(lender_cfg: dict) -> None:
    df = tornado_from_config(lender_cfg)
    assert EXPECTED_COLUMNS.issubset(df.columns)


def test_ranked_by_absolute_swing(lender_cfg: dict) -> None:
    df = tornado_from_config(lender_cfg)
    swings = df["abs_swing_gwh"].tolist()
    assert swings == sorted(swings, reverse=True)


def test_wind_bias_is_dominant(lender_cfg: dict) -> None:
    """AEP ~ cubic in wind speed, so wind bias should top the tornado."""
    df = tornado_from_config(lender_cfg)
    assert df["driver"].iloc[0] == "wind_speed_bias"


def test_all_swings_nonzero(lender_cfg: dict) -> None:
    df = tornado_from_config(lender_cfg)
    assert (df["abs_swing_gwh"] > 0).all()


def test_wind_bias_direction(lender_cfg: dict) -> None:
    """More wind → more AEP (plus setting exceeds minus setting)."""
    df = tornado_from_config(lender_cfg)
    wind = df[df["driver"] == "wind_speed_bias"].iloc[0]
    assert wind["aep_plus_gwh"] > wind["aep_minus_gwh"]


def test_losses_direction(lender_cfg: dict) -> None:
    """Heavier losses (plus setting) → lower AEP (negative signed swing)."""
    df = tornado_from_config(lender_cfg)
    losses = df[df["driver"] == "losses"].iloc[0]
    assert losses["swing_gwh"] < 0


def test_run_with_explicit_args() -> None:
    df = run_aep_tornado(
        weibull_a=8.32,
        weibull_k=2.1,
        losses={"wake_loss_pct": 5.0, "availability_pct": 97.0, "electrical_loss_pct": 2.0},
        n_turbines=23,
    )
    assert set(df["driver"]) == EXPECTED_DRIVERS
    assert df["base_aep_gwh"].iloc[0] > 0


def test_config_overrides_ranges(lender_cfg: dict) -> None:
    """A larger wind-bias range widens the wind swing."""
    narrow = tornado_from_config(lender_cfg, AEPTornadoConfig(wind_bias_pct=2.0))
    wide = tornado_from_config(lender_cfg, AEPTornadoConfig(wind_bias_pct=10.0))
    nw = narrow[narrow["driver"] == "wind_speed_bias"]["abs_swing_gwh"].iloc[0]
    ww = wide[wide["driver"] == "wind_speed_bias"]["abs_swing_gwh"].iloc[0]
    assert ww > nw


def test_write_tornado_csv(lender_cfg: dict, tmp_path: Path) -> None:
    df = tornado_from_config(lender_cfg)
    out = write_tornado_csv(df, str(tmp_path / "tornado.csv"))
    assert out.exists()
    text = out.read_text()
    assert "wind_speed_bias" in text and "swing_gwh" in text
