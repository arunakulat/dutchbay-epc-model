"""Coverage for :mod:`analytics.config_schema` — the RequiredFieldSpec registry.

Targets the previously-uncovered branches:

* ``get_required_fields(None)`` — aggregation across every registered module
  (the ``module is None`` branch).
* ``build_schema_dataframe()`` — both the populated path (flatten + sort) and
  the empty-registry path (typed empty frame).

These tests register *synthetic* specs under a unique module name so they never
collide with the real specs that production modules register at import time, and
they restore the global registry afterwards so no state leaks into sibling tests.
"""

from __future__ import annotations

from typing import Dict, Iterator, List

import pandas as pd
import pytest

from analytics import config_schema
from analytics.config_schema import (
    PathSpec,
    RequiredFieldSpec,
    ValidatorFn,
    build_schema_dataframe,
    get_required_fields,
    register_required_fields,
)

_SYNTH_MODULE = "synthetic_coverage_module"
_SYNTH_MODULE_B = "synthetic_coverage_module_b"


@pytest.fixture
def clean_registry() -> Iterator[None]:
    """Snapshot the global registry, then restore it after the test.

    The registry is a process-global populated by production imports; mutating
    it directly (rather than deep-copying) is fine as long as we restore the
    exact mapping object's contents afterwards.
    """
    saved: Dict[str, List[RequiredFieldSpec]] = {
        mod: list(specs) for mod, specs in config_schema._REGISTRY.items()
    }
    try:
        yield
    finally:
        config_schema._REGISTRY.clear()
        config_schema._REGISTRY.update(saved)


def _make_spec(
    module: str,
    name: str,
    *,
    required: bool = True,
    severity: str = "error",
    description: str = "",
    validator: ValidatorFn | None = None,
) -> RequiredFieldSpec:
    paths: list[PathSpec] = [(module, name)]
    return RequiredFieldSpec(
        module=module,
        name=name,
        paths=paths,
        required=required,
        severity=severity,
        description=description,
        validator=validator,
    )


def test_required_field_spec_defaults() -> None:
    spec = RequiredFieldSpec(module="m", name="n", paths=[("a", "b")])
    assert spec.required is True
    assert spec.severity == "error"
    assert spec.description == ""
    assert spec.validator is None


def test_required_field_spec_is_frozen() -> None:
    spec = _make_spec("m", "n")
    with pytest.raises(Exception):  # dataclass(frozen=True) -> FrozenInstanceError
        spec.name = "other"  # type: ignore[misc]


def test_required_field_spec_validator_runs() -> None:
    spec = _make_spec("m", "n", validator=lambda v: v > 0)
    assert spec.validator is not None
    assert spec.validator(5) is True
    assert spec.validator(-1) is False


def test_register_creates_then_extends(clean_registry: None) -> None:
    """First call creates the bucket; a second call extends the same list."""
    assert _SYNTH_MODULE not in config_schema._REGISTRY

    first = _make_spec(_SYNTH_MODULE, "alpha")
    register_required_fields(_SYNTH_MODULE, [first])
    assert config_schema._REGISTRY[_SYNTH_MODULE] == [first]

    second = _make_spec(_SYNTH_MODULE, "beta")
    register_required_fields(_SYNTH_MODULE, [second])
    assert config_schema._REGISTRY[_SYNTH_MODULE] == [first, second]


def test_register_accepts_generator(clean_registry: None) -> None:
    """``specs`` is an Iterable, so a one-shot generator must work too."""
    gen = (_make_spec(_SYNTH_MODULE, f"g{i}") for i in range(3))
    register_required_fields(_SYNTH_MODULE, gen)
    got = get_required_fields(_SYNTH_MODULE)
    assert [s.name for s in got] == ["g0", "g1", "g2"]


def test_get_required_fields_filtered_by_module(clean_registry: None) -> None:
    register_required_fields(_SYNTH_MODULE, [_make_spec(_SYNTH_MODULE, "x")])
    register_required_fields(_SYNTH_MODULE_B, [_make_spec(_SYNTH_MODULE_B, "y")])

    only_a = get_required_fields(_SYNTH_MODULE)
    assert {s.name for s in only_a} == {"x"}
    assert all(s.module == _SYNTH_MODULE for s in only_a)


def test_get_required_fields_unknown_module_returns_empty(clean_registry: None) -> None:
    assert get_required_fields("module_that_was_never_registered") == []


