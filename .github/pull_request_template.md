## Summary
<!-- One or two sentences: what changed, and why. -->

### Work intake (`INTAKE-01`)

Work item: <!-- #<focused issue number> OR full URL to a scoped #1353 comment -->
Base SHA: <!-- 40-character origin/main SHA observed before work -->
Open PR sweep: <!-- list all open PR numbers and overlap/blocker dispositions; write "none" if none -->
Recorded before edits: <!-- cite that issue number or exact tracker comment URL, with date -->

The work item must be a scoped issue recorded on #1353 or a scoped tracker comment
beginning `Work item:`. A bare `#1353` or a child issue that only mentions #1353
does not pass. A blocked,
unrelated PR does not stop this work; say why it is unrelated and when it will be
revisited. Bot-created PRs need this intake completed before follow-up or merge.

### Scope
- [ ] One focused, independently revertable change (`DELIVERY-01` — a dolphin, not a whale)
- [ ] KPI impact: **none** / **stated in "Financial impact" below** *(delete one)*
- [ ] Changelog fragment added under `changelog.d/` (not an edit to `CHANGELOG.md`)

### Verification — receipts, not claims

Paste the command **and its result** for each check. A check you did not run is
**declared** here as `not run — <reason>`; it is never left silent. This follows the
`required-not-run` convention of `docs/audit/2026-08-controlled-successor/`: an
unverified item is stated, not omitted.

The automated check reads these cells for **presence, not truth** — it cannot re-run your
commands, so stale or wrong numbers pass it. Paste what the command actually printed.

| Check | Command run | Result |
|---|---|---|
| Focused tests | `pytest -p no:cacheprovider <paths> -q` | *e.g.* `12 passed in 3.1s` |
| Lint | `ruff check <changed paths>` | |
| Format | `ruff format --check <changed paths>` | |
| Types | `mypy <changed paths>` | |
| Financial regression *(if finance-material)* | | |

CI remains the merge authority — this table is not a substitute for it. It exists so a
reviewer can see what was **actually executed** rather than what was asserted.

### What changed
- ...

### Financial impact *(delete this section if the change is KPI-neutral)*
- KPIs affected, with direction and magnitude.
- The re-baseline note added to `tests/_canon.py` and the oracle docstring.
- Why the new values are correct, not merely different.

### Screenshots / charts *(if applicable)*
- ...

### Notes
- Breaking changes, migrations, or follow-up work.
