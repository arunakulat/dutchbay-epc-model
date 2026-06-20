"""CAPEX contingency — quantitative risk analysis (AACE RP 119R-21), not a fixed %.

AACE International RP 119R-21 holds that a cost-estimate's contingency/accuracy range
"must be determined through a quantitative risk analysis for each particular estimate";
fixed per-class percentage tables are an explicit *fallback minimum*, usable alone only
when systemic risk dominates (Class 5/10). This module implements the parametric QRA
fallback: contingency sized from the base-cost uncertainty and a target confidence.

Config (``capex.contingency``):
- ``method: qra``   -> contingency = base_cost * (base_cost_uncertainty_pct/100) * z(conf),
  a one-sided parametric draw at ``confidence_level`` (default P80). ``estimate_class``
  (5..1, AACE) is recorded for provenance.
- ``method: fixed`` (default) -> no QRA increment; the caller keeps the explicit
  ``contingency_usd`` line item (backward-compatible).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class ContingencyResult:
    contingency_usd: float
    method: str  # "fixed" | "qra"
    base_cost_usd: float
    estimate_class: Optional[str] = None
    uncertainty_pct: Optional[float] = None
    confidence_level: Optional[float] = None
    z_score: Optional[float] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "contingency_usd": round(self.contingency_usd, 2),
            "base_cost_usd": round(self.base_cost_usd, 2),
            "estimate_class": self.estimate_class,
            "uncertainty_pct": self.uncertainty_pct,
            "confidence_level": self.confidence_level,
            "z_score": None if self.z_score is None else round(self.z_score, 4),
        }


def _contingency_cfg(capex_config: Mapping[str, Any]) -> dict[str, Any]:
    cont = capex_config.get("contingency")
    return dict(cont) if isinstance(cont, Mapping) else {}


def contingency_is_qra(capex_config: Mapping[str, Any]) -> bool:
    return str(_contingency_cfg(capex_config).get("method", "fixed")).lower() == "qra"


def _z_one_sided(confidence: float) -> float:
    """Inverse standard-normal CDF at ``confidence`` (one-sided)."""
    from scipy.stats import norm

    return float(norm.ppf(confidence))


def resolve_contingency(base_cost_usd: float, capex_config: Mapping[str, Any]) -> ContingencyResult:
    """Resolve the CAPEX contingency for a given base cost (excluding contingency)."""
    cont = _contingency_cfg(capex_config)
    method = str(cont.get("method", "fixed")).lower()
    if method != "qra":
        return ContingencyResult(contingency_usd=0.0, method="fixed", base_cost_usd=base_cost_usd)

    if "base_cost_uncertainty_pct" not in cont:
        raise ValueError(
            "capex.contingency.method 'qra' requires 'base_cost_uncertainty_pct' "
            "(1-sigma % on the base cost)"
        )
    sigma_pct = float(cont["base_cost_uncertainty_pct"])
    if sigma_pct < 0:
        raise ValueError("capex.contingency.base_cost_uncertainty_pct must be >= 0")
    conf = float(cont.get("confidence_level", 0.80))
    if not 0.5 <= conf < 1.0:
        raise ValueError("capex.contingency.confidence_level must be in [0.5, 1.0)")

    z = _z_one_sided(conf)
    contingency = base_cost_usd * (sigma_pct / 100.0) * z
    return ContingencyResult(
        contingency_usd=contingency,
        method="qra",
        base_cost_usd=base_cost_usd,
        estimate_class=cont.get("estimate_class"),
        uncertainty_pct=sigma_pct,
        confidence_level=conf,
        z_score=z,
    )


__all__ = ["ContingencyResult", "resolve_contingency", "contingency_is_qra"]
