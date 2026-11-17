"""#1787 (sandbox): a project capacity-factor shock reaches every technology coherently."""

import pytest

from analytics.evaluation_v14 import _coherent_capacity_factor


def test_shock_scales_each_technology_by_the_same_ratio() -> None:
    base = {
        "project": {"capacity_factor": 0.4},
        "generation": {
            "technologies": {
                "wind": {"capacity_factor": 0.4, "capacity_mw": 5},
                "bess_1": {"type": "bess"},
            }
        },
    }
    out = _coherent_capacity_factor(base, {"project": {"capacity_factor": 0.44}})
    assert out["generation"]["technologies"]["wind"]["capacity_factor"] == pytest.approx(0.44)
    assert "bess_1" not in out["generation"]["technologies"]


def test_no_technology_block_leaves_overrides_alone() -> None:
    ov = {"project": {"capacity_factor": 0.44}}
    assert _coherent_capacity_factor({"project": {"capacity_factor": 0.4}}, ov) == ov
