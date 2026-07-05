"""Honesty guard for the generated architecture import graph (#746).

The diagram in ``docs/architecture_import_graph.mmd`` (mirrored into
``docs/ARCHITECTURE.md``) is produced by ``scripts/gen_architecture_diagram.py``
from the live import graph. These tests fail if the committed artifacts are stale,
so the picture can never silently drift from the code it claims to describe.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GEN_SCRIPT = REPO_ROOT / "scripts" / "gen_architecture_diagram.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "gen_architecture_diagram", GEN_SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_diagram_is_up_to_date() -> None:
    """`--check` must pass: the committed .mmd and the ARCHITECTURE.md block match
    a fresh render of the current import graph."""
    gen = _load_generator()
    assert gen.main(["--check"]) == 0, (
        "Architecture diagram is stale. Regenerate with: "
        "python scripts/gen_architecture_diagram.py"
    )


def test_diagram_is_non_empty_and_first_party() -> None:
    """A fresh render lists the core first-party packages and at least one edge."""
    gen = _load_generator()
    rendered = gen.generate()
    assert rendered.startswith("%% AUTO-GENERATED")
    assert "flowchart LR" in rendered
    # The canonical engine packages must be nodes.
    for pkg in ("analytics", "finance"):
        assert f"    {pkg}[{pkg}]" in rendered
    # At least one dependency edge is drawn.
    assert " --> " in rendered


def test_markers_present_in_architecture_doc() -> None:
    """ARCHITECTURE.md carries the splice markers the generator manages."""
    gen = _load_generator()
    doc = gen.ARCH_DOC.read_text(encoding="utf-8")
    assert gen._BEGIN_MARKER in doc
    assert gen._END_MARKER in doc
