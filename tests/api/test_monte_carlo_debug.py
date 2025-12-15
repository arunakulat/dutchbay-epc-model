# tests/api/test_monte_carlo_debug.py
# SPRINT 10 DEBUG TEST - Comprehensive error visibility

from __future__ import annotations

import json
import logging
import sys
import traceback
from pathlib import Path
from typing import Any, Dict

import pytest

# Set up verbose logging to stdout
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)

logger = logging.getLogger(__name__)

from analytics.monte_carlo_v14 import run_monte_carlo

MC_CONFIG_PATH = Path("config/monte_carlo_regression_toy.yaml")
BASE_SCENARIO_CONFIG = Path("scenarios/dutchbay_lendercase_2025Q4.yaml")


class DebugError(Exception):
    """Custom exception for debug output."""
    pass


def _dump_error(msg: str, exc: Exception | None = None) -> None:
    """
    Dump error message and traceback to stdout with maximum visibility.
    """
    print(f"\n{'='*80}", file=sys.stdout, flush=True)
    print(f"ERROR: {msg}", file=sys.stdout, flush=True)
    print(f"{'='*80}", file=sys.stdout, flush=True)
    
    if exc:
        print(f"Exception Type: {type(exc).__name__}", file=sys.stdout, flush=True)
        print(f"Exception Message: {str(exc)}", file=sys.stdout, flush=True)
        print(f"\nFull Traceback:", file=sys.stdout, flush=True)
        traceback.print_exc(file=sys.stdout)
    
    print(f"{'='*80}\n", file=sys.stdout, flush=True)
    sys.stdout.flush()


def _result_to_dict(mc_result: Any) -> Dict[str, Any]:
    """Convert MonteCarloResult to dict for inspection."""
    if hasattr(mc_result, "model_dump"):
        return mc_result.model_dump()
    if hasattr(mc_result, "dict"):
        return mc_result.dict()  # type: ignore[call-arg]
    if hasattr(mc_result, "__dict__"):
        return dict(mc_result.__dict__)
    return {"_repr": repr(mc_result)}


@pytest.mark.slow
def test_monte_carlo_debug_imports() -> None:
    """
    TEST 1: Verify all imports work and modules are accessible.
    """
    print("\n" + "="*80, flush=True)
    print("TEST 1: Import Verification", flush=True)
    print("="*80, flush=True)
    
    try:
        from analytics.monte_carlo_v14 import (
            run_monte_carlo,
            run_monte_carlo_analysis,
            _thread_safe_iteration_worker,
            _run_parallel_iterations,
            _run_serial_iterations,
            _run_single_iteration,
        )
        print("✅ All imports successful", flush=True)
        print(f"  - run_monte_carlo: {run_monte_carlo}", flush=True)
        print(f"  - run_monte_carlo_analysis: {run_monte_carlo_analysis}", flush=True)
        print(f"  - _thread_safe_iteration_worker: {_thread_safe_iteration_worker}", flush=True)
        print(f"  - _run_parallel_iterations: {_run_parallel_iterations}", flush=True)
        sys.stdout.flush()
    except Exception as exc:
        _dump_error("Import failed", exc)
        raise


@pytest.mark.slow
def test_monte_carlo_debug_config_loading() -> None:
    """
    TEST 2: Verify config files exist and can be loaded.
    """
    print("\n" + "="*80, flush=True)
    print("TEST 2: Config File Verification", flush=True)
    print("="*80, flush=True)
    
    try:
        mc_path = Path(MC_CONFIG_PATH)
        base_path = Path(BASE_SCENARIO_CONFIG)
        
        print(f"MC Config path: {mc_path.absolute()}", flush=True)
        print(f"MC Config exists: {mc_path.exists()}", flush=True)
        
        print(f"\nBase Scenario path: {base_path.absolute()}", flush=True)
        print(f"Base Scenario exists: {base_path.exists()}", flush=True)
        
        if not mc_path.exists():
            raise FileNotFoundError(f"MC config not found: {mc_path}")
        if not base_path.exists():
            raise FileNotFoundError(f"Base scenario config not found: {base_path}")
        
        # Try to load configs
        import yaml
        with open(mc_path) as f:
            mc_config = yaml.safe_load(f)
        print(f"\n✅ MC Config loaded successfully", flush=True)
        print(f"  Keys: {list(mc_config.keys())}", flush=True)
        print(f"  Simulation config: {mc_config.get('simulation')}", flush=True)
        
        with open(base_path) as f:
            base_config = yaml.safe_load(f)
        print(f"\n✅ Base scenario config loaded successfully", flush=True)
        print(f"  Keys: {list(base_config.keys())}", flush=True)
        
        sys.stdout.flush()
    except Exception as exc:
        _dump_error("Config loading failed", exc)
        raise


