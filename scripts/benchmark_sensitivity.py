#!/usr/bin/env python3
"""Performance benchmarking for sensitivity analysis."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity_v14 import SensitivityRequest, run_tornado_sensitivity


def benchmark_tornado(n_params: int):
    """Benchmark with N parameters."""
    params = [
        ParameterRangeConfig(
            variable_name=f"finance.param_{i}",
            base_value=100.0,
            low_pct=-10.0,
            high_pct=10.0,
        )
        for i in range(n_params)
    ]

    request = SensitivityRequest(
        base_config_path="scenarios/test/base_scenario.yaml",
        parameters=params,
        metric="project_irr",
    )

    start = time.perf_counter()
    suite = run_tornado_sensitivity(request)
    elapsed = time.perf_counter() - start

    return {"n_params": n_params, "elapsed": elapsed, "per_param": elapsed / n_params}


if __name__ == "__main__":
    print("Sensitivity Analysis Benchmark")
    print("=" * 50)

    for n in [1, 2, 5, 10]:
        result = benchmark_tornado(n)
        print(
            f"{n:3d} params: {result['elapsed']:.3f}s ({result['per_param']:.3f}s/param)"
        )

    print("\n✅ Benchmark complete!")
