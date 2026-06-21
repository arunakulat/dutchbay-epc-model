# Releasing the DutchBay Model

This guide locks dependencies, runs full QA, tags, and produces a GitHub Release with an
artifact zip. The release number is **read from the `VERSION` file** — bump that first and
every step derives the version from it, so this guide does not go stale per release.

## 0) Set the release version

Bump `VERSION` (and keep `pyproject.toml [project].version` in sync) to the new release:

```bash
echo "15.0.0" > VERSION          # example; choose the real number
# edit pyproject.toml [project].version to match VERSION
VERSION=$(cat VERSION); echo "Releasing v${VERSION}"
```

## 1) Ensure clean state

```bash
git checkout main
git pull --rebase
make setup
make lint type security test cov
```

## 2) Freeze/lock deps (deterministic deployments)

```bash
make freeze   # writes constraints.txt from the current env
make lock     # writes requirements.lock for CI/Prod
git add constraints.txt requirements.lock
git commit -m "chore(lock): freeze dependencies for v$(cat VERSION)"
```

## 3) Verify the wheel builds and imports

```bash
python -m pip wheel . --no-deps -w dist/
python -c "import importlib.metadata as m; print('built', m.version('dutchbay-epc-model'))"
```

## 4) Update the changelog

Move the `## [Unreleased]` items in `CHANGELOG.md` under a new dated heading:
`## v<version> - YYYY-MM-DD`.

## 5) Tag & push

```bash
VERSION=$(cat VERSION)
git add VERSION pyproject.toml CHANGELOG.md
git commit -m "chore(release): v${VERSION}"
git tag -s "v${VERSION}" -m "DutchBay ${VERSION}"
git push origin main "v${VERSION}"
```

## 6) GitHub Actions

- The `release-run.yml` workflow runs on the pushed tag and creates a Release with the
  artifact `DutchBay_Model_V<version>.zip`.
- If CI fails, fix, bump the patch (e.g. `15.0.1`), and retag.

## Notes

- `VERSION` is the single source of truth for the release number; keep
  `pyproject.toml [project].version` in sync with it.
- Runtime installs use `requirements.lock` or `constraints.txt` per environment policy.
- Dev installs keep `-e .[dev,test]` so local and CI behave the same.
