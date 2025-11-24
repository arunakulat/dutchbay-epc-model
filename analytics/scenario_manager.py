from __future__ import annotations

import fnmatch
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List, Sequence, Union

from analytics.contracts_v14 import ScenarioDescriptor
from analytics.scenario_loader import load_scenario_config

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

__all__ = ["ScenarioManager"]


class ScenarioManager:
    """
    Lightweight scenario registry for v14 analytics.

    Responsibilities
    ----------------
    - Discover scenario config files under a given directory
    - Support both YAML and JSON configs
    - Provide helpers to:
        * list scenario names
        * load configs via the shared loader
        * iterate over (name, config) pairs
        * iterate over ScenarioDescriptor contracts

    Notes
    -----
    - Tests may pass an explicit scenarios_dir=Path("scenarios"), so we MUST
      respect the provided path and not second-guess it.
    - When scenarios_dir is omitted, we auto-resolve to <repo_root>/scenarios
      based on this file's location:
          <repo_root>/analytics/scenario_manager.py
    """

    def __init__(self, scenarios_dir: PathLike | None = None) -> None:
        if scenarios_dir is None:
            # This file is at:
            #   <repo_root>/analytics/scenario_manager.py
            # parents[0] = analytics
            # parents[1] = <repo_root>
            repo_root = Path(__file__).resolve().parents[1]
            scenarios_dir = repo_root / "scenarios"

        self.scenarios_dir: Path = Path(scenarios_dir)

    # ------------------------------------------------------------------
    # Core discovery API
    # ------------------------------------------------------------------

    def _iter_config_paths(self) -> List[Path]:
        """
        Discover scenario config files in scenarios_dir.

        Returns a sorted list of Paths including both YAML and JSON files.

        This is what tests use to verify that canonical scenarios like
        'example_a', 'example_b', 'edge_extreme_stress',
        'dutchbay_lendercase_2025Q4' are visible.
        """
        if not self.scenarios_dir.is_dir():
            logger.warning(
                "ScenarioManager: scenarios_dir is not a directory: %s",
                self.scenarios_dir,
            )
            return []

        exts = {".yaml", ".yml", ".json"}
        paths = sorted(
            p
            for p in self.scenarios_dir.iterdir()
            if p.is_file() and p.suffix in exts and not p.name.startswith("_")
        )
        return paths

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def list_scenario_names(self) -> List[str]:
        """
        Return the list of scenario name stems discovered in scenarios_dir.

        Example:
            ['example_a', 'example_b', 'edge_extreme_stress', ...]
        """
        return [p.stem for p in self._iter_config_paths()]

    def load_config(self, name_or_path: PathLike) -> Dict[str, Any]:
        """
        Load a scenario configuration using the central loader.

        Parameters
        ----------
        name_or_path : PathLike
            Either:
            - A relative or absolute path to a config file, or
            - A bare scenario name (e.g., 'example_b') which will be
              resolved against scenarios_dir with standard extensions.

        Returns
        -------
        dict
            Parsed config dictionary as returned by load_scenario_config.
        """
        path = Path(name_or_path)

        # Already an existing file? Just load it.
        if path.is_file():
            resolved = path
        else:
            # Resolve under scenarios_dir
            candidate = self.scenarios_dir / path
            resolved: Path | None = None

            # Bare name (no suffix): try common extensions.
            if candidate.suffix == "":
                for ext in (".yaml", ".yml", ".json"):
                    test_path = candidate.with_suffix(ext)
                    if test_path.is_file():
                        resolved = test_path
                        break
            else:
                if candidate.is_file():
                    resolved = candidate

            if resolved is None:
                raise FileNotFoundError(
                    f"ScenarioManager: could not resolve config for '{name_or_path}' "
                    f"under {self.scenarios_dir}"
                )

        logger.info("ScenarioManager: loading scenario config from %s", resolved)
        return load_scenario_config(str(resolved))

    def iter_loaded(self) -> Iterator[tuple[str, Dict[str, Any]]]:
        """
        Iterate over (scenario_name, config_dict) tuples for all discovered configs.

        This is a simple helper for callers that only need the logical name
        and the loaded config.
        """
        for path in self._iter_config_paths():
            name = path.stem
            try:
                cfg = load_scenario_config(str(path))
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "ScenarioManager: failed to load config %s: %s",
                    path,
                    exc,
                )
                continue
            yield name, cfg

    # ------------------------------------------------------------------
    # Pattern-based iterator (used by tests)
    # ------------------------------------------------------------------

    def iter_scenarios(
        self,
        patterns: Sequence[str] | None = None,
    ) -> Iterator[tuple[str, Dict[str, Any]]]:
        """
        Iterate over (scenario_name, config_dict) for discovered scenario configs.

        This is the API used by tests such as:

            manager = ScenarioManager(scenarios_dir="scenarios")
            pairs = list(
                manager.iter_scenarios(
                    patterns=("dutchbay_lendercase_2025Q4.yaml",),
                )
            )
            name, config = pairs[0]

        Parameters
        ----------
        patterns : Sequence[str] | None
            Optional filename patterns (glob-style) to restrict which
            configs are loaded, e.g. ("dutchbay_lendercase_2025Q4.yaml",).

        Returns
        -------
        Iterator[tuple[str, dict]]
            Yields (scenario_name, loaded_config) pairs.
        """
        all_paths = self._iter_config_paths()

        # Optional glob-style filtering on file name
        if patterns:
            wanted: List[Path] = []
            for p in all_paths:
                for pat in patterns:
                    if fnmatch.fnmatch(p.name, pat):
                        wanted.append(p)
                        break
        else:
            wanted = all_paths

        for path in wanted:
            name = path.stem
            try:
                cfg = load_scenario_config(str(path))
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "ScenarioManager: failed to load scenario %s via loader: %s",
                    path,
                    exc,
                )
                continue
            yield name, cfg

    # ------------------------------------------------------------------
    # Contract-based API (preferred for analytics layers)
    # ------------------------------------------------------------------

    def iter_descriptors(
        self,
        patterns: Sequence[str] | None = None,
    ) -> Iterator[ScenarioDescriptor]:
        """
        Iterate over ScenarioDescriptor contracts for discovered configs.

        This is the contract-conformant interface that analytics/executive
        layers should use going forward. It wraps iter_scenarios(...).
        """
        for name, cfg in self.iter_scenarios(patterns=patterns):
            descriptor = ScenarioDescriptor(
                scenario_name=name,
                config_path=str(self.scenarios_dir / f"{name}"),  # may be overridden
                config=cfg,
            )
            yield descriptor
            