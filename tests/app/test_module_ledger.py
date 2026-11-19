"""Tests for config/module_roles.yaml and app.reports.module_ledger (W1-1)."""

from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType
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
    optional_extra: str | None = None,
    notes: str | None = None,
) -> ModuleRoleSpec:
    return ModuleRoleSpec(
        module_path=module_path,
        pipeline_stage=pipeline_stage,
        role_description=role_description,
        excel_representation=excel_representation,
        optional_extra=optional_extra,
        notes=notes,
    )


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


def test_default_registry_loads_and_validates() -> None:
    assert DEFAULT_MODULE_ROLES_PATH.is_file()
    registry = load_module_role_registry()
    assert isinstance(registry, ModuleRoleRegistry)
    assert registry.schema_version == "1.0"
    assert registry.stages == tuple(PipelineStage)
    assert len(registry.modules) > 0

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
    used_extras = {
        spec.optional_extra
        for spec in registry.modules
        if spec.optional_extra is not None
    }
    assert used_extras <= KNOWN_OPTIONAL_EXTRAS


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

    # Load module_ledger.py directly without triggering app/reports/__init__.py
    # to prove the module itself pulls zero finance/analytics modules at import time.
    probe = (
        "import importlib.util, sys; "
        f"spec = importlib.util.spec_from_file_location('module_ledger_probe', {str(source_path)!r}); "
        "mod = importlib.util.module_from_spec(spec); "
        "sys.modules[spec.name] = mod; "
        "spec.loader.exec_module(mod); "
        "leaked = [m for m in sys.modules if m == 'finance' or m.startswith('finance.') "
        "or m == 'analytics' or m.startswith('analytics.')]; "
        "assert not leaked, f'Unexpected runtime imports: {leaked}'"
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_models_are_frozen_and_forbid_extra_fields() -> None:
    spec = _role_spec()
    with pytest.raises(ValidationError):
        spec.notes = "mutated"  # type: ignore[misc]

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
            modules=(spec,),
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
            records=(_exec_record(),),
            bogus=True,  # type: ignore[call-arg]
        )


def test_registry_negative_controls_cesspit() -> None:
    spec_a = _role_spec("analytics.mc.engine")
    spec_dup = _role_spec("analytics.mc.engine")

    with pytest.raises(ValidationError, match="Duplicate module_path"):
        ModuleRoleRegistry(
            schema_version="1.0",
            stages=tuple(PipelineStage),
            modules=(spec_a, spec_dup),
        )

    with pytest.raises(ValidationError, match="Missing pipeline stage"):
        ModuleRoleRegistry(
            schema_version="1.0",
            stages=tuple(PipelineStage)[:-1],
            modules=(spec_a,),
        )

    with pytest.raises(ValidationError, match="Duplicate pipeline stage"):
        ModuleRoleRegistry(
            schema_version="1.0",
            stages=(*tuple(PipelineStage), PipelineStage.GOVERNANCE),
            modules=(spec_a,),
        )

    for bad_extra in ("unknown_extra", "", "dev", "wind "):
        with pytest.raises(ValidationError, match="optional_extra"):
            _role_spec(optional_extra=bad_extra)

    with pytest.raises(ValidationError):
        _role_spec(role_description="   short   ")


@pytest.mark.parametrize(
    "status",
    [
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
    with pytest.raises(ValidationError, match="requires a non-empty reason"):
        _exec_record(status=status, reason=bad_reason)

    valid = _exec_record(status=status, reason="Explicitly skipped by guard policy.")
    assert valid.status is status


@pytest.mark.parametrize(
    "status",
    [ModuleExecutionStatus.EXECUTED, ModuleExecutionStatus.GUARD_PASSED],
)
def test_execution_record_allows_omitted_reason_when_executed_or_passed(
    status: ModuleExecutionStatus,
) -> None:
    record = _exec_record(status=status, reason=None)
    assert record.status is status
    assert record.reason is None


def test_load_module_role_registry_fails_loud_on_malformed_yaml(tmp_path: Path) -> None:
    missing_path = tmp_path / "does_not_exist.yaml"
    with pytest.raises(FileNotFoundError):
        load_module_role_registry(missing_path)

    non_mapping = tmp_path / "list.yaml"
    non_mapping.write_text("- item1\n- item2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Expected YAML mapping"):
        load_module_role_registry(non_mapping)

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
    rec1 = _exec_record(
        module_path="analytics.mc.engine",
        status=ModuleExecutionStatus.EXECUTED,
        key_outputs=("mc_p50_irr", "mc_p95_dscr"),
        provenance_refs=("run_manifest:sha256",),
    )
    rec2 = _exec_record(
        module_path="analytics.grid.pandapower_screening",
        pipeline_stage=PipelineStage.GRID_QSTS,
        role_description="Runs pandapower grid screen.",
        status=ModuleExecutionStatus.SKIPPED_OPTIONAL_EXTRA,
        reason="Optional extra [grid] is not installed.",
        caveat="Closed-form fallback used.",
    )
    rec3 = _exec_record(
        module_path="analytics.aep_provenance",
        pipeline_stage=PipelineStage.GOVERNANCE,
        role_description="AEP provenance guard.",
        status=ModuleExecutionStatus.GUARD_PASSED,
        excel_representation=ExcelRepresentationKind.GOVERNANCE_METADATA,
    )

    ledger = build_module_execution_ledger(
        "sync_lender",
        [rec1, rec2, rec3],
        registry=registry,
    )
    assert ledger.profile == "sync_lender"
    assert len(ledger.records) == 3
    assert ledger.summary_counts["executed"] == 1
    assert ledger.summary_counts["skipped_optional_extra"] == 1
    assert ledger.summary_counts["guard_passed"] == 1
    assert ledger.summary_counts["failed"] == 0
    assert sum(ledger.summary_counts.values()) == 3
    assert set(ledger.summary_counts) == {s.value for s in ModuleExecutionStatus}

    with pytest.raises(TypeError):
        ledger.summary_counts["executed"] = 99  # type: ignore[index]

    round_tripped = ModuleExecutionLedger.model_validate_json(ledger.model_dump_json())
    assert round_tripped == ledger

    dumped: dict[str, Any] = ledger.model_dump()
    assert dumped["summary_counts"]["executed"] == 1

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
