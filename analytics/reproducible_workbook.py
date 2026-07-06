"""Deterministic, byte-reproducible openpyxl workbook artifacts (#886).

Why this exists
---------------
Every openpyxl-written ``.xlsx`` embeds two wall-clock timestamps that make two
builds of the *same* data differ byte-for-byte moments apart:

1. ``docProps/core.xml`` — openpyxl's ``save_workbook`` unconditionally re-stamps
   ``workbook.properties.modified = datetime.now(UTC)`` immediately before writing
   the archive, so freezing ``wb.properties.modified`` *before* ``save()`` is not
   enough — the writer overwrites it. ``dcterms:created`` is also wall-clock unless
   explicitly set.
2. The ZIP member ``date_time`` header on *every* entry (local + central directory)
   — openpyxl's ``ZipFile.writestr`` stamps the current local time, which lands in
   the compressed bytes and shifts ZIP offsets between builds.

Under the emitter discipline used across this repo (the executive workbook, the
capital-risk / tech-comparison / interaction-grid report emitters, and the incoming
grid-screening emitter #884), committed artifacts are asserted **raw-ZIP-byte
identical** to prove a change is KPI-neutral. A volatile timestamp turns that
identity flaky — ``tests/solar/test_solar_resource_trend_export.py`` intermittently
failed on CI for exactly this reason (#886), flaky-blocking unrelated PRs.

The fix
-------
:func:`normalize_xlsx_reproducible` post-processes a *written* ``.xlsx`` file in
place: it rewrites the archive with a fixed ZIP ``date_time`` on every member and a
frozen ``dcterms:created`` / ``dcterms:modified`` in ``docProps/core.xml``. Because
it operates on the finished file rather than the in-memory workbook, it is robust to
*how* the workbook was produced — ``pandas.ExcelWriter(engine="openpyxl")`` (the
executive-workbook path) or a direct ``Workbook.save`` (the grid emitter #884). Any
emitter can reuse it by calling it on its output path as the last step; the shared
home in ``analytics`` keeps it importable from both ``analytics`` and
``app.reports`` without an ``analytics -> app`` layering inversion.

:func:`freeze_workbook_reproducible` is the object-level companion for emitters that
hold an openpyxl ``Workbook`` directly: it freezes ``created`` / ``modified`` on the
object so the workbook is honest even pre-save. It does NOT on its own defeat the
``save_workbook`` re-stamp of ``modified`` or the ZIP ``date_time`` drift — pair it
with :func:`normalize_xlsx_reproducible` on the written file for true byte identity.

No financial value is touched: this only pins document metadata timestamps, so the
KPI/data cells are unchanged (CCCDIR one-source-of-truth; the canon byte-identity
tests are unaffected).
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:  # pragma: no cover - typing only
    from openpyxl.workbook.workbook import Workbook

PathLike = Union[str, Path]

__all__ = [
    "REPRODUCIBLE_EPOCH",
    "freeze_workbook_reproducible",
    "normalize_xlsx_reproducible",
]

#: The single fixed timestamp stamped into every reproducible workbook. An
#: arbitrary, obviously-synthetic constant (midnight 2020-01-01) — a lender/consumer
#: reads it as "generation time not recorded", never as a real build clock. Kept in
#: one place (CCCDIR) so every emitter freezes to the identical value.
REPRODUCIBLE_EPOCH = datetime(2020, 1, 1, 0, 0, 0)

#: openpyxl / the ZIP format store member ``date_time`` with a floor of 1980-01-01
#: (the DOS epoch); anything earlier is clamped. Use that floor as the fixed member
#: timestamp so it is both deterministic and representable.
_FIXED_ZIP_DATE_TIME = (1980, 1, 1, 0, 0, 0)

#: The W3CDTF string openpyxl writes for a UTC ``dcterms`` timestamp, frozen to
#: :data:`REPRODUCIBLE_EPOCH`.
_FIXED_W3CDTF = REPRODUCIBLE_EPOCH.strftime("%Y-%m-%dT%H:%M:%SZ").encode("ascii")

_CREATED_RE = re.compile(rb"(<dcterms:created[^>]*>)[^<]*(</dcterms:created>)")
_MODIFIED_RE = re.compile(rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)")


def freeze_workbook_reproducible(wb: "Workbook") -> "Workbook":
    """Freeze an openpyxl workbook's document timestamps to a fixed epoch.

    Sets ``created`` and ``modified`` on ``wb.properties`` to
    :data:`REPRODUCIBLE_EPOCH` so the in-memory workbook carries no wall-clock. Use
    for emitters that build and hold a ``Workbook`` directly (e.g. the grid-screening
    emitter #884).

    Note: openpyxl's ``save_workbook`` re-stamps ``properties.modified`` to
    ``datetime.now(UTC)`` at write time, and every ZIP member gets a wall-clock
    ``date_time``, so this alone does NOT make the *file* byte-reproducible. Follow
    the save with :func:`normalize_xlsx_reproducible` on the written path for true
    ZIP-byte identity. Returns ``wb`` for chaining.
    """
    wb.properties.created = REPRODUCIBLE_EPOCH
    wb.properties.modified = REPRODUCIBLE_EPOCH
    return wb


def normalize_xlsx_reproducible(path: PathLike) -> Path:
    """Rewrite a written ``.xlsx`` so repeated builds are raw-ZIP-byte identical (#886).

    Post-processes the file at ``path`` in place, removing the two wall-clock sources
    that make otherwise-identical workbooks differ between builds:

    * every ZIP member's ``date_time`` header is pinned to a fixed epoch
      (:data:`_FIXED_ZIP_DATE_TIME`); and
    * ``docProps/core.xml`` has its ``dcterms:created`` / ``dcterms:modified`` frozen
      to :data:`REPRODUCIBLE_EPOCH` (defeating openpyxl's ``save_workbook``
      wall-clock re-stamp of ``modified``).

    Member content, order, names and per-entry attributes (external/internal attrs,
    create-system) are preserved, so the workbook's data and structure are untouched
    — only volatile metadata is normalised. Idempotent: normalising an
    already-normalised file yields the same bytes. Works regardless of how the
    workbook was written (``pandas.ExcelWriter`` or ``Workbook.save``), so any emitter
    can call it as the final step on its output path.

    Args:
        path: Path to the ``.xlsx`` file to normalise in place.

    Returns:
        The resolved :class:`~pathlib.Path` that was normalised.
    """
    out_path = Path(path)
    raw = out_path.read_bytes()

    with zipfile.ZipFile(io.BytesIO(raw)) as src:
        infos = src.infolist()
        payloads = {info.filename: src.read(info.filename) for info in infos}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in infos:
            data = payloads[info.filename]
            if info.filename == "docProps/core.xml":
                data = _CREATED_RE.sub(rb"\g<1>" + _FIXED_W3CDTF + rb"\g<2>", data)
                data = _MODIFIED_RE.sub(rb"\g<1>" + _FIXED_W3CDTF + rb"\g<2>", data)
            frozen = zipfile.ZipInfo(info.filename, date_time=_FIXED_ZIP_DATE_TIME)
            frozen.compress_type = zipfile.ZIP_DEFLATED
            frozen.external_attr = info.external_attr
            frozen.internal_attr = info.internal_attr
            frozen.create_system = info.create_system
            dst.writestr(frozen, data)

    out_path.write_bytes(buf.getvalue())
    return out_path
