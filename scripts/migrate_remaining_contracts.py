#!/usr/bin/env python3
"""Migrate remaining contracts to Pydantic v2."""

from pathlib import Path
import re

def main():
    contracts_file = Path("analytics/contracts_v14.py")
    content = contracts_file.read_text()
    
    # Step 1: Add field_validator and model_validator if not present
    if "from pydantic import BaseModel, ConfigDict" in content and "field_validator" not in content:
        content = content.replace(
            "from pydantic import BaseModel, ConfigDict",
            "from pydantic import BaseModel, ConfigDict, field_validator, model_validator"
        )
        print("✅ Added field_validator, model_validator imports")
    
    # Step 2: Migrate BreakevenResult
    breakeven_pattern = r'@dataclass\s+class BreakevenResult:.*?tolerance: float = 1000\.0.*?(?=\n\n@|\n\nclass |\Z)'
    breakeven_match = re.search(breakeven_pattern, content, re.DOTALL)
    
    if breakeven_match:
        new_breakeven = '''class BreakevenResult(BaseModel):
    """CASPER: Breakeven analysis (what value makes project NPV=0)."""

    model_config = ConfigDict(extra="forbid", frozen=False)

    variable_name: str
    base_value: float
    breakeven_value: float
    breakeven_pct_change: float
    is_positive_breakeven: bool
    metric_name: str = "project_npv"
    tolerance: float = 1000.0

    @field_validator("tolerance")
    @classmethod
    def validate_tolerance(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"Tolerance must be positive, got {v}")
        return v

    @field_validator("breakeven_pct_change")
    @classmethod
    def validate_pct_change(cls, v: float) -> float:
        if abs(v) > 500.0:
            raise ValueError(f"Breakeven change {v}% seems unrealistic (>500%)")
        return v'''
        
        content = re.sub(breakeven_pattern, new_breakeven, content, flags=re.DOTALL)
        print("✅ Migrated BreakevenResult to Pydantic BaseModel")
    
    # Step 3: Migrate TailRiskSnapshot
    tailrisk_pattern = r'@dataclass\s+class TailRiskSnapshot:.*?metadata: Dict\[str, Any\] = field\(default_factory=dict\)'
    tailrisk_match = re.search(tailrisk_pattern, content, re.DOTALL)
    
    if tailrisk_match:
        new_tailrisk = '''class TailRiskSnapshot(BaseModel):
    """CASPER: Tail risk metrics snapshot (VaR, CVaR, breach probabilities)."""

    model_config = ConfigDict(extra="allow", frozen=False)

    metric_name: str
    base_value: float

    # Value at Risk
    var_95: float
    var_99: float

    # Conditional Value at Risk (Expected Shortfall)
    cvar_95: float
    cvar_99: float

    # Percentiles
    p10: float
    p50: float
    p90: float

    # Breach probabilities
    covenant_breach_prob_pct: Optional[float] = None
    bankruptcy_prob_pct: Optional[float] = None

    # Distribution metrics
    mean: float = 0.0
    stdev: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0

    metadata: Dict[str, Any] = {}

    @model_validator(mode="after")
    def validate_risk_metrics(self) -> "TailRiskSnapshot":
        # VaR ordering: var_95 <= var_99
        if self.var_99 < self.var_95:
            raise ValueError(f"VaR 99% ({self.var_99}) must be >= VaR 95% ({self.var_95})")
        
        # CVaR ordering: cvar_95 <= cvar_99
        if self.cvar_99 < self.cvar_95:
            raise ValueError(f"CVaR 99% ({self.cvar_99}) must be >= CVaR 95% ({self.cvar_95})")
        
        # Percentile ordering: p10 <= p50 <= p90
        if not (self.p10 <= self.p50 <= self.p90):
            raise ValueError(f"Percentiles must be ordered: p10={self.p10} <= p50={self.p50} <= p90={self.p90}")
        
        # Probability bounds
        if self.covenant_breach_prob_pct is not None:
            if not (0 <= self.covenant_breach_prob_pct <= 100):
                raise ValueError(f"Covenant breach probability must be 0-100%, got {self.covenant_breach_prob_pct}")
        
        if self.bankruptcy_prob_pct is not None:
            if not (0 <= self.bankruptcy_prob_pct <= 100):
                raise ValueError(f"Bankruptcy probability must be 0-100%, got {self.bankruptcy_prob_pct}")
        
        return self'''
        
        content = re.sub(tailrisk_pattern, new_tailrisk, content, flags=re.DOTALL)
        print("✅ Migrated TailRiskSnapshot to Pydantic BaseModel")
    
    # Write back
    contracts_file.write_text(content)
    print(f"\n📊 Updated {contracts_file}")
    print("\nNext: Run pytest to verify migration")
    
    # Self-delete
    Path(__file__).unlink()
    print("🗑️  Self-deleted")

if __name__ == "__main__":
    main()
