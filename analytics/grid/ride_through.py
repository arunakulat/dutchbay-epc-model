"""Shared ANDES RMS ride-through dynamics core (D4a, #875).

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
CONVERGED LVRT solve derives its compliance verdict (``rode_through``) ONLY from the
PHYSICAL ENVELOPE — the post-fault RECOVERED bus voltage vs the entry threshold and whether
the IBR tripped.

A non-clean exit under an *applied* LVRT fault, though, is itself physical evidence of a
FAILURE, not an absence of evidence: when the ANDES TDS diverges / terminates early on a
stability-criteria violation while the fault is active, the plant did NOT ride through — the
solve blew up because the bus collapsed. That case is a real breach → ``rode_through=False``
(NOT ``None``). ``rode_through=None`` (NOT-RUN / UNSUPPORTED) is reserved for the cases that
never physically exercised an envelope at all: the unmodeled HVRT / frequency disturbances,
the gate-off static path, and a genuine case-SETUP failure where no candidate network could
be built to even attempt the solve.

**LVRT** is the only case this core physically models today: a shunt impedance fault
produces a real, measurable voltage DIP whose recovery can be checked against the entry
pu, and IBR trips can be detected from the device online flags. **HVRT** and **frequency**
are NOT-RUN: a shunt ``Fault`` can only DIP voltage (never SWELL), and no frequency
excursion (generator trip / load step) is applied yet — so both return an explicit
``rode_through=None`` with a follow-up detail rather than a trivial/spurious pass. Full
HVRT (source-voltage step / load rejection) and frequency (generator Toggle / load step)
dynamics are a follow-up dolphin.

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
# ride-through window; freq band the conventional 47.5–51.5 Hz continuous window.
_DEFAULT_LVRT_ENTER_PU = 0.9
_DEFAULT_HVRT_ENTER_PU = 1.1
_DEFAULT_LVRT_K = 2.0
_DEFAULT_HVRT_K = 0.0
_DEFAULT_FREQ_HZ = (47.5, 51.5)
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
        source: a human string identifying where the envelope came from (fixture path or
            "defaults") for the result provenance/detail.
    """

    lvrt_enter_pu: float
    hvrt_enter_pu: float
    lvrt_k_factor: float
    hvrt_k_factor: float
    freq_continuous_hz: tuple[float, float]
    source: str


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
    if not isinstance(rows, (list, tuple)) or not rows:
        return None
    best_setpoint: float | None = None
    best_time = -1.0
    for row in rows:
        if (
            isinstance(row, (list, tuple))
            and len(row) == 2
            and all(
                isinstance(v, (int, float)) and not isinstance(v, bool) for v in row
            )
        ):
            setpoint, clearing = float(row[0]), float(row[1])
            if clearing > best_time:
                best_time = clearing
                best_setpoint = setpoint
    return best_setpoint


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
    return RideThroughEnvelope(
        lvrt_enter_pu=lvrt_enter,
        hvrt_enter_pu=hvrt_enter,
        lvrt_k_factor=lvrt_k,
        hvrt_k_factor=hvrt_k,
        freq_continuous_hz=freq_band,
        source=source,
    )


