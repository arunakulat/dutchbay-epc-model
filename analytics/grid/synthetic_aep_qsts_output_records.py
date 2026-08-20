"""Governed #1073 synthetic AEP/QSTS execution and output-record publication.

Only the authenticated #1077 handoff and its manifest-verified package may enter this
orchestrator.  The emitted record remains segregated process-provenance evidence and is
structurally ineligible for canonical finance, lender, board, or publication use.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import platform
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, cast

from analytics.contracts_v14 import (
    QSTS_SYNTHETIC_OUTPUT_CLASS,
    SYNTHETIC_INPUT_HANDOFF_SCHEMA,
    SYNTHETIC_PROCESS_PROVENANCE_WARNING,
    SYNTHETIC_QSTS_OUTPUT_SCHEMA,
    SyntheticInputArtifactRecord,
    SyntheticInputRecordHandoff,
    SyntheticInputSourceRecord,
    SyntheticQSTSOutputRecord,
)
from analytics.grid.curtailment_qsts import run_qsts_curtailment
from analytics.grid.synthetic_feeder_placeholder import (
    verify_synthetic_feeder_package,
)
from analytics.grid.synthetic_feeder_qsts_adapter import (
    build_verified_synthetic_qsts_overlay,
)
from analytics.run_manifest import config_sha256, git_sha

ISSUE = 1073
DOWNSTREAM_ISSUE = 1074
_QSTS_MODULE = Path(__file__).with_name("curtailment_qsts.py")
_ORCHESTRATOR_MODULE = Path(__file__)
_GOVERNED_HANDOFF_PATH = (
    "outputs/synthetic_process_provenance/issue_1077/synthetic_input_records.json"
)
_GOVERNED_PACKAGE_MANIFEST_PATH = (
    "outputs/synthetic_placeholders/issue_923/manifest.json"
)
_GOVERNED_OUTPUT_DIR = "outputs/synthetic_process_provenance/issue_1073"
_OUTPUT_FILENAMES = frozenset(
    {
        "synthetic_aep_qsts_output_records.json",
        "synthetic_aep_qsts_output_records.sha256",
    }
)
_AEP_BASIS = "sum(manifest_verified_generation_profile_mw * 1.0_hour)"
_NETWORK_INJECTION_BASIS = "gross_generation_pre_export_cap_and_operator_instruction"
_GENERATOR_NAME = "synthetic923_poc_generator"


@dataclass(frozen=True)
class SyntheticQSTSOutputConfig:
    """Strict config-first controls for the #1073 execution and publication gate."""

    handoff_path: str
    expected_handoff_sha256: str
    package_manifest_path: str
    voltage_min_pu: float
    voltage_max_pu: float
    thermal_limit_pct_norm: float
    network_injection_basis: str
    generator_name: str
    energy_balance_tolerance_mwh: float
    require_all_timesteps_converged: bool
    output_dir: str
    record_filename: str
    checksum_filename: str
    allow_existing_identical: bool

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> SyntheticQSTSOutputConfig:
        """Parse an exact resolved Hydra mapping with no permissive defaults."""

        if set(raw) != {"input", "qsts", "output"}:
            raise ValueError(
                "#1073 config requires exactly input, qsts, and output mappings."
            )
        input_raw = _exact_mapping(
            raw["input"],
            "input",
            {"handoff_path", "expected_handoff_sha256", "package_manifest_path"},
        )
        qsts_raw = _exact_mapping(
            raw["qsts"],
            "qsts",
            {
                "voltage_min_pu",
                "voltage_max_pu",
                "thermal_limit_pct_norm",
                "network_injection_basis",
                "generator_name",
                "energy_balance_tolerance_mwh",
                "require_all_timesteps_converged",
            },
        )
        output_raw = _exact_mapping(
            raw["output"],
            "output",
            {
                "output_dir",
                "record_filename",
                "checksum_filename",
                "allow_existing_identical",
            },
        )
        handoff_path = _safe_relative_path(
            input_raw["handoff_path"], "input.handoff_path"
        )
        package_path = _safe_relative_path(
            input_raw["package_manifest_path"], "input.package_manifest_path"
        )
        output_dir = _safe_relative_path(output_raw["output_dir"], "output.output_dir")
        record_filename = _safe_filename(
            output_raw["record_filename"], "output.record_filename"
        )
        checksum_filename = _safe_filename(
            output_raw["checksum_filename"], "output.checksum_filename"
        )
        if handoff_path != _GOVERNED_HANDOFF_PATH:
            raise ValueError(
                f"input.handoff_path must remain {_GOVERNED_HANDOFF_PATH!r}."
            )
        if package_path != _GOVERNED_PACKAGE_MANIFEST_PATH:
            raise ValueError(
                "input.package_manifest_path must remain the governed Issue #923 package path."
            )
        if output_dir != _GOVERNED_OUTPUT_DIR:
            raise ValueError(f"output.output_dir must remain {_GOVERNED_OUTPUT_DIR!r}.")
        if {record_filename, checksum_filename} != _OUTPUT_FILENAMES:
            raise ValueError(
                "#1073 output filenames must remain the governed JSON/SHA pair."
            )
        expected_handoff_sha256 = _require_sha256(
            input_raw["expected_handoff_sha256"], "input.expected_handoff_sha256"
        )
        low = _positive_number(qsts_raw["voltage_min_pu"], "qsts.voltage_min_pu")
        high = _positive_number(qsts_raw["voltage_max_pu"], "qsts.voltage_max_pu")
        thermal = _positive_number(
            qsts_raw["thermal_limit_pct_norm"], "qsts.thermal_limit_pct_norm"
        )
        tolerance = _positive_number(
            qsts_raw["energy_balance_tolerance_mwh"],
            "qsts.energy_balance_tolerance_mwh",
        )
        if low >= high:
            raise ValueError("qsts.voltage_min_pu must be below voltage_max_pu.")
        if qsts_raw["network_injection_basis"] != _NETWORK_INJECTION_BASIS:
            raise ValueError(
                "qsts.network_injection_basis changed from the controlled basis."
            )
        if qsts_raw["generator_name"] != _GENERATOR_NAME:
            raise ValueError(f"qsts.generator_name must remain {_GENERATOR_NAME!r}.")
        if qsts_raw["require_all_timesteps_converged"] is not True:
            raise ValueError(
                "qsts.require_all_timesteps_converged must be literal true."
            )
        allow_existing = output_raw["allow_existing_identical"]
        if type(allow_existing) is not bool:  # noqa: E721
            raise ValueError(
                "output.allow_existing_identical must be a literal boolean."
            )
        return cls(
            handoff_path=handoff_path,
            expected_handoff_sha256=expected_handoff_sha256,
            package_manifest_path=package_path,
            voltage_min_pu=low,
            voltage_max_pu=high,
            thermal_limit_pct_norm=thermal,
            network_injection_basis=_NETWORK_INJECTION_BASIS,
            generator_name=_GENERATOR_NAME,
            energy_balance_tolerance_mwh=tolerance,
            require_all_timesteps_converged=True,
            output_dir=output_dir,
            record_filename=record_filename,
            checksum_filename=checksum_filename,
            allow_existing_identical=allow_existing,
        )

    def identity_mapping(self) -> dict[str, Any]:
        """Return the exact execution controls retained by the output record."""

        return {
            "input": {
                "handoff_path": self.handoff_path,
                "expected_handoff_sha256": self.expected_handoff_sha256,
                "package_manifest_path": self.package_manifest_path,
            },
            "qsts": {
                "voltage_min_pu": self.voltage_min_pu,
                "voltage_max_pu": self.voltage_max_pu,
                "thermal_limit_pct_norm": self.thermal_limit_pct_norm,
                "network_injection_basis": self.network_injection_basis,
                "generator_name": self.generator_name,
                "energy_balance_tolerance_mwh": self.energy_balance_tolerance_mwh,
                "require_all_timesteps_converged": True,
            },
            "output": {
                "output_dir": self.output_dir,
                "record_filename": self.record_filename,
                "checksum_filename": self.checksum_filename,
                "allow_existing_identical": self.allow_existing_identical,
            },
        }


