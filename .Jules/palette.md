# Palette's Journal - Critical UX/Accessibility Learnings

## 2026-02-07 - Robust Backend Initialization for Streamlit Dashboards
**Learning:** Streamlit applications that tightly couple with a complex analytical backend can crash with a raw Python traceback if the backend has syntax errors or missing dependencies. This is intimidating for business users and provides poor UX for a "UI layer".
**Action:** Wrap top-level imports in a try-except block catching `ImportError` and `SyntaxError`. If an error occurs, display a polished `st.error` component with a clear title, actionable troubleshooting steps, and technical details for developers. Use `st.stop()` to prevent the rest of the app from running in a broken state.
