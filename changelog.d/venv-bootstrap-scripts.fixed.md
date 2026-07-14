- **Developer venv bootstrap scripts corrected.** `setup_venv.sh` created a `venv/`
  directory (the project uses `.venv`), gated Python 3.9 (the project requires 3.11), and
  carried a stale "V13"/Desktop-path header; it now targets `.venv`, requires 3.11+, installs
  the `[dev]` toolchain to match `make setup`, and prints `.venv` activation instructions.
  `check_venv.sh` required the retired `pytest.ini` file as a repo-root marker (so it always
  failed the "does not look like the repo root" check) and targeted the nonexistent `.venv311`;
  it now checks `pyproject.toml` + `VERSION` and targets `.venv`. Tooling only; no engine or
  financial behaviour changed.
