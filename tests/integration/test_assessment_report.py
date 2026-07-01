#!/usr/bin/env python
"""Gated smoke test for the solar PV assessment-report generator.

scripts/generate_solar_assessment_report.py is the end-of-pipeline reporting stage. It
depends on optional extras (reportlab/pvlib/rasterio), so this test is skipped unless
they are installed — exactly like the [wind]/[report]/[solar] suites. It exercises the
analytical chain (a short Monte Carlo) without rendering the full PDF or fetching the map.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("reportlab")
pytest.importorskip("pvlib")
pytest.importorskip("rasterio")

_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "generate_solar_assessment_report.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("gen_solar_report", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_site_config_is_sane() -> None:
    m = _load_module()
    assert m.SITE["location_name"] == "Sri Jayewardenepura Kotte"
    # USc 8.0 fixed at signing FX 333.79 -> LKR 26.70 (the 5usc-style convention)
    assert m.SITE["competitive_tariff_lkr"] == round(8.0 / 100.0 * 333.79, 2)


def test_routines_run_and_produce_sane_results(tmp_path: Path) -> None:
    m = _load_module()
    m._OUT_PATH = tmp_path  # scenario YAMLs for the path-based routines land here
    R = m.run_routines(trials=20)

    assert {
        "resource",
        "case_fit",
        "case_competitive",
        "mc",
        "sensitivity",
        "optimization",
        "dscr",
    } <= set(R)

    # Wet-zone site at the competitive tariff: a marginal unlevered return, now slightly
    # negative after the 5.9% FX-drift re-baseline (~-1.5%; was low-but-positive at 3%);
    # the FiT case is deeper underwater still.
    assert -0.03 < R["case_competitive"]["project_irr"] < 0.02
    assert R["case_fit"]["project_irr"] < 0.0

    # The Monte Carlo actually ran (no toy fallbacks).
    assert R["mc"]["n"] == 20 and R["mc"]["failed"] == 0

    # Sensitivity surfaced the standard driver set (resource/tariff dominate).
    labels = {d["param"] for d in R["sensitivity"]}
    assert {"Capacity Factor", "Tariff", "CAPEX"} <= labels

    # The key DSCR finding: the unlevered project IRR is INVARIANT to the DSCR target.
    proj_irrs = {round(d["projIRR"], 5) for d in R["dscr"]["sweep"]}
    assert len(proj_irrs) == 1, f"project IRR should be DSCR-invariant, got {proj_irrs}"
