"""CESSPIT guard: every evidence corpus area must agree with its own manifests.

Two classes of defect motivate this guard, and neither is hypothetical. Manifest defects have
reached ``main`` in two classes, because **no test covered either corpus manifest**: an
*incomplete* manifest across five commits from ``637aad3`` to ``782c958``, closed at #1211, and
one *impossible* entry introduced by #1226 and fixed by #1234. Six defective states in all,
reconstructed from the manifest's state at every ``main`` commit that touched it.

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

**Why this iterates over corpus areas rather than naming one.** Until #1289 every path in this
module was hard-coded to ``docs/source_materials/nso_bess_250mw_2026``, so the *next* corpus
area would have landed covered by nothing at all — which is the precise condition the guard
was written to end, reproduced one directory across. Coverage is therefore derived from the
tree: a **corpus area** is any immediate child of ``docs/source_materials`` holding tracked
files, and every area is checked in both directions from its first commit without anyone
remembering to enlist it. What stays *declared* is the one thing that must not be inferred —
whether a nested manifest's subject lives in this repository or outside it (see
``NESTED_IN_REPO`` / ``NESTED_EXTERNAL``). An area with no parent manifest at all is a
finding, not a skip, so the discovery step cannot be defeated by omitting the manifest.

**Every guard is proved to fire.** ``VERIFY-01`` clause 5: a guard that has never been
observed to fail is itself an unverified claim. There are eight guards here and eight
``test_negative_control_*`` tests, one per guard, and that count is enforced by
:func:`test_every_guard_has_a_negative_control` rather than asserted in this docstring —
prose drifts, and a count written down by the author is exactly the unverified claim the
rule is about. Each control builds its subject in a throwaway git repository or a
``tmp_path``, asserts the helper reports nothing, introduces exactly one defect, and
asserts the same helper the live test calls reports it. They run against a synthetic tree
and never the real one, which is the point: they can be made to fail on demand.

**Where this runs, and why it matters.** The corpus is docs-only by path, and ``test-suite.yml``
skips its pytest shard entirely for docs-only PRs — and two of the six defective commits carried
nothing but documentation paths. So this module is wired into the ``fastlane`` job of
``ci_v14_fastlane.yml``, the one lane that runs unconditionally on every pull request, and not
only into the sharded suite. Move it and it stops running on exactly the changes it exists to
catch. Both workflows must keep the same ``pull_request`` branch list, or the gap reopens on
whichever branch only one of them covers.

**The module name still says ``nso``.** It is deliberate and it is a compromise: renaming a file
the ``fastlane`` job invokes by path, ``AGENTS.md`` cites and two accepted ``RECRUIT-01`` review
records bind to would trade a real risk — the step silently not running — for a cosmetic gain.
The scope is what the code says, not what the filename says.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_MATERIALS = REPO_ROOT / "docs" / "source_materials"

# A corpus area's own manifest is named exactly this; the manifests nested beneath it, one per
# source package, carry the package name in front of the same suffix.
PARENT_MANIFEST_NAME = "MANIFEST.sha256"
NESTED_MANIFEST_SUFFIX = ".MANIFEST.sha256"

NSO_CORPUS = SOURCE_MATERIALS / "nso_bess_250mw_2026"
NSO_PACKAGES = NSO_CORPUS / "source_packages"
OFFERS_MANIFEST = NSO_PACKAGES / "NSO250MW_Commercial_Offers_2026-09-03.MANIFEST.sha256"
OEM_SUPPLY_MANIFEST = NSO_PACKAGES / "NSO250MW_oem_supply_2026-08-27.MANIFEST.sha256"
CHECKLIST_MANIFEST = NSO_PACKAGES / "NSO250MW_checklist_2026-08-21.MANIFEST.sha256"

# Which NESTED manifests record files that live in this repository, and which record files held
# outside it. Declared rather than inferred: inferring "external" from "the file is missing"
# would make a genuinely missing file indistinguishable from a by-design absent one, which is
# the whole defect this module exists to catch. Parent manifests are NOT listed here — every
# area's parent records files in its own tree by construction, so it is derived from discovery
# and cannot be forgotten.
NESTED_IN_REPO: dict[Path, Path] = {
    # manifest -> the directory its recorded paths are relative to
    OEM_SUPPLY_MANIFEST: NSO_PACKAGES,
}
NESTED_EXTERNAL: tuple[Path, ...] = (
    # The 21 August checklist dossier: binaries held in the owner's private working set.
    CHECKLIST_MANIFEST,
    # The commercial offers: held in the private DutchBay_RAG corpus. Their recorded paths are
    # relative to a root that does not exist here, so they are never resolved against this tree.
    OFFERS_MANIFEST,
)

# Files that live in a corpus area but are not themselves evidence, so the area's manifest does
# not record them. Declared rather than special-cased, for the same reason the classification
# above is: an undeclared exception turns fastlane red with no supported way to express it.
NOT_EVIDENCE: frozenset[str] = frozenset(
    {
        "MANIFEST.sha256",  # a manifest cannot record its own hash
    }
)

# Each handling statement is defined in exactly ONE file and cited by identifier everywhere
# else. anchor -> (the manifest that defines it, the files that must cite it).
HANDLING_ANCHORS: dict[str, tuple[Path, tuple[Path, ...]]] = {
    "NSO250MW-OFFERS-HANDLING-2026-09-04": (
        OFFERS_MANIFEST,
        (
            NSO_CORPUS / "README.md",
            NSO_PACKAGES / "README.md",
            REPO_ROOT / "changelog.d" / "nso-commercial-offer-resupply.fixed.md",
        ),
    ),
}

# A restricted clause quoted verbatim belongs in one file or nowhere. heading that opens the
# quotation block -> the manifest that is its single home. The spans themselves are READ OUT OF
# THE MANIFEST at run time and are deliberately NOT written here: a literal copy in this file
# would itself be a second copy of the clause in a public repository, which is precisely what
# this module exists to forbid. CI caught exactly that on the first run of this guard, when the
# spans were hard-coded.
VERBATIM_QUOTATION_HOMES: dict[str, Path] = {
    "3. CLAUSE 6, VERBATIM.": OFFERS_MANIFEST,
}
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


def _tracked_under(directory: Path, repo_root: Path) -> set[str]:
    """Paths git tracks under ``directory``, relative to it."""
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--", str(directory)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    tracked = {entry for entry in listing.split("\0") if entry}
    prefix = f"{directory.relative_to(repo_root).as_posix()}/"
    return {entry[len(prefix) :] for entry in tracked}


def _corpus_areas(repo_root: Path) -> list[Path]:
    """Every corpus area: an immediate child of ``docs/source_materials`` holding tracked files.

    Derived from ``git ls-files`` rather than from ``iterdir`` so that an untracked scratch
    directory in somebody's working tree cannot turn fastlane red, and so that an area is
    discovered by the same act that puts it under version control.
    """
    source_materials = repo_root / "docs" / "source_materials"
    if not source_materials.is_dir():
        return []
    names = {
        entry.split("/", 1)[0]
        for entry in _tracked_under(source_materials, repo_root)
        if "/" in entry
    }
    return sorted(source_materials / name for name in names)


def _nested_manifests(area: Path) -> list[Path]:
    """Every manifest beneath ``area`` other than the area's own parent manifest."""
    return sorted(
        path
        for path in area.rglob(f"*{NESTED_MANIFEST_SUFFIX}")
        if path.name != PARENT_MANIFEST_NAME
    )


