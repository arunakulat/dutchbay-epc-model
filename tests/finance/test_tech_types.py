"""The explicit technology-type enum (finance.tech_types) and `type`-authoritative
classification across the cashflow + analytics layers.

Guards the multi-tech follow-up: a third generation technology (e.g. tidal) declared with
an explicit `type` aggregates everywhere automatically, retiring the old hardcoded
("wind", "solar") lists; storage (type: bess) is never treated as generation.
"""

from __future__ import annotations


from finance.tech_types import (
    GENERATION_TYPES,
    STORAGE_TYPES,
    is_generation_type,
    is_storage_type,
)


# --------------------------------------------------------------------------- #
# The registry
# --------------------------------------------------------------------------- #
def test_registry_contents() -> None:
    assert {"wind", "solar", "tidal"} <= GENERATION_TYPES
    assert "bess" in STORAGE_TYPES
    assert GENERATION_TYPES.isdisjoint(STORAGE_TYPES)


def test_classifiers_are_case_insensitive_and_strict() -> None:
    assert is_generation_type("wind") and is_generation_type("Tidal") and is_generation_type("SOLAR")
    assert is_storage_type("bess") and is_storage_type("BESS")
    # unknown / absent types are neither (callers fall back to key-sniffing)
    assert not is_generation_type("bess")
    assert not is_storage_type("wind")
    assert not is_generation_type(None) and not is_storage_type(None)
    assert not is_generation_type("typo_tech")


# --------------------------------------------------------------------------- #
# Discovery (analytics tornado) is type-authoritative and tech-agnostic
# --------------------------------------------------------------------------- #
def _three_tech_cfg() -> dict:
    return {
        "generation": {
            "technologies": {
                "wind": {"type": "wind", "capacity_mw": 150, "capacity_factor": 0.339},
                "tidal": {"type": "tidal", "capacity_mw": 30, "capacity_factor": 0.40},
                "battery": {"type": "bess", "power_mw": 50, "energy_mwh": 200},
            }
        }
    }


def test_discovery_includes_tidal_excludes_storage() -> None:
    from analytics.portfolio.multi_tech_tornado import (
        discover_generation_technologies,
        discover_storage_technologies,
    )

    cfg = _three_tech_cfg()
    assert discover_generation_technologies(cfg) == ["wind", "tidal"]
    assert discover_storage_technologies(cfg) == ["battery"]


def test_type_overrides_keysniff_for_storage() -> None:
    """A storage block that mis-carries a capacity_factor is still NOT generation,
    because the explicit type is authoritative."""
    from analytics.portfolio.multi_tech_tornado import discover_generation_technologies

    cfg = {
        "generation": {
            "technologies": {
                "wind": {"type": "wind", "capacity_mw": 150, "capacity_factor": 0.339},
                "battery": {"type": "bess", "capacity_factor": 0.25, "power_mw": 50},
            }
        }
    }
    assert discover_generation_technologies(cfg) == ["wind"]  # battery excluded by type


# --------------------------------------------------------------------------- #
# The cashflow includes a tidal generation tech (and skips storage)
# --------------------------------------------------------------------------- #
def test_cashflow_resolves_tidal_as_generation() -> None:
    from finance.cashflow_v14_production import resolve_tech_generation_specs

    cfg = _three_tech_cfg()
    # project headline reconciles: (150*0.339 + 30*0.40)/180 = 0.349166...
    params = {"capacity_mw": 180.0, "capacity_factor": (150 * 0.339 + 30 * 0.40) / 180.0,
              "degradation": 0.005}
    specs = resolve_tech_generation_specs(cfg, params)
    assert specs is not None
    techs = {s["technology"] for s in specs}
    assert techs == {"wind", "tidal"}  # tidal aggregated; battery (storage) skipped
