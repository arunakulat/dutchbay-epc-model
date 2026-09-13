"""Pin ``normalize_kpi_dict``'s drop behaviour to what its docstring claims.

The docstring and the code disagreed once: the docstring said the function
"logs warnings for skipped entries" while the code emitted ``logger.debug``.
Nothing caught it, because no test observed the log level at all.

Two later rounds of independent review each broke the controls that replaced
it, and each break is pinned below:

* Round one produced three survivors -- a *second* ``logger.warning`` per
  dropped entry (the flood the design exists to prevent), a child-logger
  warning, and the false claim paraphrased as "logs a warning for each skipped
  entry".
* Round two broke the replacements too.  A literal-phrase ban on ``log ...
  warn`` was escaped by seven of nine natural phrasings, among them "emits a
  warning to the operator log" and "warns on each skipped entry".  A logging
  call routed through ``logging.getLogger("kpi_drops")`` escaped *both* halves
  of the level oracle: the AST half matched only attributes reached through the
  bare name ``logger``, and the runtime half filtered captured records by
  logger name.

* Round three broke them again, twice over.  The counterfactual marker was any
  ``not`` anywhere in the sentence, so "the caller is warned about every entry
  that could not be converted" passed on a negation of *conversion*; and the
  emission-verb list held only present-tense forms, so "is also logged at
  ``WARNING`` level" and "is surfaced at ``WARNING`` level" passed as well.

So the two oracles below are written against the defect class rather than
against the wordings that were tried:

* **Code half** -- every logging call reached by attribute access in the except
  handler is matched on its *method name*, whatever object it is reached
  through.  Forms that do not go through an attribute (a bound-method alias, a
  ``getattr`` lookup) escape this half and are caught by the runtime half
  instead; the two cover each other.
* **Docstring half** -- in any sentence mentioning a warning, a rejection
  marker must sit within three tokens of the warn token, and no emission verb
  may appear.

**What these controls do and do not establish.**  They pin the *code*'s
behaviour, and they reject every phrasing that three rounds of independent
review produced.  They do **not** pin the *polarity* of a prose claim in
general: the docstring's direction of assertion is unchecked except where a
named control checks it, so an inverted sentence elsewhere in the docstring can
still pass.  A known residue survives even the warning gate -- a double negative
("operators are not left without a warning") satisfies the proximity rule while
asserting the opposite of the truth.  Review remains the backstop; this file
narrows what review has to catch, and does not replace it.

Raising the level is deliberately *not* the fix.  ``normalize_kpi_dict`` runs on
the ``return_full_result=False`` default path of :func:`evaluate_with_overrides`,
which Monte Carlo, sensitivity, tornado and optimizer loops call per-iteration.
"""

from __future__ import annotations

import ast
import inspect
import logging
import re
import textwrap
from decimal import Decimal
from fractions import Fraction

import pytest

from analytics.evaluation_v14 import normalize_kpi_dict

_LOGGER_NAME = "analytics.evaluation_v14"

# Every stdlib logging emission method.  Matched on the method name alone, so a
# call reached through ``logger``, ``logger.getChild(...)`` or
# ``logging.getLogger(...)`` is caught identically.
_LOG_METHODS = frozenset(
    {"debug", "info", "warning", "warn", "error", "critical", "exception", "log"}
)


def _logging_calls_in_except_handler() -> list[str]:
    """Return every logging call reached by ATTRIBUTE ACCESS in the handler.

    Derived from the live source, so the assertions below track the code rather
    than restating it.  The match is on the attribute name and ignores the
    receiver, so ``logger.warning``, ``logger.getChild(..).warning`` and
    ``logging.getLogger(..).warning`` are caught alike; an earlier version
    required ``ast.Name`` with ``id == "logger"`` and a fresh logger walked past
    it.

    It is deliberately not exhaustive over *all* emission forms.  A bound-method
    alias (``fn = logger.warning``) and a ``getattr(logger, "warning")`` lookup
    are not attribute calls at the call site and are invisible here; both are
    caught by :func:`test_no_warning_or_above_escapes_this_function`, which
    observes records rather than syntax.  Neither half is sufficient alone.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(normalize_kpi_dict)))
    return sorted(
        node.func.attr
        for handler in ast.walk(tree)
        if isinstance(handler, ast.ExceptHandler)
        for node in ast.walk(handler)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _LOG_METHODS
    )


def _caught_exception_source() -> str:
    """Return the exception tuple the drop handler catches, unparsed from source."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(normalize_kpi_dict)))
    (handler,) = [h for h in ast.walk(tree) if isinstance(h, ast.ExceptHandler)]
    assert handler.type is not None, "a bare except would swallow everything"
    return ast.unparse(handler.type)


