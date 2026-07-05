"""#683 (a): CLI-overridable wind-resource knobs (resource_overrides).

The IEC 61400-15-2 uncertainty budget / P50 haircut and the air-density corrections
are already drivable in the scenario YAML; this exposes them as a Hydra CLI override
(`resource_overrides`) deep-merged onto the scenario's `resource` block. Unset is a
no-op (byte-identical); the original scenario on disk is never mutated.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

import run_full_pipeline_v14 as rfp

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def test_deep_merge_overrides_win_and_siblings_survive() -> None:
    base: dict[str, Any] = {
        "uncertainty": {"p50_haircut_pct": 0.02, "correlation": 0.5},
        "wind": {"air_density_site_kgm3": 1.15, "aep_gwh": 480.0},
    }
    rfp._deep_merge_into(
        base,
        {
            "uncertainty": {"p50_haircut_pct": 0.03},
            "wind": {"air_density_site_kgm3": 1.12},
        },
    )
    assert base["uncertainty"]["p50_haircut_pct"] == 0.03  # overridden
    assert base["uncertainty"]["correlation"] == 0.5  # sibling preserved
    assert base["wind"]["air_density_site_kgm3"] == 1.12  # overridden
    assert base["wind"]["aep_gwh"] == 480.0  # sibling preserved


def test_deep_merge_scalar_and_list_replace_not_merge() -> None:
    base: dict[str, Any] = {"a": {"b": 1}, "keys": [1, 2, 3]}
    rfp._deep_merge_into(base, {"a": 9, "keys": [4]})
    assert base["a"] == 9  # a mapping replaced by a scalar wholesale
    assert base["keys"] == [4]  # lists replace, never element-merge


def test_apply_resource_overrides_patches_temp_and_never_mutates_original() -> None:
    before = yaml.safe_load(Path(LENDER).read_text())
    patched_path = rfp._apply_resource_overrides_to_scenario(
        LENDER, {"uncertainty": {"p50_haircut_pct": 0.09}}
    )
    try:
        patched = yaml.safe_load(Path(patched_path).read_text())
        assert patched["resource"]["uncertainty"]["p50_haircut_pct"] == 0.09
        # sibling uncertainty keys survive the overlay
        for k, v in before["resource"]["uncertainty"].items():
            if k != "p50_haircut_pct":
                assert patched["resource"]["uncertainty"][k] == v
    finally:
        os.unlink(patched_path)
    # The committed scenario on disk is unchanged.
    after = yaml.safe_load(Path(LENDER).read_text())
    assert after == before


def test_apply_resource_overrides_creates_resource_block_when_absent() -> None:
    """A scenario with no `resource` block still accepts overrides (block created)."""
    import tempfile

    scen = {"capex": {"usd_total": 100.0}, "fx": {"start_lkr_per_usd": 300.0}}
    with tempfile.NamedTemporaryFile(
        "w", suffix=".yaml", dir=str(REPO_ROOT / "scenarios"), delete=False
    ) as f:
        yaml.safe_dump(scen, f)
        scen_path = f.name
    try:
        patched_path = rfp._apply_resource_overrides_to_scenario(
            scen_path, {"uncertainty": {"p50_haircut_pct": 0.05}}
        )
        try:
            patched = yaml.safe_load(Path(patched_path).read_text())
            assert patched["resource"]["uncertainty"]["p50_haircut_pct"] == 0.05
            assert patched["capex"]["usd_total"] == 100.0  # untouched
        finally:
            os.unlink(patched_path)
    finally:
        os.unlink(scen_path)
