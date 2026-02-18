## 2025-05-22 - [Graceful Failure Pattern for Streamlit]
**Learning:** In environments with volatile backend dependencies (like corrupted Pydantic contracts), wrapping core imports in a `try-except` block allows the dashboard to render a user-friendly "Safe Mode" UI. This prevents raw tracebacks from reaching the user and provides actionable troubleshooting guidance.
**Action:** Always wrap initialization-critical imports in a `try-except` block for Streamlit dashboards and use `st.stop()` to prevent downstream execution of broken logic.

## 2025-05-22 - [Explicit Trigger for Expensive Analytics]
**Learning:** Automatically re-running complex sensitivity analyses on every input change causes UI lag and poor UX.
**Action:** Move heavy computations behind an explicit "Run Analysis" button paired with `st.spinner` to give users control and clear visual feedback during wait times.
