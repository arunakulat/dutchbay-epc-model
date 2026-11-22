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


@pytest.mark.parametrize(
    "mutate, path",
    [
        (
            lambda r: r["rates"]["pucsl_fit_2026_wind"].update(status="probably"),
            "status",
        ),
        (lambda r: r["rates"]["pucsl_fit_2026_wind"].update(colour="red"), "colour"),
        (
            lambda r: r["rates"]["pucsl_fit_2026_wind"].update(
                effective_from="25/08/2026"
            ),
            "effective_from",
        ),
        (
            lambda r: r["rates"]["pucsl_fit_2026_wind"].update(lkr_per_kwh=25.0),
            "components_lkr_per_kwh",
        ),
        (lambda r: r["rates"]["pucsl_fit_2026_wind"].pop("review"), "review"),
        (
            lambda r: r["scenarios"]["blue_whale_wind_lot5b_2026"].update(
                headline_revenue="no_such_rate"
            ),
            "headline_revenue",
        ),
        (
            lambda r: r["rates"]["pucsl_fit_2026_wind"].update(source="NO-SUCH-SOURCE"),
            "source",
        ),
    ],
)
def test_the_reader_names_the_path_of_each_problem(mutate: Any, path: str) -> None:
    raw = copy.deepcopy(_raw())
    mutate(raw)
    with pytest.raises(TariffLegalStatusError, match=path):
        read_registry(raw)


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
