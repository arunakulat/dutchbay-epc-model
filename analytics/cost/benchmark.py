"""Top-down cost sanity checks against published external benchmarks.

Best practice (IRENA 2024) is to sanity-check a bottom-up cost stack against a top-down
global anchor. Two advisory checks live here, both config-sourced (CCCDIR — the anchors
live in ``config/defaults.yaml`` under ``defaults.cost_reference``, never a Python
literal):

* :func:`capex_benchmark` — the project's CAPEX $/kW vs the IRENA global onshore-wind
  weighted-average total installed cost of USD 1,041/kW (range 727-2,110/kW).
* :func:`lcos_benchmark` — the computed BESS LCOS (USD/MWh discharged,
  :mod:`finance.bess_lcos`) vs the non-ITC literature band of USD 115-254/MWh
  (Lazard LCOS v10.0, June-2025 LCOE+; methodology cross-anchored to PNNL ESGC 2024).

Both are report-only disclosures: out-of-band flags (and, for LCOS, a WARNING log
citing the sources) — never a raise, never a changed value.
"""

from __future__ import annotations

import logging
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

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


@lru_cache(maxsize=1)
def lcos_band_usd_per_mwh() -> Tuple[float, float, Tuple[str, ...], int]:
    """The BESS LCOS literature band (low, high, sources, vintage), from config/defaults.yaml.

    The non-ITC USD/MWh comparator band (#605): Lazard LCOS v10.0 (June-2025 LCOE+)
    unsubsidised utility-scale storage, methodology cross-anchored to PNNL ESGC 2024.
    Config-sourced under ``defaults.cost_reference`` (CCCDIR) — never a Python literal.
    """
    import yaml

    data = yaml.safe_load(_DEFAULTS_PATH.read_text())
    ref = data["defaults"]["cost_reference"]
    return (
        float(ref["lcos_band_low_usd_per_mwh"]),
        float(ref["lcos_band_high_usd_per_mwh"]),
        tuple(str(s) for s in ref["lcos_band_sources"]),
        int(ref["lcos_band_year"]),
    )


def lcos_benchmark(lcos_usd_per_mwh: Optional[float]) -> Dict[str, Any]:
    """Advisory band check of a computed BESS LCOS against the literature band (#605).

    Report-only disclosure, mirroring :func:`capex_benchmark`: the computed value is
    never changed and nothing raises. An out-of-band LCOS logs a WARNING citing the
    sources (PNNL ESGC 2024; Lazard LCOS v10.0 non-ITC). An undefined LCOS (``None``,
    e.g. zero PV of discharged energy — see :class:`finance.bess_lcos.LcosResult`) or a
    non-finite value yields ``within_band=None`` with an explicit not-comparable note,
    never a crash or a silent zero (CESSPIT fail-safe).

    NB the model's LCOS is a fixed-dispatch basis (the limitation notes on each
    :class:`~finance.bess_lcos.LcosResult`, #596), while the literature band reflects
    dispatch-optimised cost stacks — an out-of-band value is a prompt to review the
    cost/cycling inputs against the cited sources, not an error.

    Args:
        lcos_usd_per_mwh: The computed LCOS in USD per MWh discharged, or ``None`` when
            the metric is undefined.

    Returns:
        A dict with the band (``band_low_usd_per_mwh`` / ``band_high_usd_per_mwh``),
        its ``band_sources`` and ``band_year`` vintage, ``within_band``
        (``True``/``False``, or ``None`` when not comparable), and a human-readable
        ``note`` citing the sources.
    """
    low, high, sources, year = lcos_band_usd_per_mwh()
    cited = "; ".join(sources)
    if lcos_usd_per_mwh is None or not math.isfinite(float(lcos_usd_per_mwh)):
        return {
            "band_low_usd_per_mwh": low,
            "band_high_usd_per_mwh": high,
            "band_sources": list(sources),
            "band_year": year,
            "within_band": None,
            "note": (
                f"LCOS is undefined ({lcos_usd_per_mwh!r}) — not comparable against "
                f"the {low:,.0f}-{high:,.0f} USD/MWh non-ITC band ({cited})."
            ),
        }
    value = float(lcos_usd_per_mwh)
    within_band = low <= value <= high
    if within_band:
        position = "inside"
    elif value < low:
        position = "BELOW"
    else:
        position = "ABOVE"
    note = (
        f"{value:,.0f} USD/MWh is {position} the {low:,.0f}-{high:,.0f} USD/MWh "
        f"non-ITC literature band ({cited})"
        + ("" if within_band else " — OUTSIDE the band, review cost/cycling inputs")
    )
    if not within_band:
        logger.warning("BESS LCOS advisory: %s", note)
    return {
        "band_low_usd_per_mwh": low,
        "band_high_usd_per_mwh": high,
        "band_sources": list(sources),
        "band_year": year,
        "within_band": within_band,
        "note": note,
    }


__all__ = [
    "capex_benchmark",
    "irena_benchmark_per_kw",
    "lcos_band_usd_per_mwh",
    "lcos_benchmark",
]
