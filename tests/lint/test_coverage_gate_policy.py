"""Execute the workflow coverage and summary guards against controlled inputs.

Missing shard data must fail before coverage is computed. Complete data must still
meet the 95% floor. Extracting the real YAML scripts makes guard mutations observable.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "test-suite.yml"

#: The single matrix leg the coverage gate runs on. Pinned by
#: :func:`test_coverage_gate_matrix_is_single_legged` — the `enforced` output is a job
#: output, and matrix legs overwrite each other's job outputs.
PYTHON_VERSION = "3.12"


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _workflow() -> dict[str, Any]:
    # NB: PyYAML parses the bare `on:` key as the boolean True (YAML 1.1). Harmless here —
    # nothing below reads it — but it is why this helper never indexes the trigger block.
    loaded: dict[str, Any] = yaml.safe_load(_workflow_text())
    return loaded


def _step_run(job: str, step_id_or_name: str) -> str:
    """The `run:` script of one step, located through the PARSED workflow.

    Text slicing on comment lines was how the previous draft found the summary job, which
    meant rewording a comment silently widened the slice and weakened every assertion
    after it without failing anything. Going through the YAML removes that whole class.
    """
    steps: list[dict[str, Any]] = _workflow()["jobs"][job]["steps"]
    matches = [
        step
        for step in steps
        if step.get("id") == step_id_or_name or step.get("name") == step_id_or_name
    ]
    assert len(matches) == 1, (
        f"expected exactly one step {step_id_or_name!r} in job {job!r}, "
        f"found {len(matches)}"
    )
    run: str = matches[0]["run"]
    return run


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


# ---------------------------------------------------------------------------
# Single source of truth: TOTAL_SHARDS vs the literal matrix list
# ---------------------------------------------------------------------------


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


def test_coverage_gate_matrix_is_single_legged() -> None:
    """`enforced` is a JOB output, and matrix legs overwrite each other's job outputs.

    With two Python legs, one leg short-counting while the other enforced would publish
    whichever finished last, and `Test Summary` would read a value that did not describe
    the failing leg. The workflow comments warn about this; this pins it.
    """
    raw = _workflow()["jobs"]["coverage"]["strategy"]["matrix"]["python-version"]

    versions = re.findall(r'"([^"]+)"', raw) if isinstance(raw, str) else list(raw)

    assert versions == [PYTHON_VERSION], (
        f"coverage gate matrix is {versions}; restoring a second leg breaks the "
        "`enforced` job output (last leg to finish wins) — see the job's own comment"
    )


# ---------------------------------------------------------------------------
# The guard itself — executed, not grepped
# ---------------------------------------------------------------------------


def _floor_script() -> str:
    """The coverage gate's real shell, with the one GitHub expression substituted."""
    script = _step_run("coverage", "floor")
    # `${{ matrix.python-version }}` is the only workflow expression in this step; the
    # rest is ordinary shell. Assert that, so a future expression cannot be silently
    # left unexpanded and turn this control back into a no-op.
    substituted = script.replace("${{ matrix.python-version }}", PYTHON_VERSION)
    assert "${{" not in substituted, (
        "the floor step gained a GitHub expression this control does not substitute; "
        "extend the substitution rather than letting the script run unexpanded"
    )
    return substituted


