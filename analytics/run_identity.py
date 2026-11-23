"""One run, one identity, and one unit/disposition/reliance contract across surfaces (#1815).

A pipeline run stamps its manifest once (``analytics.run_manifest.build_run_manifest``).
Consumer surfaces carry it together with explicit unit contracts, section dispositions,
and non-reliance/hold disclosures:

* the API pipeline response (``api.pipeline_api.RunPipelineResponse.manifest``) and wizard
  case surface (``app.api.surface.CaseSurface``);
* the report context (``app.reports.report_model.ReportContext``), which the HTML report
  and DBPL print render;
* the executive workbook (``analytics.executive_workbook``: ``Summary``, ``Cashflow``,
  ``DebtService``, ``Ratios``, ``ScenarioSummary``, ``Manifest``); and
* the DFI foundation workbook (``analytics.dfi_workbook.foundation``:
  ``Control_Provenance`` and ``Module_Ledger``).

This module provides the shared identity, unit-contract, section-disposition, reliance,
and consumer-matrix parity checks so no surface can silently drift or weaken a hold.
"""

from __future__ import annotations

import re
from typing import AbstractSet, Any, Dict, Mapping, Optional

#: The run-identity fields every output surface must carry with equal values.
#: ``generated_at`` is the run's own stamp, so it is equal across surfaces built from one
#: run, not across runs. ``validation_mode`` and ``seed`` may be null.
RUN_IDENTITY_FIELDS: tuple[str, ...] = (
    "config_sha256",
    "engine_version",
    "git_sha",
    "generated_at",
    "manifest_schema_version",
    "validation_mode",
    "seed",
)
_REQUIRED_FIELDS: tuple[str, ...] = RUN_IDENTITY_FIELDS[:5]

#: Canonical HOLD union carried across all output surfaces until explicit owner/Board release.
HOLD_UNION: tuple[str, ...] = ("F-5", "#1110", "v15.6.1")

#: Un-suppressible F-5 non-reliance notice shared across workbook, report/DBPL, and API.
F5_NON_RELIANCE_NOTICE: str = (
    "HOLD (F-5, #1110, v15.6.1): Non-reliance notice. These are model outputs for "
    "screening and discussion only. They support no covenant, lender or IC "
    "representation, and no quarterly CFADS or intra-year DSCR figure may be used "
    "for covenant purposes."
)

#: Canonical section dispositions across API, report/DBPL, and ledger surfaces.
SECTION_DISPOSITIONS: tuple[str, ...] = (
    "computed",
    "allocated",
    "degraded",
    "omitted",
    "not_run",
)
_SECTION_DISPOSITION_SET: frozenset[str] = frozenset(SECTION_DISPOSITIONS)

#: Canonical reliance-label vocabulary across output surfaces.
RELIANCE_LABELS: tuple[str, ...] = (
    "lender_reliance_prohibited",
    "screening_only_synthetic_grid",
    "allocated_within_year_non_covenant",
)
_RELIANCE_LABEL_SET: frozenset[str] = frozenset(RELIANCE_LABELS)

