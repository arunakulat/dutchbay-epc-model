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
    "analytics/fx_sensitivity_real.py",
    "finance/cashflow_v14_params.py",
    "finance/cashflow_v14_fx.py",
    "finance/epc_helper_v14.py",
    "wind_resource/energy_calculator.py",
]

# The specific stale USD/LKR rate literals to ban — integer OR decimal form (audit R1
# broadened this: the old `\.0`-only pattern missed a bare-integer `300` FX literal).
STALE_FX = re.compile(r"(?<![\d.,])(300|305|320|375|396)(\.\d+)?(?![\d.])")


@pytest.mark.parametrize("rel_path", GUARDED_FILES)
def test_no_stale_fx_literal_in_production_code(rel_path: str) -> None:
    path = REPO_ROOT / rel_path
    assert path.exists(), f"guarded file missing: {rel_path}"
    offenders = []
    in_docstring = False
    for n, line in enumerate(path.read_text().splitlines(), start=1):
        # Track multi-line docstring state so EXAMPLE rates INSIDE a """...""" block
        # (e.g. "start_lkr_per_usd: 375") are skipped, not flagged as live literals.
        triple = line.count('"""') + line.count("'''")
        if in_docstring:
            if triple % 2 == 1:
                in_docstring = False
            continue
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith(">>>"):
            continue
        if triple % 2 == 1:  # opening a multi-line docstring on this line
            in_docstring = True
            continue
        if triple >= 2:  # a self-contained single-line docstring
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


def test_finance_run_scenarios_declare_fx() -> None:
    """FIN-6: every finance RUN scenario (one with a top-level ``returns:`` block)
    must declare an ``fx:`` block.

    ``finance.cashflow_v14_fx._fx_curve`` now fails loud on a missing/unresolvable FX
    curve rather than fabricating a flat, non-depreciating one (the single most
    optimistic assumption for an unindexed-LKR model), so a shipped run-config without
    ``fx`` would hard-fail at runtime. Param/overlay/example files (no ``returns:``
    block) are not run through the cashflow and are exempt.
    """
    import yaml

    scen_dir = REPO_ROOT / "scenarios"
    offenders = []
    for path in sorted(scen_dir.glob("*.yaml")):
        try:
            cfg = yaml.safe_load(path.read_text())
        except yaml.YAMLError:
            continue
        if isinstance(cfg, dict) and "returns" in cfg and "fx" not in cfg:
            offenders.append(path.name)
    assert not offenders, (
        "Finance run-scenario(s) declare `returns:` but no `fx:` block — _fx_curve now "
        "fails loud on missing FX (FIN-6). Add an `fx` block:\n  " + "\n  ".join(offenders)
    )