def _areas_without_a_parent_manifest(repo_root: Path) -> list[str]:
    """Corpus areas that carry no ``MANIFEST.sha256``, repo-relative and sorted.

    This is the gap that would otherwise defeat discovery: an area with no manifest has no
    manifest to disagree with, so every other check below would pass it in silence.
    """
    return sorted(
        area.relative_to(repo_root).as_posix()
        for area in _corpus_areas(repo_root)
        if not (area / PARENT_MANIFEST_NAME).is_file()
    )


def _missing_and_altered(manifest: Path, base: Path) -> tuple[list[str], list[str]]:
    """Recorded entries that are absent from the tree, and ones whose hash has changed."""
    missing: list[str] = []
    altered: list[str] = []
    for path, digest in _entries(manifest).items():
        resolved = (base / path).resolve()
        if not resolved.is_file():
            missing.append(path)
        elif _sha256(resolved) != digest:
            altered.append(path)
    return sorted(missing), sorted(altered)


def _unrecorded_under(area: Path, repo_root: Path) -> set[str]:
    """Files tracked under ``area`` that its parent manifest does not record."""
    recorded = set(_entries(area / PARENT_MANIFEST_NAME))
    return _tracked_under(area, repo_root) - recorded - NOT_EVIDENCE


def _parent_pin_defects(area: Path) -> tuple[list[str], list[str]]:
    """Nested manifests the parent does not pin, and ones whose pin has gone stale."""
    recorded = _entries(area / PARENT_MANIFEST_NAME)
    unpinned: list[str] = []
    stale: list[str] = []
    for nested in _nested_manifests(area):
        key = nested.relative_to(area).as_posix()
        if key not in recorded:
            unpinned.append(key)
        elif recorded[key] != _sha256(nested):
            stale.append(key)
    return sorted(unpinned), sorted(stale)


