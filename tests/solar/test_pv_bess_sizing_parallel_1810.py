"""Parity and validation tests for CPU worker pool parallelization (#1810)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from solar_resource import pv_bess_sizing_runner as runner
from solar_resource.pv_bess_sizing import _validate_n_workers

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_CONF = REPO_ROOT / "conf" / "blue_whale_solar_bess_project_sizing.yaml"
UNIT_CONF = REPO_ROOT / "conf" / "blue_whale_solar_bess.yaml"
PRICING_CONF = REPO_ROOT / "conf" / "blue_whale_pv_bess_pricing.yaml"
REG_CONF = REPO_ROOT / "conf" / "blue_whale_pucsl_fit_2026.yaml"
SCENARIO = REPO_ROOT / "scenarios" / "blue_whale_solar_bess_lot5b_2026.yaml"


def _reduced_project_cfg() -> Dict[str, Any]:
    raw = yaml.safe_load(PROJECT_CONF.read_text(encoding="utf-8"))
    cfg = {k: v for k, v in raw.items() if k not in ("defaults", "hydra")}
    cfg["grid"]["pv_tables"] = [107, 120]
    cfg["grid"]["pv_ac_mw"] = [3.5]
    cfg["grid"]["bess_power_mw"] = [0.1]
    cfg["monte_carlo"]["n_trials"] = 2
    cfg["sensitivities"]["one_at_a_time"] = []
    cfg["sensitivities"]["break_even"] = []
    cfg["output"]["summary_json"] = None
    return cfg


@pytest.mark.parametrize("bad_workers", [0, -1, True, False, "2"])
def test_invalid_n_workers_raises(bad_workers: Any) -> None:
    with pytest.raises(ValueError, match="n_workers must be a positive integer"):
        _validate_n_workers(bad_workers)


def test_parallel_project_sizing_is_bit_identical_to_serial() -> None:
    """Two-worker ProcessPoolExecutor matches serial execution bit-for-bit."""
    serial_cfg = _reduced_project_cfg()
    parallel_cfg = _reduced_project_cfg()
    parallel_cfg["n_workers"] = 2

    limitations = ("Test limitation.",)
    serial = runner.run(
        serial_cfg,
        config_label="conf/blue_whale_solar_bess_project_sizing.yaml",
        script=REPO_ROOT / "scripts" / "run_blue_whale_pv_bess_sizing_v14.py",
        limitations=limitations,
    )
    parallel = runner.run(
        parallel_cfg,
        config_label="conf/blue_whale_solar_bess_project_sizing.yaml",
        script=REPO_ROOT / "scripts" / "run_blue_whale_pv_bess_sizing_v14.py",
        limitations=limitations,
    )

    assert parallel["points"] == serial["points"]
    assert parallel["recommendation"] == serial["recommendation"]
    assert parallel["sensitivities"] == serial["sensitivities"]
    assert parallel["spec"]["result_sha256"] == serial["spec"]["result_sha256"]
    assert (
        parallel["spec"]["sizing_config_sha256"]
        == serial["spec"]["sizing_config_sha256"]
    )
    assert (
        parallel["spec"]["effective_evaluations"]
        == serial["spec"]["effective_evaluations"]
    )
