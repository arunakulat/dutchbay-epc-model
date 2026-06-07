## 2026-06-07 - [Streamlit API & UX Patterns]
**Learning:** In Streamlit v1.58.0, users benefit from explicit action buttons ('Run Analysis') for compute-heavy tasks to avoid lag. Dataframe layout should use width="stretch" for full-width presentation.
**Action:** Always wrap expensive pipeline executions in a button and spinner for visual feedback.

## 2026-06-07 - [Graceful Failure UX]
**Learning:** Providing explicit success/error messaging in the dashboard prevents user confusion when the backend takes time to respond.
**Action:** Use st.success and st.error for all async-like operations.
