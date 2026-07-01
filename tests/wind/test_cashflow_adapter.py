"""Tests for wind_resource.cashflow_adapter (Sprint 19, Defect W6).

Two test classes:

1. ``TestAdapterContract`` — pure unit tests of the adapter itself.
   Exercise shape validation, the three modes, drift handling, immutability,
   provenance metadata. No heavy dependencies — runs in any environment.

2. ``TestRoundTrip`` — integration test that proves wind P75 AEP flows
   through the adapter into ``finance.cashflow_v14`` and emerges as
   ``annual_rows[year_1].net_kwh`` within ±0.5%. Requires ``numpy_financial``
   so is gated with ``pytest.importorskip``.
"""

from __future__ import annotations

import copy

import pytest

from wind_resource.cashflow_adapter import (
    DEFAULT_TOLERANCE_PCT,
    WindAdapterDriftError,
    WindCashflowExport,
    wind_export_to_scenario_patch,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def p75_export() -> dict:
    """Canonical P75 wind export, matching the WindPipeline contract.

    Numbers are internally consistent for a 150 MW project at CF 42.8%:
        annual_generation_mwh = 150 * 8760 * 0.428 = 562_392 MWh
    """
    return {
        "scenario": "P75",
        "annual_generation_mwh": 562_392.0,
        "capacity_factor_percent": 42.8,
        "revenue_annual_usd": 38_037_120.0,
        "revenue_cumulative_usd": 760_742_400.0,
        "project_capacity_mw": 150.0,
        "num_turbines": 15,
        "rated_capacity_per_turbine_kw": 10000.0,
        "ppa_years": 20,
        "tariff_lkr_per_kwh": 20.3,
        "exchange_rate_lkr_usd": 300.0,
    }


@pytest.fixture()
def aligned_scenario() -> dict:
    """v14 scenario fragment whose values agree with the P75 export."""
    return {
        "project": {"capacity_mw": 150.0, "capacity_factor": 0.428},
        "tariff": {"lkr_per_kwh": 20.3},
        "fx": {"start_lkr_per_usd": 300.0},
    }


# ---------------------------------------------------------------------------
# 1. Pure adapter contract
# ---------------------------------------------------------------------------


class TestAdapterContract:
    """Adapter contract — no heavy deps, runs in any environment."""

    # -- shape validation ---------------------------------------------------

    def test_validates_export_shape(self, p75_export):
        model = WindCashflowExport.model_validate(p75_export)
        assert model.scenario == "P75"
        assert model.project_capacity_mw == 150.0

    def test_missing_field_rejected(self, p75_export):
        bad = dict(p75_export)
        del bad["tariff_lkr_per_kwh"]
        with pytest.raises(Exception):  # pydantic.ValidationError
            wind_export_to_scenario_patch(bad, {}, adapter_mode="overwrite")

    def test_cf_as_decimal_rejected(self, p75_export):
        # WindPipeline emits CF in PERCENT. A value ≤ 1.0 indicates the
        # producer wrote a decimal — must refuse to avoid silently halving
        # economics.
        bad = dict(p75_export, capacity_factor_percent=0.428)
        with pytest.raises(Exception):
            wind_export_to_scenario_patch(bad, {}, adapter_mode="overwrite")

    def test_negative_capacity_rejected(self, p75_export):
        bad = dict(p75_export, project_capacity_mw=-1.0)
        with pytest.raises(Exception):
            wind_export_to_scenario_patch(bad, {}, adapter_mode="overwrite")

    def test_cf_above_100_rejected(self, p75_export):
        bad = dict(p75_export, capacity_factor_percent=101.0)
        with pytest.raises(Exception):
            wind_export_to_scenario_patch(bad, {}, adapter_mode="overwrite")

    # -- P-level selector --------------------------------------------------

    def test_scenario_name_mismatch(self, p75_export):
        with pytest.raises(ValueError, match="P-level|P50"):
            wind_export_to_scenario_patch(
                p75_export, {}, scenario_name="P50", adapter_mode="overwrite"
            )

    @pytest.mark.parametrize("p_level", ["P50", "P75", "P90"])
    def test_all_p_levels_accepted(self, p75_export, p_level):
        export = dict(p75_export, scenario=p_level)
        patch = wind_export_to_scenario_patch(
            export, {}, scenario_name=p_level, adapter_mode="overwrite"
        )
        assert patch["wind_resource"]["scenario"] == p_level

    # -- mode: overwrite ---------------------------------------------------

    def test_overwrite_empty_scenario(self, p75_export):
        patch = wind_export_to_scenario_patch(p75_export, {}, adapter_mode="overwrite")
        assert patch["project"]["capacity_mw"] == 150.0
        assert patch["project"]["capacity_factor"] == 0.428
        assert patch["tariff"]["lkr_per_kwh"] == 20.3
        assert patch["fx"]["start_lkr_per_usd"] == 300.0

    def test_overwrite_replaces_existing(self, p75_export):
        scen = {"project": {"capacity_factor": 0.500}}  # 16% drift — overwritten
        patch = wind_export_to_scenario_patch(
            p75_export, scen, adapter_mode="overwrite"
        )
        assert patch["project"]["capacity_factor"] == 0.428

    def test_overwrite_never_raises_on_drift(self, p75_export):
        scen = {"project": {"capacity_factor": 0.999}}  # huge drift
        # Must not raise — overwrite is the "replace, don't validate" mode.
        wind_export_to_scenario_patch(p75_export, scen, adapter_mode="overwrite")

    # -- mode: fill_if_absent (default) ------------------------------------

    def test_fill_if_absent_preserves_aligned(self, p75_export, aligned_scenario):
        patch = wind_export_to_scenario_patch(
            p75_export, aligned_scenario, adapter_mode="fill_if_absent"
        )
        # Aligned value is preserved — YAML wins.
        assert patch["project"]["capacity_factor"] == 0.428

    def test_fill_if_absent_writes_missing(self, p75_export):
        # Only capacity_factor present — others must be filled.
        scen = {"project": {"capacity_factor": 0.428}}
        patch = wind_export_to_scenario_patch(
            p75_export, scen, adapter_mode="fill_if_absent"
        )
        assert patch["project"]["capacity_mw"] == 150.0  # filled
        assert patch["tariff"]["lkr_per_kwh"] == 20.3  # filled
        assert patch["fx"]["start_lkr_per_usd"] == 300.0  # filled

    def test_fill_if_absent_raises_on_drift_exceeding_tolerance(self, p75_export):
        scen = {"project": {"capacity_factor": 0.500}}  # ~14% drift
        with pytest.raises(WindAdapterDriftError) as exc:
            wind_export_to_scenario_patch(
                p75_export, scen, adapter_mode="fill_if_absent"
            )
        assert exc.value.field == "project.capacity_factor"
        assert exc.value.drift_pct > DEFAULT_TOLERANCE_PCT
        assert exc.value.mode == "fill_if_absent"

    def test_fill_if_absent_passes_within_tolerance(self, p75_export):
        # 0.428 -> 0.430 = 0.466% drift, just under 0.5% default.
        scen = {"project": {"capacity_factor": 0.430}}
        patch = wind_export_to_scenario_patch(
            p75_export, scen, adapter_mode="fill_if_absent"
        )
        # Lender YAML preserved.
        assert patch["project"]["capacity_factor"] == 0.430

    def test_fill_if_absent_tolerance_configurable(self, p75_export):
        # 0.428 -> 0.500 = ~14.4% drift — passes with tolerance=15%.
        scen = {"project": {"capacity_factor": 0.500}}
        patch = wind_export_to_scenario_patch(
            p75_export, scen, adapter_mode="fill_if_absent", tolerance_pct=15.0
        )
        assert patch["project"]["capacity_factor"] == 0.500  # YAML preserved

    # -- mode: validate_only -----------------------------------------------

    def test_validate_only_passes_when_aligned(self, p75_export, aligned_scenario):
        patch = wind_export_to_scenario_patch(
            p75_export, aligned_scenario, adapter_mode="validate_only"
        )
        # Economics fields unchanged.
        assert patch["project"]["capacity_factor"] == 0.428
        assert patch["tariff"]["lkr_per_kwh"] == 20.3
        # Provenance metadata still written.
        assert patch["wind_resource"]["adapter_mode"] == "validate_only"

    def test_validate_only_raises_on_missing(self, p75_export):
        with pytest.raises(WindAdapterDriftError) as exc:
            wind_export_to_scenario_patch(p75_export, {}, adapter_mode="validate_only")
        assert exc.value.scenario_value is None
        assert exc.value.mode == "validate_only"

    def test_validate_only_raises_on_drift(self, p75_export):
        scen = {
            "project": {"capacity_mw": 150.0, "capacity_factor": 0.500},
            "tariff": {"lkr_per_kwh": 20.3},
            "fx": {"start_lkr_per_usd": 300.0},
        }
        with pytest.raises(WindAdapterDriftError) as exc:
            wind_export_to_scenario_patch(
                p75_export, scen, adapter_mode="validate_only"
            )
        assert exc.value.field == "project.capacity_factor"
        assert exc.value.drift_pct > DEFAULT_TOLERANCE_PCT

    def test_validate_only_never_writes_economics(self, p75_export, aligned_scenario):
        before = copy.deepcopy(aligned_scenario)
        patch = wind_export_to_scenario_patch(
            p75_export, aligned_scenario, adapter_mode="validate_only"
        )
        # Verify caller dict not mutated.
        assert aligned_scenario == before
        # Verify patched economics match original (no rewrite).
        assert patch["project"] == before["project"]
        assert patch["tariff"] == before["tariff"]
        assert patch["fx"] == before["fx"]

    # -- caller immutability + provenance ----------------------------------

    @pytest.mark.parametrize("mode", ["overwrite", "fill_if_absent", "validate_only"])
    def test_input_dict_not_mutated(self, p75_export, aligned_scenario, mode):
        before = copy.deepcopy(aligned_scenario)
        try:
            wind_export_to_scenario_patch(
                p75_export, aligned_scenario, adapter_mode=mode
            )
        except WindAdapterDriftError:
            pass
        assert aligned_scenario == before, f"input mutated under mode={mode}"

    @pytest.mark.parametrize("mode", ["overwrite", "fill_if_absent", "validate_only"])
    def test_provenance_metadata_present(self, p75_export, aligned_scenario, mode):
        patch = wind_export_to_scenario_patch(
            p75_export, aligned_scenario, adapter_mode=mode
        )
        meta = patch["wind_resource"]
        assert meta["source"] == "frozen_export"
        assert meta["scenario"] == "P75"
        assert meta["net_aep_mwh"] == 562_392.0
        assert meta["capacity_factor_decimal"] == pytest.approx(0.428)
        assert meta["adapter_mode"] == mode
        assert meta["adapter_tolerance_pct"] == DEFAULT_TOLERANCE_PCT
        assert meta["num_turbines"] == 15
        assert meta["ppa_years"] == 20

    def test_provenance_preserves_existing_wind_block(self, p75_export):
        scen = {
            "project": {"capacity_mw": 150.0, "capacity_factor": 0.428},
            "wind_resource": {
                "mean_wind_speed_ms": 7.85,
                "data_source": "ECMWF ERA5",
            },
        }
        patch = wind_export_to_scenario_patch(
            p75_export, scen, adapter_mode="fill_if_absent"
        )
        # Existing keys preserved
        assert patch["wind_resource"]["mean_wind_speed_ms"] == 7.85
        assert patch["wind_resource"]["data_source"] == "ECMWF ERA5"
        # New provenance keys added
        assert patch["wind_resource"]["source"] == "frozen_export"

    # -- argument hygiene --------------------------------------------------

    def test_bogus_adapter_mode_rejected(self, p75_export):
        with pytest.raises(ValueError, match="adapter_mode"):
            wind_export_to_scenario_patch(
                p75_export, {}, adapter_mode="bogus"  # type: ignore[arg-type]
            )

    def test_drift_boundary_inclusive(self, p75_export):
        # Drift exactly at tolerance should NOT raise (≤, not <).
        # Symmetric relative drift of 0.5% means scenario_value such that
        # |wind - scen| / max(wind, scen) = 0.005.
        scen = {"project": {"capacity_factor": 0.428 * 1.005025}}  # ~0.5%
        # Should pass at tolerance=0.5
        wind_export_to_scenario_patch(
            p75_export, scen, adapter_mode="fill_if_absent", tolerance_pct=0.5
        )


# ---------------------------------------------------------------------------
# 2. Round-trip integration: wind P75 → adapter → cashflow_v14 → net_kwh_y1
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Prove adapter output feeds correctly through finance.cashflow_v14.

    Gated by ``numpy_financial`` availability — the finance pipeline depends
    on it for debt-service math. In a sandbox without ``numpy_financial`` the
    class is skipped at collection time; CI installs it and runs the test.
    """

    @pytest.fixture(autouse=True)
    def _require_numpy_financial(self):
        pytest.importorskip("numpy_financial")

    def test_p75_aep_aligns_with_year1_net_kwh(self, p75_export):
        """Round-trip: P75 AEP → adapter → year-1 net_kwh within ±0.5%.

        For year-1 (year index 0), v14 cashflow computes:

            effective_cf = capacity_factor × (1 - degradation)^0
                         = capacity_factor
            gross_kwh    = capacity_mw × 1000 × 8760 × capacity_factor
            net_kwh      = gross_kwh × (1 - grid_loss_pct)

        With grid_loss_pct = 0 (lender YAML default) this reduces to

            net_kwh_y1 = capacity_mw × 1000 × 8760 × capacity_factor

        which equals the wind export's ``annual_generation_mwh × 1000``
        within floating-point tolerance. The 0.5% drift band accommodates
        any rounding inside the wind AEP synthesis.
        """
        from finance.cashflow_v14 import build_annual_rows  # noqa: WPS433

        # Minimal scenario: adapter fills wind-derived fields; remaining
        # fields are v14 cashflow schema requirements unrelated to wind.
        minimal_scenario: dict = {
            "project": {
                "name": "test",
                "life_years": 20,
                "cod_year": 2027,
                "degradation": 0.005,
                "grid_loss_pct": 0.0,
            },
            # Schema-complete tax block (CESSPIT/R22 — TaxConfig.from_yaml is
            # schema-strict since #136/#142: every required key must be present,
            # no hidden defaults). Values mirror the post-2025 SL regime but are
            # immaterial here — the assertion below is on pre-tax net_kwh.
            "tax": {
                "corporate_tax_rate": 0.30,
                "depreciation_method": "straight_line",
                "depreciation_start_year": 1,
                "depreciation_years": 5,
                "enhanced_allowance_applies": False,
                "enhanced_capital_allowance_multiple": 1.5,
                "loss_carryforward_years": 6,
                "tax_holiday_start_year": 1,
                "tax_holiday_years": 0,
                "wht_on_interest_to_nonresidents": 0.10,
                "wht_on_interest_enabled": True,
                "wht_gross_up": False,
            },
            "tariff": {"tariff_type": "fixed", "ppa_term_years": 20},
            "opex": {"usd_per_year": 0.0},  # opex zero — we only care about net_kwh
        }
        patched = wind_export_to_scenario_patch(
            p75_export, minimal_scenario, adapter_mode="fill_if_absent"
        )

        # build_annual_rows accepts the full scenario dict and resolves
        # cashflow params internally, exercising the same code path
        # run_v14_pipeline_enhanced does.
        rows = build_annual_rows(patched)

        assert len(rows) > 0, "build_annual_rows returned empty"
        year_1 = rows[0]
        net_kwh_y1 = float(year_1["net_kwh"])

        # Wind export claims this much net generation (MWh → kWh).
        wind_net_kwh = p75_export["annual_generation_mwh"] * 1000.0

        denom = max(abs(net_kwh_y1), abs(wind_net_kwh))
        drift_pct = 100.0 * abs(net_kwh_y1 - wind_net_kwh) / denom

        assert drift_pct <= 0.5, (
            f"Year-1 net_kwh drift {drift_pct:.4f}% exceeds 0.5% tolerance. "
            f"wind={wind_net_kwh:,.0f} kWh, "
            f"cashflow_v14={net_kwh_y1:,.0f} kWh"
        )

    def test_capacity_factor_threads_through(self, p75_export):
        """Adapter-written capacity_factor must reach _build_cashflow_params.

        Exercises the lower-level resolution helper to prove that the
        adapter's chosen write target (project.capacity_factor) wins the
        priority-order resolution inside finance.cashflow_v14_params.
        """
        from finance.cashflow_v14_params import (  # noqa: WPS433
            _build_cashflow_params,
        )

        minimal: dict = {
            "project": {
                "name": "test",
                "life_years": 20,
                "cod_year": 2027,
                "degradation": 0.005,
                "grid_loss_pct": 0.0,
            },
            "tariff": {"tariff_type": "fixed", "ppa_term_years": 20},
        }
        patched = wind_export_to_scenario_patch(
            p75_export, minimal, adapter_mode="overwrite"
        )
        params = _build_cashflow_params(patched)

        # CashflowParams is a TypedDict / dataclass — access by attribute or key.
        # Use getattr-with-fallback to tolerate either shape.
        def _get(p, key):
            if hasattr(p, key):
                return getattr(p, key)
            return p[key]

        assert _get(params, "capacity_mw") == pytest.approx(150.0)
        assert _get(params, "capacity_factor") == pytest.approx(0.428, abs=1e-6)
        assert _get(params, "tariff_lkr_per_kwh") == pytest.approx(20.3)
