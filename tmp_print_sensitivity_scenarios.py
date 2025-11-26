import re
base_path = "tests/analytics_layer/test_sensitivity_v14_all.py"
paths = set()
with open(base_path) as f:
    for line in f:
        m = re.search(r'ScenarioRequest\s*\(\s*[\'"](.+?\.ya?ml)[\'"]', line)
        if m:
            print(m.group(1))
            paths.add(m.group(1))
print("Unique scenario paths found:")
for p in sorted(paths):
    print("  ", p)
