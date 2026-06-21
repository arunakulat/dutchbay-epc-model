"""EnergyCalculator P75/P90 must be the IEC 61400-15-2 exceedance build-up.

Regression for the flat-haircut bug: net P90 was ``gross * loss * 0.80`` — a crude
config multiplier mislabeled as an exceedance P-value (~P99 at typical sigma).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from wind_resource import EnergyCalculator
from wind_resource.bankable_aep import UncertaintyBudget, exceedance_levels


def _calc() -> EnergyCalculator:
    # A steady wind series is enough to produce a positive AEP for the assertion.
    df = pd.DataFrame({"ws_150m": np.full(8760, 9.0)})
    return EnergyCalculator(
        df=df, ws_column="ws_150m", turbine_model="iea_reference_10mw", num_turbines=15
    )


def test_net_aep_p_levels_are_iec_exceedance_not_flat_haircut() -> None:
    calc = _calc()
    net = calc.calculate_net_aep()
    p50 = net["net_aep_p50_mwh"]
    p75 = net["net_aep_p75_mwh"]
    p90 = net["net_aep_p90_mwh"]

    # Provenance: an IEC build-up, not a flat planning haircut.
    assert net["pvalue_method"] == "iec_61400_15_2"
    assert net["uncertainty_sigma_1yr_pct"] > 0.0
    # Monotone exceedance ordering.
    assert 0 < p90 < p75 < p50

    # P75/P90 must equal the canonical bankable IEC build-up off the same P50
    # (proves the calculator delegates to exceedance_levels rather than applying a
    # flat config multiplier such as the old 0.80).
    exc = exceedance_levels(
        p50 / 1000.0, UncertaintyBudget(), life_years=int(calc.ppa_years)
    )
    assert p75 == pytest.approx(exc.p75_gwh * 1000.0)
    assert p90 == pytest.approx(exc.p90_1yr_gwh * 1000.0)
    # And it is NOT the retired flat haircut (0.80 * P50).
    assert p90 != pytest.approx(0.80 * p50, rel=1e-3)
