#!/usr/bin/env python
"""Tests for the AEP-summary builder — the two-stage power-curve gap closure.

Covers the curve-selection identifier guard (config slug <-> manifest source_id
<-> store), the one-call summary regeneration (reproduces the canonical 402.6),
and the write/reload round-trip into the AEP loader.

Context:
    Sprint 11 follow-up — power-curve sourcing wiring (#181 thread).
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from analytics.loader.aep_loader import load_aep_from_summary
from analytics.wind.aep_summary_builder import (
    build_aep_summary_from_config,
    validate_curve_selection,
    write_aep_summary,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


@pytest.fixture
def cfg() -> dict:
    return yaml.safe_load(LENDER_CONFIG.read_text())


# ── identifier guard ──────────────────────────────────────────────────────────


def test_lender_curve_selection_valid(cfg: dict) -> None:
    sel = validate_curve_selection(cfg)
    assert sel == {
        "source_id": "IEA_REFERENCE_10MW_198_PC",
        "curve_key": "iea_reference_10mw",
        "source_type": "REFERENCE",
    }


def test_curve_key_mismatch_raises(cfg: dict) -> None:
    bad = copy.deepcopy(cfg)
    bad["resource"]["power_curve"]["curve_key"] = "vestas_v150_5p6"  # != manifest
    with pytest.raises(ValueError, match="identifier mismatch"):
        validate_curve_selection(bad)


def test_missing_curve_key_raises(cfg: dict) -> None:
    bad = copy.deepcopy(cfg)
    del bad["resource"]["power_curve"]["curve_key"]
    with pytest.raises(ValueError, match="missing resource.power_curve.curve_key"):
        validate_curve_selection(bad)


def test_unknown_source_raises(cfg: dict) -> None:
    bad = copy.deepcopy(cfg)
    bad["resource"]["power_curve"]["source_id"] = "NOT_A_SOURCE"
    with pytest.raises(KeyError):
        validate_curve_selection(bad)


# ── regeneration ──────────────────────────────────────────────────────────────


def test_regen_reproduces_canonical(cfg: dict) -> None:
    summary = build_aep_summary_from_config(cfg)
    assert summary["net_site_aep_gwh"] == pytest.approx(
        464.3, abs=0.5
    )  # ERA5-fitted Weibull, post 2% P50 over-prediction haircut
    assert summary["gross_aep_gwh"] == pytest.approx(554.1, abs=1.0)
    assert summary["capacity_factor"] == pytest.approx(0.332, abs=0.002)
    assert summary["power_curve_key"] == "iea_reference_10mw"
    assert summary["source_id"] == "IEA_REFERENCE_10MW_198_PC"
    assert summary["provenance"]["aep"]["is_placeholder"] is False
    # WIND-2 (#478): the committed lender supplies no live-wake spec -> the frozen config wake
    # path is used and DISCLOSED, and the headline is byte-identical (still ~464.3).
    assert summary["wake_source"] == "frozen_config_pct"
    assert summary["losses"]["wake_loss_pct"] == pytest.approx(7.28, abs=1e-9)


# ── WIND-2 (#478): wake-source resolution + fail-loud live path ────────────────


def test_wake_resolves_frozen_when_no_live_spec(cfg: dict) -> None:
    from analytics.power_curves.oem_parser import parse_power_curve
    from analytics.wind.aep_summary_builder import _resolve_wake_loss

    curve = parse_power_curve("iea_reference_10mw")
    pct, source = _resolve_wake_loss(
        cfg["resource"], curve, weibull_a=8.199, weibull_k=2.665, hub_height_m=150.0
    )
    assert source == "frozen_config_pct"
    assert pct == pytest.approx(7.28, abs=1e-9)


def test_wake_live_with_incomplete_inputs_fails_loud(cfg: dict) -> None:
    from analytics.power_curves.oem_parser import parse_power_curve
    from analytics.wind.aep_summary_builder import _resolve_wake_loss

    cfg = copy.deepcopy(cfg)
    # model_live on, but no wind rose / coordinates -> must RAISE, not degrade to uniform rose.
    cfg["resource"]["wake"] = {"model_live": True}
    curve = parse_power_curve("iea_reference_10mw")
    with pytest.raises(ValueError, match="wind_rose_freq"):
        _resolve_wake_loss(
            cfg["resource"], curve, weibull_a=8.199, weibull_k=2.665, hub_height_m=150.0
        )


def test_wake_frozen_path_requires_a_wake_pct(cfg: dict) -> None:
    from analytics.power_curves.oem_parser import parse_power_curve
    from analytics.wind.aep_summary_builder import _resolve_wake_loss

    cfg = copy.deepcopy(cfg)
    cfg["resource"]["losses"].pop("wake_loss_pct", None)
    curve = parse_power_curve("iea_reference_10mw")
    with pytest.raises(ValueError, match="wake_loss_pct is required"):
        _resolve_wake_loss(
            cfg["resource"], curve, weibull_a=8.199, weibull_k=2.665, hub_height_m=150.0
        )


def test_wake_live_drives_pywake_when_fully_specified(cfg: dict) -> None:
    pytest.importorskip("py_wake")
    from analytics.power_curves.oem_parser import parse_power_curve
    from analytics.wind.aep_summary_builder import _resolve_wake_loss

    cfg = copy.deepcopy(cfg)
    cfg["resource"]["wake"] = {
        "model_live": True,
        "rotor_diameter_m": 198.0,
        "coordinates": {"x_m": [0.0] * 15, "y_m": [i * 650.0 for i in range(15)]},
        "wind_rose_freq": [3, 3, 3, 4, 6, 9, 14, 20, 16, 9, 6, 4],
        "deficit_model": "bastankhah",
    }
    curve = parse_power_curve("iea_reference_10mw")
    pct, source = _resolve_wake_loss(
        cfg["resource"], curve, weibull_a=8.199, weibull_k=2.665, hub_height_m=150.0
    )
    assert source.startswith("pywake_live")
    assert 3.0 < pct < 15.0  # a real modelled wake, not the flat placeholder


# ── #832: coastal-TI parametrization (config-driven, CESSPIT-strict, default-off) ─


def test_resolve_wake_ti_defaults_to_kernel_ti() -> None:
    # DEFAULT-OFF: an unset TI reproduces the engine default 0.10 (today's exact k*).
    from analytics.wind.aep_summary_builder import _resolve_wake_ti
    from wind_resource.bankable_aep import DEFAULT_TURBULENCE_INTENSITY

    assert _resolve_wake_ti({}) == DEFAULT_TURBULENCE_INTENSITY
    assert _resolve_wake_ti({"model_live": True}) == DEFAULT_TURBULENCE_INTENSITY


def test_resolve_wake_ti_accepts_a_coastal_value() -> None:
    from analytics.wind.aep_summary_builder import _resolve_wake_ti

    assert _resolve_wake_ti({"turbulence_intensity": 0.08}) == pytest.approx(0.08)


@pytest.mark.parametrize("bad", [0.0, -0.05, 1.5, "0.08", True])
def test_resolve_wake_ti_rejects_out_of_range_or_nonnumeric(bad: object) -> None:
    # CESSPIT-strict: no silent clamp/coerce that would quietly move the modelled wake.
    from analytics.wind.aep_summary_builder import _resolve_wake_ti

    with pytest.raises(ValueError, match="turbulence_intensity"):
        _resolve_wake_ti({"turbulence_intensity": bad})


def test_wake_live_ti_default_matches_explicit_kernel_ti(cfg: dict) -> None:
    # The wired live path with NO TI must equal an explicit TI=0.10 -> byte-identical wiring.
    pytest.importorskip("py_wake")
    from analytics.power_curves.oem_parser import parse_power_curve
    from analytics.wind.aep_summary_builder import _resolve_wake_loss

    live_common = {
        "model_live": True,
        "rotor_diameter_m": 198.0,
        "coordinates": {"x_m": [0.0] * 15, "y_m": [i * 650.0 for i in range(15)]},
        "wind_rose_freq": [3, 3, 3, 4, 6, 9, 14, 20, 16, 9, 6, 4],
        "deficit_model": "bastankhah",
    }
    curve = parse_power_curve("iea_reference_10mw")

    cfg_default = copy.deepcopy(cfg)
    cfg_default["resource"]["wake"] = dict(live_common)
    pct_default, _ = _resolve_wake_loss(
        cfg_default["resource"],
        curve,
        weibull_a=8.199,
        weibull_k=2.665,
        hub_height_m=150.0,
    )

    cfg_explicit = copy.deepcopy(cfg)
    cfg_explicit["resource"]["wake"] = {**live_common, "turbulence_intensity": 0.10}
    pct_explicit, _ = _resolve_wake_loss(
        cfg_explicit["resource"],
        curve,
        weibull_a=8.199,
        weibull_k=2.665,
        hub_height_m=150.0,
    )
    assert pct_default == pytest.approx(pct_explicit, abs=1e-12)


def test_wake_live_lower_coastal_ti_moves_the_modelled_wake(cfg: dict) -> None:
    # Enabling a lower coastal TI DOES change the modelled wake (why it must be gated).
    pytest.importorskip("py_wake")
    from analytics.power_curves.oem_parser import parse_power_curve
    from analytics.wind.aep_summary_builder import _resolve_wake_loss

    live_common = {
        "model_live": True,
        "rotor_diameter_m": 198.0,
        "coordinates": {"x_m": [0.0] * 15, "y_m": [i * 650.0 for i in range(15)]},
        "wind_rose_freq": [3, 3, 3, 4, 6, 9, 14, 20, 16, 9, 6, 4],
        "deficit_model": "bastankhah",
    }
    curve = parse_power_curve("iea_reference_10mw")

    cfg_base = copy.deepcopy(cfg)
    cfg_base["resource"]["wake"] = {**live_common, "turbulence_intensity": 0.10}
    pct_base, _ = _resolve_wake_loss(
        cfg_base["resource"],
        curve,
        weibull_a=8.199,
        weibull_k=2.665,
        hub_height_m=150.0,
    )

    cfg_coastal = copy.deepcopy(cfg)
    cfg_coastal["resource"]["wake"] = {**live_common, "turbulence_intensity": 0.06}
    pct_coastal, _ = _resolve_wake_loss(
        cfg_coastal["resource"],
        curve,
        weibull_a=8.199,
        weibull_k=2.665,
        hub_height_m=150.0,
    )
    assert pct_coastal != pytest.approx(pct_base, abs=1e-6)


# ── #742: wind-rose + siting metadata surfacing (display-only, AEP-neutral) ────


def test_lendercase_omits_optional_rose_and_siting(cfg: dict) -> None:
    """The committed lender declares no wind_rose/siting -> provenance has only aep."""
    summary = build_aep_summary_from_config(cfg)
    assert sorted(summary["provenance"].keys()) == ["aep"]


def test_wind_rose_surfaces_into_provenance_aep_neutral(cfg: dict) -> None:
    """An optional wind rose is surfaced into provenance WITHOUT moving the AEP."""
    base = build_aep_summary_from_config(cfg)
    with_rose = copy.deepcopy(cfg)
    with_rose["resource"]["wind_rose"] = {
        "direction_deg": [225.0] * 100 + [230.0] * 20,  # SW-dominant
        "n_sectors": 12,
    }
    summary = build_aep_summary_from_config(with_rose)
    # display block present ...
    assert "wind_rose" in summary["provenance"]
    assert summary["provenance"]["wind_rose"]["prevailing_sector_deg"] == 240.0
    assert "single grid-cell" in summary["provenance"]["wind_rose"]["provenance_note"]
    # ... and the billed quantities are byte-identical to the no-rose run.
    assert summary["net_site_aep_gwh"] == base["net_site_aep_gwh"]
    assert summary["capacity_factor"] == base["capacity_factor"]
    assert summary["gross_aep_gwh"] == base["gross_aep_gwh"]
    assert summary["losses"] == base["losses"]


def test_prebinned_wind_rose_passthrough(cfg: dict) -> None:
    """A pre-binned rose (sector_deg + frequency) is renormalised and surfaced."""
    with_rose = copy.deepcopy(cfg)
    with_rose["resource"]["wind_rose"] = {
        "sector_deg": [0.0, 90.0, 180.0, 270.0],
        "frequency": [1.0, 1.0, 4.0, 2.0],  # unnormalised
    }
    summary = build_aep_summary_from_config(with_rose)
    rose = summary["provenance"]["wind_rose"]
    assert rose["source"] == "config_prebinned"
    assert rose["frequency"] == [0.125, 0.125, 0.5, 0.25]  # renormalised to sum 1


def test_siting_metadata_surfaces_and_applies_no_correction(cfg: dict) -> None:
    """A declared terrain class is surfaced but never scales the AEP."""
    base = build_aep_summary_from_config(cfg)
    with_siting = copy.deepcopy(cfg)
    with_siting["resource"]["siting"] = {"terrain_class": "coastal"}
    summary = build_aep_summary_from_config(with_siting)
    assert summary["provenance"]["siting"]["terrain_class"] == "coastal"
    assert summary["provenance"]["siting"]["applies_aep_correction"] is False
    assert summary["net_site_aep_gwh"] == base["net_site_aep_gwh"]
    assert summary["capacity_factor"] == base["capacity_factor"]


def test_incomplete_wind_rose_fails_loud(cfg: dict) -> None:
    from analytics.wind.aep_summary_builder import _resolve_wind_rose

    with pytest.raises(ValueError, match="incomplete"):
        _resolve_wind_rose({"wind_rose": {"n_sectors": 12}})


def test_regen_summary_is_loader_compatible(cfg: dict, tmp_path: Path) -> None:
    """The regenerated summary round-trips through the AEP loader."""
    out = write_aep_summary(cfg, str(tmp_path / "regen_summary.json"))
    assert out.exists()
    loaded = load_aep_from_summary(str(out), validate_manifest=True)
    assert loaded["net_site_aep_gwh"] == pytest.approx(464.3, abs=0.5)
    assert loaded["power_curve_key"] == "iea_reference_10mw"
    assert "aep" in loaded["provenance"]
