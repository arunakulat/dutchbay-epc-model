Alright, let’s lock this in properly and then we can retire this thread with honours.

Below is:

1. **A complete `PRE-FLIGHT CHECKLIST.md`** you can drop straight into repo root.
2. **A refactored `check_venv.sh`** that both *checks* and *optionally runs* the R21 workflow.

---

## 1️⃣ `PRE-FLIGHT CHECKLIST.md` – full file

Copy-paste this as `PRE-FLIGHT CHECKLIST.md` in repo root (overwriting the old one).

````markdown
# DutchBay_EPC_Model – Pre-Flight Checklist

This checklist is the on-ramp for anyone touching the DutchBay_EPC_Model repo.

It encodes the **Go-with-the-Flow v3.0** ruleset (notably **R21 – Standard local workflow: bootstrap + pytest**) and makes sure your local environment, virtualenv, and tests are in a sane state *before* you do real work or push to CI.

---

## 0. Preconditions (machine-level)

You only need to do this once per machine:

- macOS with a recent Xcode Command Line Tools install:
  ```bash
  xcode-select --install
````

* Homebrew installed:

  ```bash
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  ```
* A current Homebrew Python (3.14.x or whatever we’ve standardised on):

  ```bash
  brew install python@3.14
  brew link python@3.14 --force
  ```
* Git + gh (GitHub CLI) installed and authenticated:

  ```bash
  brew install git gh
  gh auth login
  ```

Once this is stable, you don’t touch it often.

---

## 1. Repo layout sanity

From your Desktop snapshot:

```bash
cd ~/Desktop/DutchBay_EPC_Extracted/DutchBay_EPC_Model
ls
```

You should see, at minimum:

* `pyproject.toml`
* `pytest.ini`
* `.pre-commit-config.yaml`
* `ruff.toml`
* `run_full_pipeline_v14.py`
* `run_scenario_analytics_v14.py`
* `dutchbay_bootstrap.py`
* `go_with_the_flow_rules_v3_0_clean.csv`
* `scripts/venv_up.sh`
* `.venv311/` (once created)

If any of these are missing, fix that *before* going further (wrong folder, incomplete snapshot, etc).

---

## 2. Shared virtualenv `.venv311`

### 2.1 One-time creation (per clone)

From the repo root:

```bash
cd ~/Desktop/DutchBay_EPC_Extracted/DutchBay_EPC_Model

# Preferred: use the repo helper
./setup_venv.sh

