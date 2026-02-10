## 2026-02-10 - [Interaction Gating & Graceful Failure]
**Learning:** In computationally expensive Streamlit dashboards, users find it frustrating when the UI re-triggers a heavy run on every minor input change (e.g., typing in a text field). Additionally, raw tracebacks from broken backend imports degrade trust.
**Action:** Always gate expensive calculations behind an explicit "Run" button with an `st.spinner`. Implement a "Graceful Failure" pattern by wrapping top-level imports in a `try-except` block to provide actionable troubleshooting guidance instead of a crash.
