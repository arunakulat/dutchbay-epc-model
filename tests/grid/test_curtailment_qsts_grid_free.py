"""Grid-FREE coverage for the D6a OpenDSS QSTS curtailment engine (#882).

These tests import NO grid library (``opendssdirect`` is ABSENT in the default venv) and
are NOT marked ``grid`` — so they run in the default ``-m 'not grid'`` coverage lane and
carry the real coverage for the PURE logic of :mod:`analytics.grid.curtailment_qsts`:

  * ``split_curtailment`` — the deemed-vs-self split, the export-cap self-shed integral,
    the BESS charge-from-surplus energy balance (recovery bounded by the D5a chargeable
    headroom), the energy-conservation invariant, and every STRICT ValueError branch;
  * ``run_qsts_curtailment`` — the gating: default-off / no-grid / no-feeder → inert
    NOT-RUN, the pathless synthetic-demo refusal, explicit feeder evidence kinds, and a
    path-backed test fixture fed by injected profiles (skips the OpenDSS solve);
  * ``_require_opendss`` — the CASPER guard raises an actionable ImportError when the
    ``[grid]`` extra is absent;
  * the schema conditional validator ``_validate_qsts_conditionals`` — present-only, and
    the ``feeder_model_path``-when-enabled requirement.

The OpenDSS solve itself (``_solve_qsts`` and its monitor helpers) is grid-marked and lives
in ``test_curtailment_qsts_dynamics.py``; it is the ONLY code carrying the
``# pragma: no cover - requires [grid] extra`` marker.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from analytics.contracts_v14 import CurtailmentShareResult
from analytics.grid import curtailment_qsts as cq
from analytics.grid.curtailment_qsts import (
    NO_FEEDER_SOURCE,
    SYNTHETIC_FEEDER_SOURCE,
    run_qsts_curtailment,
    split_curtailment,
)
from analytics.grid.grid_interface_schema import validate_grid_block

# A DutchBay-shaped co-located BESS (D5a): 40 MWh, SoH BoL→yr15 0.765, window 10%–95%.
_BESS = {
    "type": "bess",
    "energy_mwh": 40.0,
    "soh_curve": {1: 1.0, 15: 0.765},
    "min_soc": 0.10,
    "max_soc": 0.95,
    "soc_fraction": 0.90,
}
_REAL_FEEDER = "/real/dutchbay_feeder.dss"
_SYNTHETIC_MANIFEST_SHA256 = "a" * 64


# ─────────────────────────────────────────────────────── split_curtailment (deemed vs self)


def test_split_deemed_vs_self_from_physical_integrals() -> None:
    """Deemed-paid (grid-instructed) and self-shed (over-cap) are distinct integrals.

    Hour 3 generates 20 MWh over a 15 MWh cap → 5 MWh SELF-shed. Hour 2 carries a 5 MWh
    grid-INSTRUCTION (exported 10 below the cap, instruction 5 ≤ 10) → 5 MWh DEEMED-PAID.
    """
    res = split_curtailment(
        generation_mwh=[10.0, 10.0, 20.0],
        export_cap_mw=15.0,
        grid_instructed_mwh=[0.0, 5.0, 0.0],
        timestep_hours=1.0,
        feeder_source=_REAL_FEEDER,
    )
    assert isinstance(res, CurtailmentShareResult)
    assert res.ran is True
    assert res.bankable is False
    assert res.method == "opendss_qsts"
    assert res.gross_energy_mwh == pytest.approx(40.0)
    assert res.deemed_paid_energy_mwh == pytest.approx(5.0)
    assert res.self_curtailed_pre_bess_mwh == pytest.approx(5.0)
    assert res.bess_absorbed_energy_mwh == pytest.approx(0.0)  # no BESS block
    assert res.self_curtailed_energy_mwh == pytest.approx(5.0)
    assert res.curtailed_total_mwh == pytest.approx(10.0)
    assert res.hours_self_curtailed == 1
    assert res.hours_total == 3
    # Energy conservation: total == deemed + self_pre_bess.
    assert res.curtailed_total_mwh == pytest.approx(
        res.deemed_paid_energy_mwh + res.self_curtailed_pre_bess_mwh
    )


def test_split_refuses_contradictory_synthetic_provenance_before_serialization() -> (
    None
):
    with pytest.raises(ValueError, match="Synthetic/test.*contradictory"):
        split_curtailment(
            generation_mwh=[20.0],
            export_cap_mw=15.0,
            grid_instructed_mwh=[0.0],
            feeder_source="/generated/issue923.dss",
            feeder_input_kind="synthetic_placeholder",
            generated_input=False,
            observed_network_data=True,
            site_representative=True,
            canonical_finance_eligible=True,
        )


def test_deemed_paid_capped_at_exported_below_cap() -> None:
    """A grid instruction can never exceed the energy actually exported below the cap.

    Hour generates 8 MWh (below the 15 cap), instruction is 20 MWh → deemed-paid is CLAMPED
    to 8 (you cannot be instructed to shed more than you were exporting). No self-shed.
    """
    res = split_curtailment(
        generation_mwh=[8.0],
        export_cap_mw=15.0,
        grid_instructed_mwh=[20.0],
        timestep_hours=1.0,
        feeder_source=_REAL_FEEDER,
    )
    assert res.deemed_paid_energy_mwh == pytest.approx(8.0)
    assert res.self_curtailed_pre_bess_mwh == pytest.approx(0.0)
    assert res.hours_self_curtailed == 0


def test_no_curtailment_when_under_cap_and_uninstructed() -> None:
    """Below the cap with no instruction → zero curtailment, both shares 0%."""
    res = split_curtailment(
        generation_mwh=[10.0, 12.0, 5.0],
        export_cap_mw=15.0,
        grid_instructed_mwh=[0.0, 0.0, 0.0],
        timestep_hours=1.0,
        feeder_source=_REAL_FEEDER,
    )
    assert res.curtailed_total_mwh == pytest.approx(0.0)
    assert res.deemed_paid_pct == pytest.approx(0.0)
    assert res.self_curtailed_pct == pytest.approx(0.0)
    assert res.hours_self_curtailed == 0


def test_timestep_hours_scales_the_cap_ceiling() -> None:
    """A sub-hourly timestep scales the per-step MWh export ceiling (cap_mw * step_h)."""
    # 15 MW cap over a 0.5 h step = 7.5 MWh ceiling; 10 MWh gen → 2.5 MWh self-shed.
    res = split_curtailment(
        generation_mwh=[10.0],
        export_cap_mw=15.0,
        grid_instructed_mwh=[0.0],
        timestep_hours=0.5,
        feeder_source=_REAL_FEEDER,
    )
    assert res.self_curtailed_pre_bess_mwh == pytest.approx(2.5)


# ─────────────────────────────────────────────── BESS charge-from-surplus (energy balance)


def test_bess_absorbs_surplus_bounded_by_chargeable_headroom() -> None:
    """Self-shed surplus is recovered into the BESS up to the D5a chargeable headroom.

    At SoC 0.90 the SoH-degraded usable energy is 40*0.765=30.6 MWh and chargeable is
    (0.95-0.90)*30.6 = 1.53 MWh. Two hours each shed 5 MWh over the 15 cap → 10 MWh surplus;
    the BESS absorbs exactly 1.53 (the headroom), leaving 8.47 net self-curtailment. Energy
    is conserved: self_net + absorbed == self_pre_bess.
    """
    res = split_curtailment(
        generation_mwh=[20.0, 20.0],
        export_cap_mw=15.0,
        grid_instructed_mwh=[0.0, 0.0],
        timestep_hours=1.0,
        bess_grid=_BESS,
        feeder_source=_REAL_FEEDER,
    )
    assert res.self_curtailed_pre_bess_mwh == pytest.approx(10.0)
    assert res.bess_absorbed_energy_mwh == pytest.approx(1.53)
    assert res.self_curtailed_energy_mwh == pytest.approx(10.0 - 1.53)
    # The recovered energy never exceeds the headroom, and the split conserves energy.
    assert (
        res.self_curtailed_energy_mwh + res.bess_absorbed_energy_mwh
        == pytest.approx(res.self_curtailed_pre_bess_mwh)
    )


def test_bess_absorbs_all_surplus_when_headroom_ample() -> None:
    """When the BESS headroom exceeds the surplus, self-curtailment nets to zero."""
    # SoC at the floor 0.10 → chargeable (0.95-0.10)*30.6 = 26.01 MWh, far above 5 MWh.
    bess = {**_BESS, "soc_fraction": 0.10}
    res = split_curtailment(
        generation_mwh=[20.0],
        export_cap_mw=15.0,
        grid_instructed_mwh=[0.0],
        timestep_hours=1.0,
        bess_grid=bess,
        feeder_source=_REAL_FEEDER,
    )
    assert res.self_curtailed_pre_bess_mwh == pytest.approx(5.0)
    assert res.bess_absorbed_energy_mwh == pytest.approx(5.0)
    assert res.self_curtailed_energy_mwh == pytest.approx(0.0)


def test_bess_soc_fraction_is_strict_no_optimistic_default() -> None:
    """A BESS block WITH a valid window but NO soc_fraction is REJECTED (KPI-relevant, CESSPIT).

    The operating SoC sets the charge headroom that caps absorption and therefore the
    self-curtailment loss (the D6b KPI-mover). A silent mid-window / full-charge default
    would OVERSTATE headroom → overstate absorption → UNDERSTATE the loss, so it is refused
    with an actionable message rather than assumed.
    """
    bess = {k: v for k, v in _BESS.items() if k != "soc_fraction"}
    with pytest.raises(
        ValueError, match="explicit operating grid.qsts.bess.soc_fraction"
    ):
        split_curtailment(
            generation_mwh=[20.0],
            export_cap_mw=15.0,
            grid_instructed_mwh=[0.0],
            timestep_hours=1.0,
            bess_grid=bess,
            feeder_source=_REAL_FEEDER,
        )


def test_bess_absent_is_zero_recovery() -> None:
    """No BESS block → 0 recovery (a valid 'no battery' declaration, not a silent pass)."""
    res = split_curtailment(
        generation_mwh=[20.0],
        export_cap_mw=15.0,
        grid_instructed_mwh=[0.0],
        timestep_hours=1.0,
        bess_grid=None,
        feeder_source=_REAL_FEEDER,
    )
    assert res.bess_absorbed_energy_mwh == pytest.approx(0.0)
    assert res.self_curtailed_energy_mwh == pytest.approx(5.0)


# ───────────────────────────────────────────────────────────────── CESSPIT strict raises


def test_export_cap_must_be_positive() -> None:
    with pytest.raises(ValueError, match="export_cap_mw"):
        split_curtailment(
            generation_mwh=[10.0],
            export_cap_mw=0.0,
            grid_instructed_mwh=[0.0],
            feeder_source=_REAL_FEEDER,
        )


def test_timestep_hours_must_be_positive() -> None:
    with pytest.raises(ValueError, match="timestep_hours"):
        split_curtailment(
            generation_mwh=[10.0],
            export_cap_mw=15.0,
            grid_instructed_mwh=[0.0],
            timestep_hours=0.0,
            feeder_source=_REAL_FEEDER,
        )


def test_empty_generation_profile_raises() -> None:
    with pytest.raises(ValueError, match="generation_mwh"):
        split_curtailment(
            generation_mwh=[],
            export_cap_mw=15.0,
            grid_instructed_mwh=[],
            feeder_source=_REAL_FEEDER,
        )


def test_generation_profile_rejects_string() -> None:
    with pytest.raises(ValueError, match="generation_mwh"):
        split_curtailment(
            generation_mwh="10,20",  # type: ignore[arg-type]
            export_cap_mw=15.0,
            grid_instructed_mwh=[0.0, 0.0],
            feeder_source=_REAL_FEEDER,
        )


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, True])
def test_generation_sample_rejects_nan_inf_negative_bool(bad: object) -> None:
    """A NaN/inf/negative/bool generation sample is rejected (no spurious 'no breach')."""
    with pytest.raises(ValueError, match="generation_mwh"):
        split_curtailment(
            generation_mwh=[10.0, bad],  # type: ignore[list-item]
            export_cap_mw=15.0,
            grid_instructed_mwh=[0.0, 0.0],
            feeder_source=_REAL_FEEDER,
        )


def test_instruction_profile_length_must_match_generation() -> None:
    with pytest.raises(ValueError, match="grid_instructed_mwh"):
        split_curtailment(
            generation_mwh=[10.0, 10.0, 10.0],
            export_cap_mw=15.0,
            grid_instructed_mwh=[0.0, 0.0],  # wrong length
            feeder_source=_REAL_FEEDER,
        )


def test_instruction_sample_rejects_negative() -> None:
    with pytest.raises(ValueError, match="grid_instructed_mwh"):
        split_curtailment(
            generation_mwh=[10.0],
            export_cap_mw=15.0,
            grid_instructed_mwh=[-2.0],
            feeder_source=_REAL_FEEDER,
        )


def test_bess_missing_soc_fraction_raises_before_window() -> None:
    """A BESS block with no soc_fraction is rejected on the KPI-relevant SoC (CESSPIT).

    The operating SoC is required first — even a block that also omits the window fails on
    the missing soc_fraction, never silently defaulting the operating point.
    """
    bad_bess = {"type": "bess", "energy_mwh": 40.0, "soh_fraction": 0.9}
    with pytest.raises(
        ValueError, match="explicit operating grid.qsts.bess.soc_fraction"
    ):
        split_curtailment(
            generation_mwh=[20.0],
            export_cap_mw=15.0,
            grid_instructed_mwh=[0.0],
            bess_grid=bad_bess,
            feeder_source=_REAL_FEEDER,
        )


def test_malformed_bess_block_raises_via_d5a() -> None:
    """A malformed co-located BESS block is rejected by the reused D5a validators."""
    bad_bess = {**_BESS, "min_soc": 0.95, "max_soc": 0.10}  # floor >= ceiling
    with pytest.raises(ValueError):
        split_curtailment(
            generation_mwh=[20.0],
            export_cap_mw=15.0,
            grid_instructed_mwh=[0.0],
            bess_grid=bad_bess,
            feeder_source=_REAL_FEEDER,
        )


# ─────────────────────────────────────────────────────────── run_qsts_curtailment (gating)


def test_no_grid_block_is_inert() -> None:
    res = run_qsts_curtailment({})
    assert res.ran is False
    assert res.feeder_source == NO_FEEDER_SOURCE
    assert res.self_curtailed_energy_mwh is None
    assert "grid" in res.reason


def test_default_off_gate_is_inert() -> None:
    """grid.qsts.enabled not True → inert NOT-RUN (default-off)."""
    res = run_qsts_curtailment({"grid": {"qsts": {"enabled": False}}})
    assert res.ran is False
    assert res.feeder_source == NO_FEEDER_SOURCE
    assert res.gross_energy_mwh is None
    assert "default-off" in res.reason


def test_missing_qsts_block_is_inert() -> None:
    res = run_qsts_curtailment({"grid": {"study_enabled": True}})
    assert res.ran is False
    assert res.feeder_source == NO_FEEDER_SOURCE


def test_enabled_but_unclassified_feeder_fails_closed() -> None:
    """An enabled study cannot turn missing identity into an innocent inert result."""
    with pytest.raises(ValueError, match="input_kind must be one of"):
        run_qsts_curtailment({"grid": {"qsts": {"enabled": True}}})


def test_enabled_with_missing_classification_fails_closed() -> None:
    """A filesystem path alone is never QSTS provenance."""
    with pytest.raises(ValueError, match="input_kind must be one of"):
        run_qsts_curtailment(
            {
                "grid": {
                    "qsts": {
                        "enabled": True,
                        "feeder_model_path": "/no/such/feeder.dss",
                    }
                }
            }
        )


def test_synthetic_feeder_is_refused_not_fabricated() -> None:
    """A synthetic/demo feeder must NOT surface as a real curtailment figure (NO SPURIOUS PASS).

    Even though the demo path can be exercised for a live smoke test, the engine refuses to
    emit a real figure for it and does NOT overwrite the real loss placeholder — the result
    is inert with the synthetic-feeder source and every energy field None.
    """
    res = run_qsts_curtailment(
        {
            "grid": {
                "qsts": {
                    "enabled": True,
                    "input_kind": "test_fixture",
                    "use_synthetic_demo": True,
                }
            }
        }
    )
    assert res.ran is False
    assert res.feeder_source == SYNTHETIC_FEEDER_SOURCE
    assert res.self_curtailed_energy_mwh is None
    assert res.curtailed_total_mwh is None
    assert "synthetic" in res.reason.lower()
    assert "placeholder" in res.notes.lower()


def test_typed_fixture_with_injected_profiles_produces_advisory_split(
    tmp_path: Path,
) -> None:
    """An explicitly typed fixture can exercise accounting without becoming site evidence."""
    feeder = tmp_path / "feeder.dss"
    feeder.write_text("! demo master\n")
    config = {
        "grid": {
            "qsts": {
                "enabled": True,
                "input_kind": "test_fixture",
                "feeder_model_path": str(feeder),
                "export_cap_mw": 15.0,
                "bess": _BESS,
            }
        }
    }
    res = run_qsts_curtailment(
        config,
        generation_mwh=[20.0, 20.0],
        grid_instructed_mwh=[0.0, 0.0],
    )
    assert res.ran is True
    assert res.feeder_source == str(feeder)
    assert res.feeder_input_kind == "test_fixture"
    assert res.generated_input is True
    assert res.canonical_finance_eligible is False
    payload = res.model_dump()
    assert payload["feeder_input_kind"] == "test_fixture"
    assert payload["generated_input"] is True
    assert payload["site_representative"] is False
    assert payload["canonical_finance_eligible"] is False
    assert payload["limitations"]
    assert res.self_curtailed_pre_bess_mwh == pytest.approx(10.0)
    assert res.bess_absorbed_energy_mwh == pytest.approx(1.53)
    assert res.self_curtailed_energy_mwh == pytest.approx(10.0 - 1.53)


def test_real_feeder_export_cap_from_config(tmp_path: Path) -> None:
    """The export cap is resolved from grid.qsts.export_cap_mw when not passed explicitly."""
    feeder = tmp_path / "feeder.dss"
    feeder.write_text("! demo\n")
    config = {
        "grid": {
            "qsts": {
                "enabled": True,
                "input_kind": "test_fixture",
                "feeder_model_path": str(feeder),
                "export_cap_mw": 12.0,
            }
        }
    }
    res = run_qsts_curtailment(config, generation_mwh=[20.0], grid_instructed_mwh=[0.0])
    assert res.export_cap_mw == pytest.approx(12.0)
    assert res.self_curtailed_pre_bess_mwh == pytest.approx(8.0)  # 20 - 12


def test_real_feeder_missing_export_cap_raises(tmp_path: Path) -> None:
    """Enabled real study with injected profiles but NO export cap → strict raise (CESSPIT)."""
    feeder = tmp_path / "feeder.dss"
    feeder.write_text("! demo\n")
    config = {
        "grid": {
            "qsts": {
                "enabled": True,
                "input_kind": "test_fixture",
                "feeder_model_path": str(feeder),
            }
        }
    }
    with pytest.raises(ValueError, match="export_cap_mw"):
        run_qsts_curtailment(config, generation_mwh=[20.0], grid_instructed_mwh=[0.0])


def test_instruction_defaults_to_zero_when_only_generation_injected(
    tmp_path: Path,
) -> None:
    """Injecting only a generation profile defaults the grid-instruction to zeros."""
    feeder = tmp_path / "feeder.dss"
    feeder.write_text("! demo\n")
    config = {
        "grid": {
            "qsts": {
                "enabled": True,
                "input_kind": "test_fixture",
                "feeder_model_path": str(feeder),
                "export_cap_mw": 15.0,
            }
        }
    }
    res = run_qsts_curtailment(config, generation_mwh=[20.0])
    assert res.deemed_paid_energy_mwh == pytest.approx(0.0)
    assert res.self_curtailed_pre_bess_mwh == pytest.approx(5.0)


# ─────────────────────────────────── energy-conservation invariant guard (NO SPURIOUS PASS)


def test_resolve_feeder_refuses_unpinned_site_declaration(
    tmp_path: Path,
) -> None:
    """#1072 removes declaration-only site classification and requires evidence binding."""
    feeder = tmp_path / "f.dss"
    feeder.write_text("! contract-shape test only; not site evidence\n")
    with pytest.raises(ValueError, match="evidence_manifest"):
        cq._resolve_feeder(
            {
                "qsts": {
                    "input_kind": "engineer_prepared_site_model",
                    "feeder_model_path": str(feeder),
                    "finance_wiring": {
                        "enabled": False,
                        "mode": "canonical",
                        "canonical_eligible": True,
                    },
                }
            }
        )


