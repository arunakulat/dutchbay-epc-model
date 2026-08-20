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
inert / NOT-RUN :class:`analytics.contracts_v14.CurtailmentShareResult` only for an
explicitly non-running state:

  * ``grid.qsts.enabled`` is not True (default-off gate) → inert;
  * the pathless built-in ``"synthetic_demo"`` is selected → inert;
  * a diagnostic ``test_fixture`` path is absent → inert.

An enabled controlled package with a missing path or identity fails closed. Utility/site
inputs additionally require an externally pinned evidence manifest that binds the feeder,
generation profile, operator-instruction schedule, export cap, timestep, and every payload.
Accepted real/site and governed synthetic payloads are executed from private immutable
snapshots so a source mutation after verification cannot change the solve.

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

import hashlib
import math
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterator, Mapping, Sequence, TypeGuard

from analytics.contracts_v14 import (
    CANONICAL_FEEDER_INPUT_KINDS,
    FEEDER_INPUT_KINDS,
    QSTS_CONTROLLED_OUTPUT_CLASS,
    QSTS_RUN_MANIFEST_SCHEMA,
    QSTS_SYNTHETIC_OUTPUT_CLASS,
    SYNTHETIC_FEEDER_INPUT_KINDS,
    SYNTHETIC_PROCESS_PROVENANCE_WARNING,
    CurtailmentShareResult,
    QSTSRunManifest,
    QSTSSolveTelemetry,
)
from analytics.grid.capabilities.bess_soc import bess_soc_state, split_reserves
from analytics.grid.qsts_evidence import (
    QSTSEvidenceError,
    VerifiedQSTSPayload,
    verify_qsts_evidence_package,
)

#: The feeder-source token stamped when the caller asked for the built-in synthetic/demo
#: feeder rather than a path-backed model file. It is an inert smoke-test marker only.
SYNTHETIC_FEEDER_SOURCE = "synthetic_demo"

#: The feeder-source token stamped when no feeder was resolved at all (default-off / absent).
NO_FEEDER_SOURCE = "none"

#: Fixed package-manifest location relative to the governed synthetic ``feeder/Master.dss``.
SYNTHETIC_PACKAGE_MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True)
class VerifiedRuntimeInputs:
    """Manifest-bound values and bytes accepted for one immutable QSTS runtime."""

    package_id: str
    master_relative_path: str
    payloads: tuple[VerifiedQSTSPayload, ...]
    generation_profile_mw: tuple[float, ...]
    export_cap_mw: float
    grid_instructed_profile_mw: tuple[float, ...] | None = None
    timestep_hours: float | None = None


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
    evidence_manifest_sha256: str | None = None
    qsts_run_manifest: QSTSRunManifest | None = None
    verified_runtime: VerifiedRuntimeInputs | None = None

    def __post_init__(self) -> None:
        """Prevent a verified-manifest identity from being attached to another kind."""

        if self.verified_runtime is not None and self.qsts_run_manifest is None:
            raise ValueError(
                "FeederInput.verified_runtime requires a typed QSTS run manifest."
            )
        if self.source_manifest_sha256 is not None:
            _require_sha256(
                self.source_manifest_sha256, "FeederInput.source_manifest_sha256"
            )
            if (
                self.input_kind != "synthetic_placeholder"
                or self.generated_input is not True
                or self.evidence_manifest_sha256 is not None
            ):
                raise ValueError(
                    "FeederInput.source_manifest_sha256 is reserved for a generated "
                    "synthetic_placeholder and cannot coexist with real/site evidence."
                )
        if self.evidence_manifest_sha256 is not None:
            _require_sha256(
                self.evidence_manifest_sha256,
                "FeederInput.evidence_manifest_sha256",
            )
            if (
                self.input_kind not in CANONICAL_FEEDER_INPUT_KINDS
                or self.generated_input is not False
                or self.source_manifest_sha256 is not None
            ):
                raise ValueError(
                    "FeederInput.evidence_manifest_sha256 is reserved for a non-generated "
                    "utility/site package and cannot coexist with synthetic evidence."
                )

    @property
    def can_solve(self) -> bool:
        return self.source is not None and self.model_exists


