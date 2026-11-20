"""Tests for the macro-free, formula-driven DFI workbook foundation (W3-1).

Covers:
- Strict Pydantic contracts (``CESSPIT`` ``extra="forbid"``, ``frozen=True``, fail-loud
  negative controls on invalid sheets, columns, rows, non-finite inputs, empty notice).
- ``CellRegistry`` duplicate-key and coordinate-collision detection, safe sheet quoting,
  and validated range references.
- Byte-reproducibility (ZIP-byte SHA-256 identity across paths and wall-clock gap) and
  macro-free OOXML archive verification.
- Live ``=COUNTIF(...)`` and ``=SUM(...)`` formulas on ``Module_Ledger``, verified against
  an independent LibreOffice Calc (``soffice``) evaluation oracle when available.
"""

from __future__ import annotations

import ast
import hashlib
import io
import math
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import openpyxl
import pytest
from pydantic import ValidationError

from analytics.dfi_workbook import (
    DFI_WORKBOOK_F5_CAVEAT,
    CellRef,
    CellRegistry,
    DfiWorkbookMetadata,
    ModuleLedgerEntry,
    WorkbookInputItem,
    build_dfi_workbook_foundation,
)
from analytics.dfi_workbook.foundation import CANONICAL_LEDGER_STATUSES
from analytics.executive_workbook import EXECUTIVE_WORKBOOK_F5_CAVEAT
from analytics.reproducible_workbook import REPRODUCIBLE_EPOCH

_EXCEL_ERRORS = (
    "#REF!",
    "#NAME?",
    "#VALUE!",
    "#DIV/0!",
    "#N/A",
    "#NUM!",
    "#NULL!",
    "Err:",
)


def _sample_metadata(**overrides: Any) -> DfiWorkbookMetadata:
    payload: dict[str, Any] = {
        "project_name": "Sample Utility Wind Project",
        "scenario_name": "base_case",
        "run_mode": "full_deterministic",
        "config_sha256": "a" * 64,
        "engine_version": "15.28.0",
        "generated_at": "2026-11-19T12:00:00Z",
    }
    payload.update(overrides)
    return DfiWorkbookMetadata(**payload)


@pytest.mark.parametrize("codepoint", (0xFFFE, 0xFFFF))
@pytest.mark.parametrize("surface", ("input", "metadata", "ledger"))
def test_xml_illegal_literals_are_refused_before_destination_creation(
    tmp_path: Path, codepoint: int, surface: str
) -> None:
    destination = tmp_path / "invalid_xml.xlsx"
    literal = "source" + chr(codepoint)
    with pytest.raises(ValueError, match="XML"):
        build_dfi_workbook_foundation(
            destination,
            metadata=_sample_metadata(
                **({"project_name": literal} if surface == "metadata" else {})
            ),
            inputs=(
                WorkbookInputItem(
                    key="source",
                    section="Source",
                    label="Literal",
                    value=literal if surface == "input" else "valid",
                    unit="",
                    provenance="source",
                ),
            ),
            ledger_entries=(
                ModuleLedgerEntry(
                    module_path="source.module",
                    pipeline_stage="source",
                    role_description=literal if surface == "ledger" else "valid",
                    status="executed",
                    excel_representation="ledger_only",
                ),
            ),
        )
    assert not destination.exists()


@pytest.mark.parametrize("literal", ("source\ufffd", "source\U00010000"))
def test_xml_boundary_literals_reopen_exactly(tmp_path: Path, literal: str) -> None:
    item = _sample_inputs()[0].model_dump() | {"value": literal}
    destination, _ = build_dfi_workbook_foundation(
        tmp_path / "valid_xml.xlsx",
        metadata=_sample_metadata(),
        inputs=(WorkbookInputItem.model_validate(item),),
        ledger_entries=(),
    )
    with zipfile.ZipFile(destination) as archive:
        for name in archive.namelist():
            if name.endswith(".xml"):
                ET.fromstring(archive.read(name))
    workbook = openpyxl.load_workbook(destination)
    assert workbook["Inputs"]["D2"].value == literal
    workbook.close()


@pytest.mark.parametrize(
    "value",
    (
        10**15,
        -(10**15),
        9007199254740992,
        9007199254740993,
        10000000000000000,
        10000000000000001,
        sys.float_info.max,
        -sys.float_info.max,
        sys.float_info.min,
        math.nextafter(0.0, 1.0),
        math.nextafter(2.2251e-308, 0.0),
        math.nextafter(9.99999999999999e307, math.inf),
        1.234567890123456,
        0.1 + 0.2,
    ),
)
def test_unsupported_numeric_sources_are_refused_before_emission(
    tmp_path: Path, value: int | float
) -> None:
    destination = tmp_path / "unsafe_numeric.xlsx"
    with pytest.raises(ValueError, match="Excel numeric"):
        item = WorkbookInputItem.model_validate(
            _sample_inputs()[0].model_dump() | {"value": value}
        )
        build_dfi_workbook_foundation(
            destination,
            metadata=_sample_metadata(),
            inputs=(item,),
            ledger_entries=(),
        )
    assert not destination.exists()


def test_supported_numeric_boundaries_survive_xml_and_readback(tmp_path: Path) -> None:
    """Decimal XML checks do not share the exporter's float formatting oracle."""
    values = (
        999999999999998,
        999999999999999,
        -999999999999999,
        0,
        True,
        -2.5,
        0.1,
        1.23456789012345,
        2.2251e-308,
        -2.2251e-308,
        9.99999999999999e307,
        -9.99999999999999e307,
    )
    items = tuple(
        WorkbookInputItem.model_validate(
            _sample_inputs()[0].model_dump() | {"key": f"n{n}", "value": value}
        )
        for n, value in enumerate(values)
    )
    path, registry = build_dfi_workbook_foundation(
        tmp_path / "numeric_boundaries.xlsx",
        metadata=_sample_metadata(),
        inputs=items,
        ledger_entries=(),
    )
    with zipfile.ZipFile(path) as archive:
        tree = ET.fromstring(archive.read("xl/worksheets/sheet2.xml"))
    workbook = openpyxl.load_workbook(path)
    for n, value in enumerate(values):
        ref = registry.get(f"n{n}")
        coordinate = f"D{ref.row}"
        cell = workbook["Inputs"][coordinate]
        assert cell.value == value
        if isinstance(value, bool):
            assert cell.data_type == "b"
            continue
        assert cell.data_type == "n"
        assert math.isfinite(cell.value)
        element = tree.find(f'.//{{*}}c[@r="{coordinate}"]/{{*}}v')
        assert element is not None and element.text is not None
        assert Decimal(element.text) == Decimal(str(value))
    workbook.close()


