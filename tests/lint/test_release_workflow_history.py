"""Release-workflow guards for tests that compare historical Git objects."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_release_checkout_fetches_history_required_by_physical_receipt() -> None:
    """Keep the release gate able to archive its pinned comparison commit."""
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github/workflows/release-run.yml").read_text(encoding="utf-8")
    )
    steps = workflow["jobs"]["release"]["steps"]
    checkout_steps = [
        step
        for step in steps
        if str(step.get("uses", "")).startswith("actions/checkout@")
    ]

    assert len(checkout_steps) == 1
    assert checkout_steps[0].get("with", {}).get("fetch-depth") == 0

    receipt_source = (
        REPO_ROOT / "tests/grid/test_base_candidate_physical_receipt.py"
    ).read_text(encoding="utf-8")
    assert '["git", "archive", _BASE_SHA]' in receipt_source
