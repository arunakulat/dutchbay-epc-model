"""dashboard/streamlit_app.py - Sensitivity explorer."""
import os
import streamlit as st
from omegaconf import OmegaConf
from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity import run_sensitivity_analysis, suite_to_tables
from analytics.sensitivity.viz import plot_tornado

st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊", layout="wide")
st.title("📊 DutchBay Sensitivity Explorer")

with st.sidebar:
    st.header("Settings")
    scenarios = sorted([os.path.join("scenarios", f) for f in os.listdir("scenarios") if f.endswith(".yaml")])
    config_path = st.selectbox("Scenario", options=scenarios, format_func=os.path.basename)
    metric_key = st.selectbox("KPI", options=["project_irr", "equity_irr", "min_dscr"])
    params = [
        ParameterRangeConfig("project.capex_usd_per_kw", 900.0, low_pct=-20, high_pct=20, points=5),
        ParameterRangeConfig("generation.capacity_factor_pct", 45.0, low_pct=-10, high_pct=10, points=5),
    ]
    st.info("Parameters preset for demo.")
    run_btn = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

if run_btn:
    with st.spinner("Analyzing..."):
        try:
            cfg = OmegaConf.to_container(OmegaConf.load(config_path), resolve=True)
            suite = run_sensitivity_analysis(base_config=cfg, base_config_path=config_path, parameters=params, metric_keys=[metric_key])
            df = suite_to_tables(suite)["tornado_rows"]
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Results Table")
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.download_button("📥 Download CSV", df.to_csv(index=False), "results.csv", "text/csv")
            with col2:
                st.subheader("Tornado Chart")
                st.pyplot(plot_tornado(table=df, title=f"Sensitivity: {metric_key.upper()}"))
            st.success("Analysis complete.")
        except Exception as e:
            st.error(f"Error: {e}")
else:
    st.info("Select scenario and click 'Run Analysis' to begin.")
