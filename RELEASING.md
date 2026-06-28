# Releasing the DutchBay Model

This guide locks dependencies, runs full QA, and produces a GitHub Release with an artifact
zip. The release number is **read from the `VERSION` file** — bump that first and every step
derives the version from it, so this guide does not go stale per release.

All release prep happens on a **`release/*` branch → PR → merge** (GWTF GOV-02: never commit
to `main` directly — the `main` ruleset and the `no-commit-to-branch` pre-commit hook both
block it). Only the signed **tag** is pushed to `main` afterward.

## 0) Cut a release branch and set the version

```bash
git fetch origin
git switch -c release/v15.0.0 origin/main   # example; choose the real number
git branch --show-current                   # GOV-02: confirm you are NOT on main
echo "15.0.0" > VERSION                      # match the branch name
# edit pyproject.toml [project].version to match VERSION
VERSION=$(cat VERSION); echo "Releasing v${VERSION}"
```

## 1) Full QA

```bash
make setup
make lint type security test cov
```

## 2) Refresh the dependency lock (deterministic deployments)

`pyproject.toml` is the single ABSTRACT source of truth (core deps + extras);
`requirements.txt` is the ONE pinned lock CI installs. There is no separate
`constraints.txt` / `requirements.lock` (retired). Regenerate the lock from a
CLEAN venv so it cannot drift or re-accrete non-dependencies:

```bash
make lock     # pip install -e ".[dev,api,dashboard,wind,gis,report]" + freeze -> requirements.txt
make audit    # re-check the regenerated lock for new CVEs (pip-audit + allowlist)
```

Review the `requirements.txt` diff before committing.

## 3) Verify the wheel builds and imports

```bash
python -m pip wheel . --no-deps -w dist/
python -c "import importlib.metadata as m; print('built', m.version('dutchbay-epc-model'))"
```

## 4) Update the changelog

Move the `## [Unreleased]` items in `CHANGELOG.md` under a new dated heading:
`## v<version> - YYYY-MM-DD`.

## 5) Commit on the branch, open the PR, merge

```bash
VERSION=$(cat VERSION)
git add VERSION pyproject.toml CHANGELOG.md requirements.txt
git commit -m "chore(release): v${VERSION}"
git push -u origin "release/v${VERSION}"
gh pr create --title "chore(release): v${VERSION}" --fill
# wait for required CI to go green, then:
gh pr merge --squash --delete-branch
```

## 6) Tag the merged commit (tag only — never push main)

```bash
VERSION=$(cat VERSION)
git switch main && git pull --ff-only origin main   # the squashed release commit
git tag -s "v${VERSION}" -m "DutchBay ${VERSION}"
git push origin "v${VERSION}"                        # push the TAG, not main
```

## 7) GitHub Actions

- The `release-run.yml` workflow runs on the pushed tag and creates a Release with the
  artifact `DutchBay_Model_V<version>.zip`.
- If CI fails, fix on a new branch → PR → merge, then bump the patch (e.g. `15.0.1`) and
  retag.

## Notes

- `VERSION` is the single source of truth for the release number; keep
  `pyproject.toml [project].version` in sync with it.
- Runtime/CI installs use the pinned `requirements.txt` lock (the single lock file).
- Dev installs use `-e ".[dev]"` (the toolchain extra) so local and CI behave the same.
