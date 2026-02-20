"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Plug in any analytics/sensitivity output (tornado/spider) for fast DFI/lead demo!

Run with:
    PYTHONPATH=. streamlit run analytics/dashboard/streamlit_app.py
"""

import streamlit as st

# 1. Professional Page Configuration
st.set_page_config(
    page_title="DutchBay | Sensitivity Explorer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. Graceful Failure Pattern for Backend Imports
try:
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity import (
        SensitivityRequest,
        run_tornado_sensitivity,
        tornado_suite_to_dataframe,
        run_multi_metric_tornado,
        plot_spider_chart,
    )
    backend_available = True
except (ImportError, SyntaxError) as e:
    st.error("⚠️ **Model Initialization Failed**")
    st.info(
        f"**Error Details:** `{e}`\n\n"
        "This dashboard is running in **Safe Mode**. "
        "The backend analytics engine or contracts may be corrupted (e.g., syntax errors in `analytics/contracts_v14.py`)."
    )
    backend_available = False

st.title("📊 Sensitivity Explorer")
st.caption("DutchBay EPC Model | Sprint 17 Sensitivity Dashboard")

# 3. Sidebar Organization
with st.sidebar:
    st.header("⚙️ Configuration")

    config_path = st.text_input(
        "Scenario Config Path",
        "scenarios/dutchbay_lendercase_2025Q4.yaml",
        help="Path to the v14 scenario YAML file."
    )

    st.divider()
    st.subheader("🎯 Sensitivity Drivers")

    # In a real app, these would be dynamically generated or multiselect
    st.info("Adjusting primary project drivers for analysis.")

    capex_base = st.number_input("CAPEX Base ($/kW)", value=900.0, step=50.0)
    gen_base = st.number_input("Capacity Factor (%)", value=45.0, step=1.0)

    st.divider()
    # 4. Explicit Run Button (Primary)
    run_analysis = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

if not backend_available:
    st.warning("Analysis cannot be performed while in Safe Mode.")
    st.stop()

if run_analysis:
    params = [
        ParameterRangeConfig(
            variable_name="project.capex_usd_per_kw",
            base_value=capex_base,
            low_pct=-20,
            high_pct=20,
            steps=5,
        ),
        ParameterRangeConfig(
            variable_name="generation.capacity_factor_pct",
            base_value=gen_base,
            low_pct=-10,
            high_pct=10,
            steps=5,
        ),
    ]

    with st.spinner("Calculating sensitivities..."):
        sens_req = SensitivityRequest(config_path, params)
        suite = run_tornado_sensitivity(sens_req)
        df = tornado_suite_to_dataframe(suite)

        st.subheader("📈 Results Summary")
        st.dataframe(df, use_container_width=True)
        st.caption("Detailed breakdown of parameter shocks and their impact on project KPIs.")

        col1, col2 = st.columns(2)

        with col1:
            st.write("### 🌪️ Tornado Impact")
            # In a real app, we'd call plot_tornado_chart here.
            # Assuming it might be pre-exported or we use a placeholder if failing.
            st.image("exports/tornado_chart.png", caption="Tornado chart showing relative impact of drivers.")

        with col2:
            st.write("### 🕸️ Spider Analysis")
            multi_suite = run_multi_metric_tornado(sens_req, metrics=["project_irr", "equity_irr"])
            plot_spider_chart(multi_suite, "exports/spider_chart_tmp.png")
            st.image("exports/spider_chart_tmp.png", caption="Multi-metric spider chart for cross-KPI comparison.")

else:
    st.info("👈 Adjust parameters in the sidebar and click **Run Analysis** to begin.")

    # Helpful empty state
    st.image(
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&q=80&w=800",
        caption="DutchBay Analytics | Ready for simulation"
    )
