"""Dedicated schema-guard tests for cashflow parameter validation (v14).

GWTF compliance (rule R22 / CESSPIT ``FRAMEWORK-02``): invalid configs are
covered here by asserting that ``validate_parameters`` *fails fast*, **not** by
weakening production validation with a ``strict=False`` bypass. ``validate_parameters``
is exercised only in its production (strict) mode:

* a v14-compliant config validates cleanly (returns an empty error list);
* a config missing any single required field raises ``ValueError``.

Tracking: issue #133 / PR #134.
"""

from __future__ import annotations

import copy
from typing import Any, Callable

import pytest

from finance.cashflow_v14_params import validate_parameters

# A minimal v14-compliant cashflow config. Mirrors the known-good shape used by
# tests/api/test_cashflow_module.py::test_build_annual_cfads_minimal_valid_params.
COMPLIANT_CONFIG: dict[str, Any] = {
    "project": {
        "capacity_mw": 100.0,
        "capacity_factor": 0.40,
        # Explicit, supported life field — do NOT rely on the heuristic
        # path-substring fallback in _extract_project_life_years.
        "project_life_years": 20,
    },
    "tariff": {
        "lkr_per_kwh": 20.0,
    },
    "opex": {
        "usd_per_year": 3_000_000.0,
    },
    "tax": {
        "corporate_tax_rate": 0.30,
        "depreciation_years": 15,
    },
}


def _drop(*path: str) -> Callable[[dict[str, Any]], None]:
    """Build a mutator that removes the config entry at ``path`` in place."""

    def _mutator(cfg: dict[str, Any]) -> None:
        cursor: Any = cfg
        for key in path[:-1]:
            cursor = cursor.get(key, {})
        if isinstance(cursor, dict):
            cursor.pop(path[-1], None)

    return _mutator


# Each case removes exactly one required field from a compliant config so the
# validator must reject it. id == the field whose absence must fail validation.
REQUIRED_FIELD_REMOVALS: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
    ("corporate_tax_rate", _drop("tax", "corporate_tax_rate")),
    ("capacity_factor", _drop("project", "capacity_factor")),
    ("capacity_mw", _drop("project", "capacity_mw")),
    ("tariff_lkr_per_kwh", _drop("tariff")),
    ("opex_usd_per_year", _drop("opex")),
]


def test_compliant_config_validates_clean() -> None:
    """A v14-compliant config passes strict validation with no errors."""
    assert validate_parameters(copy.deepcopy(COMPLIANT_CONFIG)) == []


def test_empty_config_raises() -> None:
    """An empty config fails fast under strict (default) validation."""
    with pytest.raises(ValueError):
        validate_parameters({})


@pytest.mark.parametrize(
    "remove",
    [case for _, case in REQUIRED_FIELD_REMOVALS],
    ids=[name for name, _ in REQUIRED_FIELD_REMOVALS],
)
def test_missing_required_field_raises(
    remove: Callable[[dict[str, Any]], None],
) -> None:
    """Removing any single required field makes strict validation fail fast."""
    cfg = copy.deepcopy(COMPLIANT_CONFIG)
    remove(cfg)
    with pytest.raises(ValueError):
        validate_parameters(cfg)


def test_zero_capacity_factor_validates_clean() -> None:
    """BESS-5 (#486): a storage-only scenario declares capacity_factor 0.0 (its
    revenue is the BESS capacity charge, not generation) — the validator must accept
    a literal 0 rather than the former 0.0001 placeholder."""
    cfg = copy.deepcopy(COMPLIANT_CONFIG)
    cfg["project"]["capacity_factor"] = 0.0
    assert validate_parameters(cfg) == []


def test_negative_capacity_factor_still_rejected() -> None:
    """The relaxed bound only admits 0.0 — a negative CF remains a config error."""
    cfg = copy.deepcopy(COMPLIANT_CONFIG)
    cfg["project"]["capacity_factor"] = -0.1
    with pytest.raises(ValueError):
        validate_parameters(cfg)
