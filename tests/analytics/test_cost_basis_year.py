"""Cost-basis year anchor — config-first resolution (CESSPIT/CCCDIR).

One anchored USD vintage for the cost stack (ATB-style), resolved from the scenario's
capex.cost_basis_year or the single config/defaults.yaml fallback — never a Python literal.
"""

from __future__ import annotations

import pytest

from analytics.cost.cost_basis import default_cost_basis_year, resolve_cost_basis_year


def test_default_is_config_sourced() -> None:
    """The fallback year comes from config/defaults.yaml, not a literal."""
    year = default_cost_basis_year()
    assert isinstance(year, int)
    assert 2020 <= year <= 2035  # a plausible vintage


def test_scenario_value_takes_precedence() -> None:
    assert resolve_cost_basis_year({"capex": {"cost_basis_year": 2024}}) == 2024


def test_falls_back_to_default_when_absent() -> None:
    assert resolve_cost_basis_year({"capex": {"usd_total": 1.0}}) == default_cost_basis_year()
    assert resolve_cost_basis_year({}) == default_cost_basis_year()


def test_invalid_year_raises() -> None:
    with pytest.raises(ValueError, match="cost_basis_year"):
        resolve_cost_basis_year({"capex": {"cost_basis_year": "not-a-year"}})


def test_canonical_scenario_declares_basis_year() -> None:
    from pathlib import Path

    from analytics.scenario_loader import load_scenario_config

    repo = Path(__file__).resolve().parents[2]
    cfg = load_scenario_config(str(repo / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"))
    assert resolve_cost_basis_year(cfg) == 2026