def _as_float(value: Any, default: float) -> float:
    """Coerce a fixture scalar to float, falling back to ``default`` when unusable."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


@dataclass(frozen=True)
class RideThroughCaseSpec:
    """The resolved disturbance parameters for ONE ride-through case (pure data).

    ``kind`` is one of :data:`RIDE_THROUGH_CASES`. For voltage cases the disturbance is a
    bus impedance fault (``fault_x_pu``); ``target_pu`` is the ride-through threshold the
    case probes (the entry pu). For the frequency case ``target_hz`` is the excursion the
    plant must ride through and ``fault_x_pu`` is unused (``None``).
    """

    kind: str
    fault_bus: int
    fault_start_s: float
    fault_clear_s: float
    fault_x_pu: float | None
    target_pu: float | None
    target_hz: float | None
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
    hvrt_fault_x_pu: float = 5.0,
    freq_excursion_hz: float | None = None,
) -> RideThroughCaseSpec:
    """Resolve one :class:`RideThroughCaseSpec` from the parsed envelope (pure Python).

    Args:
        kind: one of :data:`RIDE_THROUGH_CASES` (``"lvrt"`` | ``"hvrt"`` | ``"frequency"``).
        envelope: the ride-through envelope parsed from the D0 fixture.
        fault_bus / fault_start_s / fault_clear_s: the disturbance timing/location.
        lvrt_fault_x_pu: impedance (pu) for the LVRT dip — a partial dip that triggers the
            ride-through path yet keeps the positive-sequence RMS solve convergent (a
            bolted fault makes the solve singular).
        hvrt_fault_x_pu: a large shunt impedance (pu) for the HVRT swell case.
        freq_excursion_hz: the frequency (Hz) the frequency case probes; ``None`` defaults
            to the fixture's continuous overfrequency edge (the binding excursion).

    Raises:
        ValueError: for an unknown ``kind`` (CESSPIT — no silent default case).
    """
    if kind not in RIDE_THROUGH_CASES:
        raise ValueError(
            f"unknown ride-through case {kind!r}; expected one of {RIDE_THROUGH_CASES}."
        )
    if kind == "lvrt":
        return RideThroughCaseSpec(
            kind="lvrt",
            fault_bus=fault_bus,
            fault_start_s=fault_start_s,
            fault_clear_s=fault_clear_s,
            fault_x_pu=lvrt_fault_x_pu,
            target_pu=envelope.lvrt_enter_pu,
            target_hz=None,
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
            fault_bus=fault_bus,
            fault_start_s=fault_start_s,
            fault_clear_s=fault_clear_s,
            fault_x_pu=hvrt_fault_x_pu,
            target_pu=envelope.hvrt_enter_pu,
            target_hz=None,
            k_factor=envelope.hvrt_k_factor,
            detail=(
                f"HVRT swell probe at bus-{fault_bus} ({fault_start_s}-{fault_clear_s}s); "
                f"ride-through entry {envelope.hvrt_enter_pu} pu, k-factor "
                f"{envelope.hvrt_k_factor} (from {envelope.source})."
            ),
        )
    # frequency
    lo, hi = envelope.freq_continuous_hz
    excursion = freq_excursion_hz if freq_excursion_hz is not None else hi
    return RideThroughCaseSpec(
        kind="frequency",
        fault_bus=fault_bus,
        fault_start_s=fault_start_s,
        fault_clear_s=fault_clear_s,
        fault_x_pu=None,
        target_pu=None,
        target_hz=excursion,
        k_factor=0.0,
        detail=(
            f"Frequency ride-through probe to {excursion} Hz; continuous band "
            f"{lo}-{hi} Hz (from {envelope.source})."
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


def _any_ibr_tripped(
    ss: Any,
) -> bool | None:  # pragma: no cover - requires [grid] extra
    """Whether any IBR / generator device tripped offline during the run.

    Inspects each present model's online flag (``u``): a device that ends the run with
    ``u == 0`` (or whose connection-status var went to 0) tripped. Returns ``None`` when
    no online flag can be read (so the verdict treats trip-status as unknown, not a pass).
    """
    saw_flag = False
    tripped = False
    for model_name in _IBR_MODELS:
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
    if not saw_flag:
        return None
    return tripped


def _solve_case(  # pragma: no cover - requires [grid] extra
    andes: Any,
    spec: RideThroughCaseSpec,
    *,
    tf: float = 2.0,
) -> tuple[bool, bool, int, float | None, float | None, LvrtEvidence | None, str]:
    """Load a bundled ANDES IBR case, apply the disturbance, run PFlow + TDS.

    Returns ``(solved, converged, n_devices, vmin_pu, vmax_pu, evidence, detail)`` where:

      * ``solved`` is True once a candidate case loaded, the disturbance was applied and
        ``TDS.run()`` was actually invoked — REGARDLESS of exit code. It is False ONLY on a
        genuine case-SETUP failure where every candidate raised before the solve ran (no
        network could be built to even attempt it). An early-terminated / diverged solve
        still has ``solved=True``: the solver DID run, it just did not exit cleanly.
      * ``converged`` is ONLY the raw RMS-solve smoke test (``exit_code == 0``) — False on
        an early termination / stability-criteria violation / divergence.
      * ``evidence`` is the physical :class:`LvrtEvidence` (recovered voltage + IBR-trip
        status) — populated whenever the TDS ran (even if it terminated early), ``None``
        only on a setup failure.

    Tries each candidate case in order, keeping the last failure for the report. A bus
    impedance fault (LVRT dip) is the only physically-modeled disturbance; HVRT/frequency
    reach here with no evidence and are reported NOT-RUN by the caller.
    """
    last_err = "no candidate case attempted"
    for rel in _CANDIDATE_CASES:
        try:
            case = andes.get_case(rel)
            ss = andes.load(case, setup=False, no_output=True, default_config=True)
            if spec.fault_x_pu is not None:
                ss.add(
                    "Fault",
                    dict(
                        bus=spec.fault_bus,
                        tf=spec.fault_start_s,
                        tc=spec.fault_clear_s,
                        xf=spec.fault_x_pu,
                    ),
                )
            ss.setup()
            ss.PFlow.run()
            ss.TDS.config.tf = tf
            ss.TDS.run()
            converged = int(getattr(ss, "exit_code", 1)) == 0
            n_devices = _n_ibr_devices(ss)
            vmin = _min_bus_voltage(ss)
            vmax = _max_bus_voltage(ss)
            evidence = LvrtEvidence(
                min_voltage_pu=vmin,
                recovered_voltage_pu=_recovered_bus_voltage(ss),
                ibr_tripped=_any_ibr_tripped(ss),
            )
            detail = (
                f"case={rel}; TDS exit={int(getattr(ss, 'exit_code', 1))} "
                f"(raw solve smoke-test, NOT compliance"
                f"{'; unstable/early-terminated → LVRT collapse' if not converged else ''}"
                f"); IBR/gen devices={n_devices}; "
                f"recovered_v={evidence.recovered_voltage_pu}; "
                f"ibr_tripped={evidence.ibr_tripped}. {spec.detail}"
            )
            return True, converged, n_devices, vmin, vmax, evidence, detail
        except Exception as exc:  # try next candidate; keep the last failure
            last_err = f"{rel}: {exc!r}"
    return (
        False,
        False,
        0,
        None,
        None,
        None,
        f"ANDES case setup failed — no candidate solved ({last_err}). {spec.detail}",
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
    hvrt_fault_x_pu: float = 5.0,
    freq_excursion_hz: float | None = None,
    tf: float = 2.0,
) -> RideThroughResult:
    """Run ONE ride-through case and report whether the RMS solve rode it through.

    The envelope is parsed from the D0 fixture (or taken from ``envelope`` when supplied),
    the case spec is resolved, and — ONLY when ``run_dynamics`` is True — the ANDES RMS
    time-domain solve is run behind :func:`_require_andes`. With ``run_dynamics=False``
    (the default, dynamic-study gate OFF) no ANDES import or solve happens and the result
    is a NOT-RUN advisory carrying the resolved envelope + case detail.

    Args:
        kind: one of :data:`RIDE_THROUGH_CASES`.
        run_dynamics: the dynamic-study gate. False (default) → static, no ANDES.
        fixture_path: override the D0 grid-code fixture (tests inject a path).
        envelope: pre-parsed envelope (skips fixture read when supplied).
        fault_bus / fault_start_s / fault_clear_s / lvrt_fault_x_pu / hvrt_fault_x_pu /
            freq_excursion_hz: disturbance parameters forwarded to :func:`build_case_spec`.
        tf: TDS stop time (s) for the dynamics solve.

    Returns:
        :class:`analytics.contracts_v14.RideThroughResult` — advisory (``bankable=False``).
        ``ran`` reflects whether the ANDES solve actually EXECUTED (True even for an
        early-terminated / diverged solve; False only on a genuine case-setup failure);
        ``converged`` is the raw RMS smoke test (``exit_code == 0``); ``rode_through`` is
        the COMPLIANCE VERDICT. For LVRT: a cleanly converged solve is graded on the
        physical envelope (dip + recovery + trip → True / False), while an
        unstable / early-terminated solve under the APPLIED fault is a COLLAPSE →
        ``rode_through=False`` (NOT ``None``). ``rode_through=None`` (NOT-RUN / UNSUPPORTED)
        is reserved for the unmodeled HVRT / frequency cases (a shunt fault cannot swell
        voltage; no frequency excursion is modeled yet) and a genuine case-setup failure —
        never a spurious pass. A follow-up dolphin adds the over-voltage /
        frequency-excursion dynamics.
    """
    env = envelope if envelope is not None else envelope_from_fixture(fixture_path)
    spec = build_case_spec(
        kind,
        env,
        fault_bus=fault_bus,
        fault_start_s=fault_start_s,
        fault_clear_s=fault_clear_s,
        lvrt_fault_x_pu=lvrt_fault_x_pu,
        hvrt_fault_x_pu=hvrt_fault_x_pu,
        freq_excursion_hz=freq_excursion_hz,
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

    # HVRT and frequency are NOT physically modeled yet: a shunt Fault can only DIP the
    # voltage (never SWELL), and no frequency excursion (generator trip / load step) is
    # injected — so running the solver would validate nothing. Return an explicit
    # NOT-RUN / UNSUPPORTED verdict rather than a spurious pass. No ANDES import needed.
    if spec.kind != "lvrt":
        reason = (
            "HVRT NOT-RUN: a shunt Fault can only dip voltage, not swell it; a real "
            "over-voltage (source-voltage step / load rejection) is a follow-up dolphin"
            if spec.kind == "hvrt"
            else (
                "frequency ride-through NOT-RUN: no frequency excursion (generator "
                "Toggle/trip or load step) is modeled yet — follow-up dolphin"
            )
        )
        return RideThroughResult.from_case(
            case=spec.kind,
            ran=False,
            converged=False,
            rode_through=None,  # UNSUPPORTED — not yet physically modeled
            target_pu=spec.target_pu,
            target_hz=spec.target_hz,
            k_factor=spec.k_factor,
            min_voltage_pu=None,
            max_voltage_pu=None,
            n_devices=0,
            detail=f"{reason}. {spec.detail}",
        )

    andes = _require_andes()  # pragma: no cover - requires [grid] extra
    (  # pragma: no cover - requires [grid] extra
        solved,
        converged,
        n_devices,
        vmin,
        vmax,
        evidence,
        detail,
    ) = _solve_case(andes, spec, tf=tf)
    # ``ran`` reflects whether the solver ACTUALLY EXECUTED (a candidate loaded and the TDS
    # ran) — True even for an early-terminated / diverged solve; False only on a genuine
    # case-setup failure. ``rode_through`` is derived by the pure reducer, never from the
    # raw ``converged`` flag: a converged solve is graded on the physical envelope, while an
    # unstable/early-terminated solve under an APPLIED LVRT fault is a COLLAPSE → False.
    rode_through = _lvrt_dynamic_verdict(  # pragma: no cover - requires [grid] extra
        fault_applied=spec.fault_x_pu is not None,
        solved=solved,
        converged=converged,
        evidence=evidence,
        envelope=env,
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
        n_devices=n_devices,
        detail=detail,
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
    "RideThroughEnvelope",
    "RideThroughCaseSpec",
    "LvrtEvidence",
    "lvrt_rode_through",
    "_lvrt_dynamic_verdict",
    "envelope_from_fixture",
    "build_case_spec",
    "run_ride_through_case",
    "run_ride_through_suite",
]