def test_resolve_feeder_synthetic_demo_is_not_real() -> None:
    resolved = cq._resolve_feeder(
        {
            "qsts": {
                "input_kind": "test_fixture",
                "use_synthetic_demo": True,
            }
        }
    )
    assert resolved.source == SYNTHETIC_FEEDER_SOURCE
    assert resolved.can_solve is False
    assert resolved.generated_input is True


def test_runtime_refuses_builtin_demo_and_path_ambiguity(tmp_path: Path) -> None:
    feeder = tmp_path / "also-present.dss"
    feeder.write_text("! explicit path must not be ignored\n")
    with pytest.raises(ValueError, match="ambiguous with feeder_model_path"):
        cq._resolve_feeder(
            {
                "qsts": {
                    "input_kind": "test_fixture",
                    "use_synthetic_demo": True,
                    "feeder_model_path": str(feeder),
                }
            }
        )


@pytest.mark.parametrize("invalid_demo", ["true", 1, [True]])
def test_runtime_refuses_nonboolean_synthetic_demo_flag(invalid_demo: object) -> None:
    with pytest.raises(
        ValueError, match="use_synthetic_demo must be a literal boolean"
    ):
        cq._resolve_feeder(
            {
                "qsts": {
                    "input_kind": "engineer_prepared_site_model",
                    "use_synthetic_demo": invalid_demo,
                    "feeder_model_path": "/missing/site.dss",
                    "finance_wiring": {
                        "enabled": False,
                        "mode": "canonical",
                        "canonical_eligible": True,
                    },
                }
            }
        )


