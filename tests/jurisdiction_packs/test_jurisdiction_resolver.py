"""Tests for the jurisdiction pack resolver (#1843).

Fictionland (code ``FIC``) is the synthetic jurisdiction the feasibility contract tests
already use. Its values here are invented and carry no meaning for any real project.
"""

from __future__ import annotations

import ast
import copy
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from analytics.feasibility_report_contract.project_case import (
    JurisdictionBinding,
    JurisdictionSubject,
)
from analytics.jurisdiction_packs import JurisdictionPack
from analytics.jurisdiction_packs.resolver import (
    ConflictKind,
    DirectoryPackSource,
    InMemoryPackSource,
    JurisdictionRefusal,
    JurisdictionResolution,
    ProjectOverride,
    RefusalReason,
    SubjectDisposition,
    ValueOrigin,
    resolve,
)

REPO = Path(__file__).resolve().parents[2]
LENDER_CASE = REPO / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
RESOLVER = REPO / "analytics" / "jurisdiction_packs" / "resolver.py"
LK_PACK_ID = "dutchbay.jurisdiction.lk"
FIC_PACK_ID = "test.jurisdiction.fic"
TAX = JurisdictionSubject.TAX
CONTRACT = JurisdictionSubject.CONTRACT


def _binding(
    subject: JurisdictionSubject,
    *,
    code: str = "LK",
    pack_id: str = LK_PACK_ID,
    version: str = "1.0.0",
    support: str = "declared",
    binding_id: Optional[str] = None,
) -> JurisdictionBinding:
    return JurisdictionBinding.model_validate_json(
        json.dumps(
            {
                "binding_id": binding_id or f"jb:{code.lower()}:{subject.value}",
                "jurisdiction_code": code,
                "subject": subject.value,
                "support_status": support,
                "contract_pack_id": pack_id,
                "contract_pack_version": version,
            }
        )
    )


def _parameter(
    parameter_id: str,
    scenario_key: str,
    value: Any,
    unit: str,
    effective_from: str,
    *,
    subject: str = "tax",
    effective_to: Optional[str] = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "parameter_id": parameter_id,
        "subject": subject,
        "scenario_key": scenario_key,
        "value": value,
        "unit": unit,
        "effective_from": effective_from,
        "effective_from_basis": "in_force_by",
        "recorded_at": "2026-11-21",
        "status": "unconfirmed",
        "sources": [
            {
                "instrument": "Fictionland Revenue Code (synthetic)",
                "repository_record": "tests/jurisdiction_packs (synthetic fixture)",
            }
        ],
    }
    if effective_to is not None:
        entry["effective_to"] = effective_to
    return entry


def _fic_data(**pack_fields: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema_id": "dutchbay.jurisdiction_pack.v1",
        "pack_id": FIC_PACK_ID,
        "kind": "jurisdiction",
        "version": "1.0.0",
        "jurisdiction_code": "FIC",
        "jurisdiction_name": "Fictionland (synthetic test jurisdiction)",
        "status": "supported",
        "owner": "tests",
        "effective_date": "2026-11-21",
        "review_date": "2027-11-21",
        "limitations": ["Synthetic: carries no real law."],
        "prohibited_substitutions": ["Never use for a real project."],
        "parameters": [
            _parameter(
                "fic.cit.rate",
                "tax.corporate_tax_rate",
                0.20,
                "fraction",
                "2020-01-01",
                effective_to="2030-01-01",
            ),
            _parameter(
                "fic.cit.rate", "tax.corporate_tax_rate", 0.25, "fraction", "2030-01-01"
            ),
            _parameter(
                "fic.loss.years",
                "tax.loss_carryforward_years",
                7,
                "years",
                "2020-01-01",
            ),
            _parameter(
                "fic.levy.exempt",
                "statutory.fic_levy_exempt",
                True,
                "flag",
                "2020-01-01",
                subject="contract",
            ),
        ],
    }
    data.update(pack_fields)
    return data


def _pack(data: dict[str, Any]) -> JurisdictionPack:
    return JurisdictionPack.model_validate_json(json.dumps(data))


def _fic_source(data: Optional[dict[str, Any]] = None) -> InMemoryPackSource:
    return InMemoryPackSource([_pack(_fic_data() if data is None else data)])


def _refusal(reason: RefusalReason, call: Any) -> JurisdictionRefusal:
    with pytest.raises(JurisdictionRefusal) as caught:
        call()
    assert caught.value.reason is reason, caught.value
    return caught.value


