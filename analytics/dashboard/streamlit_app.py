"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Plug in any analytics/sensitivity output (tornado/spider) for fast DFI/lead demo!

Run with:
    PYTHONPATH=. streamlit run analytics/dashboard/streamlit_app.py
"""

import os
import streamlit as st

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity import run_sensitivity_analysis, suite_to_tables
from analytics.sensitivity.viz import plot_tornado
from analytics.scenario_loader import load_scenario_config

# Page Configuration
st.set_page_config(
    page_title="DutchBay | Sensitivity Explorer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stButton>button {
        border-radius: 5px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📊 DutchBay Sensitivity Explorer")
st.markdown(
    "Interactive scenario analysis and risk modeling for renewable energy projects."
)

# Sidebar for inputs
with st.sidebar:
    st.image(
        "https://raw.githubusercontent.com/arunakulat/dutchbay-epc-model/v14chat/docs/assets/logo.png",
        width=200,
    )  # Placeholder if logo exists, or just branding
    st.header("Project Configuration")

    # Scenario Selector
    scenario_dir = "scenarios"
    try:
        scenario_files = [
            f for f in os.listdir(scenario_dir) if f.endswith((".yaml", ".yml"))
        ]
        default_idx = (
            scenario_files.index("dutchbay_lendercase_2025Q4.yaml")
            if "dutchbay_lendercase_2025Q4.yaml" in scenario_files
            else 0
        )

        selected_file = st.selectbox(
            "Base Scenario",
            scenario_files,
            index=default_idx,
            help="Choose the baseline configuration for analysis.",
        )
        config_path = os.path.join(scenario_dir, selected_file)
    except Exception:
        st.error("Could not load scenarios.")
        st.stop()

    st.divider()
    st.subheader("Sensitivity Drivers")

    st.info("Define the range for key project variables.")

    # We could make these dynamic, but for now we provide sliders that define the ParameterRangeConfig
    capex_range = st.slider(
        "CAPEX Variation (%)",
        5,
        50,
        20,
        step=5,
        help="Range for CAPEX sensitivity (Low/High)",
    )
    gen_range = st.slider(
        "Generation Variation (%)",
        5,
        30,
        10,
        step=5,
        help="Range for P50 generation sensitivity",
    )

    params = [
        ParameterRangeConfig(
            variable_name="project.capex_usd_per_kw",
            base_value=900.0,
            low_pct=-float(capex_range),
            high_pct=float(capex_range),
            points=3,
        ),
        ParameterRangeConfig(
            variable_name="generation.capacity_factor_pct",
            base_value=45.0,
            low_pct=-float(gen_range),
            high_pct=float(gen_range),
            points=3,
        ),
    ]

    st.divider()
    run_analysis = st.button(
        "Run Sensitivity Analysis", type="primary", use_container_width=True
    )

# Main Content Area
if run_analysis:
    with st.spinner("Running financial simulations..."):
        try:
            # Load and run
            base_cfg = load_scenario_config(config_path)

            # Execute Sensitivity Suite
            suite = run_sensitivity_analysis(
                base_config=base_cfg,
                base_config_path=config_path,
                parameters=params,
                metric_keys=["project_irr", "equity_irr"],
            )

            # Export to tables
            tables = suite_to_tables(suite)
            df = tables["tornado_rows"]

            # UI Layout for Results
            st.success("Analysis Complete")

            tab1, tab2 = st.tabs(["📈 Visualization", "📋 Raw Data"])

            with tab1:
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.subheader(
                        f"Tornado Analysis: {suite.metric.replace('_', ' ').upper()}"
                    )
                    fig = plot_tornado(table=df, title=f"Impact on {suite.metric}")
                    st.pyplot(fig)

                with col2:
                    st.subheader("Metric Summary")
                    meta = tables["metadata"]
                    st.metric(
                        "Base Project IRR",
                        f"{meta.get('base_kpis', {}).get('project_irr', 0)*100:.2f}%",
                    )
                    st.metric(
                        "Base Equity IRR",
                        f"{meta.get('base_kpis', {}).get('equity_irr', 0)*100:.2f}%",
                    )
                    st.metric(
                        "Min DSCR",
                        f"{meta.get('base_kpis', {}).get('min_dscr', 0):.2f}",
                    )

            with tab2:
                st.subheader("Detailed Sensitivity Results")
                st.dataframe(df, use_container_width=True)
                st.download_button(
                    "Download CSV",
                    df.to_csv(index=False).encode("utf-8"),
                    "sensitivity_results.csv",
                    "text/csv",
                )

        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")
            with st.expander("Show Technical Details"):
                st.exception(e)
else:
    # Empty State
    st.info(
        "👈 Select a scenario and adjust parameters in the sidebar, then click 'Run Sensitivity Analysis'."
    )

    # Placeholder for visual appeal
    st.image(
        "https://raw.githubusercontent.com/arunakulat/dutchbay-epc-model/v14chat/docs/assets/dashboard_preview.png",
        width=800,
    )  # If it exists
