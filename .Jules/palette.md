## 2026-01-31 - [Absolute Value Constraints in UI Input]
**Learning:** In financial sensitivity models using Pydantic, parameters like "low_pct" (percentage decrease) are often enforced as absolute non-negative values (ge=0). Inputting negative values in the UI (e.g., -20 to represent a 20% drop) causes immediate validation crashes.
**Action:** Always verify Pydantic constraints in contracts before setting default values in the UI, and use tooltips or labels to clarify that absolute values are expected.

## 2026-01-31 - [Streamlit Page Config Order]
**Learning:** Streamlit requires `st.set_page_config` to be the absolute first Streamlit command in the entrypoint script. Any other UI call (like `st.title`) before it will cause a script error.
**Action:** Ensure branding and page metadata are initialized immediately after imports to guarantee a consistent user experience.