def _values(
    resolution: JurisdictionResolution, subject: JurisdictionSubject, when: date
) -> dict[str, Any]:
    for period in resolution.subject(subject).periods:
        if period.valuation_date == when:
            return {v.parameter_id: v.value for v in period.values}
    raise KeyError(when)


# --- The registered Sri Lanka pack --------------------------------------------------------


def test_lk_resolution_matches_the_committed_lender_case() -> None:
    """Oracle: every resolved value equals the lender case under its scenario key."""
    lender = yaml.safe_load(LENDER_CASE.read_text(encoding="utf-8"))
    pack = DirectoryPackSource().load("LK", "1.0.0")
    subjects = sorted({p.subject for p in pack.parameters}, key=lambda s: s.value)
    assert subjects == [CONTRACT, JurisdictionSubject.SUPPLY, TAX]
    resolution = resolve(
        [_binding(subject) for subject in subjects],
        [date(2028, 1, 1), date(2035, 6, 30)],
        required_subjects=subjects,
    )
    seen = 0
    for subject in subjects:
        entry = resolution.subject(subject)
        assert entry.disposition is SubjectDisposition.SUPPORTED
        assert [p.pack_id for p in entry.packs] == [LK_PACK_ID]
        for period in entry.periods:
            for value in period.values:
                block, key = value.scenario_key.split(".", 1)
                assert lender[block][key] == value.value, value.scenario_key
                assert value.origin is ValueOrigin.PACK
                seen += 1
    assert seen == 2 * len(pack.parameters)
    assert resolution.conflicts == () and resolution.overrides_applied == ()


def test_lk_date_before_the_recorded_window_is_refused() -> None:
    refusal = _refusal(
        RefusalReason.NO_VALUE_IN_FORCE,
        lambda: resolve([_binding(TAX)], [date(2025, 1, 1)]),
    )
    assert "before its first window" in refusal.detail


# --- Fail closed ---------------------------------------------------------------------------


def test_unknown_jurisdiction_is_refused_and_never_falls_back() -> None:
    refusal = _refusal(
        RefusalReason.UNKNOWN_JURISDICTION,
        lambda: resolve(
            [_binding(TAX, code="XX", pack_id=LK_PACK_ID)], [date(2030, 1, 1)]
        ),
    )
    assert "XX" in refusal.detail


def test_unregistered_version_is_refused() -> None:
    refusal = _refusal(
        RefusalReason.UNSUPPORTED_VERSION,
        lambda: resolve([_binding(TAX, version="9.9.9")], [date(2030, 1, 1)]),
    )
    assert "registered: 1.0.0" in refusal.detail


def test_binding_naming_another_pack_id_is_refused() -> None:
    _refusal(
        RefusalReason.PACK_IDENTITY_MISMATCH,
        lambda: resolve(
            [_binding(TAX, pack_id="dutchbay.jurisdiction.other")], [date(2030, 1, 1)]
        ),
    )


def test_missing_binding_for_a_required_subject_is_refused() -> None:
    refusal = _refusal(
        RefusalReason.MISSING_BINDING,
        lambda: resolve(
            [_binding(TAX)], [date(2030, 1, 1)], required_subjects=[TAX, CONTRACT]
        ),
    )
    assert "'contract'" in refusal.detail


def test_subject_the_pack_does_not_cover_is_refused() -> None:
    _refusal(
        RefusalReason.SUBJECT_NOT_COVERED,
        lambda: resolve([_binding(JurisdictionSubject.GRID)], [date(2030, 1, 1)]),
    )


def test_no_valuation_dates_is_refused() -> None:
    _refusal(RefusalReason.NO_VALUATION_DATES, lambda: resolve([_binding(TAX)], []))


def test_a_registered_file_that_fails_validation_is_refused(tmp_path: Path) -> None:
    (tmp_path / "fic").mkdir()
    data = _fic_data(status="assured")
    (tmp_path / "fic" / "1.0.0.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    _refusal(
        RefusalReason.INVALID_PACK,
        lambda: resolve(
            [_binding(TAX, code="FIC", pack_id=FIC_PACK_ID)],
            [date(2030, 1, 1)],
            source=DirectoryPackSource(tmp_path),
        ),
    )


# --- Unsupported -------------------------------------------------------------------------


def test_binding_declared_unsupported_is_not_run() -> None:
    resolution = resolve(
        [_binding(TAX, code="XX", support="unsupported")], [date(2030, 1, 1)]
    )
    entry = resolution.subject(TAX)
    assert entry.disposition is SubjectDisposition.NOT_RUN_UNSUPPORTED_JURISDICTION
    assert entry.periods == () and entry.packs == ()


