- Stop two ordinary-suite controls for `scripts/prove_1110_candidate_codespace.sh` from
  racing on the machine-global `/tmp/dutchbay-1110-candidate-codespace.lock`. One test
  reaches `mkdir -- "$CREATE_LOCK"` and legitimately holds the lock while the other
  asserts it is absent, so under `-n auto` the observer failed for a reason unrelated to
  the code under test. Both now drive a copy of the control bound to a per-test lock,
  keeping every behavioural assertion exact and removing the shared path from the suite.
