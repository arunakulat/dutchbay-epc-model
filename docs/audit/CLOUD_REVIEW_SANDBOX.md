# Independent cloud review sandbox for P02 and P03

## Purpose and authority boundary

This Codespaces configuration creates one reusable, private external execution
environment for the independent P02 findings review and the subsequent P03
primary-source review. It is infrastructure only. A successful bootstrap,
structural test or retained-object hash check does **not** complete either gate,
upgrade a finding or claim, authorize republication, lift release `HOLD`, or
authorize Board/lender circulation.

The environment applies the current GWTF rules and the canonical frameworks:

- **CASPER — Clear API Surfaces with Predictable Error Responses:** setup and
  verification fail loudly at their public shell surfaces and emit concise,
  value-free receipts.
- **CESSPIT — Config Explicit, Schema Strict, Pre-flight Integrity Tests:** the
  image digest, Python line, environment path and private source root are
  explicit; the existing strict P02/P03 validators remain authoritative.
- **CCCDIR — Contracts Centralized, Compliance Documented, Import Relationships
  explicit:** the sandbox calls the repository's existing controlled builders,
  Hydra verifier and publication-pack validator instead of duplicating their
  contracts.

## Isolation and private-data controls

The container is built from a base image pinned by digest and declares one
repository-configured Dev Container Feature: `sshd` 1.1.0, locked to its exact
OCI digest. That Feature supplies the Codespaces-supported SSH entrypoint
integration. The base image itself carries separate embedded Dev Container
Feature metadata for `common-utils`, `git`, `node` and `python`; those inherited
contents are transitively bound by the base-image digest and disclosed
separately in the sandbox receipt.

GitHub CLI SSH and copy require a running SSH server for a custom image. A
checked-in Dockerfile therefore installs `lsof`, `openssh-client` and
`openssh-server` directly from the pinned base image's Debian-only package
source. All packages probed by the locked Feature are already installed before
Feature composition, so its package guard does not invoke the unrelated Yarn
source that broke the original create-time build. Host private keys are removed
in the same image-build layer and are
generated uniquely when the Codespace container is created; only public-key
fingerprints derived from those private keys enter the receipt, and each derived
public key must match its `.pub` sidecar. The reusable identity binds the exact
installed SSH transport package/architecture/status/version inventory, every
package-owned transport path and mode, the locked Feature entrypoint, the
controlled PAM and drop-in configuration, the
allowlist-validated effective SSH policy, and the host public-key fingerprints.
The attestor resolves that policy for the actual `vscode`/loopback connection,
including applicable `Match` rules, and requires the intended
`authorized_keys` file while rejecting key commands, trusted user CAs,
principal commands, user environment files, forced commands and chroots.
The same drop-in sets the four fixed, non-secret review environment values that
raw `gh codespace ssh` sessions require (`DUTCHBAY_VENV`,
`DUTCHBAY_P03_SOURCE_ROOT`, `PYTHONPATH` and `PATH`); the attestor binds their
effective `SetEnv` population, so the SSH review surface cannot silently lose or
redirect the governed runtime.

