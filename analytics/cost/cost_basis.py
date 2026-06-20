"""Cost-basis year — the single anchored USD vintage for the CAPEX/OPEX stack.

NREL ATB best practice fixes every cost in one base year (2022$) and derives scenario
projections from it. DutchBay's cost figures had drifted across vintages (IRENA 2024,
Lazard 2025, the 2026-Q2 FX), so this anchors ONE basis year, resolved config-first:

    scenario ``capex.cost_basis_year``  ->  else  ``config/defaults.yaml``
    ``defaults.cost_reference.basis_year``

Never a Python literal (CESSPIT / CCCDIR — the default lives in config/). This mirrors
``analytics.fx.fx_fetch.default_fx_lkr_per_usd``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

_DEFAULTS_PATH = Path(__file__).resolve().parents[2] / "config" / "defaults.yaml"


@lru_cache(maxsize=1)
def default_cost_basis_year() -> int:
    """The single config-sourced fallback cost-basis year (config/defaults.yaml)."""
    import yaml  # project core dep

    data = yaml.safe_load(_DEFAULTS_PATH.read_text())
    try:
        return int(data["defaults"]["cost_reference"]["basis_year"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"config/defaults.yaml missing defaults.cost_reference.basis_year "
            f"({_DEFAULTS_PATH})"
        ) from exc


def resolve_cost_basis_year(config: Mapping[str, Any]) -> int:
    """Resolve the USD cost-basis year for a scenario.

    Prefers the scenario's explicit ``capex.cost_basis_year``; falls back to the single
    config-sourced default. Raises if the explicit value is not a valid year.
    """
    capex = config.get("capex")
    if isinstance(capex, Mapping):
        year = capex.get("cost_basis_year")
        if year is not None:
            try:
                return int(year)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"capex.cost_basis_year must be an integer year; got {year!r}"
                ) from exc
    return default_cost_basis_year()


__all__ = ["default_cost_basis_year", "resolve_cost_basis_year"]
