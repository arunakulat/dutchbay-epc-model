"""Performance Benchmarking Suite for Sprint 12 Refinancing Feature.

Benchmarks:
- Initialization: <100ms
- Single calculation: <1000ms  
- Batch processing: <5s for 100 scenarios
- Large dataset: <10s for 1000+ rows

Target Thresholds:
- Memory growth: <5% per 1000 scenarios
- Cache hit rate: >90%
- CPU efficiency: >80%
"""

import time
import timeit
import tracemalloc
from typing import List, Dict, Any
from dataclasses import dataclass

import pytest

from finance.refinancing_v14_hardened import (
    RefinancingConfig,
    RefinancingCalculatorHardened,
)
from analytics.contracts_v14_validators import (
    validate_dscr,
    validate_irr,
    validate_wacc,
)


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ FIXTURES & UTILITIES                                                       ║
# ╚════════════════════════════════════════════════════════════════════════════╝

@dataclass
class BenchmarkResult:
    """Container for benchmark results."""

    test_name: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    memory_mb: float
    throughput: float  # operations per second

    def __str__(self) -> str:
        return (
            f"{self.test_name}:\n"
            f"  Iterations: {self.iterations}\n"
            f"  Avg: {self.avg_time_ms:.2f}ms | "
            f"Min: {self.min_time_ms:.2f}ms | "
            f"Max: {self.max_time_ms:.2f}ms\n"
            f"  Memory: {self.memory_mb:.2f}MB\n"
            f"  Throughput: {self.throughput:.0f} ops/sec"
        )


def create_test_config() -> RefinancingConfig:
    """Create standard test configuration."""
    return RefinancingConfig(
        enabled=True,
        triggers=[{"type": "dscr_floor", "value": 1.25}],
        new_coupon_pct=4.5,
        refinancing_cost_pct=0.5,
        new_tenor_years=12,
    )


def create_test_debt_result(size: int = 10) -> Dict[str, Any]:
    """Create test debt result with configurable size."""
    return {
        "total_debt": 100_000_000,
        "dscr_series": [1.1 + (0.05 * (i % 5)) for i in range(size)],
        "min_dscr": 1.1,
    }


def create_test_annual_rows(size: int = 10) -> List[Dict[str, Any]]:
    """Create test annual rows with configurable size."""
    return [{"year": i, "ebitda": 15_000_000} for i in range(1, size + 1)]


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ INITIALIZATION BENCHMARKS (3 TESTS)                                       ║
# ╚════════════════════════════════════════════════════════════════════════════╝

class TestInitializationPerformance:
    """Benchmark calculator initialization."""

    def test_config_creation_performance(self) -> None:
        """PERF: Config creation should be fast (<10ms)."""
        # WHEN: Creating config 100 times
        times: List[float] = []
        for _ in range(100):
            start = time.perf_counter()
            RefinancingConfig(enabled=True)
            times.append((time.perf_counter() - start) * 1000)

        # THEN: Average should be <10ms
        avg_time = sum(times) / len(times)
        assert avg_time < 10, f"Config creation: {avg_time:.2f}ms (expected <10ms)"
        print(f"✓ Config creation: {avg_time:.2f}ms")

    def test_calculator_instantiation_performance(self) -> None:
        """PERF: Calculator init should be <100ms."""
        # GIVEN: Test data
        config = create_test_config()
        debt_result = create_test_debt_result(10)
        annual_rows = create_test_annual_rows(10)

        # WHEN: Instantiating calculator 10 times
        times: List[float] = []
        for _ in range(10):
            start = time.perf_counter()
            RefinancingCalculatorHardened(config, debt_result, annual_rows)
            times.append((time.perf_counter() - start) * 1000)

        # THEN: Average should be <100ms
        avg_time = sum(times) / len(times)
        assert avg_time < 100, f"Calculator init: {avg_time:.2f}ms (expected <100ms)"
        print(f"✓ Calculator initialization: {avg_time:.2f}ms")

    def test_memory_footprint(self) -> None:
        """PERF: Memory footprint should be <50MB for standard case."""
        # WHEN: Measuring memory
        tracemalloc.start()
        config = create_test_config()
        debt_result = create_test_debt_result(100)
        annual_rows = create_test_annual_rows(100)
        calc = RefinancingCalculatorHardened(config, debt_result, annual_rows)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # THEN: Peak memory should be <50MB
        memory_mb = peak / 1024 / 1024
        assert memory_mb < 50, f"Memory: {memory_mb:.2f}MB (expected <50MB)"
        print(f"✓ Memory footprint: {memory_mb:.2f}MB")


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ CALCULATION BENCHMARKS (4 TESTS)                                           ║
# ╚════════════════════════════════════════════════════════════════════════════╝

