#!/usr/bin/env python3
"""Fix the final Sequence -> list error."""

from pathlib import Path


def fix_sequence_to_list() -> None:
    """Fix analytics/evaluate_scenario.py:147 Sequence -> list."""
    file_path = Path("analytics/evaluate_scenario.py")
    content = file_path.read_text()

    # Strategy 1: Replace in parameter declarations
    content = content.replace(
        "debt_tranches: Sequence[dict[str, Any]]", "debt_tranches: list[dict[str, Any]]"
    )

    # Strategy 2: Also check for any variant spellings
    content = content.replace("Sequence[dict[str, Any]]", "list[dict[str, Any]]")

    # Save
    file_path.write_text(content)
    print("✅ Fixed Sequence -> list in evaluate_scenario.py")


if __name__ == "__main__":
    fix_sequence_to_list()

    print("\nVerify:")
    print("  python -m mypy analytics/evaluate_scenario.py")
# EOF
