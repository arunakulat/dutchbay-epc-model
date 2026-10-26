- The audit review image bootstrap (`.devcontainer/bootstrap_audit_review.sh`) no
  longer makes an editable install of the checkout. Since #1377 the environment
  contract sees that install and refuses it, so "build and boot audit review image"
  failed on every pull request that touched the dependency inputs. The checkout is
  imported from `PYTHONPATH`, which every sandbox entry point already sets. The
  job's path classifier now also runs it for changes to `dutchbay_environment.py`,
  `scripts/development_environment.sh` and `config/development_environment.json`,
  the files `check_venv.sh` executes. No runtime, financial formula, scenario, or
  KPI change.
