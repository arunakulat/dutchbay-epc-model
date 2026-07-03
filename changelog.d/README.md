# Changelog fragments

Per-PR changelog entries live here as small fragment files instead of being written
directly into [`../CHANGELOG.md`](../CHANGELOG.md). Editing the shared `[Unreleased]`
block in every PR guarantees a merge conflict between two concurrent PRs (→ forced
rebase → a second full CI run); unique fragment filenames never collide. This is the
towncrier/scriv pattern.

## Add an entry (do this in your PR, instead of editing `CHANGELOG.md`)

Create `changelog.d/<id>.<category>.md` where:

- `<category>` is one of `added`, `changed`, `deprecated`, `removed`, `fixed`,
  `security` (the verb forms `add` / `change` / `deprecate` / `remove` / `fix` are
  also accepted).
- `<id>` is any slug or issue/PR number (only used to keep filenames unique and
  ordered).

The file holds one or more markdown bullets, e.g.:

```
# changelog.d/752.changed.md
- **flake8-bugbear B905 resolved** — every `zip()` declares `strict=`.
  A continuation line is fine (indent it two spaces).
```

Do **not** edit `CHANGELOG.md` directly for routine changes.

## Flush (compile) — on demand

```
python scripts/compile_changelog.py            # fold fragments into CHANGELOG.md, delete them
python scripts/compile_changelog.py --check    # list pending fragments; exit 1 if any (CI-friendly)
python scripts/compile_changelog.py --dry-run  # print the would-be CHANGELOG.md, change nothing
```

Run it at the end of a work batch, before a release cut, or whenever you want to batch
the pending entries in. Fragments are folded into `CHANGELOG.md [Unreleased]` under
their `### Category` (Keep-a-Changelog order, newest first) and then deleted.