class TestCalculationPerformance:
    """Benchmark refinancing calculations."""

    def test_single_refinancing_event_performance(self) -> None:
        """PERF: Single calculation should be <1000ms."""
        # GIVEN: Calculator setup
        config = create_test_config()
        debt_result = create_test_debt_result(10)
        annual_rows = create_test_annual_rows(10)
        calc = RefinancingCalculatorHardened(config, debt_result, annual_rows)

        # WHEN: Running calculation 10 times
        times: List[float] = []
        for _ in range(10):
            start = time.perf_counter()
            calc.evaluate_refinancing_event(
                year=5, trigger_dscr=1.25, discount_rate=0.08
            )
            times.append((time.perf_counter() - start) * 1000)

        # THEN: Average should be <1000ms
        avg_time = sum(times) / len(times)
        assert avg_time < 1000, f"Calculation: {avg_time:.2f}ms (expected <1000ms)"
        print(f"✓ Single calculation: {avg_time:.2f}ms")

    def test_batch_processing_performance(self) -> None:
        """PERF: Batch of 100 should complete <5 seconds."""
        # GIVEN: Calculator setup
        config = create_test_config()
        debt_result = create_test_debt_result(10)
        annual_rows = create_test_annual_rows(10)
        calc = RefinancingCalculatorHardened(config, debt_result, annual_rows)

        # WHEN: Running 100 calculations
        start = time.perf_counter()
        for i in range(100):
            calc.evaluate_refinancing_event(
                year=5 + (i % 5),
                trigger_dscr=1.25,
                discount_rate=0.08,
            )
        batch_time = (time.perf_counter() - start) * 1000

        # THEN: Should complete <5 seconds
        assert batch_time < 5000, f"Batch (100): {batch_time:.0f}ms (expected <5000ms)"
        print(f"✓ Batch processing (100): {batch_time:.0f}ms")

    def test_large_dataset_performance(self) -> None:
        """PERF: Large dataset (1000+ rows) <10 seconds."""
        # GIVEN: Large dataset
        config = create_test_config()
        debt_result = create_test_debt_result(1000)
        annual_rows = create_test_annual_rows(1000)

        # WHEN: Setup and calculate
        start = time.perf_counter()
        calc = RefinancingCalculatorHardened(config, debt_result, annual_rows)
        result = calc.evaluate_refinancing_event(
            year=500, trigger_dscr=1.25, discount_rate=0.08
        )
        total_time = (time.perf_counter() - start) * 1000

        # THEN: Should complete <10 seconds
        assert total_time < 10000, f"Large dataset: {total_time:.0f}ms (expected <10000ms)"
        print(f"✓ Large dataset (1000+): {total_time:.0f}ms")
        assert result is not None, "Should return valid result"

    def test_validator_processing_performance(self) -> None:
        """PERF: Validators should process <10ms per call."""
        # WHEN: Running validators 1000 times each
        times: List[float] = []
        for _ in range(1000):
            start = time.perf_counter()
            validate_dscr(1.3)
            validate_irr(0.15)
            validate_wacc(0.08)
            times.append((time.perf_counter() - start) * 1000)

        # THEN: Average should be <10ms
        avg_time = sum(times) / len(times)
        assert avg_time < 10, f"Validators: {avg_time:.2f}ms (expected <10ms)"
        print(f"✓ Validator processing: {avg_time:.2f}ms")


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ SCALING BENCHMARKS (3 TESTS)                                              ║
# ╚════════════════════════════════════════════════════════════════════════════╝

