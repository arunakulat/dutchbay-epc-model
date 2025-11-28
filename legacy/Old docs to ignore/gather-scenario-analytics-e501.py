#!/usr/bin/env python3
"""Gather E501/B950 context from analytics/scenario_analytics.py"""

from pathlib import Path


def gather() -> str:
    path = Path("analytics/scenario_analytics.py")
    if not path.exists():
        return "❌ analytics/scenario_analytics.py not found"

    with open(path, "r") as f:
        lines = f.readlines()

    # From e501_b950_violations.txt
    violation_lines = [67, 90, 120, 230, 368]

    out: list[str] = []
    out.append("=" * 80)
    out.append("analytics/scenario_analytics.py - E501/B950 violations")
    out.append("=" * 80)
    out.append(f"\nTotal violation sites (line numbers): {len(violation_lines)}\n")

    for ln in violation_lines:
        out.append("\n" + "=" * 80)
        out.append(f"LINE {ln}")
        out.append("=" * 80)
        start = max(0, ln - 4)
        end = min(len(lines), ln + 3)
        for i in range(start, end):
            marker = ">>> " if i == ln - 1 else "    "
            out.append(f"{marker}{i+1:4d}: {lines[i].rstrip()}")
        length = len(lines[ln - 1].rstrip())
        out.append(f"\n    Length: {length} characters (limit: 88)")
        out.append(f"    Excess: {length - 88} characters")
    return "\n".join(out)


if __name__ == "__main__":
    content = gather()
    with open("scenario_analytics_e501_context.txt", "w") as f:
        f.write(content)
    print(content)
    print("\n✅ Saved to scenario_analytics_e501_context.txt")
