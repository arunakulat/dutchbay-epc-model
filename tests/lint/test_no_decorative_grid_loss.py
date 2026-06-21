"""GWTF guard: ``grid_loss_pct`` must not be declared under the UNREAD ``statutory:`` /
``regulatory:`` namespaces.

The cashflow engine resolves ``grid_loss_pct`` only from ``project`` / ``parameters`` /
top-level (``finance.cashflow_v14_params._build_cashflow_params``). A ``grid_loss_pct``
under ``statutory:`` or ``regulatory:`` is therefore a DECORATIVE no-op — it looks like a
2–10% transmission/curtailment haircut but silently does nothing (audit Round 1 found this
across 11 scenarios, incl. "PESSIMISTIC: 5% grid curtailment" and "EXTREME: 10%" that never
applied). This guard fails loud so the trap cannot recur. To actually apply a haircut, put
the value under ``project.grid_loss_pct``; for a grid-curtailment stress use
``project.curtailment_pct`` (the first-class financed lever).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_UNREAD = {"statutory", "regulatory"}


def _offending_lines(path: Path) -> list[int]:
    block: str | None = None
    hits: list[int] = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        header = re.match(r"^([A-Za-z_]\w*):", line)
        if header:
            block = header.group(1)
        if block in _UNREAD and re.match(r"^  grid_loss_pct:", line):
            hits.append(i)
    return hits


def test_no_grid_loss_under_unread_namespace() -> None:
    offenders = {}
    for path in sorted((REPO_ROOT / "scenarios").glob("*.yaml")):
        hits = _offending_lines(path)
        if hits:
            offenders[path.name] = hits
    assert not offenders, (
        "grid_loss_pct declared under the UNREAD statutory:/regulatory: namespace "
        f"(finance reads only project/parameters/top-level): {offenders}. Move it to "
        "project.grid_loss_pct to apply it, or use project.curtailment_pct for a grid-"
        "curtailment stress — do not leave a decorative no-op."
    )
