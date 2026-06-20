"""AEP tornado sensitivities (#25) — wind, shear, losses, power curve.

Deterministic one-at-a-time sensitivity of **net AEP** to the key resource
assumptions, ranked by impact, for lender tornado charts. Gross AEP is computed
by an analytic Weibull integral with **linear** power-curve interpolation
(matching :class:`wind_resource.EnergyCalculator`, which integrates a wind
timeseries with a linear curve); losses are applied via the #23 losses model.
The selected curve carries the IEC 61400-12-1 velocity-cube air-density
correction (``density_factor``), so with the declared Weibull (A=8.32, k=2.1)
and the 15 x IEA-10MW lender curve this reproduces the canonical base
(~483.6 GWh net) — method-consistent with the headline AEP. (The legacy
23 x EN-171/6.5 base, ~402.6 GWh, regenerates from its own config.)

Drivers:
    - ``wind_speed_bias``   ± on mean wind speed (scales Weibull A)
    - ``shear_exponent``    ± on shear (re-extrapolates A from the reference height)
    - ``losses``            ± relative on the loss stack
    - ``power_curve``       certified OEM curve vs an alternative store curve

Context:
    Sprint 10 - Issue #25 (AEP tornado sensitivities).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

import numpy as np
import pandas as pd
import yaml

from analytics.power_curves.oem_parser import (CANONICAL_CURVE_KEY,
                                               POWER_CURVE_STORE)
from analytics.wind.losses_model import apply_losses
from wind_resource.bankable_aep import density_velocity_factor

HOURS_PER_YEAR = 8760.0
# Fine wind-speed grid (m/s) for the analytic Weibull integral.
_WS_GRID = np.arange(0.0, 30.0001, 0.05)

# Loss keys expressed as reductions (scaled directly by the losses driver).
_REDUCTION_LOSS_KEYS = (
    "wake_loss_pct",
    "electrical_loss_pct",
    "curtailment_pct",
    "other_pct",
)


@dataclass(frozen=True)
class AEPTornadoConfig:
    """Sensitivity ranges for the AEP tornado (analysis parameters)."""

    wind_bias_pct: float = 5.0  # ± on mean wind speed (scales Weibull A)
    shear_delta: float = 0.04  # ± on the shear exponent
    losses_rel_pct: float = 20.0  # ± relative on the loss stack
    reference_height_m: float = 100.0  # shear-extrapolation reference (ERA5 100 m)
    hub_height_m: float = 150.0
    alt_curve_key: str = "ge_cypress_5p5"  # alternative curve for OEM-vs-alt driver


def _load_curve(key: str, store: Path = POWER_CURVE_STORE) -> Tuple[np.ndarray, np.ndarray]:
    """Load (wind_speed, power_kw) arrays for a turbine key from the store."""
    data = yaml.safe_load(store.read_text())
    if not isinstance(data, dict) or key not in data:
        raise KeyError(f"Power-curve key {key!r} not found in {store}")
    pc = data[key]["power_curve"]
    return (
        np.array([float(x) for x in pc["ws"]], dtype=float),
        np.array([float(x) for x in pc["power"]], dtype=float),
    )


def _weibull_pdf(v: np.ndarray, a: float, k: float) -> np.ndarray:
    pdf = (k / a) * (v / a) ** (k - 1.0) * np.exp(-((v / a) ** k))
    return np.asarray(pdf, dtype=float)


def gross_aep_farm_gwh(
    weibull_a: float,
    weibull_k: float,
    curve_ws: np.ndarray,
    curve_power_kw: np.ndarray,
    n_turbines: int,
) -> float:
    """Analytic gross farm AEP (GWh) from a Weibull and a power curve.

    Shared with the #24 Monte-Carlo AEP module so both use the same method.
    """
    pdf = _weibull_pdf(_WS_GRID, weibull_a, weibull_k)
    pdf = pdf / float(np.trapezoid(pdf, _WS_GRID))  # renormalise over the grid
    power = np.interp(_WS_GRID, curve_ws, curve_power_kw, left=0.0, right=0.0)
    mean_power_kw = float(np.trapezoid(power * pdf, _WS_GRID))
    per_turbine_gwh = mean_power_kw * HOURS_PER_YEAR / 1e6
    return per_turbine_gwh * n_turbines


def _net_aep_gwh(
    weibull_a: float,
    weibull_k: float,
    curve_ws: np.ndarray,
    curve_power_kw: np.ndarray,
    n_turbines: int,
    losses: Mapping[str, Any],
) -> float:
    gross = gross_aep_farm_gwh(
        weibull_a, weibull_k, curve_ws, curve_power_kw, n_turbines
    )
    return apply_losses(gross, losses).net_aep_gwh


def _scaled_losses(losses: Mapping[str, Any], rel: float) -> Dict[str, Any]:
    """Scale the loss stack by a relative fraction (``+rel`` = heavier losses)."""
    out: Dict[str, Any] = dict(losses)
    for key in _REDUCTION_LOSS_KEYS:
        if out.get(key) is not None:
            out[key] = float(out[key]) * (1.0 + rel)
    if out.get("availability_pct") is not None:
        loss = (100.0 - float(out["availability_pct"])) * (1.0 + rel)
        out["availability_pct"] = 100.0 - loss
    return out


def run_aep_tornado(
    *,
    weibull_a: float,
    weibull_k: float,
    losses: Mapping[str, Any],
    n_turbines: int,
    curve_key: str = CANONICAL_CURVE_KEY,
    density_factor: float = 1.0,
    cfg: AEPTornadoConfig = AEPTornadoConfig(),
) -> pd.DataFrame:
    """Run the AEP tornado and return a DataFrame ranked by absolute swing.

    Columns: ``driver``, ``minus_label``, ``plus_label``, ``aep_minus_gwh``,
    ``aep_plus_gwh``, ``base_aep_gwh``, ``swing_gwh`` (signed plus−minus),
    ``abs_swing_gwh``, ``swing_pct`` (of base).

    ``density_factor`` is the IEC 61400-12-1 velocity-cube ratio
    ``(rho_site / rho_ref) ** (1/3)`` (1.0 = no correction). Applying it is
    equivalent to shifting the curve's wind-speed axis by ``1 / density_factor``,
    so a sub-unity factor (thinner air) raises the speed needed for each power
    level and yields the canonical density-corrected AEP — matching the bankable
    engine, without disturbing the shared :func:`gross_aep_farm_gwh`.
    """
    base_ws, base_power = _load_curve(curve_key)
    base_ws = base_ws / density_factor
    base = _net_aep_gwh(weibull_a, weibull_k, base_ws, base_power, n_turbines, losses)

    rows: List[Dict[str, Any]] = []

    def _row(driver: str, minus_label: str, plus_label: str, aep_minus: float, aep_plus: float) -> None:
        rows.append(
            {
                "driver": driver,
                "minus_label": minus_label,
                "plus_label": plus_label,
                "aep_minus_gwh": round(aep_minus, 3),
                "aep_plus_gwh": round(aep_plus, 3),
            }
        )

    # 1. Wind-speed bias (scale A).
    fwb = cfg.wind_bias_pct / 100.0
    _row(
        "wind_speed_bias",
        f"-{cfg.wind_bias_pct:.0f}%",
        f"+{cfg.wind_bias_pct:.0f}%",
        _net_aep_gwh(weibull_a * (1.0 - fwb), weibull_k, base_ws, base_power, n_turbines, losses),
        _net_aep_gwh(weibull_a * (1.0 + fwb), weibull_k, base_ws, base_power, n_turbines, losses),
    )

    # 2. Shear exponent (re-extrapolate A from the reference height).
    ratio = cfg.hub_height_m / cfg.reference_height_m
    _row(
        "shear_exponent",
        f"-{cfg.shear_delta:g}",
        f"+{cfg.shear_delta:g}",
        _net_aep_gwh(weibull_a * ratio ** (-cfg.shear_delta), weibull_k, base_ws, base_power, n_turbines, losses),
        _net_aep_gwh(weibull_a * ratio ** (cfg.shear_delta), weibull_k, base_ws, base_power, n_turbines, losses),
    )

    # 3. Losses (relative). +rel = heavier losses → lower AEP.
    frl = cfg.losses_rel_pct / 100.0
    _row(
        "losses",
        f"-{cfg.losses_rel_pct:.0f}%",
        f"+{cfg.losses_rel_pct:.0f}%",
        _net_aep_gwh(weibull_a, weibull_k, base_ws, base_power, n_turbines, _scaled_losses(losses, -frl)),
        _net_aep_gwh(weibull_a, weibull_k, base_ws, base_power, n_turbines, _scaled_losses(losses, frl)),
    )

    # 4. Power curve: certified OEM vs an alternative store curve.
    alt_ws, alt_power = _load_curve(cfg.alt_curve_key)
    alt_ws = alt_ws / density_factor  # same density basis as the base curve
    alt_aep = _net_aep_gwh(weibull_a, weibull_k, alt_ws, alt_power, n_turbines, losses)
    _row("power_curve", f"alt:{cfg.alt_curve_key}", f"oem:{curve_key}", alt_aep, base)

    df = pd.DataFrame(rows)
    df["base_aep_gwh"] = round(base, 3)
    df["swing_gwh"] = (df["aep_plus_gwh"] - df["aep_minus_gwh"]).round(3)
    df["abs_swing_gwh"] = df["swing_gwh"].abs()
    df["swing_pct"] = (100.0 * df["abs_swing_gwh"] / base).round(2)
    df = df.sort_values("abs_swing_gwh", ascending=False).reset_index(drop=True)
    return df


def tornado_from_config(
    config: Mapping[str, Any],
    cfg: AEPTornadoConfig = AEPTornadoConfig(),
) -> pd.DataFrame:
    """Build and run the AEP tornado from a parsed v14 scenario config.

    Reads the selected power curve and the IEC air-density basis from
    ``resource.power_curve`` (``curve_key`` + ``air_density_{site,ref}_kgm3``),
    falling back to the canonical curve / no density correction when those
    fields are absent — so pre-10MW scenarios keep their prior behaviour.
    """
    wr = config.get("wind_resource", {}) or {}
    resource = config.get("resource", {}) or {}
    power_curve = resource.get("power_curve", {}) or {}
    curve_key = power_curve.get("curve_key", CANONICAL_CURVE_KEY)
    rho_site = power_curve.get("air_density_site_kgm3", wr.get("air_density_kgm3"))
    rho_ref = power_curve.get("air_density_ref_kgm3", wr.get("air_density_ref_kgm3"))
    density_factor = (
        density_velocity_factor(float(rho_site), float(rho_ref))
        if rho_site is not None and rho_ref is not None
        else 1.0
    )
    # Use a comparable alternative machine for the power-curve sensitivity driver
    # when the scenario names one (e.g. the other 10 MW reference), so the driver
    # measures curve choice rather than a turbine-class mismatch.
    alt_curve_key = power_curve.get("alt_curve_key")
    if alt_curve_key:
        cfg = replace(cfg, alt_curve_key=alt_curve_key)
    return run_aep_tornado(
        weibull_a=float(wr["weibull_a"]),
        weibull_k=float(wr["weibull_k"]),
        losses=resource["losses"],
        n_turbines=int(resource["turbines"]["count"]),
        curve_key=curve_key,
        density_factor=density_factor,
        cfg=cfg,
    )


def write_tornado_csv(df: pd.DataFrame, output_path: str) -> Path:
    """Write a tornado DataFrame to a lender-ready CSV; returns the path."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return out


__all__ = [
    "AEPTornadoConfig",
    "gross_aep_farm_gwh",
    "run_aep_tornado",
    "tornado_from_config",
    "write_tornado_csv",
]