class QSTSConvergenceError(RuntimeError):
    """Raised after a live QSTS horizon contains any non-converged solve."""

    def __init__(self, telemetry: QSTSSolveTelemetry) -> None:
        self.telemetry = telemetry
        super().__init__(
            "QSTS refused non-converged horizon: "
            f"{telemetry.nonconverged_steps}/{telemetry.attempted_steps} steps failed; "
            f"first={telemetry.first_nonconverged_step}, "
            f"last={telemetry.last_nonconverged_step}."
        )


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
) -> tuple[str, str, VerifiedRuntimeInputs]:
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
        raise QSTSEvidenceError(
            "Runtime use of a synthetic_placeholder requires a package whose detached "
            "OpenDSS compile check passed. Test-only compile-disabled packages are not "
            "runtime inputs."
        )
    payloads: list[VerifiedQSTSPayload] = []
    for relative_path in sorted(package.file_sha256):
        payload_path = package.output_root.joinpath(*relative_path.split("/"))
        content = payload_path.read_bytes()
        actual_sha256 = hashlib.sha256(content).hexdigest()
        expected_sha256 = package.file_sha256[relative_path]
        if actual_sha256 != expected_sha256:
            raise QSTSEvidenceError(
                "Synthetic QSTS payload changed after package verification: "
                f"{relative_path!r} expected {expected_sha256}, got {actual_sha256}."
            )
        payloads.append(VerifiedQSTSPayload(relative_path, actual_sha256, content))
    try:
        master_relative_path = package.master_path.relative_to(
            package.output_root
        ).as_posix()
    except ValueError as exc:  # defence in depth; B1 already proves package containment
        raise QSTSEvidenceError(
            "Verified synthetic feeder master escaped its accepted package root."
        ) from exc
    return (
        str(package.master_path),
        package.manifest_sha256,
        VerifiedRuntimeInputs(
            package_id=f"synthetic-placeholder-{package.manifest_sha256[:16]}",
            master_relative_path=master_relative_path,
            payloads=tuple(payloads),
            generation_profile_mw=package.generation_profile_mw,
            export_cap_mw=package.export_cap_mw,
        ),
    )


def _qsts_wiring_state(qsts: Mapping[str, Any]) -> tuple[str | None, bool, bool]:
    """Return the strictly typed finance mode/enabled/eligibility declarations."""

    wiring = qsts.get("finance_wiring")
    if wiring is None:
        return None, False, False
    if not isinstance(wiring, Mapping):
        raise QSTSEvidenceError(
            "grid.qsts.finance_wiring must be a mapping when declared."
        )
    mode = wiring.get("mode")
    if mode is not None and (
        not isinstance(mode, str)
        or mode not in {"canonical", "synthetic_counterfactual"}
    ):
        raise QSTSEvidenceError(
            "grid.qsts.finance_wiring.mode must be 'canonical' or "
            f"'synthetic_counterfactual', got {mode!r}."
        )
    enabled = wiring.get("enabled", False)
    eligible = wiring.get("canonical_eligible", False)
    if type(enabled) is not bool or type(eligible) is not bool:  # noqa: E721
        raise QSTSEvidenceError(
            "grid.qsts.finance_wiring.enabled and canonical_eligible must be literal "
            "booleans when declared."
        )
    return mode, enabled, eligible


def _build_qsts_run_manifest(
    *,
    qsts: Mapping[str, Any],
    input_kind: str,
    runtime: VerifiedRuntimeInputs,
    source_manifest_sha256: str | None,
    evidence_manifest_sha256: str | None,
) -> QSTSRunManifest:
    """Build the concise CCCDIR receipt from identities accepted at runtime."""

    mode, wiring_enabled, canonical_eligible = _qsts_wiring_state(qsts)
    generated = input_kind in SYNTHETIC_FEEDER_INPUT_KINDS
    if generated and wiring_enabled:
        raise QSTSEvidenceError(
            "Synthetic/test QSTS inputs cannot enable canonical finance wiring."
        )
    return QSTSRunManifest(
        schema=QSTS_RUN_MANIFEST_SCHEMA,
        package_id=runtime.package_id,
        input_kind=input_kind,
        output_class=(
            QSTS_SYNTHETIC_OUTPUT_CLASS if generated else QSTS_CONTROLLED_OUTPUT_CLASS
        ),
        payload_sha256=tuple(
            (payload.relative_path, payload.sha256) for payload in runtime.payloads
        ),
        source_manifest_sha256=source_manifest_sha256,
        evidence_manifest_sha256=evidence_manifest_sha256,
        finance_wiring_mode=mode,
        finance_wiring_enabled=wiring_enabled,
        canonical_finance_eligible=(
            False if generated else canonical_eligible and mode == "canonical"
        ),
        required_warning=(SYNTHETIC_PROCESS_PROVENANCE_WARNING if generated else None),
    )


@contextmanager
def _materialized_verified_feeder(
    runtime: VerifiedRuntimeInputs,
) -> Iterator[str]:
    """Yield a private feeder snapshot assembled only from digest-accepted bytes."""

    with TemporaryDirectory(prefix="dutchbay-qsts-verified-") as directory:
        root = Path(directory)
        for payload in runtime.payloads:
            target = root.joinpath(*payload.relative_path.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload.content)
            if hashlib.sha256(target.read_bytes()).hexdigest() != payload.sha256:
                raise QSTSEvidenceError(
                    f"Private QSTS snapshot write failed integrity for "
                    f"{payload.relative_path!r}."
                )
        master = root.joinpath(*runtime.master_relative_path.split("/"))
        if not master.is_file():
            raise QSTSEvidenceError(
                "Verified QSTS runtime does not contain its declared feeder master "
                f"{runtime.master_relative_path!r}."
            )
        yield str(master)