def test_runtime_refuses_padded_input_kind_instead_of_normalizing_it() -> None:
    with pytest.raises(ValueError, match="input_kind must be one of"):
        cq._resolve_feeder(
            {
                "qsts": {
                    "input_kind": " engineer_prepared_site_model ",
                    "feeder_model_path": "/missing/site.dss",
                    "finance_wiring": {
                        "enabled": False,
                        "mode": "canonical",
                        "canonical_eligible": True,
                    },
                }
            }
        )


@pytest.mark.parametrize("invalid_mode", [["canonical"], {"mode": "canonical"}])
def test_runtime_refuses_nonstring_finance_mode(invalid_mode: object) -> None:
    with pytest.raises(ValueError, match="finance_wiring.mode must be"):
        cq._resolve_feeder(
            {
                "qsts": {
                    "input_kind": "engineer_prepared_site_model",
                    "feeder_model_path": "/missing/site.dss",
                    "finance_wiring": {
                        "enabled": False,
                        "mode": invalid_mode,
                        "canonical_eligible": False,
                    },
                }
            }
        )


def test_resolve_feeder_missing_governed_file_fails_closed() -> None:
    with pytest.raises(ValueError, match="missing or not a file"):
        cq._resolve_feeder(
            {
                "qsts": {
                    "input_kind": "synthetic_placeholder",
                    "feeder_model_path": "/no/such.dss",
                    "source_manifest_sha256": _SYNTHETIC_MANIFEST_SHA256,
                }
            }
        )


