"""Scenario discovery and loading for the v14 pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Iterator, Optional, Sequence, Tuple

from analytics.scenario_loader import load_scenario_config

logger = logging.getLogger(__name__)

ScenarioPair = Tuple[str, Dict[str, object]]


class ScenarioManager:
    """Discover and load scenario configs for the v14 pipeline."""

    def __init__(self, scenarios_dir: str | Path) -> None:
        self.scenarios_dir = Path(scenarios_dir)
        if not self.scenarios_dir.is_dir():
            raise FileNotFoundError(f"Scenarios dir not found: {self.scenarios_dir}")
        logger.info("ScenarioManager initialised for: %s", self.scenarios_dir)

    def _iter_config_paths(self) -> Iterator[Path]:
        """Yield all YAML/JSON config paths in scenarios_dir (non-recursive)."""
        exts = {".yaml", ".yml", ".json"}
        try:
            entries = sorted(self.scenarios_dir.iterdir())
        except FileNotFoundError:
            # Directory was removed between construction and use; log and yield nothing.
            logger.error(
                "ScenarioManager: scenarios dir disappeared: %s", self.scenarios_dir
            )
            return iter(())  # type: ignore[return-value]

        for path in entries:
            if not path.is_file():
                continue
            if path.suffix.lower() not in exts:
                continue
            yield path

    def iter_scenarios(
        self,
        patterns: Optional[Sequence[str]] = None,
    ) -> Iterator[ScenarioPair]:
        """Yield (scenario_name, config) pairs for matching configs.

        Args:
            patterns:
                Optional list of file names (e.g. ["dutchbay_lendercase_2025Q4.yaml"])
                to include. If None, all YAML/JSON configs in the directory are yielded.
        """
        allowed_names: Optional[set[str]] = (
            set(patterns) if patterns is not None else None
        )

        for path in self._iter_config_paths():
            if allowed_names is not None and path.name not in allowed_names:
                continue

            logger.info("ScenarioManager: loading scenario config from %s", path)
            cfg: Dict[str, object] = load_scenario_config(str(path))
            yield path.stem, cfg
