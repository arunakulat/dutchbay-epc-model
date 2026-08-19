"""OpenDSSDirect QSTS curtailment engine + deemed-vs-self split (D6a, #882).

This is the D6a plug-in of the grid-capability epic. It runs a quasi-static time-series
(QSTS) power-flow over an **explicitly classified** feeder input, injects the
per-technology generation profiles of a hybrid plant behind ONE point-of-connection (POC)
export cap, and SPLITS the calculated curtailment:

  (a) **deemed-paid / grid-instructed** curtailment — the network operator instructs a
      reduction (an upstream feeder-limit / dispatch instruction). Under the CEB
      standardised PPA this is PAID as *deemed energy*, so it must NOT haircut revenue →
      KPI-NEUTRAL. It is an EXPLICIT INPUT — the committed
      ``grid.qsts.grid_instructed_profile_mw`` (the real utility feeder-limit / dispatch
      schedule), or an all-zero calculation vector when no schedule was supplied. That
      zero vector does not assert that no historical/future operator instruction exists. It is NOT
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
The QSTS solves the load-flow feasibility / voltage state on the declared feeder input and
calculates the plant's export-cap self-curtailment; the deemed-paid schedule is passed
through as an explicit input. A synthetic/test input proves only that the software path
executes—it says nothing about DutchBay site physics. A proper upstream-feeder-limit →
operator-INSTRUCTION model
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

Every one of these quantities is integrated from the supplied generation, export-cap,
grid-instruction, and SoC inputs, NEVER from a solver-convergence flag. Their evidentiary
grade remains the evidentiary grade of those inputs. The energy-conservation identity is a
real calculation assertion at emit (NO SPURIOUS PASS).

Feeder evidence classification — no path laundering
----------------------------------------------------
File existence is not provenance. Every path-backed run declares ``grid.qsts.input_kind``.
A synthetic/test file may execute for advisory software diagnostics, but the result is
typed ``generated_input=True``, ``site_representative=False`` and
``canonical_finance_eligible=False``. Canonical finance refuses it. The engine returns an
inert / NOT-RUN :class:`analytics.contracts_v14.CurtailmentShareResult` only when no
path-backed solve is available:

  * ``grid.qsts.enabled`` is not True (default-off gate) → inert;
  * no ``grid.qsts.feeder_model_path`` (or the file is absent) → inert;
  * the pathless built-in ``"synthetic_demo"`` is selected → inert.

The governed ``synthetic_placeholder`` has an additional B2 boundary: its external
configuration supplies ``grid.qsts.source_manifest_sha256``; runtime derives the colocated
manifest from the exact ``feeder/Master.dss`` path, invokes the detached B1 verifier, and
propagates the verified digest. A manifest or path does not upgrade evidence grade.

The pure-Python split math (:func:`split_curtailment`) is separately callable and is the
sole producer of the calculated energy split. Execution status never upgrades evidence
status.

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
Every result is ADVISORY (``bankable=False``). The separate D6b seam may consume only an
explicitly canonical-finance-eligible site/utility result; generated/test results are
refused. The committed scenario remains default-off and byte-identical.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence, TypeGuard

from analytics.contracts_v14 import (
    CANONICAL_FEEDER_INPUT_KINDS,
    FEEDER_INPUT_KINDS,
    SYNTHETIC_FEEDER_INPUT_KINDS,
    CurtailmentShareResult,
)
from analytics.grid.capabilities.bess_soc import bess_soc_state, split_reserves

#: The feeder-source token stamped when the caller asked for the built-in synthetic/demo
#: feeder rather than a path-backed model file. It is an inert smoke-test marker only.
SYNTHETIC_FEEDER_SOURCE = "synthetic_demo"

#: The feeder-source token stamped when no feeder was resolved at all (default-off / absent).
NO_FEEDER_SOURCE = "none"

#: Fixed package-manifest location relative to the governed synthetic ``feeder/Master.dss``.
SYNTHETIC_PACKAGE_MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True)
class FeederInput:
    """Resolved QSTS feeder input with evidence kind kept separate from its path.

    A file existing on disk says nothing about whether it is utility-provided, an
    engineer-prepared site model, a generated placeholder, or a unit-test fixture.  This
    typed boundary prevents the former ``Path.is_file() == real`` inference from laundering
    synthetic evidence into finance.
    """

    source: str | None
    input_kind: str | None
    model_exists: bool
    generated_input: bool
    observed_network_data: bool
    site_representative: bool
    canonical_finance_eligible: bool
    source_manifest_sha256: str | None = None

    def __post_init__(self) -> None:
        """Prevent a verified-manifest identity from being attached to another kind."""

        if self.source_manifest_sha256 is None:
            return
        _require_sha256(
            self.source_manifest_sha256, "FeederInput.source_manifest_sha256"
        )
        if (
            self.input_kind != "synthetic_placeholder"
            or self.generated_input is not True
        ):
            raise ValueError(
                "FeederInput.source_manifest_sha256 is reserved for a generated "
                "synthetic_placeholder."
            )

    @property
    def can_solve(self) -> bool:
        return self.source is not None and self.model_exists


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


def _require_sha256(value: Any, field: str) -> str:
    """Return an exact lowercase SHA-256 digest or raise a CESSPIT error."""

    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(
            f"{field} must be exactly 64 lowercase hexadecimal characters, got "
            f"{value!r}."
        )
    return value


def _verify_synthetic_feeder_runtime_package(
    *, master_path: Path, expected_manifest_sha256: str
) -> tuple[str, str]:
    """Verify the governed B1 package before B2 exposes it to QSTS accounting.

    The expected digest is supplied outside the package. The manifest path is derived from
    the governed ``<package>/feeder/Master.dss`` layout, so a caller cannot pair one feeder
    with an unrelated manifest. Import stays behind the explicitly synthetic enabled path;
    default-off, real/site, and test-fixture callers retain the light CASPER import surface.
    """

    try:
        from analytics.grid.synthetic_feeder_placeholder import (
            verify_synthetic_feeder_package,
        )
    except ImportError as exc:  # pragma: no cover - environment-specific dependency gap
        raise ImportError(
            "Runtime verification of the #923 synthetic feeder package requires the "
            "repository's locked synthetic-feeder dependencies. Rebuild the governed "
            "Python 3.12 environment before enabling this path."
        ) from exc

    manifest_path = master_path.parent.parent / SYNTHETIC_PACKAGE_MANIFEST_NAME
    package = verify_synthetic_feeder_package(
        manifest_path=manifest_path,
        master_path=master_path,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    if package.opendss_compile_status != "passed_compile_only_no_convergence_claim":
        raise ValueError(
            "Runtime use of a synthetic_placeholder requires a package whose detached "
            "OpenDSS compile check passed. Test-only compile-disabled packages are not "
            "runtime inputs."
        )
    return str(package.master_path), package.manifest_sha256


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
    feeder_input_kind: str | None = None,
    generated_input: bool = False,
    observed_network_data: bool = False,
    site_representative: bool = False,
    canonical_finance_eligible: bool = False,
    source_manifest_sha256: str | None = None,
    limitations: tuple[str, ...] = (),
) -> CurtailmentShareResult:
    """Split integrated curtailment into deemed-paid vs (BESS-recovered) self-curtailed.

    This is the PURE-PYTHON accounting core (no OpenDSS) that every explicitly classified
    QSTS path and the grid-free tests feed. It integrates the per-timestep configured
    quantities and enforces energy conservation; it does not assign their evidence grade:

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
            schedule supplied to the run; explicit in tests. Zeros mean no instruction
            was supplied to this calculation, not proof that none occurred.
        timestep_hours: hours per timestep (default 1.0 = hourly).
        bess_grid: the co-located BESS ``grid`` block (D5a-shaped) whose CHARGE headroom can
            absorb self-shed surplus; ``None`` = no battery (0 recovery).
        reference_year: the BESS SoH evaluation year (``None`` = end-of-life, the binding
            smallest-headroom case).
        feeder_source: path/source string stamped on the result. It is not provenance by
            itself; the explicit evidence fields carry that classification.
        source_manifest_sha256: externally pinned and runtime-verified package-manifest
            identity, when the feeder came from the governed #923 synthetic package.

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
        feeder_input_kind=feeder_input_kind,
        generated_input=generated_input,
        observed_network_data=observed_network_data,
        site_representative=site_representative,
        canonical_finance_eligible=canonical_finance_eligible,
        source_manifest_sha256=source_manifest_sha256,
        limitations=limitations,
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


