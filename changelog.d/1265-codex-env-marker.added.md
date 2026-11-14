- **test_codex_local_environment split bounded** — track bash `if`/`fi` depth when
  extracting `existing_branch` and `created_branch` in `setup_venv.sh` so downstream
  blocks (such as pre-commit hooks) do not leak into `created_branch` (#1265).
