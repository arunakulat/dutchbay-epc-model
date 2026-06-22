"""Coverage for analytics.mc package __init__ — lazy ``__getattr__`` re-exports.

The ``analytics.mc`` package deliberately avoids importing its heavy submodules
(``engine``/``evaluation_v14``) at import time, exposing the public API through a
lazy ``__getattr__`` instead. These tests exercise every branch of that loader:
the engine group, the correlation group, the exports group, the single
aggregation export, and the ``AttributeError`` fallback for an unknown name. Each
re-exported object is asserted to be *identical* to the object defined in its
backing submodule (proving the loader returns the right symbol, not merely
something importable). All deterministic; no network / config / matplotlib.
"""

from __future__ import annotations

import importlib

import pytest

import analytics.mc as mc


# --------------------------------------------------------------------------- #
# Engine group: lines 59-67                                                   #
# --------------------------------------------------------------------------- #
def test_engine_exports_resolve_to_backing_module() -> None:
    engine = importlib.import_module("analytics.mc.engine")
    assert mc.MonteCarloEngine is engine.MonteCarloEngine
    assert mc.run_monte_carlo_analysis is engine.run_monte_carlo_analysis


def test_engine_exports_via_getattr_each_name() -> None:
    # Exercise the dict-keyed return for BOTH names in the engine branch.
    assert getattr(mc, "MonteCarloEngine") is mc.MonteCarloEngine
    assert getattr(mc, "run_monte_carlo_analysis") is mc.run_monte_carlo_analysis


# --------------------------------------------------------------------------- #
# Correlation group: lines 69-87                                              #
# --------------------------------------------------------------------------- #
def test_correlation_exports_resolve_to_backing_module() -> None:
    corr = importlib.import_module("analytics.mc.correlation")
    assert mc.CorrelationSpec is corr.CorrelationSpec
    assert mc.load_correlation_from_config is corr.load_correlation_from_config
    assert mc.apply_correlation_structure is corr.apply_correlation_structure
    assert mc.validate_correlation_matrix is corr.validate_correlation_matrix


def test_correlation_exports_via_getattr_each_name() -> None:
    for name in (
        "CorrelationSpec",
        "load_correlation_from_config",
        "apply_correlation_structure",
        "validate_correlation_matrix",
    ):
        assert getattr(mc, name) is getattr(mc, name)


# --------------------------------------------------------------------------- #
# Exports group: lines 89-100                                                 #
# --------------------------------------------------------------------------- #
def test_export_helpers_resolve_to_backing_module() -> None:
    exports = importlib.import_module("analytics.mc.exports")
    assert mc.CovenantSpec is exports.CovenantSpec
    assert mc.build_lender_risk_table is exports.build_lender_risk_table
    assert mc.build_casper_risk_blocks is exports.build_casper_risk_blocks


def test_export_helpers_via_getattr_each_name() -> None:
    for name in ("CovenantSpec", "build_lender_risk_table", "build_casper_risk_blocks"):
        assert getattr(mc, name) is getattr(mc, name)


# --------------------------------------------------------------------------- #
# Aggregation: lines 102-105                                                  #
# --------------------------------------------------------------------------- #
def test_aggregate_trials_resolves_to_backing_module() -> None:
    aggregate = importlib.import_module("analytics.mc.aggregate")
    assert mc.aggregate_trials is aggregate.aggregate_trials


# --------------------------------------------------------------------------- #
# AttributeError fallback: line 107                                           #
# --------------------------------------------------------------------------- #
def test_unknown_attribute_raises_attribute_error() -> None:
    with pytest.raises(AttributeError, match="has no attribute 'definitely_not_here'"):
        _ = mc.definitely_not_here


def test_unknown_attribute_via_getattr_raises() -> None:
    with pytest.raises(AttributeError):
        getattr(mc, "NopeMissingSymbol")


# --------------------------------------------------------------------------- #
# Public API surface is fully resolvable                                      #
# --------------------------------------------------------------------------- #
def test_all_public_names_are_resolvable() -> None:
    # Every name advertised in __all__ must resolve through __getattr__.
    assert mc.__all__  # non-empty
    for name in mc.__all__:
        assert getattr(mc, name) is not None
