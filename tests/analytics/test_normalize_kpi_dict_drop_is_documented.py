"""Pin ``normalize_kpi_dict``'s drop behaviour to what its docstring claims.

The docstring and the code disagreed once: the docstring said the function
"logs warnings for skipped entries" while the code emitted ``logger.debug``.
Nothing caught it, because no test observed the log level at all.

The first version of these controls did not catch that regression class either.
Independent review produced three surviving mutants: adding a *second*
``logger.warning`` per dropped entry passed all controls (the flood the design
exists to prevent), as did a child-logger warning, as did paraphrasing the
false claim as "logs a warning for each skipped entry".  The controls below are
rewritten so that each of those fails.

The rule that makes them hold: the documented level is **derived from the
source** rather than pinned as prose, so the docstring and the code cannot
drift apart independently.

Raising the level is deliberately *not* the fix.  ``normalize_kpi_dict`` runs on
the ``return_full_result=False`` default path of the sole evaluation gateway,
which Monte Carlo, sensitivity, tornado, solver and optimizer loops call
per-iteration; a warning per dropped entry would flood them.
"""

from __future__ import annotations

import ast
import inspect
import logging
import re
import textwrap

import pytest

from analytics.evaluation_v14 import normalize_kpi_dict

_LOGGER_NAME = "analytics.evaluation_v14"


def _logging_calls_in_except_handler() -> list[str]:
    """Return the ``logger.<level>`` method names called in the except handler.

    Derived from the live source, so the assertions below track the code rather
    than restating it.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(normalize_kpi_dict)))
    return [
        node.func.attr
        for handler in ast.walk(tree)
        if isinstance(handler, ast.ExceptHandler)
        for node in ast.walk(handler)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "logger"
    ]


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


def test_a_bool_is_coerced_not_dropped() -> None:
    """``float(False)`` succeeds, so a bool becomes a finite number.

    This is the one input class that actually produces the silent ``0.0`` the
    test above guards against, and it is *not* dropped.  Pinned as known
    divergence: ``analytics.casper.casper_payload`` excludes ``bool`` from the
    same raw dict, so the two normalizers disagree by exactly these keys.
    Changing the runtime behaviour is out of scope here; going undocumented is
    what this control prevents.
    """
    out = normalize_kpi_dict({"wacc_is_real": False, "flag_on": True})

    assert out == {"wacc_is_real": 0.0, "flag_on": 1.0}
    assert isinstance(out["wacc_is_real"], float)


def test_no_warning_or_above_escapes_this_function(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No record at WARNING or above may come from this module during a drop.

    Asserted over the *unfiltered* capture.  The earlier version scoped this to
    records already asserted to be DEBUG, which made it dead code: a second,
    differently-worded ``logger.warning`` per dropped entry passed it.  That is
    precisely the per-iteration flood the design rejects.
    """
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        normalize_kpi_dict({"good": 1.0, "bad": "N/A", "worse": None})

    loud = [
        r
        for r in caplog.records
        if r.levelno >= logging.WARNING and r.name.startswith(_LOGGER_NAME)
    ]
    assert not loud, f"expected no WARNING+ from {_LOGGER_NAME}, got {loud!r}"


def test_the_drop_is_logged_at_debug(caplog: pytest.LogCaptureFixture) -> None:
    """The drop is observable at DEBUG, and only at DEBUG."""
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        normalize_kpi_dict({"good": 1.0, "bad": "N/A"})

    dropped = [r for r in caplog.records if "non-numeric KPI" in r.getMessage()]
    assert dropped, "the drop must be logged at all, or it is wholly unobservable"
    assert all(r.levelno == logging.DEBUG for r in dropped)


def test_source_emits_exactly_one_debug_call_in_the_handler() -> None:
    """The except handler logs once, at debug — the fact the docstring states.

    This is the code half of the two-sided oracle.  A second logging call at any
    level, or a level change, fails here regardless of how the docstring is
    worded.
    """
    assert _logging_calls_in_except_handler() == ["debug"]


