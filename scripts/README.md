# GWTF R25 Compliance Scripts

Prevention scripts for GWTF R25 (Branch Protection) violations.

See: `GWTF_R25_VIOLATION_REPORT.md` in repository root.

## Scripts

### Pre-Flight Checklist (`gwtf-preflight.sh`)
Run before ANY git merge, pull, or push operation.

### Daily Audit (`gwtf-daily-audit.sh`)
Run at end of each work session.

## Usage

Pre-flight
bash scripts/gwtf-preflight.sh

Daily audit
bash scripts/gwtf-daily-audit.sh

text

## Aliases

Add to your shell config (~/.zshrc or ~/.bashrc):

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
alias gpf='bash $REPO_ROOT/scripts/gwtf-preflight.sh'
alias gaud='bash $REPO_ROOT/scripts/gwtf-daily-audit.sh'
alias gfeature='git checkout feature/add-finance-contracts-pydantic-v2-20251219'

text
