"""Lender-grade (bankable) AEP engine.

A transparent, standards-referenced annual-energy-production chain for a
DFI/lender assessment:

1. **Air density correction** — IEC 61400-12-1 wind-speed normalization
   ``v_corr = v * (rho_site / rho_ref)**(1/3)`` applied to a reference-density
   power curve (vs the older approach of scaling power by ``rho``).
2. **Gross AEP** — analytic integration of the (optionally density-corrected)
   power curve over the site Weibull distribution.
3. **Granular wake** — per-turbine wake loss over the real layout via PyWake
   (DTU), default Bastankhah–Porte-Agel Gaussian, using the turbine's thrust
   (Ct) curve. Replaces a flat ``wake_loss_pct`` placeholder. PyWake is an
   optional dependency (``[wind]`` extra), guarded by ``_require_pywake``.
4. **Uncertainty build-up** — IEC 61400-15-2 P50/P75/P90 from a relative
   uncertainty budget combined in quadrature, separating the time-averageable
   interannual variability so a 1-year and an N-year (project-life) P90 are
   both emitted.

All inputs are config-driven (GWTF ARCH-01). No finance logic lives here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

import numpy as np

from analytics.core.exceedance import EXCEEDANCE_Z

logger = logging.getLogger(__name__)

IEC_REFERENCE_AIR_DENSITY_KGM3 = 1.225
# Standard 8760-h year — MUST match analytics.wind.{losses_model,aep_tornado}.HOURS_PER_YEAR
# so the bankable and analytic engines reconcile exactly (was 8766 mean-Julian, a ~0.07%
# cross-engine drift; enforced by tests/lint/test_wind_aep_config_compliance.py).
HOURS_PER_YEAR = 8760.0

# Normal-distribution z-scores for exceedance probabilities (P_x = P50 - z*sigma).
# Sourced from the shared analytics.core.exceedance table so the wind and solar
# exceedance build-ups can never silently diverge (one table, parity-tested).
_EXCEEDANCE_Z = EXCEEDANCE_Z


# ---------------------------------------------------------------------------
# 1. Air density correction (IEC 61400-12-1)
# ---------------------------------------------------------------------------
def density_velocity_factor(
    rho_site_kgm3: float, rho_ref_kgm3: float = IEC_REFERENCE_AIR_DENSITY_KGM3
) -> float:
    """IEC 61400-12-1 wind-speed normalization factor ``(rho_site/rho_ref)**(1/3)``.

    To read site power at site wind speed ``v`` off a ``rho_ref``-referenced
    curve, evaluate the curve at ``v * factor``. For ``rho_site < rho_ref`` the
    factor is < 1 (a leftward shift), i.e. less power at a given wind speed.

    Args:
        rho_site_kgm3: Site air density (kg/m^3).
        rho_ref_kgm3: Reference air density the curve is defined at (default 1.225).

    Returns:
        The multiplicative wind-speed correction factor.
    """
    if rho_site_kgm3 <= 0 or rho_ref_kgm3 <= 0:
        raise ValueError("air densities must be positive")
    return float((rho_site_kgm3 / rho_ref_kgm3) ** (1.0 / 3.0))


# ---------------------------------------------------------------------------
# 2. Gross AEP via Weibull integration
# ---------------------------------------------------------------------------
def _weibull_pdf(v: np.ndarray, a: float, k: float) -> np.ndarray:
    return np.asarray(
        (k / a) * (v / a) ** (k - 1.0) * np.exp(-((v / a) ** k)), dtype=float
    )


@dataclass(frozen=True)
class GrossAEPResult:
    """Gross (pre-loss) AEP for one turbine + farm, with the CF used."""

    capacity_factor: float
    aep_mwh_per_turbine: float
    aep_gwh_farm: float
    n_turbines: int
    density_factor: float


def gross_aep_weibull(
    *,
    wind_speed_ms: Sequence[float],
    power_kw: Sequence[float],
    weibull_a: float,
    weibull_k: float,
    rated_power_kw: float,
    n_turbines: int,
    cut_in_ms: float = 3.0,
    cut_out_ms: float = 25.0,
    rho_site_kgm3: Optional[float] = None,
    rho_ref_kgm3: float = IEC_REFERENCE_AIR_DENSITY_KGM3,
) -> GrossAEPResult:
    """Integrate a power curve over a site Weibull to a gross CF + AEP.

    The curve is optionally air-density corrected (IEC 61400-12-1 v-shift) when
    ``rho_site_kgm3`` is given.
    """
    ws = np.asarray(wind_speed_ms, dtype=float)
    pw = np.asarray(power_kw, dtype=float)
    factor = (
        density_velocity_factor(rho_site_kgm3, rho_ref_kgm3)
        if rho_site_kgm3 is not None
        else 1.0
    )

    v = np.linspace(0.01, 30.0, 3000)
    pdf = _weibull_pdf(v, weibull_a, weibull_k)
    pdf /= np.trapezoid(pdf, v)  # renormalize on the truncated grid

    # Density correction: look up the reference curve at the shifted speed.
    p_of_v = np.interp(v * factor, ws, pw, left=0.0, right=pw[-1])
    p_of_v = np.where((v < cut_in_ms) | (v > cut_out_ms), 0.0, p_of_v)

    mean_power_kw = float(np.trapezoid(p_of_v * pdf, v))
    cf = mean_power_kw / float(rated_power_kw)
    aep_mwh = mean_power_kw / 1000.0 * HOURS_PER_YEAR
    return GrossAEPResult(
        capacity_factor=cf,
        aep_mwh_per_turbine=aep_mwh,
        aep_gwh_farm=aep_mwh * n_turbines / 1000.0,
        n_turbines=n_turbines,
        density_factor=factor,
    )


# ---------------------------------------------------------------------------
# 3. Granular wake (PyWake, optional dependency)
# ---------------------------------------------------------------------------
def _require_pywake() -> Any:
    """Import PyWake or raise a clear, actionable error (CASPER optional-dep guard)."""
    try:
        import py_wake  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised when extra missing
        raise RuntimeError(
            "The granular wake model requires PyWake (the [wind] extra). "
            "Install with: pip install -e '.[wind]'  (or: pip install py-wake)."
        ) from exc
    return py_wake


@dataclass(frozen=True)
class WakeResult:
    """Modeled wake loss over a layout."""

    wake_loss_pct: float
    deficit_model: str
    n_turbines: int
    aep_gross_gwh: float
    aep_wake_gwh: float


def model_wake_loss(
    *,
    wind_speed_ms: Sequence[float],
    power_kw: Sequence[float],
    thrust_coefficient: Sequence[float],
    rotor_diameter_m: float,
    hub_height_m: float,
    layout_x_m: Sequence[float],
    layout_y_m: Sequence[float],
    weibull_a: float,
    weibull_k: float,
    wind_rose_freq: Optional[Sequence[float]] = None,
    turbulence_intensity: float = 0.10,
    deficit_model: str = "bastankhah",
) -> WakeResult:
    """Per-turbine wake loss via PyWake over the real layout + wind rose.

    Args:
        thrust_coefficient: Ct(ws) curve aligned to ``wind_speed_ms``.
        layout_x_m/layout_y_m: turbine positions (m); equal length = n_turbines.
        wind_rose_freq: directional frequency per equal sector (sums to 1); when
            None an omnidirectional rose is used (conservative for a single row).
        deficit_model: 'bastankhah' (primary) or 'turbopark' (conservative
            deep-array cross-check).

    Returns:
        A :class:`WakeResult` with the modeled wake loss percentage.
    """
    _require_pywake()
    from py_wake.literature.gaussian_models import Bastankhah_PorteAgel_2014
    from py_wake.site import UniformWeibullSite
    from py_wake.wind_turbines import WindTurbine
    from py_wake.wind_turbines.power_ct_functions import PowerCtTabular

    ws = np.asarray(wind_speed_ms, dtype=float)
    wt = WindTurbine(
        name="ref",
        diameter=float(rotor_diameter_m),
        hub_height=float(hub_height_m),
        powerCtFunction=PowerCtTabular(
            ws,
            np.asarray(power_kw, dtype=float) * 1000.0,
            "w",
            np.asarray(thrust_coefficient, dtype=float),
        ),
    )

    n_sectors = len(wind_rose_freq) if wind_rose_freq is not None else 12
    freq = (
        np.asarray(wind_rose_freq, dtype=float)
        if wind_rose_freq is not None
        else np.full(n_sectors, 1.0 / n_sectors)
    )
    freq = freq / freq.sum()
    site = UniformWeibullSite(
        p_wd=freq,
        a=[float(weibull_a)] * n_sectors,
        k=[float(weibull_k)] * n_sectors,
        ti=float(turbulence_intensity),
    )

    model = deficit_model.lower()
    if model in ("turbopark", "turbo", "turbo_gaussian"):
        from py_wake.deficit_models.gaussian import TurboGaussianDeficit
        from py_wake.wind_farm_models import PropagateDownwind

        wfm = PropagateDownwind(site, wt, wake_deficitModel=TurboGaussianDeficit())
        model_name = "TurboGaussian (TurbOPark)"
    else:
        # Wake-expansion coefficient k*: Niayifar & Porte-Agel (2016) TI-based
        # relation k* = 0.38*I + 0.004 (the standard onshore closure for the
        # Bastankhah-Porte-Agel 2014 Gaussian model).
        k_star = 0.38 * float(turbulence_intensity) + 0.004
        wfm = Bastankhah_PorteAgel_2014(site, wt, k=k_star)
        model_name = f"Bastankhah-PorteAgel 2014 (Gaussian, k*={k_star:.4f})"

    x = np.asarray(layout_x_m, dtype=float)
    y = np.asarray(layout_y_m, dtype=float)
    sim = wfm(x, y)
    aep_wake = float(sim.aep().sum())
    aep_gross = float(sim.aep(with_wake_loss=False).sum())
    wake_loss = 1.0 - aep_wake / aep_gross if aep_gross > 0 else 0.0
    return WakeResult(
        wake_loss_pct=100.0 * wake_loss,
        deficit_model=model_name,
        n_turbines=len(x),
        aep_gross_gwh=aep_gross,
        aep_wake_gwh=aep_wake,
    )


# ---------------------------------------------------------------------------
# 4. IEC 61400-15-2 uncertainty build-up
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class UncertaintyBudget:
    """Relative (% of P50 AEP) 1-sigma uncertainties — IEC 61400-15-2 categories.

    All but ``interannual_variability_pct`` are treated as systematic (constant
    over the project life); the interannual term is time-averageable and is
    divided by sqrt(life_years) for the multi-year P90.
    """

    wind_measurement_pct: float = 4.5
    long_term_pct: float = 4.0
    vertical_extrapolation_pct: float = 3.0
    horizontal_flow_pct: float = 2.5
    power_curve_pct: float = 5.0
    wake_model_pct: float = 3.0
    interannual_variability_pct: float = 4.0

    def systematic_sigma_pct(self, correlation: float = 0.0) -> float:
        """Combined sigma of the systematic (non-IAV) categories.

        ``correlation`` rho in [0, 1] is a uniform inter-category correlation. The
        standard IEC 61400-15-2 convention combines categories as the root-sum-of-
        squares (rho=0, uncorrelated) — but empirical work (e.g. WES 2021) shows this
        understates total uncertainty. With a single uniform rho the variance is
        ``(1-rho)*RSS^2 + rho*(sum sigma)^2``, so rho=0 -> RSS and rho=1 -> linear sum
        (fully correlated). Default 0.0 preserves the IEC RSS baseline.
        """
        rho = min(max(float(correlation), 0.0), 1.0)
        sigmas = (
            self.wind_measurement_pct,
            self.long_term_pct,
            self.vertical_extrapolation_pct,
            self.horizontal_flow_pct,
            self.power_curve_pct,
            self.wake_model_pct,
        )
        rss_sq = float(sum(s**2 for s in sigmas))
        lin_sq = float(sum(sigmas)) ** 2
        return float(np.sqrt((1.0 - rho) * rss_sq + rho * lin_sq))

    def combined_sigma_pct(self, life_years: float, correlation: float = 0.0) -> float:
        """Total sigma for an averaging window of ``life_years`` years."""
        iav = self.interannual_variability_pct / np.sqrt(max(life_years, 1.0))
        return float(np.sqrt(self.systematic_sigma_pct(correlation) ** 2 + iav**2))


@dataclass(frozen=True)
class ExceedanceResult:
    p50_gwh: float
    p75_gwh: float
    p90_1yr_gwh: float
    p90_life_gwh: float
    sigma_1yr_pct: float
    sigma_life_pct: float
    life_years: int


def exceedance_levels(
    p50_gwh: float,
    budget: UncertaintyBudget,
    life_years: int = 20,
    p50_haircut_pct: float = 0.0,
    correlation: float = 0.0,
) -> ExceedanceResult:
    """P50/P75/P90 (1-year and project-life) from an uncertainty budget.

    ``p50_haircut_pct`` applies a bankability haircut to the modelled P50 BEFORE the
    exceedance build-up (pre-construction P50 has historically been over-predicted,
    ~0-7% across studies; default 0.0 = no haircut). ``correlation`` (rho in [0,1]) is
    passed to the systematic-sigma combination (0.0 = IEC RSS baseline).
    """
    p50_gwh = p50_gwh * (1.0 - float(p50_haircut_pct) / 100.0)
    sig1 = budget.combined_sigma_pct(1.0, correlation)
    sigl = budget.combined_sigma_pct(life_years, correlation)

    def pxx(sigma_pct: float, z: float) -> float:
        return p50_gwh * (1.0 - z * sigma_pct / 100.0)

    return ExceedanceResult(
        p50_gwh=p50_gwh,
        p75_gwh=pxx(sig1, _EXCEEDANCE_Z[75]),
        p90_1yr_gwh=pxx(sig1, _EXCEEDANCE_Z[90]),
        p90_life_gwh=pxx(sigl, _EXCEEDANCE_Z[90]),
        sigma_1yr_pct=sig1,
        sigma_life_pct=sigl,
        life_years=life_years,
    )


# ---------------------------------------------------------------------------
# 5. Non-wake loss stack (availability/electrical/curtailment/other)
# ---------------------------------------------------------------------------
def non_wake_retention(losses: Mapping[str, Any]) -> float:
    """Multiplicative retention for the non-wake loss components.

    Wake is modeled separately (see :func:`model_wake_loss`), so it is excluded
    here. Delegates to the config-driven, fail-loud loss taxonomy in
    :mod:`analytics.wind.losses_model` (single source of truth — same taxonomy as
    :func:`~analytics.wind.losses_model.apply_losses`), so any finer non-wake loss a
    scenario itemises (turbine performance, icing, transmission, …) is honoured and
    an unknown loss key raises instead of being silently dropped.
    """
    from analytics.wind.losses_model import compute_net_factor

    return compute_net_factor(losses, exclude={"wake_loss_pct"})
