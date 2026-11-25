"""Restricted PDF structural screening; not a general PDF parser or rights clearance."""

from __future__ import annotations

import hashlib
import re
import zlib

import pymupdf

PRIVATE_KEY_RE = re.compile(rb"BEGIN\s+(?:[A-Z0-9]+\s+)*PRIVATE\s+KEY", re.I)
LOCAL_PDF_PATH_RE = re.compile(r"(?:/Users/|/Volumes/|/home/|file://)", re.I)


def has_private_marker(data: bytes) -> bool:
    return bool(PRIVATE_KEY_RE.search(data))


PDF_FORBIDDEN_NAMES = frozenset(
    {
        b"JavaScript",
        b"JS",
        b"OpenAction",
        b"AA",
        b"Launch",
        b"EmbeddedFile",
        b"Filespec",
        b"EmbeddedFiles",
        b"EF",
        b"RichMedia",
        b"RichMediaContent",
        b"Movie",
        b"Sound",
        b"Rendition",
        b"SubmitForm",
        b"ImportData",
        b"GoToR",
        b"GoToE",
        b"URI",
        b"OCG",
        b"OCMD",
        b"OCProperties",
        b"AcroForm",
        b"XFA",
        b"Annots",
        b"FileAttachment",
        b"3D",
    }
)
PDF_NAME_RE = re.compile(rb"/([^\s\[\]<>/()%]+)")
PDF_NAME_ESCAPE_RE = re.compile(rb"#([0-9a-fA-F]{2})")


def verify_pdf_envelope(data: bytes) -> None:
    """Reject multiple revisions, appended payloads and unexpected envelopes."""
    if not data.startswith(b"%PDF-") or len(data) > 5_000_000:
        raise ValueError("invalid PDF signature or size")
    if data.count(b"%%EOF") != 1 or not data.rstrip(b" \t\r\n\x0c").endswith(b"%%EOF"):
        raise ValueError("PDF trailing data or multiple EOF markers")


