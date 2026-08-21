- **`Test Summary` no longer blames the wrong gate for a superseded run** — the
  required check hardcoded a failure cause per job, so a `lint` job *cancelled* by a
  newer push reported itself as `mypy gate failed`. A cause is now attributed only
  when the result is actually `failure`; `cancelled`/`skipped` say so and name the
  usual reason. Which results block the merge is unchanged.
