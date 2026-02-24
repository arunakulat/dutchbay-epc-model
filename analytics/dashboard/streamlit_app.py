"""
dashboard/streamlit_app.py - Polished UX Edition
"""
import streamlit as st
import logging

try:
    from analytics.contracts_v14 import ParameterRangeConfig, SensitivityRequest
    from analytics.sensitivity import (
        run_tornado_sensitivity,
        tornado_suite_to_dataframe,
    )
    BACKEND_READY = True
except (ImportError, SyntaxError) as e:
    BACKEND_READY = False
    BACKEND_ERROR = str(e)

st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊", layout="wide")

# Sidebar for controls
with st.sidebar:
    st.image("https://raw.githubusercontent.com/arunakulat/dutchbay-epc-model/main/docs/logo.png", width=200) # Fallback logo
    st.title("DutchBay v14")
    st.divider()
    st.header("⚙️ Analysis Settings")
    config_path = st.text_input("Scenario Config Path", "scenarios/dutchbay_lendercase_2025Q4.yaml", help="Path to the scenario YAML configuration file.")
    run_btn = st.button("🚀 Run Analysis", type="primary", disabled=not BACKEND_READY)

st.title("📊 Sensitivity Driver Explorer")

if not BACKEND_READY:
    st.error("🚨 **Backend Initialization Failed**")
    st.warning(f"The model cannot run because of a technical error: `{BACKEND_ERROR}`")
    with st.expander("🛠️ Troubleshooting Guidance"):
        st.markdown("""
        1. **Corruption Detected**: `analytics/contracts_v14.py` or `scenario_loader.py` appear corrupted.
        2. **Fix**: Ensure placeholder text like `[... rest of file ...]` is removed and escaped newlines are restored.
        3. **Dependencies**: Verify `pydantic` and `libcst` are installed.
        """)
    st.stop()

if run_btn:
    try:
        # Default parameters for demo
        params = [
            ParameterRangeConfig(variable_name="project.capex_usd_per_kw", base_value=900.0, low_pct=20, high_pct=20, label="CAPEX"),
            ParameterRangeConfig(variable_name="generation.capacity_factor_pct", base_value=45.0, low_pct=10, high_pct=10, label="Yield"),
        ]
        with st.spinner("🔄 Running high-fidelity simulation..."):
            sens_req = SensitivityRequest(base_config_path=config_path, parameters=params, metric="project_irr")
            suite = run_tornado_sensitivity(sens_req)
            df = tornado_suite_to_dataframe(suite)

        st.subheader("📈 Driver Impact Analysis")
        st.dataframe(df, use_container_width=True)
        st.success("✅ Analysis successfully completed.")
    except Exception as e:
        st.error(f"❌ Calculation Error: {str(e)}")
else:
    st.info("👋 **Ready to begin.** Configure your scenario in the sidebar and click 'Run Analysis' to see how variables impact Project IRR.")
    st.image("https://raw.githubusercontent.com/arunakulat/dutchbay-epc-model/main/docs/sensitivity_demo.png", caption="Sample Tornado Analysis")
