#!/usr/bin/env python3
"""Fix cashflow_v14 validate_parameters backward compatibility.

Changes return type from None to list[str] for test compatibility.
"""
from pathlib import Path

def fix_validate_parameters():
    """Make validate_parameters return empty list on success."""
    
    cashflow_file = Path("finance/cashflow_v14.py")
    content = cashflow_file.read_text()
    
    # Change return type in signature
    content = content.replace(
        "def validate_parameters(config: dict[str, Any]) -> None:",
        "def validate_parameters(config: dict[str, Any]) -> list[str]:"
    )
    
    # Change docstring Returns section
    content = content.replace(
        """    Raises:
        ValueError: If required parameters missing or values out of valid range""",
        """    Returns:
        Empty list if validation passes (backward compatible)
        
    Raises:
        ValueError: If required parameters missing or values out of valid range"""
    )
    
    # Add return statement at end of function (before the final if errors block)
    # Find the last line before # EOF that has the error raising
    old_error_block = """    # Raise comprehensive error if any validation failed
    if errors:
        error_msg = "Configuration validation failed:\\n" + "\\n".join(
            f"  • {err}" for err in errors
        )
        raise ValueError(error_msg)"""
    
    new_error_block = """    # Raise comprehensive error if any validation failed
    if errors:
        error_msg = "Configuration validation failed:\\n" + "\\n".join(
            f"  • {err}" for err in errors
        )
        raise ValueError(error_msg)
    
    # Return empty list on success (backward compatible)
    return []"""
    
    content = content.replace(old_error_block, new_error_block)
    
    cashflow_file.write_text(content)
    print("✅ Fixed finance/cashflow_v14.py validate_parameters return type")

def fix_fx_loader_type_hint():
    """Fix Optional type hint in fx_loader.py."""
    
    fx_loader = Path("analytics/fx/fx_loader.py")
    content = fx_loader.read_text()
    
    content = content.replace(
        "def discover_fx_files(scenarios_dir: Path = None)",
        "def discover_fx_files(scenarios_dir: Path | None = None)"
    )
    
    fx_loader.write_text(content)
    print("✅ Fixed analytics/fx/fx_loader.py type hint")

if __name__ == "__main__":
    fix_validate_parameters()
    fix_fx_loader_type_hint()
    print("\n✅ All fixes applied!")
    print("\nNext steps:")
    print("  black finance/cashflow_v14.py analytics/fx/fx_loader.py")
    print("  mypy finance/cashflow_v14.py --strict")
    print("  python -m pytest tests/api/ -q --tb=line")

# EOF
