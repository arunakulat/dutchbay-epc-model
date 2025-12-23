# Pydantic V2 Runtime Risk Analysis

**Date:** 2025-12-23  
**Branch:** feature/add-finance-contracts-pydantic-v2-20251219  
**Analysis Scope:** Complete codebase ingestion and retrospection

---

## 🚨 **HIGH-PRIORITY RUNTIME RISKS**

### **1. Frozen Model Mutation Attempts**

**Risk Level:** 🔴 **CRITICAL**

**Location:** Any code attempting to modify Pydantic models with `frozen=True`

**Example from contracts_v14.py:**
```python
class ParameterRangeConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    variable_name: str
    base_value: float
    # ...
```

**Potential Runtime Error:**
```python
param = ParameterRangeConfig(variable_name="capex", base_value=1000.0, ...)
param.base_value = 1100.0  # ❌ ValidationError: frozen_instance
```

**Pydantic V2 Behavior:**
- V1: Would raise `TypeError: "..." is immutable...`
- V2: Raises `ValidationError` with `type='frozen_instance'`

**Mitigation:**
✅ **ALREADY APPLIED** - All adapters create new instances instead of mutating:
```python
# analytics/sensitivity/adapters.py
def parameter_to_engine_spec(param: ParameterRangeConfig) -> Dict[str, Any]:
    # Returns dict, doesn't mutate param ✅
    return {
        "name": param.label or param.variable_name,
        "override_key": param.variable_name,
        # ...
    }
```

**Action Required:** ✅ None - Code is safe

---

### **2. Model Serialization: `.dict()` vs `.model_dump()`**

**Risk Level:** 🟡 **MEDIUM** (Deprecation warnings, will break in V3)

**Location:** Anywhere Pydantic models are converted to dicts

**Pydantic V2 Changes:**
```python
# V1 (DEPRECATED)
model_dict = my_model.dict()

# V2 (CORRECT)
model_dict = my_model.model_dump()
```

**Current Codebase Status:**

✅ **SAFE** - We use `asdict()` from dataclasses, not `.dict()`:
```python
# analytics/pipeline_v14_enhanced.py
from dataclasses import asdict

scenario_result = ScenarioResult(...)
result = {
    "scenario_result": asdict(scenario_result),  # ✅ Safe
}
```

**Potential Issue in export.py:**
```python
# analytics/sensitivity/export.py (line ~95)
if tail_risk_block:
    tail_risk_block = {
        "rows": tail_df.to_dict(orient="records"),  # ✅ This is pandas, not Pydantic
    }
```

**Action Required:** ✅ None - No `.dict()` calls on Pydantic models found

---

### **3. Accessing `model_fields` on Instances**

**Risk Level:** 🟡 **MEDIUM** (Deprecation in V2.11, will break in V3)

**Pydantic V2.11+ Behavior:**
```python
# DEPRECATED (will break in V3)
my_model = Model(a=1)
fields = my_model.model_fields  # ⚠️ DeprecationWarning

# CORRECT
fields = Model.model_fields  # ✅ Access on class
```

**Search Results:** ❌ **NO VIOLATIONS FOUND**

We don't access `model_fields` anywhere in the codebase.

**Action Required:** ✅ None

---

### **4. Nested Model Serialization Behavior Change**

**Risk Level:** 🟢 **LOW** (Behavior change, not a break)

**Pydantic V2 Change:**
- V1: Always included all subclass fields when dumping
- V2: Only includes fields defined on the declared type

**Example:**
```python
class Parent(BaseModel):
    x: int

class Child(Parent):
    y: int  # Only in subclass

class Container(BaseModel):
    nested: Parent  # Type annotation is Parent

container = Container(nested=Child(x=1, y=2))
container.model_dump()
# V1: {"nested": {"x": 1, "y": 2}}  # Includes y
# V2: {"nested": {"x": 1}}          # Excludes y (matches type hint)
```

**Impact Analysis:**

Our contracts use **explicit typing** throughout:
```python
# contracts_v14.py
class ScenarioResult:
    debt_profile: Optional[TrancheDebtProfile] = None  # ✅ Explicit type
    debt_covenants: Optional[DebtCovenantSnapshot] = None
```

No polymorphic subclass usage detected.

**Action Required:** ✅ None - Not applicable to our codebase

---

### **5. Computed Fields with `@computed_field`**

**Risk Level:** 🟢 **LOW** (New feature, well-implemented)

**Location:** `contracts_v14.py` uses `@computed_field` for backward compatibility

**Example:**
```python
class ShockSpec(BaseModel):
    parameter: str
    shocks: List[float]
    
    @computed_field  # type: ignore[misc]
    @property
    def variable_name(self) -> str:
        """Backward compatibility property."""
        return self.parameter
```

**Status:** ✅ **CORRECTLY IMPLEMENTED**

- Uses `@computed_field` decorator
- Combines with `@property` for getter behavior
- Type ignore comment handles mypy issue

**Action Required:** ✅ None - Working as designed

---

## 📊 **RISK SUMMARY TABLE**

