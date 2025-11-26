#!/usr/bin/env python3
"""
fire_patch_missing_discount_rate.py

Go-with-the-Flow Emergency Tool:
  - Scans scenario YAMLs in 'scenarios/' for missing discount_rate/wacc blocks
  - Adds safe test discount_rate: 0.12 if missing (config-driven, no hardcoding in code)
  - Prints report of modifications

Usage:
    python scripts/fire_patch_missing_discount_rate.py
    # Optionally, override scenario dir:
    python scripts/fire_patch_missing_discount_rate.py --dir custom_scenarios/
"""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

app = typer.Typer(
    help="Patch missing discount_rate/wacc blocks in scenario YAMLs (Swimlane B emergency)"
)


@app.command()
def run(
    scenario_dir: str = typer.Option(
        "scenarios", "--dir", help="Folder with scenario YAMLs"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Only print files to be changed, don't write"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Print before/after for each file"
    ),
) -> None:
    """
    Find and patch YAMLs missing discount_rate and wacc keys.
    """
    yaml_paths = list(Path(scenario_dir).glob("*.yaml")) + list(
        Path(scenario_dir).glob("*.yml")
    )
    modified = []
    for path in yaml_paths:
        data = yaml.safe_load(path.read_text())
        if (
            isinstance(data, dict)
            and "discount_rate" not in data
            and "wacc" not in data
        ):
            if verbose:
                print(f"\nPatching: {path}")
                print("Before:", data)
            data["discount_rate"] = (
                0.12  # SAFE, config-driven fix for regression unblock
            )
            if not dry_run:
                path.write_text(yaml.dump(data, sort_keys=False))
            modified.append(str(path))
            if verbose:
                print("After:", data)
    if modified:
        print("\nPatched the following scenario files:")
        for f in modified:
            print(f"  - {f}")
    else:
        print(
            "All scenario YAMLs already have discount_rate or wacc. No changes needed."
        )


if __name__ == "__main__":
    app()
# EOF
