"""Power-curve sourcing for any turbine (issue #181).

Two ways to bring a turbine power curve into the project's store
(``wind_resource/config/power_curves.yaml``, consumed by :class:`EnergyCalculator`):

1. **Fetch** from the open turbine library (oedb, via ``windpowerlib``) for turbines that
   are in it -- legacy/mid machines (Vestas, Enercon, Siemens SWT, GE, Nordex).
2. **Manual** entry of a manufacturer / spec-sheet curve for turbines that are NOT in the
   open DB -- the latest large machines (Envision EN-171, Siemens Gamesa SG 8-14 MW,
   Goldwind). The curve points come from the OEM's certified spec; this tool validates and
   records them with provenance (it never fabricates curve data).

Both paths validate the curve (length, monotonicity, rated consistency) and write a block
with a ``provenance`` stamp. GWTF: typed, config-first, no hardcoded turbine constants;
``windpowerlib`` is an optional (lazy) import needed only for the fetch path.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml

logger = logging.getLogger(__name__)

DEFAULT_STORE = Path(__file__).parent / "config" / "power_curves.yaml"


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _rated_wind_speed(
    wind_speeds_ms: Sequence[float], power_kw: Sequence[float], rated_kw: float
) -> Optional[float]:
    """First wind speed at which the curve reaches ~rated power."""
    for w, p in zip(wind_speeds_ms, power_kw):
        if rated_kw > 0 and p >= 0.99 * rated_kw:
            return float(w)
    return None


@dataclass
class PowerCurve:
    """A turbine power curve in the project's store schema (+ provenance)."""

    key: str
    manufacturer: str
    model: str
    rated_capacity_kw: float
    wind_speeds_ms: List[float]
    power_kw: List[float]
    hub_heights_m: List[float] = field(default_factory=list)
    cut_in_ms: float = 3.0
    rated_ms: Optional[float] = None
    cut_out_ms: float = 25.0
    # IEC thrust-coefficient curve (Ct), aligned to ``wind_speeds_ms``. Populated
    # only when the source provides it (e.g. IEA/DTU reference designs); ``None``
    # for sources that ship power-only. Captured for the oem-parser thrust path (#166).
    thrust_coeffs: Optional[List[float]] = None
    source: str = "manual"
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_yaml_block(self) -> Dict[str, Any]:
        """Render as a ``{key: {...}}`` block matching power_curves.yaml."""
        block: Dict[str, Any] = {
            "manufacturer": self.manufacturer,
            "model": self.model,
            "rated_capacity_kw": self.rated_capacity_kw,
            "hub_heights": list(self.hub_heights_m),
            "cut_in": self.cut_in_ms,
            "rated": self.rated_ms,
            "cut_out": self.cut_out_ms,
            "power_curve": {
                "ws": [float(x) for x in self.wind_speeds_ms],
                "power": [float(x) for x in self.power_kw],
            },
        }
        if self.thrust_coeffs is not None:
            # Additive: existing consumers read only power_curve.{ws,power}; this
            # surfaces the source's thrust curve (Ct) for the #166 oem-parser path.
            block["thrust_curve"] = {
                "ws": [float(x) for x in self.wind_speeds_ms],
                "ct": [float(x) for x in self.thrust_coeffs],
            }
        block["provenance"] = {"source": self.source, **self.provenance}
        return {self.key: block}


def list_oedb_turbines(manufacturer: Optional[str] = None) -> Any:
    """List turbines available in the oedb open library (optionally filtered)."""
    from windpowerlib import get_turbine_types

    df = get_turbine_types(print_out=False)
    if manufacturer:
        mask = df["manufacturer"].astype(str).str.contains(manufacturer, case=False, na=False)
        df = df[mask]
    return df


