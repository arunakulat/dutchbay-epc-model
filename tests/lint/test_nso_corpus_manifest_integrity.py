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
finding, not a skip, so the discovery step cannot be defeated by omitting the manifest —
nor by not being a directory: an area held as a symlink or vendored as a submodule, and a
loose file dropped at the root, are each one index entry belonging to no area, and
:func:`_loose_entries` reports all three rather than passing over them.

**Every guard is proved to fire.** ``VERIFY-01`` clause 5: a guard that has never been
observed to fail is itself an unverified claim. Every guard here is paired with at least one
``test_negative_control_*``, and that pairing is enforced by
:func:`test_every_guard_has_a_negative_control` rather than asserted in this docstring. No
count is written here on purpose: the first revision of this module claimed six controls for
eight guards, and a count written down by the author is exactly the unverified claim the
rule is about. Read ``GUARD_CONTROLS`` for the current mapping. A guard whose two halves can
fail independently gets a control for each — the clause guard shipped with its extraction
proved and its search unproved, and a reviewer switched the search off without reddening
anything. Each control builds its subject in a throwaway git repository or a
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

**The module name still says ``nso``.** It is deliberate and it is a compromise. Four things
name this file: the ``fastlane`` job invokes it by literal path, ``AGENTS.md`` cites it by path,
the offers manifest cites it by filename in its handling note — so a rename would also mean
editing a nested manifest and refreshing the parent pin in the same commit, the precise coupling
recorded above as having broken twice — and two ``RECRUIT-01`` review records discuss it by
path. Those two records are **both REJECT** and both bind only to the superseded ``3e4b79f``;
they are cited here as bindings to break, not as endorsement, and an earlier revision of this
paragraph called them "accepted", which was false. Renaming would trade a real risk — the step
silently not running — for a cosmetic gain. The scope is what the code says, not what the
filename says.
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

KALPITIYA_CORPUS = SOURCE_MATERIALS / "kalpitiya_60mw_2026"
KALPITIYA_PACKAGES = KALPITIYA_CORPUS / "source_packages"
KALPITIYA_WIND_MANIFEST = (
    KALPITIYA_PACKAGES / "Kalpitiya60MW_Envision_Wind_2026-09-07.MANIFEST.sha256"
)

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
    # The Envision EN-206 wind package: held in the private DutchBay_RAG corpus, same route.
    KALPITIYA_WIND_MANIFEST,
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
    "KALPITIYA60MW-WIND-HANDLING-2026-09-21": (
        KALPITIYA_WIND_MANIFEST,
        (
            KALPITIYA_CORPUS / "README.md",
            KALPITIYA_PACKAGES / "README.md",
            KALPITIYA_PACKAGES / "Kalpitiya60MW_2026-09-20_DEDUPLICATION_RECEIPT.md",
        ),
    ),
}

# A restricted clause quoted verbatim belongs in one file or nowhere: the manifest that is its
# single home -> the headings that open the quotation blocks it carries. The spans themselves
# are READ OUT OF THE MANIFEST at run time and are deliberately NOT written here: a literal copy
# in this file would itself be a second copy of the clause in a public repository, which is
# precisely what this module exists to forbid. CI caught exactly that on the first run of this
# guard, when the spans were hard-coded.
#
# KEYED BY MANIFEST, DELIBERATELY. An earlier revision keyed this by heading, which is a
# section number and a clause name — boilerplate that every offers manifest carries, not an
# identifier. A second corpus area quoting its own clause 6 under the same heading evicted the
# NSO entry from this dict, and the tree scan that is supposed to catch an unregistered
# quotation collapsed in exactly the same way, so the two cancelled out and alphabetical order
# decided which area kept its guard. A RECRUIT-01 reviewer built that case and measured it
# green. The pair (heading, manifest) is the thing that must be unique, so it is the thing
# registered.
VERBATIM_QUOTATION_HOMES: dict[Path, tuple[str, ...]] = {
    OFFERS_MANIFEST: ("3. CLAUSE 6, VERBATIM.",),
}
MIN_SPAN_CHARS = 30


