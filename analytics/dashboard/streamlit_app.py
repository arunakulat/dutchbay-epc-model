import streamlit as st
import traceback

st.set_page_config(page_title="DutchBay | Sensitivity Explorer", page_icon="📊", layout="wide")
st.title("📊 DutchBay Sensitivity Explorer")

BACKEND_OK = True
try:
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.sensitivity import run_sensitivity_analysis, suite_to_tables
except Exception as e:
    BACKEND_OK, stack_trace = False, traceback.format_exc()

with st.sidebar:
    st.header("⚙️ Configuration")
    config_path = st.text_input("Config Path", "scenarios/dutchbay_lendercase_2025Q4.yaml")
    st.info("Drivers: CAPEX (-20%/+20%), Capacity Factor (-10%/+10%)")
    run_clicked = st.button("🚀 Run Analysis", type="primary")

if not BACKEND_OK:
    st.error("### ⚠️ Model Initialization Failed")
    with st.expander("🔍 Technical Details"):
        st.code(stack_trace)
    st.info("💡 Tip: Check `analytics/contracts_v14.py` for syntax errors.")
    st.stop()

if run_clicked:
    with st.spinner("🔄 Orchestrating sensitivity runs..."):
        try:
            params = [
                ParameterRangeConfig(variable_name="project.capex_usd_per_kw", base_value=900.0, low_pct=-20, high_pct=20),
                ParameterRangeConfig(variable_name="generation.capacity_factor_pct", base_value=45.0, low_pct=-10, high_pct=10)
            ]
            suite = run_sensitivity_analysis(base_config_path=config_path, parameters=params, metric_keys=["project_irr"])
            df = suite_to_tables(suite)["tornado_rows"]
            st.subheader("📈 Analysis Results")
            st.dataframe(df, use_container_width=True)
            st.success("Analysis complete! Visual charts are available in the 'exports/' directory.")
        except Exception as e:
            st.error(f"Analysis failed: {e}")
else:
    st.info("👈 Click **Run Analysis** to begin.")
