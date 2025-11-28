from analytics.sensitivity import (
    SensitivityRequest,
    plot_tornado_chart,
    run_tornado_sensitivity,
    tornado_suite_to_dataframe,
)

req = SensitivityRequest(
    "scenarios/dutchbay_lendercase_2025Q4.yaml",
    parameters=[...],  # Project-specific ParameterRangeConfig
    metric="project_irr",
)
suite = run_tornado_sensitivity(req)
df = tornado_suite_to_dataframe(suite)
plot_tornado_chart(suite, filename="exports/tornado_x.png")

# For advanced/risk use:

risk_df = enrich_tornado_with_tail_risk(suite, montecarlo_result)
pareto_results = optimize_from_sensitivity_insights(
    suite, req.base_config_path, objectives=["project_irr", "dscr_min"]
)