def test_docstring_names_the_level_the_source_actually_uses() -> None:
    """The docstring half: it must name the level the source emits.

    Derived rather than pinned, so prose and behaviour cannot drift apart.
    """
    (level,) = _logging_calls_in_except_handler()
    doc = normalize_kpi_dict.__doc__ or ""

    assert level.upper() in doc, f"docstring does not name the emitted level {level!r}"


def test_docstring_makes_no_warning_level_claim() -> None:
    """No claim of warning-level observability may reappear, in any wording.

    The earlier control banned the literal ``"logs warnings"``.  Paraphrasing it
    as "logs a warning for each skipped entry" restored the original defect with
    every control green, so the ban is now claim-level.
    """
    doc = normalize_kpi_dict.__doc__ or ""

    offending = re.findall(r"log\w*\s+(?:a\s+|the\s+)?warn\w*", doc, re.IGNORECASE)
    assert not offending, f"docstring claims warning-level logging: {offending!r}"


def _callers_and_their_remedy() -> dict[str, bool]:
    """Map each function calling ``normalize_kpi_dict`` to whether it has the remedy.

    Derived from the module source: a caller "has the remedy" when it accepts a
    ``return_full_result`` parameter the caller can set.  This is the code half
    of the remedy oracle.
    """
    import analytics.evaluation_v14 as module

    tree = ast.parse(inspect.getsource(module))
    out: dict[str, bool] = {}
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls_it = any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "normalize_kpi_dict"
            for n in ast.walk(fn)
        )
        if not calls_it:
            continue
        args = fn.args
        names = {a.arg for a in (*args.args, *args.posonlyargs, *args.kwonlyargs)}
        out[fn.name] = "return_full_result" in names
    return out


def test_docstring_scopes_the_remedy_to_the_caller_that_has_it() -> None:
    """The remedy must not be promised to callers that cannot use it.

    Two-sided: the callers lacking ``return_full_result`` are derived from the
    source, and the docstring must both name each of them and state that the
    remedy is unavailable there.  Pinning the names alone was not enough — a
    docstring can name a caller while claiming the opposite about it.
    """
    callers = _callers_and_their_remedy()
    doc = normalize_kpi_dict.__doc__ or ""

    with_remedy = sorted(n for n, has in callers.items() if has)
    without_remedy = sorted(n for n, has in callers.items() if not has)

    assert with_remedy, "expected at least one caller to expose the remedy"
    assert without_remedy, (
        "no caller lacks the remedy; the docstring's boundary claim is now stale "
        "and this control must be revisited"
    )

    for name in with_remedy:
        assert name in doc, f"docstring omits the caller that has the remedy: {name}"
    for name in without_remedy:
        assert name in doc, f"docstring omits a caller lacking the remedy: {name}"

    # The claim, not just the names.  Two directions, because prose can assert
    # the boundary in one sentence and contradict it in another.
    assert re.search(
        r"no such parameter|have no remedy|cannot (?:use|pass)|remedy exists on one",
        doc,
        re.IGNORECASE,
    ), "docstring names the callers but does not state that the remedy is unavailable"

    # A universal-availability claim is false while `without_remedy` is
    # non-empty, and must never appear however the rest is worded.
    universal = re.findall(
        r"\b(?:all|every|any|each)\s+callers?\b[^.]*?\b(?:can|may|should|must)\b",
        doc,
        re.IGNORECASE,
    )
    assert not universal, (
        f"docstring claims the remedy is universally available: {universal!r}; "
        f"callers without it: {without_remedy}"
    )


def test_docstring_discloses_the_bool_coercion() -> None:
    """The one input that yields a silent 0.0 must be documented as such."""
    doc = normalize_kpi_dict.__doc__ or ""

    assert "bool" in doc
    assert "wacc_is_real" in doc
