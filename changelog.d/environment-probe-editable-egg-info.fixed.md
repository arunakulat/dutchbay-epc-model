- The environment probe behind `./check_venv.sh` now reads the project's install record from
  the selected environment only. A git-ignored `dutchbay_epc_model.egg-info` in the checkout
  root sits first on the probe's `sys.path` and carries no `direct_url.json`, so it hid an
  editable install and the probe reported `"editable_project_install": false` with PASS
  (#1376). The environment may live inside the checkout (the portable `.venv`), so only
  paths under the checkout and outside `sys.prefix` are skipped.
- The Claude Code cloud SessionStart hook no longer runs `pip install -e`. It installs the
  dependencies of the selected extras, imports the checkout through `PYTHONPATH` as the
  shared environment does, and removes an editable install left by an earlier version of
  the hook. The owner's shared environment was never affected.
