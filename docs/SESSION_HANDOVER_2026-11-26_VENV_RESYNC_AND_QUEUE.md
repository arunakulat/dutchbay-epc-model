# Session handover — 26 November 2026: persistent runtime resync (#1422), version line 15.34 to 15.37, and active queue

## Status and authority

Written under `PERSIST-01` for focused issue #1422 (`env: record the owner's persistent runtime
resynced to the current lock`), tracked under `INTAKE-01` at
`https://github.com/arunakulat/dutchbay-epc-model/issues/1353#issuecomment-7200320685`. It is the
**successor** to `docs/SESSION_HANDOVER_2026-11-22_GATES_AND_VERSION_LINE.md`, its **predecessor**,
which was the newest record `scripts/list_session_handover_records.py` resolved until this one.
Between `69029b89` (#1905, which introduced the 22 November record) and `cc0d1612` (#1968), `main`
took 35 first-parent landings and `VERSION` moved from `15.33.0` (the version cited in the 22
November record) to `15.37.0`. Nothing in this record is new policy: it records verified local
runtime evidence for #1422 and carries forward the repository's standing continuity pointers.

**Startup record and carried-forward state.** `AGENTS.md` "Session continuity" directs every next
session to take these from this record, not from a hardcoded filename in the gateway. This record
carries forward, and does **not** replace:

- the **v15.6.1 startup record**, `docs/SESSION_HANDOVER_2026-10-05_RELEASE_15_6_1.md`. It remains
  the startup record because no release has been cut since: the newest release tag and the newest
  released `CHANGELOG.md` section are both v15.6.1. `VERSION` has moved without a release (now
  `15.37.0`; see "The version line" below), so the startup record's figures are history; read live
  KPIs from `main`;
- the declared work list `docs/SESSION_HANDOVER_2026-10-12_THREAD_TODO.md` and the sibling
  capability handover `docs/SESSION_HANDOVER_2026-10-11_CAPABILITY_ROADMAP.md`, as declared in the
  prior handover chain;
- from its predecessor (`docs/SESSION_HANDOVER_2026-11-22_GATES_AND_VERSION_LINE.md`): the CI and
  governance gates enforced on `main`, the residual queue #1629 (Blue Whale native-currency and
  financing gaps), the refusal guards of #1627, and every source, professional, lender, Board and
  release boundary carried forward there.

Run `scripts/list_session_handover_records.py` and read its newest result first. It refuses shallow
history, so fetch `--unshallow --tags` before relying on it.

This file grants no writer, merge, finance, evidence, professional, utility, release, lender, Board,
publication, deployment, issue-closure or `HOLD` authority.

**No `HOLD` was lifted.** #1110 remains open with its Board and lender circulation hold. The F-5
bar stands: no quarterly CFADS or intra-year DSCR figure supports a covenant, lender or IC
representation. The v15.6.1 release boundary is unchanged.

## Persistent runtime resync evidence (#1422)

On the owner's Mac, the protected persistent governed Python 3.12 runtime at
`/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv` was resynced via `./setup_venv.sh` to the current
`requirements.txt` lock and verified with `DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv ./check_venv.sh`
against `origin/main` (`cc0d1612b65b8f3265fab46a343e3c5e57eb0c65`, `VERSION` `15.37.0`).

| Check | Observed evidence |
|---|---|
| Protected runtime path | `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv` (`ENV-01` / `THREAD-01`; never delete or replace) |
| `python -VV` | `Python 3.12.16 (main, Oct 25 2026, 18:24:37) [Clang 21.0.0 (clang-2100.3.34.2)]` |
| `requirements.txt` SHA-256 | `8c09abeb1a85c6bdbb5b1416d79cd6762de0d4c4761b21765c08deaf9b00eccc` |
| `VERSION` | `15.37.0` |
| `./check_venv.sh` status | `PASS` (`schema`: `dutchbay.development_environment_receipt.v1`, `selection_source`: `DUTCHBAY_VENV`) |
| Locked distributions | `locked_distribution_count`: `317`, `absent_locked_distributions`: `[]` |
| Isolation checks | `editable_project_install`: `false`, `foreign_checkout_paths`: `[]`, `import_probe`: `analytics` resolved from active worktree |
| Required distributions | `hydra-core` `1.3.8`, `numpy` `2.4.6`, `opendssdirect.py` `0.9.4`, `pandas` `2.3.3`, `pytest` `9.1.1`, `ruff` `0.14.14`, `scipy` `1.18.1` |

Verbatim `./check_venv.sh` receipt lines (run in isolated worktree `wt_1422` at `cc0d1612`):

```text
{"absent_locked_distributions": [], "active_checkout": "/Volumes/Data backup/DutchBay_Verification/2026-11-26_Wave1/wt_1422", "dependency_lock": "requirements.txt", "editable_project_install": false, "environment_variable": "DUTCHBAY_VENV", "foreign_checkout_paths": [], "import_path": "/Volumes/Data backup/DutchBay_Verification/2026-11-26_Wave1/wt_1422/analytics/__init__.py", "import_probe": "analytics", "locked_distribution_count": 317, "portable_fallback": ".venv", "project_install_url": null, "python_executable": "/opt/homebrew/Cellar/python@3.12/3.12.16/Frameworks/Python.framework/Versions/3.12/bin/python3.12", "python_prefix": "/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv", "python_version": "3.12.16", "required_distributions": {"hydra-core": "1.3.8", "numpy": "2.4.6", "opendssdirect.py": "0.9.4", "pandas": "2.3.3", "pytest": "9.1.1", "ruff": "0.14.14", "scipy": "1.18.1"}, "schema": "dutchbay.development_environment_receipt.v1", "selection_source": "DUTCHBAY_VENV", "status": "PASS", "venv_path": "/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"}
Environment validation PASS: /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv
```

This satisfies the done-when condition of #1422 (originally `docs/SESSION_HANDOVER_2026-10-11_MERGE_COORDINATION.md`
item 8, H-D2-02's gate).

## The version line (15.34.0 to 15.37.0)

Since the `15.33.0` baseline recorded in `docs/SESSION_HANDOVER_2026-11-22_GATES_AND_VERSION_LINE.md`,
`VERSION` moved four times under `DOC-02` option B; none is a release:

| Version | Change | Pull request |
|---|---|---|
| 15.34.0 | Apply the capex price date in every capex reader; declare the moved figures | #1910 (#1899) |
| 15.35.0 | Sample FX depreciation from a sourced band; USD opex share only for Blue Whale wind | #1914 (#1898) |
| 15.36.0 | Add interannual variance `sqrt(1/T + 1/H)` to FX depreciation band | #1947 (#1917) |
| 15.37.0 | Derive native CAPEX LKR conversion from `fx.start_lkr_per_usd` (DOM-1645-03) and #1696 follow-ups | #1952 (#1629) |

## Where open work lives

Read these live; any snapshot copied here goes stale quickly:

- Tracker #1353: capability and assurance roadmap and all `INTAKE-01` pre-edit records. Merge-queue
  and landing records live on #1713; agent-to-agent coordination on #1714.
- Surviving holds and residual queues: #1110 (programme audit, Board and lender circulation HOLD),
  the F-5 intra-year DSCR bar, and #1629 (Blue Whale native-currency and financing residual queue).
- At the time of writing, the open pull requests on GitHub were draft PR #1970 (#1429 E01 equity
  lock-up DSCR threshold) and draft PR #1971 (#1615 retire zero-caller deprecated
  `analytics.wind.pipeline_aep_v14`).

When this record lands, apply `CLEANUP-01` for #1422 and record the landing on #1353 / #1713.
