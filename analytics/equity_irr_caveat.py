"""The equity IRR ranking caveat, worded once for every surface that prints equity IRR (#1688).

The owner's #1456 decision was "Optimise on NPV, caveat IRR". The waterfall records whether a
case's equity IRR can rank it (``finance.equity_v14.equity_irr_ranks_reliably``: exactly one
sign change in the equity cash flows) in the opaque ``equity_distribution.equity_summary``,
outside ``kpis``. This module turns that flag into the caveat a reader sees beside equity IRR.
It derives nothing: it reads the flag and the sign-change count the waterfall published, and
it returns no caveat when the flag is absent or True. The caveat stays out of ``kpis``.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

#: The equity summary keys the caveat reads (``finance.equity_distribution_v14_hydra``).
RANKS_RELIABLY_KEY = "equity_irr_ranks_reliably"
SIGN_CHANGES_KEY = "equity_cashflow_sign_changes"


def equity_irr_ranking_caveat(
    ranks_reliably: Any, sign_changes: Any = None
) -> Optional[str]:
    """Return the caveat for an equity IRR that cannot rank its case, or None.

    Args:
        ranks_reliably: The waterfall's ``equity_irr_ranks_reliably`` flag. Only an exact
            ``False`` gives a caveat; ``True``, ``None`` or a missing flag give none.
        sign_changes: The waterfall's ``equity_cashflow_sign_changes`` count, used only to
            word the caveat. Anything other than a non-negative integer is treated as unknown.

    Returns:
        One sentence naming why the equity IRR does not rank the case, and pointing the reader
        to equity NPV, or None.
    """
    if ranks_reliably is not False:
        return None
    count = (
        sign_changes
        if isinstance(sign_changes, int)
        and not isinstance(sign_changes, bool)
        and sign_changes >= 0
        else None
    )
    if count == 0:
        reason = "its equity cash flows never change sign, so no rate solves them"
    elif count is not None and count >= 2:
        reason = (
            f"its equity cash flows change sign {count} times, "
            "so more than one rate, or none, can solve them"
        )
    else:
        reason = "its equity cash flows do not change sign exactly once"
    return (
        f"Equity IRR does not rank this case: {reason}. "
        "Read equity NPV beside it; the model's optimisers rank on equity NPV (#1456)."
    )


def equity_irr_caveat_from_summary(summary: Any) -> Optional[str]:
    """Return the caveat from a waterfall ``equity_summary`` (or equity metadata) mapping."""
    if not isinstance(summary, Mapping):
        return None
    return equity_irr_ranking_caveat(
        summary.get(RANKS_RELIABLY_KEY), summary.get(SIGN_CHANGES_KEY)
    )


def equity_irr_caveat_from_run(run_result: Optional[Mapping[str, Any]]) -> Optional[str]:
    """Return the caveat from a ``run_v14_pipeline`` result, or None when it carries no flag."""
    if not isinstance(run_result, Mapping):
        return None
    distribution = run_result.get("equity_distribution")
    if not isinstance(distribution, Mapping):
        return None
    return equity_irr_caveat_from_summary(distribution.get("equity_summary"))
