"""Grid interconnection study config schema (#872 D1, #873 D2).

Defines and registers the required-field specs for the top-level ``grid`` block — the
strict, config-first (CESSPIT) contract for the design-stage grid-strength screen
(:mod:`analytics.grid.short_circuit`). The block is DEFAULT-OFF: ``grid.study_enabled``
gates the whole feature and is a strict required boolean whenever a ``grid`` block is
present (no silent default — a missing/typo'd value fails loud).

Enforcement is OPT-IN / validate-when-present: :func:`analytics.schema_guard.validate_config_for_v14`
adds the ``"grid"`` module only when a scenario actually declares a top-level ``grid``
block, so every non-grid scenario is byte-identical (KPI-neutral).

D1 → D2 extension
-----------------
D1 (#872) registered a MINIMAL flat surface (``study_enabled`` + the seven scalars the
closed-form / pandapower screen consumes today). D2 (#873) EXTENDS — it does NOT duplicate —
that surface with the FULL per-site interconnection block: the structured ``poc`` /
``thevenin`` / ``scr`` / ``gridcode`` sub-blocks and (where declared) the per-tech
``generation.technologies.<name>.grid`` interface. The extension is:

  * BACKWARD-COMPATIBLE: the D1 flat fields remain strict-required (they are the values the
    screen actually reads), so every already-committed D1 grid block still validates.
  * DEFAULT-OFF + validate-when-present: the auto-enforce loop only adds ``"grid"`` when a
    top-level ``grid`` mapping is present, so grid-absent scenarios stay byte-identical.
  * STRICT / no silent defaults (CESSPIT): a present ``grid`` block missing a structured
    Thevenin range or POC kV is REJECTED with an actionable, field-naming message. The
    ``thevenin.assumption_basis`` provenance enum and the ``grid.converter_type`` /
    Thevenin-range CONDITIONAL rules (an ESTIMATED basis requires the ``allow_unvalidated_grid``
    opt-in) are validated by :func:`validate_grid_block` — a dependency a flat
    required-field spec cannot express (same pattern as ``resource.crossval.source_type``).

Fields (top-level ``grid`` key)
    D1 flat core (screen inputs; strict-required):
      - ``study_enabled``            master gate (bool; strict, no default)
      - ``poc_voltage_kv``           point-of-connection nominal voltage (kV; > 0)
      - ``source_fault_level_mva``   upstream busbar short-circuit level (MVA; > 0)
      - ``source_rx``                source Thevenin R/X ratio (>= 0)
      - ``connection_r_ohm``         connection resistance, ohms @ POC kV (>= 0)
      - ``connection_x_ohm``         connection reactance, ohms @ POC kV (>= 0)
      - ``plant_rating_mva``         aggregate plant rating, the SCR denominator (MVA; > 0)
    D2 structured extension (strict-required when a ``grid`` block is present):
      - ``poc.bus_name``             POC busbar identifier (non-empty str)
      - ``poc.nominal_kv``           POC nominal voltage (kV; > 0)
      - ``poc.plant_rated_mva``      plant rating at the POC (MVA; > 0)
      - ``thevenin.short_circuit_mva_min``  IEC-60909 MIN fault level (MVA; > 0) — GOVERNS
      - ``thevenin.short_circuit_mva_max``  IEC-60909 MAX fault level (MVA; > 0; context)
      - ``thevenin.x_r``             source X/R ratio (>= 0)
      - ``thevenin.assumption_basis`` provenance enum (``utility_provided`` | ``screening_estimate``)
    D2 descriptive extension (validated by :func:`validate_grid_block` only when declared —
    the lender-facing SCR thresholds, the grid-code envelope, and the per-tech
    ``generation.technologies.<name>.grid`` interface): ``scr.*``, ``gridcode.*``,
    ``poc_transformer`` / ``collector_equivalent`` and the per-tech converter block.

Registered with :mod:`analytics.config_schema`; enforced via
:func:`analytics.schema_guard.validate_config_for_v14` with module ``"grid"``.
"""

from __future__ import annotations

from typing import Any, Mapping

from analytics.config_schema import RequiredFieldSpec, register_required_fields
from finance.grid.grid_types import (
    allow_unvalidated_grid,
    is_estimated_assumption_basis,
    is_known_assumption_basis,
    is_known_converter_type,
    is_modelled_grid_tech,
)

#: Logical module name used with ``validate_config_for_v14(..., ["grid"])``.
GRID_INTERFACE_MODULE = "grid"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_positive_number(value: Any) -> bool:
    return _is_number(value) and float(value) > 0.0