#: Canonical unit contract per KPI/column key across API, report, and workbook surfaces.
KPI_UNIT_CONTRACTS: Mapping[str, str] = {
    # Decimal percentages (displayed as 0.00%, e.g. 0.0146 -> 1.46%)
    "project_irr": "pct",
    "equity_irr": "pct",
    "irr": "pct",
    "discount_rate_used": "pct",
    "prudential_rate_used": "pct",
    "balloon_pct": "pct",
    "average_equity_cash_on_cash": "pct",
    "risk_haircut_pct": "pct",
    "effective_tax_rate": "pct",
    "gearing": "pct",
    "capacity_factor": "pct",
    # US Dollars
    "project_npv": "usd",
    "equity_npv": "usd",
    "npv": "usd",
    "project_npv_prudential": "usd",
    "project_npv_usd": "usd",
    "equity_npv_usd": "usd",
    "balloon_residual": "usd",
    "senior_fee_deferred_residual": "usd",
    "cf_after_debt": "usd",
    "cf_pre_debt": "usd",
    "debt_service_total": "usd",
    "total_service": "usd",
    "interest_total": "usd",
    "debt_outstanding": "usd",
    "balloon_resolution": "usd",
    # Sri Lankan Rupees
    "carried_forward_losses": "lkr",
    "wht_on_interest": "lkr",
    # FX rate
    "fx_rate": "lkr_per_usd",
    # Coverage & return multiples (displayed with 'x' suffix)
    "min_dscr": "multiple",
    "min_dscr_period": "multiple",
    "avg_dscr": "multiple",
    "dscr_min": "multiple",
    "dscr_max": "multiple",
    "dscr_mean": "multiple",
    "dscr_median": "multiple",
    "dscr_p10": "multiple",
    "dscr_p90": "multiple",
    "dscr_std": "multiple",
    "dscr_threshold": "multiple",
    "llcr": "multiple",
    "plcr": "multiple",
    "equity_moic": "multiple",
    "equity_multiple": "multiple",
    "raw_dscr_series": "multiple",
    # Energy
    "grid_loss": "kwh",
    # Integer counts / indices
    "year": "count",
    "period": "count",
    "years_below_threshold": "count",
    "first_breach_year": "count",
    "last_breach_year": "count",
    "equity_covenant_locked_years": "count",
    "equity_debt_service_shortfall_years": "count",
}

_UNIT_SUFFIX_RULES: tuple[tuple[str, str], ...] = (
    ("_pct", "pct"),
    ("_usd", "usd"),
    ("_lkr", "lkr"),
    ("_mw", "mw"),
    ("_gwh", "gwh"),
    ("_kwh", "kwh"),
    ("_years", "years"),
)

#: Canonical openpyxl number formats keyed by unit identifier.
UNIT_EXCEL_NUMBER_FORMATS: Mapping[str, str] = {
    "pct": "0.00%",
    "usd": '$#,##0;-$#,##0;"$0"',
    "lkr": '"LKR "#,##0;-"LKR "#,##0;"LKR 0"',
    "lkr_per_usd": "#,##0.00",
    "mw": '#,##0.0" MW"',
    "gwh": '#,##0.1" GWh"',
    "kwh": '#,##0" kWh"',
    "years": '0.0" years"',
    "multiple": '0.00"x"',
    "count": "#,##0",
}

_HOLD_WITHDRAWAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "hold withdrawal claim",
        re.compile(
            r"\bhold\b[^.?!\n]{0,40}\b"
            r"(?:lifted|withdrawn|cleared|removed|waived|superseded|suspended|revoked|overridden)\b"
            r"|\b(?:lift|lifts|lifted|lifting|withdraw|withdraws|withdrew|withdrawn|withdrawing|"
            r"clear|clears|cleared|clearing|waive|waives|waived|waiving|"
            r"supersede|supersedes|superseded|superseding|"
            r"override|overrides|overrode|overridden|overriding|"
            r"revoke|revokes|revoked|revoking)\b[^.?!\n]{0,30}\bhold\b",
            re.IGNORECASE,
        ),
    ),
    (
        "non-reliance withdrawal claim",
        re.compile(
            r"\bnon[-\s_]+reliance[\s_-]+(?:lifted|withdrawn|cleared|waived|superseded|removed|revoked)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "approval or reliance qualification claim",
        re.compile(
            r"\bapproved[\s_-]+for\b"
            r"|\b(?:lender|dfi|investment|bank|credit|covenant)[\s_-]+grade\b"
            r"|\bbankab(?:le|ility)\b"
            r"|\b(?:lender|covenant|board|ic|credit|audit|external|official|formal)[\s_-]+reliance\b"
            r"|\breliance[\s_-]+(?:granted|approved|authorized|authorised|permitted|confirmed|restored)\b"
            r"|\b(?:fit|cleared|certified|qualified|usable|suitable|valid)[\s_-]+for[\s_-]+"
            r"(?:lender|covenant|board|ic|credit)\b"
            r"|\bfor[\s_-]+(?:lender|covenant|board|ic|credit)[\s_-]+"
            r"(?:use|purposes|reliance|reporting|submission)\b"
            r"|\b(?:f[\s_-]?5|covenant)[\s_-]+(?:cleared|waived|lifted|satisfied|approved|compliant)\b",
            re.IGNORECASE,
        ),
    ),
)

