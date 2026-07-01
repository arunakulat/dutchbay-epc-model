"""analytics/dashboard/streamlit_app.py

Interactive tornado-sensitivity explorer for v14 scenarios.

Runs the canonical engine
``analytics.core.sensitivity_runner.run_sensitivity_analysis`` — the SAME engine
the FastAPI ``/run-tornado/`` endpoint uses — and renders the result via
``analytics.sensitivity.export.suite_to_records``. No pre-exported images and no
removed/renamed APIs (the previous version imported five symbols that no longer
exist; this is the cleaned rewrite).

Run with:
    streamlit run analytics/dashboard/streamlit_app.py
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.core.sensitivity_runner import run_sensitivity_analysis
from analytics.sensitivity.export import suite_to_records

st.set_page_config(page_title="DutchBay v14 — Sensitivity Explorer", layout="wide")
st.title("DutchBay v14 — Tornado Sensitivity Explorer")
st.caption(
    "One-way tornado over the canonical v14 finance engine. Same engine as the "
    "FastAPI /run-tornado/ endpoint (analytics.core.sensitivity_runner)."
)

config_path = st.text_input(
    "Scenario config path", "scenarios/dutchbay_lendercase_2025Q4.yaml"
)
metric = st.selectbox(
    "Target metric",
    ["project_irr", "equity_irr", "project_npv", "min_dscr", "llcr", "plcr"],
    index=0,
)

st.markdown(
    "**Driver ranges** — edit base/low/high (absolute values); add rows as needed."
)
DEFAULT_PARAMS = pd.DataFrame(
    [
        {
            "variable_name": "tariff.lkr_per_kwh",
            "base_value": 20.3,
            "low_value": 16.0,
            "high_value": 24.0,
        },
        {
            "variable_name": "project.capacity_factor",
            "base_value": 0.339,
            "low_value": 0.30,
            "high_value": 0.37,
        },
        {
            "variable_name": "fx.start_lkr_per_usd",
            "base_value": 333.79,
            "low_value": 300.0,
            "high_value": 367.0,
        },
    ]
)
params_df = st.data_editor(DEFAULT_PARAMS, num_rows="dynamic", use_container_width=True)


def _build_params(df: pd.DataFrame) -> List[ParameterRangeConfig]:
    out: List[ParameterRangeConfig] = []
    for _, row in df.iterrows():
        name = str(row.get("variable_name") or "").strip()
        if not name:
            continue
        out.append(
            ParameterRangeConfig(
                variable_name=name,
                base_value=float(row["base_value"]),
                low_value=float(row["low_value"]),
                high_value=float(row["high_value"]),
            )
        )
    return out


if st.button("Run sensitivity", type="primary"):
    try:
        params = _build_params(params_df)
        if not params:
            st.warning("Add at least one driver with a variable_name.")
        else:
            suite = run_sensitivity_analysis(
                config_path, metric=metric, parameters=params
            )
            records: Dict[str, Any] = suite_to_records(suite)
            rows = records.get("tornado_rows", [])
            if not rows:
                st.warning(
                    "No tornado rows produced — check the config path and drivers."
                )
            else:
                df = pd.DataFrame(rows).sort_values("impact_abs", ascending=False)
                base = float(df["base_value"].iloc[0])
                st.subheader(f"Tornado — {metric} (base = {base:.4g})")
                st.dataframe(
                    df[
                        [
                            "parameter",
                            "base_value",
                            "low_value",
                            "high_value",
                            "impact_abs",
                        ]
                    ],
                    use_container_width=True,
                )
                st.bar_chart(df.set_index("parameter")["impact_abs"])
    except Exception as exc:  # surface engine/config errors in the UI, don't crash
        st.error(f"Sensitivity run failed: {exc}")
        st.exception(exc)
