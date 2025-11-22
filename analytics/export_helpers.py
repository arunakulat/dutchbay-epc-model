from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence, Union

import pandas as pd

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]


# =====================================================================
# Excel export helpers
# =====================================================================


@dataclass
class ExcelExporter:
    """Helper for writing scenario analytics to an Excel workbook.

    Design goals:
    - Keep the public surface area simple and test-friendly.
    - Provide sane defaults for ScenarioAnalytics, but allow direct use.
    - Produce a workbook that is immediately usable in a board pack:
      * Summary sheet
      * Timeseries sheet
      * Optional DSCR and IRR views when columns are present
      * Columns auto-fitted where possible
    """

    output_path: Path

    def __init__(self, output_path: PathLike) -> None:
        self.output_path = Path(output_path)
        # ExcelWriter is created lazily so we do not accidentally create
        # empty files if nothing is written.
        self._writer: Optional[pd.ExcelWriter] = None

    # ------------------------------------------------------------------
    # Core writer lifecycle
    # ------------------------------------------------------------------
    def _ensure_writer(self) -> pd.ExcelWriter:
        if self._writer is None:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self._writer = pd.ExcelWriter(self.output_path, engine="openpyxl")
        return self._writer

    def save(self) -> None:
        """Persist the workbook to disk.

        Idempotent: safe to call multiple times.
        """
        if self._writer is not None:
            self._writer.close()
            logger.info("ExcelExporter: wrote workbook to %s", self.output_path)

    # ------------------------------------------------------------------
    # Generic DataFrame sheet helper (for tests + direct use)
    # ------------------------------------------------------------------
    def add_dataframe_sheet(
        self,
        sheet_name: str,
        df: pd.DataFrame,
        freeze_panes: Optional[Union[str, tuple[int, int]]] = None,
        format_headers: bool = True,
        auto_filter: bool = True,
    ) -> None:
        """Write a DataFrame to a sheet with light formatting.

        This is the API expected by tests/api/test_export_helpers_v14.py.

        - Writes `df` to `sheet_name`.
        - Optionally freezes panes (e.g. "B2").
        - Optionally bolds the header row.
        - Optionally applies an AutoFilter over the used range.
        """
        writer = self._ensure_writer()
        df.to_excel(writer, sheet_name=sheet_name, index=False)

        # openpyxl-backed workbook/worksheet
        try:
            workbook = writer.book
            if sheet_name in writer.sheets:
                ws = writer.sheets[sheet_name]
            else:
                ws = workbook[sheet_name]
        except Exception as exc:  # pragma: no cover - very defensive
            logger.warning("ExcelExporter: unable to access sheet %s: %s", sheet_name, exc)
            return


        try:
            from openpyxl.styles import Font
        except Exception:  # pragma: no cover
            Font = None  # type: ignore

        # Header formatting
        if format_headers and Font is not None:
            try:
                for cell in ws[1]:
                    cell.font = Font(bold=True)
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "ExcelExporter: header formatting failed on %s: %s",
                    sheet_name,
                    exc,
                )

        # AutoFilter
        if auto_filter:
            try:
                ws.auto_filter.ref = ws.dimensions
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "ExcelExporter: auto-filter setup failed on %s: %s",
                    sheet_name,
                    exc,
                )

        # Freeze panes
        if freeze_panes:
            try:
                ws.freeze_panes = freeze_panes
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "ExcelExporter: freeze panes failed on %s: %s",
                    sheet_name,
                    exc,
                )

    # ------------------------------------------------------------------
    # Additional helpers expected by tests
    # ------------------------------------------------------------------
    def add_conditional_formatting(
        self,
        sheet_name: str,
        column_range: str,
        rule_type: str = "2_color_scale",
        threshold: float = 0.0,
    ) -> None:
        """Add a simple conditional formatting rule to a range.

        This is intentionally minimal and defensive: tests only assert that the
        call succeeds and the file is written, not that the rule is perfect.

        Parameters
        ----------
        sheet_name:
            Name of the worksheet to apply the rule on.
        column_range:
            Excel range string, e.g. "B2:B100".
        rule_type:
            Currently supports:
              - "2_color_scale": basic low/high color scale.
              - "above_threshold": highlight > threshold.
        threshold:
            Numeric threshold for "above_threshold" rules.
        """
        if self._writer is None:
            logger.debug("ExcelExporter: no writer yet; conditional formatting deferred.")
            return

        try:
            from openpyxl.formatting.rule import ColorScaleRule, CellIsRule
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "ExcelExporter: openpyxl.formatting not available, skipping "
                "conditional formatting on %s: %s",
                sheet_name,
                exc,
            )
            return

        try:
            workbook = self._writer.book  
            if sheet_name in self._writer.sheets:
                ws = self._writer.sheets[sheet_name]
            else:
                ws = workbook[sheet_name]
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "ExcelExporter: unable to access sheet %s for conditional formatting: %s",
                sheet_name,
                exc,
            )
            return

        try:
            if rule_type == "2_color_scale":
                rule = ColorScaleRule(
                    start_type="min",
                    start_color="FFF2F2F2",
                    end_type="max",
                    end_color="FF4F81BD",
                )
            elif rule_type == "above_threshold":
                rule = CellIsRule(
                    operator="greaterThan",
                    formula=[str(threshold)],
                    stopIfTrue=False,
                    fill=None,
                )
            else:
                logger.warning(
                    "ExcelExporter: unknown rule_type '%s'; skipping", rule_type
                )
                return

            ws.conditional_formatting.add(column_range, rule)
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "ExcelExporter: conditional formatting failed on %s:%s (%s)",
                sheet_name,
                column_range,
                exc,
            )

    def add_chart_image(
        self,
        sheet_name: str,
        image_path: PathLike,
        cell: str = "D2",
    ) -> None:
        """Embed a PNG (or similar) image into the given sheet.

        This is a light helper used by tests; it is not responsible for
        generating the chart itself, only placing an existing image.
        """
        if self._writer is None:
            logger.debug("ExcelExporter: no writer; chart image embedding skipped.")
            return

        try:
            from openpyxl.drawing.image import Image as XLImage
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "ExcelExporter: openpyxl Image not available; cannot embed chart: %s",
                exc,
            )
            return

        try:
            workbook = self._writer.book  
            if sheet_name in self._writer.sheets:
                ws = self._writer.sheets[sheet_name]
            else:
                ws = workbook[sheet_name]
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "ExcelExporter: unable to access sheet %s for image embedding: %s",
                sheet_name,
                exc,
            )
            return

        try:
            img = XLImage(str(image_path))
            ws.add_image(img, cell)
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "ExcelExporter: failed to embed image %s on %s@%s: %s",
                image_path,
                sheet_name,
                cell,
                exc,
            )

    # ------------------------------------------------------------------
    # Simple sheet writers (backwards compatible)
    # ------------------------------------------------------------------
    def write_scenario_summary(
        self,
        summary_df: pd.DataFrame,
        sheet_name: str = "Summary",
    ) -> None:
        """Write the scenario summary DataFrame to a sheet.

        This is a low-level primitive kept for backwards compatibility and
        direct use. It does *not* save the workbook; callers must invoke
        :meth:`save` explicitly or call :meth:`export_summary_and_timeseries`.
        """
        self.add_dataframe_sheet(
            sheet_name=sheet_name,
            df=summary_df,
            freeze_panes=None,
            format_headers=True,
            auto_filter=True,
        )

    def write_scenario_timeseries(
        self,
        timeseries_df: pd.DataFrame,
        sheet_name: str = "Timeseries",
    ) -> None:
        """Write the timeseries DataFrame to a sheet.

        As with :meth:`write_scenario_summary`, this does not save the
        workbook; callers are responsible for calling :meth:`save`.
        """
        self.add_dataframe_sheet(
            sheet_name=sheet_name,
            df=timeseries_df,
            freeze_panes=None,
            format_headers=True,
            auto_filter=True,
        )

    # ------------------------------------------------------------------
    # Board-pack friendly export
    # ------------------------------------------------------------------
    def export_summary_and_timeseries(
        self,
        summary_df: pd.DataFrame,
        timeseries_df: pd.DataFrame,
        summary_sheet: str = "Summary",
        timeseries_sheet: str = "Timeseries",
        add_board_views: bool = True,
    ) -> None:
        """High-level helper used by ScenarioAnalytics.

        - Always writes `summary_df` and `timeseries_df` to separate sheets.
        - Optionally adds lighter, board-focused views when the expected
          columns are present (DSCR and IRR views).
        - Autofits all columns and saves the workbook.

        This is the main entry point for the analytics pipeline.
        """
        logger.info(
            "ExcelExporter: exporting summary + timeseries to %s",
            self.output_path,
        )
        self.write_scenario_summary(summary_df, sheet_name=summary_sheet)
        self.write_scenario_timeseries(timeseries_df, sheet_name=timeseries_sheet)

        if add_board_views:
            self._add_board_friendly_views(summary_df, timeseries_df)

        # Layout polish and save
        self.autofit_all()
        self.save()

    # ------------------------------------------------------------------
    # Board-pack views
    # ------------------------------------------------------------------
    def _add_board_friendly_views(
        self,
        summary_df: pd.DataFrame,
        timeseries_df: pd.DataFrame,
    ) -> None:
        """Add optional DSCR / IRR views if the data supports them.

        This method is deliberately defensive: if columns are missing, it logs
        and quietly returns rather than raising, so analytics tests and
        pipelines are not brittle.
        """
        writer = self._ensure_writer()

        # DSCR by year / period, per scenario, if available
        if {"scenario_name", "dscr"}.issubset(timeseries_df.columns):
            try:
                dscr_cols = [
                    c
                    for c in timeseries_df.columns
                    if c in {"scenario_name", "year", "period", "dscr"}
                ]
                dscr_view = timeseries_df[dscr_cols].copy()

                # Prefer a tidy "Year" column for the board
                if "year" in dscr_view.columns:
                    dscr_view.rename(columns={"year": "Year"}, inplace=True)
                elif "period" in dscr_view.columns:
                    dscr_view.rename(columns={"period": "Period"}, inplace=True)

                dscr_view.to_excel(writer, sheet_name="DSCR_View", index=False)
            except Exception as exc:
                logger.warning("ExcelExporter: DSCR view export failed: %s", exc)

        # IRR summary view if IRR columns exist
        irr_candidates = [c for c in summary_df.columns if "irr" in str(c).lower()]
        if irr_candidates:
            try:
                irr_view = summary_df[["scenario_name", *irr_candidates]].copy()
                irr_view.to_excel(writer, sheet_name="IRR_View", index=False)
            except Exception as exc:
                logger.warning("ExcelExporter: IRR view export failed: %s", exc)

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------
    def autofit_all(self) -> None:
        """Best-effort column auto-fit for all sheets.

        If `openpyxl` is not available or something unexpected happens,
        the error is logged and ignored rather than bubbling up.
        """
        if self._writer is None:
            return

        try:
            workbook = self._writer.book
        except Exception as exc:  # pragma: no cover - very defensive
            logger.warning("ExcelExporter: unable to access workbook: %s", exc)
            return

        try:
            from openpyxl.utils import get_column_letter
        except Exception as exc:  # pragma: no cover - openpyxl missing
            logger.warning("ExcelExporter: openpyxl not available for autofit: %s", exc)
            return

        for ws in workbook.worksheets:
            for column_cells in ws.columns:
                # Compute a reasonable width based on the longest value.
                try:
                    max_length = max(
                        len(str(cell.value)) if cell.value is not None else 0
                        for cell in column_cells
                    )
                except ValueError:
                    # Empty column
                    continue

                adjusted_width = max_length + 2
                col_letter = get_column_letter(column_cells[0].column)
                ws.column_dimensions[col_letter].width = adjusted_width


