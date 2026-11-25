"""Tax Profile Module for DutchBay v14 cashflow.

Configuration-driven corporate tax, depreciation, loss carry-forward and
interest withholding-tax handling for the v14 CFADS engine. This is the single
canonical tax engine (the parallel ``finance/tax_v14.py`` wrapper, which carried
contradictory silent defaults, was deleted in #483 / FIN-1).

Tax scope — what the model includes vs excludes (Sri Lanka regime, #483 / FIN-4):

* MODELLED: corporate income tax (CIT, 30% — the standard company rate, set by the
  First Schedule ("Rates of Income Tax") of the Sri Lanka Inland Revenue Act
  No. 24 of 2017, NOT the Second Schedule), straight-line depreciation with a
  plant/civil split, tax-loss carry-forward (6-year SL window, vintage-tracked),
  withholding tax on interest to non-residents (10%) and on dividends (15%, on the
  equity path), and the Social Services Contribution Levy (SSCL, 2.5% of revenue —
  booked as ``social_levy_lkr`` in the cashflow via ``statutory.social_services_levy_pct``).
* EXCLUDED — VAT (18%): deliberately NOT modelled as a project P&L cost. VAT on a
  BOO IPP's energy sales is a pass-through — output VAT is collected from the offtaker
  and remitted, input VAT on capex/opex is recoverable — so at steady state it is
  cashflow-neutral to the SPV and would only distort the lender economics if booked as
  a cost. (Any genuine VAT timing/cash-lock effect during construction is a working-
  capital refinement, not an operating-cashflow tax, and is out of scope here.)
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from analytics.feasibility_report_contract.project_case import (
    JurisdictionBinding,
    JurisdictionSubject,
)
from analytics.jurisdiction_packs.resolver import (
    DirectoryPackSource,
    JurisdictionRefusal,
    JurisdictionResolution,
    PackSource,
    ProjectOverride,
    RefusalReason,
    SubjectDisposition,
)
from analytics.jurisdiction_packs.resolver import resolve as resolve_jurisdiction_pack
from analytics.jurisdiction_packs.scenario_binding import (
    ScenarioBindingRegistry,
    scenario_jurisdiction_bindings,
)

#: A tax-loss carry-forward ledger: an immutable tuple of (origin_year, amount)
#: vintages. Tracking vintages (not a single scalar) lets losses EXPIRE after the
#: statutory carry-forward window (Sri Lanka: 6 years) and be preserved through
#: tax-holiday years instead of being silently consumed.
LossVintages = Tuple[Tuple[int, float], ...]


def _lookup_case_insensitive(section: Mapping[str, Any], key: str) -> Any:
    """Return exact key first, then case-insensitive key, else None."""
    if key in section:
        return section[key]
    key_lower = key.lower()
    for existing_key, value in section.items():
        if str(existing_key).lower() == key_lower:
            return value
    return None


#: The spellings of the one jurisdiction this tax and levy code implements (#1882). Compared
#: case-insensitively after trimming. ``LK`` and ``LKA`` are the ISO 3166-1 codes.
SRI_LANKA_JURISDICTION_NAMES = frozenset({"sri lanka", "lk", "lka"})


def require_sri_lanka_jurisdiction(cfg: Mapping[str, Any], ctx: str) -> None:
    """Refuse a scenario that declares a jurisdiction other than Sri Lanka (#1882).

    This module and :mod:`finance.import_levies` implement Sri Lanka rules: the
    corporate rate schedule, the six-year loss window, interest WHT, SSCL and the
    import-levy cascade. A scenario whose ``project.jurisdiction`` names another
    country must not inherit them silently (DBAY-FRC-001 section 3: fail closed, no
    implicit fallback). Until the #1841 pack resolver is wired into the engine, the
    engine therefore refuses such a scenario rather than run it on Sri Lanka law.

    An absent or null ``project.jurisdiction`` is accepted and behaves exactly as
    before; making the key required is #1841's PR 3.

    Raises:
        ValueError: ``project.jurisdiction`` is present and is not a Sri Lanka
            spelling, or is not a string.
    """
    project = _lookup_case_insensitive(cfg, "project")
    if not isinstance(project, Mapping):
        return
    declared = _lookup_case_insensitive(project, "jurisdiction")
    if declared is None:
        return
    if not isinstance(declared, str):
        raise ValueError(
            f"{ctx}: project.jurisdiction must be a string naming the jurisdiction "
            f"(got {type(declared).__name__})"
        )
    if declared.strip().lower() in SRI_LANKA_JURISDICTION_NAMES:
        return
    raise ValueError(
        f"{ctx}: project.jurisdiction is {declared!r}, but this engine implements "
        "Sri Lanka tax and levy rules only. It refuses to apply them to another "
        "jurisdiction (no silent fallback). Other jurisdictions need a pack wired "
        "through the jurisdiction resolver (#1841)."
    )


def _require_section(cfg: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    """Return a named subsection or raise if missing.

    Resolution is exact first, then case-insensitive. This keeps canonical
    ``tax`` configs unchanged while accepting compact hand-authored ``Tax``
    dictionaries used by v14 lender-stack smoke tests.
    """
    section = _lookup_case_insensitive(cfg, name)
    if not isinstance(section, Mapping):
        raise KeyError(f"Missing required YAML section: {name}")
    return section


def _get_key_with_default(
    section: Mapping[str, Any], key: str, default: Any, type_cast: type = str
) -> Any:
    """Get a key from section with a default fallback."""
    value = _lookup_case_insensitive(section, key)
    if value is not None:
        return type_cast(value)
    return default


def _require_key(section: Mapping[str, Any], key: str, ctx: str) -> Any:
    """Return a required key from a section or raise with context."""
    value = _lookup_case_insensitive(section, key)
    if value is None:
        raise KeyError(f"Missing required YAML key: {ctx}.{key}")
    return value


def _opt_float(value: Any) -> Optional[float]:
    """Cast to float, or None when the key was absent."""
    return float(value) if value is not None else None


def _opt_int(value: Any) -> Optional[int]:
    """Cast to int, or None when the key was absent."""
    return int(value) if value is not None else None


def _get_tax_rate_with_compat(tax: Mapping[str, Any]) -> float:
    """Extract corporate tax rate from canonical or compact aliases."""
    canonical = _lookup_case_insensitive(tax, "corporate_tax_rate")
    if canonical is not None:
        rate = float(canonical)
        if not (0.0 <= rate <= 1.0):
            raise ValueError(
                f"tax.corporate_tax_rate must be decimal 0.0-1.0, got {rate}"
            )
        return rate

    compact = _lookup_case_insensitive(tax, "corporate_rate")
    if compact is not None:
        rate = float(compact)
        if rate > 1.0:
            rate = rate / 100.0
        if not (0.0 <= rate <= 1.0):
            raise ValueError(
                f"tax.corporate_rate must be decimal 0.0-1.0 or percent 0-100, got {compact}"
            )
        return rate

    pct_value = _lookup_case_insensitive(tax, "corporate_tax_rate_pct")
    if pct_value is not None:
        warnings.warn(
            "tax.corporate_tax_rate_pct is deprecated. Use tax.corporate_tax_rate instead.",
            DeprecationWarning,
            stacklevel=3,
        )
        pct = float(pct_value)
        if not (0.0 <= pct <= 100.0):
            raise ValueError(f"tax.corporate_tax_rate_pct must be 0-100, got {pct}")
        return pct / 100.0

    raise KeyError(
        "Missing required YAML key: tax.corporate_tax_rate "
        "(or compact tax.corporate_rate / deprecated tax.corporate_tax_rate_pct)"
    )


def _get_enhanced_allowance_with_compat(tax: Mapping[str, Any]) -> float:
    """Extract the enhanced capital allowance MULTIPLIER, accepting a deprecated alias.

    The value is a multiplier on the depreciable base (1.0 = standard 100% allowance,
    1.5 = a 150% enhanced allowance), NOT a percent. The canonical key is
    ``enhanced_capital_allowance_multiple``; the legacy ``enhanced_capital_allowance_pct``
    (a FIN-02 misnomer — it never held a percent) is still accepted with a
    DeprecationWarning so existing scenarios keep loading unchanged.
    """
    canonical = _lookup_case_insensitive(tax, "enhanced_capital_allowance_multiple")
    if canonical is not None:
        return float(canonical)

    legacy = _lookup_case_insensitive(tax, "enhanced_capital_allowance_pct")
    if legacy is not None:
        warnings.warn(
            "tax.enhanced_capital_allowance_pct is deprecated (the field is a "
            "multiplier, not a percent). Use tax.enhanced_capital_allowance_multiple "
            "instead.",
            DeprecationWarning,
            stacklevel=3,
        )
        return float(legacy)

    raise KeyError(
        "Missing required YAML key: tax.enhanced_capital_allowance_multiple "
        "(or deprecated tax.enhanced_capital_allowance_pct)"
    )


#: Direct-tax scenario fields governed by a jurisdiction pack's ``tax`` subject (#1841 PR 4).
#: Maps scenario ``tax.<field>`` -> pack ``scenario_key`` so the engine never hardcodes
#: country-specific parameter IDs.
PACK_GOVERNED_TAX_FIELDS: Dict[str, str] = {
    "corporate_tax_rate": "tax.corporate_tax_rate",
    "loss_carryforward_years": "tax.loss_carryforward_years",
    "plant_depreciation_years": "tax.plant_depreciation_years",
    "civil_depreciation_years": "tax.civil_depreciation_years",
    "wht_on_interest_to_nonresidents": "tax.wht_on_interest_to_nonresidents",
    "wht_on_dividends": "tax.wht_on_dividends",
}

_SCENARIO_KEY_TO_TAX_FIELD: Dict[str, str] = {
    scenario_key: field_name
    for field_name, scenario_key in PACK_GOVERNED_TAX_FIELDS.items()
}

_TAX_RATE_COMPAT_ALIASES: Tuple[str, ...] = (
    "corporate_tax_rate",
    "corporate_rate",
    "corporate_tax_rate_pct",
)


class DirectTaxJurisdictionError(ValueError):
    """Raised when pack-backed direct-tax resolution fails closed (#1841 PR 4)."""


@dataclass(frozen=True)
class ResolvedDirectTax:
    """Statutory direct-tax values resolved from a scenario's jurisdiction pack."""

    corporate_tax_rate: float
    loss_carryforward_years: int
    wht_on_interest_to_nonresidents: float
    wht_on_dividends: Optional[float]
    plant_depreciation_years: Optional[int]
    civil_depreciation_years: Optional[int]
    corporate_tax_rate_by_year: Optional[Tuple[Tuple[int, float], ...]] = None
    wht_on_interest_by_year: Optional[Tuple[Tuple[int, float], ...]] = None
    resolution: Optional[JurisdictionResolution] = None


def declared_project_jurisdiction(cfg: Mapping[str, Any]) -> Any:
    """Return ``project.jurisdiction`` when declared and non-null, else ``None``."""
    project = _lookup_case_insensitive(cfg, "project")
    if not isinstance(project, Mapping):
        return None
    return _lookup_case_insensitive(project, "jurisdiction")


def _parse_optional_iso_date(raw: Any, field_name: str) -> Optional[date]:
    if raw is None:
        return None
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return date.fromisoformat(raw.strip())
        except ValueError as exc:
            raise ValueError(
                f"{field_name} must be an ISO YYYY-MM-DD date; got {raw!r}"
            ) from exc
    raise ValueError(f"{field_name} must be an ISO YYYY-MM-DD date; got {raw!r}")


def _ops_years_for_valuation(cfg: Mapping[str, Any]) -> int:
    for section_name, key in (
        ("timeline", "ops_years"),
        ("returns", "project_life_years"),
        ("project", "life_years"),
        ("project", "project_life_years"),
    ):
        section = _lookup_case_insensitive(cfg, section_name)
        if isinstance(section, Mapping):
            raw = _lookup_case_insensitive(section, key)
            if raw is not None:
                if isinstance(raw, bool):
                    raise ValueError(f"{section_name}.{key} must be an integer >= 1")
                years = int(raw)
                if years < 1:
                    raise ValueError(f"{section_name}.{key} must be >= 1, got {years}")
                return years
    return 1


def _resolve_operating_valuation_dates(
    cfg: Mapping[str, Any],
    bindings: Sequence[JurisdictionBinding],
    pack_source: PackSource,
    explicit_dates: Optional[Iterable[date]],
) -> Tuple[date, ...]:
    """Return operating-period valuation dates for direct-tax pack resolution.

    Direct tax applies only to operating periods (construction periods are excluded so
    pre-COD construction years never probe before the pack's statutory floor; #1841 PR 4).
    Each operating year uses its year-end assessment date (``YYYY-12-31``) with no
    mid-period pro-rating. Scenarios without ``project.cod_year`` or ``valuation_date``
    use the bound pack's ``effective_date``.
    """
    if explicit_dates is not None:
        return tuple(explicit_dates)

    project = _lookup_case_insensitive(cfg, "project")
    raw_val_date = (
        _lookup_case_insensitive(project, "valuation_date")
        if isinstance(project, Mapping)
        else None
    )
    if raw_val_date is None:
        raw_val_date = _lookup_case_insensitive(cfg, "valuation_date")
    parsed_val_date = _parse_optional_iso_date(raw_val_date, "project.valuation_date")
    if parsed_val_date is not None:
        return (parsed_val_date,)

    raw_cod_year = (
        _lookup_case_insensitive(project, "cod_year")
        if isinstance(project, Mapping)
        else None
    )
    if raw_cod_year is not None:
        if isinstance(raw_cod_year, bool) or not isinstance(raw_cod_year, int):
            raise ValueError(
                f"project.cod_year must be an integer calendar year; got {raw_cod_year!r}"
            )
        ops_years = _ops_years_for_valuation(cfg)
        return tuple(date(raw_cod_year + offset, 12, 31) for offset in range(ops_years))

    effective_dates: List[date] = []
    for binding in bindings:
        if (
            binding.support_status.value != "unsupported"
            and binding.contract_pack_version
            in pack_source.versions(binding.jurisdiction_code)
        ):
            try:
                pack = pack_source.load(
                    binding.jurisdiction_code, binding.contract_pack_version
                )
                effective_dates.append(pack.effective_date)
            except (FileNotFoundError, ValueError):
                continue
    if effective_dates:
        return (max(effective_dates),)
    return (date(2026, 11, 21),)


def _normalize_tax_override_key(raw_key: str) -> Optional[str]:
    key_lower = raw_key.strip().lower()
    if key_lower in ("corporate_rate", "corporate_tax_rate_pct"):
        return "tax.corporate_tax_rate"
    if key_lower in PACK_GOVERNED_TAX_FIELDS:
        return PACK_GOVERNED_TAX_FIELDS[key_lower]
    if key_lower in _SCENARIO_KEY_TO_TAX_FIELD:
        return key_lower
    return None


def _override_value_from_tax_section(
    tax_section: Optional[Mapping[str, Any]],
    field_name: str,
    raw_key: str,
) -> Any:
    if tax_section is None:
        raise KeyError(
            f"tax.pack_overrides[{raw_key!r}] requires a value or tax.{field_name}"
        )
    if field_name == "corporate_tax_rate":
        return _get_tax_rate_with_compat(tax_section)
    value = _lookup_case_insensitive(tax_section, field_name)
    if value is None:
        raise KeyError(
            f"tax.pack_overrides[{raw_key!r}] requires a value or tax.{field_name}"
        )
    return value


def _extract_pack_overrides(
    cfg: Mapping[str, Any],
    bindings: Sequence[JurisdictionBinding],
    pack_source: PackSource,
) -> Tuple[ProjectOverride, ...]:
    tax_section_raw = _lookup_case_insensitive(cfg, "tax")
    if tax_section_raw is not None and not isinstance(tax_section_raw, Mapping):
        return ()
    tax_section = tax_section_raw
    raw_overrides = (
        _lookup_case_insensitive(tax_section, "pack_overrides")
        if tax_section is not None
        else None
    )
    if raw_overrides is None:
        return ()
    if not isinstance(raw_overrides, Mapping):
        raise ValueError("tax.pack_overrides must be a mapping")
    if not raw_overrides:
        return ()

    tax_bindings = [b for b in bindings if b.subject is JurisdictionSubject.TAX]
    scenario_key_to_pid: Dict[str, str] = {}
    known_pids: set[str] = set()
    for binding in tax_bindings:
        if (
            binding.support_status.value != "unsupported"
            and binding.contract_pack_version
            in pack_source.versions(binding.jurisdiction_code)
        ):
            try:
                pack = pack_source.load(
                    binding.jurisdiction_code, binding.contract_pack_version
                )
            except (FileNotFoundError, ValueError):
                continue
            for param in pack.parameters:
                if param.subject is JurisdictionSubject.TAX:
                    scenario_key_to_pid.setdefault(
                        param.scenario_key, param.parameter_id
                    )
                    known_pids.add(param.parameter_id)

    overrides: List[ProjectOverride] = []
    for raw_key, spec in raw_overrides.items():
        key_str = str(raw_key).strip()
        if key_str in known_pids:
            parameter_id = key_str
            scenario_key = next(
                (sk for sk, pid in scenario_key_to_pid.items() if pid == parameter_id),
                None,
            )
        else:
            scenario_key = _normalize_tax_override_key(key_str)
            if scenario_key is None:
                raise JurisdictionRefusal(
                    RefusalReason.UNKNOWN_OVERRIDE,
                    f"tax.pack_overrides[{key_str!r}] names no direct-tax pack parameter",
                )
            parameter_id = scenario_key_to_pid.get(scenario_key, key_str)

        field_name = (
            _SCENARIO_KEY_TO_TAX_FIELD.get(scenario_key, key_str)
            if scenario_key is not None
            else key_str
        )

        if isinstance(spec, Mapping):
            raw_prov = spec.get("provenance")
            if "value" in spec:
                value = spec["value"]
            else:
                value = _override_value_from_tax_section(
                    tax_section, field_name, key_str
                )
        else:
            raw_prov = spec
            value = _override_value_from_tax_section(tax_section, field_name, key_str)

        if raw_prov is None or (isinstance(raw_prov, str) and not raw_prov.strip()):
            provenance: Optional[str] = None
        else:
            provenance = str(raw_prov).strip()

        overrides.append(
            ProjectOverride(
                parameter_id=parameter_id,
                value=value,
                provenance=provenance,
            )
        )
    return tuple(overrides)


def _extract_scalar_or_series(
    periods: Sequence[Any],
    scenario_key: str,
    *,
    required: bool,
    allow_time_varying: bool,
) -> Tuple[Optional[Any], Optional[Tuple[Tuple[int, float], ...]]]:
    values: List[Any] = []
    for period in periods:
        found = next(
            (item.value for item in period.values if item.scenario_key == scenario_key),
            None,
        )
        values.append(found)
    if all(v is None for v in values):
        if required:
            raise DirectTaxJurisdictionError(
                f"tax: resolved jurisdiction pack does not supply required direct-tax "
                f"parameter {scenario_key!r} (#1841)"
            )
        return None, None
    if any(v is None for v in values):
        raise DirectTaxJurisdictionError(
            f"tax: parameter {scenario_key!r} is missing on some operating valuation dates (#1841)"
        )
    first = values[0]
    if all(v == first for v in values):
        return first, None
    if not allow_time_varying:
        raise DirectTaxJurisdictionError(
            f"tax: parameter {scenario_key!r} varies across operating valuation dates "
            f"({values!r}), which is not supported as a schedule scalar (#1841)"
        )
    by_year = tuple((idx, float(val)) for idx, val in enumerate(values, start=1))
    return first, by_year


def resolve_direct_tax_from_pack(
    cfg: Mapping[str, Any],
    *,
    bindings: Optional[Iterable[JurisdictionBinding]] = None,
    source: Optional[PackSource] = None,
    registry: Optional[ScenarioBindingRegistry] = None,
    packs_root: Optional[Path] = None,
    valuation_dates: Optional[Iterable[date]] = None,
) -> ResolvedDirectTax:
    """Resolve statutory direct-tax parameters from the scenario's jurisdiction pack.

    Refuses unknown/unsupported jurisdictions, reported conflict records
    (``not_run_conflict``), unsupported subject dispositions
    (``not_run_unsupported_jurisdiction``), overrides without provenance, and valuation
    dates outside the pack's effective windows (#1841 PR 4).
    """
    bound = (
        tuple(bindings)
        if bindings is not None
        else scenario_jurisdiction_bindings(
            cfg, registry=registry, packs_root=packs_root
        )
    )
    pack_source: PackSource = (
        DirectoryPackSource(packs_root) if source is None else source
    )
    dates = _resolve_operating_valuation_dates(cfg, bound, pack_source, valuation_dates)
    overrides = _extract_pack_overrides(cfg, bound, pack_source)

    resolution = resolve_jurisdiction_pack(
        bound,
        dates,
        required_subjects=(JurisdictionSubject.TAX,),
        overrides=overrides,
        source=pack_source,
    )

    if resolution.conflicts:
        summary = "; ".join(
            f"{c.kind.value} on {c.subject.value}.{c.parameter_id} @ {c.valuation_date} "
            f"(candidates: {', '.join(f'{cand.origin}={cand.value!r}' for cand in c.candidates)})"
            for c in resolution.conflicts
        )
        raise DirectTaxJurisdictionError(
            f"tax: jurisdiction resolution refused due to not_run_conflict ({summary}) (#1841)"
        )

    tax_subject = resolution.subject(JurisdictionSubject.TAX)
    if tax_subject.disposition is SubjectDisposition.NOT_RUN_CONFLICT:
        raise DirectTaxJurisdictionError(
            "tax: jurisdiction resolution returned disposition not_run_conflict (#1841)"
        )
    if tax_subject.disposition is SubjectDisposition.NOT_RUN_UNSUPPORTED_JURISDICTION:
        raise DirectTaxJurisdictionError(
            "tax: jurisdiction resolution returned disposition "
            "not_run_unsupported_jurisdiction; refusing to apply fallback tax rules (#1841)"
        )
    if (
        tax_subject.disposition is not SubjectDisposition.SUPPORTED
        or not tax_subject.periods
    ):
        raise DirectTaxJurisdictionError(
            f"tax: jurisdiction resolution for subject 'tax' is not supported "
            f"(disposition={tax_subject.disposition.value}) (#1841)"
        )

    cit_val, cit_by_year = _extract_scalar_or_series(
        tax_subject.periods,
        "tax.corporate_tax_rate",
        required=True,
        allow_time_varying=True,
    )
    lcf_val, _ = _extract_scalar_or_series(
        tax_subject.periods,
        "tax.loss_carryforward_years",
        required=True,
        allow_time_varying=False,
    )
    wht_int_val, wht_int_by_year = _extract_scalar_or_series(
        tax_subject.periods,
        "tax.wht_on_interest_to_nonresidents",
        required=True,
        allow_time_varying=True,
    )
    wht_div_val, _ = _extract_scalar_or_series(
        tax_subject.periods,
        "tax.wht_on_dividends",
        required=False,
        allow_time_varying=False,
    )
    plant_years_val, _ = _extract_scalar_or_series(
        tax_subject.periods,
        "tax.plant_depreciation_years",
        required=False,
        allow_time_varying=False,
    )
    civil_years_val, _ = _extract_scalar_or_series(
        tax_subject.periods,
        "tax.civil_depreciation_years",
        required=False,
        allow_time_varying=False,
    )

    if cit_val is None or lcf_val is None or wht_int_val is None:
        raise DirectTaxJurisdictionError(
            "tax: resolved jurisdiction pack is missing a required direct-tax value (#1841)"
        )

    return ResolvedDirectTax(
        corporate_tax_rate=float(cit_val),
        loss_carryforward_years=int(lcf_val),
        wht_on_interest_to_nonresidents=float(wht_int_val),
        wht_on_dividends=_opt_float(wht_div_val),
        plant_depreciation_years=_opt_int(plant_years_val),
        civil_depreciation_years=_opt_int(civil_years_val),
        corporate_tax_rate_by_year=cit_by_year,
        wht_on_interest_by_year=wht_int_by_year,
        resolution=resolution,
    )


def with_tax_pack_override_provenance(
    merged_cfg: Dict[str, Any],
    expanded_overrides: Mapping[str, Any],
) -> Dict[str, Any]:
    """Attach explicit provenance to runtime ``tax.*`` overrides on bound scenarios.

    Evaluation gateways (``analytics.evaluation_v14`` and ``analytics.evaluate_scenario``)
    merge sensitivity/optimization/test overrides into ``merged_cfg``. When the scenario
    declares ``project.jurisdiction``, any runtime override touching a pack-governed direct-tax
    field is recorded under ``tax.pack_overrides`` with provenance so the resolver applies
    the override rather than overwriting it with the pack value, while still respecting any
    caller-supplied ``tax.pack_overrides`` entry.
    """
    if declared_project_jurisdiction(merged_cfg) is None:
        return merged_cfg
    ovr_tax = _lookup_case_insensitive(expanded_overrides, "tax")
    if not isinstance(ovr_tax, Mapping):
        return merged_cfg

    overridden: List[Tuple[str, str, Any]] = []
    for raw_key, raw_val in ovr_tax.items():
        key_lower = str(raw_key).strip().lower()
        if key_lower in _TAX_RATE_COMPAT_ALIASES:
            overridden.append(("corporate_tax_rate", str(raw_key), raw_val))
        elif key_lower in PACK_GOVERNED_TAX_FIELDS:
            overridden.append((key_lower, str(raw_key), raw_val))

    if not overridden:
        return merged_cfg

    existing_tax = _lookup_case_insensitive(merged_cfg, "tax")
    if not isinstance(existing_tax, Mapping):
        return merged_cfg

    existing_pack_ovr = _lookup_case_insensitive(existing_tax, "pack_overrides")
    if existing_pack_ovr is not None and not isinstance(existing_pack_ovr, Mapping):
        return merged_cfg

    caller_pack_ovr = _lookup_case_insensitive(ovr_tax, "pack_overrides")
    caller_ovr_keys = (
        {str(k).strip().lower() for k in caller_pack_ovr}
        if isinstance(caller_pack_ovr, Mapping)
        else set()
    )

    pack_overrides = (
        dict(existing_pack_ovr) if isinstance(existing_pack_ovr, Mapping) else {}
    )
    for canonical_field, raw_key, raw_val in overridden:
        if (
            canonical_field in caller_ovr_keys
            or raw_key.strip().lower() in caller_ovr_keys
        ):
            continue
        provenance = f"runtime override via evaluation gateway (tax.{raw_key})"
        if (
            canonical_field == "corporate_tax_rate"
            and raw_key.strip().lower() != "corporate_tax_rate"
        ):
            normalized = _get_tax_rate_with_compat({raw_key: raw_val})
            pack_overrides[canonical_field] = {
                "value": normalized,
                "provenance": provenance,
            }
        else:
            pack_overrides[canonical_field] = {
                "value": raw_val,
                "provenance": provenance,
            }

    out = dict(merged_cfg)
    tax_copy = dict(existing_tax)
    tax_copy["pack_overrides"] = pack_overrides
    out["tax"] = tax_copy
    return out


def _refuse_explicit_null_tax_fields(tax: Mapping[str, Any]) -> None:
    """Reject explicit ``null`` values on core statutory fields (e.g. invalid fixtures)."""
    for key in (
        "corporate_tax_rate",
        "loss_carryforward_years",
        "wht_on_interest_to_nonresidents",
    ):
        for existing_key, value in tax.items():
            if str(existing_key).lower() == key and value is None:
                raise KeyError(f"Missing required YAML key: tax.{key}")


@dataclass(frozen=True)
class TaxConfig:
    corporate_tax_rate: float
    depreciation_method: str
    depreciation_start_year: int
    depreciation_years: int
    enhanced_allowance_applies: bool
    enhanced_capital_allowance_multiple: float
    loss_carryforward_years: int
    tax_holiday_start_year: int
    tax_holiday_years: int
    wht_on_interest_to_nonresidents: float
    wht_on_interest_enabled: bool
    wht_gross_up: bool
    interest_deductibility: bool = True
    # Optional post-2025-regime fields — default-absent → legacy single-class mode.
    tax_holiday_route: str = (
        "none"  # "none" | "sdp" (descriptive; tax_holiday_years drives calc)
    )
    plant_capex_share: Optional[float] = (
        None  # set → split depreciation (plant vs civil)
    )
    plant_depreciation_years: Optional[int] = (
        None  # SL Fourth-Sched Class 2 (or Class 3) plant & machinery = 5 yr (20%/yr either way)
    )
    civil_depreciation_years: Optional[int] = (
        None  # SL Class 4 buildings/civils = 20 yr
    )
    corporate_tax_rate_by_year: Optional[Tuple[Tuple[int, float], ...]] = None
    wht_on_interest_by_year: Optional[Tuple[Tuple[int, float], ...]] = None

    def __post_init__(self) -> None:
        # enhanced_capital_allowance_multiple is an explicit MULTIPLIER on the depreciable
        # base (1.0 = standard 100% allowance, 1.5 = a 150% enhanced allowance) — only
        # applied when enhanced_allowance_applies is true (see cashflow_v14.py). This is the
        # SINGLE live resolution point; validate here so a negative multiplier fails loud
        # regardless of construction path (the parallel CashflowParams resolver that once
        # carried this check fed a dead field and was removed).
        if self.enhanced_capital_allowance_multiple < 0.0:
            raise ValueError(
                "tax.enhanced_capital_allowance_multiple must be a non-negative multiplier "
                "(1.0 = standard 100% allowance, 1.5 = a 150% enhanced allowance); got "
                f"{self.enhanced_capital_allowance_multiple}"
            )
        # Upper-bound sanity: the field is a MULTIPLIER, not a percent. A value > 3.0 is
        # almost certainly a percent-for-multiplier unit error (e.g. 150 meaning 1.5),
        # which would inflate the depreciable base ~100x and zero out tax for the whole
        # tenor. Real enhanced allowances are <= ~3.0 (300%); reject above that loudly.
        # Caught for ALL configs (not just applied ones) so a latent typo cannot lie
        # dormant until enhanced_allowance_applies flips to true.
        if self.enhanced_capital_allowance_multiple > 3.0:
            raise ValueError(
                "tax.enhanced_capital_allowance_multiple looks like a PERCENT, not a "
                f"multiplier: got {self.enhanced_capital_allowance_multiple} (> 3.0). Use "
                "the multiplier convention: 100% allowance = 1.0, 150% = 1.5."
            )

    @classmethod
    def from_yaml(
        cls,
        cfg: Mapping[str, Any],
        *,
        bindings: Optional[Iterable[JurisdictionBinding]] = None,
        pack_source: Optional[PackSource] = None,
        registry: Optional[ScenarioBindingRegistry] = None,
        packs_root: Optional[Path] = None,
        valuation_dates: Optional[Iterable[date]] = None,
    ) -> "TaxConfig":
        """Build TaxConfig from the full scenario dict.

        When ``project.jurisdiction`` (or explicit ``bindings``) is supplied, statutory
        direct-tax parameters (``corporate_tax_rate``, ``loss_carryforward_years``,
        ``plant_depreciation_years``, ``civil_depreciation_years``,
        ``wht_on_interest_to_nonresidents``) are resolved from the scenario's jurisdiction
        pack via :func:`resolve_direct_tax_from_pack` (#1841 PR 4). When
        ``project.jurisdiction`` is absent (standalone unit-test configs), the legacy
        strict direct-YAML path applies.

        CESSPIT / R22 — schema-strict, no hidden defaults: every required project tax
        field fails fast with ``KeyError: ... tax.<key>`` rather than silently
        substituting a default. The single optional field is ``interest_deductibility``
        (documented default ``True``).
        """
        has_jurisdiction = (
            bindings is not None or declared_project_jurisdiction(cfg) is not None
        )
        if has_jurisdiction:
            resolved = resolve_direct_tax_from_pack(
                cfg,
                bindings=bindings,
                source=pack_source,
                registry=registry,
                packs_root=packs_root,
                valuation_dates=valuation_dates,
            )
            tax = _require_section(cfg, "tax")
            _refuse_explicit_null_tax_fields(tax)
            corporate_tax_rate = resolved.corporate_tax_rate
            loss_carryforward_years = resolved.loss_carryforward_years
            wht_on_interest_to_nonresidents = resolved.wht_on_interest_to_nonresidents
            plant_depreciation_years = (
                resolved.plant_depreciation_years
                if resolved.plant_depreciation_years is not None
                else _opt_int(_lookup_case_insensitive(tax, "plant_depreciation_years"))
            )
            civil_depreciation_years = (
                resolved.civil_depreciation_years
                if resolved.civil_depreciation_years is not None
                else _opt_int(_lookup_case_insensitive(tax, "civil_depreciation_years"))
            )
            rate_by_year = resolved.corporate_tax_rate_by_year
            wht_by_year = resolved.wht_on_interest_by_year
        else:
            tax = _require_section(cfg, "tax")
            corporate_tax_rate = _get_tax_rate_with_compat(tax)
            loss_carryforward_years = int(
                _require_key(tax, "loss_carryforward_years", "tax")
            )
            wht_on_interest_to_nonresidents = float(
                _require_key(tax, "wht_on_interest_to_nonresidents", "tax")
            )
            plant_depreciation_years = _opt_int(
                _lookup_case_insensitive(tax, "plant_depreciation_years")
            )
            civil_depreciation_years = _opt_int(
                _lookup_case_insensitive(tax, "civil_depreciation_years")
            )
            rate_by_year = None
            wht_by_year = None

        obj = cls(
            corporate_tax_rate=corporate_tax_rate,
            depreciation_method=str(_require_key(tax, "depreciation_method", "tax")),
            depreciation_start_year=int(
                _require_key(tax, "depreciation_start_year", "tax")
            ),
            depreciation_years=int(_require_key(tax, "depreciation_years", "tax")),
            enhanced_allowance_applies=bool(
                _require_key(tax, "enhanced_allowance_applies", "tax")
            ),
            enhanced_capital_allowance_multiple=_get_enhanced_allowance_with_compat(
                tax
            ),
            loss_carryforward_years=loss_carryforward_years,
            tax_holiday_start_year=int(
                _require_key(tax, "tax_holiday_start_year", "tax")
            ),
            tax_holiday_years=int(_require_key(tax, "tax_holiday_years", "tax")),
            wht_on_interest_to_nonresidents=wht_on_interest_to_nonresidents,
            wht_on_interest_enabled=bool(
                _require_key(tax, "wht_on_interest_enabled", "tax")
            ),
            wht_gross_up=bool(_require_key(tax, "wht_gross_up", "tax")),
            interest_deductibility=bool(
                _lookup_case_insensitive(tax, "interest_deductibility")
                if _lookup_case_insensitive(tax, "interest_deductibility") is not None
                else True
            ),
            # Optional post-2025-regime fields — absent → legacy single-class mode.
            tax_holiday_route=str(
                _lookup_case_insensitive(tax, "tax_holiday_route") or "none"
            ),
            plant_capex_share=_opt_float(
                _lookup_case_insensitive(tax, "plant_capex_share")
            ),
            plant_depreciation_years=plant_depreciation_years,
            civil_depreciation_years=civil_depreciation_years,
            corporate_tax_rate_by_year=rate_by_year,
            wht_on_interest_by_year=wht_by_year,
        )
        obj._validate()
        return obj

    def _validate(self) -> None:
        if not (0.0 <= self.corporate_tax_rate <= 1.0):
            raise ValueError(
                f"tax.corporate_tax_rate must be in [0,1], got {self.corporate_tax_rate}"
            )
        if self.depreciation_years < 0:
            raise ValueError("tax.depreciation_years must be >= 0")
        if self.depreciation_start_year < 1:
            raise ValueError("tax.depreciation_start_year must be >= 1")
        if self.tax_holiday_start_year < 1 or self.tax_holiday_years < 0:
            raise ValueError("tax holiday parameters invalid")
        if self.loss_carryforward_years < 0:
            raise ValueError("tax.loss_carryforward_years must be >= 0")
        if not (0.0 <= self.wht_on_interest_to_nonresidents <= 1.0):
            raise ValueError("tax.wht_on_interest_to_nonresidents must be in [0,1]")
        if self.depreciation_method not in (
            "straight_line",
            "accelerated",
            "none",
        ):
            raise ValueError(
                f"tax.depreciation_method unsupported: {self.depreciation_method}"
            )
        if self.tax_holiday_route not in ("none", "sdp"):
            raise ValueError(
                f"tax.tax_holiday_route must be 'none' or 'sdp', got {self.tax_holiday_route}"
            )
        if self.plant_capex_share is not None:
            if not (0.0 <= self.plant_capex_share <= 1.0):
                raise ValueError("tax.plant_capex_share must be in [0,1]")
            if not self.plant_depreciation_years or self.plant_depreciation_years < 1:
                raise ValueError(
                    "tax.plant_depreciation_years must be >= 1 when plant_capex_share is set"
                )
            if not self.civil_depreciation_years or self.civil_depreciation_years < 1:
                raise ValueError(
                    "tax.civil_depreciation_years must be >= 1 when plant_capex_share is set"
                )
        if self.corporate_tax_rate_by_year is not None:
            for yr, rate in self.corporate_tax_rate_by_year:
                if not (0.0 <= rate <= 1.0):
                    raise ValueError(
                        f"tax.corporate_tax_rate_by_year[{yr}] must be in [0,1], got {rate}"
                    )
        if self.wht_on_interest_by_year is not None:
            for yr, rate in self.wht_on_interest_by_year:
                if not (0.0 <= rate <= 1.0):
                    raise ValueError(
                        f"tax.wht_on_interest_by_year[{yr}] must be in [0,1], got {rate}"
                    )


@dataclass(frozen=True)
class TaxProfile:
    tax_rate: float
    interest_deductibility: bool
    depreciation_method: str
    depreciation_schedule: List[float]
    allowable_losses_carryforward: bool
    withholding_tax_rate: float
    tax_holidays_by_year: Dict[int, bool]
    #: Statutory carry-forward window in years (Sri Lanka: 6). ``0`` means no cap
    #: (unlimited carry — the historical behaviour, kept as the default so direct
    #: TaxProfile constructions stay byte-identical). A loss originating in year ``y``
    #: can offset income through year ``y + loss_carryforward_years``.
    loss_carryforward_years: int = 0
    tax_rate_by_year: Optional[Dict[int, float]] = None
    withholding_tax_rate_by_year: Optional[Dict[int, float]] = None

    def __post_init__(self) -> None:
        if not (0.0 <= self.tax_rate <= 1.0):
            raise ValueError(f"tax_rate must be in [0,1], got {self.tax_rate}")
        if not (0.0 <= self.withholding_tax_rate <= 1.0):
            raise ValueError(
                f"withholding_tax_rate must be in [0,1], got {self.withholding_tax_rate}"
            )
        if self.tax_rate_by_year is not None:
            for yr, rate in self.tax_rate_by_year.items():
                if not (0.0 <= rate <= 1.0):
                    raise ValueError(
                        f"tax_rate_by_year[{yr}] must be in [0,1], got {rate}"
                    )
        if self.withholding_tax_rate_by_year is not None:
            for yr, rate in self.withholding_tax_rate_by_year.items():
                if not (0.0 <= rate <= 1.0):
                    raise ValueError(
                        f"withholding_tax_rate_by_year[{yr}] must be in [0,1], got {rate}"
                    )
        if self.depreciation_method not in (
            "straight_line",
            "accelerated",
            "none",
        ):
            raise ValueError(f"Unknown depreciation_method: {self.depreciation_method}")


@dataclass(frozen=True)
class DepreciationSchedule:
    method: str
    capex_base: float
    useful_life_years: int
    annual_amounts: List[float]
    accumulated_depreciation: List[float]
    book_value: List[float]

    @staticmethod
    def build_straight_line(
        capex_lkr: float,
        useful_life: int,
        project_life: int,
        start_year: int = 1,
    ) -> "DepreciationSchedule":
        if useful_life <= 0:
            raise ValueError("useful_life must be > 0 for straight_line")
        if start_year < 1:
            raise ValueError("depreciation start_year must be >= 1")

        annual_depr = capex_lkr / useful_life
        annual_amounts: List[float] = []
        accumulated: List[float] = []
        book_values: List[float] = []
        acc = 0.0

        # Depreciation runs for ``useful_life`` years beginning at ``start_year`` (1-based).
        # start_year=1 is the standard case and is byte-identical to ``year <= useful_life``.
        last_depr_year = start_year + useful_life - 1
        for year in range(1, project_life + 1):
            depr = annual_depr if start_year <= year <= last_depr_year else 0.0
            annual_amounts.append(depr)
            acc += depr
            accumulated.append(acc)
            book_values.append(max(capex_lkr - acc, 0.0))

        return DepreciationSchedule(
            method="straight_line",
            capex_base=capex_lkr,
            useful_life_years=useful_life,
            annual_amounts=annual_amounts,
            accumulated_depreciation=accumulated,
            book_value=book_values,
        )

    @staticmethod
    def build_split_straight_line(
        total_capex: float,
        plant_capex_share: float,
        plant_useful_life: int,
        civil_useful_life: int,
        project_life: int,
        start_year: int = 1,
    ) -> "DepreciationSchedule":
        """Combined straight-line schedule for a split capex base.

        Splits ``total_capex`` into a plant/machinery component
        (``plant_capex_share``, depreciated over ``plant_useful_life``) and a
        civil-works component (the remainder, over ``civil_useful_life``), builds
        each straight-line, and sums them — modelling the Sri Lanka Fourth-Schedule
        asset-class split (plant & machinery 5 yr / buildings & civils 20 yr).
        """
        if not (0.0 <= plant_capex_share <= 1.0):
            raise ValueError("plant_capex_share must be in [0,1]")
        plant = DepreciationSchedule.build_straight_line(
            total_capex * plant_capex_share, plant_useful_life, project_life, start_year
        )
        civil = DepreciationSchedule.build_straight_line(
            total_capex * (1.0 - plant_capex_share),
            civil_useful_life,
            project_life,
            start_year,
        )
        annual_amounts = [
            p + c
            for p, c in zip(plant.annual_amounts, civil.annual_amounts, strict=True)
        ]
        accumulated: List[float] = []
        acc = 0.0
        for amount in annual_amounts:
            acc += amount
            accumulated.append(acc)
        book_values = [max(total_capex - a, 0.0) for a in accumulated]
        return DepreciationSchedule(
            method="straight_line_split",
            capex_base=total_capex,
            useful_life_years=max(plant_useful_life, civil_useful_life),
            annual_amounts=annual_amounts,
            accumulated_depreciation=accumulated,
            book_value=book_values,
        )


@dataclass(frozen=True)
class TaxResult:
    year: int
    ebit: float
    interest_expense: float
    depreciation: float
    taxable_income: float
    tax_liability: float
    effective_tax_rate: float
    tax_holiday_applied: bool
    carried_forward_losses: float
    wht_on_interest: float
    #: The updated loss-vintage ledger to thread into the next year (empty for the
    #: legacy scalar path). ``carried_forward_losses`` is its running total.
    carried_forward_vintages: LossVintages = ()


def build_tax_holiday_map(
    config: TaxConfig,
    project_life_years: int,
) -> Dict[int, bool]:
    holidays: Dict[int, bool] = {}
    start = config.tax_holiday_start_year
    end = start + config.tax_holiday_years - 1
    for year in range(1, project_life_years + 1):
        holidays[year] = start <= year <= end
    return holidays


def build_tax_profile(
    config: TaxConfig,
    depreciation_schedule: DepreciationSchedule,
    project_life_years: int,
) -> TaxProfile:
    tax_holidays = build_tax_holiday_map(config, project_life_years)
    wht_rate = (
        config.wht_on_interest_to_nonresidents
        if config.wht_on_interest_enabled
        else 0.0
    )
    tax_rate_by_year = (
        dict(config.corporate_tax_rate_by_year)
        if config.corporate_tax_rate_by_year is not None
        else None
    )
    wht_by_year = (
        dict(config.wht_on_interest_by_year)
        if config.wht_on_interest_enabled and config.wht_on_interest_by_year is not None
        else None
    )
    return TaxProfile(
        tax_rate=config.corporate_tax_rate,
        interest_deductibility=config.interest_deductibility,
        depreciation_method=config.depreciation_method,
        depreciation_schedule=list(depreciation_schedule.annual_amounts),
        allowable_losses_carryforward=config.loss_carryforward_years > 0,
        loss_carryforward_years=config.loss_carryforward_years,
        withholding_tax_rate=wht_rate,
        tax_holidays_by_year=tax_holidays,
        tax_rate_by_year=tax_rate_by_year,
        withholding_tax_rate_by_year=wht_by_year,
    )


def _apply_loss_vintages(
    year: int,
    pre_offset_taxable: float,
    is_holiday: bool,
    prior_vintages: Sequence[Tuple[int, float]],
    cap: int,
    allowable: bool,
) -> Tuple[float, LossVintages]:
    """Expire, (conditionally) offset, and update the loss-vintage ledger.

    Returns ``(taxable_after_offset, new_vintages)``. Vintages older than ``cap`` years
    expire before any offset (``cap <= 0`` means unlimited). A holiday year does NOT
    consume losses (the shield would be wasted — tax is 0 regardless). A year with
    negative pre-offset income adds a new vintage. Offsets are FIFO (oldest first).
    """
    if not allowable:
        return max(pre_offset_taxable, 0.0), ()
    live = [
        (oy, amt)
        for (oy, amt) in prior_vintages
        if amt > 0.0 and (cap <= 0 or (year - oy) <= cap)
    ]
    if pre_offset_taxable < 0.0:
        new = sorted(live) + [(year, -pre_offset_taxable)]
        return 0.0, tuple(new)
    if is_holiday:
        return pre_offset_taxable, tuple(sorted(live))
    budget = pre_offset_taxable
    remaining: List[Tuple[int, float]] = []
    for oy, amt in sorted(live):
        use = min(amt, budget)
        budget -= use
        leftover = amt - use
        if leftover > 1e-9:
            remaining.append((oy, leftover))
    return budget, tuple(remaining)


def calculate_tax(
    year: int,
    ebit: float,
    interest_expense: float,
    depreciation: float,
    tax_profile: TaxProfile,
    prior_year_losses: float = 0.0,
    prior_loss_vintages: Optional[Sequence[Tuple[int, float]]] = None,
    interest_paid: Optional[float] = None,
) -> TaxResult:
    """Per-year tax. When ``prior_loss_vintages`` is supplied (the live path) losses are
    tracked per vintage so they EXPIRE after ``loss_carryforward_years`` and are PRESERVED
    through holiday years. When it is ``None`` the legacy scalar carry-forward applies
    (no expiry) — kept byte-identical for direct scalar callers.

    ``interest_paid`` is the interest settled in cash in the year, the base of the
    reported withholding tax (``wht_on_interest``): WHT arises on payment, whatever the
    income-tax basis of ``interest_expense`` (#1539 DOM-4). ``None`` takes
    ``interest_expense``, which is the same figure on the default ``paid`` basis."""
    is_holiday = tax_profile.tax_holidays_by_year.get(year, False)
    taxable = ebit
    if tax_profile.interest_deductibility:
        taxable -= interest_expense
    taxable -= depreciation

    new_vintages: LossVintages = ()
    if prior_loss_vintages is None:
        # Legacy scalar path (no expiry, consumes during holidays) — byte-identical.
        carried_forward = 0.0
        if tax_profile.allowable_losses_carryforward and prior_year_losses > 0.0:
            loss_offset = min(prior_year_losses, max(taxable, 0.0))
            taxable -= loss_offset
            carried_forward = prior_year_losses - loss_offset
        taxable_income = max(taxable, 0.0)
        new_losses = max(-taxable, 0.0) + carried_forward
    else:
        taxable_after, new_vintages = _apply_loss_vintages(
            year,
            taxable,
            is_holiday,
            prior_loss_vintages,
            tax_profile.loss_carryforward_years,
            tax_profile.allowable_losses_carryforward,
        )
        taxable_income = max(taxable_after, 0.0)
        new_losses = sum(amt for _, amt in new_vintages)

    applicable_tax_rate = (
        tax_profile.tax_rate_by_year.get(year, tax_profile.tax_rate)
        if tax_profile.tax_rate_by_year is not None
        else tax_profile.tax_rate
    )
    tax_liability = 0.0 if is_holiday else taxable_income * applicable_tax_rate
    # FIN-3 (#482): the effective tax rate is tax / TAXABLE INCOME (the base the rate is
    # applied to), not tax / EBIT (which ignores the interest + depreciation deductions and
    # would report a misleadingly low rate). Reporting-only — CFADS uses tax_liability
    # directly — so this is KPI-neutral, but the lender-audit figure must be honest.
    effective_rate = tax_liability / taxable_income if taxable_income > 0.0 else 0.0
    wht_base = interest_expense if interest_paid is None else interest_paid
    applicable_wht_rate = (
        tax_profile.withholding_tax_rate_by_year.get(
            year, tax_profile.withholding_tax_rate
        )
        if tax_profile.withholding_tax_rate_by_year is not None
        else tax_profile.withholding_tax_rate
    )
    wht_on_interest = wht_base * applicable_wht_rate

    return TaxResult(
        year=year,
        ebit=ebit,
        interest_expense=interest_expense,
        depreciation=depreciation,
        taxable_income=taxable_income,
        tax_liability=tax_liability,
        effective_tax_rate=effective_rate,
        tax_holiday_applied=is_holiday,
        carried_forward_losses=new_losses,
        wht_on_interest=wht_on_interest,
        carried_forward_vintages=new_vintages,
    )


def build_tax_series(
    years: Sequence[int],
    ebit_series: Sequence[float],
    interest_series: Sequence[float],
    depreciation_schedule: DepreciationSchedule,
    tax_profile: TaxProfile,
) -> List[TaxResult]:
    if not (
        len(years)
        == len(ebit_series)
        == len(interest_series)
        == len(depreciation_schedule.annual_amounts)
    ):
        raise ValueError("Mismatched lengths in tax series inputs")

    results: List[TaxResult] = []
    carried_vintages: LossVintages = ()
    for idx, year in enumerate(years):
        tax_result = calculate_tax(
            year=year,
            ebit=ebit_series[idx],
            interest_expense=interest_series[idx],
            depreciation=depreciation_schedule.annual_amounts[idx],
            tax_profile=tax_profile,
            prior_loss_vintages=carried_vintages,
        )
        results.append(tax_result)
        carried_vintages = tax_result.carried_forward_vintages
    return results


__all__ = [
    "TaxConfig",
    "TaxProfile",
    "TaxResult",
    "DepreciationSchedule",
    "DirectTaxJurisdictionError",
    "ResolvedDirectTax",
    "PACK_GOVERNED_TAX_FIELDS",
    "build_tax_profile",
    "build_tax_series",
    "calculate_tax",
    "build_tax_holiday_map",
    "declared_project_jurisdiction",
    "resolve_direct_tax_from_pack",
    "with_tax_pack_override_provenance",
    "require_sri_lanka_jurisdiction",
    "SRI_LANKA_JURISDICTION_NAMES",
]