# or, for a direct path:
python3 -m venv .venv311
source .venv311/bin/activate
pip install --upgrade pip
pip install -r requirements_dev.txt
```

You should now have:

* `.venv311/` in the repo root
* `python -V` inside the venv showing a supported version (currently 3.11.x in the existing env, 3.14.x for future envs once rebuilt)

### 2.2 Quick venv sanity check

Use the helper script:

```bash
./check_venv.sh
```

This will:

* Confirm `.venv311` exists
* Optionally activate it and run `dutchbay_bootstrap.py` (see script comments)
* Remind you of the **R21** workflow if not auto-running it

---

## 3. R21 – Standard local workflow (bootstrap + pytest)

This is the **canonical daily workflow** and is explicitly encoded as **Rule R21** in the Go-with-the-Flow ruleset.

Run this sequence **every time** you start a working session or before you push:

```bash
cd ~/Desktop/DutchBay_EPC_Extracted/DutchBay_EPC_Model
source .venv311/bin/activate
python dutchbay_bootstrap.py
pytest
```

What each step does:

1. `cd …DutchBay_EPC_Model`
   Ensures your CWD is the repo root. The bootstrap relies on this.

2. `source .venv311/bin/activate`
   Activates the shared project virtualenv. All tooling (pytest, ruff, mypy, CLIs) must run under this.

3. `python dutchbay_bootstrap.py`
   Runs the **Go-with-the-Flow pre-flight**:

   * Verifies repo root (pyproject, pytest.ini, ruff, pre-commit config)
   * Confirms `.venv311` exists and is discoverable
   * Checks canonical v14 entrypoints:

     * `run_full_pipeline_v14.py`
     * `run_scenario_analytics_v14.py`
   * Validates the ruleset CSV (`go_with_the_flow_rules_v3_0_clean.csv`):

     * Required columns present
     * `rule_id` uniqueness
     * Version tags (latest must be `v3.0`)
   * Calls `dutchbay_bootstrap_rules.run_ruleset_check()` to print a summary:

     * `path=…/go_with_the_flow_rules_v3_0_clean.csv`
     * `latest_version=v3.0`
     * `n_rules=44`
   * Writes `.dutchbay_bootstrap_report.json` into the repo root.

4. `pytest`
   Runs the fast test suite as configured in `pytest.ini` (v14 path, analytics, core finance, covenants, etc).

   * All failures must be understood and either fixed or explicitly parked/ignored per Go-with-the-Flow rules.

If any of these steps fail, you are **not** in a safe state to refactor, commit, or push.

---

## 4. Additional checks before refactors / commits

When you’re about to touch deeper surfaces (cashflow, debt, analytics, CLIs), layer on:

```bash
# From repo root, with .venv311 active:
ruff check .
python -m mypy analytics finance dutchbay_v14chat run_full_pipeline_v14.py
pytest
```

For “bigger” changes, also run:

```bash
python run_full_pipeline_v14.py --config full_model_variables_updated.yaml
python run_scenario_analytics_v14.py scenarios_dir=scenarios output=exports/custom.xlsx charts=false strict=true
```

The idea:

* **Ruff** keeps style and obvious bugs in check.
* **Mypy** protects the typed surfaces.
* **pytest** and the **v14 CLIs** confirm behaviour under the lender-grade scenarios.

---

## 5. Go-with-the-Flow ruleset awareness

The ruleset lives at:

* `go_with_the_flow_rules_v3_0_clean.csv` (canonical)
* Loaded and validated by:

  * `dutchbay_bootstrap.py`
  * `dutchbay_bootstrap_rules.py` via `run_ruleset_check()`

You should not hand-edit this file casually. When rules change:

1. Update the CSV in a controlled way (new rule row with `version=v3.0` or higher).
2. Re-run:

   ```bash
   source .venv311/bin/activate
   python dutchbay_bootstrap.py
   ```
3. Confirm:

   * `latest_version` is correct
   * `n_rules` matches expectations
   * No duplicate `rule_id` values

---

## 6. Common troubleshooting

### 6.1 `python` / `python3` confusion

If `python3 dutchbay_bootstrap.py` doesn’t print anything:

* Make sure you’re in the repo root:

  ```bash
  pwd
  ls dutchbay_bootstrap.py
  ```
* Prefer the venv Python explicitly:

  ```bash
  . .venv311/bin/activate
  python dutchbay_bootstrap.py
  ```

### 6.2 `.venv311` missing or corrupted

If the bootstrap complains about `.venv311`:

```bash
cd ~/Desktop/DutchBay_EPC_Extracted/DutchBay_EPC_Model
rm -rf .venv311
./setup_venv.sh   # or python3 -m venv .venv311 && source .venv311/bin/activate && pip install -r requirements_dev.txt
python dutchbay_bootstrap.py
pytest
```

### 6.3 Tests failing unexpectedly

* Confirm you are on the expected branch (`v14chat-upgrade` or whatever is current).
* Re-run:

  ```bash
  git status
  python dutchbay_bootstrap.py
  pytest -vv tests/api/test_<failing_file>.py
  ```
* Do **not** update regression pins or change scenario configs casually. Those are lender-facing surfaces and must stay aligned with the Go-with-the-Flow ruleset and v14 spec.

---

## 7. TL;DR

If you remember nothing else, remember **R21**:

```bash
cd ~/Desktop/DutchBay_EPC_Extracted/DutchBay_EPC_Model
source .venv311/bin/activate
python dutchbay_bootstrap.py
pytest
```

If that passes, you are good to Go with the Flow.

````

---

## 2️⃣ `check_venv.sh` – refactored, echo + optional run

Here’s a complete `check_venv.sh` that:

- Resolves the repo root from its own location
- Checks for `.venv311`
- **Echoes** the R21 workflow every time
- And, **optionally runs** the bootstrap under the venv if you pass `--run-bootstrap` (or set `RUN_BOOTSTRAP=1`).

Replace your existing `check_venv.sh` with this:

```bash
#!/usr/bin/env bash
#
# check_venv.sh – sanity check for the DutchBay_EPC_Model virtualenv
#
# Responsibilities:
#   - Confirm we are in a DutchBay_EPC_Model checkout.
#   - Confirm .venv311 exists (shared project venv).
#   - Optionally activate .venv311 and run dutchbay_bootstrap.py.
#   - Always print the R21 workflow for humans.
#
# Usage:
#   ./check_venv.sh
#   ./check_venv.sh --run-bootstrap
#
# You can also drive behaviour via:
#   RUN_BOOTSTRAP=1 ./check_venv.sh

