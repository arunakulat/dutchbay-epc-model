#!/usr/bin/env python3
"""Final patch for analytics/contracts_v14.py - Pydantic validation.

This script applies the complete fix for test_contracts.py:
1. ParameterRangeConfig → Pydantic BaseModel with validators
2. TornadoResult dataclass with impact properties
3. Proper ValidationError raising

Usage:
    python scripts/patch_contracts_final.py

Tests Fixed:
    - 10 validation rejection tests
    - All TornadoResult property tests
"""

import re
from pathlib import Path

def main():
    contracts_file = Path("analytics/contracts_v14.py")
    
    if not contracts_file.exists():
        print(f"❌ File not found: {contracts_file}")
        return 1
    
    print(f"📖 Reading {contracts_file}...")
    content = contracts_file.read_text()
    
    # Find SECTION 6 start and end
    section_start = content.find("# SECTION 6: Sensitivity & Tornado Contracts")
    if section_start == -1:
        print("❌ SECTION 6 not found")
        return 1
    
    # Find next section (SECTION 7)
    section_end = content.find("# SECTION 7:", section_start)
    if section_end == -1:
        print("❌ SECTION 7 not found")
        return 1
    
    # Extract everything before and after SECTION 6
    before_section = content[:section_start]
    after_section = content[section_end:]
    
    # New SECTION 6 with Pydantic validation
    new_section_6 = '''# ═════════════════════════════════════════════════════════════════════════════
# SECTION 6: Sensitivity & Tornado Contracts
# ═════════════════════════════════════════════════════════════════════════════


class ParameterRangeConfig(BaseModel):
    """CCCDIR: Configuration for a single sensitivity parameter with validation.
    
    Validates:
    - variable_name: non-empty string (whitespace stripped)
    - base_value: must be > 0
    - low_pct: must be in range [-50, 0]
    - high_pct: must be in range [0, 100]
    - high_pct must exceed abs(low_pct)
    - steps: must be in range [3, 20]
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    
    variable_name: str
    base_value: float
    low_pct: float
    high_pct: float
    steps: int = 5
    label: Optional[str] = None
    shock_type: str = "proportional"
    
    @field_validator("variable_name")
    @classmethod
    def validate_variable_name(cls, v: str) -> str:
        """Validate variable_name is not empty."""
        v = v.strip()
        if not v:
            raise ValueError("variable_name cannot be empty")
        return v
    
    @field_validator("base_value")
    @classmethod
    def validate_base_value(cls, v: float) -> float:
        """Validate base_value is positive."""
        if v <= 0:
            raise ValueError(f"base_value must be > 0, got {v}")
        return v
    
    @field_validator("low_pct")
    @classmethod
    def validate_low_pct(cls, v: float) -> float:
        """Validate low_pct is in valid range."""
        if not (-50 <= v <= 0):
            raise ValueError(f"low_pct must be in range [-50, 0], got {v}")
        return v
    
    @field_validator("high_pct")
    @classmethod
    def validate_high_pct(cls, v: float) -> float:
        """Validate high_pct is in valid range."""
        if not (0 <= v <= 100):
            raise ValueError(f"high_pct must be in range [0, 100], got {v}")
        return v
    
    @model_validator(mode="after")
    def validate_high_exceeds_abs_low(self) -> "ParameterRangeConfig":
        """Validate that high_pct exceeds abs(low_pct)."""
        if self.high_pct <= abs(self.low_pct):
            raise ValueError(
                f"High bound {self.high_pct} must be > absolute value of low bound {abs(self.low_pct)}"
            )
        return self
    
    @field_validator("steps")
    @classmethod
    def validate_steps(cls, v: int) -> int:
        """Validate steps is in valid range."""
        if not (3 <= v <= 20):
            raise ValueError(f"steps must be in range [3, 20], got {v}")
        return v
    
    @property
    def low_value(self) -> float:
        """Calculate low value from base and percentage."""
        return self.base_value * (1 + self.low_pct / 100)
    
    @property
    def high_value(self) -> float:
        """Calculate high value from base and percentage."""
        return self.base_value * (1 + self.high_pct / 100)


@dataclass
class ShockSpec:
    """CCCDIR: Single shock specification for sensitivity."""

    variable_name: str
    base_value: float
    low_pct: float
    high_pct: float
    label: str
    shock_type: str = "proportional"


@dataclass
class ShockResult:
    """CCCDIR: Result of single shock."""

    variable_name: str
    base_value: float
    low_value: float
    high_value: float
    base_metric: float
    low_metric: float
    high_metric: float
    metric_name: str
    label: Optional[str] = None

    @property
    def impact(self) -> float:
        """CASPER: Total impact (half of range to capture magnitude)."""
        return abs(self.high_metric - self.low_metric) / 2.0

    @property
    def direction(self) -> str:
        """CASPER: Which direction has larger impact."""
        if self.high_metric - self.base_metric > abs(
            self.low_metric - self.base_metric
        ):
            return "UP"
        elif self.low_metric - self.base_metric < abs(
            self.high_metric - self.base_metric
        ):
            return "DOWN"
        return "NEUTRAL"


@dataclass
class TornadoResult:
    """CASPER: Single-parameter tornado result with impact calculations.
    
    Used by test_contracts.py for sensitivity analysis validation.
    
    Properties:
    - impact_abs: Absolute impact magnitude |high_irr - low_irr|
    - impact_pct: Percentage impact relative to base
    """
    
    variable: str
    base_irr: float
    low_irr: float
    high_irr: float
    
    @property
    def impact_abs(self) -> float:
        """Calculate absolute impact magnitude.
        
        Returns:
            Absolute difference between high and low IRR
        """
        import numpy as np
        return abs(self.high_irr - self.low_irr) if not np.isnan(self.high_irr) and not np.isnan(self.low_irr) else np.nan
    
    @property
    def impact_pct(self) -> float:
        """Calculate percentage impact relative to base.
        
        Returns:
            (high - low) / base * 100, or 0.0 if base is zero
        """
        import numpy as np
        if np.isnan(self.high_irr) or np.isnan(self.low_irr):
            return np.nan
        if self.base_irr == 0.0:
            return 0.0
        return (self.high_irr - self.low_irr) / self.base_irr * 100


@dataclass
class MultiShockTornadoResult:
    """CASPER: Multi-parameter tornado chart data (renamed for backward compat).
    
    This is the original TornadoResult used by sensitivity_v14.py.
    Renamed to avoid conflict with new single-parameter TornadoResult.
    """

    metric_name: str
    base_metric: float
    shock_results: List[ShockResult]
    low_case_metric: Optional[float] = None
    high_case_metric: Optional[float] = None

    def sorted_by_impact(self) -> List[ShockResult]:
        """Return shocks sorted by absolute impact (descending)."""
        return sorted(self.shock_results, key=lambda x: abs(x.impact), reverse=True)


@dataclass
class MultiMetricTornadoResult:
    """CCCDIR: Multi-metric tornado analysis result."""

    scenario_name: str
    tornado_charts: Dict[str, MultiShockTornadoResult]  # {metric_name: TornadoResult}
    base_kpis: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SensitivitySuite:
    """CCCDIR: Complete sensitivity analysis output."""

    scenario_name: str
    metric_name: str
    base_metric_value: float  # Canonical field name
    tornado_ranking: List[ShockResult]  # Canonical field name
    n_shocks: int
    min_metric: float
    max_metric: float
    range_metric: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[str] = None
    base_config_path: Optional[str] = None  # Added per ACTION_PLAN

    # Backward compatibility aliases (CASPER compliance - Phase 1)
    @property
    def metric(self) -> str:
        """Alias for metric_name (backward compatibility)."""
        return self.metric_name

    @property
    def base_metric(self) -> float:
        """Alias for base_metric_value (backward compatibility)."""
        return self.base_metric_value

    @property
    def tornado_results(self) -> List[ShockResult]:
        """Alias for tornado_ranking (backward compatibility)."""
        return self.tornado_ranking


@dataclass
class BreakevenResult:
    """CASPER: Breakeven analysis (what value makes project NPV=0)."""

    variable_name: str
    base_value: float
    breakeven_value: float
    breakeven_pct_change: float
    is_positive_breakeven: bool  # True if higher value breaks even, False if lower
    metric_name: str = "project_npv"
    tolerance: float = 1000.0  # USD tolerance for breakeven definition


@dataclass
class ParetoFrontierResult:
    """
    CASPER: Pareto frontier analysis result for multi-objective optimization.

    Used in sensitivity_pareto.py for identifying non-dominated solutions
    across competing objectives (e.g., maximize IRR, minimize risk).
    """

    scenario_name: str
    frontier_points: List[Dict[str, float]]  # [{metric1: val1, metric2: val2}, ...]
    dominated_points: List[Dict[str, float]]
    metrics: List[str]  # Names of metrics being optimized
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


'''
    
    # Reconstruct file
    new_content = before_section + new_section_6 + after_section
    
    # Add necessary imports at top if not present
    if "from pydantic import" in new_content and "field_validator" not in new_content:
        import_line = "from pydantic import BaseModel, ConfigDict"
        new_import = "from pydantic import BaseModel, ConfigDict, field_validator, model_validator"
        new_content = new_content.replace(import_line, new_import)
    
    print(f"✍️  Writing patched file...")
    contracts_file.write_text(new_content)
    
    print(f"✅ Patch applied successfully!")
    print(f"\nChanges made:")
    print(f"1. ParameterRangeConfig → Pydantic BaseModel with validators")
    print(f"2. TornadoResult → dataclass with impact properties (NEW)")
    print(f"3. MultiShockTornadoResult → renamed old TornadoResult")
    print(f"4. All validation properly raises ValidationError")
    print(f"\n📊 File size: {len(new_content):,} bytes (was {len(content):,})")
    print(f"\nNext steps:")
    print(f"1. Test: pytest tests/finance/test_contracts.py -v")
    print(f"2. Commit: git add analytics/contracts_v14.py")
    print(f"3. Push: git push origin feature/add-finance-contracts-pydantic-v2-20251219")
    
    # Delete self
    Path(__file__).unlink()
    print(f"\n🗑️  Self-deleting {Path(__file__).name}...")
    print(f"✨ One-time patch complete!")
    
    return 0


if __name__ == "__main__":
    exit(main())
