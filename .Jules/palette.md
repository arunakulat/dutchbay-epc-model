## 2026-05-29 - [Streamlit Performance vs. Reactivity]
**Learning:** In dashboards performing expensive financial simulations, immediate reactive updates on every parameter change cause significant lag. Users prefer an explicit 'Run Analysis' action (implemented with `type="primary"` buttons) to maintain control and avoid computation overhead during iterative adjustments.
**Action:** Use a "Run" button pattern for any orchestration task taking > 500ms.

## 2026-05-29 - [Accessible File Selection]
**Learning:** For scenario selection, using `st.selectbox` with `format_func=os.path.basename` provides a clean display of file names while maintaining the full underlying path for configuration loading, improving both security (via whitelisting) and usability.
**Action:** Always whitelist scenario files and use `format_func` for cleaner UI labels.
