"""F-03 (#1394): ``validate_config_for_v14`` refuses unsupported A3 period fields.

``finance.period_grid_v14`` and ``finance.subannual_rows_v14`` have been strict about
``cashflow.resolution`` and ``cashflow.within_year_profile`` since A1/A2 -- but only at
the moment the engine first read them. Nothing registered either field in the v14 field
specs, and nothing consulted them at pre-flight, so a scenario carrying a typo'd
resolution or a profile that cannot apply reached evaluation before anything objected.
That is the gap F-03 names: ``FRAMEWORK-02`` wants the gatekeeper to name the field.

What is asserted here
---------------------
* the gate FIRES, through the public ``validate_config_for_v14`` entry point, on every
  class of bad value, with the config path and the accepted values in the message;
* the gate is SILENT on a supported pair, and on the absent pair every committed
  scenario has -- the default-off claim;
* the cross-field case, which is the mistake most likely to reach a real config: a
  four-weight profile with no declared resolution;
* the engine-support gate reaches pre-flight, proved with a SYNTHETIC describable
  resolution no builder exists for, the way ``finance.period_grid_v14``'s own tests keep
  that gate honest -- a real resolution cannot prove it, because
  ``SUPPORTED_RESOLUTIONS`` and ``ENGINE_SUPPORTED_RESOLUTIONS`` are the same set today;
* both fields are registered in the v14 field specs, at the paths their resolvers own.

Every negative case here passes if ``_validate_cashflow_period_fields`` is removed from
``validate_config_for_v14``; that is what makes them controls rather than decoration.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Iterator

import pytest

from analytics.config_schema import get_required_fields
from analytics.schema_guard import (
    ConfigValidationError,
    _validate_cashflow_period_fields,
    validate_config_for_v14,
)
from finance.period_grid_v14 import (
    CASHFLOW_RESOLUTION_KEY,
    SUPPORTED_RESOLUTIONS,
)
from finance.subannual_rows_v14 import WITHIN_YEAR_PROFILE_KEY

MODULES = ["cashflow", "debt"]


def _valid_config() -> dict[str, Any]:
    """A complete, schema-valid v14 config carrying NEITHER period field.

    Mirrors ``tests/analytics/test_schema_guard_registration._valid_config`` so a
    failure here is about the period fields and never about an unrelated missing key.
    """
    return {
        "project": {
            "name": "f03_preflight_test",
            "capacity_mw": 100.0,
            "capacity_factor_pct": 35.0,
            "project_life_years": 25,
        },
        "wind": {"weibull_k": 2.0, "weibull_lambda": 8.5, "hub_height_m": 120.0},
        "finance": {"capex_total_usd": 200e6, "discount_rate_pct": 8.0},
        "tariff": {"lkr_per_kwh": 24.0},
        "opex": {"usd_per_year": 5e6},
        "tax": {
            "corporate_tax_rate": 0.30,
            "depreciation_method": "straight_line",
            "depreciation_start_year": 1,
            "depreciation_years": 15,
            "enhanced_allowance_applies": False,
            "enhanced_capital_allowance_multiple": 1.0,
            "loss_carryforward_years": 25,
            "tax_holiday_start_year": 1,
            "tax_holiday_years": 0,
            "wht_on_interest_to_nonresidents": 0.0,
            "wht_on_interest_enabled": False,
            "wht_gross_up": False,
        },
        "fx": {"start_lkr_per_usd": 300.0, "annual_depr": 0.02},
        "debt": {"target_dscr": 1.4, "interest_rate_pct": 6.0, "term_years": 18},
    }


def _with_cashflow(**keys: Any) -> dict[str, Any]:
    """``_valid_config`` plus a ``cashflow`` block carrying exactly ``keys``."""
    cfg = _valid_config()
    cfg["cashflow"] = dict(keys)
    return cfg


# ---------------------------------------------------------------------------
# Positive controls: the gate must not fire on what the canon already ships
# ---------------------------------------------------------------------------


def test_absent_period_fields_pass() -> None:
    """Default-off. No ``cashflow`` block at all is the committed-scenario shape."""
    validate_config_for_v14(_valid_config(), "<test>", MODULES)


def test_empty_cashflow_block_passes() -> None:
    """A present but empty ``cashflow`` block resolves to the annual default."""
    validate_config_for_v14(_with_cashflow(), "<test>", MODULES)


def test_annual_resolution_passes() -> None:
    """The default named explicitly is still the default."""
    validate_config_for_v14(_with_cashflow(resolution="annual"), "<test>", MODULES)


def test_quarterly_with_matching_profile_passes() -> None:
    """A supported resolution with a well-formed profile for it."""
    cfg = _with_cashflow(
        resolution="quarterly", within_year_profile=[0.3, 0.3, 0.2, 0.2]
    )
    validate_config_for_v14(cfg, "<test>", MODULES)


def test_quarterly_without_a_profile_passes() -> None:
    """A profile is optional; absent means an even split."""
    validate_config_for_v14(_with_cashflow(resolution="quarterly"), "<test>", MODULES)


def test_resolution_is_accepted_case_and_space_insensitively() -> None:
    """The resolver lower-cases and strips; pre-flight must not be stricter than it."""
    validate_config_for_v14(
        _with_cashflow(resolution="  Quarterly "), "<test>", MODULES
    )


# ---------------------------------------------------------------------------
# Negative controls: cashflow.resolution
# ---------------------------------------------------------------------------


def test_unsupported_resolution_is_refused_with_path_and_accepted_values() -> None:
    """The headline case: a typo must not be served as annual output.

    The message has to carry both halves F-03 asks for -- the config path, and what
    would have been accepted -- so the person who typo'd it can fix it from the error.
    """
    cfg = _with_cashflow(resolution="qarterly")
    with pytest.raises(ConfigValidationError) as excinfo:
        validate_config_for_v14(cfg, "<test>", MODULES)
    message = str(excinfo.value)
    assert CASHFLOW_RESOLUTION_KEY in message
    assert "qarterly" in message
    for supported in SUPPORTED_RESOLUTIONS:
        assert supported in message


def test_monthly_is_refused_until_something_can_describe_it() -> None:
    """A resolution a reader might reasonably expect, and the model does not have."""
    with pytest.raises(ConfigValidationError, match=CASHFLOW_RESOLUTION_KEY):
        validate_config_for_v14(_with_cashflow(resolution="monthly"), "<test>", MODULES)


def test_non_string_resolution_is_refused() -> None:
    """``resolution: 4`` is a plausible way to mean quarterly, and is not the contract."""
    with pytest.raises(ConfigValidationError, match="must be a string"):
        validate_config_for_v14(_with_cashflow(resolution=4), "<test>", MODULES)


def test_blank_resolution_is_refused() -> None:
    """An emptied YAML value is not the same as an omitted key."""
    with pytest.raises(ConfigValidationError, match="is empty"):
        validate_config_for_v14(_with_cashflow(resolution="   "), "<test>", MODULES)


def test_non_dict_cashflow_mapping_is_refused() -> None:
    """The silent-demotion guard has to reach pre-flight too.

    A non-``dict`` mapping carrying a well-formed ``{"resolution": "quarterly"}`` is the
    worst case ``finance.period_grid_v14.require_mapping_node`` documents: nothing about
    the config looks wrong, and the resolver cannot read it, so the run would quietly
    receive the annual grid. ``omegaconf.DictConfig`` has exactly this shape.
    """

    class _ReadOnlyMapping(Mapping[str, Any]):
        def __init__(self, data: dict[str, Any]) -> None:
            self._data = data

        def __getitem__(self, key: str) -> Any:
            return self._data[key]

        def __iter__(self) -> Iterator[str]:
            return iter(self._data)

        def __len__(self) -> int:
            return len(self._data)

    cfg = _valid_config()
    cfg["cashflow"] = _ReadOnlyMapping({"resolution": "quarterly"})
    with pytest.raises(ConfigValidationError, match="must be a dict containing"):
        validate_config_for_v14(cfg, "<test>", MODULES)


# ---------------------------------------------------------------------------
# Negative controls: cashflow.within_year_profile
# ---------------------------------------------------------------------------


def test_profile_without_a_resolution_is_refused() -> None:
    """The cross-field case, and the reason the grid is resolved first.

    Four weights and no declared resolution is a config whose author believed they had
    asked for quarterly. Before F-03 it ran annually and the profile was never read.
    """
    cfg = _with_cashflow(within_year_profile=[0.25, 0.25, 0.25, 0.25])
    with pytest.raises(ConfigValidationError) as excinfo:
        validate_config_for_v14(cfg, "<test>", MODULES)
    message = str(excinfo.value)
    assert WITHIN_YEAR_PROFILE_KEY in message
    assert "4 weights" in message
    assert "annual" in message


def test_profile_of_the_wrong_length_for_its_grid_is_refused() -> None:
    """Three weights cannot split a four-period year."""
    cfg = _with_cashflow(resolution="quarterly", within_year_profile=[0.4, 0.3, 0.3])
    with pytest.raises(ConfigValidationError, match="3 weights"):
        validate_config_for_v14(cfg, "<test>", MODULES)


def test_profile_that_does_not_sum_to_one_is_refused() -> None:
    """Weights are shares; a sum of 0.9 would silently scale every allocated figure."""
    cfg = _with_cashflow(
        resolution="quarterly", within_year_profile=[0.3, 0.3, 0.2, 0.1]
    )
    with pytest.raises(ConfigValidationError, match="sum to"):
        validate_config_for_v14(cfg, "<test>", MODULES)


def test_profile_with_a_negative_weight_is_refused() -> None:
    """A negative share moves cash between periods instead of splitting it."""
    cfg = _with_cashflow(
        resolution="quarterly", within_year_profile=[0.6, 0.6, -0.1, -0.1]
    )
    with pytest.raises(ConfigValidationError, match="must be >= 0"):
        validate_config_for_v14(cfg, "<test>", MODULES)


def test_profile_with_a_non_numeric_weight_is_refused() -> None:
    """A YAML string where a number belongs."""
    cfg = _with_cashflow(
        resolution="quarterly", within_year_profile=[0.25, "0.25", 0.25, 0.25]
    )
    with pytest.raises(ConfigValidationError, match="must be a number"):
        validate_config_for_v14(cfg, "<test>", MODULES)


def test_profile_that_is_not_a_sequence_is_refused() -> None:
    """A mapping of period to weight is a reasonable guess and not the contract."""
    cfg = _with_cashflow(
        resolution="quarterly", within_year_profile={"q1": 0.25, "q2": 0.75}
    )
    with pytest.raises(ConfigValidationError, match="must be a sequence"):
        validate_config_for_v14(cfg, "<test>", MODULES)


# ---------------------------------------------------------------------------
# The engine-support gate, proved with a synthetic unbuilt resolution
# ---------------------------------------------------------------------------


def test_describable_but_unbuildable_resolution_is_refused_at_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A resolution the grid can describe and no builder can build must fail HERE.

    ``SUPPORTED_RESOLUTIONS`` and ``ENGINE_SUPPORTED_RESOLUTIONS`` are both
    ``{annual, quarterly}`` today, so no real value can exercise this. A synthetic
    entry is added to the describable set only -- the same device
    ``finance.period_grid_v14``'s own tests use -- which is what keeps the gate honest
    for the next resolution that lands before its builder.

    Without this delegation the config would reach evaluation and be served annual rows
    under a sub-annual label.
    """
    monkeypatch.setitem(SUPPORTED_RESOLUTIONS, "fortnightly", 26)
    cfg = _with_cashflow(resolution="fortnightly")
    with pytest.raises(ConfigValidationError) as excinfo:
        validate_config_for_v14(cfg, "<test>", MODULES)
    message = str(excinfo.value)
    assert "cannot build rows" in message
    assert "fortnightly" in message


