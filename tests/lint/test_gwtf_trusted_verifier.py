"""Run the external bootstrap against real verifier modules and hostile inputs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NAMES = (
    "gwtf_trusted_verifier.py",
    "gwtf_checkpoint_readiness.py",
    "gwtf_checkpoint_receipt.py",
    "gwtf_checkpoint_workflow.py",
    "gwtf_interruption_recovery.py",
    "gwtf_incident.py",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle_at(parent: Path) -> tuple[Path, str]:
    bundle = parent.resolve() / "verifier"
    bundle.mkdir(mode=0o700)
    for name in NAMES:
        shutil.copyfile(ROOT / "scripts" / name, bundle / name)
        (bundle / name).chmod(0o600)
    manifest = bundle / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": 1,
                "reviewed_commit": "a" * 40,
                "files": {name: digest(bundle / name) for name in NAMES},
            }
        )
    )
    manifest.chmod(0o600)
    return bundle, digest(manifest)


def invoke(
    bundle: Path, pin: str, cwd: Path, *, isolated: bool = True
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=str(cwd))
    return subprocess.run(
        [
            sys.executable,
            *(("-I", "-S", "-B") if isolated else ("-B",)),
            str(bundle / NAMES[0]),
            "--bundle",
            str(bundle),
            "--manifest-sha256",
            pin,
            "gwtf_checkpoint_workflow",
            "--help",
        ],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_pinned_source_ignores_candidate_imports(tmp_path: Path) -> None:
    bundle, pin = bundle_at(tmp_path)
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    marker = candidate / "EXECUTED"
    for name in (
        "json.py",
        "argparse.py",
        "gwtf_checkpoint_readiness.py",
        "sitecustomize.py",
    ):
        (candidate / name).write_text(
            f"open({str(marker)!r}, 'w').write('bad')\nraise RuntimeError('shadow')\n"
        )
    result = invoke(bundle, pin, candidate)
    assert result.returncode == 0, result.stderr
    assert "--journal" in result.stdout
    assert not marker.exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "source",
        "manifest",
        "extra",
        "symlink",
        "mode",
        "directory",
        "not_isolated",
        "in_worktree",
        "duplicate",
    ],
)
def test_untrusted_bundle_refused(tmp_path: Path, mutation: str) -> None:
    bundle, pin = bundle_at(tmp_path)
    marker = tmp_path / "EXECUTED"
    hostile = f"open({str(marker)!r}, 'w').write('bad')\n"
    module = bundle / "gwtf_checkpoint_readiness.py"
    if mutation == "source":
        module.write_text(hostile)
    elif mutation == "manifest":
        manifest = bundle / "manifest.json"
        manifest.write_text(manifest.read_text() + "\n")
    elif mutation == "extra":
        (bundle / "json.py").write_text(hostile)
    elif mutation == "symlink":
        target = tmp_path / "hostile.py"
        target.write_text(hostile)
        module.unlink()
        module.symlink_to(target)
    elif mutation == "mode":
        module.chmod(0o666)
    elif mutation == "directory":
        bundle.chmod(0o755)
    elif mutation == "in_worktree":
        (tmp_path / ".git").mkdir()
    elif mutation == "duplicate":
        manifest = bundle / "manifest.json"
        manifest.write_text(
            manifest.read_text().replace('"schema": 1', '"schema": 1, "schema": 1')
        )
        pin = digest(manifest)
    result = invoke(bundle, pin, tmp_path, isolated=mutation != "not_isolated")
    assert result.returncode == 1, result.stderr
    assert "STOP:" in result.stderr
    assert not marker.exists()


def test_rehashed_substitute_does_not_match_external_pin(tmp_path: Path) -> None:
    bundle, pin = bundle_at(tmp_path)
    module = bundle / "gwtf_checkpoint_readiness.py"
    module.write_text("raise RuntimeError('substituted')\n")
    manifest = bundle / "manifest.json"
    data = json.loads(manifest.read_text())
    data["files"][module.name] = digest(module)
    manifest.write_text(json.dumps(data))
    assert digest(manifest) != pin
    result = invoke(bundle, pin, tmp_path)
    assert result.returncode == 1
    assert "STOP:" in result.stderr
