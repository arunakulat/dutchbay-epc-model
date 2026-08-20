"""Issue #1074 authenticated synthetic finance report and refusal controls."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

import pytest
import yaml

from analytics.contracts_v14 import (
    QSTS_RUN_MANIFEST_SCHEMA,
    QSTS_SYNTHETIC_OUTPUT_CLASS,
    SYNTHETIC_PROCESS_PROVENANCE_WARNING,
    SYNTHETIC_QSTS_OUTPUT_SCHEMA,
    QSTSRunManifest,
    QSTSSolveTelemetry,
    SyntheticInputRecordHandoff,
    SyntheticQSTSOutputRecord,
)
from analytics.grid.synthetic_input_records import (
    SyntheticInputRecordsConfig,
    generate_and_ingress_synthetic_input_records,
)
from analytics.synthetic_qsts_finance_counterfactual import (
    AuthenticatedSyntheticReportInputs,
    canonical_json,
    evaluate_synthetic_qsts_finance_counterfactual,
    load_authenticated_synthetic_report_inputs,
    require_canonical_finance_release,
    sha256_bytes,
)
from app.reports.synthetic_qsts_finance_report import (
    SyntheticFinanceReportConfig,
    generate_synthetic_qsts_finance_report,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_CONFIG = REPO_ROOT / "conf" / "synthetic_feeder_placeholder.yaml"
HANDOFF_CONFIG = REPO_ROOT / "conf" / "synthetic_input_records.yaml"
REPORT_CONFIG = REPO_ROOT / "conf" / "synthetic_qsts_finance_report.yaml"
SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
GENERATED_AT = "2026-08-20T12:00:00+00:00"


def _generator_raw() -> Mapping[str, Any]:
    raw = yaml.safe_load(GENERATOR_CONFIG.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


def _handoff_config() -> SyntheticInputRecordsConfig:
    raw = yaml.safe_load(HANDOFF_CONFIG.read_text(encoding="utf-8"))
    assert isinstance(raw, dict) and isinstance(raw["handoff"], dict)
    return SyntheticInputRecordsConfig.from_mapping(raw["handoff"])


def _report_raw() -> dict[str, Any]:
    raw = yaml.safe_load(REPORT_CONFIG.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return {
        key: value for key, value in raw.items() if key not in {"defaults", "hydra"}
    }


def _qsts_record(handoff: SyntheticInputRecordHandoff) -> SyntheticQSTSOutputRecord:
    telemetry = QSTSSolveTelemetry(
        attempted_steps=8760,
        converged_steps=8760,
        nonconverged_steps=0,
        first_nonconverged_step=None,
        last_nonconverged_step=None,
        monitoring_configured=True,
        voltage_min_limit_pu=0.9,
        voltage_max_limit_pu=1.1,
        thermal_limit_pct_norm=100.0,
        voltage_violation_steps=8760,
        thermal_violation_steps=0,
        generator_activation_steps=8760,
        generator_setpoint_mismatch_steps=0,
        observed_voltage_min_pu=0.0,
        observed_voltage_max_pu=0.0,
        observed_max_pct_norm=0.0,
    )
    payloads = tuple(
        (record.relative_path, record.sha256) for record in handoff.artifact_records
    )
    run_manifest = QSTSRunManifest(
        schema=QSTS_RUN_MANIFEST_SCHEMA,
        package_id="synthetic-report-contract-fixture",
        input_kind="synthetic_placeholder",
        output_class=QSTS_SYNTHETIC_OUTPUT_CLASS,
        payload_sha256=payloads,
        source_manifest_sha256=handoff.package_manifest_sha256,
        evidence_manifest_sha256=None,
        finance_wiring_mode="synthetic_counterfactual",
        finance_wiring_enabled=False,
        canonical_finance_eligible=False,
        required_warning=SYNTHETIC_PROCESS_PROVENANCE_WARNING,
        bankable=False,
        lender_eligible=False,
        board_approval_eligible=False,
        release_eligible=False,
    )
    return SyntheticQSTSOutputRecord(
        schema=SYNTHETIC_QSTS_OUTPUT_SCHEMA,
        issue=1073,
        downstream_issue=1074,
        run_started_at_utc="2026-08-20T12:01:00+00:00",
        run_completed_at_utc="2026-08-20T12:02:00+00:00",
        repository_commit="a" * 40,
        qsts_code_sha256="b" * 64,
        orchestrator_code_sha256="c" * 64,
        resolved_run_config_sha256="d" * 64,
        python_version="3.12.13",
        opendssdirect_version="0.9.4",
        opendss_engine_version="contract fixture",
        input_handoff_schema=handoff.schema,
        input_handoff_sha256="0" * 64,
        input_package_manifest_sha256=handoff.package_manifest_sha256,
        input_profile_sha256=handoff.profile_sha256,
        input_profile_values_sha256=handoff.profile_values_sha256,
        payload_records=handoff.artifact_records,
        profile_row_count=handoff.profile_row_count,
        profile_start_utc=handoff.profile_start_utc,
        profile_end_utc=handoff.profile_end_utc,
        profile_timezone=handoff.profile_timezone,
        profile_timestep_hours=handoff.profile_timestep_hours,
        profile_unit=handoff.profile_unit,
        synthetic_aep_mwh=1000.0,
        synthetic_aep_gwh=1.0,
        aep_calculation_basis="sum(manifest_verified_generation_profile_mw * 1.0_hour)",
        aep_integration_residual_mwh=0.0,
        gross_energy_mwh=1000.0,
        delivered_energy_mwh=900.0,
        deemed_paid_energy_mwh=0.0,
        self_curtailed_pre_bess_mwh=100.0,
        bess_recovered_energy_mwh=0.0,
        self_curtailed_energy_mwh=100.0,
        curtailed_total_mwh=100.0,
        export_cap_breach_timesteps=100,
        energy_balance_residual_mwh=0.0,
        energy_balance_tolerance_mwh=1.0e-6,
        warning_category_counts=(
            ("thermal_limit_violation_timestep", 0),
            ("voltage_limit_violation_timestep", 8760),
        ),
        error_category_counts=(
            ("generator_setpoint_mismatch_timestep", 0),
            ("nonconverged_timestep", 0),
        ),
        operator_schedule_status="absent_no_observed_operator_instructions",
        solver_telemetry=telemetry,
        qsts_run_manifest=run_manifest,
        input_kind="synthetic_placeholder",
        output_class=QSTS_SYNTHETIC_OUTPUT_CLASS,
        required_warning=SYNTHETIC_PROCESS_PROVENANCE_WARNING,
        generated_input=True,
        observed_network_data=False,
        site_representative=False,
        canonical_finance_eligible=False,
        bankable=False,
        publishable=False,
        lender_eligible=False,
        board_eligible=False,
        finance_wiring_enabled=False,
        finance_executed=False,
        qsts_executed=True,
    )


@pytest.fixture(scope="module")
def authenticated_paths(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, str, Path, str]:
    pytest.importorskip("opendssdirect")
    root = tmp_path_factory.mktemp("issue1074-authenticated-inputs").resolve()
    handoff, handoff_sha = generate_and_ingress_synthetic_input_records(
        generator_config_raw=_generator_raw(),
        handoff_config=_handoff_config(),
        repo_root=REPO_ROOT,
        package_output_override=root / "package",
        handoff_output_override=root / "handoff",
        generated_at_utc=GENERATED_AT,
    )
    qsts = replace(_qsts_record(handoff), input_handoff_sha256=handoff_sha)
    qsts_dir = root / "qsts"
    qsts_dir.mkdir()
    qsts_path = qsts_dir / "synthetic_aep_qsts_output_records.json"
    qsts_payload = canonical_json(qsts.model_dump())
    qsts_sha = sha256_bytes(qsts_payload)
    qsts_path.write_bytes(qsts_payload)
    qsts_path.with_suffix(".sha256").write_text(
        f"{qsts_sha}  {qsts_path.name}\n", encoding="ascii"
    )
    return (
        root / "handoff" / "synthetic_input_records.json",
        handoff_sha,
        qsts_path,
        qsts_sha,
    )


@pytest.fixture(scope="module")
def authenticated_inputs(
    authenticated_paths: tuple[Path, str, Path, str],
) -> AuthenticatedSyntheticReportInputs:
    handoff_path, handoff_sha, qsts_path, qsts_sha = authenticated_paths
    return load_authenticated_synthetic_report_inputs(
        handoff_path=handoff_path,
        expected_handoff_sha256=handoff_sha,
        qsts_output_path=qsts_path,
        expected_qsts_output_sha256=qsts_sha,
    )


def _config(
    authenticated_paths: tuple[Path, str, Path, str], repo_root: Path
) -> SyntheticFinanceReportConfig:
    handoff_path, handoff_sha, qsts_path, qsts_sha = authenticated_paths
    raw = _report_raw()
    raw["input"] = {
        "handoff_path": str(handoff_path.relative_to(repo_root)),
        "expected_handoff_sha256": handoff_sha,
        "qsts_output_path": str(qsts_path.relative_to(repo_root)),
        "expected_qsts_output_sha256": qsts_sha,
    }
    raw["scenario"] = {"path": f"scenarios/{SCENARIO.name}"}
    return SyntheticFinanceReportConfig.from_mapping(raw)


def _fake_evaluator(calls: list[dict[str, float]]) -> Any:
    def evaluate(**kwargs: Any) -> dict[str, Any]:
        overrides = dict(kwargs["overrides"])
        calls.append(overrides)
        haircut = float(overrides.get("project.curtailment_pct", 0.0))
        factor = 1.0 - haircut
        return {
            "kpis": {
                "project_irr": 0.1 - haircut * 0.1,
                "equity_irr": 0.12 - haircut * 0.2,
                "project_npv": 10_000_000.0 - haircut * 1_000_000.0,
                "min_dscr": 1.4 - haircut * 0.1,
            },
            "annual_rows": [
                {"net_kwh": 1_000_000.0 * factor, "revenue_usd": 100_000.0 * factor},
                {"net_kwh": 900_000.0 * factor, "revenue_usd": 90_000.0 * factor},
            ],
        }

    return evaluate


def _stub_pdf(_html: str) -> tuple[bytes, int]:
    return b"%PDF-1.7\ncontrolled-test-fixture\n", 4


def _stub_warning(_pdf: bytes, _warning: str) -> tuple[int, int]:
    return 4, 4


def test_report_config_is_strict_and_freezes_warning_finance_and_output() -> None:
    raw = _report_raw()
    raw["input"]["expected_handoff_sha256"] = "a" * 64
    raw["input"]["expected_qsts_output_sha256"] = "b" * 64
    config = SyntheticFinanceReportConfig.from_mapping(raw)
    assert config.warning == SYNTHETIC_PROCESS_PROVENANCE_WARNING
    assert config.finance_wiring_enabled is False
    assert config.canonical_eligible is False
    assert config.output_dir == "outputs/synthetic_process_provenance/issue_1074"

    with pytest.raises(ValueError, match="governed config requires warning"):
        SyntheticFinanceReportConfig.from_mapping(
            {**raw, "report": {**raw["report"], "warning": "suppressed"}}
        )
    with pytest.raises(ValueError, match="finance_wiring_enabled=False"):
        SyntheticFinanceReportConfig.from_mapping(
            {
                **raw,
                "finance": {**raw["finance"], "finance_wiring_enabled": True},
            }
        )


def test_authenticated_inputs_refuse_wrong_digest_and_cross_record_substitution(
    authenticated_paths: tuple[Path, str, Path, str], tmp_path: Path
) -> None:
    handoff_path, handoff_sha, qsts_path, qsts_sha = authenticated_paths
    with pytest.raises(ValueError, match="#1077 handoff SHA-256 mismatch"):
        load_authenticated_synthetic_report_inputs(
            handoff_path=handoff_path,
            expected_handoff_sha256="f" * 64,
            qsts_output_path=qsts_path,
            expected_qsts_output_sha256=qsts_sha,
        )

    raw = json.loads(qsts_path.read_text(encoding="utf-8"))
    raw["input_profile_sha256"] = "f" * 64
    substituted = tmp_path / "synthetic_aep_qsts_output_records.json"
    payload = canonical_json(raw)
    digest = sha256_bytes(payload)
    substituted.write_bytes(payload)
    substituted.with_suffix(".sha256").write_text(
        f"{digest}  {substituted.name}\n", encoding="ascii"
    )
    with pytest.raises(ValueError, match="does not match authenticated #1077"):
        load_authenticated_synthetic_report_inputs(
            handoff_path=handoff_path,
            expected_handoff_sha256=handoff_sha,
            qsts_output_path=substituted,
            expected_qsts_output_sha256=digest,
        )


def test_duplicate_key_is_refused_even_when_resealed(
    authenticated_paths: tuple[Path, str, Path, str], tmp_path: Path
) -> None:
    handoff_path, _, qsts_path, qsts_sha = authenticated_paths
    original = handoff_path.read_text(encoding="utf-8")
    duplicate = original.replace(
        '  "schema":', '  "schema": "duplicate",\n  "schema":', 1
    ).encode("utf-8")
    path = tmp_path / "synthetic_input_records.json"
    digest = sha256_bytes(duplicate)
    path.write_bytes(duplicate)
    path.with_suffix(".sha256").write_text(f"{digest}  {path.name}\n", encoding="ascii")
    with pytest.raises(ValueError, match="Duplicate JSON key refused"):
        load_authenticated_synthetic_report_inputs(
            handoff_path=path,
            expected_handoff_sha256=digest,
            qsts_output_path=qsts_path,
            expected_qsts_output_sha256=qsts_sha,
        )


def test_counterfactual_uses_exact_one_key_and_excludes_deemed_paid(
    authenticated_inputs: AuthenticatedSyntheticReportInputs,
) -> None:
    calls: list[dict[str, float]] = []
    evaluation = evaluate_synthetic_qsts_finance_counterfactual(
        inputs=authenticated_inputs,
        scenario_path=SCENARIO,
        evaluator=_fake_evaluator(calls),
    )
    assert calls == [{}, {"project.curtailment_pct": pytest.approx(0.1)}]
    assert evaluation.override_items == (
        ("project.curtailment_pct", pytest.approx(0.1)),
    )
    assert evaluation.deemed_paid_finance_haircut_decimal == 0.0
    assert evaluation.kpis.counterfactual.year1_net_generation_mwh < (
        evaluation.kpis.baseline.year1_net_generation_mwh
    )
    assert evaluation.kpis.counterfactual.year1_revenue_usd < (
        evaluation.kpis.baseline.year1_revenue_usd
    )


def test_real_evaluation_gateway_produces_expected_downside_movements(
    authenticated_inputs: AuthenticatedSyntheticReportInputs,
) -> None:
    scenario_before = SCENARIO.read_bytes()
    evaluation = evaluate_synthetic_qsts_finance_counterfactual(
        inputs=authenticated_inputs, scenario_path=SCENARIO
    )
    assert evaluation.kpis.movement.project_irr < 0.0
    assert evaluation.kpis.movement.equity_irr < 0.0
    assert evaluation.kpis.movement.project_npv_usd < 0.0
    assert evaluation.kpis.movement.minimum_dscr <= 0.0
    assert evaluation.kpis.movement.lifetime_net_generation_mwh < 0.0
    assert evaluation.kpis.movement.lifetime_revenue_usd < 0.0
    assert SCENARIO.read_bytes() == scenario_before


def test_report_publishes_hashed_warning_complete_artifacts_and_refuses_release(
    authenticated_paths: tuple[Path, str, Path, str], tmp_path: Path
) -> None:
    repo_root = Path(authenticated_paths[0]).parents[1]
    # The scenario remains in the real repository; mirror only its relative reference
    # through a safe symlink-free repo root assembled beneath tmp_path.
    scenario_dir = repo_root / "scenarios"
    scenario_dir.mkdir(exist_ok=True)
    scenario_copy = scenario_dir / SCENARIO.name
    scenario_copy.write_bytes(SCENARIO.read_bytes())
    config = _config(authenticated_paths, repo_root)
    calls: list[dict[str, float]] = []
    output = tmp_path / "report-output"
    record, digest = generate_synthetic_qsts_finance_report(
        config=config,
        repo_root=repo_root,
        generated_at_utc=GENERATED_AT,
        pdf_renderer=_stub_pdf,
        pdf_warning_verifier=_stub_warning,
        finance_evaluator=_fake_evaluator(calls),
        output_dir_override=output,
    )
    assert record.pdf_warning_page_count == record.pdf_page_count == 4
    assert record.html_warning_occurrences >= 4
    assert record.finance_wiring_enabled is False
    assert record.canonical_finance_eligible is False
    assert record.canonical_finance_release_refused is True
    assert record.report_html_sha256 == sha256_bytes(
        (output / config.html_filename).read_bytes()
    )
    assert record.report_pdf_sha256 == sha256_bytes(
        (output / config.pdf_filename).read_bytes()
    )
    assert sha256_bytes((output / config.record_filename).read_bytes()) == digest
    assert SYNTHETIC_PROCESS_PROVENANCE_WARNING in (
        output / config.html_filename
    ).read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="Canonical finance release refused"):
        require_canonical_finance_release(record)


def test_report_refuses_warning_incomplete_pdf_and_differing_overwrite(
    authenticated_paths: tuple[Path, str, Path, str], tmp_path: Path
) -> None:
    repo_root = Path(authenticated_paths[0]).parents[1]
    scenario_dir = repo_root / "scenarios"
    scenario_dir.mkdir(exist_ok=True)
    (scenario_dir / SCENARIO.name).write_bytes(SCENARIO.read_bytes())
    config = _config(authenticated_paths, repo_root)
    with pytest.raises(ValueError, match="persistent warning verification failed"):
        generate_synthetic_qsts_finance_report(
            config=config,
            repo_root=repo_root,
            generated_at_utc=GENERATED_AT,
            pdf_renderer=_stub_pdf,
            pdf_warning_verifier=lambda _pdf, _warning: (4, 3),
            finance_evaluator=_fake_evaluator([]),
            output_dir_override=tmp_path / "warning-failed",
        )

    output = tmp_path / "overwrite"
    generate_synthetic_qsts_finance_report(
        config=config,
        repo_root=repo_root,
        generated_at_utc=GENERATED_AT,
        pdf_renderer=_stub_pdf,
        pdf_warning_verifier=_stub_warning,
        finance_evaluator=_fake_evaluator([]),
        output_dir_override=output,
    )
    with pytest.raises(FileExistsError, match="differing or incomplete"):
        generate_synthetic_qsts_finance_report(
            config=config,
            repo_root=repo_root,
            generated_at_utc="2026-08-20T12:00:01+00:00",
            pdf_renderer=_stub_pdf,
            pdf_warning_verifier=_stub_warning,
            finance_evaluator=_fake_evaluator([]),
            output_dir_override=output,
        )


def test_report_refuses_symlinked_output(
    authenticated_paths: tuple[Path, str, Path, str], tmp_path: Path
) -> None:
    repo_root = Path(authenticated_paths[0]).parents[1]
    scenario_dir = repo_root / "scenarios"
    scenario_dir.mkdir(exist_ok=True)
    (scenario_dir / SCENARIO.name).write_bytes(SCENARIO.read_bytes())
    config = _config(authenticated_paths, repo_root)
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "linked-output"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinked ancestor"):
        generate_synthetic_qsts_finance_report(
            config=config,
            repo_root=repo_root,
            generated_at_utc=GENERATED_AT,
            pdf_renderer=_stub_pdf,
            pdf_warning_verifier=_stub_warning,
            finance_evaluator=_fake_evaluator([]),
            output_dir_override=link,
        )


@pytest.mark.slow
@pytest.mark.report_qualification
def test_synthetic_report_real_pdf_has_exact_warning_on_every_page(
    authenticated_paths: tuple[Path, str, Path, str], tmp_path: Path
) -> None:
    repo_root = Path(authenticated_paths[0]).parents[1]
    scenario_dir = repo_root / "scenarios"
    scenario_dir.mkdir(exist_ok=True)
    (scenario_dir / SCENARIO.name).write_bytes(SCENARIO.read_bytes())
    config = _config(authenticated_paths, repo_root)
    record, _ = generate_synthetic_qsts_finance_report(
        config=config,
        repo_root=repo_root,
        generated_at_utc=GENERATED_AT,
        finance_evaluator=_fake_evaluator([]),
        output_dir_override=tmp_path / "qualified-report",
    )
    assert record.pdf_page_count == 4
    assert record.pdf_warning_page_count == 4
    assert record.required_warning == SYNTHETIC_PROCESS_PROVENANCE_WARNING
    assert record.canonical_finance_release_refused is True
