- **`constraints.txt` documentation contradiction fixed.** `RELEASING.md` and the `Makefile`
  `lock` comment both asserted that `constraints.txt` was "retired", but it is the active
  freeze-policy caps file (#756) whose own header documents the `PIP_CONSTRAINT=constraints.txt`
  regeneration recipe. The wording is corrected, and `make lock` now applies
  `PIP_CONSTRAINT=constraints.txt` so a regenerated `requirements.txt` respects the gate-cleared
  version caps (pandas<3, mypy==1.19.0, isort<8, ruff<0.15, black<27, ...) instead of producing
  an unconstrained lock. Tooling/docs only; no engine or financial behaviour changed.
