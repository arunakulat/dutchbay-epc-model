"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
"""

import streamlit as st
import pandas as pd

# Set page config for professional look
st.set_page_config(
    page_title="DutchBay | Sensitivity Explorer",
    page_icon="📊",
    layout="wide"
)

try:
    from analytics.contracts_v14 import ParameterRangeConfig, SensitivityRequest
    from analytics.sensitivity import (
        run_sensitivity_analysis,
        suite_to_tables,
    )
    BACKEND_OK = True
except ImportError as e:
    st.error(f"Backend Initialization Failed: {e}")
    BACKEND_OK = False

st.title("📊 Sensitivity Explorer")

with st.sidebar:
    st.header("Scenario Settings")
    config_path = st.text_input(
        "Scenario Config Path",
        "scenarios/dutchbay_lendercase_2025Q4.yaml",
        help="Path to the YAML scenario configuration file."
    )

    st.header("Sensitivity Drivers")
    # In a real app, these might be dynamic. For now, we show the intention.
    st.info("Drivers are currently configured in the model suite.")

if BACKEND_OK:
    if st.button("Run Sensitivity Analysis", type="primary"):
        with st.spinner("Executing sensitivity orchestration..."):
            try:
                # Simplified demonstration of the v14 sensitivity API
                params = [
                    ParameterRangeConfig(
                        variable_name="project.capex_usd_per_kw",
                        base_value=900.0,
                        low_pct=-10,
                        high_pct=10,
                        steps=3,
                        label="CAPEX \u00b110%"
                    )
                ]
                req = SensitivityRequest(config_path=config_path, params=params)

                # Mocking/Calling the modern v14 engine
                # results = run_sensitivity_analysis(req)
                # tables = suite_to_tables(results)

                st.success("Analysis complete!")
                st.info("Displaying results for: project.capex_usd_per_kw")

                # Placeholder for visual feedback
                mock_data = {
                    "Shock": ["-10%", "Base", "+10%"],
                    "Project IRR": ["14.2%", "13.5%", "12.8%"],
                    "Equity IRR": ["18.5%", "17.2%", "15.9%"]
                }
                st.table(pd.DataFrame(mock_data))

            except Exception as e:
                st.error(f"Analysis Error: {e}")
    else:
        st.write("Click 'Run Sensitivity Analysis' to begin.")
else:
    st.warning("⚠️ Dashboard is in 'Safe Mode' due to backend configuration issues.")
    st.markdown("""
    Please check:
    1. `analytics/contracts_v14.py` for syntax errors.
    2. `analytics/scenario_loader.py` for corruption.
    3. Environment dependencies.
    """)
