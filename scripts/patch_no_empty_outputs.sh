# scripts/patch_no_empty_outputs.sh
#!/usr/bin/env bash
set -euo pipefail

F="dutchbay_v13/scenario_runner.py"

# 1) Ensure helper that collects override files prints what it found
python - <<'PY'
from pathlib import Path
p = Path("dutchbay_v13/scenario_runner.py")
s = p.read_text(encoding="utf-8")

if "def _list_override_files(" not in s:
    # Insert a helper before run_dir if it doesn't exist yet
    ins = """
def _list_override_files(scenarios_dir):
    from pathlib import Path
    ymls = []
    d = Path(scenarios_dir)
    if not d.exists():
        return []
    for f in d.iterdir():
        if not f.is_file():
            continue
        n = f.name.lower()
        if not (n.endswith(".yml") or n.endswith(".yaml")):
            continue
        # Skip base/matrix/config files; keep only pure overrides
        if "matrix" in n or "full_model_variables" in n or "base" in n:
            continue
        ymls.append(f)
    print(f"[scenarios] overrides detected: {len(ymls)}")
    for f in ymls:
        print(f"  - {f}")
    return ymls
"""
    # place it just above run_dir
    if "def run_dir(" in s:
        s = s.replace("def run_dir(", ins + "\n\ndef run_dir(")
    else:
        s += "\n" + ins

# 2) Modify run_dir to use _list_override_files, and guard empty results
import re
s = re.sub(
    r"def run_dir\((.*?)\):",
    r"def run_dir(\1):",
    s,
    flags=re.DOTALL,
)
if "results = []" not in s:
    # do nothing, avoid breaking an already-patched file
    pass

# Replace the body of run_dir with a safe, minimal variant
s = re.sub(
    r"def run_dir\((.*?)\):.*?^\s*return results\s*$",
    r"""def run_dir(\1):
    import json, csv
    from pathlib import Path
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    files = _list_override_files(scenarios_dir)
    if not files:
        print("[warn] No scenario override YAMLs found; nothing to do.")
        return []

    results = []
    for f in files:
        name = f.stem
        try:
            import yaml
            overrides = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            # validate ONLY overrides (not the entire base config)
            _validate_params_dict({k: v for k, v in overrides.items() if k != "debt"}, where=name)
            _validate_debt_dict(overrides.get("debt", {}), where=name)
            r = run_scenario(overrides, name=name, mode=mode)
            if r:
                results.append(r)
                if save_annual:
                    af = out / f"scenario_000_annual_{int(__import__('time').time())}.csv"
                    with af.open("w", newline="", encoding="utf-8") as g:
                        w = csv.writer(g)
                        w.writerow(["year","cashflow"])
                        for i, c in enumerate(r.get("annual", []), 1):
                            w.writerow([i, c])
        except Exception as e:
            print(f"[warn] scenario '{name}' failed: {e}")

    if not results:
        print("[warn] No successful scenarios; skipping result file writes.")
        return []

    ts = int(__import__('time').time())
    if format in ("both", "jsonl"):
        jf = out / f"scenario_000_results_{ts}.jsonl"
        with jf.open("w", encoding="utf-8") as g:
            for row in results:
                g.write(json.dumps({k: v for k, v in row.items() if k != "annual"}) + "\\n")
    if format in ("both", "csv"):
        cf = out / f"scenario_000_results_{ts}.csv"
        # flatten keys (excluding 'annual')
        keys = sorted({k for r in results for k in r.keys() if k != "annual"})
        with cf.open("w", newline="", encoding="utf-8") as g:
            w = csv.writer(g)
            w.writerow(keys)
            for r in results:
                w.writerow([r.get(k, "") for k in keys])
    return results
""",
    s,
    flags=re.DOTALL | re.MULTILINE,
)

p.write_text(s, encoding="utf-8")
print("✓ scenario_runner.py patched to skip empty outputs and list overrides")
PY

echo "Done."