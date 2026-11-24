"""The generic solar + BESS sizing code is site-neutral (#1578 Group C, BW-4).

- L-5: the sizing module takes each config's site prefix and the regulatory readings'
  names from config, and the three generic modules carry no site or PR-number wording.
- L-8: the project-IRR sentinel reads the #1494 status, not an exact 0.0.
- #1590 domain D-1: :func:`~solar_resource.pv_bess_sizing.annual_energy` books energy by
  the dispatcher's :meth:`~solar_resource.pv_bess_dispatch.TariffConfig.rate_name`.
- #1590 assurance A-4: the wording check covers the module docstrings too.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import json
import math
import re
import tokenize
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest
import yaml

import solar_resource.pv_bess_dispatch as pbd
import solar_resource.pv_bess_sizing as sz
import solar_resource.pv_bess_sizing_runner as sz_runner

REPO_ROOT = Path(__file__).resolve().parents[2]
CONF = REPO_ROOT / "conf"
UNIT_CONF = CONF / "blue_whale_solar_bess.yaml"
PRICING_CONF = CONF / "blue_whale_pv_bess_pricing.yaml"
REG_CONF = CONF / "blue_whale_pucsl_fit_2026.yaml"
METHOD_CONF = CONF / "solar_bess_sizing.yaml"
SOLAR_BESS = REPO_ROOT / "scenarios" / "blue_whale_solar_bess_lot5b_2026.yaml"
SCENARIO = SOLAR_BESS

#: The generic modules of the solar + BESS chain (the Blue Whale runners and configs are
#: the site's, and may name it).
GENERIC_MODULES = (
    "solar_resource/pv_bess_sizing.py",
    "solar_resource/pv_bess_dispatch.py",
    "analytics/gis/pv_array_layout.py",
    # #1578 U3: the run and summary moved out of the single-site script.
    "solar_resource/pv_bess_sizing_runner.py",
)
#: "PR 4", "PR4", "PR #1590" and "PR#12" (#1820: the "#" spellings were not caught).
SITE_WORDING = re.compile(r"blue[ _-]?whale|\bPR ?#?\d", re.IGNORECASE)


def _yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict)
    return data


# ---------------------------------------------------------------------------
# L-5 and A-4: no site wording in the generic modules, docstrings included
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("rel", GENERIC_MODULES)
def test_generic_module_comments_carry_no_site_or_pr_wording(rel: str) -> None:
    """Comments too (#1725 assurance A-3): the string check does not read them."""
    with (REPO_ROOT / rel).open("rb") as handle:
        comments = [
            tok.string
            for tok in tokenize.tokenize(handle.readline)
            if tok.type == tokenize.COMMENT
        ]
    assert comments
    assert [c for c in comments if SITE_WORDING.search(c)] == []


@pytest.mark.parametrize("rel", GENERIC_MODULES)
def test_generic_modules_carry_no_site_or_pr_wording(rel: str) -> None:
    tree = ast.parse((REPO_ROOT / rel).read_text())
    texts = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    assert ast.get_docstring(tree, clean=False) in texts  # the docstring is covered
    assert [t for t in texts if SITE_WORDING.search(t)] == []


def test_the_wording_pattern_catches_what_it_is_for() -> None:
    for bad in (
        "Blue Whale",
        "conf/blue_whale_pv_bess_pricing.yaml",
        "blue-whale",
        "(PR 2)",
        "PR 4's",
        "PR #1590",
        "(PR#12)",
        "pr 7",
    ):
        assert SITE_WORDING.search(bad), bad
    for fine in (
        "PUCSL 2026",
        "the separate solar + BESS project",
        "PRICING_SCHEMA",
        "#1590",
        "PROJECT 2",
        "APR 2026",
    ):
        assert not SITE_WORDING.search(fine), fine


# ---------------------------------------------------------------------------
# L-5: the schema family is checked, the site prefix comes from config
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "family",
    [
        sz.PRICING_SCHEMA,
        sz.SIZING_SCHEMA,
        sz.REGULATORY_SCHEMA,
        sz.PROJECT_SIZING_SCHEMA,
    ],
)
def test_a_schema_is_its_family_with_or_without_a_site_prefix(family: str) -> None:
    for ok in (family, f"blue_whale_{family}", f"other_site_{family}"):
        sz._check_schema(ok, family, "cfg")
    for bad in (
        f"_{family}",  # an empty site prefix
        f"{family}_x",
        family.replace("_v1", "_v2"),
        f"site{family}",  # the prefix must end in an underscore
        None,
        1,
    ):
        with pytest.raises(ValueError, match=rf"cfg\.schema_version must be {family}"):
            sz._check_schema(bad, family, "cfg")


