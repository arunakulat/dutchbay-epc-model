"""Tests for solar_resource.cashflow_adapter (#469 — solar → finance OVERWRITE bridge).

Two test groups:

1. ``TestAdapterContract`` — pure unit tests of the adapter. Shape validation, the
   three modes, drift handling, the capacity identity check, immutability, provenance,
   and the blended-headline recompute. No heavy deps (no ``pvlib``) — runs anywhere.

2. ``TestEngineInvariant`` — proves the recomputed ``project.capacity_factor`` satisfies
   the engine's own per-tech reconciliation
   (``finance.cashflow_v14_production.resolve_tech_generation_specs``, ±1%). Gated with
   ``pytest.importorskip`` so it skips where the finance stack's deps are absent.
"""

from __future__ import annotations

import copy

import pytest

from solar_resource.cashflow_adapter import (
    DEFAULT_TOLERANCE_PCT,
    SolarAdapterDriftError,
    SolarCashflowExport,
    build_solar_cashflow_export,
    solar_export_to_scenario_patch,
)

# Canonical hybrid numbers (scenarios/dutchbay_hybrid_windsolar_2025Q4.yaml):
#   wind  159.6 MW @ CF 0.332
#   solar  50.0 MW @ CF 0.20 declared  →  pvlib-modelled 0.17901 (−10.5%)
# Blended headline after overwrite = (159.6*0.332 + 50*0.17901) / 209.6.
_WIND_MW, _WIND_CF = 159.6, 0.332
_SOLAR_MW = 50.0
_SOLAR_CF_MODELLED = 0.17901
_SOLAR_AEP_MODELLED = 78.41  # 50 * 8760 * 0.17901 / 1000
_PROJECT_MW = 209.6
_BLEND_AFTER_OVERWRITE = (
    _WIND_MW * _WIND_CF + _SOLAR_MW * _SOLAR_CF_MODELLED
) / _PROJECT_MW


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def p50_export() -> dict:
    """Frozen P50 solar export matching the pvlib producer's output for the hybrid."""
    return {
        "scenario": "P50",
        "technology": "solar",
        "annual_energy_gwh": _SOLAR_AEP_MODELLED,
        "capacity_factor": _SOLAR_CF_MODELLED,
        "dc_capacity_mw": _SOLAR_MW,
        "specific_yield_kwh_per_kwp": 1568.2,
    }


@pytest.fixture()
def hybrid_scenario() -> dict:
    """v14 hybrid fragment carrying the DECLARED (pre-overwrite) solar CF of 0.20."""
    return {
        "project": {"capacity_mw": _PROJECT_MW, "capacity_factor": 0.300584},
        "generation": {
            "technologies": {
                "wind": {
                    "capacity_mw": _WIND_MW,
                    "capacity_factor": _WIND_CF,
                    "aep_gwh": 464.3,
                },
                "solar": {
                    "capacity_mw": _SOLAR_MW,
                    "capacity_factor": 0.20,
                    "aep_gwh": 87.6,
                },
            }
        },
    }


@pytest.fixture()
def aligned_scenario() -> dict:
    """Hybrid fragment whose solar values already AGREE with the P50 export."""
    return {
        "project": {
            "capacity_mw": _PROJECT_MW,
            "capacity_factor": _BLEND_AFTER_OVERWRITE,
        },
        "generation": {
            "technologies": {
                "wind": {
                    "capacity_mw": _WIND_MW,
                    "capacity_factor": _WIND_CF,
                    "aep_gwh": 464.3,
                },
                "solar": {
                    "capacity_mw": _SOLAR_MW,
                    "capacity_factor": _SOLAR_CF_MODELLED,
                    "aep_gwh": _SOLAR_AEP_MODELLED,
                },
            }
        },
    }


# ---------------------------------------------------------------------------
# 1. Pure adapter contract
# ---------------------------------------------------------------------------


