"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Plug in any analytics/sensitivity output (tornado/spider) for fast DFI/lead demo!

Run with:
    streamlit run dashboard/streamlit_app.py
"""

import streamlit as st
import os

# Page configuration
st.set_page_config(
    page_title="DutchBay | Sensitivity Explorer",
    page_icon="📊",
    layout="wide"
)

# Safe Mode: Wrap imports to handle backend corruption gracefully
try:
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity import (
        SensitivityRequest,
        plot_spider_chart,
        run_multi_metric_tornado,
        run_tornado_sensitivity,
        tornado_suite_to_dataframe,
    )
    BACKEND_LOADED = True
except (ImportError, SyntaxError) as e:
    BACKEND_LOADED = False
    BACKEND_ERROR = str(e)

st.title("📊 Sensitivity Dashboard")

if not BACKEND_LOADED:
    st.error("⚠️ **Model Initialization Failed**")
    st.info(f"The analytics backend could not be loaded. Error: `{BACKEND_ERROR}`")
    with st.expander("🛠️ Troubleshooting Guidance"):
        st.markdown(f"""
        It looks like there's a syntax error or missing module in the core analytics engine.

        **Details:**
        ```
        {BACKEND_ERROR}
        ```

        **Recommended Actions:**
        1. Check `analytics/contracts_v14.py` for corruption (e.g. placeholder markers).
        2. Ensure all dependencies are installed: `pip install -r requirements_dev.txt`.
        3. Run `pytest` to identify specific failing contracts.
        """)

    # Render sidebar in disabled state for UI consistency
    with st.sidebar:
        st.header("⚙️ Configuration")
        st.warning("Configuration is unavailable while in Safe Mode.")
    st.stop()

# Sidebar for interactive controls
with st.sidebar:
    st.header("⚙️ Configuration")
    st.caption("Adjust scenario parameters and run analysis.")

    config_path = st.text_input(
        "Scenario Config Path",
        "scenarios/dutchbay_lendercase_2025Q4.yaml",
        help="Path to the YAML scenario configuration file."
    )

    st.subheader("Sensitivity Drivers")

    col1, col2 = st.columns(2)
    with col1:
        capex_low = st.number_input("CapEx Low %", value=-20, help="Lower bound percentage shock for CapEx")
    with col2:
        capex_high = st.number_input("CapEx High %", value=20, help="Upper bound percentage shock for CapEx")

    run_btn = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

# Main area for results
if run_btn:
    with st.spinner("🔄 Calculating sensitivity..."):
        # Define parameters based on UI input
        params = [
            ParameterRangeConfig(
                variable_name="project.capex_usd_per_kw",
                base_value=900.0,
                low_pct=capex_low,
                high_pct=capex_high,
                steps=5,
            ),
            ParameterRangeConfig(
                variable_name="generation.capacity_factor_pct",
                base_value=45.0,
                low_pct=-10,
                high_pct=10,
                steps=5,
            ),
        ]

        # Execute analysis
        sens_req = SensitivityRequest(config_path, params)
        suite = run_tornado_sensitivity(sens_req)
        df = tornado_suite_to_dataframe(suite)

        st.subheader("📈 Results Summary")
        st.dataframe(df)

        colA, colB = st.columns(2)

        with colA:
            st.subheader("🌪️ Tornado Chart")
            if os.path.exists("exports/tornado_chart.png"):
                st.image("exports/tornado_chart.png", caption="One-way sensitivity impact on key metrics.")
            else:
                st.info("Tornado chart image not yet generated.")

        with colB:
            st.subheader("🕸️ Spider Chart")
            multi_suite = run_multi_metric_tornado(sens_req, metrics=["project_irr", "equity_irr"])
            plot_spider_chart(multi_suite, "exports/spider_chart.png")
            if os.path.exists("exports/spider_chart.png"):
                st.image("exports/spider_chart.png", caption="Multi-metric sensitivity (Spider chart).")
            else:
                st.info("Spider chart image not yet generated.")

    st.success("✅ Analysis complete!")
else:
    st.info("👈 Adjust parameters in the sidebar and click **Run Analysis** to begin.")