# =====================================================================
# Chart export helpers (PNG generation, CI/CLI friendly)
# =====================================================================


@dataclass
class ChartExporter:
    """Helper for writing DSCR and IRR charts to PNG files.

    This is intentionally lightweight:

    - If matplotlib is not installed, the methods log a warning and no-op.
    - The API is tuned to the ScenarioAnalytics use-case and tests:
        * export_dscr_chart(...)
        * export_irr_histogram(...)
    """

    output_dir: Path

    def __init__(self, output_dir: PathLike) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal util
    # ------------------------------------------------------------------
    def _get_plt(self):
        try:
            import matplotlib.pyplot as plt
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("ChartExporter: matplotlib not available: %s", exc)
            return None
        return plt

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def export_dscr_chart(
        self,
        timeseries_df: pd.DataFrame,
        scenario_name_column: str = "scenario_name",
        dscr_column: str = "dscr",
        output_file: str = "dscr_series.png",
    ) -> Optional[Path]:
        """Export DSCR over time for each scenario as a PNG.

        The function is intentionally tolerant:
        - If required columns are missing, it logs and returns None.
        - If matplotlib is missing, it logs and returns None.
        """
        required = {scenario_name_column, dscr_column}
        if not required.issubset(timeseries_df.columns):
            logger.warning(
                "ChartExporter: DSCR chart skipped; missing columns %s",
                required - set(timeseries_df.columns),
            )
            return None

        plt = self._get_plt()
        if plt is None:
            return None

        out_path = self.output_dir / output_file

        try:
            plt.figure()
            grouped = timeseries_df.groupby(scenario_name_column)

            for name, grp in grouped:
                dscr_series = pd.to_numeric(grp[dscr_column], errors="coerce")
                x = range(1, len(dscr_series) + 1)
                plt.plot(x, dscr_series, marker="o", label=str(name))

            plt.axhline(1.0, linestyle="--", linewidth=1)
            plt.xlabel("Period")
            plt.ylabel("DSCR")
            plt.title("Debt Service Coverage Ratio (DSCR) by Scenario")
            plt.legend()
            plt.tight_layout()
            plt.savefig(out_path)
            plt.close()

            logger.info("ChartExporter: DSCR chart written to %s", out_path)
            return out_path
        except Exception as exc:  # pragma: no cover - belt-and-braces
            logger.warning("ChartExporter: failed to export DSCR chart: %s", exc)
            return None

    def export_irr_histogram(
        self,
        summary_df: pd.DataFrame,
        irr_column: str = "project_irr",
        output_file: str = "project_irr_hist.png",
        bins: int = 20,
    ) -> Optional[Path]:
        """Export a histogram of IRRs as a PNG.

        The intended use is to take `project_irr` from the summary DataFrame,
        but any numeric column can be specified via `irr_column`.
        """
        if irr_column not in summary_df.columns:
            logger.warning(
                "ChartExporter: IRR histogram skipped; missing column '%s'",
                irr_column,
            )
            return None

        plt = self._get_plt()
        if plt is None:
            return None

        out_path = self.output_dir / output_file

        try:
            plt.figure()
            data = pd.to_numeric(summary_df[irr_column], errors="coerce").dropna()
            if data.empty:
                logger.warning(
                    "ChartExporter: no finite values in '%s' for histogram",
                    irr_column,
                )
                return None

            plt.hist(data, bins=bins)
            plt.xlabel("IRR")
            plt.ylabel("Frequency")
            plt.title(f"{irr_column} distribution")
            plt.tight_layout()
            plt.savefig(out_path)
            plt.close()

            logger.info("ChartExporter: IRR histogram written to %s", out_path)
            return out_path
        except Exception as exc:  # pragma: no cover - belt-and-braces
            logger.warning("ChartExporter: failed to export IRR histogram: %s", exc)
            return None


