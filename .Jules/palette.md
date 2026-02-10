## 2025-01-24 - [Graceful Failure Pattern for Fragile Backends]
**Learning:** In Streamlit dashboards where backend logic is complex or volatile, wrapping core imports in a try-except block significantly improves UX by preventing raw tracebacks and providing actionable troubleshooting steps.
**Action:** Always wrap volatile imports and use st.error + st.stop() to handle initialization failures gracefully.

## 2025-01-24 - [Interaction Control for Heavy Computations]
**Learning:** Users prefer an explicit "Run" button over automatic execution for expensive financial simulations. This prevents UI "jank" and provides a clearer mental model of the analysis workflow.
**Action:** Gate heavy analytic functions behind a button and use st.spinner to provide immediate interaction feedback.
