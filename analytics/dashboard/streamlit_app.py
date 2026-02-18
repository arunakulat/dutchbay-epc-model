"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Plug in any analytics/sensitivity output (tornado/spider) for fast DFI/lead demo!

Run with:
    streamlit run dashboard/streamlit_app.py
"""

import streamlit as st
import traceback

# 🎨 Palette: Professional page config
st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊")

st.title("📊 Sensitivity Dashboard")

try:
    # 🎨 Palette: Graceful Failure pattern - wrap volatile imports
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity import (
        SensitivityRequest,
        plot_spider_chart,
        run_multi_metric_tornado,
        run_tornado_sensitivity,
        tornado_suite_to_dataframe,
    )

    # 🎨 Palette: Accessibility - added help tooltip
    config_path = st.text_input(
        "Scenario Config Path",
        "scenarios/dutchbay_lendercase_2025Q4.yaml",
        help="Path to the scenario configuration file (YAML/JSON)."
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

    st.write("Running tornado analysis...")
    sens_req = SensitivityRequest(config_path, params)
    suite = run_tornado_sensitivity(sens_req)
    df = tornado_suite_to_dataframe(suite)
    st.dataframe(df)

    st.write("Tornado Chart:")
    st.image(
        "exports/tornado_chart.png"
    )  # Assumes you pre-exported with plot_tornado_chart.

    st.write("Multi-metric (Spider) Chart:")
    multi_suite = run_multi_metric_tornado(sens_req, metrics=["project_irr", "equity_irr"])
    plot_spider_chart(multi_suite, "exports/spider_chart.png")
    st.image("exports/spider_chart.png")

    st.success("Try changing params in the code for more exploration.")

except Exception as e:
    # 🎨 Palette: Professional feedback when model components fail to load
    st.error("### ⚠️ Dashboard Initialization Failed")
    st.info("💡 **Troubleshooting:** This dashboard requires valid backend contracts. Please verify `analytics/contracts_v14.py` is correctly defined.")
    with st.expander("🔍 Technical Details"):
        st.code(traceback.format_exc())
