"""Config-driven ERA5 retrieval + site AEP for any RE project location.

Retrieves the Copernicus CDS ERA5 single-levels TIMESERIES product (ARCO/Zarr) for a
single lat/lon point, builds a clean hourly hub-height wind series, and computes net
AEP through the project's canonical power curve via :class:`EnergyCalculator`.

Generalises the wind-resource pipeline beyond DutchBay: any user supplies their own
Copernicus CDS key (in ``~/.cdsapirc``) and a project centre (lat/lon), and the tool
fetches + computes for that site. See issue #177.

GWTF: config-first (YAML), fully typed, no hardcoded site constants, no ``argparse``
or ``input()``. Credentials live ONLY in ``~/.cdsapirc`` (the cdsapi default) and are
NEVER written to the repo.

Typical usage:
    >>> from wind_resource.era5_retrieval import ERA5RequestConfig, run
    >>> cfg = ERA5RequestConfig.from_yaml(
    ...     "wind_resource/config/era5_request_kalpitiya.yaml")
    >>> result = run(cfg)            # downloads + computes
    >>> print(result["net_aep_p50_gwh"])
"""

from __future__ import annotations

import glob
import json
import logging
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd
import yaml

logger = logging.getLogger(__name__)

# CDS ARCO point-timeseries product + the variables needed for hub-height winds.
ERA5_TIMESERIES_DATASET = "reanalysis-era5-single-levels-timeseries"
ERA5_WIND_VARIABLES: Tuple[str, ...] = (
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "100m_u_component_of_wind",
    "100m_v_component_of_wind",
    "surface_pressure",
)


@dataclass(frozen=True)
class ERA5RequestConfig:
    """Immutable ERA5 retrieval request for one RE project site.

    Every field is config-supplied (CCCDIR); no hardcoded site constants.
    """

    project_name: str
    latitude: float
    longitude: float
    start_year: int
    end_year: int
    hub_height_m: float = 150.0
    reference_height_low_m: float = 10.0
    reference_height_high_m: float = 100.0
    alpha_min: float = 0.05
    alpha_max: float = 0.40
    output_dir: str = "/tmp/era5_cache"
    turbine_model: str = "envision_en171_6p5"
    num_turbines: int = 23

    @classmethod
    def from_yaml(cls, path: str) -> "ERA5RequestConfig":
        """Load a request config from YAML (``project:`` / ``download:`` / ``turbine:``)."""
        with open(path) as f:
            raw = yaml.safe_load(f)
        proj = raw.get("project", {})
        dl = raw.get("download", {})
        turb = raw.get("turbine", {})
        years = dl.get("years", {})
        return cls(
            project_name=str(proj["name"]),
            latitude=float(proj["latitude"]),
            longitude=float(proj["longitude"]),
            start_year=int(years["start"]),
            end_year=int(years["end"]),
            hub_height_m=float(turb.get("hub_height_m", 150.0)),
            alpha_min=float(dl.get("alpha_min", 0.05)),
            alpha_max=float(dl.get("alpha_max", 0.40)),
            output_dir=str(dl.get("output_dir", "/tmp/era5_cache")),
            turbine_model=str(turb.get("model", "envision_en171_6p5")),
            num_turbines=int(turb.get("num_turbines", 23)),
        )

    @property
    def date_range(self) -> str:
        """CDS ``date`` range string, e.g. ``2020-01-01/2024-12-31``."""
        return f"{self.start_year}-01-01/{self.end_year}-12-31"


def ensure_cdsapirc(
    url: str | None = None,
    key: str | None = None,
    path: str | None = None,
) -> Path:
    """Ensure a ``~/.cdsapirc`` exists; optionally write it from explicit credentials.

    Credentials are resolved in order: explicit ``url``/``key`` args, then the
    ``CDSAPI_URL`` / ``CDSAPI_KEY`` environment variables. If neither is supplied and
    the file is absent, raises with setup instructions. The key is NEVER committed —
    it is written only to the user's ``~/.cdsapirc`` with ``0600`` perms.
    """
    rc = Path(path or os.path.expanduser("~/.cdsapirc"))
    url = url or os.environ.get("CDSAPI_URL")
    key = key or os.environ.get("CDSAPI_KEY")
    if url and key:
        rc.write_text(f"url: {url}\nkey: {key}\n")
        rc.chmod(0o600)
        logger.info("Wrote CDS credentials to %s (0600)", rc)
    elif not rc.exists():
        raise FileNotFoundError(
            f"No CDS credentials at {rc}. Get an API token at "
            "https://cds.climate.copernicus.eu (profile -> API token), then create "
            "~/.cdsapirc (lines 'url:' and 'key:') or set CDSAPI_URL and CDSAPI_KEY."
        )
    return rc


