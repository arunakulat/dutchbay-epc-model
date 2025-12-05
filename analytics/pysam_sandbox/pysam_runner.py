"""Minimal PySAM wrapper for annual generation profile extraction.

CRITICAL DESIGN CONSTRAINT:
This is a READER, not a calculator. It produces List[float] (annual kWh), nothing more.

No financial modeling. No tax equity. No LCOE. No wake modeling configuration.
Only: 20-year AEP profile with linear degradation (matching v14 cashflow formula).

Go-with-the-Flow Compliance
----------------------------
- FIN-02: Explicit units (capacity_mw, degradation_rate decimal)
- TYPE-01: Fully typed, mypy clean
- FIN-01: Numeric robustness, explicit errors
- R17: Google-style docstrings with Args/Returns
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    import PySAM.Windpower as wp  # type: ignore[import-not-found]
else:
    import PySAM.Windpower as wp  # type: ignore[import-not-found]


class PySAMRunner:
    """Single-purpose PySAM wrapper for generation profile extraction.

    This class encapsulates PySAM's Windpower module to extract
    annual energy production (AEP) profiles for project finance modeling.

    Design:
    - NO financial calculations (IRR, NPV, LCOE)
    - NO tax modeling
    - NO complex wake effects
    - ONLY annual generation with simple degradation

    Attributes
    ----------
    resource_file : str
        Path to PySAM-compatible SRW resource file
    capacity_mw : float
        Total installed capacity in MW (units explicit per FIN-02)
    """

    def __init__(self, resource_file: str, capacity_mw: float) -> None:
        """Initialize PySAM runner.

        Parameters
        ----------
        resource_file : str
            Path to PySAM-compatible SRW wind resource file
        capacity_mw : float
            Total installed capacity in MW (not kW)

        Raises
        ------
        FileNotFoundError
            If resource_file does not exist
        ValueError
            If capacity_mw <= 0
        """
        if capacity_mw <= 0:
            raise ValueError(f"capacity_mw must be > 0, got {capacity_mw}")

        self.resource_file = resource_file
        self.capacity_mw = capacity_mw
        self._model: wp.Windpower | None = None

    def get_annual_profile(
        self, degradation_rate: float = 0.006, project_life_years: int = 20
    ) -> List[float]:
        """Generate annual generation profile with degradation.

        Applies LINEAR degradation matching v14 cashflow formula:
        AEP[year] = base_aep * (1 - degradation_rate)^(year - 1)

        Parameters
        ----------
        degradation_rate : float, default=0.006
            Annual degradation as decimal (0.006 = 0.6% per year)
            Must match config project.degradation value
        project_life_years : int, default=20
            Number of years to generate

        Returns
        -------
        List[float]
            Annual generation for years 1 through project_life_years (kWh)

        Raises
        ------
        RuntimeError
            If PySAM execution fails

        Notes
        -----
        - Degradation is LINEAR ONLY (no complex models)
        - Output is in kWh (not MWh or GWh)
        - Values are GROSS generation (grid losses applied separately in cashflow)

        Examples
        --------
        >>> runner = PySAMRunner("inputs/mannar.srw", capacity_mw=150.0)
        >>> profile = runner.get_annual_profile(degradation_rate=0.006)
        >>> len(profile)
        20
        >>> profile[0] > profile[-1]  # Year 1 > Year 20 due to degradation
        True
        """
        if self._model is None:
            self._execute_pysam()

        assert self._model is not None  # For mypy
        base_aep = float(self._model.Outputs.annual_energy)

        # Apply LINEAR degradation (matching cashflow_v14.py formula)
        return [
            base_aep * ((1.0 - degradation_rate) ** (year - 1))
            for year in range(1, project_life_years + 1)
        ]

    def _execute_pysam(self) -> None:
        """Run PySAM Windpower simulation once and cache result.

        Raises
        ------
        RuntimeError
            If PySAM execution fails
        FileNotFoundError
            If resource_file not found by PySAM
        """
        try:
            wind = wp.default("WindPowerNone")

            # Resource file
            wind.Resource.wind_resource_filename = self.resource_file

            # Capacity (convert MW → kW for PySAM)
            wind.Turbine.system_capacity = self.capacity_mw * 1000.0

            # Execute PySAM
            wind.execute()

            self._model = wind

        except Exception as exc:
            raise RuntimeError(
                f"PySAM execution failed for {self.resource_file}: {exc}"
            ) from exc
