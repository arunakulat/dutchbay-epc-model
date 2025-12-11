"""
Canonical scenario loader for v14 YAML/JSON configs.

Historical usage to keep working:

    from analytics.scenarioloader import loadscenarioconfig
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Union

import yaml

PathLike = Union[str, Path]


def loadscenarioconfig(path: PathLike) -> Mapping[str, Any]:
    """
    Load a v14 scenario configuration from YAML/JSON into a mapping.

    Parameters
    ----------
    path : str or Path
        Filesystem path to the scenario config.

    Returns
    -------
    Mapping[str, Any]
        Parsed configuration mapping.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file is empty or cannot be parsed as YAML/JSON.
    """
    cfg_path = Path(path)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Scenario config not found: {cfg_path}")

    with cfg_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if data is None:
        raise ValueError(f"Scenario config at {cfg_path} is empty or null")

    if not isinstance(data, Mapping):
        raise ValueError(
            f"Expected mapping from scenario loader, got {type(data).__name__}"
        )

    return data


__all__ = ["loadscenarioconfig"]
