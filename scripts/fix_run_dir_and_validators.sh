# scripts/fix_run_dir_and_validators.sh
#!/usr/bin/env bash
set -euo pipefail

F="dutchbay_v13/scenario_runner.py"

python - <<'PY'
from pathlib import Path
import re

p = Path("dutchbay_v13/scenario_runner.py")
s = p.read_text(encoding="utf-8")

def ensure_validator_signature(src: str, name: str) -> str:
    # def _validate_params_dict(d: Dict[str, Any], where="scenario"):
    pat = rf"(def\s+{name}\s*\(\s*([^\)]*?)\))"
    m = re.search(pat, src)
    if not m:
        return src
    sig = m.group(2)
    if "where" in sig:
        return src
    # insert where=None at end (before closing paren), keep existing args
    new_sig = sig.strip()
    if new_sig.endswith(","):
        new_sig = new_sig + " where=None"
    elif new_sig == "":
        new_sig = "where=None"
    else:
        new_sig = new_sig + ", where=None"
    return src.replace(m.group(1), f"def {name}({new_sig})")

# 1) Make sure validators accept "where"
s = ensure_validator_signature(s, "_validate_params_dict")
s = ensure_validator_signature(s, "_validate_debt_dict")

# 2) Ensure a helper exists to enumerate override YAMLs (and print them)
if "def _list_override_files(" not in s:
    helper = """
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
        # Skip base/matrix configs; keep only override snippets
        if "matrix" in n or "full_model_variables" in n or "base" in n:
            continue
        ymls.append(f)
    print(f"[scenarios] overrides detected: {len(ymls)}")
    for f in ymls:
        print(f"  - {f}")
    return ymls
"""
    # place just before run_dir (or at end if not found)
    idx = s.find("def run_dir(")
    if idx == -1:
        s = s.rstrip() + "\n\n" + helper.lstrip() + "\n"
    else:
        s = s[:idx] + helper + "\n" + s[idx:]

# 3) Replace run_dir with a clean, indented implementation
run_dir_re = re.compile(
    r"def\s+run_dir\s*\(\s*scenarios_dir\s*,\s*outdir\s*,.*?\):.*?(?=^\s*def\s|\Z)",
    flags=re.DOTALL | re.MULTILINE,
)

new_run_dir = r"""
def run_dir(scenarios_dir, outdir, mode="irr", format="both", save_annual=False):
    import json, csv, time
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
            # validate only the overrides (not the base config)
            _validate_params_dict({k: v for k, v in overrides.items() if k != "debt"}, where=name)
            _validate_debt_dict(overrides.get("debt", {}), where=name)

            r = run_scenario(overrides, name=name, mode=mode)
            if r:
                results.append(r)
                if save_annual and "annual" in r:
                    af = out / f"scenario_{name}_annual_{int(time.time())}.csv"
                    with af.open("w", newline="", encoding="utf-8") as g:
                        w = csv.writer(g)
                        w.writerow(["year", "cashflow"])
                        for i, c in enumerate(r["annual"], 1):
                            w.writerow([i, c])
        except Exception as e:
            print(f"[warn] scenario '{name}' failed: {e}")

    if not results:
        print("[warn] No successful scenarios; skipping result file writes.")
        return []

    ts = int(time.time())
    if format in ("both", "jsonl"):
        jf = out / f"scenario_000_results_{ts}.jsonl"
        with jf.open("w", encoding="utf-8") as g:
            for row in results:
                g.write(json.dumps({k: v for k, v in row.items() if k != "annual"}) + "\n")

    if format in ("both", "csv"):
        cf = out / f"scenario_000_results_{ts}.csv"
        keys = sorted({k for r in results for k in r.keys() if k != "annual"})
        with cf.open("w", newline="", encoding="utf-8") as g:
            w = csv.writer(g)
            w.writerow(keys)
            for r in results:
                w.writerow([r.get(k, "") for k in keys])

    return results
""".lstrip("\n")

if run_dir_re.search(s):
    s = run_dir_re.sub(new_run_dir, s)
else:
    # append if not found
    s = s.rstrip() + "\n\n" + new_run_dir + "\n"

p.write_text(s, encoding="utf-8")
print("✓ scenario_runner.py fixed: validator signatures + run_dir replacement")
PY

echo "Done."

