## 2025-11-24 - Graceful Failure Pattern for Streamlit Dashboards
**Learning:** In a configuration-driven, modular app where the backend/analytics layer is volatile or prone to corruption (e.g., during active development or merge conflicts), a raw Python traceback in the UI is highly disruptive. Wrapping core imports in a `try-except` block for `SyntaxError` and `ImportError` allows the app to stay alive and provide specific troubleshooting guidance to the user.
**Action:** Always wrap volatile backend imports in Streamlit apps and use `st.error` + `st.info` with specific troubleshooting steps (e.g., "Check X file for syntax errors").

## 2025-11-24 - Interaction Control for Expensive Computations
**Learning:** Streamlit's default behavior of re-running on every input change is detrimental for expensive financial simulations. Users prefer an explicit "Run" button to trigger analysis once they have finished configuring all parameters.
**Action:** Use `if st.button("Run ..."):` to gate expensive analytics blocks.
