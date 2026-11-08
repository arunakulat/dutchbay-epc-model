"""``model_wake_loss(counted=...)``: a turbine that wakes but is not counted (#1577).

The Blue Whale turbine stands on DutchBay T2. It still wakes T1 and T3, but its energy is
not DutchBay's, so the 14-turbine wake loss is taken over the counted turbines only. The
oracles here are properties of the flow model, not values computed by the change:

- counting every turbine reproduces the unmasked call exactly;
- waked and gross energy are additive over a partition of the turbines;
- without wake every turbine of one type sees the same gross energy, so the counted gross
  is the per-turbine gross times the number counted;
- an extra upstream turbine can only add deficit, so the counted turbines lose at least as
  much with the waker standing as with it removed.
"""

from __future__ import annotations

import pytest

from analytics.power_curves.oem_parser import parse_power_curve
from wind_resource.bankable_aep import model_wake_loss

A, K = 8.199, 2.665
RHO_REF = 1.225
ROTOR_M, HUB_M = 198.0, 150.0
ROSE = [3, 3, 3, 4, 6, 9, 14, 20, 16, 9, 6, 4]
# A short north-south row, north end first; index 1 plays T2.
N = 5
X = [0.0] * N
Y = [650.0 * (N - 1 - i) for i in range(N)]


def _run(x=X, y=Y, counted=None):
    c = parse_power_curve("iea_reference_10mw", air_density_kgm3=RHO_REF)
    return model_wake_loss(
        wind_speed_ms=c["wind_speed_ms"].to_numpy(),
        power_kw=c["power_kw"].to_numpy(),
        thrust_coefficient=c["thrust_coefficient"].to_numpy(),
        rotor_diameter_m=ROTOR_M,
        hub_height_m=HUB_M,
        layout_x_m=x,
        layout_y_m=y,
        weibull_a=A,
        weibull_k=K,
        wind_rose_freq=ROSE,
        counted=counted,
    )


def test_counting_every_turbine_matches_the_unmasked_call() -> None:
    pytest.importorskip("py_wake")
    base = _run()
    full = _run(counted=[True] * N)
    assert full.n_turbines == base.n_turbines == N
    assert full.aep_wake_gwh == pytest.approx(base.aep_wake_gwh, rel=1e-12)
    assert full.aep_gross_gwh == pytest.approx(base.aep_gross_gwh, rel=1e-12)
    assert full.wake_loss_pct == pytest.approx(base.wake_loss_pct, rel=1e-12)


def test_energy_is_additive_over_a_partition() -> None:
    pytest.importorskip("py_wake")
    mask = [i != 1 for i in range(N)]
    base = _run()
    kept = _run(counted=mask)
    rest = _run(counted=[not m for m in mask])
    assert kept.n_turbines == N - 1 and rest.n_turbines == 1
    assert kept.aep_wake_gwh + rest.aep_wake_gwh == pytest.approx(
        base.aep_wake_gwh, rel=1e-12
    )
    assert kept.aep_gross_gwh + rest.aep_gross_gwh == pytest.approx(
        base.aep_gross_gwh, rel=1e-12
    )


def test_counted_gross_is_per_turbine_gross_times_count() -> None:
    pytest.importorskip("py_wake")
    kept = _run(counted=[i != 1 for i in range(N)])
    base = _run()
    assert kept.aep_gross_gwh == pytest.approx(
        base.aep_gross_gwh * (N - 1) / N, rel=1e-12
    )


def test_a_standing_waker_adds_loss_to_the_counted_turbines() -> None:
    pytest.importorskip("py_wake")
    waking = _run(counted=[i != 1 for i in range(N)])
    removed = _run(
        x=[X[i] for i in range(N) if i != 1], y=[Y[i] for i in range(N) if i != 1]
    )
    assert waking.n_turbines == removed.n_turbines == N - 1
    assert waking.aep_gross_gwh == pytest.approx(removed.aep_gross_gwh, rel=1e-12)
    assert waking.wake_loss_pct > removed.wake_loss_pct


@pytest.mark.parametrize(
    ("counted", "message"),
    [([True] * (N - 1), "flags for a layout"), ([False] * N, "no turbine")],
)
def test_bad_counted_flags_fail_loud(counted, message) -> None:
    pytest.importorskip("py_wake")
    with pytest.raises(ValueError, match=message):
        _run(counted=counted)