def _exact_mapping(value: object, field: str, expected: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        actual = sorted(value) if isinstance(value, Mapping) else type(value).__name__
        raise ValueError(
            f"{field} keys must be exactly {sorted(expected)}, got {actual}."
        )
    return cast(Mapping[str, Any], value)


def _safe_relative_path(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.startswith(("/", "~"))
        or "\\" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError(f"{field} must be a safe repository-relative path.")
    return value


def _safe_filename(value: object, field: str) -> str:
    path = _safe_relative_path(value, field)
    if "/" in path:
        raise ValueError(f"{field} must be a filename.")
    return path


def _require_sha256(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be an exact lowercase SHA-256.")
    return value


def _positive_number(value: object, field: str) -> float:
    if type(value) not in {int, float}:  # noqa: E721
        raise ValueError(f"{field} must be a positive finite number.")
    number = float(cast(int | float, value))
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{field} must be a positive finite number.")
    return number


def _required_result_number(value: float | int | None, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Actual QSTS result omitted finite {field}.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Actual QSTS result omitted finite {field}.")
    return number


def _required_result_int(value: int | None, field: str) -> int:
    if type(value) is not int or value < 0:  # noqa: E721
        raise ValueError(f"Actual QSTS result omitted non-negative {field}.")
    return value


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _profile_values_sha256(values: tuple[float, ...]) -> str:
    payload = json.dumps(
        list(values), separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return _sha256_bytes(payload)


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _reject_symlink_ancestors(path: Path, field: str) -> None:
    candidate = path.absolute()
    for ancestor in (candidate, *candidate.parents):
        if ancestor.exists() and ancestor.is_symlink():
            raise ValueError(f"{field} must not traverse a symlinked ancestor.")


def _no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key refused: {key!r}.")
        result[key] = value
    return result


def _handoff_from_mapping(raw: Mapping[str, Any]) -> SyntheticInputRecordHandoff:
    expected = {
        field.name
        for field in SyntheticInputRecordHandoff.__dataclass_fields__.values()
    }
    if set(raw) != expected:
        raise ValueError("#1077 handoff fields do not match the centralized contract.")
    payload = dict(raw)
    payload["source_records"] = tuple(
        SyntheticInputSourceRecord(**cast(dict[str, Any], value))
        for value in cast(list[object], raw["source_records"])
    )
    payload["artifact_records"] = tuple(
        SyntheticInputArtifactRecord(**cast(dict[str, Any], value))
        for value in cast(list[object], raw["artifact_records"])
    )
    payload["limitation_records"] = tuple(cast(list[str], raw["limitation_records"]))
    payload["assumption_locations"] = tuple(
        cast(list[str], raw["assumption_locations"])
    )
    return SyntheticInputRecordHandoff(**payload)


def _load_authenticated_handoff(
    *, handoff_path: Path, expected_sha256: str
) -> tuple[SyntheticInputRecordHandoff, bytes]:
    _reject_symlink_ancestors(handoff_path, "#1077 handoff")
    if handoff_path.is_symlink() or not handoff_path.is_file():
        raise FileNotFoundError(
            "Authenticated #1077 handoff JSON is absent or a symlink."
        )
    payload = handoff_path.read_bytes()
    actual_sha256 = _sha256_bytes(payload)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"#1077 handoff SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}."
        )
    checksum_path = handoff_path.with_suffix(".sha256")
    if checksum_path.is_symlink() or not checksum_path.is_file():
        raise FileNotFoundError(
            "#1077 detached handoff checksum is absent or a symlink."
        )
    expected_checksum = f"{actual_sha256}  {handoff_path.name}\n".encode("ascii")
    if checksum_path.read_bytes() != expected_checksum:
        raise ValueError(
            "#1077 detached handoff checksum does not match the authenticated JSON."
        )
    raw = json.loads(payload.decode("utf-8"), object_pairs_hook=_no_duplicate_object)
    if not isinstance(raw, Mapping) or payload != _canonical_json(
        cast(Mapping[str, Any], raw)
    ):
        raise ValueError(
            "#1077 handoff must be canonical sorted two-space UTF-8/LF JSON."
        )
    return _handoff_from_mapping(cast(Mapping[str, Any], raw)), payload


def _require_handoff_package_match(
    handoff: SyntheticInputRecordHandoff,
    package: Any,
) -> None:
    artifact_sha = {
        record.relative_path: record.sha256 for record in handoff.artifact_records
    }
    if (
        package.manifest_sha256 != handoff.package_manifest_sha256
        or package.profile_rows != handoff.profile_row_count
        or package.profile_start_utc != handoff.profile_start_utc
        or package.profile_end_utc != handoff.profile_end_utc
        or package.export_cap_mw != handoff.export_cap_mw
        or package.file_sha256["profile/generation_profile.csv"]
        != handoff.profile_sha256
        or _profile_values_sha256(package.generation_profile_mw)
        != handoff.profile_values_sha256
    ):
        raise ValueError(
            "#1077 handoff identities do not match the verified package runtime values."
        )
    package_root = package.manifest_path.parent
    for relative_path, expected in artifact_sha.items():
        path = package_root.joinpath(*PurePosixPath(relative_path).parts)
        if path.is_symlink() or not path.is_file() or _sha256_path(path) != expected:
            raise ValueError(f"Authenticated package payload changed: {relative_path}.")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _publish_record(
    *,
    record: SyntheticQSTSOutputRecord,
    output_dir: Path,
    config: SyntheticQSTSOutputConfig,
) -> str:
    _reject_symlink_ancestors(output_dir, "#1073 output directory")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_json(record.model_dump())
    digest = _sha256_bytes(payload)
    checksum = f"{digest}  {config.record_filename}\n".encode("ascii")
    stage = Path(
        tempfile.mkdtemp(prefix=".issue1073-stage-", dir=str(output_dir.parent))
    )
    try:
        (stage / config.record_filename).write_bytes(payload)
        (stage / config.checksum_filename).write_bytes(checksum)
        if output_dir.exists():
            entries = tuple(output_dir.iterdir())
            if (
                not config.allow_existing_identical
                or {entry.name for entry in entries} != _OUTPUT_FILENAMES
                or any(entry.is_symlink() or not entry.is_file() for entry in entries)
                or any(
                    (output_dir / name).read_bytes() != (stage / name).read_bytes()
                    for name in _OUTPUT_FILENAMES
                )
            ):
                raise FileExistsError(
                    "A differing or incomplete #1073 output already exists."
                )
            shutil.rmtree(stage)
        else:
            os.replace(stage, output_dir)
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
    return digest


def generate_synthetic_aep_qsts_output_records(
    *,
    config: SyntheticQSTSOutputConfig,
    repo_root: Path,
    handoff_path_override: Path | None = None,
    package_manifest_override: Path | None = None,
    output_dir_override: Path | None = None,
    run_started_at_utc: str | None = None,
    run_completed_at_utc: str | None = None,
) -> tuple[SyntheticQSTSOutputRecord, str]:
    """Authenticate #1077, execute all OpenDSS steps, and publish the #1073 record."""

    repo = repo_root.resolve()
    handoff_path = handoff_path_override or repo.joinpath(
        *config.handoff_path.split("/")
    )
    package_path = package_manifest_override or repo.joinpath(
        *config.package_manifest_path.split("/")
    )
    output_dir = output_dir_override or repo.joinpath(*config.output_dir.split("/"))
    started = run_started_at_utc or _utc_now()
    handoff, handoff_payload = _load_authenticated_handoff(
        handoff_path=handoff_path,
        expected_sha256=config.expected_handoff_sha256,
    )
    package = verify_synthetic_feeder_package(
        manifest_path=package_path,
        expected_manifest_sha256=handoff.package_manifest_sha256,
    )
    _require_handoff_package_match(handoff, package)
    overlay = build_verified_synthetic_qsts_overlay(
        manifest_path=package_path,
        expected_manifest_sha256=handoff.package_manifest_sha256,
    )
    if (
        tuple(overlay["generation_profile_mw"]) != package.generation_profile_mw
        or overlay["export_cap_mw"] != handoff.export_cap_mw
        or overlay["finance_wiring"]
        != {
            "enabled": False,
            "mode": "synthetic_counterfactual",
            "canonical_eligible": False,
        }
    ):
        raise ValueError(
            "Production synthetic QSTS adapter changed authenticated runtime values."
        )
    grid = {
        "qsts": {
            **overlay,
            "generator_name": config.generator_name,
            "execution_monitoring": {
                "voltage_min_pu": config.voltage_min_pu,
                "voltage_max_pu": config.voltage_max_pu,
                "thermal_limit_pct_norm": config.thermal_limit_pct_norm,
            },
        }
    }
    result = run_qsts_curtailment({"grid": grid})
    telemetry = result.qsts_solve_telemetry
    if (
        not result.ran
        or telemetry is None
        or telemetry.attempted_steps != 8760
        or telemetry.converged_steps != 8760
        or telemetry.nonconverged_steps != 0
        or telemetry.generator_activation_steps != 8760
        or telemetry.generator_setpoint_mismatch_steps != 0
        or result.hours_total != 8760
    ):
        raise ValueError(
            "#1073 refuses output without 8,760 verified converged OpenDSS solves."
        )
    if result.qsts_run_manifest is None:
        raise ValueError(
            "#1073 actual solver result lacks the required QSTS run manifest."
        )
    # Close both mutation windows before any record can be emitted.
    if _sha256_bytes(handoff_path.read_bytes()) != _sha256_bytes(handoff_payload):
        raise ValueError("#1077 handoff changed during #1073 execution.")
    package_after = verify_synthetic_feeder_package(
        manifest_path=package_path,
        expected_manifest_sha256=handoff.package_manifest_sha256,
    )
    _require_handoff_package_match(handoff, package_after)
    aep_mwh = math.fsum(
        value * handoff.profile_timestep_hours
        for value in package.generation_profile_mw
    )
    gross = _required_result_number(result.gross_energy_mwh, "gross_energy_mwh")
    tolerance = config.energy_balance_tolerance_mwh
    aep_residual = gross - aep_mwh
    if abs(aep_residual) > tolerance:
        raise ValueError(
            "OpenDSS gross-generation accounting differs from authenticated AEP."
        )
    deemed = _required_result_number(
        result.deemed_paid_energy_mwh, "deemed_paid_energy_mwh"
    )
    self_pre = _required_result_number(
        result.self_curtailed_pre_bess_mwh, "self_curtailed_pre_bess_mwh"
    )
    bess = _required_result_number(
        result.bess_absorbed_energy_mwh, "bess_absorbed_energy_mwh"
    )
    self_net = _required_result_number(
        result.self_curtailed_energy_mwh, "self_curtailed_energy_mwh"
    )
    curtailed_total = _required_result_number(
        result.curtailed_total_mwh, "curtailed_total_mwh"
    )
    delivered = gross - deemed - self_pre
    balance = gross - (delivered + deemed + self_net + bess)
    completed = run_completed_at_utc or _utc_now()
    warning_counts = tuple(
        sorted(
            (
                (
                    "thermal_limit_violation_timestep",
                    int(telemetry.thermal_violation_steps or 0),
                ),
                (
                    "voltage_limit_violation_timestep",
                    int(telemetry.voltage_violation_steps or 0),
                ),
            )
        )
    )
    error_counts = (
        (
            "generator_setpoint_mismatch_timestep",
            telemetry.generator_setpoint_mismatch_steps,
        ),
        ("nonconverged_timestep", telemetry.nonconverged_steps),
    )
    record = SyntheticQSTSOutputRecord(
        schema=SYNTHETIC_QSTS_OUTPUT_SCHEMA,
        issue=ISSUE,
        downstream_issue=DOWNSTREAM_ISSUE,
        run_started_at_utc=started,
        run_completed_at_utc=completed,
        repository_commit=git_sha(),
        qsts_code_sha256=_sha256_path(_QSTS_MODULE),
        orchestrator_code_sha256=_sha256_path(_ORCHESTRATOR_MODULE),
        resolved_run_config_sha256=config_sha256(config.identity_mapping()),
        python_version=platform.python_version(),
        opendssdirect_version=importlib.metadata.version("opendssdirect.py"),
        opendss_engine_version=str(__import__("opendssdirect").Basic.Version()),
        input_handoff_schema=SYNTHETIC_INPUT_HANDOFF_SCHEMA,
        input_handoff_sha256=config.expected_handoff_sha256,
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
        synthetic_aep_mwh=aep_mwh,
        synthetic_aep_gwh=aep_mwh / 1000.0,
        aep_calculation_basis=_AEP_BASIS,
        aep_integration_residual_mwh=aep_residual,
        gross_energy_mwh=gross,
        delivered_energy_mwh=delivered,
        deemed_paid_energy_mwh=deemed,
        self_curtailed_pre_bess_mwh=self_pre,
        bess_recovered_energy_mwh=bess,
        self_curtailed_energy_mwh=self_net,
        curtailed_total_mwh=curtailed_total,
        export_cap_breach_timesteps=_required_result_int(
            result.hours_self_curtailed, "hours_self_curtailed"
        ),
        energy_balance_residual_mwh=balance,
        energy_balance_tolerance_mwh=tolerance,
        warning_category_counts=warning_counts,
        error_category_counts=error_counts,
        operator_schedule_status=handoff.operator_schedule_status,
        solver_telemetry=telemetry,
        qsts_run_manifest=result.qsts_run_manifest,
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
    digest = _publish_record(record=record, output_dir=output_dir, config=config)
    return record, digest


def cli_summary(
    record: SyntheticQSTSOutputRecord, digest: str, config: SyntheticQSTSOutputConfig
) -> dict[str, Any]:
    """Return one concise warning-bearing process-provenance CLI receipt."""

    return {
        "status": "PASS",
        "issue": ISSUE,
        "required_warning": record.required_warning,
        "record_sha256": digest,
        "record_path": f"{config.output_dir}/{config.record_filename}",
        "synthetic_aep_mwh": record.synthetic_aep_mwh,
        "synthetic_aep_gwh": record.synthetic_aep_gwh,
        "qsts_attempted_steps": record.solver_telemetry.attempted_steps,
        "qsts_converged_steps": record.solver_telemetry.converged_steps,
        "qsts_nonconverged_steps": record.solver_telemetry.nonconverged_steps,
        "finance_wiring_enabled": False,
        "finance_executed": False,
        "canonical_finance_eligible": False,
        "bankable": False,
        "publishable": False,
    }


__all__ = [
    "SyntheticQSTSOutputConfig",
    "cli_summary",
    "generate_synthetic_aep_qsts_output_records",
]
