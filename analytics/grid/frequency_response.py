"""Frequency-response de-load / droop headroom sizing (D7, #883).

Sizes the ACTIVE-POWER headroom a plant must hold back to meet a grid-code frequency
ride-through / primary-frequency-response requirement, and the annual ENERGY it foregoes
to hold it (the de-load opportunity cost). This is the light companion to the
:mod:`analytics.grid.harmonics` power-quality screen: where harmonics answers the
voltage-distortion / flicker question, this answers *how much MW (and MWh/yr) does the
frequency-response droop obligation cost the plant?*

The obligation is parameterised from the grid-code frequency ride-through band
(``gridcode.freq_ride_through`` / the D0 fixture's ``freq_trip_hz`` table) plus a droop
setting: a plant on ``R`` % droop that de-loads to reserve headroom for over-frequency
down-regulation (and/or holds a mandated reserve fraction) foregoes energy proportional
to the reserve it carries. The sizing is a SCREENING approximation — a true
primary-frequency-response study is a dynamic (RMS/EMT) run against the utility base case.

PURE PYTHON — no optional grid library. There is no frequency-domain solve here; the
sizing is closed-form (droop × band × capacity-factor). It is imported cleanly by the
default (grid-free) install and carries its own coverage. Every result is ADVISORY only;
nothing here feeds the finance engine (committed scenarios stay byte-identical).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

#: Nominal system frequency (Hz) for Sri Lanka / the modelled grid.
NOMINAL_FREQ_HZ = 50.0

#: Default conventional continuous over/under-frequency band (Hz) when the grid code does
#: not declare one — the conventional 47.5–51.5 Hz continuous-operation window.
DEFAULT_FREQ_BAND_HZ: tuple[float, float] = (47.5, 51.5)

#: Default governor droop (fraction, e.g. 0.04 = 4 %) — the conventional primary-frequency
#: -response droop when the grid code / config does not declare one.
DEFAULT_DROOP = 0.04

#: Default over-frequency dead-band (Hz): the frequency deviation below which no
#: down-regulation (de-load) is demanded. 0.15 Hz is a conventional continental value.
DEFAULT_DEADBAND_HZ = 0.15

#: Default primary-frequency-response band (Hz): the over-frequency deviation (beyond the
#: dead-band) at which FULL droop de-load is reached — the plant de-loads proportionally
#: across this band, so the reserve it must carry is sized on THIS deviation, not the far
#: continuous-operation trip edge (which is tens of times wider). 0.2 Hz is a conventional
#: primary-response band; the effective de-load deviation is capped to it.
DEFAULT_RESPONSE_BAND_HZ = 0.2

#: Hours in a (non-leap) year — the horizon the energy-foregone figure is annualised over.
HOURS_PER_YEAR = 8760.0


@dataclass(frozen=True)
class FrequencyResponseHeadroom:
    """The sized frequency-response de-load headroom for a plant (pure data).

    Fields
        droop: the governor droop fraction the sizing used (e.g. 0.04 = 4 %).
        reserve_fraction: the fraction of rated active power held back as headroom
            (0 → 1). This is the larger of the explicit mandated reserve fraction and the
            droop-implied down-regulation the over-frequency band edge demands.
        headroom_mw: the MW of active-power reserve (``reserve_fraction × rated_mw``).
        energy_foregone_mwh_yr: the annual energy (MWh/yr) foregone to hold that reserve,
            ``headroom_mw × capacity_factor × 8760`` — the de-load opportunity cost.
        over_freq_edge_hz / under_freq_edge_hz: the continuous over/under-frequency band
            edges the sizing read from the grid code (Hz).
        source: a human string identifying where the band / droop came from.
    """

    droop: float
    reserve_fraction: float
    headroom_mw: float
    energy_foregone_mwh_yr: float
    over_freq_edge_hz: float
    under_freq_edge_hz: float
    source: str


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _longest_clearing_setpoint(rows: Any) -> float | None:
    """Setpoint (Hz) of the ``(setpoint, clearing_time)`` row with the max clearing time.

    Mirrors the ride-through envelope parser: the CONTINUOUS band edge in a direction is
    the trip setpoint held for the LONGEST clearing time (the outermost point at which the
    plant still operates continuously).
    """
    if not isinstance(rows, (list, tuple)) or not rows:
        return None
    best_setpoint: float | None = None
    best_time = -1.0
    for row in rows:
        if (
            isinstance(row, (list, tuple))
            and len(row) == 2
            and all(_is_number(v) for v in row)
        ):
            setpoint, clearing = float(row[0]), float(row[1])
            if clearing > best_time:
                best_time = clearing
                best_setpoint = setpoint
    return best_setpoint


def freq_band_from_gridcode(
    gridcode: Mapping[str, Any] | None,
) -> tuple[float, float, str]:
    """Resolve the continuous (under, over)-frequency band (Hz) from a gridcode block.

    Reads either an explicit ``freq_ride_through.continuous_hz: [lo, hi]`` /
    ``freq_continuous_hz: [lo, hi]`` pair, or a ``freq_trip_hz`` trip table (the D0-fixture
    shape: ``{underfrequency: [[setpoint, clearing], ...], overfrequency: [...]}``), from
    which the longest-clearing setpoint per direction gives the continuous edges. Falls
    back to the conventional 47.5–51.5 Hz window when absent. Returns
    ``(under_hz, over_hz, source)``.
    """
    lo, hi = DEFAULT_FREQ_BAND_HZ
    if not isinstance(gridcode, Mapping):
        return lo, hi, "defaults (no gridcode)"

    frt = gridcode.get("freq_ride_through")
    if isinstance(frt, Mapping):
        cont = frt.get("continuous_hz")
        if (
            isinstance(cont, Sequence)
            and not isinstance(cont, (str, bytes))
            and len(cont) == 2
            and all(_is_number(v) for v in cont)
        ):
            clo, chi = float(cont[0]), float(cont[1])
            if clo < chi:
                return clo, chi, "gridcode.freq_ride_through.continuous_hz"

    cont = gridcode.get("freq_continuous_hz")
    if (
        isinstance(cont, Sequence)
        and not isinstance(cont, (str, bytes))
        and len(cont) == 2
        and all(_is_number(v) for v in cont)
    ):
        clo, chi = float(cont[0]), float(cont[1])
        if clo < chi:
            return clo, chi, "gridcode.freq_continuous_hz"

    table = gridcode.get("freq_trip_hz")
    if isinstance(table, Mapping):
        under = _longest_clearing_setpoint(table.get("underfrequency"))
        over = _longest_clearing_setpoint(table.get("overfrequency"))
        if under is not None:
            lo = under
        if over is not None:
            hi = over
        if under is not None or over is not None:
            return lo, hi, "gridcode.freq_trip_hz"

    return lo, hi, "defaults (gridcode present, no frequency band)"


def droop_reserve_fraction(
    *,
    over_freq_edge_hz: float,
    droop: float,
    deadband_hz: float = DEFAULT_DEADBAND_HZ,
    response_band_hz: float = DEFAULT_RESPONSE_BAND_HZ,
    nominal_hz: float = NOMINAL_FREQ_HZ,
) -> float:
    """Fraction of rated P a droop controller must de-load for primary frequency response.

    On ``R`` (fraction) droop, a per-unit frequency deviation ``Δf/f_n`` beyond the
    dead-band commands a ``(Δf/f_n)/R`` per-unit change in active power. For OVER-frequency
    the plant must be able to REDUCE output by that fraction, so it carries that much
    DOWN-regulation headroom (de-load). The de-load deviation is the over-frequency band
    excursion beyond the dead-band, but CAPPED at ``response_band_hz`` — full droop de-load
    is reached at the edge of the primary-response band, not at the far continuous-operation
    trip edge (which is tens of times wider and would imply an unphysical 50–70 % reserve).
    Clamped to [0, 1].

    Args:
        over_freq_edge_hz: the continuous over-frequency band edge (Hz) from the grid code.
        droop: the governor droop fraction (must be > 0).
        deadband_hz: the over-frequency dead-band (Hz) below which no de-load is demanded.
        response_band_hz: the over-frequency deviation (Hz, beyond the dead-band) at which
            FULL droop de-load is reached — the effective de-load deviation is capped here.
        nominal_hz: the nominal system frequency (Hz).

    Raises:
        ValueError: for a non-positive droop or nominal frequency (CESSPIT — no silent
            default that would hide a mis-specified droop).
    """
    if droop <= 0.0:
        raise ValueError(f"droop must be > 0 (a fraction, e.g. 0.04), got {droop!r}.")
    if nominal_hz <= 0.0:
        raise ValueError(f"nominal_hz must be > 0, got {nominal_hz!r}.")
    excursion_hz = max(0.0, over_freq_edge_hz - nominal_hz - max(0.0, deadband_hz))
    delta_hz = min(excursion_hz, max(0.0, response_band_hz))
    frac = (delta_hz / nominal_hz) / droop
    return max(0.0, min(1.0, frac))


def size_frequency_response_headroom(
    *,
    rated_mw: float,
    gridcode: Mapping[str, Any] | None,
    capacity_factor: float,
    droop: float | None = None,
    mandated_reserve_fraction: float = 0.0,
    deadband_hz: float = DEFAULT_DEADBAND_HZ,
    response_band_hz: float = DEFAULT_RESPONSE_BAND_HZ,
    nominal_hz: float = NOMINAL_FREQ_HZ,
    hours_per_year: float = HOURS_PER_YEAR,
) -> FrequencyResponseHeadroom:
    """Size the frequency-response de-load headroom + annual energy foregone (pure).

    The reserve fraction the plant must carry is the LARGER of (a) an explicitly mandated
    reserve fraction and (b) the droop-implied down-regulation the over-frequency band edge
    demands (:func:`droop_reserve_fraction`). The energy foregone annualises the reserve MW
    over the year at the plant's capacity factor (the energy the de-loaded MW would have
    produced). Everything is ADVISORY only — a screening opportunity-cost figure.

    Args:
        rated_mw: the plant rated active power (MW; > 0).
        gridcode: the grid-code block (supplies the frequency band); may be ``None``.
        capacity_factor: the plant capacity factor (0 → 1) used to annualise the reserve.
        droop: governor droop fraction; defaults to :data:`DEFAULT_DROOP` when ``None``.
        mandated_reserve_fraction: an explicit mandated reserve fraction (0 → 1).
        deadband_hz / nominal_hz / hours_per_year: sizing constants.

    Raises:
        ValueError: for a non-positive ``rated_mw`` or a capacity factor / mandated
            reserve fraction outside [0, 1] (CESSPIT — no silent clamp of bad inputs).
    """
    if rated_mw <= 0.0:
        raise ValueError(f"rated_mw must be > 0, got {rated_mw!r}.")
    if not 0.0 <= capacity_factor <= 1.0:
        raise ValueError(f"capacity_factor must be in [0, 1], got {capacity_factor!r}.")
    if not 0.0 <= mandated_reserve_fraction <= 1.0:
        raise ValueError(
            "mandated_reserve_fraction must be in [0, 1], got "
            f"{mandated_reserve_fraction!r}."
        )
    r = DEFAULT_DROOP if droop is None else float(droop)
    under_hz, over_hz, source = freq_band_from_gridcode(gridcode)
    droop_frac = droop_reserve_fraction(
        over_freq_edge_hz=over_hz,
        droop=r,
        deadband_hz=deadband_hz,
        response_band_hz=response_band_hz,
        nominal_hz=nominal_hz,
    )
    reserve_fraction = max(float(mandated_reserve_fraction), droop_frac)
    headroom_mw = reserve_fraction * float(rated_mw)
    energy_foregone = headroom_mw * float(capacity_factor) * float(hours_per_year)
    return FrequencyResponseHeadroom(
        droop=r,
        reserve_fraction=reserve_fraction,
        headroom_mw=headroom_mw,
        energy_foregone_mwh_yr=energy_foregone,
        over_freq_edge_hz=over_hz,
        under_freq_edge_hz=under_hz,
        source=source,
    )


__all__ = [
    "NOMINAL_FREQ_HZ",
    "DEFAULT_FREQ_BAND_HZ",
    "DEFAULT_DROOP",
    "DEFAULT_DEADBAND_HZ",
    "DEFAULT_RESPONSE_BAND_HZ",
    "HOURS_PER_YEAR",
    "FrequencyResponseHeadroom",
    "freq_band_from_gridcode",
    "droop_reserve_fraction",
    "size_frequency_response_headroom",
]
