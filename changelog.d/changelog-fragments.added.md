- **Changelog fragments: per-PR entries now live in `changelog.d/` and compile into `CHANGELOG.md` on demand (dev-workflow, no runtime/KPI impact).**
  Editing the shared `CHANGELOG.md [Unreleased]` block in every PR guaranteed a merge conflict between concurrent
  dolphins (→ forced rebase → a second full CI run). Each change now drops a `changelog.d/<id>.<category>.md`
  fragment (unique filename → never conflicts); `python scripts/compile_changelog.py` folds pending fragments into
  `[Unreleased]` under their Keep-a-Changelog section (newest first) and deletes them — run on demand (end of a
  batch / before a release). `--check` lists pending, `--dry-run` previews. See `changelog.d/README.md`.