class TestAdapterContract:
    """Adapter contract — no heavy deps, runs in any environment."""

    # -- shape validation ---------------------------------------------------

    def test_validates_export_shape(self, p50_export):
        model = SolarCashflowExport.model_validate(p50_export)
        assert model.scenario == "P50"
        assert model.capacity_factor == pytest.approx(_SOLAR_CF_MODELLED)
        assert model.dc_capacity_mw == _SOLAR_MW

    def test_missing_field_rejected(self, p50_export):
        bad = dict(p50_export)
        del bad["capacity_factor"]
        with pytest.raises(Exception):  # pydantic.ValidationError
            solar_export_to_scenario_patch(bad, {}, adapter_mode="overwrite")

    def test_cf_as_percent_rejected(self, p50_export):
        # The producer emits CF as a DECIMAL. A value > 1.0 indicates a percent slipped
        # in — must refuse to avoid booking ~18x the real solar generation.
        bad = dict(p50_export, capacity_factor=17.9)
        with pytest.raises(Exception):
            solar_export_to_scenario_patch(bad, {}, adapter_mode="overwrite")

    def test_negative_capacity_rejected(self, p50_export):
        bad = dict(p50_export, dc_capacity_mw=-1.0)
        with pytest.raises(Exception):
            solar_export_to_scenario_patch(bad, {}, adapter_mode="overwrite")

    # -- P-level selector --------------------------------------------------

    def test_scenario_name_mismatch(self, p50_export):
        with pytest.raises(ValueError, match="P-level|P75"):
            solar_export_to_scenario_patch(
                p50_export, {}, scenario_name="P75", adapter_mode="overwrite"
            )

    @pytest.mark.parametrize("p_level", ["P50", "P75", "P90"])
    def test_all_p_levels_accepted(self, p50_export, p_level):
        export = dict(p50_export, scenario=p_level)
        patch = solar_export_to_scenario_patch(
            export, {}, scenario_name=p_level, adapter_mode="overwrite"
        )
        assert patch["solar_resource"]["scenario"] == p_level

    # -- mode: overwrite ---------------------------------------------------

    def test_overwrite_replaces_declared_cf_and_reblends(
        self, p50_export, hybrid_scenario
    ):
        patch = solar_export_to_scenario_patch(
            p50_export, hybrid_scenario, adapter_mode="overwrite"
        )
        solar = patch["generation"]["technologies"]["solar"]
        assert solar["capacity_factor"] == pytest.approx(_SOLAR_CF_MODELLED)
        assert solar["aep_gwh"] == pytest.approx(_SOLAR_AEP_MODELLED)
        # Wind is untouched; the project headline is re-blended off the per-tech sum.
        assert (
            patch["generation"]["technologies"]["wind"]["capacity_factor"] == _WIND_CF
        )
        assert patch["project"]["capacity_factor"] == pytest.approx(
            _BLEND_AFTER_OVERWRITE
        )

    def test_overwrite_never_raises_on_cf_drift(self, p50_export, hybrid_scenario):
        # Declared 0.20 vs modelled 0.179 is ~10.5% drift — overwrite replaces, never raises.
        solar_export_to_scenario_patch(
            p50_export, hybrid_scenario, adapter_mode="overwrite"
        )

    def test_overwrite_creates_block_when_absent(self, p50_export):
        # An empty scenario: overwrite writes the full per-tech block. With no project
        # capacity_mw the headline recompute is a documented no-op.
        patch = solar_export_to_scenario_patch(p50_export, {}, adapter_mode="overwrite")
        solar = patch["generation"]["technologies"]["solar"]
        assert solar["capacity_mw"] == _SOLAR_MW
        assert solar["capacity_factor"] == pytest.approx(_SOLAR_CF_MODELLED)
        assert "project" not in patch  # nothing to re-blend against

    # -- capacity identity check (all modes) -------------------------------

    @pytest.mark.parametrize("mode", ["overwrite", "fill_if_absent", "validate_only"])
    def test_capacity_mismatch_raises_in_every_mode(
        self, p50_export, hybrid_scenario, mode
    ):
        # Apply a 50 MW export to a scenario whose solar slot is 60 MW — must fail loud
        # in EVERY mode (a wrong nameplate silently mis-books generation).
        hybrid_scenario["generation"]["technologies"]["solar"]["capacity_mw"] = 60.0
        with pytest.raises(SolarAdapterDriftError) as exc:
            solar_export_to_scenario_patch(
                p50_export, hybrid_scenario, adapter_mode=mode
            )
        assert exc.value.field.endswith("capacity_mw")

    # -- mode: fill_if_absent (default) ------------------------------------

    def test_fill_if_absent_flags_the_declared_cf_drift(
        self, p50_export, hybrid_scenario
    ):
        # The headline finding: declared 0.20 vs modelled 0.179 trips the guard (−10.5%).
        with pytest.raises(SolarAdapterDriftError) as exc:
            solar_export_to_scenario_patch(
                p50_export, hybrid_scenario, adapter_mode="fill_if_absent"
            )
        assert exc.value.field.endswith("solar.capacity_factor")
        assert exc.value.drift_pct == pytest.approx(10.5, abs=0.2)
        assert exc.value.mode == "fill_if_absent"

    def test_fill_if_absent_preserves_aligned(self, p50_export, aligned_scenario):
        patch = solar_export_to_scenario_patch(
            p50_export, aligned_scenario, adapter_mode="fill_if_absent"
        )
        # Aligned value preserved — YAML wins; nothing written, headline untouched.
        assert patch["generation"]["technologies"]["solar"][
            "capacity_factor"
        ] == pytest.approx(_SOLAR_CF_MODELLED)

    def test_fill_if_absent_writes_missing_and_reblends(self, p50_export):
        # Solar CF absent; capacity_mw present (and matching) — adapter fills CF + aep_gwh
        # and re-blends the headline.
        scen = {
            "project": {"capacity_mw": _PROJECT_MW},
            "generation": {
                "technologies": {
                    "wind": {"capacity_mw": _WIND_MW, "capacity_factor": _WIND_CF},
                    "solar": {"capacity_mw": _SOLAR_MW},
                }
            },
        }
        patch = solar_export_to_scenario_patch(
            p50_export, scen, adapter_mode="fill_if_absent"
        )
        solar = patch["generation"]["technologies"]["solar"]
        assert solar["capacity_factor"] == pytest.approx(_SOLAR_CF_MODELLED)  # filled
        assert solar["aep_gwh"] == pytest.approx(_SOLAR_AEP_MODELLED)  # filled
        assert patch["project"]["capacity_factor"] == pytest.approx(
            _BLEND_AFTER_OVERWRITE
        )

    def test_fill_if_absent_tolerance_configurable(self, p50_export, hybrid_scenario):
        # The 10.5% declared-vs-modelled drift passes with a wide tolerance; YAML preserved.
        patch = solar_export_to_scenario_patch(
            p50_export,
            hybrid_scenario,
            adapter_mode="fill_if_absent",
            tolerance_pct=15.0,
        )
        assert patch["generation"]["technologies"]["solar"]["capacity_factor"] == 0.20

    # -- mode: validate_only -----------------------------------------------

    def test_validate_only_passes_when_aligned(self, p50_export, aligned_scenario):
        patch = solar_export_to_scenario_patch(
            p50_export, aligned_scenario, adapter_mode="validate_only"
        )
        assert patch["generation"]["technologies"]["solar"][
            "capacity_factor"
        ] == pytest.approx(_SOLAR_CF_MODELLED)
        assert patch["solar_resource"]["adapter_mode"] == "validate_only"

    def test_validate_only_raises_on_drift(self, p50_export, hybrid_scenario):
        with pytest.raises(SolarAdapterDriftError) as exc:
            solar_export_to_scenario_patch(
                p50_export, hybrid_scenario, adapter_mode="validate_only"
            )
        assert exc.value.field.endswith("solar.capacity_factor")
        assert exc.value.drift_pct > DEFAULT_TOLERANCE_PCT

    def test_validate_only_raises_on_missing(self, p50_export):
        scen = {
            "project": {"capacity_mw": _PROJECT_MW},
            "generation": {"technologies": {"solar": {"capacity_mw": _SOLAR_MW}}},
        }
        with pytest.raises(SolarAdapterDriftError) as exc:
            solar_export_to_scenario_patch(
                p50_export, scen, adapter_mode="validate_only"
            )
        assert exc.value.scenario_value is None
        assert exc.value.mode == "validate_only"

    def test_validate_only_never_writes_economics(self, p50_export, aligned_scenario):
        before = copy.deepcopy(aligned_scenario)
        patch = solar_export_to_scenario_patch(
            p50_export, aligned_scenario, adapter_mode="validate_only"
        )
        assert aligned_scenario == before  # caller not mutated
        assert patch["generation"] == before["generation"]  # economics unchanged
        assert patch["project"] == before["project"]

    # -- immutability + provenance -----------------------------------------

    @pytest.mark.parametrize("mode", ["overwrite", "fill_if_absent", "validate_only"])
    def test_input_dict_not_mutated(self, p50_export, aligned_scenario, mode):
        before = copy.deepcopy(aligned_scenario)
        try:
            solar_export_to_scenario_patch(
                p50_export, aligned_scenario, adapter_mode=mode
            )
        except SolarAdapterDriftError:
            pass
        assert aligned_scenario == before, f"input mutated under mode={mode}"

    @pytest.mark.parametrize("mode", ["overwrite", "fill_if_absent", "validate_only"])
    def test_provenance_metadata_present(self, p50_export, aligned_scenario, mode):
        patch = solar_export_to_scenario_patch(
            p50_export, aligned_scenario, adapter_mode=mode
        )
        meta = patch["solar_resource"]
        assert meta["source"] == "frozen_export"
        assert meta["scenario"] == "P50"
        assert meta["technology"] == "solar"
        assert meta["net_aep_gwh"] == pytest.approx(_SOLAR_AEP_MODELLED)
        assert meta["capacity_factor_decimal"] == pytest.approx(_SOLAR_CF_MODELLED)
        assert meta["dc_capacity_mw"] == _SOLAR_MW
        assert meta["adapter_mode"] == mode
        assert meta["specific_yield_kwh_per_kwp"] == pytest.approx(1568.2)

    def test_provenance_preserves_existing_solar_block(
        self, p50_export, hybrid_scenario
    ):
        hybrid_scenario["solar_resource"] = {
            "latitude": 8.27,
            "annual_ghi_kwh_m2": 2000.0,
        }
        patch = solar_export_to_scenario_patch(
            p50_export, hybrid_scenario, adapter_mode="overwrite"
        )
        assert patch["solar_resource"]["latitude"] == 8.27  # existing preserved
        assert patch["solar_resource"]["annual_ghi_kwh_m2"] == 2000.0
        assert patch["solar_resource"]["source"] == "frozen_export"  # new added

    # -- headline re-blend: storage excluded -------------------------------

    def test_reblend_excludes_storage(self, p50_export, hybrid_scenario):
        # A BESS tech carrying a spurious capacity_factor must NOT enter the blend —
        # matching finance.tech_types.is_storage_type, which the engine uses.
        hybrid_scenario["generation"]["technologies"]["bess"] = {
            "type": "bess",
            "capacity_mw": 10.0,
            "capacity_factor": 0.5,  # spurious — must be ignored
        }
        patch = solar_export_to_scenario_patch(
            p50_export, hybrid_scenario, adapter_mode="overwrite"
        )
        # Blend is still wind+solar only; the 10 MW @ 0.5 storage is excluded.
        assert patch["project"]["capacity_factor"] == pytest.approx(
            _BLEND_AFTER_OVERWRITE
        )

    # -- argument hygiene + helper -----------------------------------------

    def test_bogus_adapter_mode_rejected(self, p50_export):
        with pytest.raises(ValueError, match="adapter_mode"):
            solar_export_to_scenario_patch(
                p50_export, {}, adapter_mode="bogus"  # type: ignore[arg-type]
            )

    def test_build_solar_cashflow_export_from_result(self):
        # Duck-typed stand-in for a SolarAEPResult (keeps this test pvlib-free).
        class _Result:
            annual_energy_gwh = _SOLAR_AEP_MODELLED
            capacity_factor = _SOLAR_CF_MODELLED
            specific_yield_kwh_per_kwp = 1568.2

        export = build_solar_cashflow_export(_Result(), dc_capacity_mw=_SOLAR_MW)
        model = SolarCashflowExport.model_validate(
            export
        )  # round-trips through the schema
        assert model.scenario == "P50"
        assert model.capacity_factor == pytest.approx(_SOLAR_CF_MODELLED)
        assert model.dc_capacity_mw == _SOLAR_MW


