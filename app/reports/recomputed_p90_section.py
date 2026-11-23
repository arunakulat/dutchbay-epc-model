"""The recomputed P90 cover of the committed debt, for the lender report (#1895).

Owner ruling on #1895 (option A, 22 Nov 2026): keep the P50 sizing and disclose the
recomputed P90 cover. The lender report prints it in the debt table, beside the sizing
downside. The figures come from
:func:`analytics.finance.p90_recomputed_downside.recomputed_p90_downside` (#1836): the
scenario re-run at P90 energy, set against the committed debt and taxed on its interest.

When the scenario declares the opt-in ``Financing_Terms.p90_cover_min_dscr`` and it bound,
the committed debt is the debt priced at the raised target, so the cover is measured on
that debt (:func:`analytics.finance.p90_cover.priced_config`).

The figures are a modelled one-year exceedance on the scenario's own resource basis, not a
lender P90 claim (F-5). Annual figures only.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Union

from pydantic import BaseModel

SECTION_RECOMPUTED_P90 = "Recomputed P90 cover"


class RecomputedP90Block(BaseModel):
    """The recomputed P90 case against the committed debt, as the report prints it."""

    min_dscr: float
    avg_dscr: Optional[float] = None
    llcr: Optional[float] = None
    ratio_method_min_dscr: Optional[float] = None
    p90_over_p50: float
    label: str


RecomputeFn = Callable[[Mapping[str, Any]], Mapping[str, Any]]


def build_recomputed_p90_block(
    scenario: Mapping[str, Any],
    result: Mapping[str, Any],
    recompute: Optional[RecomputeFn] = None,
) -> Union[RecomputedP90Block, str]:
    """The block for ``scenario``, or a ``not run: ...`` reason.

    Args:
        scenario: The scenario as loaded for the report.
        result: The finance run's result; its ``debt_result["p90_cover"]`` says whether a
            declared cover moved the sizing target.
        recompute: Seam for tests; production uses
            :func:`analytics.finance.p90_recomputed_downside.recomputed_p90_downside`.
    """
    from analytics.finance.p90_cover import priced_config

    if recompute is None:
        from analytics.finance.p90_recomputed_downside import recomputed_p90_downside

        recompute = recomputed_p90_downside
    debt = result.get("debt_result")
    block = debt.get("p90_cover") if isinstance(debt, Mapping) else None
    check = recompute(priced_config(scenario, block))
    if check.get("status") != "ok":
        return (
            f"not run: {check.get('reason', 'the recomputed P90 case is unavailable')}"
        )
    cases = check.get("cases") or {}
    recomputed = cases.get("recomputed") or {}
    ratio = cases.get("ratio_method") or {}
    if recomputed.get("min_dscr") is None:
        return "not run: the recomputed P90 case has no minimum DSCR"
    return RecomputedP90Block(
        min_dscr=float(recomputed["min_dscr"]),
        avg_dscr=recomputed.get("avg_dscr"),
        llcr=recomputed.get("llcr"),
        ratio_method_min_dscr=ratio.get("min_dscr"),
        p90_over_p50=float(check["p90_over_p50"]),
        label=str(check.get("label") or ""),
    )


__all__ = [
    "RecomputedP90Block",
    "SECTION_RECOMPUTED_P90",
    "build_recomputed_p90_block",
]
