"""Cost-of-equity (ke) band sensitivity for the build-up WACC discount rate.

For a post-default frontier market like Sri Lanka there is no single defensible
cost of equity, and the project NPV sits on a knife-edge against the project IRR.
This sweeps ke, recomputes the build-up WACC (from the ACTUAL sized debt), and
reports the resulting project + equity NPV so the swing is explicit rather than
buried in one hardcoded discount rate.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from analytics.evaluation_v14 import evaluate_with_overrides


def ke_band_npv(
    config_path: str,
    ke_values: Sequence[float],
    *,
    base_overrides: Optional[Mapping[str, Any]] = None,
) -> List[Dict[str, float]]:
    """Project/equity NPV + WACC across a cost-of-equity band (build_up mode).

    Args:
        config_path: Path to a v14 scenario config.
        ke_values: Cost-of-equity values to sweep (decimals, e.g. ``[0.12, 0.15]``).
        base_overrides: Extra dotted overrides applied at every point.

    Returns:
        One row per ke with ``ke``, ``wacc`` (achieved discount rate), ``project_npv``,
        ``equity_npv``, ``project_irr``, ``equity_irr`` — all floats.
    """
    rows: List[Dict[str, float]] = []
    for ke in ke_values:
        overrides: Dict[str, Any] = dict(base_overrides or {})
        overrides["wacc.mode"] = "build_up"
        overrides["wacc.drives_discount_rate"] = True
        overrides["wacc.cost_of_equity"] = float(ke)
        kpis = evaluate_with_overrides(config_path, overrides=overrides)
        rows.append(
            {
                "ke": float(ke),
                "wacc": float(kpis.get("discount_rate_used", 0.0)),
                "project_npv": float(kpis.get("project_npv", 0.0)),
                "equity_npv": float(kpis.get("equity_npv", 0.0)),
                "project_irr": float(kpis.get("project_irr", 0.0)),
                "equity_irr": float(kpis.get("equity_irr", 0.0)),
            }
        )
    return rows


__all__ = ["ke_band_npv"]