# One ``sha256sum`` output line: 64 hex digits, two spaces (text mode) or a space and an
# asterisk (binary mode, ``sha256sum -b``), then the path. Both forms, and upper-case digests,
# are accepted by ``sha256sum -c``, so rejecting them here would fail a manifest the tool
# itself verifies — a false positive that would turn fastlane red with a misleading diagnosis
# after any regeneration with ``-b``.
ENTRY = re.compile(r"([0-9a-fA-F]{64}) [ *](.*)")


def _parse_entries(manifest: Path) -> tuple[dict[str, str], list[int], list[int]]:
    """Parse a manifest, returning {path: digest} and the line numbers of any defects.

    The parsing lives in its own frame and *returns* rather than asserting, so that when
    :func:`_entries` raises, this frame has already been popped and no line of manifest text
    is bound anywhere on the failing stack. ``addopts`` in ``pyproject.toml`` carries
    ``--showlocals``, which prints every local in every frame of a failing test into the
    GitHub Actions log — and for this repository that log is public. The offers manifest is
    one of the files parsed here and it is the single home of a confidentiality clause, so
    an assertion that echoed the offending line, or a frame that still held the whole file,
    would reproduce restricted text in public to report a formatting error. That is the same
    failure this module already guards against one function down, in
    :func:`_quoted_span_matches`; it belongs here too.
    """
    entries: dict[str, str] = {}
    malformed: list[int] = []
    duplicated: list[int] = []
    text = manifest.read_text(encoding="utf-8").lstrip("\ufeff")
    for lineno, raw in enumerate(text.splitlines(), start=1):
        # splitlines() has already removed the terminator. Do NOT strip beyond that: a path
        # with trailing whitespace would be silently rewritten into a different path, and the
        # guard would then hash a file the manifest does not name.
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        match = ENTRY.fullmatch(raw)
        if match is None:
            malformed.append(lineno)
            continue
        digest, path = match.group(1).lower(), match.group(2)
        if path in entries:
            duplicated.append(lineno)
            continue
        entries[path] = digest
    return entries, malformed, duplicated


def _entries(manifest: Path) -> dict[str, str]:
    """Parse a ``sha256sum``-format manifest into {path: digest}, ignoring comments.

    Failures name the file and the line NUMBER and never quote the line: see
    :func:`_parse_entries` for why.
    """
    entries, malformed, duplicated = _parse_entries(manifest)
    assert not malformed, (
        f"{manifest.name}: line(s) {malformed} are not sha256sum entries. A line must be 64 "
        f"hex digits, two spaces or a space and an asterisk, then the path. The offending "
        f"text is withheld from this message deliberately — this log is public."
    )
    assert not duplicated, (
        f"{manifest.name}: line(s) {duplicated} record a path an earlier line already "
        f"records. Remove the duplicate rather than re-hashing it."
    )
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


# git index modes, for naming what a loose entry actually is. An area held as a symlink or a
# submodule is a single index entry with no path separator beneath the root, exactly like a
# stray file, and the three are told apart only by mode.
LOOSE_ENTRY_KINDS: dict[str, str] = {
    "120000": "a symlink",
    "160000": "a submodule (gitlink)",
}


