## 2025-05-15 - [Graceful Failure Pattern for Streamlit]
**Learning:** Wrapping core imports and initialization in a try-except block with a "Safe Mode" UI significantly improves UX when working with volatile backend dependencies. It prevents a total app crash and provides actionable troubleshooting steps.
**Action:** Always wrap volatile backend imports in Streamlit apps and use `st.stop()` to prevent cascading errors while still showing branding/sidebar.
