"""Guard the retirement of the legacy wind runners (#1424).

The owner chose "retire" for the legacy wind runners on #1424 (handover item
D1340-D-06). That removed ``scripts/legacy_runners/`` and ``conf/wind_download.yaml``,
whose only consumer was the broken download runner. This guard keeps them removed,
keeps executable code and configuration from naming them again, and pins the
replacement runner's Hydra wiring so ERA5 download stays reachable.

Run:
    pytest tests/lint/test_legacy_wind_runners_retired.py -v
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, Iterator

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
THIS_FILE = Path(__file__).resolve()

RETIRED_PATHS = (
    "scripts/legacy_runners/run_wind_download_v14.py",
    "scripts/legacy_runners/run_complete_analysis_fixed.py",
    "scripts/legacy_runners/README.md",
    "conf/wind_download.yaml",
)

# Names that only the retired files carried. A directory name such as
# ``legacy_runners`` is not listed: the replacement runner's comment records
# that it was promoted out of that directory, which stays true.
RETIRED_NAMES = (
    "run_wind_download_v14",
    "run_complete_analysis_fixed",
    "wind_download.yaml",
)

# Executable code and configuration only. Markdown is history (CHANGELOG.md,
# changelog fragments, handovers, and the pinned feasibility inventory), so it
# may keep naming the retired files.
CODE_SUFFIXES = {".py", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".sh", ".json"}
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "outputs", "archive"}

REPLACEMENT_RUNNER = REPO_ROOT / "scripts" / "run_wind_analysis_v14.py"


def _code_files() -> Iterator[Path]:
    for path in REPO_ROOT.rglob("*"):
        rel_parts = path.relative_to(REPO_ROOT).parts
        if any(part in SKIP_DIRS or part.startswith(".venv") for part in rel_parts):
            continue
        if path.suffix in CODE_SUFFIXES and path.is_file() and path != THIS_FILE:
            yield path


@pytest.mark.parametrize("rel", RETIRED_PATHS)
def test_retired_path_is_absent(rel: str) -> None:
    assert not (
        REPO_ROOT / rel
    ).exists(), f"{rel} was retired on #1424; do not restore it"


def test_legacy_runners_directory_is_gone() -> None:
    assert not (REPO_ROOT / "scripts" / "legacy_runners").exists()


def test_no_code_or_config_names_a_retired_runner() -> None:
    offenders = []
    for path in _code_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name in RETIRED_NAMES:
            if name in text:
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {name}")
    assert not offenders, "retired #1424 runner named in code/config:\n" + "\n".join(
        offenders
    )


def _hydra_main_kwargs(path: Path) -> Dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for deco in node.decorator_list:
            if (
                isinstance(deco, ast.Call)
                and isinstance(deco.func, ast.Attribute)
                and deco.func.attr == "main"
                and isinstance(deco.func.value, ast.Name)
                and deco.func.value.id == "hydra"
            ):
                return {
                    kw.arg: str(kw.value.value)
                    for kw in deco.keywords
                    if kw.arg and isinstance(kw.value, ast.Constant)
                }
    raise AssertionError(f"no @hydra.main decorator in {path}")


def test_replacement_runner_resolves_to_repo_root_conf() -> None:
    kwargs = _hydra_main_kwargs(REPLACEMENT_RUNNER)
    conf_dir = (REPLACEMENT_RUNNER.parent / kwargs["config_path"]).resolve()
    assert conf_dir == (REPO_ROOT / "conf").resolve()
    assert (conf_dir / f"{kwargs['config_name']}.yaml").is_file()


def test_replacement_config_exposes_force_download() -> None:
    import yaml

    cfg = yaml.safe_load(
        (REPO_ROOT / "conf" / "wind_analysis.yaml").read_text(encoding="utf-8")
    )
    assert cfg.get("force_download") is False