def verify_generated_pdf_raw_structure(data: bytes) -> None:
    """Conservative profile for the canonical generated PDF, not a general parser.

    Require one final Flate xref stream with a full index, direct stream lengths,
    exact physical offsets and separators, and matching compressed-object indices. Reject all
    unsupported formats rather than attempting repairs or guessing boundaries.
    """
    verify_pdf_envelope(data)
    header = re.match(rb"%PDF-1\.7\n%[\x80-\xff]{4}\n", data)
    footer = re.search(rb"startxref\n([0-9]+)\n%%EOF\n\Z", data)
    if header is None or footer is None:
        raise ValueError("unsupported generated PDF envelope profile")
    _scan_pdf_bytes(header[0])
    xref_offset = int(footer[1])
    if not header.end() <= xref_offset < footer.start():
        raise ValueError("invalid generated PDF xref offset")

    def raw_object(offset: int, end: int) -> tuple[int, bytes, bytes]:
        # All physical objects in the canonical profile are zero-generation
        # direct-length Flate streams; compressed objects live in ObjStm.
        block = data[offset:end]
        match = re.match(rb"([0-9]+) 0 obj\n(.*?)\nstream\n", block, re.S)
        if match is None:
            raise ValueError("unindexed or unsupported raw PDF object")
        dictionary = match[2]
        lengths = re.findall(rb"/Length\s+([0-9]+)\b", dictionary)
        if (
            re.search(rb"/DecodeParms\b", dictionary)
            or len(lengths) != 1
            or re.search(rb"/Length\s+[0-9]+\s+[0-9]+\s+R", dictionary)
            or re.findall(rb"/Filter\s*/([^\s<>/\[\]]+)", dictionary)
            != [b"FlateDecode"]
        ):
            raise ValueError("unsupported raw PDF stream length or filter")
        size = int(lengths[0])
        stop = match.end() + size
        if stop > len(block) or not re.fullmatch(
            rb"\nendstream\nendobj\n", block[stop:]
        ):
            raise ValueError("unexpected bytes after raw PDF stream")
        decoder = zlib.decompressobj()
        try:
            decoded = decoder.decompress(block[match.end() : stop], 20_000_001)
        except zlib.error as exc:
            raise ValueError("invalid raw PDF Flate stream") from exc
        if (
            len(decoded) > 20_000_000
            or not decoder.eof
            or decoder.unused_data
            or decoder.unconsumed_tail
        ):
            raise ValueError("raw PDF Flate stream exceeds limit or has trailing bytes")
        _scan_pdf_dictionary(dictionary)
        _scan_pdf_bytes(decoded)
        return int(match[1]), dictionary, decoded

    xref_id, dictionary, entries = raw_object(xref_offset, footer.start())
    size_match = re.search(rb"/Size\s+([0-9]+)\b", dictionary)
    index_match = re.search(rb"/Index\s*\[0\s+([0-9]+)\]", dictionary)
    if (
        not re.search(rb"/Type\s*/XRef\b", dictionary)
        or not re.search(rb"/W\s*\[1\s+3\s+2\]", dictionary)
        or size_match is None
        or index_match is None
        or size_match[1] != index_match[1]
        or re.search(rb"/(?:Prev|XRefStm)\b", dictionary)
    ):
        raise ValueError("unsupported generated PDF xref profile")
    size = int(size_match[1])
    if not 1 < size <= 20_000 or len(entries) != size * 6:
        raise ValueError("invalid generated PDF xref entry count")
    physical: dict[int, int] = {}
    compressed: dict[int, list[tuple[int, int]]] = {}
    for i in range(size):
        entry = entries[i * 6 : (i + 1) * 6]
        typ, first, second = (
            entry[0],
            int.from_bytes(entry[1:4], "big"),
            int.from_bytes(entry[4:6], "big"),
        )
        if typ == 1:
            if i == 0 or second != 0 or not header.end() <= first <= xref_offset:
                raise ValueError("invalid in-use raw PDF xref entry")
            physical[i] = first
        elif typ == 2:
            if i == 0:
                raise ValueError("invalid compressed PDF xref entry")
            compressed.setdefault(first, []).append((i, second))
        elif typ == 0:
            if i != 0 or first != 0 or second != 65535:
                raise ValueError("unexpected free PDF xref entry")
        else:
            raise ValueError("unsupported PDF xref entry type")
    if physical.get(xref_id) != xref_offset or len(set(physical.values())) != len(
        physical
    ):
        raise ValueError("raw PDF xref identity mismatch")
    ordered = sorted((offset, i) for i, offset in physical.items())
    if (
        not ordered
        or ordered[0][0] != header.end()
        or ordered[-1] != (xref_offset, xref_id)
    ):
        raise ValueError("unindexed bytes before or after raw PDF objects")
    objstreams: set[int] = set()
    decoded_total = 0
    for n, (offset, i) in enumerate(ordered):
        end = ordered[n + 1][0] if n + 1 < len(ordered) else footer.start()
        actual, objdict, decoded = raw_object(offset, end)
        if actual != i:
            raise ValueError("raw PDF object number disagrees with xref")
        decoded_total += len(decoded)
        if decoded_total > 20_000_000:
            raise ValueError("raw PDF decoded stream budget exceeded")
        if re.search(rb"/Type\s*/ObjStm\b", objdict):
            objstreams.add(i)
            counts = re.findall(rb"/N\s+([0-9]+)\b", objdict)
            starts = re.findall(rb"/First\s+([0-9]+)\b", objdict)
            if len(counts) != 1 or len(starts) != 1:
                raise ValueError("invalid PDF object stream header")
            count, first = int(counts[0]), int(starts[0])
            if not 0 < count <= size or not 0 < first < len(decoded):
                raise ValueError("invalid PDF object stream bounds")
            index = decoded[:first]
            if not re.fullmatch(rb"[0-9]+ [0-9]+(?: [0-9]+ [0-9]+)*\n", index):
                raise ValueError("unsupported PDF object stream index syntax")
            tokens = [int(token) for token in index.split()]
            pairs = list(zip(tokens[::2], tokens[1::2], strict=True))
            if len(pairs) != count or sorted(
                compressed.get(i, []), key=lambda row: row[1]
            ) != [(number, slot) for slot, (number, _) in enumerate(pairs)]:
                raise ValueError("PDF object stream index disagrees with xref")
            offsets = [offset for _, offset in pairs]
            if (
                offsets[0] != 0
                or offsets != sorted(set(offsets))
                or offsets[-1] >= len(decoded) - first
            ):
                raise ValueError("invalid PDF compressed object offsets")
            for slot, start in enumerate(offsets):
                stop = (
                    offsets[slot + 1]
                    if slot + 1 < len(offsets)
                    else len(decoded) - first
                )
                _scan_pdf_dictionary(decoded[first + start : first + stop])
    if set(compressed) != objstreams:
        raise ValueError("compressed PDF object lacks indexed object stream")