def test_path_backed_synthetic_requires_external_manifest_digest(
    tmp_path: Path,
) -> None:
    feeder = tmp_path / "Master.dss"
    feeder.write_text("! synthetic placeholder\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source_manifest_sha256"):
        cq._resolve_feeder(
            {
                "qsts": {
                    "input_kind": "synthetic_placeholder",
                    "feeder_model_path": str(feeder),
                }
            }
        )


@pytest.mark.parametrize(
    "invalid_digest",
    [True, 1, "A" * 64, "a" * 63, "g" * 64, ["a" * 64]],
)
def test_runtime_manifest_digest_is_exact_lowercase_sha256(
    invalid_digest: object,
) -> None:
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        cq._resolve_feeder(
            {
                "qsts": {
                    "input_kind": "synthetic_placeholder",
                    "feeder_model_path": "/no/such.dss",
                    "source_manifest_sha256": invalid_digest,
                }
            }
        )


def test_runtime_manifest_digest_cannot_be_attached_to_test_fixture() -> None:
    with pytest.raises(ValueError, match="test_fixture inputs cannot carry"):
        cq._resolve_feeder(
            {
                "qsts": {
                    "input_kind": "test_fixture",
                    "feeder_model_path": "/no/such.dss",
                    "source_manifest_sha256": _SYNTHETIC_MANIFEST_SHA256,
                }
            }
        )


