"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Plug in any analytics/sensitivity output (tornado/spider) for fast DFI/lead demo!

Run with:
    streamlit run dashboard/streamlit_app.py
"""

import os
import streamlit as st
from pathlib import Path

from analytics.contracts_v14 import ParameterRangeConfig, SensitivityRequest
from analytics.sensitivity import (
    run_sensitivity_analysis,
    suite_to_tables,
)
from analytics.sensitivity.viz import plot_tornado
from analytics.scenario_loader import load_scenario_config

# Page branding
st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊")

st.title("Sensitivity Dashboard (Tornado Explorer)")

# UX IMPROVEMENT: Scenario selection via dropdown instead of fragile text input
scenario_dir = Path("scenarios")
scenario_files = sorted([f.name for f in scenario_dir.glob("*.yaml")]) if scenario_dir.exists() else []

if not scenario_files:
    st.error("No scenarios found in scenarios/ directory.")
    st.stop()

# Default to dutchbay_lendercase if available
default_idx = scenario_files.index("dutchbay_lendercase_2025Q4.yaml") if "dutchbay_lendercase_2025Q4.yaml" in scenario_files else 0

selected_scenario = st.selectbox(
    "Base Scenario",
    scenario_files,
    index=default_idx,
    format_func=os.path.basename,
    help="Select the project configuration to analyze."
)
config_path = str(scenario_dir / selected_scenario)

params = [
    ParameterRangeConfig(
        variable_name="project.capex_usd_per_kw",
        base_value=900.0,
        low_pct=-20,
        high_pct=20,
        points=5,
    ),
    ParameterRangeConfig(
        variable_name="generation.capacity_factor_pct",
        base_value=45.0,
        low_pct=-10,
        high_pct=10,
        points=5,
    ),
]

# UX IMPROVEMENT: Explicit 'Run Analysis' button to avoid computation lag
if st.button("🚀 Run Analysis", type="primary"):
    with st.spinner(f"Evaluating {selected_scenario}..."):
        base_config = load_scenario_config(config_path)
        suite = run_sensitivity_analysis(
            base_config=base_config,
            base_config_path=config_path,
            parameters=params,
            metric_keys=["project_irr"]
        )
        df = suite_to_tables(suite)["tornado_rows"]

        st.subheader("Impact on Project IRR")
        st.pyplot(plot_tornado(table=df, title=f"Tornado: {selected_scenario}"))

        with st.expander("View Data Table"):
            st.dataframe(df, use_container_width=True)
else:
    st.info("Select a scenario and click 'Run Analysis' to see results.")
