"""Research-grade multi-objective capital-structure optimiser (restored V12 model).

This package hosts the standalone V12 financial model (legacy_v12) + Pareto chart
helpers (charts) that the multi-objective optimiser (optimization) depends on. The
model is self-contained (numpy/pandas/scipy only) and independent of the live v14
engine; it powers exploratory capital-structure Pareto studies, not the canonical
pipeline (which uses analytics.optimization_v14).
"""
