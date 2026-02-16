"""
dashboard/streamlit_app.py - Interactive explorer for sensitivity results.
"""
import streamlit as st

st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊", layout="wide")

try:
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity import (
        SensitivityRequest, plot_spider_chart, run_multi_metric_tornado,
        run_tornado_sensitivity, tornado_suite_to_dataframe,
    )
    BACKEND_AVAILABLE = True
except (ImportError, SyntaxError) as e:
    BACKEND_AVAILABLE = False
    IMPORT_ERROR = str(e)

st.title("DutchBay Sensitivity Explorer 🌪️")

with st.sidebar:
    st.header("Configuration")
    config_path = st.text_input(
        "Scenario Config Path", "scenarios/dutchbay_lendercase_2025Q4.yaml",
        help="Path to the YAML file containing scenario assumptions."
    )
    run_analysis = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

    if not BACKEND_AVAILABLE:
        st.warning("⚠️ Backend unavailable. Some inputs may be disabled.")

if not BACKEND_AVAILABLE:
    st.error("⚠️ Model Initialization Failed")
    st.markdown(f"**Error:** `{IMPORT_ERROR}`")
    st.info("The dashboard is running in **Safe Mode**. Please check backend contracts and dependencies.")
    st.stop()

params = [
    ParameterRangeConfig(variable_name="project.capex_usd_per_kw", base_value=900.0, low_pct=-20, high_pct=20, steps=5),
    ParameterRangeConfig(variable_name="generation.capacity_factor_pct", base_value=45.0, low_pct=-10, high_pct=10, steps=5),
]

if run_analysis:
    with st.spinner("Executing sensitivity analysis..."):
        sens_req = SensitivityRequest(config_path, params)

        # Run Tornado analysis
        suite = run_tornado_sensitivity(sens_req)
        df = tornado_suite_to_dataframe(suite)

        # Run Multi-metric spider analysis
        multi_suite = run_multi_metric_tornado(sens_req, metrics=["project_irr", "equity_irr"])
        plot_spider_chart(multi_suite, "exports/spider_chart.png")

    st.subheader("KPI Sensitivity Table")
    st.dataframe(df, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.write("### Tornado Chart")
        st.image("exports/tornado_chart.png", caption="Key drivers impact.")
    with col2:
        st.write("### Multi-metric (Spider) Chart")
        st.image("exports/spider_chart.png", caption="Cross-metric sensitivity.")
    st.success("Analysis complete!")
else:
    st.info("Adjust the configuration in the sidebar and click 'Run Analysis' to see results.")