def test_the_committed_configs_are_their_families() -> None:
    """The Blue Whale configs keep their bytes; their prefix is the site's (L-5)."""
    for path, family in (
        (PRICING_CONF, sz.PRICING_SCHEMA),
        (CONF / "blue_whale_pv_bess_sizing.yaml", sz.SIZING_SCHEMA),
        (REG_CONF, sz.REGULATORY_SCHEMA),
    ):
        version = _yaml(path)["schema_version"]
        assert version == f"blue_whale_{family}", path.name
        sz._check_schema(version, family, path.stem)


def test_project_and_unit_schemas_cannot_stand_in_for_each_other() -> None:
    with pytest.raises(ValueError, match="sizing.schema_version"):
        sz._check_schema(sz.PROJECT_SIZING_SCHEMA, sz.SIZING_SCHEMA, "sizing")
    unit_sizing = _yaml(CONF / "blue_whale_pv_bess_sizing.yaml")["schema_version"]
    with pytest.raises(ValueError, match="sizing.schema_version"):
        sz._check_schema(unit_sizing, sz.PROJECT_SIZING_SCHEMA, "sizing")


def test_a_wrong_pricing_or_regulatory_schema_is_refused() -> None:
    pricing = _yaml(PRICING_CONF)
    sz.Pricing.from_mapping(pricing)
    with pytest.raises(ValueError, match="pricing.schema_version"):
        sz.Pricing.from_mapping({**pricing, "schema_version": "blue_whale_pricing_v1"})
    reg = _yaml(REG_CONF)
    with pytest.raises(ValueError, match="regulatory.schema_version"):
        sz.RegulatoryBasis.from_mapping({**reg, "schema_version": "pucsl_fit_2025_v1"})
    other = {**reg, "schema_version": "other_site_pucsl_fit_2026_v1"}
    assert sz.RegulatoryBasis.from_mapping(other) == sz.RegulatoryBasis.from_mapping(
        reg
    )


# ---------------------------------------------------------------------------
# L-5: the readings are named by the regulatory config
# ---------------------------------------------------------------------------
def _renamed_regulatory(names: Dict[str, str]) -> Dict[str, Any]:
    reg = copy.deepcopy(_yaml(REG_CONF))
    lim = reg["standardised_ppa_limit"]
    lim["readings"] = {names.get(k, k): v for k, v in lim["readings"].items()}
    return reg


def test_regulatory_readings_keep_their_config_names_and_order() -> None:
    reg = _yaml(REG_CONF)
    basis = sz.RegulatoryBasis.from_mapping(reg)
    assert (
        basis.readings == tuple(reg["standardised_ppa_limit"]["readings"]) == ("A", "B")
    )
    renamed = sz.RegulatoryBasis.from_mapping(
        _renamed_regulatory({"A": "combined", "B": "export"})
    )
    assert renamed.readings == ("combined", "export")
    # Config order, not sorted order (#1725 assurance A-1): zeta comes before alpha.
    unsorted = sz.RegulatoryBasis.from_mapping(
        _renamed_regulatory({"A": "zeta", "B": "alpha"})
    )
    assert unsorted.readings == ("zeta", "alpha")
    assert dataclasses.replace(renamed, readings=basis.readings) == basis
    one = copy.deepcopy(reg)
    one["standardised_ppa_limit"]["readings"] = {"only": "One reading."}
    assert sz.RegulatoryBasis.from_mapping(one).readings == ("only",)


@pytest.mark.parametrize(
    "readings",
    [{}, ["A", "B"], {"committed": "x"}, {"by_reading": "x"}, {"": "x"}, {1: "x"}],
)
def test_malformed_regulatory_readings_are_refused(readings: Any) -> None:
    reg = copy.deepcopy(_yaml(REG_CONF))
    reg["standardised_ppa_limit"]["readings"] = readings
    with pytest.raises(ValueError, match="readings must map one or more reading names"):
        sz.RegulatoryBasis.from_mapping(reg)


