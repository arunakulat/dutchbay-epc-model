"""A single-currency debt mix no longer loses its FX risk profile to float rounding (#1850).

``compute_fx_risk_profile`` builds the debt-concentration Herfindahl index from the currency
shares in percent. With all debt in one currency, ``100 * x / x`` can round to
100.00000000000001, so the index came out a few ulps above 1 and ``FXRiskProfile`` refused
it ("debt_concentration_hhi must be in [0, 1]"). The caller treats FX as reporting-only, so
the run went on without its FX risk profile. Within a 1e-9 tolerance the index is now 1; a
value clearly outside [0, 1] is still refused.
"""

from __future__ import annotations

import dataclasses

import pytest

from analytics.fx.fx_builder import (
    _HHI_ROUNDING_TOL,
    _debt_concentration_hhi,
    compute_fx_curve,
    compute_fx_risk_profile,
    compute_fx_structured_block,
)
from analytics.fx.fx_contracts import FXRiskProfile, FXVolumetry
from tests.analytics.test_fx_builder import (
    _annual_rows,
    _debt_result,
    _full_fx_config,
)

#: A USD balance for which ``100 * x / x / 100`` squares to 1.0000000000000004.
_ROUNDING_BALANCE = 469635432.2264768


def _single_currency_profile(usd: float) -> FXRiskProfile:
    block = compute_fx_structured_block(
        config=_full_fx_config(),
        debt_result=_debt_result(),
        annual_rows=_annual_rows(),
    )
    block = dataclasses.replace(
        block,
        volumetry=[FXVolumetry(period=1, total_debt_lkr=0.0, total_debt_usd=usd)],
    )
    curve = compute_fx_curve(config=_full_fx_config(), annual_rows=_annual_rows())
    return compute_fx_risk_profile(fx_block=block, fx_curve=curve)


def test_the_balance_reproduces_the_rounding() -> None:
    """Control: the raw sum of squared shares is above 1 for this balance."""
    share = 100.0 * _ROUNDING_BALANCE / _ROUNDING_BALANCE
    raw = (share / 100.0) ** 2
    assert raw > 1.0
    assert raw - 1.0 < _HHI_ROUNDING_TOL


def test_a_single_currency_mix_keeps_its_risk_profile() -> None:
    profile = _single_currency_profile(_ROUNDING_BALANCE)
    assert profile.debt_concentration_hhi == 1.0
    assert profile.debt_usd_pct == pytest.approx(100.0)
    assert profile.var_95_usd_million > 0.0


@pytest.mark.parametrize(
    ("shares", "expected"),
    [
        ((0.0, 100.0, 0.0), 1.0),
        ((0.0, 100.00000000000001, 0.0), 1.0),
        ((30.0, 60.0, 10.0), 0.46),
        ((0.0, 0.0, 0.0), 0.0),
    ],
)
def test_the_index_is_the_sum_of_squared_shares_within_the_bounds(
    shares: tuple[float, float, float], expected: float
) -> None:
    assert _debt_concentration_hhi(*shares) == pytest.approx(expected, abs=1e-15)
    assert 0.0 <= _debt_concentration_hhi(*shares) <= 1.0


def test_a_value_clearly_above_one_is_left_for_the_contract_to_refuse() -> None:
    """Only rounding is absorbed: an inconsistent mix still fails validation."""
    hhi = _debt_concentration_hhi(0.0, 101.0, 0.0)
    assert hhi == pytest.approx(1.0201)
    with pytest.raises(ValueError, match="debt_concentration_hhi must be in"):
        FXRiskProfile(
            var_95_usd_million=1.0,
            cvar_95_usd_million=1.5,
            debt_lkr_pct=0.0,
            debt_usd_pct=101.0,
            debt_cny_pct=0.0,
            debt_concentration_hhi=hhi,
        )


def test_just_past_the_tolerance_is_not_clamped() -> None:
    share = 100.0 * (1.0 + 1e-9)  # squared, about 2e-9 above 1
    assert _debt_concentration_hhi(0.0, share, 0.0) > 1.0
