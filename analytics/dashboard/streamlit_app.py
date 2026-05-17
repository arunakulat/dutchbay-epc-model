"""
dashboard/streamlit_app.py
Interactive explorer for sensitivity results using Streamlit.
"""
import streamlit as st
from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity import run_sensitivity_analysis, suite_to_tables
from analytics.scenario_loader import load_scenario_config

st.set_page_config(page_title="DutchBay | Sensitivity", page_icon="📊", layout="wide")
st.title("📊 DutchBay Sensitivity Explorer")

with st.sidebar:
    st.header("Analysis Settings")
    cfg_path = st.text_input("Scenario Config", "scenarios/dutchbay_lendercase_2025Q4.yaml", help="Path to scenario YAML.")

    st.subheader("Drivers")
    p1 = ParameterRangeConfig(variable_name="project.capacity_factor", base_value=0.428, low_pct=-5, high_pct=5, label="Capacity Factor")
    p2 = ParameterRangeConfig(variable_name="capex.capex_per_kw_usd", base_value=1000.0, low_pct=-10, high_pct=10, label="CAPEX ($/kW)")
    st.caption(f"Testing: {p1.label}, {p2.label}")

    st.markdown("---")
    run_btn = st.button("Run Analysis", type="primary", use_container_width=True)

if run_btn:
    with st.spinner("Executing sensitivity sweep..."):
        try:
            cfg = load_scenario_config(cfg_path)
            suite = run_sensitivity_analysis(base_config=cfg, base_config_path=cfg_path, parameters=[p1, p2], metric_keys=["project_irr"])
            df = suite_to_tables(suite)["tornado_rows"]
            st.subheader(f"Results for {suite.metric}")
            st.dataframe(df, use_container_width=True)
            st.success("✅ Sensitivity analysis complete.")
        except Exception as e:
            st.error(f"Analysis failed: {e}")
            st.info("Check if the scenario config path is correct and dependencies are installed.")
else:
    st.info("👈 Configure drivers in the sidebar and click 'Run Analysis' to begin.")

st.markdown("---")
st.caption("DutchBay EPC Model v14 | Palette UX Edition 🎨")
