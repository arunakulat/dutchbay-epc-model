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
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

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
# Every config the runner hands the engine: a config= override or the scenario() helper.
_CONFIG_ARG = re.compile(r'config=["\']?([^"\'\s]+\.yaml)')
_SCENARIO_ARG = re.compile(r'\bscenario "?[^"\s]+"? "?([^"\s]+\.yaml)')
_PY_CALL = re.compile(r'"\$PY" "?([^"\s]+\.py)\b')
_LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
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


def _resolve(token: str) -> Path:
    if token.startswith("$KIT/"):
        return KIT / token[len("$KIT/") :]
    return REPO_ROOT / token


_HELPER_CONFIG = re.compile(r'^CONFIG = "([^"]+\.yaml)"', re.MULTILINE)


def engine_configs(text: str) -> set[Path]:
    """Every scenario YAML the runner text, or a kit helper it calls, hands the engine."""
    tokens = set(_CONFIG_ARG.findall(text)) | set(_SCENARIO_ARG.findall(text))
    paths = {_resolve(t) for t in tokens if "$" not in t.replace("$KIT/", "")}
    for helper in set(_PY_CALL.findall(text)):
        source = _resolve(helper)
        if helper.startswith("$KIT/") and source.is_file():
            constants = _HELPER_CONFIG.findall(source.read_text(encoding="utf-8"))
            paths |= {REPO_ROOT / c for c in constants}
    loop = _STUDY_LOOP.search(text)
    if loop is not None:
        words = loop.group(1).replace("\\", " ").split()
        paths |= {REPO_ROOT / _STUDY_TEMPLATE.format(w) for w in words}
    return paths


def _stale_engine_configs(text: str) -> list[str]:
    """Configs outside scenarios/, or with a turbine count other than the lender case's."""
    lender = yaml.safe_load(_LENDER.read_text(encoding="utf-8"))
    count = lender["turbine"]["n_turbines"]
    bad = []
    for path in sorted(engine_configs(text)):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if path.parent != REPO_ROOT / "scenarios":
            bad.append(rel)
            continue
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        stated = [
            (cfg.get("turbine") or {}).get("n_turbines"),
            (cfg.get("project") or {}).get("n_turbines"),
            ((cfg.get("resource") or {}).get("turbines") or {}).get("count"),
        ]
        if any(n is not None and n != count for n in stated):
            bad.append(rel)
    return bad


def test_the_config_extractor_sees_each_route_to_the_engine() -> None:
    """Negative control (#1659 N-3 M08/M09, R2D-3): each stale route is flagged."""
    planted = (
        'run_step "a" scenario "x" "$KIT/cache/lender_gridon.yaml"\n'
        'run_step "b" scenario y feasibility_reproduce/cache/lender_gridon.yaml\n'
        '  "$PY" run_full_pipeline_v14.py "config=$KIT/cache/lender_gridon.yaml"\n'
        "  config=legacy_scenarios/dutchbay_lendercase_2025Q4_15_turbines.yaml x\n"
        "  config=scenarios/dutchbay_mc_enhanced_2025Q4.yaml x\n"
        "  config=scenarios/dutchbay_lendercase_2025Q4.yaml x\n"
    )
    assert _stale_engine_configs(planted) == [
        "feasibility_reproduce/cache/lender_gridon.yaml",
        "legacy_scenarios/dutchbay_lendercase_2025Q4_15_turbines.yaml",
        "scenarios/dutchbay_mc_enhanced_2025Q4.yaml",
    ]
    assert len(engine_configs(planted)) == 4
    helper = '"$PY" "$KIT/lib/mc_run.py" 1 out\n'
    assert engine_configs(helper) == {_LENDER}


def test_every_engine_config_is_a_current_scenario_that_loads() -> None:
    """#1659 B-1 / D-1: no kit-cache, legacy or other-layout config reaches the engine."""
    configs = engine_configs(_runner_text())
    assert len(configs) >= 11
    assert _stale_engine_configs(_runner_text()) == []
    for path in sorted(configs):
        assert isinstance(load_scenario_config(path), dict), path


def _logical_lines(text: str) -> list[str]:
    return text.replace("\\\n", " ").splitlines()


