#!/usr/bin/env python
"""Tests for the AEP losses model (#23).

Covers the gross → net loss stack, the net capacity factor, low/high loss
scenarios for the same gross AEP, and reproduction of the canonical DutchBay
net AEP (402.6 GWh) from gross (459.5 GWh) using the lender config's losses.

Context:
    Sprint 10 - Issue #23 (Implement AEP losses model).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from analytics.wind.losses_model import (
    apply_losses,
    build_aep_losses_block,
    compute_net_factor,
    net_capacity_factor,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

CANONICAL_STACK = {
    "wake_loss_pct": 5.0,
    "availability_pct": 97.0,
    "electrical_loss_pct": 2.0,
    "curtailment_pct": 2.0,
    "other_pct": 1.0,
}
GROSS_CANONICAL_GWH = 459.5
# Lender case after the 15 x IEA-10MW re-model + ERA5-fitted Weibull re-baseline:
# density-corrected farm gross (was 565.5 at the declared 8.32/2.1 Weibull).
LENDER_GROSS_GWH = 554.1


def test_reproduces_canonical_net_aep() -> None:
    """The canonical stack turns gross 459.5 into net ~402.6 GWh."""
    result = apply_losses(GROSS_CANONICAL_GWH, CANONICAL_STACK)
    assert result.net_aep_gwh == pytest.approx(402.6, abs=0.2)
    assert result.total_loss_pct == pytest.approx(12.4, abs=0.1)


def test_net_capacity_factor_matches_summary() -> None:
    """402.6 GWh over 149.5 MW gives the canonical CF ~0.307."""
    cf = net_capacity_factor(402.6, 149.5)
    assert cf == pytest.approx(0.307, abs=0.001)


def test_low_vs_high_losses_same_gross() -> None:
    """For one gross AEP, a heavier loss stack yields lower net AEP (#23)."""
    low = {"wake_loss_pct": 3.0, "availability_pct": 98.0, "electrical_loss_pct": 1.0}
    high = {"wake_loss_pct": 12.0, "availability_pct": 94.0, "electrical_loss_pct": 3.0}
    net_low = apply_losses(GROSS_CANONICAL_GWH, low).net_aep_gwh
    net_high = apply_losses(GROSS_CANONICAL_GWH, high).net_aep_gwh
    assert net_low > net_high
    assert net_high < GROSS_CANONICAL_GWH


def test_multiplicative_and_order_independent() -> None:
    """The net factor is the product of retentions, regardless of key order."""
    a = compute_net_factor({"wake_loss_pct": 5.0, "electrical_loss_pct": 2.0})
    b = compute_net_factor({"electrical_loss_pct": 2.0, "wake_loss_pct": 5.0})
    assert a == pytest.approx(b)
    assert a == pytest.approx(0.95 * 0.98)


def test_zero_losses_is_identity() -> None:
    result = apply_losses(100.0, {})
    assert result.net_factor == pytest.approx(1.0)
    assert result.net_aep_gwh == pytest.approx(100.0)
    assert result.total_loss_pct == pytest.approx(0.0)


def test_components_breakdown_present() -> None:
    result = apply_losses(GROSS_CANONICAL_GWH, CANONICAL_STACK)
    assert set(result.components) == set(CANONICAL_STACK)
    assert result.components["availability_pct"] == pytest.approx(0.97)
    assert result.components["wake_loss_pct"] == pytest.approx(0.95)


def test_invalid_percentage_raises() -> None:
    with pytest.raises(ValueError, match="Percentage must be in"):
        apply_losses(100.0, {"wake_loss_pct": 150.0})


def test_negative_gross_raises() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        apply_losses(-1.0, CANONICAL_STACK)


def test_zero_capacity_raises() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        net_capacity_factor(100.0, 0.0)


def test_output_block_shape() -> None:
    block = build_aep_losses_block(GROSS_CANONICAL_GWH, CANONICAL_STACK, 149.5)
    assert block["net_aep_gwh"] == pytest.approx(402.6, abs=0.2)
    assert block["net_capacity_factor"] == pytest.approx(0.307, abs=0.001)
    assert "loss_components" in block


def test_lender_config_losses_reproduce_summary() -> None:
    """The real lender config's resource.losses reproduces the canonical net AEP."""
    cfg = yaml.safe_load(LENDER_CONFIG.read_text())
    losses = cfg["resource"]["losses"]
    result = apply_losses(LENDER_GROSS_GWH, losses)
    assert result.net_aep_gwh == pytest.approx(473.8, abs=0.5)  # ERA5-fitted Weibull
