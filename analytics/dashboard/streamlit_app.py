import streamlit as st
st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊")

try:
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity import (
        SensitivityRequest, run_tornado_sensitivity, tornado_suite_to_dataframe
    )
except (ImportError, SyntaxError) as e:
    st.error(f"⚠️ Model Initialization Failed: {e}")
    st.info("💡 Troubleshooting: Check 'analytics/contracts_v14.py' for syntax errors.")
    st.stop()

st.title("📊 Sensitivity Explorer")
config_path = st.text_input("Scenario Path", "scenarios/dutchbay_lendercase_2025Q4.yaml", help="Path to YAML config.")

params = [
    ParameterRangeConfig(variable_name="project.capex_usd_per_kw", base_value=900.0, low_pct=20, high_pct=20, label="CapEx"),
    ParameterRangeConfig(variable_name="generation.capacity_factor_pct", base_value=45.0, low_pct=10, high_pct=10, label="Capacity Factor"),
]

if st.button("🚀 Run Analysis", help="Execute simulation"):
    with st.spinner("Analyzing..."):
        try:
            suite = run_tornado_sensitivity(SensitivityRequest(config_path, params))
            st.subheader("📈 Results")
            st.dataframe(tornado_suite_to_dataframe(suite), use_container_width=True)
        except Exception as e:
            st.error(f"❌ Analysis failed: {e}")

st.divider()
st.image("exports/tornado_chart.png", caption="Tornado Chart: Key drivers of Project IRR")
