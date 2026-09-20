"""Guard: every ``wind_resource/`` module is described in ``docs/MODULE_REFERENCE.md``.

``synthetic_mcp_measurement.py`` sat undocumented while the other 16 modules were covered
(#1277). Nothing checked, so nothing said. The reference doc is where a reviewer goes to
learn which module is on the lender path and which is a validate-only side branch, and a
module missing from it is invisible to that reader.

Deliberately narrow: this asserts PRESENCE of a row per module, not the quality of its
description, so it can never fail for a reason a reviewer cannot act on.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WIND_RESOURCE = REPO_ROOT / "wind_resource"
MODULE_REFERENCE = REPO_ROOT / "docs" / "MODULE_REFERENCE.md"


def test_module_reference_names_every_wind_resource_module() -> None:
    text = MODULE_REFERENCE.read_text()
    modules = sorted(
        p.name for p in WIND_RESOURCE.glob("*.py") if p.name != "__init__.py"
    )
    assert modules, "no wind_resource modules found — check the glob"
    missing = [name for name in modules if f"`{name}`" not in text]
    assert not missing, (
        "wind_resource modules absent from docs/MODULE_REFERENCE.md: "
        + ", ".join(missing)
        + ". Add a row under 'Wind Resource Pipeline (ERA5 to bankable AEP)' saying what "
        "the module is for and whether it is on the lender path."
    )
