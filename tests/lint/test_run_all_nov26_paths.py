"""#1616: every file the NOV26 runner names must exist, and the runner must parse.

``feasibility_reproduce/run_all_NOV26.sh`` names tests, scripts, scenarios and configs
by path. Its branch was cut before #1618 reverted #1589's wake-gap test, so the runner
still listed a deleted test file and its Blue Whale regression stage would have failed
on a missing path rather than on a model result. This lint catches that class of drift
without running the (long) runner itself.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
KIT = REPO_ROOT / "feasibility_reproduce"
RUNNER = KIT / "run_all_NOV26.sh"

# A repo-relative path token: a top-level directory the runner reads from, then a file
# with an extension. "$KIT/..." tokens resolve under the kit directory.
_REPO_PATH = re.compile(
    r"(?<![\w$/.-])((?:tests|scripts|scenarios|conf|analytics)/[\w./-]+\.(?:py|yaml))"
)
_KIT_PATH = re.compile(r"\$KIT/([\w./-]+\.(?:py|yaml))")
# "scenarios/dutchbay_${s}_2025Q4.yaml" is expanded over the loop's literal word list.
_STUDY_LOOP = re.compile(r"for s in ([^;]+);\s*do", re.DOTALL)
_STUDY_TEMPLATE = "scenarios/dutchbay_{}_2025Q4.yaml"


def named_paths(text: str) -> set[Path]:
    """Return every file path the runner text names, resolved against the repo."""
    paths = {REPO_ROOT / m for m in _REPO_PATH.findall(text)}
    paths |= {KIT / m for m in _KIT_PATH.findall(text)}
    loop = _STUDY_LOOP.search(text)
    if loop is not None:
        words = loop.group(1).replace("\\", " ").split()
        paths |= {REPO_ROOT / _STUDY_TEMPLATE.format(w) for w in words}
    return paths


def test_the_extractor_sees_each_kind_of_reference() -> None:
    """Negative control: a planted missing name of each kind is extracted."""
    planted = (
        "  tests/wind/test_planted_missing.py\n"
        '"$PY" "$KIT/lib/planted_missing.py" x\n'
        "for s in basecase planted_missing; do\n"
        "  config=scenarios/dutchbay_lendercase_2025Q4.yaml\n"
    )
    got = {p.relative_to(REPO_ROOT).as_posix() for p in named_paths(planted)}
    assert got == {
        "tests/wind/test_planted_missing.py",
        "feasibility_reproduce/lib/planted_missing.py",
        "scenarios/dutchbay_basecase_2025Q4.yaml",
        "scenarios/dutchbay_planted_missing_2025Q4.yaml",
        "scenarios/dutchbay_lendercase_2025Q4.yaml",
    }
    missing = sorted(p for p in named_paths(planted) if not p.exists())
    assert [p.name for p in missing] == [
        "planted_missing.py",
        "dutchbay_planted_missing_2025Q4.yaml",
        "test_planted_missing.py",
    ]


def test_every_path_the_runner_names_exists() -> None:
    paths = named_paths(RUNNER.read_text(encoding="utf-8"))
    # The runner names tests, scripts, scenarios, configs and kit helpers; a scan that
    # finds only a handful has stopped matching the runner's own syntax.
    assert len(paths) >= 30, sorted(paths)
    missing = sorted(
        p.relative_to(REPO_ROOT).as_posix() for p in paths if not p.exists()
    )
    assert missing == []


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
def test_the_runner_parses_and_plans_without_executing() -> None:
    subprocess.run(["bash", "-n", str(RUNNER)], check=True)
    plan = subprocess.run(
        ["bash", str(RUNNER), "--plan"],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert "No PDF from the stale August 2026 kit is certified" in plan.stdout
    bad = subprocess.run(
        ["bash", str(RUNNER), "--profile", "nightly", "--plan"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert bad.returncode == 1
    assert "profile must be full or quick" in bad.stderr
