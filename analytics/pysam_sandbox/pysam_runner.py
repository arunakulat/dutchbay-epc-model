"""
Minimal PySAM wrapper for annual generation profile extraction.

Design constraints

- This is a READER, not a calculator.
- Produces List[float] of annual kWh only.
- No financial modeling (IRR, NPV, LCOE, tax, etc.).
- Generation profile: 20-year AEP with simple degradation.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    import PySAM.Windpower as wp
else:
    # At runtime we still import; mypy ignores missing stubs via mypy.ini
    import PySAM.Windpower as wp  # type: ignore[import-not-found]


class PySAMRunner:
    """
    Single-purpose PySAM wrapper for generation profile extraction.

    This class encapsulates PySAM's Windpower module to extract
    annual energy production (AEP) profiles for project finance modeling.
    """

    def __init__(self, resource_file: str, capacity_mw: float) -> None:
        """
        Initialize PySAM runner.

        Args:
            resource_file: Path to PySAM-compatible SRW wind resource file.
            capacity_mw: Total installed capacity in MW (not kW).

        Raises:
            FileNotFoundError: If resource_file does not exist.
            ValueError: If capacity_mw <= 0.
        """
        if capacity_mw <= 0:
            raise ValueError(f"capacity_mw must be > 0, got {capacity_mw}")

        path = Path(resource_file)
        if not path.is_file():
            raise FileNotFoundError(f"PySAM resource file not found: {resource_file}")

        self.resource_file = str(path)
        self.capacity_mw = float(capacity_mw)
        self._model: Optional[wp.Windpower] = None  # type: ignore[name-defined]

    def get_annual_profile(
        self,
        degradation_rate: float = 0.006,
        project_life_years: int = 20,
    ) -> List[float]:
        """
        Generate annual generation profile with degradation.

        AEP[year] = base_aep * (1 - degradation_rate)^(year - 1)

        Args:
            degradation_rate: Annual degradation as decimal
                (0.006 = 0.6% per year).
            project_life_years: Number of years to generate.

        Returns:
            List of annual generation values (kWh) for each year.

        Raises:
            RuntimeError: If PySAM execution fails.
        """
        if project_life_years <= 0:
            raise ValueError(
                f"project_life_years must be positive, got {project_life_years}"
            )

        if not 0.0 <= degradation_rate < 1.0:
            raise ValueError(
                f"degradation_rate must be in [0, 1), got {degradation_rate}"
            )

        if self._model is None:
            self._execute_pysam()

        assert self._model is not None  # for mypy
        base_aep = float(self._model.Outputs.annual_energy)  # type: ignore[attr-defined]

        return [
            base_aep * ((1.0 - degradation_rate) ** (year - 1))
            for year in range(1, project_life_years + 1)
        ]

    def _execute_pysam(self) -> None:
        """
        Run PySAM Windpower simulation once and cache result.

        Raises:
            RuntimeError: If PySAM execution fails.
            FileNotFoundError: If the resource file cannot be used by PySAM.
        """
        try:
            wind = wp.default("WindPowerNone")  # type: ignore[attr-defined]

            # Resource file
            wind.Resource.wind_resource_filename = self.resource_file  # type: ignore[attr-defined]

            # Capacity (convert MW → kW for PySAM)
            wind.Turbine.system_capacity = self.capacity_mw * 1000.0  # type: ignore[attr-defined]

            # Execute PySAM
            wind.execute()  # type: ignore[attr-defined]
            self._model = wind
        except FileNotFoundError:
            # Re-raise file errors explicitly
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError(
                f"PySAM execution failed for {self.resource_file}: {exc}"
            ) from exc