@pytest.mark.slow
def test_monte_carlo_debug_single_run() -> None:
    """
    TEST 3: Run Monte Carlo with full error visibility.
    """
    print("\n" + "="*80, flush=True)
    print("TEST 3: Single Monte Carlo Run (write_output=False)", flush=True)
    print("="*80, flush=True)
    
    try:
        print(f"\nStarting run_monte_carlo with:", flush=True)
        print(f"  mc_config_path: {MC_CONFIG_PATH}", flush=True)
        print(f"  base_config_path: {BASE_SCENARIO_CONFIG}", flush=True)
        print(f"  write_output: False", flush=True)
        print(f"  (Starting at {__import__('datetime').datetime.now()})", flush=True)
        sys.stdout.flush()
        
        results = run_monte_carlo(
            mc_config_path=str(MC_CONFIG_PATH),
            base_config_path=str(BASE_SCENARIO_CONFIG),
            write_output=False,
        )
        
        print(f"\n✅ run_monte_carlo completed successfully", flush=True)
        print(f"  Scenarios returned: {list(results.keys())}", flush=True)
        print(f"  (Completed at {__import__('datetime').datetime.now()})", flush=True)
        
        # Dump all results to stdout
        for scenario_name, mc_result in results.items():
            print(f"\n--- Scenario: {scenario_name} ---", flush=True)
            result_dict = _result_to_dict(mc_result)
            print(json.dumps(result_dict, indent=2, default=str), flush=True)
        
        sys.stdout.flush()
        
    except Exception as exc:
        _dump_error(f"run_monte_carlo failed", exc)
        raise


@pytest.mark.slow
def test_monte_carlo_debug_parallel_vs_serial() -> None:
    """
    TEST 4: Compare parallel (P1.3) vs serial execution to identify bottleneck.
    """
    print("\n" + "="*80, flush=True)
    print("TEST 4: Parallel vs Serial Performance Comparison", flush=True)
    print("="*80, flush=True)
    
    import time
    
    try:
        # Test with serial execution
        print(f"\nRunning SERIAL test...", flush=True)
        start_serial = time.time()
        
        results_serial = run_monte_carlo(
            mc_config_path=str(MC_CONFIG_PATH),
            base_config_path=str(BASE_SCENARIO_CONFIG),
            write_output=False,
            parallel_workers=1,  # Force serial
        )
        
        time_serial = time.time() - start_serial
        print(f"✅ SERIAL completed in {time_serial:.2f}s", flush=True)
        print(f"  Scenarios: {list(results_serial.keys())}", flush=True)
        sys.stdout.flush()
        
        # Test with parallel execution (P1.3)
        print(f"\nRunning PARALLEL test (4 workers)...", flush=True)
        start_parallel = time.time()
        
        results_parallel = run_monte_carlo(
            mc_config_path=str(MC_CONFIG_PATH),
            base_config_path=str(BASE_SCENARIO_CONFIG),
            write_output=False,
            parallel_workers=4,  # Use threading
        )
        
        time_parallel = time.time() - start_parallel
        print(f"✅ PARALLEL completed in {time_parallel:.2f}s", flush=True)
        print(f"  Scenarios: {list(results_parallel.keys())}", flush=True)
        
        # Compare
        speedup = time_serial / time_parallel
        slowdown = time_parallel / time_serial
        
        print(f"\n--- PERFORMANCE ANALYSIS ---", flush=True)
        print(f"Serial time:    {time_serial:.2f}s", flush=True)
        print(f"Parallel time:  {time_parallel:.2f}s", flush=True)
        print(f"Ratio:          {slowdown:.2f}x", flush=True)
        
        if speedup > 1.0:
            print(f"✅ Speedup:      {speedup:.2f}x (GOOD)", flush=True)
        else:
            print(f"⚠️  SLOWDOWN:     {slowdown:.2f}x (BAD - P1.3 threading is slower!)", flush=True)
        
        sys.stdout.flush()
        
    except Exception as exc:
        _dump_error("Performance comparison failed", exc)
        raise


@pytest.mark.slow
def test_monte_carlo_debug_thread_worker() -> None:
    """
    TEST 5: Test the thread worker function directly to isolate issues.
    """
    print("\n" + "="*80, flush=True)
    print("TEST 5: Direct Thread Worker Test", flush=True)
    print("="*80, flush=True)
    
    try:
        from analytics.monte_carlo_v14 import (
            _thread_safe_iteration_worker,
            _load_monte_carlo_config,
            _load_scenarios,
        )
        
        print(f"\nLoading MC config...", flush=True)
        mc_config = _load_monte_carlo_config(str(MC_CONFIG_PATH))
        print(f"✅ MC config loaded", flush=True)
        
        print(f"\nLoading scenarios...", flush=True)
        scenarios = _load_scenarios(mc_config, None)
        print(f"✅ {len(scenarios)} scenario(s) loaded", flush=True)
        
        if scenarios:
            scenario = scenarios[0]
            print(f"\nTesting worker with scenario: {scenario.name}", flush=True)
            
            # Create a simple test sample
            test_sample = {f"param_{i}": 0.5 for i in range(3)}
            print(f"  Test sample: {test_sample}", flush=True)
            
            # Call worker directly
            print(f"\nCalling _thread_safe_iteration_worker...", flush=True)
            result = _thread_safe_iteration_worker(
                iteration_idx=0,
                base_config_path=str(BASE_SCENARIO_CONFIG),
                scenario=scenario,
                sample=test_sample,
                write_output=False,
            )
            
            idx, result_data = result
            print(f"✅ Worker returned: idx={idx}, result={'PASS' if result_data else 'FAIL'}", flush=True)
            
            if result_data:
                print(f"  Result keys: {list(result_data.keys())}", flush=True)
                print(f"  Sample values: {dict(list(result_data.items())[:3])}", flush=True)
            else:
                print(f"  ⚠️  Result was None (iteration failed)", flush=True)
        
        sys.stdout.flush()
        
    except Exception as exc:
        _dump_error("Thread worker test failed", exc)
        raise


if __name__ == "__main__":
    # Allow running directly: python tests/api/test_monte_carlo_debug.py
    pytest.main([__file__, "-v", "-s", "--tb=short"])
