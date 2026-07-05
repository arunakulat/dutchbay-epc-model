"""Tests for ``analytics.run_modes`` — the #733 run-mode contract (slice 1).

Pins the contract surface only (nothing consumes it yet; wiring is #733b/#733c):

* the four-token :class:`~analytics.run_modes.RunMode` enum round-trips through
  its config token;
* ``POLICIES`` covers every mode, lender/IC force the honest posture (no toy
  fallback, no toy capex, lender-grade trial floor), and the duplicated
  :data:`~analytics.run_modes.LENDER_GRADE_MIN_TRIALS` is pinned equal to the
  app-layer ``app.reports.capital_risk_emit.LENDER_GRADE_MIN_TRIALS`` via a
  LAZY import (the constant is duplicated so the analytics layer never imports
  the app report stack — drift fails here);
* :func:`~analytics.run_modes.resolve_run_mode` is opt-in (absent -> ``None``,
  today's behaviour), case-insensitive on valid tokens, and fail-loud (CESSPIT)
  on invalid / non-string tokens, a non-mapping ``run`` block, unrecognised
  keys inside the ``run`` block (a typo'd ``Mode:``/``mdoe:`` must not
  silently resolve to no-mode), and conflicting ``run.mode`` vs ``run_mode``
  declarations;
* the ``validate_config_for_v14`` pre-flight gate (#601 lesson) rejects a
  malformed declaration at config time, naming the valid tokens, and passes
  valid / absent declarations unchanged.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest

from analytics.run_modes import (
    LENDER_GRADE_MIN_TRIALS,
    POLICIES,
    RunMode,
    RunModePolicy,
    resolve_run_mode,
)
from analytics.schema_guard import (
    FX_DEPR_KEY,
    FX_START_KEY,
    ConfigValidationError,
    validate_config_for_v14,
)

ALL_TOKENS = ("screening", "developer", "lender", "ic")


def _valid_config(**extra: Any) -> dict[str, Any]:
    """A minimal config that passes ``validate_config_for_v14`` with no modules."""
    config: dict[str, Any] = {"fx": {FX_START_KEY: 333.79, FX_DEPR_KEY: 0.02}}
    config.update(extra)
    return config


# ---------------------------------------------------------------------------
# RunMode enum
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("token", ALL_TOKENS)
def test_enum_round_trips_through_config_token(token: str) -> None:
    """Each mode is constructible from its token and serialises back to it."""
    mode = RunMode(token)
    assert mode.value == token
    assert RunMode(mode.value) is mode


def test_enum_has_exactly_the_four_contract_modes() -> None:
    """The #733 contract defines exactly screening/developer/lender/ic."""
    assert {mode.value for mode in RunMode} == set(ALL_TOKENS)


# ---------------------------------------------------------------------------
# POLICIES table
# ---------------------------------------------------------------------------


def test_policies_covers_every_mode() -> None:
    """Every RunMode has exactly one policy row (no mode falls through)."""
    assert set(POLICIES) == set(RunMode)
    assert all(isinstance(policy, RunModePolicy) for policy in POLICIES.values())


@pytest.mark.parametrize("mode", [RunMode.LENDER, RunMode.IC])
def test_lender_and_ic_force_honest_posture(mode: RunMode) -> None:
    """Lender/IC refuse toy substitution and require the lender trial floor."""
    policy = POLICIES[mode]
    assert policy.allow_toy_fallback is False
    assert policy.allow_toy_capex is False
    assert policy.min_mc_trials == LENDER_GRADE_MIN_TRIALS
    assert policy.strict_validation is True
    assert policy.report_grade == mode.value


@pytest.mark.parametrize("mode", [RunMode.SCREENING, RunMode.DEVELOPER])
def test_screening_and_developer_are_permissive_ceilings(
    mode: RunMode,
) -> None:
    """Screening/developer are permissive CEILINGS, not today's defaults.

    On the MC axis ``allow_toy_fallback=True`` matches the engine default; on
    the capex axis the debt engine's toy fallback stays OPT-IN (default
    ``False``) — ``allow_toy_capex=True`` only means the mode does not FORBID
    it (wiring must not apply it as a default-on; see the module Assumptions).
    """
    policy = POLICIES[mode]
    assert policy.allow_toy_fallback is True
    assert policy.allow_toy_capex is True
    assert policy.min_mc_trials is None
    assert policy.strict_validation is True
    assert policy.report_grade == mode.value


