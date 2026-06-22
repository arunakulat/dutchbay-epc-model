"""Coverage tests for finance.cashflow_v14_production.

Targets the config-loading path of the wind-degradation profile that the
existing degradation suite does not exercise:

- ``_load_degradation_config`` (file-present / file-absent / empty-file)
- ``apply_degradation_profile`` with ``degradation_rate_pct=None`` so the
  rate/start_year/method are sourced from ``config/defaults.yaml`` (the
  ``enabled``-log and ``enabled: false`` no-log branches, plus the
  config-driven exponential method).

All expectations are DERIVED from first principles inside each test (the
linear factor ``(1 - r)^t`` and exponential factor ``exp(-r * t)`` with the
documented "decline accrues the year AFTER start_year" convention). No
economic magic numbers are hardcoded.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from finance.cashflow_v14_production import (
    _load_degradation_config,
    apply_degradation_profile,
)


@pytest.fixture
def chdir_tmp(tmp_path: Path) -> Iterator[Path]:
    """Run the test body with cwd set to an isolated temp directory.

    ``_load_degradation_config`` resolves ``config/defaults.yaml`` relative to
    the process cwd, so isolating cwd lets each test control exactly what (if
    anything) is on disk without touching the real repo config.
    """
    prev = Path.cwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(prev)


def _write_config(root: Path, body: str) -> None:
    """Write ``config/defaults.yaml`` under *root* with the given YAML body."""
    cfg_dir = root / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "defaults.yaml").write_text(body)


# --------------------------------------------------------------------------
# _load_degradation_config
# --------------------------------------------------------------------------


def test_load_config_absent_returns_empty(chdir_tmp: Path) -> None:
    """No config/defaults.yaml on disk -> the function returns ``{}``."""
    assert not (chdir_tmp / "config" / "defaults.yaml").exists()
    assert _load_degradation_config() == {}


def test_load_config_empty_file_returns_empty(chdir_tmp: Path) -> None:
    """An empty YAML file (safe_load -> None) is coalesced to ``{}``."""
    _write_config(chdir_tmp, "")
    assert _load_degradation_config() == {}


def test_load_config_without_wind_key_returns_empty(chdir_tmp: Path) -> None:
    """A populated config lacking ``wind_degradation`` returns ``{}``."""
    _write_config(chdir_tmp, "some_other_block:\n  foo: 1\n")
    assert _load_degradation_config() == {}


def test_load_config_with_wind_block_returns_block(chdir_tmp: Path) -> None:
    """The ``wind_degradation`` sub-mapping is returned verbatim."""
    _write_config(
        chdir_tmp,
        "wind_degradation:\n"
        "  annual_rate_pct: 1.0\n"
        "  start_year: 2\n"
        "  method: exponential\n"
        "  enabled: false\n",
    )
    cfg = _load_degradation_config()
    assert cfg == {
        "annual_rate_pct": 1.0,
        "start_year": 2,
        "method": "exponential",
        "enabled": False,
    }


# --------------------------------------------------------------------------
# apply_degradation_profile: config-driven (degradation_rate_pct is None)
# --------------------------------------------------------------------------


def test_none_rate_uses_config_linear_enabled(chdir_tmp: Path) -> None:
    """None rate + linear config (enabled default True) sources its params.

    The expected profile is derived independently from the linear factor
    ``(1 - r)^t`` with start_year=1 (so year 1 == base).
    """
    rate_pct = 0.5
    _write_config(
        chdir_tmp,
        f"wind_degradation:\n  annual_rate_pct: {rate_pct}\n",
    )
    aep_base = 100_000.0
    years = 4

    production = apply_degradation_profile(aep_base, years, degradation_rate_pct=None)

    r = rate_pct / 100.0
    expected = [aep_base * (1.0 - r) ** t for t in range(years)]
    assert production == pytest.approx(expected, rel=1e-12)
    # Year 1 is base; strictly declining thereafter.
    assert production[0] == pytest.approx(aep_base, rel=1e-12)
    for i in range(1, years):
        assert production[i] < production[i - 1]


def test_none_rate_uses_config_exponential_and_start_year(chdir_tmp: Path) -> None:
    """None rate + exponential config + start_year=2 (enabled: false).

    Exercises the ``enabled: false`` branch (no info log) AND the
    config-supplied method/start_year. Expectation derived from
    ``exp(-r * (year - start_year))`` with the convention that decline accrues
    the year AFTER start_year (years_since_start = 0 at year == start_year).
    """
    rate_pct = 1.0
    start_year = 2
    _write_config(
        chdir_tmp,
        "wind_degradation:\n"
        f"  annual_rate_pct: {rate_pct}\n"
        f"  start_year: {start_year}\n"
        "  method: exponential\n"
        "  enabled: false\n",
    )
    aep_base = 100_000.0
    years = 5

    production = apply_degradation_profile(aep_base, years, degradation_rate_pct=None)

    r = rate_pct / 100.0
    expected = []
    for year_idx in range(years):
        year_number = year_idx + 1
        if year_number < start_year:
            factor = 1.0
        else:
            factor = float(np.exp(-r * (year_number - start_year)))
        expected.append(aep_base * factor)

    assert production == pytest.approx(expected, rel=1e-12)
    # Year 1 (< start_year) and year 2 (== start_year) both sit at base.
    assert production[0] == pytest.approx(aep_base, rel=1e-12)
    assert production[1] == pytest.approx(aep_base, rel=1e-12)
    # Decline begins the year after start_year.
    assert production[2] < aep_base
    assert production[3] < production[2]


def test_none_rate_no_config_falls_back_to_defaults(chdir_tmp: Path) -> None:
    """None rate with no config file falls back to the 0.65%/yr linear default.

    The empty-config path returns ``{}`` so ``.get`` defaults apply
    (rate 0.65, start_year 1, linear). Expectation derived from ``(1 - r)^t``.
    """
    assert not (chdir_tmp / "config" / "defaults.yaml").exists()
    aep_base = 350_000.0
    years = 3

    production = apply_degradation_profile(aep_base, years, degradation_rate_pct=None)

    r = 0.65 / 100.0
    expected = [aep_base * (1.0 - r) ** t for t in range(years)]
    assert production == pytest.approx(expected, rel=1e-12)