_ALLOWED_NON_RELIANCE_EXEMPT_PHRASE = re.compile(
    r"\bno\s+(?:lender|covenant|board|ic)\s+reliance\b"
    r"|\bnot\s+for\s+(?:lender|covenant|board|ic)\s+(?:or\s+\w+\s+)?reliance\b"
    r"|\bsupport\s+no\s+covenant,\s+lender\s+or\s+ic\b"
    r"|\bno\s+quarterly\s+cfads\s+or\s+intra-year\s+dscr\s+figure\s+may\s+be\s+used\s+for\s+covenant\s+purposes\b"
    r"|\bnot\s+the\s+utility-accepted\s+bankable\b"
    r"|\bthe\s+bankable\s+connection\s+study\s+is\b"
    r"|\bnon[-\s_]+bankable\b"
    r"|\bbankable\s*=\s*false\b",
    re.IGNORECASE,
)


def run_identity(manifest: Optional[Mapping[str, Any]], surface: str) -> Dict[str, Any]:
    """Return the run-identity fields of one surface's manifest.

    Raises:
        ValueError: The surface carries no manifest, or omits one of
            ``config_sha256``, ``engine_version``, ``git_sha``, ``generated_at`` and
            ``manifest_schema_version``.
    """
    if not isinstance(manifest, Mapping):
        raise ValueError(f"{surface}: no run manifest")
    missing = [key for key in _REQUIRED_FIELDS if not manifest.get(key)]
    if missing:
        raise ValueError(f"{surface}: run manifest lacks {', '.join(missing)}")
    return {key: manifest.get(key) for key in RUN_IDENTITY_FIELDS}


def require_same_run_identity(
    manifests: Mapping[str, Optional[Mapping[str, Any]]],
) -> Dict[str, Any]:
    """Refuse outputs that do not carry one and the same run identity.

    Args:
        manifests: Each surface's manifest, keyed by surface name.

    Returns:
        The shared identity.

    Raises:
        ValueError: Fewer than two surfaces, a surface without its identity, or two
            surfaces that disagree. The message names every disagreeing field.
    """
    if len(manifests) < 2:
        raise ValueError("a run-identity comparison needs at least two surfaces")
    identities = {name: run_identity(m, name) for name, m in manifests.items()}
    names = list(identities)
    reference = identities[names[0]]
    problems = []
    for key in RUN_IDENTITY_FIELDS:
        values = {name: identities[name][key] for name in names}
        if any(value != reference[key] for value in values.values()):
            problems.append(
                f"{key}: "
                + ", ".join(f"{name}={value!r}" for name, value in values.items())
            )
    if problems:
        raise ValueError(
            "the outputs do not carry one run identity: " + "; ".join(problems)
        )
    return reference


def metric_unit(key: str) -> Optional[str]:
    """Return the canonical unit identifier for a KPI or schedule column key."""
    if key in KPI_UNIT_CONTRACTS:
        return KPI_UNIT_CONTRACTS[key]
    for suffix, unit in _UNIT_SUFFIX_RULES:
        if key.endswith(suffix):
            return unit
    if "dscr" in key:
        return "multiple"
    return None


def excel_number_format(key: str) -> Optional[str]:
    """Return the canonical openpyxl ``number_format`` string for ``key``, or ``None``."""
    unit = metric_unit(key)
    if unit is None:
        return None
    return UNIT_EXCEL_NUMBER_FORMATS.get(unit)


