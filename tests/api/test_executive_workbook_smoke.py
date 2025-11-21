#!/usr/bin/env python3
"""
Smoke tests for ExecutiveWorkbookExporter.

Goals:
- Exercise the happy path of create_report() without requiring real Excel.
- Stub xlwings so that no external dependencies or UI are needed.
"""

from pathlib import Path
import sys
import types

import pandas as pd
import pytest

from analytics.executive_workbook import ExecutiveWorkbookExporter


# ---------------------------------------------------------------------------
# Lightweight xlwings stub for tests
# ---------------------------------------------------------------------------


class _FakeRange:
    def __init__(self):
        self._value = None

    def options(self, **_kwargs):
        # ScenarioAnalytics/exporter only chains .options(...).value = df
        return self

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, _val):
        # We don't need to store the actual value for these tests.
        self._value = _val


class _FakeSheet:
    def __init__(self):
        self._cells = {}

    def range(self, addr: str) -> _FakeRange:
        # Return a stable _FakeRange per address if we ever care later.
        if addr not in self._cells:
            self._cells[addr] = _FakeRange()
        return self._cells[addr]


class _FakeWorkbook:
    def __init__(self):
        # Provide the two sheets expected by ExecutiveWorkbookExporter.
        self.sheets = {
            "Summary": _FakeSheet(),
            "Timeseries": _FakeSheet(),
        }

    def save(self, path: str) -> None:
        # Emulate Excel saving a file to disk so callers can rely on it existing.
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_bytes(b"")

    def close(self) -> None:
        # Nothing special to do here; just keep the API surface.
        pass

    def to_pdf(self, path: str) -> None:
        # Emulate Excel's PDF export by touching the file path.
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_bytes(b"")


class _FakeBooks:
    def open(self, _path: str) -> _FakeWorkbook:
        # Always return a fresh fake workbook instance.
        return _FakeWorkbook()


class _FakeApi:
    def __init__(self):
        # Calculation mode flag; value is irrelevant for tests.
        self.Calculation = -4105  # xlCalculationAutomatic (placeholder)

    def Calculate(self):
        # No-op; we don't simulate Excel calc.
        return None


class _FakeApp:
    """Context-manager compatible stub for xlwings.App."""

    def __init__(self, visible: bool = False):
        self.visible = visible
        self.books = _FakeBooks()
        self.api = _FakeApi()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        # Nothing special to clean up.
        return False


def _install_fake_xlwings(monkeypatch):
    """Install a fake xlwings module into sys.modules for the duration of the test."""
    fake_mod = types.SimpleNamespace(App=_FakeApp)
    monkeypatch.setitem(sys.modules, "xlwings", fake_mod)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_executive_workbook_create_report_smoke(monkeypatch, tmp_path):
    """
    Happy-path smoke test for ExecutiveWorkbookExporter.create_report().

    - Uses a fake xlwings implementation (no real Excel required).
    - Uses a minimal template file and small DataFrames.
    - Requests both XLSX and PDF outputs.
    """
    _install_fake_xlwings(monkeypatch)

    # Minimal but non-empty DataFrames that look like analytics outputs.
    summary_df = pd.DataFrame(
        [
            {
                "scenario_name": "example_a",
                "npv": 123.0,
                "project_irr": 0.12,
            }
        ]
    )
    timeseries_df = pd.DataFrame(
        [
            {
                "scenario_name": "example_a",
                "year": 1,
                "cfads_usd": 100.0,
                "dscr": 1.3,
            }
        ]
    )

    # Create a dummy template file – existence is all the exporter checks.
    template_path = tmp_path / "Dummy_Template.xlsx"
    template_path.write_bytes(b"")

    output_path = tmp_path / "Executive_Report.xlsx"

    exporter = ExecutiveWorkbookExporter(
        template_path=template_path,
        output_path=output_path,
        scenario_name="Example A 150 MW",
    )

    # Act
    result_path = exporter.create_report(
        summary_df=summary_df,
        timeseries_df=timeseries_df,
        to_pdf=True,
    )

    # Assert basic invariants
    assert result_path == output_path
    # Our fake workbook.save() should have created the XLSX file.
    assert output_path.exists()

    # PDF should have been written next to the workbook (default behaviour).
    pdf_path = output_path.with_suffix(".pdf")
    assert pdf_path.exists()
