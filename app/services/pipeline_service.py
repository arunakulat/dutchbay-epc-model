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

from analytics.aep_provenance import (
    enforce_aep_provenance,
    register_scenario_approved_sources,
)
from analytics.aep_reconciliation import reconcile_capacity_factor_with_bankable_aep
from analytics.conditions_precedent import validate_conditions_precedent
from analytics.development_readiness import validate_development_readiness
from analytics.evidence_register import validate_evidence_register
from analytics.feasibility_sections import validate_feasibility_sections
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.run_manifest import build_run_manifest
from analytics.run_modes import RunMode, resolve_run_mode
from analytics.scenario_loader import _assert_fx_spot_consistency
from solar_resource.cashflow_adapter import solar_export_to_scenario_patch
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
    skip_bankable_reconciliation: bool = False,
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
        skip_bankable_reconciliation: When ``True``, skip the frozen-bankable AEP
            reconciliation (:func:`reconcile_capacity_factor_with_bankable_aep`).
            Set only for a SCREENING-grade run (a live location assessment
            computes its OWN P50/P75/P90 from scratch, so there is no frozen
            bankable P50 to reconcile against — comparing the fresh result to an
            unrelated committed P50 is the #996 false failure). All OTHER
            integrity guards (provenance, evidence, FX-spot, …) still run. The
            synchronous authored lender path never sets this — it keeps the
            strict guard (default ``False``).

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
    # This seam accepts an in-memory scenario dict, which reaches run_v14_pipeline via the
    # Mapping branch that bypasses load_scenario_config — so the load-time integrity guards
    # do NOT fire here. Re-apply them at the seam (the symmetric fix to the API boundary in
    # api.pipeline_api) so a web / notebook / batch caller cannot run a stale capacity that
    # disagrees with the bankable AEP, nor an unapproved/placeholder AEP source. Pure
    # detectors: they raise or no-op, changing no number (byte-identical economics); the
    # input is not mutated.
    guarded = dict(scenario)
    if not skip_bankable_reconciliation:
        # Screening runs (live location assessments) compute their own AEP, so the
        # frozen-bankable P50 in a base scenario is unrelated to them; comparing the
        # two is the #996 false failure. Every other guard below still runs.
        reconcile_capacity_factor_with_bankable_aep(guarded, "<inline>")
    register_scenario_approved_sources(guarded, "<inline>")
    enforce_aep_provenance(guarded, "<inline>")
    validate_evidence_register(guarded, "<inline>")
    validate_development_readiness(guarded, "<inline>")
    validate_conditions_precedent(guarded, "<inline>")
    validate_feasibility_sections(guarded, "<inline>")
    # PIPE-3 (#489): the FX spot cross-assert is a load-time guard too, and was the one
    # integrity detector this seam still skipped — so a web/notebook caller could submit a
    # scenario whose fx.rates.lkr_per_usd, fx.start_lkr_per_usd and fx.source.pinned_rate
    # disagree and get a self-inconsistent lender pack (the #236 stale-FX class) silently.
    # Run it here too (api.pipeline_api already does at its boundary). It is a no-op unless
    # two spot keys disagree, so committed scenarios are byte-identical; MC perturbation
    # paths do not route through this seam (they evaluate in-memory dicts directly).
    _assert_fx_spot_consistency(guarded, "<inline>")

    modules = list(validation_modules) if validation_modules is not None else None
    result = run_v14_pipeline(
        config=scenario,
        validation_mode=validation_mode,
        validation_modules=modules,
    )
    # Auditable run manifest (resolved-config SHA-256 + engine version + commit) so this
    # gateway's result is reproducible and tamper-evident (ICAEW posture). As of #577 the
    # engine (run_v14_pipeline) stamps the manifest itself from the RESOLVED config it
    # evaluated, so this guard normally no-ops; it is RETAINED as a stamp-if-absent
    # fallback (e.g. a monkeypatched engine in tests) so the web API (/cases,
    # /cases/report.*) and the integrated/hybrid seam (run_integrated_case, which routes
    # through here on its patched config) never omit the manifest the CaseResult and
    # report pack expose. Metadata only — no KPI is touched.
    if isinstance(result, dict) and not result.get("run_manifest"):
        result["run_manifest"] = build_run_manifest(
            scenario, validation_mode=validation_mode
        ).as_dict()
    return result


def run_integrated_case(
    scenario: Mapping[str, Any],
    wind_export: Mapping[str, Any] | None = None,
    *,
    solar_export: Mapping[str, Any] | None = None,
    scenario_name: str = "P75",
    adapter_mode: AdapterMode = "fill_if_absent",
    tolerance_pct: float = 0.5,
    solar_scenario_name: str = "P50",
    solar_adapter_mode: AdapterMode = "fill_if_absent",
    solar_tolerance_pct: float = 0.5,
    solar_technology: str = "solar",
    validation_mode: str = "strict",
    validation_modules: Sequence[str] | None = DEFAULT_VALIDATION_MODULES,
) -> dict[str, Any]:
    """Apply a frozen wind and/or solar export to the scenario, then run finance.

    Bridges frozen resource exports into the scenario via the drift-checked
    adapters, then runs the finance pipeline on the **patched** scenario. Pure
    in-memory; neither ``scenario`` nor either export is mutated (each adapter
    deep-copies). At least one of ``wind_export`` / ``solar_export`` must be
    supplied — for a plain scenario call :func:`run_finance_case` directly.

    The two exports patch *different* parts of the scenario, mirroring how each
    technology bills the cashflow:

    * ``wind_export`` (the output of ``WindPipeline.export_for_cashflow_model``)
      writes the project-level ``project.capacity_factor`` — the wind-only
      headline. Use it for a wind-only scenario.
    * ``solar_export`` (the output of
      ``solar_resource.cashflow_adapter.build_solar_cashflow_export``) writes the
      per-tech ``generation.technologies.<tech>`` block and re-blends the project
      headline. Use it for a hybrid — the declared per-tech wind stays, solar is
      overwritten, and ``project.capacity_factor`` re-blends.

    Both adapters are pvlib/PyWake-free (they consume frozen dicts), so this seam
    never pulls a resource toolchain into the finance path. Passing *both* a
    wind_export and a solar_export to a hybrid is a misuse — the wind adapter
    would clobber the blended headline with the wind-only capacity; pass only the
    solar_export for a hybrid.

    Args:
        scenario: A full v14 scenario mapping. Not mutated.
        wind_export: A wind-resource export dict, or ``None`` to skip wind.
        solar_export: A solar-resource export dict, or ``None`` to skip solar.
        scenario_name: P-level guard for the wind export.
        adapter_mode: Wind adapter mode (``overwrite`` | ``fill_if_absent`` |
            ``validate_only``).
        tolerance_pct: Wind adapter drift tolerance (percent).
        solar_scenario_name: P-level guard for the solar export (default ``P50`` —
            the producer is deterministic P50 today).
        solar_adapter_mode: Solar adapter mode.
        solar_tolerance_pct: Solar adapter drift tolerance (percent).
        solar_technology: ``generation.technologies`` key the solar export targets.
        validation_mode: ``"strict"`` (default) or ``"off"``.
        validation_modules: As ``run_finance_case``.

    Returns:
        The canonical pipeline result dict (see ``run_finance_case``).

    Raises:
        ValueError: Neither export supplied, or a ``scenario_name`` does not match
            its export's P-level.
        wind_resource.cashflow_adapter.WindAdapterDriftError: Wind drift beyond
            ``tolerance_pct``.
        solar_resource.cashflow_adapter.SolarAdapterDriftError: Solar drift beyond
            ``solar_tolerance_pct`` (or a per-tech capacity-identity mismatch).
        pydantic.ValidationError: An export fails schema validation.
        analytics.schema_guard.ConfigValidationError: As ``run_finance_case``.
    """
    if wind_export is None and solar_export is None:
        raise ValueError(
            "run_integrated_case requires a wind_export and/or a solar_export; "
            "for a plain scenario with no frozen resource export, call "
            "run_finance_case instead."
        )

    # #996 screening seam (config-first, single signal): a scenario that declares
    # run.mode=screening is a LIVE location assessment — it computes its own AEP, so
    # the wind export is the authoritative PHYSICAL source. Overwrite the fresh
    # capacity factor (no drift-check against the frozen lender-case CF) and stay
    # physical-only (the scenario's own tariff/FX are kept, never clobbered by a
    # possibly-stale export — #996 P2), and skip the frozen-bankable P50
    # reconciliation downstream. A non-screening (authored lender / developer / no-
    # mode) run is byte-identical to before: fill_if_absent drift-check + strict
    # reconciliation. The wind adapter is used only by this seam, so the switch is
    # fully contained.
    is_screening = resolve_run_mode(scenario) == RunMode.SCREENING
    wind_mode: AdapterMode = "overwrite" if is_screening else adapter_mode

    patched: Mapping[str, Any] = scenario
    if wind_export is not None:
        patched = wind_export_to_scenario_patch(
            wind_export,
            patched,
            scenario_name=scenario_name,
            adapter_mode=wind_mode,
            tolerance_pct=tolerance_pct,
            physical_only=is_screening,
        )
    if solar_export is not None:
        patched = solar_export_to_scenario_patch(
            solar_export,
            patched,
            scenario_name=solar_scenario_name,
            adapter_mode=solar_adapter_mode,
            tolerance_pct=solar_tolerance_pct,
            technology=solar_technology,
        )
    return run_finance_case(
        patched,
        validation_mode=validation_mode,
        validation_modules=validation_modules,
        skip_bankable_reconciliation=is_screening,
    )
