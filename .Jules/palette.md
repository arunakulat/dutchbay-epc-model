# Palette's Journal - DutchBay EPC Model

This journal documents critical UX and accessibility learnings discovered during the development of the DutchBay EPC Model interface.

## 2025-02-09 - [Graceful Failure Pattern]
**Learning:** In a complex environment where backend dependencies (like `analytics/contracts_v14.py`) might be corrupted or in a broken state, a raw Streamlit traceback is a poor UX. It intimidates non-technical users and provides no path forward.
**Action:** Implement a `try-except` wrapper around critical imports to show a user-friendly `st.error` with troubleshooting steps.
