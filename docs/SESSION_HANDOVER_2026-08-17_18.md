# Session handover — 2026-08-17/18

Durable record per **PERSIST-01**. Written so a cold session can resume without
replaying the conversation.

**Session:** `session_016PHDbTmd333epYCbaU9vWv` · **Branch:** `claude/previous-session-review-iyjzte`
**Entry point:** "check the last claude session I was working on / continue from where you left off"

---

## 1. What shipped

Seven PRs, squash-merged to `main` in order. **Released as v15.4.0** at #1045;
#1046 carries this handover and the automatic-provisioning fix.

| PR | Commit | What |
|---|---|---|
| #1038 | `7e64d33` | F5-01: bind operating FX to COD (reviewed, then merged) |
| #1040 | `32f83d2` | Re-baseline `feasibility_reproduce/` to the COD-aligned canon |
| #1041 | `2034d16` | `feasibility` extra, SessionStart hook, missing kit scripts |
| #1042 | `1db8ac0` | **Python 3.12 baseline** + grid in the lock — unblocks #923 |
| #1044 | `f0d8eed` | Synthetic micro-siting geometry + real-solver QSTS→finance e2e |
| #1045 | `0379843` | **v15.4.0 release** — changelog cut, `[micrositing]` in the lock, dead test revived |
| #1046 | `cc7ab52` | Web sessions provision fully and automatically (`env` block + full hook fallback) |

**Issue #1034 (F5-01) closed** `completed`, all nine Dolphin steps ticked.

**Test-suite trajectory across the session:** 5138 passed / 31 skipped →
**5184 passed / 13 skipped**. The 18 closed skips were tests that had never
executed in CI: 9 `optimize_layout()` cases (no TopFarm in the lock), the andes
and OpenDSS grid legs, and `test_evaluation_v14_lender_stack.py`'s PRIMARY
regression pin, whose fixture had never been committed.

### The release tag — CLOSED OUT 2026-08-18 (see §9)

`RELEASING.md` §6 wants `git tag -s v15.4.0` on the merged release commit, which
triggers `release-run.yml` to publish the GitHub Release. At the time this section
was written it was **not done** and needed the owner's signing key.

**It is done now.** The owner pushed the tag on 2026-08-18 and the GitHub Release
is published. One deviation to know about: the tag is *annotated* (`-a`), not
*signed* (`-s`). Full detail — including why v15.4.0 cannot be re-tagged in
place — is in **§9**.

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

**Fully-enabled sessions are now AUTOMATIC.** `.claude/settings.json` carries an
`env` block setting `DUTCHBAY_EXTRAS=dev,feasibility,jobs,solar,pareto`, and the
hook's own fallback is the same full set — so a web session provisions grid,
micro-siting, redis, solar and pareto with no flag to remember, and starts
`redis-server` on :6379. Set `DUTCHBAY_EXTRAS=dev` explicitly for the fast
tests-and-linters path.

