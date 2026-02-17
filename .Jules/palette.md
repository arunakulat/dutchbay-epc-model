## 2025-12-23 - Safe Mode / Graceful Failure Pattern for Streamlit
**Learning:** In financial modeling tools where backends are volatile or computationally expensive, wrapping core imports in a try-except block (Safe Mode) prevents raw tracebacks and provides a professional troubleshooting UI. This is critical for maintainability and user trust.
**Action:** Always wrap volatile backend imports in Streamlit apps and provide an 'st.expander' with troubleshooting steps for identified failure modes (e.g., SyntaxError in contracts).
