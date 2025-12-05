"""PySAM integration sandbox (OPTIONAL MODULE).

This module is NOT imported by core pipeline unless explicitly requested
via config generation.engine=pysam.

Installation
------------
pip install NREL-PySAM==5.1.0

Design Principles
-----------------
- Isolated from finance/cashflow_v14.py
- No dependencies in requirements.txt (optional only)
- Falls back gracefully if PySAM not installed
- Single responsibility: AEP profile extraction

Go-with-the-Flow Compliance
----------------------------
- ARCH-01: Config-first (resource file from YAML)
- TYPE-01: Fully typed (mypy clean)
- FIN-01: Numeric robustness, explicit errors
- R17: Documented public APIs
"""

from __future__ import annotations

import importlib.util
from typing import List

# Check PySAM availability using importlib (ruff-compliant)
PYSAM_AVAILABLE = importlib.util.find_spec("PySAM.Windpower") is not None


def _not_installed(*args: object, **kwargs: object) -> None:
    """Raise error if PySAM not installed."""
    raise RuntimeError(
        "PySAM not installed. Install with: pip install NREL-PySAM==5.1.0"
    )


class PySAMRunner:
    """PySAM wrapper for generation profile extraction.

    Acts as a proxy to the real implementation when PySAM is installed,
    or raises clear errors when PySAM is not available.

    This wrapper pattern avoids mypy re-export issues while maintaining
    type safety and ruff compliance.
    """

    def __init__(self, resource_file: str, capacity_mw: float) -> None:
        """Initialize PySAM runner.

        Parameters
        ----------
        resource_file : str
            Path to PySAM-compatible SRW wind resource file
        capacity_mw : float
            Total installed capacity in MW

        Raises
        ------
        RuntimeError
            If PySAM not installed
        """
        if not PYSAM_AVAILABLE:
            _not_installed()

        # Import real implementation only when PySAM available
        from analytics.pysam_sandbox.pysam_runner import PySAMRunner as _RealRunner

        self._runner = _RealRunner(resource_file, capacity_mw)

    def get_annual_profile(
        self, degradation_rate: float = 0.006, project_life_years: int = 20
    ) -> List[float]:
        """Generate annual generation profile with degradation.

                Parameters
                ----------
                degradation_rate : float, default=0.006
                    Annual degradation as

        project_life_years : int, default=20
                    Number of years to generate

                Returns
                -------
                List[float]
                    Annual generation for years 1 through project_life_years (kWh)

                Raises
                ------
                RuntimeError
                    If PySAM not installed or execution fails
        """
        if not PYSAM_AVAILABLE:
            _not_installed()
            return []  # Never reached, but satisfies mypy

        return self._runner.get_annual_profile(degradation_rate, project_life_years)


__all__ = ["PySAMRunner", "PYSAM_AVAILABLE"]
