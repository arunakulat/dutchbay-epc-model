"""Authenticated #1074 synthetic-QSTS finance counterfactual.

This module is the only bridge between the governed #1077/#1073 evidence records and
the segregated #1074 finance calculation.  It never enables the canonical QSTS finance
switch.  The canonical scenario is evaluated once unchanged and once with exactly one
temporary override: ``project.curtailment_pct`` composed from the baseline value and the
net synthetic self-curtailment fraction.  Deemed-paid energy is deliberately ignored by
that override.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, cast

from analytics.contracts_v14 import (
    QSTSRunManifest,
    QSTSSolveTelemetry,
    SyntheticFinanceKpiMovement,
    SyntheticFinanceKpis,
    SyntheticInputArtifactRecord,
    SyntheticInputRecordHandoff,
    SyntheticInputSourceRecord,
    SyntheticQSTSOutputRecord,
)
from analytics.evaluation_v14 import (
    compose_noncanonical_project_curtailment,
    evaluate_with_overrides,
)
from analytics.scenario_loader import load_scenario_config

FinanceEvaluator = Callable[..., dict[str, Any]]
_DEFAULT_EVALUATOR = cast(FinanceEvaluator, evaluate_with_overrides)


@dataclass(frozen=True)
class AuthenticatedSyntheticReportInputs:
    """Strict authenticated #1077 and #1073 records plus immutable bytes."""

    handoff: SyntheticInputRecordHandoff
    handoff_sha256: str
    handoff_payload: bytes
    qsts: SyntheticQSTSOutputRecord
    qsts_sha256: str
    qsts_payload: bytes


@dataclass(frozen=True)
class SyntheticCounterfactualEvaluation:
    """The one-key segregated finance treatment and evaluated KPI movement."""

    baseline_project_curtailment_decimal: float
    synthetic_self_curtailment_decimal: float
    counterfactual_project_curtailment_decimal: float
    deemed_paid_finance_haircut_decimal: float
    override_items: tuple[tuple[str, float], ...]
    kpis: SyntheticFinanceKpiMovement


def sha256_bytes(payload: bytes) -> str:
    """Return a lowercase SHA-256 for exact evidence bytes."""

    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    """Hash an existing regular file."""

    return sha256_bytes(path.read_bytes())


def canonical_json(value: Mapping[str, Any]) -> bytes:
    """Serialize the repository's canonical sorted two-space JSON form."""

    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _reject_symlink_ancestors(path: Path, field: str) -> None:
    candidate = path.absolute()
    for ancestor in (candidate, *candidate.parents):
        if ancestor.exists() and ancestor.is_symlink():
            raise ValueError(f"{field} must not traverse a symlinked ancestor.")


def _require_sha256(value: str, field: str) -> str:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{field} must be an exact lowercase SHA-256.")
    return value


def _no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key refused: {key!r}.")
        result[key] = value
    return result


def _load_authenticated_mapping(
    path: Path, expected_sha256: str, *, label: str
) -> tuple[Mapping[str, Any], bytes]:
    """Authenticate canonical JSON and its detached sibling checksum."""

    _require_sha256(expected_sha256, f"expected {label} SHA-256")
    _reject_symlink_ancestors(path, label)
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError(f"Authenticated {label} JSON is absent or a symlink.")
    payload = path.read_bytes()
    actual = sha256_bytes(payload)
    if actual != expected_sha256:
        raise ValueError(
            f"{label} SHA-256 mismatch: expected {expected_sha256}, got {actual}."
        )
    checksum_path = path.with_suffix(".sha256")
    if checksum_path.is_symlink() or not checksum_path.is_file():
        raise FileNotFoundError(f"{label} detached checksum is absent or a symlink.")
    expected_checksum = f"{actual}  {path.name}\n".encode("ascii")
    if checksum_path.read_bytes() != expected_checksum:
        raise ValueError(f"{label} detached checksum does not authenticate its JSON.")
    raw = json.loads(payload.decode("utf-8"), object_pairs_hook=_no_duplicate_object)
    if not isinstance(raw, Mapping) or payload != canonical_json(
        cast(Mapping[str, Any], raw)
    ):
        raise ValueError(f"{label} must be canonical sorted two-space UTF-8/LF JSON.")
    return cast(Mapping[str, Any], raw), payload


def _handoff_from_mapping(raw: Mapping[str, Any]) -> SyntheticInputRecordHandoff:
    expected = {item.name for item in fields(SyntheticInputRecordHandoff)}
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


