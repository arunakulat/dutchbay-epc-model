"""Tests for config/module_roles.yaml, lazy app.reports exports, and module_ledger (W1-1)."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import Any

import pytest
from pydantic import ValidationError

from app.ops.extras import declared_extras
from app.reports.module_ledger import (
    DEFAULT_MODULE_ROLES_PATH,
    KNOWN_OPTIONAL_EXTRAS,
    ExcelRepresentationKind,
    ModuleExecutionLedger,
    ModuleExecutionRecord,
    ModuleExecutionStatus,
    ModuleRoleRegistry,
    ModuleRoleSpec,
    OptionalExtraMode,
    PipelineStage,
    build_module_execution_ledger,
    load_module_role_registry,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = REPO_ROOT / "docs" / "MODULE_COVERAGE_MAP.md"


def _load_module_coverage_map_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "module_coverage_map_for_ledger_test",
        REPO_ROOT / "scripts" / "module_coverage_map.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _role_spec(
    module_path: str = "analytics.mc.engine",
    pipeline_stage: PipelineStage = PipelineStage.RISK_SENSITIVITY_OPT,
    role_description: str = "Executes seeded Monte Carlo risk simulations.",
    excel_representation: ExcelRepresentationKind = ExcelRepresentationKind.ENGINE_TABLE_PLUS_ROLLUP,
    optional_extras: tuple[str, ...] = (),
    extra_mode: OptionalExtraMode = OptionalExtraMode.NONE,
    notes: str | None = None,
) -> ModuleRoleSpec:
    return ModuleRoleSpec(
        module_path=module_path,
        pipeline_stage=pipeline_stage,
        role_description=role_description,
        excel_representation=excel_representation,
        optional_extras=optional_extras,
        extra_mode=extra_mode,
        notes=notes,
    )


def _complete_stage_specs(
    *,
    exclude_stage: PipelineStage | None = None,
) -> tuple[ModuleRoleSpec, ...]:
    """Build one minimal ModuleRoleSpec per PipelineStage for isolated registry tests."""
    specs: list[ModuleRoleSpec] = []
    for idx, stage in enumerate(PipelineStage):
        if stage is exclude_stage:
            continue
        specs.append(
            _role_spec(
                module_path=f"test_pkg.stage_{idx}",
                pipeline_stage=stage,
                role_description=f"Synthetic module covering stage {stage.value}.",
                excel_representation=ExcelRepresentationKind.GOVERNANCE_METADATA,
            )
        )
    return tuple(specs)


def _exec_record(
    module_path: str = "analytics.mc.engine",
    pipeline_stage: PipelineStage = PipelineStage.RISK_SENSITIVITY_OPT,
    role_description: str = "Executes seeded Monte Carlo risk simulations.",
    status: ModuleExecutionStatus = ModuleExecutionStatus.EXECUTED,
    excel_representation: ExcelRepresentationKind = ExcelRepresentationKind.ENGINE_TABLE_PLUS_ROLLUP,
    reason: str | None = None,
    key_outputs: tuple[str, ...] = (),
    provenance_refs: tuple[str, ...] = (),
    caveat: str | None = None,
) -> ModuleExecutionRecord:
    return ModuleExecutionRecord(
        module_path=module_path,
        pipeline_stage=pipeline_stage,
        role_description=role_description,
        status=status,
        excel_representation=excel_representation,
        reason=reason,
        key_outputs=key_outputs,
        provenance_refs=provenance_refs,
        caveat=caveat,
    )


def _record_from_spec(
    spec: ModuleRoleSpec,
    *,
    status: ModuleExecutionStatus = ModuleExecutionStatus.EXECUTED,
    reason: str | None = None,
    key_outputs: tuple[str, ...] = (),
    provenance_refs: tuple[str, ...] = (),
    caveat: str | None = None,
) -> ModuleExecutionRecord:
    return ModuleExecutionRecord(
        module_path=spec.module_path,
        pipeline_stage=spec.pipeline_stage,
        role_description=spec.role_description,
        status=status,
        excel_representation=spec.excel_representation,
        reason=reason,
        key_outputs=key_outputs,
        provenance_refs=provenance_refs,
        caveat=caveat,
    )


def test_default_registry_loads_and_validates() -> None:
    assert DEFAULT_MODULE_ROLES_PATH.is_file()
    registry = load_module_role_registry()
    assert isinstance(registry, ModuleRoleRegistry)
    assert registry.schema_version == "1.0"
    assert registry.stages == tuple(PipelineStage)
    assert len(registry.modules) > 0
    assert isinstance(registry.by_path, MappingProxyType)

    for stage in PipelineStage:
        by_stage = registry.by_stage(stage)
        assert by_stage, f"Expected at least one module in stage {stage.value!r}"
        assert all(spec.pipeline_stage is stage for spec in by_stage)

    assert registry.by_stage("governance") == registry.by_stage(
        PipelineStage.GOVERNANCE
    )
    assert (
        registry.get("app.reports.module_ledger").pipeline_stage
        is PipelineStage.GOVERNANCE
    )
    assert (
        registry.get("run_full_pipeline_v14").pipeline_stage
        is PipelineStage.CORE_FINANCE
    )
    assert "analytics.mc.engine" in registry

    # Verify factual remediation fixes against source contracts.
    solar_report = registry.get("app.reports.solar_assessment")
    assert "bankable" not in solar_report.role_description.lower()
    assert "not a lender representation" in solar_report.role_description.lower()
    assert solar_report.optional_extras == ("solar", "report", "gis")
    assert solar_report.extra_mode is OptionalExtraMode.CASPER_FALLBACK

    assert (
        registry.get("analytics.site_analysis_blocks").pipeline_stage
        is PipelineStage.GOVERNANCE
    )

    crossval = registry.get("wind_resource.crossval")
    assert crossval.optional_extras == ()
    assert crossval.extra_mode is OptionalExtraMode.NONE

    for mod in (
        "solar_resource.pv_bess_sizing",
        "solar_resource.pv_bess_sizing_runner",
    ):
        spec = registry.get(mod)
        assert spec.optional_extras == ("solar", "gis")
        assert spec.extra_mode is OptionalExtraMode.REQUIRED

    wind_pipeline = registry.get("wind_resource.wind_pipeline")
    assert wind_pipeline.optional_extras == ("wind",)
    assert wind_pipeline.extra_mode is OptionalExtraMode.REQUIRED

    arco = registry.get("wind_resource.arco_assessment")
    assert arco.optional_extras == ("wind",)
    assert arco.extra_mode is OptionalExtraMode.CASPER_FALLBACK

    for mod in (
        "analytics.grid.evaluate_grid",
        "analytics.grid.short_circuit",
        "analytics.grid.harmonics",
        "analytics.grid.reactive_screen",
    ):
        spec = registry.get(mod)
        assert spec.optional_extras == ("grid",)
        assert spec.extra_mode is OptionalExtraMode.CASPER_FALLBACK

    security = registry.get("app.api.security")
    assert security.optional_extras == ("api",)
    assert security.extra_mode is OptionalExtraMode.REQUIRED

    assert registry.get("analytics.gis.gis_export").optional_extras == ("gis", "wind")
    assert registry.get("analytics.gis.pv_array_layout").optional_extras == (
        "gis",
        "solar",
    )
    assert registry.get("analytics.gis.shadow_flicker").optional_extras == (
        "gis",
        "solar",
    )
    assert registry.get("app.api.jobs_router").optional_extras == ("api", "jobs")
    assert registry.get(
        "app.reports.synthetic_qsts_finance_report"
    ).optional_extras == ("report", "ingestion")
    assert registry.get("wind_resource.layout_optimizer").optional_extras == (
        "micrositing",
        "wind",
    )
    assert registry.get("analytics.sensitivity.global_sa").optional_extras == (
        "feasibility",
    )

    with pytest.raises(KeyError, match="not registered"):
        registry.get("nonexistent.module.path")

    with pytest.raises(ValueError):
        registry.by_stage("not_a_real_stage")


def test_registry_completeness_against_coverage_map_and_disk() -> None:
    mcm = _load_module_coverage_map_script()
    registry = load_module_role_registry()

    map_rows = mcm.parse_map(MAP_PATH.read_text(encoding="utf-8"))
    expected_modules = {row.module for row in map_rows} | {"run_full_pipeline_v14"}
    registered_modules = {spec.module_path for spec in registry.modules}

    missing = sorted(expected_modules - registered_modules)
    stale = sorted(registered_modules - expected_modules)
    assert not missing, f"Modules missing from config/module_roles.yaml: {missing}"
    assert not stale, f"Stale/unmapped modules in config/module_roles.yaml: {stale}"
    assert "app.reports.module_ledger" in {row.module for row in map_rows}

    for spec in registry.modules:
        rel_stem = spec.module_path.replace(".", "/")
        py_file = REPO_ROOT / f"{rel_stem}.py"
        pkg_init = REPO_ROOT / rel_stem / "__init__.py"
        exists = py_file.is_file() or pkg_init.is_file()
        assert exists, f"Registered module_path {spec.module_path!r} missing on disk"


def test_registry_optional_extras_match_pyproject() -> None:
    pyproject_extras = set(declared_extras())
    assert KNOWN_OPTIONAL_EXTRAS <= pyproject_extras
    registry = load_module_role_registry()
    used_extras = {extra for spec in registry.modules for extra in spec.optional_extras}
    assert used_extras == KNOWN_OPTIONAL_EXTRAS


def test_module_ledger_imports_remain_pure_and_cold_import_safe() -> None:
    source_path = REPO_ROOT / "app" / "reports" / "module_ledger.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    forbidden = [
        name
        for name in sorted(imported_modules)
        if name == "finance"
        or name.startswith("finance.")
        or name == "analytics"
        or name.startswith("analytics.")
        or name == "app"
        or name.startswith("app.")
    ]
    assert not forbidden, f"Forbidden imports in module_ledger.py: {forbidden}"

    # Real cold-import probe of `import app.reports.module_ledger`: app/reports/__init__.py
    # uses PEP 562 lazy loading, so importing module_ledger loads ONLY app, app.reports,
    # and app.reports.module_ledger (zero report_model, analytics.*, finance.*, or api.*).
    cold_probe = (
        "import sys; "
        "import app.reports.module_ledger as ml; "
        "assert 'app.reports' in sys.modules; "
        "assert 'app.reports.module_ledger' in sys.modules; "
        "leaked = sorted(m for m in sys.modules if "
        "m in ('analytics', 'finance', 'api', 'app.reports.report_model', "
        "'app.reports.renderer', 'app.reports.report_config') "
        "or m.startswith(('analytics.', 'finance.', 'api.'))); "
        "assert not leaked, f'Unexpected cold-import leak: {leaked}'; "
        "reg = ml.load_module_role_registry(); "
        "assert len(reg.modules) > 0"
    )
    proc = subprocess.run(
        [sys.executable, "-c", cold_probe],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr

    # Verify PEP 562 lazy package exports on app.reports still work identically.
    lazy_export_probe = textwrap.dedent("""
        import app.reports as reports
        from app.reports import (
            ReportConfig,
            load_report_config,
            ReportContext,
            build_report_context,
            ReportDependencyError,
            render_report_html,
            render_report_pdf,
        )
        assert set(reports.__all__) <= set(dir(reports))
        assert ReportConfig is not None and callable(load_report_config)
        assert ReportContext is not None and callable(build_report_context)
        assert issubclass(ReportDependencyError, RuntimeError)
        assert callable(render_report_html) and callable(render_report_pdf)
        try:
            _ = reports.does_not_exist_attr
        except AttributeError:
            pass
        else:
            raise AssertionError("Expected AttributeError for unknown attr")
        """)
    lazy_proc = subprocess.run(
        [sys.executable, "-c", lazy_export_probe],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
    )
    assert lazy_proc.returncode == 0, lazy_proc.stderr


def test_models_are_frozen_and_forbid_extra_fields() -> None:
    spec = _role_spec()
    with pytest.raises(ValidationError):
        spec.notes = "mutated"  # type: ignore[misc]

    registry = ModuleRoleRegistry(
        schema_version="1.0",
        stages=tuple(PipelineStage),
        modules=_complete_stage_specs(),
    )
    with pytest.raises(ValidationError):
        registry.schema_version = "2.0"  # type: ignore[misc,assignment]
    with pytest.raises(TypeError):
        registry.by_path["fake.mod"] = spec  # type: ignore[index]
    with pytest.raises(TypeError):
        registry._by_path["fake.mod"] = spec  # type: ignore[index]

    record = _exec_record()
    with pytest.raises(ValidationError):
        record.reason = "mutated"  # type: ignore[misc]

    ledger = build_module_execution_ledger("lender", [record])
    with pytest.raises(ValidationError):
        ledger.profile = "mutated"  # type: ignore[misc]
    with pytest.raises(TypeError):
        ledger.summary_counts["executed"] = 99  # type: ignore[index]

    with pytest.raises(ValidationError):
        ModuleRoleSpec(
            module_path="analytics.mc.engine",
            pipeline_stage=PipelineStage.RISK_SENSITIVITY_OPT,
            role_description="Executes seeded Monte Carlo risk simulations.",
            excel_representation=ExcelRepresentationKind.ENGINE_TABLE_PLUS_ROLLUP,
            unknown_key="nope",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        ModuleRoleRegistry(
            schema_version="1.0",
            stages=tuple(PipelineStage),
            modules=_complete_stage_specs(),
            unexpected="bad",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        ModuleExecutionRecord(
            module_path="analytics.mc.engine",
            pipeline_stage=PipelineStage.RISK_SENSITIVITY_OPT,
            role_description="Executes seeded Monte Carlo risk simulations.",
            status=ModuleExecutionStatus.EXECUTED,
            excel_representation=ExcelRepresentationKind.ENGINE_TABLE_PLUS_ROLLUP,
            extra_field=123,  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        ModuleExecutionLedger(
            profile="lender",
            records=(record,),
            bogus=True,  # type: ignore[call-arg]
        )


def test_registry_negative_controls_cesspit() -> None:
    base_specs = _complete_stage_specs()
    spec_a = _role_spec("analytics.mc.engine")
    spec_dup = _role_spec("analytics.mc.engine")

    with pytest.raises(ValidationError, match="Duplicate module_path"):
        ModuleRoleRegistry(
            schema_version="1.0",
            stages=tuple(PipelineStage),
            modules=(*base_specs, spec_a, spec_dup),
        )

    with pytest.raises(ValidationError, match="Missing pipeline stage"):
        ModuleRoleRegistry(
            schema_version="1.0",
            stages=tuple(PipelineStage)[:-1],
            modules=base_specs,
        )

    with pytest.raises(ValidationError, match="Duplicate pipeline stage"):
        ModuleRoleRegistry(
            schema_version="1.0",
            stages=(*tuple(PipelineStage), PipelineStage.GOVERNANCE),
            modules=base_specs,
        )

    swapped_stages = (
        PipelineStage.SITE_GIS,
        PipelineStage.GOVERNANCE,
        *tuple(PipelineStage)[2:],
    )
    with pytest.raises(ValidationError, match="canonical order"):
        ModuleRoleRegistry(
            schema_version="1.0",
            stages=swapped_stages,
            modules=base_specs,
        )

    with pytest.raises(ValidationError, match="at least one module"):
        ModuleRoleRegistry(
            schema_version="1.0",
            stages=tuple(PipelineStage),
            modules=(),
        )

    with pytest.raises(ValidationError, match="empty stage"):
        ModuleRoleRegistry(
            schema_version="1.0",
            stages=tuple(PipelineStage),
            modules=_complete_stage_specs(exclude_stage=PipelineStage.GRID_QSTS),
        )

    for bad_extra in ("unknown_extra", "", "dev", "wind "):
        with pytest.raises(ValidationError, match="optional_extras"):
            _role_spec(
                optional_extras=(bad_extra,),
                extra_mode=OptionalExtraMode.REQUIRED,
            )

    with pytest.raises(ValidationError, match="Duplicate entries in optional_extras"):
        _role_spec(
            optional_extras=("wind", "wind"),
            extra_mode=OptionalExtraMode.REQUIRED,
        )

    with pytest.raises(ValidationError, match="cannot use extra_mode='none'"):
        _role_spec(
            optional_extras=("wind",),
            extra_mode=OptionalExtraMode.NONE,
        )

    for bad_mode in (OptionalExtraMode.REQUIRED, OptionalExtraMode.CASPER_FALLBACK):
        with pytest.raises(ValidationError, match="must use extra_mode='none'"):
            _role_spec(optional_extras=(), extra_mode=bad_mode)

    for short_desc in ("   short   ", "", "   "):
        with pytest.raises(ValidationError):
            _role_spec(role_description=short_desc)
        with pytest.raises(ValidationError):
            _exec_record(role_description=short_desc)

    for blank in ("", "   ", "\t\n"):
        with pytest.raises(ValidationError):
            _role_spec(notes=blank)
        with pytest.raises(ValidationError):
            _exec_record(caveat=blank)
        with pytest.raises(ValidationError):
            _exec_record(status=ModuleExecutionStatus.EXECUTED, reason=blank)
        with pytest.raises(ValidationError):
            _exec_record(status=ModuleExecutionStatus.GUARD_PASSED, reason=blank)
        with pytest.raises(ValidationError):
            ModuleExecutionLedger(profile=blank, records=())

    trimmed_spec = _role_spec(notes="  Useful provenance note.  ")
    assert trimmed_spec.notes == "Useful provenance note."
    trimmed_rec = _exec_record(
        status=ModuleExecutionStatus.EXECUTED,
        reason="  Explicit note.  ",
        caveat="  Screening only.  ",
    )
    assert trimmed_rec.reason == "Explicit note."
    assert trimmed_rec.caveat == "Screening only."


@pytest.mark.parametrize(
    "status",
    [
        ModuleExecutionStatus.DEGRADED,
        ModuleExecutionStatus.FAILED,
        ModuleExecutionStatus.GUARD_REFUSED,
        ModuleExecutionStatus.NOT_APPLICABLE,
        ModuleExecutionStatus.SKIPPED_MISSING_INPUTS,
        ModuleExecutionStatus.SKIPPED_OPTIONAL_EXTRA,
        ModuleExecutionStatus.SKIPPED_SYNC_PROFILE,
    ],
)
@pytest.mark.parametrize("bad_reason", [None, "", "   "])
def test_execution_record_requires_non_empty_reason_for_non_run_statuses(
    status: ModuleExecutionStatus,
    bad_reason: str | None,
) -> None:
    if bad_reason is None:
        with pytest.raises(ValidationError, match="requires a non-empty reason"):
            _exec_record(status=status, reason=bad_reason)
    else:
        with pytest.raises(ValidationError):
            _exec_record(status=status, reason=bad_reason)

    valid = _exec_record(status=status, reason="Explicitly skipped or degraded.")
    assert valid.status is status


@pytest.mark.parametrize(
    "status",
    [ModuleExecutionStatus.EXECUTED, ModuleExecutionStatus.GUARD_PASSED],
)
def test_execution_record_allows_omitted_or_non_empty_reason_when_executed_or_passed(
    status: ModuleExecutionStatus,
) -> None:
    record = _exec_record(status=status, reason=None)
    assert record.status is status
    assert record.reason is None

    noted = _exec_record(status=status, reason="Completed with full inputs.")
    assert noted.reason == "Completed with full inputs."


def test_load_module_role_registry_fails_loud_on_malformed_yaml(tmp_path: Path) -> None:
    missing_path = tmp_path / "does_not_exist.yaml"
    with pytest.raises(FileNotFoundError):
        load_module_role_registry(missing_path)

    empty_yaml = tmp_path / "empty.yaml"
    empty_yaml.write_text("# comment only\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Expected YAML mapping.*NoneType"):
        load_module_role_registry(empty_yaml)

    null_yaml = tmp_path / "null.yaml"
    null_yaml.write_text("null\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Expected YAML mapping.*NoneType"):
        load_module_role_registry(null_yaml)

    non_mapping = tmp_path / "list.yaml"
    non_mapping.write_text("- item1\n- item2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Expected YAML mapping"):
        load_module_role_registry(non_mapping)

    dup_top_key = tmp_path / "dup_top_key.yaml"
    dup_top_key.write_text(
        textwrap.dedent("""
            schema_version: "1.0"
            schema_version: "1.0"
            stages: []
            modules: []
            """),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate YAML mapping key"):
        load_module_role_registry(dup_top_key)

    dup_entry_key = tmp_path / "dup_entry_key.yaml"
    dup_entry_key.write_text(
        textwrap.dedent("""
            schema_version: "1.0"
            stages:
              - governance
              - site_gis
              - resource_yield
              - tech_hybrid_bess
              - grid_qsts
              - cost_levies_epc
              - core_finance
              - risk_sensitivity_opt
              - reporting_delivery
            modules:
              - module_path: analytics.aep_provenance
                pipeline_stage: governance
                pipeline_stage: core_finance
                role_description: Enforces AEP source-provenance verification for runs.
                excel_representation: governance_metadata
            """),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate YAML mapping key"):
        load_module_role_registry(dup_entry_key)

    empty_modules = tmp_path / "empty_modules.yaml"
    empty_modules.write_text(
        textwrap.dedent("""
            schema_version: "1.0"
            stages:
              - governance
              - site_gis
              - resource_yield
              - tech_hybrid_bess
              - grid_qsts
              - cost_levies_epc
              - core_finance
              - risk_sensitivity_opt
              - reporting_delivery
            modules: []
            """),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="at least one module"):
        load_module_role_registry(empty_modules)

    bad_version = tmp_path / "bad_version.yaml"
    bad_yaml = textwrap.dedent("""
        schema_version: "2.0"
        stages:
          - governance
          - site_gis
          - resource_yield
          - tech_hybrid_bess
          - grid_qsts
          - cost_levies_epc
          - core_finance
          - risk_sensitivity_opt
          - reporting_delivery
        modules: []
        """)
    bad_version.write_text(bad_yaml, encoding="utf-8")
    with pytest.raises(ValidationError):
        load_module_role_registry(bad_version)

    missing_version = tmp_path / "missing_version.yaml"
    missing_version.write_text("stages: []\nmodules: []\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_module_role_registry(missing_version)


def test_build_module_execution_ledger_validates_uniqueness_membership_and_counts() -> (
    None
):
    registry = load_module_role_registry()
    mc_spec = registry.get("analytics.mc.engine")
    pp_spec = registry.get("analytics.grid.pandapower_screening")
    aep_spec = registry.get("analytics.aep_provenance")
    sc_spec = registry.get("analytics.grid.short_circuit")

    rec1 = _record_from_spec(
        mc_spec,
        status=ModuleExecutionStatus.EXECUTED,
        key_outputs=("mc_p50_irr", "mc_p95_dscr"),
        provenance_refs=("run_manifest:sha256",),
    )
    rec2 = _record_from_spec(
        pp_spec,
        status=ModuleExecutionStatus.SKIPPED_OPTIONAL_EXTRA,
        reason="Optional extra [grid] is not installed.",
        caveat="Closed-form fallback used.",
    )
    rec3 = _record_from_spec(
        aep_spec,
        status=ModuleExecutionStatus.GUARD_PASSED,
    )
    rec4 = _record_from_spec(
        sc_spec,
        status=ModuleExecutionStatus.DEGRADED,
        reason="Closed-form Thevenin fallback executed because [grid] is absent.",
        caveat="method=closed_form",
    )

    ledger = build_module_execution_ledger(
        "sync_lender",
        [rec1, rec2, rec3, rec4],
        registry=registry,
    )
    assert ledger.profile == "sync_lender"
    assert len(ledger.records) == 4
    assert ledger.summary_counts["executed"] == 1
    assert ledger.summary_counts["degraded"] == 1
    assert ledger.summary_counts["skipped_optional_extra"] == 1
    assert ledger.summary_counts["guard_passed"] == 1
    assert ledger.summary_counts["failed"] == 0
    assert sum(ledger.summary_counts.values()) == 4
    assert set(ledger.summary_counts) == {s.value for s in ModuleExecutionStatus}

    with pytest.raises(TypeError):
        ledger.summary_counts["executed"] = 99  # type: ignore[index]

    round_tripped = ModuleExecutionLedger.model_validate_json(ledger.model_dump_json())
    assert round_tripped == ledger

    dumped: dict[str, Any] = ledger.model_dump()
    assert dumped["summary_counts"]["executed"] == 1
    assert dumped["summary_counts"]["degraded"] == 1

    # Duplicate module_path fails loud
    with pytest.raises(ValueError, match="Duplicate module_path"):
        build_module_execution_ledger("sync_lender", [rec1, rec1], registry=registry)

    with pytest.raises(ValueError, match="Duplicate module_path"):
        build_module_execution_ledger("sync_lender", [rec1, rec1])

    # Unregistered module_path fails loud when registry is provided
    unregistered = _exec_record(module_path="unregistered.fake.module")
    with pytest.raises(ValueError, match="Unregistered module_path"):
        build_module_execution_ledger(
            "sync_lender", [rec1, unregistered], registry=registry
        )

    # Registry metadata disagreement fails loud
    bad_stage = rec1.model_copy(update={"pipeline_stage": PipelineStage.CORE_FINANCE})
    with pytest.raises(ValueError, match="pipeline_stage"):
        build_module_execution_ledger("sync_lender", [bad_stage], registry=registry)

    bad_excel = rec1.model_copy(
        update={"excel_representation": ExcelRepresentationKind.FORMULA}
    )
    with pytest.raises(ValueError, match="excel_representation"):
        build_module_execution_ledger("sync_lender", [bad_excel], registry=registry)

    bad_role = rec1.model_copy(
        update={"role_description": "Drifted role description for MC engine."}
    )
    with pytest.raises(ValueError, match="role_description"):
        build_module_execution_ledger("sync_lender", [bad_role], registry=registry)

    bad_skip_extra = _record_from_spec(
        aep_spec,
        status=ModuleExecutionStatus.SKIPPED_OPTIONAL_EXTRA,
        reason="Claimed missing optional extra on core module.",
    )
    with pytest.raises(ValueError, match="optional_extras is empty"):
        build_module_execution_ledger(
            "sync_lender", [bad_skip_extra], registry=registry
        )

    # Without registry validation, synthetic module paths are permitted
    unvalidated = build_module_execution_ledger("unit_synthetic", [unregistered])
    assert unvalidated.summary_counts["executed"] == 1

    # Tampered or mismatched summary_counts fails loud
    with pytest.raises(ValidationError, match="summary_counts do not match"):
        ModuleExecutionLedger(
            profile="sync_lender",
            records=(rec1,),
            summary_counts={},
        )

    with pytest.raises(ValidationError, match="summary_counts do not match"):
        ModuleExecutionLedger(
            profile="sync_lender",
            records=(rec1,),
            summary_counts={**dict(ledger.summary_counts), "executed": 99},
        )


@pytest.mark.parametrize(
    ("yaml_value", "mode"),
    [
        ("!!set {wind: null}", "required"),
        ("!!set {wind: null, wind: null}", "required"),
        ("!!pairs []", "none"),
        ("!!omap []", "none"),
    ],
)
def test_tagged_collections_cannot_normalize_to_valid_extras(
    tmp_path: Path, yaml_value: str, mode: str
) -> None:
    modules = [spec.model_dump(mode="json") for spec in _complete_stage_specs()]
    modules[0].update(extra_mode=mode, optional_extras="EXTRAS_PLACEHOLDER")
    template = json.dumps(
        {"schema_version": "1.0", "stages": list(PipelineStage), "modules": modules}
    )
    path = tmp_path / "registry.yaml"
    plain_sequence = "[wind]" if mode == "required" else "[]"
    path.write_text(template.replace('"EXTRAS_PLACEHOLDER"', plain_sequence))
    assert load_module_role_registry(path).modules[0].extra_mode.value == mode
    path.write_text(template.replace('"EXTRAS_PLACEHOLDER"', yaml_value))
    with pytest.raises(ValueError, match="plain YAML"):
        load_module_role_registry(path)


def test_duplicate_merge_keys_cannot_disappear_during_flattening(
    tmp_path: Path,
) -> None:
    path = tmp_path / "registry.yaml"
    path.write_text('<<: {schema_version: "1.0"}\n<<: {stages: []}\nmodules: []\n')
    with pytest.raises(ValueError, match="Duplicate YAML mapping key '<<'"):
        load_module_role_registry(path)


@pytest.mark.parametrize("supplied", [True, "1", 1.0])
def test_json_summary_counts_require_integer_tokens(supplied: object) -> None:
    ledger = build_module_execution_ledger("fixture", [_exec_record()])
    payload = json.loads(ledger.model_dump_json())
    payload["summary_counts"]["executed"] = supplied
    with pytest.raises(ValidationError, match="summary_counts.executed"):
        ModuleExecutionLedger.model_validate_json(json.dumps(payload))
    del payload["summary_counts"]
    assert ModuleExecutionLedger.model_validate_json(json.dumps(payload)) == ledger


@pytest.mark.parametrize(
    ("module", "paths"),
    [
        ("run_full_pipeline_v14", {"frozen": (), "auto_wind": ("wind",)}),
        ("wind_resource.aep_summary", {"frozen": (), "live_wake": ("wind",)}),
        ("app.api.jobs_router", {"memory": ("api",), "redis": ("api", "jobs")}),
        ("app.api.main", {"base": ("api",), "pdf_report": ("api", "report")}),
        ("app.reports.renderer", {"html": (), "pdf_report": ("report",)}),
        ("app.web.routes", {"base": ("api",), "pdf_report": ("api", "report")}),
    ],
)
def test_conditional_skips_identify_the_selected_runtime_path(
    module: str, paths: dict[str, tuple[str, ...]]
) -> None:
    registry = load_module_role_registry()
    role = registry.get(module)
    assert role.extra_mode.value == "conditional"
    assert {p.name: p.required_extras for p in role.dependency_paths} == paths
    template = _record_from_spec(role).model_dump()

    def record_ledger(**fields: Any) -> ModuleExecutionLedger:
        record = ModuleExecutionRecord.model_validate({**template, **fields})
        return build_module_execution_ledger("fixture", [record], registry)

    for path_name, required in paths.items():
        assert record_ledger(dependency_path=path_name).summary_counts["executed"] == 1
        for extra in {*role.optional_extras, "gis"}:
            skip = dict(
                status="skipped_optional_extra",
                dependency_path=path_name,
                missing_extra=extra,
                reason=f"Missing [{extra}] for {path_name}.",
            )
            if extra in required:
                ledger = record_ledger(**skip)
                assert ledger.summary_counts["skipped_optional_extra"] == 1
                assert (
                    ModuleExecutionLedger.model_validate_json(ledger.model_dump_json())
                    == ledger
                )
            else:
                with pytest.raises(ValueError, match="not declared"):
                    record_ledger(**skip)

    with pytest.raises(ValueError, match="Unknown dependency_path"):
        record_ledger(dependency_path="other")
    skip_fields = {
        "status": "skipped_optional_extra",
        "reason": "Dependency unavailable.",
    }
    with pytest.raises(ValueError, match="dependency_path"):
        record_ledger(**skip_fields, missing_extra=role.optional_extras[0])
    with pytest.raises(ValueError, match="missing_extra"):
        record_ledger(
            **skip_fields,
            dependency_path=next(name for name, required in paths.items() if required),
        )
    with pytest.raises(ValidationError, match="missing_extra"):
        record_ledger(missing_extra=role.optional_extras[0])


def test_api_pdf_dependency_guard_matches_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "weasyprint", None)

    from fastapi import HTTPException

    from app.api.main import health, run_case_report_pdf
    from app.models.inputs import WindFarmInputs

    inputs = WindFarmInputs(
        site_name="Dependency guard test",
        capacity_mw=148.9,
        capacity_factor=0.332,
        project_life_years=20,
        ppa_price_lkr_per_kwh=20.3,
        ppa_term_years=20,
        capex_total_usd=159_600_000.0,
        opex_annual_usd=5_000_000.0,
        fx_start_lkr_per_usd=333.79,
    )
    assert health()["status"] == "ok"
    with pytest.raises(HTTPException) as refused_pdf:
        run_case_report_pdf(inputs)
    assert refused_pdf.value.status_code == 503
    assert "[report]" in refused_pdf.value.detail

    registry = load_module_role_registry()
    role = registry.get("app.api.main")
    template = _record_from_spec(
        role,
        status=ModuleExecutionStatus.SKIPPED_OPTIONAL_EXTRA,
        reason=refused_pdf.value.detail,
    ).model_dump()
    pdf_skip = ModuleExecutionRecord.model_validate(
        {**template, "dependency_path": "pdf_report", "missing_extra": "report"}
    )
    ledger = build_module_execution_ledger("sync_lender", [pdf_skip], registry)
    assert ledger.records == (pdf_skip,)
    assert ledger.summary_counts["skipped_optional_extra"] == 1

    base_skip = pdf_skip.model_copy(update={"dependency_path": "base"})
    with pytest.raises(ValueError, match="Missing extra 'report' is not declared"):
        build_module_execution_ledger("sync_lender", [base_skip], registry)


@pytest.mark.parametrize(
    ("mode", "paths", "error"),
    [
        ("required", [("offline", [])], "require extra_mode"),
        ("conditional", [], "distinct requirements"),
        (
            "conditional",
            [("first", ["wind"]), ("second", ["wind"])],
            "distinct requirements",
        ),
        (
            "conditional",
            [("same", []), ("same", ["wind"])],
            "Duplicate dependency path",
        ),
        ("conditional", [("offline", []), ("online", ["jobs"])], "union"),
        (
            "conditional",
            [("offline", []), ("online", ["wind", "wind"])],
            "Duplicate entries",
        ),
        (
            "conditional",
            [("offline", []), ("online", ["bogus"])],
            "Unknown optional_extras",
        ),
    ],
)
def test_conditional_declarations_reject_inconsistent_requirements(
    mode: str, paths: list[tuple[str, list[str]]], error: str
) -> None:
    fields = _role_spec().model_dump()
    fields.update(
        extra_mode=mode,
        optional_extras=["wind"],
        dependency_paths=[
            {"name": name, "required_extras": extras} for name, extras in paths
        ],
    )
    with pytest.raises(ValidationError, match=error):
        ModuleRoleSpec.model_validate(fields)


def test_router_skip_cannot_borrow_jobs_from_the_redis_path() -> None:
    registry = load_module_role_registry()
    role = registry.get("app.api.jobs_router")
    # Old records omit both new fields. Executed still has its original meaning.
    executed = _record_from_spec(role)
    assert build_module_execution_ledger("fixture", [executed], registry).records == (
        executed,
    )
    skip = _record_from_spec(
        role,
        status=ModuleExecutionStatus.SKIPPED_OPTIONAL_EXTRA,
        reason="Redis worker dependency is missing.",
    )
    for fields in ({}, {"missing_extra": "jobs"}):
        record = ModuleExecutionRecord.model_validate({**skip.model_dump(), **fields})
        with pytest.raises(ValueError, match="dependency_path"):
            build_module_execution_ledger("fixture", [record], registry)
