# Session handover — 2026-08-20

Durable record per **PERSIST-01**. Successor to
`docs/SESSION_HANDOVER_2026-08-17_18.md`, which remains the account of the
2026-08-17/18 session and is **not** superseded wholesale — its §2 canon, §3
traps and §5 open items still stand except where this file says otherwise.

**Session:** web/container session, 2026-08-18 → 2026-08-20.
**Entry point:** cold start on `main` at v15.4.0 + #1046.

---

## 1. Bootstrap — do NOT read this file for it

`AGENTS.md` is the machine memory and the single source of the startup
contract. It was rewritten by **#1119 on 2026-08-20** and is newer than any
bootstrap text in the 08-17/18 handover. Read `AGENTS.md` first, in full.

Duplicating the commands here would create a second copy that drifts, which is
the exact failure §9 of the previous handover kept hitting. The contract in one
line: `AGENTS.md` lines 10–50 and rules **ENV-01** and **THREAD-01**.

What a successor must internalise, because getting it wrong is silent:

- **Two different folders, both real, different jobs.** The durable project
  folder is `/Users/aruna/Downloads/Dutchbay_EPC_Model` (underscores) and holds
  the persistent governed Python 3.12 runtime at its `.venv`. The Git checkout
  is `/Users/aruna/Downloads/dutchbay-epc-model` (hyphens). ENV-01 is explicit
  that these are **complementary, not alternatives**: root work at the checkout,
  point `DUTCHBAY_VENV` at the project folder's `.venv`, and put the active
  checkout first on `PYTHONPATH`. A successor that collapses them into one path
  will look like it works and will resolve imports from the wrong tree.
- **Prohibited environments are named, not implied.** A checkout-local
  replacement `.venv`, `.venv311`, bare/system Python, and another project's
  environment are all refused. `tests/lint/test_gwtf_canonical_source.py`
  asserts these strings, so this is enforced, not advisory.
- **The portable `.venv` fallback is a boundary, not a default.** It is
  permitted only when `DUTCHBAY_VENV` is unset on an unconfigured developer host
  or an ephemeral CI/container host.

## 2. Governance moved: 66 → 70 rules

The previous handover's §7 says "GWTF v3.0, 66 active rules". **That count is
stale.** The ruleset is now **70 active rules**, still v3.0. Verify, do not
trust:

```bash
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  PYTHONPATH="$PWD" "$DUTCHBAY_VENV/bin/python" dutchbay_bootstrap_rules.py
```

Two of the new rules are dated `Governance addendum (2026-08-20)` and bind every
session:

- **THREAD-01** — every new thread, *regardless of subject*, must be created
  from and remain associated with the DutchBay_EPC_Model project, using its
  persistent venv. Not an unscoped chat, not another project.
- **ENV-01** — root work at the active checkout, bind shared Python imports to
  it. Shared-environment changes must be proved with
  `scripts/verify_shared_venv_worktrees.py` against **two distinct clean
  worktrees**, retaining the concise JSON receipt rather than raw logs.

## 3. What this session did

| PR | Commit | What |
|---|---|---|
| #1048 | `384e990` | `MODULE_REFERENCE.md` file-provenance paths made repo-relative (merged on request) |
| #1049 | `4bbc6dec` | This chain's predecessor: recorded the v15.4.0 release close-out as §9 |
| #1050 | `b10af651` | Corrected `go_with_the_flow_ci.py`'s path in `MODULE_REFERENCE.md` |

**v15.4.0 is released.** The owner pushed the tag on 2026-08-18;
`release-run.yml` run `32114800889` went green first attempt and published the
Release with `DutchBay_Model_V15.4.0.zip` attached. Two facts recorded in the
predecessor's §9.3 and still true: the tag is **annotated, not signed** (`-a`
where `RELEASING.md` §6 says `-s`), and the published Release is
`immutable: true`, so v15.4.0 **cannot be re-tagged in place** — replacing it
means delete-and-republish. Use `-s` on the next cut.

## 4. Environment receipt for a container session