def _read_repo(rel: str) -> Any:
    text = (REPO_ROOT / rel).read_text()
    return (
        json.loads(text)
        if rel.endswith((".json", ".geojson"))
        else yaml.safe_load(text)
    )


@pytest.fixture(scope="module")
def site() -> Dict[str, Any]:
    pytest.importorskip("pvlib")
    pytest.importorskip("shapely")
    pytest.importorskip("pyproj")
    return sz.site_context(_yaml(UNIT_CONF), _read_repo)


def _small_project(names: Dict[str, str]) -> Dict[str, Any]:
    """A two-point, two-trial project run with its readings renamed by ``names``."""
    cfg = sz_runner.config_from_block(
        _yaml(SOLAR_BESS)["solar_storage_sizing"],
        _yaml(METHOD_CONF)["method"],
        scenario_label="scenarios/blue_whale_solar_bess_lot5b_2026.yaml",
    )
    cfg["grid"] = {
        **cfg["grid"],
        "pv_tables": ["land_max"],
        "pv_ac_mw": [5.0],
        "bess_power_mw": [4.0, 5.0],
    }
    cfg["monte_carlo"] = {**cfg["monte_carlo"], "n_trials": 2}
    cfg["sensitivities"] = {
        **cfg["sensitivities"],
        "one_at_a_time": [],
        "break_even": [],
    }
    readings = cfg["readings"]
    cfg["readings"] = {
        names.get(k, k): v for k, v in readings.items() if k != "committed"
    }
    cfg["readings"]["committed"] = names.get(
        readings["committed"], readings["committed"]
    )
    for role in cfg["recommendation"].values():
        if isinstance(role, dict) and "reading" in role:
            role["reading"] = names.get(role["reading"], role["reading"])
    return cfg


def _project_run(cfg: Dict[str, Any], reg: Dict[str, Any], site: Dict[str, Any]) -> Any:
    from analytics.evaluation_v14 import evaluate_with_overrides

    return sz.run_project_sizing(
        cfg,
        unit_cfg=_yaml(UNIT_CONF),
        pricing_cfg=_yaml(PRICING_CONF),
        regulatory_cfg=reg,
        scenario=_yaml(SCENARIO),
        site=site,
        evaluator=evaluate_with_overrides,
    )


def _rename_key(key: str, names: Dict[str, str]) -> str:
    """A reading's name, or a per-reading key such as ``eligible_A``, under ``names``."""
    for old, new in names.items():
        if key == old:
            return new
        for prefix in ("eligible_", "rule_", "land_"):
            if key == prefix + old:
                return prefix + new
    return key


def _rename_keys(obj: Any, names: Dict[str, str]) -> Any:
    if isinstance(obj, dict):
        return {_rename_key(k, names): _rename_keys(v, names) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_rename_keys(v, names) for v in obj]
    if isinstance(obj, str):
        return names.get(obj, obj)
    if isinstance(obj, float) and math.isnan(obj):
        return "nan"
    return obj


def test_renamed_readings_give_the_same_run_under_their_new_names(
    site: Dict[str, Any],
) -> None:
    """A site whose regulator names its readings differently sizes the same way."""
    names = {"A": "combined", "B": "export"}
    base = _project_run(_small_project({}), _yaml(REG_CONF), site)
    renamed = _project_run(_small_project(names), _renamed_regulatory(names), site)
    want = _rename_keys(dataclasses.asdict(base), names)
    got = _rename_keys(dataclasses.asdict(renamed), {})
    assert got == want
    assert list(renamed.recommendation["by_reading"]) == ["combined", "export"]


def test_sizing_readings_must_be_the_regulatory_ones(site: Dict[str, Any]) -> None:
    names = {"A": "combined", "B": "export"}
    # The sizing config keeps A and B while the regulatory config renames them.
    with pytest.raises(ValueError, match="readings: missing keys"):
        _project_run(_small_project({}), _renamed_regulatory(names), site)
    cfg = _small_project(names)
    cfg["readings"]["committed"] = "A"
    with pytest.raises(
        ValueError, match="readings.committed must be one of combined, export"
    ):
        _project_run(cfg, _renamed_regulatory(names), site)


