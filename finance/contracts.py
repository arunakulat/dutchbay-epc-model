from typing import Optional, List
from pydantic import BaseModel, field_validator, model_validator
import numpy as np

class TornadoResult(BaseModel):
    variable: str
    base_irr: float
    low_irr: float
    high_irr: float
    
    @property
    def impact_pct(self) -> float:
        if self.base_irr == 0:
            return 0.0
        return ((self.high_irr - self.low_irr) / abs(self.base_irr)) * 100
    
    @property
    def impact_abs(self) -> float:
        return self.high_irr - self.low_irr

class ParameterRangeConfig(BaseModel):
    variable_name: str
    base_value: float
    low_pct: float
    high_pct: float
    steps: int = 5
    label: Optional[str] = None
    shock_type: str = "scalar"
    low_value: Optional[float] = None
    high_value: Optional[float] = None
    
    @field_validator('variable_name', mode='before')
    @classmethod
    def validate_variable_name(cls, v):
        v = str(v).strip()
        if not v:
            raise ValueError('variable_name cannot be empty')
        return v
    
    @field_validator('base_value')
    @classmethod
    def validate_base_value(cls, v):
        if v <= 0:
            raise ValueError('base_value must be positive')
        return v
    
    @field_validator('low_pct')
    @classmethod
    def validate_low_pct(cls, v):
        if v >= 0:
            raise ValueError('low_pct must be negative')
        if v < -50:
            raise ValueError('low_pct cannot be less than -50%')
        return v
    
    @field_validator('high_pct')
    @classmethod
    def validate_high_pct(cls, v):
        if v <= 0:
            raise ValueError('high_pct must be positive')
        if v > 100:
            raise ValueError('high_pct cannot exceed 100%')
        return v
    
    @field_validator('steps')
    @classmethod
    def validate_steps(cls, v):
        if v < 3:
            raise ValueError('steps must be at least 3')
        if v > 20:
            raise ValueError('steps cannot exceed 20')
        return v
    
    @model_validator(mode='after')
    def compute_and_validate_range(self):
        if self.high_pct <= abs(self.low_pct):
            raise ValueError('high_pct must exceed abs(low_pct)')
        self.low_value = self.base_value * (1 + self.low_pct / 100)
        self.high_value = self.base_value * (1 + self.high_pct / 100)
        return self
    
    def generate_values(self) -> List[float]:
        if self.low_value is None or self.high_value is None:
            low = self.base_value * (1 + self.low_pct / 100)
            high = self.base_value * (1 + self.high_pct / 100)
            return list(np.linspace(low, high, self.steps))
        return list(np.linspace(self.low_value, self.high_value, self.steps))

class TornadoAnalysisResults(BaseModel):
    results: List[TornadoResult]
    base_case_irr: float
    
    def sorted_by_impact_abs(self) -> List[TornadoResult]:
        return sorted(self.results, key=lambda r: r.impact_abs, reverse=True)
    
    def sorted_by_impact_pct(self) -> List[TornadoResult]:
        return sorted(self.results, key=lambda r: r.impact_pct, reverse=True)

class SensitivityScenario(BaseModel):
    name: str
    description: Optional[str] = None
    parameter_configs: List[ParameterRangeConfig]
    
    def total_combinations(self) -> int:
        total = 1
        for config in self.parameter_configs:
            total *= config.steps
        return total

class TornadoMetrics(BaseModel):
    mean_impact_pct: float
    median_impact_pct: float
    max_impact_pct: float
    min_impact_pct: float
    std_dev_impact_pct: float
    
    @classmethod
    def from_results(cls, results: List[TornadoResult]) -> 'TornadoMetrics':
        impacts = [r.impact_pct for r in results]
        return cls(
            mean_impact_pct=float(np.mean(impacts)),
            median_impact_pct=float(np.median(impacts)),
            max_impact_pct=float(np.max(impacts)),
            min_impact_pct=float(np.min(impacts)),
            std_dev_impact_pct=float(np.std(impacts))
        )

class ParameterImpactRanking(BaseModel):
    variable: str
    impact_pct_rank: int
    impact_abs_rank: int
    impact_pct: float
    impact_abs: float