`[feasibility]` composes wind/micrositing/gis/report/grid; `jobs` adds redis+arq
(the `redis-server` binary ships in the image). **BESS needs no extra** — it is
core (`finance.bess_revenue`, `bess_lcos`, `bess_project_economics`,
`analytics.grid.capabilities.bess_soc`). Verified: all twelve capabilities import,
redis round-trips, and the 202 tests in the paths CI skips all pass.

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
   what the SessionStart hook (`.claude/hooks/session-start.sh`, #1041) exists for.
   Since #1046 it needs no flag: `.claude/settings.json` injects
   `DUTCHBAY_EXTRAS=dev,feasibility,jobs,solar,pareto` and the hook's own fallback
   is the *same full set*, so injection failing cannot silently under-provision.
   The legacy `DUTCHBAY_INSTALL_FEASIBILITY=1` alias only fires when
   `DUTCHBAY_EXTRAS` is *unset*, so in a web session it is now inert — set
   `DUTCHBAY_EXTRAS` directly. Costs ~1 GB and a few minutes at session start —
   paid deliberately, because a half-provisioned session fails late (a missing
   import mid-run) rather than loudly at start.
5. **protobuf: resolved in v15.4.0, recorded because the pattern recurs.**
   topfarm pulls optiwindnet → ortools, which caps `protobuf<6.34`. While
   `[micrositing]` sat outside the lock, installing it downgraded the locked
   `protobuf==7.35.1` to `6.33.6` and pip printed a live resolver conflict. #1045
   put `[micrositing]` *in* the lock and pinned `protobuf==6.33.6`, which satisfies
   every consumer in the tree and is imported by no first-party module. Third
   instance of one failure mode — an extra quietly contradicting the lock (see
   also scipy/pandapower and pyproj). `docs/ENVIRONMENT_PROVISIONING.md` §4 is the
   standing register; add the fourth there when it appears.
6. **A dev venv is NOT the CI environment.** `[dev,feasibility]` pulls
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

### 5.4 Version signalling — SETTLED
`15.3.1` was a patch bump for a change the changelog calls a material correction
(headline projIRR +1.46 % → −0.12 %). Raised three times; the owner took the
minor bump and **v15.4.0** shipped in #1045. Nothing outstanding but the signed
tag (§1).

### 5.5 Kit is one-shot for compute, not for acquisition
`feasibility_reproduce/lib/` is now committed in full — `mc_run.py`,
`wind_provenance.py`, `run_global_sa.py`, `build_study_pdf.py`, `build_md_pdf.py`,
`synthetic_site.py` — after the `.gitignore` defect in §6.1 kept it out of every
prior release. `run_all.sh` therefore runs end to end.

What is *not* one-shot: the GIS and ERA5 steps still read shipped cache rather
than re-acquiring from source. Re-deriving them needs CDS credentials and the raster
inputs, neither of which is in the repo. Treat the cache as an input, not an output.

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

Everything opened in this session is merged; `main` is at **v15.4.0** plus #1046.
There is no in-flight branch and no failing gate.

Two things the next session inherits rather than discovers:

1. ~~**The signed tag is still unpushed** (§1).~~ **Done 2026-08-18** — tag
   pushed, Release published, run green. It went up *annotated* rather than
   *signed*, and v15.4.0 can no longer be re-tagged in place. See **§9**.
2. **Provisioning is automatic now.** A web session comes up with grid,
   micro-siting, redis, solar and pareto already installed. Do *not* re-run
   `pip install` by reflex; check the hook's banner first. `DUTCHBAY_EXTRAS=dev`
   is the explicit opt-out for a fast tests-and-linters session.

After that, the next piece of work is whichever of §5 the owner chooses. §5.1
(the #923 flag flip) is the only one that moves the canon, and it is deliberately
user-gated: it wants a real feeder, a `kpi_oracle` before/after diff, and explicit
sign-off — plus, on the evidence of §5.1's guard note, a positive provenance
marker so a toy `.dss` cannot masquerade as a real feeder.

---

## 9. Addendum — 2026-08-18 session (release close-out)

Appended rather than folded into §1–§8, so the record above stays a faithful
account of what was known on 2026-08-17/18. Everything here happened *after* it.

### 9.1 Environment — the automatic provisioning of #1046 works

First cold start under the `env` block. Verified rather than assumed:

- Hook banner: `creating .venv` → `installing pinned lock +
  [dev,feasibility,jobs,solar,pareto]` → `redis started on :6379` →
  `ready — Python 3.12.3`. No flag set by hand.
- `import pandapower, andes, opendssdirect, topfarm, pvlib, pymoo, redis` → `ok`;
  `weasyprint, reportlab, arq` likewise. `redis-cli ping` → `PONG`.
- Pins land where §3 says they should: pandapower 3.5.4, scipy 1.18.0 +
  scipy-stubs 1.18.0.1, **protobuf 6.33.6** (the trap-5 pin), topfarm 2.6.2,
  numpy 2.4.6, Python 3.12.3.
- Full suite: **5247 passed, 5 skipped, 0 failed** in 20m15s.

**On the skip count.** CI's headline is 5184 passed / 13 skipped, measured against
a venv built from `requirements.txt` alone. A fully-provisioned session should skip
*fewer*, and does: 13 → 5. Three of the five survivors are *inverse* guards that
skip precisely **because** the optional dependency is present —
`test_jobs_backend_gate.py:44` (`[jobs]` installed, fail-loud path unreachable),
`test_report_renderer.py:375` (WeasyPrint installed), and
`test_self_curtailment_enablement_readiness.py:147` (`[grid]` installed, CASPER
absent-dependency guard unreachable). The other two are environmental, not
dependency-related: `test_fx_sensitivity_real.py:409` (needs a real scenario file)
and `test_mc_exports.py:293` (requires pandas to be *missing*).

A skip count *higher* than CI's is the signal that something failed to install.
Lower, with the inverse guards accounting for the delta, is the healthy shape.

The §2 canon oracle is inside that run and passed — KPIs unchanged.

### 9.2 #1048 merged

`docs(module-reference): make file-provenance paths repo-relative` — `384e990`.
Docs-only: strips a `/Users/…/Downloads/dutchbay-epc-model/` prefix off the two
"Files referenced/read" provenance lines in `docs/MODULE_REFERENCE.md` and
relabels the parenthetical `(all absolute)` → `(repo-relative)`. 8 insertions,
2 deletions, plus a changelog fragment. `grep -c '/Users/' docs/MODULE_REFERENCE.md`
→ 0.

Two process notes for anyone repeating this:

- It was opened as a **draft**. GitHub will not merge a draft; it has to be marked
  ready for review first. That is a step, not a formality.
- CI was read via `get_check_runs`, **not** `get_status`. §3 trap 2 still holds —
  `get_status` returns legacy commit statuses this repo does not use. 16 checks:
  15 success, 1 skipped (Grid Study, opt-in and non-blocking). The six test shards
  each finished in ~5s, which is `test-suite.yml`'s docs-only fast path firing
  correctly (`docs/*` and `changelog.d/*` are both allowlisted).

### 9.3 v15.4.0 tagged and released

The owner pushed the tag from a scratch clone, targeting the release commit
explicitly rather than the tip of `main`:

```bash
git tag -a v15.4.0 0379843 -m "DutchBay 15.4.0"
git push origin v15.4.0
```

Targeting `0379843` (#1045) is correct — that is the squashed release commit
§6 means, and `VERSION` there reads `15.4.0`. Tagging the tip of `main` would have
been the mistake.

`release-run.yml` fired on the tag: run **32114800889**, `success` on the first
attempt, 17m08s. All 13 steps green — full suite (15m11s), lender-pipeline smoke,
lendercase artifacts, upload, package, publish.

**GitHub Release v15.4.0 is published** — `draft: false`, `prerelease: false`,
asset `DutchBay_Model_V15.4.0.zip`, 43,241 bytes,
`sha256:f37d7954a2487e0c180f3999d48347752fbe07e4c8fd4d1ea12f470bb05c17d0`.

Two things about it that are worth not re-deriving:

1. **The tag is annotated, not signed.** `-a` was used where `RELEASING.md` §6
   says `-s`, so `git tag -v v15.4.0` reports `error: no signature found`. Nothing
   is blocked: `release-run.yml` triggers on a bare `on: push: tags: ["v*"]` and
   verifies no signature anywhere (grepped). The cost is provenance only — the
   release carries no cryptographic attribution.
2. **v15.4.0 cannot be re-tagged in place.** The published Release is
   `immutable: true`, so §7's "the release step is idempotent — re-tagging
   re-uploads the asset rather than failing" **no longer applies to this
   version**. Replacing the tag now means deleting the Release and republishing.
   Not done, and not proportionate for a provenance nicety on an already-published
   version. Use `git tag -s` on the next cut.

The Release's `target_commitish` field reads `main`. That is cosmetic — GitHub's
default on a release created from an existing ref. The tag resolves to `0379843`,
which is what was built, tested, and zipped.

### 9.4 What is open now

`main` is at `384e990`. No in-flight branch, no failing gate, no unpushed tag.

`changelog.d/` holds two unreleased fragments — `auto-provision-full-extras.changed.md`
(#1046) and `module-reference-absolute-paths.fixed.md` (#1048). Both are
post-15.4.0 and belong to the next cut. Flush with
`python scripts/compile_changelog.py` before that cut, not before.

**§5 is unchanged and still the menu.** §5.1 (the #923 flag flip) remains
user-gated — it moves the canon and wants a real feeder, a `kpi_oracle`
before/after diff, explicit sign-off, and a positive provenance marker so a toy
`.dss` cannot masquerade as a real feeder. §5.2 and §5.3 are untouched.

One item queued by #1048 and deliberately left undone there:
`docs/MODULE_REFERENCE.md`'s Scope line (line 9) still reads *"Describes the code
at version 15.3.0 (repository `main` at commit `3012641`)"*. `main` is now v15.4.0
at `384e990`. #1048's reasoning for not touching it holds and should be respected:
bumping the number without re-reviewing all 766 lines against v15.4.0 converts an
honest stale marker into a false currency claim, which is worse than the
staleness. It needs a real review, not an edit.
