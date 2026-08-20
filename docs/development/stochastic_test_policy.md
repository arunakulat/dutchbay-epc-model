# Stochastic pytest policy

## Outcome

The ordinary full pytest suite is bounded to at most 200 effective Monte Carlo
model evaluations per test. This keeps the regression and coverage gate useful
without silently running production-scale stochastic work on every branch.

The policy is controlled by
`config/stochastic_test_policy.yaml` and enforced by `tests/conftest.py`.

## Test modes

| Mode | Command | Model-evaluation policy | Permitted claim |
| --- | --- | --- | --- |
| Fast | `pytest <focused paths>` | 20 recommended; 200 hard maximum | Focused development feedback |
| Full | `make test` | 200 hard maximum | Regression and coverage only |
| Qualification | `make test-stochastic-qualification` | Explicit counts above 200 allowed only in marked tests | Scale or qualification evidence subject to a separate governed receipt |

`stochastic_qualification` tests are skipped in fast and full modes. In
qualification mode, unmarked tests are skipped so an uncapped session cannot
silently turn into an ordinary full-suite run.

The GitHub Actions regression, FX, release, and sharded full-suite workflows
select `DUTCHBAY_TEST_MODE=full`. Nightly/manual Test Suite runs and tagged
release runs execute the separately named stochastic qualification target.
Every GitHub Actions Python test interpreter is pinned to Python 3.12; an
executable structural guard resolves both direct `setup-python` values and
matrix-backed values so another interpreter cannot be added silently.

The cap applies to effective model or finance-pipeline executions. It includes
Sobol rounding: for example, a request for 129 Sobol trials evaluates 256
points and is therefore refused in an ordinary run. Pure vector/statistical
unit checks may use arrays larger than 200 when they do not execute the model.

## Evidence boundary

Two hundred model evaluations are not evidence of Monte Carlo convergence,
tail adequacy, bankability, or lender readiness. The ordinary suite does not
change production scenario defaults, the lender-grade minimum-trial guard, or
the governed run configuration.

A qualification run that supports an external claim must retain a concise
structured receipt containing, at minimum, the requested and effective trial
counts, explicit seed, resolved-config SHA-256, Git SHA, result SHA-256, and
limitations. Raw per-trial diagnostic logs remain ephemeral under the runtime
logging policy.
