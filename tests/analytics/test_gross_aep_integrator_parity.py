"""Pin the agreement between the two analytic gross-AEP integrators (#1281).

The repository carries two independently written integrations of a power curve over a
site Weibull:

- :func:`analytics.wind.aep_tornado.gross_aep_farm_gwh` — the PRODUCTION path, called by
  :func:`analytics.wind.aep_summary_builder.build_aep_summary_from_config`. Cut-out is
  implicit: ``np.interp(..., right=0.0)``, so the supplied curve must encode it.
- :func:`wind_resource.bankable_aep.gross_aep_weibull` — no production caller, retained
  as the independently written cross-check. Cut-out is explicit: power is zeroed outside
  ``[cut_in_ms, cut_out_ms]``.

They also differ in quadrature grid (a 3,000-point ``linspace`` versus a 0.05 m/s
``arange``).

WIND-3 recorded that the two "were verified to agree to < 0.1%" — as prose, in a
docstring, with nothing executing it. That is precisely the class of claim `VERIFY-01`
exists to stop, and it matters more than an ordinary doc assertion: the second
integrator's whole value is being an oracle for the first (`TEST-01`), and an oracle
nothing checks is not an oracle. This module executes the comparison.

Measured spread at the time of writing, on the canonical ERA5-fitted Weibull: every
curve in the store agrees to better than 0.002%, except ``dtu_reference_10mw`` at
0.012% — that curve has the sharpest cut-in onset (it starts at 4.0 m/s), which the
coarser 3,000-point grid resolves slightly differently. The tolerance below is set at
0.05%: tight enough that a real divergence in either integrator fails here, loose
enough that grid-resolution noise does not.
"""

from __future__ import annotations

import pytest

from analytics.power_curves.oem_parser import (
    IEC_REFERENCE_AIR_DENSITY_KGM3,
    parse_power_curve,
)
from analytics.wind.aep_tornado import gross_aep_farm_gwh
from wind_resource.bankable_aep import gross_aep_weibull

#: The canonical lender resource: the ERA5-fitted Weibull behind the committed headline.
CANONICAL_WEIBULL_A = 8.199
CANONICAL_WEIBULL_K = 2.665
N_TURBINES = 15

#: Maximum tolerated relative disagreement between the two integrators, in percent.
#: See the module docstring for how this was chosen.
PARITY_TOLERANCE_PCT = 0.05

CURVE_KEYS = [
    "iea_reference_10mw",
    "dtu_reference_10mw",
    "nrel_reference_10mw",
    "envision_en171_6p5",
    "vestas_v150_5p6",
    "ge_cypress_5p5",
]


def _both_integrators(curve_key: str) -> tuple[float, float]:
    curve = parse_power_curve(
        curve_key, air_density_kgm3=IEC_REFERENCE_AIR_DENSITY_KGM3
    )
    ws = curve["wind_speed_ms"].to_numpy()
    power = curve["power_kw"].to_numpy()
    production = gross_aep_farm_gwh(
        CANONICAL_WEIBULL_A, CANONICAL_WEIBULL_K, ws, power, N_TURBINES
    )
    cross_check = gross_aep_weibull(
        wind_speed_ms=ws,
        power_kw=power,
        weibull_a=CANONICAL_WEIBULL_A,
        weibull_k=CANONICAL_WEIBULL_K,
        rated_power_kw=float(power.max()),
        n_turbines=N_TURBINES,
    ).aep_gwh_farm
    return production, cross_check


@pytest.mark.parametrize("curve_key", CURVE_KEYS)
def test_integrators_agree_on_every_curve_in_the_store(curve_key: str) -> None:
    production, cross_check = _both_integrators(curve_key)
    assert production > 0.0
    drift_pct = 100.0 * abs(cross_check - production) / production
    assert drift_pct < PARITY_TOLERANCE_PCT, (
        f"{curve_key}: the production integrator (gross_aep_farm_gwh, {production:.3f} GWh) "
        f"and its cross-check (gross_aep_weibull, {cross_check:.3f} GWh) disagree by "
        f"{drift_pct:.4f}%, over the {PARITY_TOLERANCE_PCT}% tolerance. One of them has "
        "changed behaviour — establish which before trusting either."
    )


def test_parity_holds_across_the_resource_range() -> None:
    """A single Weibull could agree by coincidence; sweep the plausible site range."""
    curve = parse_power_curve(
        "iea_reference_10mw", air_density_kgm3=IEC_REFERENCE_AIR_DENSITY_KGM3
    )
    ws = curve["wind_speed_ms"].to_numpy()
    power = curve["power_kw"].to_numpy()
    for weibull_a in (6.0, 7.5, 8.199, 9.5, 11.0):
        for weibull_k in (1.8, 2.2, 2.665, 3.2):
            production = gross_aep_farm_gwh(weibull_a, weibull_k, ws, power, N_TURBINES)
            cross_check = gross_aep_weibull(
                wind_speed_ms=ws,
                power_kw=power,
                weibull_a=weibull_a,
                weibull_k=weibull_k,
                rated_power_kw=float(power.max()),
                n_turbines=N_TURBINES,
            ).aep_gwh_farm
            drift_pct = 100.0 * abs(cross_check - production) / production
            assert (
                drift_pct < PARITY_TOLERANCE_PCT
            ), f"A={weibull_a}, k={weibull_k}: integrators disagree by {drift_pct:.4f}%"
