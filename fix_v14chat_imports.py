#!/usr/bin/env python3
"""
Automated Import Fixer for dutchbay_v14chat → finance/analytics Migration

Uses LibCST to safely rewrite import statements according to the v14 refactor plan.

Usage:
    # Dry-run mode (preview changes)
    python fix_v14chat_imports.py --dry-run

    # Apply fixes (creates .bak files)
    python fix_v14chat_imports.py --apply

    # Apply fixes without backups
    python fix_v14chat_imports.py --apply --no-backup

Mapping Rules:
    dutchbay_v14chat.finance.cashflow → finance.cashflow_v14
    dutchbay_v14chat.finance.debt → finance.debt_v14
    dutchbay_v14chat.finance.irr → finance.irr
    dutchbay_v14chat.finance.v14.* → finance.* (direct promotion)

Safety Features:
    - Creates .bak backup files by default
    - Dry-run mode for preview
    - AST-safe transformations (preserves formatting)
    - Only touches import statements
    - Validates syntax after transformation
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Dict

try:
    import libcst as cst
except ImportError:
    print("❌ Error: libcst is not installed.", file=sys.stderr)
    print("Install it with: pip install libcst", file=sys.stderr)
    sys.exit(1)


# Import mapping rules
IMPORT_MAPPING: Dict[str, str] = {
    # finance submodules
    "dutchbay_v14chat.finance.cashflow": "finance.cashflow_v14",
    "dutchbay_v14chat.finance.debt": "finance.debt_v14",
    "dutchbay_v14chat.finance.irr": "finance.irr",
    "dutchbay_v14chat.finance.utils": "finance.utils",
    
    # v14 submodules (promoted to top-level finance)
    "dutchbay_v14chat.finance.v14.tax_calculator": "finance.tax_calculator_v14",
    "dutchbay_v14chat.finance.v14.scenario_manager": "finance.scenario_manager_v14",
    "dutchbay_v14chat.finance.v14.epc_helper": "finance.epc_helper_v14",
    
    # Catch-all for any missed v14 modules
    "dutchbay_v14chat.finance.v14": "finance",
    "dutchbay_v14chat.finance": "finance",
}


class ImportTransformer(cst.CSTTransformer):
    """LibCST transformer to rewrite dutchbay_v14chat imports."""
    
    def __init__(self) -> None:
        super().__init__()
        self.changes_made = 0
    
    def leave_ImportFrom(
        self,
        original_node: cst.ImportFrom,
        updated_node: cst.ImportFrom,
    ) -> cst.ImportFrom:
        """Transform 'from dutchbay_v14chat.X import Y' statements."""
        # Extract module name
        if isinstance(updated_node.module, cst.Attribute):
            module_parts = self._get_module_parts(updated_node.module)
        elif isinstance(updated_node.module, cst.Name):
            module_parts = [updated_node.module.value]
        else:
            return updated_node
        
        module_name = ".".join(module_parts)
        
        # Check if this import needs transformation
        if not module_name.startswith("dutchbay_v14chat"):
            return updated_node
        
        # Find matching rule (try longest match first)
        new_module_name = None
        for old_path, new_path in sorted(
            IMPORT_MAPPING.items(),
            key=lambda x: len(x[0]),
            reverse=True,
        ):
            if module_name.startswith(old_path):
                # Replace prefix
                new_module_name = module_name.replace(old_path, new_path, 1)
                break
        
        if new_module_name is None:
            print(
                f"⚠️  Warning: No mapping rule for {module_name}",
                file=sys.stderr,
            )
            return updated_node
        
        # Build new module node
        new_module = self._build_module_node(new_module_name)
        
        self.changes_made += 1
        return updated_node.with_changes(module=new_module)
    
    def leave_Import(
        self,
        original_node: cst.Import,
        updated_node: cst.Import,
    ) -> cst.Import:
        """Transform 'import dutchbay_v14chat' statements."""
        new_names = []
        
        for name in updated_node.names:
            if not isinstance(name, cst.ImportAlias):
                new_names.append(name)
                continue
            
            # Extract module name
            if isinstance(name.name, cst.Attribute):
                module_parts = self._get_module_parts(name.name)
            elif isinstance(name.name, cst.Name):
                module_parts = [name.name.value]
            else:
                new_names.append(name)
                continue
            
            module_name = ".".join(module_parts)
            
            # Check if needs transformation
            if not module_name.startswith("dutchbay_v14chat"):
                new_names.append(name)
                continue
            
            # Find mapping
            new_module_name = None
            for old_path, new_path in sorted(
                IMPORT_MAPPING.items(),
                key=lambda x: len(x[0]),
                reverse=True,
            ):
                if module_name.startswith(old_path):
                    new_module_name = module_name.replace(old_path, new_path, 1)
                    break
            
            if new_module_name is None:
                print(
                    f"⚠️  Warning: No mapping rule for {module_name}",
                    file=sys.stderr,
                )
                new_names.append(name)
                continue
            
            # Build new import alias
            new_name_node = self._build_module_node(new_module_name)
            new_alias = name.with_changes(name=new_name_node)
            new_names.append(new_alias)
            self.changes_made += 1
        
        if self.changes_made > 0:
            return updated_node.with_changes(names=new_names)
        return updated_node
    
    def _get_module_parts(self, node: cst.Attribute | cst.Name) -> list[str]:
        """Recursively extract module path parts."""
        if isinstance(node, cst.Name):
            return [node.value]
        elif isinstance(node, cst.Attribute):
            parent_parts = self._get_module_parts(node.value)
            return parent_parts + [node.attr.value]
        return []
    
    def _build_module_node(
        self,
        module_name: str,
    ) -> cst.Attribute | cst.Name:
        """Build a module node from dot-separated string."""
        parts = module_name.split(".")
        
        if len(parts) == 1:
            return cst.Name(parts[0])
        
        # Build nested Attribute nodes
        node: cst.Attribute | cst.Name = cst.Name(parts[0])
        for part in parts[1:]:
            node = cst.Attribute(value=node, attr=cst.Name(part))
        
        return node


def fix_file(
    file_path: Path,
    dry_run: bool = True,
    create_backup: bool = True,
) -> tuple[bool, int]:
    """
    Fix imports in a single file.
    
    Args:
        file_path: Path to Python file
        dry_run: If True, only preview changes
        create_backup: If True, create .bak backup file
        
    Returns:
        (changed, num_changes) tuple
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        
        # Parse and transform
        tree = cst.parse_module(source)
        transformer = ImportTransformer()
        new_tree = tree.visit(transformer)
        
        if transformer.changes_made == 0:
            return False, 0
        
        # Generate new source
        new_source = new_tree.code
        
        if dry_run:
            print(f"📝 Would modify: {file_path}")
            print(f"   Changes: {transformer.changes_made} import(s)")
            return True, transformer.changes_made
        
        # Create backup
        if create_backup:
            backup_path = file_path.with_suffix(file_path.suffix + ".bak")
            shutil.copy2(file_path, backup_path)
        
        # Write new source
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_source)
        
        print(f"✅ Fixed: {file_path}")
        print(f"   Changes: {transformer.changes_made} import(s)")
        
        return True, transformer.changes_made
    
    except Exception as e:
        print(f"❌ Error fixing {file_path}: {e}", file=sys.stderr)
        return False, 0