# ---------------------------------------------------------------------------
# L-8: the project-IRR sentinel reads the status
# ---------------------------------------------------------------------------
def test_the_status_literal_is_the_engines_constant() -> None:
    from analytics.core.metrics import PROJECT_IRR_COMPUTED

    assert sz._PROJECT_IRR_COMPUTED == PROJECT_IRR_COMPUTED


@pytest.mark.parametrize(
    "kpis, want",
    [
        ({"project_irr": 0.0}, 0.0),  # the numeric surface: a solved break-even
        ({"project_irr": 0.0, "project_irr_status": "computed"}, 0.0),
        ({"project_irr": -0.031, "project_irr_status": "computed"}, -0.031),
        ({"project_irr": 0.124}, 0.124),
        ({}, None),  # undefined: the numeric surface leaves the key out (#1494)
        ({"project_irr": None, "project_irr_status": "undefined"}, None),
        ({"project_irr": 0.0, "project_irr_status": "not_computed"}, None),
        # #1820 (#1725 A-2): an explicit None status is no status; any other status that
        # is not exactly "computed" (empty, another case, not a string) is no IRR.
        ({"project_irr": 0.05, "project_irr_status": None}, 0.05),
        ({"project_irr": 0.05, "project_irr_status": ""}, None),
        ({"project_irr": 0.05, "project_irr_status": "COMPUTED"}, None),
        ({"project_irr": 0.05, "project_irr_status": "Computed"}, None),
        ({"project_irr": 0.05, "project_irr_status": 1}, None),
        ({"project_irr": 0.05, "project_irr_status": True}, None),
    ],
)
def test_project_irr_reads_the_engines_status(kpis: Dict[str, Any], want: Any) -> None:
    got = sz._project_irr(kpis)
    if want is None:
        assert math.isnan(got)
    else:
        assert got == want


# ---------------------------------------------------------------------------
# #1590 D-1: annual_energy books energy by the dispatcher's rule
# ---------------------------------------------------------------------------
def _sums() -> sz.ColumnSums:
    one = np.array([1.0])
    return sz.ColumnSums(
        pv_mwh=one * 100.0,
        charge_mwh=one * 30.0,
        discharge_mwh_by_window={"evening": one * 25.0},
        pv_export_mwh_by_window={"evening": one * 10.0, "outside": one * 40.0},
        curtailed_mwh=one * 0.0,
        soc_end_mwh=one * 5.0,
        initial_soc_mwh=one * 5.0,
        iterations=np.array([1], dtype=np.int64),
    )


@dataclasses.dataclass(frozen=True)
class _EverythingPriority(pbd.TariffConfig):
    """A tariff whose rule books every kWh at the priority rate."""

    def rate_name(self, window_rate: Any, year: int) -> str:
        return "priority"


def test_annual_energy_books_energy_through_rate_name() -> None:
    unit = _yaml(UNIT_CONF)
    tariff = pbd.TariffConfig.from_mapping(unit["tariff"])
    windows = [pbd.Window("evening", 18 * 60, 22 * 60, "priority")]
    kw: Dict[str, Any] = dict(
        windows=windows, pv_factor=1.0, usable_mwh=20.0, discharge_efficiency=0.9
    )
    term = tariff.priority_term_years
    inside = sz.annual_energy(_sums(), 0, tariff=tariff, year=term, **kw)
    after = sz.annual_energy(_sums(), 0, tariff=tariff, year=term + 1, **kw)
    assert inside.export_mwh_by_rate == {"priority": 35.0, "other": 40.0}
    assert after.export_mwh_by_rate == {"priority": 0.0, "other": 75.0}
    # The booking follows the tariff's rule, whatever it says: no copy of it is left here.
    spy = _EverythingPriority(**dataclasses.asdict(tariff))
    moved = sz.annual_energy(_sums(), 0, tariff=spy, year=term + 1, **kw)
    assert moved.export_mwh_by_rate == {"priority": 35.0, "other": 40.0}
    calls: List[Any] = []

    class _Counting(pbd.TariffConfig):
        def rate_name(self, window_rate: Any, year: int) -> str:
            calls.append((window_rate, year))
            return super().rate_name(window_rate, year)

    sz.annual_energy(
        _sums(), 0, tariff=_Counting(**dataclasses.asdict(tariff)), year=3, **kw
    )
    assert calls == [("priority", 3)]
