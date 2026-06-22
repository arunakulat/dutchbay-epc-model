"""Tests for ``finance.irr_config`` — YAML-driven IRR/XIRR bound extraction.

The module is a thin "Pattern 1" config helper: ``load_config`` reads a YAML
file from disk, and ``get_irr_bounds`` / ``get_xirr_bounds`` pluck validation
bounds out of the loaded ``irr_validation`` block. There is no dataclass — the
public surface is three plain functions over a ``dict``.

Coverage here:
  * ``load_config`` default-path resolution, custom paths, and the documented
    ``FileNotFoundError``.
  * ``get_irr_bounds`` project-level + role-specific (``equity``/``debt``)
    extraction, fallbacks, and the ``(None, None)`` empty-config contract.
  * ``get_xirr_bounds`` extraction and empty-config contract.
  * The values wired into the canonical master config match the docstring
    examples (a regression pin on the shipped numbers).

REGRESSION PIN (bug fixed in #304): the role-specific fallback once used
``lower = lower or irr_cfg.get("irr_lower_bound")``, so a legitimate bound of
``0.0`` (falsy) was silently replaced by the project-level fallback. It now uses
``lower if lower is not None else ...``; the test below pins the corrected
``0.0``-bound behaviour (there is no xfail — the defect is closed).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from finance.irr_config import get_irr_bounds, get_xirr_bounds, load_config

REPO_ROOT = Path(__file__).resolve().parents[2]
MASTER_CONFIG = REPO_ROOT / "scenarios" / "dutchbay_master_config_v14.yaml"


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


def test_load_config_explicit_path_returns_dict() -> None:
    """An explicit valid path yields the parsed YAML as a dict."""
    config = load_config(str(MASTER_CONFIG))
    assert isinstance(config, dict)
    assert "irr_validation" in config


def test_load_config_default_path_resolves_from_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    """``load_config(None)`` resolves the default master-config path from cwd."""
    monkeypatch.chdir(REPO_ROOT)
    config = load_config()  # default: scenarios/dutchbay_master_config_v14.yaml
    assert isinstance(config, dict)
    assert "irr_validation" in config


def test_load_config_missing_file_raises_filenotfound() -> None:
    """A non-existent path raises FileNotFoundError with a helpful message."""
    with pytest.raises(FileNotFoundError) as excinfo:
        load_config(str(REPO_ROOT / "scenarios" / "does_not_exist_xyz.yaml"))
    msg = str(excinfo.value)
    assert "Config file not found" in msg
    assert "does_not_exist_xyz.yaml" in msg


def test_load_config_default_missing_when_cwd_wrong(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """From a directory without the scenarios/ tree, the default path is missing."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        load_config()


# ---------------------------------------------------------------------------
# get_irr_bounds — project-level
# ---------------------------------------------------------------------------


def test_get_irr_bounds_project_level_from_master_config() -> None:
    """Project-level bounds match the shipped master-config values."""
    config = load_config(str(MASTER_CONFIG))
    lower, upper = get_irr_bounds(config)
    assert lower == -0.7
    assert upper == 0.35


def test_get_irr_bounds_project_level_from_constructed_dict() -> None:
    """Project-level extraction reads irr_lower/upper_bound verbatim."""
    config: Dict[str, Any] = {
        "irr_validation": {"irr_lower_bound": -0.6, "irr_upper_bound": 0.3}
    }
    assert get_irr_bounds(config) == (-0.6, 0.3)


def test_get_irr_bounds_no_irr_validation_returns_none_pair() -> None:
    """A config without an irr_validation block yields (None, None)."""
    assert get_irr_bounds({}) == (None, None)


def test_get_irr_bounds_empty_irr_validation_returns_none_pair() -> None:
    """An empty (falsy) irr_validation block yields (None, None)."""
    assert get_irr_bounds({"irr_validation": {}}) == (None, None)


def test_get_irr_bounds_partial_project_bounds() -> None:
    """A missing individual bound is reported as None, the other passes through."""
    config: Dict[str, Any] = {"irr_validation": {"irr_lower_bound": -0.4}}
    assert get_irr_bounds(config) == (-0.4, None)


# ---------------------------------------------------------------------------
# get_irr_bounds — role-specific (equity / debt)
# ---------------------------------------------------------------------------


def test_get_irr_bounds_equity_role_from_master_config() -> None:
    """role='equity' returns the equity-specific bounds."""
    config = load_config(str(MASTER_CONFIG))
    assert get_irr_bounds(config, role="equity") == (-0.5, 0.5)


def test_get_irr_bounds_debt_role_from_master_config() -> None:
    """role='debt' returns the debt-specific bounds."""
    config = load_config(str(MASTER_CONFIG))
    assert get_irr_bounds(config, role="debt") == (-0.2, 0.15)


