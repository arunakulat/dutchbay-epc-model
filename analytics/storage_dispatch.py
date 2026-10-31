"""Default-off hourly instruction feasibility; no optimization or finance wiring."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from analytics.contracts_v14 import (
    ChronologicalDispatchInput,
    DispatchLedger,
    DispatchStep,
)
from analytics.grid.capabilities.bess_soc import bess_soc_state
from analytics.storage_dispatch_contracts import ENERGY_TOLERANCE_MWH


def simulate_dispatch(inputs: ChronologicalDispatchInput) -> DispatchLedger:
    """Account for supplied hourly instructions within physical envelope limits.

    Generation serves the POC before requested discharge. Renewable charging takes
    its requested energy before export; wind/solar custody is attributed pro rata.
    Grid charging and export conservatively share the explicitly authored gross
    POC limit. Clipping is recorded as unmet instruction, never optimization.
    """
    inputs.__post_init__()
    cfg = inputs
    usable = cfg.sizing.energy_mwh * cfg.soh_fraction
    energy = usable * cfg.initial_soc_fraction
    grid = {
        "type": "bess",
        "energy_mwh": cfg.sizing.energy_mwh,
        "soh_fraction": cfg.soh_fraction,
        "min_soc": cfg.minimum_soc_fraction,
        "max_soc": cfg.maximum_soc_fraction,
    }
    rows: list[DispatchStep] = []
    for index, timestamp in enumerate(cfg.timestamps_utc):
        # Only suppress round-off at a boundary computed by the prior bounded step.
        fraction = min(
            cfg.maximum_soc_fraction, max(cfg.minimum_soc_fraction, energy / usable)
        )
        soc = bess_soc_state(grid, soc_fraction=fraction)
        start = energy
        wind_raw = cfg.wind_generation_mwh[index]
        solar_raw = cfg.solar_generation_mwh[index]
        wind = 0.0 if cfg.wind_outage[index] else wind_raw
        solar = 0.0 if cfg.solar_outage[index] else solar_raw
        generation = wind + solar
        cap = 0.0 if cfg.poc_outage[index] else cfg.poc_limit_mw[index] * cfg.step_h
        charge_request = max(0.0, -cfg.dispatch_instruction_mw[index]) * cfg.step_h
        discharge_request = max(0.0, cfg.dispatch_instruction_mw[index]) * cfg.step_h
        charge = 0.0
        discharge = 0.0
        renewable_charge = 0.0
        grid_charge = 0.0
        if not cfg.bess_outage[index] and charge_request > 0:
            source_available = (
                generation if cfg.charge_source[index] == "renewable" else cap
            )
            charge = min(
                charge_request,
                cfg.sizing.power_mw * cfg.step_h,
                soc.chargeable_mwh / cfg.charge_efficiency,
                source_available,
            )
            if cfg.charge_source[index] == "renewable":
                renewable_charge = charge
            else:
                grid_charge = charge
        wind_charge = renewable_charge * (wind / generation) if generation else 0.0
        solar_charge = renewable_charge - wind_charge
        remaining_wind = max(0.0, wind - wind_charge)
        remaining_solar = max(0.0, solar - solar_charge)
        remaining = remaining_wind + remaining_solar
        generation_export = min(remaining, max(0.0, cap - grid_charge))
        wind_export = (
            generation_export * (remaining_wind / remaining) if remaining else 0.0
        )
        solar_export = generation_export - wind_export
        if not cfg.bess_outage[index] and discharge_request > 0:
            discharge = min(
                discharge_request,
                cfg.sizing.power_mw * cfg.step_h,
                soc.dischargeable_mwh * cfg.discharge_efficiency,
                max(0.0, cap - generation_export),
            )
        energy = (
            start
            + charge * cfg.charge_efficiency
            - discharge / cfg.discharge_efficiency
        )
        floor = usable * cfg.minimum_soc_fraction
        ceiling = usable * cfg.maximum_soc_fraction
        if (
            energy < floor - ENERGY_TOLERANCE_MWH
            or energy > ceiling + ENERGY_TOLERANCE_MWH
        ):
            raise ValueError("computed SOC exceeds the authored window.")
        # Bound only floating-point round-off; request shortfalls remain explicit.
        energy = min(ceiling, max(floor, energy))
        rows.append(
            DispatchStep(
                timestamp_utc=timestamp,
                wind_outage_mwh=wind_raw - wind,
                solar_outage_mwh=solar_raw - solar,
                wind_to_bess_mwh=wind_charge,
                solar_to_bess_mwh=solar_charge,
                grid_to_bess_mwh=grid_charge,
                wind_to_poc_mwh=wind_export,
                solar_to_poc_mwh=solar_export,
                bess_to_poc_mwh=discharge,
                wind_curtailed_mwh=max(0.0, remaining_wind - wind_export),
                solar_curtailed_mwh=max(0.0, remaining_solar - solar_export),
                charge_loss_mwh=charge * (1 - cfg.charge_efficiency),
                discharge_loss_mwh=discharge / cfg.discharge_efficiency - discharge,
                soc_start_mwh=start,
                soc_end_mwh=energy,
                unmet_charge_mwh=charge_request - charge,
                unmet_discharge_mwh=discharge_request - discharge,
            )
        )
    return DispatchLedger(inputs=cfg, steps=tuple(rows))


def evaluate_chronological_dispatch(config: Mapping[str, Any]) -> DispatchLedger | None:
    """Run only an explicitly enabled standalone block; absent/disabled is inert.

    This function is intentionally not registered in evaluation or finance. Price
    signals do not generate instructions: optimization/remuneration need separate
    authority. Enabled inputs must contain the complete physical envelope.
    """
    if "chronological_dispatch" not in config:
        return None
    block = config["chronological_dispatch"]
    if not isinstance(block, Mapping):
        raise ValueError("chronological_dispatch must be a mapping.")
    if set(block) - {"enabled", "inputs"}:
        raise ValueError("chronological_dispatch has unknown fields.")
    if type(block.get("enabled")) is not bool:
        raise ValueError("chronological_dispatch.enabled must be an explicit boolean.")
    if not block["enabled"]:
        return None
    raw = block.get("inputs")
    if not isinstance(raw, Mapping):
        raise ValueError("chronological_dispatch.inputs is required when enabled.")
    return simulate_dispatch(ChronologicalDispatchInput.from_mapping(raw))