def _hydra_calls_without_run_dir(text: str) -> list[str]:
    missing = []
    for line in _logical_lines(text):
        for script in _PY_CALL.findall(line):
            source = _resolve(script)
            if not source.is_file() or "@hydra.main" not in source.read_text(
                encoding="utf-8"
            ):
                continue
            if "hydra_dir" not in line and "hydra.run.dir" not in line:
                missing.append(line.strip())
    return missing


def test_every_hydra_entry_point_gets_a_run_dir_under_out() -> None:
    """#1659 B-3 (N-3 M10/M11): otherwise Hydra writes outputs/ into the checkout."""
    text = _runner_text()
    planted = '  "$PY" run_full_pipeline_v14.py "config=$cfg" x=1\n'
    assert _hydra_calls_without_run_dir(planted) == [planted.strip()]
    hydra_lines = [
        line
        for line in _logical_lines(text)
        if any(
            "@hydra.main" in _resolve(s).read_text(encoding="utf-8")
            for s in _PY_CALL.findall(line)
            if _resolve(s).is_file()
        )
    ]
    assert len(hydra_lines) >= 10
    assert _hydra_calls_without_run_dir(text) == []
    mc_run = (KIT / "lib" / "mc_run.py").read_text(encoding="utf-8")
    assert "f\"hydra.run.dir={outdir / 'hydra'}\"," in mc_run
    # The two suite tests that run a Hydra CLI from the checkout (#1659 N-1).
    for test in (
        "tests/integration/test_sensitivity_cli_smoke.py",
        "tests/analytics/test_mc_sobol_sampler.py",
    ):
        source = (REPO_ROOT / test).read_text(encoding="utf-8")
        assert "f\"hydra.run.dir={tmp_path / 'hydra'}\"," in source, test


_REQUIRED_LINES = (
    # Every place the run writes is under --out or a private mktemp dir (B-3, N-1).
    "umask 077",
    "export PYTHONDONTWRITEBYTECODE=1",
    'export COVERAGE_FILE="$OUT/.coverage"',
    'TMP_PRIVATE="$(mktemp -d /tmp/dutchbay-nov26-tmp.XXXXXXXX)"',
    'TMP_WORK="$OUT/tmp"',
    'export MPLCONFIGDIR="$OUT/cache/matplotlib"',
    'export NUMBA_CACHE_DIR="$OUT/cache/numba"',
    'export PYTEST_ADDOPTS="${PYTEST_ADDOPTS:+$PYTEST_ADDOPTS }-p no:cacheprovider"',
    'export HYPOTHESIS_STORAGE_DIRECTORY="$OUT/cache/hypothesis"',
    'export RUFF_CACHE_DIR="$OUT/cache/ruff"',
    'export MYPY_CACHE_DIR="$OUT/cache/mypy"',
    'export BLACK_CACHE_DIR="$OUT/cache/black"',
    'hydra_dir() { printf \'hydra.run.dir=%s/hydra/%s\' "$OUT" "$1"; }',
    # The residue stage's reference points (N-1, N-5).
    'CHECKOUT_MARKER="$OUT/.checkout_marker"',
    ': > "$CHECKOUT_MARKER"',
    'GIT_STATUS_BEFORE="$OUT/.git_status_before"',
    'git status --porcelain=v1 --untracked-files=all > "$GIT_STATUS_BEFORE"',
    'if [[ -s "$GIT_STATUS_BEFORE" ]]; then TREE_DIRTY=yes; else TREE_DIRTY=no; fi',
    'printf \'tree_dirty=%s\\n\' "$TREE_DIRTY" >> "$OUT/manifest.txt"',
    # Defence in depth after the preflight (N-4).
    "if ((REQUIRE_PRIVATE)); then exit 3; fi",
)


@pytest.mark.parametrize("line", _REQUIRED_LINES)
def test_write_locations_and_receipt_lines_are_as_reviewed(line: str) -> None:
    """#1659 B-3 / N-1 / N-4 / N-5: each reviewed line is present verbatim."""
    stripped = [ln.strip() for ln in _runner_text().splitlines()]
    assert line in stripped