def _sample_inputs() -> tuple[WorkbookInputItem, ...]:
    return (
        WorkbookInputItem(
            key="project.capacity_mw",
            section="Technical",
            label="Installed Capacity",
            value=100.0,
            unit="MW",
            number_format="#,##0.0",
            provenance="scenario_yaml:project.capacity_mw",
        ),
        WorkbookInputItem(
            key="debt.tenor_years",
            section="Financing",
            label="Senior Debt Tenor",
            value=15,
            unit="years",
            number_format="0",
            provenance="scenario_yaml:debt.tenor_years",
        ),
        WorkbookInputItem(
            key="tariff.rate_usd_mwh",
            section="Revenue",
            label="Flat PPA Tariff",
            value=68.5,
            unit="USD/MWh",
            number_format="$#,##0.00",
            provenance="ppa_schedule:base_tariff",
        ),
        WorkbookInputItem(
            key="control.tax_holiday_enabled",
            section="Tax",
            label="Tax Holiday Enabled",
            value=True,
            unit="",
            number_format="General",
            provenance="scenario_yaml:tax.holiday_enabled",
        ),
        WorkbookInputItem(
            key="project.currency",
            section="Macro",
            label="Reporting Currency",
            value="USD",
            unit="ISO-4217",
            number_format="@",
            provenance="scenario_yaml:project.currency",
        ),
    )


def _sample_ledger() -> tuple[ModuleLedgerEntry, ...]:
    return (
        ModuleLedgerEntry(
            module_path="finance.cashflow_v14",
            pipeline_stage="cashflow",
            role_description="Annual project cashflow waterfall",
            status="executed",
            excel_representation="engine_table",
            reason="",
            provenance_ref="run_manifest:cashflow",
        ),
        ModuleLedgerEntry(
            module_path="finance.debt_v14",
            pipeline_stage="debt",
            role_description="Multi-tranche DSCR sculpting engine",
            status="executed",
            excel_representation="engine_table",
            reason="",
            provenance_ref="run_manifest:debt",
        ),
        ModuleLedgerEntry(
            module_path="analytics.schema_guard",
            pipeline_stage="preflight",
            role_description="Strict v14 schema validation",
            status="guard_passed",
            excel_representation="ledger_only",
            reason="all required keys validated",
            provenance_ref="guard:schema_v14",
        ),
        ModuleLedgerEntry(
            module_path="analytics.grid.pandapower_screening",
            pipeline_stage="grid",
            role_description="Optional grid hosting-capacity screen",
            status="skipped_optional_extra",
            excel_representation="omitted",
            reason="grid extra disabled in deterministic profile",
            provenance_ref="opt_extra:grid",
        ),
        ModuleLedgerEntry(
            module_path="analytics.mc.engine",
            pipeline_stage="stochastic",
            role_description="Monte Carlo simulation engine",
            status="skipped_sync_profile",
            excel_representation="omitted",
            reason="deterministic run mode selected",
            provenance_ref="run_mode:deterministic",
        ),
    )


def _assert_no_excel_errors(wb: openpyxl.Workbook) -> None:
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            for value in row:
                if isinstance(value, str):
                    for err in _EXCEL_ERRORS:
                        err_msg = (
                            f"Excel formula error {err!r} found in "
                            f"{ws.title}: {value!r}"
                        )
                        assert err not in value, err_msg


# ---------------------------------------------------------------------------
# Architecture boundary checks
# ---------------------------------------------------------------------------