def fetch_oedb_power_curve(
    turbine_type: str,
    *,
    hub_height_m: float = 100.0,
    manufacturer: str = "",
    key: Optional[str] = None,
) -> PowerCurve:
    """Fetch a turbine power curve from the oedb library via ``windpowerlib``.

    Raises ``ImportError`` if windpowerlib is absent, ``ValueError`` if the turbine has no
    power curve in the library.
    """
    try:
        from windpowerlib import WindTurbine
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "Fetching curves needs windpowerlib: pip install windpowerlib"
        ) from exc

    turbine = WindTurbine(turbine_type=turbine_type, hub_height=hub_height_m)
    if turbine.power_curve is None:
        raise ValueError(f"No power curve in the oedb library for {turbine_type!r}")
    ws = [float(x) for x in turbine.power_curve["wind_speed"]]
    power = [float(v) / 1000.0 for v in turbine.power_curve["value"]]  # W -> kW
    rated_kw = float(turbine.nominal_power) / 1000.0
    return PowerCurve(
        key=key or _slugify(f"{manufacturer}_{turbine_type}"),
        manufacturer=manufacturer or "unknown",
        model=turbine_type,
        rated_capacity_kw=rated_kw,
        wind_speeds_ms=ws,
        power_kw=power,
        hub_heights_m=[hub_height_m],
        rated_ms=_rated_wind_speed(ws, power, rated_kw),
        source="oedb_windpowerlib",
        provenance={
            "dataset": "OpenEnergy Platform (oedb) turbine library",
            "turbine_type": turbine_type,
        },
    )


def manual_power_curve(
    key: str,
    manufacturer: str,
    model: str,
    rated_capacity_kw: float,
    wind_speeds_ms: Sequence[float],
    power_kw: Sequence[float],
    *,
    hub_heights_m: Optional[Sequence[float]] = None,
    cut_in_ms: float = 3.0,
    cut_out_ms: float = 25.0,
    certificate: Optional[str] = None,
) -> PowerCurve:
    """Build a curve from manufacturer / spec-sheet points (e.g. Envision EN-171, SG models)."""
    ws = [float(x) for x in wind_speeds_ms]
    power = [float(x) for x in power_kw]
    prov: Dict[str, Any] = {"entry": "manual"}
    if certificate:
        prov["certificate"] = certificate
    return PowerCurve(
        key=key,
        manufacturer=manufacturer,
        model=model,
        rated_capacity_kw=float(rated_capacity_kw),
        wind_speeds_ms=ws,
        power_kw=power,
        hub_heights_m=[float(h) for h in (hub_heights_m or [])],
        cut_in_ms=cut_in_ms,
        rated_ms=_rated_wind_speed(ws, power, float(rated_capacity_kw)),
        cut_out_ms=cut_out_ms,
        source="manual",
        provenance=prov,
    )


def validate_power_curve(pc: PowerCurve, *, rated_tol_pct: float = 5.0) -> List[str]:
    """Sanity / IEC-style checks; returns a list of issues (empty == valid)."""
    issues: List[str] = []
    ws, power = pc.wind_speeds_ms, pc.power_kw
    if len(ws) != len(power):
        issues.append(f"ws/power length mismatch ({len(ws)} vs {len(power)})")
    if len(ws) < 3:
        issues.append("need at least 3 curve points")
    if any(b <= a for a, b in zip(ws, ws[1:])):
        issues.append("wind speeds must be strictly increasing")
    if any(p < -1e-9 for p in power):
        issues.append("power must be non-negative")
    if pc.rated_capacity_kw <= 0:
        issues.append("rated_capacity_kw must be positive")
    elif power:
        peak = max(power)
        if peak > pc.rated_capacity_kw * (1 + rated_tol_pct / 100.0):
            issues.append(
                f"peak power {peak:.0f} kW exceeds rated {pc.rated_capacity_kw:.0f} kW "
                f"by >{rated_tol_pct:.0f}%"
            )
        if peak < pc.rated_capacity_kw * (1 - rated_tol_pct / 100.0):
            issues.append(
                f"peak power {peak:.0f} kW never reaches rated {pc.rated_capacity_kw:.0f} kW"
            )
    if pc.thrust_coeffs is not None:
        if len(pc.thrust_coeffs) != len(ws):
            issues.append(
                f"thrust_coeffs length {len(pc.thrust_coeffs)} != ws length {len(ws)}"
            )
        elif any((c < -1e-9 or c > 1.2) for c in pc.thrust_coeffs):
            issues.append("thrust coefficients must be within [0, 1.2]")
    return issues


