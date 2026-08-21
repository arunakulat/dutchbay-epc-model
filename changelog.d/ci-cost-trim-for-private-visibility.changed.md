Removed the post-merge `push: main` duplication from the Test Suite and docker-build workflows,
and reduced the full-suite backstop from nightly to weekly. The ruleset enforces
`strict_required_status_checks_policy`, so a PR validates a tree byte-identical to the one that
lands and the post-merge re-run tested nothing new. Post-merge health on main is still covered by
`CI - v14 fastlane` and `Regression Smoke` (~5 minutes combined, against ~63 for the full suite).
All three required checks — `Test Summary`, `fastlane`, `smoke` — still run on every PR.
