"""
dashboard/streamlit_app.py - Interactive explorer with Graceful Failure.
"""
import streamlit as st
import traceback

st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊", layout="wide")

try:
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity import (
        SensitivityRequest,
        run_sensitivity_analysis, suite_to_tables,
    )
    BACKEND_OK = True
except (ImportError, SyntaxError, AttributeError, NameError) as e:
    BACKEND_OK, ERR, TRACE = False, e, traceback.format_exc()

st.title("📊 Sensitivity Dashboard")

if not BACKEND_OK:
    st.error("### ⚠️ Model Initialization Failed")
    st.info("The application is running in **Safe Mode**. This usually happens when backend contracts are corrupted or dependencies are missing.")
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
        sens_req = SensitivityRequest(config_path=conf_path, parameters=params)
        suite = run_sensitivity_analysis(sens_req)
        tables = suite_to_tables(suite)
        st.dataframe(tables["summary"], use_container_width=True)
        st.success("Analysis Complete!")
else:
    st.info("👈 Adjust parameters in the sidebar and click **Run Analysis** to begin.")
