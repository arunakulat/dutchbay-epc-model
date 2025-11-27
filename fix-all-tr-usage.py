#!/usr/bin/env python3
"""Find and fix ALL 'tr.' references in debt_v14.py after renaming to _tr"""

from pathlib import Path

filepath = Path('finance/debt_v14.py')

with open(filepath, 'r') as f:
    lines = f.readlines()

# Find the loop that starts with "for k, _tr in tranches.items():"
# and update ALL tr. references to _tr. until the next loop or unindented line

fixed = 0
in_tr_loop = False
loop_indent = 0

for i, line in enumerate(lines):
    # Detect start of _tr loop
    if 'for k, _tr in tranches.items():' in line:
        in_tr_loop = True
        loop_indent = len(line) - len(line.lstrip())
        print(f"Line {i+1}: Found _tr loop")
        continue
    
    if in_tr_loop:
        # Check if we've exited the loop (unindented or same indent as for)
        current_indent = len(line) - len(line.lstrip())
        if line.strip() and current_indent <= loop_indent:
            in_tr_loop = False
            print(f"Line {i+1}: Exited _tr loop")
        else:
            # Replace tr. with _tr. in this line
            if 'tr.' in line and '_tr.' not in line:
                old_line = line
                lines[i] = line.replace('tr.', '_tr.')
                print(f"Line {i+1}: Replaced tr. → _tr.")
                fixed += 1

with open(filepath, 'w') as f:
    f.writelines(lines)

print(f"\n✅ Fixed {fixed} tr. references")