set -euo pipefail

# ---------------------------------------------------------------------------
# Locate repo root (directory containing this script)
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

echo ">> check_venv.sh – repo root: ${REPO_ROOT}"

# ---------------------------------------------------------------------------
# Basic repo sanity
# ---------------------------------------------------------------------------

if [[ ! -f "pyproject.toml" ]] || [[ ! -f "pytest.ini" ]]; then
  echo "❌ This does not look like the DutchBay_EPC_Model repo root."
  echo "    Expected pyproject.toml and pytest.ini under: ${REPO_ROOT}"
  exit 1
fi

# ---------------------------------------------------------------------------
# Virtualenv presence
# ---------------------------------------------------------------------------

if [[ -d ".venv311" ]]; then
  echo "✅ Found .venv311 in repo root."
else
  echo "❌ .venv311 not found in repo root."
  echo "   Please create it first, e.g.:"
  echo "     cd ${REPO_ROOT}"
  echo "     ./setup_venv.sh"
  echo "   or:"
  echo "     python3 -m venv .venv311"
  echo "     source .venv311/bin/activate"
  echo "     pip install --upgrade pip"
  echo "     pip install -r requirements_dev.txt"
  echo ""
  echo "R21 – Standard local workflow will not run cleanly without .venv311."
  exit 1
fi

# ---------------------------------------------------------------------------
# Optional bootstrap run
# ---------------------------------------------------------------------------

RUN_BOOTSTRAP_FLAG=0

# Allow CLI flag and/or env var
if [[ "${RUN_BOOTSTRAP:-0}" == "1" ]]; then
  RUN_BOOTSTRAP_FLAG=1
fi

if [[ "${1:-}" == "--run-bootstrap" ]]; then
  RUN_BOOTSTRAP_FLAG=1
fi

if [[ "${RUN_BOOTSTRAP_FLAG}" -eq 1 ]]; then
  echo ""
  echo ">> [R21] Activating .venv311 and running dutchbay_bootstrap.py ..."
  # shellcheck disable=SC1091
  source ".venv311/bin/activate"

  python -V || true
  if [[ -f "dutchbay_bootstrap.py" ]]; then
    python dutchbay_bootstrap.py
  else
    echo "⚠️ dutchbay_bootstrap.py not found in ${REPO_ROOT} (unexpected)."
  fi
else
  echo ""
  echo ">> Skipping automatic bootstrap run (no --run-bootstrap / RUN_BOOTSTRAP=1)."
fi

# ---------------------------------------------------------------------------
# Always print the R21 workflow for humans
# ---------------------------------------------------------------------------

echo ""
echo "R21 – Standard local workflow (Go-with-the-Flow v3.0):"
echo ""
echo "  cd ${REPO_ROOT}"
echo "  source .venv311/bin/activate"
echo "  python dutchbay_bootstrap.py"
echo "  pytest"
echo ""
echo "Use this sequence before making changes or pushing to CI."

echo ""
echo "check_venv.sh completed."
````

---

If you drop these in:

* `PRE-FLIGHT CHECKLIST.md` clearly encodes R21 + context.
* `check_venv.sh` becomes a small, opinionated bouncer at the door: checks `.venv311`, optionally runs bootstrap, and always surfaces the canonical workflow.

Once you’ve saved both, we can hop to a **fresh thread** and tackle the two failing debt/covenant tests without dragging all this history along.
