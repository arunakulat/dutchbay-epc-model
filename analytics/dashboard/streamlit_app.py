"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
"""

import streamlit as st

# MUST be the first Streamlit command
st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊")

try:
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity import run_sensitivity_analysis, suite_to_tables
    from analytics.scenario_loader import load_scenario_config
except (ImportError, SyntaxError) as e:
    st.error(f"⚠️ Model Initialization Failed: {e}")
    st.info("💡 Troubleshooting: Check analytics/contracts_v14.py for syntax errors or missing dependencies.")
    st.stop()

st.title("📊 Sensitivity Explorer")

config_path = st.text_input(
    "Scenario Config Path",
    "scenarios/dutchbay_lendercase_2025Q4.yaml",
    help="Path to the YAML configuration file for the scenario."
)

params = [
    ParameterRangeConfig(
        variable_name="project.capex_usd_per_kw",
        base_value=900.0,
        low_pct=20,  # Must be non-negative
        high_pct=20,
        label="CapEx (USD/kW)"
    ),
    ParameterRangeConfig(
        variable_name="generation.capacity_factor_pct",
        base_value=45.0,
        low_pct=10,
        high_pct=10,
        label="Capacity Factor (%)"
    ),
]

if st.button("🚀 Run Sensitivity Analysis"):
    with st.spinner("Crunching numbers..."):
        try:
            cfg = load_scenario_config(config_path)
            suite = run_sensitivity_analysis(
                base_config=cfg,
                base_config_path=config_path,
                parameters=params,
                metric_keys=["project_irr"]
            )
            tables = suite_to_tables(suite)

            st.subheader("📈 Sensitivity Results")
            st.dataframe(tables["tornado_rows"])

        except Exception as e:
            st.error(f"❌ Analysis failed: {e}")

st.divider()
st.subheader("🖼️ Visualizations")
st.image(
    "exports/tornado_chart.png",
    caption="Tornado Chart: Impact of key drivers on Project IRR. (Note: Ensure chart is pre-generated in exports/)"
)