def test_out_is_checked_again_after_it_is_created() -> None:
    """#1659 N-2: check, create, re-resolve, check again, in that order."""
    code = [
        ln.strip()
        for ln in _runner_text().splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    seq = ["check_out", 'mkdir -p "$OUT"', 'OUT="$(cd "$OUT" && pwd -P)"', "check_out"]
    starts = [i for i in range(len(code)) if code[i : i + len(seq)] == seq]
    assert len(starts) == 1
    marker = code.index(': > "$CHECKOUT_MARKER"')
    first_stage = next(i for i, ln in enumerate(code) if ln.startswith("run_step "))
    assert starts[0] < marker < first_stage


def test_the_residue_stage_is_the_last_stage() -> None:
    """#1659 R3-2: it must run after every stage that could write."""
    stages = [
        ln
        for ln in _logical_lines(_runner_text())
        if re.search(r'(^|\s)run_step "', ln)
    ]
    assert stages[-1].strip() == 'run_step "checkout-residue" checkout_residue'
    assert sum("checkout_residue" in ln for ln in stages) == 1


def _residue_function() -> str:
    text = _runner_text()
    start = text.index("checkout_residue() {")
    end = text.index("\n}\n", start) + 3
    return text[start:end]


@pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="bash and git are needed",
)
@pytest.mark.parametrize(
    "plant, expect",
    [
        (None, 0),
        ("new_file.txt", 1),
        ("outputs/receipt.json", 1),
        ("outputs/existing.json", 1),
        ("tracked.txt", 1),
        ("delete:tracked.txt", 1),
        (".git/new_object", 0),
        (".venv/lib/new.py", 0),
    ],
)
def test_the_residue_check_catches_writes_into_the_checkout(
    tmp_path: Path, plant: str | None, expect: int
) -> None:
    """#1659 R3-2 / R3D-4: the extracted function fails on each kind of write."""
    repo = tmp_path / "repo"
    out = tmp_path / "out"
    (repo / ".venv" / "lib").mkdir(parents=True)
    out.mkdir()
    git = ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".gitignore").write_text(".venv/\noutputs/\n", encoding="utf-8")
    (repo / "tracked.txt").write_text("a\n", encoding="utf-8")
    # An ignored file that already exists: appending to it changes neither git status
    # nor its directory's mtime, so only the file-level mtime check can see it.
    (repo / "outputs").mkdir()
    (repo / "outputs" / "existing.json").write_text("{}\n", encoding="utf-8")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "init"], check=True)
    old = 1_600_000_000
    for path in repo.rglob("*"):
        os.utime(path, (old, old))
    script = f"""
set -euo pipefail
REPO={str(repo)!r}; VENV={str(repo / ".venv")!r}
CHECKOUT_MARKER={str(out / ".checkout_marker")!r}
GIT_STATUS_BEFORE={str(out / ".git_status_before")!r}
: > "$CHECKOUT_MARKER"
git -C "$REPO" status --porcelain=v1 --untracked-files=all > "$GIT_STATUS_BEFORE"
sleep 1
{_residue_function()}
PLANT={plant or ""!r}
case "$PLANT" in
  "") ;;
  delete:*) rm "$REPO/${{PLANT#delete:}}" ;;
  *) mkdir -p "$(dirname "$REPO/$PLANT")"; echo x >> "$REPO/$PLANT" ;;
esac
checkout_residue
"""
    proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert proc.returncode == expect, proc.stdout + proc.stderr


