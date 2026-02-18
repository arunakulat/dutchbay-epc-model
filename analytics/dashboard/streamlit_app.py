"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Plug in any analytics/sensitivity output (tornado/spider) for fast DFI/lead demo!

Run with:
    streamlit run dashboard/streamlit_app.py
"""

import streamlit as st

# ✅ Micro-UX: Professional page config
st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊", layout="wide")

try:
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity import (
        SensitivityRequest,
        plot_spider_chart,
        run_multi_metric_tornado,
        run_tornado_sensitivity,
        tornado_suite_to_dataframe,
    )
except (ImportError, SyntaxError) as e:
    # ✅ Micro-UX: Graceful failure when backend is broken
    st.error("### ⚠️ Dashboard Initialization Failed")
    st.info("💡 **Troubleshooting:** This dashboard requires valid backend contracts. Please verify `analytics/contracts_v14.py` is correctly defined.")
    with st.expander("🔍 Technical Details"):
        st.code(str(e))
    st.stop()

# Quick UI for scenario and drivers (customize as needed)
st.title("📊 Sensitivity Dashboard")

config_path = st.text_input(
    "Scenario Config Path",
    "scenarios/dutchbay_lendercase_2025Q4.yaml",
    help="Path to the YAML scenario configuration file. Ensure the file exists in the repository."
)
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
    # Add or make this dynamic as needed
]

# ✅ Micro-UX: Explicit Run button with feedback
if st.button("🚀 Run Analysis", type="primary", use_container_width=True):
    with st.spinner("Calculating sensitivity matrices..."):
        try:
            sens_req = SensitivityRequest(config_path, params)
            suite = run_tornado_sensitivity(sens_req)
            df = tornado_suite_to_dataframe(suite)

            st.subheader("📈 Sensitivity Results")
            st.dataframe(df, use_container_width=True)

            st.subheader("🌪️ Tornado Chart")
            st.image("exports/tornado_chart.png", caption="Variation of NPV/IRR across parameters")

            st.subheader("🕸️ Multi-metric Spider Chart")
            multi_suite = run_multi_metric_tornado(sens_req, metrics=["project_irr", "equity_irr"])
            plot_spider_chart(multi_suite, "exports/spider_chart.png")
            st.image("exports/spider_chart.png", caption="Comparison of Project and Equity IRR sensitivity")

            st.success("Analysis complete!")
        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")

st.info("💡 **Pro-tip:** Modify `params` in `streamlit_app.py` to explore different financial drivers.")
