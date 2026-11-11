"""The construction-period count must equal the scenario's declared build time (#1570).

``finance.debt.terms._resolve_construction_periods`` used to read only the financing
section and fall back to two periods, so a scenario that declared a one-year build in
``timeline.construction_years`` and nothing in ``Financing_Terms`` ran on two. These tests
pin the guard and the placeholder draw and phasing that are now sized to the count.

``TEST-01`` oracles that did not originate in this change:

* the IDC closed forms. A one-period build with the placeholder draw capitalises
  ``0.5 * D * r``; two periods with ``[0.5, 0.5]`` capitalise
  ``0.5 * D * r + (D + 0.5 * D * r) * r``, the engine's start-of-period convention
  before and after this change;
* the committed scenarios' own ``timeline.construction_years``, read straight from YAML
  and compared with the engine's count;
* a responsiveness guard: changing ``timeline.construction_years`` changes the count
  and the IDC.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from finance.debt_v14 import (
    _extract_financing_terms,
    _resolve_construction_periods,
    apply_debt_layer,
    placeholder_construction_schedule,
    placeholder_debt_drawdown_pct,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = REPO_ROOT / "scenarios"

CAPEX_USD = 1_000_000.0
DEBT_RATIO = 0.5
RATE = 0.10
DEBT_USD = CAPEX_USD * DEBT_RATIO


def _config(
    *,
    financing: dict[str, Any] | None = None,
    timeline_years: Any = None,
    section: str = "Financing_Terms",
) -> dict[str, Any]:
    """Build a minimal debt-engine config with no draw or phasing supplied."""
    terms: dict[str, Any] = {
        "debt_ratio": DEBT_RATIO,
        "tenor_years": 5,
        "rates": {"usd_nominal": RATE},
        "mix": {"usd_commercial_min": 1.0},
        **(financing or {}),
    }
    config: dict[str, Any] = {"capex": {"usd_total": CAPEX_USD}, section: terms}
    if timeline_years is not None:
        config["timeline"] = {"construction_years": timeline_years}
    return config


# --- The guard -------------------------------------------------------------------


@pytest.mark.parametrize("section", ["Financing_Terms", "financing", "debt"])
def test_financing_count_disagreeing_with_timeline_is_refused(section: str) -> None:
    """Both declared and different: refused, naming both values."""
    config = _config(
        financing={"construction_periods": 2}, timeline_years=1, section=section
    )

    with pytest.raises(ValueError) as excinfo:
        _resolve_construction_periods(config)
    message = str(excinfo.value)
    assert f"{section}.construction_periods = 2" in message
    assert "timeline.construction_years = 1" in message

    with pytest.raises(ValueError, match="timeline.construction_years = 1"):
        apply_debt_layer(config, annual_rows=[])


def test_legacy_financing_terms_construction_years_is_checked_too() -> None:
    """``Financing_Terms.construction_years`` is a declared count like the other key."""
    config = _config(financing={"construction_years": 3}, timeline_years=2)

    with pytest.raises(
        ValueError, match=r"Financing_Terms.construction_years = 3 .*timeline"
    ):
        _resolve_construction_periods(config)


def test_two_financing_terms_keys_that_disagree_are_refused() -> None:
    """``construction_periods`` and ``construction_years`` must not contradict."""
    config = _config(financing={"construction_periods": 1, "construction_years": 2})

    with pytest.raises(ValueError) as excinfo:
        _resolve_construction_periods(config)
    message = str(excinfo.value)
    assert "Financing_Terms.construction_periods = 1" in message
    assert "Financing_Terms.construction_years = 2" in message


@pytest.mark.parametrize(
    ("financing", "timeline_years", "expected"),
    [
        ({"construction_periods": 1}, 1, 1),
        ({"construction_periods": 2}, 2, 2),
        ({"construction_years": 1}, 1, 1),
        ({"construction_periods": 1, "construction_years": 1}, 1, 1),
        ({"construction_periods": "1.0"}, 1, 1),
        ({}, 1, 1),
        ({}, 3, 3),
        ({}, None, 2),
        ({"construction_periods": 4}, None, 4),
    ],
)
def test_agreeing_or_single_declarations_resolve(
    financing: dict[str, Any], timeline_years: Any, expected: int
) -> None:
    """Agreeing pairs pass; ``timeline`` alone is used; neither keeps the default 2."""
    config = _config(financing=financing, timeline_years=timeline_years)

    assert _resolve_construction_periods(config) == expected
    assert apply_debt_layer(config, annual_rows=[])["construction_periods"] == expected
    if "construction_periods" not in financing:
        # Extraction fills an absent key with the resolved count, never a default.
        assert _extract_financing_terms(config)["construction_periods"] == expected


@pytest.mark.parametrize("section", ["financing", "debt"])
def test_timeline_alone_sets_the_count_for_the_compact_schemas(section: str) -> None:
    """The compact schemas take ``timeline`` too, instead of falling back to two."""
    config = _config(timeline_years=1, section=section)

    assert _resolve_construction_periods(config) == 1
    assert apply_debt_layer(config, annual_rows=[])["construction_periods"] == 1


# --- Placeholders sized to the count ---------------------------------------------


@pytest.mark.parametrize(
    ("periods", "phasing", "draw"),
    [
        (0, [], []),
        (1, [100.0], [0.5]),
        (2, [40.0, 60.0], [0.5, 0.5]),
        (4, [25.0, 25.0, 25.0, 25.0], [0.25, 0.25, 0.25, 0.25]),
    ],
)
def test_placeholders_have_one_entry_per_period(
    periods: int, phasing: list[float], draw: list[float]
) -> None:
    """One entry per period; two periods keep the historical placeholders."""
    assert placeholder_construction_schedule(periods) == phasing
    assert placeholder_debt_drawdown_pct(periods) == draw
    if periods:
        assert sum(phasing) == pytest.approx(100.0)


@pytest.mark.parametrize("periods", [1, 2, 3])
def test_engine_uses_the_sized_placeholders(periods: int) -> None:
    """With no draw or phasing supplied, the engine publishes the sized placeholders."""
    config = _config(timeline_years=periods)

    result = apply_debt_layer(config, annual_rows=[])
    terms = _extract_financing_terms(config)

    assert result["construction_schedule"] == placeholder_construction_schedule(periods)
    assert len(result["construction_schedule"]) == periods
    assert terms["debt_drawdown_pct"] == placeholder_debt_drawdown_pct(periods)


# --- The IDC convention, as closed forms ---------------------------------------


def test_one_year_build_capitalises_half_a_years_interest() -> None:
    """One period, placeholder draw: IDC = 0.5 * D * r (the average-balance figure)."""
    result = apply_debt_layer(_config(timeline_years=1), annual_rows=[])

    assert result["total_idc_capitalized"] == pytest.approx(0.5 * DEBT_USD * RATE)
    assert result["principal_after_idc"]["USD"] == pytest.approx(
        DEBT_USD * (1.0 + 0.5 * RATE)
    )


def test_two_year_build_keeps_the_start_of_period_convention() -> None:
    """Two periods, ``[0.5, 0.5]``: each draw accrues a full period, compounded."""
    first = 0.5 * DEBT_USD * RATE
    second = (DEBT_USD + first) * RATE
    result = apply_debt_layer(_config(timeline_years=2), annual_rows=[])

    assert result["total_idc_capitalized"] == pytest.approx(first + second)


def test_idc_responds_to_the_declared_build_time() -> None:
    """Responsiveness: the same financing terms give a different IDC per build time."""
    one = apply_debt_layer(_config(timeline_years=1), annual_rows=[])
    two = apply_debt_layer(_config(timeline_years=2), annual_rows=[])

    assert one["construction_periods"] == 1
    assert two["construction_periods"] == 2
    assert two["total_idc_capitalized"] > one["total_idc_capitalized"] > 0.0


# --- Every committed scenario -----------------------------------------------------


def _committed_scenarios() -> list[Path]:
    return sorted(SCENARIOS.glob("*.yaml"))


def _load(path: Path) -> dict[str, Any] | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


@pytest.mark.parametrize("path", _committed_scenarios(), ids=lambda p: p.name)
def test_committed_scenario_count_equals_its_declared_build_time(path: Path) -> None:
    """No committed scenario runs on a count other than the build time it declares."""
    config = _load(path)
    if config is None:
        pytest.skip("not a single-document mapping")
    timeline = config.get("timeline")
    declared = (
        timeline.get("construction_years") if isinstance(timeline, dict) else None
    )

    count = _resolve_construction_periods(config)

    if declared is not None:
        assert count == int(declared)


def test_superseded_hybrid_runs_on_its_declared_one_year_build() -> None:
    """The hybrid declares one year in ``timeline`` only, and now runs on one."""
    config = _load(SCENARIOS / "blue_whale_hybrid_lot5b_2026.yaml")
    assert config is not None
    assert config["timeline"]["construction_years"] == 1
    assert "construction_periods" not in config["Financing_Terms"]

    assert _resolve_construction_periods(config) == 1

    altered = copy.deepcopy(config)
    altered["timeline"]["construction_years"] = 2
    assert _resolve_construction_periods(altered) == 2
