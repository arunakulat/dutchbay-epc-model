#!/usr/bin/env python3
"""Fix test imports from dutchbay_v14chat to canonical v14 using LibCST.

Go with the Flow Compliance:
- LibCST for lossless, format-preserving refactoring
- Handles both direct imports and module aliases
- Absolute imports from package root
- v14 naming conventions
"""
from pathlib import Path
from typing import Union

import libcst as cst

# Module remapping: old_module -> new_module
MODULE_REMAP = {
    "dutchbay_v14chat.finance.irr": "finance.irr",
    "dutchbay_v14chat.finance.cashflow": "finance.cashflow_v14",
    "dutchbay_v14chat.finance.debt": "finance.debt_v14",
    "dutchbay_v14chat.finance.v14.scenario_manager": "analytics.scenario_manager",
    "dutchbay_v14chat.finance.v14.epc_helper": "analytics.core.epc_helper",
    "dutchbay_v14chat.finance.v14.tax_calculator": "finance.cashflow_v14",
    # Module aliases (import X as Y)
    "dutchbay_v14chat.finance": "finance",  # Will need submodule mapping
}

# Submodule mapping for aliased imports
SUBMODULE_REMAP = {
    "cashflow": "cashflow_v14",
    "debt": "debt_v14",
    "irr": "irr",  # No suffix for IRR
}


class LegacyImportTransformer(cst.CSTTransformer):
    """Transform legacy imports to v14 canonical imports."""

    def __init__(self):
        self.changes_made = False

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> Union[cst.ImportFrom, cst.RemovalSentinel]:
        """Handle 'from X import Y' statements."""
        if updated_node.module is None:
            return updated_node

        # Get the full module path
        module_parts = self._get_dotted_name_parts(updated_node.module)
        if not module_parts:
            return updated_node

        full_module = ".".join(module_parts)

        # Check if this is a legacy import we need to remap
        if not full_module.startswith("dutchbay_v14chat"):
            return updated_node

        # Handle module alias imports (from dutchbay_v14chat.finance import cashflow as cf_mod)
        if full_module == "dutchbay_v14chat.finance":
            return self._handle_module_alias_import(updated_node)

        # Handle direct imports (from dutchbay_v14chat.finance.cashflow import ...)
        new_module = MODULE_REMAP.get(full_module)
        if not new_module:
            print(f"⚠️  Unknown legacy import: {full_module}")
            return updated_node

        # Build new module node
        new_module_node = self._build_dotted_name(new_module)

        # Update the import
        self.changes_made = True
        return updated_node.with_changes(module=new_module_node)

    def _handle_module_alias_import(self, node: cst.ImportFrom) -> cst.ImportFrom:
        """Handle: from dutchbay_v14chat.finance import cashflow as cf_mod"""
        if not isinstance(node.names, cst.ImportStar):
            names = node.names if isinstance(node.names, list) else [node.names]

            # Check if we're importing a known submodule
            for name in names:
                if isinstance(name, cst.ImportAlias):
                    imported_name = (
                        name.name.value if isinstance(name.name, cst.Name) else None
                    )
                    if imported_name in SUBMODULE_REMAP:
                        # Map to correct v14 module
                        new_submodule = SUBMODULE_REMAP[imported_name]
                        new_module = f"finance.{new_submodule}"

                        # If there's an alias, we need to change the import pattern
                        # from dutchbay_v14chat.finance import cashflow as cf_mod
                        # becomes: from finance import cashflow_v14 as cf_mod

                        new_module_node = self._build_dotted_name("finance")
                        new_name = cst.ImportAlias(
                            name=cst.Name(new_submodule),
                            asname=name.asname,  # Keep the alias (as cf_mod)
                        )

                        self.changes_made = True
                        return node.with_changes(
                            module=new_module_node, names=[new_name]
                        )

        return node

    def _get_dotted_name_parts(self, node: cst.BaseExpression) -> list[str]:
        """Extract dotted name as list of parts."""
        if isinstance(node, cst.Name):
            return [node.value]
        elif isinstance(node, cst.Attribute):
            parts = self._get_dotted_name_parts(node.value)
            if parts:
                parts.append(node.attr.value)
                return parts
        return []

    def _build_dotted_name(self, dotted_name: str) -> cst.BaseExpression:
        """Build a dotted name node from string."""
        parts = dotted_name.split(".")
        if len(parts) == 1:
            return cst.Name(parts[0])

        result = cst.Name(parts[0])
        for part in parts[1:]:
            result = cst.Attribute(value=result, attr=cst.Name(part))
        return result


def fix_imports_in_file(filepath: Path) -> bool:
    """Fix imports in a single file using LibCST."""
    try:
        source_code = filepath.read_text()

        # Parse the module
        tree = cst.parse_module(source_code)

        # Transform
        transformer = LegacyImportTransformer()
        modified_tree = tree.visit(transformer)

        if transformer.changes_made:
            # Write back
            new_source = modified_tree.code
            filepath.write_text(new_source)
            print(f"✅ Fixed: {filepath.name}")
            return True

        return False

    except Exception as e:
        print(f"❌ Error fixing {filepath.name}: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Fix all test files in tests/api/."""
    repo_root = Path(__file__).parent.parent
    tests_dir = repo_root / "tests" / "api"

    if not tests_dir.exists():
        print(f"❌ Tests directory not found: {tests_dir}")
        return 1

    print("🔄 Scanning test files for legacy imports...\n")

    fixed_count = 0
    for test_file in sorted(tests_dir.glob("test_*.py")):
        if fix_imports_in_file(test_file):
            fixed_count += 1

    print(f"\n✅ Fixed {fixed_count} test files with LibCST")

    if fixed_count > 0:
        print("\n📋 Next steps:")
        print("  1. Verify: python scripts/check_legacy_imports.py")
        print("  2. Test syntax: python -m pytest tests/api/ --collect-only")
        print("  3. Format: black tests/api/ && isort tests/api/")
        print("  4. Commit changes")

    return 0


if __name__ == "__main__":
    exit(main())

# EOF
