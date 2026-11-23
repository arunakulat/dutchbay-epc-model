"""Tariff legal status: what each rate a scenario prices rests on (#1837).

Reads ``conf/tariff_legal_status.yaml``, the one shared registry of the tariffs scenarios
price, and resolves the record for one scenario. Every rate in the registry carries a
``status`` (``published``, ``analogy_unpublished`` or ``unconfirmed``), the instrument and
clause that set it, and its effective window. The reader is strict: an unknown key, a missing
key, a rate without a status, an unknown status, a malformed date, a reference to a rate or
source that does not exist, or a cited source whose PDF hash differs from the one its config
pins is an error that names the path (``FRAMEWORK-02``).

Nothing here holds a site name, a rate or a date (``ARCH-01``): every value comes from the
registry and the scenario. A scenario the registry does not list resolves to
:data:`STATUS_NOT_RECORDED`, which reports say plainly; it is never treated as published.

This is labelling, not a legal opinion, and it never changes a tariff value or a KPI.
"""

from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The shared registry.
REGISTRY_PATH = Path("conf") / "tariff_legal_status.yaml"
REGISTRY_SCHEMA = "tariff_legal_status_v1"

STATUS_PUBLISHED = "published"
STATUS_ANALOGY_UNPUBLISHED = "analogy_unpublished"
STATUS_UNCONFIRMED = "unconfirmed"
#: A recorded rate must carry one of these.
STATUSES: Tuple[str, ...] = (
    STATUS_PUBLISHED,
    STATUS_ANALOGY_UNPUBLISHED,
    STATUS_UNCONFIRMED,
)
#: Not a registry value: what a scenario the registry does not list resolves to.
STATUS_NOT_RECORDED = "not_recorded"
#: Not a registry value: the scenario's tariff differs from the rate the registry names.
STATUS_MISMATCH = "mismatch"

#: Statuses that must be printed beside every figure built on the rate.
LABELLED_STATUSES: Tuple[str, ...] = (
    STATUS_ANALOGY_UNPUBLISHED,
    STATUS_UNCONFIRMED,
    STATUS_NOT_RECORDED,
    STATUS_MISMATCH,
)

#: How each status reads in a report.
STATUS_LABELS: Dict[str, str] = {
    STATUS_PUBLISHED: "Published",
    STATUS_ANALOGY_UNPUBLISHED: "Analogy, unpublished",
    STATUS_UNCONFIRMED: "Unconfirmed",
    STATUS_NOT_RECORDED: "Legal status not recorded",
    STATUS_MISMATCH: "Does not match the recorded rate",
}

#: Use keys a scenario entry may declare.
USE_HEADLINE_REVENUE = "headline_revenue"
USE_STORAGE_OPTIONS = "storage_options"

#: Relative tolerance when matching a scenario's tariff with a recorded rate.
_RATE_RTOL = 1e-9


class TariffLegalStatusError(ValueError):
    """The registry is malformed. The message lists every problem, each with its path."""


@dataclass(frozen=True)
class TariffRate:
    """One recorded rate."""

    rate_id: str
    status: str
    lkr_per_kwh: Optional[float]
    instrument: str
    clause: str
    source: str
    effective_from: Optional[_dt.date]
    effective_to: Optional[_dt.date]
    effective_note: Optional[str] = None
    review: Optional[str] = None
    conditions: Tuple[str, ...] = ()
    open_questions: Tuple[str, ...] = ()

    @property
    def label(self) -> str:
        """The status as a report prints it."""
        return STATUS_LABELS[self.status]

    @property
    def needs_label(self) -> bool:
        """Whether every figure built on this rate must print its status beside it."""
        return self.status in LABELLED_STATUSES

    def window_text(self) -> str:
        """The effective window in words, from the recorded dates and their quotes."""
        start = (
            f"from {self.effective_from.isoformat()}"
            if self.effective_from is not None
            else f"start: {self.effective_note}"
        )
        end = (
            f"to {self.effective_to.isoformat()}"
            if self.effective_to is not None
            else (self.review or "no end date recorded")
        )
        return f"{start}, {end}"