def _inert_result(
    feeder_source: str,
    reason: str,
    *,
    feeder_input_kind: str | None = None,
    generated_input: bool = False,
    limitations: tuple[str, ...] = (),
) -> CurtailmentShareResult:
    """Build the NOT-RUN / inert result (energy fields ``None``, ``ran=False``).

    Used for default-off, no/absent path, and the pathless built-in demo. A path-backed
    synthetic/test input may execute but remains typed noncanonical. A fabricated zero-loss
    "pass" is refused here: energy fields stay ``None`` when no calculation ran.
    """
    return CurtailmentShareResult(
        ran=False,
        feeder_source=feeder_source,
        feeder_input_kind=feeder_input_kind,
        generated_input=generated_input,
        observed_network_data=False,
        site_representative=False,
        canonical_finance_eligible=False,
        limitations=limitations,
        reason=reason,
        notes=(
            "QSTS curtailment study NOT-RUN (inert): no path-backed calculation was "
            "produced. This does NOT overwrite the real-data placeholder — a fabricated "
            "zero-loss pass is refused (NO SPURIOUS PASS)."
        ),
    )


def _resolve_feeder(grid: Mapping[str, Any]) -> FeederInput:
    """Resolve a feeder without inferring evidence quality from file existence.

    ``grid.qsts.input_kind`` is the controlling provenance token.  An existing path may be
    solved for any declared kind, including a synthetic placeholder or test fixture, but
    only a site/utility kind can ever be marked canonical-finance eligible. A path-backed
    ``synthetic_placeholder`` must additionally bind an externally pinned manifest digest;
    B2 invokes the detached B1 verifier before exposing the feeder to accounting.
    """
    qsts = grid.get("qsts")
    if not isinstance(qsts, Mapping):
        return FeederInput(None, None, False, False, False, False, False)

    raw_kind = qsts.get("input_kind")
    input_kind = raw_kind if isinstance(raw_kind, str) else None
    if raw_kind is not None and input_kind not in FEEDER_INPUT_KINDS:
        allowed = ", ".join(sorted(FEEDER_INPUT_KINDS))
        raise ValueError(
            "grid.qsts.input_kind must be one of "
            f"[{allowed}], got {raw_kind!r}. A feeder path is not provenance."
        )

    raw_manifest_sha256 = qsts.get("source_manifest_sha256")
    source_manifest_sha256: str | None = None
    if raw_manifest_sha256 is not None:
        source_manifest_sha256 = _require_sha256(
            raw_manifest_sha256, "grid.qsts.source_manifest_sha256"
        )
        if input_kind != "synthetic_placeholder":
            raise ValueError(
                "grid.qsts.source_manifest_sha256 is reserved for the governed "
                "synthetic_placeholder package; do not attach it to utility, site, test, "
                "or unclassified feeder inputs."
            )

    generated = input_kind in SYNTHETIC_FEEDER_INPUT_KINDS
    observed = input_kind == "utility_observed_model"
    site_representative = input_kind in CANONICAL_FEEDER_INPUT_KINDS
    wiring = qsts.get("finance_wiring")
    if wiring is not None and not isinstance(wiring, Mapping):
        raise ValueError(
            "grid.qsts.finance_wiring must be a mapping when declared, got "
            f"{type(wiring).__name__}."
        )
    wiring_enabled = wiring.get("enabled") if isinstance(wiring, Mapping) else None
    mode = wiring.get("mode") if isinstance(wiring, Mapping) else None
    requested_canonical = (
        wiring.get("canonical_eligible") if isinstance(wiring, Mapping) else None
    )
    if wiring_enabled is not None and type(wiring_enabled) is not bool:
        raise ValueError(
            "grid.qsts.finance_wiring.enabled must be a literal boolean when declared, "
            f"got {wiring_enabled!r}."
        )
    if mode is not None and (
        not isinstance(mode, str)
        or mode not in {"canonical", "synthetic_counterfactual"}
    ):
        raise ValueError(
            "grid.qsts.finance_wiring.mode must be 'canonical' or "
            f"'synthetic_counterfactual', got {mode!r}."
        )
    if requested_canonical is not None and type(requested_canonical) is not bool:
        raise ValueError(
            "grid.qsts.finance_wiring.canonical_eligible must be a literal boolean when "
            f"declared, got {requested_canonical!r}."
        )
    if requested_canonical and input_kind not in CANONICAL_FEEDER_INPUT_KINDS:
        raise ValueError(
            "grid.qsts.finance_wiring.canonical_eligible=true is permitted only for "
            "input_kind 'utility_observed_model' or 'engineer_prepared_site_model'. "
            f"Got input_kind={input_kind!r}; synthetic/test inputs are never canonical."
        )
    if mode == "canonical" and input_kind in SYNTHETIC_FEEDER_INPUT_KINDS:
        raise ValueError(
            "grid.qsts.finance_wiring.mode='canonical' refuses synthetic_placeholder and "
            "test_fixture inputs."
        )
    if (
        mode == "synthetic_counterfactual"
        and input_kind not in SYNTHETIC_FEEDER_INPUT_KINDS
    ):
        raise ValueError(
            "grid.qsts.finance_wiring.mode='synthetic_counterfactual' requires "
            "synthetic_placeholder or test_fixture input."
        )
    if wiring_enabled is True and input_kind in CANONICAL_FEEDER_INPUT_KINDS:
        if mode != "canonical" or requested_canonical is not True:
            raise ValueError(
                "Enabled utility/site feeder finance wiring requires mode='canonical' "
                "and canonical_eligible=true."
            )
    if wiring_enabled is True and input_kind in SYNTHETIC_FEEDER_INPUT_KINDS:
        raise ValueError(
            "Synthetic/test feeder finance wiring cannot be enabled in the canonical "
            "cashflow pipeline; keep it disabled and use the separately governed "
            "counterfactual pathway once #923-D is implemented."
        )
    canonical_eligible = bool(
        requested_canonical is True
        and mode == "canonical"
        and input_kind in CANONICAL_FEEDER_INPUT_KINDS
    )

    use_synthetic_demo = qsts.get("use_synthetic_demo")
    if use_synthetic_demo is not None and type(use_synthetic_demo) is not bool:
        raise ValueError(
            "grid.qsts.use_synthetic_demo must be a literal boolean when declared, got "
            f"{use_synthetic_demo!r}."
        )
    if use_synthetic_demo is True:
        if input_kind not in SYNTHETIC_FEEDER_INPUT_KINDS:
            raise ValueError(
                "grid.qsts.use_synthetic_demo=true requires grid.qsts.input_kind to be "
                "'synthetic_placeholder' or 'test_fixture'; it cannot be classified as "
                "a real/site feeder."
            )
        if source_manifest_sha256 is not None:
            raise ValueError(
                "The pathless grid.qsts.use_synthetic_demo has no package manifest; "
                "remove grid.qsts.source_manifest_sha256."
            )
        demo_feeder_path = qsts.get("feeder_model_path")
        if isinstance(demo_feeder_path, str) and demo_feeder_path.strip():
            raise ValueError(
                "grid.qsts.use_synthetic_demo=true is ambiguous with feeder_model_path. "
                "Choose the inert built-in demo or one explicitly classified path-backed "
                "input, never both."
            )
        return FeederInput(
            SYNTHETIC_FEEDER_SOURCE,
            input_kind,
            False,
            True,
            False,
            False,
            False,
        )

    path = qsts.get("feeder_model_path")
    if not isinstance(path, str) or not path.strip():
        return FeederInput(
            None,
            input_kind,
            False,
            generated,
            observed,
            site_representative,
            False,
        )

    normalized_path = path.strip()
    if input_kind == "synthetic_placeholder" and source_manifest_sha256 is None:
        raise ValueError(
            "An enabled path-backed grid.qsts.input_kind='synthetic_placeholder' requires "
            "grid.qsts.source_manifest_sha256 pinned outside the package."
        )

    model_path = Path(normalized_path)
    model_exists = model_path.is_file()
    resolved_source = normalized_path if model_exists else None
    verified_manifest_sha256: str | None = None
    if model_exists and input_kind == "synthetic_placeholder":
        assert source_manifest_sha256 is not None
        resolved_source, verified_manifest_sha256 = (
            _verify_synthetic_feeder_runtime_package(
                master_path=model_path,
                expected_manifest_sha256=source_manifest_sha256,
            )
        )
    return FeederInput(
        resolved_source,
        input_kind,
        model_exists,
        generated,
        observed,
        site_representative,
        canonical_eligible,
        verified_manifest_sha256,
    )


