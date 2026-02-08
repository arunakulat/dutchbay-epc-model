"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Plug in any analytics/sensitivity output (tornado/spider) for fast DFI/lead demo!

Run with:
    streamlit run dashboard/streamlit_app.py
"""

import streamlit as st

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity import (
    run_sensitivity_analysis,
    suite_to_tables,
)

# UX Improvement: Set page configuration for professional branding
st.set_page_config(
    page_title="DutchBay | Sensitivity Explorer",
    page_icon="📊",
)

# Quick UI for scenario and drivers (customize as needed)
st.title("Sensitivity Dashboard (Tornado/Spider Explorer)")

config_path = st.text_input(
    "Scenario Config Path", "scenarios/dutchbay_lendercase_2025Q4.yaml"
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

# UX Improvement: Use st.spinner for long-running analysis to provide feedback
with st.spinner("Running tornado analysis..."):
    # Fix broken imports/calls to use new v14 engine
    from analytics.scenario_loader import load_scenario_config
    base_cfg = load_scenario_config(config_path)
    suite = run_sensitivity_analysis(
        base_config=base_cfg,
        base_config_path=config_path,
        parameters=params,
        metric_keys=["project_irr"]
    )
    df = suite_to_tables(suite)["tornado_rows"]

st.dataframe(df)

st.write("Tornado Chart:")
st.image(
    "exports/tornado_chart.png"
)  # Assumes you pre-exported with plot_tornado_chart.

st.success("Try changing params in the code for more exploration.")
