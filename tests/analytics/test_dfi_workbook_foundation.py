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
import shutil
import subprocess
import time
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

import openpyxl
import pytest
from pydantic import ValidationError

from analytics.dfi_workbook import (
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

        max_len = CellRef(sheet="S" * 31, column="A", row=1)
        assert len(max_len.sheet) == 31

    @pytest.mark.parametrize(
        "bad_sheet",
        [
            "",
            "   ",
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
        with pytest.raises(ValueError):
            reg.register("   ", sheet="Inputs", column="D", row=2)
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
        assert meta.non_reliance_notice == EXECUTIVE_WORKBOOK_F5_CAVEAT
        assert "HOLD (F-5, #1110, v15.6.1)" in meta.non_reliance_notice
        assert "Option B" in meta.formula_boundary_note

        for bad_notice in ("", "   "):
            with pytest.raises(ValueError, match="non_reliance_notice"):
                _sample_metadata(non_reliance_notice=bad_notice)

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
        "bad_val", [float("nan"), float("inf"), float("-inf"), None, [1]]
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
