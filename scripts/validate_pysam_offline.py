#!/usr/bin/env python3
"""Offline PySAM validation script (NO PIPELINE INTEGRATION).

Compares PySAM runner output against legacy cashflow_v14 generation formula.

Exit Codes
----------
0 : PySAM validated (<5% mean deviation) - SAFE TO INTEGRATE
1 : PySAM validation FAILED (>5% deviation) - DO NOT INTEGRATE
2 : PySAM not installed or resource file missing

Go-with-the-Flow Compliance
----------------------------
- ARCH-01: Config-first (hardcoded for POC, will use YAML in production)
- FIN-01: Numeric robustness (explicit deviation threshold)
- TYPE-01: Fully typed
- R17: Documented with Args/Returns
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

# Check PySAM availability
try:
    from analytics.pysam_sandbox import PYSAM_AVAILABLE, PySAMRunner
except ImportError:
    print("❌ analytics.pysam_sandbox not found")
    sys.exit(2)

if not PYSAM_AVAILABLE:
    print("❌ PySAM not installed. Install: pip install NREL-PySAM==5.1.0")
    sys.exit(2)


def legacy_aep_profile(
    capacity_mw: float,
    capacity_factor: float,
    degradation: float,
    years: int = 20,
) -> List[float]:
    """Legacy generation formula from cashflow_v14.py.

    Replicates _calculate_net_production() logic without grid losses.

    Parameters
    ----------
    capacity_mw : float
        Installed capacity (MW)
    capacity_factor : float
        Net capacity factor (decimal, e.g. 0.40)
    degradation : float
        Annual degradation rate (decimal, e.g. 0.006)
    years : int, default=20
        Project life

    Returns
    -------
    List[float]
        Annual gross generation (kWh) for years 1-20

    Notes
    -----
    Formula: capacity_mw * 1000 * cf * 8760 * (1 - degradation)^(year-1)
    """
    hours = 8760.0
    base = capacity_mw * 1000.0 * capacity_factor * hours

    return [base * ((1.0 - degradation) ** (year - 1)) for year in range(1, years + 1)]


def main() -> None:
    """Run offline PySAM validation."""
    # Test configuration (hardcoded for proof-of-concept)
    # In production, these will come from YAML config
    capacity_mw = 150.0
    capacity_factor = 0.40
    degradation = 0.006
    resource_file = "inputs/mannar_synthetic.srw"

    # Check resource file exists
    if not Path(resource_file).exists():
        print(f"❌ Resource file not found: {resource_file}")
        print("   Create with external notebook/MATLAB tool")
        print("   Example: NREL System Advisor Model (SAM) resource generator")
        sys.exit(2)

    # Legacy calculation
    print("Running legacy formula...")
    legacy_profile = legacy_aep_profile(capacity_mw, capacity_factor, degradation)

    # PySAM calculation
    print(f"Running PySAM with resource: {resource_file}")
    try:
        runner = PySAMRunner(resource_file, capacity_mw)
        pysam_profile = runner.get_annual_profile(degradation)
    except Exception as exc:
        print(f"❌ PySAM execution failed: {exc}")
        sys.exit(1)

    # Compare profiles
    deviations = [
        abs(pysam - legacy) / legacy * 100.0
        for pysam, legacy in zip(pysam_profile, legacy_profile)
    ]

    mean_dev = sum(deviations) / len(deviations)
    max_dev = max(deviations)

    # Print results
    print("\n" + "=" * 60)
    print("PySAM OFFLINE VALIDATION RESULTS")
    print("=" * 60)
    print(f"Config:")
    print(f"  Capacity:        {capacity_mw} MW")
    print(f"  Capacity Factor: {capacity_factor:.1%}")
    print(f"  Degradation:     {degradation:.2%}/year")
    print(f"\nYear 1 Generation:")
    print(f"  Legacy:  {legacy_profile[0] / 1e6:.2f} GWh")
    print(f"  PySAM:   {pysam_profile[0] / 1e6:.2f} GWh")
    print(f"\nDeviation Analysis:")
    print(f"  Mean Deviation: {mean_dev:.2f}%")
    print(f"  Max Deviation:  {max_dev:.2f}%")
    print(f"  Threshold:      5.00%")
    print("=" * 60)

    # Decision
    if mean_dev < 5.0:
        print("✅ VALIDATION PASSED - PySAM approved for integration")
        print("   Next step: Proceed to Day 4-5 (pipeline integration)")
        sys.exit(0)
    else:
        print("❌ VALIDATION FAILED - Deviation exceeds 5% threshold")
        print("   DO NOT INTEGRATE into pipeline")
        print("   Action required:")
        print("   1. Review resource file quality")
        print("   2. Check turbine power curve configuration")
        print("   3. Verify PySAM version (expect 5.1.0)")
        sys.exit(1)


if __name__ == "__main__":
    main()
