"""Tests for the itemised solar loss chain (#469 — SOLAR-2 / dolphin 4b).

The loss-model maths is pure (it reuses the generic wind retention engine with a solar
taxonomy). One gated test proves the producer integration + the flat-fallback equivalence.
"""

from __future__ import annotations

import pytest

from solar_resource.loss_model import (
    DEFAULT_SOLAR_LOSS_TAXONOMY,
    compute_net_solar_loss_factor,
    default_solar_loss_taxonomy,
    validate_solar_loss_keys,
)


class TestSolarLossTaxonomy:
    def test_config_taxonomy_loaded(self):
        tax = default_solar_loss_taxonomy()
        assert tax["soiling_pct"] == "reduction"
        assert tax["availability_pct"] == "uptime"
        assert tax["dc_wiring_loss_pct"] == "reduction"

    def test_builtin_fallback_matches_config_keys(self):
        # The built-in fallback covers the same keys as the config block (drift guard).
        assert set(DEFAULT_SOLAR_LOSS_TAXONOMY) <= set(default_solar_loss_taxonomy())


class TestComputeNetSolarLossFactor:
    def test_single_reduction(self):
        # other_pct 14 (reduction) reproduces the flat 14% derate retention exactly.
        assert compute_net_solar_loss_factor({"other_pct": 14.0}) == pytest.approx(0.86)

    def test_availability_is_uptime(self):
        # availability_pct 98 -> retention 0.98 (uptime), not 1-0.98.
        assert compute_net_solar_loss_factor(
            {"availability_pct": 98.0}
        ) == pytest.approx(0.98)

    def test_multi_component_product(self):
        losses = {
            "soiling_pct": 2.0,
            "dc_wiring_loss_pct": 1.5,
            "mismatch_loss_pct": 1.0,
            "availability_pct": 99.0,
        }
        expected = 0.98 * 0.985 * 0.99 * 0.99
        assert compute_net_solar_loss_factor(losses) == pytest.approx(expected)

    def test_unknown_key_raises(self):
        # CESSPIT: a loss-shaped key absent from the taxonomy fails loud (no silent drop).
        with pytest.raises(
            ValueError, match="not in the loss taxonomy|Unknown loss key"
        ):
            compute_net_solar_loss_factor({"sloiling_pct": 2.0})  # typo

    def test_exclude_omits_a_key(self):
        full = compute_net_solar_loss_factor({"soiling_pct": 2.0, "other_pct": 5.0})
        excl = compute_net_solar_loss_factor(
            {"soiling_pct": 2.0, "other_pct": 5.0}, exclude=("other_pct",)
        )
        assert excl == pytest.approx(0.98)  # only soiling retained
        assert full == pytest.approx(0.98 * 0.95)

    def test_validate_solar_loss_keys(self):
        validate_solar_loss_keys({"soiling_pct": 2.0})  # ok
        with pytest.raises(ValueError):
            validate_solar_loss_keys({"bogus_pct": 1.0})


class TestConfigIntegration:
    def test_config_accepts_losses(self):
        from solar_resource.pv_producer import SolarResourceConfig

        cfg = SolarResourceConfig(
            latitude=8.27,
            longitude=79.75,
            annual_ghi_kwh_m2=2000.0,
            dc_capacity_mw=50.0,
            losses={"soiling_pct": 2.0, "availability_pct": 99.0},
        )
        assert cfg.losses == {"soiling_pct": 2.0, "availability_pct": 99.0}

    def test_config_rejects_non_mapping_losses(self):
        from solar_resource.pv_producer import SolarResourceConfig

        with pytest.raises(TypeError, match="losses must be a mapping"):
            SolarResourceConfig(
                latitude=8.27,
                longitude=79.75,
                annual_ghi_kwh_m2=2000.0,
                dc_capacity_mw=50.0,
                losses=[("soiling_pct", 2.0)],  # type: ignore[arg-type]
            )

    def test_from_scenario_rejects_both_flat_and_itemised(self):
        from solar_resource.pv_producer import SolarResourceConfig

        scenario = {
            "resource": {
                "solar": {
                    "latitude": 8.27,
                    "longitude": 79.75,
                    "annual_ghi_kwh_m2": 2000.0,
                    "dc_capacity_mw": 50.0,
                    "system_loss_pct": 14.0,
                    "losses": {"soiling_pct": 2.0},
                }
            }
        }
        with pytest.raises(KeyError, match="BOTH system_loss_pct and losses"):
            SolarResourceConfig.from_scenario(scenario)

    def test_from_scenario_accepts_itemised_alone(self):
        from solar_resource.pv_producer import SolarResourceConfig

        scenario = {
            "resource": {
                "solar": {
                    "latitude": 8.27,
                    "longitude": 79.75,
                    "annual_ghi_kwh_m2": 2000.0,
                    "dc_capacity_mw": 50.0,
                    "losses": {"soiling_pct": 2.0, "availability_pct": 99.0},
                }
            }
        }
        cfg = SolarResourceConfig.from_scenario(scenario)
        assert cfg.losses == {"soiling_pct": 2.0, "availability_pct": 99.0}


class TestProducerIntegration:
    """compute_solar_aep loss-chain integration — gated on the [solar] extra."""

    def test_itemised_14pct_equivalent_to_flat_and_absent_is_flat(self):
        pytest.importorskip("pvlib")
        from solar_resource.pv_producer import SolarResourceConfig, compute_solar_aep

        base_kwargs = dict(
            latitude=8.27,
            longitude=79.75,
            annual_ghi_kwh_m2=2000.0,
            dc_capacity_mw=50.0,
        )
        flat = compute_solar_aep(SolarResourceConfig(**base_kwargs))  # default 14% flat
        # A single other_pct=14 itemised stack has the same 0.86 retention as flat 14%.
        itemised = compute_solar_aep(
            SolarResourceConfig(**base_kwargs, losses={"other_pct": 14.0})
        )
        assert itemised.annual_energy_gwh == pytest.approx(
            flat.annual_energy_gwh, rel=1e-9
        )
        # A different itemised stack genuinely changes the net energy.
        lighter = compute_solar_aep(
            SolarResourceConfig(**base_kwargs, losses={"soiling_pct": 2.0})
        )
        assert lighter.annual_energy_gwh > flat.annual_energy_gwh  # 2% loss < 14%
