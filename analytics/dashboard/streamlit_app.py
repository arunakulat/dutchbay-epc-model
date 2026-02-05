"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Plug in any analytics/sensitivity output (tornado/spider) for fast DFI/lead demo!

Run with:
    streamlit run dashboard/streamlit_app.py
"""

import streamlit as st

# ✅ UX: Set professional page config first
st.set_page_config(
    page_title="DutchBay Sensitivity Explorer",
    page_icon="🎨",
    layout="wide",
)

try:
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity import (
        SensitivityRequest,
        plot_spider_chart,
        run_multi_metric_tornado,
        run_tornado_sensitivity,
        tornado_suite_to_dataframe,
    )
except (SyntaxError, ImportError) as e:
    # ✅ UX: Graceful error handling for backend issues
    st.error(f"⚠️ **Backend Initialization Error:** {e}")
    st.info(
        "💡 This usually indicates a syntax or import error in the core analytics contracts. "
        "Please check `analytics/contracts_v14.py` for placeholder markers or missing definitions."
    )
    st.stop()

# ✅ UX: Professional Branding
st.title("🎨 Sensitivity Analysis Dashboard")
st.caption("Interactive explorer for tornado and spider sensitivity results (v14)")
st.divider()

config_path = st.text_input(
    "Scenario Config Path",
    value="scenarios/dutchbay_lendercase_2025Q4.yaml",
    help="Enter the relative path to the scenario YAML configuration file.",
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
]

# ✅ UX: Spinner for interaction feedback
with st.spinner("🚀 Running tornado analysis..."):
    sens_req = SensitivityRequest(config_path, params)
    suite = run_tornado_sensitivity(sens_req)
    df = tornado_suite_to_dataframe(suite)

st.subheader("📊 Sensitivity Results")
st.dataframe(df, use_container_width=True)

st.divider()
col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 🌪️ Tornado Chart")
    st.image("exports/tornado_chart.png")

with col2:
    st.markdown("#### 🕷️ Multi-metric (Spider) Chart")
    with st.spinner("Generating spider chart..."):
        multi_suite = run_multi_metric_tornado(
            sens_req, metrics=["project_irr", "equity_irr"]
        )
        plot_spider_chart(multi_suite, "exports/spider_chart.png")
    st.image("exports/spider_chart.png")

st.success("✅ Analysis complete. Try adjusting parameters for further exploration.")
