## 2025-11-24 - [Graceful Failure Pattern in Streamlit]
**Learning:** In Streamlit, top-level imports are a major point of failure if the backend is corrupted. Wrapping these in a try-except block and using `st.stop()` prevents ugly tracebacks.
**Action:** Always call `st.set_page_config` and `st.title` before any potentially failing imports to ensure the user at least sees the application branding and a clear error message.
