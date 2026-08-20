"""Issue #1073 authenticated 8,760-step synthetic AEP/QSTS output records."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, cast

import pytest
import yaml

import analytics.grid.curtailment_qsts as curtailment_module
from analytics.contracts_v14 import (
    SYNTHETIC_PROCESS_PROVENANCE_WARNING,
    SyntheticQSTSOutputRecord,
)
from analytics.grid.curtailment_qsts import QSTSConvergenceError
from analytics.grid.synthetic_aep_qsts_output_records import (
    SyntheticQSTSOutputConfig,
    cli_summary,
    generate_synthetic_aep_qsts_output_records,
)
from analytics.grid.synthetic_input_records import (
    SyntheticInputRecordsConfig,
    generate_and_ingress_synthetic_input_records,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATED_AT = "2026-08-20T12:00:00+00:00"
RUN_STARTED = "2026-08-20T12:01:00+00:00"
RUN_COMPLETED = "2026-08-20T12:02:00+00:00"


def _yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


def _output_config(digest: str) -> SyntheticQSTSOutputConfig:
    raw = _yaml(REPO_ROOT / "conf" / "synthetic_aep_qsts.yaml")
    raw.pop("defaults")
    raw.pop("hydra")
    raw["input"]["expected_handoff_sha256"] = digest
    return SyntheticQSTSOutputConfig.from_mapping(raw)


@pytest.fixture(scope="module")
def executed_output(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[SyntheticQSTSOutputRecord, str, Path, Path, SyntheticQSTSOutputConfig]:
    pytest.importorskip("opendssdirect")
    root = tmp_path_factory.mktemp("issue1073-output-records").resolve()
    generator_raw = _yaml(REPO_ROOT / "conf" / "synthetic_feeder_placeholder.yaml")
    handoff_raw = _yaml(REPO_ROOT / "conf" / "synthetic_input_records.yaml")["handoff"]
    handoff, handoff_digest = generate_and_ingress_synthetic_input_records(
        generator_config_raw=generator_raw,
        handoff_config=SyntheticInputRecordsConfig.from_mapping(handoff_raw),
        repo_root=REPO_ROOT,
        package_output_override=root / "package",
        handoff_output_override=root / "handoff",
        generated_at_utc=GENERATED_AT,
    )
    config = _output_config(handoff_digest)
    record, digest = generate_synthetic_aep_qsts_output_records(
        config=config,
        repo_root=REPO_ROOT,
        handoff_path_override=root / "handoff" / "synthetic_input_records.json",
        package_manifest_override=root / "package" / "manifest.json",
        output_dir_override=root / "output",
        run_started_at_utc=RUN_STARTED,
        run_completed_at_utc=RUN_COMPLETED,
    )
    assert record.input_package_manifest_sha256 == handoff.package_manifest_sha256
    return record, digest, root, root / "output", config


def test_config_is_strict_config_first_and_requires_external_digest() -> None:
    raw = _yaml(REPO_ROOT / "conf" / "synthetic_aep_qsts.yaml")
    raw.pop("defaults")
    raw.pop("hydra")
    with pytest.raises(ValueError, match="exact lowercase SHA-256"):
        SyntheticQSTSOutputConfig.from_mapping(raw)
    raw["input"]["expected_handoff_sha256"] = "a" * 64
    config = SyntheticQSTSOutputConfig.from_mapping(raw)
    assert config.require_all_timesteps_converged is True
    assert config.generator_name == "synthetic923_poc_generator"
    with pytest.raises(ValueError, match="controlled basis"):
        SyntheticQSTSOutputConfig.from_mapping(
            {
                **raw,
                "qsts": {**raw["qsts"], "network_injection_basis": "substituted"},
            }
        )


@pytest.mark.grid
def test_full_authenticated_8760_step_output_and_finance_refusal(
    executed_output: tuple[
        SyntheticQSTSOutputRecord, str, Path, Path, SyntheticQSTSOutputConfig
    ],
) -> None:
    record, digest, _, output_dir, config = executed_output
    telemetry = record.solver_telemetry
    assert telemetry.attempted_steps == 8760
    assert telemetry.converged_steps == 8760
    assert telemetry.nonconverged_steps == 0
    assert telemetry.first_nonconverged_step is None
    assert telemetry.last_nonconverged_step is None
    assert telemetry.generator_activation_steps == 8760
    assert telemetry.generator_setpoint_mismatch_steps == 0
    assert telemetry.voltage_violation_steps == 8760
    assert telemetry.thermal_violation_steps == 0
    assert record.synthetic_aep_mwh == pytest.approx(554_674.358039)
    assert record.synthetic_aep_gwh == pytest.approx(record.synthetic_aep_mwh / 1000.0)
    assert record.gross_energy_mwh == pytest.approx(record.synthetic_aep_mwh)
    assert record.energy_balance_residual_mwh == pytest.approx(0.0)
    assert record.deemed_paid_energy_mwh == pytest.approx(0.0)
    assert record.operator_schedule_status == "absent_no_observed_operator_instructions"
    assert record.required_warning == SYNTHETIC_PROCESS_PROVENANCE_WARNING
    assert record.finance_wiring_enabled is False
    assert record.finance_executed is False
    assert record.canonical_finance_eligible is False
    assert record.bankable is False
    assert record.publishable is False
    payload = (output_dir / config.record_filename).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == digest
    assert (output_dir / config.checksum_filename).read_text(encoding="ascii") == (
        f"{digest}  {config.record_filename}\n"
    )
    summary = cli_summary(record, digest, config)
    assert summary["required_warning"] == SYNTHETIC_PROCESS_PROVENANCE_WARNING
    assert summary["qsts_converged_steps"] == 8760
    assert summary["finance_executed"] is False


@pytest.mark.grid
def test_wrong_external_handoff_digest_is_refused_before_qsts(
    executed_output: tuple[
        SyntheticQSTSOutputRecord, str, Path, Path, SyntheticQSTSOutputConfig
    ],
    tmp_path: Path,
) -> None:
    _, _, root, _, config = executed_output
    wrong = replace(config, expected_handoff_sha256="0" * 64)
    with pytest.raises(ValueError, match="handoff SHA-256 mismatch"):
        generate_synthetic_aep_qsts_output_records(
            config=wrong,
            repo_root=REPO_ROOT,
            handoff_path_override=root / "handoff" / "synthetic_input_records.json",
            package_manifest_override=root / "package" / "manifest.json",
            output_dir_override=tmp_path / "output",
        )


@pytest.mark.grid
def test_identical_reexecution_allowed_but_differing_output_refused(
    executed_output: tuple[
        SyntheticQSTSOutputRecord, str, Path, Path, SyntheticQSTSOutputConfig
    ],
) -> None:
    original, digest, root, output_dir, config = executed_output
    repeated, repeated_digest = generate_synthetic_aep_qsts_output_records(
        config=config,
        repo_root=REPO_ROOT,
        handoff_path_override=root / "handoff" / "synthetic_input_records.json",
        package_manifest_override=root / "package" / "manifest.json",
        output_dir_override=output_dir,
        run_started_at_utc=RUN_STARTED,
        run_completed_at_utc=RUN_COMPLETED,
    )
    assert repeated == original
    assert repeated_digest == digest
    with pytest.raises(FileExistsError, match="differing or incomplete"):
        generate_synthetic_aep_qsts_output_records(
            config=config,
            repo_root=REPO_ROOT,
            handoff_path_override=root / "handoff" / "synthetic_input_records.json",
            package_manifest_override=root / "package" / "manifest.json",
            output_dir_override=output_dir,
            run_started_at_utc=RUN_STARTED,
            run_completed_at_utc="2026-08-20T12:02:01+00:00",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("bankable", True, "bankable must be False"),
        ("publishable", True, "publishable must be False"),
        ("finance_wiring_enabled", True, "finance_wiring_enabled must be False"),
        ("finance_executed", True, "finance_executed must be False"),
        ("qsts_executed", False, "qsts_executed must be True"),
        ("profile_row_count", 8759, "complete governed"),
    ],
)
def test_output_contract_refuses_upgrade_or_shortened_horizon(
    executed_output: tuple[
        SyntheticQSTSOutputRecord, str, Path, Path, SyntheticQSTSOutputConfig
    ],
    field: str,
    value: object,
    message: str,
) -> None:
    record = executed_output[0]
    with pytest.raises(ValueError, match=message):
        cast(Any, replace)(record, **{field: value})


def test_solver_records_first_and_last_nonconverged_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubDss:
        def __init__(self) -> None:
            self._kw = 0.0
            self._name = ""
            self._solve_index = -1
            outer = self

            class Basic:
                @staticmethod
                def ClearAll() -> None:
                    return None

            class Error:
                @staticmethod
                def Number() -> int:
                    return 0

                @staticmethod
                def Description() -> str:
                    return ""

            class Solution:
                @staticmethod
                def Mode(_: int) -> None:
                    return None

                @staticmethod
                def StepSize(_: float) -> None:
                    return None

                @staticmethod
                def Number(_: int) -> None:
                    return None

                @staticmethod
                def Solve() -> None:
                    outer._solve_index += 1

                @staticmethod
                def Converged() -> bool:
                    return outer._solve_index != 1

            class Generators:
                @staticmethod
                def Name(value: str | None = None) -> str:
                    if value is not None:
                        outer._name = value
                    return outer._name

                @staticmethod
                def kW(value: float | None = None) -> float:
                    if value is not None:
                        outer._kw = value
                    return outer._kw

            self.Basic = Basic
            self.Error = Error
            self.Solution = Solution
            self.Generators = Generators

        @staticmethod
        def Command(_: str) -> None:
            return None

    monkeypatch.setattr(curtailment_module, "_require_opendss", StubDss)
    grid: Mapping[str, Any] = {
        "qsts": {
            "generation_profile_mw": [1.0, 2.0, 3.0],
            "generator_name": "controlled_generator",
        }
    }
    with pytest.raises(QSTSConvergenceError) as captured:
        curtailment_module._solve_qsts(
            grid,
            feeder_path="fixture.dss",
            timestep_hours=1.0,
        )
    telemetry = captured.value.telemetry
    assert telemetry.attempted_steps == 3
    assert telemetry.converged_steps == 2
    assert telemetry.nonconverged_steps == 1
    assert telemetry.first_nonconverged_step == 1
    assert telemetry.last_nonconverged_step == 1


def test_orchestrator_has_no_finance_import_or_evaluator_call() -> None:
    source = (
        REPO_ROOT / "analytics" / "grid" / "synthetic_aep_qsts_output_records.py"
    ).read_text(encoding="utf-8")
    assert "from finance" not in source
    assert "import finance" not in source
    assert "evaluate_with_overrides" not in source
