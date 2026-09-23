- Extend the governed environment health contract to compare every pin in
  `requirements.txt` against what the selected environment actually has installed.
  The contract previously asserted only that the seven distributions named in
  `config/development_environment.json` were present, so a drifted environment still
  reported `Environment validation PASS`: of the lock's 311 pins only nine carried a
  version assertion anywhere under `tests/`, leaving the rest to drift unseen.
  A version disagreement is now fatal for any locked distribution and names the
  remedy (`./setup_venv.sh`); a locked distribution that is merely absent stays fatal
  only for the required set and is otherwise recorded in the receipt, because which
  optional extras a host must carry is owned by the guards at the point of use.
