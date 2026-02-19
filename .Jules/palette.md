## 2025-05-15 - Graceful Failure Pattern for Fragile Backends
**Learning:** In projects with frequent backend corruption or API shifts, a "Graceful Failure" pattern in the UI (wrapping imports in try-except and providing troubleshooting info) significantly improves the developer/user experience by replacing raw tracebacks with actionable guidance.
**Action:** Use an `st.error` coupled with an `st.expander` for technical details and an `st.info` for troubleshooting tips. Always call `st.stop()` to prevent cascading errors.
