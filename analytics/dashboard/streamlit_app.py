"""
dashboard/streamlit_app.py
Interactive explorer for sensitivity results using Streamlit.
"""
import streamlit as st
import glob
import os
from analytics.contracts_v14 import ParameterRangeConfig
from analytics.scenario_loader import load_scenario_config
from analytics.sensitivity import run_sensitivity_analysis, suite_to_tables

st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊")
st.title("📊 Sensitivity Explorer")

# UX Improvement: Moved inputs to sidebar and replaced text input with selectbox
with st.sidebar:
    st.header("Scenario Settings")
    scenarios = sorted(glob.glob("scenarios/*.yaml"))
    config_path = st.selectbox(
        "Select Scenario", scenarios, format_func=os.path.basename,
        help="Select a scenario configuration from the scenarios/ directory."
    )
    st.divider()
    run_analysis = st.button("Run Analysis", type="primary", use_container_width=True)

if run_analysis:
    with st.spinner("Calculating sensitivities..."):
        try:
            cfg = load_scenario_config(config_path)
            params = [
                ParameterRangeConfig("project.capex_usd_per_kw", cfg["project"]["capex_usd_per_kw"], -20, 20, points=3),
                ParameterRangeConfig("generation.capacity_factor_pct", cfg["generation"]["capacity_factor_pct"], -10, 10, points=3),
            ]
            suite = run_sensitivity_analysis(base_config=cfg, base_config_path=config_path, parameters=params, metric_keys=["project_irr"])
            df = suite_to_tables(suite)["tornado_rows"]
            st.subheader("Tornado Results")
            st.dataframe(df[["label", "base_value", "low_value", "high_value", "impact"]], use_container_width=True, hide_index=True)
            st.success("Analysis complete!")
        except Exception as e:
            st.error(f"Analysis failed: {e}")
else:
    st.info("👈 Select a scenario in the sidebar and click **'Run Analysis'**.")