def test_pack_with_status_unsupported_is_not_run() -> None:
    resolution = resolve(
        [_binding(TAX, code="FIC", pack_id=FIC_PACK_ID)],
        [date(2030, 1, 1)],
        source=_fic_source(_fic_data(status="unsupported")),
    )
    entry = resolution.subject(TAX)
    assert entry.disposition is SubjectDisposition.NOT_RUN_UNSUPPORTED_JURISDICTION
    assert entry.periods == ()
    assert [p.pack_id for p in entry.packs] == [FIC_PACK_ID]


# --- Effective dating --------------------------------------------------------------------


def test_window_is_half_open_at_an_amendment() -> None:
    resolution = resolve(
        [_binding(TAX, code="FIC", pack_id=FIC_PACK_ID)],
        [date(2029, 12, 31), date(2030, 1, 1)],
        source=_fic_source(),
    )
    assert _values(resolution, TAX, date(2029, 12, 31))["fic.cit.rate"] == 0.20
    assert _values(resolution, TAX, date(2030, 1, 1))["fic.cit.rate"] == 0.25


def test_date_in_a_gap_between_windows_is_refused() -> None:
    data = _fic_data()
    data["parameters"][0]["effective_to"] = "2028-01-01"
    refusal = _refusal(
        RefusalReason.NO_VALUE_IN_FORCE,
        lambda: resolve(
            [_binding(TAX, code="FIC", pack_id=FIC_PACK_ID)],
            [date(2029, 1, 1)],
            source=_fic_source(data),
        ),
    )
    assert "in a gap" in refusal.detail and "fic.cit.rate" in refusal.detail


def test_date_after_the_last_window_closes_is_refused() -> None:
    data = _fic_data()
    data["parameters"][1]["effective_to"] = "2040-01-01"
    refusal = _refusal(
        RefusalReason.NO_VALUE_IN_FORCE,
        lambda: resolve(
            [_binding(TAX, code="FIC", pack_id=FIC_PACK_ID)],
            [date(2041, 1, 1)],
            source=_fic_source(data),
        ),
    )
    assert "after its last window" in refusal.detail


def _overlapping_closed_windows() -> dict[str, Any]:
    """Two closed windows for fic.cit.rate: [2020, 2030) and [2025, 2028)."""
    data = _fic_data()
    inner = copy.deepcopy(data["parameters"][0])
    inner["effective_from"] = "2025-01-01"
    inner["effective_to"] = "2028-01-01"
    inner["value"] = 0.22
    data["parameters"][1]["effective_to"] = "2040-01-01"
    data["parameters"].append(inner)
    return data


def test_two_closed_windows_that_overlap_never_reach_the_resolver() -> None:
    """The pack schema refuses the overlap, so no date can match two windows."""
    with pytest.raises(ValidationError, match="overlapping effective windows"):
        _pack(_overlapping_closed_windows())


def test_a_registered_pack_with_overlapping_closed_windows_is_refused(
    tmp_path: Path,
) -> None:
    (tmp_path / "fic").mkdir()
    (tmp_path / "fic" / "1.0.0.yaml").write_text(
        yaml.safe_dump(_overlapping_closed_windows()), encoding="utf-8"
    )
    refusal = _refusal(
        RefusalReason.INVALID_PACK,
        lambda: resolve(
            [_binding(TAX, code="FIC", pack_id=FIC_PACK_ID)],
            [date(2026, 1, 1)],
            source=DirectoryPackSource(tmp_path),
        ),
    )
    assert "overlapping effective windows" in refusal.detail


def test_two_jurisdictions_bind_different_subjects() -> None:
    source = InMemoryPackSource(
        [_pack(_fic_data()), DirectoryPackSource().load("LK", "1.0.0")]
    )
    resolution = resolve(
        [_binding(TAX, code="FIC", pack_id=FIC_PACK_ID), _binding(CONTRACT)],
        [date(2031, 1, 1)],
        source=source,
    )
    assert resolution.subject(TAX).packs[0].jurisdiction_code == "FIC"
    assert resolution.subject(CONTRACT).packs[0].jurisdiction_code == "LK"
    assert _values(resolution, TAX, date(2031, 1, 1))["fic.cit.rate"] == 0.25


# --- Bitemporal safety -------------------------------------------------------------------


def _amended(amendment: date, new_value: float) -> dict[str, Any]:
    data = _fic_data()
    later = copy.deepcopy(data["parameters"][1])
    data["parameters"][1]["effective_to"] = amendment.isoformat()
    later["effective_from"] = amendment.isoformat()
    later["value"] = new_value
    data["parameters"].append(later)
    return data


