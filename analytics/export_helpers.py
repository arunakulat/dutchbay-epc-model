"""Excel export and chart generation helpers."""

import os
from typing import Dict, List, Any, Optional

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows

matplotlib.use("Agg")


class ExcelExporter:
    """Excel workbook exporter with multi-sheet support and formatting."""

    def __init__(self, output_path: str):
        self.output_path = output_path
        self.wb = Workbook()
        # Remove default sheet if present
        if "Sheet" in self.wb.sheetnames:
            del self.wb["Sheet"]

        self.header_font = Font(bold=True, size=11, color="FFFFFF")
        self.header_fill = PatternFill(
            start_color="366092", end_color="366092", fill_type="solid"
        )
        self.header_alignment = Alignment(horizontal="center", vertical="center")
        self.thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

    def add_dataframe_sheet(
        self,
        sheet_name: str,
        df: pd.DataFrame,
        freeze_panes: str = "B2",
        format_headers: bool = True,
        auto_filter: bool = True,
        column_widths: Optional[Dict[str, float]] = None,
    ) -> None:
        ws = self.wb.create_sheet(title=sheet_name)

        for r_idx, row in enumerate(
            dataframe_to_rows(df, index=False, header=True), start=1
        ):
            for c_idx, value in enumerate(row, start=1):
                cell = ws.cell(row=r_idx, column=c_idx, value=value)
                if r_idx == 1 and format_headers:
                    cell.font = self.header_font
                    cell.fill = self.header_fill
                    cell.alignment = self.header_alignment
                    cell.border = self.thin_border
                else:
                    cell.border = self.thin_border

        if freeze_panes:
            ws.freeze_panes = freeze_panes

        if auto_filter and len(df) > 0:
            ws.auto_filter.ref = ws.dimensions

        if column_widths:
            for col_letter, width in column_widths.items():
                ws.column_dimensions[col_letter].width = width
        else:
            # Auto-fit columns (within a max width)
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if cell.value is not None:
                            max_length = max(max_length, len(str(cell.value)))
                    except Exception:
                        # Fallback: ignore cells that blow up on str()
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width

    def add_conditional_formatting(
        self,
        sheet_name: str,
        column_range: str,
        rule_type: str = "lessThan",
        threshold: float = 1.25,
        format_color: str = "F8696B",
    ) -> None:
        ws = self.wb[sheet_name]
        red_fill = PatternFill(
            start_color=format_color, end_color=format_color, fill_type="solid"
        )
        ws.conditional_formatting.add(
            column_range,
            CellIsRule(operator=rule_type, formula=[threshold], fill=red_fill),
        )

    def add_chart_image(self, sheet_name: str, image_path: str, cell: str = "B2") -> None:
        if not os.path.exists(image_path):
            print(f"Warning: Image not found: {image_path}")
            return
        ws = self.wb[sheet_name]
        img = XLImage(image_path)
        ws.add_image(img, cell)

    def save(self) -> None:
        self.wb.save(self.output_path)
        print(f"Excel workbook saved to: {self.output_path}")


class ChartGenerator:
    """Generate matplotlib charts for scenario analysis."""

    def __init__(self, output_dir: str = "exports/charts"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        plt.style.use("seaborn-v0_8-darkgrid")

    def plot_dscr_comparison(
        self,
        scenario_data: Dict[str, List[float]],
        output_file: str = "dscr_comparison.png",
        threshold: float = 1.25,
    ) -> str:
        fig, ax = plt.subplots(figsize=(12, 6))

        for scenario_name, dscr_series in scenario_data.items():
            years = list(range(1, len(dscr_series) + 1))
            ax.plot(years, dscr_series, marker="o", label=scenario_name, linewidth=2)

        if threshold is not None:
            ax.axhline(
                y=threshold,
                color="r",
                linestyle="--",
                linewidth=2,
                label=f"Threshold ({threshold})",
            )

        ax.set_xlabel("Year", fontsize=12)
        ax.set_ylabel("DSCR", fontsize=12)
        ax.set_title(
            "Debt Service Coverage Ratio by Scenario",
            fontsize=14,
            fontweight="bold",
        )
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)

        output_path = os.path.join(self.output_dir, output_file)
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        print(f"DSCR chart saved to: {output_path}")
        return output_path

    def plot_debt_waterfall(
        self,
        scenario_data: Dict[str, List[float]],
        output_file: str = "debt_waterfall.png",
    ) -> str:
        fig, ax = plt.subplots(figsize=(12, 6))

        for scenario_name, debt_series in scenario_data.items():
            years = list(range(1, len(debt_series) + 1))
            ax.plot(years, debt_series, marker="o", label=scenario_name, linewidth=2)

        ax.set_xlabel("Year", fontsize=12)
        ax.set_ylabel("Debt Outstanding (USD)", fontsize=12)
        ax.set_title(
            "Debt Outstanding by Scenario",
            fontsize=14,
            fontweight="bold",
        )
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)

        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, p: f"${x/1e6:.1f}M")
        )

        output_path = os.path.join(self.output_dir, output_file)
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        print(f"Debt waterfall chart saved to: {output_path}")
        return output_path

    def plot_kpi_comparison(
        self,
        kpi_data: pd.DataFrame,
        kpi_name: str,
        output_file: Optional[str] = None,
    ) -> str:
        if output_file is None:
            output_file = f"{kpi_name}_comparison.png"

        fig, ax = plt.subplots(figsize=(10, 6))

        scenarios = kpi_data["scenario"].tolist()
        values = kpi_data[kpi_name].tolist()

        bars = ax.bar(scenarios, values, alpha=0.8)

        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{height:,.0f}",
                ha="center",
                va="bottom",
                fontsize=10,
            )

        ax.set_xlabel("Scenario", fontsize=12)
        ax.set_ylabel(kpi_name, fontsize=12)
        ax.set_title(f"{kpi_name} by Scenario", fontsize=14, fontweight="bold")
        plt.xticks(rotation=45, ha="right")
        ax.grid(True, alpha=0.3, axis="y")

        output_path = os.path.join(self.output_dir, output_file)
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        print(f"KPI comparison chart saved to: {output_path}")
        return output_path

    def plot_npv_distribution(
        self,
        npv_values: List[float],
        output_file: str = "npv_distribution.png",
        bins: int = 30,
    ) -> str:
        fig, ax = plt.subplots(figsize=(10, 6))

        n, bins_edges, patches = ax.hist(
            npv_values,
            bins=bins,
            alpha=0.7,
            edgecolor="black",
        )

        mean_npv = sum(npv_values) / len(npv_values)
        ax.axvline(
            mean_npv,
            color="red",
            linestyle="--",
            linewidth=2,
            label=f"Mean: ${mean_npv/1e6:.1f}M",
        )

        ax.set_xlabel("NPV (USD)", fontsize=12)
        ax.set_ylabel("Frequency", fontsize=12)
        ax.set_title("NPV Distribution", fontsize=14, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")

        ax.xaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, p: f"${x/1e6:.1f}M")
        )

        output_path = os.path.join(self.output_dir, output_file)
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        print(f"NPV distribution chart saved to: {output_path}")
        return output_path