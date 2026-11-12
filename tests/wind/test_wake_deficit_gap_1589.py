"""Tests for DutchBay PyWake aerodynamic wake deficit gap investigation (#1589).

Audits the factorial decomposition of the ~12 pp gap between the bankable frozen
calibration (7.28% / 7.32%) and live PyWake modeling (19.33% / 19.44%).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from scripts.analyze_dutchbay_wake_deficit_gap_1589 import compute_gap_analysis

_REPO = Path(__file__).resolve().parents[2]
_CONF_PATH = _REPO / "conf" / "dutchbay_wake_14_turbines.yaml"


@pytest.fixture(scope="module")
def gap_data() -> Dict[str, Any]:
    """Execute the gap analysis once for the test module."""
    raw = yaml.safe_load(_CONF_PATH.read_text())
    return compute_gap_analysis(raw)


def test_gap_analysis_structural_integrity(gap_data: Dict[str, Any]) -> None:
    """Verify top-level structure, work item reference, and baseline values."""
    assert gap_data["work_item"] == "#1589"
    assert gap_data["frozen_wake_15_pct"] == pytest.approx(7.28, abs=0.01)
    assert gap_data["live_wake_15_pct"] == pytest.approx(19.33, abs=0.05)
    assert gap_data["live_wake_14_pct"] == pytest.approx(19.44, abs=0.05)


def test_gap_attribution_factorial_math(gap_data: Dict[str, Any]) -> None:
    """Audit the factorial decomposition into layout density and rose weighting."""
    attr = gap_data["gap_attribution"]
    # Synthetic single row (650m N-S) yields ~8.19%
    assert attr["synthetic_row_wake_pct"] == pytest.approx(8.19, abs=0.05)
    # Recorded layout yields ~19.33%
    assert attr["real_layout_wake_pct"] == pytest.approx(19.33, abs=0.05)
    # Spacing density alone accounts for >9 pp of wake deficit
    assert attr["layout_geometry_pp"] > 9.0
    assert attr["layout_geometry_pp"] == pytest.approx(9.62, abs=0.10)
    # Directional SW rose accounts for ~1.9 pp over omnidirectional
    assert attr["wind_rose_directional_penalty_pp"] > 1.5
    assert attr["wind_rose_directional_penalty_pp"] == pytest.approx(1.95, abs=0.10)


def test_spacing_density_under_three_diameters(gap_data: Dict[str, Any]) -> None:
    """Assert that the real layout turbine pairs are tightly spaced (< 3.2 D)."""
    pairwise = gap_data["pairwise_spacing"]
    assert len(pairwise) == 15
    for item in pairwise:
        # Every single turbine has a neighbor within 3.2 rotor diameters
        assert item["distance_diameters"] < 3.20
        # The majority have spacing under 2.85 rotor diameters
        assert item["distance_m"] < 630.0

    # Specifically check T1-T2 and T2-T3
    t1 = next(t for t in pairwise if t["id"] == "T1")
    t2 = next(t for t in pairwise if t["id"] == "T2")
    t3 = next(t for t in pairwise if t["id"] == "T3")
    assert t1["nearest_neighbor_id"] == "T2"
    assert t1["distance_diameters"] == pytest.approx(3.14, abs=0.05)
    assert t2["nearest_neighbor_id"] == "T3"
    assert t2["distance_diameters"] == pytest.approx(2.66, abs=0.05)
    assert t3["nearest_neighbor_id"] == "T2"
    assert t3["distance_diameters"] == pytest.approx(2.66, abs=0.05)


def test_rotor_diameter_monotonic_wake_scaling(gap_data: Dict[str, Any]) -> None:
    """Audit the turbine proxy scaling effect from D=120m to D=198m."""
    sens = gap_data["rotor_diameter_sensitivities_pct"]
    d_list = [120, 140, 160, 180, 198]
    vals = [sens[f"rotor_{d}m_pct"] for d in d_list]

    # Strictly monotonic rise in wake loss with rotor diameter
    for i in range(len(vals) - 1):
        assert vals[i] < vals[i + 1]

    # At D=120m (~3 MW class machine), wake loss is ~9.79%, close to historical calibration
    assert sens["rotor_120m_pct"] == pytest.approx(9.79, abs=0.10)
    assert sens["rotor_198m_pct"] == pytest.approx(19.33, abs=0.10)


def test_bankable_p50_p90_sensitivity_disclosure(gap_data: Dict[str, Any]) -> None:
    """Verify bankable P50/P90 impact figures under live wake sensitivity."""
    bank = gap_data["bankable_sensitivity"]
    # P50 at 7.32% wake loss is ~459.36 GWh/yr
    assert bank["frozen_7_32_pct"]["p50_net_gwh"] == pytest.approx(459.36, abs=0.10)
    # P50 at 19.44% wake loss is ~399.31 GWh/yr
    assert bank["live_19_44_pct"]["p50_net_gwh"] == pytest.approx(399.31, abs=0.10)

    # Delta is approximately -60 GWh/yr (-13.07%)
    assert bank["p50_delta_gwh"] == pytest.approx(-60.05, abs=0.10)
    assert bank["p50_delta_pct"] == pytest.approx(-13.07, abs=0.10)

    # 20-year P90 net delta is strictly negative
    assert (
        bank["live_19_44_pct"]["p90_life_net_gwh"]
        < bank["frozen_7_32_pct"]["p90_life_net_gwh"]
    )
