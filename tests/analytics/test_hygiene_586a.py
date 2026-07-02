"""Regression tests for the #586 dolphin A hygiene items (docs/header/naming shims).

Covers, at comment/docstring/alias-shim level only (no behavioral change to any
committed scenario):

- ``finance.debt_v14`` has a real module docstring (the corrupted
  ``# [File content too long...]`` header is gone).
- ``analytics.pipeline_v14_enhanced.PipelineMetrics.timestamp`` is tz-aware UTC
  (``datetime.utcnow()`` deprecation fix).
- ``analytics.mc.samplers.generate_lhs_samples``: ``shared_permutation_stream``
  is the canonical flag name; the deprecated ``common_random_numbers`` alias
  keeps working (identical output), warns, and conflicts fail loud.
- ``analytics.core.sensitivity_runner.run_sensitivity_analysis_from_path`` is
  the canonical path-based entry point; the historical
  ``run_sensitivity_analysis`` export remains as an additive alias.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

pytestmark = pytest.mark.unit

_BOUNDS = [(0.0, 1.0), (10.0, 20.0), (-5.0, 5.0)]


class TestDebtV14Header:
    def test_module_has_real_docstring(self) -> None:
        import finance.debt_v14 as debt_v14

        assert debt_v14.__doc__ is not None
        assert debt_v14.__doc__.startswith("Debt Planning Module")

    def test_corrupted_header_gone(self) -> None:
        import inspect

        import finance.debt_v14 as debt_v14

        source = inspect.getsource(debt_v14)
        assert "[File content too long" not in source


class TestPipelineMetricsTimestamp:
    def test_timestamp_is_tz_aware_utc(self) -> None:
        from analytics.pipeline_v14_enhanced import PipelineMetrics

        metrics = PipelineMetrics(
            total_runtime_sec=0.0,
            config_load_time_sec=0.0,
            validation_time_sec=0.0,
            cashflow_time_sec=0.0,
            debt_time_sec=0.0,
            kpi_time_sec=0.0,
            wacc_time_sec=0.0,
            fx_integration_time_sec=0.0,
            annual_rows_count=0,
            kpis_count=0,
        )
        parsed = datetime.fromisoformat(metrics.timestamp)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timezone.utc.utcoffset(None)


class TestLhsSamplerNamingShim:
    def test_new_name_matches_default(self) -> None:
        from analytics.mc.samplers import generate_lhs_samples

        default = generate_lhs_samples(n_trials=32, bounds=_BOUNDS, seed=7)
        explicit = generate_lhs_samples(
            n_trials=32, bounds=_BOUNDS, seed=7, shared_permutation_stream=True
        )
        np.testing.assert_array_equal(default, explicit)

    def test_deprecated_alias_identical_output_and_warns(self) -> None:
        from analytics.mc.samplers import generate_lhs_samples

        for flag in (True, False):
            new = generate_lhs_samples(
                n_trials=32, bounds=_BOUNDS, seed=7, shared_permutation_stream=flag
            )
            with pytest.warns(DeprecationWarning, match="common_random_numbers"):
                old = generate_lhs_samples(
                    n_trials=32, bounds=_BOUNDS, seed=7, common_random_numbers=flag
                )
            np.testing.assert_array_equal(new, old)

    def test_conflicting_names_fail_loud(self) -> None:
        from analytics.mc.samplers import generate_lhs_samples

        with pytest.warns(DeprecationWarning):
            with pytest.raises(ValueError, match="Conflicting"):
                generate_lhs_samples(
                    n_trials=8,
                    bounds=_BOUNDS,
                    seed=7,
                    shared_permutation_stream=True,
                    common_random_numbers=False,
                )

    def test_agreeing_names_accepted(self) -> None:
        from analytics.mc.samplers import generate_lhs_samples

        with pytest.warns(DeprecationWarning):
            out = generate_lhs_samples(
                n_trials=8,
                bounds=_BOUNDS,
                seed=7,
                shared_permutation_stream=True,
                common_random_numbers=True,
            )
        assert out.shape == (8, len(_BOUNDS))


class TestSensitivityRunnerNamingShim:
    def test_alias_is_same_object(self) -> None:
        from analytics.core.sensitivity_runner import (
            run_sensitivity_analysis,
            run_sensitivity_analysis_from_path,
        )

        assert run_sensitivity_analysis is run_sensitivity_analysis_from_path

    def test_both_names_exported_from_core(self) -> None:
        import analytics.core as core

        assert core.run_sensitivity_analysis is core.run_sensitivity_analysis_from_path
        assert "run_sensitivity_analysis" in core.__all__
        assert "run_sensitivity_analysis_from_path" in core.__all__

    def test_engine_orchestrator_unchanged(self) -> None:
        """The engine's same-named orchestrator is untouched (distinct object)."""
        from analytics.core.sensitivity_runner import (
            run_sensitivity_analysis_from_path,
        )
        from analytics.sensitivity.engine import run_sensitivity_analysis as engine_run

        assert engine_run is not run_sensitivity_analysis_from_path
