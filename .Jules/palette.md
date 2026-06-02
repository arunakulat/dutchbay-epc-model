## 2026-06-02 - [Scenario Selection via Selectbox]
**Learning:** Replacing free-text path inputs with a directory-aware `st.selectbox` prevents navigation errors and improves discoverability of available scenario configurations.
**Action:** Always prefer `st.selectbox` with a whitelist of valid configuration files (e.g., from `scenarios/`) instead of `st.text_input` for file paths in Streamlit apps.
