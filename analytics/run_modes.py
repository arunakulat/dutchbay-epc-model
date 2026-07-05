"""Run-mode contract + policy table for the #733 honesty gate (slice 1 of 3).

The repo already carries several INDEPENDENT honesty gates that decide whether a
run may substitute toy/fabricated numbers and how large a Monte-Carlo sample must
be before its tail statistics are presentable:

* ``analytics.mc.engine`` — per-run ``monte_carlo.allow_toy_fallback`` (default
  ``True``), with ``analytics.mc.aggregate`` disclosing ``toy_fallback_count``;
* ``analytics.capital_risk_layer_v14`` — refuses any toy-contaminated MC result;
* ``app.reports.capital_risk_emit`` — forces ``allow_toy_fallback: false`` and
  enforces the ``LENDER_GRADE_MIN_TRIALS = 1000`` sample floor on the lender path;
* ``finance.debt_v14`` — ``_allow_toy_capex_fallback`` (default ``False``).

Issue #733 unifies those scattered switches behind ONE declared intent: a config
says *what grade of run this is* (``run.mode`` — alias ``run_mode``) and a single
policy table says what that grade permits. The four modes:

* ``screening`` — quick-look triage. Toy fallbacks tolerated; output is for
  sizing a question, never for showing anyone.
* ``developer`` — day-to-day modelling and iteration. Permits everything the
  engines permit today (toy MC fallback is engine-default-on; toy capex stays
  engine OPT-IN — see Assumptions), so a config that declares nothing loses
  nothing.
* ``lender`` — lender-/DD-grade. No toy substitution anywhere (MC trials or
  capex), and the MC sample must meet the lender-grade trial floor.
* ``ic`` — investment-committee grade. Decision-grade rigor, identical gates to
  ``lender``; the distinct ``report_grade`` stamp keeps IC artefacts labelled as
  IC, not lender, output.

Slice-1 scope (#733a): **contract only — nothing consumes this yet; wiring is
#733b/#733c.** The only behavioural surface added anywhere is the opt-in
pre-flight token validation in :mod:`analytics.schema_guard` (CESSPIT: a config
that declares a mode mis-spells it at config time, not at first use — the #601
lesson). A config without ``run.mode``/``run_mode`` resolves to ``None`` and the
model behaves byte-identically to today.

Assumptions and limitations:
    - ``resolve_run_mode`` returns ``None`` for an undeclared mode; it does NOT
      default to ``developer``. Choosing a default posture for undeclared
      configs is a wiring decision deferred to #733b/#733c.
    - ``strict_validation`` is ``True`` for every mode today: no mode relaxes
      the ``validate_config_for_v14`` pre-flight. The field exists so the
      policy surface can express a future relaxation EXPLICITLY instead of via
      a scattered flag.
    - Policy booleans are permission CEILINGS, not default values. On the
      capex axis the ceiling is deliberately LOOSER than the engine default:
      ``allow_toy_capex=True`` (screening/developer) merely declines to forbid
      ``finance.debt_v14``'s toy-capex fallback, which is OPT-IN per config
      (``_allow_toy_capex_fallback`` defaults ``False``). **#733b/#733c wiring
      MUST NOT apply ``allow_toy_capex=True`` as a default-on: it may only
      widen where the config already opted in, or the wiring must keep the
      debt engine's opt-in semantics.** ``False`` (lender/IC) is the hard
      gate — it forbids the fallback even where a config opted in. The MC
      axis has no such inversion hazard (``monte_carlo.allow_toy_fallback``
      already defaults ``True`` in the engine).
    - :data:`LENDER_GRADE_MIN_TRIALS` (1000) is deliberately DUPLICATED from
      ``app.reports.capital_risk_emit.LENDER_GRADE_MIN_TRIALS``: importing the
      app module drags the report stack (FastAPI response models, jinja2
      renderer) into the analytics layer and inverts the app→analytics
      dependency direction (CCCDIR). A test pins the two constants equal via a
      lazy import (``tests/analytics/test_run_modes.py``).
    - The policy table governs run POSTURE only; it does not (and will not)
      alter any finance mathematics — a lender run computes the same numbers,
      it just refuses fabricated inputs and thin samples.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, unique
from types import MappingProxyType
from typing import Any, Optional

__all__ = [
    "LENDER_GRADE_MIN_TRIALS",
    "POLICIES",
    "RunMode",
    "RunModePolicy",
    "resolve_run_mode",
]

#: Lender-grade minimum MC trial count (CESSPIT floor). Duplicated — with a
#: pinned-equality test — from ``app.reports.capital_risk_emit.LENDER_GRADE_MIN_TRIALS``
#: (the #779 lender-report precedent: below ~1000 trials the ~5% VaR/CVaR tail is
#: too thin for a defensible lender number). Duplicated rather than imported
#: because ``app.reports.capital_risk_emit`` imports the app report stack
#: (FastAPI response models + the jinja2 renderer), which must not become an
#: analytics-layer dependency. If you change one, change both — the test
#: ``tests/analytics/test_run_modes.py::test_min_trials_matches_app_lender_floor``
#: fails on drift.
LENDER_GRADE_MIN_TRIALS: int = 1000


@unique
class RunMode(str, Enum):
    """Declared grade of a model run (#733).

    The str mix-in keeps the token YAML/JSON-friendly: ``RunMode.LENDER ==
    "lender"`` and the enum round-trips through its config token.
    """

    SCREENING = "screening"
    DEVELOPER = "developer"
    LENDER = "lender"
    IC = "ic"


@dataclass(frozen=True)
class RunModePolicy:
    """What a declared :class:`RunMode` permits (#733 policy contract).

    Every boolean is a permission CEILING, not a default value: ``True`` means
    the mode does not forbid the behaviour (the engine's own default / opt-in
    semantics still govern); ``False`` means the mode forbids it even where a
    config opted in. See the module Assumptions for the #733b wiring warning.

    Attributes:
        allow_toy_fallback: Whether the mode permits the MC engine to
            substitute a toy Gaussian trial for a failed canonical trial
            (``monte_carlo.allow_toy_fallback`` in ``analytics.mc.engine``,
            engine default ``True``; disclosed as ``toy_fallback_count``).
        allow_toy_capex: Whether the mode permits the debt sizer's toy-capex
            fallback (``finance.debt_v14._allow_toy_capex_fallback`` — engine
            default ``False``, opt-in per config). ``True`` leaves that opt-in
            semantics untouched; ``False`` forbids the fallback even for an
            opted-in config. Wiring MUST NOT apply ``True`` as a default-on.
        min_mc_trials: Minimum Monte-Carlo trial count for the mode's outputs
            to be presentable, or ``None`` for no floor. Lender/IC use
            :data:`LENDER_GRADE_MIN_TRIALS`.
        strict_validation: Whether the ``validate_config_for_v14`` pre-flight
            gate must run strict. ``True`` for every mode today (see the module
            docstring's Assumptions).
        report_grade: Provenance stamp a report built from this run may carry
            (``"screening"`` / ``"developer"`` / ``"lender"`` / ``"ic"``).
    """

    allow_toy_fallback: bool
    allow_toy_capex: bool
    min_mc_trials: Optional[int]
    strict_validation: bool
    report_grade: str


#: The single policy table (#733): one row per :class:`RunMode`. Read-only so a
#: consumer cannot mutate the contract at runtime.
POLICIES: Mapping[RunMode, RunModePolicy] = MappingProxyType(
    {
        RunMode.SCREENING: RunModePolicy(
            allow_toy_fallback=True,
            allow_toy_capex=True,
            min_mc_trials=None,
            strict_validation=True,
            report_grade="screening",
        ),
        RunMode.DEVELOPER: RunModePolicy(
            allow_toy_fallback=True,
            allow_toy_capex=True,
            min_mc_trials=None,
            strict_validation=True,
            report_grade="developer",
        ),
        RunMode.LENDER: RunModePolicy(
            allow_toy_fallback=False,
            allow_toy_capex=False,
            min_mc_trials=LENDER_GRADE_MIN_TRIALS,
            strict_validation=True,
            report_grade="lender",
        ),
        RunMode.IC: RunModePolicy(
            allow_toy_fallback=False,
            allow_toy_capex=False,
            min_mc_trials=LENDER_GRADE_MIN_TRIALS,
            strict_validation=True,
            report_grade="ic",
        ),
    }
)

_VALID_TOKENS: str = "/".join(sorted(mode.value for mode in RunMode))

#: Keys recognised inside the ``run`` block (#733 slice 1). Anything else is
#: rejected loudly: a mangled declaration (``Mode:`` / ``mdoe:``) must never
#: silently resolve to "no mode declared" — that typo'd-lender-declaration
#: failure class is exactly what #733 exists to close. Key names are
#: case-SENSITIVE; only the mode TOKEN itself is case-insensitive.
_RUN_BLOCK_ALLOWED_KEYS: frozenset[str] = frozenset({"mode"})


def _parse_token(token: Any, key: str) -> RunMode:
    """Parse one declared mode token, failing loud with the offending key.

    Args:
        token: The raw config value found under ``key``.
        key: The config key the token came from (``"run.mode"`` or
            ``"run_mode"``), named in every error (CESSPIT).

    Returns:
        The parsed :class:`RunMode`.

    Raises:
        ValueError: If ``token`` is not a string (the #683
            ``amortization_style`` precedent: a present-but-non-string value is
            a config error, not a stylistic typo) or is not a recognised mode
            token. Case-insensitive: ``"Lender"`` parses as ``RunMode.LENDER``.
    """
    if not isinstance(token, str):
        raise ValueError(
            f"{key} must be a string run-mode token (got {token!r}); "
            f"valid: {_VALID_TOKENS}"
        )
    try:
        return RunMode(token.lower())
    except ValueError:
        raise ValueError(
            f"{key}={token!r} is not a recognised run mode; valid: {_VALID_TOKENS}"
        ) from None


def resolve_run_mode(config: Mapping[str, Any]) -> Optional[RunMode]:
    """Resolve the declared :class:`RunMode` from a raw scenario config.

    Reads canonical ``run.mode`` and the top-level ``run_mode`` alias. The mode
    is OPT-IN: a config that declares neither resolves to ``None`` (today's
    behaviour, byte-identical) — no default mode is imposed here (see the module
    docstring's Assumptions).

    Args:
        config: Raw scenario config mapping (as produced by
            ``analytics.scenario_loader``).

    Returns:
        The declared :class:`RunMode`, or ``None`` when no mode is declared.
        An EMPTY ``run`` block and an explicitly null ``mode`` / ``run_mode``
        also resolve as undeclared: neither carries a mis-spelled intent (the
        unknown-key gate below covers typos), and a null value stays available
        as the overlay idiom for clearing a base-file declaration.

    Raises:
        ValueError: Fail-loud (CESSPIT) when a declaration is present but
            malformed — naming the offending key, the bad value, and the valid
            tokens. Specifically: a non-mapping ``run`` block (e.g.
            ``run: lender`` — the block belongs to this contract, so a
            mis-shaped one is an error, not a silent no-op); an unrecognised
            key inside the ``run`` block (``Mode:`` / ``mdoe:`` — a typo'd
            declaration must not silently resolve to no-mode; key names are
            case-SENSITIVE, only the mode token is case-insensitive); a
            non-string or unrecognised token under either key (#683
            precedent); or BOTH keys declared with conflicting modes
            (ambiguity is never resolved silently). Both keys declaring the
            SAME mode is accepted.
    """
    canonical: Optional[RunMode] = None
    alias: Optional[RunMode] = None

    run_block = config.get("run")
    if run_block is not None:
        if not isinstance(run_block, Mapping):
            raise ValueError(
                f"`run` must be a mapping with a `mode` key (got {run_block!r}); "
                f"e.g. run: {{mode: lender}}; valid modes: {_VALID_TOKENS}"
            )
        unknown_keys = sorted(
            str(key) for key in run_block if key not in _RUN_BLOCK_ALLOWED_KEYS
        )
        if unknown_keys:
            raise ValueError(
                "`run` block contains unrecognised key(s): "
                f"{', '.join(unknown_keys)} "
                f"(recognised: {', '.join(sorted(_RUN_BLOCK_ALLOWED_KEYS))}); "
                f"e.g. run: {{mode: lender}}; valid modes: {_VALID_TOKENS}"
            )
        mode_token = run_block.get("mode")
        if mode_token is not None:
            canonical = _parse_token(mode_token, "run.mode")

    alias_token = config.get("run_mode")
    if alias_token is not None:
        alias = _parse_token(alias_token, "run_mode")

    if canonical is not None and alias is not None and canonical is not alias:
        raise ValueError(
            "Conflicting run-mode declarations: "
            f"run.mode={canonical.value!r} vs run_mode={alias.value!r}. "
            "Declare ONE mode (canonical key: run.mode)."
        )
    return canonical if canonical is not None else alias
