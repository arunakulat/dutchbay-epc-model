# Session handover — 2026-08-17/18

Durable record per **PERSIST-01**. Written so a cold session can resume without
replaying the conversation.

**Session:** `session_016PHDbTmd333epYCbaU9vWv` · **Branch:** `claude/previous-session-review-iyjzte`
**Entry point:** "check the last claude session I was working on / continue from where you left off"

---

## 1. What shipped

Six PRs, all squash-merged to `main` except the last (open at handover).

| PR | Commit | What |
|---|---|---|
| #1038 | `7e64d33` | F5-01: bind operating FX to COD (reviewed, then merged) |
| #1040 | `32f83d2` | Re-baseline `feasibility_reproduce/` to the COD-aligned canon |
| #1041 | `2034d16` | `feasibility` extra, SessionStart hook, missing kit scripts |
| #1042 | `1db8ac0` | **Python 3.12 baseline** + grid in the lock — unblocks #923 |
| #1044 | `76f5e15` | Synthetic micro-siting geometry + real-solver QSTS→finance e2e |

**Issue #1034 (F5-01) closed** `completed`, all nine Dolphin steps ticked.

---

## 2. The canonical numbers (post-F5-01)

These are the current canon. Any run that disagrees is a regression:

```
project_irr      -0.001166233356501311   (-0.12 %)
equity_irr       -0.07853839579881527    (-7.85 %)
project_npv      -91810995.06051566      (-$91.81 M)
min_dscr          1.3                    (covenant fold AND per-period floor)
llcr              1.2809565246089147
plcr              1.3189081165240502
avg_dscr          1.3928683726550086
max_debt_usd      59590051.5             ($59.59 M)
total_cfads_usd   166083177.3168602      ($166.08 M)
equity_moic       0.4109391856659192
equity_covenant_locked_years  0          (the lockup year retired under F5-01)
```

The canon oracle asserts `pytest.approx(abs=1e-9 / rel=1e-9)` — **not** exact
equality, despite the "byte-identical" wording in the fixture note. Verified drift
under the 3.12/scipy-1.18 migration was 1–2 ULP (worst 7.07e-15 relative), i.e.
~7 orders of magnitude inside the gate, so **no re-baseline was required**.

---

## 3. Environment — read this before running anything

