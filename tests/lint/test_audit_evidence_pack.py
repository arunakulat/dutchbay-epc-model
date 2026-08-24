"""Repository gate for the August 2026 controlled audit successor pack."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = (
    REPO_ROOT
    / "docs"
    / "audit"
    / "2026-08-controlled-successor"
    / "scripts"
    / "validate_published_pack.py"
)


def _load_validator() -> ModuleType:
    """Load the pack validator so refusal paths can be exercised directly."""
    spec = importlib.util.spec_from_file_location("audit_pack_validator", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy_erratum_control_surface(module: ModuleType, destination: Path) -> None:
    """Copy only the files used by the focused erratum validation."""
    for relative in (
        module.IMMUTABLE_CONTROL_RECORD,
        module.RULESET_COUNT_ERRATUM,
        module.ARCHITECTURE_REGISTER,
    ):
        source = module.PACK_ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def test_controlled_audit_successor_pack_is_internally_valid() -> None:
    """The published pack must remain manifest-complete and explicitly on HOLD."""
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert '"status": "PASS"' in completed.stdout
    assert '"release_status": "HOLD"' in completed.stdout
    assert '"ruleset_count_erratum": "PASS"' in completed.stdout


@pytest.mark.parametrize("mutation", ["record", "instruction"])
def test_ruleset_count_erratum_guard_rejects_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    """The erratum guard must reject both provenance and instruction drift."""
    validator = _load_validator()
    pack_root = tmp_path / "pack"
    _copy_erratum_control_surface(validator, pack_root)
    monkeypatch.setattr(validator, "PACK_ROOT", pack_root)

    if mutation == "record":
        record = pack_root / validator.IMMUTABLE_CONTROL_RECORD
        record.write_text(record.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        expected = "immutable programming record digest drift"
    else:
        erratum = pack_root / validator.RULESET_COUNT_ERRATUM
        text = erratum.read_text(encoding="utf-8").replace(
            validator.STABLE_RULESET_INGRESS_INSTRUCTION,
            "Re-ingress a copied fixed count",
        )
        erratum.write_text(text, encoding="utf-8")
        expected = "source-derived re-ingress instruction"

    with pytest.raises(validator.ValidationError, match=expected):
        validator._validate_ruleset_count_erratum()
