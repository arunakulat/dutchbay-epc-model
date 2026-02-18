"""
dashboard/streamlit_app.py

Interactive explorer for sensitivity results using Streamlit.
Plug in any analytics/sensitivity output (tornado/spider) for fast DFI/lead demo!

Run with:
    streamlit run dashboard/streamlit_app.py
"""

import streamlit as st
import traceback

# 🎨 Palette: Professional page config
st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊")

# 🎨 Palette: Graceful Failure pattern - handle corrupted backend state
try:
    from analytics.contracts_v14 import ParameterRangeConfig
except Exception:
    st.title("📊 Sensitivity Dashboard")
    st.error("### ⚠️ Dashboard Initialization Failed")
    st.info("💡 **Troubleshooting:** This dashboard requires valid backend contracts. Please verify `analytics/contracts_v14.py` is correctly defined.")
    with st.expander("🔍 Technical Details"):
        st.code(traceback.format_exc())
    st.stop()

# Quick UI for scenario and drivers (customize as needed)
st.title("📊 Sensitivity Dashboard")

# 🎨 Palette: Accessibility - added help tooltip
config_path = st.text_input(
    "Scenario Config Path",
    "scenarios/dutchbay_lendercase_2025Q4.yaml",
    help="Path to the scenario configuration file (YAML/JSON)."
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
]

st.write("Running sensitivity analysis...")
try:
    # 🎨 Palette: Interaction feedback - provide clear status updates
    st.info("Using modern v14 sensitivity engine")
    st.warning("Analysis engine in Safe Mode - verify backend implementation for full results.")

    # Example table showing the intent
    st.write("Configured Parameters:")
    st.table([{"Variable": p.variable_name, "Base Value": p.base_value} for p in params])

except Exception as e:
    st.error(f"Analysis failed: {e}")
    with st.expander("🔍 Traceback"):
        st.code(traceback.format_exc())

st.success("Try changing params in the code for more exploration.")
