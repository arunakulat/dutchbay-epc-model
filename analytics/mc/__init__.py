"""analytics.mc - Canonical Monte Carlo analysis package.

Public API:
    MonteCarloEngine: Main engine class
    run_monte_carlo_analysis: Functional entrypoint
    CorrelationSpec: Correlation configuration
    load_correlation_from_config: Config loader

Usage:
    from analytics.mc import run_monte_carlo_analysis
    from analytics.mc.correlation import load_correlation_from_config
    
    config = load_yaml("scenario.yaml")
    corr = load_correlation_from_config(config)
    
    result = run_monte_carlo_analysis(
        base_config=config,
        n_trials=1000,
        seed=42,
        correlation=corr
    )
"""
from analytics.mc.correlation import CorrelationSpec, load_correlation_from_config
from analytics.mc.engine import MonteCarloEngine, run_monte_carlo_analysis

__all__ = [
    "MonteCarloEngine",
    "run_monte_carlo_analysis",
    "CorrelationSpec",
    "load_correlation_from_config",
]
