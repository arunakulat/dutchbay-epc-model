Governed setup now installs the git pre-commit hooks, so `R10` and `GOV-02` stop claiming
enforcement that does not exist.

Both rules describe the hook set as local enforcement that runs automatically on commit —
`R10` says failed hooks prevent the commit, and `GOV-02` relies on `no-commit-to-branch`
blocking a commit on `main` *before* the confusing push-time ruleset rejection. Hooks live
in `.git/hooks`, which git does not track, so a fresh clone has none and both claims are
silently false until someone runs the install by hand. Until now that install existed only
as a line in `docs/DEVELOPMENT.md`. This repository was found on 2026-09-13 with no
pre-commit hook installed at all.

`./setup_venv.sh` (and therefore `make setup`) now installs the hooks, `make hooks` restores
them in an existing checkout without a full environment reconcile, and `DUTCHBAY_SKIP_HOOKS=1`
opts out. A failure is reported loudly rather than swallowed. `tests/lint/test_precommit_hook_installation.py`
pins the setup path and ships negative controls; it deliberately does not assert that a hook
is installed on the running host, because CI legitimately has none.
