"""Framework-agnostic service seam over the canonical v14 finance pipeline.

This is the single backend entry point for web / API / notebook / batch callers.
It wraps the canonical gateways — ``analytics.pipeline_v14_enhanced.run_v14_pipeline``
and ``wind_resource.cashflow_adapter.wind_export_to_scenario_patch`` — **without**
any file I/O, subprocess orchestration, or ``stdout`` printing. Those are CLI
concerns and live in ``run_full_pipeline_v14.py``.

Design rules:

* **Dolphin** — this module adds NO finance logic; it only delegates to the
  canonical engine. There is no parallel/duplicate pipeline here.
* **CESSPIT** — fail-fast: exceptions from the engine (e.g.
  ``ConfigValidationError`` in strict mode, ``WindAdapterDriftError`` on
  out-of-tolerance wind drift) propagate unchanged; nothing is swallowed.
* **CCCDIR** — no hardcoded scenario constants; a single named default for the
  validation-module set, overridable per call.
* **CASPER** — clean, fully-typed, documented interface; inputs are never
  mutated (the wrapped gateways deep-copy internally).
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, Sequence

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from wind_resource.cashflow_adapter import wind_export_to_scenario_patch

#: Default lender-grade validation modules. ``None`` validates all registered
#: modules; this named default keeps the common web path explicit (CCCDIR).
DEFAULT_VALIDATION_MODULES: tuple[str, ...] = ("cashflow", "debt")

AdapterMode = Literal["overwrite", "fill_if_absent", "validate_only"]


def run_finance_case(
    scenario: Mapping[str, Any],
    *,
    validation_mode: str = "strict",
    validation_modules: Sequence[str] | None = DEFAULT_VALIDATION_MODULES,
) -> dict[str, Any]:
    """Run the lender-grade finance pipeline from an in-memory scenario dict.

    The synchronous (frozen-AEP) path: on a scenario whose AEP is pre-computed
    this returns in ~0.05s, so it is safe to call inline from a request handler.

    Args:
        scenario: A full v14 scenario mapping — as a customer-facing form would
            assemble, or a parsed scenario YAML. Not mutated.
        validation_mode: ``"strict"`` (default) or ``"off"``.
        validation_modules: Logical modules to validate (e.g. ``("cashflow",
            "debt")``). ``None`` validates all registered modules.

    Returns:
        The canonical pipeline result dict — ``status``, ``kpis``
        (``project_irr``, ``equity_irr``, ``min_dscr``, ``avg_dscr``, ``llcr``,
        ``plcr``, ``project_npv``, ...), ``annual_rows``, ``debt_result``,
        ``equity_distribution``, ``metrics``, ``run_manifest``.

    Raises:
        analytics.schema_guard.ConfigValidationError: In strict mode, when the
            scenario is missing or has invalid required fields.
        Other engine exceptions propagate unchanged (fail-fast).
    """
    modules = list(validation_modules) if validation_modules is not None else None
    return run_v14_pipeline(
        config=scenario,
        validation_mode=validation_mode,
        validation_modules=modules,
    )


def run_integrated_case(
    scenario: Mapping[str, Any],
    wind_export: Mapping[str, Any],
    *,
    scenario_name: str = "P75",
    adapter_mode: AdapterMode = "fill_if_absent",
    tolerance_pct: float = 0.5,
    validation_mode: str = "strict",
    validation_modules: Sequence[str] | None = DEFAULT_VALIDATION_MODULES,
) -> dict[str, Any]:
    """Apply a frozen wind export to the scenario, then run finance.

    Bridges a wind-resource export (validated against ``WindCashflowExport`` at
    the boundary) into the scenario's ``resource.wind`` block via the
    drift-checked adapter, then runs the finance pipeline on the **patched**
    scenario. Pure in-memory; neither ``scenario`` nor ``wind_export`` is mutated
    (the adapter deep-copies).

    Args:
        scenario: A full v14 scenario mapping. Not mutated.
        wind_export: A wind-resource export dict (the output of
            ``WindPipeline.export_for_cashflow_model``).
        scenario_name: P-level guard — must match ``wind_export['scenario']``.
        adapter_mode: ``"overwrite"`` | ``"fill_if_absent"`` (default) |
            ``"validate_only"``.
        tolerance_pct: Acceptable symmetric drift (percent) before the adapter
            raises in the fill/validate modes.
        validation_mode: ``"strict"`` (default) or ``"off"``.
        validation_modules: As ``run_finance_case``.

    Returns:
        The canonical pipeline result dict (see ``run_finance_case``).

    Raises:
        wind_resource.cashflow_adapter.WindAdapterDriftError: A present scenario
            value disagrees with the wind export beyond ``tolerance_pct``.
        ValueError: ``scenario_name`` does not match the export's P-level.
        pydantic.ValidationError: The wind export fails schema validation.
        analytics.schema_guard.ConfigValidationError: As ``run_finance_case``.
    """
    patched = wind_export_to_scenario_patch(
        wind_export,
        scenario,
        scenario_name=scenario_name,
        adapter_mode=adapter_mode,
        tolerance_pct=tolerance_pct,
    )
    return run_finance_case(
        patched,
        validation_mode=validation_mode,
        validation_modules=validation_modules,
    )
