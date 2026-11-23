"""The committed PySAM energy cross-check stays current and within its tolerance (#1888).

``scripts/run_pysam_energy_crosscheck.py`` recomputes one committed wind scenario's gross,
modelled net and bankable net energy with NREL PySAM, outside the repository's
environment (PySAM is not a dependency), and ``docs/wind/pysam_energy_crosscheck_1888.json``
records the result. These tests need no PySAM. They fail when:

- any declared energy input the record was run on has changed (the scenario's resource,
  turbine, density, losses or haircut, or the power curve it keys into);
- the runner or its config has changed since the run;
- the committed AEP summary the record compares with has changed;
- the record's deltas do not follow from its own figures, or leave the tolerance;
- the control (no density shift) stops failing, so the comparison could no longer fail.

The last test re-runs PySAM and requires the record byte for byte when the pinned release
is importable, and is skipped otherwise.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "run_pysam_energy_crosscheck.py"
CONFIG = REPO_ROOT / "conf" / "pysam_energy_crosscheck_1888.yaml"
RECORD = REPO_ROOT / "docs" / "wind" / "pysam_energy_crosscheck_1888.json"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("pysam_crosscheck_1888", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script() -> ModuleType:
    return _load_script()


@pytest.fixture(scope="module")
def record() -> Dict[str, Any]:
    data: Dict[str, Any] = json.loads(RECORD.read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module")
def block() -> Dict[str, Any]:
    data: Dict[str, Any] = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return dict(data["crosscheck"])


def test_record_identity(record: Dict[str, Any], script: ModuleType) -> None:
    assert record["schema"] == script.SCHEMA
    assert record["work_item"] == "#1888"
    assert record["engine"]["distribution"] == "NREL-PySAM"


def test_declared_inputs_unchanged(
    record: Dict[str, Any], block: Dict[str, Any], script: ModuleType
) -> None:
    inputs = script.declared_inputs(block["scenario"], block["power_curve_store"])
    assert (
        inputs == record["inputs"]
    ), "a declared energy input changed: re-run the check"
    assert script.canonical_sha256(inputs) == record["inputs_sha256"]


def test_method_unchanged(record: Dict[str, Any], script: ModuleType) -> None:
    assert (
        script.method_digests() == record["method_sha256"]
    ), "the runner or its config changed since the record was produced: re-run the check"


def test_pinned_release_matches_config(
    record: Dict[str, Any], block: Dict[str, Any]
) -> None:
    assert record["engine"]["version"] == str(block["pysam"]["version"])
    assert record["tolerance_pct"] == float(block["tolerance_pct"])


def test_committed_figures_unchanged(
    record: Dict[str, Any], script: ModuleType
) -> None:
    committed = script.committed_figures(record["inputs"])
    assert committed == record["committed"], "the committed AEP summary changed"
    # The summary is built on the scenario's own turbine count and losses, so the two
    # runs compare like with like.
    assert committed["n_turbines"] == record["inputs"]["n_turbines"]
    assert committed["losses_pct"] == record["inputs"]["losses_pct"]


def test_deltas_follow_from_the_figures(record: Dict[str, Any]) -> None:
    for key, delta in record["delta_pct"].items():
        expected = round(
            (record["pysam"][key] / record["committed"][key] - 1.0) * 100.0, 4
        )
        assert delta == expected, key
    haircut = record["inputs"]["p50_haircut_pct"]
    assert record["pysam"]["net_bankable_gwh"] == pytest.approx(
        record["pysam"]["net_modelled_gwh"] * (1.0 - haircut / 100.0), abs=1e-4
    )


def test_within_tolerance(record: Dict[str, Any]) -> None:
    tolerance = record["tolerance_pct"]
    assert record["within_tolerance"] is True
    for key, delta in record["delta_pct"].items():
        assert abs(delta) <= tolerance, f"{key}: {delta}% is outside {tolerance}%"


def test_control_fails_the_tolerance(record: Dict[str, Any]) -> None:
    """Non-vacuity: without the density shift, the same comparison fails."""
    control = record["control"]
    expected = round(
        (control["gross_gwh"] / record["committed"]["gross_gwh"] - 1.0) * 100.0, 4
    )
    assert control["delta_pct"] == expected
    assert control["outside_tolerance"] is True
    assert abs(control["delta_pct"]) > record["tolerance_pct"]


def test_a_changed_input_shows_as_stale(
    tmp_path: Path, record: Dict[str, Any], block: Dict[str, Any], script: ModuleType
) -> None:
    """Hostile control: one changed resource input changes the inputs digest."""
    scenario_rel = block["scenario"]
    store_rel = block["power_curve_store"]
    for rel in (scenario_rel, store_rel):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / rel, tmp_path / rel)
    same = script.declared_inputs(scenario_rel, store_rel, root=tmp_path)
    assert script.canonical_sha256(same) == record["inputs_sha256"]
    scenario = yaml.safe_load((tmp_path / scenario_rel).read_text(encoding="utf-8"))
    scenario["wind_resource"]["weibull_a"] = (
        scenario["wind_resource"]["weibull_a"] + 0.01
    )
    (tmp_path / scenario_rel).write_text(yaml.safe_dump(scenario), encoding="utf-8")
    changed = script.declared_inputs(scenario_rel, store_rel, root=tmp_path)
    assert script.canonical_sha256(changed) != record["inputs_sha256"]


def test_unmapped_loss_is_refused(
    tmp_path: Path, block: Dict[str, Any], script: ModuleType
) -> None:
    scenario_rel = block["scenario"]
    store_rel = block["power_curve_store"]
    for rel in (scenario_rel, store_rel):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / rel, tmp_path / rel)
    scenario = yaml.safe_load((tmp_path / scenario_rel).read_text(encoding="utf-8"))
    scenario["resource"]["losses"]["icing_pct"] = 0.5
    (tmp_path / scenario_rel).write_text(yaml.safe_dump(scenario), encoding="utf-8")
    with pytest.raises(ValueError, match="unmapped"):
        script.declared_inputs(scenario_rel, store_rel, root=tmp_path)


def test_sam_grid_is_uniform_quarter_metre(
    record: Dict[str, Any], script: ModuleType
) -> None:
    """SAM's Weibull sum assumes 0.25 m/s bins; the resampled curve must use them."""
    ws, power = script.sam_power_curve(
        record["inputs"], record["engine"]["density_velocity_factor"]
    )
    steps = {round(b - a, 9) for a, b in zip(ws, ws[1:], strict=False)}
    assert steps == {script.SAM_WEIBULL_BIN_MS}
    assert ws[0] == 0.0 and power[0] == 0.0 and power[-1] == 0.0


def test_rerun_reproduces_the_record(
    record: Dict[str, Any], block: Dict[str, Any]
) -> None:
    pytest.importorskip("PySAM.Windpower")
    from importlib.metadata import version

    if version("NREL-PySAM") != str(block["pysam"]["version"]):
        pytest.skip("a different PySAM release is installed")
    script = _load_script()
    rerun = json.loads(json.dumps(script.run({"crosscheck": block})))
    expected = json.loads(json.dumps(record))
    for engine in (rerun["engine"], expected["engine"]):
        # The host the run happened on, not part of the result.
        engine.pop("python")
        engine.pop("machine")
    assert rerun == expected
