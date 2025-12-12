# Releasing DutchBay Model — v13.1.0

This guide locks dependencies, runs full QA, tags, and produces a GitHub Release with an artifact zip.

## 1) Ensure clean state
```bash
git checkout main
git pull --rebase
make setup
make lint type security test cov
```

## 2) Freeze/lock deps (deterministic deployments)
```bash
make freeze   # writes constraints.txt from your current env
make lock     # writes requirements.lock for CI/Prod
git add constraints.txt requirements.lock
git commit -m "chore(lock): freeze dependencies for v13.1.0"
```

## 3) Bump version
- Update `VERSION` file to `13.1.0` (already included in this kit).

## 4) Tag & push
```bash
git add VERSION
git commit -m "chore(release): v13.1.0"
git tag -s v13.1.0 -m "DutchBay 13.1.0"
git push origin main --tags
```

## 5) GitHub Actions
- CI will run on the tag and create a Release with the artifact: `DutchBay_Model_V13.1.0.zip`.
- If CI fails, fix, bump to 13.1.1, and retag.

## Notes
- Runtime installs use `requirements.lock` or `constraints.txt` per environment policy.
- Dev installs keep `-e .[dev,test]` so local/CI behave the same.
