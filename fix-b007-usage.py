#!/usr/bin/env python3
"""Fix B007 where we renamed vars but loop body still uses old names"""

from pathlib import Path

# Fix: finance/debt_v14.py - change 'tr' usage to '_tr' in loop body
filepath = Path('finance/debt_v14.py')

with open(filepath, 'r') as f:
    content = f.read()

# Around line 185-206, replace tr.rate with _tr.rate, tr.schedule with _tr.schedule
old_block = """    for k, tr in tranches.items():
        bal = obals[k]
        prorata = bal / total_bal if total_bal > 0 else 0.0
        principal_k = min(bal, principal_total * prorata)
        interest = bal * tr.rate"""

new_block = """    for k, _tr in tranches.items():
        bal = obals[k]
        prorata = bal / total_bal if total_bal > 0 else 0.0
        principal_k = min(bal, principal_total * prorata)
        interest = bal * _tr.rate"""

if old_block in content:
    content = content.replace(old_block, new_block)
    print("✓ Fixed tr → _tr usage in debt_v14.py loop body")
else:
    # Try more targeted fix
    content = content.replace('interest = bal * tr.rate', 'interest = bal * _tr.rate')
    content = content.replace('tr.schedule', '_tr.schedule')
    print("✓ Fixed tr → _tr references in debt_v14.py")

with open(filepath, 'w') as f:
    f.write(content)

print("Done!")
