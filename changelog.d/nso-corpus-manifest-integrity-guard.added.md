- **The NSO evidence corpus now has a test** — `tests/lint/test_nso_corpus_manifest_integrity.py`.
  Manifest defects have reached `main` in two classes because nothing covered either corpus
  manifest: an **incomplete** manifest across five commits from `637aad3` to `782c958`, closed at
  #1211, and one **impossible** entry introduced by #1226 and fixed by #1234. This repository's own
  session archive had recorded the gap twice without closing it.
- **It runs the gate in both directions, which `sha256sum -c` does not.** `-c` walks the *recorded*
  entries and checks each is present and hashes as recorded; it is structurally blind to a file
  that is tracked in git but absent from the manifest. At `782c958` the corpus held **119 recorded
  / 130 tracked / 11 unrecorded** and `sha256sum -c` returned `119/119 OK`, exit 0 — a green check
  on a corpus missing eleven files. The guard adds the tracked→recorded direction, the
  nested-manifest parent pin whose staleness reported `FAILED` on a *present* file twice on one
  branch, and a completeness check so a new nested manifest cannot sit unclassified and unchecked.
- **It is wired into `fastlane`, not the sharded suite.** `test-suite.yml` skips its pytest shard
  for PRs whose diff is only `*.md`, `changelog.d/` and `docs/` — and two of the six defective
  commits carried nothing else. A guard that skips on exactly the changes it exists to catch is not
  a guard, so it runs in the one lane that runs unconditionally on every PR. It costs about two
  seconds, roughly half of that pytest collection, and needs the `[dev]` install and git.
- **Every guard is proved against its own defect.** Each failure mode was reproduced in the working
  tree and confirmed to fail the corresponding assertion, then reverted — including the parent-pin
  guard, which caught a scripted revert that silently undid part of this change while it was being
  written.
- **The clause-6 guard caught itself, on its first CI run.** Its search terms were originally
  hard-coded, which made the test file a second copy of the clause in a public repository — the
  exact thing it forbids. It passed locally only because the file was still untracked and `git
  grep` could not see it. The terms are now **read out of the manifest at run time**, so no copy
  exists to drift, and a liveness assertion requires each derived span to match its own source:
  a malformed search term fails loudly instead of matching nothing and passing.
