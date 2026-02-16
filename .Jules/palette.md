## 2025-11-25 - Graceful Failure Pattern for Dashboards
**Learning:** In dashboards tightly coupled with backend logic (like Streamlit apps), a broken backend (syntax errors, missing imports) can cause a total crash with cryptic tracebacks. Implementing a "Safe Mode" that catches these errors at the import level and displays actionable troubleshooting guidance significantly improves the developer and user experience.
**Action:** Always wrap core backend imports in Streamlit apps with a try-except block and use `st.stop()` with a helpful `st.error` message to provide a graceful fallback.

## 2025-11-25 - Sidebar Persistence with st.stop()
**Learning:** In Streamlit, if `st.stop()` is called before `with st.sidebar:`, the sidebar will not render at all.
**Action:** Render the sidebar content (or at least the shell) before calling `st.stop()` to ensure the user still has access to navigation or settings even during an error state.
