"""The wake-gap investigation (#1589): the summary is reproducible and the note quotes it.

``scripts/analyze_dutchbay_wake_deficit_gap_1589.py`` decomposes the gap between the frozen
wake value and the live PyWake loss on the #1577 re-baseline's own inputs and writes
``docs/wind/dutchbay_wake_gap_1589_summary.json``. These tests pin that summary to its
inputs, reproduce it from a fresh run, tie it to the lender-basis summary it investigates,
and check that every figure the write-up quotes is the summary's.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "analyze_dutchbay_wake_deficit_gap_1589.py"
SUMMARY = REPO_ROOT / "docs" / "wind" / "dutchbay_wake_gap_1589_summary.json"
BASIS = REPO_ROOT / "docs" / "wind" / "dutchbay_14_turbine_wake_summary.json"
NOTE = REPO_ROOT / "docs" / "wind" / "dutchbay_wake_loss_gap_investigation_1589.md"
CONF_DIR = REPO_ROOT / "conf"


def _summary() -> Dict[str, Any]:
    data: Dict[str, Any] = json.loads(SUMMARY.read_text(encoding="utf-8"))
    return data


def _cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location("wake_gap_1589", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_summary_pins_the_committed_inputs() -> None:
    pins = _summary()["inputs_sha256"]
    conf = yaml.safe_load((CONF_DIR / "dutchbay_wake_gap_1589.yaml").read_text())
    assert set(pins) == set(conf["wake_gap"]["pinned_inputs"])
    for rel, digest in pins.items():
        assert (
            hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest() == digest
        ), f"{rel} changed: regenerate {SUMMARY.relative_to(REPO_ROOT)}"


def test_a_fresh_run_reproduces_the_summary() -> None:
    pytest.importorskip("py_wake")
    pytest.importorskip("pyproj")
    from hydra import compose, initialize_config_dir
    from omegaconf import OmegaConf

    with initialize_config_dir(version_base="1.3", config_dir=str(CONF_DIR)):
        cfg = compose(config_name="dutchbay_wake_gap_1589")
    raw = OmegaConf.to_container(cfg, resolve=True)
    assert isinstance(raw, dict)
    fresh = json.loads(json.dumps(_cli().run(raw), sort_keys=True))
    assert fresh == _summary()


def test_it_investigates_the_lender_basis_without_changing_it() -> None:
    gap, basis = _summary(), json.loads(BASIS.read_text(encoding="utf-8"))
    assert gap["frozen_wake_15_pct"] == basis["frozen_wake_15_pct"]
    assert gap["basis_wake_14_pct"] == basis["wake_loss_14_pct"]
    per_turbine = basis["per_turbine_sensitivity"]
    assert (
        gap["live"]["recorded_layout_counted_t2_waking_pct"]
        == per_turbine["live_farm_wake_loss_pct"]
    )
    # The per-turbine figures are #1786's own.
    assert gap["per_turbine_live_pct"] == {
        t["id"]: t["live_wake_loss_pct"]
        for t in per_turbine["turbines"]
        if t["counted"]
    }
    assert gap["live"]["synthetic_row_all_turbines_pct"] == round(
        basis["synthetic_row"]["all_15"]["wake_loss_pct"], 2
    )


def test_the_attribution_adds_up() -> None:
    a = _summary()["attribution_pp"]
    assert a["frozen_to_live_synthetic_row"] + a["layout_under_site_rose"] == (
        pytest.approx(a["total_frozen_to_live_recorded"], abs=0.011)
    )
    # Layout carries almost all of the gap.
    assert a["layout_under_site_rose"] > 0.9 * a["total_frozen_to_live_recorded"]


def test_every_exceedance_level_moves_by_the_same_factor() -> None:
    b = _summary()["bankable_sensitivity"]
    changes = set(b["relative_change_pct"].values())
    assert len(changes) == 1
    expected = (b["net_energy_factor"] - 1.0) * 100.0
    assert changes.pop() == pytest.approx(expected, abs=0.006)


def _pct(value: float) -> str:
    return f"{value:.2f}%"


def test_the_note_quotes_the_summary() -> None:
    s, note = _summary(), NOTE.read_text(encoding="utf-8")
    a, live = s["attribution_pp"], s["live"]
    sweep = {r["rotor_diameter_m"]: r for r in s["rotor_diameter_sweep"]}
    ti = {r["turbulence_intensity"]: r for r in s["turbulence_intensity_sweep"]}
    models = {r["deficit_model"]: r for r in s["deficit_model_sweep"]}
    spacing = s["spacing"]
    rng = s["per_turbine_live_range"]
    quoted = [
        _pct(s["frozen_wake_15_pct"]),
        _pct(s["basis_wake_14_pct"]),
        *(_pct(v) for v in live.values()),
        *(
            f"+{a[k]:.2f} pp"
            for k in (
                "frozen_to_live_synthetic_row",
                "layout_under_site_rose",
                "total_frozen_to_live_recorded",
            )
        ),
        *(
            f"{a[k]:.2f} pp"
            for k in (
                "layout_under_uniform_rose",
                "site_rose_on_recorded_layout",
                "site_rose_on_synthetic_row",
            )
        ),
        f"{spacing['synthetic_row_spacing_rotor_diameters']:.2f} rotor diameters",
        f"{spacing['counted_nearest_neighbour_rotor_diameters_min']:.2f} D to "
        f"{spacing['counted_nearest_neighbour_rotor_diameters_max']:.2f} D",
        *(
            f"| {d:.0f} m{' (configured)' if d == spacing['rotor_diameter_m'] else ''} | "
            f"{r['counted_nearest_neighbour_min_rotor_diameters']:.2f} D | "
            f"{_pct(r['all_turbines_pct'])} | {_pct(r['counted_t2_waking_pct'])} |"
            for d, r in sweep.items()
        ),
        f"from {_pct(ti[0.06]['all_turbines_pct'])} down to "
        f"{_pct(ti[0.14]['all_turbines_pct'])}",
        f"TurbOPark deficit gives {_pct(models['turbopark']['all_turbines_pct'])}",
        _pct(models["turbopark"]["counted_t2_waking_pct"]),
        f"{_pct(rng['lowest']['pct'])} at {rng['lowest']['id']}",
        f"{_pct(rng['highest']['pct'])} at {rng['highest']['id']}",
        f"= {s['bankable_sensitivity']['net_energy_factor']:.4f}",
        *(
            f"−{-v:.2f}%"
            for v in s["bankable_sensitivity"]["relative_change_pct"].values()
        ),
    ]
    missing = [q for q in quoted if q not in note]
    assert not missing, missing


def test_the_note_names_no_source_document() -> None:
    for path in (NOTE, CONF_DIR / "dutchbay_wake_gap_1589.yaml", SCRIPT):
        assert ".pdf" not in path.read_text(encoding="utf-8").lower(), path