def test_contract_refuses_malformed_source_manifest_digest() -> None:
    with pytest.raises(ValueError, match="source_manifest_sha256.*64 lowercase"):
        CurtailmentShareResult(
            ran=False,
            feeder_source=NO_FEEDER_SOURCE,
            source_manifest_sha256="not-a-sha256",
        )


def test_contract_manifest_digest_is_reserved_for_governed_synthetic_package() -> None:
    with pytest.raises(ValueError, match="reserved.*synthetic_placeholder"):
        CurtailmentShareResult(
            ran=False,
            feeder_source="/fixtures/Master.dss",
            feeder_input_kind="test_fixture",
            generated_input=True,
            source_manifest_sha256=_SYNTHETIC_MANIFEST_SHA256,
        )


def test_default_off_does_not_import_synthetic_package_verifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        sys.modules, "analytics.grid.synthetic_feeder_placeholder", None
    )
    result = run_qsts_curtailment(
        {
            "grid": {
                "qsts": {
                    "enabled": False,
                    "input_kind": "synthetic_placeholder",
                    "feeder_model_path": "/not/present/Master.dss",
                }
            }
        }
    )
    assert result.ran is False
    assert result.source_manifest_sha256 is None


def test_enabled_synthetic_verifier_dependency_gap_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    master_path = tmp_path / "feeder" / "Master.dss"
    master_path.parent.mkdir()
    master_path.write_text("! synthetic placeholder\n", encoding="utf-8")
    monkeypatch.setitem(
        sys.modules, "analytics.grid.synthetic_feeder_placeholder", None
    )
    with pytest.raises(ImportError, match="locked synthetic-feeder dependencies"):
        run_qsts_curtailment(
            {
                "grid": {
                    "qsts": {
                        "enabled": True,
                        "input_kind": "synthetic_placeholder",
                        "feeder_model_path": str(master_path),
                        "source_manifest_sha256": _SYNTHETIC_MANIFEST_SHA256,
                    }
                }
            },
            generation_mwh=[151.0],
            grid_instructed_mwh=[0.0],
            export_cap_mw=150.0,
        )


