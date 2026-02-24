## 2026-02-24 - [Graceful Failure Pattern for Model Initialization]
**Learning:** In complex financial models where backend dependencies (like Pydantic contracts) are volatile or prone to corruption during refactoring, the Streamlit dashboard should implement a "Safe Mode" pattern. By wrapping core imports in a try-except block, the UI can remain interactive and provide troubleshooting guidance instead of showing a raw traceback.
**Action:** Always wrap volatile backend imports in a try-except block and provide an st.error/st.expander combination for identified failure modes.
