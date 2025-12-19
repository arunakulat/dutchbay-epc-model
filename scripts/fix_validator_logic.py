#!/usr/bin/env python3
"""Fix validator logic to allow equal absolute bounds."""

from pathlib import Path

def main():
    contracts_file = Path("analytics/contracts_v14.py")
    content = contracts_file.read_text()
    
    # Find and replace the validator line
    old_logic = "if self.high_pct <= abs(self.low_pct):"
    new_logic = "if self.high_pct < abs(self.low_pct):"  # Changed <= to <
    
    old_msg = 'f"High bound {self.high_pct} must be > absolute value of low bound {abs(self.low_pct)}"'
    new_msg = 'f"High bound {self.high_pct} must be >= absolute value of low bound {abs(self.low_pct)}"'
    
    if old_logic in content:
        content = content.replace(old_logic, new_logic)
        content = content.replace(old_msg, new_msg)
        contracts_file.write_text(content)
        print("✅ Fixed validator logic!")
        print("Changed: high > abs(low) to high >= abs(low)")
        print("Now allows symmetric ranges like -20%, +20%")
    else:
        print("❌ Validator line not found or already fixed")
    
    # Delete self
    Path(__file__).unlink()
    print("🗑️  Self-deleted")

if __name__ == "__main__":
    main()
