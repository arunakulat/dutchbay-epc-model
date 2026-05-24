## 2026-05-24 - [Interactive Sensitivity Dashboard Patterns]
**Learning:** In dashboards performing expensive financial simulations, users benefit from an explicit 'Run Analysis' action (implemented with `type="primary"` buttons) to avoid computation lag during iterative parameter adjustments. Active visual feedback via `st.spinner` is essential for maintaining perceived performance.
**Action:** Always use `st.spinner` for execution blocks > 1s and provide `help` tooltips for domain-specific parameters (like CAPEX or CF) to improve accessibility.
>>>>>>> REPLACE
