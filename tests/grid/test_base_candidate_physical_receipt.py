"""Persist a paired physical receipt for the base and candidate ride-through paths."""

from __future__ import annotations

import io
import json
import math
import os
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from analytics.contracts_v14 import RideThroughResult
from analytics.grid import ride_through

pytestmark = [
    pytest.mark.grid,
    pytest.mark.filterwarnings(
        "error:This process .* is multi-threaded.*:DeprecationWarning"
    ),
]

_BASE_SHA = "4da2a82352d532138ee7f2483b82dfbf5a1d9c2b"
_RECEIPT_PATH = Path("outputs/grid_base_candidate_numerical_receipt.json")
_CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "lvrt_mild",
        "kind": "lvrt",
        "kwargs": {
            "lvrt_fault_x_pu": 0.30,
            "fault_start_s": 1.0,
            "fault_clear_s": 1.08,
        },
    },
    {
        "id": "lvrt_severe",
        "kind": "lvrt",
        "kwargs": {
            "lvrt_fault_x_pu": 0.001,
            "fault_start_s": 1.0,
            "fault_clear_s": 1.9,
            "tf": 3.0,
        },
    },
    {"id": "hvrt_default", "kind": "hvrt", "kwargs": {}},
    {
        "id": "hvrt_severe",
        "kind": "hvrt",
        "kwargs": {"envelope_kind": "hvrt_severe"},
    },
    {"id": "frequency_default", "kind": "frequency", "kwargs": {}},
    {
        "id": "frequency_severe",
        "kind": "frequency",
        "kwargs": {"envelope_kind": "frequency_severe"},
    },
)
_FLOAT_FIELDS = (
    "target_pu",
    "target_hz",
    "k_factor",
    "min_voltage_pu",
    "max_voltage_pu",
    "freq_extreme_hz",
)
_EXACT_FIELDS = (
    "case",
    "ran",
    "converged",
    "rode_through",
    "n_devices",
)


def _apply_envelope(ride_module: Any, case: dict[str, Any]) -> dict[str, Any]:
    """Turn a serializable case description into ride-through call arguments."""
    kwargs = dict(case["kwargs"])
    envelope_kind = kwargs.pop("envelope_kind", None)
    if envelope_kind == "hvrt_severe":
        envelope = ride_module.envelope_from_fixture()
        kwargs["envelope"] = replace(
            envelope,
            hvrt_enter_pu=1.001,
            ov_trip_pu=1.002,
        )
    elif envelope_kind == "frequency_severe":
        envelope = ride_module.envelope_from_fixture()
        kwargs["envelope"] = replace(
            envelope,
            freq_continuous_hz=(49.99, 50.01),
            freq_trip_hz=(49.98, 50.02),
        )
    return kwargs


def _record(case: dict[str, Any], result: RideThroughResult) -> dict[str, Any]:
    """Select the physical and solver fields that form the paired receipt."""
    return {
        "id": case["id"],
        "inputs": case,
        "result": {
            field: getattr(result, field) for field in (*_EXACT_FIELDS, *_FLOAT_FIELDS)
        },
    }


_BASE_RUNNER = r"""
import json
import sys
from dataclasses import replace

from analytics.contracts_v14 import RideThroughResult
from analytics.grid import ride_through

case = json.loads(sys.argv[1])
kwargs = dict(case["kwargs"])
envelope_kind = kwargs.pop("envelope_kind", None)
if envelope_kind == "hvrt_severe":
    envelope = ride_through.envelope_from_fixture()
    kwargs["envelope"] = replace(envelope, hvrt_enter_pu=1.001, ov_trip_pu=1.002)
elif envelope_kind == "frequency_severe":
    envelope = ride_through.envelope_from_fixture()
    kwargs["envelope"] = replace(
        envelope,
        freq_continuous_hz=(49.99, 50.01),
        freq_trip_hz=(49.98, 50.02),
    )
result = ride_through.run_ride_through_case(
    case["kind"], run_dynamics=True, **kwargs
)
assert isinstance(result, RideThroughResult)
fields = (
    "case", "ran", "converged", "rode_through", "n_devices",
    "target_pu", "target_hz", "k_factor", "min_voltage_pu",
    "max_voltage_pu", "freq_extreme_hz",
)
print(json.dumps({"id": case["id"], "inputs": case, "result": {
    field: getattr(result, field) for field in fields
}}))
"""