@settings(max_examples=60, deadline=None)
@given(
    dates=st.lists(
        st.dates(min_value=date(2020, 1, 1), max_value=date(2040, 12, 31)),
        min_size=1,
        max_size=6,
    ),
    gap_days=st.integers(min_value=1, max_value=3650),
    new_value=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
)
def test_amendment_after_the_valuation_dates_never_changes_the_run(
    dates: list[date], gap_days: int, new_value: float
) -> None:
    amendment = max(max(dates), date(2030, 1, 1)) + timedelta(days=gap_days)
    binding = [_binding(TAX, code="FIC", pack_id=FIC_PACK_ID)]
    before = resolve(binding, dates, source=_fic_source())
    after = resolve(binding, dates, source=_fic_source(_amended(amendment, new_value)))
    assert after.subject(TAX).periods == before.subject(TAX).periods


def test_amendment_on_a_valuation_date_does_change_the_run() -> None:
    """Non-vacuity control for the property above."""
    binding = [_binding(TAX, code="FIC", pack_id=FIC_PACK_ID)]
    when = date(2032, 1, 1)
    after = resolve(binding, [when], source=_fic_source(_amended(when, 0.4)))
    assert _values(after, TAX, when)["fic.cit.rate"] == 0.4


# --- Conflicts ---------------------------------------------------------------------------


def test_two_packs_claiming_one_subject_are_reported_with_both_values() -> None:
    other = _fic_data(pack_id="test.jurisdiction.fic2", jurisdiction_code="FIC2")
    other["parameters"][0]["value"] = 0.18
    source = InMemoryPackSource([_pack(_fic_data()), _pack(other)])
    when = date(2025, 1, 1)
    resolution = resolve(
        [
            _binding(TAX, code="FIC", pack_id=FIC_PACK_ID),
            _binding(TAX, code="FIC2", pack_id="test.jurisdiction.fic2"),
        ],
        [when],
        source=source,
    )
    entry = resolution.subject(TAX)
    assert entry.disposition is SubjectDisposition.NOT_RUN_CONFLICT
    assert entry.periods == ()
    assert len(entry.packs) == 2
    records = {c.parameter_id: c for c in resolution.conflicts}
    assert set(records) == {"fic.cit.rate", "fic.loss.years"}
    cit = records["fic.cit.rate"]
    assert cit.kind is ConflictKind.SUBJECT_CLAIMED_BY_TWO_PACKS
    assert sorted(c.value for c in cit.candidates if c.value is not None) == [
        0.18,
        0.20,
    ]


def test_the_same_pack_bound_twice_is_not_a_conflict() -> None:
    resolution = resolve(
        [_binding(TAX, binding_id="jb:a"), _binding(TAX, binding_id="jb:b")],
        [date(2030, 1, 1)],
    )
    assert resolution.subject(TAX).disposition is SubjectDisposition.SUPPORTED
    assert resolution.subject(TAX).binding_ids == ("jb:a", "jb:b")
    assert resolution.conflicts == ()


def test_override_with_provenance_is_applied_and_records_both_values() -> None:
    dates = [date(2029, 1, 1), date(2031, 1, 1)]
    resolution = resolve(
        [_binding(TAX, code="FIC", pack_id=FIC_PACK_ID)],
        dates,
        overrides=[
            ProjectOverride(
                parameter_id="fic.cit.rate", value=0.05, provenance="synthetic relief"
            )
        ],
        source=_fic_source(),
    )
    for when, pack_value in zip(dates, (0.20, 0.25), strict=True):
        period = next(
            p for p in resolution.subject(TAX).periods if p.valuation_date == when
        )
        cit = next(v for v in period.values if v.parameter_id == "fic.cit.rate")
        assert (cit.value, cit.pack_value, cit.origin) == (
            0.05,
            pack_value,
            ValueOrigin.OVERRIDE,
        )
    assert [
        (o.valuation_date, o.pack_value, o.override_value)
        for o in resolution.overrides_applied
    ] == [
        (dates[0], 0.20, 0.05),
        (dates[1], 0.25, 0.05),
    ]
    assert resolution.conflicts == ()