def test_get_required_fields_returns_a_copy(clean_registry: None) -> None:
    """The per-module result is a fresh list; mutating it must not corrupt
    the registry's stored bucket."""
    register_required_fields(_SYNTH_MODULE, [_make_spec(_SYNTH_MODULE, "x")])
    got = get_required_fields(_SYNTH_MODULE)
    got.append(_make_spec(_SYNTH_MODULE, "injected"))
    assert len(config_schema._REGISTRY[_SYNTH_MODULE]) == 1


def test_get_required_fields_none_aggregates_all_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``module=None`` flattens specs from every registered module.

    We isolate the registry to two synthetic modules so the assertion on the
    aggregate is exact regardless of what production modules registered.
    """
    isolated: Dict[str, List[RequiredFieldSpec]] = {
        _SYNTH_MODULE: [_make_spec(_SYNTH_MODULE, "x"), _make_spec(_SYNTH_MODULE, "y")],
        _SYNTH_MODULE_B: [_make_spec(_SYNTH_MODULE_B, "z")],
    }
    monkeypatch.setattr(config_schema, "_REGISTRY", isolated)

    everything = get_required_fields(None)
    assert {(s.module, s.name) for s in everything} == {
        (_SYNTH_MODULE, "x"),
        (_SYNTH_MODULE, "y"),
        (_SYNTH_MODULE_B, "z"),
    }


def test_get_required_fields_default_arg_matches_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolated: Dict[str, List[RequiredFieldSpec]] = {
        _SYNTH_MODULE: [_make_spec(_SYNTH_MODULE, "x")],
    }
    monkeypatch.setattr(config_schema, "_REGISTRY", isolated)
    assert get_required_fields() == get_required_fields(None)


def test_build_schema_dataframe_populated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The populated path: one row per spec, multi-path candidates joined with
    dots, and rows sorted by (module, name) with a reset index."""
    multi_path: list[PathSpec] = [("tax", "corporate_tax_rate_pct"), ("tax", "cit")]
    spec_b_late = RequiredFieldSpec(
        module=_SYNTH_MODULE_B,
        name="zeta",
        paths=multi_path,
        required=False,
        severity="warning",
        description="late-in-sort module",
    )
    spec_a1 = _make_spec(_SYNTH_MODULE, "beta", description="second by name")
    spec_a2 = _make_spec(_SYNTH_MODULE, "alpha", description="first by name")

    # Intentionally out of sorted order to prove sort_values runs.
    isolated: Dict[str, List[RequiredFieldSpec]] = {
        _SYNTH_MODULE_B: [spec_b_late],
        _SYNTH_MODULE: [spec_a1, spec_a2],
    }
    monkeypatch.setattr(config_schema, "_REGISTRY", isolated)

    df = build_schema_dataframe()

    assert list(df.columns) == [
        "module",
        "name",
        "path_candidates",
        "required",
        "severity",
        "description",
    ]
    assert len(df) == 3
    # Sorted by (module, name): synthetic_coverage_module (alpha, beta) then ..._b (zeta)
    assert list(df["module"]) == [_SYNTH_MODULE, _SYNTH_MODULE, _SYNTH_MODULE_B]
    assert list(df["name"]) == ["alpha", "beta", "zeta"]
    # Index reset after sort.
    assert list(df.index) == [0, 1, 2]
    # Multi-path candidate joined with "." per path.
    zeta_row = df[df["name"] == "zeta"].iloc[0]
    assert zeta_row["path_candidates"] == [
        "tax.corporate_tax_rate_pct",
        "tax.cit",
    ]
    assert bool(zeta_row["required"]) is False  # pandas stores np.bool_
    assert zeta_row["severity"] == "warning"


def test_build_schema_dataframe_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """The empty-registry path returns a typed-but-empty frame with the same
    columns (not an error and not a 1-row frame)."""
    monkeypatch.setattr(config_schema, "_REGISTRY", {})

    df = build_schema_dataframe()

    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert len(df) == 0
    assert list(df.columns) == [
        "module",
        "name",
        "path_candidates",
        "required",
        "severity",
        "description",
    ]


def test_build_schema_dataframe_real_registry_nonempty() -> None:
    """With the real, import-populated registry, the frame has rows for the
    production wind/era5 interface schemas — a smoke that the unfiltered build
    path works end-to-end against live registrations.

    Importing the schema modules guarantees their specs are registered even
    when this test runs in isolation (the registrations happen at import time).
    """
    import analytics.wind.era5_interface_schema  # noqa: F401
    import analytics.wind.wind_interface_schema  # noqa: F401

    df = build_schema_dataframe()
    assert not df.empty
    assert set(df.columns) >= {"module", "name", "path_candidates"}
    # Every path_candidates cell is a list of dotted strings.
    for cell in df["path_candidates"]:
        assert isinstance(cell, list)
        assert all(isinstance(p, str) for p in cell)
