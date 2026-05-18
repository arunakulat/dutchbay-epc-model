import os, streamlit as st, yaml
from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity import run_sensitivity_analysis, suite_to_tables
from analytics.sensitivity.viz import plot_tornado

st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊", layout="wide")
st.title("📊 Sensitivity Analysis Dashboard")

SCENARIO_DIR = "scenarios"
allowed = sorted([f for f in os.listdir(SCENARIO_DIR) if f.endswith(".yaml")])

with st.sidebar:
    st.header("Configuration")
    selected = st.selectbox("Scenario Config", allowed, index=allowed.index("dutchbay_lendercase_2025Q4.yaml") if "dutchbay_lendercase_2025Q4.yaml" in allowed else 0)
    st.subheader("Drivers")
    c_low, c_high = st.slider("CAPEX (%)", -50, 50, (-20, 20), help="Low/High shocks for CAPEX")
    f_low, f_high = st.slider("Capacity Factor (%)", -30, 30, (-10, 10))
    run = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

if run:
    with st.spinner("Analyzing..."):
        try:
            with open(os.path.join(SCENARIO_DIR, selected), "r") as f:
                cfg = yaml.safe_load(f)
            params = [
                ParameterRangeConfig("project.capex_usd_per_kw", 900.0, float(c_low), float(c_high), label="CAPEX"),
                ParameterRangeConfig("generation.capacity_factor_pct", 45.0, float(f_low), float(f_high), label="Capacity Factor")
            ]
            suite = run_sensitivity_analysis(base_config=cfg, base_config_path=selected, parameters=params, metric_keys=["project_irr"])
            df = suite_to_tables(suite)["tornado_rows"]
            st.subheader(f"Results: {suite.metric}")
            st.pyplot(plot_tornado(table=df))
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"Error: {e}")
else:
    st.info("👈 Adjust parameters in the sidebar and click 'Run Analysis' to begin.")
