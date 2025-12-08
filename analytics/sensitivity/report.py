"""
analytics/sensitivity/report.py

Auto-generates a Markdown report of tornado results for a given scenario.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity import (
    SensitivityRequest,
    run_tornado_sensitivity,
    tornado_suite_to_dataframe,
)


def generate_report(
    config_path: str,
    params: Iterable[ParameterRangeConfig],
    chart_path: Optional[str] = None,
) -> str:
    """
    Generate a Markdown sensitivity report for a given scenario.

    Args:
        config_path: Path to the base scenario configuration file.
        params: Iterable of ParameterRangeConfig describing driver ranges.
        chart_path: Optional path to a pre-rendered tornado chart image.

    Returns:
        Markdown document as a string.
    """
    req = SensitivityRequest(config_path=config_path, parameters=list(params))
    suite = run_tornado_sensitivity(req)
    df = tornado_suite_to_dataframe(suite)

    lines: List[str] = [
        "# Sensitivity Report",
        f"**Scenario:** `{config_path}`",
        "",
    ]

    if chart_path:
        # Use relative path in markdown if possible
        rel_chart = Path(chart_path)
        lines.append(f"![Tornado Chart]({rel_chart.as_posix()})")
        lines.append("")

    lines.append("## Tornado Table")
    lines.append("")
    lines.append(df.to_markdown(index=False))

    return "\n".join(lines)


if __name__ == "__main__":
    example_params: List[ParameterRangeConfig] = [
        ParameterRangeConfig(
            variable_name="project.capex_usd_per_kw",
            base_value=900.0,
            low_pct=-20.0,
            high_pct=20.0,
            steps=5,
        )
    ]

    scenario_path = "scenarios/dutchbay_lendercase_2025Q4.yaml"
    chart_output = "exports/tornado_chart.png"
    report_output = "exports/sensitivity_report.md"

    markdown = generate_report(scenario_path, example_params, chart_output)

    Path(report_output).parent.mkdir(parents=True, exist_ok=True)
    with open(report_output, "w", encoding="utf-8") as fh:
        fh.write(markdown)

    print(f"Markdown report created at {report_output}")