**Python 3.12 is now the baseline** (`requires-python = ">=3.12"`). 3.11 is no
longer supported and the CI matrix is a single 3.12 leg.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e ".[dev,feasibility]"
```

Traps that cost real time this session:

1. **Never `pip install` into the system interpreter.** Debian's patched
   setuptools raises `AttributeError: install_layout` building the lock's legacy
   sdists (`antlr4-python3-runtime`, `odfpy`) and fails the whole install. A real
   venv has clean build tooling.
2. **`pull_request_read` `get_status` reports 0 checks** for this repo — it returns
   legacy commit statuses, which aren't used. Query Actions runs instead:
   `curl .../actions/runs?branch=<branch>`.
3. **`ruff check analytics finance tests scripts` shows 112 pre-existing errors**
   because it bypasses `ruff.toml`'s excludes. CI runs `ruff check .` from the
   root, which passes clean. Use the CI invocation.
4. The container is **ephemeral** — the 2.3 GB `.venv` does not survive. That is
   what the SessionStart hook (`.claude/hooks/session-start.sh`, merged in #1041)
   exists for; it provisions lock + `[dev]` automatically on a web session, with
   `[feasibility]` behind `DUTCHBAY_INSTALL_FEASIBILITY=1`.
5. **A dev venv is NOT the CI environment.** `[dev,feasibility]` pulls
   `[micrositing]`/topfarm, which drags in transitive packages CI never gets — CI
   installs `requirements.txt` only. This bit once: `pyproj` reached the dev venv
   via topfarm, so the new geometry tests passed locally and failed on six CI
   shards. Validate anything dependency-sensitive in a venv built from the **lock
   alone** (`pip install -r requirements.txt && pip install -e .`) before pushing.

---

## 4. Why 3.12 happened (the #923 chain)

Not a preference — a forced move. Flipping `grid.qsts.finance_wiring.enabled`
makes pandapower a **runtime dependency of the canonical path**, and on 3.11 no
assignment satisfied it:

| | scipy required |
|---|---|
| `pandapower==3.3.0` (old `[grid]` pin) | `~=1.15` |
| `pandapower 3.5.4` on py3.11 | `<1.17` |
| the lock | `==1.17.1`, `scipy-stubs` needs `>=1.17.1` |

On 3.12 pandapower 3.5.x wants `scipy~=1.18`; the lock now pins `scipy==1.18.0` +
`scipy-stubs==1.18.0.1` and the set resolves. `[grid]` (pandapower/andes/
opendssdirect) is now **in the lock** and composed into `[feasibility]`.

Effect: `tests/grid/` went **576 passed / 19 skipped → 595 passed / 0 skipped**.
The andes-dynamics and OpenDSS legs had never executed in CI before.

---

## 5. Open items — nothing here is blocked, all are decisions

### 5.1 #923 flag flip (user-gated, KPI-moving)
Now **unblocked** but deliberately not flipped. Requires: a real feeder QSTS run,
a `kpi_oracle` before/after diff, explicit sign-off. Measured impact at 8 %
self-curtailment: projIRR −1.01 pp, eqIRR −1.64 pp, min_dscr −0.0092.

**Guard to understand:** the "real feeder" check is **declared-intent, not physical
reality**. `use_synthetic_demo: true` is refused, but `feeder_model_path` pointing
at *any* parseable `.dss` is treated as real and produces a live number. A toy
radial would therefore flow into the canon if the flag were on. Consider requiring
a positive provenance marker before flipping.

### 5.2 Micro-siting optimiser does not converge
SLSQP hits the committed 200-iteration cap. 600 and 1200 were tried and exceeded a
10-minute budget without settling. Cap left bounded and honest —
`"converged": false` in the artefact plus a `WARN` line (FIN-01: no silent
fallback). TODO recorded in `cache/micrositing_synthetic_site.yaml`.
Note converging would still be an optimum over *fabricated* geometry.

### 5.3 The real site geometry is still missing
`cache/micrositing_synthetic_site.yaml` **derives** a boundary and baseline from
committed parameters because the real polygon and layout were never committed.
Replace it when the real geometry exists. The committed
`cache/expected/layout_optimized.json` (550.987 → 555.433 GWh) came from geometry
that is not in the repo and cannot currently be reproduced.

### 5.4 Version signalling
`15.3.1` was a **patch** bump for a change the changelog calls a material
correction (headline projIRR +1.46 % → −0.12 %). Raised three times, never
changed — it is a judgement call for the owner. `15.4.0` would signal it better.

### 5.5 Kit still not fully one-shot
`run_all.sh` is closer but `feasibility_reproduce/lib/` was never fully
reconstructed. `mc_run.py`, `wind_provenance.py`, `run_global_sa.py`,
`build_study_pdf.py`, `build_md_pdf.py` and `synthetic_site.py` now exist. The
GIS/ERA5 steps still rely on shipped cache.

---

## 6. Defects found and fixed (all pre-existing)

1. **`.gitignore` swallowed the kit's own scripts.** The stock `lib/` rule was
   unanchored, matching at any depth, so `feasibility_reproduce/lib/` was never
   committed — `run_all.sh` shipped calling files that did not exist. Now `/lib/`.
2. **`capex_contingency` silently no-opped.** It requires
   `base_capex_usd=157206000`; `run_all.sh` swallowed the resulting `ValueError`
   via `>/dev/null 2>&1 &&`, so a broken step reported as success.
3. **`turbine_spacing_avg_D: 3.8` was wrong in all 10 scenarios** — the comment
   carried a stale 171 m rotor; the committed machine is 198 m (→ 3.28 D),
   Mullikulam 150 m (→ 4.33 D). Doc-only (no code reads it), but a layout sized
   from it would be ~16 % too sparse.
4. **The feasibility study reported the superseded canon** at full precision,
   making a value-destructive project look ~1.6 pp better on equity IRR and
   ~$12.5 M better on NPV. Fixed in #1040.

---

## 7. Governance in force

GWTF v3.0, 66 active rules, validated via:

```bash
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  .venv/bin/python dutchbay_bootstrap_rules.py
```

Binding for this work: **DELIVERY-01** (dolphins, not whales — decompose into
small-but-complete increments), **GOV-02/R23/R25** (never commit to `main`;
verify `git branch --show-current` before *every* commit), **CESSPIT** (config
explicit, no hidden constants), **CASPER** (optional deps fail at call-time with
actionable messages), **FIN-01** (no silent fallback on non-convergence),
**FIN-02** (units in field names), **MRM-01/02** (deterministic seeds; artefacts
carry provenance), **PERSIST-01** (checkpoint early — this file).

---

## 8. Immediate next step

PR **#1044** was open with CI running at handover. Verify it went green, merge it,
then `git remote prune origin` and delete the local branch. After that the tree is
clean and the next piece of work is whichever of §5 the owner chooses.