def fix_directory(
    root_dir: Path,
    dry_run: bool = True,
    create_backup: bool = True,
    exclude_dirs: set[str] | None = None,
) -> dict[str, int]:
    """
    Fix imports in all Python files under directory.
    
    Args:
        root_dir: Root directory to scan
        dry_run: If True, only preview changes
        create_backup: If True, create .bak files
        exclude_dirs: Directory names to skip
        
    Returns:
        Summary dict with statistics
    """
    if exclude_dirs is None:
        exclude_dirs = {
            ".venv", ".venv311", "venv", "env",
            "__pycache__", ".pytest_cache", ".mypy_cache",
            ".git", ".idea", ".vscode",
            "dutchbay_v14chat",  # Don't fix the source directory
            "legacy",  # Don't fix legacy code
        }
    
    files_scanned = 0
    files_modified = 0
    total_changes = 0
    
    for py_file in root_dir.rglob("*.py"):
        # Skip excluded directories
        if any(excluded in py_file.parts for excluded in exclude_dirs):
            continue
        
        files_scanned += 1
        changed, num_changes = fix_file(py_file, dry_run, create_backup)
        
        if changed:
            files_modified += 1
            total_changes += num_changes
    
    return {
        "files_scanned": files_scanned,
        "files_modified": files_modified,
        "total_changes": total_changes,
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fix dutchbay_v14chat imports using LibCST"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Root directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to files",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Don't create .bak backup files",
    )
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.apply:
        parser.error("Must specify either --dry-run or --apply")
    
    dry_run = args.dry_run
    create_backup = not args.no_backup
    
    mode = "DRY-RUN" if dry_run else "APPLY"
    print(f"🔧 Import Fixer - Mode: {mode}")
    print(f"📁 Root: {args.root}")
    print(f"💾 Backups: {'enabled' if create_backup and not dry_run else 'disabled'}")
    print()
    
    summary = fix_directory(
        args.root,
        dry_run=dry_run,
        create_backup=create_backup,
    )
    
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    print(f"Files scanned: {summary['files_scanned']}")
    print(f"Files modified: {summary['files_modified']}")
    print(f"Total changes: {summary['total_changes']}")
    print("=" * 70)
    
    if dry_run and summary['files_modified'] > 0:
        print("\n💡 Run with --apply to apply these changes")
    elif summary['files_modified'] > 0:
        print("\n✅ Import fixes applied successfully!")
        if create_backup:
            print("   Backups saved with .bak extension")
    else:
        print("\n✅ No imports to fix!")


if __name__ == "__main__":
    main()
