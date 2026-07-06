"""Single source of truth for GRID interconnection TYPE discriminators (CCCDIR, #873).

The design-stage grid-strength screen (:mod:`analytics.grid`) classifies a technology's
converter interface as either **grid-following (GFL)** or **grid-forming (GFM)**. GFL
converters track an external grid voltage phasor (a PLL) and need a stiff grid (high SCR);
GFM converters synthesise their own voltage source and can operate into a weak grid. This
distinction drives the SCR-band → GFL/GFM recommendation the screen emits, and the
grid-forming clause a lender/utility (CEB/NSCC) may require at a low SCR@POC.

Mirrors :mod:`finance.tech_types` deliberately (the ``_norm`` / ``is_*`` pattern + an
``allow_unvalidated_*`` opt-in gate), so the grid layer reuses one proven convention.

Provenance / bankability gate
-----------------------------
A committed grid block often carries a Thevenin source impedance that is a SCREENING
ESTIMATE (a rule-of-thumb SCR at the POC), not a utility-provided fault level from the
CEB/NSCC confidential grid base case. Likewise a per-tech ``grid.converter_type`` may be
an ENUM-ONLY declaration with no committed dynamic model (no ``.dyr``/``params_ref``).
Either path yields an UNVALIDATED grid screen. To ensure a user can never SILENTLY treat
a screening estimate as a bankable input, such paths are gated behind the per-block opt-in
``allow_unvalidated_grid: true`` (exactly as ``allow_unvalidated_flat_cf`` gates the
enum-only flat-CF generation proxy in :mod:`finance.tech_types`). The in-house screen is
NEVER bankable regardless (``GridStrengthResult.bankable is False``); this gate only
governs whether an ESTIMATED / ENUM-ONLY input is allowed to feed it at all.
"""

from __future__ import annotations

from typing import Any

#: Converter topologies that operate as GRID-FOLLOWING (PLL-tracked; need a stiff grid).
GFL_CONVERTER_TYPES: frozenset[str] = frozenset({"gfl", "grid_following"})

#: Converter topologies CAPABLE of GRID-FORMING (voltage-source; tolerate a weak grid).
GFM_CAPABLE_CONVERTER_TYPES: frozenset[str] = frozenset({"gfm", "grid_forming"})

#: All recognised converter-interface topologies (GFL ∪ GFM). A declared
#: ``generation.technologies.<name>.grid.converter_type`` is validated against this set.
CONVERTER_TYPES: frozenset[str] = GFL_CONVERTER_TYPES | GFM_CAPABLE_CONVERTER_TYPES

#: WIND-TURBINE converter topologies (D4b, #876) — a distinct axis from the GFL/GFM
#: control mode above. A ``type4_full_converter`` turbine decouples the machine from the
#: grid through a FULL back-to-back converter, so its reactive (Q) capability is a full
#: ~rectangular PQ box available across the whole active-power range. A ``type3_dfig``
#: (doubly-fed induction generator) converts only the ~30 % rotor slip power, so its Q
#: capability SHRINKS at partial load — the reactive headroom is proportional to the
#: converter's slip-power rating, which falls with active power. Aliases mirror the
#: ``_norm`` convention (spaces/dashes/underscores collapse to the canonical token).
TYPE3_DFIG_CONVERTER_TYPES: frozenset[str] = frozenset(
    {"type3_dfig", "type3", "dfig", "doubly_fed"}
)
TYPE4_FULL_CONVERTER_TYPES: frozenset[str] = frozenset(
    {"type4_full_converter", "type4", "full_converter", "full_scale_converter"}
)

#: All recognised wind-turbine converter topologies (Type-3 ∪ Type-4).
WIND_TURBINE_CONVERTER_TYPES: frozenset[str] = (
    TYPE3_DFIG_CONVERTER_TYPES | TYPE4_FULL_CONVERTER_TYPES
)

#: Generation/storage classes for which a real grid-interface model (converter dynamics +
#: transformer/collector impedance) is meaningful — the inverter/converter-interfaced
#: technologies. Synchronous/other classes are recognised elsewhere but are NOT screened by
#: the converter-interface path here. Kept as the SCR/GFL-GFM screen's tech allow-list so a
#: scenario that attaches a per-tech ``grid`` block to an unsupported class fails loud.
MODELLED_GRID_TECHS: frozenset[str] = frozenset({"wind", "solar", "bess"})

