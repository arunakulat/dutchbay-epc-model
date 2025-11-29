#!/usr/bin/env python3
"""Fix the syntax error in finance/__init__.py line 51."""

from pathlib import Path

file_path = Path("finance/__init__.py")
lines = file_path.read_text().splitlines()

# The issue is at line 51 (index 50)
# Check if previous line (50, index 49) ends with ':'
if len(lines) > 50:
    prev_line = lines[49] if len(lines) > 49 else ""
    curr_line = lines[50]

    # If previous line is 'if' statement and current line isn't indented
    if prev_line.strip().endswith(":") and not curr_line.startswith("    "):
        # Add 4 spaces if it's an import statement
        if curr_line.strip().startswith("from ") or curr_line.strip().startswith(
            "import "
        ):
            lines[50] = "    " + curr_line.lstrip()
            print(f"✅ Fixed indentation at line 51")
        else:
            # Add a pass statement
            lines.insert(50, "    pass")
            print(f"✅ Added 'pass' statement at line 51")

    file_path.write_text("\n".join(lines) + "\n")
else:
    print("⚠️  File too short, check manually")
