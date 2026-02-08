## 2025-02-08 - Streamlit Spinner UX Pattern
**Learning:** Wrapping both computation and rendering in a single 'with st.spinner' block can lead to inconsistent UI updates where the spinner disappears before the data is fully rendered by the browser.
**Action:** Always separate computation (wrapped in spinner) from rendering (outside spinner) in Streamlit apps to ensure a smooth transition from 'loading' to 'data visible'.
