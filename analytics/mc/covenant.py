# analytics/mc/covenant.py

"""Shared DSCR covenant-floor resolution (config-first, CESSPIT).

Single source of truth for the DSCR covenant floor used by BOTH the Monte
Carlo engine (the fixed-debt stress breach test in
``analytics.mc.engine.MonteCarloEngine``) and the CASPER ``mc_risk`` block
(``analytics.casper.casper_payload``). Extracted from ``analytics.mc.engine``
(#639, MOVE -> SHIM: the engine re-exports the resolvers under their original
private names, unchanged), so the two surfaces cannot disagree on which floor
a scenario's breach probability is measured against.

Deliberately dependency-light: stdlib-only — no numpy, no evaluation_v14, no
MC engine — so contracts-facing consumers (CCCDIR: ``casper_payload`` imports
result types only from ``contracts_v14``) can import it without pulling the
heavy MC stack into their import chain. ``analytics.mc.__init__`` is lazy
(PEP 562), so ``import analytics.mc.covenant`` stays light as well.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

#: Engine precedence for the covenant floor (config-first, CESSPIT): the
#: explicit lender covenant wins; the debt-sizing targets are successive
#: fallbacks; the MC-local override comes last.
MIN_DSCR_COVENANT_PATHS: tuple[str, ...] = (
    "constraints.min_dscr_covenant",
    "Financing_Terms.target_dscr",
    "Financing_Terms.min_dscr",
    "monte_carlo.min_dscr_covenant",
)

#: Documented default when no precedence path resolves. Matches
#: ``analytics.mc.exports.CovenantSpec.dscr_floor``.
DEFAULT_MIN_DSCR_COVENANT: float = 1.30


def resolve_config_value(cfg: Mapping[str, Any], dotted: str) -> Optional[float]:
    """Resolve a dotted path to its float base value in cfg, or None if absent/non-numeric."""
    cur: Any = cfg
    for k in dotted.split("."):
        if isinstance(cur, Mapping) and k in cur:
            cur = cur[k]
        else:
            return None
    try:
        return float(cur)
    except (TypeError, ValueError):
        return None


def resolve_min_dscr_covenant(cfg: Mapping[str, Any]) -> float:
    """The DSCR covenant a fixed-debt stress breaches, from the scenario (default 1.30)."""
    for path in MIN_DSCR_COVENANT_PATHS:
        v = resolve_config_value(cfg, path)
        if v is not None:
            return float(v)
    return DEFAULT_MIN_DSCR_COVENANT