def test_resolve_feeder_non_mapping_qsts_is_none() -> None:
    """A grid whose qsts is not a mapping resolves to no feeder (defensive guard)."""
    resolved = cq._resolve_feeder({"qsts": ["oops"]})
    assert resolved.source is None
    assert resolved.can_solve is False


def test_grid_instructed_profile_absent_is_zeros() -> None:
    """No committed instruction schedule → all-zeros (the QSTS asserts no deemed curtailment)."""
    prof = cq._resolve_grid_instructed_profile_mw({"qsts": {}}, n_steps=4)
    assert prof == [0.0, 0.0, 0.0, 0.0]


def test_grid_instructed_profile_present_is_validated() -> None:
    """A committed instruction schedule is passed through as a strict MW series."""
    prof = cq._resolve_grid_instructed_profile_mw(
        {"qsts": {"grid_instructed_profile_mw": [0.0, 3.0, 0.0]}}, n_steps=3
    )
    assert prof == [0.0, 3.0, 0.0]


def test_grid_instructed_profile_length_must_match_generation() -> None:
    """A committed instruction schedule whose length != generation is rejected (CESSPIT)."""
    with pytest.raises(ValueError, match="grid.qsts.grid_instructed_profile_mw"):
        cq._resolve_grid_instructed_profile_mw(
            {"qsts": {"grid_instructed_profile_mw": [1.0, 2.0]}}, n_steps=3
        )


def test_grid_instructed_profile_non_mapping_qsts_is_zeros() -> None:
    """A grid whose qsts is not a mapping yields an all-zeros instruction schedule."""
    prof = cq._resolve_grid_instructed_profile_mw({"qsts": ["oops"]}, n_steps=2)
    assert prof == [0.0, 0.0]


def test_energy_conserved_helper_accepts_a_valid_balance() -> None:
    """A physically consistent balance passes silently (the happy path)."""
    cq._assert_energy_conserved(
        self_pre_bess=10.0, bess_absorbed=4.0, self_curtailed=6.0, headroom=5.0
    )


def test_energy_conserved_rejects_absorption_over_headroom() -> None:
    """Absorbing more than the D5a chargeable headroom is a no-double-count breach."""
    with pytest.raises(ValueError, match="exceeds the SoC chargeable headroom"):
        cq._assert_energy_conserved(
            self_pre_bess=10.0, bess_absorbed=6.0, self_curtailed=4.0, headroom=5.0
        )


