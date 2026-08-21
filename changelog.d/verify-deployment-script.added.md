Added `scripts/verify_deployment.py` — verifies a running deployment from outside using only its
public health surface, so confirming what an instance actually has installed no longer requires
`flyctl` access to the machine. Checks liveness and contract version, that runtime-critical
config is present, and that every optional extra the image installs is present, satisfies its
declared pin and (with `--deep`) actually imports. Exits non-zero on failure so it works as a
post-deploy CI gate, and emits `--json` for machine consumption.
