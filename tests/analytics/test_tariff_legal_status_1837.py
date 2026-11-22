"""The shared tariff legal-status registry is strict and resolves per scenario (#1837)."""

from __future__ import annotations

import copy
import datetime as dt
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.scenario_loader import load_scenario_config
from analytics.tariff_legal_status import (
    REGISTRY_PATH,
    STATUS_ANALOGY_UNPUBLISHED,
    STATUS_MISMATCH,
    STATUS_NOT_RECORDED,
    STATUS_PUBLISHED,
    STATUSES,
    TariffLegalStatusError,
    load_registry,
    read_registry,
    resolve_scenario_status,
    window_flags,
)

ROOT = Path(__file__).resolve().parents[2]
PUCSL = ROOT / "conf" / "blue_whale_pucsl_fit_2026.yaml"


def _raw() -> Dict[str, Any]:
    with open(ROOT / REGISTRY_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _scenario(stem: str) -> Dict[str, Any]:
    return dict(load_scenario_config(str(ROOT / "scenarios" / f"{stem}.yaml")))


def test_the_committed_registry_reads() -> None:
    reg = load_registry()
    assert reg.rates and reg.scenarios


def test_a_rate_without_a_status_is_refused() -> None:
    raw = _raw()
    del raw["rates"]["pucsl_fit_2026_wind"]["status"]
    with pytest.raises(
        TariffLegalStatusError, match=r"rates\.pucsl_fit_2026_wind\.status"
    ):
        read_registry(raw)


W = "rates.pucsl_fit_2026_wind"
A = "rates.wind_bess_on_solar_bess_formula"
D = "sources.PUCSL-DECISION-2026-08"
M = "sources.PUCSL-METHOD-2026"
S = "scenarios.blue_whale_wind_lot5b_2026"
SO = f"{S}.storage_options"


def _rate(r: Dict[str, Any], rid: str = "pucsl_fit_2026_wind") -> Dict[str, Any]:
    node: Dict[str, Any] = r["rates"][rid]
    return node


def _drop_status(r: Dict[str, Any]) -> None:
    del _rate(r)["status"]


#: Every refusal the strict reader makes, each with the complete list of problems it must
#: report. The list is compared whole, so a case cannot pass on another check's message.
REFUSALS = [
    # registry level
    (
        "registry_unknown_key",
        lambda r: r.update(extra=1),
        ["registry.extra: unknown key"],
    ),
    (
        "registry_missing_key",
        lambda r: r.pop("retrieved"),
        ["registry.retrieved: required"],
    ),
    (
        "wrong_schema_version",
        lambda r: r.update(schema_version="tariff_legal_status_v0"),
        [
            "schema_version: expected 'tariff_legal_status_v1', "
            "got 'tariff_legal_status_v0'"
        ],
    ),
    (
        "malformed_retrieved_date",
        lambda r: r.update(retrieved="22 Nov 2026"),
        ["retrieved: expected an ISO date (YYYY-MM-DD) or null, got '22 Nov 2026'"],
    ),
    (
        "empty_sources",
        lambda r: r.update(sources={}),
        [
            "sources: expected a non-empty mapping",
            f"{W}.source: unknown source 'PUCSL-ANNEX2-2026-08'",
            f"{W}.effective_from_source: unknown source 'PUCSL-DECISION-2026-08'",
            f"{W}.review_source: unknown source 'PUCSL-DECISION-2026-08'",
            "rates.pucsl_fit_2026_ground_solar_other_period.source: "
            "unknown source 'PUCSL-ANNEX2-2026-08'",
            "rates.pucsl_fit_2026_ground_solar_other_period.effective_from_source: "
            "unknown source 'PUCSL-DECISION-2026-08'",
            "rates.pucsl_fit_2026_ground_solar_other_period.review_source: "
            "unknown source 'PUCSL-DECISION-2026-08'",
            f"{A}.source: unknown source 'PUCSL-METHOD-2026'",
            f"{A}.review_source: unknown source 'PUCSL-METHOD-2026'",
        ],
    ),
    # sources
    (
        "source_not_a_mapping",
        lambda r: r["sources"].update({"EXTRA": "text"}),
        ["sources.EXTRA: expected a mapping"],
    ),
    (
        "source_unknown_key",
        lambda r: r["sources"]["PUCSL-DECISION-2026-08"].update(colour="red"),
        [f"{D}.colour: unknown key"],
    ),
    (
        "malformed_pdf_hash",
        lambda r: r["sources"]["PUCSL-DECISION-2026-08"].update(
            pdf_sha256="1151EFD22A797ECA174D06C1B1C6AF9380193A8ECBA121362BBF9A5879F16C45"
        ),
        [f"{D}.pdf_sha256: expected 64 lowercase hex characters"],
    ),
    (
        "short_pdf_hash",
        lambda r: r["sources"]["PUCSL-DECISION-2026-08"].update(pdf_sha256="abc123"),
        [f"{D}.pdf_sha256: expected 64 lowercase hex characters"],
    ),
    (
        "missing_pdf_hash",
        lambda r: r["sources"]["PUCSL-DECISION-2026-08"].pop("pdf_sha256"),
        [
            f"{D}.pdf_sha256: required",
            f"{D}.pdf_sha256: expected 64 lowercase hex characters",
        ],
    ),
    (
        "cited_in_not_a_file",
        lambda r: r["sources"]["PUCSL-METHOD-2026"].update(
            cited_in="conf/no_such_file.yaml"
        ),
        [f"{M}.cited_in: not a file in the repository: 'conf/no_such_file.yaml'"],
    ),
    (
        "cited_source_hash_differs_from_its_pin",
        lambda r: r["sources"]["PUCSL-METHOD-2026"].update(pdf_sha256="0" * 64),
        [
            f"{M}.pdf_sha256: differs from the hash "
            "conf/blue_whale_pucsl_fit_2026.yaml pins"
        ],
    ),
    (
        "cited_config_does_not_pin_the_source",
        lambda r: r["sources"]["PUCSL-METHOD-2026"].update(
            cited_in="conf/wind_bess_options.yaml"
        ),
        [
            f"{M}.cited_in: conf/wind_bess_options.yaml pins no pdf_sha256 "
            "for PUCSL-METHOD-2026"
        ],
    ),
    (
        "uncited_source_without_url",
        lambda r: r["sources"]["PUCSL-DECISION-2026-08"].pop("url"),
        [f"{D}: a source not cited from another config needs url and verbatim"],
    ),
    (
        "verbatim_not_a_list",
        lambda r: r["sources"]["PUCSL-DECISION-2026-08"].update(verbatim="one line"),
        [f"{D}.verbatim: expected a list of text"],
    ),
    # rates
    (
        "empty_rates",
        lambda r: r.update(rates={}),
        [
            "rates: expected a non-empty mapping",
            f"{S}.headline_revenue: unknown rate 'pucsl_fit_2026_wind'",
            f"{SO}.whole_wind_peak_rate: unknown rate 'wind_bess_on_solar_bess_formula'",
            f"{SO}.stacked: unknown rate 'wind_bess_on_solar_bess_formula'",
            f"{SO}.whole_wind_peak_rate_on_all_window_exports: "
            "unknown rate 'wind_bess_on_solar_bess_formula'",
            "scenarios.blue_whale_solar_bess_lot5b_2026.headline_revenue: "
            "unknown rate 'pucsl_fit_2026_ground_solar_other_period'",
        ],
    ),
    (
        "rate_not_a_mapping",
        lambda r: r["rates"].update(extra_rate=25.0),
        ["rates.extra_rate: expected a mapping"],
    ),
    (
        "rate_unknown_key",
        lambda r: _rate(r).update(colour="red"),
        [f"{W}.colour: unknown key"],
    ),
    (
        "rate_missing_status",
        _drop_status,
        [
            f"{W}.status: required",
            f"{W}.status: expected one of {list(STATUSES)}, got None",
        ],
    ),
    (
        "unknown_status",
        lambda r: _rate(r).update(status="probably"),
        [f"{W}.status: expected one of {list(STATUSES)}, got 'probably'"],
    ),
    (
        "rate_not_a_number",
        lambda r: _rate(r).update(lkr_per_kwh="25.73"),
        [f"{W}.lkr_per_kwh: expected a number or null"],
    ),
    (
        "rate_is_a_bool",
        lambda r: _rate(r).update(lkr_per_kwh=True),
        [f"{W}.lkr_per_kwh: expected a number or null"],
    ),
    (
        "zero_rate",
        lambda r: _rate(r).update(lkr_per_kwh=0, components_lkr_per_kwh=None),
        [f"{W}.lkr_per_kwh: expected a positive number"],
    ),
    (
        "negative_rate",
        lambda r: _rate(r).update(lkr_per_kwh=-25.73, components_lkr_per_kwh=None),
        [f"{W}.lkr_per_kwh: expected a positive number"],
    ),
    (
        "non_finite_rate",
        lambda r: _rate(r).update(
            lkr_per_kwh=float("inf"), components_lkr_per_kwh=None
        ),
        [f"{W}.lkr_per_kwh: expected a positive number"],
    ),
    (
        "published_rate_without_value",
        lambda r: _rate(r).update(lkr_per_kwh=None),
        [f"{W}.lkr_per_kwh: a published rate states its value"],
    ),
    (
        "components_not_numbers",
        lambda r: _rate(r).update(components_lkr_per_kwh=["20.80", 4.93]),
        [f"{W}.components_lkr_per_kwh: expected a list of numbers"],
    ),
    (
        "components_do_not_sum",
        lambda r: _rate(r).update(lkr_per_kwh=25.0),
        [
            f"{W}.components_lkr_per_kwh: the components sum to "
            f"{20.80 + 4.93!r}, not lkr_per_kwh 25.0"
        ],
    ),
    (
        "unknown_source",
        lambda r: _rate(r).update(source="NO-SUCH-SOURCE"),
        [f"{W}.source: unknown source 'NO-SUCH-SOURCE'"],
    ),
    (
        "unknown_effective_from_source",
        lambda r: _rate(r).update(effective_from_source="NO-SUCH-SOURCE"),
        [f"{W}.effective_from_source: unknown source 'NO-SUCH-SOURCE'"],
    ),
    (
        "unknown_review_source",
        lambda r: _rate(r).update(review_source="NO-SUCH-SOURCE"),
        [f"{W}.review_source: unknown source 'NO-SUCH-SOURCE'"],
    ),
    (
        "malformed_effective_from",
        lambda r: _rate(r).update(effective_from="25/08/2026"),
        [
            f"{W}.effective_from: expected an ISO date (YYYY-MM-DD) or null, "
            "got '25/08/2026'",
            f"{W}.effective_note: required when effective_from is null "
            "(quote why the source states no date)",
        ],
    ),
    (
        "impossible_effective_from",
        lambda r: _rate(r).update(effective_from="2026-02-30", effective_note="x"),
        [
            f"{W}.effective_from: expected an ISO date (YYYY-MM-DD) or null, "
            "got '2026-02-30'"
        ],
    ),
    (
        "malformed_effective_to",
        lambda r: _rate(r).update(effective_to=20270630),
        [f"{W}.effective_to: expected an ISO date (YYYY-MM-DD) or null, got 20270630"],
    ),
    (
        "end_before_start",
        lambda r: _rate(r).update(effective_to="2026-08-24"),
        [f"{W}.effective_to: before effective_from"],
    ),
    (
        "null_start_without_note",
        lambda r: _rate(r, "wind_bess_on_solar_bess_formula").pop("effective_note"),
        [
            f"{A}.effective_note: required when effective_from is null "
            "(quote why the source states no date)"
        ],
    ),
    (
        "null_end_without_review",
        lambda r: _rate(r).pop("review"),
        [
            f"{W}.review: required when effective_to is null "
            "(quote what ends the rate)"
        ],
    ),
    (
        "empty_instrument",
        lambda r: _rate(r).update(instrument="  "),
        [f"{W}.instrument: expected non-empty text"],
    ),
    (
        "conditions_not_a_list",
        lambda r: _rate(r).update(conditions="one condition"),
        [f"{W}.conditions: expected a list of text"],
    ),
    (
        "empty_open_question",
        lambda r: _rate(r).update(open_questions=[""]),
        [f"{W}.open_questions[0]: expected non-empty text"],
    ),
    # scenarios
    (
        "scenarios_not_a_mapping",
        lambda r: r.update(scenarios=["blue_whale_wind_lot5b_2026"]),
        ["scenarios: expected a mapping"],
    ),
    (
        "scenario_not_a_mapping",
        lambda r: r["scenarios"].update(extra_scenario="pucsl_fit_2026_wind"),
        ["scenarios.extra_scenario: expected a mapping"],
    ),
    (
        "scenario_unknown_key",
        lambda r: r["scenarios"]["blue_whale_wind_lot5b_2026"].update(colour="red"),
        [f"{S}.colour: unknown key"],
    ),
    (
        "scenario_without_headline",
        lambda r: r["scenarios"]["blue_whale_wind_lot5b_2026"].pop("headline_revenue"),
        [f"{S}.headline_revenue: required", f"{S}.headline_revenue: unknown rate None"],
    ),
    (
        "unknown_headline_rate",
        lambda r: r["scenarios"]["blue_whale_wind_lot5b_2026"].update(
            headline_revenue="no_such_rate"
        ),
        [f"{S}.headline_revenue: unknown rate 'no_such_rate'"],
    ),
    (
        "empty_storage_options",
        lambda r: r["scenarios"]["blue_whale_wind_lot5b_2026"].update(
            storage_options={}
        ),
        [f"{SO}: expected a non-empty mapping"],
    ),
    (
        "unknown_storage_rate",
        lambda r: r["scenarios"]["blue_whale_wind_lot5b_2026"][
            "storage_options"
        ].update(stacked="no_such_rate"),
        [f"{SO}.stacked: unknown rate 'no_such_rate'"],
    ),
]


def _problems(raw: Dict[str, Any]) -> list:
    with pytest.raises(TariffLegalStatusError) as info:
        read_registry(raw)
    head, *lines = str(info.value).split("\n")
    assert head == "conf/tariff_legal_status.yaml is invalid:"
    return [line.removeprefix("  ") for line in lines]


@pytest.mark.parametrize(
    "mutate, expected", [c[1:] for c in REFUSALS], ids=[c[0] for c in REFUSALS]
)
def test_each_refusal_reports_exactly_its_own_problems(
    mutate: Any, expected: list
) -> None:
    raw = copy.deepcopy(_raw())
    mutate(raw)
    assert _problems(raw) == expected


def test_a_registry_that_is_not_a_mapping_is_refused() -> None:
    with pytest.raises(TariffLegalStatusError, match=r"^registry: expected a mapping$"):
        read_registry(["not", "a", "mapping"])  # type: ignore[arg-type]


def test_the_refusal_table_is_not_vacuous() -> None:
    """Every case changes the registry, and the unchanged registry reads."""
    read_registry(copy.deepcopy(_raw()))
    assert len({c[0] for c in REFUSALS}) == len(REFUSALS)
    for mutate, _ in [c[1:] for c in REFUSALS]:
        raw = copy.deepcopy(_raw())
        mutate(raw)
        assert raw != _raw()


def test_recorded_rates_agree_with_the_regulatory_config() -> None:
    """One fact, one home: the values and PDF hashes match conf/blue_whale_pucsl_fit_2026.yaml."""
    with open(PUCSL, encoding="utf-8") as fh:
        pucsl = yaml.safe_load(fh)
    reg = load_registry()
    tariffs = pucsl["tariff_lkr_per_kwh"]
    assert reg.rates["pucsl_fit_2026_wind"].lkr_per_kwh == tariffs["wind"]
    assert (
        reg.rates["pucsl_fit_2026_ground_solar_other_period"].lkr_per_kwh
        == tariffs["solar_bess_other"]
    )
    raw = _raw()
    for sid, node in raw["sources"].items():
        if node.get("cited_in") == "conf/blue_whale_pucsl_fit_2026.yaml":
            assert pucsl["sources"][sid]["pdf_sha256"] == node["pdf_sha256"], sid


def test_the_wind_scenario_resolves_published_headline_and_analogy_storage() -> None:
    status = resolve_scenario_status(
        _scenario("blue_whale_wind_lot5b_2026"), "blue_whale_wind_lot5b_2026"
    )
    assert status.recorded
    assert status.headline.status == STATUS_PUBLISHED
    assert status.headline.rate is not None
    assert status.headline.rate.effective_from == dt.date(2026, 8, 25)
    assert status.storage_options
    assert {u.status for u in status.storage_options.values()} == {
        STATUS_ANALOGY_UNPUBLISHED
    }
    assert all(u.needs_label for u in status.storage_options.values())
    assert status.window_flags == ()


def test_every_storage_basis_the_wind_scenario_uses_is_recorded() -> None:
    """A revenue basis of the options analysis may not reach a report unrecorded."""
    with open(ROOT / "conf" / "wind_bess_options.yaml", encoding="utf-8") as fh:
        method = yaml.safe_load(fh)["method"]["revenue_bases"]
    used = {method["base"], *method["sensitivities"]}
    recorded = set(_raw()["scenarios"]["blue_whale_wind_lot5b_2026"]["storage_options"])
    assert used <= recorded


def test_an_unlisted_scenario_is_not_recorded_never_published() -> None:
    status = resolve_scenario_status(
        _scenario("dutchbay_lendercase_2025Q4"), "dutchbay_lendercase_2025Q4"
    )
    assert not status.recorded
    assert status.headline.status == STATUS_NOT_RECORDED
    assert status.headline.needs_label
    assert "20.3 LKR/kWh" in status.headline.detail


def test_a_different_tariff_value_is_a_mismatch() -> None:
    scenario = _scenario("blue_whale_wind_lot5b_2026")
    scenario["tariff"] = {**scenario["tariff"], "lkr_per_kwh": 30.0}
    status = resolve_scenario_status(scenario, "blue_whale_wind_lot5b_2026")
    assert status.headline.status == STATUS_MISMATCH
    assert status.headline.needs_label


def test_dates_outside_the_window_are_flagged() -> None:
    reg = load_registry()
    rate = reg.rates["pucsl_fit_2026_wind"]
    ended = type(rate)(**{**rate.__dict__, "effective_to": dt.date(2027, 6, 30)})
    flags = window_flags([ended], cod_year=2028, signing_date=dt.date(2026, 1, 1))
    assert any("COD year 2028 is after the rate ends" in f for f in flags)
    assert any(
        "signing date 2026-01-01 is before the rate takes effect" in f for f in flags
    )
    assert window_flags([rate], cod_year=2028, signing_date=None) == ()


def test_a_declared_signing_date_is_checked() -> None:
    scenario = _scenario("blue_whale_wind_lot5b_2026")
    scenario["ppa"] = {**(scenario.get("ppa") or {}), "signing_date": "2026-05-01"}
    status = resolve_scenario_status(scenario, "blue_whale_wind_lot5b_2026")
    assert status.signing_date == dt.date(2026, 5, 1)
    assert any("before the rate takes effect" in f for f in status.window_flags)


def test_a_signing_date_after_the_end_and_a_cod_before_the_start_are_flagged() -> None:
    rate = load_registry().rates["pucsl_fit_2026_wind"]
    ended = type(rate)(**{**rate.__dict__, "effective_to": dt.date(2027, 6, 30)})
    flags = window_flags([ended], cod_year=2025, signing_date=dt.date(2027, 7, 1))
    assert flags == (
        "pucsl_fit_2026_wind: the assumed SPPA signing date 2027-07-01 is after the "
        "rate ends (2027-06-30).",
        "pucsl_fit_2026_wind: the scenario's COD year 2025 is before the rate takes "
        "effect (2026-08-25).",
    )
    # Inside the window on both counts: no flag.
    assert window_flags([ended], cod_year=2026, signing_date=dt.date(2026, 8, 25)) == ()


def test_the_published_rates_record_that_they_govern_the_signing_date() -> None:
    """Decision Annex 3 s.7(d): the tariff applies to SPPAs signed on or after the start."""
    reg = load_registry()
    for rid in ("pucsl_fit_2026_wind", "pucsl_fit_2026_ground_solar_other_period"):
        assert any(
            "signed on or after 25 August 2026 (Decision Annex 3 s.7(d))" in c
            for c in reg.rates[rid].conditions
        ), rid
    quotes = _raw()["sources"]["PUCSL-DECISION-2026-08"]["verbatim"]
    assert any(q.startswith("Annex 3 s.7(d): ") for q in quotes)
