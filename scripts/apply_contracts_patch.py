#!/usr/bin/env python3
"""ONE-TIME patch script for analytics/contracts_v14.py.

This script applies ALL fixes needed for test compatibility.
Run once, commit result, then script self-deletes.

Usage:
    python scripts/apply_contracts_patch.py
    
The script will:
1. Read analytics/contracts_v14.py
2. Replace SECTION 6 (Sensitivity & Tornado Contracts) entirely
3. Write the corrected file
4. Self-delete on success

GWTF Compliance: R14, R17, R24, TYPE-01
"""

import re
import sys
from pathlib import Path
from typing import Optional


# Complete corrected SECTION 6
SECTION_6_CORRECTED = '''# ═════════════════════════════════════════════════════════════════════════════
# SECTION 6: Sensitivity & Tornado Contracts
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class ParameterRangeConfig:
    """CCCDIR: Configuration for a single sensitivity parameter with validation."""

    variable_name: str
    base_value: float
    low_pct: float = -10.0
    high_pct: float = 10.0
    steps: int = 5
    label: Optional[str] = None
    shock_type: str = "scalar"

    def __post_init__(self) -> None:
        """GWTF R15: Post-initialization validation."""
        self.variable_name = self.variable_name.strip()
        
        if not self.variable_name:
            raise ValueError("variable_name cannot be empty")
        
        if self.base_value <= 0:
            raise ValueError(f"base_value must be > 0, got {self.base_value}")
        
        if self.low_pct < -50.0 or self.low_pct > 0.0:
            raise ValueError(f"low_pct must be in range [-50, 0], got {self.low_pct}")
        
        if self.high_pct < 0.0 or self.high_pct > 100.0:
            raise ValueError(f"high_pct must be in range [0, 100], got {self.high_pct}")
        
        if self.high_pct < abs(self.low_pct):
            raise ValueError(
                f"High bound ({self.high_pct}%) must be >= absolute value "
                f"of low bound ({abs(self.low_pct)}%)"
            )
        
        if self.steps < 3 or self.steps > 20:
            raise ValueError(f"steps must be in range [3, 20], got {self.steps}")

    @property
    def low_value(self) -> float:
        """Computed low value: base_value * (1 + low_pct/100)."""
        return self.base_value * (1.0 + self.low_pct / 100.0)

    @property
    def high_value(self) -> float:
        """Computed high value: base_value * (1 + high_pct/100)."""
        return self.base_value * (1.0 + self.high_pct / 100.0)


@dataclass
class TornadoResult:
    """CASPER: Single-parameter tornado analysis result (test-compatible)."""

    variable: str
    base_irr: float
    low_irr: float
    high_irr: float

    @property
    def impact_abs(self) -> float:
        """Absolute impact: |high_irr - low_irr|."""
        import math
        
        if math.isnan(self.low_irr) or math.isnan(self.high_irr):
            return float('nan')
        
        return abs(self.high_irr - self.low_irr)

    @property
    def impact_pct(self) -> float:
        """Percentage impact: (high_irr - low_irr) / base_irr * 100."""
        import math
        
        if math.isnan(self.low_irr) or math.isnan(self.high_irr) or math.isnan(self.base_irr):
            return float('nan')
        
        if self.base_irr == 0.0:
            return 0.0
        
        return ((self.high_irr - self.low_irr) / self.base_irr) * 100.0


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
class MultiShockTornadoResult:
    """CASPER: Multi-shock tornado chart data (legacy compatibility)."""

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
    tornado_charts: Dict[str, MultiShockTornadoResult]  # Updated reference
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


def apply_section_6_patch(content: str) -> str:
    """Replace SECTION 6 with corrected version.
    
    Args:
        content: Original file content
        
    Returns:
        Patched content
    """
    # Find SECTION 6 boundaries
    section_6_start = content.find('# SECTION 6: Sensitivity & Tornado Contracts')
    section_7_start = content.find('# SECTION 7: Tail Risk & Monte Carlo Contracts')
    
    if section_6_start == -1 or section_7_start == -1:
        raise ValueError("Could not find SECTION 6 or SECTION 7 markers")
    
    # Replace SECTION 6
    before = content[:section_6_start]
    after = content[section_7_start:]
    
    return before + SECTION_6_CORRECTED + "\n\n" + after


def main() -> None:
    """Main execution: Apply patch and self-delete."""
    
    file_path = Path('analytics/contracts_v14.py')
    script_path = Path(__file__)
    
    if not file_path.exists():
        print(f"❌ ERROR: {file_path} not found")
        print("   Make sure you're running from repo root")
        sys.exit(1)
    
    print("📖 Reading analytics/contracts_v14.py...")
    content = file_path.read_text()
    original_size = len(content)
    
    print("🔧 Applying SECTION 6 patch...")
    try:
        patched_content = apply_section_6_patch(content)
    except Exception as e:
        print(f"❌ ERROR: Patch failed: {e}")
        sys.exit(1)
    
    new_size = len(patched_content)
    
    print(f"💾 Writing patched file ({new_size} bytes, was {original_size})...")
    file_path.write_text(patched_content)
    
    print("\n✅ Patch applied successfully!")
    print("\n📋 Changes made:")
    print("  1. ParameterRangeConfig: Added steps, __post_init__, @property methods")
    print("  2. TornadoResult: NEW single-parameter class")
    print("  3. MultiShockTornadoResult: Renamed from old TornadoResult")
    
    print("\n🧪 Next steps:")
    print("  1. Test: pytest tests/finance/test_contracts.py -v")
    print("  2. Commit: git add analytics/contracts_v14.py")
    print("  3. Commit: git commit -m 'fix: update contracts with test-compatible signatures'")
    print("  4. Push: git push origin feature/add-finance-contracts-pydantic-v2-20251219")
    
    # Self-delete
    print(f"\n🗑️  Self-deleting {script_path.name}...")
    try:
        script_path.unlink()
        print("   ✅ Script removed (one-time use complete)")
    except Exception as e:
        print(f"   ⚠️  Could not self-delete: {e}")
        print("   Please manually remove scripts/apply_contracts_patch.py after committing")


if __name__ == '__main__':
    main()
