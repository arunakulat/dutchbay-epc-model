"""Monte Carlo analysis engine.

Exports:
- MonteCarloEngine: Backward-compatible wrapper
- run_monte_carlo_analysis: Functional entrypoint

Backward Compatibility (Sprint 18 - Reindeer-2):
The MonteCarloEngine API changed in Sprint 17:
- OLD: engine = MonteCarloEngine(config, n_iterations=1000)
- NEW: engine = MonteCarloEngine(config); result = engine.run(n_trials=1000)

This module provides a compatibility shim to prevent breaking 14 integration tests.
"""

from __future__ import annotations

import warnings
from typing import Any, Mapping, Optional

from analytics.mc.engine import MonteCarloEngine as _MonteCarloEngineNew
from analytics.mc.engine import run_monte_carlo_analysis
from analytics.mc.correlation import CorrelationSpec
from analytics.contracts_v14 import MonteCarloResult


class MonteCarloEngine(_MonteCarloEngineNew):
    """Backward-compatible MonteCarloEngine wrapper.
    
    Maintains old API: MonteCarloEngine(config, n_iterations=N)
    while internally using new API: engine.run(n_trials=N)
    
    🦌 REINDEER-2: This wrapper fixes 14 integration test failures.
    
    Deprecation Notice:
    The n_iterations parameter in __init__ is deprecated.
    Use: engine = MonteCarloEngine(config); result = engine.run(n_trials=N)
    
    This wrapper will be removed in Sprint 20.
    """
    
    def __init__(
        self,
        base_config: Mapping[str, Any] = None,  # Make optional for positional arg compat
        *,
        n_iterations: Optional[int] = None,  # DEPRECATED
        seed: int = 123,
        common_random_numbers: bool = True,
        correlation: Optional[CorrelationSpec] = None,
        # Also accept old positional pattern: MonteCarloEngine(config, n_iterations=N)
        **kwargs: Any
    ) -> None:
        """Initialize Monte Carlo engine with backward compatibility.
        
        Args:
            base_config: Project configuration dict
            n_iterations: (DEPRECATED) Number of Monte Carlo iterations
                         Use engine.run(n_trials=N) instead
            seed: Random seed for reproducibility
            common_random_numbers: Use common random numbers
            correlation: Correlation specification (optional)
            **kwargs: Catch old parameter names for compatibility
        
        Raises:
            ValueError: If base_config is missing
            
        Example (OLD API - still works):
            >>> engine = MonteCarloEngine(config, n_iterations=1000)
            >>> result = engine.run()  # Uses stored 1000
            
        Example (NEW API - preferred):
            >>> engine = MonteCarloEngine(base_config=config)
            >>> result = engine.run(n_trials=1000)
        """
        # Handle positional argument pattern: MonteCarloEngine(config, n_iterations=N)
        if base_config is None:
            # Try to extract from kwargs if passed as keyword
            base_config = kwargs.pop('base_config', None)
            if base_config is None:
                raise ValueError(
                    "MonteCarloEngine requires base_config. "
                    "Usage: MonteCarloEngine(base_config=config) or MonteCarloEngine(config)"
                )
        
        # Extract n_iterations from various possible kwarg names (backward compat)
        if n_iterations is None:
            n_iterations = kwargs.pop('n_iterations', None)
        if n_iterations is None:
            n_iterations = kwargs.pop('n_trials', None)
        if n_iterations is None:
            n_iterations = kwargs.pop('niterations', None)
            
        # Store for later use in run()
        self._stored_n_iterations = n_iterations
        
        # Warn about deprecated usage
        if n_iterations is not None:
            warnings.warn(
                "Passing n_iterations to MonteCarloEngine.__init__ is deprecated. "
                "Use: engine = MonteCarloEngine(config); result = engine.run(n_trials=N). "
                "This backward-compatibility wrapper will be removed in Sprint 20.",
                DeprecationWarning,
                stacklevel=2
            )
        
        # Initialize parent with new API (no n_iterations)
        super().__init__(
            base_config=base_config,
            seed=seed,
            common_random_numbers=common_random_numbers,
            correlation=correlation
        )
    
    def run(self, *, n_trials: Optional[int] = None) -> MonteCarloResult:
        """Run Monte Carlo simulation.
        
        Args:
            n_trials: Number of trials to run. If None, uses n_iterations
                     from __init__ (deprecated path)
        
        Returns:
            MonteCarloResult with aggregated statistics
            
        Raises:
            ValueError: If n_trials not provided and n_iterations not set in __init__
            
        Example:
            >>> engine = MonteCarloEngine(config)
            >>> result = engine.run(n_trials=1000)  # Preferred
            
            >>> # Backward compatible:
            >>> engine = MonteCarloEngine(config, n_iterations=1000)
            >>> result = engine.run()  # Uses stored 1000
        """
        # Use stored n_iterations if n_trials not provided (backward compat)
        if n_trials is None:
            if self._stored_n_iterations is None:
                raise ValueError(
                    "n_trials must be provided to run() or n_iterations to __init__. "
                    "Usage: engine.run(n_trials=1000)"
                )
            n_trials = self._stored_n_iterations
        
        # Call parent run() with correct parameter name
        return super().run(n_trials=n_trials)


__all__ = [
    'MonteCarloEngine',
    'run_monte_carlo_analysis',
    'CorrelationSpec',
    'MonteCarloResult',
]
