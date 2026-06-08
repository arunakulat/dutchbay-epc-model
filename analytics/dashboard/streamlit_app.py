import streamlit as st
import glob
from omegaconf import OmegaConf
from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity import run_sensitivity_analysis, suite_to_tables
from analytics.sensitivity.viz import plot_tornado

st.set_page_config(page_title="Sensitivity Dashboard", layout="wide")
st.title("🎨 Sensitivity Explorer")

with st.sidebar:
    st.header("Settings")
    yaml_files = sorted(glob.glob("scenarios/*.yaml"))
    default_idx = yaml_files.index("scenarios/dutchbay_lendercase_2025Q4.yaml") if "scenarios/dutchbay_lendercase_2025Q4.yaml" in yaml_files else 0
    config_path = st.selectbox("Scenario", yaml_files, index=default_idx)

    st.subheader("Parameters")
    params = [
        ParameterRangeConfig("project.capex_usd_per_kw", 900.0, low_pct=-20, high_pct=20),
        ParameterRangeConfig("generation.capacity_factor_pct", 45.0, low_pct=-10, high_pct=10),
    ]
    for p in params:
        st.caption(f"📌 {p.variable_name} ({p.low_pct}% to {p.high_pct}%)")

if st.button("Run Analysis", type="primary"):
    with st.spinner("Analyzing..."):
        try:
            cfg = OmegaConf.to_container(OmegaConf.load(config_path), resolve=True)
            suite = run_sensitivity_analysis(
                base_config=cfg,
                base_config_path=config_path,
                parameters=params,
                metric_keys=["project_irr"]
            )
            df = suite_to_tables(suite)["tornado_rows"]

            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Data")
                st.dataframe(df, use_container_width=True)
            with c2:
                st.subheader("Visualization")
                st.pyplot(plot_tornado(table=df, title=f"Impact on {suite.metric}"))
        except Exception as e:
            st.error(f"Analysis failed: {e}")
else:
    st.info("Adjust settings in the sidebar and click 'Run Analysis'.")
