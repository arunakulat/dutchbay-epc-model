Fixed two environment-sensitive failures in `tests/lint/test_cloud_audit_review_sandbox.py`. Neither
was a defect in the code under test: the create wrapper's transport watchdog and the sandbox identity
controls both behave correctly.

The watchdog test probed the hung child with `os.kill(pid, 0)`, which **succeeds for a zombie** —
a PID stays in the process table until its parent reaps it. The wrapper does escalate SIGTERM to
SIGKILL correctly, but where PID 1 does not reap orphans promptly (the common container case) the
correctly-killed child lingers as `Z`/defunct and the probe read it as alive. The probe now reads the
process state from `/proc`, treating a killed-but-unreaped process as dead, and falls back to the
signal probe where `/proc` is unavailable. Verified the test still fails when the SIGKILL escalation
is removed from the script, so the control keeps its teeth.

The sshd policy test shelled out to `ssh-keygen` as an independent oracle corroborating the
repository's own rejection of a malformed host key. That binary ships in the sandbox image but is not
guaranteed on the machine running the lint suite, where its absence raised `FileNotFoundError`
instead of returning non-zero. The cross-check is now guarded on availability; the repository-owned
validation is asserted unconditionally as before.