def run_qsts_curtailment(
    config: Mapping[str, Any],
    *,
    generation_mwh: Sequence[float] | None = None,
    grid_instructed_mwh: Sequence[float] | None = None,
    export_cap_mw: float | None = None,
    timestep_hours: float = 1.0,
    reference_year: int | None = None,
) -> CurtailmentShareResult:
    """Run QSTS with explicit feeder evidence classification and finance eligibility.

    The single entry seam. It applies the gating BEFORE any solve, so the OpenDSS path is
    reached only for an enabled study with an existing path and explicit input kind:

      * ``grid.qsts.enabled`` not True (default-off) → inert NOT-RUN result;
      * no ``grid.qsts.feeder_model_path`` (absent / missing file) → inert;
      * the pathless built-in demo (``grid.qsts.use_synthetic_demo: true``) → inert;
      * a path-backed synthetic/test input may run diagnostically, but its result remains
        generated, non-site-representative, nonbankable, and canonical-finance-ineligible.

    Only when a classified path is resolved and the study is enabled does it reach the
    OpenDSS QSTS solve (behind :func:`_require_opendss`), which produces the per-timestep gross
    generation + upstream grid-instruction profiles the pure :func:`split_curtailment`
    consumes. Tests may inject those profiles directly via ``generation_mwh`` /
    ``grid_instructed_mwh`` (skipping the solve) to exercise the accounting grid-free.

    Args:
        config: the full scenario config (or its top-level ``grid`` block).
        generation_mwh / grid_instructed_mwh / export_cap_mw: optional pre-computed QSTS
            profiles + export cap (tests inject these to drive the pure accounting without
            an OpenDSS solve). When omitted on a path-backed enabled study, the OpenDSS solve
            supplies them.
        timestep_hours: hours per QSTS timestep (default 1.0).
        reference_year: the BESS SoH evaluation year forwarded to the split (``None`` =
            end-of-life).

    Returns:
        A :class:`CurtailmentShareResult`: ``ran=True`` when the classified path was
        calculated, with evidence eligibility carried separately; otherwise an inert
        NOT-RUN result with a reason.
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

    feeder = _resolve_feeder(grid)
    if not feeder.can_solve:
        if feeder.source == SYNTHETIC_FEEDER_SOURCE:
            return _inert_result(
                SYNTHETIC_FEEDER_SOURCE,
                "grid.qsts uses the synthetic/demo feeder — a smoke test only. A synthetic "
                "feeder MUST NOT overwrite the real-data curtailment placeholder, so the "
                "pathless built-in demo is NOT-RUN (a path-backed, explicitly typed fixture "
                "may be solved diagnostically but never becomes bankable/canonical).",
                feeder_input_kind=feeder.input_kind,
                generated_input=True,
                limitations=(
                    "Built-in synthetic demo only; no feeder model was solved.",
                    "Not site-representative, utility-accepted, bankable, or canonical.",
                ),
            )
        return _inert_result(
            NO_FEEDER_SOURCE,
            "grid.qsts.enabled is True but no existing grid.qsts.feeder_model_path resolved "
            "(absent path or missing file) — QSTS cannot run without a path-backed model.",
            feeder_input_kind=feeder.input_kind,
            generated_input=feeder.generated_input,
        )

    if feeder.input_kind is None:
        raise ValueError(
            "grid.qsts.enabled resolved an existing feeder_model_path but "
            "grid.qsts.input_kind is missing. A filesystem path is not provenance; "
            "declare utility_observed_model, engineer_prepared_site_model, "
            "synthetic_placeholder, or test_fixture."
        )

    cap = export_cap_mw if export_cap_mw is not None else _export_cap_from_grid(grid)

    # A classified, path-backed, enabled study. When the caller injected the QSTS profiles
    # (tests / a pre-solved horizon), account them directly. Otherwise run the OpenDSS QSTS
    # solve to produce them. The solve is the ONLY [grid]-extra path here.
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
            feeder_path=str(feeder.source),
            timestep_hours=timestep_hours,
        )

    limitations: tuple[str, ...] = ()
    if feeder.generated_input:
        limitations = (
            "Synthetic/test feeder input; result exercises software only.",
            "Not the CEB Kalpitiya/Puttalam feeder and not site-representative.",
            "Not engineering-validated, utility-accepted, bankable, or canonical.",
        )
        if feeder.source_manifest_sha256 is not None:
            limitations += (
                "Package manifest verified against an externally pinned SHA-256; this "
                "authenticates the synthetic package identity but does not upgrade its "
                "evidence grade.",
            )

    return split_curtailment(
        generation_mwh=gen,
        export_cap_mw=float(cap),
        grid_instructed_mwh=instructed,
        timestep_hours=timestep_hours,
        bess_grid=_bess_block(grid),
        reference_year=reference_year,
        feeder_source=str(feeder.source),
        feeder_input_kind=feeder.input_kind,
        generated_input=feeder.generated_input,
        observed_network_data=feeder.observed_network_data,
        site_representative=feeder.site_representative,
        canonical_finance_eligible=feeder.canonical_finance_eligible,
        source_manifest_sha256=feeder.source_manifest_sha256,
        limitations=limitations,
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
    """Run OpenDSSDirect over the declared path; evidence grade stays in ``FeederInput``.

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
        load-flow-feasibility value-add); the pure split derives self-curtailment from it
        vs the cap.
      * ``grid_instructed_mwh`` — the committed deemed-paid schedule (or zeros), passed
        straight through — NOT derived from a monitor heuristic.

    A proper upstream-feeder-limit → operator-instruction model (mapping a monitored thermal
    / voltage breach to a dispatch instruction WITHOUT conflating it with the plant's own
    export-cap self-shed) is a follow-up study, not this dolphin.

    This is the ONLY function that touches ``opendssdirect``. It is reached for an enabled,
    explicitly classified, path-backed input; this can include a synthetic/test diagnostic
    path. Evidence grade remains in the typed result and generated/test output is refused by
    canonical finance. The pathless built-in demo never reaches here.
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
    "FeederInput",
    "SYNTHETIC_FEEDER_SOURCE",
    "NO_FEEDER_SOURCE",
    "split_curtailment",
    "run_qsts_curtailment",
]
