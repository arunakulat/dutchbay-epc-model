"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Plug in any analytics/sensitivity output (tornado/spider) for fast DFI/lead demo!

Run with:
    streamlit run dashboard/streamlit_app.py
"""

import streamlit as st

st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊")
st.title("📊 Sensitivity Explorer")

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
    st.error(f"⚠️ Model Initialization Failed: {e}")
    st.stop()

config_path = st.text_input(
    "Scenario Config Path",
    "scenarios/dutchbay_lendercase_2025Q4.yaml",
    help="Relative path to the scenario YAML configuration file."
)
params = [
    ParameterRangeConfig(
        variable_name="project.capex_usd_per_kw",
        base_value=900.0,
        low_pct=20,
        high_pct=20,
        steps=5,
    ),
    ParameterRangeConfig(
        variable_name="generation.capacity_factor_pct",
        base_value=45.0,
        low_pct=10,
        high_pct=10,
        steps=5,
    ),
    # Add or make this dynamic as needed
]

if st.button("🚀 Run Analysis", type="primary", help="Execute sensitivity analysis"):
    st.write("Running tornado analysis...")
    sens_req = SensitivityRequest(config_path, params)
    suite = run_tornado_sensitivity(sens_req)
    df = tornado_suite_to_dataframe(suite)
    st.dataframe(df)

    st.write("Tornado Chart:")
    st.image(
        "exports/tornado_chart.png",
        caption="Impact of key drivers on project returns."
    )

    st.write("Multi-metric (Spider) Chart:")
    multi_suite = run_multi_metric_tornado(sens_req, metrics=["project_irr", "equity_irr"])
    plot_spider_chart(multi_suite, "exports/spider_chart.png")
    st.image(
        "exports/spider_chart.png",
        caption="Spider chart comparing sensitivity across multiple financial metrics."
    )
    st.success("Analysis complete!")
else:
    st.info("👋 Welcome! Adjust parameters and click **Run Analysis** to begin.")
