"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Plug in any analytics/sensitivity output (tornado/spider) for fast DFI/lead demo!

Run with:
    PYTHONPATH=. python3 -m streamlit run analytics/dashboard/streamlit_app.py
"""

import streamlit as st
import os
import glob
from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity import run_sensitivity_analysis, suite_to_tables
from analytics.sensitivity.viz import plot_tornado
from analytics.scenario_loader import load_scenario_config

# Page Config must be first
st.set_page_config(
    page_title="DutchBay | Sensitivity Explorer", page_icon="📊", layout="wide"
)

st.title("Sensitivity Dashboard (Tornado Explorer)")

# Scenario selection in sidebar
st.sidebar.title("Configuration")
scenario_files = sorted(glob.glob("scenarios/*.yaml"))
if not scenario_files:
    st.sidebar.error("No scenario files found in scenarios/")
    st.stop()

# Get default index for dutchbay_lendercase_2025Q4.yaml if it exists
try:
    default_index = scenario_files.index("scenarios/dutchbay_lendercase_2025Q4.yaml")
except ValueError:
    default_index = 0

config_path = st.sidebar.selectbox(
    "Select Scenario",
    scenario_files,
    index=default_index,
    format_func=os.path.basename,
    help="Select a scenario configuration file from the scenarios/ directory.",
)

st.sidebar.markdown("---")
st.sidebar.write("### Parameters")
# In a real app, these could be dynamic based on the config
params = [
    ParameterRangeConfig(
        variable_name="project.capex_usd_per_kw",
        base_value=900.0,
        low_pct=-20,
        high_pct=20,
        points=5,
        label="CAPEX ($/kW)",
    ),
    ParameterRangeConfig(
        variable_name="generation.capacity_factor_pct",
        base_value=45.0,
        low_pct=-10,
        high_pct=10,
        points=5,
        label="Capacity Factor (%)",
    ),
]

for p in params:
    st.sidebar.text(f"{p.label or p.variable_name}: {p.low_pct}% to +{p.high_pct}%")

st.sidebar.markdown("---")
run_clicked = st.sidebar.button(
    "🚀 Run Analysis", type="primary", use_container_width=True
)

if os.path.exists(config_path):
    st.subheader(f"Analyzing: {os.path.basename(config_path)}")

    if run_clicked:
        with st.spinner("Calculating sensitivity results..."):
            try:
                base_cfg = load_scenario_config(config_path)
                suite = run_sensitivity_analysis(
                    base_config=base_cfg,
                    base_config_path=config_path,
                    parameters=params,
                    metric_keys=["project_irr"],
                )
                tables = suite_to_tables(suite)
                df = tables["tornado_rows"]

                st.write("### Results")
                st.dataframe(df, use_container_width=True)

                st.write("### Tornado Chart")
                fig = plot_tornado(
                    table=df,
                    title=f"Sensitivity Analysis: {os.path.basename(config_path)}",
                )
                st.pyplot(fig)

            except Exception as e:
                st.error(f"Error running analysis: {e}")
                st.exception(e)
    else:
        st.info("Click 'Run Analysis' in the sidebar to start the computation.")
else:
    st.error(f"Config file not found: {config_path}")

st.success("Sensitivity analysis module loaded.")