def _qsts_from_mapping(raw: Mapping[str, Any]) -> SyntheticQSTSOutputRecord:
    expected = {item.name for item in fields(SyntheticQSTSOutputRecord)}
    if set(raw) != expected:
        raise ValueError("#1073 output fields do not match the centralized contract.")
    payload = dict(raw)
    payload["payload_records"] = tuple(
        SyntheticInputArtifactRecord(**cast(dict[str, Any], value))
        for value in cast(list[object], raw["payload_records"])
    )
    payload["warning_category_counts"] = tuple(
        (str(value[0]), cast(int, value[1]))
        for value in cast(list[list[object]], raw["warning_category_counts"])
    )
    payload["error_category_counts"] = tuple(
        (str(value[0]), cast(int, value[1]))
        for value in cast(list[list[object]], raw["error_category_counts"])
    )
    payload["solver_telemetry"] = QSTSSolveTelemetry(
        **cast(dict[str, Any], raw["solver_telemetry"])
    )
    manifest = dict(cast(Mapping[str, Any], raw["qsts_run_manifest"]))
    manifest["payload_sha256"] = tuple(
        (str(value[0]), str(value[1]))
        for value in cast(list[list[object]], manifest["payload_sha256"])
    )
    payload["qsts_run_manifest"] = QSTSRunManifest(**manifest)
    return SyntheticQSTSOutputRecord(**payload)


def load_authenticated_synthetic_report_inputs(
    *,
    handoff_path: Path,
    expected_handoff_sha256: str,
    qsts_output_path: Path,
    expected_qsts_output_sha256: str,
) -> AuthenticatedSyntheticReportInputs:
    """Load both upstream records and require their complete identity chain."""

    handoff_raw, handoff_payload = _load_authenticated_mapping(
        handoff_path, expected_handoff_sha256, label="#1077 handoff"
    )
    qsts_raw, qsts_payload = _load_authenticated_mapping(
        qsts_output_path, expected_qsts_output_sha256, label="#1073 QSTS output"
    )
    handoff = _handoff_from_mapping(handoff_raw)
    qsts = _qsts_from_mapping(qsts_raw)
    handoff_artifacts = tuple(
        (record.relative_path, record.sha256) for record in handoff.artifact_records
    )
    qsts_artifacts = tuple(
        (record.relative_path, record.sha256) for record in qsts.payload_records
    )
    if (
        qsts.input_handoff_sha256 != expected_handoff_sha256
        or qsts.input_handoff_schema != handoff.schema
        or qsts.input_package_manifest_sha256 != handoff.package_manifest_sha256
        or qsts.input_profile_sha256 != handoff.profile_sha256
        or qsts.input_profile_values_sha256 != handoff.profile_values_sha256
        or qsts_artifacts != handoff_artifacts
        or qsts.profile_row_count != handoff.profile_row_count
        or qsts.profile_start_utc != handoff.profile_start_utc
        or qsts.profile_end_utc != handoff.profile_end_utc
        or qsts.profile_timezone != handoff.profile_timezone
        or qsts.profile_timestep_hours != handoff.profile_timestep_hours
        or qsts.profile_unit != handoff.profile_unit
        or qsts.required_warning != handoff.required_warning
    ):
        raise ValueError(
            "#1073 output identity does not match authenticated #1077 input."
        )
    return AuthenticatedSyntheticReportInputs(
        handoff=handoff,
        handoff_sha256=expected_handoff_sha256,
        handoff_payload=handoff_payload,
        qsts=qsts,
        qsts_sha256=expected_qsts_output_sha256,
        qsts_payload=qsts_payload,
    )


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Finance result omitted finite {field}.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Finance result omitted finite {field}.")
    return result


def _extract_kpis(result: Mapping[str, Any]) -> SyntheticFinanceKpis:
    raw_kpis = result.get("kpis")
    raw_rows = result.get("annual_rows")
    if (
        not isinstance(raw_kpis, Mapping)
        or not isinstance(raw_rows, list)
        or not raw_rows
    ):
        raise ValueError("Full finance evaluation omitted KPI or annual-row evidence.")
    rows: list[Mapping[str, Any]] = []
    for index, value in enumerate(raw_rows):
        if not isinstance(value, Mapping):
            raise ValueError(f"Finance annual row {index} is not a mapping.")
        rows.append(value)
    generation = [
        _finite_number(row.get("net_kwh"), f"annual_rows[{index}].net_kwh") / 1000.0
        for index, row in enumerate(rows)
    ]
    revenue = [
        _finite_number(row.get("revenue_usd"), f"annual_rows[{index}].revenue_usd")
        for index, row in enumerate(rows)
    ]
    return SyntheticFinanceKpis(
        project_irr=_finite_number(raw_kpis.get("project_irr"), "project_irr"),
        equity_irr=_finite_number(raw_kpis.get("equity_irr"), "equity_irr"),
        project_npv_usd=_finite_number(raw_kpis.get("project_npv"), "project_npv"),
        minimum_dscr=_finite_number(raw_kpis.get("min_dscr"), "min_dscr"),
        year1_net_generation_mwh=generation[0],
        lifetime_net_generation_mwh=math.fsum(generation),
        year1_revenue_usd=revenue[0],
        lifetime_revenue_usd=math.fsum(revenue),
    )


