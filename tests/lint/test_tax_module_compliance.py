"""
LibCST Compliance Tests for Tax Profile Module

Verifies that the tax profile module follows GWTF v3.0 compliance rules:
- No hardcoded constants
- No banned imports (argparse, typer)
- Proper OmegaConf usage
- No dangerous patterns

Author: DutchBay Finance Team
Date: December 16, 2025
"""

from pathlib import Path


class TestTaxModuleCompliance:
    """Test tax module compliance with GWTF rules."""

    @staticmethod
    def get_tax_module_content() -> str:
        """Load tax profile module content."""
        module_path = Path("finance/tax_profile_v14_hydra.py")
        return module_path.read_text()

    def test_no_hardcoded_numeric_constants(self):
        """Tax module must not have hardcoded numeric constants in code.

        GWTF ARCH-01: All parameters must come from YAML config.
        """
        content = self.get_tax_module_content()

        # Only check the code part (after function definitions)
        # Skip docstring section which may contain documentation
        code_section = content.split("__all__")[0]  # Get everything before __all__

        # Check for patterns like: variable = 0.24 or rate = 3
        # These are indicators of hardcoded constants in actual code
        # Only match actual assignments in function bodies (use = with leading space)
        import re

        # Check for hardcoded numbers assigned to meaningful variables
        # Pattern: spaces + word = digit
        hardcoded_rate = re.search(r"\s+corporate_tax_rate\s*=\s*0\.", code_section)
        if hardcoded_rate:
            raise AssertionError(
                "Hardcoded corporate_tax_rate found. All values must come from config."
            )

        hardcoded_holiday = re.search(r"\s+tax_holiday_years\s*=\s*\d+", code_section)
        if hardcoded_holiday:
            raise AssertionError(
                "Hardcoded tax_holiday_years found. All values must come from config."
            )

        hardcoded_depr = re.search(r"\s+depreciation_years\s*=\s*\d+", code_section)
        if hardcoded_depr:
            raise AssertionError(
                "Hardcoded depreciation_years found. All values must come from config."
            )

    def test_no_argparse_import(self):
        """Tax module must not import argparse.

        GWTF CLI-01: All v14 CLIs must use Hydra (hydra-core).
        argparse is banned repo-wide for v14 code.
        """
        content = self.get_tax_module_content()

        assert (
            "import argparse" not in content
        ), "argparse is banned in v14 code. Use Hydra instead."
        assert (
            "from argparse" not in content
        ), "argparse is banned in v14 code. Use Hydra instead."

    def test_no_typer_import(self):
        """Tax module must not import typer.

        GWTF R4: No Typer in v14 CLIs.
        """
        content = self.get_tax_module_content()

        assert (
            "from typer" not in content
        ), "Typer is banned in v14 code. Use Hydra instead."
        assert (
            "import typer" not in content
        ), "Typer is banned in v14 code. Use Hydra instead."

    def test_no_sys_argv_parsing(self):
        """Tax module should not parse sys.argv directly.

        GWTF CLI-01: Configuration must come through Hydra, not sys.argv.
        """
        content = self.get_tax_module_content()

        # Check for direct sys.argv usage (not comprehensive, but good indicator)
        assert (
            "sys.argv" not in content
        ), "Do not parse sys.argv directly. Use Hydra for config."

    def test_has_omegaconf_import(self):
        """Tax module must import OmegaConf.

        GWTF CLI-01: Hydra CLIs use OmegaConf for config management.
        """
        content = self.get_tax_module_content()

        assert (
            "from omegaconf import" in content
        ), "Tax module must import from omegaconf (DictConfig, OmegaConf)"
        assert (
            "DictConfig" in content
        ), "Tax module must use DictConfig for config parameters"

    def test_has_proper_config_extraction(self):
        """Tax module must extract config from DictConfig parameters.

        GWTF ARCH-01: Config-first architecture.
        """
        content = self.get_tax_module_content()

        # Should extract from config, not hardcode
        assert (
            "def build_tax_profile" in content
        ), "Tax module should have build_tax_profile function"
        assert (
            "config_tax" in content or "config.tax" in content
        ), "Tax module should extract tax config section"

    def test_has_docstring(self):
        """Tax module must have module-level docstring.

        GWTF TYPE-01: All modules must be documented.
        """
        content = self.get_tax_module_content()

        # Check for opening docstring
        assert '"""' in content or "'''" in content, "Module must have docstring"

    def test_has_type_hints(self):
        """Tax module should have type hints.

        GWTF TYPE-01: All new v14 modules must be fully type-annotated.
        """
        content = self.get_tax_module_content()

        # Check for common type hint patterns
        assert "->" in content, "Functions should have return type hints"
        assert ": " in content, "Parameters should have type hints"
        assert (
            "from typing import" in content or "typing." in content
        ), "Module should use typing for annotations"

    def test_has_frozen_dataclass(self):
        """Tax profile should use frozen dataclass for immutability.

        Frozen dataclasses prevent accidental mutation and improve audit safety.
        """
        content = self.get_tax_module_content()

        assert "@dataclass" in content, "Tax profile should use dataclass"
        assert (
            "frozen=True" in content
        ), "Tax profile should be frozen (immutable) for audit safety"

    def test_has_config_source_tracking(self):
        """Tax profile should track config source for audit trail.

        Enables reproducibility and tracing of where values came from.
        """
        content = self.get_tax_module_content()

        assert (
            "config_source" in content
        ), "Tax profile should track config source for audit trail"

    def test_no_interactive_input(self):
        """Tax module should not use input() for interactive input.

        GWTF CST-01: interactive input() is forbidden in CI-covered code.
        """
        content = self.get_tax_module_content()

        assert (
            "input(" not in content
        ), "No interactive input() allowed in production code"

    def test_no_global_mutable_defaults(self):
        """Tax module should not use mutable defaults in function signatures.

        Python anti-pattern: mutable defaults are shared across calls.
        """
        content = self.get_tax_module_content()

        # Check for patterns like: def func(list=[]) or def func(dict={})
        assert "=[]" not in content, "Mutable list default found"
        assert "={}" not in content, "Mutable dict default found"

    def test_has_validation(self):
        """Tax module should validate config inputs.

        GWTF VAL-01: Schema guard validates before use.
        """
        content = self.get_tax_module_content()

        # Check for validation patterns
        assert (
            "raise ValueError" in content or "raise TypeError" in content
        ), "Module should validate inputs"
        assert (
            "if not" in content or "assert" in content
        ), "Module should have validation checks"

    def test_no_bare_except(self):
        """Tax module should not use bare except clauses.

        Bare except hides errors. Should catch specific exceptions.
        """
        content = self.get_tax_module_content()

        # Check for bare except (not perfect, but good indicator)
        lines = content.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "except:":
                # This is a bare except - not allowed
                raise AssertionError(
                    f"Bare except clause found at line {i+1}. "
                    "Catch specific exceptions instead."
                )


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