def test_the_full_profile_mirrors_ci_gates() -> None:
    """#1659 D-3 / D-4 (N-3 M20, M21): the mypy scripts/ gate and the receipt ignore."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "test-suite.yml").read_text(
        encoding="utf-8"
    )
    ci_mypy = re.search(r"(mypy scripts/ [^\n]+\n\s+--[^\n]+)", workflow)
    assert ci_mypy is not None
    ci_flags = ci_mypy.group(1).split()
    lines = _logical_lines(_runner_text())
    runner_mypy = [ln for ln in lines if '"mypy-scripts"' in ln]
    assert len(runner_mypy) == 1
    assert runner_mypy[0].split()[-len(ci_flags) :] == ci_flags
    ignore = "--ignore=tests/grid/test_base_candidate_physical_receipt.py"
    assert ignore in workflow
    full = [ln for ln in lines if '"full-pytest-six-package-95pct-coverage"' in ln]
    assert len(full) == 1 and ignore in full[0]
    # The receipt test writes outputs/ into its cwd (the checkout); CI's Grid Study job
    # runs it, so the runner's grid stage leaves it out too (#1659 R3-1).
    grid = [ln for ln in lines if '"grid-study"' in ln]
    assert len(grid) == 1 and ignore in grid[0]


def test_the_14_turbine_oracle_stage_keeps_its_three_oracles() -> None:
    """#1659 R3D-4 (DM12)."""
    stage = [
        ln
        for ln in _logical_lines(_runner_text())
        if '"current-14-turbine-oracles"' in ln
    ]
    assert len(stage) == 1
    for oracle in (
        "tests/finance/test_multitech_generation.py::"
        "test_canonical_lendercase_economics_unchanged",
        "tests/finance/test_lendercase_expected_results.py",
        "tests/wind/test_dutchbay_14_turbines.py",
    ):
        assert oracle in stage[0]


def _expected_basis_fragments(cfg: dict) -> list[str]:
    """An independent reading of what a study note must say about its own YAML."""
    techs = (cfg.get("generation") or {}).get("technologies") or {}
    count = (cfg.get("turbine") or {}).get("n_turbines")
    if count is None:
        count = (cfg.get("project") or {}).get("n_turbines")
    frags = [f"{count}-turbine layout"] if count is not None else ["no turbine layout"]
    frags += [f"{name} {spec['capacity_mw']} MW" for name, spec in techs.items()]
    if count is None:
        frags += [
            f"capacity factor {spec['capacity_factor']}" for spec in techs.values()
        ] or [f"capacity factor {cfg['project']['capacity_factor']}"]
    if len(techs) > 1:
        frags.append(f"({cfg['project']['capacity_mw']} MW total)")
    return frags


def test_study_receipts_name_what_each_row_models() -> None:
    """#1659 D-1 / R2D-1 / R3D-3: each row's note is read from that row's own YAML."""
    lines = _logical_lines(_runner_text())
    micrositing = [ln for ln in lines if '"study-wind-aep-synthetic-micrositing"' in ln]
    assert len(micrositing) == 1
    assert 'STEP_NOTE="synthetic 15-turbine wiring check' in micrositing[0]
    study = [ln for ln in lines if '"study-scenario-$s"' in ln]
    assert len(study) == 1
    template = '"scenarios/dutchbay_${s}_2025Q4.yaml"'
    note_arg = f'"$KIT/lib/scenario_basis.py" {template})"'
    assert note_arg in study[0]
    assert study[0].rstrip().endswith(f'scenario "$s" {template}')
    script = str(KIT / "lib" / "scenario_basis.py")
    loop = _STUDY_LOOP.search(_runner_text())
    assert loop is not None
    notes = set()
    for word in loop.group(1).replace("\\", " ").split():
        path = REPO_ROOT / _STUDY_TEMPLATE.format(word)
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        note = subprocess.run(
            [sys.executable, script, str(path)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        for fragment in _expected_basis_fragments(cfg):
            assert fragment in note, (word, note)
        notes.add(note)
    # Rows that model different things must not share one note.
    assert len(notes) >= 4


def _private_env(tmp_path: Path, missing: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in _PRIVATE_ENV}
    (tmp_path / "nasa").mkdir()
    for var in _PRIVATE_ENV:
        if var == missing:
            continue
        if var == "DUTCHBAY_NASA_POWER_DIR":
            env[var] = str(tmp_path / "nasa")
        else:
            target = tmp_path / f"{var.lower()}.dat"
            target.write_text("x", encoding="utf-8")
            env[var] = str(target)
    return env


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
@pytest.mark.parametrize("missing", _PRIVATE_ENV)
def test_require_private_exits_3_before_any_write(tmp_path: Path, missing: str) -> None:
    """#1659 B-2 / D-2 (N-3 M14): each missing confidential input exits 3."""
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
        env=_private_env(tmp_path, missing),
    )
    assert proc.returncode == 3, proc.stderr
    assert f"--require-private needs {missing}" in proc.stderr
    assert not out.exists()


def _run_out(out: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k not in _PRIVATE_ENV}
    return subprocess.run(
        ["bash", str(RUNNER), "--profile", "quick", "--out", out],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        timeout=120,
    )


_NEEDS_TOOLS = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("make") is None,
    reason="bash and make are needed to reach the --out checks",
)