def add_curve_to_store(
    pc: PowerCurve, *, store_path: Path = DEFAULT_STORE, overwrite: bool = False
) -> Path:
    """Validate and append the curve to power_curves.yaml (preserving existing entries).

    Raises ``ValueError`` on validation failure and ``KeyError`` if the key already exists
    and ``overwrite`` is False.
    """
    store_path = Path(store_path)
    issues = validate_power_curve(pc)
    if issues:
        raise ValueError(f"Curve {pc.key!r} failed validation: {issues}")

    existing: Dict[str, Any] = {}
    if store_path.exists():
        existing = yaml.safe_load(store_path.read_text()) or {}
    if pc.key in existing and not overwrite:
        raise KeyError(
            f"Curve {pc.key!r} already in {store_path.name}; choose a new key or pass "
            "overwrite=True (which rewrites the file)."
        )

    if overwrite and pc.key in existing:
        existing.update(pc.to_yaml_block())
        store_path.write_text(yaml.safe_dump(existing, sort_keys=False))
    else:
        block = yaml.safe_dump(pc.to_yaml_block(), sort_keys=False, default_flow_style=False)
        with open(store_path, "a") as f:
            f.write(f"\n# Added via power_curve_sourcing (source: {pc.source})\n{block}")
    logger.info("Added power curve %r (%s) to %s", pc.key, pc.source, store_path)
    return store_path


# ---------------------------------------------------------------------------
# Additional sources (issue #181 follow-up; see the deep-research shortlist):
#   - NREL `turbine-models` package: free, BSD-3 REFERENCE designs (IEA/NREL/DTU 5-18 MW).
#   - WAsP `.wtg` and tabular `.dat`/`.csv` parsers for OEM curves mined from permit/EIA
#     portals or exported from WAsP/EMD (the practical route to real large-turbine curves).
# ---------------------------------------------------------------------------


def _turbine_models_data_dir() -> Path:
    try:
        import turbine_models
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "Reference curves need the turbine-models package: pip install turbine-models"
        ) from exc
    return Path(turbine_models.__file__).parent / "data"


def list_turbine_models() -> List[str]:
    """List reference turbines available in the NREL ``turbine-models`` package (BSD-3)."""
    return sorted(
        p.stem
        for p in _turbine_models_data_dir().rglob("*.csv")
        if "Validation" not in p.stem
    )


def fetch_turbine_models_curve(
    name: str, *, key: Optional[str] = None, manufacturer: str = "reference"
) -> PowerCurve:
    """Load a power curve from the NREL ``turbine-models`` package by name.

    These are institutional REFERENCE designs (e.g. ``IEA_Reference_15MW_240``,
    ``2020ATB_NREL_Reference_18MW_263``, ``DTU_Reference_v1_10MW_178``), NOT commercial OEM
    curves -- use them as defaults/fallbacks for the 5-18 MW band. Exact stem match first,
    then case-insensitive substring.
    """
    import pandas as pd

    csvs = list(_turbine_models_data_dir().rglob("*.csv"))
    matches = [p for p in csvs if p.stem == name]
    if not matches:
        matches = [p for p in csvs if name.lower() in p.stem.lower() and "Validation" not in p.stem]
    if not matches:
        raise ValueError(f"No turbine-models curve named {name!r}; see list_turbine_models()")
    csv = matches[0]
    df = pd.read_csv(csv)
    ws_col = next((c for c in df.columns if "wind speed" in str(c).lower()), None)
    power_col = next((c for c in df.columns if str(c).lower().startswith("power")), None)
    if ws_col is None or power_col is None:
        raise ValueError(f"{csv.name} missing wind-speed/power columns: {list(df.columns)}")
    sub = df[[ws_col, power_col]].apply(pd.to_numeric, errors="coerce").dropna()
    ws = [float(x) for x in sub[ws_col]]
    power = [float(x) for x in sub[power_col]]  # already kW
    # Capture the thrust-coefficient (Ct) curve when the source ships one, aligned
    # to the same rows as ws/power (IEA/DTU reference designs carry it; others don't).
    ct_col = next(
        (c for c in df.columns if str(c).strip().lower() in ("ct [-]", "ct", "thrust coefficient")),
        None,
    )
    thrust: Optional[List[float]] = None
    if ct_col is not None:
        ct_series = pd.to_numeric(df.loc[sub.index, ct_col], errors="coerce")
        if not bool(ct_series.isna().any()):
            thrust = [float(x) for x in ct_series]
    rated = max(power) if power else 0.0
    prov: Dict[str, Any] = {
        "dataset": "NREL turbine-models (BSD-3, reference design)",
        "file": csv.name,
    }
    if thrust is not None:
        prov["has_thrust_coefficient"] = True
    return PowerCurve(
        key=key or _slugify(csv.stem),
        manufacturer=manufacturer,
        model=csv.stem,
        rated_capacity_kw=round(rated, 1),
        wind_speeds_ms=ws,
        power_kw=power,
        thrust_coeffs=thrust,
        rated_ms=_rated_wind_speed(ws, power, rated),
        source="nrel_turbine_models",
        provenance=prov,
    )