def _run_floor_script(
    tmp_path: Path, shard_files: int, total_shards: str | None = "6"
) -> subprocess.CompletedProcess[str]:
    """Run the extracted gate in a scratch tree with `shard_files` artifacts present.

    `coverage` is stubbed on PATH so the control exercises the GUARD, not the coverage
    tool. GitHub runs steps as `bash -e {0}`, which is reproduced exactly.
    """
    workdir = tmp_path / "work"
    workdir.mkdir()
    artifacts = workdir / "shard-artifacts"
    artifacts.mkdir()
    for shard in range(1, shard_files + 1):
        (artifacts / f".coverage.{PYTHON_VERSION}.{shard}").write_text("stub", "utf-8")

    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    stub = stub_bin / "coverage"
    stub.write_text('#!/usr/bin/env bash\necho "STUB coverage $*"\n', encoding="utf-8")
    stub.chmod(0o755)

    script = tmp_path / "floor.sh"
    script.write_text(_floor_script(), encoding="utf-8")

    github_output = tmp_path / "github_output"
    github_output.touch()

    env = {
        "PATH": f"{stub_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        "GITHUB_OUTPUT": str(github_output),
    }
    if total_shards is not None:
        env["TOTAL_SHARDS"] = total_shards

    result = subprocess.run(
        ["bash", "-e", str(script)],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    # Attach the recorded output so assertions can read it back.
    result.stdout += "\n__GITHUB_OUTPUT__\n" + github_output.read_text(encoding="utf-8")
    return result


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash, as GitHub uses")
@pytest.mark.parametrize("shard_files", [0, 1, 3, 5, 7])
def test_guard_blocks_a_short_shard_count(tmp_path: Path, shard_files: int) -> None:
    """NEGATIVE CONTROL (VERIFY-01): the guard is OBSERVED to fire.

    `shard_files=3` is the observed PR #1233 shape. This is the assertion that kills the
    `present=$TOTAL_SHARDS` mutation which every string pin in this module misses.
    """
    result = _run_floor_script(tmp_path, shard_files)

    assert result.returncode == 1, (
        f"a {shard_files}-of-6 shard set did NOT block (rc={result.returncode}); the "
        f"floor was enforced over an incomplete tree.\nstdout:\n{result.stdout}"
    )
    assert (
        f"coverage not enforced: {shard_files} of 6 shard artifacts present"
        in result.stdout
    )
    assert "NOT evidence of a coverage regression" in result.stdout
    # The floor must never have been reached — no percentage may be printed at all.
    assert "STUB coverage report" not in result.stdout
    assert "STUB coverage combine" not in result.stdout
    # An incomplete run must never publish enforced=true.
    assert "enforced=true" not in result.stdout


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash, as GitHub uses")
def test_guard_passes_through_when_every_shard_reported(tmp_path: Path) -> None:
    """POSITIVE CONTROL: a complete set enforces the floor exactly as before."""
    result = _run_floor_script(tmp_path, 6)

    assert result.returncode == 0, f"complete set blocked:\n{result.stdout}"
    assert "6 of 6 shard artifacts present" in result.stdout
    assert "STUB coverage combine" in result.stdout
    assert "STUB coverage report --fail-under=95" in result.stdout
    # `enforced` is written false-then-true; the runner takes the last value.
    recorded = result.stdout.split("__GITHUB_OUTPUT__\n", 1)[1].strip().splitlines()
    assert recorded[-1] == "enforced=true"


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash, as GitHub uses")
@pytest.mark.parametrize("total_shards", [None, "", "invalid", "0", "-1", "6.5"])
def test_guard_fails_closed_on_a_missing_total_shards(
    tmp_path: Path, total_shards: str | None
) -> None:
    """Invalid shard configuration must block before coverage is combined."""
    result = _run_floor_script(tmp_path, 6, total_shards=total_shards)

    assert result.returncode != 0, (
        "the gate ran to completion with no TOTAL_SHARDS to check against; the "
        f"completeness guard failed OPEN.\nstdout:\n{result.stdout}"
    )
    assert "STUB coverage report" not in result.stdout


# ---------------------------------------------------------------------------
# Structural invariants (ordering, floor, output wiring)
# ---------------------------------------------------------------------------


def test_completeness_is_checked_before_the_floor() -> None:
    """Ordering invariant: an incomplete set can never reach `--fail-under`."""
    run = _floor_script()

    assert _command_line_index(run, 'if [ "$present" -ne') < _command_line_index(
        run, "coverage combine"
    )
    assert _command_line_index(run, "coverage combine") < _command_line_index(
        run, "coverage report --fail-under=95"
    )

    # A short count must BLOCK — never silently pass.
    guard_branch = run.split('if [ "$present" -ne', 1)[1].split("fi", 1)[0]
    assert "exit 1" in guard_branch


def test_coverage_floor_is_unchanged_at_95_and_unconditional() -> None:
    """The fix is accurate diagnosis, not a weaker gate."""
    run = _floor_script()

    assert "coverage report --fail-under=95" in run
    # Exactly one floor, at exactly 95 — no second, lower `--fail-under` anywhere.
    assert re.findall(r"--fail-under=(\d+)", run) == ["95"]
    # The floor is never wrapped in a condition that could skip it.
    assert not re.search(r"^\s*if\b.*\n\s*coverage report --fail-under=95", run, re.M)


def test_enforced_output_marks_a_complete_union_not_a_passing_floor() -> None:
    """`enforced` must be set BEFORE the floor runs, or a real breach reads as 'cancelled'.

    The behavioural half of this is covered by the controls above; this pins the wiring
    from the step's output to the job's, which those cannot see.
    """
    workflow = _workflow()
    run = _floor_script()

    assert (
        workflow["jobs"]["coverage"]["outputs"]["enforced"]
        == "${{ steps.floor.outputs.enforced }}"
    )

    assert _command_line_index(run, 'echo "enforced=false"') < _command_line_index(
        run, 'if [ "$present" -ne'
    )
    assert _command_line_index(run, 'echo "enforced=true"') < _command_line_index(
        run, "coverage report --fail-under=95"
    )


def test_test_summary_distinguishes_a_breach_from_an_unmeasured_gate() -> None:
    """The summary's coverage line reads `enforced`, routed through the #1121 gate()."""
    summary = _step_run("summary", "Check test status")

    assert 'if [ "${{ needs.coverage.outputs.enforced }}" = "true" ]; then' in summary
    # Both branches must set the variable the gate call consumes.
    assert len(re.findall(r"^\s*coverage_cause=", summary, re.M)) == 2
    assert 'gate "Coverage" "${{ needs.coverage.result }}" "$coverage_cause"' in summary
    # The two causes must actually differ in what they attribute.
    assert "95% R8/TEST-02 coverage floor" in summary
    assert "NOT evidence of a coverage regression" in summary


@pytest.mark.parametrize("inherited_datafile", [None, ".coverage.3.12.1"])
@pytest.mark.parametrize(("covered", "returncode"), [(19, 0), (18, 2)])
def test_complete_inputs_enforce_real_coverage_floor(
    tmp_path: Path,
    covered: int,
    returncode: int,
    inherited_datafile: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real Coverage.py accepts 95% and rejects 90% over a complete shard union."""
    from coverage import CoverageData

    # CI's pytest shard sets COVERAGE_FILE. The nested coverage CLI must use its
    # own scratch basename, leaving the parent shard's coverage database intact.
    parent_data = tmp_path / (inherited_datafile or "parent-coverage")
    parent_data.write_bytes(b"parent coverage sentinel")
    if inherited_datafile is None:
        monkeypatch.delenv("COVERAGE_FILE", raising=False)
    else:
        monkeypatch.setenv("COVERAGE_FILE", str(parent_data))

    workdir = tmp_path / "work"
    artifacts = workdir / "shard-artifacts"
    artifacts.mkdir(parents=True)
    source = workdir / "subject.py"
    source.write_text("\n".join(f"value_{i} = {i}" for i in range(20)) + "\n")
    for shard in range(1, 7):
        data = CoverageData(basename=str(artifacts / f".coverage.3.12.{shard}"))
        data.add_lines({str(source): set(range(shard, covered + 1, 6))})
        data.write()
    script = tmp_path / "floor.sh"
    script.write_text(_floor_script())
    output = tmp_path / "github_output"
    env = os.environ.copy()
    env.update(
        PATH=f"{Path(sys.executable).parent}{os.pathsep}{env.get('PATH', '')}",
        TOTAL_SHARDS="6",
        GITHUB_OUTPUT=str(output),
        COVERAGE_RCFILE=os.devnull,
        COVERAGE_FILE=str(workdir / ".coverage"),
    )
    result = subprocess.run(
        ["bash", "-e", str(script)],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert parent_data.read_bytes() == b"parent coverage sentinel"
    assert result.returncode == returncode, result.stdout + result.stderr
    assert output.read_text().splitlines()[-1] == "enforced=true"
    if returncode:
        assert "Coverage failure" in result.stdout
        assert not (workdir / "coverage.xml").exists()
    else:
        assert (workdir / "coverage.xml").is_file()


@pytest.mark.parametrize(
    (
        "test_result",
        "coverage_result",
        "enforced",
        "code_changed",
        "expected_rc",
        "diagnosis",
    ),
    [
        (
            "success",
            "failure",
            "false",
            "true",
            1,
            "NOT evidence of a coverage regression",
        ),
        ("success", "failure", "true", "true", 1, "95% R8/TEST-02 coverage floor"),
        ("success", "cancelled", "", "true", 1, "Coverage job did not complete"),
        ("cancelled", "failure", "false", "true", 1, "Test job did not complete"),
        ("success", "success", "true", "true", 0, "Test suite completed"),
        ("success", "success", "", "false", 0, "Test suite completed"),
    ],
)
def test_summary_executes_coverage_diagnosis(
    tmp_path: Path,
    test_result: str,
    coverage_result: str,
    enforced: str,
    code_changed: str,
    expected_rc: int,
    diagnosis: str,
) -> None:
    """Exercise the real summary, including the earlier cancellation gate and docs skip."""
    values = {
        "needs.test.result": test_result,
        "needs.lint.result": "success",
        "needs.security.result": "success",
        "needs.coverage.result": coverage_result,
        "needs.coverage.outputs.enforced": enforced,
        "needs.changes.outputs.code_changed": code_changed,
        "needs.changes.outputs.qsts_execution_changed": "false",
        "needs.grid-study.result": "skipped",
        "github.event_name": "pull_request",
    }
    script = _step_run("summary", "Check test status")
    for key, value in values.items():
        script = script.replace("${{ " + key + " }}", value)
    assert "${{" not in script
    path = tmp_path / "summary.sh"
    path.write_text(script)
    result = subprocess.run(
        ["bash", "-e", str(path)],
        cwd=tmp_path,
        env={**os.environ, "TOTAL_SHARDS": "6"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == expected_rc, result.stdout + result.stderr
    assert diagnosis in result.stdout
    if coverage_result == "failure" and test_result == "success":
        assert "Coverage job failed" in result.stdout
        assert ("NOT evidence" in result.stdout) == (enforced != "true")
