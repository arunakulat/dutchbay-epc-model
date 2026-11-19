"""Parity tests for the shared construction-period configuration resolver."""

from __future__ import annotations

from typing import Any

import pytest

from finance.debt_v14 import _resolve_construction_periods, apply_debt_layer


def _engine_config(section: str | None, values: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal debt-engine config around one financing schema shape."""
    probe: dict[str, Any] = {"capex": {"usd_total": 100.0}}
    if section is None:
        probe.update(values)
    else:
        probe[section] = dict(values)
    try:
        n = _resolve_construction_periods(probe)
    except ValueError:
        n = 0  # no declared count: the config under test is refused below (#1429)
    sched = [100.0 / n] * n if n >= 1 else []
    draw = [1.0 / n] * n if n >= 1 else []
    debt_terms: dict[str, Any] = {
        "debt_ratio": 0.0,
        "target_dscr": 1.30,  # no code default since #1429
        "tenor_years": 1,
        "construction_schedule": sched,
        "debt_drawdown_pct": draw,
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
        ("Financing_Terms", {"construction_periods": -2}, 0),
        ("Financing_Terms", {"construction_periods": "3.9"}, 3),
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


@pytest.mark.parametrize(
    "values",
    [{}, {"CONSTRUCTION_PERIODS": 9}],
    ids=["absent", "child_key_case_sensitive"],
)
def test_resolver_and_debt_layer_refuse_an_undeclared_count(
    values: dict[str, Any],
) -> None:
    """No count declared (child keys stay case-sensitive): both refuse, naming the path.

    Before #1429's second debt step both published the default of two periods.
    """
    config = _engine_config("Financing_Terms", values)

    message = r"Financing_Terms\.construction_periods \(or timeline"
    with pytest.raises(ValueError, match=message):
        _resolve_construction_periods(config)
    with pytest.raises(ValueError, match=message):
        apply_debt_layer(config, annual_rows=[])


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
    """A present empty debt mapping masks the top-level count, which is then undeclared.

    The debt section is selected, so the top-level ``construction_periods: 9`` is not
    read. Before #1429's second debt step the count became the default of two; now it
    is refused, naming ``debt.construction_periods``.
    """
    config = {
        "capex": {"usd_total": 100.0},
        "allow_toy_fallback": True,
        debt_key: {},
        "construction_periods": 9,
    }

    message = r"debt\.construction_periods \(or timeline.*no code default \(#1429\)"
    with pytest.raises(ValueError, match=message):
        _resolve_construction_periods(config)
    with pytest.raises(ValueError, match=message):
        apply_debt_layer(config, annual_rows=[])
    # Declared in the debt section, the count is used and the top level still ignored.
    config[debt_key] = {
        "debt_ratio": 0.0,
        "target_dscr": 1.30,
        "tenor_years": 1,
        "construction_periods": 2,
    }
    assert _resolve_construction_periods(config) == 2
    assert apply_debt_layer(config, annual_rows=[])["construction_periods"] == 2
