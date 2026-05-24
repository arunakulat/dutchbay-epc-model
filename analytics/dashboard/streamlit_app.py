"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
"""

import streamlit as st

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity import (
    run_sensitivity_analysis,
    suite_to_tables,
)
from analytics.scenario_loader import load_scenario_config

st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊")
st.title("📊 Sensitivity Dashboard")

config_path = st.text_input(
    "Scenario Config Path",
    "scenarios/dutchbay_lendercase_2025Q4.yaml",
    help="Path to the scenario YAML configuration file."
)

params = [
    ParameterRangeConfig(
        variable_name="project.capex_usd_per_kw",
        base_value=900.0,
        low_pct=-20,
        high_pct=20,
        label="CAPEX"
    ),
    ParameterRangeConfig(
        variable_name="generation.capacity_factor_pct",
        base_value=45.0,
        low_pct=-10,
        high_pct=10,
        label="Capacity Factor"
    ),
]

if st.button("🚀 Run Analysis", type="primary"):
    with st.spinner("Executing sensitivity analysis..."):
        base_config = load_scenario_config(config_path)
        suite = run_sensitivity_analysis(
            base_config=base_config,
            base_config_path=config_path,
            parameters=params,
            metric_keys=["project_irr"]
        )
        df = suite_to_tables(suite)["tornado_rows"]
        st.dataframe(df, use_container_width=True)
        st.success("Analysis complete!")
else:
    st.info("Click 'Run Analysis' to begin.")