def validate_display_matches_unit(
    key: str,
    unit: Optional[str],
    value: Any,
    display: str,
    *,
    surface: str = "surface",
) -> None:
    """Verify that a formatted display string matches the metric's declared unit contract.

    Raises:
        ValueError: Missing unit, unknown unit, or a display string whose suffix/prefix
            disagrees with the unit contract.
    """
    if not unit or unit not in UNIT_EXCEL_NUMBER_FORMATS:
        raise ValueError(
            f"{surface}: metric {key!r} has missing or unsupported unit {unit!r}"
        )
    if value is None and display in ("undefined", "—", ""):
        return
    if unit == "pct" and not display.endswith("%"):
        raise ValueError(
            f"{surface}: pct metric {key!r} display {display!r} must end with '%'"
        )
    if unit == "multiple" and not display.endswith("x"):
        raise ValueError(
            f"{surface}: multiple metric {key!r} display {display!r} must end with 'x'"
        )
    if unit == "usd" and not (display.startswith("$") or display.startswith("-$")):
        raise ValueError(
            f"{surface}: usd metric {key!r} display {display!r} must carry '$' accounting sign"
        )
    if unit == "lkr" and "LKR" not in display:
        raise ValueError(
            f"{surface}: lkr metric {key!r} display {display!r} must carry 'LKR'"
        )
    if unit == "gwh" and not display.endswith("GWh"):
        raise ValueError(
            f"{surface}: gwh metric {key!r} display {display!r} must end with 'GWh'"
        )
    if unit == "mw" and not display.endswith("MW"):
        raise ValueError(
            f"{surface}: mw metric {key!r} display {display!r} must end with 'MW'"
        )
    if unit == "years" and "year" not in display.lower():
        raise ValueError(
            f"{surface}: years metric {key!r} display {display!r} must mention years"
        )


def require_unit_contracts_aligned(
    surface_units: Mapping[str, Mapping[str, Optional[str]]],
) -> Dict[str, str]:
    """Refuse outputs whose declared unit contracts disagree or are missing.

    Args:
        surface_units: Mapping of ``surface_name -> {metric_key: unit}``.

    Returns:
        The verified shared ``{metric_key: unit}`` mapping.

    Raises:
        ValueError: Fewer than two surfaces, missing/empty unit mapping, unknown unit, or
            any cross-surface unit mismatch.
    """
    if len(surface_units) < 2:
        raise ValueError("a unit-contract comparison needs at least two surfaces")
    names = list(surface_units)
    for name in names:
        if not surface_units[name]:
            raise ValueError(f"{name}: no unit contracts declared")
    all_keys = sorted({k for mapping in surface_units.values() for k in mapping})
    resolved: Dict[str, str] = {}
    problems: list[str] = []
    for key in all_keys:
        per_surface = {name: surface_units[name].get(key) for name in names}
        non_null = {
            name: unit for name, unit in per_surface.items() if unit is not None
        }
        if len(non_null) != len(names):
            problems.append(
                f"{key}: missing on "
                + ", ".join(name for name, unit in per_surface.items() if unit is None)
            )
            continue
        unique_units = set(non_null.values())
        if len(unique_units) != 1:
            problems.append(
                f"{key}: "
                + ", ".join(f"{name}={unit!r}" for name, unit in per_surface.items())
            )
            continue
        unit = next(iter(unique_units))
        if unit not in UNIT_EXCEL_NUMBER_FORMATS:
            problems.append(f"{key}: unsupported unit {unit!r}")
            continue
        resolved[key] = unit
    if problems:
        raise ValueError(
            "unit contract mismatch across surfaces: " + "; ".join(problems)
        )
    return resolved


def validate_section_disposition(section: str, disposition: str) -> str:
    """Validate that ``disposition`` belongs to :data:`SECTION_DISPOSITIONS`."""
    if disposition not in _SECTION_DISPOSITION_SET:
        allowed = ", ".join(SECTION_DISPOSITIONS)
        raise ValueError(
            f"section {section!r} has invalid disposition {disposition!r}; "
            f"expected one of: {allowed}"
        )
    return disposition


