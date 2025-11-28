#!/usr/bin/env python3
"""Gather E501/B950 context for all 9 single-violation analytics files"""

from pathlib import Path


def gather_analytics_singles():
    # From e501_b950_violations.txt
    files_and_lines = [
        ("analytics/contracts_v14.py", [198, 700]),
        ("analytics/fx/fx_loader.py", [48]),
        ("analytics/fx/returns.py", [204]),
        ("analytics/fx/risk.py", [83]),
        ("analytics/sensitivity_pareto.py", [21]),
        ("analytics/sensitivity_v14.py", [72, 560]),
    ]

    all_output = []

    for filepath_str, violation_lines in files_and_lines:
        path = Path(filepath_str)
        if not path.exists():
            all_output.append(f"❌ {filepath_str} not found\n")
            continue

        with open(path, "r") as f:
            lines = f.readlines()

        for ln in violation_lines:
            all_output.append("=" * 80)
            all_output.append(f"{filepath_str}:{ln}")
            all_output.append("=" * 80)

            start = max(0, ln - 4)
            end = min(len(lines), ln + 3)
            for i in range(start, end):
                marker = ">>> " if i == ln - 1 else "    "
                all_output.append(f"{marker}{i+1:4d}: {lines[i].rstrip()}")

            length = len(lines[ln - 1].rstrip())
            all_output.append(f"\n    Length: {length} characters (limit: 88)")
            all_output.append(f"    Excess: {length - 88} characters\n")

    return "\n".join(all_output)


if __name__ == "__main__":
    content = gather_analytics_singles()
    with open("analytics_singles_e501_context.txt", "w") as f:
        f.write(content)
    print(content)
    print("\n✅ Saved to analytics_singles_e501_context.txt")
