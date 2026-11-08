"""Blue Whale PR 6: the wind and BESS capex blend, and the solar resource at the site.

Two I/O-free calculations read by ``scripts/run_blue_whale_capex_solar_resource_v14.py`` from
``conf/blue_whale_capex_solar_resource.yaml`` (FRAMEWORK-02: strict keys, fail loud).

**Capex blend.** A landed-cost build-up whose turbine (or BESS equipment) price is a weighted
blend of China FOB evidence from the web and internal anchors::

    wind  = CIF_blend x (1 + ins) + levies(CIF) + EPC wrap on (CIF + inland) + inland
            + BoP_blend x k_single + VAT on the domestic share (full-stack posture only)
    bess  = ((EQ_blend + levies(EQ) + BoP) x (1 + epc) + augmentation) / (1 - land share)

``levies`` follows :mod:`finance.import_levies`'s cascade (duties on CIF; VAT on CIF plus
duties, and on the domestic share when ``vat_on_domestic``; zero VAT when relieved).
``k_single`` is the single-machine factor from the knowledge base's MW^0.7 rule for shared
infrastructure. Each case (low, mode, high) takes every uncertain input at that case. Private
anchors are passed in at run time and never stored; only blended results leave this module.

**Solar resource.** The repository's pvlib chain (the TMY branch of
:func:`solar_resource.pv_producer.compute_solar_aep`), stepped so that each loss is visible:
monthly and annual GHI, DNI, DHI and plane-of-array irradiation, the DC and AC energy, the
specific yield, the performance ratio and its loss breakdown, and an independent isotropic-sky
plane-of-array irradiation computed without pvlib.

pvlib is an optional dependency, imported only inside the solar functions (FRAMEWORK-01).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np

__all__ = [
    "CASES",
    "LevyPosture",
    "blend_weights_ok",
    "bess_all_in",
    "isotropic_poa_w_m2",
    "levy_lines",
    "parse_levy_postures",
    "pricing_build_up",
    "single_machine_factor",
    "solar_resource_summary",
    "wind_all_in",
]

#: The three cases every uncertain input carries, in output order.
CASES: Tuple[str, str, str] = ("low", "mode", "high")

#: Weights must sum to one within this tolerance.
WEIGHT_TOLERANCE = 1e-12

_HOURS = 8760.0


def _strict(raw: Mapping[str, Any], keys: Sequence[str], where: str) -> None:
    """Refuse a missing or unknown key (FRAMEWORK-02)."""
    if not isinstance(raw, Mapping):
        raise ValueError(f"{where} must be a mapping")
    missing = [k for k in keys if k not in raw]
    unknown = [k for k in raw if k not in keys]
    if missing or unknown:
        raise ValueError(
            f"{where}: missing {missing}, unknown {sorted(map(str, unknown))}"
        )


def _case(raw: Mapping[str, Any], where: str) -> Dict[str, float]:
    """A low/mode/high mapping of finite numbers with low <= mode <= high."""
    _strict(raw, CASES, where)
    out = {c: float(raw[c]) for c in CASES}
    if not all(math.isfinite(v) for v in out.values()):
        raise ValueError(f"{where}: values must be finite")
    if not out["low"] <= out["mode"] <= out["high"]:
        raise ValueError(f"{where}: needs low <= mode <= high, got {out}")
    return out


def blend_weights_ok(weights: Sequence[float]) -> bool:
    """True when every weight is in [0, 1] and they sum to one."""
    return all(0.0 <= w <= 1.0 for w in weights) and abs(sum(weights) - 1.0) <= (
        WEIGHT_TOLERANCE
    )


@dataclass(frozen=True)
class LevyPosture:
    """One Sri Lankan import-levy posture (rates from the repository's configs)."""

    cid_pct: float
    pal_pct: float
    sscl_import_pct: float
    vat_pct: float
    vat_relieved: bool
    vat_on_domestic: bool
    source: str

    @property
    def duty_rate(self) -> float:
        """CID + PAL + SSCL, applied flat on CIF."""
        return self.cid_pct + self.pal_pct + self.sscl_import_pct


def parse_levy_postures(raw: Mapping[str, Any]) -> Dict[str, LevyPosture]:
    """Build the named postures, refusing a missing or unknown key."""
    keys = (
        "cid_pct",
        "pal_pct",
        "sscl_import_pct",
        "vat_pct",
        "vat_relieved",
        "vat_on_domestic",
        "source",
    )
    out: Dict[str, LevyPosture] = {}
    for name, block in raw.items():
        _strict(block, keys, f"levy_postures.{name}")
        rates = [float(block[k]) for k in keys[:4]]
        if any(not 0.0 <= r < 1.0 for r in rates):
            raise ValueError(f"levy_postures.{name}: rates must be fractions in [0, 1)")
        out[str(name)] = LevyPosture(
            cid_pct=rates[0],
            pal_pct=rates[1],
            sscl_import_pct=rates[2],
            vat_pct=rates[3],
            vat_relieved=bool(block["vat_relieved"]),
            vat_on_domestic=bool(block["vat_on_domestic"]),
            source=str(block["source"]),
        )
    return out


def levy_lines(
    cif: float, domestic: float, posture: LevyPosture
) -> Tuple[float, float]:
    """Duties and VAT on one unit of capex (finance.import_levies's cascade).

    Args:
        cif: The imported (CIF) value.
        domestic: The domestic spend, VAT-charged only under ``vat_on_domestic``.
        posture: The levy posture.

    Returns:
        ``(duties, vat)`` in the units of ``cif``.
    """
    duties = cif * posture.duty_rate
    if posture.vat_relieved:
        return duties, 0.0
    base = cif + duties + (domestic if posture.vat_on_domestic else 0.0)
    return duties, base * posture.vat_pct


def single_machine_factor(
    reference_mw: float, machine_mw: float, exponent: float, shared_fraction: float
) -> float:
    """Per-kW BoP multiplier for a single machine against a reference farm.

    Shared infrastructure scales as MW^exponent, so its per-kW cost scales as
    ``(reference_mw / machine_mw) ** (1 - exponent)``; the rest scales linearly.
    """
    if machine_mw <= 0 or reference_mw <= 0 or not 0.0 <= shared_fraction <= 1.0:
        raise ValueError("single_machine_factor: bad inputs")
    scale = float((reference_mw / machine_mw) ** (1.0 - exponent))
    return (1.0 - shared_fraction) + shared_fraction * scale


def _weighted(values: Mapping[str, float], weights: Mapping[str, float]) -> float:
    """The weighted blend, refusing weights that do not sum to one."""
    if set(values) != set(weights):
        raise ValueError("blend: values and weights name different anchors")
    if not blend_weights_ok(list(weights.values())):
        raise ValueError(f"blend weights must sum to 1, got {dict(weights)}")
    return float(sum(values[k] * weights[k] for k in sorted(values)))


def _anchor_value(
    anchor: Mapping[str, Any],
    name: str,
    private: Mapping[str, float],
    field: str,
) -> float:
    """A public anchor's stated value, or the private value supplied at run time."""
    kind = anchor.get("kind")
    if kind == "public":
        if field not in anchor:
            raise ValueError(f"public anchor {name} needs {field}")
        return float(anchor[field])
    if kind == "private":
        if field in anchor:
            raise ValueError(
                f"private anchor {name} must not carry a value in the config"
            )
        if name not in private:
            raise ValueError(f"private anchor {name} was not supplied at run time")
        return float(private[name])
    raise ValueError(f"anchor {name}: kind must be public or private")


def wind_all_in(
    cfg: Mapping[str, Any],
    postures: Mapping[str, LevyPosture],
    cny_per_usd: float,
    private: Mapping[str, float],
) -> Dict[str, Dict[str, float]]:
    """The single-turbine all-in capex, USD per kW, for each case.

    Args:
        cfg: The ``wind`` block of the config.
        postures: The levy postures by name.
        cny_per_usd: The exchange rate for CNY figures.
        private: Private anchor values by anchor name (``W-DB150-DEV`` turbine supply in
            USD/kW, ``W-DB150-DEV-BOP`` BoP in USD/kW), supplied at run time.

    Returns:
        For each case, the component lines and ``all_in_usd_per_kw``.
    """
    _strict(
        cfg,
        (
            "rated_kw",
            "turbine_supply",
            "inland_transport_usd_per_kw",
            "epc_margin_pct",
            "levy_posture",
            "bop",
            "single_machine",
        ),
        "wind",
    )
    ts = cfg["turbine_supply"]
    _strict(
        ts,
        ("web", "anchors", "freight_insurance_pct_for_fob", "marine_insurance_pct"),
        "wind.turbine_supply",
    )
    web = ts["web"]
    _strict(web, ("source", "weight", "cny_per_kw", "includes_freight"), "wind.web")
    if not bool(web["includes_freight"]):
        raise ValueError("wind.web: the cited export price includes freight")
    web_usd = {
        c: v / cny_per_usd for c, v in _case(web["cny_per_kw"], "wind.web").items()
    }
    fob_freight = float(ts["freight_insurance_pct_for_fob"])
    insurance = float(ts["marine_insurance_pct"])
    anchors = ts["anchors"]
    supply_values: Dict[str, float] = {}
    weights: Dict[str, float] = {"web": float(web["weight"])}
    for name, anchor in anchors.items():
        value = _anchor_value(anchor, name, private, "usd_per_kw")
        supply_values[name] = value * (
            1.0 if bool(anchor["includes_freight"]) else 1.0 + fob_freight
        )
        weights[name] = float(anchor["weight"])
    bop_anchors = cfg["bop"]["anchors"]
    bop_values = {
        n: _anchor_value(a, f"{n}", private, "usd_per_kw")
        for n, a in bop_anchors.items()
    }
    bop_weights = {n: float(a["weight"]) for n, a in bop_anchors.items()}
    bop_blend = _weighted(bop_values, bop_weights)
    bop_case = {
        "low": min(bop_values.values()),
        "mode": bop_blend,
        "high": max(bop_values.values()),
    }
    inland = _case(cfg["inland_transport_usd_per_kw"], "wind.inland")
    epc = _case(cfg["epc_margin_pct"], "wind.epc_margin_pct")
    sm = cfg["single_machine"]
    _strict(sm, ("reference_mw", "exponent", "shared_fraction"), "wind.single_machine")
    shared = _case(sm["shared_fraction"], "wind.single_machine.shared_fraction")
    machine_mw = float(cfg["rated_kw"]) / 1000.0
    out: Dict[str, Dict[str, float]] = {}
    for c in CASES:
        cif = _weighted({"web": web_usd[c], **supply_values}, weights) * (
            1.0 + insurance
        )
        k = single_machine_factor(
            float(sm["reference_mw"]), machine_mw, float(sm["exponent"]), shared[c]
        )
        bop = bop_case[c] * k
        wrap = (cif + inland[c]) * epc[c]
        domestic = inland[c] + wrap + bop
        duties, vat = levy_lines(cif, domestic, postures[cfg["levy_posture"][c]])
        total = cif + duties + vat + domestic
        out[c] = {
            "turbine_cif_usd_per_kw": cif,
            "duties_usd_per_kw": duties,
            "vat_usd_per_kw": vat,
            "inland_transport_usd_per_kw": inland[c],
            "epc_wrap_usd_per_kw": wrap,
            "bop_farm_usd_per_kw": bop_case[c],
            "single_machine_factor": k,
            "bop_single_usd_per_kw": bop,
            "all_in_usd_per_kw": total,
        }
    return out


def bess_all_in(
    cfg: Mapping[str, Any],
    postures: Mapping[str, LevyPosture],
    cny_per_usd: float,
    private: Mapping[str, float],
    private_dc_share: Mapping[str, float],
) -> Dict[str, Dict[str, float]]:
    """The BESS all-in capex, USD per kWh contracted, for each case.

    Args:
        cfg: The ``bess`` block of the config.
        postures: The levy postures by name.
        cny_per_usd: The exchange rate for CNY figures.
        private: Private equipment anchors (USD per kWh contracted, before freight).
        private_dc_share: The DC block's share of equipment for every equipment anchor that
            states none publicly (public anchors whose split is private included).

    Returns:
        For each case, the component lines (DC block, PCS and EMS, levies, BoP, EPC,
        augmentation, land and auxiliaries) and ``all_in_usd_per_kwh``.
    """
    _strict(
        cfg,
        (
            "equipment",
            "bop_usd_per_kwh",
            "epc_margin_pct",
            "augmentation_usd_per_kwh",
            "land_and_auxiliaries_share",
            "levy_posture",
        ),
        "bess",
    )
    eq = cfg["equipment"]
    _strict(eq, ("web", "anchors"), "bess.equipment")
    web = eq["web"]
    _strict(
        web,
        (
            "weight",
            "source",
            "low_source",
            "cny_per_wh",
            "vat_in_price_pct",
            "dc_per_contracted",
            "freight_insurance_pct",
            "dc_block_share",
        ),
        "bess.web",
    )
    freight = float(web["freight_insurance_pct"])
    web_cif = {
        c: v
        * 1000.0
        / (1.0 + float(web["vat_in_price_pct"]))
        / cny_per_usd
        * float(web["dc_per_contracted"])
        * (1.0 + freight)
        for c, v in _case(web["cny_per_wh"], "bess.web.cny_per_wh").items()
    }
    values: Dict[str, float] = {}
    weights: Dict[str, float] = {"web": float(web["weight"])}
    shares: Dict[str, float] = {"web": float(web["dc_block_share"])}
    for name, anchor in eq["anchors"].items():
        value = _anchor_value(anchor, name, private, "usd_per_kwh")
        values[name] = value * (
            1.0 if bool(anchor["includes_freight"]) else 1.0 + freight
        )
        weights[name] = float(anchor["weight"])
        if name not in private_dc_share:
            raise ValueError(f"no DC-block share supplied for {name}")
        shares[name] = float(private_dc_share[name])
    dc_share = _weighted(shares, weights)
    bop = _case(cfg["bop_usd_per_kwh"], "bess.bop")
    epc = _case(cfg["epc_margin_pct"], "bess.epc")
    aug = float(cfg["augmentation_usd_per_kwh"])
    land = float(cfg["land_and_auxiliaries_share"])
    if not 0.0 <= land < 1.0:
        raise ValueError("bess.land_and_auxiliaries_share must be in [0, 1)")
    out: Dict[str, Dict[str, float]] = {}
    for c in CASES:
        cif = _weighted({"web": web_cif[c], **values}, weights)
        posture = postures[cfg["levy_posture"][c]]
        duties, vat_import = levy_lines(cif, 0.0, posture)
        landed = cif + duties + vat_import
        wrapped = (landed + bop[c]) * (1.0 + epc[c])
        vat_domestic = (
            (wrapped - landed) * posture.vat_pct
            if posture.vat_on_domestic and not posture.vat_relieved
            else 0.0
        )
        pre_land = wrapped + vat_domestic + aug
        total = pre_land / (1.0 - land)
        out[c] = {
            "equipment_cif_usd_per_kwh": cif,
            "dc_block_cif_usd_per_kwh": cif * dc_share,
            "pcs_ems_cif_usd_per_kwh": cif * (1.0 - dc_share),
            "dc_block_share": dc_share,
            "duties_usd_per_kwh": duties,
            "vat_usd_per_kwh": vat_import + vat_domestic,
            "landed_equipment_usd_per_kwh": landed,
            "bop_usd_per_kwh": bop[c],
            "epc_margin_usd_per_kwh": wrapped - landed - bop[c],
            "augmentation_usd_per_kwh": aug,
            "land_and_auxiliaries_usd_per_kwh": total - pre_land,
            "all_in_usd_per_kwh": total,
        }
    return out


def pricing_build_up(mode: Mapping[str, float], land_share: float) -> Dict[str, float]:
    """The mode as ``conf/blue_whale_pv_bess_pricing.yaml``'s four build-up lines.

    The pricing parser checks ``(equipment + bop + augmentation) / (1 - land) = all-in``.
    BoP carries the BoP with its share of the EPC margin; equipment carries everything else
    before augmentation (landed equipment, its EPC margin and any domestic VAT), so the four
    lines reproduce the all-in exactly.
    """
    scale = 1.0 + (
        mode["epc_margin_usd_per_kwh"]
        / (mode["landed_equipment_usd_per_kwh"] + mode["bop_usd_per_kwh"])
    )
    bop = mode["bop_usd_per_kwh"] * scale
    equipment = (
        mode["all_in_usd_per_kwh"] * (1.0 - land_share)
        - bop
        - mode["augmentation_usd_per_kwh"]
    )
    return {
        "equipment_usd_per_kwh_base": equipment,
        "bop_usd_per_kwh_base": bop,
        "augmentation_reserve_usd_per_kwh_base": mode["augmentation_usd_per_kwh"],
        "land_and_auxiliaries_share_base": land_share,
    }


# --------------------------------------------------------------------------- solar


def _require_pvlib() -> Any:
    """Import pvlib or raise an actionable error (FRAMEWORK-01 optional dependency)."""
    try:
        import pvlib
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            "The solar resource summary needs pvlib: pip install -e '.[solar]'"
        ) from exc
    return pvlib


