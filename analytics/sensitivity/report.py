"""
analytics/sensitivity/report.py

Auto-generates a Markdown report of tornado results for a given scenario.
"""

from analytics.sensitivity import (
    SensitivityRequest, run_tornado_sensitivity, tornado_suite_to_dataframe
)
from analytics.contracts_v14 import ParameterRangeConfig

def generate_report(config_path, params, chart_path=None):
    req = SensitivityRequest(config_path, params)
    suite = run_tornado_sensitivity(req)
    df = tornado_suite_to_dataframe(suite)
    lines = ["# Sensitivity Report", f"**Scenario:** {config_path}", ""]
    if chart_path:
        lines.append(f"![Tornado Chart]({chart_path})\n")
    lines.append("## Tornado Table\n")
    lines.append(df.to_markdown(index=False))
    return "\n".join(lines)

if __name__ == "__main__":
    params = [
        ParameterRangeConfig(variable_name="project.capex_usd_per_kw", base_value=900, low_pct=-20, high_pct=20, steps=5)
    ]
    md = generate_report("scenarios/dutchbay_lendercase_2025Q4.yaml", params, "exports/tornado_chart.png")
    with open("exports/sensitivity_report.md", "w") as f:
        f.write(md)
    print("Markdown report created at exports/sensitivity_report.md")
