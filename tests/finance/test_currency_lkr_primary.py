"""Lock the LKR-primary currency invariant (currency de-lock decision).

`ppa.primary_currency` was decorative: a YAML comment claimed "Wind revenue
calculator reads this field", but NO Python reads it — the model is structurally
LKR-primary (LKR tariff -> LKR revenue -> LKR CFADS/tax; USD only as a post-hoc FX
division). Rather than wire a numeraire flip across the whole cashflow/debt/tax
stack, the field is formally documented as informational-only and pinned to "LKR".
This test enforces that invariant so a future stray "USD" (which would silently do
nothing) is caught at CI time.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIRS = [REPO_ROOT / "analytics", REPO_ROOT / "finance", REPO_ROOT / "wind_resource"]
SCENARIOS = list((REPO_ROOT / "scenarios").glob("*.yaml"))


def test_primary_currency_is_not_read_by_any_code() -> None:
    """No production module reads primary_currency to select the revenue numeraire."""
    readers = []
    for d in SRC_DIRS:
        for py in d.rglob("*.py"):
            if "primary_currency" in py.read_text():
                readers.append(str(py.relative_to(REPO_ROOT)))
    assert not readers, (
        "primary_currency is now READ in code — if a real numeraire selector was wired, "
        "update this test and the LKR-primary documentation:\n  " + "\n  ".join(readers)
    )


def test_all_scenarios_declare_lkr_primary() -> None:
    """Every scenario that declares ppa.primary_currency must pin it to 'LKR'."""
    offenders = []
    for scn in SCENARIOS:
        try:
            cfg = yaml.safe_load(scn.read_text())
        except yaml.YAMLError:
            continue  # multi-document example files (not real single-scenario configs)
        if not isinstance(cfg, dict):
            continue
        ppa = cfg.get("ppa")
        if isinstance(ppa, dict) and "primary_currency" in ppa:
            if str(ppa["primary_currency"]).upper() != "LKR":
                offenders.append(f"{scn.name}: {ppa['primary_currency']}")
    assert not offenders, (
        "The model is LKR-primary; primary_currency must equal 'LKR' until a USD-primary "
        "numeraire flip is actually wired:\n  " + "\n  ".join(offenders)
    )
