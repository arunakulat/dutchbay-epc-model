#!/usr/bin/env python3
"""
Focused unit tests for analytics.scenario_loader._resolve_fx.

Covers:
- Missing 'fx' key
- Scalar 'fx' (banned)
- Non-mapping 'fx'
- Missing 'start_lkr_per_usd'
- Non-numeric 'start_lkr_per_usd'
- Non-numeric 'annual_depr'
- Happy path mapping
"""

from __future__ import annotations

import pytest

from analytics.scenario_loader import _resolve_fx


def test_resolve_fx_missing_fx_key_raises():
    cfg = {"meta": {"name": "no_fx_here"}}
    with pytest.raises(ValueError) as excinfo:
        _resolve_fx(cfg)
    msg = str(excinfo.value)
    assert "FX configuration missing" in msg
    assert "fx.start_lkr_per_usd" in msg


def test_resolve_fx_scalar_fx_rejected():
    cfg = {"fx": 375.0}
    with pytest.raises(ValueError) as excinfo:
        _resolve_fx(cfg)
    msg = str(excinfo.value)
    assert "Scalar 'fx' not supported" in msg
    assert "start_lkr_per_usd" in msg


def test_resolve_fx_non_mapping_rejected():
    cfg = {"fx": ["not", "a", "mapping"]}
    with pytest.raises(ValueError) as excinfo:
        _resolve_fx(cfg)
    msg = str(excinfo.value)
    assert "FX configuration must be a mapping" in msg
    assert "start_lkr_per_usd" in msg


def test_resolve_fx_missing_start_key_rejected():
    cfg = {"fx": {"annual_depr": 0.03}}
    with pytest.raises(ValueError) as excinfo:
        _resolve_fx(cfg)
    msg = str(excinfo.value)
    assert "FX configuration missing" in msg
    assert "fx.start_lkr_per_usd" in msg


def test_resolve_fx_non_numeric_start_rejected():
    cfg = {"fx": {"start_lkr_per_usd": "not-a-number", "annual_depr": 0.02}}
    with pytest.raises(ValueError) as excinfo:
        _resolve_fx(cfg)
    msg = str(excinfo.value)
    assert "fx.start_lkr_per_usd must be a valid number" in msg


def test_resolve_fx_non_numeric_annual_depr_rejected():
    cfg = {"fx": {"start_lkr_per_usd": 375.0, "annual_depr": "nope"}}
    with pytest.raises(ValueError) as excinfo:
        _resolve_fx(cfg)
    msg = str(excinfo.value)
    assert "fx.annual_depr must be a valid number" in msg


def test_resolve_fx_happy_path_defaults_annual_depr_to_zero():
    cfg = {"fx": {"start_lkr_per_usd": 375}}
    result = _resolve_fx(cfg)
    assert result["start_lkr_per_usd"] == pytest.approx(375.0)
    assert result["annual_depr"] == pytest.approx(0.0)


def test_resolve_fx_happy_path_with_explicit_annual_depr():
    cfg = {"fx": {"start_lkr_per_usd": "400.5", "annual_depr": "0.025"}}
    result = _resolve_fx(cfg)
    assert result["start_lkr_per_usd"] == pytest.approx(400.5)
    assert result["annual_depr"] == pytest.approx(0.025)
