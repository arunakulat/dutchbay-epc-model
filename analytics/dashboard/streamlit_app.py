import streamlit as st

st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊")

try:
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity import run_sensitivity_analysis, suite_to_tables
    from analytics.scenario_loader import load_scenario_config
except (ImportError, SyntaxError) as e:
    st.error(f"⚠️ Model Initialization Failed: {e}")
    st.stop()

st.title("📊 Sensitivity Explorer")
config_path = st.text_input(
    "Scenario Path",
    "scenarios/dutchbay_lendercase_2025Q4.yaml",
    help="Path to YAML config.",
)

col1, col2 = st.columns(2)
with col1:
    capex_pct = st.number_input(
        "CapEx ±%", 0, 100, 20, help="Variation for CapEx"
    )
with col2:
    gen_pct = st.number_input(
        "Generation ±%", 0, 100, 10, help="Variation for Generation"
    )

params = [
    ParameterRangeConfig(
        variable_name="project.capex_usd_per_kw",
        base_value=900.0,
        low_pct=float(capex_pct),
        high_pct=float(capex_pct),
        label="CapEx",
    ),
    ParameterRangeConfig(
        variable_name="generation.capacity_factor_pct",
        base_value=45.0,
        low_pct=float(gen_pct),
        high_pct=float(gen_pct),
        label="Generation",
    ),
]

if st.button("🚀 Run Sensitivity Analysis", use_container_width=True):
    with st.spinner("Crunching numbers..."):
        try:
            suite = run_sensitivity_analysis(
                base_config=load_scenario_config(config_path),
                base_config_path=config_path,
                parameters=params,
                metric_keys=["project_irr"],
            )
            st.subheader("📈 Results")
            st.dataframe(
                suite_to_tables(suite)["tornado_rows"],
                use_container_width=True,
            )
            st.image(
                "exports/tornado_chart.png",
                caption="Tornado Chart: Impact on Project IRR",
            )
        except Exception as e:
            st.error(f"❌ Analysis failed: {e}")
