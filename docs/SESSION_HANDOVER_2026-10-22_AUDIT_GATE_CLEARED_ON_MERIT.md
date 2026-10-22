# Session handover — 22 October 2026: handover resolver restored, audit gate cleared on merit

## Status and authority

Written under `PERSIST-01` by the project thread "Handover bootstrap and readiness check", which
ran 2026-10-21 02:18Z to 2026-10-22 05:40Z and changed load-bearing state three times. Successor
to `docs/SESSION_HANDOVER_2026-10-17_D3_OPERATIONAL_AEP.md`; `scripts/list_session_handover_records.py`
orders the chain by committer lineage, so this record joins it when this change merges.

`main` moved `8c4d0761` → `050fb56e` → `0255c1fd` → `2d56ed66` in under twelve hours. `VERSION` and
the latest release tag are both `v15.6.1` and did not change: nothing here touches committed
financial behaviour.

**No `HOLD` was lifted and no authority beyond merge was taken.** Issue #1110 remains `OPEN` with
its Board and lender circulation `HOLD`. The F-5 bar stands: no quarterly CFADS or intra-year DSCR
figure supports a covenant, lender or IC representation until a within-year event calendar lands.
No finance formula, model input, KPI, scenario, tariff, FX or evidence surface was touched by any of
the three changes. Each merge was separately authorised by the project owner in the owning thread;
the authorisations are quoted in the merge records cited below.

## Delivered result and durable receipts

### 1. The handover resolver works on every git in use again — #1368, squash `0255c1fd`

`scripts/list_session_handover_records.py` exited 2 with `malformed batched lineage ISO timestamp`
before printing any record, on any host with git older than **2.45.0**. #1358's guard accepted a
zero UTC offset only spelled `Z`; git writes `%cI` that way only from 2.45.0, and older git writes
`+00:00`. The spelling is chosen by the git that **reads** the history, not the one that wrote the
commit, so the failure was not confined to two commits: every zero-offset commit touching a
handover record hits it, on every pre-2.45 host, forever — and GitHub's squash button, this
repository's normal merge path, stamps UTC every time. CI never caught it because runners are
`ubuntu-latest`, whose git moves, and nothing records the git version observed.

The guard now admits `+00:00` as well as `Z`, still rejects `-00:00` (RFC 3339 reads it as an
unknown local offset) and all fourteen malformed forms the suite exercises, and
`tests/lint/test_codex_project_guidance.py` pins both spellings through injected headers instead of
encoding the git version it was written on. Reviewed head `3c9b0747`, merged 20:14:25Z, 3 files
+41/−3. Merge record: PR comment 6325606386. Verified on the merged `main` at this container's git
**2.43.0** — the version that reproduced the defect: resolver `exit=0` printing five records,
`tests/lint/test_codex_project_guidance.py` `66 passed`.

### 2. The audit gate, twice — #1369 squash `050fb56e`, then #1372 squash `2d56ed66`

**#1369, 16:50:50Z.** `certifi` 2026.7.22 → 2026.10.19 (PYSEC-2026-4320), plus eight
`--ignore-vuln` entries in the `Makefile`'s `PIP_AUDIT_IGNORES` for eight advisories against
`pillow==12.3.0`. Those eight were fixed only in `pillow 13.0.0`; every `streamlit` release then
published capped `pillow<13`; and PyPI had no `pillow` between 12.3.0 and 13.0.0. The allowlist is
the hatch the `Makefile` itself reserves for exactly that case, and the entries carried their cap,
their reachability argument and their removal condition. Reviewed head `7c5c387c`. Merge record: PR
comment 6321535907.

**#1372, 04:24Z the next morning.** All eight entries deleted, `PIP_AUDIT_IGNORES` empty again;
`pillow` → 13.0.0, `streamlit` 1.62.0 → 1.66.1, `virtualenv` 21.7.13 → 21.14.12. Reviewed head
`96cf5bb1`, 4 files +36/−29. Merge record: PR comment 6332674959.

Two measurements explain why the same gate needed two changes twelve hours apart, and both are
reproducible from the objects rather than inferred:

- **The cap lifted.** `streamlit 1.66.1` was published to PyPI at **2026-10-21T17:02:55Z**, twelve
  minutes after #1369 merged, raising its own cap from `pillow<13` to `pillow<14,>=9.2.0`. Checked
  release by release: 1.62.0 through 1.65.0 all require `pillow<13`; 1.66.0 requires
  `pillow<13,>=9.2.0`; 1.66.1 is the first `streamlit` admitting `pillow 13`. #1369's justification
  was true when written and overtaken within the hour. After #1372 nothing in the lock caps
  `pillow` below 14.