def _is_nonneg_number(value: Any) -> bool:
    return _is_number(value) and float(value) >= 0.0


def _is_bool(value: Any) -> bool:
    """Strict boolean — the master gate must be a real bool, not a truthy string/int."""
    return isinstance(value, bool)


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_assumption_basis(value: Any) -> bool:
    return is_known_assumption_basis(value)


_GRID_SPECS = [
    # --- D1 flat core (screen inputs) ------------------------------------------------- #
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="study_enabled",
        paths=[("grid", "study_enabled")],
        description="Master gate for the grid interconnection study (bool; default-off).",
        validator=_is_bool,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="poc_voltage_kv",
        paths=[("grid", "poc_voltage_kv")],
        description="Point-of-connection nominal voltage (kV; > 0).",
        validator=_is_positive_number,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="source_fault_level_mva",
        paths=[("grid", "source_fault_level_mva")],
        description="Upstream (source) busbar short-circuit level (MVA; > 0).",
        validator=_is_positive_number,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="source_rx",
        paths=[("grid", "source_rx")],
        description="Source Thevenin R/X ratio (>= 0).",
        validator=_is_nonneg_number,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="connection_r_ohm",
        paths=[("grid", "connection_r_ohm")],
        description="Connection resistance, ohms referred to POC voltage (>= 0).",
        validator=_is_nonneg_number,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="connection_x_ohm",
        paths=[("grid", "connection_x_ohm")],
        description="Connection reactance, ohms referred to POC voltage (>= 0).",
        validator=_is_nonneg_number,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="plant_rating_mva",
        paths=[("grid", "plant_rating_mva")],
        description="Aggregate plant rating (MVA; > 0) — the SCR denominator.",
        validator=_is_positive_number,
    ),
    # --- D2 structured per-site block (#873) ------------------------------------------ #
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="poc.bus_name",
        paths=[("grid", "poc", "bus_name")],
        description="Point-of-connection busbar identifier (non-empty string).",
        validator=_is_nonempty_str,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="poc.nominal_kv",
        paths=[("grid", "poc", "nominal_kv")],
        description="Point-of-connection nominal voltage (kV; > 0).",
        validator=_is_positive_number,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="poc.plant_rated_mva",
        paths=[("grid", "poc", "plant_rated_mva")],
        description="Plant rated apparent power at the POC (MVA; > 0) — SCR denominator.",
        validator=_is_positive_number,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="thevenin.short_circuit_mva_min",
        paths=[("grid", "thevenin", "short_circuit_mva_min")],
        description="IEC-60909 MINIMUM fault level at the POC (MVA; > 0) — governs the screen.",
        validator=_is_positive_number,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="thevenin.short_circuit_mva_max",
        paths=[("grid", "thevenin", "short_circuit_mva_max")],
        description="IEC-60909 MAXIMUM fault level at the POC (MVA; > 0) — reported for context.",
        validator=_is_positive_number,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="thevenin.x_r",
        paths=[("grid", "thevenin", "x_r")],
        description="Source X/R ratio at the POC (>= 0).",
        validator=_is_nonneg_number,
    ),
    RequiredFieldSpec(
        module=GRID_INTERFACE_MODULE,
        name="thevenin.assumption_basis",
        paths=[("grid", "thevenin", "assumption_basis")],
        description=(
            "Provenance of the Thevenin/fault-level input: 'utility_provided' (CEB/NSCC "
            "fault level, bankable) or 'screening_estimate' (in-house; requires "
            "allow_unvalidated_grid: true)."
        ),
        validator=_is_assumption_basis,
    ),
]

# Registered at import (idempotent via Python's import cache). schema_guard maps the
# "grid" module name to this module so validation triggers registration.
register_required_fields(GRID_INTERFACE_MODULE, _GRID_SPECS)


# --------------------------------------------------------------------------- #
# Conditional / cross-field rules the flat required-field specs cannot express #
# (same pattern as `resource.crossval.source_type` conditionality). Delegated  #
# to by `schema_guard._validate_grid_conditionals` when a grid block is present.#
# --------------------------------------------------------------------------- #