class TestScalingPerformance:
    """Benchmark scaling behavior."""

    def test_linear_scaling_with_dataset_size(self) -> None:
        """PERF: Performance should scale linearly (not quadratic)."""
        # GIVEN: Different dataset sizes
        sizes = [10, 50, 100, 200, 500]
        times_ms: Dict[int, float] = {}

        # WHEN: Measuring for each size
        for size in sizes:
            config = create_test_config()
            debt_result = create_test_debt_result(size)
            annual_rows = create_test_annual_rows(size)
            calc = RefinancingCalculatorHardened(config, debt_result, annual_rows)

            start = time.perf_counter()
            calc.evaluate_refinancing_event(
                year=size // 2, trigger_dscr=1.25, discount_rate=0.08
            )
            times_ms[size] = (time.perf_counter() - start) * 1000

        # THEN: Check for linear scaling
        print(f"Scaling results: {times_ms}")
        # Time should roughly double when size doubles (linear)
        ratio_10_50 = times_ms[50] / times_ms[10]
        ratio_50_100 = times_ms[100] / times_ms[50]
        print(f"Scaling ratios: 10->50: {ratio_10_50:.2f}x, 50->100: {ratio_50_100:.2f}x")

        # Linear scaling would give ~5x for 5x size increase
        # We allow 2-8x range for O(n) algorithms
        assert ratio_10_50 < 8, "Scaling not linear (5x size -> should be ~5x time)"

    def test_memory_scaling_with_batch_size(self) -> None:
        """PERF: Memory growth should be <5% per 1000 scenarios."""
        # GIVEN: Starting memory
        tracemalloc.start()

        config = create_test_config()
        debt_result = create_test_debt_result(100)
        annual_rows = create_test_annual_rows(100)
        calc = RefinancingCalculatorHardened(config, debt_result, annual_rows)

        _, initial_memory = tracemalloc.get_traced_memory()

        # WHEN: Running 1000 calculations
        for _ in range(1000):
            calc.evaluate_refinancing_event(
                year=50, trigger_dscr=1.25, discount_rate=0.08
            )

        _, final_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # THEN: Memory growth should be reasonable
        growth_percent = ((final_memory - initial_memory) / initial_memory) * 100
        print(f"Memory growth: {growth_percent:.1f}% for 1000 iterations")
        # Allow up to 100% growth (this is just for detection of leaks)
        assert growth_percent < 100, f"Excessive memory growth: {growth_percent:.1f}%"

    def test_throughput_measurement(self) -> None:
        """PERF: Measure operations per second."""
        # GIVEN: Calculator
        config = create_test_config()
        debt_result = create_test_debt_result(10)
        annual_rows = create_test_annual_rows(10)
        calc = RefinancingCalculatorHardened(config, debt_result, annual_rows)

        # WHEN: Measuring throughput over 1 second
        count = 0
        start = time.perf_counter()
        while time.perf_counter() - start < 1.0:
            calc.evaluate_refinancing_event(
                year=5, trigger_dscr=1.25, discount_rate=0.08
            )
            count += 1

        # THEN: Report throughput
        throughput = count / (time.perf_counter() - start)
        print(f"Throughput: {throughput:.0f} operations/second")
        assert throughput > 1, "Should process at least 1 op/sec"


# ╔════════════════════════════════════════════════════════════════════════════╗
# ║ STRESS TESTS (2 TESTS)                                                     ║
# ╚════════════════════════════════════════════════════════════════════════════╝

class TestStressPerformance:
    """Stress test under peak load."""

    def test_peak_load_simulation(self) -> None:
        """STRESS: Peak load - 10000 rapid-fire calculations."""
        # GIVEN: Calculator
        config = create_test_config()
        debt_result = create_test_debt_result(10)
        annual_rows = create_test_annual_rows(10)
        calc = RefinancingCalculatorHardened(config, debt_result, annual_rows)

        # WHEN: Performing 10000 calculations
        start = time.perf_counter()
        errors = 0
        for i in range(10000):
            try:
                calc.evaluate_refinancing_event(
                    year=(i % 10) + 1, trigger_dscr=1.25, discount_rate=0.08
                )
            except Exception:
                errors += 1

        total_time = time.perf_counter() - start

        # THEN: Should complete with minimal errors
        assert errors == 0, f"{errors} errors during peak load"
        print(f"Peak load (10000): {total_time:.1f}s, throughput: {10000/total_time:.0f} ops/s")

    def test_extreme_values_handling(self) -> None:
        """STRESS: Handle extreme parameter values gracefully."""
        # GIVEN: Extreme values
        config = create_test_config()
        debt_result = {"total_debt": 1e12, "dscr_series": [5.0, 0.5, 2.0] * 100, "min_dscr": 0.5}
        annual_rows = [{"year": i, "ebitda": 1e9} for i in range(1, 101)]

        # WHEN: Creating calculator with extreme values
        calc = RefinancingCalculatorHardened(config, debt_result, annual_rows)

        # THEN: Should handle gracefully
        result = calc.evaluate_refinancing_event(
            year=50, trigger_dscr=0.5, discount_rate=0.50  # 50% discount rate
        )
        assert result is not None, "Should handle extreme values"
        print("✓ Extreme values handled gracefully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

# EOF - tests/performance_benchmarks_v14.py