def _scan_pdf_bytes(data: bytes) -> None:
    if has_private_marker(data):
        raise ValueError(
            "private evidence/path marker inside PDF decoded text or metadata"
        )
    if LOCAL_PDF_PATH_RE.search(data.decode("latin-1")):
        raise ValueError("absolute local path or private material inside PDF")


def _scan_pdf_dictionary(data: bytes) -> None:
    _scan_pdf_bytes(data)
    names = {
        PDF_NAME_ESCAPE_RE.sub(lambda m: bytes([int(m.group(1), 16)]), name)
        for name in PDF_NAME_RE.findall(data)
    }
    if names & PDF_FORBIDDEN_NAMES:
        raise ValueError("embedded, hidden-layer or active PDF object prohibited")


def scan_decoded_pdf(report: pymupdf.Document) -> str:
    """Scan text, metadata and every current xref object and decoded stream."""
    if report.is_encrypted or report.is_repaired or report.version_count > 1:
        raise ValueError("encrypted, repaired or incremental PDF prohibited")
    if report.xref_length() > 20_000:
        raise ValueError("PDF object count exceeds static screening limit")

    text = " ".join(page.get_text() for page in report)
    metadata = " ".join(str(v) for v in report.metadata.values())
    extra = " ".join(
        [report.get_xml_metadata() or "", *(str(row[1]) for row in report.get_toc())]
    )
    _scan_pdf_bytes("\n".join((text, metadata, extra)).encode())
    for page in report:
        # The default extraction clips to the MediaBox and omits off-page text.
        unclipped = page.get_text(
            flags=pymupdf.TEXTFLAGS_TEXT & ~pymupdf.TEXT_MEDIABOX_CLIP,
            clip=pymupdf.INFINITE_RECT(),
        )
        trace = "".join(
            chr(char[0]) for span in page.get_texttrace() for char in span["chars"]
        )
        _scan_pdf_bytes(unclipped.encode())
        _scan_pdf_bytes(trace.encode())

    # Include the trailer and all current objects, not just reachable pages.
    decoded_total = 0
    for xref in (-1, *range(1, report.xref_length())):
        dictionary = report.xref_object(xref, compressed=False).encode()
        _scan_pdf_dictionary(dictionary)
        for key in report.xref_get_keys(xref):
            kind, value = report.xref_get_key(xref, key)
            if kind == "string":
                _scan_pdf_bytes(value.encode())
        if xref > 0 and report.xref_is_stream(xref):
            stream = report.xref_stream(xref)
            if stream is None:
                raise ValueError("PDF stream could not be decoded")
            decoded_total += len(stream)
            if decoded_total > 20_000_000:
                raise ValueError("decoded PDF streams exceed static screening limit")
            _scan_pdf_bytes(stream)
    return text


def verify_bound_generated_pdf(data: bytes, expected_sha256: str) -> None:
    """Screen one byte snapshot; the caller must independently authorize its contents."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("invalid expected PDF digest")
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("PDF digest mismatch")
    verify_generated_pdf_raw_structure(data)
    with pymupdf.open(stream=data, filetype="pdf") as report:
        if report.embfile_count() or any(
            page.get_images(full=True)
            or page.get_links()
            or list(page.annots() or ())
            or list(page.widgets() or ())
            for page in report
        ):
            raise ValueError("unexpected active or image content in text-only PDF")
        scan_decoded_pdf(report)
