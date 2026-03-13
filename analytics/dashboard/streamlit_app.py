"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Plug in any analytics/sensitivity output (tornado/spider) for fast DFI/lead demo!

Run with:
    streamlit run dashboard/streamlit_app.py
"""

import streamlit as st

st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊", layout="wide")

BACKEND_OK = False
try:
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity import run_sensitivity_analysis, suite_to_tables
    from analytics.scenario_loader import load_scenario_config
    BACKEND_OK = True
except ImportError as e:
    st.error(f"Model Initialization Failed: {e}")

st.title("📊 DutchBay Sensitivity Explorer")

with st.sidebar:
    st.header("Scenario Settings")
    config_path = st.text_input(
        "Scenario Config Path 📁",
        "scenarios/dutchbay_lendercase_2025Q4.yaml",
        help="Path to the Hydra YAML scenario configuration."
    )
if not BACKEND_OK:
    st.warning("⚠️ Safe Mode: Dashboard is running without backend integration.")
    st.info("Check `analytics/contracts_v14.py` for syntax errors or missing dependencies.")
    st.stop()

params = [
    ParameterRangeConfig(variable_name="project.capex_usd_per_kw", base_value=900.0, low_pct=-20, high_pct=20),
    ParameterRangeConfig(variable_name="generation.capacity_factor_pct", base_value=45.0, low_pct=-10, high_pct=10),
]

if st.button("🚀 Run Analysis", type="primary"):
    with st.spinner("Orchestrating sensitivity trials..."):
        try:
            base_cfg = load_scenario_config(config_path)
            suite = run_sensitivity_analysis(base_config=base_cfg, parameters=params, metric_keys=["project_irr"])
            tables = suite_to_tables(suite)
            st.subheader("Tornado Impact Table")
            st.table(tables[0])
            st.success("Analysis complete.")
        except Exception as e:
            st.error(f"Analysis Failed: {e}")
else:
    st.info("Adjust parameters in the sidebar and click 'Run Analysis' to see results.")