def test_get_irr_bounds_unknown_role_falls_through_to_project() -> None:
    """An unrecognised role falls through to project-level bounds."""
    config = load_config(str(MASTER_CONFIG))
    # Neither 'equity' nor 'debt' -> project-level branch.
    assert get_irr_bounds(config, role="mezzanine") == (-0.7, 0.35)


def test_get_irr_bounds_role_none_is_project_level() -> None:
    """role=None is equivalent to project-level extraction."""
    config = load_config(str(MASTER_CONFIG))
    assert get_irr_bounds(config, role=None) == get_irr_bounds(config)


def test_get_irr_bounds_equity_absent_falls_back_to_project() -> None:
    """With no equity-specific keys, role='equity' falls back to project bounds."""
    config: Dict[str, Any] = {
        "irr_validation": {"irr_lower_bound": -0.7, "irr_upper_bound": 0.35}
    }
    # No equity_irr_* keys -> the role branch is skipped, project-level used.
    assert get_irr_bounds(config, role="equity") == (-0.7, 0.35)


def test_get_irr_bounds_equity_partial_fills_missing_from_project() -> None:
    """A role with only an upper bound borrows the lower bound from project level.

    The function documents this: "may still fall back to project-level for one".
    Here equity sets only the upper bound, so the lower bound is taken from the
    project-level value.
    """
    config: Dict[str, Any] = {
        "irr_validation": {
            "irr_lower_bound": -0.7,
            "irr_upper_bound": 0.35,
            "equity_irr_upper_bound": 0.6,
        }
    }
    lower, upper = get_irr_bounds(config, role="equity")
    assert lower == -0.7  # borrowed from project-level
    assert upper == 0.6  # equity-specific


def test_get_irr_bounds_debt_partial_fills_missing_from_project() -> None:
    """A debt role with only a lower bound borrows the upper from project level."""
    config: Dict[str, Any] = {
        "irr_validation": {
            "irr_lower_bound": -0.7,
            "irr_upper_bound": 0.35,
            "debt_irr_lower_bound": -0.25,
        }
    }
    lower, upper = get_irr_bounds(config, role="debt")
    assert lower == -0.25  # debt-specific
    assert upper == 0.35  # borrowed from project-level


def test_get_irr_bounds_zero_equity_lower_bound_not_clobbered() -> None:
    """A role lower bound of exactly 0.0 must be preserved, not overwritten.

    Regression for the `or`-based fallback that treated a legitimate 0.0 bound as
    falsy and substituted the project lower bound (-0.7); now an explicit
    `is not None` check preserves it.
    """
    config: Dict[str, Any] = {
        "irr_validation": {
            "irr_lower_bound": -0.7,
            "irr_upper_bound": 0.35,
            "equity_irr_lower_bound": 0.0,
            "equity_irr_upper_bound": 0.5,
        }
    }
    lower, _ = get_irr_bounds(config, role="equity")
    assert lower == 0.0

    # Project-level fallback still applies when a role bound is genuinely absent.
    cfg2: Dict[str, Any] = {
        "irr_validation": {
            "irr_lower_bound": -0.7,
            "equity_irr_upper_bound": 0.5,
        }
    }
    lo2, up2 = get_irr_bounds(cfg2, role="equity")
    assert lo2 == -0.7  # equity lower absent -> falls back to project level
    assert up2 == 0.5


# ---------------------------------------------------------------------------
# get_xirr_bounds
# ---------------------------------------------------------------------------


def test_get_xirr_bounds_from_master_config() -> None:
    """XIRR bounds match the shipped master-config values."""
    config = load_config(str(MASTER_CONFIG))
    assert get_xirr_bounds(config) == (-0.7, 0.25)


def test_get_xirr_bounds_from_constructed_dict() -> None:
    """XIRR extraction reads xirr_lower/upper_bound verbatim."""
    config: Dict[str, Any] = {
        "irr_validation": {"xirr_lower_bound": -0.55, "xirr_upper_bound": 0.2}
    }
    assert get_xirr_bounds(config) == (-0.55, 0.2)


def test_get_xirr_bounds_no_irr_validation_returns_none_pair() -> None:
    """A config without irr_validation yields (None, None) for XIRR too."""
    assert get_xirr_bounds({}) == (None, None)


def test_get_xirr_bounds_empty_irr_validation_returns_none_pair() -> None:
    """An empty irr_validation block yields (None, None)."""
    assert get_xirr_bounds({"irr_validation": {}}) == (None, None)


def test_get_xirr_bounds_missing_keys_returns_none_pair() -> None:
    """An irr_validation block without xirr keys yields (None, None)."""
    config: Dict[str, Any] = {
        "irr_validation": {"irr_lower_bound": -0.7, "irr_upper_bound": 0.35}
    }
    assert get_xirr_bounds(config) == (None, None)
