"""OpenDSSDirect QSTS curtailment engine + deemed-vs-self split (D6a, #882).

This is the D6a plug-in of the grid-capability epic. It runs a quasi-static time-series
(QSTS) power-flow over a **real** feeder model, injects the per-technology generation
profiles of a hybrid plant behind ONE point-of-connection (POC) export cap, and SPLITS the
curtailed energy the way the CEB SPPA does:

  (a) **deemed-paid / grid-instructed** curtailment — the network operator instructs a
      reduction (an upstream feeder-limit / dispatch instruction). Under the CEB
      standardised PPA this is PAID as *deemed energy*, so it must NOT haircut revenue →
      KPI-NEUTRAL. It is an EXPLICIT INPUT — the committed
      ``grid.qsts.grid_instructed_profile_mw`` (the real utility feeder-limit / dispatch
      schedule), or all-zeros when the operator supplied none. It is deliberately NOT
      inferred from the QSTS monitors: a bare power-flow cannot honestly derive operator
      DISPATCH instructions, and the export cap is the plant's own self-curtailment
      boundary, not an upstream limit — so deriving deemed from a `(export − cap)` heuristic
      would DOUBLE-COUNT the same above-cap MWh as both self and deemed.
  (b) **self-curtailed** — the plant physically sheds its OWN excess above the export cap
      (the combined instantaneous output exceeds the POC export limit and there is nowhere
      for the surplus to go). This IS what the QSTS establishes — generation vs the export
      cap, its real competency. It is a REAL energy loss — the SOLE future KPI-mover — but
      it is NOT wired to finance HERE. D6b does that; this module is advisory only.

What the QSTS honestly does, and the follow-up
----------------------------------------------
The QSTS solves the load-flow feasibility / voltage state on the real feeder and establishes
the plant's self-curtailment against the export cap; the deemed-paid schedule is passed
through as an explicit input. A proper upstream-feeder-limit → operator-INSTRUCTION model
(mapping a monitored thermal / voltage breach to a dispatch instruction WITHOUT conflating
it with the plant's own export-cap self-shed) is a follow-up study — noted here rather than
faked, exactly like the D4a NOT-RUN stubs.

Hybrid curtailment-sharing with BESS charge-from-surplus (energy-conserved)
---------------------------------------------------------------------------
Surplus that would be self-curtailed can instead be ABSORBED by a co-located BESS when it
has charge headroom. The absorption reuses the D5a shared SoC model
(:func:`analytics.grid.capabilities.bess_soc.split_reserves`, the curtailment-absorption
CHARGE-direction reserve): the MWh absorbed is bounded by the SoC ``chargeable_mwh``
headroom, so the battery converts a would-be loss into stored energy WITHOUT creating
energy from nothing. ``self_curtailed`` is therefore the export-cap surplus MINUS what the
BESS absorbed, and energy is conserved:

    curtailed_total   = deemed_paid + self_curtailed_pre_bess
    self_curtailed    = self_curtailed_pre_bess - bess_absorbed     (>= 0)
    bess_absorbed    <= SoC chargeable headroom                     (D5a invariant)

Every one of these quantities is an INTEGRAL of PHYSICAL evidence (export-cap breaches of
the injected generation, the committed grid-instruction schedule, and the SoC headroom),
NEVER a solver-convergence flag. The energy-conservation identity is a real assertion at
emit (NO SPURIOUS PASS).

Real feeder vs synthetic/demo — no fabricated curtailment
---------------------------------------------------------
The QSTS is only meaningful against a REAL feeder model. A synthetic/demo feeder (the
tiny self-built radial used for a smoke test) is a demo ONLY: it MUST NOT masquerade as a
real curtailment figure and MUST refuse to overwrite the real loss placeholder. So the
engine returns an inert / NOT-RUN :class:`analytics.contracts_v14.CurtailmentShareResult`
(``ran=False``, energy fields ``None``, ``reason`` set) for every non-real path:

  * ``grid.qsts.enabled`` is not True (default-off gate) → inert;
  * no ``grid.qsts.feeder_model_path`` (or the file is absent) → inert;
  * ``feeder_source`` resolves to ``"synthetic_demo"`` → inert (a demo never overwrites the
    real placeholder), even though the demo path CAN be exercised for a live smoke test.

The pure-Python split math (:func:`split_curtailment`) is separately callable and IS the
sole producer of a real energy figure; it is fed either by the OpenDSS QSTS monitors (the
real path) or, in tests, by explicit per-timestep arrays.

CASPER
------
``opendssdirect`` is an OPTIONAL dependency of the ``[grid]`` extra. It is NEVER imported
at module-import time; the import is deferred to :func:`_require_opendss`, which raises an
actionable ImportError at call-time if the extra is absent (mirroring
:func:`analytics.grid.ride_through._require_andes`). The default (grid-free) install
imports this module cleanly and runs the whole split / gating / accounting layer.

CESSPIT
-------
Every input (export cap, per-timestep profiles, BESS block) is strict-validated with an
actionable, field-naming message and NO silent default. NaN / ±inf / bool-as-number are
rejected at every boundary, exactly like :mod:`analytics.grid.capabilities.bess_soc`.

KPI-neutral
-----------
Every result is ADVISORY (``bankable=False``); nothing here feeds the finance engine, so
committed scenarios stay byte-identical. The self-curtailment loss is wired to finance by
the follow-up dolphin D6b — not here.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping, Sequence, TypeGuard

from analytics.contracts_v14 import CurtailmentShareResult
from analytics.grid.capabilities.bess_soc import bess_soc_state, split_reserves

#: The feeder-source token stamped when the caller asked for the built-in synthetic/demo
#: feeder rather than a real model file. It is a smoke-test marker ONLY — the engine refuses
#: to emit a real curtailment figure for it (no fabricated number overwrites the placeholder).
SYNTHETIC_FEEDER_SOURCE = "synthetic_demo"

#: The feeder-source token stamped when no feeder was resolved at all (default-off / absent).
NO_FEEDER_SOURCE = "none"

#: A hair of numerical tolerance so an export-cap comparison / energy identity that holds to
#: within floating-point round-off is NOT spuriously flagged. It is one-sided slack on the
#: breach/identity checks only — it never lets a genuinely mis-balanced accounting through.
_MWH_TOL = 1e-9


def _require_opendss() -> Any:
    """Return the ``opendssdirect`` module or raise an actionable CASPER error if absent."""
    try:
        import opendssdirect  # noqa: F401

        return opendssdirect  # pragma: no cover - requires [grid] extra
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "The grid QSTS curtailment engine requires the [grid] extra: "
            "pip install 'opendssdirect.py>=0.9.4'  (or  PIP_CONSTRAINT=constraints.txt "
            "pip install -e '.[grid]'). It is an OPTIONAL dependency — the base finance "
            "install never needs it."
        ) from exc


def _is_number(value: Any) -> TypeGuard[int | float]:
    """True iff ``value`` is a real, FINITE (non-bool, non-NaN/inf) int/float.

    Finiteness is part of the guard so NaN / ±inf are REJECTED at every input boundary: a
    NaN silently passes all ``<`` / ``>`` comparisons, which would let a NaN generation
    sample yield a spurious "no breach" (``nan > cap`` is False). Rejecting it here keeps
    the energy accounting honest (NO SPURIOUS PASS).
    """
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _require_positive(value: Any, field: str) -> float:
    """Return ``value`` as a positive float or raise a CESSPIT config error."""
    if not _is_number(value) or float(value) <= 0.0:
        raise ValueError(
            f"QSTS curtailment engine requires {field} to be a number > 0, got {value!r}."
        )
    return float(value)


def _require_profile(
    values: Any, field: str, *, length: int | None = None
) -> list[float]:
    """Validate a per-timestep MWh profile: a non-empty sequence of finite floats >= 0.

    Strict (CESSPIT): a missing / non-sequence / empty profile, a non-finite / negative /
    bool sample, or a length mismatch against ``length`` (when given) RAISES with an
    actionable, field-naming message. This is the boundary that stops a NaN / negative
    generation sample from fabricating a spurious "no self-curtailment" pass.
    """
    if (
        not isinstance(values, Sequence)
        or isinstance(values, (str, bytes))
        or len(values) == 0
    ):
        raise ValueError(
            f"QSTS curtailment engine requires {field} to be a non-empty sequence of "
            f"per-timestep MWh values (>= 0), got {values!r}."
        )
    if length is not None and len(values) != length:
        raise ValueError(
            f"QSTS curtailment engine requires {field} to have {length} timesteps "
            f"(matching the generation profile), got {len(values)}."
        )
    out: list[float] = []
    for i, v in enumerate(values):
        if not _is_number(v) or float(v) < 0.0:
            raise ValueError(
                f"QSTS curtailment engine requires every {field}[{i}] to be a finite "
                f"number >= 0 (MWh), got {v!r}."
            )
        out.append(float(v))
    return out


def _bess_chargeable_headroom_mwh(
    grid: Mapping[str, Any] | None, reference_year: int | None
) -> float:
    """Total BESS CHARGE headroom (MWh) available to absorb export-cap surplus (strict).

    Reuses the D5a shared SoC model — :func:`bess_soc_state` for the SoH-degraded usable
    energy + operating-window headroom, then :func:`split_reserves` to bound the
    curtailment-absorption CHARGE-direction reserve by ``chargeable_mwh`` (the room below
    the max-SoC ceiling). We do NOT re-derive battery energy accounting; the D5a
    no-double-count invariant is the point — the absorbed MWh can never exceed this
    headroom.

    ``grid`` None (no co-located BESS) → 0.0 headroom (a valid "no battery" declaration, not
    a silent pass). Present → strict per the D5a validators (a malformed BESS block raises).
    """
    if grid is None:
        return 0.0
    # The operating SoC is a KPI-relevant input: it sets the charge headroom, which caps
    # BESS absorption, which reduces the (D6b) self-curtailment loss. So it is STRICT — there
    # is NO silent default (a mid-window / full-charge assumption would OVERSTATE headroom,
    # overstate absorption, and UNDERSTATE the self-curtailment KPI-mover). A block with no
    # explicit soc_fraction is REJECTED with an actionable message (CESSPIT); the caller must
    # commit the operating SoC (the binding, conservative case) — mirroring D5a's refusal to
    # assume state-of-health. The [min_soc, max_soc] window stays strict via bess_soc_state.
    raw_soc = grid.get("soc_fraction")
    if not _is_number(raw_soc):
        raise ValueError(
            "QSTS BESS absorption requires the co-located battery block to declare an "
            "explicit operating grid.qsts.bess.soc_fraction (a fraction in the "
            "[min_soc, max_soc] window). It is NOT defaulted: the operating SoC sets the "
            "charge headroom that caps absorption and therefore the self-curtailment loss "
            "(a KPI-relevant quantity), so a silent optimistic default is not allowed. Got "
            f"soc_fraction={raw_soc!r}."
        )
    state = bess_soc_state(
        grid, soc_fraction=float(raw_soc), reference_year=reference_year
    )
    # Ask the D5a splitter for the whole chargeable headroom as the curtailment reserve;
    # the grant is clamped to chargeable_mwh, so it is the true absorbable ceiling.
    split = split_reserves(
        state,
        firming_mwh=0.0,
        frequency_mwh=0.0,
        curtailment_mwh=state.chargeable_mwh,
    )
    return split.curtailment_allocated_mwh


def _assert_energy_conserved(
    *,
    self_pre_bess: float,
    bess_absorbed: float,
    self_curtailed: float,
    headroom: float,
) -> None:
    """Raise iff the BESS-recovery energy balance violates a physical invariant.

    The three physical identities the curtailment split MUST satisfy (NO SPURIOUS PASS):

      * ``bess_absorbed <= headroom`` — the D5a no-double-count invariant: the battery can
        never absorb more than its chargeable headroom (no energy created from nothing);
      * ``self_curtailed >= 0`` — the net self-curtailment cannot be negative (the BESS
        cannot absorb more than the surplus that existed);
      * ``self_curtailed + bess_absorbed == self_pre_bess`` — the self-shed surplus is
        exactly partitioned into recovered-into-BESS + net-loss (energy conserved).

    A violation is an internal accounting bug; this raises rather than emitting a spurious
    result. Extracted as a pure helper so every branch is directly unit-testable (grid-free)
    without having to fabricate a QSTS run.
    """
    if bess_absorbed > headroom + _MWH_TOL:
        raise ValueError(
            f"QSTS BESS absorption {bess_absorbed} MWh exceeds the SoC chargeable headroom "
            f"{headroom} MWh — the D5a no-double-count invariant would be violated."
        )
    if self_curtailed < -_MWH_TOL:
        raise ValueError(
            f"QSTS net self-curtailment is negative ({self_curtailed} MWh) — the BESS "
            "absorbed more than the surplus, which is physically impossible."
        )
    if abs((self_curtailed + bess_absorbed) - self_pre_bess) > _MWH_TOL:
        raise ValueError(
            "QSTS self-curtailment split breach: self_curtailed "
            f"{self_curtailed} + bess_absorbed {bess_absorbed} != self_pre_bess "
            f"{self_pre_bess} (energy not conserved)."
        )


def split_curtailment(
    *,
    generation_mwh: Sequence[float],
    export_cap_mw: float,
    grid_instructed_mwh: Sequence[float],
    timestep_hours: float = 1.0,
    bess_grid: Mapping[str, Any] | None = None,
    reference_year: int | None = None,
    feeder_source: str,
) -> CurtailmentShareResult:
    """Split integrated curtailment into deemed-paid vs (BESS-recovered) self-curtailed.

    This is the PURE-PYTHON accounting core (no OpenDSS) that both the real QSTS path and
    the grid-free tests feed. It integrates the per-timestep curtailment from PHYSICAL
    quantities and enforces energy conservation:

      * At each timestep the plant's export ceiling is ``export_cap_mw * timestep_hours``
        MWh. Any generation ABOVE that ceiling is SELF-curtailed surplus (the plant sheds
        its own excess). ``grid_instructed_mwh[t]`` is the MWh the operator instructed to
        curtail at that timestep for an UPSTREAM feeder-limit reason (a monitor breach the
        plant did not cause by over-producing) — that is DEEMED-PAID, capped at the energy
        actually exported below the cap (you cannot be instructed to shed more than you were
        exporting).
      * The self-shed surplus is then offered to the BESS: up to the SoC ``chargeable``
        headroom is ABSORBED (recovered energy), and the NET self-curtailment is the surplus
        minus what the BESS took. The absorbed MWh is bounded by the D5a headroom, so no
        energy is created.

    Args:
        generation_mwh: per-timestep GROSS generation (MWh, >= 0) injected at the POC.
        export_cap_mw: the POC export limit (MW, > 0). The per-timestep ceiling is
            ``export_cap_mw * timestep_hours``.
        grid_instructed_mwh: per-timestep grid-instructed (deemed-paid) curtailment (MWh,
            >= 0), same length as ``generation_mwh``. From the QSTS upstream-feeder-limit
            monitors on the real path; explicit in tests. Zeros = no instruction.
        timestep_hours: hours per timestep (default 1.0 = hourly).
        bess_grid: the co-located BESS ``grid`` block (D5a-shaped) whose CHARGE headroom can
            absorb self-shed surplus; ``None`` = no battery (0 recovery).
        reference_year: the BESS SoH evaluation year (``None`` = end-of-life, the binding
            smallest-headroom case).
        feeder_source: provenance string stamped on the result (the real feeder path, or a
            demo marker). A real figure is produced regardless of this string — the CALLER
            decides (via :func:`run_qsts_curtailment`) whether a synthetic source is allowed
            to surface as a real result.

    Returns:
        A :class:`CurtailmentShareResult` with ``ran=True`` and the full deemed-vs-self
        split + BESS-recovery accounting. ADVISORY (``bankable=False``).

    Raises:
        ValueError: on any strict input failure (CESSPIT), or if the energy-conservation
            identity fails to hold (an internal invariant breach — NEVER silently emitted).
    """
    cap_mw = _require_positive(export_cap_mw, "export_cap_mw")
    step_h = _require_positive(timestep_hours, "timestep_hours")
    gen = _require_profile(generation_mwh, "generation_mwh")
    instructed = _require_profile(
        grid_instructed_mwh, "grid_instructed_mwh", length=len(gen)
    )

    cap_mwh = cap_mw * step_h  # the per-timestep export ceiling in MWh

    gross_energy = 0.0
    self_pre_bess = 0.0
    deemed_paid = 0.0
    hours_self_curtailed = 0
    for g, instr in zip(gen, instructed, strict=True):
        gross_energy += g
        # SELF-curtailment: generation strictly above the export ceiling is physically shed
        # by the plant (its own excess). This is the real-loss quantity.
        over_cap = max(0.0, g - cap_mwh)
        if over_cap > _MWH_TOL:
            self_pre_bess += over_cap
            hours_self_curtailed += 1
        # DEEMED-PAID: the operator can only instruct a reduction of the energy that WAS
        # being exported (at or below the cap) — you cannot be told to shed more than you
        # were putting onto the grid. Cap the instruction at the exported-below-cap energy.
        exported_below_cap = min(g, cap_mwh)
        deemed_paid += min(max(0.0, instr), exported_below_cap)

    # BESS charge-from-surplus: absorb up to the SoC chargeable headroom (D5a-bounded), so
    # the net self-curtailment is the surplus the battery could NOT take. This is the ONLY
    # place recovery happens; it can never exceed the headroom, so no energy is created.
    headroom = _bess_chargeable_headroom_mwh(bess_grid, reference_year)
    bess_absorbed = min(self_pre_bess, headroom)
    self_curtailed = self_pre_bess - bess_absorbed

    curtailed_total = deemed_paid + self_pre_bess

    # ENERGY-CONSERVATION ASSERTION (NO SPURIOUS PASS): re-derive the physical identities
    # from the integrated quantities and raise on ANY violation. These come from the
    # integrals above, never from a solver flag; a breach is an internal accounting bug and
    # must NEVER be emitted as a result.
    _assert_energy_conserved(
        self_pre_bess=self_pre_bess,
        bess_absorbed=bess_absorbed,
        self_curtailed=self_curtailed,
        headroom=headroom,
    )

    deemed_pct = (deemed_paid / gross_energy * 100.0) if gross_energy > 0.0 else 0.0
    self_pct = (self_curtailed / gross_energy * 100.0) if gross_energy > 0.0 else 0.0

    return CurtailmentShareResult(
        ran=True,
        feeder_source=feeder_source,
        export_cap_mw=cap_mw,
        gross_energy_mwh=gross_energy,
        curtailed_total_mwh=curtailed_total,
        deemed_paid_energy_mwh=deemed_paid,
        self_curtailed_pre_bess_mwh=self_pre_bess,
        bess_absorbed_energy_mwh=bess_absorbed,
        self_curtailed_energy_mwh=self_curtailed,
        deemed_paid_pct=deemed_pct,
        self_curtailed_pct=self_pct,
        hours_self_curtailed=hours_self_curtailed,
        hours_total=len(gen),
        method="opendss_qsts",
        reason=(
            f"QSTS over {len(gen)} timestep(s) @ {step_h:g} h against feeder "
            f"'{feeder_source}': gross {gross_energy:.3f} MWh; curtailed "
            f"{curtailed_total:.3f} = deemed-paid {deemed_paid:.3f} (grid-instructed → PAID "
            f"as deemed energy, KPI-neutral) + self-shed {self_pre_bess:.3f}; BESS absorbed "
            f"{bess_absorbed:.3f} (<= chargeable {headroom:.3f}) → NET self-curtailment "
            f"{self_curtailed:.3f} MWh (the D6b KPI-mover). Energy conserved."
        ),
        notes=(
            "Advisory QSTS curtailment split — deemed-paid is grid-instructed (paid as "
            "deemed energy, does NOT haircut revenue); self-curtailed is the physical "
            "export-cap loss AFTER BESS recovery (the sole future KPI-mover, wired by D6b). "
            "NOT the utility-accepted hosting-capacity study."
        ),
    )


def _inert_result(feeder_source: str, reason: str) -> CurtailmentShareResult:
    """Build the NOT-RUN / inert result (energy fields ``None``, ``ran=False``).

    Used for every non-real path: default-off gate, no/absent feeder, or a synthetic/demo
    feeder (which must NEVER surface as a real curtailment figure). A fabricated zero-loss
    "pass" is exactly what this refuses to emit — the energy fields stay ``None`` so no
    downstream consumer can mistake the inert result for a real, zero-curtailment run.
    """
    return CurtailmentShareResult(
        ran=False,
        feeder_source=feeder_source,
        reason=reason,
        notes=(
            "QSTS curtailment study NOT-RUN (inert): no real feeder curtailment figure was "
            "produced. This does NOT overwrite the real loss placeholder — a fabricated "
            "zero-loss pass is refused (NO SPURIOUS PASS)."
        ),
    )


def _resolve_feeder(grid: Mapping[str, Any]) -> tuple[str | None, bool]:
    """Resolve the QSTS feeder source from the grid.qsts block → (source, is_real).

    Returns ``(feeder_path, True)`` when a real, existing ``grid.qsts.feeder_model_path``
    file is declared; ``(SYNTHETIC_FEEDER_SOURCE, False)`` when the block explicitly opts
    into the built-in demo feeder (``grid.qsts.use_synthetic_demo: true``); and
    ``(None, False)`` when no feeder is resolvable (absent path / missing file). A synthetic
    feeder is NEVER treated as real (``is_real`` False), so it cannot overwrite the real
    placeholder.
    """
    qsts = grid.get("qsts")
    if not isinstance(qsts, Mapping):
        return None, False
    if qsts.get("use_synthetic_demo") is True:
        return SYNTHETIC_FEEDER_SOURCE, False
    path = qsts.get("feeder_model_path")
    if isinstance(path, str) and path.strip() and Path(path).is_file():
        return path, True
    return None, False


def run_qsts_curtailment(
    config: Mapping[str, Any],
    *,
    generation_mwh: Sequence[float] | None = None,
    grid_instructed_mwh: Sequence[float] | None = None,
    export_cap_mw: float | None = None,
    timestep_hours: float = 1.0,
    reference_year: int | None = None,
) -> CurtailmentShareResult:
    """Run the QSTS curtailment study for a scenario config, gated + real-feeder-guarded.

    The single entry seam. It applies the gating BEFORE any solve, so the OpenDSS path is
    reached ONLY for a real, enabled study:

      * ``grid.qsts.enabled`` not True (default-off) → inert NOT-RUN result;
      * no real ``grid.qsts.feeder_model_path`` (absent / missing file) → inert;
      * a synthetic/demo feeder (``grid.qsts.use_synthetic_demo: true``) → inert (a demo
        NEVER surfaces as a real curtailment figure, so it cannot overwrite the placeholder).

    Only when a REAL feeder is resolved and the study is enabled does it reach the OpenDSS
    QSTS solve (behind :func:`_require_opendss`), which produces the per-timestep gross
    generation + upstream grid-instruction profiles the pure :func:`split_curtailment`
    consumes. Tests may inject those profiles directly via ``generation_mwh`` /
    ``grid_instructed_mwh`` (skipping the solve) to exercise the accounting grid-free.

    Args:
        config: the full scenario config (or its top-level ``grid`` block).
        generation_mwh / grid_instructed_mwh / export_cap_mw: optional pre-computed QSTS
            profiles + export cap (tests inject these to drive the pure accounting without
            an OpenDSS solve). When omitted on a real+enabled study, the OpenDSS QSTS solve
            supplies them.
        timestep_hours: hours per QSTS timestep (default 1.0).
        reference_year: the BESS SoH evaluation year forwarded to the split (``None`` =
            end-of-life).

    Returns:
        A :class:`CurtailmentShareResult`: ``ran=True`` with the deemed-vs-self split only
        for a real, enabled, solved study; otherwise an inert NOT-RUN result with a reason.
    """
    grid = config.get("grid") if isinstance(config, Mapping) else None
    if not isinstance(grid, Mapping):
        return _inert_result(
            NO_FEEDER_SOURCE,
            "no grid block — the QSTS curtailment study is grid-scoped and default-off.",
        )

    qsts = grid.get("qsts")
    if not isinstance(qsts, Mapping) or qsts.get("enabled") is not True:
        return _inert_result(
            NO_FEEDER_SOURCE,
            "grid.qsts.enabled is not True (default-off gate) — QSTS curtailment NOT-RUN.",
        )

    feeder_source, is_real = _resolve_feeder(grid)
    if not is_real:
        if feeder_source == SYNTHETIC_FEEDER_SOURCE:
            return _inert_result(
                SYNTHETIC_FEEDER_SOURCE,
                "grid.qsts uses the synthetic/demo feeder — a smoke test only. A synthetic "
                "feeder MUST NOT overwrite the real curtailment placeholder, so no real "
                "figure is produced (run the OpenDSS demo path directly for a live smoke "
                "test; it never surfaces as bankable).",
            )
        return _inert_result(
            NO_FEEDER_SOURCE,
            "grid.qsts.enabled is True but no real grid.qsts.feeder_model_path resolved "
            "(absent path or missing file) — the QSTS requires a real feeder model.",
        )

    cap = export_cap_mw if export_cap_mw is not None else _export_cap_from_grid(grid)

    # A real, enabled study. When the caller injected the QSTS profiles (tests / a
    # pre-solved horizon), account them directly. Otherwise run the OpenDSS QSTS solve to
    # produce them. The solve is the ONLY [grid]-extra path here.
    if generation_mwh is not None:
        gen = generation_mwh
        instructed = (
            grid_instructed_mwh
            if grid_instructed_mwh is not None
            else [0.0] * len(generation_mwh)
        )
    else:  # pragma: no cover - requires [grid] extra
        gen, instructed = _solve_qsts(
            grid,
            feeder_path=str(feeder_source),
            timestep_hours=timestep_hours,
        )

    return split_curtailment(
        generation_mwh=gen,
        export_cap_mw=float(cap),
        grid_instructed_mwh=instructed,
        timestep_hours=timestep_hours,
        bess_grid=_bess_block(grid),
        reference_year=reference_year,
        feeder_source=str(feeder_source),
    )


def _export_cap_from_grid(grid: Mapping[str, Any]) -> float:
    """Resolve the POC export cap (MW) for the QSTS (strict, no silent default).

    Prefers ``grid.qsts.export_cap_mw``; falls back to the top-level ``grid.export_cap_mw``.
    STRICT (CESSPIT): neither present / ill-formed RAISES — the self-curtailment split is
    meaningless without a real export ceiling to measure the surplus against.
    """
    qsts = grid.get("qsts")
    cap = qsts.get("export_cap_mw") if isinstance(qsts, Mapping) else None
    if cap is None:
        cap = grid.get("export_cap_mw")
    return _require_positive(cap, "grid.qsts.export_cap_mw (or grid.export_cap_mw)")


def _bess_block(grid: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Return the co-located BESS ``grid`` block (D5a-shaped) if declared, else ``None``.

    Reads ``grid.qsts.bess`` (the curtailment-absorption battery). Absent → ``None`` (no
    battery; 0 recovery — a valid declaration, not a silent pass).
    """
    qsts = grid.get("qsts")
    bess = qsts.get("bess") if isinstance(qsts, Mapping) else None
    return bess if isinstance(bess, Mapping) else None


