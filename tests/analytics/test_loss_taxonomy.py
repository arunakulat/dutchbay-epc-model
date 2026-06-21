"""Config-driven IEC 61400-15-2 loss taxonomy: fail-loud + honour finer losses.

Roadmap gap #2. The loss stack used to iterate a hardcoded four-key whitelist, so
any finer loss key a scenario author added (turbine_performance_pct, icing_pct, …)
was *silently dropped* and never reduced net AEP — a CASPER silent-failure hazard.
The taxonomy is now config-first (config/defaults.yaml
defaults.wind_resource.loss_taxonomy) and an unknown loss-shaped key fails loud.
The canonical back-compat keys are unchanged, so canonical economics are preserved.
"""

from __future__ import annotations

import pytest

from analytics.wind.losses_model import (
    apply_losses,
    compute_net_factor,
    default_loss_taxonomy,
    validate_loss_keys,
)
from wind_resource.bankable_aep import non_wake_retention

CANONICAL = {
    "wake_loss_pct": 7.28,
    "availability_pct": 97.0,
    "electrical_loss_pct": 2.0,
    "curtailment_pct": 2.0,
    "other_pct": 1.0,
}


def test_default_taxonomy_is_config_sourced() -> None:
    tax = default_loss_taxonomy()
    assert tax["wake_loss_pct"] == "reduction"
    assert tax["availability_pct"] == "uptime"
    # the optional IEC sub-loss the gap explicitly adds
    assert tax["high_wind_hysteresis_pct"] == "reduction"


def test_unknown_loss_key_fails_loud() -> None:
    with pytest.raises(ValueError, match="taxonomy"):
        apply_losses(100.0, {"wake_loss_pct": 5.0, "made_up_loss_pct": 3.0})


def test_total_loss_pct_result_field_is_ignored() -> None:
    """A losses block that carries its own result field (total_loss_pct) must not
    raise and must not change the net — it is metadata, not a loss input."""
    with_field = apply_losses(100.0, {**CANONICAL, "total_loss_pct": 12.0})
    without = apply_losses(100.0, CANONICAL)
    assert with_field.net_aep_gwh == pytest.approx(without.net_aep_gwh)


def test_canonical_back_compat_keys_preserve_factor() -> None:
    """The five canonical keys reproduce the exact retention product (no drift)."""
    expected = 0.9272 * 0.97 * 0.98 * 0.98 * 0.99  # wake7.28/avail97/elec2/curt2/other1
    assert apply_losses(100.0, CANONICAL).net_factor == pytest.approx(expected, rel=1e-9)


def test_finer_loss_now_reduces_aep_instead_of_being_dropped() -> None:
    """The core fix: a taxonomy loss the old whitelist ignored now bites."""
    net = apply_losses(100.0, {"turbine_performance_pct": 3.0}).net_aep_gwh
    assert net == pytest.approx(97.0)  # previously silently dropped -> would be 100.0


def test_high_wind_hysteresis_default_zero_is_inert() -> None:
    base = apply_losses(100.0, CANONICAL).net_aep_gwh
    with_zero = apply_losses(100.0, {**CANONICAL, "high_wind_hysteresis_pct": 0.0})
    assert with_zero.net_aep_gwh == pytest.approx(base)
    with_loss = apply_losses(100.0, {**CANONICAL, "high_wind_hysteresis_pct": 4.0})
    assert with_loss.net_aep_gwh == pytest.approx(base * 0.96)


def test_non_wake_retention_unchanged_by_dry_refactor() -> None:
    """bankable_aep.non_wake_retention now delegates to the taxonomy; the value for
    the canonical stack is identical (wake excluded)."""
    f = non_wake_retention(CANONICAL)
    assert f == pytest.approx(0.97 * 0.98 * 0.98 * 0.99)  # no wake term


def test_mc_fixed_retention_excludes_sampled_and_honours_new_keys() -> None:
    """The Monte-Carlo 'fixed' retention (everything except the sampled
    wake/electrical/availability) honours a newly itemised loss."""
    losses = {**CANONICAL, "icing_pct": 1.5}
    excl = {"wake_loss_pct", "electrical_loss_pct", "availability_pct"}
    # curtailment 2, other 1, icing 1.5 -> 0.98 * 0.99 * 0.985
    assert compute_net_factor(losses, exclude=excl) == pytest.approx(0.98 * 0.99 * 0.985)


def test_validate_loss_keys_guard() -> None:
    validate_loss_keys(CANONICAL)  # no raise
    with pytest.raises(ValueError, match="taxonomy"):
        validate_loss_keys({"typo_loss_pct": 1.0})
