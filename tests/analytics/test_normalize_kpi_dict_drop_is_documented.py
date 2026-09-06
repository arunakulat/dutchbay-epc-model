"""Pin ``normalize_kpi_dict``'s drop behaviour to what its docstring claims.

The docstring and the code disagreed once: the docstring said the function
"logs warnings for skipped entries" while the code emitted ``logger.debug``.
Nothing caught it, because no test observed the log level at all.  These
controls make the disagreement impossible to reintroduce silently.

Raising the level is deliberately *not* the fix.  ``normalize_kpi_dict`` runs on
the ``return_full_result=False`` default path of the sole evaluation gateway,
which Monte Carlo, sensitivity, tornado, solver and optimizer loops call
per-iteration; a warning per dropped entry would flood them.
"""

from __future__ import annotations

import logging

import pytest

from analytics.evaluation_v14 import normalize_kpi_dict


def test_non_numeric_entries_are_dropped_not_defaulted() -> None:
    """A non-convertible KPI is absent, never zero-filled or defaulted."""
    out = normalize_kpi_dict(
        {"project_irr": 0.145, "status": "N/A", "min_dscr": "1.45", "note": None}
    )

    assert out == {"project_irr": 0.145, "min_dscr": 1.45}
    # The dangerous failure mode is a silent 0.0, which would read as a
    # computed value downstream.  Prove the keys are gone, not zeroed.
    assert "status" not in out
    assert "note" not in out


def test_the_drop_is_logged_at_debug_and_not_at_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The drop is DEBUG-only, exactly as the docstring now states.

    This is the negative control for the documentation claim: if someone raises
    the level to WARNING without updating the docstring and the call-site
    reasoning, this fails.
    """
    with caplog.at_level(logging.DEBUG, logger="analytics.evaluation_v14"):
        normalize_kpi_dict({"good": 1.0, "bad": "N/A"})

    dropped = [
        r for r in caplog.records if "skipping non-numeric KPI" in r.getMessage()
    ]
    assert dropped, "the drop must be logged at all, or it is wholly unobservable"
    assert all(r.levelno == logging.DEBUG for r in dropped)
    assert not [r for r in dropped if r.levelno >= logging.WARNING]


def test_docstring_documents_the_silent_drop_and_the_caller_side_remedy() -> None:
    """The docstring must not claim an observability this function does not give.

    Pins the three facts a caller relies on: the drop is DEBUG-only, it is
    therefore silent in ordinary operation, and ``return_full_result=True`` is
    the way to avoid it.
    """
    doc = normalize_kpi_dict.__doc__ or ""

    assert "DEBUG" in doc
    assert "silent in ordinary" in doc
    assert "return_full_result=True" in doc
    # The prior wording claimed warnings; it must not come back.
    assert "logs warnings" not in doc
