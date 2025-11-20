"""Scenario manager utilities for the v14 pipeline.

This module is intentionally thin: it is a small orchestration layer for loading
scenario configurations for the Dutch Bay EPC model.

**Use_scenario_loader pattern**

To keep all configuration loading logic (YAML/JSON handling, defaults, FX rate
inference, schema evolution) in one place, *all* scenario files must be loaded
via :func:`analytics.scenario_loader.load_scenario_config`.

In particular:

- Do **not** call ``yaml.safe_load`` on scenario files directly in v14 modules.
- If you need to load a scenario here, route through ``load_scenario_config``.
- This ensures tests, validators, and the v14 pipeline all see exactly the same
  configuration view.

If you need to change how scenarios are parsed, do it in ``analytics/scenario_loader.py``,
not here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, Union

from analytics.scenario_loader import load_scenario_config


class ScenarioManager:
    """Small helper for discovering and loading v14 scenario configs.

    This lives in the v14 finance layer, but all heavy lifting is delegated to
    :mod:`analytics.scenario_loader` so that the pipeline has a single source of
    truth for how scenarios are parsed and normalised.
    """

    def __init__(self, scenarios_dir: Union[str, Path]) -> None:
        self.scenarios_dir = Path(scenarios_dir)

    def _iter_config_paths(
        self,
        patterns: Iterable[str] | None = None,
    ) -> List[Path]:
        """Return a deterministic list of scenario config paths.

        Parameters
        ----------
        patterns:
            Optional iterable of glob patterns (relative to ``scenarios_dir``)
            to match. If omitted, we use a sensible default that picks up both
            YAML and JSON scenario files.

        Returns
        -------
        list[Path]
            Sorted list of matching paths.
        """
        base = self.scenarios_dir

        if patterns is None:
            patterns = ("*.yaml", "*.yml", "*.json")

        paths: List[Path] = []
        for pattern in patterns:
            paths.extend(sorted(base.glob(pattern)))

        return paths

    def load_config(self, path: Union[str, Path]) -> Dict[str, Any]:
        """Load a single scenario config via the shared loader.

        This is the only place in v14 where a scenario file is turned into a
        Python dict. The underlying parsing logic (YAML vs JSON, defaults,
        FX-handling, schema evolution) is all owned by
        :func:`analytics.scenario_loader.load_scenario_config`.
        """
        return load_scenario_config(str(path))

    def iter_scenarios(
        self,
        patterns: Iterable[str] | None = None,
    ) -> Iterable[Tuple[str, Dict[str, Any]]]:
        """Yield ``(scenario_name, config)`` pairs for all matching configs.

        Parameters
        ----------
        patterns:
            Optional iterable of glob patterns. See :meth:`_iter_config_paths`.

        Yields
        ------
        tuple[str, dict]
            Scenario name (stem of the file) and the loaded config.
        """
        for path in self._iter_config_paths(patterns):
            name = path.stem
            config = self.load_config(path)
            yield name, config
