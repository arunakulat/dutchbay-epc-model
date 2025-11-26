"""Scenario discovery and loading for the v14 pipeline.

This module provides a single, authoritative way to:
- Discover scenario config files under a scenarios/ directory
- Load them via the shared analytics.scenario_loader.load_scenario_config

Design rules (Go with the Flow):
- YAML/JSON config–driven (no hardcoded scenario lists)
- Stateless and batch/CLI friendly
- No dependencies on dutchbay_v14chat or legacy code
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Iterator, Optional, Sequence, Tuple

from analytics.scenario_loader import load_scenario_config

logger = logging.getLogger(__name__)

ScenarioConfig = Dict[str, object]
ScenarioPair = Tuple[str, ScenarioConfig]


class ScenarioManager:
    """Discover and load scenario configs for the v14 pipeline.

    This is the *only* module that should know about the on-disk layout of
    scenario configs. All callers (CLI, analytics, dashboards) should go
    through ScenarioManager instead of globbing the scenarios/ folder
    themselves.

    A "scenario" is a single YAML or JSON config file living directly under
    a scenarios/ directory (non-recursive by design).
    """

    def __init__(self, scenarios_dir: str | Path) -> None:
        """Create a manager for the given scenarios directory.

        Parameters
        ----------
        scenarios_dir:
            Path to the directory containing scenario config files. This
            must exist and be a directory; otherwise FileNotFoundError is
            raised.
        """
        self.scenarios_dir = Path(scenarios_dir)
        if not self.scenarios_dir.is_dir():
            raise FileNotFoundError(f"Scenarios dir not found: {self.scenarios_dir}")

        logger.info("ScenarioManager initialised for: %s", self.scenarios_dir)

    # ------------------------------------------------------------------
    # Low-level path discovery
    # ------------------------------------------------------------------

    def _iter_config_paths(self) -> Iterator[Path]:
        """Yield all YAML/JSON config paths in scenarios_dir (non-recursive).

        This is a low-level helper used by higher-level APIs. Callers should
        prefer iter_scenarios() unless they explicitly need raw Paths.

        The returned paths are sorted by filename to keep ordering stable.
        """
        exts = {".yaml", ".yml", ".json"}

        try:
            entries = sorted(self.scenarios_dir.iterdir())
        except FileNotFoundError:
            # Should not happen after __init__ guard, but keep it defensive.
            logger.error(
                "ScenarioManager: scenarios dir disappeared: %s", self.scenarios_dir
            )
            return iter(())

        for path in entries:
            if not path.is_file():
                continue
            if path.suffix.lower() not in exts:
                continue
            yield path

    # ------------------------------------------------------------------
    # High-level scenario iteration
    # ------------------------------------------------------------------

    def iter_scenarios(
        self,
        patterns: Sequence[str] | None = None,
    ) -> Iterator[ScenarioPair]:
        """Yield (scenario_name, config) pairs for matching configs.

        Parameters
        ----------
        patterns:
            Optional list/tuple of filenames to include, e.g.
            ("dutchbay_lendercase_2025Q4.yaml", "example_a.yaml").
            If None, all scenario configs in the directory are included.

        Yields
        ------
        (scenario_name, config) tuples:
            scenario_name:
                The filename stem, e.g. "dutchbay_lendercase_2025Q4".
                This is what tests and analytics code expect.
            config:
                The loaded config dict as returned by load_scenario_config().
        """
        allowed_names: Optional[set[str]] = None
        if patterns:
            # Match *filenames* exactly (including extension), because tests
            # pass "dutchbay_lendercase_2025Q4.yaml" as a pattern.
            allowed_names = set(patterns)

        for path in self._iter_config_paths():
            if allowed_names is not None and path.name not in allowed_names:
                continue

            logger.info("ScenarioManager: loading scenario config from %s", path)
            config = load_scenario_config(str(path))

            # The public scenario name is the stem (no extension), e.g.
            # "dutchbay_lendercase_2025Q4". Tests assert on this value.
            scenario_name = path.stem

            # Yield as (name, config) pair; no Path objects leak out.
            yield scenario_name, config
