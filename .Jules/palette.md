## 2025-05-22 - [Graceful Failure Pattern for Streamlit]
**Learning:** In dashboards with volatile backend dependencies (like corrupted contracts or shifting APIs), wrapping core imports in a `try-except` block to provide a "Safe Mode" UI prevents a complete application crash and maintains user trust.
**Action:** Always wrap top-level backend imports in Streamlit apps and use `st.stop()` after displaying a friendly error message to halt execution safely while keeping the UI responsive.

## 2025-05-22 - [Streamlit Performance UX]
**Learning:** Users can trigger expensive re-calculations accidentally when inputs are linked directly to execution. An explicit "Run Analysis" button with `type="primary"` improves both performance and UX by providing a clear intentional action.
**Action:** Use a primary button to gate expensive computations in Streamlit dashboards, especially when multiple parameters are adjustable.
