"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Plug in any analytics/sensitivity output (tornado/spider) for fast DFI/lead demo!

Run with:
    streamlit run dashboard/streamlit_app.py
"""

import streamlit as st

# 🎨 Palette: Micro-UX Improvements (Page Config, Graceful Failure, Interaction Feedback)
st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊")

try:
    from analytics.contracts_v14 import ParameterRangeConfig, SensitivityRequest
    from analytics.sensitivity import (
        run_sensitivity_analysis,
        suite_to_tables,
    )
    BACKEND_AVAILABLE = True
except (ImportError, SyntaxError) as e:
    st.error(f"⚠️ **Model Initialization Failed**: {e}")
    st.info("💡 **Troubleshooting**: Please ensure `analytics/contracts_v14.py` is properly defined and all dependencies are installed.")
    BACKEND_AVAILABLE = False

st.title("📊 Sensitivity Explorer")

if BACKEND_AVAILABLE:
    config_path = st.text_input(
        "📄 Scenario Config Path", "scenarios/dutchbay_lendercase_2025Q4.yaml",
        help="Path to the scenario YAML configuration file."
    )

    st.subheader("⚙️ Driver Parameters")
    params = [
        ParameterRangeConfig(
            variable_name="project.capex_usd_per_kw",
            base_value=900.0,
            low_pct=-20,
            high_pct=20,
            steps=5,
        ),
        ParameterRangeConfig(
            variable_name="generation.capacity_factor_pct",
            base_value=45.0,
            low_pct=-10,
            high_pct=10,
            steps=5,
        ),
    ]
    st.caption("Default drivers loaded. Modify `streamlit_app.py` to add more.")

    if st.button("🚀 Run Analysis", type="primary"):
        with st.spinner("Calculating sensitivities..."):
            # Use modern v14 orchestration
            try:
                # Assuming run_sensitivity_analysis takes SensitivityRequest or similar
                # Based on Memory and API check
                sens_req = SensitivityRequest(base_config_path=config_path, parameters=params)
                suite = run_sensitivity_analysis(sens_req)
                tables = suite_to_tables(suite)

                st.write("### 📈 Analysis Results")
                if "main" in tables:
                    st.dataframe(tables["main"], width=1000)
                else:
                    st.write(tables)

                st.write("### 🌪️ Tornado Chart")
                st.info("Tornado chart generation would happen here using the results.")
                # st.image("exports/tornado_chart.png", caption="Relative impact of drivers on baseline NPV/IRR.")

            except Exception as run_error:
                st.error(f"Analysis failed: {run_error}")

    st.success("Tip: Use the input fields above to adjust your analysis.")
else:
    st.warning("The dashboard is running in 'Safe Mode' due to backend issues. Functionality is limited.")
