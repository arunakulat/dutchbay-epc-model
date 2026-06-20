"""CESSPIT / ARCH-01 guard: no hardcoded USD/LKR rate literals in production code.

Five divergent stale FX constants (300 / 305 / 320 / 375 / 396) had accreted across
the FX, cashflow, EPC and wind-resource modules. They are now collapsed into a single
config-sourced reference (config/defaults.yaml -> analytics.fx.fx_fetch.default_fx_lkr_per_usd)
plus the scenario's own pinned fx.source vintage. This test prevents any of them from
creeping back as a Python literal.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Production modules that historically carried a magic FX rate.
GUARDED_FILES = [
    "analytics/fx/fx_builder.py",
    "analytics/fx/fx_contracts.py",
    "analytics/fx/fx_loader.py",
    "analytics/fx/correlation.py",
    "analytics/fx_sensitivity_real.py",
    "finance/cashflow_v14_params.py",
    "finance/cashflow_v14_fx.py",
    "finance/epc_helper_v14.py",
    "wind_resource/energy_calculator.py",
]

# The specific stale USD/LKR rate literals to ban (as float literals).
STALE_FX = re.compile(r"(?<![\d.])(300|305|320|375|396)\.0(?!\d)")


def _is_comment_or_docstring_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("#") or stripped.startswith(">>>") or '"""' in line


@pytest.mark.parametrize("rel_path", GUARDED_FILES)
def test_no_stale_fx_literal_in_production_code(rel_path: str) -> None:
    path = REPO_ROOT / rel_path
    assert path.exists(), f"guarded file missing: {rel_path}"
    offenders = []
    for n, line in enumerate(path.read_text().splitlines(), start=1):
        if _is_comment_or_docstring_line(line):
            continue
        if STALE_FX.search(line):
            offenders.append(f"{rel_path}:{n}: {line.strip()}")
    assert not offenders, (
        "Hardcoded FX rate literal(s) reintroduced — route through the config-sourced "
        "analytics.fx.fx_fetch.default_fx_lkr_per_usd or fx.source pinned vintage:\n  "
        + "\n  ".join(offenders)
    )


def test_default_fx_helper_is_the_single_source() -> None:
    """The one sanctioned FX default is config-sourced (config/defaults.yaml)."""
    from analytics.fx.fx_fetch import default_fx_lkr_per_usd

    assert default_fx_lkr_per_usd() > 320.0  # the corrected rate, not the stale 300
