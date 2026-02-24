"""
dashboard/streamlit_app.py - Interactive explorer with Graceful Failure.
"""
import streamlit as st
import traceback

st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊", layout="wide")

try:
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity import (
        SensitivityRequest, plot_spider_chart, run_multi_metric_tornado,
        run_tornado_sensitivity, tornado_suite_to_dataframe,
    )
    BACKEND_OK = True
except (ImportError, SyntaxError, AttributeError) as e:
    BACKEND_OK, ERR, TRACE = False, e, traceback.format_exc()

st.title("📊 Sensitivity Dashboard")

if not BACKEND_OK:
    st.error("### ⚠️ Model Initialization Failed")
    with st.expander("Show Technical Details"):
        st.code(TRACE)
    st.stop()

with st.sidebar:
    st.header("Settings")
    conf_path = st.text_input("Config Path", "scenarios/dutchbay_lendercase_2025Q4.yaml", help="Path to scenario YAML")
    run_btn = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

if run_btn:
    with st.spinner("Analyzing..."):
        params = [
            ParameterRangeConfig(variable_name="project.capex_usd_per_kw", base_value=900.0, low_pct=20, high_pct=20, steps=5),
            ParameterRangeConfig(variable_name="generation.capacity_factor_pct", base_value=45.0, low_pct=10, high_pct=10, steps=5),
        ]
        sens_req = SensitivityRequest(conf_path, params)
        suite = run_tornado_sensitivity(sens_req)
        st.dataframe(tornado_suite_to_dataframe(suite), use_container_width=True)
        st.image("exports/tornado_chart.png", caption="Tornado Results")
else:
    st.info("👈 Adjust parameters in the sidebar and click **Run Analysis** to begin.")
