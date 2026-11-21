"""Tests for the jurisdiction pack schema and the Sri Lanka reference pack (#1842)."""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any, Iterator

import pytest
import yaml
from pydantic import ValidationError

from analytics.feasibility_report_contract.vocabulary import PackStatus
from analytics.jurisdiction_packs import (
    PACKS_ROOT,
    JurisdictionPack,
    ParameterStatus,
    load_pack_file,
    load_registered_pack,
)

REPO = Path(__file__).resolve().parents[2]
SCENARIOS = REPO / "scenarios"
LENDER_CASE = SCENARIOS / "dutchbay_lendercase_2025Q4.yaml"
LK_PACK = PACKS_ROOT / "lk" / "1.0.0.yaml"
INVENTORY = (
    REPO
    / "tests"
    / "fixtures"
    / "jurisdiction_packs"
    / "lk_1_0_0_scenario_disagreements.yaml"
)
CLASSIFICATIONS = {"synthetic_fixture", "project_override", "discrepancy_for_owner"}


def _raw_pack() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(LK_PACK.read_text(encoding="utf-8"))
    return data


def _write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "pack.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _lookup(document: dict[str, Any], dotted: str) -> tuple[bool, Any]:
    block, key = dotted.split(".", 1)
    section = document.get(block)
    if not isinstance(section, dict) or key not in section:
        return False, None
    return True, section[key]


def _same(scenario_value: Any, pack_value: Any) -> bool:
    if isinstance(scenario_value, bool) or isinstance(pack_value, bool):
        return type(scenario_value) is type(pack_value) and scenario_value == pack_value
    if not isinstance(scenario_value, (int, float)):
        return False
    return math.isclose(
        float(scenario_value), float(pack_value), rel_tol=0.0, abs_tol=1e-12
    )


def _scenario_documents(root: Path) -> Iterator[tuple[str, dict[str, Any]]]:
    for path in sorted(root.rglob("*.yaml")):
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if isinstance(document, dict):
                yield path.relative_to(root).as_posix(), document


def _disagreements(pack: JurisdictionPack, root: Path) -> set[tuple[str, str, Any]]:
    found: set[tuple[str, str, Any]] = set()
    for name, document in _scenario_documents(root):
        for parameter in pack.parameters:
            present, value = _lookup(document, parameter.scenario_key)
            if present and not _same(value, parameter.value):
                found.add((name, parameter.scenario_key, value))
    return found


# --- The Sri Lanka reference pack ---------------------------------------------------


def test_lk_pack_loads_as_supported_and_never_assured() -> None:
    pack = load_registered_pack("LK", "1.0.0")
    assert pack.jurisdiction_code == "LK"
    assert pack.status is PackStatus.SUPPORTED
    assert len(pack.parameters) == 13
    assert {p.status for p in pack.parameters} == {ParameterStatus.AS_RECORDED}


def test_every_lk_parameter_has_a_source_and_an_effective_date() -> None:
    for parameter in load_registered_pack("LK", "1.0.0").parameters:
        assert parameter.sources, parameter.parameter_id
        assert all(s.repository_record for s in parameter.sources)
        assert parameter.effective_from <= parameter.recorded_at, parameter.parameter_id


def test_lk_pack_values_equal_the_committed_lender_case() -> None:
    """Oracle: the lender case committed before this change carries every pack value."""
    lender = yaml.safe_load(LENDER_CASE.read_text(encoding="utf-8"))
    for parameter in load_registered_pack("LK", "1.0.0").parameters:
        present, value = _lookup(lender, parameter.scenario_key)
        assert present, f"lender case has no {parameter.scenario_key}"
        assert _same(value, parameter.value), (
            parameter.scenario_key,
            value,
            parameter.value,
        )


def test_disagreement_inventory_matches_the_scenarios() -> None:
    inventory = yaml.safe_load(INVENTORY.read_text(encoding="utf-8"))["disagreements"]
    recorded = {
        (e["scenario"], e["scenario_key"], e["scenario_value"]) for e in inventory
    }
    assert len(recorded) == len(inventory), "duplicate inventory rows"
    assert {e["classification"] for e in inventory} <= CLASSIFICATIONS
    live = _disagreements(load_registered_pack("LK", "1.0.0"), SCENARIOS)
    assert live == recorded, {
        "unclassified": sorted(live - recorded, key=str),
        "stale": sorted(recorded - live, key=str),
    }


def test_disagreement_check_responds_to_a_changed_scenario(tmp_path: Path) -> None:
    """Responsiveness guard: a moved lender-case value shows up as a disagreement."""
    lender = yaml.safe_load(LENDER_CASE.read_text(encoding="utf-8"))
    pack = load_registered_pack("LK", "1.0.0")
    (tmp_path / "lender.yaml").write_text(yaml.safe_dump(lender), encoding="utf-8")
    assert _disagreements(pack, tmp_path) == set()
    lender["tax"]["corporate_tax_rate"] = 0.31
    (tmp_path / "lender.yaml").write_text(yaml.safe_dump(lender), encoding="utf-8")
    assert _disagreements(pack, tmp_path) == {
        ("lender.yaml", "tax.corporate_tax_rate", 0.31)
    }