def isotropic_poa_w_m2(
    ghi: np.ndarray,
    dni: np.ndarray,
    dhi: np.ndarray,
    zenith_deg: np.ndarray,
    sun_azimuth_deg: np.ndarray,
    tilt_deg: float,
    surface_azimuth_deg: float,
    albedo: float,
) -> np.ndarray:
    """Plane-of-array irradiance by the isotropic sky model, in closed form (no pvlib).

    ``POA = DNI cos(AOI)+ + DHI (1 + cos b) / 2 + GHI albedo (1 - cos b) / 2``, with
    ``cos(AOI) = cos z cos b + sin z sin b cos(az_sun - az_surface)``.
    """
    z = np.radians(zenith_deg)
    b = math.radians(tilt_deg)
    cos_aoi = np.cos(z) * math.cos(b) + np.sin(z) * math.sin(b) * np.cos(
        np.radians(sun_azimuth_deg - surface_azimuth_deg)
    )
    beam = dni * np.clip(cos_aoi, 0.0, None)
    sky = dhi * (1.0 + math.cos(b)) / 2.0
    ground = ghi * albedo * (1.0 - math.cos(b)) / 2.0
    return np.asarray(np.clip(beam + sky + ground, 0.0, None), dtype=np.float64)


def solar_resource_summary(
    tmy: Any,
    *,
    latitude: float,
    longitude: float,
    altitude_m: float,
    timezone: str,
    tilt_deg: float,
    azimuth_deg: float,
    dc_mwp: float,
    ac_mw: float,
    inverter_eff_nom: float,
    gamma_pdc_per_c: float,
    system_loss_pct: float,
    albedo: float,
) -> Dict[str, Any]:
    """The resource and the array's yield, stepped through the repository's pvlib chain.

    Args:
        tmy: The frozen hourly TMY (``ghi``, ``dni``, ``dhi``, ``temp_air``,
            ``wind_speed``; UTC index), as :func:`solar_resource.pv_producer._load_tmy`
            returns it.
        latitude, longitude, altitude_m, timezone: The site for solar position.
        tilt_deg, azimuth_deg: Fixed-tilt geometry (azimuth 180 = south).
        dc_mwp, ac_mw: DC nameplate and the inverters' AC limit.
        inverter_eff_nom: PVWatts nominal inverter efficiency.
        gamma_pdc_per_c: PVWatts power temperature coefficient (1/C).
        system_loss_pct: The flat post-inverter loss stack.
        albedo: Ground reflectance for the transposition.

    Returns:
        Annual and monthly irradiation (kWh/m2), energy (MWh), specific yield, performance
        ratio with its loss breakdown, capacity factors, and the isotropic-sky check.
    """
    pvlib = _require_pvlib()
    times = tmy.index
    loc = pvlib.location.Location(latitude, longitude, tz=timezone, altitude=altitude_m)
    solpos = loc.get_solarposition(times)
    dni_extra = pvlib.irradiance.get_extra_radiation(times)
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=tilt_deg,
        surface_azimuth=azimuth_deg,
        solar_zenith=solpos["apparent_zenith"],
        solar_azimuth=solpos["azimuth"],
        dni=tmy["dni"],
        ghi=tmy["ghi"],
        dhi=tmy["dhi"],
        dni_extra=dni_extra,
        model="haydavies",
    )["poa_global"].clip(lower=0.0)
    poa_iso_pvlib = pvlib.irradiance.get_total_irradiance(
        surface_tilt=tilt_deg,
        surface_azimuth=azimuth_deg,
        solar_zenith=solpos["apparent_zenith"],
        solar_azimuth=solpos["azimuth"],
        dni=tmy["dni"],
        ghi=tmy["ghi"],
        dhi=tmy["dhi"],
        albedo=albedo,
        model="isotropic",
    )["poa_global"].clip(lower=0.0)
    poa_iso_closed = isotropic_poa_w_m2(
        tmy["ghi"].to_numpy(dtype=float),
        tmy["dni"].to_numpy(dtype=float),
        tmy["dhi"].to_numpy(dtype=float),
        solpos["apparent_zenith"].to_numpy(dtype=float),
        solpos["azimuth"].to_numpy(dtype=float),
        tilt_deg,
        azimuth_deg,
        albedo,
    )
    cell = pvlib.temperature.faiman(
        poa, temp_air=tmy["temp_air"], wind_speed=tmy["wind_speed"]
    )
    pdc0_w = dc_mwp * 1.0e6
    dc = pvlib.pvsystem.pvwatts_dc(poa, cell, pdc0_w, gamma_pdc_per_c)
    ac_limit_w = ac_mw * 1.0e6
    ac = pvlib.inverter.pvwatts(
        dc, pdc0=ac_limit_w / inverter_eff_nom, eta_inv_nom=inverter_eff_nom
    ).clip(upper=ac_limit_w)
    retention = 1.0 - system_loss_pct / 100.0
    net = ac * retention

    def kwh_m2(series: Any) -> float:
        return float(series.sum()) / 1000.0

    ref_mwh = kwh_m2(poa) * dc_mwp  # POA x kWp: the energy at STC efficiency
    dc_mwh = float(dc.sum()) / 1.0e6
    ac_mwh = float(ac.sum()) / 1.0e6
    net_mwh = float(net.sum()) / 1.0e6
    specific_yield = net_mwh * 1000.0 / (dc_mwp * 1000.0)
    pr = specific_yield / kwh_m2(poa)
    month = times.month
    frame = {
        "ghi": tmy["ghi"],
        "dni": tmy["dni"],
        "dhi": tmy["dhi"],
        "poa": poa,
    }
    monthly: List[Dict[str, float]] = []
    for m in range(1, 13):
        sel = month == m
        row: Dict[str, float] = {"month": float(m)}
        for key, series in frame.items():
            row[f"{key}_kwh_m2"] = kwh_m2(series[sel])
        row["net_ac_mwh"] = float(net[sel].sum()) / 1.0e6
        row["specific_yield_kwh_per_kwp"] = row["net_ac_mwh"] / dc_mwp
        row["performance_ratio"] = row["specific_yield_kwh_per_kwp"] / row["poa_kwh_m2"]
        monthly.append(row)
    clip_hours = int(((dc * inverter_eff_nom) > ac_limit_w * (1.0 + 1e-12)).sum())
    return {
        "annual": {
            "ghi_kwh_m2": kwh_m2(tmy["ghi"]),
            "dni_kwh_m2": kwh_m2(tmy["dni"]),
            "dhi_kwh_m2": kwh_m2(tmy["dhi"]),
            "poa_kwh_m2": kwh_m2(poa),
            "poa_isotropic_pvlib_kwh_m2": kwh_m2(poa_iso_pvlib),
            "poa_isotropic_closed_form_kwh_m2": float(poa_iso_closed.sum()) / 1000.0,
            "mean_ambient_c": float(tmy["temp_air"].mean()),
            "poa_weighted_cell_c": float((cell * poa).sum() / poa.sum()),
            "reference_mwh": ref_mwh,
            "dc_mwh": dc_mwh,
            "ac_mwh": ac_mwh,
            "net_ac_mwh": net_mwh,
            "specific_yield_kwh_per_kwp": specific_yield,
            "performance_ratio": pr,
            "capacity_factor_ac": net_mwh / (ac_mw * _HOURS),
            "capacity_factor_dc": net_mwh / (dc_mwp * _HOURS),
            "clipping_hours": float(clip_hours),
        },
        "loss_breakdown_of_reference": {
            "temperature_and_irradiance": (dc_mwh - ref_mwh) / ref_mwh,
            "inverter_efficiency_and_clipping": (ac_mwh - dc_mwh) / ref_mwh,
            "system_losses": (net_mwh - ac_mwh) / ref_mwh,
            "total": (net_mwh - ref_mwh) / ref_mwh,
        },
        "monthly": monthly,
    }
