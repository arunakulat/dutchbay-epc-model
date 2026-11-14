"""Export public scenario references and blank financing questions, not lender terms."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = {
    "wind": "scenarios/blue_whale_wind_lot5b_2026.yaml",
    "solar_bess": "scenarios/blue_whale_solar_bess_lot5b_2026.yaml",
}
SUPPORTED_PATHS = frozenset(
    {
        "Financing_Terms.interest_rate_nominal",
        "Financing_Terms.rates.lkr_nominal",
        "Financing_Terms.rates.dfi_nominal",
        "Financing_Terms.rates.usd_nominal",
        "Financing_Terms.debt_ratio",
        "Financing_Terms.tenor_years",
        "Financing_Terms.interest_only_years",
        "Financing_Terms.target_dscr",
        "Financing_Terms.min_dscr",
        "constraints.min_dscr_covenant",
        "constraints.target_dscr",
        "Financing_Terms.reserves.dsra_months",
        "Financing_Terms.fees.upfront_pct",
        "capex.usd_total",
        "capex.price_basis.price_year",
        "fx.start_lkr_per_usd",
        "ppa.primary_currency",
        "Financing_Terms.mix.lkr_max",
    }
)


class QuestionnaireError(ValueError):
    """Invalid export configuration or source data."""


def _keys(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise QuestionnaireError(f"{label}: expected keys {sorted(expected)}")


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QuestionnaireError(f"{label}: nonempty string required")
    return value


class _UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader: _UniqueLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise QuestionnaireError("source YAML contains duplicate or non-string key")
        result[key] = loader.construct_object(value_node)
    return result


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def build_questionnaire(config: Mapping[str, Any], raw: bytes) -> dict[str, Any]:
    """Build a deterministic public export from one selected scenario's bytes.

    Args:
        config: Strict questionnaire configuration, excluding Hydra settings.
        raw: Exact UTF-8 source scenario bytes.

    Returns:
        A JSON-serializable questionnaire with untouched source bytes and blank answers.

    Raises:
        QuestionnaireError: If configuration or required source values are invalid.
    """
    _keys(config, {"project", "output_name", "fields", "gaps"}, "config")
    project = config["project"]
    if not isinstance(project, str) or project not in SCENARIOS:
        raise QuestionnaireError("unsupported project")
    name = _text(config["output_name"], "output_name")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise QuestionnaireError("output_name must be a simple file stem")
    try:
        source = yaml.load(  # nosec B506 - _UniqueLoader subclasses yaml.SafeLoader
            raw.decode("utf-8"), Loader=_UniqueLoader
        )
    except (UnicodeError, yaml.YAMLError) as exc:
        raise QuestionnaireError("invalid source YAML") from exc
    if not isinstance(source, dict):
        raise QuestionnaireError("source must be a mapping")

    def reject_nonfinite(value: Any) -> None:
        if isinstance(value, float) and not math.isfinite(value):
            raise QuestionnaireError("source contains a non-finite number")
        if isinstance(value, dict):
            for nested in value.values():
                reject_nonfinite(nested)
        elif isinstance(value, list):
            for nested in value:
                reject_nonfinite(nested)

    reject_nonfinite(source)
    digest = hashlib.sha256(raw).hexdigest()
    rows: list[dict[str, Any]] = []
    ids: set[str] = set()
    paths: set[str] = set()
    for section, expected in (
        ("fields", {"id", "path", "unit", "label", "note"}),
        ("gaps", {"id", "label", "note"}),
    ):
        entries = config[section]
        if not isinstance(entries, list) or not entries:
            raise QuestionnaireError(f"{section}: nonempty list required")
        for item in entries:
            _keys(item, expected, section)
            for key in expected:
                _text(item[key], key)
            identifier = item["id"]
            if identifier in ids:
                raise QuestionnaireError("duplicate id")
            ids.add(identifier)
            reference = None
            if section == "fields":
                path = item["path"]
                if path not in SUPPORTED_PATHS or path in paths:
                    raise QuestionnaireError(f"unsupported or duplicate path: {path}")
                paths.add(path)
                value: Any = source
                for part in path.split("."):
                    if not isinstance(value, dict) or part not in value:
                        raise QuestionnaireError(
                            f"missing required source path: {path}"
                        )
                    value = value[part]
                valid_type = (
                    type(value) is str
                    if path == "ppa.primary_currency"
                    else type(value) in (int, float)
                )
                if not valid_type or (
                    isinstance(value, float) and not math.isfinite(value)
                ):
                    raise QuestionnaireError(f"invalid scalar at {path}")
                reference = {
                    "value": value,
                    "unit": item["unit"],
                    "source_kind": "model_assumption",
                    "source_model_path": SCENARIOS[project],
                    "source_sha256": digest,
                    "source_field_path": path,
                }
            rows.append(
                {
                    "id": identifier,
                    "label": item["label"],
                    "note": item["note"],
                    "model_reference": reference,
                    "answer_status": "unknown",
                    "answer_value": None,
                    "answer_basis": None,
                    "answer_date": None,
                    "answer_citation": None,
                }
            )
    if paths != SUPPORTED_PATHS:
        raise QuestionnaireError("all supported source paths must be configured")
    return {
        "schema_version": "1",
        "project": project,
        "notice": "Public model references are assumptions, not confirmed transaction terms. This outbound questionnaire is not a validated F5-02 evidence return. Completed answers require separately scoped private ingress and acceptance under F5-02 controls; this generator does not import answers or authenticate terms.",
        "source": {
            "path": SCENARIOS[project],
            "sha256": digest,
            "raw_yaml_base64": base64.b64encode(raw).decode("ascii"),
        },
        "questions": rows,
    }


def export_questionnaire(
    config: Mapping[str, Any], root: Path = ROOT
) -> dict[str, str]:
    """Write a new JSON and fillable workbook under outputs without overwriting files.

    Args:
        config: Strict export configuration.
        root: Repository root supplying the two public scenarios and outputs directory.

    Returns:
        Relative output paths and source hash for a concise receipt.

    Raises:
        QuestionnaireError: If paths or source/configuration are invalid.
    """
    try:
        from openpyxl import Workbook
        from openpyxl.worksheet.worksheet import Worksheet
    except ImportError as exc:
        raise QuestionnaireError("openpyxl is required for workbook export") from exc
    project = config.get("project")
    if not isinstance(project, str) or project not in SCENARIOS:
        raise QuestionnaireError("unsupported project")
    raw = (root / SCENARIOS[project]).read_bytes()
    data = build_questionnaire(config, raw)
    out = root / "outputs"
    out.mkdir(exist_ok=True)
    if out.is_symlink() or not out.is_dir() or out.resolve().parent != root.resolve():
        raise QuestionnaireError("outputs must be a real directory under the root")
    stem = config["output_name"]
    json_path, xlsx_path = out / f"{stem}.json", out / f"{stem}.xlsx"
    # Exclusive creation ensures a rerun never overwrites either existing artifact.
    if (
        json_path.exists()
        or json_path.is_symlink()
        or xlsx_path.exists()
        or xlsx_path.is_symlink()
    ):
        raise QuestionnaireError("output already exists")
    wb = Workbook()
    ws = wb.active
    if not isinstance(ws, Worksheet):
        raise QuestionnaireError("workbook has no worksheet")
    ws.title = "Questions"
    headers = [
        "id",
        "label",
        "note",
        "model_reference_value",
        "unit",
        "source_kind",
        "source_model_path",
        "source_sha256",
        "source_field_path",
        "answer_status",
        "answer_value",
        "answer_basis",
        "answer_date",
        "answer_citation",
    ]
    ws.append(headers)
    for row in data["questions"]:
        ref = row["model_reference"] or {}
        values = [
            row["id"],
            row["label"],
            row["note"],
            ref.get("value"),
            ref.get("unit"),
            ref.get("source_kind"),
            ref.get("source_model_path"),
            ref.get("source_sha256"),
            ref.get("source_field_path"),
            row["answer_status"],
            None,
            None,
            None,
            None,
        ]
        # Explicit string type prevents formula interpretation without changing displayed text.
        ws.append(values)
        for cell in ws[ws.max_row]:
            if isinstance(cell.value, str):
                cell.data_type = "s"
    ws.freeze_panes = "D2"
    ws.auto_filter.ref = ws.dimensions
    readme = wb.create_sheet("Read me")
    readme.append(["Status", "Outbound questionnaire; answers are unconfirmed"])
    readme.append(["Notice", data["notice"]])
    readme.append(["Project", data["project"]])
    readme.append(["Model source", data["source"]["path"]])
    readme.append(["Source SHA-256", data["source"]["sha256"]])
    created_json = False
    created_xlsx = False
    try:
        with json_path.open("x", encoding="utf-8", newline="\n") as file:
            created_json = True
            json.dump(
                data,
                file,
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )
            file.write("\n")
        with xlsx_path.open("xb") as file:
            created_xlsx = True
            wb.save(file)
    except Exception:
        if created_xlsx:
            xlsx_path.unlink()
        if created_json:
            json_path.unlink()
        raise
    return {
        "json": f"outputs/{stem}.json",
        "xlsx": f"outputs/{stem}.xlsx",
        "source_sha256": data["source"]["sha256"],
    }