def _solve_qsts(  # pragma: no cover - requires [grid] extra
    grid: Mapping[str, Any],
    *,
    feeder_path: str,
    timestep_hours: float,
) -> tuple[list[float], list[float]]:
    """Run the OpenDSSDirect QSTS solve over the REAL feeder and return the QSTS profiles.

    What the QSTS honestly measures — and what it does NOT
    -----------------------------------------------------
    A bare QSTS power-flow establishes the plant's own SELF-curtailment against the export
    cap (generation vs the cap — its real competency), which the pure
    :func:`split_curtailment` derives downstream. It CANNOT infer operator DISPATCH
    INSTRUCTIONS: an over-cap hour is the plant's own self-curtailment boundary, not an
    upstream feeder-limit instruction, so deriving "deemed" from a `(export − cap)` voltage
    heuristic would DOUBLE-COUNT the same above-cap MWh as both self AND deemed. Therefore
    grid-instructed / deemed-paid curtailment is an EXPLICIT INPUT here — the committed
    per-timestep ``grid.qsts.grid_instructed_profile_mw`` (the real utility feeder-limit /
    dispatch schedule), or all-zeros when the operator supplied no schedule. This function
    returns:

      * ``generation_mwh`` — the per-timestep GROSS generation injected (before the export
        cap); the QSTS solves each step (the load-flow feasibility / voltage state is the
        real-feeder value-add); the pure split derives self-curtailment from it vs the cap.
      * ``grid_instructed_mwh`` — the committed deemed-paid schedule (or zeros), passed
        straight through — NOT derived from a monitor heuristic.

    A proper upstream-feeder-limit → operator-instruction model (mapping a monitored thermal
    / voltage breach to a dispatch instruction WITHOUT conflating it with the plant's own
    export-cap self-shed) is a follow-up study, not this dolphin.

    This is the ONLY function that touches ``opendssdirect``; it is reached solely for a
    real, enabled study (the caller gated everything else). A synthetic/demo feeder never
    reaches here.
    """
    dss = _require_opendss()
    dss.Command(f'Redirect "{feeder_path}"')
    dss.Solution.Mode(1)  # daily/QSTS time-series mode
    dss.Solution.StepSize(timestep_hours * 3600.0)

    profiles = _resolve_generation_profiles(grid)
    instructed_profile = _resolve_grid_instructed_profile_mw(
        grid, n_steps=len(profiles)
    )
    generation: list[float] = []
    instructed: list[float] = []
    for t, p_mw in enumerate(profiles):
        _inject_poc_power(dss, p_mw)
        dss.Solution.Number(1)
        dss.Solution.Solve()
        generation.append(p_mw * timestep_hours)
        # Deemed-paid is the COMMITTED operator schedule, NOT a monitor heuristic — deriving
        # it from generation-vs-cap here would double-count the plant's own self-curtailment.
        instructed.append(instructed_profile[t] * timestep_hours)
    return generation, instructed


