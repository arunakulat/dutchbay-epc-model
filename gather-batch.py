#!/usr/bin/env python3
from pathlib import Path
def gather():
    path = Path("analytics/sensitivity/batch.py")
    if not path.exists(): return "❌ not found"
    with open(path, "r") as f: lines = f.readlines()
    violation_lines = [6, 13, 42]
    out = ["=" * 80, "analytics/sensitivity/batch.py - E501/B950 violations", "=" * 80, f"\nTotal violation sites: {len(violation_lines)}\n"]
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
    with open("batch_e501_context.txt", "w") as f: f.write(content)
    print(content)
    print("\n✅ Saved to batch_e501_context.txt")
