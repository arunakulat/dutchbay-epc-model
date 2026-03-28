## 2025-03-28 - Graceful Failure and Explicit Action in Financial Dashboards
**Learning:** In dashboards performing expensive financial simulations, users benefit from an explicit 'Run' action to avoid lag during parameter adjustment. Additionally, wrapping core logic in a styled error UI prevents technical jargon from overwhelming the user when backends are in a development/broken state.
**Action:** Implement 'Run Analysis' buttons with `type="primary"` for simulations and use try-except blocks around imports/orchestration to provide troubleshooting tips.