def _movement(
    baseline: SyntheticFinanceKpis, counterfactual: SyntheticFinanceKpis
) -> SyntheticFinanceKpis:
    values = {
        item.name: getattr(counterfactual, item.name) - getattr(baseline, item.name)
        for item in fields(SyntheticFinanceKpis)
    }
    return SyntheticFinanceKpis(**values)


def evaluate_synthetic_qsts_finance_counterfactual(
    *,
    inputs: AuthenticatedSyntheticReportInputs,
    scenario_path: Path,
    evaluator: FinanceEvaluator = _DEFAULT_EVALUATOR,
) -> SyntheticCounterfactualEvaluation:
    """Evaluate unchanged baseline and the one-key synthetic counterfactual."""

    _reject_symlink_ancestors(scenario_path, "counterfactual scenario")
    if scenario_path.is_symlink() or not scenario_path.is_file():
        raise FileNotFoundError("Counterfactual scenario is absent or a symlink.")
    scenario_before = scenario_path.read_bytes()
    raw_scenario = load_scenario_config(scenario_path)
    qsts = inputs.qsts
    if qsts.gross_energy_mwh <= 0.0:
        raise ValueError("#1073 gross energy must be positive for finance treatment.")
    self_decimal = qsts.self_curtailed_energy_mwh / qsts.gross_energy_mwh
    if not 0.0 <= self_decimal < 1.0:
        raise ValueError("Synthetic self-curtailment fraction must be in [0, 1).")
    baseline_decimal, composed = compose_noncanonical_project_curtailment(
        raw_scenario, self_decimal
    )
    overrides = {"project.curtailment_pct": composed}
    baseline_result = evaluator(
        config_path=str(scenario_path), overrides={}, return_full_result=True
    )
    counterfactual_result = evaluator(
        config_path=str(scenario_path),
        overrides=overrides,
        return_full_result=True,
    )
    if not isinstance(baseline_result, Mapping) or not isinstance(
        counterfactual_result, Mapping
    ):
        raise TypeError("Finance evaluation gateway must return full result mappings.")
    baseline = _extract_kpis(baseline_result)
    counterfactual = _extract_kpis(counterfactual_result)
    movement = SyntheticFinanceKpiMovement(
        baseline=baseline,
        counterfactual=counterfactual,
        movement=_movement(baseline, counterfactual),
    )
    if self_decimal > 0.0:
        for field_name in (
            "project_irr",
            "equity_irr",
            "project_npv_usd",
            "minimum_dscr",
            "year1_net_generation_mwh",
            "lifetime_net_generation_mwh",
            "year1_revenue_usd",
            "lifetime_revenue_usd",
        ):
            if (
                getattr(counterfactual, field_name)
                > getattr(baseline, field_name) + 1.0e-9
            ):
                raise ValueError(
                    f"Synthetic self-curtailment unexpectedly improved {field_name}."
                )
    if scenario_path.read_bytes() != scenario_before:
        raise ValueError("Canonical scenario bytes changed during #1074 evaluation.")
    return SyntheticCounterfactualEvaluation(
        baseline_project_curtailment_decimal=baseline_decimal,
        synthetic_self_curtailment_decimal=self_decimal,
        counterfactual_project_curtailment_decimal=composed,
        deemed_paid_finance_haircut_decimal=0.0,
        override_items=(("project.curtailment_pct", composed),),
        kpis=movement,
    )


def require_canonical_finance_release(
    record: Any,
) -> None:
    """Refuse use of the #1074 synthetic record as a canonical finance release."""

    raise ValueError(
        "Canonical finance release refused: #1074 is synthetic, non-bankable, "
        "noncanonical, and only for process-provenance purposes."
    )


__all__ = [
    "AuthenticatedSyntheticReportInputs",
    "SyntheticCounterfactualEvaluation",
    "canonical_json",
    "evaluate_synthetic_qsts_finance_counterfactual",
    "load_authenticated_synthetic_report_inputs",
    "require_canonical_finance_release",
    "sha256_bytes",
    "sha256_path",
]