def require_consistent_section_dispositions(
    dispositions_by_surface: Mapping[str, Mapping[str, str]],
    *,
    allow_surface_omissions: Optional[Mapping[str, AbstractSet[str]]] = None,
) -> Dict[str, str]:
    """Refuse invalid or contradictory section dispositions across surfaces.

    ``omitted`` on a surface is accepted only for sections listed in
    ``allow_surface_omissions[surface]`` (e.g., heavy out-of-band blocks omitted on the
    synchronous API route). Every other disagreement — such as ``computed`` vs
    ``allocated``, ``computed`` vs ``not_run``, or an unpermitted omission — fails loudly.
    """
    if len(dispositions_by_surface) < 2:
        raise ValueError("a section-disposition comparison needs at least two surfaces")
    allowed_omissions = allow_surface_omissions or {}
    names = list(dispositions_by_surface)
    for name in names:
        for section, disposition in dispositions_by_surface[name].items():
            validate_section_disposition(f"{name}.{section}", disposition)

    all_sections = sorted(
        {sec for mapping in dispositions_by_surface.values() for sec in mapping}
    )
    canonical: Dict[str, str] = {}
    problems: list[str] = []
    for section in all_sections:
        per_surface = {
            name: dispositions_by_surface[name].get(section) for name in names
        }
        missing = [name for name, disp in per_surface.items() if disp is None]
        if missing:
            problems.append(f"{section}: missing on {', '.join(missing)}")
            continue
        active: Dict[str, str] = {
            name: disp
            for name, disp in per_surface.items()
            if disp is not None
            and not (disp == "omitted" and section in allowed_omissions.get(name, ()))
        }
        if not active:
            canonical[section] = "omitted"
            continue
        unique_active = set(active.values())
        if len(unique_active) != 1:
            problems.append(
                f"{section}: "
                + ", ".join(f"{name}={disp!r}" for name, disp in per_surface.items())
            )
            continue
        canonical[section] = next(iter(unique_active))
    if problems:
        raise ValueError(
            "section disposition mismatch across surfaces: " + "; ".join(problems)
        )
    return canonical


def check_no_hold_withdrawal(text: str, surface: str) -> None:
    """Refuse hold-withdrawal or false bankability/lender-reliance wording on a surface."""
    sanitized = _ALLOWED_NON_RELIANCE_EXEMPT_PHRASE.sub(" ", text)
    for category, pattern in _HOLD_WITHDRAWAL_PATTERNS:
        match = pattern.search(sanitized)
        if match is not None:
            raise ValueError(
                f"{surface}: contains forbidden {category} {match.group(0)!r} "
                "contradicting the active HOLD union (F-5, #1110, v15.6.1)"
            )