def test_only_typeerror_and_valueerror_are_caught() -> None:
    """The docstring's propagation claim, pinned on both sides.

    Two independent reviewers found the same hole: widening the handler to
    ``except Exception:`` silently falsified the docstring's ``OverflowError``
    sentence while all ten controls stayed green -- precisely the defect class
    this file exists to close.  So the caught tuple is derived from the source,
    and the behaviour it produces is exercised.
    """
    assert ast.dump(ast.parse(_caught_exception_source(), mode="eval")) == ast.dump(
        ast.parse("(TypeError, ValueError)", mode="eval")
    ), f"the handler now catches {_caught_exception_source()!r}"

    # An out-of-range int raises OverflowError, which is NOT caught: it must
    # propagate rather than be dropped.
    with pytest.raises(OverflowError):
        normalize_kpi_dict({"huge": 10**400})

    assert "OverflowError" in (normalize_kpi_dict.__doc__ or "")


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

    This is one of the input classes that produces the silent ``0.0`` the test
    above guards against, and it is *not* dropped.  Changing the runtime
    behaviour is out of scope here; going undocumented is what this control
    prevents.
    """
    out = normalize_kpi_dict({"wacc_is_real": False, "flag_on": True})

    assert out == {"wacc_is_real": 0.0, "flag_on": 1.0}
    assert isinstance(out["wacc_is_real"], float)


def _casper_kpi_predicate_source() -> str:
    """Return CASPER's baseline-KPI admission test, unparsed from its source.

    The divergence documented on ``normalize_kpi_dict`` is a claim about
    *another* module, so it is read from that module rather than restated.  If
    CASPER changes which entries it admits, this returns something else and the
    control below fails, sending the docstring back for review.
    """
    from analytics.casper import casper_payload

    tree = ast.parse(inspect.getsource(casper_payload))
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef) or fn.name != "build_casper_payload":
            continue
        for node in ast.walk(fn):
            # Selected by ASSIGNMENT TARGET, not by walk order.  ``ast.walk`` is
            # breadth-first, so an unrelated comprehension at the function's top
            # level was found before this one, which sits inside an ``if``: the
            # control then failed with a misleading diagnosis naming a predicate
            # CASPER never used.
            if not isinstance(node, ast.Assign) or not isinstance(
                node.value, ast.DictComp
            ):
                continue
            targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if "baseline_kpis" not in targets:
                continue
            ifs = node.value.generators[0].ifs
            assert ifs, "CASPER's baseline-KPI comprehension no longer filters"
            return ast.unparse(ifs[0])
    raise AssertionError("CASPER's baseline-KPI assignment was not found")


def test_the_casper_divergence_is_one_way_and_wider_than_bool() -> None:
    """The documented divergence must be the one the two normalizers produce.

    The docstring claimed once that the two "disagree by exactly those keys",
    meaning bools.  The inference was false, and falsifiable end-to-end: a
    scenario whose ``name`` is ``"2030"`` arrives here as the phantom numeric
    KPI ``scenario_name=2030.0`` and is absent from the CASPER payload.
    ``float()`` also accepts ``Decimal`` and ``Fraction``, neither of which
    satisfies CASPER's ``isinstance`` test.
    """
    expected = "isinstance(v, (int, float)) and not isinstance(v, bool)"
    actual = _casper_kpi_predicate_source()
    # Compared as trees, so ``ast.unparse``'s parenthesisation (which varies by
    # Python version) cannot fail the control on formatting alone.
    assert ast.dump(ast.parse(actual, mode="eval")) == ast.dump(
        ast.parse(expected, mode="eval")
    ), (
        f"CASPER's admission rule moved to {actual!r}; the documented divergence "
        "must be re-derived"
    )

    raw: dict[str, object] = {
        "project_irr": 0.145,  # float      -> both
        "term_years": 20,  # int        -> both
        "wacc_is_real": False,  # bool       -> here only
        "scenario_name": "2030",  # str        -> here only
        "hurdle": Decimal("0.12"),  # Decimal    -> here only
        "equity_share": Fraction(1, 4),  # Fraction   -> here only
        "status": "N/A",  # unparseable -> neither
    }

    ours = normalize_kpi_dict(raw)
    theirs = {
        str(k): float(v)
        for k, v in raw.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }

    # Strictly wider, and wider by more than the bools.
    assert set(theirs) < set(ours)
    assert set(ours) - set(theirs) == {
        "wacc_is_real",
        "scenario_name",
        "hurdle",
        "equity_share",
    }
    assert ours["scenario_name"] == 2030.0  # the phantom KPI, pinned

    # The docstring restates CASPER's rule in prose.  That restatement was
    # compared to nothing, so misstating it as ``isinstance(v, float)`` passed
    # every control.  Pin the prose to the source: every ``...`` span in the
    # docstring that parses as an expression is compared as a TREE, so the
    # restatement may be parenthesised however reads best.
    normalised_doc = " ".join((normalize_kpi_dict.__doc__ or "").split())
    quoted = re.findall(r"``([^`]+)``", normalised_doc)
    restated: list[str] = []
    for span in quoted:
        try:
            restated.append(ast.dump(ast.parse(span, mode="eval")))
        except SyntaxError:
            continue
    assert ast.dump(ast.parse(actual, mode="eval")) in restated, (
        f"docstring does not restate CASPER's actual admission rule {actual!r}; "
        "prose and source must agree, not merely coexist"
    )

    # One-directional: nothing CASPER admits is lost here, values included.
    for key, value in theirs.items():
        assert ours[key] == value

    # The prose half.  "Disagree by exactly those keys" was the false claim, so
    # naming bool alone is not enough: the wider classes must be named too.
    doc = normalize_kpi_dict.__doc__ or ""
    for token in ("Decimal", "Fraction", "2030"):
        assert token in doc, (
            f"docstring omits {token!r}: the divergence is wider than bool and "
            "must not be documented as bool-only"
        )


def test_no_warning_or_above_escapes_this_function(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No record at WARNING or above may be emitted during a drop, by anyone.

    Asserted over the *whole* capture, deliberately unfiltered by logger name.
    The previous version scoped it to ``analytics.evaluation_v14``, and a
    handler line routed through ``logging.getLogger("kpi_drops")`` passed it
    while flooding the operator log once per dropped entry per iteration.
    Only this function runs inside the block, so any WARNING+ record is its own.
    """
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        normalize_kpi_dict({"good": 1.0, "bad": "N/A", "worse": None})

    loud = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert not loud, f"expected no WARNING+ during the call, got {loud!r}"


