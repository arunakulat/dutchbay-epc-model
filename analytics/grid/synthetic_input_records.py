"""Governed #1077 synthetic input-record generation and runtime ingress.

This module composes the existing deterministic synthetic feeder generator with the
production verified-package adapter.  It emits an authenticated input-only handoff for
#1073 and deliberately does not execute QSTS, integrate AEP, or call finance.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
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
    SyntheticInputArtifactRecord,
    SyntheticInputRecordHandoff,
    SyntheticInputSourceRecord,
)
from analytics.grid.synthetic_feeder_placeholder import (
    GENERATOR_VERSION,
    MANIFEST_SCHEMA,
    RNG_ALGORITHM,
    SyntheticFeederPlaceholderConfig,
    generate_synthetic_feeder_placeholder,
    verify_synthetic_feeder_package,
)
from analytics.grid.synthetic_feeder_qsts_adapter import (
    build_verified_synthetic_qsts_overlay,
)
from analytics.run_manifest import config_sha256, engine_version, git_sha

ISSUE = 1077
HANDOFF_TARGET_ISSUE = 1073
_GENERATOR_MODULE = Path(__file__).with_name("synthetic_feeder_placeholder.py")
_ADAPTER_MODULE = Path(__file__).with_name("synthetic_feeder_qsts_adapter.py")
_PROFILE_RELATIVE_PATH = "profile/generation_profile.csv"
_MASTER_RELATIVE_PATH = "feeder/Master.dss"
_MANIFEST_RELATIVE_PATH = "manifest.json"
_CHECKSUM_RELATIVE_PATH = "MANIFEST.sha256"
_HANDOFF_FILENAMES = frozenset(
    {"synthetic_input_records.json", "synthetic_input_records.sha256"}
)
_GOVERNED_HANDOFF_OUTPUT_DIR = "outputs/synthetic_process_provenance/issue_1077"
_GOVERNED_GENERATOR_CONFIG_SOURCE = "conf/synthetic_feeder_placeholder.yaml"


@dataclass(frozen=True)
class SyntheticInputRecordsConfig:
    """Strict publication settings for the #1077 input handoff."""

    output_dir: str
    record_filename: str
    checksum_filename: str
    allow_existing_identical: bool
    generator_config_source: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> SyntheticInputRecordsConfig:
        """Parse a resolved Hydra handoff mapping without permissive fallbacks."""

        expected = {
            "output_dir",
            "record_filename",
            "checksum_filename",
            "allow_existing_identical",
            "generator_config_source",
        }
        if set(raw) != expected:
            raise ValueError(
                "handoff configuration keys must be exactly "
                f"{sorted(expected)}, got {sorted(raw)}."
            )
        output_dir = _safe_relative_path(raw["output_dir"], "handoff.output_dir")
        generator_config_source = _safe_relative_path(
            raw["generator_config_source"], "handoff.generator_config_source"
        )
        record_filename = _safe_filename(
            raw["record_filename"], "handoff.record_filename"
        )
        checksum_filename = _safe_filename(
            raw["checksum_filename"], "handoff.checksum_filename"
        )
        if {record_filename, checksum_filename} != _HANDOFF_FILENAMES:
            raise ValueError(
                "#1077 handoff filenames must remain synthetic_input_records.json and "
                "synthetic_input_records.sha256."
            )
        if output_dir != _GOVERNED_HANDOFF_OUTPUT_DIR:
            raise ValueError(
                "#1077 handoff output_dir must remain the segregated governed path "
                f"{_GOVERNED_HANDOFF_OUTPUT_DIR!r}."
            )
        if generator_config_source != _GOVERNED_GENERATOR_CONFIG_SOURCE:
            raise ValueError(
                "#1077 generator_config_source must reuse the governed synthetic "
                f"package configuration {_GOVERNED_GENERATOR_CONFIG_SOURCE!r}."
            )
        allow_existing_identical = raw["allow_existing_identical"]
        if type(allow_existing_identical) is not bool:  # noqa: E721
            raise ValueError(
                "handoff.allow_existing_identical must be a literal boolean."
            )
        return cls(
            output_dir=output_dir,
            record_filename=record_filename,
            checksum_filename=checksum_filename,
            allow_existing_identical=allow_existing_identical,
            generator_config_source=generator_config_source,
        )


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
        raise ValueError(f"{field} must be a filename, not a path.")
    return path


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _profile_values_sha256(values: tuple[float, ...]) -> str:
    if len(values) != 8760 or any(not math.isfinite(value) for value in values):
        raise ValueError("Runtime generation profile must contain 8,760 finite values.")
    payload = json.dumps(
        list(values), separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return _sha256_bytes(payload)


def _generated_at(value: str | None) -> str:
    generated = value or datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        parsed = datetime.fromisoformat(generated.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("generated_at_utc must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("generated_at_utc must carry an explicit UTC offset.")
    return generated


def _resolved_generator_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Return only the controlled generator fields used by its strict parser."""

    return {
        str(key): value
        for key, value in raw.items()
        if key not in {"defaults", "hydra"}
    }


def _manifest_records(manifest: Mapping[str, Any], package_root: Path) -> tuple[
    tuple[SyntheticInputSourceRecord, ...],
    tuple[SyntheticInputArtifactRecord, ...],
]:
    snapshots = cast(Mapping[str, Mapping[str, Any]], manifest["source_snapshots"])
    sources = tuple(
        SyntheticInputSourceRecord(
            logical_id=logical_id,
            sha256=str(record["sha256"]),
            source_path=cast(str | None, record["path"]),
            note=cast(str | None, record.get("note")),
        )
        for logical_id, record in sorted(snapshots.items())
    )
    payload_metadata = {
        str(record["path"]): record
        for record in cast(list[Mapping[str, Any]], manifest["artifacts"])
    }
    artifact_paths = tuple(
        sorted((*payload_metadata, _MANIFEST_RELATIVE_PATH, _CHECKSUM_RELATIVE_PATH))
    )
    artifacts: list[SyntheticInputArtifactRecord] = []
    for relative_path in artifact_paths:
        path = package_root.joinpath(*PurePosixPath(relative_path).parts)
        record = payload_metadata.get(relative_path)
        if record is None:
            media_type = (
                "application/json; charset=utf-8"
                if relative_path == _MANIFEST_RELATIVE_PATH
                else "text/plain; charset=ascii"
            )
            byte_length = path.stat().st_size
            digest = _sha256_path(path)
        else:
            media_type = str(record["media_type"])
            byte_length = int(record["byte_length"])
            digest = str(record["sha256"])
        artifacts.append(
            SyntheticInputArtifactRecord(
                relative_path=relative_path,
                sha256=digest,
                byte_length=byte_length,
                media_type=media_type,
            )
        )
    return sources, tuple(artifacts)


def _handoff_payload(record: SyntheticInputRecordHandoff) -> dict[str, Any]:
    return record.model_dump()


def _reject_symlink_ancestors(path: Path, field: str) -> None:
    """Refuse an output path that exists through any symlinked ancestor."""

    candidate = path.absolute()
    for ancestor in (candidate, *candidate.parents):
        if ancestor.exists() and ancestor.is_symlink():
            raise ValueError(f"{field} must not traverse a symlinked ancestor.")


def _publish_handoff(
    *,
    record: SyntheticInputRecordHandoff,
    output_dir: Path,
    config: SyntheticInputRecordsConfig,
) -> str:
    _reject_symlink_ancestors(output_dir, "Synthetic input handoff output directory")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_json(_handoff_payload(record))
    digest = _sha256_bytes(payload)
    checksum_payload = f"{digest}  {config.record_filename}\n".encode("ascii")
    stage = Path(
        tempfile.mkdtemp(prefix=".issue1077-stage-", dir=str(output_dir.parent))
    )
    try:
        (stage / config.record_filename).write_bytes(payload)
        (stage / config.checksum_filename).write_bytes(checksum_payload)
        if output_dir.exists():
            actual_entries = tuple(output_dir.iterdir())
            actual_names = {path.name for path in actual_entries}
            if not config.allow_existing_identical:
                raise FileExistsError(
                    f"Synthetic input handoff already exists: {output_dir}"
                )
            if (
                actual_names != _HANDOFF_FILENAMES
                or any(
                    path.is_symlink() or not path.is_file() for path in actual_entries
                )
                or any(
                    (output_dir / name).read_bytes() != (stage / name).read_bytes()
                    for name in _HANDOFF_FILENAMES
                )
            ):
                raise FileExistsError(
                    "A differing or incomplete #1077 handoff already exists; refuse "
                    "implicit replacement."
                )
            shutil.rmtree(stage)
        else:
            os.replace(stage, output_dir)
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
    return digest


def generate_and_ingress_synthetic_input_records(
    *,
    generator_config_raw: Mapping[str, Any],
    handoff_config: SyntheticInputRecordsConfig,
    repo_root: Path,
    package_output_override: Path | None = None,
    handoff_output_override: Path | None = None,
    generated_at_utc: str | None = None,
) -> tuple[SyntheticInputRecordHandoff, str]:
    """Generate, authenticate, ingress, and publish the #1077 input-only handoff.

    Returns:
        The validated handoff contract and its external detached SHA-256.
    """

    repo = repo_root.resolve()
    resolved_generator = _resolved_generator_mapping(generator_config_raw)
    generator_config = SyntheticFeederPlaceholderConfig.from_mapping(resolved_generator)
    calculator_logger = logging.getLogger("wind_resource.energy_calculator")
    prior_calculator_level = calculator_logger.level
    calculator_logger.setLevel(logging.WARNING)
    try:
        package = generate_synthetic_feeder_placeholder(
            generator_config,
            repo_root=repo,
            output_dir_override=package_output_override,
        )
    finally:
        calculator_logger.setLevel(prior_calculator_level)
    overlay = build_verified_synthetic_qsts_overlay(
        manifest_path=package.manifest_path,
        expected_manifest_sha256=package.manifest_sha256,
    )
    if (
        tuple(overlay["generation_profile_mw"]) != package.generation_profile_mw
        or overlay["export_cap_mw"] != package.export_cap_mw
        or Path(overlay["feeder_model_path"]).resolve() != package.master_path.resolve()
        or overlay["source_manifest_sha256"] != package.manifest_sha256
    ):
        raise ValueError(
            "Production adapter runtime inputs do not match the verified package."
        )

    # Re-verify after adapter ingress so a payload changed after the first verification
    # cannot receive a handoff record.
    accepted = verify_synthetic_feeder_package(
        manifest_path=package.manifest_path,
        expected_manifest_sha256=package.manifest_sha256,
        master_path=overlay["feeder_model_path"],
    )
    if (
        accepted.generation_profile_mw != tuple(overlay["generation_profile_mw"])
        or accepted.export_cap_mw != overlay["export_cap_mw"]
    ):
        raise ValueError("Runtime inputs changed after package verification.")

    manifest = cast(
        Mapping[str, Any],
        json.loads(accepted.manifest_path.read_text(encoding="utf-8")),
    )
    sources, artifacts = _manifest_records(manifest, accepted.output_root)
    generator_source_sha = _sha256_path(_GENERATOR_MODULE)
    generated_at = _generated_at(generated_at_utc)
    record = SyntheticInputRecordHandoff(
        schema=SYNTHETIC_INPUT_HANDOFF_SCHEMA,
        issue=ISSUE,
        handoff_target_issue=HANDOFF_TARGET_ISSUE,
        generated_at_utc=generated_at,
        repository_commit=git_sha(),
        engine_version=engine_version(),
        package_schema=MANIFEST_SCHEMA,
        package_manifest_path=_MANIFEST_RELATIVE_PATH,
        package_manifest_sha256=accepted.manifest_sha256,
        resolved_generator_config_sha256=config_sha256(resolved_generator),
        generator_code_sha256=generator_source_sha,
        verifier_code_sha256=generator_source_sha,
        adapter_code_sha256=_sha256_path(_ADAPTER_MODULE),
        generator_version=GENERATOR_VERSION,
        random_seed=generator_config.random_seed,
        algorithm=RNG_ALGORITHM,
        profile_path=_PROFILE_RELATIVE_PATH,
        profile_sha256=accepted.file_sha256[_PROFILE_RELATIVE_PATH],
        profile_values_sha256=_profile_values_sha256(accepted.generation_profile_mw),
        profile_row_count=accepted.profile_rows,
        profile_start_utc=accepted.profile_start_utc,
        profile_end_utc=accepted.profile_end_utc,
        profile_timezone="UTC",
        profile_timestep_hours=1.0,
        profile_unit="MW",
        export_cap_mw=accepted.export_cap_mw,
        feeder_master_path=_MASTER_RELATIVE_PATH,
        source_records=sources,
        artifact_records=artifacts,
        limitation_records=tuple(cast(list[str], manifest["limitations"])),
        assumption_locations=(
            handoff_config.generator_config_source,
            "manifest.json#electrical_parameters",
            "manifest.json#profile",
            "manifest.json#limitations",
        ),
        opendss_compile_status=accepted.opendss_compile_status,
        convergence_status=accepted.convergence_status,
        operator_schedule_present=False,
        operator_schedule_status="absent_no_observed_operator_instructions",
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
        qsts_executed=False,
        finance_executed=False,
    )
    output_input = (
        handoff_output_override
        if handoff_output_override is not None
        else repo.joinpath(*PurePosixPath(handoff_config.output_dir).parts)
    )
    _reject_symlink_ancestors(output_input, "Synthetic input handoff output directory")
    output_dir = output_input.resolve()
    if handoff_output_override is None and not output_dir.is_relative_to(repo):
        raise ValueError("Configured handoff output directory escapes the repository.")
    digest = _publish_handoff(
        record=record, output_dir=output_dir, config=handoff_config
    )
    return record, digest


def cli_summary(
    record: SyntheticInputRecordHandoff,
    handoff_sha256: str,
    config: SyntheticInputRecordsConfig,
) -> dict[str, Any]:
    """Build the concise warning-bearing handoff summary printed by the CLI."""

    return {
        "status": "PASS",
        "issue": ISSUE,
        "required_warning": SYNTHETIC_PROCESS_PROVENANCE_WARNING,
        "input_kind": record.input_kind,
        "package_manifest_sha256": record.package_manifest_sha256,
        "handoff_sha256": handoff_sha256,
        "handoff_path": f"{config.output_dir}/{config.record_filename}",
        "profile_row_count": record.profile_row_count,
        "profile_start_utc": record.profile_start_utc,
        "profile_end_utc": record.profile_end_utc,
        "opendss_compile_status": record.opendss_compile_status,
        "operator_schedule_status": record.operator_schedule_status,
        "qsts_executed": False,
        "finance_executed": False,
        "canonical_finance_eligible": False,
        "bankable": False,
        "publishable": False,
    }


__all__ = [
    "SyntheticInputRecordsConfig",
    "cli_summary",
    "generate_and_ingress_synthetic_input_records",
]