| Risk Category | Severity | Status | Action Required |
|---|---|---|---|
| Frozen model mutation | 🔴 Critical | ✅ Safe | None - adapters use immutable patterns |
| `.dict()` deprecation | 🟡 Medium | ✅ Safe | None - using `asdict()` instead |
| `model_fields` on instance | 🟡 Medium | ✅ Safe | None - not used |
| Nested serialization | 🟢 Low | ✅ Safe | None - explicit typing used |
| Computed fields | 🟢 Low | ✅ Safe | None - correctly implemented |

---

## 🛡️ **DEFENSIVE PATTERNS APPLIED**

### **1. Adapter Pattern for Contract Isolation**

**File:** `analytics/sensitivity/adapters.py`

**Strategy:**
- Never mutate Pydantic models
- Always create new instances or extract to dicts
- Type conversions happen in adapter layer

```python
def parameter_to_engine_spec(param: ParameterRangeConfig) -> Dict[str, Any]:
    # Extract values, don't mutate ✅
    base = float(param.base_value)
    low_mult = 1.0 + (float(param.low_pct) / 100.0)
    high_mult = 1.0 + (float(param.high_pct) / 100.0)
    
    return {  # New dict, not mutation
        "name": param.label or param.variable_name,
        "override_key": param.variable_name,
        "base": base,
        "low": base * low_mult,
        "high": base * high_mult,
    }
```

### **2. Dataclass Usage for Mutable State**

**File:** `analytics/contracts_v14.py`

**Strategy:**
- Use `@dataclass` for non-validated, mutable structures
- Use Pydantic `BaseModel` for validated, immutable contracts

```python
@dataclass(frozen=True)  # Immutable, but not Pydantic
class TrancheDebtProfile:
    construction_years: int = 0
    tenor_years: int = 0
    # ...

class ParameterRangeConfig(BaseModel):  # Validated, immutable
    model_config = ConfigDict(frozen=True)
    variable_name: str
```

### **3. Type Coercion Instead of Model Access**

**File:** `analytics/sensitivity/adapters.py`

**Strategy:**
- Use `float(param.base_value)` to coerce, not assume type
- Defensive against Pydantic's type flexibility

```python
# DEFENSIVE ✅
base = float(param.base_value)  # Coerce even if already float
low_mult = 1.0 + (float(param.low_pct) / 100.0)

# RISKY ❌ (if Pydantic coerces string "10.5" to Decimal)
# base = param.base_value
# low_mult = 1.0 + (param.low_pct / 100.0)  # Could fail with Decimal
```

---

## 🔍 **TESTING RECOMMENDATIONS**

### **Unit Tests to Add:**

```python
# tests/test_pydantic_v2_safety.py

import pytest
from pydantic import ValidationError
from analytics.contracts_v14 import ParameterRangeConfig

def test_frozen_model_immutability():
    """Ensure frozen models raise ValidationError on mutation."""
    param = ParameterRangeConfig(
        variable_name="capex",
        base_value=1000.0,
        low_pct=-10.0,
        high_pct=10.0,
    )
    
    with pytest.raises(ValidationError) as exc_info:
        param.base_value = 1100.0
    
    assert exc_info.value.errors()[0]['type'] == 'frozen_instance'

def test_adapter_creates_new_instances():
    """Ensure adapters don't mutate original models."""
    from analytics.sensitivity.adapters import parameter_to_engine_spec
    
    param = ParameterRangeConfig(
        variable_name="capex",
        base_value=1000.0,
        low_pct=-10.0,
        high_pct=10.0,
    )
    
    original_id = id(param)
    spec = parameter_to_engine_spec(param)
    
    # Ensure original unchanged
    assert param.base_value == 1000.0
    assert id(param) == original_id
    
    # Ensure spec is independent
    assert spec['base'] == 1000.0
    assert spec['low'] == 900.0
    assert spec['high'] == 1100.0
```

---

## ✅ **MIGRATION COMPLIANCE CHECKLIST**

- [x] All Pydantic models use `BaseModel` from `pydantic` v2
- [x] `ConfigDict` used instead of `Config` class
- [x] `frozen=True` in `model_config` instead of `Config.allow_mutation = False`
- [x] No `.dict()` calls on Pydantic models
- [x] No `model_fields` access on instances
- [x] `@computed_field` used correctly for backward-compat properties
- [x] Adapter layer isolates Pydantic from business logic
- [x] Defensive type coercion in all data extraction

---

## 📚 **REFERENCES**

1. [Pydantic V2 Migration Guide](https://docs.pydantic.dev/latest/migration/)
2. [Pydantic V2 Frozen Models](https://docs.pydantic.dev/latest/errors/validation_errors/#frozen_instance)
3. [Model Serialization Changes](https://docs.pydantic.dev/2.0/usage/serialization/)
4. [Computed Fields](https://docs.pydantic.dev/latest/concepts/models/#computed-fields)

---

## 🎯 **CONCLUSION**

**Overall Risk Assessment:** 🟢 **LOW**

The codebase demonstrates **excellent Pydantic v2 hygiene**:

✅ No frozen model mutations  
✅ No deprecated `.dict()` usage  
✅ Clean adapter pattern for contract isolation  
✅ Defensive type coercion throughout  
✅ Proper use of `@computed_field` for backward compatibility  

**No immediate action required.** The code is production-ready for Pydantic v2.

**Future-Proofing:**
- Monitor for Pydantic v2.11+ deprecation warnings
- Add unit tests for frozen model immutability
- Consider type stubs if mypy issues arise with `@computed_field`
