#!/usr/bin/env python
"""Tests for analytics.mc.covenant — the shared DSCR covenant-floor resolver (#639).

The resolver was extracted verbatim from ``analytics.mc.engine`` (MOVE -> SHIM)
so the MC engine's fixed-debt breach test and the CASPER ``mc_risk`` block share
one floor resolution and cannot disagree. These tests pin:

- the 4-path config precedence and the 1.30 default;
- non-numeric / absent values falling through to the next path;
- the engine shim re-exporting the SAME function objects (zero drift);
- the committed mixed-covenant scenarios (equitycase, edge_extreme_stress),
  where the engine floor now also governs the CASPER block, and the canonical
  lendercase, where both historic resolutions already agreed at 1.30.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from analytics.mc.covenant import (
    DEFAULT_MIN_DSCR_COVENANT,
    MIN_DSCR_COVENANT_PATHS,
    resolve_config_value,
    resolve_min_dscr_covenant,
)

SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"


def _load(name: str) -> dict[str, Any]:
    with (SCENARIOS / name).open() as fh:
        cfg = yaml.safe_load(fh)
    assert isinstance(cfg, dict)
    return cfg


# ────────────────────────── resolve_config_value ──────────────────────────


def test_resolve_config_value_nested_and_absent() -> None:
    cfg = {"a": {"b": {"c": 1.25}}}
    assert resolve_config_value(cfg, "a.b.c") == pytest.approx(1.25)
    assert resolve_config_value(cfg, "a.b.missing") is None
    assert resolve_config_value(cfg, "missing.b.c") is None
    assert resolve_config_value({}, "a") is None


def test_resolve_config_value_non_numeric_is_none() -> None:
    cfg = {"a": {"b": "not-a-number"}, "c": [1.3], "d": None}
    assert resolve_config_value(cfg, "a.b") is None
    assert resolve_config_value(cfg, "c") is None
    assert resolve_config_value(cfg, "d") is None


def test_resolve_config_value_numeric_string_coerces() -> None:
    """YAML normally types numbers, but a quoted numeric still resolves (float())."""
    assert resolve_config_value({"a": "1.35"}, "a") == pytest.approx(1.35)


# ────────────────────────── resolve_min_dscr_covenant ─────────────────────


def test_precedence_constraints_wins_over_everything() -> None:
    cfg = {
        "constraints": {"min_dscr_covenant": 1.30},
        "Financing_Terms": {"target_dscr": 1.40, "min_dscr": 1.20},
        "monte_carlo": {"min_dscr_covenant": 1.10},
    }
    assert resolve_min_dscr_covenant(cfg) == pytest.approx(1.30)


def test_precedence_falls_through_each_path_in_order() -> None:
    """Dropping the winning path each time walks the documented precedence."""
    cfg: dict[str, Any] = {
        "constraints": {"min_dscr_covenant": 1.31},
        "Financing_Terms": {"target_dscr": 1.32, "min_dscr": 1.33},
        "monte_carlo": {"min_dscr_covenant": 1.34},
    }
    assert resolve_min_dscr_covenant(cfg) == pytest.approx(1.31)
    del cfg["constraints"]
    assert resolve_min_dscr_covenant(cfg) == pytest.approx(1.32)
    del cfg["Financing_Terms"]["target_dscr"]
    assert resolve_min_dscr_covenant(cfg) == pytest.approx(1.33)
    del cfg["Financing_Terms"]
    assert resolve_min_dscr_covenant(cfg) == pytest.approx(1.34)
    del cfg["monte_carlo"]
    assert resolve_min_dscr_covenant(cfg) == pytest.approx(DEFAULT_MIN_DSCR_COVENANT)


def test_non_numeric_path_value_falls_through() -> None:
    """A present-but-non-numeric covenant does not block the next path."""
    cfg = {
        "constraints": {"min_dscr_covenant": "n/a"},
        "Financing_Terms": {"target_dscr": 1.27},
    }
    assert resolve_min_dscr_covenant(cfg) == pytest.approx(1.27)


def test_default_is_covenant_spec_default() -> None:
    assert resolve_min_dscr_covenant({}) == pytest.approx(1.30)
    assert DEFAULT_MIN_DSCR_COVENANT == pytest.approx(1.30)


def test_precedence_tuple_matches_engine_contract() -> None:
    assert MIN_DSCR_COVENANT_PATHS == (
        "constraints.min_dscr_covenant",
        "Financing_Terms.target_dscr",
        "Financing_Terms.min_dscr",
        "monte_carlo.min_dscr_covenant",
    )


# ────────────────────────── engine shim (MOVE -> SHIM) ────────────────────


def test_engine_reexports_the_same_function_objects() -> None:
    """The engine path is behaviorally unchanged: its private names ARE the
    shared resolvers (identity, not copies), so the two surfaces cannot drift."""
    from analytics.mc import engine

    assert engine._resolve_config_value is resolve_config_value
    assert engine._resolve_min_dscr_covenant is resolve_min_dscr_covenant


# ────────────────────────── committed scenarios ────────────────────────────


def test_committed_lendercase_floor_unchanged_at_1_30() -> None:
    """Canonical lendercase: engine resolution and the historic CASPER path
    (Financing_Terms.target_dscr snapshot) agree at 1.30 — #639 moves nothing."""
    cfg = _load("dutchbay_lendercase_2025Q4.yaml")
    assert resolve_min_dscr_covenant(cfg) == pytest.approx(1.30)
    assert resolve_config_value(cfg, "Financing_Terms.target_dscr") == pytest.approx(
        1.30
    )


def test_committed_equitycase_adopts_engine_floor() -> None:
    """Equitycase carries mixed covenants: constraints.min_dscr_covenant 1.30 vs
    Financing_Terms.target_dscr 1.40. The engine floor (1.30) now governs the
    CASPER mc_risk block too (runtime-only surface; non-bankable scenario)."""
    cfg = _load("dutchbay_equitycase_2025Q4.yaml")
    assert resolve_min_dscr_covenant(cfg) == pytest.approx(1.30)
    assert resolve_config_value(cfg, "Financing_Terms.target_dscr") == pytest.approx(
        1.40
    )


def test_committed_edge_extreme_stress_adopts_engine_floor() -> None:
    """edge_extreme_stress: constraints.min_dscr_covenant 1.15 vs target_dscr 1.25;
    the engine floor (1.15) now governs the CASPER mc_risk block too."""
    cfg = _load("edge_extreme_stress.yaml")
    assert resolve_min_dscr_covenant(cfg) == pytest.approx(1.15)
    assert resolve_config_value(cfg, "Financing_Terms.target_dscr") == pytest.approx(
        1.25
    )
