"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Refactored for usability and canonical API usage.

Run with:
    PYTHONPATH=. streamlit run analytics/dashboard/streamlit_app.py
"""

import os
import glob
import yaml
import streamlit as st

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity import (
    run_sensitivity_analysis,
    suite_to_tables,
)
from analytics.sensitivity.viz import plot_tornado

# Page configuration
st.set_page_config(
    page_title="DutchBay | Sensitivity Dashboard",
    page_icon="🎨",
    layout="wide",
)

st.title("🎨 Sensitivity Dashboard")
st.markdown("---")

# Sidebar for Configuration
st.sidebar.header("Configuration")

# 1. Scenario Selection
scenario_files = sorted(glob.glob("scenarios/*.yaml"))
if not scenario_files:
    st.error("No scenario files found in 'scenarios/' directory.")
    st.stop()

selected_scenario = st.sidebar.selectbox(
    "Select Scenario",
    scenario_files,
    index=scenario_files.index("scenarios/dutchbay_lendercase_2025Q4.yaml") if "scenarios/dutchbay_lendercase_2025Q4.yaml" in scenario_files else 0,
    format_func=os.path.basename,
    help="Choose the base financial scenario to analyze."
)

# 2. Parameters Configuration
st.sidebar.subheader("Sensitivity Parameters")

# Default parameters
params = [
    ParameterRangeConfig(
        variable_name="project.capex_usd_per_kw",
        base_value=900.0,
        low_pct=-20,
        high_pct=20,
        points=5,
        label="CAPEX ($/kW)"
    ),
    ParameterRangeConfig(
        variable_name="generation.capacity_factor_pct",
        base_value=45.0,
        low_pct=-10,
        high_pct=10,
        points=5,
        label="Capacity Factor (%)"
    ),
]

for p in params:
    with st.sidebar.expander(f"📌 {p.label or p.variable_name}", expanded=False):
        st.write(f"**Variable:** `{p.variable_name}`")
        st.write(f"**Base Value:** {p.base_value}")
        st.write(f"**Sensitivity Range:** {p.low_pct}% to {p.high_pct}%")
        st.write(f"**Steps:** {p.points}")

st.sidebar.markdown("---")
with st.sidebar.expander("ℹ️ About This Dashboard"):
    st.write("""
    This dashboard allows you to explore how key financial metrics
    respond to changes in input parameters.

    It uses the DutchBay v14 Analytics Engine to run multiple
    deterministic scenario evaluations in real-time.
    """)

# Main Execution
try:
    with open(selected_scenario, "r") as f:
        base_config = yaml.safe_load(f)
except Exception as e:
    st.error(f"Failed to load scenario: {e}")
    st.stop()

st.subheader(f"📊 Analysis Results: {os.path.basename(selected_scenario)}")

if st.button("🚀 Run Sensitivity Analysis", type="primary", use_container_width=True):
    with st.spinner("Executing sensitivity trials..."):
        try:
            # Canonical API usage
            suite = run_sensitivity_analysis(
                base_config=base_config,
                base_config_path=selected_scenario,
                parameters=params,
                metric_keys=["project_irr", "equity_irr"]
            )

            tables = suite_to_tables(suite)
            df_tornado = tables.get("tornado_rows")

            # Layout: Results
            col1, col2 = st.columns([1, 1])

            with col1:
                st.write("### Tornado Plot")
                if df_tornado is not None and not df_tornado.empty:
                    fig = plot_tornado(table=df_tornado, title=f"Sensitivity: {suite.metric}")
                    st.pyplot(fig)
                else:
                    st.warning("No data available for tornado plot.")

            with col2:
                st.write("### Data Table")
                if df_tornado is not None:
                    st.dataframe(df_tornado, use_container_width=True)
                else:
                    st.warning("No data table available.")

            st.success("Analysis complete!")

        except Exception as e:
            st.error(f"Error during analysis: {e}")
            st.exception(e)
else:
    st.info("Click 'Run Sensitivity Analysis' in the sidebar or above to start.")
