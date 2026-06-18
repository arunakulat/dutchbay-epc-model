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
    source: str = "manual"
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_yaml_block(self) -> Dict[str, Any]:
        """Render as a ``{key: {...}}`` block matching power_curves.yaml."""
        return {
            self.key: {
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
                "provenance": {"source": self.source, **self.provenance},
            }
        }


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

    existing = {}
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