@dataclass(frozen=True)
class RevenueUse:
    """One revenue figure set and the rate it rests on."""

    use: str
    rate_id: Optional[str]
    status: str
    detail: str
    rate: Optional[TariffRate] = None

    @property
    def label(self) -> str:
        """The status as a report prints it."""
        return STATUS_LABELS[self.status]

    @property
    def needs_label(self) -> bool:
        """Whether every figure in this use must print its status beside it."""
        return self.status in LABELLED_STATUSES


@dataclass(frozen=True)
class ScenarioTariffStatus:
    """What one scenario's revenue rests on, and any effective-window flags."""

    scenario: str
    recorded: bool
    headline: RevenueUse
    storage_options: Dict[str, RevenueUse] = field(default_factory=dict)
    window_flags: Tuple[str, ...] = ()
    cod_year: Optional[int] = None
    signing_date: Optional[_dt.date] = None

    @property
    def rates(self) -> List[TariffRate]:
        """Every distinct recorded rate the scenario uses, headline first."""
        seen: Dict[str, TariffRate] = {}
        for use in [self.headline, *self.storage_options.values()]:
            if use.rate is not None and use.rate.rate_id not in seen:
                seen[use.rate.rate_id] = use.rate
        return list(seen.values())

    def storage_label(self, basis: Optional[str]) -> Optional[RevenueUse]:
        """The status of one storage-options revenue basis, if the scenario records it."""
        if basis is None:
            return None
        return self.storage_options.get(str(basis))


def _use_summary(use: RevenueUse) -> Dict[str, Any]:
    """One revenue use in strict JSON-ready form, for a committed site-analysis summary."""
    rate = use.rate
    return {
        "use": use.use,
        "rate_id": use.rate_id,
        "lkr_per_kwh": rate.lkr_per_kwh if rate is not None else None,
        "status": use.status,
        "status_label": use.label,
        "needs_label": use.needs_label,
        "instrument": rate.instrument if rate is not None else None,
        "clause": rate.clause if rate is not None else use.detail,
        "source": rate.source if rate is not None else None,
        "effective_from": (
            rate.effective_from.isoformat()
            if rate is not None and rate.effective_from is not None
            else None
        ),
        "effective_to": (
            rate.effective_to.isoformat()
            if rate is not None and rate.effective_to is not None
            else None
        ),
        "effective_note": rate.effective_note if rate is not None else None,
        "review": rate.review if rate is not None else None,
        "window": rate.window_text() if rate is not None else None,
        "conditions": list(rate.conditions) if rate is not None else [],
        "open_questions": list(rate.open_questions) if rate is not None else [],
    }


def storage_options_tariff_legal_status(
    scenario: Mapping[str, Any],
    scenario_name: str,
    bases: Sequence[str],
    registry: Optional[TariffRegistry] = None,
) -> Dict[str, Any]:
    """Machine-readable tariff legal status for a storage-options summary (#1837).

    Records the scenario's headline revenue rate status alongside the legal status of each
    storage-options revenue basis ``bases`` evaluates, plus any effective-window flags. An
    unrecorded basis resolves to :data:`STATUS_NOT_RECORDED` (never published).
    """
    status = resolve_scenario_status(scenario, scenario_name, registry)
    basis_entries: Dict[str, Dict[str, Any]] = {}
    for basis in bases:
        key = str(basis)
        use = status.storage_label(key) or RevenueUse(
            use=f"{USE_STORAGE_OPTIONS}.{key}",
            rate_id=None,
            status=STATUS_NOT_RECORDED,
            detail=(
                f"no legal status is recorded for the revenue basis {key} of this scenario "
                f"in {REGISTRY_PATH.as_posix()}"
            ),
        )
        basis_entries[key] = _use_summary(use)
    return {
        "registry": REGISTRY_PATH.as_posix(),
        "scenario": status.scenario,
        "recorded": status.recorded,
        "headline_revenue": _use_summary(status.headline),
        "revenue_bases": basis_entries,
        "window_flags": list(status.window_flags),
    }


# --------------------------------------------------------------------------- reading