def test_the_drop_is_logged_at_debug(caplog: pytest.LogCaptureFixture) -> None:
    """The drop is observable at DEBUG, and only at DEBUG."""
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        normalize_kpi_dict({"good": 1.0, "bad": "N/A"})

    dropped = [r for r in caplog.records if "non-numeric KPI" in r.getMessage()]
    assert dropped, "the drop must be logged at all, or it is wholly unobservable"
    assert all(r.levelno == logging.DEBUG for r in dropped)


def test_source_emits_exactly_one_debug_call_in_the_handler() -> None:
    """The except handler logs once, at debug — the fact the docstring states.

    This is the code half of the two-sided oracle, and it is receiver-agnostic:
    a second logging call at any level, through any logger object, or a level
    change, fails here regardless of how the docstring is worded.
    """
    assert _logging_calls_in_except_handler() == ["debug"]


def test_docstring_names_the_level_the_source_actually_uses() -> None:
    """The docstring half: it must name the level the source emits.

    Derived rather than pinned, so prose and behaviour cannot drift apart on
    *this* fact.
    """
    (level,) = _logging_calls_in_except_handler()
    doc = normalize_kpi_dict.__doc__ or ""

    assert level.upper() in doc, f"docstring does not name the emitted level {level!r}"


# A mention of a warning is legitimate only where the docstring is explaining
# why one is *not* emitted.  Both conditions must hold for every such sentence.
#
# The marker must SCOPE OVER the warn token, not merely share a sentence with
# it.  An earlier version accepted any `\bnot\b` anywhere in the sentence, and
# review found the obvious consequence: "The caller is warned about every entry
# that could not be converted" passed, because `not` negated *conversion* — a
# word this function's own subject matter supplies constantly.  Proximity is the
# fix: the marker must sit within three tokens of the warn token, on either side.
_MARKER = r"(?:would|rather\s+than|instead\s+of|never|no|not)"
_GAP = r"(?:\s+\w+){0,3}"
_MARKER_THEN_WARN = rf"{_MARKER}{_GAP}\s+warn\w*"
_WARN_THEN_MARKER = rf"warn\w*{_GAP}\s+{_MARKER}"
_SCOPED_REJECTION = re.compile(
    f"{_MARKER_THEN_WARN}|{_WARN_THEN_MARKER}", re.IGNORECASE
)
# Past participles included: review escaped the present-tense-only list with
# "is also logged at WARNING level" and "is surfaced at WARNING level".
_EMISSION_VERB = re.compile(
    r"\b(?:emit|emits|emitted|log|logs|logged|warn|warns|warned|write|writes"
    r"|written|record|records|recorded|issue|issues|issued|produce|produces"
    r"|produced|send|sends|sent|report|reports|reported|raise|raises|raised"
    r"|surface|surfaces|surfaced|trigger|triggers|triggered|accompany"
    r"|accompanies|accompanied|see|sees|seen)\b",
    re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def test_docstring_makes_no_warning_level_claim() -> None:
    """No claim of warning-level observability may reappear, in any wording.

    The first control banned the literal ``"logs warnings"``; paraphrasing it
    restored the defect.  The second banned ``log ... warn``; seven of nine
    natural phrasings escaped, including "emits a warning to the operator log".

    So the ban is on the *claim*: every sentence mentioning a warning must
    carry a counterfactual marker (``would``/``rather than``/``instead of``/
    ``not``) **and** must make no present-tense emission claim.  Either
    condition alone is escapable -- "emits a warning, not a debug record"
    satisfies the first, and "a warning accompanies each dropped entry"
    satisfies the second.
    """
    doc = normalize_kpi_dict.__doc__ or ""

    offending: list[tuple[str, str]] = []
    for sentence in _sentences(doc):
        if not re.search(r"\bwarn\w*", sentence, re.IGNORECASE):
            continue
        if not _SCOPED_REJECTION.search(sentence):
            offending.append(("marker does not scope over the warning", sentence))
        elif _EMISSION_VERB.search(sentence):
            offending.append(("emission claim", sentence))

    assert not offending, f"docstring asserts warning-level logging: {offending!r}"


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

    # The claim must sit in the SAME SENTENCE as the callers it is about.
    # Searching the whole docstring was not enough: the heading "The remedy
    # exists on one caller only" satisfied the anchor on its own, so inverting
    # the boundary sentence to "the other two callers accept the same parameter"
    # left every control green while asserting the opposite of the truth.
    unavailable = re.compile(
        r"no such parameter|have no remedy|has no remedy|no remedy"
        r"|cannot (?:use|pass|set)|lacks? (?:the )?remedy",
        re.IGNORECASE,
    )
    sentences = _sentences(doc)
    for name in without_remedy:
        mentioning = [s for s in sentences if name in s]
        assert mentioning, f"docstring omits a caller lacking the remedy: {name}"
        assert any(unavailable.search(s) for s in mentioning), (
            f"docstring names {name} but no sentence mentioning it states that the "
            f"remedy is unavailable there; sentences were {mentioning!r}"
        )

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