def test_dfi_workbook_package_has_no_forbidden_layer_imports() -> None:
    package_dir = Path(__file__).resolve().parents[2] / "analytics" / "dfi_workbook"
    for py_file in sorted(package_dir.glob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                targets = [node.module]
            else:
                continue
            for mod in targets:
                app_msg = f"{py_file.name} imports forbidden app module {mod!r}"
                assert not (mod == "app" or mod.startswith("app.")), app_msg
                fin_msg = f"{py_file.name} imports forbidden finance module {mod!r}"
                assert not (mod == "finance" or mod.startswith("finance.")), fin_msg
                pipe_msg = f"{py_file.name} imports forbidden pipeline module {mod!r}"
                assert not mod.startswith("analytics.pipeline_"), pipe_msg
                exec_msg = f"{py_file.name} must not import {mod!r}"
                assert not (
                    mod == "analytics.executive_workbook"
                    or mod == "pandas"
                    or mod.startswith("pandas.")
                    or mod == "numpy"
                    or mod.startswith("numpy.")
                ), exec_msg


def test_f5_caveat_matches_executive_workbook_and_stays_pandas_numpy_free() -> None:
    assert DFI_WORKBOOK_F5_CAVEAT == EXECUTIVE_WORKBOOK_F5_CAVEAT
    repo_root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(repo_root)
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys, analytics.dfi_workbook; "
                "assert 'pandas' not in sys.modules, 'pandas leaked at import'; "
                "assert 'numpy' not in sys.modules, 'numpy leaked at import'; "
                "assert 'openpyxl' not in sys.modules, 'openpyxl leaked at import'"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Clean-import guard failed: {proc.stderr}"


# ---------------------------------------------------------------------------
# CellRef & CellRegistry validation and negative controls
# ---------------------------------------------------------------------------


class TestCellRef:
    def test_valid_coordinates_and_safe_quoting(self) -> None:
        simple = CellRef(sheet="Inputs", column="c", row=5, unit="MW")
        assert simple.column == "C"
        assert simple.coord == "C5"
        assert simple.abs_coord == "$C$5"
        assert simple.formula_ref() == "Inputs!$C$5"
        assert simple.formula_ref(absolute=False) == "Inputs!C5"

        spaced = CellRef(sheet="Cash Flow", column="XFD", row=1_048_576)
        assert spaced.formula_ref() == "'Cash Flow'!$XFD$1048576"
        assert spaced.formula_ref(absolute=False) == "'Cash Flow'!XFD1048576"

        quoted = CellRef(sheet="Bob's_Sheet", column="AA", row=12)
        assert quoted.formula_ref() == "'Bob''s_Sheet'!$AA$12"

        a1_collision = CellRef(sheet="FY2026", column="B", row=3)
        assert a1_collision.formula_ref() == "'FY2026'!$B$3"

        for rc_name in ("R", "r", "C", "c", "RC", "R1C1", "R12C34"):
            rc_ref = CellRef(sheet=rc_name, column="A", row=1)
            assert rc_ref.formula_ref() == f"'{rc_name}'!$A$1"

        max_len = CellRef(sheet="S" * 31, column="A", row=1)
        assert len(max_len.sheet) == 31

    @pytest.mark.parametrize(
        "bad_sheet",
        [
            "",
            "   ",
            " Inputs",
            "Inputs ",
            "In\x00puts",
            "In\nputs",
            "In\rputs",
            "In\tputs",
            "In\x1fputs",
            "S" * 32,
            "Bad\\Sheet",
            "Bad/Sheet",
            "Bad?Sheet",
            "Bad*Sheet",
            "Bad[Sheet",
            "Bad]Sheet",
            "Bad:Sheet",
            "'Leading",
            "Trailing'",
        ],
    )
    def test_invalid_sheet_name_fails_loud(self, bad_sheet: str) -> None:
        with pytest.raises(ValueError):
            CellRef(sheet=bad_sheet, column="A", row=1)

    @pytest.mark.parametrize("bad_ctrl", ["ok\x00", "ok\n", "ok\r", "ok\t", "ok\x1f"])
    def test_cell_ref_rejects_control_chars_in_metadata(self, bad_ctrl: str) -> None:
        with pytest.raises(ValueError):
            CellRef(sheet="Inputs", column="A", row=1, unit=bad_ctrl)
        with pytest.raises(ValueError):
            CellRef(sheet="Inputs", column="A", row=1, provenance=bad_ctrl)
        with pytest.raises(ValueError):
            CellRef(sheet="Inputs", column="A", row=1, number_format=bad_ctrl)

    @pytest.mark.parametrize(
        "bad_col",
        ["", " ", "1", "A1", "$A", "AAAA", "XFE", "ZZZ", " A"],
    )
    def test_invalid_column_fails_loud(self, bad_col: str) -> None:
        with pytest.raises(ValueError):
            CellRef(sheet="Inputs", column=bad_col, row=1)

    @pytest.mark.parametrize(
        "bad_row",
        [0, -1, True, False, 1.5, "1", 1_048_577],
    )
    def test_invalid_row_fails_loud(self, bad_row: Any) -> None:
        with pytest.raises(ValueError):
            CellRef(sheet="Inputs", column="A", row=bad_row)

    def test_extra_forbid_and_frozen(self) -> None:
        with pytest.raises(ValidationError):
            CellRef(sheet="Inputs", column="A", row=1, unknown_field=123)  # type: ignore[call-arg]
        ref = CellRef(sheet="Inputs", column="A", row=1)
        with pytest.raises(ValidationError):
            ref.row = 2  # type: ignore[misc]


class TestCellRegistry:
    def test_register_get_ref_and_range_ref(self) -> None:
        reg = CellRegistry()
        ref = reg.register(
            "tariff.base",
            sheet="Inputs",
            column="d",
            row=4,
            unit="USD/MWh",
            number_format="$#,##0.00",
            provenance="ppa",
        )
        assert ref.formula_ref() == "Inputs!$D$4"
        assert reg.get("tariff.base") == ref
        assert reg.ref("tariff.base") == "Inputs!$D$4"
        assert reg.ref("tariff.base", absolute=False) == "Inputs!D4"
        assert "tariff.base" in reg
        assert len(reg) == 1
        assert reg.keys() == ("tariff.base",)
        assert (
            reg.range_ref("Module_Ledger", "D", 2, "D", 9) == "Module_Ledger!$D$2:$D$9"
        )
        assert (
            reg.range_ref("Cash Flow", "b", 2, "d", 5, absolute=False)
            == "'Cash Flow'!B2:D5"
        )

    def test_duplicate_key_fails_loud(self) -> None:
        reg = CellRegistry()
        reg.register("k1", sheet="Inputs", column="D", row=2)
        with pytest.raises(ValueError, match="Duplicate CellRegistry key"):
            reg.register("k1", sheet="Inputs", column="D", row=3)

    def test_coordinate_collision_fails_loud(self) -> None:
        reg = CellRegistry()
        reg.register("k1", sheet="Inputs", column="D", row=2)
        with pytest.raises(ValueError, match="collision"):
            reg.register("k2", sheet="inputs", column="d", row=2)

    def test_missing_key_raises_actionable_key_error(self) -> None:
        reg = CellRegistry()
        reg.register("present.key", sheet="Inputs", column="D", row=2)
        with pytest.raises(KeyError, match="present.key"):
            reg.get("missing.key")

    def test_empty_key_and_inverted_range_fail_loud(self) -> None:
        reg = CellRegistry()
        for bad_key in ("   ", " k1", "k1 ", " k1 ", "k1\n", "k1\x00", "\tk1"):
            with pytest.raises(ValueError):
                reg.register(bad_key, sheet="Inputs", column="D", row=2)
        with pytest.raises(ValueError, match="Inverted"):
            reg.range_ref("Inputs", "D", 5, "D", 2)
        with pytest.raises(ValueError, match="Inverted"):
            reg.range_ref("Inputs", "E", 2, "B", 5)


# ---------------------------------------------------------------------------
# Strict contract negative controls (CESSPIT)
# ---------------------------------------------------------------------------


class TestStrictContracts:
    def test_metadata_defaults_and_non_reliance_refusal(self) -> None:
        meta = _sample_metadata()
        assert meta.non_reliance_notice == DFI_WORKBOOK_F5_CAVEAT
        assert meta.non_reliance_notice == EXECUTIVE_WORKBOOK_F5_CAVEAT
        assert "HOLD (F-5, #1110, v15.6.1)" in meta.non_reliance_notice
        assert "Option B" in meta.formula_boundary_note

        for bad_notice in (
            "",
            "   ",
            "Approved for IC reliance",
            "HOLD (F-5, #1110, v15.6.1): custom truncated notice",
            f"Approved for IC reliance. {DFI_WORKBOOK_F5_CAVEAT}",
            f"  {DFI_WORKBOOK_F5_CAVEAT}",
        ):
            with pytest.raises(ValueError, match="non_reliance_notice"):
                _sample_metadata(non_reliance_notice=bad_notice)

        appended = _sample_metadata(
            non_reliance_notice=f"{DFI_WORKBOOK_F5_CAVEAT} Scenario: stress-test."
        )
        assert appended.non_reliance_notice.startswith(DFI_WORKBOOK_F5_CAVEAT)

        with pytest.raises(ValidationError):
            DfiWorkbookMetadata(
                project_name="P",
                scenario_name="S",
                config_sha256="a" * 64,
                engine_version="1.0",
                generated_at="2026-11-19T00:00:00Z",
                unexpected="nope",  # type: ignore[call-arg]
            )

    @pytest.mark.parametrize(
        "bad_sha",
        [
            "A" * 64,
            "g" * 64,
            "a" * 63,
            "a" * 65,
            " " + "a" * 64,
            "not-a-sha",
        ],
    )
    def test_metadata_rejects_invalid_config_sha256(self, bad_sha: str) -> None:
        with pytest.raises(ValueError, match="config_sha256"):
            _sample_metadata(config_sha256=bad_sha)

    def test_metadata_validates_generated_at_iso8601(self) -> None:
        for ok_ts in (
            "2026-11-19T12:00:00Z",
            "2026-11-19T12:00:00+00:00",
            "2026-11-19T17:30:00+05:30",
            "2026-11-19",
        ):
            assert _sample_metadata(generated_at=ok_ts).generated_at == ok_ts

        for bad_ts in (
            "not-a-date",
            "2026-13-01T00:00:00Z",
            "2026-02-30",
            "2026-11-19T12:00:00",
            "20261119",
            " 2026-11-19T12:00:00Z",
            "=TODAY()",
        ):
            with pytest.raises(ValueError, match="generated_at"):
                _sample_metadata(generated_at=bad_ts)

    @pytest.mark.parametrize(
        "bad_val",
        [
            float("nan"),
            float("inf"),
            float("-inf"),
            None,
            [1],
            (1,),
            np.array([1.0]),
            np.array(1.0),
            np.float64(1.0),
            np.int64(1),
            np.bool_(True),
        ],
    )
    def test_input_item_rejects_non_finite_and_non_scalar(self, bad_val: Any) -> None:
        with pytest.raises(ValueError):
            WorkbookInputItem(
                key="k",
                section="Sec",
                label="Lbl",
                value=bad_val,
                unit="MW",
                provenance="cfg",
            )

    def test_input_item_allows_negative_numeric_and_hyphenated_strings(self) -> None:
        neg_int = WorkbookInputItem(
            key="tax.loss_carryforward",
            section="Tax-Config",
            label="Initial Balance",
            value=-42,
            unit="USD",
            provenance="base-case",
        )
        assert neg_int.value == -42

        neg_float = WorkbookInputItem(
            key="macro.delta_pct",
            section="Macro-Assumptions",
            label="CPI Adjustment",
            value=-0.25,
            unit="pct",
            provenance="non-reliance-case",
        )
        assert neg_float.value == -0.25

        with pytest.raises(ValueError, match="whitespace"):
            WorkbookInputItem(
                key=" padded.key ",
                section="Sec",
                label="Lbl",
                value=1.0,
                unit="MW",
                provenance="cfg",
            )

    @pytest.mark.parametrize(
        "bad_status",
        [
            "MixedCase",
            "EXECUTED",
            "Executed",
            "*",
            "exec*",
            "?",
            "~",
            "total",
            "Total",
            "<>failed",
            "=executed",
            ">1",
            "<0",
            "executed\n",
            "\texecuted",
            "executed\x00",
            "with space",
            "1bad",
            "",
            "   ",
        ],
    )
    def test_ledger_status_rejects_non_canonical_and_wildcard_inputs(
        self, bad_status: str
    ) -> None:
        with pytest.raises(ValueError):
            ModuleLedgerEntry(
                module_path="finance.cashflow_v14",
                pipeline_stage="cashflow",
                role_description="Cashflow engine",
                status=bad_status,
                excel_representation="engine_table",
            )

    def test_ledger_status_strips_outer_spaces_on_valid_lowercase(self) -> None:
        entry = ModuleLedgerEntry(
            module_path="finance.cashflow_v14",
            pipeline_stage="cashflow",
            role_description="Multi-tranche cashflow",
            status="  executed  ",
            excel_representation="engine_table",
        )
        assert entry.status == "executed"

    @pytest.mark.parametrize(
        "bad_payload",
        [
            "=1+1",
            "+CMD|' /C calc'!A0",
            "-1+1",
            "@SUM(1,1)",
            " =1+1",
            "\t=1+1",
            "\r=1+1",
            "\n=1+1",
            "line1\nline2",
            "line1\rline2",
            "bad\x00nul",
            "bad\x1fus",
        ],
    )
    def test_formula_injection_and_control_chars_rejected_across_models(
        self, bad_payload: str
    ) -> None:
        for field in (
            "project_name",
            "scenario_name",
            "run_mode",
            "engine_version",
            "formula_boundary_note",
        ):
            with pytest.raises(ValueError):
                _sample_metadata(**{field: bad_payload})

        notice_val = (
            f"{DFI_WORKBOOK_F5_CAVEAT} {bad_payload}"
            if any(ord(c) < 0x20 for c in bad_payload)
            else bad_payload
        )
        with pytest.raises(ValueError):
            _sample_metadata(non_reliance_notice=notice_val)

        for item_field in ("key", "section", "label", "unit", "provenance", "value"):
            kwargs: dict[str, Any] = {
                "key": "k.ok",
                "section": "Sec",
                "label": "Lbl",
                "value": "USD",
                "unit": "MW",
                "provenance": "cfg",
            }
            kwargs[item_field] = bad_payload
            with pytest.raises(ValueError):
                WorkbookInputItem(**kwargs)

        for ledger_field in (
            "module_path",
            "pipeline_stage",
            "role_description",
            "excel_representation",
            "reason",
            "provenance_ref",
        ):
            l_kwargs: dict[str, Any] = {
                "module_path": "finance.cashflow_v14",
                "pipeline_stage": "cashflow",
                "role_description": "Cashflow",
                "status": "executed",
                "excel_representation": "engine_table",
                "reason": "",
                "provenance_ref": "",
            }
            l_kwargs[ledger_field] = bad_payload
            with pytest.raises(ValueError):
                ModuleLedgerEntry(**l_kwargs)


# ---------------------------------------------------------------------------
# Foundation workbook builder, reproducibility, macro-free & LibreOffice oracle
# ---------------------------------------------------------------------------


class TestBuildDfiWorkbookFoundation:
    def test_sheets_control_inputs_and_ledger_structure(self, tmp_path: Path) -> None:
        target = tmp_path / "out" / "dfi_foundation.xlsx"
        meta = _sample_metadata()
        inputs = _sample_inputs()
        ledger = _sample_ledger()

        out_path, registry = build_dfi_workbook_foundation(
            target,
            metadata=meta,
            inputs=inputs,
            ledger_entries=ledger,
        )
        assert out_path == target.resolve()
        assert out_path.exists()
        assert registry.keys() == tuple(item.key for item in inputs)

        wb = openpyxl.load_workbook(out_path, data_only=False)
        assert wb.sheetnames == ["Control_Provenance", "Inputs", "Module_Ledger"]

        # Sheet 1: Control_Provenance
        ctrl = wb["Control_Provenance"]
        assert ctrl["A1"].value == EXECUTIVE_WORKBOOK_F5_CAVEAT
        assert ctrl.freeze_panes == "A4"
        ctrl_fields = {
            ctrl.cell(row=r, column=1).value: ctrl.cell(row=r, column=2).value
            for r in range(4, 11)
        }
        assert ctrl_fields["project_name"] == meta.project_name
        assert ctrl_fields["scenario_name"] == meta.scenario_name
        assert ctrl_fields["run_mode"] == meta.run_mode
        assert ctrl_fields["config_sha256"] == meta.config_sha256
        assert ctrl_fields["engine_version"] == meta.engine_version
        assert ctrl_fields["generated_at"] == meta.generated_at
        assert ctrl_fields["formula_boundary_note"] == meta.formula_boundary_note

        # Sheet 2: Inputs
        inp_ws = wb["Inputs"]
        assert inp_ws.freeze_panes == "A2"
        assert [inp_ws.cell(row=1, column=c).value for c in range(1, 8)] == [
            "Key",
            "Section",
            "Label",
            "Value",
            "Unit",
            "Provenance",
            "Excel_Ref",
        ]
        for row_idx, item in enumerate(inputs, start=2):
            assert inp_ws.cell(row=row_idx, column=1).value == item.key
            val_cell = inp_ws.cell(row=row_idx, column=4)
            assert val_cell.value == item.value
            assert isinstance(val_cell.value, bool) is isinstance(item.value, bool)
            if isinstance(item.value, str):
                assert isinstance(val_cell.value, str)
            assert val_cell.number_format == item.number_format
            expected_ref = f"Inputs!$D${row_idx}"
            assert inp_ws.cell(row=row_idx, column=7).value == expected_ref
            assert registry.ref(item.key) == expected_ref

        # Sheet 3: Module_Ledger & live formula Status Rollup
        led_ws = wb["Module_Ledger"]
        assert led_ws.freeze_panes == "A2"
        assert [led_ws.cell(row=1, column=c).value for c in range(1, 8)] == [
            "Module",
            "Stage",
            "Role",
            "Status",
            "Excel_Representation",
            "Reason",
            "Provenance_Ref",
        ]
        for row_idx, entry in enumerate(ledger, start=2):
            assert led_ws.cell(row=row_idx, column=1).value == entry.module_path
            assert led_ws.cell(row=row_idx, column=4).value == entry.status

        assert led_ws["I1"].value == "Status"
        assert led_ws["J1"].value == "Count"
        rollup_end_row = 1 + len(CANONICAL_LEDGER_STATUSES)
        for offset, status_name in enumerate(CANONICAL_LEDGER_STATUSES, start=2):
            assert led_ws[f"I{offset}"].value == status_name
            formula = led_ws[f"J{offset}"].value
            assert isinstance(formula, str)
            assert formula == f"=COUNTIF(Module_Ledger!$D$2:$D$6, I{offset})"

        total_row = rollup_end_row + 1
        assert led_ws[f"I{total_row}"].value == "Total"
        assert (
            led_ws[f"J{total_row}"].value
            == f"=SUM(Module_Ledger!$J$2:$J${rollup_end_row})"
        )
        wb.close()

    def test_refuses_empty_inputs_duplicate_keys_and_macro_extension(
        self, tmp_path: Path
    ) -> None:
        meta = _sample_metadata()
        with pytest.raises(ValueError, match="at least one WorkbookInputItem"):
            build_dfi_workbook_foundation(
                tmp_path / "empty.xlsx",
                metadata=meta,
                inputs=[],
                ledger_entries=[],
            )

        dup_item = _sample_inputs()[0]
        with pytest.raises(ValueError, match="Duplicate CellRegistry key"):
            build_dfi_workbook_foundation(
                tmp_path / "dup.xlsx",
                metadata=meta,
                inputs=[dup_item, dup_item],
                ledger_entries=_sample_ledger(),
            )

        with pytest.raises(ValueError, match="macro-free"):
            build_dfi_workbook_foundation(
                tmp_path / "bad.xlsm",
                metadata=meta,
                inputs=_sample_inputs(),
                ledger_entries=_sample_ledger(),
            )

        for bad_name in (
            "bad.xlam",
            "bad.xlsb",
            "bad.xltm",
            "bad.xls",
            "no_suffix",
            "bad.csv",
        ):
            with pytest.raises(ValueError, match="macro-free"):
                build_dfi_workbook_foundation(
                    tmp_path / bad_name,
                    metadata=meta,
                    inputs=_sample_inputs(),
                    ledger_entries=_sample_ledger(),
                )

    def test_always_run_ooxml_xml_formula_parity_and_responsiveness_oracle(
        self, tmp_path: Path
    ) -> None:
        main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        pkg_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        cell_ref_re = re.compile(r"^([A-Z]+)([0-9]+)$")
        countif_re = re.compile(
            r"^COUNTIF\(Module_Ledger!\$D\$2:\$D\$(\d+),\s*I(\d+)\)$"
        )
        sum_re = re.compile(r"^SUM\(Module_Ledger!\$J\$2:\$J\$(\d+)\)$")

        def _parse_sheet_cells(
            zf: zipfile.ZipFile,
            sheet_xml_path: str,
            shared_strings: list[str],
        ) -> dict[str, tuple[str | None, str | None]]:
            root = ET.fromstring(zf.read(sheet_xml_path))
            cells: dict[str, tuple[str | None, str | None]] = {}
            for cell_el in root.findall(f".//{{{main_ns}}}c"):
                coord = cell_el.attrib["r"]
                f_el = cell_el.find(f"{{{main_ns}}}f")
                formula = f_el.text if f_el is not None else None
                cell_type = cell_el.attrib.get("t")
                val: str | None = None
                if cell_type == "inlineStr":
                    val = "".join(
                        t.text or ""
                        for t in cell_el.findall(f".//{{{main_ns}}}is/{{{main_ns}}}t")
                    )
                elif cell_type == "s":
                    v_el = cell_el.find(f"{{{main_ns}}}v")
                    if v_el is not None and v_el.text is not None:
                        val = shared_strings[int(v_el.text)]
                else:
                    v_el = cell_el.find(f"{{{main_ns}}}v")
                    if v_el is not None:
                        val = v_el.text
                cells[coord] = (val, formula)
            return cells

        def _verify_ooxml_workbook(
            tag: str,
            ledger: tuple[ModuleLedgerEntry, ...],
            *,
            meta: DfiWorkbookMetadata,
            inputs: tuple[WorkbookInputItem, ...],
        ) -> tuple[dict[str, int], int]:
            out_path = tmp_path / f"ooxml_{tag}.xlsx"
            build_dfi_workbook_foundation(
                out_path,
                metadata=meta,
                inputs=inputs,
                ledger_entries=ledger,
            )
            with zipfile.ZipFile(out_path) as zf:
                shared_strings: list[str] = []
                if "xl/sharedStrings.xml" in zf.namelist():
                    ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                    for si in ss_root.findall(f"{{{main_ns}}}si"):
                        shared_strings.append(
                            "".join(t.text or "" for t in si.iter(f"{{{main_ns}}}t"))
                        )

                rels_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
                rel_targets: dict[str, str] = {}
                for rel in rels_root.findall(f"{{{pkg_rel_ns}}}Relationship"):
                    target = rel.attrib["Target"].lstrip("/")
                    if not target.startswith("xl/"):
                        target = f"xl/{target}"
                    rel_targets[rel.attrib["Id"]] = target

                wb_root = ET.fromstring(zf.read("xl/workbook.xml"))
                sheet_map: list[tuple[str, str]] = []
                for sh in wb_root.findall(f".//{{{main_ns}}}sheet"):
                    rid = sh.attrib[f"{{{rel_ns}}}id"]
                    sheet_map.append((sh.attrib["name"], rel_targets[rid]))

                assert [name for name, _ in sheet_map] == [
                    "Control_Provenance",
                    "Inputs",
                    "Module_Ledger",
                ]
                sheet_paths = dict(sheet_map)

                ctrl_cells = _parse_sheet_cells(
                    zf, sheet_paths["Control_Provenance"], shared_strings
                )
                assert not any(
                    formula is not None for _, formula in ctrl_cells.values()
                ), "Unexpected <f> formula found on Control_Provenance"
                a1_text = ctrl_cells["A1"][0]
                assert a1_text is not None
                assert a1_text.startswith(DFI_WORKBOOK_F5_CAVEAT)

                inputs_cells = _parse_sheet_cells(
                    zf, sheet_paths["Inputs"], shared_strings
                )
                assert not any(
                    formula is not None for _, formula in inputs_cells.values()
                ), "Unexpected <f> formula found on Inputs sheet"
                for row_idx in range(2, 2 + len(inputs)):
                    assert inputs_cells[f"D{row_idx}"][1] is None

                ledger_cells = _parse_sheet_cells(
                    zf, sheet_paths["Module_Ledger"], shared_strings
                )

            d_statuses: dict[int, str] = {}
            for coord, (val, formula) in ledger_cells.items():
                m = cell_ref_re.fullmatch(coord)
                assert m is not None
                col_letters, row_num = m.group(1), int(m.group(2))
                if col_letters != "J":
                    err_msg = (
                        f"Unexpected <f> formula in Module_Ledger!{coord}: {formula}"
                    )
                    assert formula is None, err_msg
                if col_letters == "D" and row_num >= 2 and val is not None:
                    d_statuses[row_num] = val

            expected_end_row = max(2, 1 + len(ledger))
            evaluated_counts: dict[str, int] = {}
            rollup_rows: list[int] = []
            row_idx = 2
            while True:
                label, label_formula = ledger_cells[f"I{row_idx}"]
                _, j_formula = ledger_cells[f"J{row_idx}"]
                assert label is not None and label_formula is None
                assert j_formula is not None
                if label == "Total":
                    sum_match = sum_re.fullmatch(j_formula)
                    assert sum_match is not None, f"Unexpected SUM formula: {j_formula}"
                    assert int(sum_match.group(1)) == row_idx - 1
                    assert rollup_rows == list(range(2, row_idx))
                    evaluated_total = sum(evaluated_counts.values())
                    break

                cnt_match = countif_re.fullmatch(j_formula)
                assert cnt_match is not None, f"Unexpected COUNTIF formula: {j_formula}"
                assert int(cnt_match.group(1)) == expected_end_row
                assert int(cnt_match.group(2)) == row_idx
                evaluated_counts[label] = sum(
                    1
                    for r in range(2, expected_end_row + 1)
                    if d_statuses.get(r, "").casefold() == label.casefold()
                )
                rollup_rows.append(row_idx)
                row_idx += 1

            return evaluated_counts, evaluated_total

        base_ledger = _sample_ledger()
        base_counts, base_total = _verify_ooxml_workbook(
            "base",
            base_ledger,
            meta=_sample_metadata(),
            inputs=_sample_inputs(),
        )
        expected_base = Counter(entry.status for entry in base_ledger)
        for status_name, cnt in base_counts.items():
            assert cnt == expected_base.get(status_name, 0)
        assert base_total == len(base_ledger)

        expanded_ledger = base_ledger + (
            ModuleLedgerEntry(
                module_path="analytics.custom_plugin",
                pipeline_stage="custom",
                role_description="Custom extension module",
                status="custom_deferred",
                excel_representation="ledger_only",
                reason="deferred in wave 3",
            ),
            ModuleLedgerEntry(
                module_path="finance.irr",
                pipeline_stage="core",
                role_description="Canonical IRR/NPV helper",
                status="executed",
                excel_representation="engine_table",
            ),
            ModuleLedgerEntry(
                module_path="analytics.grid_guard",
                pipeline_stage="grid",
                role_description="Grid guard check",
                status="failed",
                excel_representation="ledger_only",
            ),
        )
        appended_meta = _sample_metadata(
            non_reliance_notice=f"{DFI_WORKBOOK_F5_CAVEAT} Scenario: stress-case."
        )
        neg_inputs = _sample_inputs() + (
            WorkbookInputItem(
                key="tax.tlcf_opening_usd",
                section="Tax-Config",
                label="Opening Tax Loss",
                value=-125000.5,
                unit="USD",
                number_format="#,##0.00",
                provenance="base-case",
            ),
        )
        exp_counts, exp_total = _verify_ooxml_workbook(
            "expanded",
            expanded_ledger,
            meta=appended_meta,
            inputs=neg_inputs,
        )
        expected_exp = Counter(entry.status for entry in expanded_ledger)
        assert exp_counts["executed"] == expected_exp["executed"] == 3
        assert exp_counts["failed"] == expected_exp["failed"] == 1
        assert exp_counts["custom_deferred"] == 1
        assert exp_total == len(expanded_ledger) == 8

        empty_counts, empty_total = _verify_ooxml_workbook(
            "empty",
            (),
            meta=_sample_metadata(),
            inputs=_sample_inputs(),
        )
        assert all(val == 0 for val in empty_counts.values())
        assert empty_total == 0

    def test_macro_free_zip_and_byte_reproducibility_oracle(
        self, tmp_path: Path
    ) -> None:
        path_a = tmp_path / "dir_a" / "first.xlsx"
        path_b = tmp_path / "dir_b" / "second.xlsx"
        meta = _sample_metadata()
        inputs = _sample_inputs()
        ledger = _sample_ledger()

        build_dfi_workbook_foundation(
            path_a, metadata=meta, inputs=inputs, ledger_entries=ledger
        )
        time.sleep(1.1)
        build_dfi_workbook_foundation(
            path_b, metadata=meta, inputs=inputs, ledger_entries=ledger
        )

        bytes_a = path_a.read_bytes()
        bytes_b = path_b.read_bytes()
        assert (
            hashlib.sha256(bytes_a).hexdigest() == hashlib.sha256(bytes_b).hexdigest()
        )

        with zipfile.ZipFile(io.BytesIO(bytes_a)) as zf:
            names = zf.namelist()
            assert not any("vbaproject" in name.lower() for name in names)
            assert not any(name.lower().endswith(".bin") for name in names)
            assert {info.date_time for info in zf.infolist()} == {(1980, 1, 1, 0, 0, 0)}

        wb = openpyxl.load_workbook(path_a)
        assert wb.properties.created == REPRODUCIBLE_EPOCH
        assert wb.properties.modified == REPRODUCIBLE_EPOCH
        wb.close()

    def test_libreoffice_formula_evaluation_and_responsiveness_oracle(
        self, tmp_path: Path
    ) -> None:
        soffice = shutil.which("soffice")
        if soffice is None:
            pytest.skip("LibreOffice `soffice` not installed on this host")

        def _evaluate_with_soffice(
            tag: str, ledger: tuple[ModuleLedgerEntry, ...]
        ) -> tuple[dict[str, int], int]:
            src = tmp_path / f"{tag}_src.xlsx"
            out_dir = tmp_path / f"{tag}_recalc"
            out_dir.mkdir(parents=True, exist_ok=True)
            build_dfi_workbook_foundation(
                src,
                metadata=_sample_metadata(),
                inputs=_sample_inputs(),
                ledger_entries=ledger,
            )
            proc = subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--convert-to",
                    "xlsx",
                    "--outdir",
                    str(out_dir),
                    str(src),
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            fail_msg = (
                f"soffice recalculation failed ({proc.returncode}): {proc.stderr}"
            )
            assert proc.returncode == 0, fail_msg
            recalc_path = out_dir / src.name
            assert recalc_path.exists()

            wb_vals = openpyxl.load_workbook(recalc_path, data_only=True)
            _assert_no_excel_errors(wb_vals)
            assert (
                wb_vals["Control_Provenance"]["A1"].value
                == EXECUTIVE_WORKBOOK_F5_CAVEAT
            )
            led_ws = wb_vals["Module_Ledger"]

            counts: dict[str, int] = {}
            row_idx = 2
            while True:
                label = led_ws[f"I{row_idx}"].value
                val = led_ws[f"J{row_idx}"].value
                if label == "Total":
                    total = int(val)
                    break
                assert isinstance(label, str)
                assert isinstance(val, (int, float))
                counts[label] = int(val)
                row_idx += 1
            wb_vals.close()
            return counts, total

        base_ledger = _sample_ledger()
        counts_base, total_base = _evaluate_with_soffice("base", base_ledger)
        expected_base = Counter(entry.status for entry in base_ledger)
        for status_name, evaluated in counts_base.items():
            assert evaluated == expected_base.get(status_name, 0)
        assert total_base == len(base_ledger)

        # Responsiveness guard (TEST-01): altering ledger counts changes evaluated COUNTIF/SUM.
        expanded_ledger = base_ledger + (
            ModuleLedgerEntry(
                module_path="analytics.custom_plugin",
                pipeline_stage="custom",
                role_description="Custom extension module",
                status="custom_deferred",
                excel_representation="ledger_only",
                reason="deferred in wave 3",
            ),
            ModuleLedgerEntry(
                module_path="finance.irr",
                pipeline_stage="core",
                role_description="Canonical IRR/NPV helper",
                status="executed",
                excel_representation="engine_table",
            ),
        )
        counts_exp, total_exp = _evaluate_with_soffice("expanded", expanded_ledger)
        expected_exp = Counter(entry.status for entry in expanded_ledger)
        assert counts_exp["executed"] == expected_exp["executed"] == 3
        assert counts_exp["custom_deferred"] == 1
        assert total_exp == len(expanded_ledger)

        # Empty ledger boundary: formulas evaluate cleanly to zero with no Excel errors.
        counts_empty, total_empty = _evaluate_with_soffice("empty_ledger", ())
        assert all(v == 0 for v in counts_empty.values())
        assert total_empty == 0


@pytest.mark.parametrize("token", _EXCEL_ERRORS[:-1])
def test_error_spelled_literals_keep_text_type_in_all_three_sheets(
    tmp_path: Path, token: str
) -> None:
    """Accepted text must survive serialization without becoming an Excel error."""
    path, _ = build_dfi_workbook_foundation(
        tmp_path / "literal_types.xlsx",
        metadata=_sample_metadata(
            project_name=token,
            scenario_name=token,
            engine_version=token,
            formula_boundary_note=token,
        ),
        inputs=(
            WorkbookInputItem(
                key="literal_input",
                section=token,
                label=token,
                value=token,
                unit=token,
                provenance=token,
            ),
        ),
        ledger_entries=(
            ModuleLedgerEntry(
                module_path="sample.module",
                pipeline_stage=token,
                role_description=token,
                status="executed",
                excel_representation=token,
                reason=token,
                provenance_ref=token,
            ),
        ),
    )
    workbook = openpyxl.load_workbook(path, data_only=False)
    expected = {
        "Control_Provenance": ("B4", "B5", "B8", "B10"),
        "Inputs": ("B2", "C2", "D2", "E2", "F2"),
        "Module_Ledger": ("B2", "C2", "E2", "F2", "G2"),
    }
    for sheet, cells in expected.items():
        for address in cells:
            cell = workbook[sheet][address]
            assert (cell.value, cell.data_type) == (token, "s")
    formulas = [
        str(cell.value)
        for row in workbook["Module_Ledger"]
        for cell in row
        if cell.data_type == "f"
    ]
    assert any(value.startswith("=COUNTIF(") for value in formulas)
    assert any(value.startswith("=SUM(") for value in formulas)
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                tree = ET.fromstring(archive.read(name))
                assert not tree.findall('.//{*}c[@t="e"]')


def test_last_supported_text_retains_distinct_input_identity(tmp_path: Path) -> None:
    """A boundary-length source must not collide with another registered input."""
    keys = ("k" * 32766 + "a", "k" * 32766 + "b")
    values = ("v" * 32766 + "a", "v" * 32766 + "b")
    provenance = ("p" * 32766 + "a", "p" * 32766 + "b")
    items = tuple(
        WorkbookInputItem(
            key=key,
            section="Source",
            label="Boundary",
            value=value,
            unit="",
            provenance=source,
        )
        for key, value, source in zip(keys, values, provenance, strict=True)
    )
    path, registry = build_dfi_workbook_foundation(
        tmp_path / "boundary.xlsx",
        metadata=_sample_metadata(),
        inputs=items,
        ledger_entries=(),
    )
    sheet = openpyxl.load_workbook(path)["Inputs"]
    for row, (key, value, source) in enumerate(
        zip(keys, values, provenance, strict=True), 2
    ):
        assert sheet.cell(row, 1).value == key
        assert sheet.cell(row, 4).value == value
        assert sheet.cell(row, 6).value == source
        assert registry.get(key).row == row


@pytest.mark.parametrize(
    "field", ("key", "section", "label", "value", "unit", "provenance")
)
def test_refuses_unrepresentable_input_text_before_emission(field: str) -> None:
    payload = _sample_inputs()[0].model_dump()
    payload[field] = "a" * 32768
    with pytest.raises(ValueError, match="32767"):
        WorkbookInputItem.model_validate(payload)


@pytest.mark.parametrize(
    "field",
    (
        "project_name",
        "scenario_name",
        "engine_version",
        "run_mode",
        "formula_boundary_note",
        "non_reliance_notice",
    ),
)
def test_refuses_unrepresentable_metadata_text_before_emission(field: str) -> None:
    text = "a" * 32768
    if field == "non_reliance_notice":
        text = DFI_WORKBOOK_F5_CAVEAT + text
    with pytest.raises(ValueError, match="32767"):
        _sample_metadata(**{field: text})


@pytest.mark.parametrize(
    "field",
    (
        "module_path",
        "pipeline_stage",
        "role_description",
        "status",
        "excel_representation",
        "reason",
        "provenance_ref",
    ),
)
def test_refuses_unrepresentable_ledger_text_before_emission(field: str) -> None:
    payload = {
        "module_path": "sample.module",
        "pipeline_stage": "stage",
        "role_description": "source metadata",
        "status": "executed",
        "excel_representation": "metadata",
        "reason": "",
        "provenance_ref": "",
    }
    payload[field] = "a" * 32768
    with pytest.raises(ValueError, match="32767"):
        ModuleLedgerEntry.model_validate(payload)


def test_empty_scalar_and_invalid_unicode_are_explicitly_refused() -> None:
    payload = _sample_inputs()[0].model_dump()
    for text in ("", chr(0xD800)):
        with pytest.raises(ValueError):
            WorkbookInputItem.model_validate({**payload, "value": text})


def test_supplementary_unicode_respects_cell_text_capacity(tmp_path: Path) -> None:
    payload = _sample_inputs()[0].model_dump()
    safe_text = "\U0001f30d" * 16383 + "x"
    item = WorkbookInputItem.model_validate({**payload, "value": safe_text})
    path, _ = build_dfi_workbook_foundation(
        tmp_path / "unicode.xlsx",
        metadata=_sample_metadata(),
        inputs=(item,),
        ledger_entries=(),
    )
    assert openpyxl.load_workbook(path)["Inputs"]["D2"].value == safe_text
    with pytest.raises(ValueError, match="32767"):
        WorkbookInputItem.model_validate({**payload, "value": "\U0001f30d" * 16384})


def test_public_builder_refuses_keys_distinguishable_only_past_capacity(
    tmp_path: Path,
) -> None:
    payload = _sample_inputs()[0].model_dump()
    bad_inputs: Any = tuple(
        {**payload, "key": "k" * 32767 + suffix} for suffix in ("a", "b")
    )
    destination = tmp_path / "must_not_exist.xlsx"
    with pytest.raises(ValueError, match="32767"):
        build_dfi_workbook_foundation(
            destination,
            metadata=_sample_metadata(),
            inputs=bad_inputs,
            ledger_entries=(),
        )
    assert not destination.exists()