def _date(value: Any, path: str, errors: List[str]) -> Optional[_dt.date]:
    if value is None:
        return None
    if isinstance(value, _dt.date) and not isinstance(value, _dt.datetime):
        return value
    if isinstance(value, str):
        try:
            return _dt.date.fromisoformat(value)
        except ValueError:
            pass
    errors.append(f"{path}: expected an ISO date (YYYY-MM-DD) or null, got {value!r}")
    return None


def _text(value: Any, path: str, errors: List[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: expected non-empty text")
        return ""
    return value


def _texts(value: Any, path: str, errors: List[str]) -> Tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        errors.append(f"{path}: expected a list of text")
        return ()
    return tuple(_text(v, f"{path}[{i}]", errors) for i, v in enumerate(value))


def _keys(
    node: Mapping[str, Any],
    path: str,
    required: Sequence[str],
    optional: Sequence[str],
    errors: List[str],
) -> None:
    for key in required:
        if key not in node:
            errors.append(f"{path}.{key}: required")
    for key in node:
        if key not in required and key not in optional:
            errors.append(f"{path}.{key}: unknown key")


_SOURCE_REQUIRED = ("pdf_sha256",)
_SOURCE_OPTIONAL = (
    "title",
    "publisher",
    "url",
    "read_with",
    "verbatim",
    "note",
    "cited_in",
)
_RATE_REQUIRED = (
    "status",
    "lkr_per_kwh",
    "instrument",
    "clause",
    "source",
    "effective_from",
    "effective_to",
)
_RATE_OPTIONAL = (
    "components_lkr_per_kwh",
    "effective_from_source",
    "effective_note",
    "review",
    "review_source",
    "conditions",
    "open_questions",
)


def _check_cited_pin(
    sid: str, sha: Any, cited: str, path: str, errors: List[str]
) -> None:
    """A source cited from another config must carry the PDF hash that config pins."""
    try:
        with open(REPO_ROOT / cited, encoding="utf-8") as handle:
            other = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError):
        other = None
    pinned = None
    if isinstance(other, Mapping):
        node = (other.get("sources") or {}).get(sid)
        if isinstance(node, Mapping):
            pinned = node.get("pdf_sha256")
    if pinned is None:
        errors.append(f"{path}.cited_in: {cited} pins no pdf_sha256 for {sid}")
    elif pinned != sha:
        errors.append(f"{path}.pdf_sha256: differs from the hash {cited} pins")


def _read_sources(raw: Any, errors: List[str]) -> Dict[str, Mapping[str, Any]]:
    if not isinstance(raw, Mapping) or not raw:
        errors.append("sources: expected a non-empty mapping")
        return {}
    for sid, node in raw.items():
        path = f"sources.{sid}"
        if not isinstance(node, Mapping):
            errors.append(f"{path}: expected a mapping")
            continue
        _keys(node, path, _SOURCE_REQUIRED, _SOURCE_OPTIONAL, errors)
        sha = node.get("pdf_sha256")
        if not (
            isinstance(sha, str)
            and len(sha) == 64
            and all(c in "0123456789abcdef" for c in sha)
        ):
            errors.append(f"{path}.pdf_sha256: expected 64 lowercase hex characters")
        if "cited_in" in node:
            cited = node["cited_in"]
            if not isinstance(cited, str) or not (REPO_ROOT / cited).is_file():
                errors.append(
                    f"{path}.cited_in: not a file in the repository: {cited!r}"
                )
            else:
                _check_cited_pin(str(sid), sha, cited, path, errors)
        elif not node.get("url") or not node.get("verbatim"):
            errors.append(
                f"{path}: a source not cited from another config needs url and verbatim"
            )
        _texts(node.get("verbatim"), f"{path}.verbatim", errors)
    return dict(raw)


def _read_rate(
    rid: str, node: Any, sources: Mapping[str, Any], errors: List[str]
) -> Optional[TariffRate]:
    path = f"rates.{rid}"
    if not isinstance(node, Mapping):
        errors.append(f"{path}: expected a mapping")
        return None
    _keys(node, path, _RATE_REQUIRED, _RATE_OPTIONAL, errors)
    status = node.get("status")
    if status not in STATUSES:
        errors.append(
            f"{path}.status: expected one of {list(STATUSES)}, got {status!r}"
        )
    value = node.get("lkr_per_kwh")
    rate_value: Optional[float] = None
    if value is not None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{path}.lkr_per_kwh: expected a number or null")
        elif not math.isfinite(float(value)) or float(value) <= 0:
            errors.append(f"{path}.lkr_per_kwh: expected a positive number")
        else:
            rate_value = float(value)
    elif status == STATUS_PUBLISHED:
        errors.append(f"{path}.lkr_per_kwh: a published rate states its value")
    comps = node.get("components_lkr_per_kwh")
    if comps is not None:
        if not (
            isinstance(comps, list)
            and comps
            and all(
                isinstance(c, (int, float)) and not isinstance(c, bool) for c in comps
            )
        ):
            errors.append(f"{path}.components_lkr_per_kwh: expected a list of numbers")
        elif rate_value is not None and not math.isclose(
            sum(float(c) for c in comps), rate_value, rel_tol=1e-9, abs_tol=1e-9
        ):
            errors.append(
                f"{path}.components_lkr_per_kwh: the components sum to "
                f"{sum(float(c) for c in comps)!r}, not lkr_per_kwh {rate_value!r}"
            )
    for key in ("source", "effective_from_source", "review_source"):
        sid = node.get(key)
        if sid is not None and sid not in sources:
            errors.append(f"{path}.{key}: unknown source {sid!r}")
    start = _date(node.get("effective_from"), f"{path}.effective_from", errors)
    end = _date(node.get("effective_to"), f"{path}.effective_to", errors)
    if start is None and not node.get("effective_note"):
        errors.append(
            f"{path}.effective_note: required when effective_from is null "
            "(quote why the source states no date)"
        )
    if end is None and not node.get("review"):
        errors.append(
            f"{path}.review: required when effective_to is null "
            "(quote what ends the rate)"
        )
    if start is not None and end is not None and end < start:
        errors.append(f"{path}.effective_to: before effective_from")
    return TariffRate(
        rate_id=str(rid),
        status=str(status) if status in STATUSES else STATUS_UNCONFIRMED,
        lkr_per_kwh=rate_value,
        instrument=_text(node.get("instrument"), f"{path}.instrument", errors),
        clause=_text(node.get("clause"), f"{path}.clause", errors),
        source=str(node.get("source")),
        effective_from=start,
        effective_to=end,
        effective_note=node.get("effective_note"),
        review=node.get("review"),
        conditions=_texts(node.get("conditions"), f"{path}.conditions", errors),
        open_questions=_texts(
            node.get("open_questions"), f"{path}.open_questions", errors
        ),
    )


@dataclass(frozen=True)
class TariffRegistry:
    """The parsed registry."""

    rates: Dict[str, TariffRate]
    scenarios: Dict[str, Mapping[str, Any]]


def read_registry(data: Mapping[str, Any]) -> TariffRegistry:
    """Check and parse a registry already loaded from YAML.

    Raises:
        TariffLegalStatusError: Listing every problem found, each with its path.
    """
    errors: List[str] = []
    if not isinstance(data, Mapping):
        raise TariffLegalStatusError("registry: expected a mapping")
    _keys(
        data,
        "registry",
        ("schema_version", "retrieved", "sources", "rates", "scenarios"),
        (),
        errors,
    )
    if data.get("schema_version") != REGISTRY_SCHEMA:
        errors.append(
            f"schema_version: expected {REGISTRY_SCHEMA!r}, "
            f"got {data.get('schema_version')!r}"
        )
    _date(data.get("retrieved"), "retrieved", errors)
    sources = _read_sources(data.get("sources"), errors)
    raw_rates = data.get("rates")
    rates: Dict[str, TariffRate] = {}
    if not isinstance(raw_rates, Mapping) or not raw_rates:
        errors.append("rates: expected a non-empty mapping")
    else:
        for rid, node in raw_rates.items():
            rate = _read_rate(str(rid), node, sources, errors)
            if rate is not None:
                rates[str(rid)] = rate
    raw_scen = data.get("scenarios")
    scenarios: Dict[str, Mapping[str, Any]] = {}
    if not isinstance(raw_scen, Mapping):
        errors.append("scenarios: expected a mapping")
    else:
        for name, node in raw_scen.items():
            path = f"scenarios.{name}"
            if not isinstance(node, Mapping):
                errors.append(f"{path}: expected a mapping")
                continue
            _keys(node, path, (USE_HEADLINE_REVENUE,), (USE_STORAGE_OPTIONS,), errors)
            if node.get(USE_HEADLINE_REVENUE) not in rates:
                errors.append(
                    f"{path}.{USE_HEADLINE_REVENUE}: unknown rate "
                    f"{node.get(USE_HEADLINE_REVENUE)!r}"
                )
            storage = node.get(USE_STORAGE_OPTIONS)
            if storage is not None:
                if not isinstance(storage, Mapping) or not storage:
                    errors.append(
                        f"{path}.{USE_STORAGE_OPTIONS}: expected a non-empty mapping"
                    )
                else:
                    for basis, rid in storage.items():
                        if rid not in rates:
                            errors.append(
                                f"{path}.{USE_STORAGE_OPTIONS}.{basis}: unknown rate {rid!r}"
                            )
            scenarios[str(name)] = node
    if errors:
        raise TariffLegalStatusError(
            "conf/tariff_legal_status.yaml is invalid:\n  " + "\n  ".join(errors)
        )
    return TariffRegistry(rates=rates, scenarios=scenarios)


def load_registry(path: Optional[Path] = None) -> TariffRegistry:
    """Load and check the shared registry (``conf/tariff_legal_status.yaml``)."""
    target = path if path is not None else REPO_ROOT / REGISTRY_PATH
    with open(target, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return read_registry(data)


# --------------------------------------------------------------------------- resolving


def _scenario_tariff(scenario: Mapping[str, Any]) -> Optional[float]:
    tariff = scenario.get("tariff")
    if not isinstance(tariff, Mapping):
        return None
    value = tariff.get("lkr_per_kwh")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _scenario_dates(
    scenario: Mapping[str, Any],
) -> Tuple[Optional[int], Optional[_dt.date]]:
    project = scenario.get("project")
    cod: Optional[int] = None
    if isinstance(project, Mapping):
        raw = project.get("cod_year")
        if isinstance(raw, int) and not isinstance(raw, bool):
            cod = raw
    signing: Optional[_dt.date] = None
    ppa = scenario.get("ppa")
    if isinstance(ppa, Mapping) and ppa.get("signing_date") is not None:
        raw_date = ppa.get("signing_date")
        if isinstance(raw_date, _dt.date):
            signing = raw_date
        else:
            try:
                signing = _dt.date.fromisoformat(str(raw_date))
            except ValueError:
                signing = None
    return cod, signing


def window_flags(
    rates: Sequence[TariffRate],
    *,
    cod_year: Optional[int],
    signing_date: Optional[_dt.date],
) -> Tuple[str, ...]:
    """Say where the scenario's assumed signing date or COD falls outside a rate's window.

    COD is compared as a year: it is outside a window that ends before 1 January of that
    year or starts after 31 December of it.
    """
    flags: List[str] = []
    for rate in rates:
        start, end = rate.effective_from, rate.effective_to
        if signing_date is not None:
            if start is not None and signing_date < start:
                flags.append(
                    f"{rate.rate_id}: the assumed SPPA signing date "
                    f"{signing_date.isoformat()} is before the rate takes effect "
                    f"({start.isoformat()})."
                )
            if end is not None and signing_date > end:
                flags.append(
                    f"{rate.rate_id}: the assumed SPPA signing date "
                    f"{signing_date.isoformat()} is after the rate ends ({end.isoformat()})."
                )
        if cod_year is not None:
            if end is not None and end < _dt.date(cod_year, 1, 1):
                flags.append(
                    f"{rate.rate_id}: the scenario's COD year {cod_year} is after the rate "
                    f"ends ({end.isoformat()})."
                )
            if start is not None and start > _dt.date(cod_year, 12, 31):
                flags.append(
                    f"{rate.rate_id}: the scenario's COD year {cod_year} is before the rate "
                    f"takes effect ({start.isoformat()})."
                )
    return tuple(flags)


def resolve_scenario_status(
    scenario: Mapping[str, Any],
    scenario_name: str,
    registry: Optional[TariffRegistry] = None,
) -> ScenarioTariffStatus:
    """Resolve what one scenario's revenue rests on.

    Args:
        scenario: The scenario config as the run used it.
        scenario_name: The scenario file stem, the registry's key.
        registry: The registry; defaults to the shared one.

    Returns:
        The headline revenue's status (``not_recorded`` for an unlisted scenario, or
        ``mismatch`` when the scenario's tariff differs from the recorded rate), the status
        of each storage-options revenue basis, and any effective-window flags.
    """
    reg = registry if registry is not None else load_registry()
    cod, signing = _scenario_dates(scenario)
    entry = reg.scenarios.get(scenario_name)
    tariff = _scenario_tariff(scenario)
    if entry is None:
        headline = RevenueUse(
            use=USE_HEADLINE_REVENUE,
            rate_id=None,
            status=STATUS_NOT_RECORDED,
            detail=(
                "No legal status is recorded for this scenario's tariff "
                f"({'n/a' if tariff is None else f'{tariff:g} LKR/kWh'}) in "
                f"{REGISTRY_PATH.as_posix()}. Treat it as an assumption until it is."
            ),
        )
        return ScenarioTariffStatus(
            scenario=scenario_name,
            recorded=False,
            headline=headline,
            cod_year=cod,
            signing_date=signing,
        )
    rate = reg.rates[str(entry[USE_HEADLINE_REVENUE])]
    if (
        rate.lkr_per_kwh is not None
        and tariff is not None
        and not math.isclose(tariff, rate.lkr_per_kwh, rel_tol=_RATE_RTOL)
    ):
        headline = RevenueUse(
            use=USE_HEADLINE_REVENUE,
            rate_id=rate.rate_id,
            status=STATUS_MISMATCH,
            detail=(
                f"The scenario prices {tariff:g} LKR/kWh, but the recorded rate "
                f"{rate.rate_id} is {rate.lkr_per_kwh:g} LKR/kWh. Its status does not "
                "carry over to a different value."
            ),
            rate=rate,
        )
    else:
        headline = RevenueUse(
            use=USE_HEADLINE_REVENUE,
            rate_id=rate.rate_id,
            status=rate.status,
            detail=f"{rate.instrument}; {rate.clause}",
            rate=rate,
        )
    storage: Dict[str, RevenueUse] = {}
    for basis, rid in (entry.get(USE_STORAGE_OPTIONS) or {}).items():
        srate = reg.rates[str(rid)]
        storage[str(basis)] = RevenueUse(
            use=f"{USE_STORAGE_OPTIONS}.{basis}",
            rate_id=srate.rate_id,
            status=srate.status,
            detail=f"{srate.instrument}; {srate.clause}",
            rate=srate,
        )
    used = [headline.rate] if headline.rate is not None else []
    used += [u.rate for u in storage.values() if u.rate is not None]
    return ScenarioTariffStatus(
        scenario=scenario_name,
        recorded=True,
        headline=headline,
        storage_options=storage,
        window_flags=window_flags(
            [r for r in used if r is not None], cod_year=cod, signing_date=signing
        ),
        cod_year=cod,
        signing_date=signing,
    )


__all__ = [
    "LABELLED_STATUSES",
    "REGISTRY_PATH",
    "REGISTRY_SCHEMA",
    "STATUSES",
    "STATUS_ANALOGY_UNPUBLISHED",
    "STATUS_LABELS",
    "STATUS_MISMATCH",
    "STATUS_NOT_RECORDED",
    "STATUS_PUBLISHED",
    "STATUS_UNCONFIRMED",
    "RevenueUse",
    "ScenarioTariffStatus",
    "TariffLegalStatusError",
    "TariffRate",
    "TariffRegistry",
    "load_registry",
    "read_registry",
    "resolve_scenario_status",
    "storage_options_tariff_legal_status",
    "window_flags",
]
