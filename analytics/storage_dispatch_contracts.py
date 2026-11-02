"""Strict immutable hourly battery-ledger inputs and physical receipts (#1402)."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timedelta
from typing import Any, cast

from analytics.storage_sizing import BessSizing

# Numerical accounting tolerance in MWh, not permission to relax an authored limit.
ENERGY_TOLERANCE_MWH = 1e-8


def number(value: object, field: str) -> float:
    """Require a finite YAML number, refusing bool/string and overflow coercion."""
    if type(value) not in (int, float):
        raise ValueError(f"{field} must be a finite YAML number.")
    try:
        result = float(cast(int | float, value))
    except OverflowError as exc:
        raise ValueError(f"{field} must be finite.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite.")
    return result


def _utc(value: object) -> datetime:
    """Require an explicit UTC timestamp without interpreting a local timezone."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamps_utc must contain ISO UTC timestamps.") from exc
    if not isinstance(value, datetime) or value.utcoffset() != timedelta(0):
        raise ValueError("timestamps_utc must contain timezone-aware UTC timestamps.")
    return value


def _json_values(value: Any) -> Any:
    """Convert immutable dataclass values into JSON-native values."""
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {key: _json_values(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_values(item) for item in value]
    return value


@dataclass(frozen=True)
class ChronologicalDispatchInput:
    """An authored hourly physical envelope, with no financial/dispatch-right claim.

    Generation is available AC energy before the explicitly supplied outage masks.
    Positive instructions request AC discharge; negative instructions request AC
    charging. SOC is a fraction of nameplate energy times authored static SoH.
    Tariff/LD terms are provenance text only; this ledger never values them.
    """

    sizing: BessSizing
    timestamps_utc: tuple[datetime, ...]
    step_h: float
    wind_generation_mwh: tuple[float, ...]
    solar_generation_mwh: tuple[float, ...]
    dispatch_instruction_mw: tuple[float, ...]
    poc_limit_mw: tuple[float, ...]
    wind_outage: tuple[bool, ...]
    solar_outage: tuple[bool, ...]
    bess_outage: tuple[bool, ...]
    poc_outage: tuple[bool, ...]
    charge_source: tuple[str, ...]
    charge_efficiency: float
    discharge_efficiency: float
    soh_fraction: float
    minimum_soc_fraction: float
    maximum_soc_fraction: float
    initial_soc_fraction: float
    final_soc_fraction: float
    poc_flow_basis: str
    allocation_policy: str
    tariff_terms: str
    ld_terms: str
    provenance: str

    def __post_init__(self) -> None:
        """Refuse missing, mutable, misaligned or physically invalid envelopes."""
        if not isinstance(self.sizing, BessSizing):
            raise ValueError("sizing must be the shared BessSizing contract.")
        self.sizing.__post_init__()
        if number(self.step_h, "step_h") != 1.0:
            raise ValueError("step_h must be explicitly 1.0 for this hourly ledger.")
        if type(self.timestamps_utc) is not tuple or not self.timestamps_utc:
            raise ValueError("timestamps_utc must be a non-empty immutable tuple.")
        if any(not isinstance(item, datetime) for item in self.timestamps_utc):
            raise ValueError("timestamps_utc constructor values must be UTC datetimes.")
        times = tuple(_utc(item) for item in self.timestamps_utc)
        if any(
            later - earlier != timedelta(hours=1)
            for earlier, later in zip(times, times[1:], strict=False)
        ):
            raise ValueError("timestamps_utc must be strictly consecutive hourly UTC.")
        size = len(times)
        for field in (
            "wind_generation_mwh",
            "solar_generation_mwh",
            "dispatch_instruction_mw",
            "poc_limit_mw",
            "wind_outage",
            "solar_outage",
            "bess_outage",
            "poc_outage",
            "charge_source",
        ):
            series = getattr(self, field)
            if type(series) is not tuple or len(series) != size:
                raise ValueError(
                    f"{field} must be an immutable tuple of length {size}."
                )
            for index, value in enumerate(series):
                label = f"{field}[{index}]"
                if field.endswith("_outage"):
                    if type(value) is not bool:
                        raise ValueError(f"{label} must be an explicit boolean.")
                elif field == "charge_source":
                    if value not in ("renewable", "grid", "none"):
                        raise ValueError(f"{label} must be renewable, grid or none.")
                    charging = self.dispatch_instruction_mw[index] < 0
                    if charging == (value == "none"):
                        raise ValueError(
                            f"{label} must match the charging instruction."
                        )
                else:
                    numeric = number(value, label)
                    if field != "dispatch_instruction_mw" and numeric < 0:
                        raise ValueError(f"{label} must be non-negative.")
        for field in ("charge_efficiency", "discharge_efficiency", "soh_fraction"):
            if not 0 < number(getattr(self, field), field) <= 1:
                raise ValueError(f"{field} must be in (0, 1].")
        usable = self.sizing.energy_mwh * self.soh_fraction
        if not math.isfinite(usable) or usable <= 0:
            raise ValueError(
                "sizing.energy_mwh*soh_fraction must remain finite and positive."
            )
        if any(
            not math.isfinite(wind + solar)
            for wind, solar in zip(
                self.wind_generation_mwh, self.solar_generation_mwh, strict=True
            )
        ):
            raise ValueError(
                "wind_generation_mwh+solar_generation_mwh must remain finite."
            )
        for field in (
            "minimum_soc_fraction",
            "maximum_soc_fraction",
            "initial_soc_fraction",
            "final_soc_fraction",
        ):
            if not 0 <= number(getattr(self, field), field) <= 1:
                raise ValueError(f"{field} must be in [0, 1].")
        if not self.minimum_soc_fraction < self.maximum_soc_fraction:
            raise ValueError("minimum_soc_fraction must be below maximum_soc_fraction.")
        for field in ("initial_soc_fraction", "final_soc_fraction"):
            if (
                not self.minimum_soc_fraction
                <= getattr(self, field)
                <= self.maximum_soc_fraction
            ):
                raise ValueError(f"{field} must be inside the authored SOC window.")
        if self.poc_flow_basis != "gross_sum":
            raise ValueError("poc_flow_basis must explicitly select gross_sum.")
        if self.allocation_policy != "charge_then_generation_then_discharge":
            raise ValueError(
                "allocation_policy must explicitly select charge_then_generation_then_discharge."
            )
        for field in ("tariff_terms", "ld_terms", "provenance"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{field} must explicitly state its provenance/limitation."
                )

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> ChronologicalDispatchInput:
        """Copy all required YAML fields, refusing omissions and unknown keys."""
        if not isinstance(raw, Mapping):
            raise ValueError("chronological dispatch inputs must be a mapping.")
        required = {field.name for field in fields(cls)}
        missing = required - raw.keys()
        unknown = raw.keys() - required
        if missing or unknown:
            raise ValueError(
                f"chronological dispatch fields: missing={sorted(missing)!r}; "
                f"unknown={sorted(map(str, unknown))!r}."
            )
        values = dict(raw)
        sizing = values["sizing"]
        if not isinstance(sizing, Mapping):
            raise ValueError("sizing must be an explicit rating mapping.")
        if set(sizing) - {"power_mw", "duration_h", "energy_mwh"}:
            raise ValueError("sizing has unknown rating fields.")
        values["sizing"] = BessSizing.from_mapping(sizing)
        for field in fields(cls):
            if field.name in {
                "timestamps_utc",
                "wind_generation_mwh",
                "solar_generation_mwh",
                "dispatch_instruction_mw",
                "poc_limit_mw",
                "wind_outage",
                "solar_outage",
                "bess_outage",
                "poc_outage",
                "charge_source",
            }:
                value = values[field.name]
                if not isinstance(value, (list, tuple)):
                    raise ValueError(
                        f"{field.name} must be an explicit hourly sequence."
                    )
                values[field.name] = tuple(
                    _utc(item) if field.name == "timestamps_utc" else item
                    for item in value
                )
        return cls(**values)

    def model_dump(self) -> dict[str, Any]:
        """Return a detached JSON-native copy after revalidating the envelope."""
        self.__post_init__()
        return cast(dict[str, Any], _json_values(asdict(self)))

    @property
    def sha256(self) -> str:
        """Bind the complete authored envelope, including terms and provenance."""
        raw = json.dumps(
            self.model_dump(), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class DispatchStep:
    """One immutable hourly source/destination ledger, all energies in MWh."""

    timestamp_utc: datetime
    wind_outage_mwh: float
    solar_outage_mwh: float
    wind_to_bess_mwh: float
    solar_to_bess_mwh: float
    grid_to_bess_mwh: float
    wind_to_poc_mwh: float
    solar_to_poc_mwh: float
    bess_to_poc_mwh: float
    wind_curtailed_mwh: float
    solar_curtailed_mwh: float
    charge_loss_mwh: float
    discharge_loss_mwh: float
    soc_start_mwh: float
    soc_end_mwh: float
    unmet_charge_mwh: float
    unmet_discharge_mwh: float

    def __post_init__(self) -> None:
        """Refuse non-finite or negative physical flows in a receipt."""
        _utc(self.timestamp_utc)
        for field in fields(self):
            if (
                field.name != "timestamp_utc"
                and number(getattr(self, field.name), field.name) < 0
            ):
                raise ValueError(f"{field.name} must be non-negative.")


def _equal(actual: float, expected: float, label: str) -> None:
    """Check accounting identities within a declared absolute rounding tolerance."""
    if not math.isclose(actual, expected, rel_tol=0, abs_tol=ENERGY_TOLERANCE_MWH):
        raise ValueError(f"dispatch ledger violates {label}: {actual} != {expected}.")


@dataclass(frozen=True)
class DispatchLedger:
    """A replayable physical receipt; feasibility conveys no financial authority."""

    inputs: ChronologicalDispatchInput
    steps: tuple[DispatchStep, ...]

    def __post_init__(self) -> None:
        """Verify source custody, conservation, continuity and authored bounds."""
        if not isinstance(self.inputs, ChronologicalDispatchInput):
            raise ValueError("inputs must be a ChronologicalDispatchInput contract.")
        self.inputs.__post_init__()
        cfg = self.inputs
        if type(self.steps) is not tuple or len(self.steps) != len(cfg.timestamps_utc):
            raise ValueError("steps must be an immutable aligned hourly ledger.")
        usable = cfg.sizing.energy_mwh * cfg.soh_fraction
        previous = usable * cfg.initial_soc_fraction
        for index, row in enumerate(self.steps):
            if not isinstance(row, DispatchStep):
                raise ValueError("steps must contain DispatchStep contracts.")
            row.__post_init__()
            if row.timestamp_utc != cfg.timestamps_utc[index]:
                raise ValueError("step timestamp does not match its input.")
            _equal(row.soc_start_mwh, previous, "SOC continuity")
            charge = row.wind_to_bess_mwh + row.solar_to_bess_mwh + row.grid_to_bess_mwh
            discharge = row.bess_to_poc_mwh
            export = row.wind_to_poc_mwh + row.solar_to_poc_mwh + discharge
            for resource in ("wind", "solar"):
                raw = getattr(cfg, f"{resource}_generation_mwh")[index]
                outage = getattr(row, f"{resource}_outage_mwh")
                _equal(
                    outage,
                    raw if getattr(cfg, f"{resource}_outage")[index] else 0,
                    f"{resource} outage",
                )
                _equal(
                    raw,
                    outage
                    + getattr(row, f"{resource}_to_bess_mwh")
                    + getattr(row, f"{resource}_to_poc_mwh")
                    + getattr(row, f"{resource}_curtailed_mwh"),
                    f"{resource} custody",
                )
            _equal(
                row.charge_loss_mwh, charge * (1 - cfg.charge_efficiency), "charge loss"
            )
            _equal(
                row.discharge_loss_mwh,
                discharge / cfg.discharge_efficiency - discharge,
                "discharge loss",
            )
            _equal(
                row.soc_end_mwh,
                previous
                + charge * cfg.charge_efficiency
                - discharge / cfg.discharge_efficiency,
                "stored energy",
            )
            _equal(
                charge + row.unmet_charge_mwh,
                max(0, -cfg.dispatch_instruction_mw[index]) * cfg.step_h,
                "charge request",
            )
            _equal(
                discharge + row.unmet_discharge_mwh,
                max(0, cfg.dispatch_instruction_mw[index]) * cfg.step_h,
                "discharge request",
            )
            cap = 0 if cfg.poc_outage[index] else cfg.poc_limit_mw[index] * cfg.step_h
            if export + row.grid_to_bess_mwh > cap + ENERGY_TOLERANCE_MWH:
                raise ValueError("dispatch ledger exceeds the gross shared POC limit.")
            if (
                max(charge, discharge)
                > cfg.sizing.power_mw * cfg.step_h + ENERGY_TOLERANCE_MWH
            ):
                raise ValueError("dispatch ledger exceeds battery power.")
            if charge > 0 and discharge > 0:
                raise ValueError(
                    "dispatch ledger cannot charge and discharge together."
                )
            if cfg.bess_outage[index] and (charge > 0 or discharge > 0):
                raise ValueError("dispatch ledger operates a battery in outage.")
            if (row.grid_to_bess_mwh > 0 and cfg.charge_source[index] != "grid") or (
                row.wind_to_bess_mwh + row.solar_to_bess_mwh > 0
                and cfg.charge_source[index] != "renewable"
            ):
                raise ValueError("dispatch ledger violates the authored charge source.")
            if (
                not usable * cfg.minimum_soc_fraction - ENERGY_TOLERANCE_MWH
                <= row.soc_end_mwh
                <= usable * cfg.maximum_soc_fraction + ENERGY_TOLERANCE_MWH
            ):
                raise ValueError("dispatch ledger exceeds the authored SOC window.")
            previous = row.soc_end_mwh

    @property
    def feasible(self) -> bool:
        """True only when every instruction and the final-SOC target are met."""
        self.__post_init__()
        target = (
            self.inputs.sizing.energy_mwh
            * self.inputs.soh_fraction
            * self.inputs.final_soc_fraction
        )
        return all(
            max(row.unmet_charge_mwh, row.unmet_discharge_mwh) <= ENERGY_TOLERANCE_MWH
            for row in self.steps
        ) and math.isclose(
            self.steps[-1].soc_end_mwh, target, rel_tol=0, abs_tol=ENERGY_TOLERANCE_MWH
        )

    def model_dump(self) -> dict[str, Any]:
        """Emit JSON-first evidence with explicit limitations and no revenue fields."""
        self.__post_init__()
        return {
            "schema": "dutchbay.chronological_dispatch.v1",
            "input_sha256": self.inputs.sha256,
            "inputs": self.inputs.model_dump(),
            "steps": _json_values([asdict(row) for row in self.steps]),
            "feasible": self.feasible,
            "final_soc_error_mwh": self.steps[-1].soc_end_mwh
            - self.inputs.sizing.energy_mwh
            * self.inputs.soh_fraction
            * self.inputs.final_soc_fraction,
            "bankable": False,
            "energy_balance_semantics": "accounting_identity_not_independent_validation",
            "limitations": [
                "Hourly instruction feasibility only; no optimization or network study.",
                "Gross import plus export shares the authored POC cap; conservative, not net-metered trading.",
                "Pro-rata renewable source attribution is bookkeeping, not dispatch priority.",
                "Static authored SoH only; no cycle aging, augmentation, self-discharge or sub-hour dynamics.",
                "Tariff/LD provenance is retained but never valued; no dispatch right or merchant remuneration is inferred.",
                "No revenue, cashflow, IRR or DSCR apply path.",
            ],
        }
