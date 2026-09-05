"""CESSPIT guard: the NSO 250 MW evidence corpus must agree with its own manifests.

Two classes of defect motivate this guard, and neither is hypothetical — between #1226 and
#1234 four manifest defects reached ``main`` unnoticed, because **no test covered either
corpus manifest**.

1. **The manifest and the tree disagree.**

   ``sha256sum -c`` is only half a gate. It walks the *recorded* entries and checks each one
   is present and hashes as recorded; it is structurally blind to the opposite direction, a
   file that is tracked in git but absent from the manifest. At commit ``782c958`` the corpus
   held **119 recorded / 130 tracked / 11 unrecorded**, and ``sha256sum -c`` returned
   ``119/119 OK``, exit 0. A green check on a corpus missing eleven files is worse than no
   check, so this module runs the gate in **both** directions.

   The related coupling: the parent manifest pins the SHA-256 of each nested manifest, so any
   edit to a nested file invalidates the parent unless the same commit refreshes it. That
   broke twice on one branch, the second time reporting ``FAILED`` on a *present* file —
   which in an evidence corpus is the signal reserved for content having been altered.

2. **One fact, restated in five places, drifting apart.**

   How the 3/4 September commercial offer package is handled — where the documents live, what
   this public repository does and does not disclose about them, and on whose authority — was
   written out in five places at once. The five copies disagreed, and *every* blocking finding
   of two ``RECRUIT-01`` reviews was one of the disagreements. The statement now lives once, in
   the offers manifest header under ``NSO250MW-OFFERS-HANDLING-2026-09-04``; the READMEs and
   the changelog fragment cite that identifier. A sixth copy, a stale citation, or clause 6 of
   the offers quoted anywhere but its single home fails here rather than in a third review.

**Where this runs, and why it matters.** The corpus is docs-only by path, and ``test-suite.yml``
skips its pytest shard entirely for docs-only PRs — while every manifest defect that reached
``main`` arrived on a docs-only PR. So this module is wired into the ``fastlane`` job of
``ci_v14_fastlane.yml``, the one lane that runs unconditionally on every pull request, and not
only into the sharded suite. Move it and it stops running on exactly the changes it exists to
catch.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS = REPO_ROOT / "docs" / "source_materials" / "nso_bess_250mw_2026"
PARENT_MANIFEST = CORPUS / "MANIFEST.sha256"
PACKAGES = CORPUS / "source_packages"
OFFERS_MANIFEST = PACKAGES / "NSO250MW_Commercial_Offers_2026-09-03.MANIFEST.sha256"

# Which manifests record files that live in this repository, and which record files held
# outside it. Declared rather than inferred: inferring "external" from "the file is missing"
# would make a genuinely missing file indistinguishable from a by-design absent one, which is
# the whole defect this module exists to catch.
IN_REPO_MANIFESTS: dict[Path, Path] = {
    # manifest -> the directory its recorded paths are relative to
    PARENT_MANIFEST: CORPUS,
    PACKAGES / "NSO250MW_oem_supply_2026-08-27.MANIFEST.sha256": PACKAGES,
}
EXTERNAL_MANIFESTS: tuple[Path, ...] = (
    # The 21 August checklist dossier: binaries held in the owner's private working set.
    PACKAGES / "NSO250MW_checklist_2026-08-21.MANIFEST.sha256",
    # The commercial offers: held in the private DutchBay_RAG corpus. Their recorded paths are
    # relative to a root that does not exist here, so they are never resolved against this tree.
    OFFERS_MANIFEST,
)

# The one place the offer package's handling is stated, and the files that must cite it
# instead of restating it.
HANDLING_ANCHOR = "NSO250MW-OFFERS-HANDLING-2026-09-04"
HANDLING_REFERRERS: tuple[Path, ...] = (
    CORPUS / "README.md",
    PACKAGES / "README.md",
    REPO_ROOT / "changelog.d" / "nso-commercial-offer-resupply.fixed.md",
)

# Distinctive spans of clause 6 of the Envision offers. The clause is quoted verbatim in the
# offers manifest and must not be reproduced anywhere else in this public repository — the
# clause is the very thing that forbids third-party communication of the offer.
CLAUSE_SIX_SPANS: tuple[str, ...] = (
    "The offer is confidential thus shall be used",
    "more generally, communicated to any third party",
    "prior, explicit and written authorization",
)


def _entries(manifest: Path) -> dict[str, str]:
    """Parse a ``sha256sum``-format manifest into {path: digest}, ignoring comments."""
    entries: dict[str, str] = {}
    for lineno, raw in enumerate(
        manifest.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        digest, separator, path = line.partition("  ")
        assert separator, f"{manifest.name}:{lineno}: not a sha256sum entry: {raw!r}"
        assert len(digest) == 64 and not set(digest) - set("0123456789abcdef"), (
            f"{manifest.name}:{lineno}: malformed digest {digest!r}"
        )
        assert path not in entries, (
            f"{manifest.name}:{lineno}: duplicate entry for {path}"
        )
        entries[path] = digest
    return entries


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tracked_under(directory: Path) -> set[str]:
    """Paths git tracks under ``directory``, relative to it."""
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--", str(directory)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    tracked = {entry for entry in listing.split("\0") if entry}
    prefix = f"{directory.relative_to(REPO_ROOT).as_posix()}/"
    return {entry[len(prefix) :] for entry in tracked}


@pytest.mark.parametrize(
    "manifest", list(IN_REPO_MANIFESTS), ids=lambda path: path.name
)
def test_recorded_entries_are_present_and_hash_as_recorded(manifest: Path) -> None:
    """Direction 1 — every recorded entry exists and matches. This is ``sha256sum -c``."""
    base = IN_REPO_MANIFESTS[manifest]
    missing: list[str] = []
    altered: list[str] = []

    for path, digest in _entries(manifest).items():
        resolved = (base / path).resolve()
        if not resolved.is_file():
            missing.append(path)
        elif _sha256(resolved) != digest:
            altered.append(path)

    assert not missing, (
        f"{manifest.name} records {len(missing)} file(s) that are not in the tree. An entry for "
        f"a path git cannot hold — anything under a gitignored directory, for instance — is "
        f"permanently unsatisfiable and must be removed, not re-hashed: {sorted(missing)}"
    )
    assert not altered, (
        f"{manifest.name} records a different hash than the file now has, which in an evidence "
        f"corpus is the signal reserved for content having been altered. If the change is "
        f"intended, refresh the manifest in the SAME commit: {sorted(altered)}"
    )


def test_every_nested_manifest_is_classified() -> None:
    """No nested manifest may sit unclassified, silently skipped by both directions above.

    Adding a package manifest without deciding whether its subject lives in this repository is
    how a manifest ends up covered by nothing at all — which was the state of every manifest in
    this corpus until this module existed.
    """
    on_disk = {path.resolve() for path in PACKAGES.glob("*.MANIFEST.sha256")}
    declared = {path.resolve() for path in IN_REPO_MANIFESTS} | {
        path.resolve() for path in EXTERNAL_MANIFESTS
    }

    unclassified = sorted(
        path.relative_to(REPO_ROOT).as_posix() for path in on_disk - declared
    )
    vanished = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in declared - on_disk
        if PACKAGES in path.parents
    )

    assert not unclassified, (
        f"{unclassified} are nested manifests that this guard does not classify, so nothing "
        f"checks them. Add each to IN_REPO_MANIFESTS (its subject is committed here) or to "
        f"EXTERNAL_MANIFESTS (its subject is held elsewhere and recorded by hash only)."
    )
    assert not vanished, f"{vanished} are declared here but no longer on disk."


def test_every_tracked_corpus_file_is_recorded() -> None:
    """Direction 2 — the blind spot. ``sha256sum -c`` never looks this way.

    A file added to the corpus but not recorded leaves the manifest an incomplete index of the
    evidence, and every ``-c`` run stays green while it does.
    """
    recorded = set(_entries(PARENT_MANIFEST))
    tracked = _tracked_under(CORPUS)
    # A manifest cannot record its own hash; nothing else is exempt.
    unrecorded = tracked - recorded - {PARENT_MANIFEST.name}

    assert not unrecorded, (
        f"{len(unrecorded)} file(s) are tracked under {CORPUS.relative_to(REPO_ROOT)} but absent "
        f"from MANIFEST.sha256. `sha256sum -c` passes on this state — it only walks recorded "
        f"entries — so nothing else will tell you. Add them with "
        f"scripts/analysis/refresh_corpus_manifest.py: {sorted(unrecorded)}"
    )


def test_nested_manifest_parent_pins_are_current() -> None:
    """The coupling that broke twice: the parent pins each nested manifest by hash.

    Editing a nested manifest invalidates the parent's pin. Refresh the parent **last**, after
    every nested edit, in the same commit.
    """
    recorded = _entries(PARENT_MANIFEST)
    stale: list[str] = []

    for nested in sorted(PACKAGES.glob("*.MANIFEST.sha256")):
        key = nested.relative_to(CORPUS).as_posix()
        assert key in recorded, (
            f"the parent manifest does not pin nested manifest {key}"
        )
        if recorded[key] != _sha256(nested):
            stale.append(key)

    assert not stale, (
        f"the parent manifest's pin is stale for {stale}. A nested manifest was edited without "
        f"refreshing the parent in the same commit, so `sha256sum -c` now reports FAILED on a "
        f"file that is present and correct."
    )


def test_offer_handling_is_stated_once() -> None:
    """The handling statement is defined in one place and cited, never restated, elsewhere."""
    manifest_text = OFFERS_MANIFEST.read_text(encoding="utf-8")

    assert f"HANDLING NOTE — {HANDLING_ANCHOR}" in manifest_text, (
        f"the offers manifest no longer defines the handling note under {HANDLING_ANCHOR}. Every "
        f"referrer points at that identifier; moving or renaming it orphans all of them."
    )

    orphaned = [
        referrer.relative_to(REPO_ROOT).as_posix()
        for referrer in HANDLING_REFERRERS
        if HANDLING_ANCHOR not in referrer.read_text(encoding="utf-8")
    ]
    assert not orphaned, (
        f"{orphaned} describe the offer package but no longer cite {HANDLING_ANCHOR}. Cite the "
        f"identifier; do not restate what it says. Five copies of this statement disagreed with "
        f"each other on 4 September 2026, and that is what these files are pointing at instead."
    )


def test_clause_six_is_quoted_in_exactly_one_file() -> None:
    """Clause 6 is the confidentiality clause itself. It belongs in one place, or nowhere."""
    home = OFFERS_MANIFEST.relative_to(REPO_ROOT).as_posix()

    for span in CLAUSE_SIX_SPANS:
        found = subprocess.run(
            ["git", "grep", "--name-only", "--fixed-strings", span, "--", "."],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        # git grep exits 1 when there are no matches; that is not an error here.
        assert found.returncode in (0, 1), found.stderr
        elsewhere = sorted(set(found.stdout.split()) - {home})
        assert not elsewhere, (
            f"clause 6 of the Envision offers is reproduced outside {home}, in {elsewhere} "
            f"(span: {span!r}). The clause forbids communicating the offer to third parties, and "
            f"this repository is public. Paraphrase and cite {HANDLING_ANCHOR} instead. A review "
            f"record re-publishing what a fix removed is how this recurred last time."
        )