The GitHub control-plane identity check plus the authenticated Codespaces
tunnel is the operational endpoint-identity boundary for `gh codespace ssh` and
`gh codespace cp`. GitHub CLI connects the inner SSH client to a loopback tunnel
and disables client-side host authentication for that loopback endpoint. The
recorded host-key fingerprints therefore prove the daemon key-pair population
and provide post-connection continuity/attestation; they are not described as
a second client-side endpoint pin. The Actions lifecycle additionally exercises
a direct loopback SSH connection with a strict, ephemeral `known_hosts` pin to
falsify daemon authentication and key-pair defects, but that local-Docker check
does not substitute for the authenticated real-Codespaces candidate proof.
Package selection at initial image build remains a disclosed Debian-repository
trust boundary; a changed identity requires recreation and a new receipt. SSH
runs on port 2222 for the explicit `vscode` remote user, requires the
`publickey` authentication method, denies root, every alternative authentication
method and every forwarding class, and is not a publicly forwarded application
port. The locked Feature's root entrypoint starts the daemon through the
Codespaces-supported integration. The post-create bootstrap and post-start
lifecycle both invoke the same repository-owned, root-reexecuted and serialized
start control as fail-closed validation/restart paths. The start control writes a
runtime-only marker atomically only after a bounded loop receives the expected
`SSH-2.0-OpenSSH_` banner on `127.0.0.1:2222`. The post-create bootstrap starts
the control before audit setup, then requires both that exact marker and the same
listener-specific banner. A Codespaces lifecycle that delays the Feature
entrypoint therefore takes the explicit lifecycle-recovery path, while a real
start or banner failure still fails setup closed. The Python environment is rebuilt from the
repository's exact `requirements.txt`, `constraints.txt` and
`pyproject.toml` inputs at `/workspaces/.dutchbay-audit-review-venv`, outside the
checkout. The retained P03 corpus is copied only to
`/workspaces/.dutchbay-private/p03/sources`, also outside the checkout and with
owner-only directory permissions. The post-create bootstrap uses non-interactive
sudo only to assign the fixed `/workspaces` parent to `vscode`, immediately
asserts the exact owner/group/mode, and then materializes those two
out-of-checkout roots as the non-root reviewer user.

Do not commit, publish, upload as an Actions artifact, or copy retained source
objects back into the repository. Do not expose a source path, source name,
credential or source content in a PR, issue, externally shared receipt or
durable runtime log. The Codespace has no forwarded ports. Delete it after both
review-result dolphins have merged and their exact-head evidence has been
retained in the controlled pack.

## Creation and structural preflight

Before merge, prove the exact topic-branch SHA in a disposable, P03-empty real
Codespace:

```bash
scripts/prove_1110_candidate_codespace.sh \
  codex/1110-cloud-sandbox-runtime-fix \
  "$(git rev-parse HEAD)"
```

The candidate control accepts only a valid `codex/*` branch and full expected
SHA that exactly matches the remote branch. It creates a uniquely named
24-hour Codespace, verifies API repository/ref identity, exact remote HEAD, a
clean checkout, fixed environment, empty private-source root and SSH
attestation, exercises `gh codespace cp`, stops and resumes the Codespace,
re-attests after the post-start marker changes, emits a `HOLD`-side receipt and
deletes that exact no-P03 candidate. This is pre-merge infrastructure evidence
only; it is not the protected-main environment and cannot execute or close P02
or P03. Copy calls use remote expansion only for repository-owned, fixed
absolute destination paths; no user-provided remote expression is expanded.

After this configuration is protected-merged to current `main`, create a
creator-private Codespace attached to the public source repository:

```bash
DUTCHBAY_1110_REVIEW_CODESPACE_NAME="$(
  scripts/create_1110_cloud_review_codespace.sh
)" || exit 2
export DUTCHBAY_1110_REVIEW_CODESPACE_NAME
```

The wrapper deliberately omits `gh codespace create -s`: that option can request
SSH status before the locked Feature lifecycle settles. It first rejects a
same-display-name collision, creates the protected-`main` Codespace, then retries
the exact SSH banner/marker probe for at most five minutes. It prints the unique
Codespace name only after transport is ready, or fails with the unresolved name
so the disposable environment can be inspected or deleted. Preserve that exact
name in `DUTCHBAY_1110_REVIEW_CODESPACE_NAME`; the later private-ingress control
requires it, authenticates it against the exact repository and display name
before preflight and again before private copy, and never re-resolves a mutable
display name from a truncated list. A local create lock plus a post-create
all-page identity check prevents two local creators from silently succeeding;
cross-host creation remains outside that lock and therefore fails loud if the
post-create population is not exactly the one immutable name returned here.

Run the structural preflight inside the Codespace before reviewing P02:

```bash
set -euo pipefail
test "$(git branch --show-current)" = "main"
test -z "$(git status --porcelain)"
git fetch --prune origin
git switch --detach origin/main
test "$(git rev-parse HEAD)" = "$(git rev-parse refs/remotes/origin/main)"
scripts/verify_1110_cloud_review_sandbox.sh
```

The final JSON line must state `status=PASS`, `release_status=HOLD`, and
`completion_authorized=false`. Before the private corpus is copied, P03 must be
reported as not executed. The receipt binds the controlled publication manifest,
so later P02/P03 result artifacts are transitively bound through their manifest
entries without changing the reusable dependency environment.

## P02 independent review

Review issue #1161 and every row in
`registers/findings_current_state_overlay.v1.json`. The review is
population-exact: account for all 111 finding IDs, the five
implementation-delivered/review-pending mappings, the separate F5-02
external-evidence block, the remaining 105 not-reassessed/not-examined rows,
the F5 separation rule, the unsigned-tag exception and the hash-bound repository
history receipt.

Record the independent decision in a new additive result artifact on its own
dolphin branch. Do not edit the historical findings register, candidate plan,
candidate overlay or implementer self-check. A row may remain unresolved; it
must not be silently closed or upgraded.

## Reuse for P03

Only after the P02 result dolphin has protected-merged, use the checked ingress
wrapper to copy the separately retained corpus into the same creator-private
Codespace. The local source root remains an environment-only value and must not
be pasted into an issue, PR or receipt:

```bash
export DUTCHBAY_P03_CLOUD_INGRESS_AUTHORIZED=YES
scripts/upload_1110_p03_sources_to_codespace.sh
```

The wrapper rejects an unset, broad, aliased or symlinked local root; executes
the existing exact 74-object/hash verifier locally; resolves exactly one named
Codespace for this repository; verifies an empty fixed remote destination; and
copies only `original/`, `converted/`, both controlled source manifests and the
governed IEC query log.

Run the wrapper only from clean protected local `main`. It fetches but never
moves that protected branch; a stale local checkout fails and must be
synchronized through the normal protected workflow before retrying. If transfer
is interrupted after the remote destination becomes non-empty, delete and
recreate the disposable Codespace; do not improvise a recursive cleanup command.

GitHub Codespaces permits outbound internet access. No-forwarded-port settings
are inbound controls, not egress controls. The corpus upload therefore requires
the explicit authorization environment variable above, and the receipt records
the residual egress boundary. Dependencies are installed and
content-fingerprinted before upload; no further package or extension
installation is permitted after ingress. Reuse checks hash all installed
regular-file bytes and modes—including executable bytecode—with container
Python under `-S` before any venv code, `.pth` file or `sitecustomize` module can
execute. Every post-marker venv invocation suppresses new bytecode writes. This
is a content-bound reuse control, not a hash-complete external package lock: the
initial installation retains the repository's existing pinned-requirement and
public-index trust boundary. Use the CLI/SSH review surface only. Do not
describe this environment as no-egress or rely on repository visibility as a
confidentiality control.

The ingress wrapper performs the required currency step before copying: the
Codespace may begin clean on `main` or in the clean detached exact-main state
left by the P02 preflight. It then fetches and switches to detached exact
`origin/main` without moving the protected branch, and proves
`HEAD == origin/main`. Before retained-source transfer, it also exercises SSH
and copies a non-sensitive controlled file into a fixed owner-only directory,
compares it byte-for-byte, and removes it under both local and remote cleanup
traps. P03 therefore starts from the protected P02
merge and any intervening controlled updates, never from the older
sandbox-creation commit.

