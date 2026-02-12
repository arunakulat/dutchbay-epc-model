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
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity import (
        SensitivityRequest,
        plot_spider_chart,
        run_multi_metric_tornado,
        run_tornado_sensitivity,
        tornado_suite_to_dataframe,
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
            sens_req = SensitivityRequest(config_path, params)
            suite = run_tornado_sensitivity(sens_req)
            df = tornado_suite_to_dataframe(suite)

            st.write("### 📈 Analysis Results")
            st.dataframe(df, width=1000)

            st.write("### 🌪️ Tornado Chart")
            st.image("exports/tornado_chart.png", caption="Relative impact of drivers on baseline NPV/IRR.")

            st.write("### 🕷️ Spider Chart")
            multi_suite = run_multi_metric_tornado(sens_req, metrics=["project_irr", "equity_irr"])
            plot_spider_chart(multi_suite, "exports/spider_chart.png")
            st.image("exports/spider_chart.png", caption="Sensitivity across multiple metrics.")

    st.success("Tip: Use the sidebar or input fields above to adjust your analysis.")
else:
    st.warning("The dashboard is running in 'Safe Mode' due to backend issues. Functionality is limited.")