def _resolve_generation_profiles(  # pragma: no cover - requires [grid] extra
    grid: Mapping[str, Any],
) -> list[float]:
    """Per-timestep aggregate plant generation (MW) at the POC for the QSTS horizon.

    Resolves the injection profile the QSTS steps through. Preference order:

      * an explicit ``grid.qsts.generation_profile_mw`` (a committed per-timestep MW series
        — the reproducible, network-free path); otherwise
      * the per-tech resource producers (wind_resource / solar_resource) built behind their
        OWN call-time PyWake / windpowerlib / pvlib guards — this module never imports them
        at module scope.

    The common path is a caller-supplied profile (``run_qsts_curtailment(generation_mwh=)``),
    which skips this entirely; live per-tech profile generation from the resource packages
    is wired by a follow-up dolphin (kept behind those packages' optional-dep guards).
    """
    qsts = grid.get("qsts")
    profile = qsts.get("generation_profile_mw") if isinstance(qsts, Mapping) else None
    return _require_profile(profile, "grid.qsts.generation_profile_mw")


def _resolve_grid_instructed_profile_mw(
    grid: Mapping[str, Any], *, n_steps: int
) -> list[float]:
    """The committed per-timestep grid-instructed (deemed-paid) MW schedule for the QSTS.

    Reads ``grid.qsts.grid_instructed_profile_mw`` — the REAL utility feeder-limit / operator
    dispatch schedule (the deemed-paid curtailment the CEB SPPA pays). When ABSENT the
    schedule is all-zeros (the QSTS then measures ONLY the plant's own export-cap
    self-curtailment — no deemed curtailment is asserted where none was instructed). When
    present it is strict (CESSPIT): a finite, non-negative per-timestep MW series that MUST
    match the generation profile length. This is deliberately NOT derived from the QSTS
    monitors — a bare power-flow cannot infer operator instructions, and deriving deemed from
    generation-vs-cap would double-count the self-curtailment.
    """
    qsts = grid.get("qsts")
    profile = (
        qsts.get("grid_instructed_profile_mw") if isinstance(qsts, Mapping) else None
    )
    if profile is None:
        return [0.0] * n_steps
    return _require_profile(
        profile, "grid.qsts.grid_instructed_profile_mw", length=n_steps
    )


def _inject_poc_power(  # pragma: no cover - requires [grid] extra
    dss: Any, p_mw: float
) -> None:
    """Set the POC generator active-power injection (MW) for the current QSTS step."""
    dss.Generators.kW(p_mw * 1000.0)


__all__ = [
    "SYNTHETIC_FEEDER_SOURCE",
    "NO_FEEDER_SOURCE",
    "split_curtailment",
    "run_qsts_curtailment",
]
