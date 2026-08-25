"""Synthetic measure-correlate-predict measurement for the governed synthetic lane (#961).

WHAT THIS IS, STATED PLAINLY
----------------------------
``wind_resource/mcp.py`` implements measure-correlate-predict but has had no production
consumer since it was written: DutchBay has no on-site mast, so there has never been a
``mast_concurrent`` series to give it. This module supplies one **synthetically**, so the
MCP code path is exercised, typed and tested before the blocked real-evidence chain
(#1075 -> #1076 -> #1078) lands.

The mast series produced here **does not exist**. It is deterministically generated from the
pinned reanalysis summary with a planted, config-declared bias. It is not a measurement, it
is not evidence about the site, and it must never be presented as either.

WHY THIS IS SAFE HERE AND WOULD NOT BE ON THE CANONICAL PATH
------------------------------------------------------------
Wiring MCP into the canonical path would emit a long-term-adjusted number that *resembles* a
measured one — strictly worse than honest dead code, because the model currently discloses
the absence of measurement and that disclosure is what keeps it truthful. The governed
synthetic lane is different: it is already fenced off from canonical finance by contract
(``SYNTHETIC_FEEDER_INPUT_KINDS``, ``QSTS_SYNTHETIC_OUTPUT_CLASS``, the mandatory warning
string, and ``finance_wiring_mode``). Everything this module emits is a
:class:`~analytics.contracts_v14.SyntheticMCPMeasurementRecord`, which cannot be marked
canonical, cannot shed its warning, and is refused by
:func:`~analytics.contracts_v14.require_canonical_wind_measurement`.

CESSPIT: every parameter is read from an explicit config mapping. There are no defaults and
no fallbacks — a missing or malformed key raises.

MRM-01: generation is seeded and reproducible. The same config yields byte-identical output.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

import numpy as np

from analytics.contracts_v14 import SyntheticMCPMeasurementRecord
from wind_resource.mcp import run_mcp

#: Schema identity for the emitted record.
SYNTHETIC_MCP_SCHEMA = "dutchbay.synthetic_mcp_measurement.v1"

#: Generator identity. Bump when the generated series changes shape, so a stored record can
#: be told apart from one produced by a different generator (MRM-02).
SYNTHETIC_MCP_GENERATOR_VERSION = "synthetic_mcp_ar1_biased_reference_v1"

#: Concurrent-sample counts, restated locally so this module does not depend on the
#: threshold rename in flight against ``wind_resource/mcp.py`` (PR #1132). Both values are
#: the same standards-derived numbers that module documents.
_LENDER_DISCLOSURE_MIN_CONCURRENT = 2880  # ~4 months hourly
_IEC_BANKABLE_MIN_CONCURRENT = (
    8760  # 12 months hourly (MEASNET v3.1 / IEC 61400-15-1:2025)
)

_REQUIRED_GENERATOR_KEYS = frozenset(
    {
        "reference_seed",
        "mast_seed",
        "reference_hours",
        "campaign_hours",
        "reference_mean_ms",
        "reference_sigma_ms",
        "ar1_phi",
    }
)
_REQUIRED_BIAS_KEYS = frozenset({"slope", "intercept", "noise_sigma_ms"})
_REQUIRED_MCP_KEYS = frozenset({"method", "min_concurrent", "allow_below_bankable"})
_REQUIRED_SOURCE_KEYS = frozenset({"scenario_sha256", "era5_summary_sha256"})


def _exact_keys(raw: object, expected: frozenset[str], field: str) -> Mapping[str, Any]:
    """Return ``raw`` as a mapping whose key set is EXACTLY ``expected`` (CESSPIT)."""
    if not isinstance(raw, Mapping):
        raise ValueError(f"{field} must be a mapping; got {type(raw).__name__}.")
    got = set(raw)
    if got != set(expected):
        missing = sorted(set(expected) - got)
        unexpected = sorted(got - set(expected))
        raise ValueError(
            f"{field} must declare exactly {sorted(expected)}; "
            f"missing={missing}, unexpected={unexpected}. No defaults are applied."
        )
    return raw


def _strict_bool(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{field} must be a real bool; got {value!r}.")
    return value


def _positive_int(value: object, field: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field} must be a positive int; got {value!r}.")
    return value


def _finite_float(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number; got {value!r}.")
    out = float(value)
    if not np.isfinite(out):
        raise ValueError(f"{field} must be finite; got {value!r}.")
    return out


def _ar1_series(
    *, n: int, mean: float, sigma: float, phi: float, seed: int
) -> np.ndarray:
    """Deterministic AR(1) wind-speed series, clipped to physical (>= 0) speeds.

    Mirrors the shape of the synthetic chronology the #923 feeder generator already uses
    (PCG64 + AR(1)), without importing it — that generator is frozen behind pinned digests
    and must not move.
    """
    rng = np.random.default_rng(seed)
    innovation_sigma = sigma * float(np.sqrt(max(1.0 - phi * phi, 1e-12)))
    out = np.empty(n, dtype=float)
    value = 0.0
    for index in range(n):
        value = phi * value + rng.normal(0.0, innovation_sigma)
        out[index] = value
    return np.clip(out + mean, 0.0, None)


def build_synthetic_mcp_measurement(
    config: Mapping[str, Any], *, generated_at_utc: str
) -> SyntheticMCPMeasurementRecord:
    """Generate a synthetic mast series, run MCP against it, and return a fenced record.

    Args:
        config: Explicit configuration. Must contain exactly the blocks ``generator``,
            ``mast_bias``, ``mcp`` and ``source``, each with exactly its documented keys.
        generated_at_utc: Caller-supplied timestamp, so this function stays pure and its
            output stays reproducible (MRM-01 — the clock is an input, not a hidden read).

    Returns:
        A :class:`SyntheticMCPMeasurementRecord`, which is finance-ineligible by contract.

    Raises:
        ValueError: on any missing, extra or malformed configuration (CESSPIT/FIN-01 — this
            never falls back to a plausible default).
    """
    top = _exact_keys(
        config, frozenset({"generator", "mast_bias", "mcp", "source"}), "config"
    )
    generator = _exact_keys(
        top["generator"], _REQUIRED_GENERATOR_KEYS, "config.generator"
    )
    bias = _exact_keys(top["mast_bias"], _REQUIRED_BIAS_KEYS, "config.mast_bias")
    mcp_cfg = _exact_keys(top["mcp"], _REQUIRED_MCP_KEYS, "config.mcp")
    source = _exact_keys(top["source"], _REQUIRED_SOURCE_KEYS, "config.source")

    reference_hours = _positive_int(
        generator["reference_hours"], "generator.reference_hours"
    )
    campaign_hours = _positive_int(
        generator["campaign_hours"], "generator.campaign_hours"
    )
    if campaign_hours > reference_hours:
        raise ValueError(
            f"generator.campaign_hours ({campaign_hours}) cannot exceed "
            f"generator.reference_hours ({reference_hours}) — the concurrent window is a "
            "subset of the reference series."
        )

    reference = _ar1_series(
        n=reference_hours,
        mean=_finite_float(
            generator["reference_mean_ms"], "generator.reference_mean_ms"
        ),
        sigma=_finite_float(
            generator["reference_sigma_ms"], "generator.reference_sigma_ms"
        ),
        phi=_finite_float(generator["ar1_phi"], "generator.ar1_phi"),
        seed=_positive_int(generator["reference_seed"], "generator.reference_seed"),
    )

    # The "mast": the reference over the concurrent window, with a PLANTED bias. The bias is
    # declared in config precisely so nobody can mistake it for a discovered site property.
    concurrent_reference = reference[:campaign_hours]
    mast_rng = np.random.default_rng(
        _positive_int(generator["mast_seed"], "generator.mast_seed")
    )
    synthetic_mast = np.clip(
        _finite_float(bias["slope"], "mast_bias.slope") * concurrent_reference
        + _finite_float(bias["intercept"], "mast_bias.intercept")
        + mast_rng.normal(
            0.0,
            _finite_float(bias["noise_sigma_ms"], "mast_bias.noise_sigma_ms"),
            campaign_hours,
        ),
        0.0,
        None,
    )

    # run_mcp declares Sequence[float]; hand it lists rather than ndarrays so the typed
    # surface stays clean. float64 -> float is exact, so no value changes.
    result = run_mcp(
        synthetic_mast.tolist(),
        concurrent_reference.tolist(),
        reference.tolist(),
        method=str(mcp_cfg["method"]),
        min_concurrent=_positive_int(mcp_cfg["min_concurrent"], "mcp.min_concurrent"),
        allow_below_bankable=_strict_bool(
            mcp_cfg["allow_below_bankable"], "mcp.allow_below_bankable"
        ),
    )

    return SyntheticMCPMeasurementRecord(
        schema=SYNTHETIC_MCP_SCHEMA,
        generated_at_utc=str(generated_at_utc),
        generator_version=SYNTHETIC_MCP_GENERATOR_VERSION,
        reference_seed=int(generator["reference_seed"]),
        mast_seed=int(generator["mast_seed"]),
        source_scenario_sha256=str(source["scenario_sha256"]),
        source_era5_summary_sha256=str(source["era5_summary_sha256"]),
        mcp_method=result.method,
        mcp_n_concurrent=result.n_concurrent,
        synthetic_predicted_long_term_mean_ms=result.predicted_long_term_mean_ms,
        synthetic_weibull_a=result.weibull_a,
        synthetic_weibull_k=result.weibull_k,
        synthetic_uplift_pct=result.uplift_pct,
        campaign_adequacy=campaign_adequacy_for(result.n_concurrent),
    )


def campaign_adequacy_for(n_concurrent: int) -> str:
    """Classify a campaign length against the standards.

    Kept local rather than read off ``MCPResult`` so this module does not depend on the
    threshold work in flight against ``wind_resource/mcp.py`` (PR #1132). Once that lands
    the two agree by construction; a follow-up can collapse them.
    """
    if n_concurrent >= _IEC_BANKABLE_MIN_CONCURRENT:
        return "iec_bankable"
    if n_concurrent >= _LENDER_DISCLOSURE_MIN_CONCURRENT:
        return "below_iec_bankable"
    return "below_lender_disclosure_floor"


def synthetic_series_for_audit(
    config: Mapping[str, Any],
) -> Tuple[np.ndarray, np.ndarray]:
    """Return ``(synthetic_mast, concurrent_reference)`` for inspection and determinism tests.

    Exposed so a reviewer can see exactly what was generated rather than taking the record's
    word for it.
    """
    record_config: Dict[str, Any] = dict(config)
    generator = _exact_keys(
        record_config["generator"], _REQUIRED_GENERATOR_KEYS, "config.generator"
    )
    bias = _exact_keys(
        record_config["mast_bias"], _REQUIRED_BIAS_KEYS, "config.mast_bias"
    )
    campaign_hours = _positive_int(
        generator["campaign_hours"], "generator.campaign_hours"
    )
    reference = _ar1_series(
        n=_positive_int(generator["reference_hours"], "generator.reference_hours"),
        mean=_finite_float(
            generator["reference_mean_ms"], "generator.reference_mean_ms"
        ),
        sigma=_finite_float(
            generator["reference_sigma_ms"], "generator.reference_sigma_ms"
        ),
        phi=_finite_float(generator["ar1_phi"], "generator.ar1_phi"),
        seed=_positive_int(generator["reference_seed"], "generator.reference_seed"),
    )
    concurrent_reference = reference[:campaign_hours]
    mast_rng = np.random.default_rng(int(generator["mast_seed"]))
    synthetic_mast = np.clip(
        float(bias["slope"]) * concurrent_reference
        + float(bias["intercept"])
        + mast_rng.normal(0.0, float(bias["noise_sigma_ms"]), campaign_hours),
        0.0,
        None,
    )
    return synthetic_mast, concurrent_reference
