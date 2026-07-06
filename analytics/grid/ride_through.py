"""Shared ANDES RMS ride-through dynamics core (D4a #875; D4b HVRT/frequency #892).

Generalises the D1 LVRT scaffold (:mod:`analytics.grid.ride_through_poc`) into ONE
parameterised ride-through core that runs the grid-code fault-ride-through cases against a
generic WECC IBR — **LVRT** (a voltage dip), **HVRT** (a voltage swell), and a
**frequency** excursion — and reports, per case, whether the plant rode through the
disturbance. The ride-through envelope (entry thresholds, k-factors, trip tables) is
parameterised from the redacted D0 grid-code fixture
(``tests/fixtures/grid/envision_enpcs01_gridcode.yaml``) rather than magic constants, so
the core is seeded from the OEM envelope.

Convergence is NOT compliance
-----------------------------
The ANDES RMS solve returns a raw convergence flag (``converged`` — a smoke test that the
time-domain integration exited cleanly). That flag is NEVER read as a PASS: a solve can
converge to a state where the IBR has tripped or the bus voltage has collapsed. A CLEANLY
CONVERGED solve derives its compliance verdict (``rode_through``) ONLY from the PHYSICAL
ENVELOPE — the measured post-disturbance voltage / frequency vs the entry threshold and
trip curve, and whether the IBR tripped.

A non-clean exit under an *applied* disturbance, though, is itself physical evidence of a
FAILURE, not an absence of evidence: when the ANDES TDS diverges / terminates early on a
stability-criteria violation while the disturbance is active, the plant did NOT ride
through — the solve blew up because the bus collapsed / the frequency ran away. That case
is a real breach → ``rode_through=False`` (NOT ``None``). ``rode_through=None`` (NOT-RUN /
UNSUPPORTED) is reserved for the cases that never physically exercised an envelope at all:
the gate-off static path, a disturbance that did not actually move the measured quantity
past its entry threshold (so nothing was tested), a case-SETUP failure where no candidate
network could be built, and a genuine measurement gap (e.g. an IBR-trip status that cannot
be read on a k-factor path — never flipped to a fabricated pass).

**All three cases are now physically modeled (D4b, #892).** LVRT injects a shunt impedance
fault (a real voltage DIP whose recovery is checked against the entry pu). **HVRT** applies
a real over-voltage swell — a **load rejection** (a large ``PQ`` load is toggled OFF
mid-run so the freed real+reactive power swells the bus) — and the verdict is derived from
the measured PEAK bus voltage vs the HVRT entry pu and the over-voltage trip curve plus
IBR-trip status. **Frequency** applies a real excursion — a **generator trip** (``Toggle``
of a synchronous machine) or a **load step**, moving system frequency — and the verdict is
derived from the measured nadir/zenith (frequency extreme) vs the continuous band and the
under/over-frequency trip curve. A disturbance that fails to move the quantity past its
entry threshold stays an honest NOT-RUN (nothing was exercised), never a spurious pass.

The dynamic model is the **generic WECC IBR** (REGCA1 / REECA1 / REPCA1 — whichever the
installed ANDES exposes on the bundled case). It is a SCREENING-grade RMS/positive-
sequence study, NOT the OEM-certified ``.dyr``/``.dll`` model: a true FRT compliance
study is an EMT (PSCAD/EMTP) run against the utility base case with the OEM binaries.
Every result is ADVISORY (``bankable=False``) and carries that disclaimer; nothing here
feeds the finance engine, so committed scenarios stay byte-identical (KPI-neutral).

CASPER
------
``andes`` is an OPTIONAL dependency of the ``[grid]`` extra. It is NEVER imported at
module-import time; the import is deferred to :func:`_require_andes`, which raises an
actionable ImportError at call-time if the extra is absent (mirroring
:func:`analytics.grid.reactive_screen._require_pandapower`). The default (grid-free)
install imports this module cleanly.

Default-off / dynamic-study gate
--------------------------------
The ANDES time-domain path is additionally gated behind a ``run_dynamics`` flag
(default ``False``). With the gate off, the core does only pure-Python envelope parsing
and case set-up (no ANDES import, no solve) and returns a NOT-RUN result — so the default
screen stays STATIC-only and ``andes`` is never imported by default even in a ``[grid]``
environment. The dynamics solve runs ONLY when a caller explicitly opts in
(``run_dynamics=True``), which is how the D-later gateway will wire the dynamic study
behind the master ``grid.study_enabled`` gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from analytics.contracts_v14 import RideThroughResult

# The D0 redacted grid-code fixture (referenced, never executed). Resolves relative to
# the repo root so the core seeds its ride-through envelope from the OEM values.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_D0_FIXTURE = (
    _REPO_ROOT / "tests" / "fixtures" / "grid" / "envision_enpcs01_gridcode.yaml"
)

#: Generic WECC IBR / synchronous device models we count as the "dynamics present" check
#: (REGCA1/REECA1/REPCA1 are the WECC generic renewable set the study targets; the rest
#: cover the ANDES-bundled Type-3 wind / PV / synchronous cases we fall back onto).
_IBR_MODELS = (
    "REGCA1",
    "REGCP1",
    "REECA1",
    "REPCA1",
    "WTARA1",
    "WTDTA1",
    "PVD1",
    "GENROU",
)

#: ANDES bundled example cases carrying an IBR, tried in order (self-contained core).
_CANDIDATE_CASES = (
    "ieee14/ieee14_wt3.xlsx",
    "ieee14/ieee14_regcp1.xlsx",
    "ieee14/ieee14_pvd1.xlsx",
)

#: The three ride-through case kinds this core generalises D1's single LVRT into.
RIDE_THROUGH_CASES = ("lvrt", "hvrt", "frequency")

# Fallbacks when the D0 fixture (or a key) is absent — so the core never hard-fails on a
# missing optional reference file. LVRT/HVRT entry pu mirror the conventional IEC/SLSEA
# ride-through window; freq band the conventional 47.5–51.5 Hz continuous window; the
# over-voltage / frequency TRIP curve edges mirror the conventional instantaneous-trip
# thresholds (a swell above ``_DEFAULT_OV_TRIP_PU`` or a frequency outside the
# ``_DEFAULT_FREQ_TRIP_HZ`` window is a disconnect).
_DEFAULT_LVRT_ENTER_PU = 0.9
_DEFAULT_HVRT_ENTER_PU = 1.1
_DEFAULT_LVRT_K = 2.0
_DEFAULT_HVRT_K = 0.0
_DEFAULT_FREQ_HZ = (47.5, 51.5)
_DEFAULT_OV_TRIP_PU = 1.3
_DEFAULT_FREQ_TRIP_HZ = (47.0, 52.0)
_NOMINAL_FREQ_HZ = 50.0


def _require_andes() -> Any:
    """Return the ``andes`` module or raise an actionable CASPER error if absent."""
    try:
        import andes  # noqa: F401

        return andes  # pragma: no cover - requires [grid] extra
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "The grid ride-through dynamics core requires the [grid] extra: "
            "pip install 'andes>=2.0'  (or  PIP_CONSTRAINT=constraints.txt "
            "pip install -e '.[grid]'). It is an OPTIONAL dependency — the base finance "
            "install never needs it."
        ) from exc


@dataclass(frozen=True)
class RideThroughEnvelope:
    """Ride-through envelope parsed from the D0 grid-code fixture (pure data).

    Fields
        lvrt_enter_pu / hvrt_enter_pu: the low-/high-voltage ride-through entry
            thresholds (pu) — the plant must stay connected for dips below
            ``lvrt_enter_pu`` and swells above ``hvrt_enter_pu`` per the trip tables.
        lvrt_k_factor / hvrt_k_factor: the fault-current (reactive) injection gains
            (dimensionless k-factor) the code demands during the dip / swell.
        freq_continuous_hz: the (under, over) frequency band (Hz) inside which the plant
            must ride through continuously (the widest continuous-operation window from
            the fixture's frequency trip table).
        ov_trip_pu: the over-voltage INSTANTANEOUS trip threshold (pu) — the shortest-
            clearing over-voltage setpoint from the fixture's ``volt_trip_pu`` table. A
            swell whose peak reaches this must disconnect, so a measured peak at/above it
            is a trip (HVRT breach) even if the plant would ride a smaller swell through.
        freq_trip_hz: the (under, over) INSTANTANEOUS frequency trip band (Hz) — the
            shortest-clearing under/over-frequency setpoints. A measured extreme beyond
            this band is an instantaneous trip (a frequency breach).
        source: a human string identifying where the envelope came from (fixture path or
            "defaults") for the result provenance/detail.
    """

    lvrt_enter_pu: float
    hvrt_enter_pu: float
    lvrt_k_factor: float
    hvrt_k_factor: float
    freq_continuous_hz: tuple[float, float]
    source: str
    # D4b (#892) trip-curve edges — defaulted so pre-D4b constructions (e.g. capability
    # tests seeding a bare envelope for the LVRT-only path) stay valid; the fixture parser
    # always supplies the fixture-derived values.
    ov_trip_pu: float = _DEFAULT_OV_TRIP_PU
    freq_trip_hz: tuple[float, float] = _DEFAULT_FREQ_TRIP_HZ


def _pcs_block(fixture_path: Path | str | None) -> tuple[Mapping[str, Any], str]:
    """Return the fixture's ``pcs`` mapping (or empty) plus a source-description string."""
    path = Path(fixture_path) if fixture_path is not None else _D0_FIXTURE
    if not path.is_file():
        return {}, "defaults (D0 fixture absent)"
    data = yaml.safe_load(path.read_text()) or {}
    pcs = data.get("pcs", {}) if isinstance(data, dict) else {}
    if not isinstance(pcs, Mapping):
        return {}, f"defaults ({path.name}: no pcs block)"
    return pcs, str(path.name)


def _freq_continuous_from_trip_table(pcs: Mapping[str, Any]) -> tuple[float, float]:
    """Widest continuous under/over-frequency band (Hz) from the fixture trip table.

    The fixture's ``freq_trip_hz`` gives ``(setpoint_hz @ clearing_time_s)`` pairs per
    direction. The CONTINUOUS band is bounded by the setpoint with the *longest* clearing
    time in each direction (the outermost point at which the plant still operates for an
    extended period). Falls back to the conventional 47.5–51.5 Hz window when absent.
    """
    table = pcs.get("freq_trip_hz")
    lo, hi = _DEFAULT_FREQ_HZ
    if isinstance(table, Mapping):
        under = _longest_clearing_setpoint(table.get("underfrequency"))
        over = _longest_clearing_setpoint(table.get("overfrequency"))
        if under is not None:
            lo = under
        if over is not None:
            hi = over
    return lo, hi


def _longest_clearing_setpoint(rows: Any) -> float | None:
    """Setpoint (Hz) of the ``(setpoint, clearing_time)`` row with the max clearing time."""
    return _extremal_clearing_setpoint(rows, longest=True)


def _shortest_clearing_setpoint(rows: Any) -> float | None:
    """Setpoint of the ``(setpoint, clearing_time)`` row with the MIN clearing time.

    The INSTANTANEOUS trip edge: the setpoint held for the SHORTEST clearing time is the
    outermost point at which the plant must disconnect near-immediately (the trip curve's
    hard edge). Used to seed the over-voltage / instantaneous frequency trip thresholds.
    """
    return _extremal_clearing_setpoint(rows, longest=False)


def _extremal_clearing_setpoint(rows: Any, *, longest: bool) -> float | None:
    """Setpoint of the ``(setpoint, clearing_time)`` row with the extremal clearing time.

    ``longest=True`` returns the max-clearing-time setpoint (continuous-band edge);
    ``longest=False`` the min-clearing-time setpoint (instantaneous trip edge). Malformed
    rows (wrong arity / non-numeric / bool) are skipped, so a bad table degrades to
    ``None`` rather than crashing (the caller falls back to a conventional default).
    """
    if not isinstance(rows, (list, tuple)) or not rows:
        return None
    best_setpoint: float | None = None
    best_time = float("-inf") if longest else float("inf")
    for row in rows:
        if (
            isinstance(row, (list, tuple))
            and len(row) == 2
            and all(
                isinstance(v, (int, float)) and not isinstance(v, bool) for v in row
            )
        ):
            setpoint, clearing = float(row[0]), float(row[1])
            if (longest and clearing > best_time) or (
                not longest and clearing < best_time
            ):
                best_time = clearing
                best_setpoint = setpoint
    return best_setpoint


def _ov_trip_from_volt_table(pcs: Mapping[str, Any]) -> float:
    """Over-voltage INSTANTANEOUS trip threshold (pu) from the fixture ``volt_trip_pu``.

    Reads ``volt_trip_pu.overvoltage`` — ``(pu @ clearing_time_s)`` rows — and returns the
    setpoint with the SHORTEST clearing time (the hard instantaneous-trip edge). Falls back
    to :data:`_DEFAULT_OV_TRIP_PU` when the table (or key) is absent or malformed.
    """
    table = pcs.get("volt_trip_pu")
    if isinstance(table, Mapping):
        over = _shortest_clearing_setpoint(table.get("overvoltage"))
        if over is not None:
            return over
    return _DEFAULT_OV_TRIP_PU


def _freq_trip_from_trip_table(pcs: Mapping[str, Any]) -> tuple[float, float]:
    """Instantaneous (under, over) frequency trip band (Hz) from ``freq_trip_hz``.

    The trip-curve HARD edge in each direction is the setpoint with the SHORTEST clearing
    time (near-instantaneous disconnect). Falls back to :data:`_DEFAULT_FREQ_TRIP_HZ` per
    direction when absent / malformed.
    """
    table = pcs.get("freq_trip_hz")
    lo, hi = _DEFAULT_FREQ_TRIP_HZ
    if isinstance(table, Mapping):
        under = _shortest_clearing_setpoint(table.get("underfrequency"))
        over = _shortest_clearing_setpoint(table.get("overfrequency"))
        if under is not None:
            lo = under
        if over is not None:
            hi = over
    return lo, hi


def envelope_from_fixture(
    fixture_path: Path | str | None = None,
) -> RideThroughEnvelope:
    """Parse the ride-through envelope from the D0 grid-code fixture (pure Python).

    Reads the ``pcs`` block's LVRT/HVRT entry thresholds, k-factors, and frequency trip
    table. Every field falls back to a conventional default when the fixture (or the key)
    is absent, so this never hard-fails on a missing optional reference file.
    """
    pcs, source = _pcs_block(fixture_path)
    lvrt_enter = _as_float(pcs.get("lvrt_enter_pu"), _DEFAULT_LVRT_ENTER_PU)
    hvrt_enter = _as_float(pcs.get("hvrt_enter_pu"), _DEFAULT_HVRT_ENTER_PU)
    lvrt_k = _as_float(pcs.get("lvrt_k_factor"), _DEFAULT_LVRT_K)
    hvrt_k = _as_float(pcs.get("hvrt_k_factor"), _DEFAULT_HVRT_K)
    freq_band = _freq_continuous_from_trip_table(pcs)
    ov_trip = _ov_trip_from_volt_table(pcs)
    freq_trip = _freq_trip_from_trip_table(pcs)
    return RideThroughEnvelope(
        lvrt_enter_pu=lvrt_enter,
        hvrt_enter_pu=hvrt_enter,
        lvrt_k_factor=lvrt_k,
        hvrt_k_factor=hvrt_k,
        freq_continuous_hz=freq_band,
        ov_trip_pu=ov_trip,
        freq_trip_hz=freq_trip,
        source=source,
    )


def _as_float(value: Any, default: float) -> float:
    """Coerce a fixture scalar to float, falling back to ``default`` when unusable."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


#: Disturbance mechanisms the core can inject (the physics behind each case). LVRT is a
#: shunt impedance fault; HVRT is a LOAD REJECTION (a load toggled off swells the bus);
#: frequency is a GENERATOR TRIP or a LOAD STEP (either moves system frequency). CESSPIT:
#: an unknown mechanism raises — there is no silent default disturbance.
DISTURBANCES = ("impedance_fault", "load_rejection", "generator_trip", "load_step")


@dataclass(frozen=True)
class RideThroughCaseSpec:
    """The resolved disturbance parameters for ONE ride-through case (pure data).

    ``kind`` is one of :data:`RIDE_THROUGH_CASES`; ``disturbance`` is the physical
    mechanism (one of :data:`DISTURBANCES`) the ANDES solve injects:

      * LVRT → ``impedance_fault``: a bus shunt impedance fault (``fault_x_pu``) DIPS the
        voltage; ``target_pu`` = the LVRT entry pu.
      * HVRT → ``load_rejection``: a large ``PQ`` load is toggled OFF at ``fault_start_s``
        so the freed power SWELLS the bus; ``target_pu`` = the HVRT entry pu and
        ``ov_trip_pu`` = the over-voltage instantaneous-trip edge.
      * frequency → ``generator_trip`` (default) or ``load_step``: a synchronous machine is
        tripped (under-frequency) or a load is stepped, moving system frequency;
        ``target_hz`` = the probed excursion and ``freq_trip_hz`` = the instantaneous
        under/over-frequency trip band.

    ``fault_x_pu`` is set only for the impedance-fault (LVRT) mechanism; ``ov_trip_pu`` /
    ``freq_trip_hz`` carry the trip-curve edges the HVRT / frequency verdicts screen against.
    """

    kind: str
    disturbance: str
    fault_bus: int
    fault_start_s: float
    fault_clear_s: float
    fault_x_pu: float | None
    target_pu: float | None
    target_hz: float | None
    ov_trip_pu: float | None
    freq_trip_hz: tuple[float, float] | None
    k_factor: float
    detail: str


def build_case_spec(
    kind: str,
    envelope: RideThroughEnvelope,
    *,
    fault_bus: int = 4,
    fault_start_s: float = 1.0,
    fault_clear_s: float = 1.1,
    lvrt_fault_x_pu: float = 0.05,
    freq_excursion_hz: float | None = None,
    freq_mechanism: str = "generator_trip",
) -> RideThroughCaseSpec:
    """Resolve one :class:`RideThroughCaseSpec` from the parsed envelope (pure Python).

    Args:
        kind: one of :data:`RIDE_THROUGH_CASES` (``"lvrt"`` | ``"hvrt"`` | ``"frequency"``).
        envelope: the ride-through envelope parsed from the D0 fixture.
        fault_bus / fault_start_s / fault_clear_s: the disturbance timing/location.
        lvrt_fault_x_pu: impedance (pu) for the LVRT dip — a partial dip that triggers the
            ride-through path yet keeps the positive-sequence RMS solve convergent (a
            bolted fault makes the solve singular).
        freq_excursion_hz: the frequency (Hz) the frequency case probes; ``None`` defaults
            to the fixture's continuous overfrequency edge (the binding excursion).
        freq_mechanism: the frequency disturbance to inject — ``"generator_trip"``
            (default; a synchronous machine is toggled off → under-frequency) or
            ``"load_step"`` (a load is stepped → over- or under-frequency).

    Raises:
        ValueError: for an unknown ``kind`` or an unknown ``freq_mechanism`` (CESSPIT — no
            silent default case / mechanism).
    """
    if kind not in RIDE_THROUGH_CASES:
        raise ValueError(
            f"unknown ride-through case {kind!r}; expected one of {RIDE_THROUGH_CASES}."
        )
    if kind == "lvrt":
        return RideThroughCaseSpec(
            kind="lvrt",
            disturbance="impedance_fault",
            fault_bus=fault_bus,
            fault_start_s=fault_start_s,
            fault_clear_s=fault_clear_s,
            fault_x_pu=lvrt_fault_x_pu,
            target_pu=envelope.lvrt_enter_pu,
            target_hz=None,
            ov_trip_pu=None,
            freq_trip_hz=None,
            k_factor=envelope.lvrt_k_factor,
            detail=(
                f"LVRT dip at bus-{fault_bus} ({fault_start_s}-{fault_clear_s}s, "
                f"x={lvrt_fault_x_pu} pu); ride-through entry {envelope.lvrt_enter_pu} pu, "
                f"k-factor {envelope.lvrt_k_factor} (from {envelope.source})."
            ),
        )
    if kind == "hvrt":
        return RideThroughCaseSpec(
            kind="hvrt",
            disturbance="load_rejection",
            fault_bus=fault_bus,
            fault_start_s=fault_start_s,
            fault_clear_s=fault_clear_s,
            fault_x_pu=None,
            target_pu=envelope.hvrt_enter_pu,
            target_hz=None,
            ov_trip_pu=envelope.ov_trip_pu,
            freq_trip_hz=None,
            k_factor=envelope.hvrt_k_factor,
            detail=(
                f"HVRT swell via LOAD REJECTION at t={fault_start_s}s; ride-through entry "
                f"{envelope.hvrt_enter_pu} pu, over-voltage trip {envelope.ov_trip_pu} pu, "
                f"k-factor {envelope.hvrt_k_factor} (from {envelope.source})."
            ),
        )
    # frequency
    if freq_mechanism not in ("generator_trip", "load_step"):
        raise ValueError(
            f"unknown freq_mechanism {freq_mechanism!r}; expected 'generator_trip' or "
            "'load_step'."
        )
    lo, hi = envelope.freq_continuous_hz
    excursion = freq_excursion_hz if freq_excursion_hz is not None else hi
    trip_lo, trip_hi = envelope.freq_trip_hz
    return RideThroughCaseSpec(
        kind="frequency",
        disturbance=freq_mechanism,
        fault_bus=fault_bus,
        fault_start_s=fault_start_s,
        fault_clear_s=fault_clear_s,
        fault_x_pu=None,
        target_pu=None,
        target_hz=excursion,
        ov_trip_pu=None,
        freq_trip_hz=envelope.freq_trip_hz,
        k_factor=0.0,
        detail=(
            f"Frequency ride-through probe to {excursion} Hz via {freq_mechanism}; "
            f"continuous band {lo}-{hi} Hz, instantaneous trip band {trip_lo}-{trip_hi} Hz "
            f"(from {envelope.source})."
        ),
    )


@dataclass(frozen=True)
class LvrtEvidence:
    """The PHYSICAL evidence a solved LVRT case yields (pure data, grid-free testable).

    Fields
        min_voltage_pu: the deepest bus voltage over the run (confirms a real dip was
            actually injected — a case with no measurable dip did not test the envelope).
        recovered_voltage_pu: the post-fault RECOVERED bus voltage (steady-state after
            fault clearance). The plant rode through only if this returns above the entry
            threshold — a collapse that fails to recover is a breach.
        ibr_tripped: whether any IBR device tripped offline during the run.
    """

    min_voltage_pu: float | None
    recovered_voltage_pu: float | None
    ibr_tripped: bool | None


def lvrt_rode_through(
    evidence: LvrtEvidence,
    envelope: RideThroughEnvelope,
    *,
    recovery_margin_pu: float = 0.0,
) -> bool | None:
    """Envelope-derived LVRT compliance verdict (PURE — no ANDES, grid-free testable).

    The verdict is derived from PHYSICAL EVIDENCE, never from a solver convergence flag:

      * ``None`` (NOT-RUN / UNSUPPORTED) if the evidence is missing — no measurable dip
        was injected (``min_voltage_pu`` is None or not actually below the entry pu, so
        the fault did not exercise the ride-through path) or the recovered voltage is
        unknown. We cannot claim a pass we did not physically validate.
      * ``False`` (breach) if the IBR tripped, OR the post-fault RECOVERED voltage failed
        to return at/above the entry threshold (``lvrt_enter_pu`` + margin) — i.e. the bus
        collapsed / did not recover.
      * ``True`` (rode through) only when a real dip was injected, no IBR tripped, and the
        voltage recovered above the entry threshold.

    Args:
        evidence: the physical LVRT evidence gathered from the solved case.
        envelope: the ride-through envelope (supplies ``lvrt_enter_pu``).
        recovery_margin_pu: extra pu the recovered voltage must clear the entry threshold
            by (default 0.0 — recovery to the entry pu counts).
    """
    vmin = evidence.min_voltage_pu
    vrec = evidence.recovered_voltage_pu
    enter = envelope.lvrt_enter_pu
    # NOT-RUN: no measurable dip below the entry pu means the ride-through path was never
    # exercised, so there is nothing to certify. Return an honest None.
    if vmin is None or vmin >= enter:
        return None
    if vrec is None:
        return None
    if evidence.ibr_tripped:
        return False
    return bool(vrec >= enter + recovery_margin_pu)


def _lvrt_dynamic_verdict(
    *,
    fault_applied: bool,
    solved: bool,
    converged: bool,
    evidence: LvrtEvidence | None,
    envelope: RideThroughEnvelope,
) -> bool | None:
    """Map a solved LVRT dynamics run to a ``rode_through`` verdict (PURE, grid-free).

    This is the reducer the ANDES LVRT path delegates to; it is deliberately andes-free so
    the collapse→False / setup-failure→None mapping is unit-testable without the [grid]
    extra. The rules, in order:

      * ``None`` (NOT-RUN) when no candidate case could even be set up and solved
        (``solved is False``) — a genuine setup failure, nothing was physically attempted.
      * ``None`` (NOT-RUN) for a solved run that did not actually apply a fault
        (``fault_applied is False``) — no disturbance was injected, so nothing to certify.
      * ``False`` (BREACH) when a fault WAS applied but the TDS did not exit cleanly
        (``converged is False``: diverged / early-terminated on a stability-criteria
        violation). An unstable solve under an active fault IS the collapse — the plant did
        not ride through. This is the deep/long-fault case; it is a real breach, not
        NOT-RUN.
      * otherwise (a fault was applied AND the solve converged cleanly) the verdict comes
        from the PHYSICAL ENVELOPE via :func:`lvrt_rode_through` (dip depth + post-fault
        recovery + IBR-trip), which itself may return True / False / None.

    Args:
        fault_applied: whether an LVRT impedance fault was injected (``fault_x_pu`` set).
        solved: whether a candidate ANDES case loaded and the TDS was actually run
            (regardless of exit code) — False only on a genuine case-setup failure.
        converged: the raw RMS smoke test (``exit_code == 0``): False on an early
            termination / divergence / stability-criteria violation.
        evidence: the physical LVRT evidence from the run (``None`` on a setup failure).
        envelope: the ride-through envelope (supplies ``lvrt_enter_pu``).
    """
    if not solved or evidence is None:
        return None
    if not fault_applied:
        return None
    if not converged:
        # An applied fault whose TDS diverged / terminated early on instability is a
        # COLLAPSE: the plant did not ride through. A real breach, NOT an honest NOT-RUN.
        return False
    return lvrt_rode_through(evidence, envelope)


# ─────────────────────────────────────────────────────────────────────────────
# D4b (#892) — HVRT (over-voltage swell) physical evidence + verdict (PURE).
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class HvrtEvidence:
    """The PHYSICAL evidence a solved HVRT (over-voltage swell) case yields (pure data).

    Fields
        max_voltage_pu: the PEAK bus voltage over the run — confirms a real swell was
            actually injected. A case whose peak never reaches the HVRT entry pu did not
            exercise the over-voltage ride-through path (nothing to certify → NOT-RUN).
        settled_voltage_pu: the post-event SETTLED bus voltage (steady-state after the
            load rejection / swell). The plant rode through only if the bus settles back
            at/below the entry pu — a voltage stuck above it is an over-voltage breach.
        ibr_tripped: whether any IBR device tripped offline during the run (True/False, or
            None when trip status could not be read).
    """

    max_voltage_pu: float | None
    settled_voltage_pu: float | None
    ibr_tripped: bool | None


def hvrt_rode_through(
    evidence: HvrtEvidence,
    envelope: RideThroughEnvelope,
    *,
    settle_margin_pu: float = 0.0,
) -> bool | None:
    """Envelope-derived HVRT compliance verdict (PURE — no ANDES, grid-free testable).

    Derived from PHYSICAL EVIDENCE (the measured swell), NEVER from a solver flag:

      * ``None`` (NOT-RUN) when no measurable SWELL was injected (``max_voltage_pu`` is
        None or never rose above the HVRT entry pu, so the over-voltage path was never
        exercised) or the settled voltage is unknown — nothing was physically validated.
      * ``False`` (breach) when the IBR tripped, OR the measured PEAK reached the
        over-voltage INSTANTANEOUS-trip threshold (``ov_trip_pu``: the swell hit the hard
        disconnect edge), OR the post-event bus did NOT settle back at/below the entry pu
        (``hvrt_enter_pu`` − margin: it stayed swollen).
      * ``True`` (rode through) only when a real swell above the entry pu was injected, no
        IBR tripped, the peak stayed below the instantaneous-trip edge, and the bus settled
        back inside the continuous window.

    Args:
        evidence: the physical HVRT evidence gathered from the solved case.
        envelope: the ride-through envelope (supplies ``hvrt_enter_pu`` + ``ov_trip_pu``).
        settle_margin_pu: extra pu the settled voltage must clear BELOW the entry threshold
            by (default 0.0 — a settle to the entry pu counts as recovered).
    """
    vmax = evidence.max_voltage_pu
    vset = evidence.settled_voltage_pu
    enter = envelope.hvrt_enter_pu
    # NOT-RUN: no swell above the entry pu means the over-voltage path was never exercised.
    if vmax is None or vmax <= enter:
        return None
    if vset is None:
        return None
    if evidence.ibr_tripped:
        return False
    # The peak reached the over-voltage instantaneous-trip edge: a hard disconnect breach.
    if vmax >= envelope.ov_trip_pu:
        return False
    # The bus must settle back at/below the continuous HVRT entry pu (a lingering swell is
    # a breach). A margin can DEMAND it settle strictly below the entry pu.
    return bool(vset <= enter - settle_margin_pu)


def _hvrt_dynamic_verdict(
    *,
    swell_applied: bool,
    solved: bool,
    converged: bool,
    evidence: HvrtEvidence | None,
    envelope: RideThroughEnvelope,
) -> bool | None:
    """Map a solved HVRT dynamics run to a ``rode_through`` verdict (PURE, grid-free).

    Mirrors :func:`_lvrt_dynamic_verdict` for the swell direction. In order:

      * ``None`` (NOT-RUN) when no candidate case could be set up (``solved is False`` /
        ``evidence is None``) — a genuine setup failure, nothing physically attempted.
      * ``None`` (NOT-RUN) when no swell disturbance was applied (``swell_applied`` False).
      * ``False`` (BREACH) when the swell WAS applied but the TDS did not exit cleanly
        (``converged is False``): a runaway over-voltage that diverges IS the collapse — the
        plant did not ride through. A real breach, not NOT-RUN.
      * otherwise the verdict comes from the PHYSICAL ENVELOPE via :func:`hvrt_rode_through`
        (peak swell + settle + trip-curve + IBR-trip), which may return True / False / None.
    """
    if not solved or evidence is None:
        return None
    if not swell_applied:
        return None
    if not converged:
        return False
    return hvrt_rode_through(evidence, envelope)


# ─────────────────────────────────────────────────────────────────────────────
# D4b (#892) — frequency-excursion physical evidence + verdict (PURE).
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FreqEvidence:
    """The PHYSICAL evidence a solved frequency-excursion case yields (pure data).

    Fields
        nadir_hz / zenith_hz: the frequency MINIMUM (nadir, under-frequency events) and
            MAXIMUM (zenith, over-frequency events) over the run. The binding extreme is
            whichever moved further from nominal — that is the quantity screened against the
            band + trip curve. A run whose frequency never left the continuous band did not
            exercise the ride-through path (nothing to certify → NOT-RUN).
        settled_hz: the post-event SETTLED frequency (steady-state after the disturbance).
        ibr_tripped: whether any IBR / generator device tripped offline during the run
            (True/False, or None when trip status could not be read). NOTE: for a
            generator-TRIP disturbance the tripped machine is the *disturbance itself*, not
            a compliance failure — the caller passes IBR-only trip evidence here.
    """

    nadir_hz: float | None
    zenith_hz: float | None
    settled_hz: float | None
    ibr_tripped: bool | None


def freq_extreme_hz(evidence: FreqEvidence, *, nominal_hz: float) -> float | None:
    """The binding frequency extreme (Hz) — the nadir/zenith furthest from nominal (PURE).

    Returns whichever of ``nadir_hz`` / ``zenith_hz`` deviates MORE from ``nominal_hz`` (the
    excursion the ride-through envelope must contain). ``None`` when neither is measured.
    """
    nadir = evidence.nadir_hz
    zenith = evidence.zenith_hz
    candidates = [f for f in (nadir, zenith) if f is not None]
    if not candidates:
        return None
    return max(candidates, key=lambda f: abs(f - nominal_hz))


def frequency_rode_through(
    evidence: FreqEvidence,
    envelope: RideThroughEnvelope,
    *,
    nominal_hz: float = _NOMINAL_FREQ_HZ,
) -> bool | None:
    """Envelope-derived frequency ride-through verdict (PURE — no ANDES, grid-free).

    Derived from the measured frequency EXTREME (nadir/zenith), NEVER from a solver flag:

      * ``None`` (NOT-RUN) when no measurable excursion left the continuous band (the
        binding extreme is None or stayed inside ``freq_continuous_hz``, so the frequency
        ride-through path was never exercised) or the settled frequency is unknown.
      * ``False`` (breach) when the IBR tripped, OR the measured extreme reached the
        INSTANTANEOUS trip band (``freq_trip_hz``: a hard under/over-frequency disconnect),
        OR the frequency did NOT settle back inside the continuous band.
      * ``True`` (rode through) only when a real excursion past the continuous band was
        measured, no IBR tripped, the extreme stayed inside the instantaneous-trip band, and
        the frequency settled back inside the continuous window.

    Args:
        evidence: the physical frequency evidence gathered from the solved case.
        envelope: the envelope (supplies ``freq_continuous_hz`` + ``freq_trip_hz``).
        nominal_hz: nominal system frequency (Hz) — the reference the extreme is measured
            against.
    """
    extreme = freq_extreme_hz(evidence, nominal_hz=nominal_hz)
    settled = evidence.settled_hz
    cont_lo, cont_hi = envelope.freq_continuous_hz
    trip_lo, trip_hi = envelope.freq_trip_hz
    # NOT-RUN: the frequency never left the continuous band → the path was not exercised.
    if extreme is None or cont_lo <= extreme <= cont_hi:
        return None
    if settled is None:
        return None
    if evidence.ibr_tripped:
        return False
    # The extreme reached the instantaneous under/over-frequency trip edge → a hard breach.
    if extreme <= trip_lo or extreme >= trip_hi:
        return False
    # The frequency must settle back inside the continuous ride-through band.
    return bool(cont_lo <= settled <= cont_hi)


def _frequency_dynamic_verdict(
    *,
    excursion_applied: bool,
    solved: bool,
    converged: bool,
    evidence: FreqEvidence | None,
    envelope: RideThroughEnvelope,
    nominal_hz: float = _NOMINAL_FREQ_HZ,
) -> bool | None:
    """Map a solved frequency dynamics run to a ``rode_through`` verdict (PURE, grid-free).

    Mirrors :func:`_lvrt_dynamic_verdict` for the frequency direction. In order:

      * ``None`` (NOT-RUN) when no candidate case could be set up (``solved is False`` /
        ``evidence is None``) — a genuine setup failure.
      * ``None`` (NOT-RUN) when no frequency excursion was applied (``excursion_applied``
        False) — no disturbance injected.
      * ``False`` (BREACH) when the excursion WAS applied but the TDS did not exit cleanly
        (``converged is False``): a runaway frequency that diverges IS the collapse.
      * otherwise the verdict comes from the PHYSICAL ENVELOPE via
        :func:`frequency_rode_through` (extreme + settle + trip-curve + IBR-trip).
    """
    if not solved or evidence is None:
        return None
    if not excursion_applied:
        return None
    if not converged:
        return False
    return frequency_rode_through(evidence, envelope, nominal_hz=nominal_hz)


def _n_ibr_devices(ss: Any) -> int:  # pragma: no cover - requires [grid] extra
    """Count the WECC IBR / synchronous devices present on the loaded ANDES system."""
    return int(sum(getattr(ss, m).n for m in _IBR_MODELS if hasattr(ss, m)))


def _min_bus_voltage(
    ss: Any,
) -> float | None:  # pragma: no cover - requires [grid] extra
    """Deepest bus voltage over the simulation (the depth of the dip the IBRs rode)."""
    try:
        ts = ss.dae.ts
        # ANDES bus voltage-MAGNITUDE algebraic vars are named lowercase "v Bus N"
        # (the "a Bus N" vars are the angles); match "v Bus" so this returns a real
        # float, not always-None.
        vidx = [i for i, name in enumerate(ss.dae.y_name) if name.startswith("v Bus")]
        if vidx:
            return float(ts.y[:, vidx].min())
    except Exception:  # diagnostic only
        return None
    return None


def _max_bus_voltage(
    ss: Any,
) -> float | None:  # pragma: no cover - requires [grid] extra
    """Peak bus voltage over the simulation (the height of the swell the IBRs rode)."""
    try:
        ts = ss.dae.ts
        # See _min_bus_voltage: magnitude vars are lowercase "v Bus N".
        vidx = [i for i, name in enumerate(ss.dae.y_name) if name.startswith("v Bus")]
        if vidx:
            return float(ts.y[:, vidx].max())
    except Exception:  # diagnostic only
        return None
    return None


def _recovered_bus_voltage(
    ss: Any,
) -> float | None:  # pragma: no cover - requires [grid] extra
    """Post-fault RECOVERED bus voltage (min over buses at the LAST time step).

    Reads the final time-domain sample of every ``v Bus N`` magnitude var and returns the
    lowest — the steady-state the plant settled to once the fault cleared. This is the
    quantity the LVRT verdict checks against the entry threshold (a converged solve that
    settled to a collapsed voltage is NOT a ride-through).
    """
    try:
        ts = ss.dae.ts
        vidx = [i for i, name in enumerate(ss.dae.y_name) if name.startswith("v Bus")]
        if vidx:
            return float(ts.y[-1, vidx].min())
    except Exception:  # diagnostic only
        return None
    return None


def _settled_max_bus_voltage(
    ss: Any,
) -> float | None:  # pragma: no cover - requires [grid] extra
    """Post-event SETTLED bus voltage (max over buses at the LAST time step).

    The HVRT counterpart of :func:`_recovered_bus_voltage`: reads the FINAL time-domain
    sample of every ``v Bus N`` magnitude var and returns the HIGHEST — the steady-state
    the plant settled to after the swell. This is the quantity the HVRT verdict checks
    against the entry threshold (a bus that settles ABOVE the HVRT entry pu is a breach).
    """
    try:
        ts = ss.dae.ts
        vidx = [i for i, name in enumerate(ss.dae.y_name) if name.startswith("v Bus")]
        if vidx:
            return float(ts.y[-1, vidx].max())
    except Exception:  # diagnostic only
        return None
    return None


def _freq_extremes_hz(
    ss: Any, *, nominal_hz: float
) -> tuple[
    float | None, float | None, float | None
]:  # pragma: no cover - requires [grid]
    """``(nadir_hz, zenith_hz, settled_hz)`` of the system frequency over the run.

    Reads the machine-speed ``omega`` states (pu on nominal) — their min/max over the run
    are the frequency nadir/zenith, and the final-step value is the settled frequency. All
    converted to Hz via ``omega · nominal_hz``. Returns ``(None, None, None)`` when no
    frequency var could be read (so the verdict treats the excursion as unmeasured, not a
    pass). Uses ``omega`` (the synchronous-machine speed) as the system-frequency proxy —
    the physically meaningful RMS frequency for this positive-sequence screen.
    """
    try:
        ts = ss.dae.ts
        # omega machine-speed states carry the RMS system frequency (pu on nominal).
        omega_idx = [
            i
            for i, name in enumerate(ss.dae.x_name)
            if name.lower().startswith("omega ")
        ]
        if not omega_idx:
            return None, None, None
        series = ts.x[:, omega_idx]
        nadir = float(series.min()) * nominal_hz
        zenith = float(series.max()) * nominal_hz
        settled = float(ts.x[-1, omega_idx].mean()) * nominal_hz
        return nadir, zenith, settled
    except Exception:  # diagnostic only
        return None, None, None


#: IBR-only device models (the WECC renewable set) — excludes the synchronous ``GENROU``
#: so a frequency case that TRIPS a synchronous machine as its disturbance does not read
#: that intended trip as an IBR compliance failure.
_IBR_ONLY_MODELS = (
    "REGCA1",
    "REGCP1",
    "REECA1",
    "REPCA1",
    "WTARA1",
    "WTDTA1",
    "PVD1",
)


def _online_flag_tripped(
    ss: Any, models: tuple[str, ...]
) -> tuple[bool, bool]:  # pragma: no cover - requires [grid] extra
    """``(saw_flag, tripped)`` from the models' online flag ``u`` (the primary evidence).

    A device that ends the run with ``u == 0`` tripped. ``saw_flag`` is True iff at least
    one present model exposed a readable online flag — the caller uses it to distinguish a
    real "no trip" from an UNREADABLE trip status (→ None, never a pass).
    """
    saw_flag = False
    tripped = False
    for model_name in models:
        model = getattr(ss, model_name, None)
        if model is None or getattr(model, "n", 0) == 0:
            continue
        u = getattr(model, "u", None)
        values = getattr(u, "v", None)
        if values is None:
            continue
        saw_flag = True
        try:
            if any(float(v) == 0.0 for v in values):
                tripped = True
        except (TypeError, ValueError):
            continue
    return saw_flag, tripped


def _current_injection_collapsed(
    ss: Any, models: tuple[str, ...]
) -> bool:  # pragma: no cover - requires [grid] extra
    """Corroborating trip evidence: an IBR whose current injection went to (near) zero.

    Hardening (#892): a protection trip may LATCH the converter's current output to zero
    WITHOUT clearing the model online flag ``u`` (``u`` reflects the topology switch, not the
    inner protection state). We cross-check the final-step current-injection algebraic vars
    (``Ipout`` / ``Iqout`` for REGCA1/REGCP1, or a generic ``I``) — if a present IBR ends the
    run injecting ~0 current, that is a tripped / blocked converter the online flag missed.
    Returns True iff any present IBR's final current magnitude collapsed to ~0.
    """
    _CUR_TOKENS = ("Ipout", "Iqout", "Ipcmd", "Iqcmd")
    try:
        ts = ss.dae.ts
        y_name = ss.dae.y_name
    except Exception:  # diagnostic only
        return False
    # Only look when at least one target IBR model is actually present on the case.
    if not any(getattr(getattr(ss, m, None), "n", 0) for m in models):
        return False
    cur_idx = [
        i for i, name in enumerate(y_name) if any(tok in name for tok in _CUR_TOKENS)
    ]
    if not cur_idx:
        return False
    try:
        # A pre-disturbance sample (early in the run) vs the final sample: a converter that
        # WAS injecting current and ends at ~0 has been blocked/tripped. We require it was
        # non-trivial earlier so a genuinely idle var is not misread as a trip.
        final = ts.y[-1, cur_idx]
        early = ts.y[0, cur_idx]
        for f, e in zip(final, early, strict=True):
            if abs(float(e)) > 1e-3 and abs(float(f)) < 1e-4:
                return True
    except Exception:  # diagnostic only
        return False
    return False


def _any_ibr_tripped(
    ss: Any, *, ibr_only: bool = False
) -> bool | None:  # pragma: no cover - requires [grid] extra
    """Whether any IBR / generator device tripped offline during the run (HARDENED #892).

    Trip detection now draws on TWO independent lines of physical evidence, so a protection
    trip that does not clear the topology online flag is not silently missed:

      1. the model ONLINE flag ``u`` (a device ending at ``u == 0`` tripped), and
      2. a CURRENT-INJECTION collapse (an IBR whose converter current went to ~0 by the
         final step despite being non-zero earlier — a blocked / tripped converter).

    A trip on EITHER line reports ``True``. Returns ``None`` (UNKNOWN — never a pass) when
    NEITHER line yielded readable evidence: no online flag was legible AND no
    current-injection var existed to corroborate. The verdict then treats trip-status as
    UNREADABLE and refuses to certify a pass off unknown protection state.

    Args:
        ibr_only: restrict the online-flag scan to the WECC IBR set (excluding the
            synchronous ``GENROU``). Used by the frequency case, whose disturbance TRIPS a
            synchronous machine — that intended trip must NOT be read as an IBR compliance
            failure.
    """
    models = _IBR_ONLY_MODELS if ibr_only else _IBR_MODELS
    saw_flag, tripped = _online_flag_tripped(ss, models)
    if tripped:
        return True
    current_collapsed = _current_injection_collapsed(ss, models)
    if current_collapsed:
        return True
    if not saw_flag:
        # No legible online flag AND no current-injection collapse detected → the trip
        # status is UNREADABLE. Return None so the verdict does not certify off unknown
        # protection state (NO SPURIOUS PASS) — NOT False (which would be a fabricated
        # "did-not-trip").
        return None
    return False


def _apply_load_rejection(
    ss: Any, spec: RideThroughCaseSpec
) -> bool:  # pragma: no cover - requires [grid] extra
    """Toggle EVERY ``PQ`` load OFF at ``fault_start_s`` (the HVRT swell mechanism).

    A LOAD REJECTION removes real+reactive demand from the network mid-run; the freed power
    SWELLS the bus voltages — a real over-voltage the shunt ``Fault`` model can never
    produce. Rejecting a SINGLE load on a stiff test network (ieee14) only lifts the bus a
    few percent (empirically ~1.07 pu — below the 1.10 HVRT entry, so nothing is exercised);
    a FULL load rejection is the classic HVRT stimulus and reliably drives the peak past the
    entry pu (empirically ~1.26 pu on ieee14). We ``Toggle`` every ``PQ`` device offline at
    the disturbance start. Returns True iff at least one load was scheduled for rejection.
    """
    pq: Any = getattr(ss, "PQ", None)
    n = getattr(pq, "n", 0) if pq is not None else 0
    if not n:
        return False
    for idx in list(pq.idx.v):
        ss.add(
            "Toggle",
            dict(model="PQ", dev=idx, t=spec.fault_start_s),
        )
    return True


def _apply_generator_trip(
    ss: Any, spec: RideThroughCaseSpec
) -> bool:  # pragma: no cover - requires [grid] extra
    """Toggle a synchronous machine OFF at ``fault_start_s`` (the frequency mechanism).

    Tripping a generator removes an active-power source, so the remaining machines
    decelerate and system frequency dips → a real UNDER-frequency excursion. We ``Toggle``
    a non-slack ``GENROU`` machine offline (tripping the slack would make the solve
    singular). Returns True iff a generator was scheduled for trip.
    """
    gen: Any = getattr(ss, "GENROU", None)
    n = getattr(gen, "n", 0) if gen is not None else 0
    if not n:
        return False
    # Trip the LAST machine (least likely to be the slack, which ANDES orders first).
    target_idx = gen.idx.v[-1]
    ss.add(
        "Toggle",
        dict(model="GENROU", dev=target_idx, t=spec.fault_start_s),
    )
    return True


def _apply_load_step(
    ss: Any, spec: RideThroughCaseSpec
) -> bool:  # pragma: no cover - requires [grid] extra
    """Toggle the largest ``PQ`` load OFF as an over-frequency step (frequency mechanism).

    A sudden load LOSS leaves surplus generation, so the machines accelerate → an
    OVER-frequency excursion (the mirror of a generator trip). Reuses the load-rejection
    actuator. Returns True iff a load was scheduled.
    """
    return _apply_load_rejection(ss, spec)


def _solve_case(  # pragma: no cover - requires [grid] extra
    andes: Any,
    spec: RideThroughCaseSpec,
    *,
    nominal_hz: float = _NOMINAL_FREQ_HZ,
    tf: float = 2.0,
) -> tuple[
    bool,
    bool,
    int,
    float | None,
    float | None,
    LvrtEvidence | None,
    HvrtEvidence | None,
    FreqEvidence | None,
    str,
]:
    """Load a bundled ANDES IBR case, apply the case's disturbance, run PFlow + TDS.

    Returns ``(solved, converged, n_devices, vmin_pu, vmax_pu, lvrt_ev, hvrt_ev, freq_ev,
    detail)``. Exactly ONE of the three evidence bundles is populated per case (the others
    ``None``): LVRT → ``lvrt_ev``, HVRT → ``hvrt_ev``, frequency → ``freq_ev``. The disturbance
    is dispatched off ``spec.disturbance``:

      * ``impedance_fault`` (LVRT): a bus shunt ``Fault`` DIPS voltage.
      * ``load_rejection`` (HVRT): the largest ``PQ`` load is ``Toggle``d off → a voltage SWELL.
      * ``generator_trip`` (frequency): a ``GENROU`` machine is ``Toggle``d off → under-frequency.
      * ``load_step`` (frequency): a load is ``Toggle``d off → over-frequency.

    ``solved`` is True once a candidate case loaded, the disturbance was applied AND
    ``TDS.run()`` was invoked — REGARDLESS of exit code. It is False ONLY on a genuine
    case-SETUP failure (every candidate raised before the solve) OR when the case carried no
    device to actuate (no ``PQ`` for a rejection, no ``GENROU`` for a trip) — then the
    disturbance could not be applied, so the case is NOT-RUN, never a fabricated pass.
    ``converged`` is ONLY the raw RMS-solve smoke test (``exit_code == 0``).

    Tries each candidate case in order, keeping the last failure for the report.
    """
    last_err = "no candidate case attempted"
    for rel in _CANDIDATE_CASES:
        try:
            case = andes.get_case(rel)
            ss = andes.load(case, setup=False, no_output=True, default_config=True)

            disturbance_applied = _apply_disturbance(ss, spec)
            if not disturbance_applied:
                # The candidate case had no device to actuate (no PQ / no GENROU). Try the
                # next candidate; if none can be actuated the loop ends in a NOT-RUN.
                last_err = f"{rel}: no device to apply {spec.disturbance!r}"
                continue

            ss.setup()
            ss.PFlow.run()
            ss.TDS.config.tf = tf
            ss.TDS.run()
            converged = int(getattr(ss, "exit_code", 1)) == 0
            n_devices = _n_ibr_devices(ss)
            vmin = _min_bus_voltage(ss)
            vmax = _max_bus_voltage(ss)

            lvrt_ev, hvrt_ev, freq_ev = _gather_case_evidence(
                ss, spec, vmin=vmin, vmax=vmax, nominal_hz=nominal_hz
            )
            detail = _solve_detail(rel, ss, spec, converged, n_devices)
            return (
                True,
                converged,
                n_devices,
                vmin,
                vmax,
                lvrt_ev,
                hvrt_ev,
                freq_ev,
                detail,
            )
        except Exception as exc:  # try next candidate; keep the last failure
            last_err = f"{rel}: {exc!r}"
    return (
        False,
        False,
        0,
        None,
        None,
        None,
        None,
        None,
        f"ANDES case setup failed — no candidate solved ({last_err}). {spec.detail}",
    )


def _apply_disturbance(
    ss: Any, spec: RideThroughCaseSpec
) -> bool:  # pragma: no cover - requires [grid] extra
    """Apply the case's disturbance to the loaded (un-setup) system; True iff it landed."""
    if spec.disturbance == "impedance_fault":
        if spec.fault_x_pu is None:
            return False
        ss.add(
            "Fault",
            dict(
                bus=spec.fault_bus,
                tf=spec.fault_start_s,
                tc=spec.fault_clear_s,
                xf=spec.fault_x_pu,
            ),
        )
        return True
    if spec.disturbance == "load_rejection":
        return _apply_load_rejection(ss, spec)
    if spec.disturbance == "generator_trip":
        return _apply_generator_trip(ss, spec)
    if spec.disturbance == "load_step":
        return _apply_load_step(ss, spec)
    return False


def _gather_case_evidence(  # pragma: no cover - requires [grid] extra
    ss: Any,
    spec: RideThroughCaseSpec,
    *,
    vmin: float | None,
    vmax: float | None,
    nominal_hz: float,
) -> tuple[LvrtEvidence | None, HvrtEvidence | None, FreqEvidence | None]:
    """Build the case-appropriate physical evidence bundle from the solved system."""
    if spec.kind == "lvrt":
        return (
            LvrtEvidence(
                min_voltage_pu=vmin,
                recovered_voltage_pu=_recovered_bus_voltage(ss),
                ibr_tripped=_any_ibr_tripped(ss),
            ),
            None,
            None,
        )
    if spec.kind == "hvrt":
        return (
            None,
            HvrtEvidence(
                max_voltage_pu=vmax,
                settled_voltage_pu=_settled_max_bus_voltage(ss),
                ibr_tripped=_any_ibr_tripped(ss),
            ),
            None,
        )
    # frequency: the disturbance itself may TRIP a synchronous machine, so read IBR-ONLY
    # trip evidence — the intended generator trip is the DISTURBANCE, not a compliance fail.
    nadir, zenith, settled = _freq_extremes_hz(ss, nominal_hz=nominal_hz)
    return (
        None,
        None,
        FreqEvidence(
            nadir_hz=nadir,
            zenith_hz=zenith,
            settled_hz=settled,
            ibr_tripped=_any_ibr_tripped(ss, ibr_only=True),
        ),
    )


def _solve_detail(  # pragma: no cover - requires [grid] extra
    rel: str,
    ss: Any,
    spec: RideThroughCaseSpec,
    converged: bool,
    n_devices: int,
) -> str:
    """Human-readable per-solve provenance line for the result detail."""
    exit_code = int(getattr(ss, "exit_code", 1))
    collapse = (
        "" if converged else f"; unstable/early-terminated → {spec.kind} collapse"
    )
    return (
        f"case={rel}; disturbance={spec.disturbance}; TDS exit={exit_code} "
        f"(raw solve smoke-test, NOT compliance{collapse}); IBR/gen devices={n_devices}. "
        f"{spec.detail}"
    )


def run_ride_through_case(
    kind: str,
    *,
    run_dynamics: bool = False,
    fixture_path: Path | str | None = None,
    envelope: RideThroughEnvelope | None = None,
    fault_bus: int = 4,
    fault_start_s: float = 1.0,
    fault_clear_s: float = 1.1,
    lvrt_fault_x_pu: float = 0.05,
    freq_excursion_hz: float | None = None,
    freq_mechanism: str = "generator_trip",
    nominal_hz: float = _NOMINAL_FREQ_HZ,
    tf: float = 2.0,
) -> RideThroughResult:
    """Run ONE ride-through case and report whether the RMS solve rode it through.

    The envelope is parsed from the D0 fixture (or taken from ``envelope`` when supplied),
    the case spec is resolved, and — ONLY when ``run_dynamics`` is True — the ANDES RMS
    time-domain solve is run behind :func:`_require_andes`. With ``run_dynamics=False``
    (the default, dynamic-study gate OFF) no ANDES import or solve happens and the result
    is a NOT-RUN advisory carrying the resolved envelope + case detail.

    All three cases are now physically modeled (D4b, #892): LVRT injects a shunt impedance
    fault (dip), HVRT injects a LOAD REJECTION (swell), and frequency injects a generator
    trip / load step (a frequency excursion). Each verdict comes from the PHYSICAL ENVELOPE
    — the measured dip/swell/frequency-extreme vs the entry threshold + trip curve + IBR
    trip — NEVER from the raw ``converged`` flag.

    Args:
        kind: one of :data:`RIDE_THROUGH_CASES`.
        run_dynamics: the dynamic-study gate. False (default) → static, no ANDES.
        fixture_path: override the D0 grid-code fixture (tests inject a path).
        envelope: pre-parsed envelope (skips fixture read when supplied).
        fault_bus / fault_start_s / fault_clear_s / lvrt_fault_x_pu / freq_excursion_hz /
            freq_mechanism: disturbance parameters forwarded to :func:`build_case_spec`.
        nominal_hz: nominal system frequency (Hz) — the reference the frequency extreme is
            measured against.
        tf: TDS stop time (s) for the dynamics solve.

    Returns:
        :class:`analytics.contracts_v14.RideThroughResult` — advisory (``bankable=False``).
        ``ran`` reflects whether the ANDES solve actually EXECUTED (True even for an
        early-terminated / diverged solve; False on a genuine case-setup failure OR when the
        case carried no device to actuate the disturbance); ``converged`` is the raw RMS
        smoke test (``exit_code == 0``); ``rode_through`` is the COMPLIANCE VERDICT graded on
        the physical envelope for the case's disturbance. An unstable / early-terminated
        solve under an APPLIED disturbance is a COLLAPSE → ``rode_through=False`` (NOT
        ``None``). ``rode_through=None`` (NOT-RUN) is reserved for the gate-off path, a
        disturbance that did not move the measured quantity past its entry threshold
        (nothing exercised), a case-setup failure, and an unreadable trip status — never a
        spurious pass.
    """
    env = envelope if envelope is not None else envelope_from_fixture(fixture_path)
    spec = build_case_spec(
        kind,
        env,
        fault_bus=fault_bus,
        fault_start_s=fault_start_s,
        fault_clear_s=fault_clear_s,
        lvrt_fault_x_pu=lvrt_fault_x_pu,
        freq_excursion_hz=freq_excursion_hz,
        freq_mechanism=freq_mechanism,
    )

    if not run_dynamics:
        return RideThroughResult.from_case(
            case=spec.kind,
            ran=False,
            converged=False,
            rode_through=None,  # gate off — nothing physically validated
            target_pu=spec.target_pu,
            target_hz=spec.target_hz,
            k_factor=spec.k_factor,
            min_voltage_pu=None,
            max_voltage_pu=None,
            n_devices=0,
            detail=(
                "Dynamic-study gate OFF (run_dynamics=False): envelope parsed + case set "
                f"up, ANDES not run — rode_through=None (NOT-RUN). {spec.detail}"
            ),
        )

    andes = _require_andes()  # pragma: no cover - requires [grid] extra
    (  # pragma: no cover - requires [grid] extra
        solved,
        converged,
        n_devices,
        vmin,
        vmax,
        lvrt_ev,
        hvrt_ev,
        freq_ev,
        detail,
    ) = _solve_case(andes, spec, nominal_hz=nominal_hz, tf=tf)
    # ``ran`` reflects whether the solver ACTUALLY EXECUTED. ``rode_through`` is derived by
    # the pure per-case reducer, NEVER from the raw ``converged`` flag: a converged solve is
    # graded on the physical envelope; an unstable/early-terminated solve under an APPLIED
    # disturbance is a COLLAPSE → False.
    rode_through = _dynamic_verdict(  # pragma: no cover - requires [grid] extra
        spec=spec,
        solved=solved,
        converged=converged,
        lvrt_ev=lvrt_ev,
        hvrt_ev=hvrt_ev,
        freq_ev=freq_ev,
        envelope=env,
        nominal_hz=nominal_hz,
    )
    # Surface the measured frequency EXTREME (nadir/zenith) for the frequency case so the
    # D5c combined-frequency study can read a REAL dynamic nadir (instead of NOT-RUN). It
    # is None for the voltage cases and when no frequency var was measured.
    freq_extreme = (  # pragma: no cover - requires [grid] extra
        freq_extreme_hz(freq_ev, nominal_hz=nominal_hz) if freq_ev is not None else None
    )
    return RideThroughResult.from_case(  # pragma: no cover - requires [grid] extra
        case=spec.kind,
        ran=solved,
        converged=converged,
        rode_through=rode_through,
        target_pu=spec.target_pu,
        target_hz=spec.target_hz,
        k_factor=spec.k_factor,
        min_voltage_pu=vmin,
        max_voltage_pu=vmax,
        freq_extreme_hz=freq_extreme,
        n_devices=n_devices,
        detail=detail,
    )


def _dynamic_verdict(  # pragma: no cover - requires [grid] extra
    *,
    spec: RideThroughCaseSpec,
    solved: bool,
    converged: bool,
    lvrt_ev: LvrtEvidence | None,
    hvrt_ev: HvrtEvidence | None,
    freq_ev: FreqEvidence | None,
    envelope: RideThroughEnvelope,
    nominal_hz: float,
) -> bool | None:
    """Dispatch to the case-appropriate PURE verdict reducer (thin ANDES-side router).

    The heavy logic is in the pure reducers (grid-free tested); this only routes by case.
    """
    if spec.kind == "lvrt":
        return _lvrt_dynamic_verdict(
            fault_applied=spec.fault_x_pu is not None,
            solved=solved,
            converged=converged,
            evidence=lvrt_ev,
            envelope=envelope,
        )
    if spec.kind == "hvrt":
        return _hvrt_dynamic_verdict(
            swell_applied=spec.disturbance == "load_rejection",
            solved=solved,
            converged=converged,
            evidence=hvrt_ev,
            envelope=envelope,
        )
    return _frequency_dynamic_verdict(
        excursion_applied=spec.disturbance in ("generator_trip", "load_step"),
        solved=solved,
        converged=converged,
        evidence=freq_ev,
        envelope=envelope,
        nominal_hz=nominal_hz,
    )


def run_ride_through_suite(
    *,
    run_dynamics: bool = False,
    fixture_path: Path | str | None = None,
    **case_kwargs: Any,
) -> dict[str, RideThroughResult]:
    """Run all three ride-through cases (LVRT + HVRT + frequency) from ONE envelope.

    Parses the envelope once, then runs each case in :data:`RIDE_THROUGH_CASES`, returning
    a ``kind → RideThroughResult`` mapping. With ``run_dynamics=False`` (default) this is
    pure Python (no ANDES). Extra keyword arguments are forwarded to
    :func:`run_ride_through_case`.
    """
    env = envelope_from_fixture(fixture_path)
    return {
        kind: run_ride_through_case(
            kind, run_dynamics=run_dynamics, envelope=env, **case_kwargs
        )
        for kind in RIDE_THROUGH_CASES
    }


__all__ = [
    "RIDE_THROUGH_CASES",
    "DISTURBANCES",
    "RideThroughEnvelope",
    "RideThroughCaseSpec",
    "LvrtEvidence",
    "HvrtEvidence",
    "FreqEvidence",
    "lvrt_rode_through",
    "hvrt_rode_through",
    "frequency_rode_through",
    "freq_extreme_hz",
    "_lvrt_dynamic_verdict",
    "_hvrt_dynamic_verdict",
    "_frequency_dynamic_verdict",
    "envelope_from_fixture",
    "build_case_spec",
    "run_ride_through_case",
    "run_ride_through_suite",
]
