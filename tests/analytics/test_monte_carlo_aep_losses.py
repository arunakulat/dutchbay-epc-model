"""Regression: MC-AEP must apply the full loss stack, and the mock must agree.

Two confirmed wind/AEP defects:
  * The v14 ``monte_carlo_aep`` applied only wake/availability/electrical via
    ``compute_aep_from_curve`` and dropped curtailment + other, under-counting
    losses by ~3% and overstating AEP.
  * The frozen AEP mock used ``environmental_pct`` while the canonical
    ``losses_model`` reads ``other_pct``, so the mock could not reproduce its
    own declared net AEP through the model.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from analytics.simulation.monte_carlo_aep import run_monte_carlo_aep
from analytics.wind.losses_model import apply_losses

REPO_ROOT = Path(__file__).resolve().parents[2]
AEP_MOCK = REPO_ROOT / "tests" / "mocks" / "aep_summary_dutchbay.json"


def test_frozen_mock_roundtrips_through_canonical_losses_model() -> None:
    """The mock's own loss block must reproduce its declared net via losses_model."""
    mock = json.loads(AEP_MOCK.read_text(encoding="utf-8"))
    result = apply_losses(mock["gross_aep_gwh"], mock["losses"])
    assert abs(result.net_aep_gwh - mock["net_site_aep_gwh"]) < 1.0
    assert abs(result.total_loss_pct - mock["losses"]["total_loss_pct"]) < 0.1
    # The canonical key must be present (the bug was environmental_pct).
    assert "other_pct" in mock["losses"]
    assert "environmental_pct" not in mock["losses"]


def test_mc_aep_applies_curtailment_and_other(tmp_path: Path) -> None:
    """Differential: zeroing curtailment+other raises AEP by exactly their retention.

    Same seed → identical Weibull/wake/avail/electrical samples, so the only
    difference between the two runs is the fixed curtailment+other retention.
    """
    mock = json.loads(AEP_MOCK.read_text(encoding="utf-8"))
    curt = mock["losses"]["curtailment_pct"]
    other = mock["losses"]["other_pct"]
    expected_retention = (1.0 - curt / 100.0) * (1.0 - other / 100.0)
    assert expected_retention < 1.0  # the mock genuinely has these components

    # A twin summary with curtailment + other removed.
    zeroed = copy.deepcopy(mock)
    zeroed["losses"]["curtailment_pct"] = 0.0
    zeroed["losses"]["other_pct"] = 0.0
    zeroed_path = tmp_path / "aep_summary_no_curt_other.json"
    zeroed_path.write_text(json.dumps(zeroed), encoding="utf-8")

    full = run_monte_carlo_aep(
        aep_summary_path=str(AEP_MOCK), n_scenarios=200, seed=42, export_scenarios=False
    )
    without = run_monte_carlo_aep(
        aep_summary_path=str(zeroed_path), n_scenarios=200, seed=42, export_scenarios=False
    )

    ratio = full["percentiles"]["p50"] / without["percentiles"]["p50"]
    assert abs(ratio - expected_retention) < 1e-6, (
        f"MC-AEP did not apply curtailment+other: ratio {ratio:.6f} != "
        f"{expected_retention:.6f}"
    )
