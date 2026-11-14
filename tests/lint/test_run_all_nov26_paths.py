"""#1616: every file the NOV26 runner names must exist, and the runner must parse.

``feasibility_reproduce/run_all_NOV26.sh`` names tests, scripts, scenarios and configs
by path. Its branch was cut before #1618 reverted #1589's wake-gap test, so the runner
still listed a deleted test file and its Blue Whale regression stage would have failed
on a missing path rather than on a model result. This lint catches that class of drift
without running the (long) runner itself.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from analytics.scenario_loader import load_scenario_config

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
# Non-path names the runner also depends on (#1659 assurance A-6).
_MARKER = re.compile(r'(?<!"\$PY" )-m ([a-z_]+)\b')
_CONFIG_NAME = re.compile(r"--config-name ([\w-]+)")
_ENTRY_POINT = re.compile(r'"\$PY" ([\w-]+\.py)\b')
_MAKE_TARGET = re.compile(r'run_step "[^"]+" make ([\w-]+)')
_NODE_ID = re.compile(r"([\w/]+\.py)::(\w+)")
_REPO_VAR_PATH = re.compile(r"\$REPO/([\w./-]+\.\w+)")
# The August grid-on lender fork and other kit caches predate the 14-turbine layout.
_KIT_CACHE_CONFIG = re.compile(r"config=\S*\$KIT/cache/")
_PRIVATE_ENV = (
    "BLUE_WHALE_POWER_CURVE_CSV",
    "DUTCHBAY_MET_MAST_617725_SOURCE",
    "DUTCHBAY_NASA_POWER_DIR",
    "BLUE_WHALE_PRIVATE_ANCHORS_PATH",
)


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


def _runner_text() -> str:
    return RUNNER.read_text(encoding="utf-8")


def test_every_pytest_marker_the_runner_selects_is_registered() -> None:
    markers = set(_MARKER.findall(_runner_text()))
    assert markers >= {"grid", "stochastic_qualification", "report_qualification"}
    pyproject = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    registered = {
        m.split(":", 1)[0].strip()
        for m in pyproject["tool"]["pytest"]["ini_options"]["markers"]
    }
    assert sorted(markers - registered) == []


def test_every_hydra_config_name_entry_point_and_repo_path_exists() -> None:
    text = _runner_text()
    names = _CONFIG_NAME.findall(text)
    assert len(names) >= 2
    entry_points = _ENTRY_POINT.findall(text)
    assert "run_full_pipeline_v14.py" in entry_points
    repo_paths = _REPO_VAR_PATH.findall(text)
    missing = [
        f"conf/{n}.yaml"
        for n in names
        if not (REPO_ROOT / "conf" / f"{n}.yaml").is_file()
    ]
    missing += [e for e in entry_points if not (REPO_ROOT / e).is_file()]
    missing += [r for r in repo_paths if not (REPO_ROOT / r).exists()]
    assert missing == []


def test_every_make_target_the_runner_calls_exists() -> None:
    targets = set(_MAKE_TARGET.findall(_runner_text()))
    assert targets >= {"lint", "type", "security"}
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    defined = set(re.findall(r"^([\w-]+):", makefile, flags=re.MULTILINE))
    assert sorted(targets - defined) == []


def test_every_pytest_node_id_names_a_test_in_its_file() -> None:
    nodes = _NODE_ID.findall(_runner_text())
    assert nodes
    for path, name in nodes:
        source = (REPO_ROOT / path).read_text(encoding="utf-8")
        assert re.search(rf"^def {name}\(", source, flags=re.MULTILINE), (path, name)


def test_the_runner_passes_no_kit_cache_config_to_the_engine() -> None:
    """#1659 B-1 / D-1: study mode must not replay the August 15-turbine forks."""
    assert _KIT_CACHE_CONFIG.search(_runner_text()) is None
    assert (
        _KIT_CACHE_CONFIG.search('"config=$KIT/cache/lender_gridon.yaml"') is not None
    )


def test_every_scenario_the_runner_names_loads() -> None:
    """A named config that exists but is refused at load fails its stage (#1659 B-1)."""
    scenarios = sorted(
        p for p in named_paths(_runner_text()) if p.parent == REPO_ROOT / "scenarios"
    )
    assert len(scenarios) >= 10
    for path in scenarios:
        cfg = load_scenario_config(path)
        assert isinstance(cfg, dict), path


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
def test_require_private_exits_3_before_any_write(tmp_path: Path) -> None:
    """#1659 B-2 / D-2: missing confidential inputs exit 3, distinct from a stage failure."""
    env = {k: v for k, v in os.environ.items() if k not in _PRIVATE_ENV}
    out = tmp_path / "out"
    proc = subprocess.run(
        [
            "bash",
            str(RUNNER),
            "--profile",
            "quick",
            "--require-private",
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    assert proc.returncode == 3, proc.stderr
    assert "--require-private needs BLUE_WHALE_POWER_CURVE_CSV" in proc.stderr
    assert not out.exists()
