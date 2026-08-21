- **`.envrc` no longer activates a retired environment** — it sourced
  `~/.venvs/dutchbay-epc-model-venv311/bin/activate`, a path that does not exist on any
  host and a `.venv311` name THREAD-01 and R21 prohibit, so `direnv` either failed or
  bound a `cd` to an ungoverned Python 3.11 tree. It now resolves, validates, and
  activates through `scripts/development_environment.sh` — the same config-first contract
  `check_venv.sh` and `scripts/venv_up.sh` use — and deliberately does **not** provision:
  entering a directory must never create a checkout-local `.venv` in place of the
  persistent `DUTCHBAY_VENV` environment. A lint guard keeps it on the contract.
