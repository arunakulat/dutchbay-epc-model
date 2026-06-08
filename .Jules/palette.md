# Palette's Journal - DutchBay EPC Model

## 2026-06-08 - Streamlit Dashboard Refactoring
**Learning:** The existing dashboard was using deprecated and non-existent APIs, leading to a complete failure of the UI. For financial modeling tools, providing a list of available scenarios via a dropdown is much more user-friendly than requiring a manual path entry.
**Action:** Use `st.selectbox` with a filtered list of `.yaml` files from the `scenarios/` directory. Organize configuration inputs in `st.sidebar` to keep the main results area focused and clean.