def _run_base_case(repo: Path, case: dict[str, Any]) -> dict[str, Any]:
    """Run one base case in an isolated interpreter and return its JSON result."""
    archive = subprocess.check_output(["git", "archive", _BASE_SHA], cwd=repo)
    with tempfile.TemporaryDirectory(prefix="dutchbay-base-case-") as base_dir_text:
        base_dir = Path(base_dir_text)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as archive_file:
            archive_file.extractall(base_dir, filter="data")
        with tempfile.TemporaryDirectory(prefix="dutchbay-base-home-") as home_text:
            environment = os.environ.copy()
            environment.update(
                {
                    "HOME": home_text,
                    "PYTHONPATH": str(base_dir),
                    "PYTHONDONTWRITEBYTECODE": "1",
                }
            )
            completed = subprocess.run(
                [sys.executable, "-c", _BASE_RUNNER, json.dumps(case)],
                cwd=base_dir,
                env=environment,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        if completed.returncode != 0:
            detail = completed.stderr.strip().splitlines()[-1:]
            pytest.fail(
                f"base case {case['id']} failed with exit {completed.returncode}: {detail}"
            )
        try:
            return json.loads(completed.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            pytest.fail(f"base case {case['id']} did not emit JSON: {exc}")
    raise AssertionError("unreachable")


def _assert_equivalent(
    base: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    """Require paired result fields to match and return numeric deltas."""
    base_result = base["result"]
    candidate_result = candidate["result"]
    for field in _EXACT_FIELDS:
        assert candidate_result[field] == base_result[field], (
            f"{candidate['id']} changed {field}: "
            f"base={base_result[field]!r} candidate={candidate_result[field]!r}"
        )
    deltas: dict[str, float | None] = {}
    for field in _FLOAT_FIELDS:
        before = base_result[field]
        after = candidate_result[field]
        if before is None or after is None:
            if before is not after:
                raise AssertionError(
                    f"{candidate['id']} changed {field}: "
                    f"base={before!r} candidate={after!r}"
                )
            deltas[field] = None
            continue
        if not math.isclose(after, before, rel_tol=1e-9, abs_tol=1e-12):
            raise AssertionError(
                f"{candidate['id']} changed {field}: "
                f"base={before!r} candidate={after!r}"
            )
        deltas[field] = after - before
    return deltas


def test_base_candidate_physical_numerical_receipt() -> None:
    """Compare identical physical cases and persist the current exact-head receipt."""
    pytest.importorskip("andes")
    repo = Path.cwd()
    candidate_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    paired: list[dict[str, Any]] = []
    for case in _CASES:
        candidate_result = ride_through.run_ride_through_case(
            case["kind"], run_dynamics=True, **_apply_envelope(ride_through, case)
        )
        candidate_record = _record(case, candidate_result)
        base_record = _run_base_case(repo, case)
        paired.append(
            {
                "id": case["id"],
                "base": base_record,
                "candidate": candidate_record,
                "numeric_deltas": _assert_equivalent(base_record, candidate_record),
            }
        )
    receipt = {
        "schema": "dutchbay.ci_fork.base_candidate_physical_receipt.v1",
        "base_commit": _BASE_SHA,
        "candidate_commit": candidate_sha,
        "case_count": len(paired),
        "comparison": "identical case/disturbance inputs; exact booleans/counts and 1e-9 relative numeric tolerance",
        "cases": paired,
    }
    _RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _RECEIPT_PATH.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