def _classification_gaps(
    areas: Sequence[Path],
    in_repo: Iterable[Path],
    external: Iterable[Path],
) -> tuple[list[Path], list[Path]]:
    """Nested manifests nobody classified, and classifications pointing at nothing."""
    on_disk = {path.resolve() for area in areas for path in _nested_manifests(area)}
    declared = {path.resolve() for path in in_repo} | {
        path.resolve() for path in external
    }
    return sorted(on_disk - declared), sorted(declared - on_disk)


def _in_repo_manifests(repo_root: Path) -> dict[Path, Path]:
    """Manifest -> the directory its recorded paths resolve against.

    Every discovered area's parent manifest, plus the nested manifests declared in-repo. A
    parent that is missing is left out here and reported by
    :func:`test_every_corpus_area_has_a_parent_manifest` instead, so the absence is one loud
    finding rather than a collection error smeared across every parametrised case.
    """
    mapping: dict[Path, Path] = {
        area / PARENT_MANIFEST_NAME: area
        for area in _corpus_areas(repo_root)
        if (area / PARENT_MANIFEST_NAME).is_file()
    }
    mapping.update(NESTED_IN_REPO)
    return mapping


CORPUS_AREAS: list[Path] = _corpus_areas(REPO_ROOT)
IN_REPO_MANIFESTS: dict[Path, Path] = _in_repo_manifests(REPO_ROOT)


def _require_parent_manifest(area: Path) -> Path:
    """Fail with a pointer rather than a ``FileNotFoundError`` traceback.

    The area-parametrised checks below have nothing to compare the tree against when the
    manifest is absent. Reporting that as a plain assertion keeps the output of a missing
    manifest to three readable findings instead of one finding and two stack traces, and
    keeps the area in the parametrisation rather than silently dropping it.
    """
    manifest = area / PARENT_MANIFEST_NAME
    assert manifest.is_file(), (
        f"{area.name} has no {PARENT_MANIFEST_NAME}, so this check has nothing to compare "
        f"the tree against. See test_every_corpus_area_has_a_parent_manifest for how to "
        f"write one."
    )
    return manifest


def _label(path: Path) -> str:
    """A parametrisation id that stays unique once several areas each have a MANIFEST."""
    return path.relative_to(SOURCE_MATERIALS).as_posix()


def test_every_corpus_area_has_a_parent_manifest() -> None:
    """Discovery must not be defeatable by simply not writing a manifest."""
    assert CORPUS_AREAS, (
        f"no corpus area was discovered under {SOURCE_MATERIALS.relative_to(REPO_ROOT)}. "
        f"Either the tree moved or `git ls-files` returned nothing, and in both cases every "
        f"other check in this module is now vacuous."
    )

    orphans = _areas_without_a_parent_manifest(REPO_ROOT)
    assert not orphans, (
        f"{orphans} are corpus areas with no {PARENT_MANIFEST_NAME}. An area without one has "
        f"no manifest to disagree with, so nothing here checks it — the exact condition that "
        f"let manifest defects reach main six times. Write the manifest from the area root "
        f"with `find . -type f ! -name {PARENT_MANIFEST_NAME} -exec sha256sum {{}} +`, then "
        f"verify with `sha256sum -c {PARENT_MANIFEST_NAME}`."
    )