#: Documented provenance bases for a committed Thevenin / fault-level input. A
#: ``utility_provided`` basis is the CEB/NSCC-issued fault level (the bankable source); a
#: ``screening_estimate`` is an in-house rule-of-thumb and is gated (see module docstring).
GRID_ASSUMPTION_BASES: frozenset[str] = frozenset(
    {"utility_provided", "screening_estimate"}
)

#: Provenance bases that are ESTIMATED (not utility-provided) and therefore require the
#: per-block ``allow_unvalidated_grid: true`` opt-in before they may feed the screen.
_ESTIMATED_ASSUMPTION_BASES: frozenset[str] = frozenset({"screening_estimate"})


def _norm(value: Any) -> str:
    """Normalise a declared token to a lower-case string ("" when absent)."""
    return str(value).strip().lower() if value is not None else ""


def is_gfl_converter(converter_type: Any) -> bool:
    """True iff ``converter_type`` is a recognised grid-FOLLOWING topology."""
    return _norm(converter_type) in GFL_CONVERTER_TYPES


def is_gfm_capable_converter(converter_type: Any) -> bool:
    """True iff ``converter_type`` is a recognised grid-FORMING-capable topology."""
    return _norm(converter_type) in GFM_CAPABLE_CONVERTER_TYPES


def is_known_converter_type(converter_type: Any) -> bool:
    """True iff ``converter_type`` is a recognised converter topology (GFL or GFM)."""
    return _norm(converter_type) in CONVERTER_TYPES


def is_modelled_grid_tech(tech_name: Any) -> bool:
    """True iff ``tech_name`` is a converter-interfaced tech screened by the grid layer."""
    return _norm(tech_name) in MODELLED_GRID_TECHS


def _norm_wind_converter(converter_type: Any) -> str:
    """Collapse a wind-turbine converter token (spaces/dashes -> underscores) and lower-case."""
    raw = str(converter_type).strip().lower() if converter_type is not None else ""
    return "_".join(raw.replace("-", " ").split())


def is_type3_dfig(converter_type: Any) -> bool:
    """True iff ``converter_type`` is a Type-3 doubly-fed-induction (DFIG) turbine."""
    return _norm_wind_converter(converter_type) in TYPE3_DFIG_CONVERTER_TYPES


def is_type4_full_converter(converter_type: Any) -> bool:
    """True iff ``converter_type`` is a Type-4 full-converter turbine."""
    return _norm_wind_converter(converter_type) in TYPE4_FULL_CONVERTER_TYPES


def is_known_wind_converter_type(converter_type: Any) -> bool:
    """True iff ``converter_type`` is a recognised wind-turbine converter topology."""
    return _norm_wind_converter(converter_type) in WIND_TURBINE_CONVERTER_TYPES


def is_known_assumption_basis(basis: Any) -> bool:
    """True iff ``basis`` is a recognised Thevenin/fault-level provenance basis."""
    return _norm(basis) in GRID_ASSUMPTION_BASES


def is_estimated_assumption_basis(basis: Any) -> bool:
    """True iff ``basis`` denotes an ESTIMATED (non-utility) fault level.

    An estimated basis (``screening_estimate``) is not a bankable utility fault level and
    must be opted into via ``allow_unvalidated_grid`` before it may feed the screen.
    """
    return _norm(basis) in _ESTIMATED_ASSUMPTION_BASES


def allow_unvalidated_grid(block: Any) -> bool:
    """Return the per-block ``allow_unvalidated_grid`` opt-in flag (strict bool; default False).

    Mirrors the ``allow_unvalidated_flat_cf`` read in
    :mod:`finance.cashflow_v14_production`: only a real boolean ``True`` opts in; anything
    else (absent, ``None``, a truthy string) leaves the estimated/enum-only path REFUSED.
    """
    if not isinstance(block, dict):
        return False
    return block.get("allow_unvalidated_grid", False) is True


__all__ = [
    "GFL_CONVERTER_TYPES",
    "GFM_CAPABLE_CONVERTER_TYPES",
    "CONVERTER_TYPES",
    "TYPE3_DFIG_CONVERTER_TYPES",
    "TYPE4_FULL_CONVERTER_TYPES",
    "WIND_TURBINE_CONVERTER_TYPES",
    "MODELLED_GRID_TECHS",
    "GRID_ASSUMPTION_BASES",
    "is_gfl_converter",
    "is_gfm_capable_converter",
    "is_known_converter_type",
    "is_type3_dfig",
    "is_type4_full_converter",
    "is_known_wind_converter_type",
    "is_modelled_grid_tech",
    "is_known_assumption_basis",
    "is_estimated_assumption_basis",
    "allow_unvalidated_grid",
]
