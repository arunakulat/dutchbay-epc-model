"""CAPEX top-down sanity check against the IRENA global onshore-wind benchmark.

Best practice (IRENA 2024) is to sanity-check a bottom-up cost stack against a top-down
global anchor: the weighted-average total installed cost of USD 1,041/kW (range
727-2,110/kW). This computes the project's $/kW and flags whether it sits in a plausible
band around that anchor. The benchmark lives in config/defaults.yaml (CCCDIR), never a
Python literal.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Tuple

_DEFAULTS_PATH = Path(__file__).resolve().parents[2] / "config" / "defaults.yaml"

# Plausible band around the IRENA weighted-average (its own published range is
# 727-2,110/kW; we flag outside ~0.6x-1.8x of the average as worth a second look).
_BAND_LO = 0.60
_BAND_HI = 1.80


@lru_cache(maxsize=1)
def irena_benchmark_per_kw() -> Tuple[float, int]:
    """The IRENA global onshore-wind TIC benchmark (USD/kW, year), from config/defaults.yaml."""
    import yaml

    data = yaml.safe_load(_DEFAULTS_PATH.read_text())
    ref = data["defaults"]["cost_reference"]
    return float(ref["irena_benchmark_per_kw"]), int(ref["irena_benchmark_year"])


def capex_benchmark(capex_usd: float, capacity_mw: float) -> Dict[str, Any]:
    """Compare a project's CAPEX/kW to the IRENA global anchor; flag if out of band."""
    if capacity_mw <= 0:
        raise ValueError("capacity_mw must be > 0 for a $/kW benchmark")
    per_kw = capex_usd / (capacity_mw * 1000.0)
    benchmark, year = irena_benchmark_per_kw()
    ratio = per_kw / benchmark
    within_band = _BAND_LO <= ratio <= _BAND_HI
    return {
        "capex_per_kw_usd": round(per_kw, 1),
        "irena_benchmark_per_kw": benchmark,
        "irena_benchmark_year": year,
        "ratio_to_benchmark": round(ratio, 3),
        "within_band": within_band,
        "note": (
            f"{per_kw:,.0f} USD/kW is {ratio:.2f}x the IRENA {year} global average "
            f"({benchmark:,.0f}/kW)"
            + ("" if within_band else " — OUTSIDE the plausible 0.6x-1.8x band, review")
        ),
    }


__all__ = ["capex_benchmark", "irena_benchmark_per_kw"]
