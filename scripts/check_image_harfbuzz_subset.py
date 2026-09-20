#!/usr/bin/env python3
"""Prove WeasyPrint takes the HarfBuzz-Subset path INSIDE the built image.

Why this exists
---------------
The runtime stage installs ``libharfbuzz-subset0`` because WeasyPrint 70.0 ``dlopen``s it
by name at import, with ``allow_fail=True`` (``weasyprint/text/ffi.py``). That
``allow_fail`` is the whole problem: when the library is absent WeasyPrint does not fail.
It warns once at import that the library "will be required by future versions", then
subsets every font face with fontTools instead and warns again per face at render time.
The PDF is still valid, so a missing library is invisible to every check the image gate
had — it builds, it boots, ``/health`` answers 200, and the lender-facing PDF path has
silently moved onto a deprecated code path.

What the gate proved before this script: that ``libharfbuzz-subset0`` RESOLVES AND
INSTALLS on bookworm, because the ``RUN`` line's apt install genuinely re-executed. That
is a fact about the build host's package index. It is not the claim that matters, which is
that the LOADER FINDS THE LIBRARY AT RUN TIME — from the runtime stage (a different stage
from the one that compiled the venv), under the non-root account, with the venv's
interpreter. Nothing asserted that, so this script does, and
``.github/workflows/docker-build.yml`` runs it inside the built image.

What it checks
--------------
1. ``weasyprint.text.ffi.harfbuzz_subset`` is not ``None`` — the loader resolved the
   library under one of the names WeasyPrint tries, in THIS filesystem.
2. A subset symbol called through that handle returns a live object, so the handle binds
   the HarfBuzz-Subset ABI rather than merely naming a file that opened.
3. ``harfbuzz.hb_version_atleast(4, 1, 0)`` — the other half of the gate in
   ``weasyprint/pdf/fonts.py``::``Font.subset``. Bookworm ships 6.0.0, which
   clears it; a base-image change that regressed HarfBuzz below 4.1.0 would not.
4. A real ``write_pdf()`` reaches ``Font.subset`` with glyphs to subset, and emits
   neither the fontTools fallback warning nor the "Unable to subset ... with HarfBuzz"
   failure warning. The first half matters: with no font embedded, nothing is subset,
   no warning is logged and a warning-only check would pass while proving nothing.

Checks 1-3 say the path is AVAILABLE. Check 4 is the one that says it was TAKEN, and it is
the check the deferred advisory on PR #1266 asked for: it exercises the same
``Font.subset`` branch a DBPL render does, so it fails for a missing library, a
too-old HarfBuzz, and a subset call that loads but errors — the three ways the deprecated
path gets taken without anything going red.

Usage
-----
Run it INSIDE an image, with the repository checkout supplying the source over stdin, so
the check does not depend on the image happening to carry ``scripts/``::

    docker run --rm -i <image> python - < scripts/check_image_harfbuzz_subset.py

Exit codes
----------
``0`` the HarfBuzz-Subset path is live · ``1`` it is not (the message names which check
failed and what it saw).

GWTF:
    - CESSPIT: no silent defaults. Each of the four checks reports its own receipt, and a
      failure names the check rather than collapsing to a generic "PDF rendering broken".
"""

from __future__ import annotations

import logging
import sys
from typing import NoReturn

# The two warnings WeasyPrint logs when a render does NOT take the HarfBuzz path. The
# first is the missing/too-old library falling back to fontTools; the second is the
# HarfBuzz subset call itself failing. Either means the deprecated path ran.
FALLBACK_MARKERS = (
    "Using fontTools instead of HarfBuzz-Subset",
    "Unable to subset",
)

# Text worth shaping: enough distinct codepoints that `to_unicode` is non-empty, which is
# what makes `Font.subset` do anything at all (it returns early otherwise).
PROBE_HTML = (
    "<html><body style='font-family: sans-serif'>"
    "<p>DutchBay EPC 0123456789 HarfBuzz subset probe.</p>"
    "</body></html>"
)


