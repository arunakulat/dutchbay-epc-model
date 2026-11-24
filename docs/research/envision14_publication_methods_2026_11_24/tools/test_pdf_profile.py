"""Synthetic structure fixtures only; no historical report or project data."""

import hashlib

import pytest


def _synthetic_raw_pdf(*, mode: str = "valid") -> bytes:
    """Construct a tiny structural oracle independent of PyMuPDF serialization."""
    import zlib

    header = b"%PDF-1.7\n%\xf0\x9f\x96\xa4\n"
    if mode == "header":
        header = b"%PDF-1.7\n%unexpected comment\n"
    payload = b"1 0\n<< /Type /Catalog >>"
    if mode == "offset":
        payload = b"1 1\n<< /Type /Catalog >>"
    elif mode == "index":
        payload = b"4 0\n<< /Type /Catalog >>"
    elif mode == "syntax":
        payload = b"1\t0\n<< /Type /Catalog >>"
    elif mode == "forbidden":
        payload = b"1 0\n<< /S /JavaScript >>"
    elif mode == "unindexed":
        payload = b"1 0 4 4\n<< >><< /S /JavaScript >>"
    first = 8 if mode == "unindexed" else 4
    attrs = b"/Type /ObjStm/N 1/First " + str(first).encode()
    if mode == "bounds":
        attrs = b"/Type /ObjStm/N 1/First 9999"
    elif mode == "missing_first":
        attrs = b"/Type /ObjStm/N 1"
    elif mode == "decodeparms":
        attrs += b"/DecodeParms <<>>"

    def stream(number: int, attrs: bytes, payload: bytes) -> bytes:
        encoded = zlib.compress(payload)
        if mode == "deflate" and number == 2:
            encoded = b"invalid"
        elif mode == "deflate_tail" and number == 2:
            encoded += b"extra"
        length = str(len(encoded)).encode()
        if mode == "length" and number == 2:
            length = b"0 0 R"
        return (
            str(number).encode()
            + b" 0 obj\n<<"
            + attrs
            + b"/Filter /FlateDecode/Length "
            + length
            + b">>\nstream\n"
            + encoded
            + b"\nendstream\nendobj\n"
        )

    object_offset = len(header)
    obj = stream(2, attrs, payload)
    if mode == "separator":
        obj += b" \t\n"
    xref_offset = object_offset + len(obj)

    def entry(kind: int, first: int, second: int) -> bytes:
        return bytes([kind]) + first.to_bytes(3, "big") + second.to_bytes(2, "big")

    entries = (
        entry(0, 0, 65535)
        + entry(2, 2, 1 if mode == "slot" else 0)
        + entry(1, object_offset, 0)
        + entry(1, xref_offset, 0)
    )
    if mode == "entry_kind":
        entries = entry(3, 0, 0) + entries[6:]
    elif mode == "free":
        entries = entries[:6] + entry(0, 0, 0) + entries[12:]
    elif mode == "generation":
        entries = entries[:12] + entry(1, object_offset, 1) + entries[18:]
    elif mode == "xref_identity":
        entries = entries[:18] + entry(1, object_offset, 0)
    elif mode == "count":
        entries = entries[:-1]
    elif mode == "parent":
        entries = entries[:6] + entry(2, 3, 0) + entries[12:]
    xattrs = b"/Type /XRef/Index [0 4]/W [1 3 2]/Size 4"
    if mode == "xref_profile":
        xattrs += b"/Prev 10"
    xref = stream(3, xattrs, entries)
    footer = (
        b"startxref\n"
        + str(xref_offset if mode != "xref_offset" else 1).encode()
        + b"\n%%EOF\n"
    )
    return header + obj + xref + footer


def test_raw_pdf_synthetic_profile_positive() -> None:
    from pdf_profile import verify_generated_pdf_raw_structure

    verify_generated_pdf_raw_structure(_synthetic_raw_pdf())


@pytest.mark.parametrize(
    "mode,message",
    [
        ("header", "envelope profile"),
        ("separator", "unexpected bytes after raw PDF stream"),
        ("decodeparms", "length or filter"),
        ("length", "length or filter"),
        ("deflate", "invalid raw PDF Flate stream"),
        ("deflate_tail", "trailing bytes"),
        ("xref_profile", "xref profile"),
        ("xref_offset", "xref offset"),
        ("count", "xref entry count"),
        ("entry_kind", "entry type"),
        ("free", "free PDF xref entry"),
        ("generation", "in-use raw PDF xref entry"),
        ("xref_identity", "xref identity mismatch"),
        ("missing_first", "object stream header"),
        ("bounds", "object stream bounds"),
        ("syntax", "index syntax"),
        ("index", "index disagrees"),
        ("slot", "index disagrees"),
        ("unindexed", "index disagrees"),
        ("offset", "compressed object offsets"),
        ("parent", "index disagrees"),
        ("forbidden", "active PDF object"),
    ],
)
def test_raw_pdf_synthetic_rejects_structural_drift(mode: str, message: str) -> None:
    from pdf_profile import verify_generated_pdf_raw_structure

    with pytest.raises(ValueError, match=message):
        verify_generated_pdf_raw_structure(_synthetic_raw_pdf(mode=mode))


def test_digest_mismatch_precedes_parser() -> None:
    from pdf_profile import verify_bound_generated_pdf

    with pytest.raises(ValueError, match="digest mismatch"):
        verify_bound_generated_pdf(b"not a pdf", hashlib.sha256(b"other").hexdigest())