@_NEEDS_TOOLS
def test_out_inside_the_checkout_is_refused(tmp_path: Path) -> None:
    """#1659 A-4 (N-3 M18): nothing is created in the checkout."""
    probe = REPO_ROOT / "feasibility_reproduce" / "nov26_out_probe_refused"
    assert not probe.exists()
    try:
        proc = _run_out(str(probe), tmp_path)
        assert not probe.exists()
    finally:
        shutil.rmtree(probe, ignore_errors=True)
    assert proc.returncode == 1
    assert "--out must be outside checkout" in proc.stderr


@_NEEDS_TOOLS
@pytest.mark.parametrize("form", ["dotdot", "dot"])
def test_out_with_dot_components_is_refused(tmp_path: Path, form: str) -> None:
    """#1659 N-2: a "." or ".." component is refused before anything is created."""
    landing = REPO_ROOT / "nov26_dotdot_probe_refused"
    assert not landing.exists()
    up = "/".join([".."] * (len(tmp_path.parts) + 1))
    if form == "dotdot":
        out = f"{tmp_path}/missing/{up}{REPO_ROOT}/{landing.name}"
    else:
        out = f"{tmp_path}/missing/./x"
    try:
        proc = _run_out(out, tmp_path)
        assert not landing.exists()
    finally:
        shutil.rmtree(landing, ignore_errors=True)
    assert proc.returncode == 1
    assert "must not contain . or .. components" in proc.stderr
    assert not (tmp_path / "missing").exists()


@_NEEDS_TOOLS
def test_group_writable_out_is_refused(tmp_path: Path) -> None:
    """#1659 A-4 (N-3 M17)."""
    out = tmp_path / "shared"
    out.mkdir()
    out.chmod(0o770)
    proc = _run_out(str(out), tmp_path)
    assert proc.returncode == 1
    assert "writable by group or others" in proc.stderr
    assert list(out.iterdir()) == []


@_NEEDS_TOOLS
def test_out_owned_by_another_user_is_refused(tmp_path: Path) -> None:
    """#1659 A-4 (N-3 M16). As root, a dir is handed to nobody; otherwise /tmp is used."""
    if os.geteuid() == 0:
        out = tmp_path / "foreign"
        out.mkdir(mode=0o755)
        os.chown(out, 65534, 65534)
    else:
        out = Path("/tmp")
        if out.stat().st_uid == os.geteuid():
            pytest.skip("no directory owned by another user is available")
    proc = _run_out(str(out), tmp_path)
    assert proc.returncode == 1
    assert "is not owned by the invoking user" in proc.stderr


@_NEEDS_TOOLS
def test_relative_private_paths_are_made_absolute_before_cd(tmp_path: Path) -> None:
    """#1659 N-4 (R10): a relative path means the caller's directory, not the checkout."""
    env = {k: v for k, v in os.environ.items() if k not in _PRIVATE_ENV}
    (tmp_path / "nasa").mkdir()
    for var in _PRIVATE_ENV:
        name = "nasa" if var == "DUTCHBAY_NASA_POWER_DIR" else f"{var.lower()}.dat"
        if name != "nasa":
            (tmp_path / name).write_text("x", encoding="utf-8")
        env[var] = name
    shared = tmp_path / "shared"
    shared.mkdir()
    shared.chmod(0o770)
    proc = subprocess.run(
        ["bash", "-x", str(RUNNER), "--profile", "quick", "--out", str(shared)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        timeout=120,
    )
    assert proc.returncode == 1
    assert "writable by group or others" in proc.stderr
    for var in _PRIVATE_ENV:
        name = "nasa" if var == "DUTCHBAY_NASA_POWER_DIR" else f"{var.lower()}.dat"
        assert f"export {var}={tmp_path}/{name}" in proc.stderr, var
