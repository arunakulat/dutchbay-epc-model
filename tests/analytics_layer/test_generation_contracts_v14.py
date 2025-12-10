from dataclasses import asdict

from analytics.contracts_v14 import TechnologyBreakdown


def test_technology_breakdown_snapshot() -> None:
    """Minimal snapshot to pin the lender-facing shape.

    This is deliberately tiny: we just assert the dict form, so any future
    field changes will be very obvious in diffs.
    """
    tb = TechnologyBreakdown(
        technology="wind",
        share_of_capex_pct=70.0,
        share_of_cfads_pct=80.0,
        share_of_aep_pct=100.0,
        notes="toy snapshot for tests",
    )

    assert asdict(tb) == {
        "technology": "wind",
        "share_of_capex_pct": 70.0,
        "share_of_cfads_pct": 80.0,
        "share_of_aep_pct": 100.0,
        "notes": "toy snapshot for tests",
    }