@pytest.mark.parametrize("manifest", list(IN_REPO_MANIFESTS), ids=_label)
def test_recorded_entries_are_present_and_hash_as_recorded(manifest: Path) -> None:
    """Direction 1 — every recorded entry exists and matches. This is ``sha256sum -c``."""
    missing, altered = _missing_and_altered(manifest, IN_REPO_MANIFESTS[manifest])

    assert not missing, (
        f"{manifest.name} records {len(missing)} file(s) that are not in the tree. An entry for "
        f"a path git cannot hold — anything under a gitignored directory, for instance — is "
        f"permanently unsatisfiable and must be removed, not re-hashed: {missing}"
    )
    assert not altered, (
        f"{manifest.name} records a different hash than the file now has, which in an evidence "
        f"corpus is the signal reserved for content having been altered. If the change is "
        f"intended, refresh the manifest in the SAME commit: {altered}"
    )


@pytest.mark.parametrize("manifest", list(NESTED_EXTERNAL), ids=_label)
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
    unclassified, vanished = _classification_gaps(
        CORPUS_AREAS, NESTED_IN_REPO, NESTED_EXTERNAL
    )

    assert not unclassified, (
        f"{[path.relative_to(REPO_ROOT).as_posix() for path in unclassified]} are nested "
        f"manifests that this guard does not classify, so nothing checks them. Add each to "
        f"NESTED_IN_REPO (its subject is committed here) or to NESTED_EXTERNAL (its subject is "
        f"held elsewhere and recorded by hash only)."
    )
    assert not vanished, (
        f"{[path.relative_to(REPO_ROOT).as_posix() for path in vanished]} are declared here "
        f"but no longer on disk."
    )


@pytest.mark.parametrize("area", CORPUS_AREAS, ids=_label)
def test_every_tracked_corpus_file_is_recorded(area: Path) -> None:
    """Direction 2 — the blind spot. ``sha256sum -c`` never looks this way.

    A file added to the corpus but not recorded leaves the manifest an incomplete index of the
    evidence, and every ``-c`` run stays green while it does.
    """
    _require_parent_manifest(area)
    unrecorded = _unrecorded_under(area, REPO_ROOT)

    assert not unrecorded, (
        f"{len(unrecorded)} file(s) are tracked under {area.relative_to(REPO_ROOT)} but absent "
        f"from {PARENT_MANIFEST_NAME}. `sha256sum -c` passes on this state — it only walks "
        f"recorded entries — so nothing else will tell you. Append each from the area root "
        f"with `sha256sum <path> >> {PARENT_MANIFEST_NAME}`, then re-verify with `sha256sum "
        f"-c`. scripts/analysis/refresh_corpus_manifest.py will NOT do this: it refuses "
        f"unrecorded paths by design, so it cannot be used to quietly add a file: "
        f"{sorted(unrecorded)}"
    )


@pytest.mark.parametrize("area", CORPUS_AREAS, ids=_label)
def test_nested_manifest_parent_pins_are_current(area: Path) -> None:
    """The coupling that broke twice: the parent pins each nested manifest by hash.

    Editing a nested manifest invalidates the parent's pin. Refresh the parent **last**, after
    every nested edit, in the same commit.
    """
    _require_parent_manifest(area)
    unpinned, stale = _parent_pin_defects(area)

    assert not unpinned, (
        f"the parent manifest of {area.relative_to(REPO_ROOT)} does not pin nested "
        f"manifest(s) {unpinned}. A nested manifest the parent does not record is outside "
        f"both directions of this gate."
    )
    assert not stale, (
        f"the parent manifest's pin is stale for {stale}. A nested manifest was edited without "
        f"refreshing the parent in the same commit, so `sha256sum -c` now reports FAILED on a "
        f"file that is present and correct."
    )


def _defines_anchor(home: Path, anchor: str) -> bool:
    """True when ``home`` carries the handling note's definition line for ``anchor``."""
    return f"HANDLING NOTE \u2014 {anchor}" in home.read_text(encoding="utf-8")