def retrieve_era5_timeseries(config: ERA5RequestConfig) -> Path:
    """Download the ERA5 point timeseries for the configured site; return the .nc path.

    Uses the ARCO ``reanalysis-era5-single-levels-timeseries`` product, which returns a
    zipped NetCDF; this unpacks it and returns the extracted NetCDF path. Requires the
    optional ``[wind]`` extra (cdsapi) and valid ``~/.cdsapirc`` credentials.
    """
    try:
        import cdsapi
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "ERA5 retrieval requires the [wind] extra: pip install cdsapi xarray netcdf4"
        ) from exc

    ensure_cdsapirc()
    out_dir = Path(config.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = config.project_name.lower().replace(" ", "_")
    zip_path = out_dir / f"era5_{safe}_{config.start_year}_{config.end_year}.zip"

    logger.info(
        "Retrieving ERA5 timeseries for %s (%.4f, %.4f) %s",
        config.project_name,
        config.latitude,
        config.longitude,
        config.date_range,
    )
    client = cdsapi.Client()
    client.retrieve(
        ERA5_TIMESERIES_DATASET,
        {
            "variable": list(ERA5_WIND_VARIABLES),
            "location": {"longitude": config.longitude, "latitude": config.latitude},
            "date": [config.date_range],
            "data_format": "netcdf",
        },
        str(zip_path),
    )

    extract_dir = out_dir / f"{safe}_{config.start_year}_{config.end_year}"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    ncs = sorted(glob.glob(str(extract_dir / "*.nc")))
    if not ncs:
        raise RuntimeError(f"No NetCDF found in CDS response {zip_path}")
    logger.info("Extracted %s", ncs[0])
    return Path(ncs[0])


def build_hub_height_series(nc_path: Path, config: ERA5RequestConfig) -> pd.DataFrame:
    """Convert an ERA5 point NetCDF to an hourly hub-height wind series.

    Computes ws10/ws100 from u/v components, derives per-hour wind shear ``alpha``
    (clipped to the config bounds), and extrapolates to ``hub_height_m`` via the power
    law. Returns a DataFrame indexed by timestamp with a ``ws_<hub>m`` column.
    """
    import xarray as xr

    ds = xr.open_dataset(nc_path)
    tname = "valid_time" if "valid_time" in ds.coords else "time"
    times = pd.to_datetime(ds[tname].values)

    def comp(*names: str) -> np.ndarray:
        for n in names:
            if n in ds:
                return np.asarray(ds[n].values, dtype="float64").ravel()
        raise KeyError(f"None of {names} in ERA5 dataset {list(ds.data_vars)}")

    ws10 = np.hypot(comp("u10"), comp("v10"))
    ws100 = np.hypot(comp("u100"), comp("v100"))
    h_lo = config.reference_height_low_m
    h_hi = config.reference_height_high_m
    h_t = config.hub_height_m
    with np.errstate(divide="ignore", invalid="ignore"):
        alpha = np.log(ws100 / ws10) / np.log(h_hi / h_lo)
    alpha = np.clip(
        np.nan_to_num(alpha, nan=config.alpha_min), config.alpha_min, config.alpha_max
    )
    ws_hub = ws100 * (h_t / h_hi) ** alpha

    col = f"ws_{int(h_t)}m"
    df = pd.DataFrame({col: ws_hub, "wind_shear_alpha": alpha}, index=times)
    df.index.name = "timestamp"
    logger.info(
        "Built %d-h hub series for %s: mean %.2f m/s (%.2f yr)",
        len(df),
        config.project_name,
        float(df[col].mean()),
        len(df) / 8760.0,
    )
    return df


def compute_site_aep(series: pd.DataFrame, config: ERA5RequestConfig) -> Dict[str, Any]:
    """Compute net AEP from a hub-height series via :class:`EnergyCalculator`."""
    from wind_resource.energy_calculator import EnergyCalculator

    col = f"ws_{int(config.hub_height_m)}m"
    calc = EnergyCalculator(
        df=series,
        ws_column=col,
        turbine_model=config.turbine_model,
        num_turbines=config.num_turbines,
    )
    net = calc.calculate_net_aep()
    return {
        "project": config.project_name,
        "latitude": config.latitude,
        "longitude": config.longitude,
        "hours": int(len(series)),
        "years": round(len(series) / 8760.0, 2),
        "mean_ws_hub_ms": round(float(series[col].mean()), 3),
        "net_aep_p50_gwh": round(net["net_aep_p50_mwh"] / 1000.0, 1),
        "net_aep_p90_gwh": round(net["net_aep_p90_mwh"] / 1000.0, 1),
        "capacity_factor_p50": round(net["capacity_factor_net_p50"] / 100.0, 4),
    }


def run(config: ERA5RequestConfig) -> Dict[str, Any]:
    """End-to-end: retrieve ERA5 -> hub-height series -> net AEP. Returns the summary."""
    nc_path = retrieve_era5_timeseries(config)
    series = build_hub_height_series(nc_path, config)
    result = compute_site_aep(series, config)
    logger.info(
        "%s: %.1f GWh P50 (CF %.1f%%) from %.2f yr ERA5",
        config.project_name,
        result["net_aep_p50_gwh"],
        result["capacity_factor_p50"] * 100,
        result["years"],
    )
    return result


def main() -> None:
    """Config-driven entry point (no argparse; honours ``ERA5_REQUEST_CONFIG``)."""
    cfg_path = os.environ.get(
        "ERA5_REQUEST_CONFIG", "wind_resource/config/era5_request_kalpitiya.yaml"
    )
    result = run(ERA5RequestConfig.from_yaml(cfg_path))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    main()
