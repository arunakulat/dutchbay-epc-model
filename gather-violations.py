#!/usr/bin/env python3
"""Gather violation files for inspection"""

from pathlib import Path

def gather():
    files = {
        'analytics/fx/returns.py': 163,
        'analytics/sensitivity_visualization.py': [40, 81],
        'finance/debt_v14.py': 198,
        'tests/test_export_smoke.py': [58, 59],
        'tests/test_scenario_analytics_smoke.py': [57, 58],
        'analytics/fx/risk.py': 83,
        'analytics/sensitivity_pareto.py': 21,
    }
    
    output = ["=" * 80, "VIOLATION CONTEXT", "=" * 80, ""]
    
    for filepath, line_nums in files.items():
        if not Path(filepath).exists():
            output.append(f"NOT FOUND: {filepath}")
            continue
        
        if isinstance(line_nums, int):
            line_nums = [line_nums]
        
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        for line_num in line_nums:
            output.append("")
            output.append("=" * 80)
            output.append(f"FILE: {filepath} | LINE: {line_num}")
            output.append("=" * 80)
            
            start = max(0, line_num - 4)
            end = min(len(lines), line_num + 3)
            
            for i in range(start, end):
                marker = ">>> " if i == line_num - 1 else "    "
                output.append(f"{marker}{i+1:4d}: {lines[i].rstrip()}")
    
    return "\n".join(output)

if __name__ == '__main__':
    content = gather()
    with open('violations_context.txt', 'w') as f:
        f.write(content)
    print(content)
    print("\n✅ Saved to violations_context.txt")