Recorded because the previous handover's §3 environment text predates the shared
venv contract and would mislead. On this ephemeral container the new
`check_venv.sh` (rewritten by #1118) returns **PASS**:

```
status                PASS
selection_source      portable_fallback
python_prefix         <checkout>/.venv
python_version        3.12.3
active_checkout       <checkout>
editable_project_install   false
foreign_checkout_paths     []
```

`selection_source: portable_fallback` is the **correct and permitted** value
here — `DUTCHBAY_VENV` is unset on an ephemeral container host, which is exactly
the boundary AGENTS.md carves out. On the owner's Mac it must instead read the
configured `DUTCHBAY_VENV` path; `portable_fallback` there means the contract
was not honoured.

Full suite on this container, fully provisioned: **5247 passed, 5 skipped, 0
failed**. CI's headline is measured against `requirements.txt` alone and skips
more; a fully-provisioned session should skip **fewer**. A count *above* CI's
means something failed to install. Three of the five skips are inverse guards
that skip *because* an optional dependency is present. Check the reason strings,
never the line numbers — they rot (see §5).

## 5. Lessons this session paid for

1. **Line numbers in durable docs rot; reason strings do not.** A skip cited as
   `:147` moved to `:151` within hours when #1052 rewrote its file. Cite the
   file and the reason string.
2. **Do not enumerate volatile state in a durable doc.** The predecessor's §9.4
   was overtaken twice in one afternoon by listing commit ids and changelog
   fragments. It now opens by telling the reader to check rather than trust, and
   gives the commands. Follow that pattern here.
3. **`mergeable_state` lies on first poll.** It returned `unknown`, then
   `behind` against an already-merged base. Verify with
   `git merge-base --is-ancestor origin/main <head>` before acting. This is a
   sibling of the previous handover's §3 trap 2 (`get_status` reporting 0
   checks); use `get_check_runs`.
4. **Check for an existing merge before force-pushing.** A push of #1050 was
   rejected non-fast-forward because another actor had made the *identical*
   `origin/main` merge on the branch. Both trees resolved to `0f1554b2`. The fix
   was `reset --hard` to the remote, not `--force`.
5. **`main` moves fast — assume it moved.** It took 26 merges from other actors
   across this session's span, twice putting green PRs back to `behind`.
   Re-verify against `origin/main` at the start of any piece of work.

## 6. Open items

**Check, do not trust.** `git log --oneline -10 origin/main` and
`ls changelog.d/` settle current state faster than reading further.

- **The August 2026 controlled audit successor pack is published and on HOLD.**
  #1111 added `docs/audit/2026-08-controlled-successor/` — 111 findings, 42
  source records, 72 architecture pointers, 34 reproduction controls, structural
  status `PASS`, release status **HOLD**. It is **not** approved for Board or
  lender circulation. The live remediation queue and the release decision are
  **GitHub issue #1110**; merging the pack did not close it. Validate with
  `python docs/audit/2026-08-controlled-successor/scripts/validate_published_pack.py`.
- **#923 is being worked in governed slices by another actor.** #1052 (#923-A)
  typed feeder provenance and made synthetic feeders ineligible for canonical
  finance — that is the positive provenance marker the 08-17/18 handover's §5.1
  guard note asked for. #1056–#1117 continue through #923-B and beyond. The
  **flag flip itself remains user-gated**: it moves the canon and still wants a
  real feeder, a `kpi_oracle` before/after diff, and explicit sign-off.
- **`MODULE_REFERENCE.md`'s Scope line is still stale** at *"version 15.3.0
  (`main` at `3012641`)"*. #1048's reasoning stands: bumping the number without
  re-reviewing all 766 lines converts an honest stale marker into a false
  currency claim. Measure the gap before quoting it — it only grows:

  ```bash
  git rev-list --count 3012641..origin/main
  git diff --name-only 3012641 origin/main -- '*.py' | grep -v '^tests/' | wc -l
  ```

  Observed series: 71 commits / 43 modules at `384e990`; 72 / 48 at `372edaed`;
  77 / 48 at `4bbc6dec`. This is a whale — decompose it per DELIVERY-01 across
  the document's 19 domain sections rather than attempting one pass.
- §5.2 (micro-siting optimiser non-convergence) and §5.3 (real site geometry
  missing) in the 08-17/18 handover are **untouched** and still open.

## 7. Binding governance

GWTF v3.0, **70** active rules. Binding for this work: **THREAD-01** and
**ENV-01** (both new, see §1–§2), **DELIVERY-01** (dolphins, not whales),
**GOV-02/R23/R25** (never commit to `main`; verify `git branch --show-current`
before *every* commit), **CESSPIT**, **CASPER**, **FIN-01/02**, **MRM-01/02**,
**PERSIST-01** (this file).