def require_reliance_labels(
    surface_reliance: Mapping[str, Mapping[str, Any]],
    *,
    require_f5: bool = True,
    require_synthetic_grid_screening: bool = False,
    require_allocated_covenant_distinction: bool = False,
) -> None:
    """Enforce consistent F-5, synthetic-grid, and allocated-vs-covenant reliance labels.

    Each surface entry expects:
    - ``reliance_label``: one of :data:`RELIANCE_LABELS`
    - ``notice``: non-empty reliance/hold notice text carrying ``F-5``, ``#1110``, ``v15.6.1``
    - optional ``synthetic_grid_screening_only`` (bool) & ``synthetic_grid_notice`` (str)
    - optional ``allocated_covenant_distinct`` (bool) & ``covenant_distinction_notice`` (str)
    """
    if not surface_reliance:
        raise ValueError("reliance verification requires at least one surface")
    for surface, payload in surface_reliance.items():
        if not isinstance(payload, Mapping):
            raise ValueError(f"{surface}: invalid reliance payload")
        label = payload.get("reliance_label")
        if label not in _RELIANCE_LABEL_SET:
            raise ValueError(
                f"{surface}: invalid reliance_label {label!r}; "
                f"expected one of {', '.join(RELIANCE_LABELS)}"
            )
        notice = payload.get("notice")
        if not isinstance(notice, str) or not notice.strip():
            raise ValueError(f"{surface}: missing non-reliance notice")
        check_no_hold_withdrawal(notice, surface)
        if require_f5:
            missing_tokens = [tok for tok in HOLD_UNION if tok not in notice]
            if missing_tokens:
                raise ValueError(
                    f"{surface}: reliance notice lacks HOLD token(s) "
                    f"{', '.join(missing_tokens)}"
                )
            if (
                "non-reliance" not in notice.lower()
                and "no lender reliance" not in notice.lower()
            ):
                raise ValueError(
                    f"{surface}: reliance notice must explicitly state non-reliance"
                )
        if require_synthetic_grid_screening:
            if payload.get("synthetic_grid_screening_only") is not True:
                raise ValueError(
                    f"{surface}: synthetic grid output is not marked screening-only"
                )
            grid_notice = str(payload.get("synthetic_grid_notice") or "")
            check_no_hold_withdrawal(grid_notice, f"{surface}.synthetic_grid_notice")
            lowered = grid_notice.lower()
            if "screening" not in lowered or (
                "non-bankable" not in lowered and "not bankable" not in lowered
            ):
                raise ValueError(
                    f"{surface}: synthetic grid notice must disclose screening-only / non-bankable status"
                )
        if require_allocated_covenant_distinction:
            if payload.get("allocated_covenant_distinct") is not True:
                raise ValueError(
                    f"{surface}: allocated within-year figures are not distinguished from approved covenant metrics"
                )
            cov_notice = str(payload.get("covenant_distinction_notice") or notice)
            lowered_cov = cov_notice.lower()
            if "covenant" not in lowered_cov or (
                "intra-year" not in lowered_cov
                and "within-year" not in lowered_cov
                and "allocated" not in lowered_cov
                and "sculpt" not in lowered_cov
            ):
                raise ValueError(
                    f"{surface}: covenant distinction notice must separate allocated/intra-year figures from approved annual covenant metrics"
                )


def verify_consumer_matrix(
    *,
    manifests: Mapping[str, Optional[Mapping[str, Any]]],
    units: Mapping[str, Mapping[str, Optional[str]]],
    dispositions: Mapping[str, Mapping[str, str]],
    reliance: Mapping[str, Mapping[str, Any]],
    allow_surface_omissions: Optional[Mapping[str, AbstractSet[str]]] = None,
    require_f5: bool = True,
    require_synthetic_grid_screening: bool = False,
    require_allocated_covenant_distinction: bool = False,
) -> Dict[str, Any]:
    """Verify full cross-surface parity for one run across identity, units, dispositions, and reliance."""
    shared_identity = require_same_run_identity(manifests)
    shared_units = require_unit_contracts_aligned(units)
    shared_dispositions = require_consistent_section_dispositions(
        dispositions, allow_surface_omissions=allow_surface_omissions
    )
    require_reliance_labels(
        reliance,
        require_f5=require_f5,
        require_synthetic_grid_screening=require_synthetic_grid_screening,
        require_allocated_covenant_distinction=require_allocated_covenant_distinction,
    )
    return {
        "run_identity": shared_identity,
        "shared_units": shared_units,
        "shared_dispositions": shared_dispositions,
        "surfaces_verified": sorted(manifests),
    }


__all__ = [
    "F5_NON_RELIANCE_NOTICE",
    "HOLD_UNION",
    "KPI_UNIT_CONTRACTS",
    "RELIANCE_LABELS",
    "RUN_IDENTITY_FIELDS",
    "SECTION_DISPOSITIONS",
    "UNIT_EXCEL_NUMBER_FORMATS",
    "check_no_hold_withdrawal",
    "excel_number_format",
    "metric_unit",
    "require_consistent_section_dispositions",
    "require_reliance_labels",
    "require_same_run_identity",
    "require_unit_contracts_aligned",
    "run_identity",
    "validate_display_matches_unit",
    "validate_section_disposition",
    "verify_consumer_matrix",
]