def _validate_thevenin_conditionals(grid: Mapping[str, Any], errors: list[str]) -> None:
    """Cross-field Thevenin rules: min<=max range coherence + estimated-basis opt-in gate.

    Both rules only fire once the structured ``thevenin`` sub-block resolves to numbers /
    a known basis (the flat required-field specs already reject a missing/typed value), so
    this never double-reports a field the spec loop already flagged.
    """
    thevenin = grid.get("thevenin")
    if not isinstance(thevenin, Mapping):
        return  # absence handled by the required-field spec (thevenin.* paths -> None)

    sc_min = thevenin.get("short_circuit_mva_min")
    sc_max = thevenin.get("short_circuit_mva_max")
    if (
        _is_positive_number(sc_min)
        and _is_positive_number(sc_max)
        and float(sc_min) > float(sc_max)  # type: ignore[arg-type]  # narrowed by _is_positive_number
    ):
        errors.append(
            "grid.thevenin: short_circuit_mva_min "
            f"({sc_min}) must be <= short_circuit_mva_max ({sc_max}) "
            "(the IEC-60909 min case governs the screen and cannot exceed the max case)."
        )

    basis = thevenin.get("assumption_basis")
    if is_estimated_assumption_basis(basis) and not allow_unvalidated_grid(grid):
        errors.append(
            "grid.thevenin.assumption_basis='screening_estimate' is an in-house ESTIMATED "
            "fault level, not a utility-provided (CEB/NSCC) value — it is not bankable and "
            "must be opted into. Set grid.allow_unvalidated_grid: true to run the screen on "
            "a screening estimate, or supply a utility_provided fault level."
        )


def _validate_per_tech_grid_blocks(
    raw_config: Mapping[str, Any], errors: list[str]
) -> None:
    """Validate any per-tech ``generation.technologies.<name>.grid`` interface block.

    Present-only (a tech without a ``grid`` block is untouched). When present, the block's
    ``rated_mva`` (MVA; > 0) and ``converter_type`` enum (GFL/GFM) are strict; the tech must
    be a converter-interfaced class (:data:`finance.grid.grid_types.MODELLED_GRID_TECHS`);
    and an enum-only interface (a ``converter_type`` with no committed ``dynamic_model``)
    requires the per-block ``allow_unvalidated_grid: true`` opt-in (mirrors the top-level
    estimated-Thevenin gate).
    """
    generation = raw_config.get("generation")
    techs = generation.get("technologies") if isinstance(generation, Mapping) else None
    if not isinstance(techs, Mapping):
        return

    for name, block in techs.items():
        if not isinstance(block, Mapping):
            continue
        grid = block.get("grid")
        if grid is None:
            continue  # per-tech grid interface is opt-in
        if not isinstance(grid, Mapping):
            errors.append(
                f"generation.technologies['{name}'].grid must be a mapping, "
                f"got {type(grid).__name__}."
            )
            continue

        if not is_modelled_grid_tech(name):
            errors.append(
                f"generation.technologies['{name}'] declares a grid interface but '{name}' "
                "is not a converter-interfaced technology (supported: wind, solar, bess). "
                "Remove the block or attach it to a converter-interfaced tech."
            )

        rated = grid.get("rated_mva")
        if not _is_positive_number(rated):
            errors.append(
                f"generation.technologies['{name}'].grid.rated_mva must be a number > 0 "
                f"(MVA), got {rated!r}."
            )

        converter = grid.get("converter_type")
        if not is_known_converter_type(converter):
            errors.append(
                f"generation.technologies['{name}'].grid.converter_type={converter!r} is "
                "not a recognised converter topology "
                "(valid: gfl / grid_following / gfm / grid_forming)."
            )

        # An enum-only interface (no committed dynamic model) is UNVALIDATED and must be
        # opted into — a user can never silently screen on a bare converter enum.
        dynamic_model = grid.get("dynamic_model")
        if not isinstance(dynamic_model, Mapping) and not allow_unvalidated_grid(grid):
            errors.append(
                f"generation.technologies['{name}'].grid declares converter_type="
                f"{converter!r} with no dynamic_model — this is an UNVALIDATED enum-only "
                "interface. Supply a dynamic_model {family, params_ref, source} or set "
                "this block's allow_unvalidated_grid: true to opt into the enum-only screen."
            )


def validate_grid_block(raw_config: Mapping[str, Any], errors: list[str]) -> None:
    """Run the conditional / cross-field grid rules that a flat spec cannot express.

    Called by the schema guard AFTER the flat required-field specs (which handle
    presence/type of each leaf) and ONLY when a top-level ``grid`` block is present, so
    grid-absent scenarios never touch this path (byte-identical). Appends actionable,
    field-naming messages to ``errors``.
    """
    grid = raw_config.get("grid")
    if isinstance(grid, Mapping):
        _validate_thevenin_conditionals(grid, errors)
    _validate_per_tech_grid_blocks(raw_config, errors)


__all__ = ["GRID_INTERFACE_MODULE", "validate_grid_block"]
