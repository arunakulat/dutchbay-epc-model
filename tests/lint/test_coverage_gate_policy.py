"""Govern the sharded coverage gate's completeness contract (R8/TEST-02, #1121 follow-up).

The 95% floor is enforced downstream of a 6-way pytest-split matrix, so the gate's answer
is only meaningful when it combined EVERY shard's coverage data. Cancellation is routine —
the workflow's ``concurrency`` group cancels in-flight PR runs on a newer push — and a
cancelled shard still runs its ``always()`` upload step, so the download succeeds while
carrying a partial set. Combining that subset yields a real percentage over an incomplete
tree, which the floor then reports as a coverage regression (observed on run 33960436162,
PR #1233: three of six shards, ``TOTAL 89.72%``, floor breach).

That is the #1121 misattribution — naming a cause for a non-success result that was really
a cancellation — in the one form it left behind, so these tests pin the fix: the gate
counts its input before enforcing, blocks with the right diagnosis when the count is short,
and publishes ``enforced`` so ``Test Summary`` can tell a real breach from a gate that
never measured anything. They also pin the single-source-of-truth relationship between
``TOTAL_SHARDS`` and the literal ``shard:`` matrix list, which GitHub will not let the
workflow express directly (the ``env`` context is unavailable to ``strategy``).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "test-suite.yml"


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _workflow() -> dict[str, Any]:
    # NB: PyYAML parses the bare `on:` key as the boolean True (YAML 1.1). Harmless here —
    # nothing below reads it — but it is why this helper never indexes the trigger block.
    loaded: dict[str, Any] = yaml.safe_load(_workflow_text())
    return loaded


def _command_line_index(script: str, command: str) -> int:
    """Line number of the executable line starting with ``command``, ignoring comments.

    The step's prose names `coverage combine` and `--fail-under` while explaining them, so
    a plain ``str.index`` finds the commentary rather than the command and makes an
    ordering assertion silently meaningless.
    """
    for number, line in enumerate(script.splitlines()):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.startswith(command):
            return number
    raise AssertionError(f"no executable line starting with {command!r}")


def _coverage_floor_step() -> dict[str, Any]:
    steps: list[dict[str, Any]] = _workflow()["jobs"]["coverage"]["steps"]
    matches = [step for step in steps if step.get("id") == "floor"]
    assert len(matches) == 1, "expected exactly one id: floor step in the coverage job"
    return matches[0]


def test_total_shards_is_defined_once_at_workflow_level() -> None:
    """The shard count is shared by the `test` and `coverage` jobs — one definition only."""
    workflow = _workflow()

    assert workflow["env"]["TOTAL_SHARDS"] == 6

    # A job-level redefinition would shadow the workflow-level value for that job only,
    # which is precisely the drift this pins against.
    for job_name, job in workflow["jobs"].items():
        assert "TOTAL_SHARDS" not in (job.get("env") or {}), (
            f"job {job_name!r} redefines TOTAL_SHARDS; it must inherit the "
            "workflow-level value so the matrix and the coverage gate cannot drift"
        )


def test_shard_matrix_list_matches_total_shards() -> None:
    """GitHub forbids `env` in `strategy`, so the literal list is held here instead."""
    workflow = _workflow()
    total = workflow["env"]["TOTAL_SHARDS"]

    shards = workflow["jobs"]["test"]["strategy"]["matrix"]["shard"]

    assert shards == list(range(1, total + 1)), (
        f"shard matrix {shards} does not enumerate 1..{total}; TOTAL_SHARDS is the single "
        "source of truth and the coverage gate counts artifacts against it"
    )


def test_coverage_gate_counts_shards_before_enforcing_the_floor() -> None:
    """Completeness is checked BEFORE the floor, and a short count blocks."""
    run = _coverage_floor_step()["run"]

    # The count is taken from the shard data files actually on disk, against TOTAL_SHARDS.
    assert "present=$(ls -1 .coverage.${{ matrix.python-version }}.*" in run
    assert 'if [ "$present" -ne "$TOTAL_SHARDS" ]; then' in run

    # The diagnosis names the real cause and refuses to call it a coverage regression.
    assert (
        "::error::coverage not enforced: $present of $TOTAL_SHARDS shard artifacts "
        "present; shards were cancelled or did not complete, so this number is not a "
        "coverage measurement." in run
    )
    assert "This is NOT a coverage regression" in run

    # Missing shards must BLOCK — never silently pass.
    short_count_branch = run.split('if [ "$present" -ne "$TOTAL_SHARDS" ]; then', 1)[1]
    short_count_branch = short_count_branch.split("fi", 1)[0]
    assert "exit 1" in short_count_branch

    # Ordering: the guard precedes both the combine and the floor, so an incomplete set
    # can never reach `--fail-under` and print a percentage. Anchored to real command
    # lines — the prose above them mentions `coverage combine` too.
    assert _command_line_index(run, 'if [ "$present" -ne "$TOTAL_SHARDS" ]; then') < (
        _command_line_index(run, "coverage combine")
    )
    assert _command_line_index(run, "coverage combine") < _command_line_index(
        run, "coverage report --fail-under=95"
    )


def test_coverage_floor_is_unchanged_at_95_and_unconditional() -> None:
    """The fix is accurate diagnosis, not a weaker gate."""
    run = _coverage_floor_step()["run"]

    assert "coverage report --fail-under=95" in run
    # Exactly one floor, at exactly 95 — no second, lower `--fail-under` anywhere.
    assert re.findall(r"--fail-under=(\d+)", run) == ["95"]
    # The floor is never wrapped in a condition that could skip it.
    assert not re.search(r"^\s*if\b.*\n\s*coverage report --fail-under=95", run, re.M)


def test_enforced_output_marks_a_complete_union_not_a_passing_floor() -> None:
    """`enforced` must be set BEFORE the floor runs, or a real breach reads as 'cancelled'."""
    workflow = _workflow()
    run = _coverage_floor_step()["run"]

    assert (
        workflow["jobs"]["coverage"]["outputs"]["enforced"]
        == "${{ steps.floor.outputs.enforced }}"
    )

    # Default is false; it flips to true only after the completeness check passes...
    assert _command_line_index(run, 'echo "enforced=false" >> "$GITHUB_OUTPUT"') < (
        _command_line_index(run, 'if [ "$present" -ne "$TOTAL_SHARDS" ]; then')
    )
    # ...and BEFORE the floor, because the default `bash -e` shell aborts on a breach.
    assert _command_line_index(run, 'echo "enforced=true" >> "$GITHUB_OUTPUT"') < (
        _command_line_index(run, "coverage report --fail-under=95")
    )


def test_test_summary_distinguishes_a_breach_from_an_unmeasured_gate() -> None:
    """The summary's coverage line reads `enforced`, consistent with the #1121 gate()."""
    summary = _workflow_text().split("  summary:\n", maxsplit=1)[1]
    summary = summary.split("  # TEST-03 scale lane", maxsplit=1)[0]

    assert 'if [ "${{ needs.coverage.outputs.enforced }}" = "true" ]; then' in summary
    assert (
        'coverage_cause="combined coverage fell below the 95% R8/TEST-02 floor"'
        in summary
    )
    assert "the gate never applied the floor to a complete tree" in summary
    assert "NOT evidence of a coverage regression" in summary

    # Still routed through the #1121 helper, so blocking behaviour is unchanged.
    assert 'gate "Coverage" "${{ needs.coverage.result }}" "$coverage_cause"' in summary


@pytest.mark.parametrize(
    ("present", "total", "blocks"),
    [
        (6, 6, False),  # every shard reported — the floor is enforced as before
        (3, 6, True),  # the observed PR #1233 case — three shards cancelled
        (0, 6, True),  # nothing downloaded at all
        (5, 6, True),  # a single missing shard is still not a measurement
    ],
)
def test_shard_completeness_predicate_negative_control(
    present: int, total: int, blocks: bool
) -> None:
    """Negative control (VERIFY-01): demonstrate the guard's condition actually fires.

    Mirrors the workflow's `[ "$present" -ne "$TOTAL_SHARDS" ]` test so the pinned
    behaviour is exercised, not merely asserted to exist as a string.
    """
    assert (present != total) is blocks
