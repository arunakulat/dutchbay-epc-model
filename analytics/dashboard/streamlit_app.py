"""Interactive explorer for sensitivity results using Streamlit."""

import os
from glob import glob
import streamlit as st

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity import run_sensitivity_analysis, suite_to_tables
from analytics.sensitivity.viz import plot_tornado
from analytics.scenario_loader import load_scenario_config

st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊")
st.title("📊 DutchBay Sensitivity Explorer")

scenarios = sorted(glob("scenarios/*.yaml"))
config_path = st.selectbox("Select Scenario", scenarios, format_func=os.path.basename)

params = [
    ParameterRangeConfig("project.capex_usd_per_kw", 900.0, -20, 20, points=5),
    ParameterRangeConfig("generation.capacity_factor_pct", 45.0, -10, 10, points=5),
]

if st.button("🚀 Run Analysis", type="primary"):
    with st.spinner("Calculating..."):
        base_config = load_scenario_config(config_path)
        suite = run_sensitivity_analysis(
            base_config=base_config, base_config_path=config_path,
            parameters=params, metric_keys=["project_irr"]
        )
        df = suite_to_tables(suite)["tornado_rows"]

    st.dataframe(df, use_container_width=True)
    st.pyplot(plot_tornado(table=df, title=f"Tornado: {suite.metric}"))
else:
    st.info("Select a scenario and click 'Run Analysis' to begin.")