def test_policies_table_is_read_only() -> None:
    """The policy contract cannot be mutated at runtime."""
    with pytest.raises(TypeError):
        POLICIES[RunMode.LENDER] = POLICIES[RunMode.DEVELOPER]  # type: ignore[index]


def test_min_trials_matches_app_lender_floor() -> None:
    """The duplicated floor is pinned equal to the app-layer constant.

    LAZY import: ``app.reports.capital_risk_emit`` drags the app report stack
    (FastAPI response models + the jinja2 renderer), which is exactly why
    ``analytics.run_modes`` duplicates the constant instead of importing it.
    This test is the drift guard for that duplication.
    """
    emit = importlib.import_module("app.reports.capital_risk_emit")
    assert LENDER_GRADE_MIN_TRIALS == emit.LENDER_GRADE_MIN_TRIALS
    assert POLICIES[RunMode.LENDER].min_mc_trials == emit.LENDER_GRADE_MIN_TRIALS
    assert POLICIES[RunMode.IC].min_mc_trials == emit.LENDER_GRADE_MIN_TRIALS


# ---------------------------------------------------------------------------
# resolve_run_mode
# ---------------------------------------------------------------------------


def test_resolve_absent_returns_none() -> None:
    """No declaration -> None (opt-in; today's behaviour is untouched)."""
    assert resolve_run_mode({}) is None
    assert resolve_run_mode(_valid_config()) is None


def test_resolve_empty_block_and_null_mode_are_undeclared() -> None:
    """An empty ``run`` block / explicitly null mode is undeclared, not an error.

    Neither carries a mis-spelled intent (the unknown-key gate covers typos),
    and an explicit null stays available as the overlay idiom for clearing a
    base-file declaration.
    """
    assert resolve_run_mode({"run": {}}) is None
    assert resolve_run_mode({"run": {"mode": None}}) is None
    assert resolve_run_mode({"run_mode": None}) is None


@pytest.mark.parametrize("bad_key", ["Mode", "mdoe"])
def test_resolve_rejects_unknown_run_block_key(bad_key: str) -> None:
    """A typo'd declaration key must not silently resolve to no-mode.

    ``{"run": {"Mode": "lender"}}`` / ``{"run": {"mdoe": "lender"}}`` is the
    exact typo'd-lender-declaration failure class #733 exists to close.
    """
    with pytest.raises(ValueError) as excinfo:
        resolve_run_mode({"run": {bad_key: "lender"}})
    message = str(excinfo.value)
    assert bad_key in message
    assert "recognised: mode" in message


def test_resolve_rejects_unknown_key_even_beside_valid_mode() -> None:
    """An unknown key is rejected even when a valid ``mode`` is present."""
    with pytest.raises(ValueError, match="unrecognised key"):
        resolve_run_mode({"run": {"mode": "lender", "grade": "gold"}})


def test_resolve_names_all_unknown_keys_sorted() -> None:
    """Every unknown key is named, sorted, in one error."""
    with pytest.raises(ValueError, match=r"Mode, mdoe"):
        resolve_run_mode({"run": {"mdoe": "lender", "Mode": "ic"}})


def test_resolve_canonical_run_mode_key() -> None:
    """``run.mode: lender`` resolves to RunMode.LENDER."""
    assert resolve_run_mode({"run": {"mode": "lender"}}) is RunMode.LENDER


@pytest.mark.parametrize("token", ALL_TOKENS)
def test_resolve_alias_top_level_run_mode(token: str) -> None:
    """The top-level ``run_mode`` alias resolves every valid token."""
    assert resolve_run_mode({"run_mode": token}) is RunMode(token)


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("Lender", RunMode.LENDER),
        ("SCREENING", RunMode.SCREENING),
        ("Ic", RunMode.IC),
        ("dEvElOpEr", RunMode.DEVELOPER),
    ],
)
def test_resolve_is_case_insensitive(token: str, expected: RunMode) -> None:
    """Valid tokens normalise case-insensitively."""
    assert resolve_run_mode({"run": {"mode": token}}) is expected
    assert resolve_run_mode({"run_mode": token}) is expected