def _orphaned_referrers(anchor: str, referrers: Iterable[Path]) -> list[Path]:
    """Referrers that no longer cite ``anchor``."""
    return sorted(
        referrer
        for referrer in referrers
        if anchor not in referrer.read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("anchor", sorted(HANDLING_ANCHORS))
def test_handling_notes_are_stated_once(anchor: str) -> None:
    """A handling statement is defined in one place and cited, never restated, elsewhere."""
    home, referrers = HANDLING_ANCHORS[anchor]

    assert _defines_anchor(home, anchor), (
        f"{home.name} no longer defines the handling note under {anchor}. Every referrer "
        f"points at that identifier; moving or renaming it orphans all of them."
    )

    orphaned = [
        referrer.relative_to(REPO_ROOT).as_posix()
        for referrer in _orphaned_referrers(anchor, referrers)
    ]
    assert not orphaned, (
        f"{orphaned} describe this package but no longer cite {anchor}. Cite the identifier; "
        f"do not restate what it says. Five copies of this statement disagreed with each other "
        f"on 4 September 2026, and that is what these files are pointing at instead."
    )


def _quoted_spans(manifest: Path, heading: str) -> list[str]:
    """The quoted lines under ``heading``, long enough to be worth searching for.

    Returns them rather than searching, so the extraction can be exercised on a tree this
    module is allowed to break. An empty result is the silent-pass failure mode the live
    test's minimum-span assertion exists to catch: a moved or reshaped quotation block
    leaves the search looking for nothing at all.
    """
    quoted: list[str] = []
    inside = False
    for raw in manifest.read_text(encoding="utf-8").splitlines():
        line = raw.lstrip("#").strip()
        if heading in line:
            inside = True
            continue
        if not inside:
            continue
        if line.startswith('"') or quoted:
            # The quotation runs from the opening double quote to the line that closes it.
            quoted.append(line.strip('"'))
            if line.endswith('"'):
                break
    return [span for span in quoted if len(span) >= MIN_SPAN_CHARS]


def _quoted_span_matches(manifest: Path, heading: str) -> list[tuple[int, set[str]]]:
    """Search for each quoted line under ``heading`` and return only *where* it was found.

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
    results: list[tuple[int, set[str]]] = []
    for index, span in enumerate(_quoted_spans(manifest, heading)):
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


@pytest.mark.parametrize("heading", sorted(VERBATIM_QUOTATION_HOMES))
def test_quoted_clauses_appear_in_exactly_one_file(heading: str) -> None:
    """A quoted restricted clause belongs in one place, or nowhere."""
    manifest = VERBATIM_QUOTATION_HOMES[heading]
    home = manifest.relative_to(REPO_ROOT).as_posix()
    results = _quoted_span_matches(manifest, heading)

    assert len(results) >= 3, (
        f"only {len(results)} quoted span(s) could be read from {manifest.name} under "
        f"{heading!r}. This guard searches for text it reads out of the manifest, so "
        f"a moved or reshaped quotation block leaves it searching for nothing — which would pass "
        f"silently. Restore the block or update VERBATIM_QUOTATION_HOMES."
    )

    for index, matches in results:
        # Liveness: the span was read out of the manifest, so it must be found there. If it is
        # not, the search term is malformed and every "no other file matched" below is vacuous.
        assert home in matches, (
            f"span {index} was read from {home} but does not match the manifest "
            f"itself. The search term is malformed, so this guard is checking nothing."
        )

        elsewhere = sorted(matches - {home})
        assert not elsewhere, (
            f"a restricted clause held in {home} is reproduced outside it: span {index} also "
            f"matches {elsewhere}. The clause forbids communicating the document to third "
            f"parties and this repository is public. Paraphrase and cite the handling note "
            f"instead. The span text is withheld from this message deliberately — this log is "
            f"public."
        )


# --------------------------------------------------------------------------------------
# Negative controls (VERIFY-01 clause 5)
#
# "A guard that has never been observed to fail is itself an unverified claim, so a new
# guard ships with the negative control demonstrating that it fires."
#
# Each control builds a small, VALID corpus in a throwaway git repository under tmp_path,
# asserts the helper reports nothing (the positive control — without it, a helper that
# always reported a defect would pass every negative control below), then introduces
# exactly one defect and asserts the SAME helper the live tests above call reports it.
# The defects are injected into the synthetic tree only; the real corpus is never mutated.
# --------------------------------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture()
def synthetic_corpus(tmp_path: Path) -> Path:
    """A minimal, valid one-area corpus in a throwaway git repository. Returns its root.

    The files are staged but never committed: ``git ls-files`` reads the index, which is what
    :func:`_tracked_under` and :func:`_corpus_areas` consult, and committing would need a
    ``user.email`` this environment does not guarantee.
    """
    repo = tmp_path / "repo"
    area = repo / "docs" / "source_materials" / "alpha_2026"
    packages = area / "source_packages"

    _write(area / "README.md", "# alpha area\n")
    _write(packages / "README.md", "# alpha packages\n")
    nested = packages / "ALPHA_2026-01-01.MANIFEST.sha256"
    _write(nested, f"# material held outside this repository\n{'0' * 64}  held/a.pdf\n")

    _write(
        area / PARENT_MANIFEST_NAME,
        "".join(
            f"{_sha256(target)}  {key}\n"
            for target, key in (
                (area / "README.md", "README.md"),
                (packages / "README.md", "source_packages/README.md"),
                (nested, f"source_packages/{nested.name}"),
            )
        ),
    )

    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    return repo


def _alpha(repo: Path) -> Path:
    return repo / "docs" / "source_materials" / "alpha_2026"


def test_negative_control_unrecorded_tracked_file_is_reported(
    synthetic_corpus: Path,
) -> None:
    """Direction 2 fires. This is the state ``sha256sum -c`` returns 0 on."""
    area = _alpha(synthetic_corpus)
    assert _unrecorded_under(area, synthetic_corpus) == set()

    _write(area / "smuggled.md", "# tracked, never recorded\n")
    _git(synthetic_corpus, "add", "-A")

    assert _unrecorded_under(area, synthetic_corpus) == {"smuggled.md"}


def test_negative_control_missing_and_altered_entries_are_reported(
    synthetic_corpus: Path,
) -> None:
    """Direction 1 fires, for both of its cases, and tells them apart."""
    area = _alpha(synthetic_corpus)
    manifest = area / PARENT_MANIFEST_NAME
    assert _missing_and_altered(manifest, area) == ([], [])

    (area / "README.md").write_text("# altered after the manifest was written\n")
    assert _missing_and_altered(manifest, area) == ([], ["README.md"])

    (area / "README.md").unlink()
    assert _missing_and_altered(manifest, area) == (["README.md"], [])


def test_negative_control_parent_pin_defects_are_reported(
    synthetic_corpus: Path,
) -> None:
    """The coupling that broke twice on one branch fires, for both of its cases."""
    area = _alpha(synthetic_corpus)
    assert _parent_pin_defects(area) == ([], [])

    nested = area / "source_packages" / "ALPHA_2026-01-01.MANIFEST.sha256"
    nested.write_text(nested.read_text() + f"{'1' * 64}  held/b.pdf\n")
    assert _parent_pin_defects(area) == (
        [],
        [f"source_packages/{nested.name}"],
    )

    unpinned_nested = area / "source_packages" / "BETA_2026-02-02.MANIFEST.sha256"
    _write(unpinned_nested, f"# a second package\n{'2' * 64}  held/c.pdf\n")
    assert _parent_pin_defects(area)[0] == [f"source_packages/{unpinned_nested.name}"]


def test_negative_control_unclassified_nested_manifest_is_reported(
    synthetic_corpus: Path,
) -> None:
    """A nested manifest nobody classified is reported, and so is a dangling declaration."""
    areas = _corpus_areas(synthetic_corpus)
    nested = _nested_manifests(areas[0])
    assert len(nested) == 1

    unclassified, vanished = _classification_gaps(areas, [], [])
    assert unclassified == [nested[0].resolve()] and vanished == []

    unclassified, vanished = _classification_gaps(areas, [], nested)
    assert (unclassified, vanished) == ([], [])

    ghost = areas[0] / "source_packages" / "GONE_2026-03-03.MANIFEST.sha256"
    unclassified, vanished = _classification_gaps(areas, [], [*nested, ghost])
    assert unclassified == [] and vanished == [ghost.resolve()]


def test_negative_control_new_area_without_a_manifest_is_reported(
    synthetic_corpus: Path,
) -> None:
    """The gap this change exists to close: a second corpus area, covered from commit one.

    Before #1289 every path in this module was hard-coded to the NSO area, so ``beta_2026``
    below would have been discovered by nothing, checked by nothing, and green.
    """
    assert [area.name for area in _corpus_areas(synthetic_corpus)] == ["alpha_2026"]
    assert _areas_without_a_parent_manifest(synthetic_corpus) == []

    beta = synthetic_corpus / "docs" / "source_materials" / "beta_2026"
    _write(beta / "README.md", "# a second corpus area\n")
    _git(synthetic_corpus, "add", "-A")

    assert [area.name for area in _corpus_areas(synthetic_corpus)] == [
        "alpha_2026",
        "beta_2026",
    ]
    assert _areas_without_a_parent_manifest(synthetic_corpus) == [
        "docs/source_materials/beta_2026"
    ]

    # And the finding clears the moment the area is given its manifest — a guard that cannot
    # be satisfied is a guard people delete.
    _write(
        beta / PARENT_MANIFEST_NAME,
        f"{_sha256(beta / 'README.md')}  README.md\n",
    )
    _git(synthetic_corpus, "add", "-A")
    assert _areas_without_a_parent_manifest(synthetic_corpus) == []
    assert _unrecorded_under(beta, synthetic_corpus) == set()


def test_negative_control_malformed_manifest_entries_are_reported(
    tmp_path: Path,
) -> None:
    """``_entries`` fires on the authoring errors the external manifests are checked for.

    An external manifest's paths cannot be resolved against this tree, so form is the only
    thing that can be checked and it has to actually be checked. Three ways to get it wrong:
    a digest that is not 64 hex, the same path recorded twice, and a manifest that records
    nothing at all.
    """
    good = tmp_path / "good.MANIFEST.sha256"
    good.write_text(f"# a comment\n{'a' * 64}  held/a.pdf\n", encoding="utf-8")
    assert _entries(good) == {"held/a.pdf": "a" * 64}

    short = tmp_path / "short.MANIFEST.sha256"
    short.write_text(f"{'a' * 63}  held/a.pdf\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="not a sha256sum entry"):
        _entries(short)

    duplicated = tmp_path / "dupe.MANIFEST.sha256"
    duplicated.write_text(
        f"{'a' * 64}  held/a.pdf\n{'b' * 64}  held/a.pdf\n", encoding="utf-8"
    )
    with pytest.raises(AssertionError, match="duplicate for"):
        _entries(duplicated)

    empty = tmp_path / "empty.MANIFEST.sha256"
    empty.write_text("# nothing but a comment\n", encoding="utf-8")
    assert not _entries(empty)


def test_negative_control_orphaned_handling_referrer_is_reported(
    tmp_path: Path,
) -> None:
    """The single-source handling note fires when a citation goes stale or the note moves."""
    anchor = "SYNTHETIC-HANDLING-2026-01-01"
    home = tmp_path / "PACKAGE.MANIFEST.sha256"
    home.write_text(
        f"# HANDLING NOTE — {anchor}\n# how this is handled\n", encoding="utf-8"
    )
    citing = tmp_path / "README.md"
    citing.write_text(f"Handling is stated once, at {anchor}.\n", encoding="utf-8")

    assert _defines_anchor(home, anchor)
    assert _orphaned_referrers(anchor, [citing]) == []

    # A referrer that has stopped citing the identifier — usually because somebody restated
    # what it says instead, which is how five copies came to disagree on 4 September 2026.
    restating = tmp_path / "RESTATED.md"
    restating.write_text("The documents are private. Trust me.\n", encoding="utf-8")
    assert _orphaned_referrers(anchor, [citing, restating]) == [restating]

    # The note itself renamed or removed, which orphans every referrer at once.
    home.write_text("# HANDLING NOTE — SOME-OTHER-ANCHOR\n", encoding="utf-8")
    assert not _defines_anchor(home, anchor)


def test_negative_control_reshaped_quotation_block_is_reported(
    tmp_path: Path,
) -> None:
    """The quoted-clause guard fires when its search terms silently become nothing.

    This is the module's own history: the first revision hard-coded the spans, which made
    the test file a second copy of the clause. Reading them out of the manifest fixed that
    but introduced the opposite risk — a moved or reshaped block leaves the search looking
    for nothing and passing. The live test asserts a minimum span count for exactly this,
    and this control is what shows that assertion can fail.
    """
    heading = "3. CLAUSE 9, VERBATIM."
    manifest = tmp_path / "PACKAGE.MANIFEST.sha256"
    long_enough = "x" * (MIN_SPAN_CHARS + 5)
    manifest.write_text(
        f'# {heading}\n#   "{long_enough}\n#    {long_enough}\n#    {long_enough}"\n',
        encoding="utf-8",
    )
    assert len(_quoted_spans(manifest, heading)) == 3

    # The heading renamed: the walk never enters the block, so there is nothing to search
    # for and every "no other file matched" downstream would be vacuous.
    assert _quoted_spans(manifest, "3. CLAUSE 9, IN FULL.") == []

    # The block reshaped so the quotation no longer opens with a double quote.
    manifest.write_text(
        f"# {heading}\n#   {long_enough}\n#   {long_enough}\n", encoding="utf-8"
    )
    assert _quoted_spans(manifest, heading) == []

    # Spans below the minimum length are dropped, so a block of short lines is also nothing.
    manifest.write_text(f'# {heading}\n#   "short"\n', encoding="utf-8")
    assert _quoted_spans(manifest, heading) == []


# The map from each guard to the control that proves it fires. Written down once, here,
# because the alternative is a count in prose that nobody re-checks: the first revision of
# this block claimed six controls for eight guards and three guards had none.
GUARD_CONTROLS: dict[str, str] = {
    "test_every_corpus_area_has_a_parent_manifest": "test_negative_control_new_area_without_a_manifest_is_reported",
    "test_recorded_entries_are_present_and_hash_as_recorded": "test_negative_control_missing_and_altered_entries_are_reported",
    "test_external_manifests_are_well_formed": "test_negative_control_malformed_manifest_entries_are_reported",
    "test_every_nested_manifest_is_classified": "test_negative_control_unclassified_nested_manifest_is_reported",
    "test_every_tracked_corpus_file_is_recorded": "test_negative_control_unrecorded_tracked_file_is_reported",
    "test_nested_manifest_parent_pins_are_current": "test_negative_control_parent_pin_defects_are_reported",
    "test_handling_notes_are_stated_once": "test_negative_control_orphaned_handling_referrer_is_reported",
    "test_quoted_clauses_appear_in_exactly_one_file": "test_negative_control_reshaped_quotation_block_is_reported",
}


def test_every_guard_has_a_negative_control() -> None:
    """``VERIFY-01`` clause 5, enforced on this module rather than claimed by it.

    A guard added later without a control is the same unverified claim as a guard that has
    never been observed to fail, and it is the easy mistake: the guard is the interesting
    part and the control is the chore. This reads the module's own test functions, so it
    catches the omission at the moment it is made instead of at the next review.
    """
    defined = {
        name
        for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    }
    guards = {name for name in defined if not name.startswith("test_negative_control")}
    controls = {name for name in defined if name.startswith("test_negative_control")}

    # This test is itself a guard over the module, not over the corpus, so it is its own
    # exception — a control for it would be a control for a control.
    guards.discard("test_every_guard_has_a_negative_control")

    uncontrolled = sorted(guards - set(GUARD_CONTROLS))
    assert not uncontrolled, (
        f"{uncontrolled} check the corpus but no negative control proves they fire. "
        f"VERIFY-01 clause 5: a guard that has never been observed to fail is itself an "
        f"unverified claim. Add a test_negative_control_* that drives the same helper "
        f"against a tree it may break, then map it in GUARD_CONTROLS."
    )

    retired = sorted(set(GUARD_CONTROLS) - guards)
    assert not retired, f"{retired} are mapped in GUARD_CONTROLS but no longer exist."

    missing = sorted(
        control for control in GUARD_CONTROLS.values() if control not in controls
    )
    assert not missing, f"{missing} are named as controls but are not defined here."

    orphaned = sorted(controls - set(GUARD_CONTROLS.values()))
    assert not orphaned, (
        f"{orphaned} are negative controls that no guard claims. Map each to the guard it "
        f"proves, or delete it: a control nothing is paired with proves nothing."
    )
