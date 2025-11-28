#!/usr/bin/env python3
"""Revert _tr back to tr - the B007 was a false positive"""

from pathlib import Path

filepath = Path("finance/debt_v14.py")

with open(filepath, "r") as f:
    content = f.read()

# Replace all _tr back to tr in the function
content = content.replace(
    "for k, _tr in tranches.items():", "for k, tr in tranches.items():"
)
content = content.replace("interest = bal * _tr.rate", "interest = bal * tr.rate")
content = content.replace("_tr.schedule", "tr.schedule")
content = content.replace("_annuity_schedule(_tr,", "_annuity_schedule(tr,")

with open(filepath, "w") as f:
    f.write(content)

print("✅ Reverted _tr → tr (B007 was false positive)")