- **The advisory set tripled overnight.** `pillow 12.3.0` carried eight advisories when #1369's
  gate ran green at 16:56Z and **twenty-four** by 00:50Z, all `fixed_in 13.0.0`, none withdrawn,
  plus five new ones against `virtualenv 21.7.13`. Re-run at 04:21Z against `main`'s own lock at
  `0255c1fd`: `pip-audit --no-deps` → `Found 29 known vulnerabilities in 2 packages`, exit 1; and
  **with #1369's eight ignores applied**, still exit 1 on `Found 21 known vulnerabilities, ignored
  8 in 2 packages`. So `main` was red on its own bytes, and an allowlist route would by then have
  needed 21 entries and kept growing.

The `virtualenv` five (CVE-2026-113722, -113725, -113726, -113732, -113776) are shell-quoting
defects in the generated bash, zsh and fish `activate` scripts, fixed across 21.14.2 through
21.14.9; 21.14.12 clears all five and carries none of its own. Only `pre-commit` requires
`virtualenv`, with no upper bound.

### Receipts on the merged `main` (`2d56ed66`)

| Check | Result |
|---|---|
| `pip-audit --no-deps -r requirements.txt` | `No known vulnerabilities found`, exit 0, with `PIP_AUDIT_IGNORES :=` empty |
| `pip install --dry-run --ignore-installed -r requirements.txt` | exit 0, 312 packages, only the three targets moved |
| `pip check` | `No broken requirements found.` |
| `make lint` | exit 0 — `All checks passed!`, black `777 files would be left unchanged`, isort skipped |
| CI on `96cf5bb1` | 20 checks success, 2 skipped by their own path filters; all six shards, 9 126 tests, 0 failures |
| `scripts/list_session_handover_records.py` at git 2.43.0 | `exit=0`, five records in order |

### Review and merge governance

All three changes carried two independent `RECRUIT-01` R2 dispositions, in separate sessions from
the writing thread and from each other, with durable records under
`/mnt/project-files/review-records/`: `2026-10-21/pr1369-{domain,assurance}.txt`,
`2026-10-21/pr1368-{domain,assurance}.txt` and `2026-10-22/pr1372-{domain,assurance}.txt`. Each
merge verified, at the objects and immediately before the call, that the head and base had not
moved, that the subject blobs matched the bound ones, that each disposition comment was unedited
(`created_at == updated_at`), and that every required check was green on that exact head; and
afterwards that the squash tree equalled the reviewed head's tree and its single parent equalled
the `main` SHA recorded before the call. None of the three squash messages carries an attribution
trailer, deliberately: this repository is public and `main`'s history cannot be redacted.

`#1372` carried one condition into the merge rather than fixing it — recorded, not shipped silently;
see P-7 below. Both lanes offered that route explicitly.

## Local environment

Cloud container, not the owner's Mac. The checkout-local `.venv` provisioned by
`.claude/hooks/session-start.sh` under the `ENV-01`/`THREAD-01` portable fallback: Python 3.12.3,
`pip check` clean. **git 2.43.0**, which is what made #1368's defect reproducible here at all; the
owner's Mac git version remains unknown and unrecorded, which is half of P-5. `MANIFEST`-bearing
evidence under `/Users/aruna/...` cannot be read from a container and was not inferred.

Up to five tests in `tests/lint/test_cloud_audit_review_sandbox.py` (sandbox watchdog and
process-reaping cases) fail in cloud containers on an unmodified `main` and pass in CI (#1289,
#1292). Observed **five** this session, at both the candidate and the base of #1368 — verified at
both ends rather than cited, so they are pre-existing and local, not caused by any change here.

## Live queue and next-session route

Open, all recorded on #1353, none owned:

- **P-1** — nothing fences `PIP_AUDIT_IGNORES`. No test asserts an entry carries a reason, still
  matches a live finding, or is removed when its cap lifts. Less exposed now that the variable is
  empty, and the rewritten comment demands a future entry name its cap and the release that would
  lift it, but the gap is real: it is what would have caught both of this session's surprises.
- **P-5** (comment 6325525012) — the resolver is never run against this repository's own history in
  CI, nothing records the host `git --version`, and its error names neither the rejected field nor
  the git it saw. That combination is what let a version-dependent guard ship green.
- **P-7** (comment 6330262975) — four claims across the two uncompiled changelog fragments are false
  after #1372: three in `changelog.d/certifi-pysec-2026-4320.fixed.md` still describe an allowlist
  that no longer exists, and the new fragment's reason for "no abstract dependency change" is wrong
  (`pyproject.toml:108` does declare `streamlit>=1.40`; the conclusion survives, the reason does
  not). Both fragments compile into the same `### Fixed` section. **Must close before the next
  release compiles `changelog.d/`.**
- **P-8** (same comment) — `app/streamlit_app.py:68` and `:117` pass `use_container_width`, whose
  announced removal date was 2025-12-31. It works in both 1.62.0 and 1.66.1, so nothing is urgent,
  but a future minor can drop it. Migration is mechanical: `width="stretch"`.
- **#1359–#1363** — Dependabot's 2026-10-14 batch, still open, still red on `INTAKE-01` because no
  non-bot comment on #1353 names them. They fill `open-pull-requests-limit: 5`, so no further pip
  version-update PR can open until they clear. This needs an owner, not a decision.

Closed this session: #1370 (`pillow` 12.3.0 → 13.0.0) closed itself at 04:26:27Z, two minutes after
#1372 merged, with no `.github/dependabot.yml` entry ever added — landing the target version
retires the bot's PR, which an ignore rule would not have done for the gate. P-2, P-3 and P-4 are
closed or withdrawn, recorded on the work items.

Two things for whoever picks this up:

1. **Re-check a capping release before trusting an accepted CVE, not just before the next release.**
   Twelve minutes was enough here. The same applies to any `--ignore-vuln` entry and any dependabot
   `ignore` rule justified by an upstream cap.
2. **An advisory count from a record hours old is not evidence.** Re-run the audit. Eight became
   twenty-four overnight against an unchanged pin.
