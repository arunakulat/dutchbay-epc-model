"""Coverage tests for ``analytics.schema_guard``.

Targets the lines uncovered by ``test_schema_guard_registration.py``:

* ``_first_resolved_value`` empty-path ``continue`` branch (line 103),
* ``_validate_fx_section`` rejection paths: scalar ``fx``, wrong-type ``fx``,
  and ``fx`` mappings missing required keys (lines 124-150),
* the ``validate_config_for_v14`` validator-exception path and the
  warning-severity short-circuit (lines 199-219).

Everything is exercised against the live module: FX validation through the
public ``validate_config_for_v14`` entry point, and the spec-driven branches by
registering synthetic ``RequiredFieldSpec`` objects under a private module name
(so ``_ensure_module_registered`` is a no-op for it) and asserting the documented
raise / no-raise behaviour. No network, matplotlib, or filesystem access.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

import pytest

from analytics.config_schema import (
    RequiredFieldSpec,
    register_required_fields,
)
from analytics.schema_guard import (
    FX_DEPR_KEY,
    FX_START_KEY,
    ConfigValidationError,
    _first_resolved_value,
    _validate_fx_section,
    validate_config_for_v14,
)


def _valid_fx() -> dict[str, Any]:
    """A minimal, schema-valid ``fx`` mapping for v14."""
    return {FX_START_KEY: 333.79, FX_DEPR_KEY: 0.02}


def _fresh_module_name() -> str:
    """Return a registry module name guaranteed not to clash with real specs.

    The name is absent from ``schema_guard._MODULE_IMPORTS`` so
    ``_ensure_module_registered`` is a no-op for it (no import side effects),
    while ``get_required_fields`` still returns whatever we register here.
    """
    return f"_covtest_{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# _first_resolved_value: empty-path continue branch (line 103)
# ---------------------------------------------------------------------------


def test_first_resolved_value_skips_empty_path() -> None:
    """An empty path tuple is skipped; resolution continues to the next path."""
    raw: Mapping[str, Any] = {"fx": {FX_START_KEY: 333.79}}
    # First candidate is empty (must be skipped via `continue`), second resolves.
    value = _first_resolved_value(raw, [(), ("fx", FX_START_KEY)])
    assert value == 333.79


def test_first_resolved_value_all_empty_returns_none() -> None:
    """When every candidate path is empty, resolution yields None."""
    assert _first_resolved_value({"fx": {}}, [(), ()]) is None


def test_first_resolved_value_no_candidates_returns_none() -> None:
    """No candidate paths at all resolves to None."""
    assert _first_resolved_value({"fx": {}}, []) is None


def test_first_resolved_value_first_match_wins() -> None:
    """The first resolvable path wins over later candidates."""
    raw = {"a": {"x": 1}, "b": {"x": 2}}
    assert _first_resolved_value(raw, [("a", "x"), ("b", "x")]) == 1


# ---------------------------------------------------------------------------
# _validate_fx_section: every rejection branch (lines 122-150)
# ---------------------------------------------------------------------------


def test_fx_section_missing_appends_error() -> None:
    """A config with no `fx` key appends the 'Missing `fx` section' error."""
    errors: list[str] = []
    _validate_fx_section({}, errors)
    assert len(errors) == 1
    assert "Missing `fx` section" in errors[0]


def test_fx_section_none_value_appends_error() -> None:
    """An explicit `fx: None` is treated as missing."""
    errors: list[str] = []
    _validate_fx_section({"fx": None}, errors)
    assert len(errors) == 1
    assert "Missing `fx` section" in errors[0]


@pytest.mark.parametrize("scalar", [300, 333.79, "300"])
def test_fx_section_scalar_rejected(scalar: object) -> None:
    """Scalar `fx` (int/float/str) is explicitly rejected in v14."""
    errors: list[str] = []
    _validate_fx_section({"fx": scalar}, errors)
    assert len(errors) == 1
    assert "scalar `fx` is no longer supported" in errors[0]


@pytest.mark.parametrize("bad", [[FX_START_KEY, FX_DEPR_KEY], (1, 2), {1, 2}])
def test_fx_section_wrong_type_rejected(bad: object) -> None:
    """Non-scalar, non-mapping `fx` (e.g. list/tuple/set) is rejected by type."""
    errors: list[str] = []
    _validate_fx_section({"fx": bad}, errors)
    assert len(errors) == 1
    assert "Invalid FX config type" in errors[0]


def test_fx_section_missing_start_key() -> None:
    """A mapping missing `start_lkr_per_usd` reports the missing key."""
    errors: list[str] = []
    _validate_fx_section({"fx": {FX_DEPR_KEY: 0.02}}, errors)
    assert len(errors) == 1
    assert FX_START_KEY in errors[0]
    assert "missing required key" in errors[0]


def test_fx_section_missing_depr_key() -> None:
    """A mapping missing `annual_depr` reports the missing key."""
    errors: list[str] = []
    _validate_fx_section({"fx": {FX_START_KEY: 333.79}}, errors)
    assert len(errors) == 1
    assert FX_DEPR_KEY in errors[0]


def test_fx_section_missing_both_keys() -> None:
    """An empty `fx` mapping reports both required keys missing."""
    errors: list[str] = []
    _validate_fx_section({"fx": {}}, errors)
    assert len(errors) == 1
    assert FX_START_KEY in errors[0]
    assert FX_DEPR_KEY in errors[0]


def test_fx_section_valid_mapping_no_error() -> None:
    """A complete `fx` mapping appends no error."""
    errors: list[str] = []
    _validate_fx_section({"fx": _valid_fx()}, errors)
    assert errors == []


def test_fx_section_non_numeric_depr_rejected() -> None:
    """A non-numeric `annual_depr` is caught at pre-flight (audit D14, #581)."""
    errors: list[str] = []
    _validate_fx_section(
        {"fx": {FX_START_KEY: 333.79, FX_DEPR_KEY: "not-a-number"}}, errors
    )
    assert any(FX_DEPR_KEY in e and "finite number" in e for e in errors)


def test_fx_section_non_numeric_or_nonpositive_start_rejected() -> None:
    """A non-numeric or non-positive `start_lkr_per_usd` is caught at pre-flight."""
    bad_str: list[str] = []
    _validate_fx_section({"fx": {FX_START_KEY: "foo", FX_DEPR_KEY: 0.05}}, bad_str)
    assert any(FX_START_KEY in e and "finite number" in e for e in bad_str)

    non_positive: list[str] = []
    _validate_fx_section({"fx": {FX_START_KEY: -5.0, FX_DEPR_KEY: 0.05}}, non_positive)
    assert any(FX_START_KEY in e and "> 0" in e for e in non_positive)


def test_fx_section_numeric_string_still_accepted() -> None:
    """A numeric string passes (float() semantics mirror the loader) — no over-tightening."""
    errors: list[str] = []
    _validate_fx_section({"fx": {FX_START_KEY: "333.79", FX_DEPR_KEY: "0.05"}}, errors)
    assert errors == []


# ---------------------------------------------------------------------------
# validate_config_for_v14: FX errors surface through the public API
# ---------------------------------------------------------------------------


def test_validate_raises_on_scalar_fx_with_config_path() -> None:
    """Public entry point raises with the config_path header on scalar `fx`."""
    with pytest.raises(ConfigValidationError) as exc:
        validate_config_for_v14({"fx": 300}, "scenario.yaml", [])
    msg = str(exc.value)
    assert "scenario.yaml" in msg
    assert "scalar `fx`" in msg


def test_validate_raises_on_missing_fx_without_config_path() -> None:
    """With config_path=None the generic header is used."""
    with pytest.raises(ConfigValidationError) as exc:
        validate_config_for_v14({}, None, None)
    msg = str(exc.value)
    assert "Config is missing or has invalid required fields" in msg
    assert "Missing `fx` section" in msg


def test_validate_accepts_valid_fx_no_modules() -> None:
    """A valid `fx` mapping with no modules requested passes silently."""
    # Returns None (no raise).
    assert validate_config_for_v14({"fx": _valid_fx()}, "<test>", []) is None


# ---------------------------------------------------------------------------
# ARCH-6 (#488): technology `type` enum validation at pre-flight
# ---------------------------------------------------------------------------


def test_unknown_technology_type_is_rejected_at_preflight() -> None:
    """A declared but unrecognised technology `type` (typo / unsupported class) fails
    fast at the schema guard — before the pipeline runs."""
    cfg = {
        "fx": _valid_fx(),
        "generation": {
            "technologies": {
                "w": {"type": "wnid", "capacity_factor": 0.3},
                "b": {"type": "battery", "power_mw": 10},
            }
        },
    }
    with pytest.raises(ConfigValidationError) as exc:
        validate_config_for_v14(cfg, "scenario.yaml", [])
    msg = str(exc.value)
    assert "wnid" in msg and "battery" in msg
    assert "not a recognised technology type" in msg


def test_known_technology_types_pass() -> None:
    """Recognised generation/storage types pass the type check."""
    cfg = {
        "fx": _valid_fx(),
        "generation": {
            "technologies": {
                "wind": {"type": "wind", "capacity_factor": 0.34},
                "solar": {"type": "solar", "capacity_factor": 0.18},
                "bess": {"type": "bess", "power_mw": 11},
            }
        },
    }
    assert validate_config_for_v14(cfg, "<test>", []) is None


def test_untyped_technology_block_is_not_gated() -> None:
    """An untyped block is the backward-compatible key-sniff path — not forced a type."""
    cfg = {
        "fx": _valid_fx(),
        "generation": {"technologies": {"wind": {"capacity_factor": 0.34}}},
    }
    assert validate_config_for_v14(cfg, "<test>", []) is None


# ---------------------------------------------------------------------------
# validate_config_for_v14: spec-driven branches via synthetic specs
# ---------------------------------------------------------------------------


def test_warning_severity_spec_does_not_block() -> None:
    """A warning-severity spec is skipped (not hard-enforced), so no raise.

    Even though the required value is absent, severity != "error" short-circuits
    before the value is resolved, so validation passes on the FX section alone.
    """
    module = _fresh_module_name()
    register_required_fields(
        module,
        [
            RequiredFieldSpec(
                module=module,
                name="soft_field",
                paths=[("never", "present")],
                required=True,
                severity="warning",
                validator=lambda _v: False,
            )
        ],
    )
    # FX is valid and the warning spec must not block -> no raise.
    assert validate_config_for_v14({"fx": _valid_fx()}, "<test>", [module]) is None


def test_validator_exception_is_treated_as_failure() -> None:
    """A validator that raises is caught and counted as a validation failure.

    Exercises the try/except path: the exception is logged at debug level and
    `ok` is set False, so the field is reported as invalid.
    """

    def _boom(_value: Any) -> bool:
        raise RuntimeError("validator blew up")

    module = _fresh_module_name()
    register_required_fields(
        module,
        [
            RequiredFieldSpec(
                module=module,
                name="exploding_field",
                paths=[("fx", FX_START_KEY)],
                required=True,
                severity="error",
                validator=_boom,
            )
        ],
    )
    with pytest.raises(ConfigValidationError, match="exploding_field"):
        validate_config_for_v14({"fx": _valid_fx()}, "<test>", [module])


def test_validator_returning_false_reports_field() -> None:
    """A validator returning False (no exception) flags the field as invalid."""
    module = _fresh_module_name()
    register_required_fields(
        module,
        [
            RequiredFieldSpec(
                module=module,
                name="rejected_field",
                paths=[("fx", FX_START_KEY)],
                required=True,
                severity="error",
                validator=lambda _v: False,
            )
        ],
    )
    with pytest.raises(ConfigValidationError, match="rejected_field"):
        validate_config_for_v14({"fx": _valid_fx()}, "<test>", [module])


def test_missing_required_value_reports_field_with_paths() -> None:
    """A required error-severity spec whose value is absent is reported.

    The error message includes the dotted path labels for the field.
    """
    module = _fresh_module_name()
    register_required_fields(
        module,
        [
            RequiredFieldSpec(
                module=module,
                name="absent_field",
                paths=[("does", "not", "exist")],
                required=True,
                severity="error",
                validator=None,
            )
        ],
    )
    with pytest.raises(ConfigValidationError) as exc:
        validate_config_for_v14({"fx": _valid_fx()}, "<test>", [module])
    msg = str(exc.value)
    assert "absent_field" in msg
    assert "does.not.exist" in msg


def test_valid_validator_and_present_value_passes() -> None:
    """A present, valid required field passes (validator returns True)."""
    module = _fresh_module_name()
    register_required_fields(
        module,
        [
            RequiredFieldSpec(
                module=module,
                name="good_field",
                paths=[("fx", FX_START_KEY)],
                required=True,
                severity="error",
                validator=lambda v: isinstance(v, float),
            )
        ],
    )
    assert validate_config_for_v14({"fx": _valid_fx()}, "<test>", [module]) is None


def test_optional_field_absent_does_not_block() -> None:
    """A non-required spec with an absent value (no validator) does not raise."""
    module = _fresh_module_name()
    register_required_fields(
        module,
        [
            RequiredFieldSpec(
                module=module,
                name="optional_field",
                paths=[("missing",)],
                required=False,
                severity="error",
                validator=None,
            )
        ],
    )
    assert validate_config_for_v14({"fx": _valid_fx()}, "<test>", [module]) is None


def test_spec_with_no_paths_uses_placeholder_label() -> None:
    """A required spec with no paths reports the '<no paths>' placeholder label."""
    module = _fresh_module_name()
    register_required_fields(
        module,
        [
            RequiredFieldSpec(
                module=module,
                name="pathless_field",
                paths=[],
                required=True,
                severity="error",
                validator=None,
            )
        ],
    )
    with pytest.raises(ConfigValidationError) as exc:
        validate_config_for_v14({"fx": _valid_fx()}, "<test>", [module])
    msg = str(exc.value)
    assert "pathless_field" in msg
    assert "<no paths>" in msg


# ---------------------------------------------------------------------------
# Wave-2: wind/era5 interface guards auto-enforce when the block is present
# ---------------------------------------------------------------------------
def _lender_config() -> dict[str, Any]:
    from pathlib import Path

    import yaml

    repo = Path(__file__).resolve().parents[2]
    return yaml.safe_load(
        (repo / "scenarios" / "dutchbay_lendercase_2025Q4.yaml").read_text()
    )


def test_era5_guard_auto_enforced_when_block_present() -> None:
    """The canonical declares resource.era5, so even with the DEFAULT module set
    (cashflow/debt) the era5 interface schema is now enforced: corrupting it (dropping the
    required latitude) raises, where before it was silently never validated (Wave-2 fix).
    """
    cfg = _lender_config()
    cfg["resource"]["era5"].pop("latitude", None)
    with pytest.raises(ConfigValidationError, match="latitude"):
        validate_config_for_v14(cfg, "lender", ["cashflow", "debt"])


def test_clean_lender_config_passes_with_wind_era5_enforced() -> None:
    """The unmodified canonical satisfies the wind + era5 schemas (byte-identical: the
    guard fires but finds nothing wrong)."""
    validate_config_for_v14(
        _lender_config(), "lender", ["cashflow", "debt"]
    )  # no raise


def test_wind_era5_not_enforced_when_absent() -> None:
    """A config without resource.wind/era5 is not subjected to those guards (no spurious
    failure for non-wind scenarios)."""
    cfg = _lender_config()
    cfg.pop("resource", None)
    # cashflow/debt/fx still validate; absence of resource must not raise a wind/era5 error.
    try:
        validate_config_for_v14(cfg, "no-resource", ["cashflow", "debt"])
    except ConfigValidationError as exc:
        assert "latitude" not in str(exc) and "hub_height" not in str(exc)
