# R23 Git Workflow - Quick Reference Card

**Print this. Keep it handy.** 🖨️

---

## 🚀 Your Current Status

```
✅ Branch:  feature/sprint12-monte-carlo
✅ Status:  Ready for development
✅ Base:    main (commit 3886d9e1d024)
✅ Rule:    R23 (Branch-based development with full CI gate)
```

---

## 📋 The R23 Workflow (4 Steps)

### Step 1️⃣: Develop Locally

```bash
# Edit code
vim finance/refinancing_v14_hydra.py

# Test (repeat until ✅ green)
pytest tests/api/test_refinancing_v14.py --no-cov
mypy finance/refinancing_v14_hydra.py

# Commit (pre-commit hooks run automatically)
git add finance/refinancing_v14_hydra.py
git commit -m "feat: implement refinancing calculator

- Added class
- Tests: 8 green
- Mypy: clean"
```

### Step 2️⃣: Push to Feature Branch

```bash
git push origin feature/sprint12-monte-carlo
```

### Step 3️⃣: Wait for CI (GitHub Actions)

```
⏳ Waiting...
✅ pytest: PASS
✅ mypy: PASS
✅ linting: PASS
✅ Ready to merge
```

### Step 4️⃣: Merge, Cleanup, Sync

```bash
# Merge on GitHub (click "Merge pull request")
# Then locally:

git branch -d feature/sprint12-monte-carlo
git push origin --delete feature/sprint12-monte-carlo
git pull origin main
pytest tests/api/ --no-cov -q  # Sanity check
```

---

## ✅ Before Every Commit

```bash
Checklist:
☐ Code written
☐ pytest green: pytest tests/api/test_*.py --no-cov
☐ mypy clean:   mypy finance/
☐ Ready to commit
```

---

## 💬 Commit Message Template (R18)

```
type: brief summary (50 chars max)

Optional body explaining WHY and test status.

Issue: #42
Tests: 8 passing
Mypy: clean
```

**Types:** `feat`, `fix`, `chore`, `docs`, `test`, `refactor`

---

## ❌ Never Do This

```bash
❌ git commit directly to main
   → Branch protection blocks it

❌ git push without pytest ✅
   → CI will fail

❌ git push --force
   → Breaks history

❌ Merge without CI passing
   → GitHub blocks merge button

❌ Leave branches orphaned
   → Git cleanup required later
```

---

## ✅ Always Do This

```bash
✅ git checkout -b feature/name
   → Branch first

✅ pytest && mypy .
   → Test before pushing

✅ Descriptive commit messages (R18)
   → Clear history

✅ Wait for CI
   → GitHub must pass

✅ Delete branch after merge
   → Keep repo clean

✅ git pull origin main
   → Sync after merge
```

---

## 🔍 Troubleshooting

### Pytest fails
```bash
rm -rf .pytest_cache __pycache__ .mypy_cache
pip install -e . --force-reinstall
pytest
```

### Mypy complains
```bash
# Add type hints:
def func(x: int) -> str:
    return str(x)

mypy .
```

### Pre-commit fails
```bash
black .
ruff check --fix .
isort .
git add . && git commit -m "chore: auto-format"
```

### Can't push
```bash
git branch  # Verify you're on feature/...
git remote -v  # Verify origin points to repo
git push origin feature/sprint12-monte-carlo
```

---

## 📊 Time Estimates

| Phase | Time | What |
|-------|------|------|
| Setup | 5 min | Branch + bootstrap |
| Development | Variable | Code + test locally |
| Commit & Push | 2 min | git commit + push |
| CI Wait | 2-5 min | GitHub runs tests |
| Merge | 1 min | Click merge on GitHub |
| Cleanup | 2 min | Delete branch + sync |
| **Total per feature** | **~20 min** | Including CI wait |

---

## 📚 Reference

**Full Guide:**
- `SPRINT_12_R23_WORKFLOW_GUIDE.md` (comprehensive)
- `SPRINT_12_R23_STATUS.md` (status & checklist)

**Rules:**
- `go_with_the_flow_rules_v3_0_clean.csv` (all rules R1-R23)

**Your Branch:**
- `feature/sprint12-monte-carlo` (current)

---

## 🎯 Your Mission

**Implement:**
1. Refinancing module
2. Equity distribution module
3. Monte Carlo engine
4. Stress testing suite
5. Pipeline CLI

**Follow R23 workflow for EVERY commit**

**Deliver production-grade code**

---

## 💡 Pro Tips

1. **Test frequently:** Don't wait until end to test
2. **Small commits:** One feature per PR = easier review
3. **Descriptive messages:** Future you will thank present you
4. **Read error messages:** CI output tells you what to fix
5. **Sync early:** `git pull origin main` before starting new feature

---

## ✅ Ready?

```bash
cd DutchBay_EPC_Model
source .venv311/bin/activate
vim finance/refinancing_v14_hydra.py
# Start coding! Follow R23 for every commit.
```

---

**Rule:** R23 ✅  
**Status:** 🟢 READY  
**Command:** `pytest && mypy .`
