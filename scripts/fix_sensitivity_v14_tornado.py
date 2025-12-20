#!/usr/bin/env python3
"""Fix TornadoResult instantiation in sensitivity_v14.py."""

from pathlib import Path
import re

def main():
    sensitivity_file = Path("analytics/sensitivity_v14.py")
    content = sensitivity_file.read_text()
    
    # Count occurrences
    occurrences = content.count('TornadoResult.model_validate')
    print(f"Found {occurrences} occurrences of TornadoResult.model_validate")
    
    if occurrences == 0:
        print("✅ Already fixed or nothing to fix")
        return
    
    # Replace TornadoResult.model_validate with direct instantiation
    # Pattern: TornadoResult.model_validate({...})
    # Replace with: TornadoResult(**{...})
    content = content.replace(
        'TornadoResult.model_validate(',
        'TornadoResult('
    )
    
    # Similarly for BreakevenResult
    content = content.replace(
        'BreakevenResult.model_validate(',
        'BreakevenResult('
    )
    
    sensitivity_file.write_text(content)
    print(f"✅ Fixed {occurrences} TornadoResult instantiations")
    print("   Changed: TornadoResult.model_validate({...})")
    print("   To:      TornadoResult({...})")
    
    # Self-delete
    Path(__file__).unlink()
    print("🗑️  Self-deleted")

if __name__ == "__main__":
    main()
