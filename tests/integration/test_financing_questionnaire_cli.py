"""Exercise the Hydra entrypoint in an isolated public-source checkout."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from analysis_tools.financing_questionnaire import ROOT

# Fixtures only: the CLI names its scenario on the command line (#1783).
SCENARIOS = {
    "wind": "scenarios/blue_whale_wind_lot5b_2026.yaml",
    "solar_bess": "scenarios/blue_whale_solar_bess_lot5b_2026.yaml",
}


@pytest.mark.parametrize("project", ["wind", "solar_bess"])
def test_cli(project: str, tmp_path: Path) -> None:
    """Exercise one complete JSON/workbook export without Hydra side effects."""
    for relative in [
        # The package marker too, so the copy is a regular package and wins over any
        # other checkout an environment's .pth file puts on the path.
        "analysis_tools/__init__.py",
        "analysis_tools/financing_questionnaire.py",
        "scripts/generate_financing_questionnaire.py",
        "conf/financing_questionnaire.yaml",
        *SCENARIOS.values(),
    ]:
        dest = tmp_path / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, dest)
    env = dict(os.environ, PYTHONPATH=str(tmp_path), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [
            sys.executable,
            str(tmp_path / "scripts/generate_financing_questionnaire.py"),
            f"scenario={SCENARIOS[project]}",
            f"output_name={project}",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    receipt = json.loads(result.stdout)
    data = json.loads((tmp_path / receipt["json"]).read_text())
    assert data["scenario"] == SCENARIOS[project]
    assert data["source"]["path"] == SCENARIOS[project]
    assert (tmp_path / receipt["xlsx"]).is_file()
    assert sorted(p.name for p in (tmp_path / "outputs").iterdir()) == [
        f"{project}.json",
        f"{project}.xlsx",
    ]
    assert not (tmp_path / ".hydra").exists()


def test_cli_rejects_hydra_output_override(tmp_path: Path) -> None:
    """Refuse overrides that could enable unrelated file or log writes."""
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/generate_financing_questionnaire.py"),
            "hydra.run.dir=elsewhere",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "args",
    [[], ["output_name=x"], ["scenario=scenarios/blue_whale_wind_lot5b_2026.yaml"]],
    ids=["neither", "no scenario", "no output name"],
)
def test_cli_requires_scenario_and_output_name(args: list[str], tmp_path: Path) -> None:
    """No scenario is fixed in the config: an unnamed one is refused, not defaulted."""
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/generate_financing_questionnaire.py"),
            *args,
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2, result.stderr
    assert "required" in result.stderr
    assert not list(tmp_path.iterdir())


def test_cli_rejects_the_retired_project_selector(tmp_path: Path) -> None:
    """The old fixed `project=` selector is gone and is refused, not ignored."""
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/generate_financing_questionnaire.py"),
            "project=wind",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2
    assert not list(tmp_path.iterdir())