def test_energy_conserved_rejects_negative_self_curtailment() -> None:
    """A negative net self-curtailment (absorbed > surplus) is physically impossible."""
    with pytest.raises(ValueError, match="negative"):
        cq._assert_energy_conserved(
            self_pre_bess=3.0, bess_absorbed=3.0, self_curtailed=-1.0, headroom=5.0
        )


def test_energy_conserved_rejects_non_partition() -> None:
    """self_curtailed + bess_absorbed must equal the pre-BESS surplus (energy conserved)."""
    with pytest.raises(ValueError, match="not conserved"):
        cq._assert_energy_conserved(
            self_pre_bess=10.0, bess_absorbed=4.0, self_curtailed=5.0, headroom=5.0
        )


# ───────────────────────────────────────────────────────────── CASPER optional-dep guard


def test_require_opendss_raises_actionable_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """opendssdirect absent (simulated; environment-independent) → actionable ImportError."""
    monkeypatch.setitem(sys.modules, "opendssdirect", None)
    with pytest.raises(ImportError, match=r"\[grid\] extra"):
        cq._require_opendss()


# ─────────────────────────────────────────────── schema conditional validator (CESSPIT)


def test_schema_qsts_absent_is_byte_identical() -> None:
    """A grid block WITHOUT a qsts sub-block passes cleanly (opt-in; byte-identical)."""
    errors: list[str] = []
    validate_grid_block({"grid": {"study_enabled": True}}, errors)
    assert errors == []


def test_schema_qsts_enabled_must_be_bool() -> None:
    errors: list[str] = []
    validate_grid_block({"grid": {"qsts": {"enabled": "yes"}}}, errors)
    assert any("qsts.enabled" in e for e in errors)


def test_schema_qsts_must_be_mapping() -> None:
    errors: list[str] = []
    validate_grid_block({"grid": {"qsts": ["enabled"]}}, errors)
    assert any("grid.qsts must be a mapping" in e for e in errors)


def test_schema_enabled_requires_feeder_path() -> None:
    """Enabled QSTS with no feeder_model_path is REJECTED (a synthetic demo isn't bankable)."""
    errors: list[str] = []
    validate_grid_block({"grid": {"qsts": {"enabled": True}}}, errors)
    assert any("feeder_model_path" in e for e in errors)
    assert any("input_kind" in e for e in errors)


def test_schema_enabled_with_pinned_site_evidence_passes() -> None:
    errors: list[str] = []
    validate_grid_block(
        {
            "grid": {
                "qsts": {
                    "enabled": True,
                    "input_kind": "engineer_prepared_site_model",
                    "feeder_model_path": "/x/feeder.dss",
                    "evidence_manifest_path": "/x/evidence.json",
                    "evidence_manifest_sha256": "b" * 64,
                }
            }
        },
        errors,
    )
    assert errors == []


def test_schema_path_backed_synthetic_requires_external_manifest_digest() -> None:
    errors: list[str] = []
    validate_grid_block(
        {
            "grid": {
                "qsts": {
                    "enabled": True,
                    "input_kind": "synthetic_placeholder",
                    "feeder_model_path": "/x/synthetic.dss",
                }
            }
        },
        errors,
    )
    assert any(
        "source_manifest_sha256" in error and "requires" in error for error in errors
    )


@pytest.mark.parametrize(
    "invalid_digest",
    [True, 1, "A" * 64, "a" * 63, "g" * 64, {"sha256": "a" * 64}],
)
def test_schema_manifest_digest_is_exact_lowercase_sha256(
    invalid_digest: object,
) -> None:
    errors: list[str] = []
    validate_grid_block(
        {
            "grid": {
                "qsts": {
                    "enabled": True,
                    "input_kind": "synthetic_placeholder",
                    "feeder_model_path": "/x/synthetic.dss",
                    "source_manifest_sha256": invalid_digest,
                }
            }
        },
        errors,
    )
    assert any("64 lowercase hexadecimal" in error for error in errors)


def test_schema_manifest_digest_is_reserved_for_governed_synthetic_package() -> None:
    errors: list[str] = []
    validate_grid_block(
        {
            "grid": {
                "qsts": {
                    "enabled": True,
                    "input_kind": "test_fixture",
                    "feeder_model_path": "/x/fixture.dss",
                    "source_manifest_sha256": _SYNTHETIC_MANIFEST_SHA256,
                }
            }
        },
        errors,
    )
    assert any("reserved for the governed" in error for error in errors)


def test_schema_pathless_demo_refuses_package_manifest_digest() -> None:
    errors: list[str] = []
    validate_grid_block(
        {
            "grid": {
                "qsts": {
                    "enabled": True,
                    "input_kind": "synthetic_placeholder",
                    "use_synthetic_demo": True,
                    "source_manifest_sha256": _SYNTHETIC_MANIFEST_SHA256,
                }
            }
        },
        errors,
    )
    assert any(
        "pathless" in error and "has no package manifest" in error for error in errors
    )


