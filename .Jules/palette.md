## 2025-02-07 - Graceful Backend Failure in Streamlit
**Learning:** In projects undergoing active refactoring or migration (like Pydantic V2), backend modules often break with `SyntaxError` or `ImportError`. Standard Streamlit behavior shows a raw traceback, which is intimidating for non-technical users. Wrapping imports and core logic in a `try...except` block with a styled `st.error` provides a much better UX and clear troubleshooting steps.
**Action:** Always wrap volatile backend imports in Streamlit dashboards to provide a polished failure state.
