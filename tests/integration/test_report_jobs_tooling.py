"""Integration guards for the governed report and async-job toolchain."""

from __future__ import annotations

import zlib
from importlib.metadata import version

import brotli
import hiredis
from weasyprint import HTML
from zopfli.zlib import compress as zopfli_compress


def test_governed_report_jobs_versions_are_installed() -> None:
    """Pin the report/worker versions cleared together under Python 3.12."""

    assert version("weasyprint") == "69.0"
    assert version("arq") == "0.28.0"
    assert version("brotli") == "1.2.0"
    assert version("hiredis") == "3.4.1"
    assert version("zopfli") == "0.4.3"


def test_report_and_compression_backends_execute() -> None:
    """Exercise PDF rendering and each retained acceleration backend."""

    payload = b"DutchBay governed Python 3.12 report and jobs tooling"

    pdf = HTML(string="<h1>DutchBay governed report</h1>").write_pdf()
    assert pdf.startswith(b"%PDF-")

    assert brotli.decompress(brotli.compress(payload)) == payload
    assert zlib.decompress(zopfli_compress(payload)) == payload

    reader = hiredis.Reader()
    reader.feed(b"+PONG\r\n")
    assert reader.gets() == b"PONG"
