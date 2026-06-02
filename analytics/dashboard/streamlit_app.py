"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Plug in any analytics/sensitivity output (tornado/spider) for fast DFI/lead demo!

Run with:
    streamlit run dashboard/streamlit_app.py
"""

import streamlit as st

import os
from analytics.contracts_v14 import ParameterRangeConfig
from analytics.scenario_loader import load_scenario_config
from analytics.sensitivity import run_sensitivity_analysis, suite_to_tables
from analytics.sensitivity.viz import plot_tornado

st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊")
st.title("📊 DutchBay Sensitivity Explorer")

scenario_dir = "scenarios"
scenarios = sorted([f for f in os.listdir(scenario_dir) if f.endswith(".yaml")])
default_scenario = "dutchbay_lendercase_2025Q4.yaml"
default_index = scenarios.index(default_scenario) if default_scenario in scenarios else 0
selected = st.selectbox("Select Scenario", options=scenarios, index=default_index)
config_path = os.path.join(scenario_dir, selected)

params = [
    ParameterRangeConfig("project.capex_usd_per_kw", 900.0, low_pct=-20, high_pct=20),
    ParameterRangeConfig("generation.capacity_factor_pct", 45.0, low_pct=-10, high_pct=10),
]

if st.button("Run Analysis", type="primary"):
    with st.spinner("Executing sensitivity analysis..."):
        cfg = load_scenario_config(config_path)
        suite = run_sensitivity_analysis(
            base_config=cfg, base_config_path=config_path, parameters=params, metric_keys=["project_irr"]
        )
        df = suite_to_tables(suite)["tornado_rows"]
        st.dataframe(df, use_container_width=True)
        st.pyplot(plot_tornado(table=df, title=f"Project IRR Sensitivity: {selected}"))
        st.success("Analysis complete.")