def from_wasp_wtg(
    path: Any,
    *,
    air_density_kgm3: float = 1.225,
    manufacturer: str = "",
    key: Optional[str] = None,
) -> PowerCurve:
    """Parse a WAsP ``.wtg`` (XML) turbine file -- the format OEMs / permit portals distribute.

    Multi-mode files carry several ``PerformanceTable`` blocks (one per air density); the one
    nearest ``air_density_kgm3`` is used. ``PowerOutput`` (W) is converted to kW.
    """
    root = ElementTree.parse(str(path)).getroot()
    desc = root.get("Description") or root.get("ManufacturerName") or Path(str(path)).stem
    rotor = root.get("RotorDiameter")
    tables = root.findall(".//PerformanceTable")
    if not tables:
        raise ValueError(f"No <PerformanceTable> in WAsP file {path}")

    def _density(table: Any) -> float:
        try:
            return float(table.get("AirDensity"))
        except (TypeError, ValueError):
            return 1.225

    table = min(tables, key=lambda t: abs(_density(t) - air_density_kgm3))
    points = table.findall(".//DataPoint")
    ws = [float(_ws) for p in points if (_ws := p.get("WindSpeed")) is not None]
    power = [float(_po) / 1000.0 for p in points if (_po := p.get("PowerOutput")) is not None]
    rated = max(power) if power else 0.0
    strat = table.find(".//StartStopStrategy")
    cut_in = float(_ci) if (strat is not None and (_ci := strat.get("LowSpeedCutIn"))) else 3.0
    cut_out = float(_co) if (strat is not None and (_co := strat.get("HighSpeedCutOut"))) else 25.0
    return PowerCurve(
        key=key or _slugify(str(desc)),
        manufacturer=manufacturer or "unknown",
        model=str(desc),
        rated_capacity_kw=round(rated, 1),
        wind_speeds_ms=ws,
        power_kw=power,
        cut_in_ms=cut_in,
        cut_out_ms=cut_out,
        rated_ms=_rated_wind_speed(ws, power, rated),
        source="wasp_wtg",
        provenance={
            "file": Path(str(path)).name,
            "air_density_kgm3": _density(table),
            "rotor_diameter_m": float(rotor) if rotor else None,
        },
    )


def from_tabular_file(
    path: Any,
    *,
    key: str,
    manufacturer: str,
    model: str,
    rated_capacity_kw: Optional[float] = None,
    power_unit: str = "kW",
    hub_heights_m: Optional[Sequence[float]] = None,
    certificate: Optional[str] = None,
) -> PowerCurve:
    """Parse a ws/power table from a ``.dat``/``.tsv``/``.csv`` file.

    For IEA reference ``.dat`` performance files or a curve extracted from a permit-portal
    PDF. Delimiter is sniffed from the extension; the wind-speed and power columns are found
    by header keyword. ``power_unit`` may be ``kW`` (default) or ``W``.
    """
    import pandas as pd

    sep = "\t" if str(path).endswith((".dat", ".tsv")) else None
    df = pd.read_csv(path, sep=sep, engine="python")

    def _find(keywords: List[str]) -> Optional[Any]:
        for col in df.columns:
            if any(k in str(col).lower() for k in keywords):
                return col
        return None

    ws_col = _find(["wind speed", "wind_speed", "windspeed", "speed", "ws"])
    power_col = _find(["power", "electrical"])
    if ws_col is None or power_col is None:
        raise ValueError(f"Could not find ws/power columns in {path}: {list(df.columns)}")
    sub = df[[ws_col, power_col]].apply(pd.to_numeric, errors="coerce").dropna()
    divisor = 1000.0 if power_unit.lower() in ("w", "watt", "watts") else 1.0
    ws = [float(x) for x in sub[ws_col]]
    power = [float(x) / divisor for x in sub[power_col]]
    rated = float(rated_capacity_kw) if rated_capacity_kw else (max(power) if power else 0.0)
    prov: Dict[str, Any] = {"file": Path(str(path)).name, "power_unit": power_unit}
    if certificate:
        prov["certificate"] = certificate
    return PowerCurve(
        key=key,
        manufacturer=manufacturer,
        model=model,
        rated_capacity_kw=round(rated, 1),
        wind_speeds_ms=ws,
        power_kw=power,
        hub_heights_m=[float(h) for h in (hub_heights_m or [])],
        rated_ms=_rated_wind_speed(ws, power, rated),
        source="tabular_import",
        provenance=prov,
    )
