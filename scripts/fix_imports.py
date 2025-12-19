#!/usr/bin/env python3
"""Quick fix for missing Pydantic imports."""

from pathlib import Path

def main():
    contracts_file = Path("analytics/contracts_v14.py")
    content = contracts_file.read_text()
    
    # Replace the import line
    old_import = "from pydantic import BaseModel, ConfigDict"
    new_import = "from pydantic import BaseModel, ConfigDict, field_validator, model_validator"
    
    if old_import in content:
        content = content.replace(old_import, new_import)
        contracts_file.write_text(content)
        print("✅ Fixed imports!")
        print(f"Added: field_validator, model_validator")
    else:
        print("❌ Import line not found or already fixed")
    
    # Delete self
    Path(__file__).unlink()
    print("🗑️  Self-deleted")

if __name__ == "__main__":
    main()
