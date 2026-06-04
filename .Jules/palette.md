## 2026-06-04 - [Streamlit UX: Explicit Action & Robust Selection]
**Learning:** In dashboards performing expensive financial simulations, users benefit from an explicit 'Run Analysis' action (implemented with `type="primary"` buttons) to avoid computation lag during iterative parameter adjustments. Additionally, replacing free-text path inputs with a directory-scanning `st.selectbox` prevents invalid file errors and significantly improves accessibility.
**Action:** Always favor `st.selectbox` for file-based configuration selection and use primary buttons for heavy computational tasks.
