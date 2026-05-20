## 2026-05-20 - [Streamlit Scenario Selection UX]
**Learning:** Replacing a text input for file paths with an `st.selectbox` populated by a whitelist of valid scenario files significantly improves usability and prevents path traversal/typo errors.
**Action:** Always use interactive selection widgets for file-based configuration inputs in Streamlit dashboards.

## 2026-05-20 - [Run Analysis Button Pattern]
**Learning:** For expensive analytical operations, using an explicit 'Run Analysis' button (st.button with type="primary") prevents unnecessary re-calculations on every minor widget change, improving responsiveness.
**Action:** Implement explicit action triggers for heavy financial simulations to avoid UI lag.
