"""Exercise the Hydra entrypoint in an isolated public-source checkout."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from analysis_tools.financing_questionnaire import ROOT, SCENARIOS


@pytest.mark.parametrize("project", ["wind", "solar_bess"])
def test_cli(project: str, tmp_path: Path) -> None:
    """Exercise one complete JSON/workbook export without Hydra side effects."""
    for relative in [
        "analysis_tools/financing_questionnaire.py",
        "scripts/generate_financing_questionnaire.py",
        "conf/blue_whale_financing_questionnaire.yaml",
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
            f"project={project}",
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
    assert data["project"] == project
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
