## 2026-05-17 - [Explicit Action for Expensive Computations]
**Learning:** In dashboards performing expensive financial simulations (like sensitivity sweeps), users benefit from an explicit 'Run Analysis' action (implemented with `st.button(..., type="primary")`) rather than automatic re-triggering. This prevents UI lag during parameter adjustment and provides a clear interaction target.
**Action:** Always use an explicit primary button for high-latency orchestration tasks in Streamlit dashboards.
