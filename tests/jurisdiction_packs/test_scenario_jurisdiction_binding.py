"""Every scenario binds to a registered jurisdiction pack (#1841 PR 3)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from analytics.feasibility_report_contract.project_case import (
    ContractSupportStatus,
    JurisdictionSubject,
)
from analytics.jurisdiction_packs import (
    JurisdictionRefusal,
    RefusalReason,
    SubjectDisposition,
    resolve,
)
from analytics.jurisdiction_packs.scenario_binding import (
    SCENARIO_BINDINGS_PATH,
    ScenarioBindingRegistry,
    load_scenario_binding_registry,
    scenario_jurisdiction_bindings,
    scenario_jurisdiction_entry,
)
from analytics.jurisdiction_packs.schema import load_registered_pack
from finance.cashflow_v14_tax import require_sri_lanka_jurisdiction

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = REPO_ROOT / "scenarios"
# All parameters of the LK 1.0.0 pack are in force from 2026-07-05 with no end date.
IN_FORCE = date(2027, 1, 1)


def _scenario_documents() -> list[tuple[str, dict[str, Any]]]:
    """Each committed scenario document that has a ``project`` section."""
    out: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(SCENARIOS.rglob("*.yaml")):
        documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        for index, document in enumerate(documents):
            if isinstance(document, dict) and isinstance(document.get("project"), dict):
                label = path.relative_to(REPO_ROOT).as_posix()
                if len(documents) > 1:
                    label = f"{label}#{index}"
                out.append((label, document))
    return out


_DOCUMENTS = _scenario_documents()


def test_the_scenario_census_is_not_vacuous() -> None:
    labels = {label for label, _ in _DOCUMENTS}
    assert len(labels) >= 35
    assert "scenarios/dutchbay_lendercase_2025Q4.yaml" in labels
    assert "scenarios/blue_whale_wind_lot5b_2026.yaml" in labels


@pytest.mark.parametrize(
    ("label", "document"), _DOCUMENTS, ids=[label for label, _ in _DOCUMENTS]
)
def test_every_scenario_declares_a_bound_jurisdiction(
    label: str, document: dict[str, Any]
) -> None:
    bindings = scenario_jurisdiction_bindings(document)
    assert bindings, label
    resolution = resolve(bindings, [IN_FORCE])
    for subject in resolution.subjects:
        assert subject.disposition is SubjectDisposition.SUPPORTED, (label, subject)
    # The engine's own guard (#1882) runs the same scenario.
    require_sri_lanka_jurisdiction(document, label)


def test_the_sri_lanka_binding_covers_each_pack_subject() -> None:
    bindings = scenario_jurisdiction_bindings(
        {"project": {"jurisdiction": "Sri Lanka"}}
    )
    pack = load_registered_pack("LK", "1.0.0")
    assert [b.subject for b in bindings] == sorted({p.subject for p in pack.parameters})
    assert {b.subject for b in bindings} >= {
        JurisdictionSubject.TAX,
        JurisdictionSubject.SUPPLY,
        JurisdictionSubject.CONTRACT,
    }
    for binding in bindings:
        assert binding.binding_id == f"jb:lk:{binding.subject.value}"
        assert binding.jurisdiction_code == "LK"
        assert binding.contract_pack_id == pack.pack_id
        assert binding.contract_pack_version == "1.0.0"
        assert binding.support_status is ContractSupportStatus.DECLARED


@pytest.mark.parametrize(
    "spelling", ("Sri Lanka", "sri lanka", " SRI LANKA ", "LK", "lka")
)
def test_each_accepted_spelling_binds_lk_and_the_engine_accepts_it(
    spelling: str,
) -> None:
    config = {"project": {"jurisdiction": spelling}}
    assert scenario_jurisdiction_entry(config).jurisdiction_code == "LK"
    require_sri_lanka_jurisdiction(config, "test")


def test_registry_spellings_are_all_accepted_by_the_engine_guard() -> None:
    """No spelling the registry binds to LK can be refused by the Sri Lanka code."""
    registry = load_scenario_binding_registry()
    (lk,) = [e for e in registry.jurisdictions if e.jurisdiction_code == "LK"]
    for spelling in (lk.jurisdiction_code, *lk.names):
        require_sri_lanka_jurisdiction({"project": {"jurisdiction": spelling}}, "t")


@pytest.mark.parametrize(
    ("config", "reason"),
    (
        ({}, RefusalReason.MISSING_BINDING),
        ({"project": {}}, RefusalReason.MISSING_BINDING),
        ({"project": {"jurisdiction": None}}, RefusalReason.MISSING_BINDING),
        ({"project": {"jurisdiction": ""}}, RefusalReason.UNKNOWN_JURISDICTION),
        ({"project": {"jurisdiction": 7}}, RefusalReason.UNKNOWN_JURISDICTION),
        (
            {"project": {"jurisdiction": "Fictionland"}},
            RefusalReason.UNKNOWN_JURISDICTION,
        ),
        ({"project": {"jurisdiction": "India"}}, RefusalReason.UNKNOWN_JURISDICTION),
    ),
    ids=("no-project", "no-key", "null", "empty", "number", "fictionland", "india"),
)
def test_a_scenario_without_a_known_jurisdiction_is_refused(
    config: dict[str, Any], reason: RefusalReason
) -> None:
    with pytest.raises(JurisdictionRefusal) as error:
        scenario_jurisdiction_bindings(config)
    assert error.value.reason is reason


def _registry(**entry: Any) -> ScenarioBindingRegistry:
    base = {
        "jurisdiction_code": "LK",
        "names": ["Sri Lanka"],
        "pack_id": "dutchbay.jurisdiction.lk",
        "pack_version": "1.0.0",
    }
    return ScenarioBindingRegistry.model_validate_json(
        json.dumps(
            {
                "schema_id": "dutchbay.jurisdiction_scenario_bindings.v1",
                "jurisdictions": [base | entry],
            }
        )
    )


def test_an_unregistered_pack_version_is_refused() -> None:
    with pytest.raises(JurisdictionRefusal) as error:
        scenario_jurisdiction_bindings(
            {"project": {"jurisdiction": "Sri Lanka"}},
            registry=_registry(pack_version="9.9.9"),
        )
    assert error.value.reason is RefusalReason.UNSUPPORTED_VERSION


def test_a_registry_entry_naming_another_pack_id_is_refused() -> None:
    with pytest.raises(JurisdictionRefusal) as error:
        scenario_jurisdiction_bindings(
            {"project": {"jurisdiction": "Sri Lanka"}},
            registry=_registry(pack_id="dutchbay.jurisdiction.other"),
        )
    assert error.value.reason is RefusalReason.PACK_IDENTITY_MISMATCH


def test_a_spelling_may_name_only_one_jurisdiction() -> None:
    entry = {
        "names": ["Sri Lanka"],
        "pack_id": "dutchbay.jurisdiction.x",
        "pack_version": "1.0.0",
    }
    with pytest.raises(ValueError, match="names both"):
        ScenarioBindingRegistry.model_validate_json(
            json.dumps(
                {
                    "schema_id": "dutchbay.jurisdiction_scenario_bindings.v1",
                    "jurisdictions": [
                        entry | {"jurisdiction_code": "LK"},
                        entry | {"jurisdiction_code": "XX"},
                    ],
                }
            )
        )


def test_the_committed_registry_loads_and_names_lk() -> None:
    registry = load_scenario_binding_registry(SCENARIO_BINDINGS_PATH)
    assert [e.jurisdiction_code for e in registry.jurisdictions] == ["LK"]