def test_override_without_provenance_is_a_conflict_and_the_value_is_withheld() -> None:
    when = date(2031, 1, 1)
    resolution = resolve(
        [_binding(TAX, code="FIC", pack_id=FIC_PACK_ID)],
        [when],
        overrides=[ProjectOverride(parameter_id="fic.cit.rate", value=0.05)],
        source=_fic_source(),
    )
    assert "fic.cit.rate" not in _values(resolution, TAX, when)
    assert resolution.overrides_applied == ()
    (record,) = resolution.conflicts
    assert record.kind is ConflictKind.OVERRIDE_WITHOUT_PROVENANCE
    assert [c.value for c in record.candidates] == [0.25, 0.05]


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        (
            [ProjectOverride(parameter_id="fic.unknown", value=0.1, provenance="x")],
            RefusalReason.UNKNOWN_OVERRIDE,
        ),
        (
            [ProjectOverride(parameter_id="fic.cit.rate", value=True, provenance="x")],
            RefusalReason.INVALID_OVERRIDE,
        ),
        (
            [ProjectOverride(parameter_id="fic.cit.rate", value=1.5, provenance="x")],
            RefusalReason.INVALID_OVERRIDE,
        ),
        (
            [ProjectOverride(parameter_id="fic.loss.years", value=-1, provenance="x")],
            RefusalReason.INVALID_OVERRIDE,
        ),
        (
            [
                ProjectOverride(parameter_id="fic.cit.rate", value=0.1, provenance="x"),
                ProjectOverride(parameter_id="fic.cit.rate", value=0.2, provenance="y"),
            ],
            RefusalReason.INVALID_OVERRIDE,
        ),
    ],
)
def test_bad_overrides_are_refused(
    overrides: list[ProjectOverride], reason: RefusalReason
) -> None:
    _refusal(
        reason,
        lambda: resolve(
            [_binding(TAX, code="FIC", pack_id=FIC_PACK_ID)],
            [date(2031, 1, 1)],
            overrides=overrides,
            source=_fic_source(),
        ),
    )


def test_override_of_a_subject_that_did_not_resolve_is_refused() -> None:
    _refusal(
        RefusalReason.UNKNOWN_OVERRIDE,
        lambda: resolve(
            [_binding(TAX, code="FIC", pack_id=FIC_PACK_ID, support="unsupported")],
            [date(2031, 1, 1)],
            overrides=[
                ProjectOverride(parameter_id="fic.cit.rate", value=0.1, provenance="x")
            ],
            source=_fic_source(),
        ),
    )


# --- Determinism -------------------------------------------------------------------------


def test_same_inputs_in_any_order_give_the_same_output_and_digest() -> None:
    dates = [date(2031, 1, 1), date(2028, 1, 1), date(2031, 1, 1)]
    first = resolve([_binding(TAX), _binding(CONTRACT)], dates)
    second = resolve([_binding(CONTRACT), _binding(TAX)], list(reversed(dates)))
    assert first == second
    assert first.digest == second.digest
    assert first.valuation_dates == (date(2028, 1, 1), date(2031, 1, 1))
    assert len(first.digest) == 64


def test_digest_responds_to_a_changed_value() -> None:
    binding = [_binding(TAX, code="FIC", pack_id=FIC_PACK_ID)]
    data = _fic_data()
    data["parameters"][2]["value"] = 8
    base = resolve(binding, [date(2031, 1, 1)], source=_fic_source())
    moved = resolve(binding, [date(2031, 1, 1)], source=_fic_source(data))
    assert base.digest != moved.digest


def test_a_resolution_with_a_wrong_digest_is_refused() -> None:
    payload = resolve([_binding(TAX)], [date(2031, 1, 1)]).model_dump(mode="json")
    payload["digest"] = "0" * 64
    with pytest.raises(ValidationError, match="does not match its content"):
        JurisdictionResolution.model_validate_json(json.dumps(payload))


def test_a_resolution_round_trips_through_json() -> None:
    resolution = resolve([_binding(TAX), _binding(CONTRACT)], [date(2031, 1, 1)])
    again = JurisdictionResolution.model_validate_json(resolution.model_dump_json())
    assert again == resolution


# --- Isolation ---------------------------------------------------------------------------


def test_resolver_imports_no_engine_module() -> None:
    allowed = (
        "analytics.feasibility_report_contract",
        "analytics.jurisdiction_packs",
        "pydantic",
        "__future__",
    )
    tree = ast.parse(RESOLVER.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module
        elif isinstance(node, ast.Import):
            module = node.names[0].name
        else:
            continue
        top = module.split(".")[0]
        assert module.startswith(allowed) or top in {
            "hashlib",
            "json",
            "collections",
            "datetime",
            "enum",
            "pathlib",
            "typing",
        }, module
