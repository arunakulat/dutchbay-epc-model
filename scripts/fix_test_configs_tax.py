#!/usr/bin/env python3
"""Add missing tax fields to test configuration files."""

from pathlib import Path
import yaml

def fix_config_file(config_path: Path) -> bool:
    """Add missing tax fields to a single config file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        if not config:
            return False
        
        modified = False
        
        # Add tax section if missing
        if 'tax' not in config:
            config['tax'] = {}
            modified = True
        
        # Add corporate_tax_rate if missing
        if 'corporate_tax_rate' not in config['tax']:
            config['tax']['corporate_tax_rate'] = 0.24  # Default 24%
            modified = True
        
        # Add depreciation if missing
        if 'depreciation' not in config['tax']:
            config['tax']['depreciation'] = {}
            modified = True
        
        # Add depreciation_start_year if missing
        if 'depreciation_start_year' not in config['tax'].get('depreciation', {}):
            if 'depreciation' not in config['tax']:
                config['tax']['depreciation'] = {}
            config['tax']['depreciation']['depreciation_start_year'] = 1  # Default year 1
            modified = True
        
        # Add straight_line_years if missing
        if 'straight_line_years' not in config['tax'].get('depreciation', {}):
            config['tax']['depreciation']['straight_line_years'] = 20  # Default 20 years
            modified = True
        
        if modified:
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            return True
        
        return False
    
    except Exception as e:
        print(f"⚠️  Error processing {config_path}: {e}")
        return False

def main():
    """Find and fix all test config files."""
    tests_dir = Path("tests")
    configs_dir = Path("configs")
    
    fixed_count = 0
    
    # Find all YAML files in tests/ and configs/
    for directory in [tests_dir, configs_dir]:
        if not directory.exists():
            continue
        
        for yaml_file in directory.rglob("*.yaml"):
            if yaml_file.name.startswith('.'):
                continue
            
            if fix_config_file(yaml_file):
                print(f"✅ Fixed: {yaml_file}")
                fixed_count += 1
    
    print(f"\n📊 Fixed {fixed_count} configuration files")
    print("\nAdded fields:")
    print("  - tax.corporate_tax_rate: 0.24")
    print("  - tax.depreciation.depreciation_start_year: 1")
    print("  - tax.depreciation.straight_line_years: 20")
    print("\nNext: Run pytest to verify fixes")
    
    # Self-delete
    Path(__file__).unlink()
    print("🗑️  Self-deleted")

if __name__ == "__main__":
    main()
