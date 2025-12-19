#!/usr/bin/env python3
"""Patch analytics/contracts_v14.py with missing sensitivity contracts.

This script updates the contracts file to add:
1. Enhanced ParameterRangeConfig with validation and computed properties
2. New single-parameter TornadoResult class
3. Renames existing TornadoResult to MultiShockTornadoResult

GWTF Compliance:
- R14: Scripts in scripts/ directory
- R17: Google-style docstrings
- R24: Docstring-first development
- TYPE-01: Full type annotations

Usage:
    python scripts/patch_contracts_v14_add_tornado_single.py
"""

import re
from pathlib import Path
from typing import Tuple


def patch_param_range_config(content: str) -> str:
    """Replace ParameterRangeConfig with enhanced version.
    
    Args:
        content: Original file content
        
    Returns:
        Modified content with updated ParameterRangeConfig
    """
    
    old_pattern = r'@dataclass\s+class ParameterRangeConfig:.*?shock_type: str = "scalar".*?(?=#|\n\n@|\nclass)'
    
    new_impl = '''@dataclass
class ParameterRangeConfig:
    """CCCDIR: Configuration for a single sensitivity parameter.
    
    Supports both explicit value ranges and percentage-based ranges.
    Includes validation and computed properties for low/high values.
    """

    variable_name: str
    base_value: float
    low_pct: float = -10.0
    high_pct: float = 10.0
    steps: int = 5
    label: Optional[str] = None
    shock_type: str = "scalar"

    def __post_init__(self) -> None:
        """GWTF R15: Post-initialization validation."""
        import math
        
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
'''
    
    return re.sub(old_pattern, new_impl, content, flags=re.DOTALL)


def add_tornado_result_single(content: str) -> str:
    """Add new single-parameter TornadoResult after ParameterRangeConfig.
    
    Args:
        content: Original file content
        
    Returns:
        Modified content with new TornadoResult class
    """
    
    # Find insertion point after ParameterRangeConfig
    insertion_marker = 'class ShockSpec:'
    
    new_class = '''\n\n@dataclass
class TornadoResult:
    """CASPER: Single-parameter tornado analysis result.
    
    Captures the sensitivity of a metric (typically IRR) to changes in
    a single input variable.
    """

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
'''
    
    return content.replace(f'@dataclass\nclass {insertion_marker}', new_class + insertion_marker)


def rename_existing_tornado(content: str) -> str:
    """Rename existing TornadoResult to MultiShockTornadoResult.
    
    Args:
        content: Original file content
        
    Returns:
        Modified content with renamed class
    """
    # Find the existing TornadoResult that has metric_name, base_metric, shock_results
    old_pattern = r'@dataclass\s+class TornadoResult:\s+"""CASPER: Tornado chart data.*?shock_results: List\[ShockResult\]'
    
    replacement = '@dataclass\nclass MultiShockTornadoResult:\n    """CASPER: Multi-shock tornado chart data (legacy)."""\n\n    metric_name: str\n    base_metric: float\n    shock_results: List[ShockResult]'
    
    content = re.sub(old_pattern, replacement, content, flags=re.DOTALL)
    
    # Also update references in MultiMetricTornadoResult
    content = content.replace(
        'tornado_charts: Dict[str, TornadoResult]',
        'tornado_charts: Dict[str, MultiShockTornadoResult]'
    )
    
    return content


def main() -> None:
    """Main execution: Apply all patches to analytics/contracts_v14.py."""
    
    file_path = Path('analytics/contracts_v14.py')
    
    if not file_path.exists():
        raise FileNotFoundError(f"{file_path} not found")
    
    print(f"📖 Reading {file_path}...")
    content = file_path.read_text()
    original_size = len(content)
    
    print("🔧 Applying patches...")
    
    # Step 1: Update ParameterRangeConfig
    print("  1. Updating ParameterRangeConfig...")
    content = patch_param_range_config(content)
    
    # Step 2: Rename existing TornadoResult
    print("  2. Renaming TornadoResult → MultiShockTornadoResult...")
    content = rename_existing_tornado(content)
    
    # Step 3: Add new TornadoResult
    print("  3. Adding new single-parameter TornadoResult...")
    content = add_tornado_result_single(content)
    
    # Write back
    print(f"💾 Writing updated file ({len(content)} bytes, was {original_size})...")
    file_path.write_text(content)
    
    print("\n✅ Patches applied successfully!")
    print("\nNext steps:")
    print("  1. Review changes: git diff analytics/contracts_v14.py")
    print("  2. Run tests: pytest tests/finance/test_contracts.py -v")
    print("  3. Commit: git add analytics/contracts_v14.py && git commit")


if __name__ == '__main__':
    main()