def test_an_unbuildable_resolution_suppresses_the_profile_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One mistake, one message.

    With no usable grid there is nothing to measure a profile against, so the delegation
    returns instead of falling back to the annual grid. Falling back would report a
    second error saying the 26-weight profile is wrong for a one-period year, which is
    true of the fallback and not of anything the author wrote.
    """
    monkeypatch.setitem(SUPPORTED_RESOLUTIONS, "fortnightly", 26)
    errors: list[str] = []
    _validate_cashflow_period_fields(
        _with_cashflow(
            resolution="fortnightly",
            within_year_profile=[1.0 / 26] * 26,
        ),
        errors,
    )
    assert len(errors) == 1, errors
    assert "cannot build rows" in errors[0]
    assert WITHIN_YEAR_PROFILE_KEY not in errors[0]


# ---------------------------------------------------------------------------
# Registration in the v14 field specs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("spec_name", "dotted_key"),
    [
        ("cashflow_resolution", CASHFLOW_RESOLUTION_KEY),
        ("cashflow_within_year_profile", WITHIN_YEAR_PROFILE_KEY),
    ],
)
def test_period_field_is_registered_at_the_path_its_resolver_owns(
    spec_name: str, dotted_key: str
) -> None:
    """Both fields appear in the v14 field specs, at the resolver's own path.

    The path is asserted against the resolver's exported dotted key rather than a
    literal, so this case cannot pass while the registration points somewhere the
    engine does not read.
    """
    import finance.cashflow_v14  # noqa: F401  (import side effect registers the specs)

    specs = {spec.name: spec for spec in get_required_fields("cashflow")}
    assert spec_name in specs, sorted(specs)
    spec = specs[spec_name]
    assert {".".join(path) for path in spec.paths} == {dotted_key}
    # Opt-in: a required spec would reject every committed scenario.
    assert spec.required is False
    assert spec.description


def test_registered_period_specs_carry_no_second_validator() -> None:
    """The declaration must not grow a partial copy of the resolvers' rules.

    This is the drift control for the design decision recorded at the registration
    site: enforcement lives in the resolvers, which pre-flight delegates to. A
    validator added here would be a second authority, and the one that is wrong is
    always the copy.
    """
    import finance.cashflow_v14  # noqa: F401

    specs = {spec.name: spec for spec in get_required_fields("cashflow")}
    for name in ("cashflow_resolution", "cashflow_within_year_profile"):
        assert specs[name].validator is None
