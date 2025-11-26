from bowler import Query

(
    Query("calculate_scenario_kpis($args< any* >)")
    .file_paths([
        "analytics/scenario_analytics.py",
        "tests/api/test_metrics_core_stats.py",
        "tests/api/test_metrics_module.py",
        "tests/test_metrics_integration.py"
    ])
    .modify(
        lambda node, capture, filename:
            node.with_changes(
                args=[
                    arg.with_changes(prefix=f"{name}=")
                    for arg, name in zip(
                        list(capture["args"]),
                        ["annual_rows", "debt_result", "config", "discount_rate"]
                    )
                ]
                if len(capture["args"]) == 4 else list(capture["args"])
            )
    )
    .write()
)

