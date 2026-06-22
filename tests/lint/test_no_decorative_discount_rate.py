"""GWTF guard: a bare top-level ``discount_rate:`` must not appear in scenario configs.

The canonical v14 pipeline derives the project discount rate from the build-up WACC
(``wacc:`` / ``returns.project_discount_rate``) and the equity discount from the cost of
equity — NOT from a top-level ``discount_rate`` key. That key is read only by the
non-canonical ``analytics.scenario_analytics`` path, so a top-level ``discount_rate:`` in a
scenario is a DECORATIVE no-op: it advertises a 12–15% hurdle that the engine never applies
(audit Round 2 finding 3.2 found stale 0.12–0.15 placeholders across 13 scenarios — the
Round 1 lender-case removal had not been propagated to the siblings). Removing them is
byte-identical for the canonical pipeline (verified). This guard fails loud so the trap
cannot recur; rglob covers scenario subdirectories too (finding 5.3).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = REPO_ROOT / "scenarios"

# A bare top-level key (column 0), e.g. ``discount_rate: 0.12`` — NOT a nested
# ``equity.discount_rate`` / ``returns.project_discount_rate`` (those are real).
_TOP_LEVEL_DISCOUNT_RATE = re.compile(r"^discount_rate\s*:")


def test_no_top_level_discount_rate_in_scenarios() -> None:
    offenders: list[str] = []
    for path in sorted(SCENARIOS_DIR.rglob("*.yaml")):
        for n, line in enumerate(path.read_text().splitlines(), start=1):
            if _TOP_LEVEL_DISCOUNT_RATE.match(line):
                rel = path.relative_to(REPO_ROOT)
                offenders.append(f"{rel}:{n}: {line.strip()}")
    assert not offenders, (
        "Decorative top-level `discount_rate:` found in scenario config(s) — the canonical "
        "pipeline IGNORES it (project discount comes from the build-up WACC). Remove it; for "
        "a real discount use the `wacc:` build-up or `returns.project_discount_rate`:\n  "
        + "\n  ".join(offenders)
    )