def test_resolve_invalid_token_names_key_value_and_tokens() -> None:
    """An unrecognised token fails loud, naming key, value, and valid tokens."""
    with pytest.raises(ValueError) as excinfo:
        resolve_run_mode({"run": {"mode": "banker"}})
    message = str(excinfo.value)
    assert "run.mode" in message
    assert "banker" in message
    for token in ALL_TOKENS:
        assert token in message


def test_resolve_invalid_alias_token_names_alias_key() -> None:
    """The alias key is named when IT carries the bad token."""
    with pytest.raises(ValueError, match="run_mode"):
        resolve_run_mode({"run_mode": "bankable"})


@pytest.mark.parametrize("bad", [5, True])
def test_resolve_non_string_token_rejected_loudly(bad: Any) -> None:
    """A present-but-non-string token is a config error (#683 precedent)."""
    with pytest.raises(ValueError) as excinfo:
        resolve_run_mode({"run": {"mode": bad}})
    message = str(excinfo.value)
    assert "run.mode" in message
    assert repr(bad) in message
    with pytest.raises(ValueError, match="run_mode"):
        resolve_run_mode({"run_mode": bad})


def test_resolve_non_mapping_run_block_rejected_loudly() -> None:
    """``run: lender`` (scalar block) is a mis-shape, not a silent no-op."""
    with pytest.raises(ValueError, match="`run` must be a mapping"):
        resolve_run_mode({"run": "lender"})


def test_resolve_conflicting_declarations_rejected() -> None:
    """run.mode vs run_mode disagreement is never resolved silently."""
    with pytest.raises(ValueError, match="Conflicting run-mode declarations"):
        resolve_run_mode({"run": {"mode": "lender"}, "run_mode": "ic"})


def test_resolve_agreeing_declarations_accepted() -> None:
    """Both keys declaring the SAME mode (any case) is accepted."""
    config = {"run": {"mode": "lender"}, "run_mode": "Lender"}
    assert resolve_run_mode(config) is RunMode.LENDER


# ---------------------------------------------------------------------------
# Schema-guard pre-flight (#601 lesson: fail at config time, not first use)
# ---------------------------------------------------------------------------


def test_schema_guard_rejects_bad_run_mode_naming_tokens() -> None:
    """A malformed declaration fails pre-flight validation with the token list."""
    config = _valid_config(run={"mode": "bogus"})
    with pytest.raises(ConfigValidationError) as excinfo:
        validate_config_for_v14(config, "bad_run_mode.yaml", [])
    message = str(excinfo.value)
    assert "run.mode" in message
    assert "bogus" in message
    for token in ALL_TOKENS:
        assert token in message


def test_schema_guard_rejects_non_string_run_mode_alias() -> None:
    """The pre-flight gate also rejects a non-string alias token."""
    with pytest.raises(ConfigValidationError, match="run_mode"):
        validate_config_for_v14(_valid_config(run_mode=5), "typed.yaml", [])


def test_schema_guard_rejects_typoed_run_block_key() -> None:
    """Pre-flight catches the typo'd-key class too, naming the unknown key."""
    config = _valid_config(run={"Mode": "lender"})
    with pytest.raises(ConfigValidationError) as excinfo:
        validate_config_for_v14(config, "typo.yaml", [])
    message = str(excinfo.value)
    assert "Mode" in message
    assert "recognised: mode" in message


@pytest.mark.parametrize("token", ALL_TOKENS)
def test_schema_guard_passes_valid_run_mode(token: str) -> None:
    """Every valid token passes the pre-flight gate."""
    validate_config_for_v14(_valid_config(run={"mode": token}), "ok.yaml", [])


def test_schema_guard_passes_absent_run_mode() -> None:
    """No declaration -> no error (opt-in; existing configs untouched)."""
    validate_config_for_v14(_valid_config(), "absent.yaml", [])