def _fail(check: str, detail: str) -> NoReturn:
    """Report one failed check on stderr and end the process non-zero.

    Args:
        check: The check's name, as the passing line would have named it.
        detail: What was observed and what it means for the image, in a form a
            reviewer can act on without reading this file.

    Raises:
        SystemExit: Always, with code 1. The return type is ``NoReturn`` so the
            caller's later use of a name bound in a guarded ``try`` stays sound.
    """
    print(f"FAIL  {check}\n      {detail}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    """Run the four checks in order, cheapest and most diagnostic first.

    Each check prints its own receipt, so a passing run records what was proved
    rather than a bare exit code.

    Returns:
        ``0`` when the HarfBuzz-Subset path is live in this image.

    Raises:
        SystemExit: Code 1, via `_fail`, naming the first check that failed.
    """
    # ── 1. The loader resolved the library, here, in this filesystem ────────────────
    try:
        from weasyprint.text.ffi import ffi, harfbuzz, harfbuzz_subset
    # An import failure here is itself the answer: report it as the first check.
    except Exception as exc:
        _fail(
            "import weasyprint.text.ffi",
            f"{type(exc).__name__}: {exc}. The WeasyPrint runtime libraries are not all "
            f"present in this image.",
        )

    if harfbuzz_subset is None:
        _fail(
            "harfbuzz_subset is not None",
            "WeasyPrint's dlopen of libharfbuzz-subset found nothing under any of the "
            "names it tries. The runtime stage is missing libharfbuzz-subset0, or the "
            "loader cannot reach it. Every PDF this image renders is subset with "
            "fontTools, on WeasyPrint's deprecated path.",
        )
    print("ok    weasyprint.text.ffi.harfbuzz_subset resolved")

    # ── 2. The handle binds the subset ABI, not just a file that opened ─────────────
    try:
        subset_input = harfbuzz_subset.hb_subset_input_create_or_fail()
        if subset_input == ffi.NULL:
            _fail(
                "hb_subset_input_create_or_fail()",
                "returned NULL — the library loaded but cannot create a subset input.",
            )
        harfbuzz_subset.hb_subset_input_destroy(subset_input)
    except Exception as exc:
        _fail(
            "hb_subset_input_create_or_fail()",
            f"{type(exc).__name__}: {exc}. The loaded object does not export the "
            f"HarfBuzz-Subset symbols WeasyPrint calls.",
        )
    print("ok    hb_subset_input_create_or_fail() bound and returned a live input")

    # ── 3. The version half of WeasyPrint's own gate ────────────────────────────────
    if not harfbuzz.hb_version_atleast(4, 1, 0):
        _fail(
            "hb_version_atleast(4, 1, 0)",
            "HarfBuzz is older than 4.1.0, so WeasyPrint refuses the HarfBuzz path "
            "(it needs hb_set_add_sorted_array) and falls back to fontTools whatever "
            "libharfbuzz-subset0 is installed.",
        )
    print("ok    harfbuzz >= 4.1.0, so WeasyPrint's subset gate is satisfied")

    # ── 4. A real render TAKES the path ─────────────────────────────────────────────
    from weasyprint import HTML
    from weasyprint.pdf.fonts import Font

    records: list[str] = []

    class _Capture(logging.Handler):
        """Collect WeasyPrint's warnings so the render's log can be asserted on."""

        def emit(self, record: logging.LogRecord) -> None:
            """Append one formatted record to the enclosing `records` list.

            Args:
                record: The log record WeasyPrint emitted.
            """
            records.append(record.getMessage())

    # Glyph counts per Font.subset call. Font.subset returns early on an empty
    # to_unicode, so a render that embedded no font logs no warning and would let a
    # warnings-only check pass vacuously. Counting the calls closes that hole.
    subset_glyphs: list[int] = []
    original_subset = Font.subset

    def _counting_subset(self, to_unicode, hinting):
        """Record the glyph count, then delegate to the real `Font.subset`.

        Args:
            self: The `Font` being subset.
            to_unicode: The glyph set the render wants kept; empty means
                `Font.subset` returns without reaching the HarfBuzz gate.
            hinting: Passed straight through.

        Returns:
            Whatever `Font.subset` returns (it returns ``None``).
        """
        subset_glyphs.append(len(to_unicode or ()))
        return original_subset(self, to_unicode, hinting)

    handler = _Capture(level=logging.WARNING)
    logger = logging.getLogger("weasyprint")
    logger.addHandler(handler)
    previous_level = logger.level
    logger.setLevel(logging.WARNING)
    Font.subset = _counting_subset
    try:
        pdf = HTML(string=PROBE_HTML).write_pdf()
    finally:
        Font.subset = original_subset
        logger.removeHandler(handler)
        logger.setLevel(previous_level)

    if not pdf.startswith(b"%PDF-"):
        _fail("write_pdf()", "did not return a PDF.")

    if not any(subset_glyphs):
        _fail(
            "write_pdf() reaches the subset gate",
            "the probe render embedded no font with glyphs to subset, so it never "
            "reached Font.subset and this check would have proved nothing. Fontconfig "
            "found no usable font in this image (fonts-dejavu-core / fonts-liberation).",
        )

    fell_back = [line for line in records if any(m in line for m in FALLBACK_MARKERS)]
    if fell_back:
        _fail(
            "write_pdf() takes the HarfBuzz path",
            "the render fell back to fontTools despite the library loading:\n      "
            + "\n      ".join(fell_back),
        )
    print(
        f"ok    write_pdf() subset {len(subset_glyphs)} font(s) through HarfBuzz "
        f"({len(pdf)} bytes, no fallback warning)"
    )

    print("PASS  the HarfBuzz-Subset path is live in this image")
    return 0


if __name__ == "__main__":
    sys.exit(main())