def _require_profile(
    values: Any, field: str, *, length: int | None = None, unit: str = "MWh"
) -> list[float]:
    """Validate a per-timestep profile: a non-empty sequence of finite floats >= 0.

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
            f"per-timestep {unit} values (>= 0), got {values!r}."
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
                f"number >= 0 ({unit}), got {v!r}."
            )
        out.append(float(v))
    return out


def _require_verified_profile_match(
    values: Any,
    expected_mw: tuple[float, ...],
    field: str,
    *,
    unit: str,
    mw_to_value: float = 1.0,
) -> list[float]:
    """Return verifier-derived values after rejecting a substituted runtime profile.

    Args:
        values: Caller/config profile to compare with the verified package profile.
        expected_mw: Immutable MW profile returned by the package verifier.
        field: Fully qualified input field for actionable errors.
        unit: Unit of ``values`` and the returned profile.
        mw_to_value: Multiplier from the verified MW values to ``unit``.

    Returns:
        A fresh list derived from ``expected_mw`` rather than the caller's sequence.

    Raises:
        ValueError: If length, numeric validity, or any value differs from the verified
            package profile.
    """

    expected = [float(value) * mw_to_value for value in expected_mw]
    supplied = _require_profile(values, field, length=len(expected), unit=unit)
    for index, (actual, verified) in enumerate(zip(supplied, expected, strict=True)):
        if abs(actual - verified) > _MWH_TOL:
            raise ValueError(
                f"{field} must match the manifest-verified QSTS package; first "
                f"mismatch at index {index}: got {actual}, expected {verified} {unit}."
            )
    return expected


def _require_verified_export_cap_match(
    value: Any, expected_mw: float, field: str
) -> float:
    """Return the verified export cap after rejecting a substituted MW value."""

    supplied = _require_positive(value, field)
    if abs(supplied - expected_mw) > _MWH_TOL:
        raise ValueError(
            f"{field} must match the manifest-verified QSTS package export cap: "
            f"got {supplied}, expected {expected_mw} MW."
        )
    return expected_mw


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
    evidence_manifest_sha256: str | None = None,
    qsts_run_manifest: QSTSRunManifest | None = None,
    qsts_solve_telemetry: QSTSSolveTelemetry | None = None,
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
        evidence_manifest_sha256: externally pinned real/site evidence-manifest identity.
        qsts_run_manifest: typed receipt binding the accepted payloads and output class.

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
        evidence_manifest_sha256=evidence_manifest_sha256,
        qsts_run_manifest=qsts_run_manifest,
        qsts_solve_telemetry=qsts_solve_telemetry,
        solver_converged_all_steps=(
            qsts_solve_telemetry.nonconverged_steps == 0
            if qsts_solve_telemetry is not None
            else None
        ),
        n_nonconverged_steps=(
            qsts_solve_telemetry.nonconverged_steps
            if qsts_solve_telemetry is not None
            else None
        ),
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

    Used for default-off, an absent diagnostic test fixture, and the pathless built-in demo.
    Missing governed synthetic or real/site evidence fails closed instead. A path-backed
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
    only a manifest-verified site/utility kind can ever be marked canonical-finance eligible.
    A path-backed ``synthetic_placeholder`` binds the external B1 manifest digest; a
    utility/site package binds its external #1072 evidence digest. Both retain accepted
    payload bytes for immutable execution before reaching accounting.
    """
    qsts = grid.get("qsts")
    if not isinstance(qsts, Mapping):
        return FeederInput(
            source=None,
            input_kind=None,
            model_exists=False,
            generated_input=False,
            observed_network_data=False,
            site_representative=False,
            canonical_finance_eligible=False,
        )

    raw_kind = qsts.get("input_kind")
    input_kind = raw_kind if isinstance(raw_kind, str) else None
    if input_kind not in FEEDER_INPUT_KINDS:
        allowed = ", ".join(sorted(FEEDER_INPUT_KINDS))
        raise QSTSEvidenceError(
            "grid.qsts.input_kind must be one of "
            f"[{allowed}], got {raw_kind!r}. A filesystem path is not provenance."
        )

    raw_source_sha256 = qsts.get("source_manifest_sha256")
    source_manifest_sha256 = (
        _require_sha256(raw_source_sha256, "grid.qsts.source_manifest_sha256")
        if raw_source_sha256 is not None
        else None
    )
    raw_evidence_path = qsts.get("evidence_manifest_path")
    evidence_manifest_path = (
        raw_evidence_path.strip()
        if isinstance(raw_evidence_path, str) and raw_evidence_path.strip()
        else None
    )
    raw_evidence_sha256 = qsts.get("evidence_manifest_sha256")
    evidence_manifest_sha256 = (
        _require_sha256(raw_evidence_sha256, "grid.qsts.evidence_manifest_sha256")
        if raw_evidence_sha256 is not None
        else None
    )

    mode, wiring_enabled, requested_canonical = _qsts_wiring_state(qsts)
    generated = input_kind in SYNTHETIC_FEEDER_INPUT_KINDS
    if requested_canonical and input_kind not in CANONICAL_FEEDER_INPUT_KINDS:
        raise QSTSEvidenceError(
            "grid.qsts.finance_wiring.canonical_eligible=true is permitted only for "
            "verified utility/site inputs."
        )
    if mode == "canonical" and generated:
        raise QSTSEvidenceError(
            "grid.qsts.finance_wiring.mode='canonical' refuses synthetic/test inputs."
        )
    if mode == "synthetic_counterfactual" and not generated:
        raise QSTSEvidenceError(
            "grid.qsts.finance_wiring.mode='synthetic_counterfactual' requires a "
            "synthetic/test input."
        )
    if wiring_enabled and generated:
        raise QSTSEvidenceError(
            "Synthetic/test QSTS inputs cannot enable canonical cashflow wiring."
        )
    if wiring_enabled and (mode != "canonical" or requested_canonical is not True):
        raise QSTSEvidenceError(
            "Enabled utility/site QSTS finance wiring requires mode='canonical' and "
            "canonical_eligible=true."
        )

    use_synthetic_demo = qsts.get("use_synthetic_demo")
    if use_synthetic_demo is not None and type(use_synthetic_demo) is not bool:
        raise QSTSEvidenceError(
            "grid.qsts.use_synthetic_demo must be a literal boolean when declared."
        )
    if use_synthetic_demo is True:
        if input_kind not in SYNTHETIC_FEEDER_INPUT_KINDS:
            raise QSTSEvidenceError(
                "grid.qsts.use_synthetic_demo=true requires synthetic/test input_kind."
            )
        if any(
            identity is not None
            for identity in (
                source_manifest_sha256,
                evidence_manifest_path,
                evidence_manifest_sha256,
            )
        ):
            raise QSTSEvidenceError(
                "The pathless synthetic demo has no package identity; remove source and "
                "evidence manifest fields."
            )
        demo_path = qsts.get("feeder_model_path")
        if demo_path is not None and demo_path != "":
            raise QSTSEvidenceError(
                "grid.qsts.use_synthetic_demo=true is ambiguous with feeder_model_path."
            )
        return FeederInput(
            source=SYNTHETIC_FEEDER_SOURCE,
            input_kind=input_kind,
            model_exists=False,
            generated_input=True,
            observed_network_data=False,
            site_representative=False,
            canonical_finance_eligible=False,
        )

    if input_kind == "synthetic_placeholder":
        if source_manifest_sha256 is None:
            raise QSTSEvidenceError(
                "An enabled path-backed synthetic_placeholder requires an externally "
                "pinned grid.qsts.source_manifest_sha256."
            )
        if evidence_manifest_path is not None or evidence_manifest_sha256 is not None:
            raise QSTSEvidenceError(
                "Synthetic QSTS inputs cannot carry or borrow a real/site evidence "
                "manifest identity."
            )
    elif input_kind in CANONICAL_FEEDER_INPUT_KINDS:
        if source_manifest_sha256 is not None:
            raise QSTSEvidenceError(
                "Utility/site QSTS inputs cannot carry a synthetic source manifest "
                "identity."
            )
        if evidence_manifest_path is None or evidence_manifest_sha256 is None:
            raise QSTSEvidenceError(
                "An enabled utility/site QSTS input requires both "
                "grid.qsts.evidence_manifest_path and an externally pinned "
                "grid.qsts.evidence_manifest_sha256. A YAML label and feeder path are "
                "not authenticated evidence."
            )
    elif (
        source_manifest_sha256 is not None
        or evidence_manifest_path is not None
        or evidence_manifest_sha256 is not None
    ):
        raise QSTSEvidenceError(
            "test_fixture inputs cannot carry synthetic production or real/site evidence "
            "manifest identities."
        )

    path = qsts.get("feeder_model_path")
    if not isinstance(path, str) or not path.strip():
        raise QSTSEvidenceError(
            "grid.qsts.enabled=true requires a non-empty feeder_model_path."
        )
    normalized_path = path.strip()
    model_path = Path(normalized_path)

    if input_kind == "synthetic_placeholder":
        if not model_path.is_file():
            raise QSTSEvidenceError(
                f"Synthetic QSTS feeder model is missing or not a file: {model_path}."
            )
        assert source_manifest_sha256 is not None
        resolved_source, verified_source_sha256, runtime = (
            _verify_synthetic_feeder_runtime_package(
                master_path=model_path,
                expected_manifest_sha256=source_manifest_sha256,
            )
        )
        receipt = _build_qsts_run_manifest(
            qsts=qsts,
            input_kind=input_kind,
            runtime=runtime,
            source_manifest_sha256=verified_source_sha256,
            evidence_manifest_sha256=None,
        )
        return FeederInput(
            source=resolved_source,
            input_kind=input_kind,
            model_exists=True,
            generated_input=True,
            observed_network_data=False,
            site_representative=False,
            canonical_finance_eligible=False,
            source_manifest_sha256=verified_source_sha256,
            qsts_run_manifest=receipt,
            verified_runtime=runtime,
        )

    if input_kind in CANONICAL_FEEDER_INPUT_KINDS:
        assert evidence_manifest_path is not None
        assert evidence_manifest_sha256 is not None
        package = verify_qsts_evidence_package(
            manifest_path=evidence_manifest_path,
            expected_manifest_sha256=evidence_manifest_sha256,
            expected_input_kind=input_kind,
            configured_master_path=model_path,
        )
        runtime = VerifiedRuntimeInputs(
            package_id=package.package_id,
            master_relative_path=package.master_relative_path,
            payloads=package.payloads,
            generation_profile_mw=package.generation_profile_mw,
            export_cap_mw=package.export_cap_mw,
            grid_instructed_profile_mw=package.grid_instructed_profile_mw,
            timestep_hours=package.timestep_hours,
        )
        receipt = _build_qsts_run_manifest(
            qsts=qsts,
            input_kind=input_kind,
            runtime=runtime,
            source_manifest_sha256=None,
            evidence_manifest_sha256=package.manifest_sha256,
        )
        return FeederInput(
            source=normalized_path,
            input_kind=input_kind,
            model_exists=True,
            generated_input=False,
            observed_network_data=package.observed_network_data,
            site_representative=package.site_representative,
            canonical_finance_eligible=receipt.canonical_finance_eligible,
            evidence_manifest_sha256=package.manifest_sha256,
            qsts_run_manifest=receipt,
            verified_runtime=runtime,
        )

    if not model_path.is_file():
        return FeederInput(
            source=None,
            input_kind=input_kind,
            model_exists=False,
            generated_input=True,
            observed_network_data=False,
            site_representative=False,
            canonical_finance_eligible=False,
        )
    return FeederInput(
        source=normalized_path,
        input_kind=input_kind,
        model_exists=True,
        generated_input=True,
        observed_network_data=False,
        site_representative=False,
        canonical_finance_eligible=False,
    )


