import yaml
import sys
# Path to scenario YAML actually used by failing test
yaml_path = "scenarios/dutchbay_lendercase_2025Q4.yaml"
with open(yaml_path) as f:
    config = yaml.safe_load(f)
print("Loaded YAML type:", type(config))
print("Loaded YAML content:", repr(config)[:500])  # First 500 chars for brevity
