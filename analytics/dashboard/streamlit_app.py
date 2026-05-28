"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Refactored for DutchBay v14 canonical API with micro-UX improvements.
"""

import os
import yaml
import streamlit as st

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity import (
    run_sensitivity_analysis,
    suite_to_tables,
)

# Page configuration
st.set_page_config(
    page_title="DutchBay | Sensitivity Explorer",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Sensitivity Explorer")

# Sidebar for configuration
with st.sidebar:
    st.header("Settings")

    # Scenario Selection (Micro-UX: Dropdown instead of text input)
    scenario_dir = "scenarios"
    if os.path.exists(scenario_dir):
        scenarios = sorted([f for f in os.listdir(scenario_dir) if f.endswith(".yaml")])
        selected_scenario = st.selectbox(
            "Select Scenario",
            scenarios,
            index=scenarios.index("dutchbay_lendercase_2025Q4.yaml") if "dutchbay_lendercase_2025Q4.yaml" in scenarios else 0,
            help="Choose the base scenario configuration to analyze."
        )
        config_path = os.path.join(scenario_dir, selected_scenario)
    else:
        st.error(f"Directory `{scenario_dir}` not found.")
        st.stop()

    st.divider()
    st.subheader("Drivers")
    st.caption("Configured in-code for this version.")

    # Pre-defined common drivers
    params = [
        ParameterRangeConfig(
            variable_name="capex.capex_per_kw_usd",
            base_value=1000.0,
            low_pct=-20,
            high_pct=20,
            points=2,
            label="CAPEX ($/kW)"
        ),
        ParameterRangeConfig(
            variable_name="project.capacity_factor",
            base_value=0.428,
            low_pct=-10,
            high_pct=10,
            points=2,
            label="Capacity Factor"
        ),
    ]

    for p in params:
        st.text(f"• {p.label or p.variable_name}")

# Main area
# Micro-UX: Explicit Run button to prevent lag during config changes
if st.button("Run Sensitivity Analysis", type="primary"):
    with st.spinner("Executing analysis..."):
        try:
            with open(config_path, "r") as f:
                base_config = yaml.safe_load(f)

            # Use the canonical v14 API
            suite = run_sensitivity_analysis(
                base_config=base_config,
                base_config_path=config_path,
                parameters=params,
                metric_keys=["project_irr"]
            )

            tables = suite_to_tables(suite)
            df = tables["tornado_rows"]

            st.subheader("Results")
            st.dataframe(df, use_container_width=True)

            st.success("Analysis complete!")

        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")
else:
    st.info("Adjust settings and click **Run Sensitivity Analysis** to begin.")

st.markdown("---")
st.caption("DutchBay v14 Analytics Engine")