def run_qsts_curtailment(
    config: Mapping[str, Any],
    *,
    generation_mwh: Sequence[float] | None = None,
    grid_instructed_mwh: Sequence[float] | None = None,
    export_cap_mw: float | None = None,
    timestep_hours: float | None = None,
    reference_year: int | None = None,
) -> CurtailmentShareResult:
    """Run QSTS with explicit feeder evidence classification and finance eligibility.

    The single entry seam. It applies the gating BEFORE any solve, so the OpenDSS path is
    reached only for an enabled study with an existing path and explicit input kind:

      * ``grid.qsts.enabled`` not True (default-off) → inert NOT-RUN result;
      * a missing controlled feeder path/identity → fail-closed evidence error;
      * an absent diagnostic ``test_fixture`` path → inert;
      * the pathless built-in demo (``grid.qsts.use_synthetic_demo: true``) → inert;
      * a path-backed synthetic/test input may run diagnostically, but its result remains
        generated, non-site-representative, nonbankable, and canonical-finance-ineligible.

    Only when a classified path is resolved and the study is enabled does it reach the
    OpenDSS QSTS solve (behind :func:`_require_opendss`), which produces the per-timestep gross
    generation + upstream grid-instruction profiles the pure :func:`split_curtailment`
    consumes. Tests may inject those profiles directly via ``generation_mwh`` /
    ``grid_instructed_mwh`` (skipping the solve) to exercise the accounting grid-free. For
    a manifest-verified package, runtime values are instead bound to that package: supplied
    config or caller overrides must match exactly. Real/site packages additionally bind the
    operator schedule and timestep.

    Args:
        config: the full scenario config (or its top-level ``grid`` block).
        generation_mwh / grid_instructed_mwh / export_cap_mw: optional pre-computed QSTS
            profiles + export cap (tests inject these to drive the pure accounting without
            an OpenDSS solve). When omitted on a path-backed enabled study, the OpenDSS solve
            supplies them. For a manifest-verified package, generation and export-cap
            values must match; real/site packages also own schedule and timestep.
        timestep_hours: hours per QSTS timestep. A verified real/site manifest owns this
            value; an override must match it. Unverified test fixtures default to 1.0.
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

    verified_runtime = feeder.verified_runtime
    if verified_runtime is not None and verified_runtime.timestep_hours is not None:
        qsts_timestep = qsts.get("timestep_hours")
        for supplied, field in (
            (qsts_timestep, "grid.qsts.timestep_hours"),
            (timestep_hours, "timestep_hours override"),
        ):
            if (
                supplied is not None
                and abs(
                    _require_positive(supplied, field) - verified_runtime.timestep_hours
                )
                > _MWH_TOL
            ):
                raise QSTSEvidenceError(
                    f"{field} must match the manifest-verified QSTS timestep: got "
                    f"{supplied}, expected {verified_runtime.timestep_hours} hours."
                )
        step_hours = verified_runtime.timestep_hours
    else:
        step_hours = _require_positive(
            1.0 if timestep_hours is None else timestep_hours, "timestep_hours"
        )

    if verified_runtime is not None:
        qsts_profile = qsts.get("generation_profile_mw")
        if qsts_profile is not None:
            _require_verified_profile_match(
                qsts_profile,
                verified_runtime.generation_profile_mw,
                "grid.qsts.generation_profile_mw",
                unit="MW",
            )
        verified_instructed = verified_runtime.grid_instructed_profile_mw
        qsts_instructed = qsts.get("grid_instructed_profile_mw")
        if verified_instructed is not None and qsts_instructed is not None:
            _require_verified_profile_match(
                qsts_instructed,
                verified_instructed,
                "grid.qsts.grid_instructed_profile_mw",
                unit="MW",
            )

        qsts_cap = qsts.get("export_cap_mw")
        configured_cap = qsts_cap if qsts_cap is not None else grid.get("export_cap_mw")
        if configured_cap is not None:
            _require_verified_export_cap_match(
                configured_cap,
                verified_runtime.export_cap_mw,
                "grid.qsts.export_cap_mw (or grid.export_cap_mw)",
            )
        if export_cap_mw is not None:
            _require_verified_export_cap_match(
                export_cap_mw,
                verified_runtime.export_cap_mw,
                "export_cap_mw override",
            )
        cap = verified_runtime.export_cap_mw
    else:
        cap = (
            export_cap_mw if export_cap_mw is not None else _export_cap_from_grid(grid)
        )

    # A classified, path-backed, enabled study. When the caller injected the QSTS profiles
    # (tests / a pre-solved horizon), account them directly. Otherwise run the OpenDSS QSTS
    # solve to produce them. The solve is the ONLY [grid]-extra path here.
    gen: Sequence[float]
    instructed: Sequence[float]
    solve_telemetry: QSTSSolveTelemetry | None = None
    if generation_mwh is not None:
        if verified_runtime is not None:
            gen = _require_verified_profile_match(
                generation_mwh,
                verified_runtime.generation_profile_mw,
                "generation_mwh override",
                unit="MWh",
                mw_to_value=step_hours,
            )
        else:
            gen = generation_mwh
        if (
            verified_runtime is not None
            and verified_runtime.grid_instructed_profile_mw is not None
        ):
            if grid_instructed_mwh is None:
                instructed = [
                    value * step_hours
                    for value in verified_runtime.grid_instructed_profile_mw
                ]
            else:
                instructed = _require_verified_profile_match(
                    grid_instructed_mwh,
                    verified_runtime.grid_instructed_profile_mw,
                    "grid_instructed_mwh override",
                    unit="MWh",
                    mw_to_value=step_hours,
                )
        else:
            instructed = (
                grid_instructed_mwh
                if grid_instructed_mwh is not None
                else [0.0] * len(generation_mwh)
            )
    else:  # pragma: no cover - requires [grid] extra
        if verified_runtime is not None:
            with _materialized_verified_feeder(verified_runtime) as snapshot_feeder:
                gen, instructed, solve_telemetry = _solve_qsts(
                    grid,
                    feeder_path=snapshot_feeder,
                    timestep_hours=step_hours,
                    generation_profile_mw=verified_runtime.generation_profile_mw,
                    grid_instructed_profile_mw=(
                        verified_runtime.grid_instructed_profile_mw
                    ),
                )
        else:
            gen, instructed, solve_telemetry = _solve_qsts(
                grid,
                feeder_path=str(feeder.source),
                timestep_hours=step_hours,
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
                SYNTHETIC_PROCESS_PROVENANCE_WARNING,
            )
    elif feeder.evidence_manifest_sha256 is not None:
        limitations = (
            "Feeder, generation profile, operator-instruction schedule, export cap, "
            "timestep, and referenced payloads were bound to an externally pinned "
            "evidence manifest and executed from an immutable private snapshot.",
            "Controlled runtime identity does not make the result utility-accepted, "
            "bankable, lender-ready, board-approved, or release-approved.",
        )

    return split_curtailment(
        generation_mwh=gen,
        export_cap_mw=float(cap),
        grid_instructed_mwh=instructed,
        timestep_hours=step_hours,
        bess_grid=_bess_block(grid),
        reference_year=reference_year,
        feeder_source=str(feeder.source),
        feeder_input_kind=feeder.input_kind,
        generated_input=feeder.generated_input,
        observed_network_data=feeder.observed_network_data,
        site_representative=feeder.site_representative,
        canonical_finance_eligible=feeder.canonical_finance_eligible,
        source_manifest_sha256=feeder.source_manifest_sha256,
        evidence_manifest_sha256=feeder.evidence_manifest_sha256,
        qsts_run_manifest=feeder.qsts_run_manifest,
        qsts_solve_telemetry=solve_telemetry,
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
    generation_profile_mw: Sequence[float] | None = None,
    grid_instructed_profile_mw: Sequence[float] | None = None,
) -> tuple[list[float], list[float], QSTSSolveTelemetry]:
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
    dss.Basic.ClearAll()
    dss.Command(f'Redirect "{feeder_path}"')
    _raise_on_dss_error(dss, "feeder Redirect")
    dss.Solution.Mode(1)  # daily/QSTS time-series mode
    dss.Solution.StepSize(timestep_hours * 3600.0)

    profiles = (
        _require_profile(
            generation_profile_mw,
            "manifest-verified generation_profile_mw",
            unit="MW",
        )
        if generation_profile_mw is not None
        else _resolve_generation_profiles(grid)
    )
    instructed_profile = (
        _require_profile(
            grid_instructed_profile_mw,
            "manifest-verified grid_instructed_profile_mw",
            length=len(profiles),
            unit="MW",
        )
        if grid_instructed_profile_mw is not None
        else _resolve_grid_instructed_profile_mw(grid, n_steps=len(profiles))
    )
    generation: list[float] = []
    instructed: list[float] = []
    monitoring = _resolve_execution_monitoring(grid)
    converged_steps = 0
    failing_steps: list[int] = []
    voltage_violation_steps = 0
    thermal_violation_steps = 0
    observed_voltage_min = math.inf
    observed_voltage_max = -math.inf
    observed_max_pct_norm = 0.0
    generator_activation_steps = 0
    generator_setpoint_mismatch_steps = 0
    generator_name = _resolve_generator_name(grid)
    for t, p_mw in enumerate(profiles):
        activated, setpoint_matches = _inject_poc_power(
            dss, p_mw, generator_name=generator_name
        )
        generator_activation_steps += int(activated)
        generator_setpoint_mismatch_steps += int(not setpoint_matches)
        dss.Solution.Number(1)
        dss.Solution.Solve()
        _raise_on_dss_error(dss, f"QSTS timestep {t}")
        step_converged = bool(dss.Solution.Converged())
        if step_converged:
            converged_steps += 1
        else:
            failing_steps.append(t)
        if monitoring is not None and step_converged:
            voltage_values = [float(value) for value in dss.Circuit.AllBusMagPu()]
            thermal_values = [float(value) for value in dss.PDElements.AllPctNorm()]
            if (
                not voltage_values
                or any(
                    not math.isfinite(value) or value < 0.0 for value in voltage_values
                )
                or any(
                    not math.isfinite(value) or value < 0.0 for value in thermal_values
                )
            ):
                raise RuntimeError(
                    f"OpenDSS monitoring returned invalid values at step {t}."
                )
            voltage_min = min(voltage_values)
            voltage_max = max(voltage_values)
            max_pct_norm = max(thermal_values, default=0.0)
            observed_voltage_min = min(observed_voltage_min, voltage_min)
            observed_voltage_max = max(observed_voltage_max, voltage_max)
            observed_max_pct_norm = max(observed_max_pct_norm, max_pct_norm)
            if voltage_min < monitoring[0] or voltage_max > monitoring[1]:
                voltage_violation_steps += 1
            if max_pct_norm > monitoring[2]:
                thermal_violation_steps += 1
        generation.append(p_mw * timestep_hours)
        # Deemed-paid is the COMMITTED operator schedule, NOT a monitor heuristic — deriving
        # it from generation-vs-cap here would double-count the plant's own self-curtailment.
        instructed.append(instructed_profile[t] * timestep_hours)
    telemetry = QSTSSolveTelemetry(
        attempted_steps=len(profiles),
        converged_steps=converged_steps,
        nonconverged_steps=len(failing_steps),
        first_nonconverged_step=failing_steps[0] if failing_steps else None,
        last_nonconverged_step=failing_steps[-1] if failing_steps else None,
        monitoring_configured=monitoring is not None,
        voltage_min_limit_pu=monitoring[0] if monitoring is not None else None,
        voltage_max_limit_pu=monitoring[1] if monitoring is not None else None,
        thermal_limit_pct_norm=monitoring[2] if monitoring is not None else None,
        voltage_violation_steps=(
            voltage_violation_steps if monitoring is not None else None
        ),
        thermal_violation_steps=(
            thermal_violation_steps if monitoring is not None else None
        ),
        generator_activation_steps=generator_activation_steps,
        generator_setpoint_mismatch_steps=generator_setpoint_mismatch_steps,
        observed_voltage_min_pu=(
            observed_voltage_min
            if monitoring is not None and converged_steps > 0
            else None
        ),
        observed_voltage_max_pu=(
            observed_voltage_max
            if monitoring is not None and converged_steps > 0
            else None
        ),
        observed_max_pct_norm=(
            observed_max_pct_norm
            if monitoring is not None and converged_steps > 0
            else None
        ),
    )
    if failing_steps:
        raise QSTSConvergenceError(telemetry)
    return generation, instructed, telemetry


def _resolve_execution_monitoring(
    grid: Mapping[str, Any],
) -> tuple[float, float, float] | None:
    """Return strict voltage/thermal limits when whole-horizon monitoring is enabled."""

    qsts = grid.get("qsts")
    raw = qsts.get("execution_monitoring") if isinstance(qsts, Mapping) else None
    if raw is None:
        return None
    if not isinstance(raw, Mapping) or set(raw) != {
        "voltage_min_pu",
        "voltage_max_pu",
        "thermal_limit_pct_norm",
    }:
        raise ValueError(
            "grid.qsts.execution_monitoring requires exactly voltage_min_pu, "
            "voltage_max_pu, and thermal_limit_pct_norm."
        )
    low = _require_positive(
        raw["voltage_min_pu"], "execution_monitoring.voltage_min_pu"
    )
    high = _require_positive(
        raw["voltage_max_pu"], "execution_monitoring.voltage_max_pu"
    )
    thermal = _require_positive(
        raw["thermal_limit_pct_norm"], "execution_monitoring.thermal_limit_pct_norm"
    )
    if low >= high:
        raise ValueError(
            "execution_monitoring.voltage_min_pu must be below voltage_max_pu."
        )
    return low, high, thermal


def _resolve_generator_name(grid: Mapping[str, Any]) -> str | None:
    """Return an optional controlled generator name for explicit activation."""

    qsts = grid.get("qsts")
    raw = qsts.get("generator_name") if isinstance(qsts, Mapping) else None
    if raw is None:
        return None
    if (
        not isinstance(raw, str)
        or not raw.strip()
        or any(character.isspace() for character in raw)
    ):
        raise ValueError("grid.qsts.generator_name must be a non-empty token.")
    return raw


def _raise_on_dss_error(dss: Any, operation: str) -> None:
    """Fail loudly when the OpenDSS C-API reports an execution error."""

    error_number = int(dss.Error.Number())
    if error_number:
        description = str(dss.Error.Description()).strip()
        raise RuntimeError(
            f"OpenDSS error {error_number} after {operation}: {description or 'unknown error'}"
        )


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
    return _require_profile(profile, "grid.qsts.generation_profile_mw", unit="MW")


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
        profile,
        "grid.qsts.grid_instructed_profile_mw",
        length=n_steps,
        unit="MW",
    )


def _inject_poc_power(  # pragma: no cover - requires [grid] extra
    dss: Any, p_mw: float, *, generator_name: str | None = None
) -> tuple[bool, bool]:
    """Activate and set the POC generator, returning activation/read-back status."""

    activated = False
    if generator_name is not None:
        dss.Generators.Name(generator_name)
        activated = str(dss.Generators.Name()).casefold() == generator_name.casefold()
        if not activated:
            raise RuntimeError(
                f"OpenDSS did not activate controlled generator {generator_name!r}."
            )
    requested_kw = p_mw * 1000.0
    dss.Generators.kW(requested_kw)
    actual_kw = float(dss.Generators.kW())
    matches = math.isclose(actual_kw, requested_kw, rel_tol=0.0, abs_tol=1.0e-6)
    if not matches:
        raise RuntimeError(
            "OpenDSS generator setpoint read-back mismatch: "
            f"requested {requested_kw} kW, got {actual_kw} kW."
        )
    return activated, matches


__all__ = [
    "FeederInput",
    "SYNTHETIC_FEEDER_SOURCE",
    "NO_FEEDER_SOURCE",
    "split_curtailment",
    "run_qsts_curtailment",
    "QSTSConvergenceError",
]
