#!/usr/bin/env python3
"""
Quarantine tests that violate current v14/MC contracts:

- asserts absolute IRR bands (e.g. [0.17, 0.19]) unless explicitly marked frozen regression
- assumes project_irr is top-level (instead of normalized KPI aliasing)
- passes config_path= into run_monte_carlo_analysis (new contract: config + scenario_name etc.)

Behavior:
- Moves offending test files into tests/_quarantine/
- Creates a small README in quarantine folder describing why.
- Exits non-zero if any files were quarantined (so CI can force review).
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = PROJECT_ROOT / "tests"
QUAR_DIR = TESTS_DIR / "_quarantine"

FROZEN_MARKERS = (
    "FROZEN_REGRESSION",
    "frozen regression",
    "REGRESSION_SNAPSHOT",
    "pinned snapshot",
)

ABS_IRR_PATTERNS = (
    re.compile(r"\b0\.17\b.*\b0\.19\b"),
    re.compile(r"\b0\.18\b"),
    re.compile(r"\bassert\b.*\bproject_irr\b.*\b0\.\d+\b"),
    re.compile(r"\bassert\b.*\b0\.\d+\b.*\bproject_irr\b"),
)

BAD_ASSUMPTION_PATTERNS = (
    re.compile(r"\bproject_irr\s*\]"),               # suspicious indexing
    re.compile(r"\bkpis\s*\[\s*['\"]project_irr['\"]\s*\]"),
    re.compile(r"\brun_monte_carlo_analysis\s*\(.*config_path\s*=",
               re.DOTALL),
)

@dataclass(frozen=True)
class Hit:
    path: Path
    reasons: list[str]


def _iter_test_files() -> Iterable[Path]:
    for p in TESTS_DIR.rglob("test_*.py"):
        if "_quarantine" in p.parts:
            continue
        yield p


def _is_frozen(text: str) -> bool:
    tl = text.lower()
    return any(m.lower() in tl for m in FROZEN_MARKERS)


def _scan(path: Path) -> Hit | None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    reasons: list[str] = []

    # Absolute IRR bands
    if any(p.search(text) for p in ABS_IRR_PATTERNS):
        if not _is_frozen(text):
            reasons.append("absolute IRR band assertions without frozen/regression labeling")

    # Old assumptions
    if BAD_ASSUMPTION_PATTERNS[0].search(text) or BAD_ASSUMPTION_PATTERNS[1].search(text):
        reasons.append("assumes project_irr is top-level KPI (legacy expectation)")

    # config_path argument into MC
    if BAD_ASSUMPTION_PATTERNS[2].search(text):
        reasons.append("passes config_path= into run_monte_carlo_analysis (legacy signature)")

    if not reasons:
        return None

    return Hit(path=path, reasons=reasons)


def _rel(p: Path) -> str:
    return str(p.relative_to(PROJECT_ROOT))


def main() -> int:
    hits: list[Hit] = []
    for p in _iter_test_files():
        h = _scan(p)
        if h:
            hits.append(h)

    if not hits:
        print("OK: no offending tests found.")
        return 0

    QUAR_DIR.mkdir(parents=True, exist_ok=True)
    readme = QUAR_DIR / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Quarantined tests\n\n"
            "These tests were moved here because they violate current v14 contracts:\n"
            "- absolute IRR band asserts without explicit frozen regression labeling\n"
            "- legacy assumptions about project_irr location\n"
            "- legacy Monte Carlo API usage (config_path=)\n",
            encoding="utf-8",
        )

    for h in hits:
        dest = QUAR_DIR / h.path.name
        # Avoid collisions
        if dest.exists():
            dest = QUAR_DIR / f"{h.path.stem}__dup{h.path.suffix}"
        shutil.move(str(h.path), str(dest))

        stub = h.path
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text(
            "# This test was quarantined by scripts/quarantine_bad_irr_mc_tests.py\n"
            "# Reasons:\n"
            + "".join(f"# - {r}\n" for r in h.reasons)
            + f"# Original file moved to: {dest.relative_to(PROJECT_ROOT)}\n",
            encoding="utf-8",
        )

        print(f"QUARANTINED: {_rel(h.path)} -> {_rel(dest)}")
        for r in h.reasons:
            print(f"  - {r}")

    print(f"\nQuarantined {len(hits)} file(s). Review and either:")
    print("  (a) convert to frozen regression snapshots with explicit markers, or")
    print("  (b) rewrite to be contract-based (no absolute IRR bands).")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
