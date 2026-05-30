## 2026-05-30 - [Dashboard Interactivity Control]
**Learning:** In dashboards performing expensive financial simulations, users benefit from an explicit 'Run Analysis' action (implemented with `type="primary"` buttons) to avoid computation lag during iterative parameter adjustments.
**Action:** Use `st.button(..., type="primary")` for main calculation triggers in Streamlit apps to establish clear visual hierarchy and prevent accidental heavy re-runs.

## 2026-05-30 - [Scenario Selection UX]
**Learning:** For tool-based interfaces using configuration files, replacing manual path inputs with a dynamic `selectbox` (using `os.path.basename` for display) significantly reduces user error and cognitive load.
**Action:** Always provide a whitelist-based file selector if the application relies on local directory-based configurations.
