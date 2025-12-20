# GWTF R25 Compliance Scripts

Prevention scripts for GWTF R25 (Branch Protection) violations.

## Background

See: `GWTF_R25_VIOLATION_REPORT.md` in repository root.

Due to GitHub limitations on private single-user repos, branch protection cannot be technically enforced. These scripts provide **discipline-based prevention** through automated checks and reminders.

## Scripts

### 1. Pre-Flight Checklist (`gwtf-preflight.sh`)

**Usage**: Run before ANY git merge, pull, or push operation

bash scripts/gwtf-preflight.sh

Or use alias:
gpf

text

**What it checks**:
- Current branch (warns if on main)
- GWTF R25 requirements reminder
- Uncommitted changes
- Unpushed commits
- Requires confirmation before proceeding

**When to use**: Before EVERY git push/pull/merge

### 2. Daily Audit (`gwtf-daily-audit.sh`)

**Usage**: Run at end of each work session

bash scripts/gwtf-daily-audit.sh

Or use alias:
gaud

text

**What it checks**:
- Direct commits to main today
- GWTF R25 overrides logged today
- Current branch status
- Unpushed commits on feature branch

**When to use**: End of day, before shutting down

### 3. Pre-Push Hook (`.git/hooks/pre-push`)

**Automatic**: Runs every time you `git push`

**What it does**:
- Warns loudly if pushing to main
- Requires typing "GWTF-R25-OVERRIDE" to proceed
- Logs all overrides to `.gwtf-overrides.log`
- Cannot block (repo owner limitation), but makes violations deliberate

## Aliases

Added to `~/.zshrc` (or `~/.bashrc`):

- `gpf` - Run pre-flight checklist
- `gaud` - Run daily audit
- `gfeature` - Switch to feature branch
- `gpush` - Push with pre-flight check

## Workflow

### Daily Routine

**Morning**:
gfeature # Switch to feature branch
git pull origin feature/add-finance-contracts-pydantic-v2-20251219

text

**Before any git operation**:
gpf && git push origin <branch>

text

**End of day**:
gaud # Run audit

text

### Weekly Review (Saturday)

Check override log
cat .gwtf-overrides.log

Check main commits last 7 days
git log main --since="7 days ago" --oneline

text

## Emergency Override

If you absolutely must push to main (emergency only):

1. Pre-push hook will warn
2. Type: `GWTF-R25-OVERRIDE`
3. Override is logged to `.gwtf-overrides.log`
4. Document in `GWTF_R25_VIOLATION_REPORT.md` within 24 hours

## Files Created

- `scripts/gwtf-preflight.sh` - Pre-flight checklist
- `scripts/gwtf-daily-audit.sh` - Daily audit
- `.git/hooks/pre-push` - Pre-push hook (not committed)
- `.gwtf-overrides.log` - Override log (gitignored, not committed)

## Key Principle

**DISCIPLINE** - Scripts help, but cannot enforce. Must build habit of:
1. Always working on feature branch
2. Running pre-flight before push
3. Merging to main ONLY via PR
4. Daily audit review