def test_schema_refuses_synthetic_input_as_canonical_finance() -> None:
    errors: list[str] = []
    validate_grid_block(
        {
            "grid": {
                "qsts": {
                    "enabled": True,
                    "input_kind": "synthetic_placeholder",
                    "feeder_model_path": "/x/synthetic.dss",
                    "source_manifest_sha256": _SYNTHETIC_MANIFEST_SHA256,
                    "finance_wiring": {
                        "enabled": True,
                        "mode": "canonical",
                        "canonical_eligible": True,
                    },
                }
            }
        },
        errors,
    )
    assert any("synthetic/test inputs are never canonical" in e for e in errors)
    assert any("mode='canonical' refuses" in e for e in errors)


def test_schema_accepts_parked_synthetic_counterfactual_contract() -> None:
    errors: list[str] = []
    validate_grid_block(
        {
            "grid": {
                "qsts": {
                    "enabled": True,
                    "input_kind": "synthetic_placeholder",
                    "feeder_model_path": "/x/synthetic.dss",
                    "source_manifest_sha256": _SYNTHETIC_MANIFEST_SHA256,
                    "finance_wiring": {
                        "enabled": False,
                        "mode": "synthetic_counterfactual",
                        "canonical_eligible": False,
                    },
                }
            }
        },
        errors,
    )
    assert errors == []


def test_schema_refuses_enabled_synthetic_counterfactual_until_segregated_path_exists() -> (
    None
):
    errors: list[str] = []
    validate_grid_block(
        {
            "grid": {
                "qsts": {
                    "enabled": True,
                    "input_kind": "synthetic_placeholder",
                    "feeder_model_path": "/x/synthetic.dss",
                    "source_manifest_sha256": _SYNTHETIC_MANIFEST_SHA256,
                    "finance_wiring": {
                        "enabled": True,
                        "mode": "synthetic_counterfactual",
                        "canonical_eligible": False,
                    },
                }
            }
        },
        errors,
    )
    assert any(
        "cannot be enabled in the canonical cashflow pipeline" in e for e in errors
    )


def test_schema_accepts_explicit_site_model_canonical_contract() -> None:
    errors: list[str] = []
    validate_grid_block(
        {
            "grid": {
                "qsts": {
                    "enabled": True,
                    "input_kind": "engineer_prepared_site_model",
                    "feeder_model_path": "/x/site.dss",
                    "evidence_manifest_path": "/x/evidence.json",
                    "evidence_manifest_sha256": "b" * 64,
                    "finance_wiring": {
                        "enabled": True,
                        "mode": "canonical",
                        "canonical_eligible": True,
                    },
                }
            }
        },
        errors,
    )
    assert errors == []


def test_schema_rejects_nonstring_input_kind_without_crashing() -> None:
    errors: list[str] = []
    validate_grid_block(
        {
            "grid": {
                "qsts": {
                    "enabled": True,
                    "input_kind": ["test_fixture"],
                    "feeder_model_path": "/x/fixture.dss",
                }
            }
        },
        errors,
    )
    assert any("input_kind must be one of" in e for e in errors)


@pytest.mark.parametrize("invalid_mode", [["canonical"], {"mode": "canonical"}])
def test_schema_rejects_nonstring_finance_mode_without_crashing(
    invalid_mode: object,
) -> None:
    errors: list[str] = []
    validate_grid_block(
        {
            "grid": {
                "qsts": {
                    "enabled": True,
                    "input_kind": "engineer_prepared_site_model",
                    "feeder_model_path": "/x/site.dss",
                    "finance_wiring": {
                        "enabled": True,
                        "mode": invalid_mode,
                        "canonical_eligible": True,
                    },
                }
            }
        },
        errors,
    )
    assert any("finance_wiring.mode must be" in e for e in errors)


def test_schema_rejects_path_and_builtin_demo_ambiguity() -> None:
    errors: list[str] = []
    validate_grid_block(
        {
            "grid": {
                "qsts": {
                    "enabled": True,
                    "input_kind": "test_fixture",
                    "use_synthetic_demo": True,
                    "feeder_model_path": "/x/fixture.dss",
                }
            }
        },
        errors,
    )
    assert any("ambiguous with feeder_model_path" in e for e in errors)


def test_runtime_refuses_path_without_explicit_input_kind(tmp_path: Path) -> None:
    feeder = tmp_path / "unclassified.dss"
    feeder.write_text("! path existence is not provenance\n")
    config = {
        "grid": {
            "qsts": {
                "enabled": True,
                "feeder_model_path": str(feeder),
                "export_cap_mw": 10.0,
            }
        }
    }
    with pytest.raises(ValueError, match="filesystem path is not provenance"):
        run_qsts_curtailment(config, generation_mwh=[5.0])


def test_schema_disabled_needs_no_feeder_path() -> None:
    """A present-but-disabled qsts block needs no feeder path (default-off is valid)."""
    errors: list[str] = []
    validate_grid_block({"grid": {"qsts": {"enabled": False}}}, errors)
    assert errors == []
