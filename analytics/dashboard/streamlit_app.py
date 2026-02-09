"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Plug in any analytics/sensitivity output (tornado/spider) for fast DFI/lead demo!

Run with:
    streamlit run dashboard/streamlit_app.py
"""

import streamlit as st

st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊", layout="wide")

try:
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity import (
        SensitivityRequest, plot_spider_chart, run_multi_metric_tornado,
        run_tornado_sensitivity, tornado_suite_to_dataframe
    )
except (ImportError, SyntaxError) as e:
    st.error(f"### 🛑 System Load Error\n{e}")
    st.info("Check `analytics/contracts_v14.py` for syntax errors or missing dependencies.")
    st.stop()

st.title("Sensitivity Dashboard (Tornado/Spider Explorer)")

col1, col2 = st.columns([2, 1])
with col1:
    config_path = st.text_input("📄 Scenario Config Path", "scenarios/dutchbay_lendercase_2025Q4.yaml")
with col2:
    st.info("Select a scenario to analyze sensitivities.")
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

with st.spinner("Running sensitivity analysis..."):
    sens_req = SensitivityRequest(config_path, params)
    suite = run_tornado_sensitivity(sens_req)
    df = tornado_suite_to_dataframe(suite)
st.dataframe(df)

st.subheader("📊 Visualizations")
st.image("exports/tornado_chart.png", caption="Tornado Chart: Parameter impacts.", use_container_width=True)

with st.spinner("Generating spider chart..."):
    multi_suite = run_multi_metric_tornado(sens_req, metrics=["project_irr", "equity_irr"])
    plot_spider_chart(multi_suite, "exports/spider_chart.png")
st.image("exports/spider_chart.png", caption="Spider Chart: Multi-metric sensitivity.", use_container_width=True)

st.success("Try changing params in the code for more exploration.")