The bootstrap markers bind the initial dependency inputs, configured base-image
digest, full SSH transport identity and installed environment-content
fingerprint. The SSH identity includes the installed file surface, PAM policy,
complete runtime main/drop-in configuration population, effective configuration
and Codespace-unique host public keys. Construction attestation uses the fixed
loopback model; every authenticated SSH control then derives and validates the
actual `SSH_CONNECTION`/`SSH_CLIENT` tuple and requires its session-specific
identity digest to equal the construction marker. The Python
environment fingerprint covers
`pyvenv.cfg`, every regular file and symlink under the venv `bin/` launch
surface, and all site-packages content. The three Python launchers must resolve
to `/usr/local/bin/python3.12` from the digest-pinned image; that absolute
interpreter performs every pre-attestation check regardless of `PATH`. The
dependency identity includes the Dev Container Feature lock, Dockerfile,
repository-owned SSH installer, runtime host-key/start control and transport
attestor. The receipt distinguishes the one digest-resolved
`repository_configured_devcontainer_features` entry from the four inherited
`base_image_embedded_feature_metadata` entries. Before transfer, current-main
inputs and the live environment must reproduce those markers. Any dependency,
bootstrap, identity-contract, devcontainer, base-image, SSH or
environment-content drift fails before ingress and requires deletion/recreation
of the disposable Codespace.

Receipts distinguish `github_codespaces` from
`github_actions_devcontainer_emulation` and bind the corresponding network
boundary. The Actions emulation must never claim the creator-private
Codespaces boundary; neither execution-host mode authorizes completion or
changes the release status from `HOLD`.

The in-container host field is a provenance label, not independent proof of a
GitHub resource: the `vscode` owner can replace its own private receipt. Real
Codespaces evidence is authoritative only through the outer governed controls,
which authenticate with GitHub, verify exact name/repository/ref, pass that
name into the SSH child, and require it to equal the platform `CODESPACE_NAME`
captured in the atomic bootstrap receipt. GitHub's non-interactive SSH shell is
not assumed to re-export that platform variable.
The hosted oracle supplies and asserts its separate explicit Actions label.

The bootstrap writes that provenance atomically to the fixed owner-only path
`/workspaces/.dutchbay-private/bootstrap-receipt.json`. Hosted CI asserts the
Actions host, network boundary and exact candidate SHA from that receipt. The
protected verifier and disposable real-Codespaces proof require the Codespaces
host and creator-private boundary from the same receipt. A disposable proof
emits PASS only after the exact named Codespace is deleted, its absence is
confirmed through the Codespaces API, and the local creation lock is released.
Its `DB1110-<12-SHA>-<16-hex nonce>` display name is unique to one local run
while remaining below GitHub Codespaces' 48-character limit; the full SHA is
still verified independently through the remote ref and checkout controls.
Initial readiness first proves the repository-owned SSH marker under a bounded
transport deadline, then waits separately for the atomically published
bootstrap receipt under a bounded first-install deadline. The two-stage check
prevents transport availability from racing ahead of dependency installation,
environment attestation or receipt binding while preserving accurate failure
diagnostics. The disposable proof also allows a separately bounded five-minute
GitHub shutdown transition before exercising restart recovery.

The bootstrap commit identifies environment construction, not an immutable
review checkout. Reusing the same governed Codespace after a P02 result merge is
allowed only when the live dependency and environment markers still reproduce;
the later verification receipt binds the new clean exact `origin/main` commit.
The disposable pre-merge candidate is different: its outer control requires the
bootstrap commit itself to equal the exact topic-branch SHA.

Re-run `scripts/verify_1110_cloud_review_sandbox.sh`. It must independently hash
all 74 retained objects before semantic review begins. Then follow issue #1162
and review all 42 claims, all source locations, limitations, evidence-status
boundaries and publication/redistribution rights. PSR-0009 remains analyst
judgment, PSR-0005 retains its unavailable transaction-evidence boundary, and
PSR-0012 retains its internal-evidence limitation unless authenticated new
evidence supports an additive change.

The P03 decision is a separate additive result dolphin. Structural or hash PASS
does not establish semantic support, publication rights, lender acceptance,
transaction evidence, bankability or release approval.

## Retirement

Stop and delete the Codespace only after the P02 and P03 result PRs are both
verified merged, their branches are current at merge, their result hashes are
bound into the controlled pack, and no reviewer still owns the environment.
Retirement of the sandbox does not retire the retained source archive.
