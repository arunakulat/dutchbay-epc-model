#!/usr/bin/env python3
"""Hydra CLI: cross-check a wind scenario's energy against NREL PySAM (#1888).

The repository's gross wind energy is an analytic Weibull integral over a power curve
(:func:`wind_resource.aep_integral.gross_aep_farm_gwh`), frozen into the scenario's AEP
summary, and its net energy applies a multiplicative loss stack and a P50 haircut. This
script recomputes the same three figures with an independent engine, NREL PySAM's
``Windpower`` module in Weibull mode, from the scenario's own declared inputs, and prints
one JSON record comparing them (CLI-01, CLI-03). The committed record is
``docs/wind/pysam_energy_crosscheck_1888.json``; the write-up beside it explains the
method and the result.

Independence. No repository energy code runs here. The script reads the scenario YAML
and the power-curve store as plain data and hands PySAM:

- the Weibull shape, and a mean speed of ``A * Gamma(1 + 1/k)``, at the height the scenario
  declares its resource fit at (``resource.era5.hub_height_m``), with the declared shear;
- the declared power curve, shifted to site air density with the IEC 61400-12-1
  velocity factor ``(rho_site / rho_ref) ** (1/3)`` (PySAM's Weibull mode takes no air
  density), resampled onto the 0.25 m/s grid that PySAM's Weibull sum assumes (SAM's
  ``windPowerUsingWeibull`` hard-codes a half-bin of 0.125 m/s);
- the declared losses, mapped one to one onto PySAM loss inputs, with the declared wake
  loss as PySAM's constant internal wake loss.

PySAM applies its loss stack multiplicatively, as the repository does. The P50 haircut,
which PySAM has no input for, is applied to PySAM's net afterwards.

A control run repeats the gross calculation without the density shift. It must fall
outside the tolerance, which shows the comparison can fail.

PySAM is not a dependency of this repository (owner ruling of 2026-11-22). Run the script
in a throwaway environment that adds the release pinned in the config, for example::

    pip install --no-deps --target /tmp/pysam-site NREL-PySAM==<version>
    PYTHONPATH=.:/tmp/pysam-site .venv/bin/python scripts/run_pysam_energy_crosscheck.py \\
        crosscheck.summary_json=docs/wind/pysam_energy_crosscheck_1888.json

The functions that read the declared inputs and digest the method files need no PySAM,
so the staleness test runs in CI without it.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import platform
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

import hydra
import numpy as np
import yaml
from omegaconf import DictConfig, OmegaConf

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = "scripts/run_pysam_energy_crosscheck.py"
CONFIG_PATH = "conf/pysam_energy_crosscheck_1888.yaml"
SCHEMA = "dutchbay.pysam_energy_crosscheck.v1"

#: SAM's Weibull sum pairs each power-curve point with the probability of the bin
#: ``(v - 0.125, v + 0.125]`` and so assumes a uniform 0.25 m/s curve.
SAM_WEIBULL_BIN_MS = 0.25
#: Upper end of the resampled curve. Above the cut-out the curve is zero either way.
SAM_GRID_TOP_MS = 40.0

#: Each declared loss and the PySAM input it maps to. ``True`` marks an availability,
#: which the scenario declares as the share available, so its loss is ``100 - value``.
LOSS_MAP: Dict[str, Tuple[str, bool]] = {
    "wake_loss_pct": ("wake_int_loss", False),
    "availability_pct": ("avail_turb_loss", True),
    "electrical_loss_pct": ("elec_eff_loss", False),
    "curtailment_pct": ("ops_grid_loss", False),
    "other_pct": ("env_env_loss", False),
}

#: Every PySAM Windpower loss input, all set explicitly so no default enters.
PYSAM_LOSS_INPUTS = (
    "avail_bop_loss",
    "avail_grid_loss",
    "avail_turb_loss",
    "elec_eff_loss",
    "elec_parasitic_loss",
    "env_degrad_loss",
    "env_env_loss",
    "env_exposure_loss",
    "env_icing_loss",
    "ops_env_loss",
    "ops_grid_loss",
    "ops_load_loss",
    "ops_strategies_loss",
    "turb_generic_loss",
    "turb_hysteresis_loss",
    "turb_perf_loss",
    "turb_specific_loss",
    "wake_ext_loss",
    "wake_future_loss",
    "wake_int_loss",
)


def _get(mapping: Mapping[str, Any], dotted: str) -> Any:
    """Read a dotted key from a nested mapping, refusing a missing one.

    Args:
        mapping: The parsed scenario or store.
        dotted: A key path such as ``resource.losses``.

    Returns:
        The value at that path.

    Raises:
        KeyError: If any part of the path is missing.
    """
    node: Any = mapping
    for part in dotted.split("."):
        if not isinstance(node, Mapping) or part not in node:
            raise KeyError(f"declared input {dotted!r} is missing")
        node = node[part]
    return node


def _number(mapping: Mapping[str, Any], dotted: str) -> float:
    """Read a finite number from a dotted key.

    Args:
        mapping: The parsed scenario.
        dotted: The key path.

    Returns:
        The value as a float.

    Raises:
        ValueError: If the value is not a finite number.
    """
    value = _get(mapping, dotted)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"declared input {dotted!r} must be a number, got {value!r}")
    if not math.isfinite(float(value)):
        raise ValueError(f"declared input {dotted!r} must be finite, got {value!r}")
    return float(value)


def declared_inputs(
    scenario_rel: str, store_rel: str, root: Path = REPO_ROOT
) -> Dict[str, Any]:
    """Collect every energy input the cross-check uses, from committed files only.

    Args:
        scenario_rel: Scenario YAML path, relative to ``root``.
        store_rel: Power-curve store path, relative to ``root``.
        root: Repository root.

    Returns:
        A JSON-ready mapping of the declared inputs.

    Raises:
        KeyError: If a declared input is missing.
        ValueError: If an input is malformed or a loss is not mapped.
    """
    scenario = yaml.safe_load((root / scenario_rel).read_text(encoding="utf-8"))
    store = yaml.safe_load((root / store_rel).read_text(encoding="utf-8"))
    curve_key = str(_get(scenario, "resource.power_curve.curve_key"))
    entry = _get(store, curve_key)
    ws = [float(v) for v in _get(entry, "power_curve.ws")]
    power = [float(v) for v in _get(entry, "power_curve.power")]
    if len(ws) != len(power) or len(ws) < 2:
        raise ValueError(f"power curve {curve_key!r} needs matching ws/power arrays")
    if any(b <= a for a, b in zip(ws, ws[1:], strict=False)):
        raise ValueError(f"power curve {curve_key!r} wind speeds must increase")
    losses_raw = _get(scenario, "resource.losses")
    if not isinstance(losses_raw, Mapping):
        raise ValueError("resource.losses must be a mapping")
    unmapped = sorted(set(losses_raw) - set(LOSS_MAP))
    missing = sorted(set(LOSS_MAP) - set(losses_raw))
    if unmapped or missing:
        raise ValueError(
            f"resource.losses does not match the PySAM loss map: unmapped {unmapped}, "
            f"missing {missing}"
        )
    losses = {key: _number(scenario, f"resource.losses.{key}") for key in LOSS_MAP}
    n_turbines = _get(scenario, "turbine.n_turbines")
    if (
        isinstance(n_turbines, bool)
        or not isinstance(n_turbines, int)
        or n_turbines < 1
    ):
        raise ValueError(
            f"turbine.n_turbines must be a positive integer, got {n_turbines!r}"
        )
    return {
        "scenario": scenario_rel,
        "power_curve_store": store_rel,
        "aep_summary_path": str(_get(scenario, "resource.aep_summary_path")),
        "n_turbines": n_turbines,
        "hub_height_m": _number(scenario, "turbine.hub_height_m"),
        "rotor_diameter_m": _number(scenario, "turbine.rotor_diameter_m"),
        "weibull_a_ms": _number(scenario, "wind_resource.weibull_a"),
        "weibull_k": _number(scenario, "wind_resource.weibull_k"),
        "weibull_reference_height_m": _number(scenario, "resource.era5.hub_height_m"),
        "shear_exponent": _number(scenario, "wind_resource.shear_exponent"),
        "air_density_site_kgm3": _number(
            scenario, "resource.power_curve.air_density_site_kgm3"
        ),
        "air_density_ref_kgm3": _number(
            scenario, "resource.power_curve.air_density_ref_kgm3"
        ),
        "p50_haircut_pct": _number(scenario, "resource.uncertainty.p50_haircut_pct"),
        "losses_pct": losses,
        "power_curve": {"curve_key": curve_key, "ws_ms": ws, "power_kw": power},
    }


def canonical_sha256(payload: Any) -> str:
    """SHA-256 of a JSON value in canonical form (sorted keys, no spaces).

    Args:
        payload: Any JSON-serialisable value.

    Returns:
        The hex digest.
    """
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def method_digests(root: Path = REPO_ROOT) -> Dict[str, str]:
    """SHA-256 of the runner and its config, so a changed method shows as stale.

    Args:
        root: Repository root.

    Returns:
        Path to hex digest, for the script and the config.
    """
    return {
        rel: hashlib.sha256((root / rel).read_bytes()).hexdigest()
        for rel in (SCRIPT_PATH, CONFIG_PATH)
    }


def committed_figures(
    inputs: Mapping[str, Any], root: Path = REPO_ROOT
) -> Dict[str, Any]:
    """The committed AEP summary's figures that the PySAM run is compared with.

    Args:
        inputs: Output of :func:`declared_inputs`.
        root: Repository root.

    Returns:
        Gross, modelled net and bankable net energy (GWh), the turbine count and losses.
    """
    summary = json.loads(
        (root / inputs["aep_summary_path"]).read_text(encoding="utf-8")
    )
    losses = summary.get("losses", {})
    return {
        "gross_gwh": float(summary["gross_aep_gwh"]),
        "net_modelled_gwh": float(summary["uncertainty"]["modelled_p50_gwh"]),
        "net_bankable_gwh": float(summary["net_site_aep_gwh"]),
        "n_turbines": int(summary["n_turbines"]),
        "total_loss_pct": float(losses["total_loss_pct"]),
        "losses_pct": {key: float(losses[key]) for key in LOSS_MAP},
    }


def density_factor(inputs: Mapping[str, Any]) -> float:
    """IEC 61400-12-1 velocity factor ``(rho_site / rho_ref) ** (1/3)``.

    Args:
        inputs: Output of :func:`declared_inputs`.

    Returns:
        The factor; a curve point at ``v`` moves to ``v / factor``.
    """
    return float(
        (inputs["air_density_site_kgm3"] / inputs["air_density_ref_kgm3"])
        ** (1.0 / 3.0)
    )


def sam_power_curve(
    inputs: Mapping[str, Any], factor: float
) -> Tuple[List[float], List[float]]:
    """The declared curve, density-shifted and resampled onto SAM's 0.25 m/s grid.

    Args:
        inputs: Output of :func:`declared_inputs`.
        factor: Velocity factor; 1.0 leaves the curve at its reference density.

    Returns:
        Wind speeds (m/s) and power (kW) on the uniform grid, zero outside the curve.
    """
    curve = inputs["power_curve"]
    shifted = np.asarray(curve["ws_ms"], dtype=float) / factor
    grid = np.round(np.arange(0.0, SAM_GRID_TOP_MS + 1e-9, SAM_WEIBULL_BIN_MS), 6)
    power = np.interp(
        grid, shifted, np.asarray(curve["power_kw"], dtype=float), 0.0, 0.0
    )
    return [float(v) for v in grid], [float(v) for v in power]


def pysam_energy(
    inputs: Mapping[str, Any], factor: float, apply_losses: bool
) -> Dict[str, float]:
    """Run PySAM Windpower in Weibull mode on the declared inputs.

    Args:
        inputs: Output of :func:`declared_inputs`.
        factor: Density velocity factor for the curve.
        apply_losses: Whether to pass the declared losses.

    Returns:
        PySAM's farm gross and net energy (GWh) and its total loss (%).
    """
    import PySAM.Windpower as wp  # imported here: not a dependency of this repository

    ws, power = sam_power_curve(inputs, factor)
    n = int(inputs["n_turbines"])
    model = wp.new()
    model.Resource.wind_resource_model_choice = 1  # Weibull
    model.Resource.weibull_k_factor = inputs["weibull_k"]
    model.Resource.weibull_wind_speed = inputs["weibull_a_ms"] * math.gamma(
        1.0 + 1.0 / inputs["weibull_k"]
    )
    model.Resource.weibull_reference_height = inputs["weibull_reference_height_m"]
    model.Turbine.wind_resource_shear = inputs["shear_exponent"]
    model.Turbine.wind_turbine_hub_ht = inputs["hub_height_m"]
    model.Turbine.wind_turbine_rotor_diameter = inputs["rotor_diameter_m"]
    model.Turbine.wind_turbine_powercurve_windspeeds = ws
    model.Turbine.wind_turbine_powercurve_powerout = power
    # Required by the module; it does not enter a Weibull run on a supplied curve.
    model.Turbine.wind_turbine_max_cp = 0.45
    # Constant wake model: the declared wake loss enters as wake_int_loss below.
    model.Farm.wind_farm_wake_model = 3
    model.Farm.wind_resource_turbulence_coeff = 0.1
    # Placeholder positions, far apart: the constant wake model does not read them.
    spacing = 20.0 * inputs["rotor_diameter_m"]
    model.Farm.wind_farm_xCoordinates = [spacing * i for i in range(n)]
    model.Farm.wind_farm_yCoordinates = [0.0] * n
    model.Farm.system_capacity = n * max(power)
    for name in PYSAM_LOSS_INPUTS:
        setattr(model.Losses, name, 0.0)
    if apply_losses:
        for key, (name, is_availability) in LOSS_MAP.items():
            value = inputs["losses_pct"][key]
            setattr(model.Losses, name, 100.0 - value if is_availability else value)
    model.execute()
    gross = float(model.Outputs.annual_gross_energy) / 1e6
    net = float(model.Outputs.annual_energy) / 1e6
    return {
        "gross_gwh": gross,
        "net_gwh": net,
        "total_loss_pct": (1.0 - net / gross) * 100.0,
    }


def _delta_pct(value: float, reference: float) -> float:
    return round((value / reference - 1.0) * 100.0, 4)


def run(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Run the cross-check and build the record.

    Args:
        cfg: The resolved ``crosscheck`` config block's parent mapping.

    Returns:
        The record.

    Raises:
        RuntimeError: If the installed PySAM is not the pinned release.
    """
    from importlib.metadata import version

    block = cfg["crosscheck"]
    pinned = block["pysam"]
    installed = version(str(pinned["distribution"]))
    if installed != str(pinned["version"]):
        raise RuntimeError(
            f"PySAM {installed} is installed; the record pins {pinned['version']}"
        )
    tolerance = float(block["tolerance_pct"])
    inputs = declared_inputs(str(block["scenario"]), str(block["power_curve_store"]))
    committed = committed_figures(inputs)
    factor = density_factor(inputs)
    gross_only = pysam_energy(inputs, factor, apply_losses=False)
    with_losses = pysam_energy(inputs, factor, apply_losses=True)
    control = pysam_energy(inputs, 1.0, apply_losses=False)
    bankable = with_losses["net_gwh"] * (1.0 - inputs["p50_haircut_pct"] / 100.0)
    pysam_figures = {
        "gross_gwh": round(gross_only["gross_gwh"], 4),
        "net_modelled_gwh": round(with_losses["net_gwh"], 4),
        "net_bankable_gwh": round(bankable, 4),
        "total_loss_pct": round(with_losses["total_loss_pct"], 4),
    }
    deltas = {
        key: _delta_pct(pysam_figures[key], committed[key])
        for key in ("gross_gwh", "net_modelled_gwh", "net_bankable_gwh")
    }
    control_delta = _delta_pct(round(control["gross_gwh"], 4), committed["gross_gwh"])
    return {
        "schema": SCHEMA,
        "work_item": "#1888",
        "inputs": inputs,
        "inputs_sha256": canonical_sha256(inputs),
        "method_sha256": method_digests(),
        "engine": {
            "distribution": str(pinned["distribution"]),
            "version": installed,
            "module": "Windpower",
            "resource_model": "Weibull (wind_resource_model_choice = 1)",
            "wake_model": "constant (wind_farm_wake_model = 3), declared wake loss",
            "power_curve_grid_ms": SAM_WEIBULL_BIN_MS,
            "density_velocity_factor": round(factor, 6),
            "python": platform.python_version(),
            "machine": platform.machine(),
        },
        "committed": committed,
        "pysam": pysam_figures,
        "delta_pct": deltas,
        "tolerance_pct": tolerance,
        "within_tolerance": all(abs(d) <= tolerance for d in deltas.values()),
        "control": {
            "description": (
                "Gross energy with the density shift left out. It must fall outside the "
                "tolerance, which shows the comparison can fail."
            ),
            "gross_gwh": round(control["gross_gwh"], 4),
            "delta_pct": control_delta,
            "outside_tolerance": abs(control_delta) > tolerance,
        },
    }


@hydra.main(
    version_base="1.3",
    config_path="../conf",
    config_name="pysam_energy_crosscheck_1888",
)
def main(cfg: DictConfig) -> None:
    """Run the cross-check, print one JSON object, and write it when asked.

    Args:
        cfg: Hydra config composed from ``conf/pysam_energy_crosscheck_1888.yaml``.

    Raises:
        TypeError: If the config does not resolve to a mapping.
    """
    logging.disable(logging.INFO)
    raw: Any = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(raw, dict):
        raise TypeError("expected the Hydra config to resolve to a mapping")
    result = run(copy.deepcopy(raw))
    text = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
    out = raw["crosscheck"].get("summary_json")
    if out:
        target = Path(str(out))
        if not target.is_absolute():
            target = REPO_ROOT / target
        target.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
