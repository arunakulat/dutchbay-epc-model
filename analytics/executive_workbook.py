# analytics/executive_workbook.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ExecutiveWorkbookExporter:
    """
    High-polish, template-based Excel export using xlwings.

    This is intentionally **optional** and Mac/Excel dependent:

    - Uses a pre-formatted Excel template (`template_path`) that already
      contains:
        * A 'Summary' sheet with a table placeholder for scenario KPIs.
        * A 'Timeseries' sheet with a table placeholder for annual/cashflow data.
        * Pre-built charts driven off those tables.
    - Requires Excel + xlwings on the local machine.
    - Never used inside CI: this is for board decks and investor packs.

    Typical usage:

        exporter = ExecutiveWorkbookExporter(
            template_path="templates/Dutch_Bay_Executive_Template.xlsx",
            output_path="exports/Executive_BaseCase.xlsx",
            scenario_name="Base Case 150 MW",
        )
        exporter.create_report(summary_df, timeseries_df, to_pdf=True)
    """

    template_path: Path
    output_path: Path
    scenario_name: str
    report_title: Optional[str] = None

    def __init__(
        self,
        template_path: str | Path,
        output_path: str | Path,
        scenario_name: str,
        report_title: str | None = None,
    ) -> None:
        self.template_path = Path(template_path)
        self.output_path = Path(output_path)
        self.scenario_name = scenario_name
        self.report_title = report_title or "Dutch Bay – Executive Summary"

    # ------------------------------------------------------------------
    # Core entrypoint
    # ------------------------------------------------------------------
    def create_report(
        self,
        summary_df: pd.DataFrame,
        timeseries_df: pd.DataFrame,
        to_pdf: bool = False,
        pdf_path: str | Path | None = None,
    ) -> Path:
        """
        Generate an executive workbook (and optional PDF) from the template.

        - Writes `summary_df` into the 'Summary' sheet at anchor cell A5
          (you can adjust this to match your template).
        - Writes `timeseries_df` into the 'Timeseries' sheet at A5.
        - Updates a couple of obvious titles/placeholders:
            * Scenario name
            * Report title
        - Relies on the template's built-in charts to re-point to the new data.

        Returns the path to the created Excel file.
        """
        try:
            import xlwings as xw  # type: ignore[import]
        except Exception as exc:  # pragma: no cover - env dependent
            raise RuntimeError(
                "xlwings is required for ExecutiveWorkbookExporter. "
                "Install via `pip install xlwings` on the machine with Excel."
            ) from exc

        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found: {self.template_path}")

        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            "ExecutiveWorkbookExporter: creating report from %s -> %s",
            self.template_path,
            self.output_path,
        )

        # Run Excel in the background for speed / no UI flashing.
        with xw.App(visible=False) as app:
            # Open template
            wb = app.books.open(str(self.template_path))

            try:
                self._populate_summary_sheet(wb, summary_df)
                self._populate_timeseries_sheet(wb, timeseries_df)
                self._update_titles(wb)

                # Let Excel recalc any formulas before saving.
                try:
                    app.api.Calculation = -4135  # xlCalculationManual
                    app.api.Calculate()
                finally:
                    app.api.Calculation = -4105  # xlCalculationAutomatic

                # Save as new workbook
                wb.save(str(self.output_path))
                logger.info(
                    "ExecutiveWorkbookExporter: saved executive workbook to %s",
                    self.output_path,
                )

                # Optional PDF export
                if to_pdf:
                    pdf_target = Path(pdf_path) if pdf_path else self.output_path.with_suffix(".pdf")
                    self._export_pdf(wb, pdf_target)
                    logger.info(
                        "ExecutiveWorkbookExporter: exported PDF to %s",
                        pdf_target,
                    )

            finally:
                # Ensure workbook closed even on error.
                wb.close()

        return self.output_path

    # ------------------------------------------------------------------
    # Sheet population helpers
    # ------------------------------------------------------------------
    def _populate_summary_sheet(self, wb, summary_df: pd.DataFrame) -> None:
        """
        Write the scenario KPI table into the 'Summary' sheet.

        Assumes:
          - Sheet named 'Summary' exists.
          - Anchor cell for the table is 'A5'.
        Adjust as needed to match your template layout.
        """
        sheet_name = "Summary"
        try:
            ws = wb.sheets[sheet_name]
        except Exception as exc:
            raise RuntimeError(f"Template is missing sheet '{sheet_name}'") from exc

        anchor = "A5"
        ws.range(anchor).options(index=False).value = summary_df
        logger.debug(
            "ExecutiveWorkbookExporter: wrote %d rows to %s!%s",
            len(summary_df),
            sheet_name,
            anchor,
        )

    def _populate_timeseries_sheet(self, wb, timeseries_df: pd.DataFrame) -> None:
        """
        Write the annual / cashflow timeseries into 'Timeseries' sheet at A5.
        """
        sheet_name = "Timeseries"
        try:
            ws = wb.sheets[sheet_name]
        except Exception as exc:
            raise RuntimeError(f"Template is missing sheet '{sheet_name}'") from exc

        anchor = "A5"
        ws.range(anchor).options(index=False).value = timeseries_df
        logger.debug(
            "ExecutiveWorkbookExporter: wrote %d rows to %s!%s",
            len(timeseries_df),
            sheet_name,
            anchor,
        )

    def _update_titles(self, wb) -> None:
        """
        Update obvious title cells / placeholders for scenario + report title.

        This assumes your template uses, for example:
          - 'Summary'!B2 for the scenario name
          - 'Summary'!A2 for the report title

        Tweak these cell addresses to match your actual template.
        """
        try:
            ws = wb.sheets["Summary"]
        except Exception:
            logger.warning(
                "ExecutiveWorkbookExporter: unable to update titles; "
                "Summary sheet missing."
            )
            return

        try:
            ws.range("A2").value = self.report_title
            ws.range("B2").value = self.scenario_name
            logger.debug(
                "ExecutiveWorkbookExporter: updated title and scenario in Summary sheet"
            )
        except Exception as exc:
            logger.warning(
                "ExecutiveWorkbookExporter: failed to update titles: %s", exc
            )

    def _export_pdf(self, wb, pdf_path: Path) -> None:
        """
        Export the entire workbook to a single PDF file.

        This relies on Excel's own PDF export, so page setup is controlled
        by the template (margins, orientation, scaling, etc.).
        """
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            wb.to_pdf(str(pdf_path))
        except Exception as exc:
            logger.warning(
                "ExecutiveWorkbookExporter: PDF export failed (%s). "
                "Check that Excel supports PDF export on this machine.",
                exc,
            )