def _loose_entries(repo_root: Path) -> list[str]:
    """Tracked entries sitting directly under ``docs/source_materials``, belonging to no area.

    :func:`_corpus_areas` takes an area to be the first path segment and keeps only entries
    that have one, so an entry with no separator beneath the root is discovered by nothing,
    checked by nothing and reported by nothing. Three shapes land that way and all three are
    plausible in an evidence corpus: a loose evidence file dropped at the root, an area held
    as a **symlink**, and an area vendored as a **submodule** — and the last two are the
    obvious shapes for material that lives elsewhere, which is what this corpus is about. A
    ``RECRUIT-01`` reviewer built all three and measured them green, against a docstring
    saying discovery could not be defeated by omitting the manifest. It could: by omitting
    the directory.
    """
    source_materials = repo_root / "docs" / "source_materials"
    if not source_materials.is_dir():
        return []
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--stage", "--", str(source_materials)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    prefix = f"{source_materials.relative_to(repo_root).as_posix()}/"
    loose: list[str] = []
    for record in listing.split("\0"):
        if not record:
            continue
        # `git ls-files --stage` emits "<mode> <object> <stage>\t<path>"; -z keeps the path
        # unquoted, so a non-ASCII name is not C-escaped here.
        meta, _, path = record.partition("\t")
        name = path.removeprefix(prefix)
        if "/" in name:
            continue
        kind = LOOSE_ENTRY_KINDS.get(meta.split(" ", 1)[0], "a file")
        loose.append(f"{name} ({kind})")
    return sorted(loose)


