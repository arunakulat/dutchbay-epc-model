#!/usr/bin/env python3
"""
Root Directory Cleanup Script
Moves obsolete files to legacy/ and reorganizes FX data files.

Generated: 2025-11-29
Purpose: Clean up root directory post v14 migration
"""

import os
import shutil
from pathlib import Path
from typing import List


def create_directories(dirs: List[str]) -> None:
    """Create directory structure if it doesn't exist."""
    for directory in dirs:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created: {directory}")


def move_file(src: str, dest: str) -> bool:
    """Move file from src to dest, handling errors gracefully."""
    try:
        if os.path.exists(src):
            shutil.move(src, dest)
            print(f"   📦 Moved: {src} → {dest}")
            return True
        else:
            print(f"   ⚠️  Not found: {src}")
            return False
    except Exception as e:
        print(f"   ❌ Error moving {src}: {e}")
        return False


def main():
    """Execute the cleanup."""
    print("=" * 70)
    print("🧹 ROOT DIRECTORY CLEANUP - DutchBay EPC Model")
    print("=" * 70)
    print()

    # Track statistics
    moved_count = 0
    total_count = 0

    # ========================================================================
    # Phase 1: Create directory structure
    # ========================================================================
    print("📁 PHASE 1: Creating directory structure...")
    print("-" * 70)

    directories = [
        "legacy/ci_variants",
        "legacy/v14_migration",
        "legacy/temp_debug",
        "legacy/old_configs",
        "legacy/data_files",
        "inputs/fxdata",
    ]

    create_directories(directories)
    print()

    # ========================================================================
    # Phase 2: Move FX data files to inputs/fxdata
    # ========================================================================
    print("📊 PHASE 2: Moving FX data files to inputs/fxdata...")
    print("-" * 70)

    fx_files = [
        "fx_data_historical_Decade4_2005_2014.yaml",
        "fx_data_historical_Decade5_2015_2025.yaml",
        "fx_data_recent_Period1_2016_2017.yaml",
        "fx_data_recent_Period2_2018_2019.yaml",
        "fx_data_recent_Period3_2020_2021.yaml",
        "fx_data_recent_Period4_2022_2023.yaml",
        "fx_data_recent_Period5_2024_2025.yaml",
    ]

    for fx_file in fx_files:
        total_count += 1
        if move_file(fx_file, f"inputs/fxdata/{fx_file}"):
            moved_count += 1

    print()

    # ========================================================================
    # Phase 3: Move fx_correlation_module.py to scripts/
    # ========================================================================
    print("🐍 PHASE 3: Moving FX correlation module to scripts/...")
    print("-" * 70)

    # Handle the file with trailing space in name
    fx_module_files = [
        "fx_correlation_module.py",
        "fx_correlation_module.py ",  # with trailing space
    ]

    for fx_module in fx_module_files:
        if os.path.exists(fx_module):
            total_count += 1
            dest_name = "fx_correlation_module.py"  # normalize name
            if move_file(fx_module, f"scripts/{dest_name}"):
                moved_count += 1
            break  # Only move one (whichever exists)

    print()

    # ========================================================================
    # Phase 4: Move obsolete CI/workflow variants to legacy
    # ========================================================================
    print("🔄 PHASE 4: Moving obsolete CI variants to legacy...")
    print("-" * 70)

    ci_files = [
        "go_with_the_flow_ci_enhanced.py",
        "go_with_the_flow_ci_v2_final.py",
        "ci.yml",
        "test.ci.yml",
    ]

    for ci_file in ci_files:
        total_count += 1
        if move_file(ci_file, f"legacy/ci_variants/{ci_file}"):
            moved_count += 1

    print()

    # ========================================================================
    # Phase 5: Move v13 old pipeline to legacy
    # ========================================================================
    print("📜 PHASE 5: Moving v13 pipeline to legacy...")
    print("-" * 70)

    total_count += 1
    if move_file("run_full_pipeline.py", "legacy/run_full_pipeline.py"):
        moved_count += 1

    print()

    # ========================================================================
    # Phase 6: Move temporary debug files to legacy
    # ========================================================================
    print("🐛 PHASE 6: Moving temporary debug files to legacy...")
    print("-" * 70)

    debug_files = [
        "tmp_debug_metrics_fail.py",
        "tmp_print_sensitivity_scenarios.py",
    ]

    for debug_file in debug_files:
        total_count += 1
        if move_file(debug_file, f"legacy/temp_debug/{debug_file}"):
            moved_count += 1

    print()

    # ========================================================================
    # Phase 7: Move v14 migration scripts (one-time use) to legacy
    # ========================================================================
    print("🔧 PHASE 7: Moving v14 migration scripts to legacy...")
    print("-" * 70)

    migration_files = [
        "fix_v14chat_imports.py",
        "scan_v14chat_imports.py",
        "quarantine_v14chat.py",
        "task1_legacy_quarantine.sh",
        "v14_setup_diagnostic.sh",
        "refactor_kpi_args.py",
        "fix_parameter_range_config.py",
    ]

    for migration_file in migration_files:
        total_count += 1
        if move_file(migration_file, f"legacy/v14_migration/{migration_file}"):
            moved_count += 1

    print()

    # ========================================================================
    # Phase 8: Move old config files to legacy
    # ========================================================================
    print("⚙️  PHASE 8: Moving old config files to legacy...")
    print("-" * 70)

    config_files = [
        "full_model_variables_updated.yaml",
        "wacc_config_example.yaml",
    ]

    for config_file in config_files:
        total_count += 1
        if move_file(config_file, f"legacy/old_configs/{config_file}"):
            moved_count += 1

    print()

    # ========================================================================
    # Phase 9: Move miscellaneous data files to legacy
    # ========================================================================
    print("📄 PHASE 9: Moving miscellaneous data files to legacy...")
    print("-" * 70)

    data_files = [
        "data.csv",
        "output_summary.csv",
        "scenario_timeseries.csv",
        "scenario_wide.csv",
        "sprint_tracker_v2.csv",
    ]

    for data_file in data_files:
        total_count += 1
        if move_file(data_file, f"legacy/data_files/{data_file}"):
            moved_count += 1

    print()

    # ========================================================================
    # Final Summary
    # ========================================================================
    print("=" * 70)
    print("✨ CLEANUP COMPLETE!")
    print("=" * 70)
    print()
    print("📊 Summary:")
    print(f"   Total files processed: {total_count}")
    print(f"   Successfully moved: {moved_count}")
    print(f"   Not found/skipped: {total_count - moved_count}")
    print()
    print("📁 Files organized into:")
    print("   • inputs/fxdata/ - FX historical data (7 files)")
    print("   • scripts/ - FX correlation module (1 file)")
    print("   • legacy/ci_variants/ - Obsolete CI versions (4 files)")
    print("   • legacy/v14_migration/ - One-time migration scripts (7 files)")
    print("   • legacy/temp_debug/ - Temporary debug files (2 files)")
    print("   • legacy/old_configs/ - Old configuration files (2 files)")
    print("   • legacy/data_files/ - Miscellaneous data files (5 files)")
    print("   • legacy/ - Old v13 pipeline (1 file)")
    print()
    print("🎯 Next steps:")
    print("   1. Review the moved files in legacy/")
    print("   2. Verify inputs/fxdata/ contains expected FX data")
    print("   3. Check scripts/fx_correlation_module.py")
    print("   4. Run tests to ensure nothing broke")
    print("   5. Commit changes with descriptive message")
    print()
    print("✅ Root directory is now clean and organized!")
    print("=" * 70)


if __name__ == "__main__":
    main()
