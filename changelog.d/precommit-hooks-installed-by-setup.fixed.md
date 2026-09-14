Governed setup now installs the configured git pre-commit hooks, activating GOV-02's local
`no-commit-to-branch` defence and the formatting, lint, import-order and file checks.
Hooks live in `.git/hooks`, which git does not track, so a fresh clone has none
until installation; this repository was found on 2026-09-13 without a pre-commit hook.

The configured set does not include mypy even though R10 names it. This change does not
claim to close that mismatch; issue #1270 owns its governed resolution, while `make type`
and CI remain mandatory. `./setup_venv.sh` (and therefore `make setup`) installs the
configured set, `make hooks` safely handles an external environment path containing spaces,
and `DUTCHBAY_SKIP_HOOKS=1` explicitly opts out. Setup now fails closed if mandatory hook
installation fails. `tests/lint/test_precommit_hook_installation.py` pins those behaviours
and carries hostile negative controls; behavioral reachability remains tracked in #1262.