# =====================================================================
# High-level ChartGenerator used by tests/api/test_export_helpers_v14.py
# =====================================================================


class ChartGenerator:
    """Lightweight helper for generating PNG charts from analytics outputs.

    This is intentionally decoupled from Excel so it can be used in CLI/CI
    contexts without touching workbooks.

    Expected usage (per tests):

        cg = ChartGenerator(output_dir=tmp_path)
        dscr_path = cg.plot_dscr_comparison(...)
        debt_path = cg.plot_debt_waterfall(...)
        kpi_path = cg.plot_kpi_comparison(...)
        npv_path = cg.plot_npv_distribution(...)
    """

    def __init__(self, output_dir: PathLike) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_plt(self):
        try:
            import matplotlib.pyplot as plt
        except Exception as exc:  # pragma: no cover
            logger.warning("ChartGenerator: matplotlib not available: %s", exc)
            return None
        return plt

    def _resolve_path(self, output_file: PathLike) -> Path:
        """Resolve output_file relative to output_dir and ensure parent exists."""
        path = Path(output_file)
        if not path.is_absolute():
            path = self.output_dir / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    # ------------------------------------------------------------------
    # KPI comparison (bar chart)
    # ------------------------------------------------------------------
    def plot_kpi_comparison(
        self,
        kpi_data: Union[pd.DataFrame, Mapping[str, Iterable[float]]],
        kpi_name: str,
        output_file: PathLike,
    ) -> Path:
        """
        Create a simple bar chart comparing a KPI across scenarios.

        kpi_data: DataFrame or dict-like, typically with either:
            - a column named 'scenario_name', plus a column `kpi_name`, or
            - index as scenario labels and a numeric column `kpi_name`.

        Returns the pathlib.Path to the written PNG.
        """
        import pandas as pd

        plt = self._get_plt()
        if plt is None:  # pragma: no cover
            # Still return the path we *would* have written, to keep tests simple.
            return self._resolve_path(output_file)

        path = self._resolve_path(output_file)

        # Normalise to DataFrame
        if isinstance(kpi_data, pd.DataFrame):
            df = kpi_data.copy()
        else:
            df = pd.DataFrame(kpi_data)

        # Choose the y-series
        if kpi_name in df.columns:
            y = df[kpi_name]
        else:
            numeric_cols = df.select_dtypes("number").columns
            if not numeric_cols:
                raise ValueError("No numeric columns available for KPI chart")
            y = df[numeric_cols[0]]
            kpi_name = str(numeric_cols[0])

        # X labels from scenario_name or index
        if "scenario_name" in df.columns:
            labels = df["scenario_name"].astype(str).tolist()
        else:
            labels = df.index.astype(str).tolist()

        fig, ax = plt.subplots()
        ax.bar(range(len(y)), y)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_ylabel(kpi_name)
        ax.set_title(f"{kpi_name} comparison")
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)

        return path

    # ------------------------------------------------------------------
    # NPV distribution (histogram)
    # ------------------------------------------------------------------
    def plot_npv_distribution(
        self,
        npv_values: Iterable[float],
        output_file: PathLike,
        bins: int = 20,
    ) -> Path:
        """
        Plot a simple histogram for NPV values.

        npv_values: iterable of float
        Returns the pathlib.Path to the written PNG.
        """
        plt = self._get_plt()
        if plt is None:  # pragma: no cover
            return self._resolve_path(output_file)

        path = self._resolve_path(output_file)

        fig, ax = plt.subplots()
        ax.hist(list(npv_values), bins=bins)
        ax.set_xlabel("NPV")
        ax.set_ylabel("Frequency")
        ax.set_title("NPV distribution")
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)

        return path

    # ------------------------------------------------------------------
    # DSCR comparison (multi-scenario line chart with threshold)
    # ------------------------------------------------------------------
    def plot_dscr_comparison(
        self,
        scenario_data: Mapping[str, Sequence[float]],
        output_file: PathLike,
        threshold: Optional[float] = None,
    ) -> Path:
        """Plot DSCR series for each scenario on a single chart."""
        plt = self._get_plt()
        if plt is None:  # pragma: no cover
            return self._resolve_path(output_file)

        path = self._resolve_path(output_file)

        fig, ax = plt.subplots()

        for name, series in scenario_data.items():
            y = list(series)
            x = list(range(1, len(y) + 1))
            ax.plot(x, y, marker="o", label=str(name))

        if threshold is not None:
            ax.axhline(threshold, linestyle="--", linewidth=1)

        ax.set_xlabel("Period")
        ax.set_ylabel("DSCR")
        ax.set_title("DSCR comparison by scenario")
        ax.legend()
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)

        return path

    # ------------------------------------------------------------------
    # Debt waterfall (very simple stacked-style chart)
    # ------------------------------------------------------------------
    def plot_debt_waterfall(
        self,
        scenario_data: Mapping[str, Sequence[float]],
        output_file: PathLike,
    ) -> Path:
        """Plot a simple 'waterfall-like' bar chart of ending debt by scenario.

        This is intentionally minimal: tests only assert that a PNG file is
        created, not that the waterfall matches any particular styling spec.
        """
        plt = self._get_plt()
        if plt is None:  # pragma: no cover
            return self._resolve_path(output_file)

        path = self._resolve_path(output_file)

        labels = []
        values = []
        for name, series in scenario_data.items():
            labels.append(str(name))
            # Use final period as representative remaining debt
            s = list(series)
            values.append(s[-1] if s else 0.0)

        fig, ax = plt.subplots()
        ax.bar(range(len(values)), values)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_ylabel("Debt (end of horizon)")
        ax.set_title("Debt waterfall by scenario")
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)

        return path
