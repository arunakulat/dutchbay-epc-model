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
catch. Both workflows must keep the same ``pull_request`` branch list, or the gap reopens on
whichever branch only one of them covers.
"""

from __future__ import annotations

import hashlib
import re
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

# Files that live in the corpus tree but are not themselves evidence, so the manifest does not
# record them. Declared rather than special-cased, for the same reason the classification above
# is: an undeclared exception turns fastlane red with no supported way to express it.
NOT_EVIDENCE: frozenset[str] = frozenset(
    {
        "MANIFEST.sha256",  # a manifest cannot record its own hash
    }
)

# The one place the offer package's handling is stated, and the files that must cite it
# instead of restating it.
HANDLING_ANCHOR = "NSO250MW-OFFERS-HANDLING-2026-09-04"
HANDLING_REFERRERS: tuple[Path, ...] = (
    CORPUS / "README.md",
    PACKAGES / "README.md",
    REPO_ROOT / "changelog.d" / "nso-commercial-offer-resupply.fixed.md",
)

# The manifest header line that opens the verbatim quotation of clause 6, and the shortest
# span worth searching for. The spans themselves are READ OUT OF THE MANIFEST at run time and
# are deliberately NOT written here: a literal copy in this file would itself be a second copy
# of the clause in a public repository, which is precisely what this module exists to forbid.
# CI caught exactly that on the first run of this guard, when the spans were hard-coded.
CLAUSE_SIX_HEADING = "3. CLAUSE 6, VERBATIM."
MIN_SPAN_CHARS = 30


# One ``sha256sum`` output line: 64 hex digits, two spaces (text mode) or a space and an
# asterisk (binary mode, ``sha256sum -b``), then the path. Both forms, and upper-case digests,
# are accepted by ``sha256sum -c``, so rejecting them here would fail a manifest the tool
# itself verifies — a false positive that would turn fastlane red with a misleading diagnosis
# after any regeneration with ``-b``.
ENTRY = re.compile(r"([0-9a-fA-F]{64}) [ *](.*)")


def _entries(manifest: Path) -> dict[str, str]:
    """Parse a ``sha256sum``-format manifest into {path: digest}, ignoring comments."""
    entries: dict[str, str] = {}
    text = manifest.read_text(encoding="utf-8").lstrip("\ufeff")
    for lineno, raw in enumerate(text.splitlines(), start=1):
        # splitlines() has already removed the terminator. Do NOT strip beyond that: a path
        # with trailing whitespace would be silently rewritten into a different path, and the
        # guard would then hash a file the manifest does not name.
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        match = ENTRY.fullmatch(raw)
        assert match, f"{manifest.name}:{lineno}: not a sha256sum entry: {raw!r}"
        digest, path = match.group(1).lower(), match.group(2)
        assert path not in entries, f"{manifest.name}:{lineno}: duplicate for {path}"
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


@pytest.mark.parametrize(
    "manifest", list(EXTERNAL_MANIFESTS), ids=lambda path: path.name
)
def test_external_manifests_are_well_formed(manifest: Path) -> None:
    """Classification must not mean "checked by nothing".

    An external manifest's paths cannot be resolved against this tree — that is what makes it
    external — but its *form* can still be validated: 64-hex digests, a legal separator, no
    duplicate entries. Without this, a malformed digest or a duplicated path in the checklist
    or offers manifest is caught by nothing at the moment it is written. The parent pins their
    bytes, which detects later tampering, not authoring error.
    """
    entries = _entries(manifest)
    assert entries, f"{manifest.name} records no entries at all"


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
    unrecorded = tracked - recorded - NOT_EVIDENCE

    assert not unrecorded, (
        f"{len(unrecorded)} file(s) are tracked under {CORPUS.relative_to(REPO_ROOT)} but absent "
        f"from MANIFEST.sha256. `sha256sum -c` passes on this state — it only walks recorded "
        f"entries — so nothing else will tell you. Append each from the corpus "
        f"root with `sha256sum <path> >> MANIFEST.sha256`, then re-verify with `sha256sum -c`. "
        f"scripts/analysis/refresh_corpus_manifest.py will NOT do this: it refuses unrecorded "
        f"paths by design, so it cannot be used to quietly add a file: {sorted(unrecorded)}"
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
        assert (
            key in recorded
        ), f"the parent manifest does not pin nested manifest {key}"
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


def _clause_six_span_matches() -> list[tuple[int, set[str]]]:
    """Search for each quoted line of clause 6 and return only *where* it was found.

    Two properties matter here and both are deliberate.

    The search terms are read out of the manifest rather than written down, so this module
    holds no copy of the clause. An earlier revision hard-coded them, which made this file a
    second copy of the confidentiality clause in a public repository — precisely what the guard
    forbids — and CI caught it on the first run.

    The span text also never leaves this function. ``addopts`` in ``pyproject.toml`` carries
    ``--showlocals``, so any local bound in a frame on a failing stack is printed into the
    GitHub Actions log, which for this repository is public. Returning span *indices* and file
    paths lets a genuine failure report that the clause was reproduced and where, without
    reproducing it again in the log — which is how the first run of this guard put a fragment
    of the clause into the log of run 33959805520.
    """
    quoted: list[str] = []
    inside = False
    for raw in OFFERS_MANIFEST.read_text(encoding="utf-8").splitlines():
        line = raw.lstrip("#").strip()
        if CLAUSE_SIX_HEADING in line:
            inside = True
            continue
        if not inside:
            continue
        if line.startswith('"') or quoted:
            # The quotation runs from the opening double quote to the line that closes it.
            quoted.append(line.strip('"'))
            if line.endswith('"'):
                break

    results: list[tuple[int, set[str]]] = []
    for index, span in enumerate(q for q in quoted if len(q) >= MIN_SPAN_CHARS):
        found = subprocess.run(
            ["git", "grep", "--name-only", "--fixed-strings", span, "--", "."],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        # git grep exits 1 when there are no matches; that is not an error here.
        assert found.returncode in (0, 1), found.stderr
        # splitlines(), not split(): `git grep --name-only` emits one path per line and
        # does not quote plain spaces, and this repository has tracked paths with spaces.
        results.append((index, set(found.stdout.splitlines())))
    return results


def test_clause_six_is_quoted_in_exactly_one_file() -> None:
    """Clause 6 is the confidentiality clause itself. It belongs in one place, or nowhere."""
    home = OFFERS_MANIFEST.relative_to(REPO_ROOT).as_posix()
    results = _clause_six_span_matches()

    assert len(results) >= 3, (
        f"only {len(results)} quoted span(s) could be read from the manifest under "
        f"{CLAUSE_SIX_HEADING!r}. This guard searches for text it reads out of the manifest, so "
        f"a moved or reshaped quotation block leaves it searching for nothing — which would pass "
        f"silently. Restore the block or update CLAUSE_SIX_HEADING."
    )

    for index, matches in results:
        # Liveness: the span was read out of the manifest, so it must be found there. If it is
        # not, the search term is malformed and every "no other file matched" below is vacuous.
        assert home in matches, (
            f"clause-6 span {index} was read from the manifest but does not match the manifest "
            f"itself. The search term is malformed, so this guard is checking nothing."
        )

        elsewhere = sorted(matches - {home})
        assert not elsewhere, (
            f"clause 6 of the Envision offers is reproduced outside {home}: span {index} also "
            f"matches {elsewhere}. The clause forbids communicating the offer to third parties "
            f"and this repository is public. Paraphrase and cite {HANDLING_ANCHOR} instead. The "
            f"span text is withheld from this message deliberately — this log is public."
        )
