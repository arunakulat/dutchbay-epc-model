"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Plug in any analytics/sensitivity output (tornado) for fast DFI/lead demo!

Run with:
    PYTHONPATH=. python3 -m streamlit run analytics/dashboard/streamlit_app.py
"""

import os
import streamlit as st
import matplotlib.pyplot as plt

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity import (
    run_sensitivity_analysis,
    suite_to_tables,
)
from analytics.sensitivity.viz import plot_tornado
from analytics.scenario_loader import load_scenario_config

# Page Config
st.set_page_config(
    page_title="DutchBay | Sensitivity Explorer",
    page_icon="📊",
    layout="wide",
)

st.title("DutchBay | Sensitivity Explorer")

# Sidebar for configuration
with st.sidebar:
    st.header("Scenario Configuration")

    # Discovery of scenarios
    scenario_dir = "scenarios"
    if os.path.exists(scenario_dir):
        yaml_files = [f for f in os.listdir(scenario_dir) if f.endswith((".yaml", ".yml"))]
        default_index = 0
        if "dutchbay_lendercase_2025Q4.yaml" in yaml_files:
            default_index = yaml_files.index("dutchbay_lendercase_2025Q4.yaml")

        config_file = st.selectbox(
            "Select Base Scenario",
            options=yaml_files,
            index=default_index,
            help="Choose the base financial scenario to run sensitivity against."
        )
        config_path = os.path.join(scenario_dir, config_file)
    else:
        config_path = st.text_input(
            "Scenario Config Path",
            "scenarios/dutchbay_lendercase_2025Q4.yaml",
            help="Path to the YAML configuration file."
        )

    st.divider()
    st.header("Parameters")

    # We could make these dynamic, but for now we'll stick to core drivers
    capex_range = st.slider(
        "Capex Sensitivity (%)",
        min_value=-50,
        max_value=50,
        value=(-20, 20),
        step=5,
        help="Range of variation for Capex USD per kW"
    )

    gen_range = st.slider(
        "Generation Sensitivity (%)",
        min_value=-30,
        max_value=30,
        value=(-10, 10),
        step=5,
        help="Range of variation for Capacity Factor"
    )

    st.divider()
    run_analysis = st.button("Run Analysis", type="primary", use_container_width=True)

# Main Area
if run_analysis:
    try:
        with st.spinner("Loading scenario and running simulations..."):
            # Load config
            base_config = load_scenario_config(config_path)

            # Build params
            params = [
                ParameterRangeConfig(
                    variable_name="project.capex_usd_per_kw",
                    base_value=base_config.get("project", {}).get("capex_usd_per_kw", 900.0),
                    low_pct=float(capex_range[0]),
                    high_pct=float(capex_range[1]),
                    points=2,
                ),
                ParameterRangeConfig(
                    variable_name="generation.capacity_factor_pct",
                    base_value=base_config.get("generation", {}).get("capacity_factor_pct", 45.0),
                    low_pct=float(gen_range[0]),
                    high_pct=float(gen_range[1]),
                    points=2,
                ),
            ]

            # Run Analysis
            suite = run_sensitivity_analysis(
                base_config=base_config,
                base_config_path=config_path,
                parameters=params,
                metric_keys=["project_irr", "equity_irr"]
            )

            tables = suite_to_tables(suite)
            df = tables["tornado_rows"]

        # Results Display
        st.subheader("Key Drivers (Project IRR Impact)")

        col1, col2 = st.columns([1, 1])

        with col1:
            st.dataframe(df, use_container_width=True)

        with col2:
            fig = plot_tornado(table=df, title=f"Tornado Analysis: {suite.metric}")
            st.pyplot(fig)

        st.success("Analysis complete!")

    except Exception as e:
        st.error(f"Error running analysis: {str(e)}")
        st.info("Check if the selected scenario contains all required fields.")
else:
    st.info("👈 Select a scenario and adjust parameters in the sidebar, then click 'Run Analysis'.")

# Footer
st.divider()
st.caption("DutchBay EPC Model v14 | Sensitivity Analytics Dashboard")
