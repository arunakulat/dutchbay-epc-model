"""Execute sourcing tests with hostile inputs; unexpected skips are failures."""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pandas as pd
import pytest

from wind_resource import power_curve_sourcing

from . import test_power_curve_sourcing as sourcing_tests

CASES = ("list", "fetch", "thrust", "reference")


def _call(case: str) -> None:
    """Call the original collected test function, including its assertions."""
    if case in ("list", "fetch"):
        sourcing_tests.test_oedb_paths_if_available(case)
    elif case == "thrust":
        sourcing_tests.test_turbine_models_fetch_captures_thrust_when_present()
    else:
        assert case == "reference"
        sourcing_tests.test_fetch_turbine_models_if_available()


def _without_skip(case: str) -> None:
    """Make a swallowed failure fail this guard instead of skipping it."""
    try:
        _call(case)
    except pytest.skip.Exception as exc:
        pytest.fail(f"unexpected skip from original {case} test: {exc}")


@pytest.fixture
def installed_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[ModuleType]:
    """Provide discoverable packages while exercising the real source loaders."""
    wind = ModuleType("windpowerlib")
    wind.__spec__ = importlib.machinery.ModuleSpec("windpowerlib", loader=None)
    turbine = SimpleNamespace(
        nominal_power=7_500_000.0,
        power_curve=pd.DataFrame(
            {"wind_speed": [3.0, 12.0, 25.0], "value": [0.0, 7_500_000.0, 0.0]}
        ),
    )
    monkeypatch.setattr(
        wind,
        "get_turbine_types",
        lambda **kwargs: pd.DataFrame({"manufacturer": ["Enercon"]}),
        raising=False,
    )
    monkeypatch.setattr(wind, "WindTurbine", lambda **kwargs: turbine, raising=False)
    monkeypatch.setitem(sys.modules, "windpowerlib", wind)

    models = ModuleType("turbine_models")
    models.__spec__ = importlib.machinery.ModuleSpec("turbine_models", loader=None)
    models.__file__ = str(tmp_path / "__init__.py")
    data = tmp_path / "data"
    data.mkdir()
    for name, capacity, thrust in (
        ("IEA_Reference_10MW_198", 10638, True),
        ("2016CACost_NREL_Reference_10MW_205", 10000, False),
        ("IEA_Reference_15MW_240", 15000, False),
    ):
        frame = pd.DataFrame(
            {"Wind Speed [m/s]": [3.0, 12.0, 25.0], "Power [kW]": [0, capacity, 0]}
        )
        if thrust:
            frame["Ct [-]"] = [0.8, 0.7, 0.0]
        frame.to_csv(data / f"{name}.csv", index=False)
    monkeypatch.setitem(sys.modules, "turbine_models", models)
    for case in CASES:
        _without_skip(case)
    yield wind
    # The test's nested monkeypatch context must restore every hostile input.
    for case in CASES:
        _without_skip(case)


def test_empty_listing_fails(
    installed_sources: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty manufacturer listing reaches the original nonempty assertion."""
    with monkeypatch.context() as patch:
        patch.setattr(
            installed_sources,
            "get_turbine_types",
            lambda **kwargs: pd.DataFrame({"manufacturer": []}),
        )
        with pytest.raises(AssertionError):
            _without_skip("list")


def test_wrong_rated_capacity_fails(
    installed_sources: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real loaded turbine with the wrong nominal power fails the rating oracle."""
    turbine = installed_sources.WindTurbine()
    with monkeypatch.context() as patch:
        patch.setattr(turbine, "nominal_power", 1000.0)
        with pytest.raises(AssertionError):
            _without_skip("fetch")


@pytest.mark.parametrize("case", ["thrust", "reference"])
def test_malformed_curve_fails(
    installed_sources: ModuleType, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """Malformed source columns escape both reference test loading paths."""
    with monkeypatch.context() as patch:
        patch.setattr(
            pd, "read_csv", lambda *args, **kwargs: pd.DataFrame({"bad": [1]})
        )
        with pytest.raises(ValueError, match="missing wind-speed/power columns"):
            _without_skip(case)


def test_internal_listing_import_error_fails(
    installed_sources: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An internal listing ImportError is not evidence of package absence."""

    def broken_listing() -> list[str]:
        raise ImportError("internal listing failure")

    with monkeypatch.context() as patch:
        patch.setattr(power_curve_sourcing, "list_turbine_models", broken_listing)
        with pytest.raises(ImportError, match="internal listing failure"):
            _without_skip("reference")


@pytest.mark.parametrize("case", CASES)
def test_absent_optional_package_skips(
    monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """Genuine top-level package absence deliberately skips the original test."""
    package = "windpowerlib" if case in ("list", "fetch") else "turbine_models"
    monkeypatch.setitem(sys.modules, package, None)
    with pytest.raises(pytest.skip.Exception, match=package.replace("_", "[-_]")):
        _call(case)


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("missing_name", ["transitive_dependency", "package.internal"])
def test_broken_installed_package_fails(
    monkeypatch: pytest.MonkeyPatch, case: str, missing_name: str
) -> None:
    """Discoverable packages with failed internal imports must never skip."""
    package = "windpowerlib" if case in ("list", "fetch") else "turbine_models"
    missing_name = missing_name.replace("package", package)

    class BrokenPackage(importlib.abc.MetaPathFinder, importlib.abc.Loader):
        def find_spec(
            self,
            fullname: str,
            path: Sequence[str] | None = None,
            target: ModuleType | None = None,
        ) -> importlib.machinery.ModuleSpec | None:
            if fullname == package:
                return importlib.machinery.ModuleSpec(fullname, self)
            return None

        def create_module(
            self, spec: importlib.machinery.ModuleSpec
        ) -> ModuleType | None:
            return None

        def exec_module(self, module: ModuleType) -> None:
            raise ModuleNotFoundError(
                f"No module named {missing_name!r}", name=missing_name
            )

    monkeypatch.delitem(sys.modules, package, raising=False)
    monkeypatch.setattr(sys, "meta_path", [BrokenPackage(), *sys.meta_path])
    with pytest.raises(ImportError):
        _without_skip(case)


def test_guard_rejects_assertion_to_skip_mutant(
    installed_sources: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Observe the guard fail when the original assertion is caught as a skip."""
    original = sourcing_tests.test_oedb_paths_if_available

    def masked(path: str) -> None:
        try:
            original(path)
        except AssertionError:
            pytest.skip("deliberately masked assertion")

    with monkeypatch.context() as patch:
        patch.setattr(sourcing_tests, "test_oedb_paths_if_available", masked)
        patch.setattr(
            installed_sources,
            "get_turbine_types",
            lambda **kwargs: pd.DataFrame({"manufacturer": []}),
        )
        with pytest.raises(pytest.fail.Exception, match="unexpected skip"):
            _without_skip("list")
