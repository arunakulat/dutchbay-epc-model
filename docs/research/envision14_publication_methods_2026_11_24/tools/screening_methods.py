"""Source-independent illustrative arithmetic and fail-closed input checks.

Not a resource model, utility study, financial model or publication authorization.
All inputs are caller-provided; no project-specific datasets are embedded.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
import re
from typing import TypedDict


class WindAccountingResult(TypedDict):
    status: str
    owned_nameplate_mw: float
    owned_active_cap_mw: float
    gross_mwh: float
    waked_mwh: float
    net_mwh: float
    net_capacity_factor_on_assumed_cap: float
    probability_quantiles: None


class ExportCase(TypedDict):
    boundary: str
    selected_design: bool
    plant_rating_mva: float
    active_mw: float
    scr_magnitude_only: float
    n_minus_one_static_active_limit_mw: float
    n_minus_one_static_shortfall_mw: float


class ExportScreenResult(TypedDict):
    status: str
    physical_boundary: str
    cases: list[ExportCase]
    annual_energy_curtailment: None
    shared_asset_allocation: None
    transformer_impedance_modelled: bool
    utility_approval: bool


def positive(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"invalid {label}")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"invalid {label}") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"invalid {label}")
    return number


def fraction(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"invalid {label}")
    if not 0 <= value <= 1:
        raise ValueError(f"invalid {label}")
    return float(value)


def count(value: int, label: str) -> int:
    if type(value) is not int or not 1 <= value <= 1_000_000:
        raise ValueError(f"invalid {label}")
    return value


def wind_accounting(
    *,
    owned_units: int,
    nameplate_mw: float,
    cap_mw: float,
    gross_mwh: float,
    wake_loss: float,
    nonwake_retention: float,
    hours: float,
) -> WindAccountingResult:
    units = count(owned_units, "unit count")
    rating = positive(nameplate_mw, "nameplate")
    cap = positive(cap_mw, "active cap")
    duration = positive(hours, "hours")
    gross = positive(gross_mwh, "gross energy")
    loss = fraction(wake_loss, "wake loss")
    retention = fraction(nonwake_retention, "nonwake retention")
    nameplate = units * rating
    active_cap = units * cap
    energy_cap = active_cap * duration
    if not all(math.isfinite(v) and v > 0 for v in (nameplate, active_cap, energy_cap)):
        raise ValueError("nonfinite or underflowed capability")
    if cap > rating or gross > energy_cap:
        raise ValueError("energy or derating exceeds assumed active capability")
    waked = gross * (1 - loss)
    net = waked * retention
    return {
        "status": "ILLUSTRATIVE_NON_BANKABLE",
        "owned_nameplate_mw": nameplate,
        "owned_active_cap_mw": active_cap,
        "gross_mwh": gross,
        "waked_mwh": waked,
        "net_mwh": net,
        "net_capacity_factor_on_assumed_cap": net / energy_cap,
        "probability_quantiles": None,
    }


def paired_export_screen(
    *,
    nominal_kv: float,
    source_fault_mva: float,
    line_r_ohm: float,
    line_x_ohm: float,
    own_mva: float,
    own_mw: float,
    external_mva: float,
    external_mw: float,
    transformer_mva: float,
    transformer_count: int,
    power_factor: float,
) -> ExportScreenResult:
    v = positive(nominal_kv, "voltage")
    fault = positive(source_fault_mva, "source fault")
    r = positive(line_r_ohm, "line resistance")
    x = positive(line_x_ohm, "line reactance")
    rating = positive(own_mva, "own MVA")
    active = positive(own_mw, "own MW")
    ext_rating = positive(external_mva, "external MVA")
    ext_active = positive(external_mw, "external MW")
    tx = positive(transformer_mva, "transformer MVA")
    n = count(transformer_count, "transformer count")
    pf = fraction(power_factor, "power factor")
    if active > rating or ext_active > ext_rating or n < 2 or pf == 0:
        raise ValueError("inconsistent illustrative electrical ratings")
    v_squared = v * v
    if not math.isfinite(v_squared) or v_squared <= 0:
        raise ValueError("invalid squared voltage")
    z = v_squared / fault + math.hypot(r, x)
    if not math.isfinite(z) or z <= 0:
        raise ValueError("invalid equivalent impedance")
    equivalent_fault = v_squared / z
    static_limit = (n - 1) * tx * pf
    if not all(math.isfinite(q) and q > 0 for q in (equivalent_fault, static_limit)):
        raise ValueError("invalid illustrative fault or capacity")
    cases: list[ExportCase] = []
    for label, shared in (("export_excluded", False), ("shared_export", True)):
        mw = active + (ext_active if shared else 0)
        mva = rating + (ext_rating if shared else 0)
        scr = equivalent_fault / mva
        if not all(math.isfinite(q) and q > 0 for q in (mw, mva, scr)):
            raise ValueError("invalid combined illustrative rating or SCR")
        cases.append(
            {
                "boundary": label,
                "selected_design": False,
                "plant_rating_mva": mva,
                "active_mw": mw,
                "scr_magnitude_only": scr,
                "n_minus_one_static_active_limit_mw": static_limit,
                "n_minus_one_static_shortfall_mw": max(0.0, mw - static_limit),
            }
        )
    return {
        "status": "ILLUSTRATIVE_NON_BANKABLE",
        "physical_boundary": "UNKNOWN",
        "cases": cases,
        "annual_energy_curtailment": None,
        "shared_asset_allocation": None,
        "transformer_impedance_modelled": False,
        "utility_approval": False,
    }


def validate_curve_snapshot(
    data: bytes, expected_sha256: str, nameplate_kw: float
) -> tuple[tuple[float, float, float], ...]:
    """Validate caller-supplied tabular bytes without retaining or emitting them."""
    rating = positive(nameplate_kw, "nameplate kW")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("invalid expected digest")
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("curve digest mismatch")
    if len(data) > 1_000_000:
        raise ValueError("curve byte limit exceeded")
    reader = csv.DictReader(io.StringIO(data.decode("utf-8"), newline=""))
    if reader.fieldnames != ["wind_speed_ms", "power_kw", "thrust_coefficient"]:
        raise ValueError("curve schema mismatch")
    parsed: list[tuple[float, float, float]] = []
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("curve row shape mismatch")
        try:
            ws, p, ct = map(float, row.values())
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid curve number") from exc
        if not all(math.isfinite(v) for v in (ws, p, ct)):
            raise ValueError("nonfinite curve value")
        if ws < 0 or not 0 <= p <= rating or not 0 <= ct <= 2:
            raise ValueError("illustrative curve bounds exceeded")
        if parsed and ws <= parsed[-1][0]:
            raise ValueError("wind speed must increase strictly")
        parsed.append((ws, p, ct))
    if len(parsed) < 2:
        raise ValueError("insufficient curve rows")
    return tuple(parsed)
