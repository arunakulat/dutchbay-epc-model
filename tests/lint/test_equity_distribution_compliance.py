"""GWTF v3.0 Compliance tests for Equity Distribution Module v14.

Validates adherence to Go-with-the-Flow ruleset:
- R3: No argparse anywhere
- R4: No Typer in v14 modules
- R10: Ruff linting passes
- CST-01: LibCST import guardrails
- TYPE-01: Type annotations complete
- ARCH-01: Config-first design
- VAL-01: Pydantic v2 validators
- DOC-01: Docstring completeness

Author: DutchBay Test Team
Date: December 16, 2025
"""

import ast
import re
from pathlib import Path
import pytest


MODULE_PATH = Path("finance/equity_distribution_v14_hydra.py")


class TestGWTFCompliance:
    """Test Go-with-the-Flow v3.0 compliance."""
    
    def test_module_exists(self) -> None:
        """Equity distribution module file exists."""
        assert MODULE_PATH.exists(), f"Module not found: {MODULE_PATH}"
    
    def test_no_argparse_import(self) -> None:
        """R3: Module must not import argparse."""
        content = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(MODULE_PATH))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "argparse", (
                        f"GWTF R3 violation: argparse import found in {MODULE_PATH}. "
                        "Use Hydra/OmegaConf instead."
                    )
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "argparse", (
                    f"GWTF R3 violation: argparse import found in {MODULE_PATH}. "
                    "Use Hydra/OmegaConf instead."
                )
    
    def test_no_typer_import(self) -> None:
        """R4: Module must not import Typer (v14 uses Hydra)."""
        content = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(MODULE_PATH))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "typer", (
                        f"GWTF R4 violation: typer import found in {MODULE_PATH}. "
                        "v14 modules use Hydra, not Typer."
                    )
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "typer", (
                    f"GWTF R4 violation: typer import found in {MODULE_PATH}. "
                    "v14 modules use Hydra, not Typer."
                )
    
    def test_uses_pydantic_v2(self) -> None:
        """VAL-01: Module must use Pydantic v2 BaseModel."""
        content = MODULE_PATH.read_text(encoding="utf-8")
        
        # Check for Pydantic import
        assert "from pydantic import" in content, "Module must import from pydantic"
        
        # Check for v2 ConfigDict usage (not Config class)
        assert "ConfigDict" in content, (
            "Pydantic v2 uses ConfigDict, not nested Config class"
        )
        assert "model_config = ConfigDict(" in content, (
            "Pydantic v2 requires 'model_config = ConfigDict(...)'"
        )
    
    def test_has_type_annotations(self) -> None:
        """TYPE-01: All public functions must have type annotations."""
        content = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(MODULE_PATH))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Skip private functions (start with _)
                if node.name.startswith("_"):
                    continue
                
                # Check return annotation
                assert node.returns is not None, (
                    f"Function '{node.name}' missing return type annotation (TYPE-01)"
                )
                
                # Check argument annotations (skip 'self' and 'cls')
                for arg in node.args.args:
                    if arg.arg in {'self', 'cls'}:
                        continue
                    assert arg.annotation is not None, (
                        f"Function '{node.name}' argument '{arg.arg}' "
                        f"missing type annotation (TYPE-01)"
                    )
    
    def test_has_module_docstring(self) -> None:
        """DOC-01: Module must have comprehensive docstring."""
        content = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(MODULE_PATH))
        
        docstring = ast.get_docstring(tree)
        assert docstring is not None, "Module missing docstring (DOC-01)"
        assert len(docstring) > 100, "Module docstring too short (DOC-01)"
        assert "Equity Distribution" in docstring, (
            "Module docstring must describe Equity Distribution"
        )
    
    def test_classes_have_docstrings(self) -> None:
        """DOC-01: All classes must have docstrings."""
        content = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(MODULE_PATH))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                docstring = ast.get_docstring(node)
                assert docstring is not None, (
                    f"Class '{node.name}' missing docstring (DOC-01)"
                )
                assert len(docstring) > 20, (
                    f"Class '{node.name}' docstring too short (DOC-01)"
                )
    
    def test_public_methods_have_docstrings(self) -> None:
        """DOC-01: All public methods must have docstrings."""
        content = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(MODULE_PATH))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Skip private methods
                if node.name.startswith("_") and node.name != "__init__":
                    continue
                
                docstring = ast.get_docstring(node)
                assert docstring is not None, (
                    f"Method '{node.name}' missing docstring (DOC-01)"
                )
    
    def test_uses_logging_not_print(self) -> None:
        """CST-01: Module should use logging, not print (except __main__)."""
        content = MODULE_PATH.read_text(encoding="utf-8")
        lines = content.split('\n')
        
        in_main_block = False
        for line in lines:
            # Track if we're in __main__ block
            if 'if __name__ ==' in line:
                in_main_block = True
            
            # Allow print() in __main__ for testing
            if in_main_block:
                continue
            
            # Disallow print() outside __main__
            if re.search(r'\bprint\s*\(', line) and not line.strip().startswith('#'):
                assert False, (
                    f"Found print() outside __main__ block (CST-01): {line.strip()}. "
                    "Use logger.info/debug instead."
                )
    
    def test_has_field_validators(self) -> None:
        """VAL-01: Config class must use Pydantic v2 field validators."""
        content = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(MODULE_PATH))
        
        # Find EquityDistributionConfig class
        config_class = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "EquityDistributionConfig":
                config_class = node
                break
        
        assert config_class is not None, "EquityDistributionConfig class not found"
        
        # Check for field_validator decorators
        has_validators = False
        for item in config_class.body:
            if isinstance(item, ast.FunctionDef):
                for decorator in item.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == "field_validator":
                        has_validators = True
                        break
                    elif isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Name) and decorator.func.id == "field_validator":
                            has_validators = True
                            break
        
        assert has_validators, (
            "EquityDistributionConfig must use @field_validator for validation (VAL-01)"
        )
    
    def test_imports_from_future(self) -> None:
        """CST-01: Module should use future annotations for cleaner types."""
        content = MODULE_PATH.read_text(encoding="utf-8")
        lines = content.split('\n')
        
        # Check first few lines for future import
        first_20_lines = '\n'.join(lines[:20])
        assert "from __future__ import annotations" in first_20_lines, (
            "Module should import annotations from __future__ (CST-01)"
        )
    
    def test_no_hardcoded_magic_numbers(self) -> None:
        """ARCH-01: Business logic should use config, not magic numbers."""
        content = MODULE_PATH.read_text(encoding="utf-8")
        
        # Check that thresholds come from config, not hardcoded
        # This is a heuristic check for common patterns
        assert "self.config.min_dscr_threshold" in content, (
            "DSCR threshold should come from config (ARCH-01)"
        )
        assert "self.config.min_llcr_threshold" in content, (
            "LLCR threshold should come from config (ARCH-01)"
        )
        assert "self.config.min_reserve_months" in content, (
            "Reserve months should come from config (ARCH-01)"
        )
    
    def test_classes_use_proper_typing(self) -> None:
        """TYPE-01: Classes should use Dict, List, Tuple from typing."""
        content = MODULE_PATH.read_text(encoding="utf-8")
        
        # Check for proper typing imports
        assert "from typing import" in content, "Module must import from typing"
        
        # Should use Dict[str, Any] not dict
        # Should use List[float] not list
        tree = ast.parse(content, filename=str(MODULE_PATH))
        
        has_typed_returns = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.returns:
                # Check if return type uses proper typing constructs
                return_str = ast.unparse(node.returns)
                if 'Dict' in return_str or 'List' in return_str or 'Tuple' in return_str:
                    has_typed_returns = True
        
        assert has_typed_returns, (
            "Module should use typing.Dict, typing.List for return types (TYPE-01)"
        )
    
    def test_config_uses_field_defaults(self) -> None:
        """ARCH-01: Config should use Pydantic Field() with defaults."""
        content = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(MODULE_PATH))
        
        # Find EquityDistributionConfig class
        config_class = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "EquityDistributionConfig":
                config_class = node
                break
        
        assert config_class is not None, "EquityDistributionConfig class not found"
        
        # Check for Field() usage with default values
        has_field_defaults = False
        for item in config_class.body:
            if isinstance(item, ast.AnnAssign):
                if isinstance(item.value, ast.Call):
                    if isinstance(item.value.func, ast.Name) and item.value.func.id == "Field":
                        # Check for 'default' keyword argument
                        for keyword in item.value.keywords:
                            if keyword.arg == "default":
                                has_field_defaults = True
                                break
        
        assert has_field_defaults, (
            "EquityDistributionConfig should use Field(default=...) for config values (ARCH-01)"
        )
    
    def test_no_global_state(self) -> None:
        """ARCH-01: Module should not use global mutable state."""
        content = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(MODULE_PATH))
        
        # Check for module-level mutable assignments (except logger)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Allow logger = logging.getLogger(...)
                        if target.id == "logger":
                            continue
                        
                        # Disallow mutable globals like lists/dicts
                        if isinstance(node.value, (ast.List, ast.Dict, ast.Set)):
                            assert False, (
                                f"Global mutable state found: {target.id} (ARCH-01). "
                                "Use class attributes or config instead."
                            )
