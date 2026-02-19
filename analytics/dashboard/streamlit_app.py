"""
dashboard/streamlit_app.py - Sensitivity results explorer.
"""
import streamlit as st

# Professional Page Config
st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊", layout="wide")
st.title("Sensitivity Dashboard (Tornado/Spider Explorer)")

# Graceful Failure Pattern for core dependencies
try:
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity import (
        SensitivityRequest, plot_spider_chart, run_multi_metric_tornado,
        run_tornado_sensitivity, tornado_suite_to_dataframe
    )
except (ImportError, SyntaxError) as e:
    st.error("🚨 **Model Initialization Failed**")
    st.info("💡 **Troubleshooting:** This typically happens when backend contracts are corrupted.")
    with st.expander("Show Technical Details"):
        st.code(str(e))
    st.stop()

config_path = st.text_input(
    "Scenario Config Path", "scenarios/dutchbay_lendercase_2025Q4.yaml",
    help="Path to the YAML configuration file for the scenario."
)

params = [
    ParameterRangeConfig(variable_name="project.capex_usd_per_kw", base_value=900.0, low_pct=-20, high_pct=20, steps=5),
    ParameterRangeConfig(variable_name="generation.capacity_factor_pct", base_value=45.0, low_pct=-10, high_pct=10, steps=5),
]

if st.button("🚀 Run Analysis", type="primary"):
    st.write("Running tornado analysis...")
    sens_req = SensitivityRequest(config_path, params)
    suite = run_tornado_sensitivity(sens_req)
    df = tornado_suite_to_dataframe(suite)
    st.dataframe(df, use_container_width=True)

    st.write("Tornado Chart:")
    st.image("exports/tornado_chart.png", caption="Key sensitivity drivers")

    st.write("Multi-metric (Spider) Chart:")
    multi_suite = run_multi_metric_tornado(sens_req, metrics=["project_irr", "equity_irr"])
    plot_spider_chart(multi_suite, "exports/spider_chart.png")
    st.image("exports/spider_chart.png", caption="Spider chart of IRR metrics")
    st.success("Analysis complete!")
else:
    st.info("👈 Click 'Run Analysis' to start exploration.")
