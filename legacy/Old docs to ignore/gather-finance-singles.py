#!/usr/bin/env python3
"""Gather E501/B950 context for all 4 finance single-violation files"""

from pathlib import Path


def gather_finance_singles():
    files_and_lines = [
        ("finance/debt_v14.py", [225]),
        ("finance/equity_v14.py", [39]),
        ("finance/irr.py", [291]),
        ("finance/wacc_v14.py", [443]),
    ]

    all_output = []

    for filepath_str, violation_lines in files_and_lines:
        path = Path(filepath_str)
        if not path.exists():
            all_output.append(f"❌ {filepath_str} not found\n")
            continue

        with open(path, "r") as f:
            lines = f.readlines()

        all_output.append("=" * 80)
        all_output.append(f"{filepath_str} - E501/B950 violation")
        all_output.append("=" * 80)
        all_output.append(f"\nLine: {violation_lines[0]}\n")

        ln = violation_lines[0]
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
    content = gather_finance_singles()
    with open("finance_singles_e501_context.txt", "w") as f:
        f.write(content)
    print(content)
    print("\n✅ Saved to finance_singles_e501_context.txt")
