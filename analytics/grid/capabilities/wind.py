"""Wind-turbine grid-capability plug-in (D4b, #876).

The per-technology capability plug-in for WIND. It answers two design-stage questions for
a wind resource's converter interface, keyed on the turbine converter topology
(``turbine.converter_type`` — :func:`finance.grid.grid_types.is_type3_dfig` /
:func:`~finance.grid.grid_types.is_type4_full_converter`):

1. **Reactive capability (PQ envelope).** How much reactive power (Mvar) can the plant
   deliver across the active-power range, and does that meet the grid-code PQ box?
   The envelope SHAPE is turbine-topology dependent:

     * A **Type-4 full-converter** turbine decouples the machine from the grid through a
       full back-to-back converter, so its reactive headroom is a full ~RECTANGULAR PQ
       box: the ±Q limit is (approximately) CONSTANT across the whole 0→rated active-power
       range (S-limited only near rated).
     * A **Type-3 DFIG** processes only the ~30 % rotor-slip power through its converter,
       so its reactive headroom SHRINKS AT PARTIAL LOAD: the ±Q range NARROWS as active
       power drops (a triangular-ish envelope), because the converter's reactive capacity
       is tied to the slip-power throughput.

   The governing (worst) operating point of a 0→rated active-power sweep sets the reported
   Mvar shortfall vs the grid-code demand and the PQ-box verdict — emitted as the D3
   :class:`analytics.contracts_v14.ReactiveCapabilityResult` (reused, advisory).

2. **LVRT ride-through.** Does the wind plant ride through the grid-code low-voltage dip?
   This is delegated to the shared D4a ANDES ride-through core
   (:func:`analytics.grid.ride_through.run_ride_through_case`), parameterised from the same
   D0 grid-code envelope. It is GATED (``run_dynamics``, default off) exactly like the
   core, so the default screen is static-only and never imports ``andes``.

SCREENING ONLY — design-stage. NOT the utility-accepted bankable connection study
(CEB/NSCC require PSS/E or PowerFactory against their confidential base case; a true FRT
study is an EMT run with the OEM ``.dyr``/``.dll``). Every result is ADVISORY
(``bankable=False``) and NEVER feeds the finance engine (committed scenarios stay
byte-identical / KPI-neutral).

CASPER
------
The reactive PQ-envelope + config math here is PURE Python and imports NO grid library.
The only optional-dependency path is the LVRT dynamics, which is delegated to the D4a
core's own ``andes``-behind-``_require_andes`` guard (never imported at module-import
time; the default grid-free install imports this module cleanly).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence, TypeGuard

from analytics.contracts_v14 import ReactiveCapabilityResult, RideThroughResult
from analytics.grid.reactive_screen import pf_to_qp_ratio
from analytics.grid.ride_through import (
    RideThroughEnvelope,
    envelope_from_fixture,
    run_ride_through_case,
)
from finance.grid.grid_types import is_type3_dfig, is_type4_full_converter

#: Provenance stamped on the wind capability result (distinct from the pandapower screen —
#: this is the topology-aware analytical PQ envelope, not an AC load-flow).
_WIND_CAPABILITY_PROVENANCE = (
    "In-house Python design-stage WIND reactive-capability screen (analytical PQ envelope "
    "from the turbine converter topology: Type-4 full-converter ~rectangular box; Type-3 "
    "DFIG slip-power-limited box narrowing at partial load). NOT the utility-accepted "
    "bankable grid-connection study — CEB/NSCC require PSS/E or PowerFactory against their "
    "confidential grid base case."
)

#: Number of active-power steps (0 -> rated, inclusive) in the PQ-envelope sweep.
_DEFAULT_P_STEPS = 5

#: The minimum fraction of the converter's reactive rating a Type-3 DFIG retains at ZERO
#: active power. A pure slip-power model would give 0 Mvar at P=0; real DFIGs keep a small
#: magnetising/converter reserve, so the narrowing floors at this fraction rather than
#: collapsing to zero. Type-4 turbines ignore this (their box does not narrow).
_DFIG_QMIN_FRACTION_AT_ZERO_P = 0.10


@dataclass(frozen=True)
class WindConverterSpec:
    """Resolved wind-turbine converter descriptor for the PQ envelope (pure data).

    Fields
        converter_type: the canonical turbine topology token
            (``"type3_dfig"`` | ``"type4_full_converter"``).
        is_full_converter: True for a Type-4 full-converter turbine (rectangular PQ box);
            False for a Type-3 DFIG (partial-load-narrowing box).
        rated_mva: the aggregate wind plant rating (MVA) — the PQ-box S base.
        q_max_mvar: the ±Q reactive rating (Mvar) at RATED active power (the widest edge of
            the box). Resolved from an explicit ``q_max_mvar`` or from a ``pf_range`` +
            ``rated_mva`` (Q = rated · tan(acos(pf))).
    """

    converter_type: str
    is_full_converter: bool
    rated_mva: float
    q_max_mvar: float


def resolve_wind_converter_spec(grid: Mapping[str, Any]) -> WindConverterSpec:
    """Parse the wind converter descriptor from a per-tech ``grid`` block (pure Python).

    Reads (strict — CESSPIT, no silent defaults):
      * ``turbine.converter_type`` — a recognised wind-turbine converter enum
        (``type3_dfig`` / ``type4_full_converter`` incl. aliases). An unknown / absent
        value raises rather than silently assuming a topology.
      * ``rated_mva`` (MVA; > 0) — the aggregate wind plant rating.
      * the ±Q reactive rating at rated power, from EITHER an explicit
        ``reactive_capability.max_q_mvar`` OR a ``turbine.pf_range`` / ``pf_range``
        (Q = rated_mva · tan(acos(pf))).

    Args:
        grid: the per-tech ``generation.technologies.wind.grid`` block.

    Raises:
        ValueError: on a missing/unknown converter type, a non-positive rating, or an
            undetermined reactive rating (no explicit Q and no pf_range).
    """
    turbine = grid.get("turbine")
    turbine_map = turbine if isinstance(turbine, Mapping) else {}
    converter_raw = turbine_map.get("converter_type", grid.get("converter_type"))

    if is_type4_full_converter(converter_raw):
        canonical, full = "type4_full_converter", True
    elif is_type3_dfig(converter_raw):
        canonical, full = "type3_dfig", False
    else:
        raise ValueError(
            "wind grid interface requires turbine.converter_type to be a recognised wind "
            "turbine topology (type3_dfig | type4_full_converter), got "
            f"{converter_raw!r}."
        )

    rated = grid.get("rated_mva")
    if not _is_positive_number(rated):
        raise ValueError(
            f"wind grid interface requires rated_mva (MVA; > 0), got {rated!r}."
        )
    rated_mva = float(rated)

    q_max = _resolve_q_max_mvar(grid, turbine_map, rated_mva)
    return WindConverterSpec(
        converter_type=canonical,
        is_full_converter=full,
        rated_mva=rated_mva,
        q_max_mvar=q_max,
    )


def _resolve_q_max_mvar(
    grid: Mapping[str, Any], turbine: Mapping[str, Any], rated_mva: float
) -> float:
    """Resolve the ±Q reactive rating (Mvar) at RATED active power (strict, pure Python)."""
    cap = grid.get("reactive_capability")
    if isinstance(cap, Mapping) and "max_q_mvar" in cap:
        q_max = abs(float(cap["max_q_mvar"]))
        if q_max <= 0.0:
            raise ValueError(
                f"wind reactive_capability.max_q_mvar must be > 0, got {cap['max_q_mvar']!r}."
            )
        return q_max

    pf_range = turbine.get("pf_range", grid.get("pf_range"))
    if (
        isinstance(pf_range, Sequence)
        and not isinstance(pf_range, (str, bytes))
        and len(pf_range) == 2
    ):
        # The BINDING reactive rating is the tighter (smaller |pf|) endpoint — the pf the
        # plant must hold demands the most Mvar there.
        pf_binding = min(abs(float(pf_range[0])), abs(float(pf_range[1])))
        if pf_binding <= 0.0 or pf_binding > 1.0:
            raise ValueError(
                f"wind turbine.pf_range endpoints must have magnitude in (0, 1], got "
                f"{pf_range!r}."
            )
        return rated_mva * pf_to_qp_ratio(pf_binding)

    raise ValueError(
        "wind reactive rating undetermined — supply reactive_capability.max_q_mvar or a "
        "turbine.pf_range [lag, lead] (with rated_mva) so ±Q at rated can be derived."
    )


def q_capability_mvar_at_p(spec: WindConverterSpec, p_mw: float) -> float:
    """Reactive (±Q, Mvar) capability of the wind plant at active power ``p_mw`` (PURE).

    The envelope SHAPE is the crux of D4b — it is turbine-topology dependent:

      * **Type-4 full-converter** — the reactive headroom is a ~RECTANGULAR box: the ±Q
        limit is CONSTANT (= ``spec.q_max_mvar``) across the whole active-power range
        (the full converter is not throughput-limited by active power for a screen).
      * **Type-3 DFIG** — the reactive headroom NARROWS at partial load: the ±Q limit
        scales roughly LINEARLY with the active-power fraction (the converter processes
        only slip power, so its Mvar capacity falls with P), flooring at
        :data:`_DFIG_QMIN_FRACTION_AT_ZERO_P` of the rated Q at zero active power (a small
        magnetising/converter reserve rather than a hard zero).

    Args:
        spec: the resolved wind converter descriptor.
        p_mw: the active-power operating point (MW; clamped to [0, rated]).

    Returns:
        The ±Q magnitude (Mvar) available at that operating point (>= 0).
    """
    rated = spec.rated_mva
    frac = 0.0 if rated <= 0.0 else max(0.0, min(1.0, abs(float(p_mw)) / rated))
    if spec.is_full_converter:
        # Rectangular box: full ±Q at every active-power point.
        return spec.q_max_mvar
    # DFIG: linear narrowing from the zero-P floor up to the full rated Q at rated P.
    floor = _DFIG_QMIN_FRACTION_AT_ZERO_P
    scale = floor + (1.0 - floor) * frac
    return spec.q_max_mvar * scale


@dataclass(frozen=True)
class WindPQEnvelopePoint:
    """One swept operating point of the wind PQ envelope (pure data, grid-free testable).

    Fields
        p_mw: the active-power operating point (MW).
        q_available_mvar: the ±Q the plant can deliver there (from
            :func:`q_capability_mvar_at_p`).
        q_required_mvar: the ±Q the grid code demands there (|P| · tan(acos(pf_required))).
        shortfall_mvar: ``max(0, q_required - q_available)`` — the Mvar gap at this point.
    """

    p_mw: float
    q_available_mvar: float
    q_required_mvar: float
    shortfall_mvar: float


def build_wind_pq_envelope(
    spec: WindConverterSpec,
    pf_required: float,
    *,
    p_steps: int = _DEFAULT_P_STEPS,
) -> list[WindPQEnvelopePoint]:
    """Sweep P (0 -> rated) and build the wind PQ envelope points (PURE, grid-free).

    At each active-power step the grid-code reactive DEMAND is ``|P|·tan(acos(pf_required))``
    and the AVAILABLE ±Q comes from the topology-aware :func:`q_capability_mvar_at_p`. The
    per-point shortfall is the gap between them. The governing (worst-shortfall) point is
    selected by the caller.

    Args:
        spec: the resolved wind converter descriptor.
        pf_required: the binding grid-code power-factor magnitude (in (0, 1]).
        p_steps: number of active-power steps (>= 2; clamped).

    Raises:
        ValueError: if ``pf_required`` is not a power-factor magnitude in (0, 1].
    """
    if not (0.0 < float(pf_required) <= 1.0):
        raise ValueError(
            f"pf_required must be a power-factor magnitude in (0, 1], got {pf_required!r}."
        )
    qp_ratio = pf_to_qp_ratio(pf_required)
    steps = max(2, int(p_steps))
    points: list[WindPQEnvelopePoint] = []
    for i in range(steps):
        p_mw = spec.rated_mva * i / (steps - 1)
        q_avail = q_capability_mvar_at_p(spec, p_mw)
        q_req = abs(p_mw) * qp_ratio
        points.append(
            WindPQEnvelopePoint(
                p_mw=p_mw,
                q_available_mvar=q_avail,
                q_required_mvar=q_req,
                shortfall_mvar=max(0.0, q_req - q_avail),
            )
        )
    return points


def _governing_point(points: Sequence[WindPQEnvelopePoint]) -> WindPQEnvelopePoint:
    """The worst (max-shortfall) envelope point; ties break to the higher active power."""
    return max(points, key=lambda pt: (pt.shortfall_mvar, pt.p_mw))


def _binding_pf_magnitude(grid: Mapping[str, Any]) -> tuple[float, float, float]:
    """Return (pf_required_magnitude, pf_min_signed, pf_max_signed) from ``gridcode.pf_range``.

    Strict (CESSPIT): an absent/ill-formed ``gridcode.pf_range`` raises — the screen never
    silently assumes a unity-pf (no reactive) demand.
    """
    gridcode = grid.get("gridcode")
    pf_range = gridcode.get("pf_range") if isinstance(gridcode, Mapping) else None
    if (
        not isinstance(pf_range, Sequence)
        or isinstance(pf_range, (str, bytes))
        or len(pf_range) != 2
    ):
        raise ValueError(
            "wind capability screen requires grid.gridcode.pf_range [pf_lag, pf_lead] "
            "(the grid-code power-factor envelope the plant must hold at the POC)."
        )
    pf_min, pf_max = float(pf_range[0]), float(pf_range[1])
    pf_required = min(abs(pf_min), abs(pf_max))
    if not (0.0 < pf_required <= 1.0):
        raise ValueError(
            f"grid.gridcode.pf_range endpoints must have magnitude in (0, 1], got "
            f"{pf_range!r}."
        )
    return pf_required, pf_min, pf_max


def _pf_at_poc(p_mw: float, q_mvar: float) -> float:
    """Signed power factor from (P, Q) at the governing point (sign follows Q)."""
    s = math.hypot(p_mw, q_mvar)
    if s <= 0.0:
        return 1.0
    pf = abs(p_mw) / s
    return math.copysign(pf, q_mvar) if q_mvar != 0.0 else 1.0


def assemble_reactive_result(
    spec: WindConverterSpec,
    grid: Mapping[str, Any],
    *,
    p_steps: int = _DEFAULT_P_STEPS,
) -> ReactiveCapabilityResult:
    """Build the advisory :class:`ReactiveCapabilityResult` for the wind PQ envelope (PURE).

    Sweeps the topology-aware PQ envelope, picks the governing (worst-shortfall) point, and
    assembles the D3 reactive result. ``mvar_available`` is the ±Q available at the
    governing point (which, for a DFIG, is the NARROWED partial-load value that governs);
    ``mvar_required`` is the grid-code demand there. Advisory (``bankable=False``).
    """
    pf_required, pf_min, pf_max = _binding_pf_magnitude(grid)
    points = build_wind_pq_envelope(spec, pf_required, p_steps=p_steps)
    gov = _governing_point(points)
    # The achievable pf at the governing point uses the Q actually deliverable there
    # (capped at what the code demands — you don't over-supply reactive).
    q_deliver = min(gov.q_available_mvar, gov.q_required_mvar)
    pf_poc = _pf_at_poc(gov.p_mw, q_deliver)
    return ReactiveCapabilityResult.from_screen(
        pf_required_min=pf_min,
        pf_required_max=pf_max,
        mvar_required=gov.q_required_mvar,
        mvar_available=gov.q_available_mvar,
        pf_at_poc=pf_poc,
        governing_p_mw=gov.p_mw,
        governing_grid_v_pu=None,
        governing_converged=True,
        method="wind_pq_envelope",
        provenance=_WIND_CAPABILITY_PROVENANCE,
        notes=(
            f"Wind {spec.converter_type} PQ envelope over P(0->rated={spec.rated_mva} MVA); "
            f"±Q rated {spec.q_max_mvar:.3f} Mvar. "
            + (
                "Type-4 full-converter ~rectangular box (±Q constant across P). "
                if spec.is_full_converter
                else "Type-3 DFIG box NARROWS at partial load (±Q scales with P). "
            )
            + "Mvar shortfall is the gap at the governing (worst) operating point — the "
            "STATCOM/MSC sizing figure. Design-stage screen — confirm with the utility's "
            "PQ requirement + base case."
        ),
    )


@dataclass(frozen=True)
class WindCapabilityResult:
    """Bundled advisory wind grid-capability result (reactive + LVRT ride-through).

    Fields
        converter_type: the resolved turbine topology
            (``"type3_dfig"`` | ``"type4_full_converter"``).
        reactive: the D3 :class:`ReactiveCapabilityResult` for the PQ envelope (advisory).
        lvrt: the D4a :class:`RideThroughResult` for the LVRT case (advisory). With the
            dynamics gate off (default) this is a NOT-RUN advisory (envelope parsed, ANDES
            not run); with the gate on it carries the ANDES verdict.
        envelope_points: the swept PQ-envelope points (pure data, for reporting/inspection).
    """

    converter_type: str
    reactive: ReactiveCapabilityResult
    lvrt: RideThroughResult
    envelope_points: tuple[WindPQEnvelopePoint, ...]


def screen_wind_capability(
    grid: Mapping[str, Any],
    *,
    p_steps: int = _DEFAULT_P_STEPS,
    run_dynamics: bool = False,
    fixture_path: Path | str | None = None,
    ride_through_envelope: RideThroughEnvelope | None = None,
) -> WindCapabilityResult:
    """Screen a wind resource's grid capability: PQ-envelope reactive + LVRT ride-through.

    Resolves the turbine converter topology, builds the topology-aware reactive PQ envelope
    (:func:`assemble_reactive_result`), and drives the LVRT ride-through case through the
    shared D4a core (:func:`analytics.grid.ride_through.run_ride_through_case`) — GATED by
    ``run_dynamics`` (default off, so no ANDES import and a NOT-RUN LVRT advisory).

    Args:
        grid: the per-tech ``generation.technologies.wind.grid`` block. Reads
            ``turbine.converter_type``, ``rated_mva``, the reactive rating
            (``reactive_capability.max_q_mvar`` or ``turbine.pf_range``), and
            ``gridcode.pf_range`` (required).
        p_steps: number of active-power steps in the 0->rated PQ sweep.
        run_dynamics: the D4a dynamic-study gate. False (default) -> LVRT NOT-RUN, no ANDES.
        fixture_path: override the D0 grid-code fixture for the LVRT envelope.
        ride_through_envelope: pre-parsed LVRT envelope (skips the fixture read when given).

    Returns:
        :class:`WindCapabilityResult` — advisory (every sub-result ``bankable=False``).
    """
    spec = resolve_wind_converter_spec(grid)
    reactive = assemble_reactive_result(spec, grid, p_steps=p_steps)
    points = build_wind_pq_envelope(
        spec, _binding_pf_magnitude(grid)[0], p_steps=p_steps
    )

    env = (
        ride_through_envelope
        if ride_through_envelope is not None
        else envelope_from_fixture(fixture_path)
    )
    lvrt = run_ride_through_case("lvrt", run_dynamics=run_dynamics, envelope=env)

    return WindCapabilityResult(
        converter_type=spec.converter_type,
        reactive=reactive,
        lvrt=lvrt,
        envelope_points=tuple(points),
    )


def _is_positive_number(value: Any) -> TypeGuard[float]:
    """True iff ``value`` is a real (non-bool) number strictly greater than zero."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and float(value) > 0.0
    )


__all__ = [
    "WindConverterSpec",
    "WindPQEnvelopePoint",
    "WindCapabilityResult",
    "resolve_wind_converter_spec",
    "q_capability_mvar_at_p",
    "build_wind_pq_envelope",
    "assemble_reactive_result",
    "screen_wind_capability",
]
