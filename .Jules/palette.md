## 2026-06-06 - [Streamlit Layout & Interaction]
**Learning:** For financial dashboards with expensive backends, using a primary "Run Analysis" button prevents UI lag and unnecessary computation during parameter adjustment, improving perceived performance.
**Action:** Always implement explicit execution triggers for long-running financial simulations.

## 2026-06-06 - [Streamlit Container Width Deprecation]
**Learning:** Streamlit version 1.58.0 deprecates `use_container_width` in `st.dataframe`.
**Action:** Use `width="stretch"` or follow latest Streamlit API guidelines for full-width components to ensure future compatibility.
