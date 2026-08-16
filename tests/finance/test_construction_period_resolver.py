"""Parity tests for the shared construction-period configuration resolver."""

from __future__ import annotations

from typing import Any

import pytest

from finance.debt_v14 import _resolve_construction_periods, apply_debt_layer


def _engine_config(section: str | None, values: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal debt-engine config around one financing schema shape."""
    debt_terms: dict[str, Any] = {
        "debt_ratio": 0.0,
        "tenor_years": 1,
        "construction_schedule": [100.0],
        "debt_drawdown_pct": [1.0],
        "rates": {"usd_nominal": 0.08},
        "mix": {"usd_commercial_min": 1.0},
        **values,
    }
    config: dict[str, Any] = {"capex": {"usd_total": 100.0}}
    if section is None:
        config.update(debt_terms)
    else:
        config[section] = debt_terms
    return config


@pytest.mark.parametrize(
    ("section", "values", "expected"),
    [
        ("Financing_Terms", {"construction_periods": 3}, 3),
        ("Financing_Terms", {"construction_years": 4}, 4),
        ("FINANCING_TERMS", {"construction_periods": 5}, 5),
        ("financing", {"construction_periods": 6}, 6),
        ("debt", {"construction_periods": 7}, 7),
        (None, {"construction_periods": 8}, 8),
        ("Financing_Terms", {}, 2),
        ("Financing_Terms", {"construction_periods": -2}, 0),
        ("Financing_Terms", {"construction_periods": "3.9"}, 3),
        ("Financing_Terms", {"CONSTRUCTION_PERIODS": 9}, 2),
    ],
)
def test_resolver_matches_published_debt_construction_count(
    section: str | None,
    values: dict[str, Any],
    expected: int,
) -> None:
    """The pure resolver and live debt layer must publish the same count."""
    config = _engine_config(section, values)

    assert _resolve_construction_periods(config) == expected
    assert apply_debt_layer(config, annual_rows=[])["construction_periods"] == expected


def test_nonempty_financing_terms_wins_over_other_sections() -> None:
    """A selected nonempty Financing_Terms section keeps historical precedence."""
    config = _engine_config("Financing_Terms", {"construction_periods": 3})
    config["financing"] = {"construction_periods": 4}
    config["debt"] = {"construction_periods": 5}
    config["construction_periods"] = 6

    assert _resolve_construction_periods(config) == 3
    assert apply_debt_layer(config, annual_rows=[])["construction_periods"] == 3


def test_empty_financing_terms_falls_through_to_financing() -> None:
    """An empty Financing_Terms mapping does not mask the financing section."""
    config = _engine_config("financing", {"construction_periods": 4})
    config["Financing_Terms"] = {}
    config["debt"] = {"construction_periods": 5}

    assert _resolve_construction_periods(config) == 4
    assert apply_debt_layer(config, annual_rows=[])["construction_periods"] == 4


def test_financing_wins_over_debt_when_both_are_present() -> None:
    """The compact financing section retains precedence over compact debt."""
    config = _engine_config("financing", {"construction_periods": 4})
    config["debt"] = {"construction_periods": 5}

    assert _resolve_construction_periods(config) == 4
    assert apply_debt_layer(config, annual_rows=[])["construction_periods"] == 4


@pytest.mark.parametrize("debt_key", ["debt", "DEBT"])
def test_present_empty_debt_masks_conflicting_top_level_periods(
    debt_key: str,
) -> None:
    """A present empty debt mapping retains the extraction path's default of two."""
    config = {
        "capex": {"usd_total": 100.0},
        "allow_toy_fallback": True,
        debt_key: {},
        "construction_periods": 9,
    }

    assert _resolve_construction_periods(config) == 2
    assert apply_debt_layer(config, annual_rows=[])["construction_periods"] == 2