# ---------------------------------------------------------------------------
# 2. Engine invariant: the recomputed headline reconciles per-tech (±1%)
# ---------------------------------------------------------------------------


class TestEngineInvariant:
    """Prove the re-blended project.capacity_factor satisfies the engine's own check."""

    @pytest.fixture(autouse=True)
    def _require_finance_stack(self):
        pytest.importorskip("numpy_financial")

    def test_reblended_headline_reconciles_per_tech(self, p50_export, hybrid_scenario):
        from finance.cashflow_v14_production import resolve_tech_generation_specs

        patched = solar_export_to_scenario_patch(
            p50_export, hybrid_scenario, adapter_mode="overwrite"
        )
        # Build the minimal params the resolver reads, off the re-blended headline.
        params = {
            "degradation": 0.0,
            "capacity_mw": patched["project"]["capacity_mw"],
            "capacity_factor": patched["project"]["capacity_factor"],
        }
        # Raises if the per-tech sum diverges from the headline beyond ±1% — so a clean
        # return proves the adapter's recompute matches the engine invariant exactly.
        specs = resolve_tech_generation_specs(patched, params)
        assert specs is not None
        assert {s["technology"] for s in specs} == {"wind", "solar"}
        solar_spec = next(s for s in specs if s["technology"] == "solar")
        assert solar_spec["capacity_factor"] == pytest.approx(_SOLAR_CF_MODELLED)