def _nested_manifests(area: Path) -> list[Path]:
    """Every manifest beneath ``area`` other than the area's own parent manifest.

    A nested manifest normally carries its package name in front of the suffix, but a
    ``MANIFEST.sha256`` sitting in a SUBDIRECTORY is a manifest too, and an earlier revision
    missed it: it globbed ``*.MANIFEST.sha256``, whose leading ``*`` requires the dot, so the
    bare name never matched and the ``path.name !=`` filter beside it was unreachable. A
    manifest at depth was therefore classified by nothing and its entries checked by nothing
    — the module's own headline defect, one directory further down. Both shapes are collected
    here, and only the area's own parent manifest is excluded, by path rather than by name.
    """
    parent = (area / PARENT_MANIFEST_NAME).resolve()
    return sorted(
        path
        for path in area.rglob("*")
        if path.is_file()
        and (
            path.name == PARENT_MANIFEST_NAME
            or path.name.endswith(NESTED_MANIFEST_SUFFIX)
        )
        and path.resolve() != parent
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


# A handling note defines itself with this line, and a verbatim quotation opens with a heading
# in this shape. Both conventions are mechanical, so the tables above can be checked for
# completeness against the tree instead of being trusted. Without that check the two tables are
# the one part of this module a new corpus area does NOT get for free: its manifests would be
# gated in both directions while its handling note was gated by nothing, silently — which is the
# defect class that produced every blocking finding of both predecessor reviews.
HANDLING_NOTE_DEFINITION = re.compile(r"HANDLING NOTE \u2014 ([A-Z0-9][A-Z0-9-]*)")
VERBATIM_HEADING = re.compile(r"^#?\s*(\d+\.[^\n]*?, VERBATIM\.)", re.MULTILINE)


def _manifests_of(area: Path) -> list[Path]:
    """Every manifest in ``area``: its parent manifest, if present, and the nested ones."""
    parent = area / PARENT_MANIFEST_NAME
    return ([parent] if parent.is_file() else []) + _nested_manifests(area)


def _declarations_in_tree(
    areas: Sequence[Path], pattern: re.Pattern[str]
) -> list[tuple[str, Path]]:
    """Every ``(identifier, manifest)`` occurrence ``pattern`` finds across the areas.

    A list of occurrences rather than a mapping from identifier to manifest. The mapping
    lost one of two areas whenever both used the same identifier, which for a quotation
    heading is the normal case rather than the exotic one, and it lost it silently.
    """
    found: list[tuple[str, Path]] = []
    for area in areas:
        for manifest in _manifests_of(area):
            for identifier in pattern.findall(manifest.read_text(encoding="utf-8")):
                found.append((identifier, manifest))
    return found


def _occurrence(identifier: str, manifest: Path) -> str:
    """``identifier`` and the file carrying it, since an identifier may occur in several."""
    try:
        where = _label(manifest)
    except ValueError:
        where = manifest.name
    return f"{identifier!r} in {where}"


def _registered_quotations() -> list[tuple[str, Path]]:
    """``VERBATIM_QUOTATION_HOMES`` as ``(heading, manifest)`` pairs, the unit that is unique."""
    return sorted(
        (
            (heading, manifest)
            for manifest, headings in VERBATIM_QUOTATION_HOMES.items()
            for heading in headings
        ),
        key=lambda pair: (pair[1].as_posix(), pair[0]),
    )


def _quotation_id(value: object) -> str:
    """Parametrisation id for either half of a ``(heading, manifest)`` pair."""
    return value if isinstance(value, str) else _label(Path(str(value)))


def _unregistered(
    areas: Sequence[Path],
    pattern: re.Pattern[str],
    registered: Iterable[tuple[str, Path]],
) -> tuple[list[str], list[str]]:
    """Occurrences defined in the tree but unregistered, and ones registered to another file.

    Both sides are compared as ``(identifier, file)`` pairs. Comparing identifiers alone let
    a second area inherit the first area's registration and pass on it.
    """
    pairs = {(identifier, home.resolve()) for identifier, home in registered}
    identifiers = {identifier for identifier, _ in pairs}
    missing: set[str] = set()
    misrouted: set[str] = set()
    for identifier, manifest in _declarations_in_tree(areas, pattern):
        if (identifier, manifest.resolve()) in pairs:
            continue
        if identifier in identifiers:
            misrouted.add(_occurrence(identifier, manifest))
        else:
            missing.add(_occurrence(identifier, manifest))
    return sorted(missing), sorted(misrouted)


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
    """Discovery must not be defeatable by not writing a manifest, nor by not being a directory."""
    loose = _loose_entries(REPO_ROOT)
    assert not loose, (
        f"{loose} are tracked directly under {SOURCE_MATERIALS.relative_to(REPO_ROOT)} rather "
        f"than inside a corpus area. An area is the first path segment below that root, so "
        f"these belong to no area and every check in this module skips them without a word. "
        f"A symlinked or submoduled area is the same case: git holds it as one entry with no "
        f"segment beneath it. Move the evidence into an area with its own "
        f"{PARENT_MANIFEST_NAME}, or commit the area's files rather than a link to them."
    )

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
        f"with `find . -type f ! -name {PARENT_MANIFEST_NAME} -printf '%P\\n' | sort | "
        f"xargs -d '\\n' sha256sum > {PARENT_MANIFEST_NAME}`, then verify with "
        f"`sha256sum -c {PARENT_MANIFEST_NAME}`. Use -printf '%P', not a bare `-exec sha256sum "
        f"{{}} +`: that writes ./-prefixed paths, which `sha256sum -c` accepts but which do "
        f"not match the tracked paths, so this guard would then report every file unrecorded."
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


def test_every_handling_note_in_the_tree_is_registered() -> None:
    """A handling note nobody registered is gated by nothing, and nothing says so.

    Nested-manifest classification is forced by
    :func:`test_every_nested_manifest_is_classified`, so a new corpus area cannot land with
    an unclassified manifest. ``HANDLING_ANCHORS`` had no such forcing function, which left
    the module inconsistent with its own argument: a new area's manifests were checked in
    both directions from the first commit while its handling note — the statement that says
    what may and may not be published about restricted documents — was checked by nothing,
    silently. That is the defect class that produced every blocking finding of both
    predecessor reviews, so it is the last one that should be opt-in.
    """
    missing, misrouted = _unregistered(
        CORPUS_AREAS,
        HANDLING_NOTE_DEFINITION,
        [(anchor, home) for anchor, (home, _) in HANDLING_ANCHORS.items()],
    )

    assert not missing, (
        f"{missing} are handling notes defined in a manifest but absent from "
        f"HANDLING_ANCHORS, so nothing checks that their referrers still cite them. Add each "
        f"as anchor -> (the manifest that defines it, the files that must cite it)."
    )
    assert not misrouted, (
        f"{misrouted} are registered against a different manifest than the one that defines "
        f"them. The home must be the file the note actually lives in."
    )


def test_every_verbatim_quotation_in_the_tree_is_registered() -> None:
    """Same forcing function for a quoted restricted clause, where the stakes are highest."""
    missing, misrouted = _unregistered(
        CORPUS_AREAS, VERBATIM_HEADING, _registered_quotations()
    )

    assert not missing, (
        f"{missing} open a verbatim quotation block in a manifest but are absent from "
        f"VERBATIM_QUOTATION_HOMES, so nothing checks that the quoted text appears in that "
        f"file and nowhere else. This repository is public; register each heading."
    )
    assert not misrouted, (
        f"{misrouted} are registered against a different manifest than the one carrying the "
        f"quotation."
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
    __tracebackhide__ = True
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


def _spans_found_in(
    repo_root: Path, spans: Sequence[str]
) -> list[tuple[int, set[str]]]:
    """Which tracked files contain each span, by index — never the span text itself.

    Separated from :func:`_quoted_span_matches` so that the *detection* half of the clause
    guard has a negative control. Extraction had one; the search did not, and a reviewer
    showed that narrowing the pathspec from the whole tree to the manifest alone made the
    guard find no duplicate anywhere while every test in this module stayed green — a guard
    that reports nothing looks exactly like a corpus with nothing to report.
    """
    __tracebackhide__ = True
    results: list[tuple[int, set[str]]] = []
    for index, span in enumerate(spans):
        found = subprocess.run(
            # -z separates paths with NUL and turns off C-quoting, so a path with a space or
            # a non-ASCII character comes back as itself. Without it `git grep --name-only`
            # renders "docs/caf\u00e9 report.md" quoted and escaped, and the set below would
            # then never match the home path it is compared against.
            ["git", "grep", "--name-only", "-z", "--fixed-strings", span, "--", "."],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        # git grep exits 1 when there are no matches; that is not an error here.
        assert found.returncode in (0, 1), found.stderr
        results.append((index, {path for path in found.stdout.split("\0") if path}))
    return results


def _quoted_span_matches(manifest: Path, heading: str) -> list[tuple[int, set[str]]]:
    """Search for each quoted line under ``heading`` and return only *where* it was found.

    Two properties matter here and both are deliberate.

    The search terms are read out of the manifest rather than written down, so this module
    holds no copy of the clause. An earlier revision hard-coded them, which made this file a
    second copy of the confidentiality clause in a public repository — precisely what the guard
    forbids — and CI caught it on the first run.

    The span text is kept out of the log by two mechanisms, because one was not enough.
    ``addopts`` in ``pyproject.toml`` carries ``--showlocals``, so any local bound in a frame
    on a failing stack is printed into the GitHub Actions log, which for this repository is
    public. Returning span *indices* and file paths is the first: it lets a genuine failure
    report that the clause was reproduced and where, without
    reproducing it again in the log — which is how the first run of this guard put a fragment
    of the clause into the log of run 33959805520. The second is ``__tracebackhide__``: the
    loop below binds each span to a local, and returning indices does nothing about a local
    on the stack. A ``RECRUIT-01`` reviewer forced the assertion and measured three of the
    four clause lines printed, against a docstring that claimed the text never left. It does
    not leave now, and the two guards below carry the same marker for the same reason.
    """
    # --showlocals prints every local of every frame on a failing stack into the GitHub
    # Actions log, which for this repository is public. __tracebackhide__ drops this frame
    # from that stack, so `span` — a line of the restricted clause — is never printed. The
    # docstring below used to claim the span text "never leaves this function"; measured, it
    # did: a reviewer forced the assertion and counted three of four clause lines in the log.
    __tracebackhide__ = True
    return _spans_found_in(REPO_ROOT, _quoted_spans(manifest, heading))


@pytest.mark.parametrize(
    ("heading", "manifest"),
    _registered_quotations(),
    ids=_quotation_id,
)
def test_quoted_clauses_appear_in_exactly_one_file(
    heading: str, manifest: Path
) -> None:
    """A quoted restricted clause belongs in one place, or nowhere.

    Parametrised over ``(heading, manifest)`` pairs rather than over headings: a heading is
    boilerplate and two areas may legitimately share one, and keying by it dropped a case.
    """
    __tracebackhide__ = True
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
    with pytest.raises(AssertionError, match="are not sha256sum entries"):
        _entries(short)

    duplicated = tmp_path / "dupe.MANIFEST.sha256"
    duplicated.write_text(
        f"{'a' * 64}  held/a.pdf\n{'b' * 64}  held/a.pdf\n", encoding="utf-8"
    )
    with pytest.raises(AssertionError, match="record a path an earlier line already"):
        _entries(duplicated)

    empty = tmp_path / "empty.MANIFEST.sha256"
    empty.write_text("# nothing but a comment\n", encoding="utf-8")
    assert not _entries(empty)

    # AS-R2: the diagnosis must not reproduce the line it is complaining about. --showlocals
    # prints every frame local into a public CI log, and one of the manifests parsed here is
    # the single home of a confidentiality clause.
    secret = tmp_path / "secret.MANIFEST.sha256"
    sentinel = "SENTINEL-THAT-MUST-NOT-REACH-A-PUBLIC-LOG"
    secret.write_text(f"not-a-digest {sentinel}\n", encoding="utf-8")
    with pytest.raises(AssertionError) as raised:
        _entries(secret)
    assert sentinel not in str(raised.value)
    assert sentinel not in repr(raised.traceback[-1].frame.f_locals)


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
# A tuple per guard, because two of them have two halves that fail independently and a
# single control leaves the other half unproved. That is not hypothetical: the clause guard
# carried only an extraction control, and a reviewer disabled its search half without
# reddening anything in this module.
GUARD_CONTROLS: dict[str, tuple[str, ...]] = {
    "test_every_handling_note_in_the_tree_is_registered": (
        "test_negative_control_unregistered_handling_note_is_reported",
    ),
    "test_every_verbatim_quotation_in_the_tree_is_registered": (
        "test_negative_control_unregistered_verbatim_quotation_is_reported",
    ),
    "test_every_corpus_area_has_a_parent_manifest": (
        "test_negative_control_new_area_without_a_manifest_is_reported",
        "test_negative_control_loose_entry_under_source_materials_is_reported",
    ),
    "test_recorded_entries_are_present_and_hash_as_recorded": (
        "test_negative_control_missing_and_altered_entries_are_reported",
    ),
    "test_external_manifests_are_well_formed": (
        "test_negative_control_malformed_manifest_entries_are_reported",
    ),
    "test_every_nested_manifest_is_classified": (
        "test_negative_control_unclassified_nested_manifest_is_reported",
    ),
    "test_every_tracked_corpus_file_is_recorded": (
        "test_negative_control_unrecorded_tracked_file_is_reported",
    ),
    "test_nested_manifest_parent_pins_are_current": (
        "test_negative_control_parent_pin_defects_are_reported",
    ),
    "test_handling_notes_are_stated_once": (
        "test_negative_control_orphaned_handling_referrer_is_reported",
    ),
    "test_quoted_clauses_appear_in_exactly_one_file": (
        "test_negative_control_reshaped_quotation_block_is_reported",
        "test_negative_control_a_reproduced_span_is_found_in_both_files",
    ),
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

    unpaired = sorted(guard for guard, named in GUARD_CONTROLS.items() if not named)
    assert not unpaired, (
        f"{unpaired} are mapped to an empty tuple, which passes every check below while "
        f"proving nothing. Name the control, or remove the guard."
    )

    claimed = {control for named in GUARD_CONTROLS.values() for control in named}
    missing = sorted(control for control in claimed if control not in controls)
    assert not missing, f"{missing} are named as controls but are not defined here."

    orphaned = sorted(controls - claimed)
    assert not orphaned, (
        f"{orphaned} are negative controls that no guard claims. Map each to the guard it "
        f"proves, or delete it: a control nothing is paired with proves nothing."
    )


def test_negative_control_unregistered_handling_note_is_reported(
    synthetic_corpus: Path,
) -> None:
    """A handling note defined in the tree but absent from the table is reported.

    This is the trap the next corpus area would have walked into: its manifests gated in
    both directions, its handling note gated by nothing, and the operator checklist saying
    it was covered.
    """
    areas = _corpus_areas(synthetic_corpus)
    nested = _nested_manifests(areas[0])[0]
    anchor = "SYNTHETIC-HANDLING-2026-01-01"
    nested.write_text(
        f"# HANDLING NOTE \u2014 {anchor}\n" + nested.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    missing, misrouted = _unregistered(areas, HANDLING_NOTE_DEFINITION, [])
    assert len(missing) == 1 and anchor in missing[0] and misrouted == []

    # Registered against the manifest that defines it: clean.
    missing, misrouted = _unregistered(
        areas, HANDLING_NOTE_DEFINITION, [(anchor, nested)]
    )
    assert (missing, misrouted) == ([], [])

    # Registered against the wrong file: reported, because the referrer check would then be
    # reading a file that does not define the note and passing vacuously.
    elsewhere = areas[0] / PARENT_MANIFEST_NAME
    missing, misrouted = _unregistered(
        areas, HANDLING_NOTE_DEFINITION, [(anchor, elsewhere)]
    )
    assert missing == [] and len(misrouted) == 1 and anchor in misrouted[0]


def test_negative_control_unregistered_verbatim_quotation_is_reported(
    synthetic_corpus: Path,
) -> None:
    """A verbatim quotation block in the tree that no table entry claims is reported."""
    areas = _corpus_areas(synthetic_corpus)
    nested = _nested_manifests(areas[0])[0]
    heading = "3. CLAUSE 9, VERBATIM."
    nested.write_text(
        f"# {heading} Quoted here and nowhere else:\n"
        + nested.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    missing, misrouted = _unregistered(areas, VERBATIM_HEADING, [])
    assert len(missing) == 1 and heading in missing[0] and misrouted == []

    missing, misrouted = _unregistered(areas, VERBATIM_HEADING, [(heading, nested)])
    assert (missing, misrouted) == ([], [])

    # The collision case, which is the whole reason this is keyed by pair. A SECOND area
    # quotes its own clause under the SAME boilerplate heading. Registering the first area's
    # block must not cover the second: keyed by heading alone, the two entries collapsed into
    # one, the tree scan collapsed with them and this came back empty and green.
    beta = synthetic_corpus / "docs" / "source_materials" / "beta_2026"
    beta_manifest = beta / "source_packages" / "BETA_2026-01-01.MANIFEST.sha256"
    _write(beta_manifest, f"# {heading} Quoted here too:\n{'0' * 64}  held/b.pdf\n")
    _write(beta / PARENT_MANIFEST_NAME, "")
    _git(synthetic_corpus, "add", "-A")
    two_areas = _corpus_areas(synthetic_corpus)
    assert len(two_areas) == 2

    missing, misrouted = _unregistered(two_areas, VERBATIM_HEADING, [(heading, nested)])
    # With NEITHER registered, BOTH occurrences must come back. This is the assertion that
    # fails if the tree scan ever goes back to one manifest per identifier: the dedup keeps
    # whichever area sorts last and drops the other without a word, so asserting only that
    # the second area is reported passes under the very defect this control exists for.
    both, _ = _unregistered(two_areas, VERBATIM_HEADING, [])
    assert len(both) == 2 and {nested.name, beta_manifest.name} == {
        entry.rsplit(" in ", 1)[1] for entry in both
    }, f"each area's quotation block must be reported in its own right; got {both}"

    # Reported as misrouted rather than missing: the heading IS registered, just against
    # another area's manifest. Either way it is named, which is the property that was lost.
    reported = missing + misrouted
    assert len(reported) == 1 and beta_manifest.name in reported[0], (
        f"the second area's quotation block must still be reported in its own right; "
        f"got {reported}"
    )

    # Registering it in its own right clears it, and the first area keeps its own entry.
    missing, misrouted = _unregistered(
        two_areas,
        VERBATIM_HEADING,
        [(heading, nested), (heading, beta_manifest)],
    )
    assert (missing, misrouted) == ([], [])


def test_negative_control_loose_entry_under_source_materials_is_reported(
    synthetic_corpus: Path,
) -> None:
    """All three shapes that belong to no corpus area are named, and told apart.

    An area is the first path segment below ``docs/source_materials``, so anything git holds
    as a single entry with no segment beneath it is discovered by nothing. A file dropped at
    the root is the obvious one; an area held as a symlink or vendored as a submodule is the
    one that matters here, because material held elsewhere is what this corpus is about, and
    both were green while the module's docstring said discovery could not be defeated.
    """
    root = synthetic_corpus / "docs" / "source_materials"
    assert _loose_entries(synthetic_corpus) == []

    _write(root / "LOOSE_EVIDENCE.pdf", "dropped at the root, inside no area\n")
    (root / "linked_area").symlink_to("alpha_2026")
    _git(synthetic_corpus, "add", "-A")
    _git(
        synthetic_corpus,
        "update-index",
        "--add",
        "--cacheinfo",
        f"160000,{'0' * 39}1,docs/source_materials/vendored_area",
    )

    reported = _loose_entries(synthetic_corpus)

    assert reported == [
        "LOOSE_EVIDENCE.pdf (a file)",
        "linked_area (a symlink)",
        "vendored_area (a submodule (gitlink))",
    ], reported

    # And the area that is a real directory is still discovered, so this reports the strays
    # rather than replacing discovery with a blanket complaint.
    assert [area.name for area in _corpus_areas(synthetic_corpus)] == ["alpha_2026"]


def test_negative_control_a_reproduced_span_is_found_in_both_files(
    tmp_path: Path,
) -> None:
    """The search half of the clause guard fires, which extraction alone never proved.

    ``test_negative_control_reshaped_quotation_block_is_reported`` covers reading the spans
    out of the manifest. It says nothing about whether the search then finds a copy, and a
    ``RECRUIT-01`` reviewer narrowed the pathspec from the whole tree to the manifest itself,
    which left the guard unable to find a duplicate anywhere while this module stayed green.
    A guard that reports no leak and a guard that cannot see one look identical from here,
    so the difference is asserted: a planted duplicate must come back naming both files.
    """
    repo = tmp_path / "repo"
    span = "This document is confidential and shall not be reproduced in any form."
    only = "A sentence that exists in the manifest and in no other tracked file at all."

    _write(
        repo / "home.MANIFEST.sha256",
        f'# 3. CLAUSE 6, VERBATIM.\n#   "{span}"\n#   "{only}"\n',
    )
    _write(repo / "docs" / "leaked.md", f"Someone pasted it here too: {span}\n")
    _write(repo / "docs" / "innocent.md", "Nothing quoted in this one.\n")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")

    found = dict(_spans_found_in(repo, [span, only]))

    assert found[0] == {"home.MANIFEST.sha256", "docs/leaked.md"}, (
        f"the reproduced span must name both files; got {sorted(found[0])}. A search that "
        f"reaches only the manifest returns just its home and reports no leak."
    )
    assert found[1] == {"home.MANIFEST.sha256"}, (
        f"a span with no duplicate anywhere must name only its home; "
        f"got {sorted(found[1])}"
    )
