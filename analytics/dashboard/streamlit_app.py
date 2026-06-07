"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
"""

import streamlit as st
import os
from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity import run_sensitivity_analysis, suite_to_tables
from analytics.sensitivity.viz import plot_tornado
from analytics.scenario_loader import load_scenario_config

st.set_page_config(page_title="DutchBay Sensitivity", layout="wide")
st.title("🎨 Sensitivity Explorer")

with st.sidebar:
    st.header("Settings")
    config_path = st.text_input(
        "Scenario Path",
        "scenarios/dutchbay_lendercase_2025Q4.yaml",
        help="Path to the scenario YAML file in the repository."
    )

    st.info("💡 Pro-tip: Adjust parameters in the code for deeper analysis.")
    params = [
        ParameterRangeConfig(
            variable_name="project.capex_usd_per_kw",
            base_value=900.0, low_pct=-20, high_pct=20, points=3
        ),
        ParameterRangeConfig(
            variable_name="generation.capacity_factor_pct",
            base_value=45.0, low_pct=-10, high_pct=10, points=3
        ),
    ]

if st.button("🚀 Run Analysis", type="primary"):
    with st.spinner("Calculating sensitivities..."):
        try:
            config = load_scenario_config(config_path)
            suite = run_sensitivity_analysis(
                base_config=config, base_config_path=config_path,
                parameters=params, metric_keys=["project_irr"]
            )
            df = suite_to_tables(suite)["tornado_rows"]

            c1, c2 = st.columns(2)
            c1.subheader("Data View")
            c1.dataframe(df, use_container_width=True)

            c2.subheader("Visual Impact")
            c2.pyplot(plot_tornado(table=df, title="Project IRR Sensitivity"))
            st.success("Analysis complete!")
        except Exception as e:
            st.error(f"Error: {e}")
else:
    st.info("Click 'Run Analysis' to begin.")