# --- Loader ----------------------------------------------------------------------------


def test_unregistered_pack_is_refused() -> None:
    with pytest.raises(
        FileNotFoundError, match="no jurisdiction pack registered for XX"
    ):
        load_registered_pack("XX", "1.0.0")


def test_pack_filed_under_another_version_is_refused(tmp_path: Path) -> None:
    (tmp_path / "lk").mkdir()
    (tmp_path / "lk" / "9.9.9.yaml").write_text(LK_PACK.read_text(encoding="utf-8"))
    with pytest.raises(
        ValueError, match="declares LK 1.0.0, but is filed under LK 9.9.9"
    ):
        load_registered_pack("LK", "9.9.9", root=tmp_path)


def test_a_non_mapping_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "pack.yaml"
    path.write_text("- not a mapping\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a YAML mapping"):
        load_pack_file(path)


# --- Schema refusals -------------------------------------------------------------------


def _mutated(mutate: Any) -> dict[str, Any]:
    data = copy.deepcopy(_raw_pack())
    mutate(data)
    return data


def _p0(data: dict[str, Any]) -> dict[str, Any]:
    first: dict[str, Any] = data["parameters"][0]
    return first


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d.update(unknown_key=1), "unknown_key"),
        (lambda d: _p0(d).update(unknown_key=1), "unknown_key"),
        (lambda d: _p0(d).update(sources=[]), "sources"),
        (lambda d: _p0(d).pop("sources"), "sources"),
        (lambda d: _p0(d).pop("effective_from"), "effective_from"),
        (lambda d: _p0(d)["sources"][0].pop("repository_record"), "repository_record"),
        (lambda d: d.update(status="assured"), "cannot be 'assured'"),
        (
            lambda d: d.update(review_date=d["effective_date"]),
            "review_date must be after",
        ),
        (lambda d: _p0(d).update(value="0.30"), "value"),
        (lambda d: _p0(d).update(value=1.3), "fraction must lie in"),
        (lambda d: _p0(d).update(value=True), "unit 'flag'"),
        (
            lambda d: _p0(d).update(effective_to=_p0(d)["effective_from"]),
            "effective_to",
        ),
        (
            lambda d: _p0(d).update(status="published"),
            "status 'published' needs a source",
        ),
        (lambda d: _p0(d).update(subject="planet"), "subject"),
        (lambda d: _p0(d).update(unit="percent"), "unit"),
        (lambda d: d.update(parameters=[]), "parameters"),
        (lambda d: d.update(limitations=[]), "limitations"),
        (lambda d: d.update(kind="technology"), "kind"),
        (
            lambda d: d["parameters"][1].update(scenario_key=_p0(d)["scenario_key"]),
            "is claimed by both",
        ),
    ],
)
def test_schema_refuses(tmp_path: Path, mutate: Any, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        load_pack_file(_write(tmp_path, _mutated(mutate)))


def test_overlapping_windows_for_one_parameter_are_refused(tmp_path: Path) -> None:
    def add_second_window(data: dict[str, Any]) -> None:
        later = copy.deepcopy(_p0(data))
        later["effective_from"] = "2027-01-01"
        data["parameters"].append(later)

    with pytest.raises(ValidationError, match="overlapping effective windows"):
        load_pack_file(_write(tmp_path, _mutated(add_second_window)))


def test_consecutive_windows_for_one_parameter_are_accepted(tmp_path: Path) -> None:
    def close_and_reopen(data: dict[str, Any]) -> None:
        _p0(data)["effective_to"] = "2027-01-01"
        later = copy.deepcopy(_p0(data))
        later["effective_from"] = "2027-01-01"
        later.pop("effective_to")
        later["value"] = 0.28
        data["parameters"].append(later)

    pack = load_pack_file(_write(tmp_path, _mutated(close_and_reopen)))
    rates = [
        p.value for p in pack.parameters if p.parameter_id == "lk.cit.standard_rate"
    ]
    assert rates == [0.30, 0.28]


def test_a_published_parameter_needs_an_instrument_date(tmp_path: Path) -> None:
    def publish(data: dict[str, Any]) -> None:
        source = _p0(data)["sources"][0]
        source["official_url"] = "https://example.invalid/act.pdf"
        source["document_sha256"] = "0" * 64
        _p0(data)["status"] = "published"

    with pytest.raises(ValidationError, match="effective_from_basis 'instrument'"):
        load_pack_file(_write(tmp_path, _mutated(publish)))
    data = _mutated(publish)
    _p0(data)["effective_from_basis"] = "instrument"
    assert load_pack_file(_write(tmp_path, data)).parameters[0].status is (
        ParameterStatus.PUBLISHED
    )
