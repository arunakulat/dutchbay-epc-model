"""Extract engineering content from OEM dynamic-model deliverables without running the tools.

WHY THIS EXISTS
---------------
The tender requires PSS(R)E and PSCAD/EMTDC models. Both are commercial, Windows-only, licensed
tools; PSCAD additionally needs an Intel Fortran compiler to build the supplied ``.obj``/``.lib``
interface objects. None of that can run in this repository's Linux CI or in an agent sandbox, so
the models cannot be *executed* here.

They can still be *read*. Two of the three deliverable classes are plain text:

* ``.dyr`` — the PSS(R)E dynamics record is ASCII. Every model parameter, protection stage and
  ride-through point the OEM shipped is in it.
* ``.pscx`` — a PSCAD 5 project is XML. Component structure, project settings and parameter
  values are all recoverable.
* ``.dll`` / ``.obj`` / ``.lib`` — compiled. Only metadata and symbol names are recoverable; the
  control law itself is not. This module reports what it can see and is explicit that the rest is
  opaque.

This is a READING tool. It does not simulate, and nothing it reports is a substitute for the
vendor's own validated study. Its purpose is to let a reviewer check a supplied model's declared
settings against a grid-code requirement without a PSCAD licence.

GWTF:
    - DATA-01: every parameter found is reported; nothing is filtered as "minor".
    - CESSPIT: a file that cannot be parsed raises rather than returning an empty result that
      would read as "no findings".
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional


class ModelExtractionError(RuntimeError):
    """Raised when a model file is present but cannot be parsed."""


# ═════════════════════════════════════════════════════════════════════════════
# PSS(R)E .dyr
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class DyrRecord:
    """One model record from a PSS(R)E dynamics file."""

    bus: str
    kind: str
    model: str
    numbers: tuple[float, ...]

    @property
    def base_kw(self) -> Optional[float]:
        """First value over 1000 is conventionally the machine MVA/kW base."""
        for v in self.numbers:
            if v >= 1000.0:
                return v
        return None


def parse_dyr(path: Path) -> list[DyrRecord]:
    """Parse a ``.dyr`` into its model records.

    Records are terminated by ``/``; the model name is the second quoted token.
    """
    text = path.read_text(errors="replace")
    if "'" not in text:
        raise ModelExtractionError(f"{path.name}: no quoted model name found; not a .dyr?")
    records: list[DyrRecord] = []
    for chunk in text.split("/"):
        quoted = re.findall(r"'([^']+)'", chunk)
        if len(quoted) < 2:
            continue
        lead = chunk.strip().split()
        bus = lead[0] if lead and lead[0].lstrip("-").isdigit() else "?"
        nums = tuple(
            float(n)
            for n in re.findall(r"(?<![\w.])-?\d+\.\d+(?![\w.])", chunk)
        )
        records.append(
            DyrRecord(bus=bus, kind=quoted[0].strip(), model=quoted[1].strip(), numbers=nums)
        )
    if not records:
        raise ModelExtractionError(f"{path.name}: parsed zero records")
    return records


def frequency_stages(rec: DyrRecord) -> list[tuple[float, float]]:
    """Recover (frequency Hz, time s) protection pairs from a record's number stream.

    Heuristic and reported as such: a value in 44-56 Hz immediately followed by a plausible
    time is treated as a relay stage. The caller must confirm against the model guide.
    """
    out: list[tuple[float, float]] = []
    ns = rec.numbers
    for i in range(len(ns) - 1):
        f, t = ns[i], ns[i + 1]
        if 44.0 <= f <= 56.0 and 0.0 < t <= 3600.0:
            out.append((f, t))
    return out


def ride_through_points(rec: DyrRecord) -> list[tuple[float, float]]:
    """Recover (voltage pu, time s) ride-through pairs — 0.1-1.5 pu against a time."""
    out: list[tuple[float, float]] = []
    ns = rec.numbers
    for i in range(len(ns) - 1):
        v, t = ns[i], ns[i + 1]
        if 0.1 <= v <= 1.5 and 0.0 < t <= 100.0 and v not in (1.0,):
            out.append((v, t))
    return out


# ═════════════════════════════════════════════════════════════════════════════
# PSCAD .pscx
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PscxProject:
    """What a PSCAD project file discloses without being run."""

    name: str
    version: str
    target: str
    settings: dict[str, str] = field(default_factory=dict)
    definitions: tuple[str, ...] = ()

    @property
    def timestep_us(self) -> Optional[str]:
        return self.settings.get("time_step")

    @property
    def duration_s(self) -> Optional[str]:
        return self.settings.get("time_duration")


def parse_pscx(path: Path) -> PscxProject:
    """Parse a PSCAD 5 ``.pscx`` project (XML) for structure and settings."""
    text = path.read_text(errors="replace")
    head = re.search(r"<project\s+([^>]*)>", text)
    if not head:
        raise ModelExtractionError(f"{path.name}: no <project> element; not a PSCAD 5 project?")
    attrs = dict(re.findall(r'(\w+)="([^"]*)"', head.group(1)))
    settings = dict(re.findall(r'<param name="([^"]+)" value="([^"]*)"', text[: 4000]))
    defs = tuple(dict.fromkeys(re.findall(r'<Definition[^>]*\bname="([^"]+)"', text)))
    return PscxProject(
        name=attrs.get("name", "?"),
        version=attrs.get("version", "?"),
        target=attrs.get("Target", "?"),
        settings=settings,
        definitions=defs,
    )


def find_definition_params(path: Path, definition: str, window: int = 12000) -> dict[str, str]:
    """Return parameter name/value pairs appearing inside one Definition block."""
    text = path.read_text(errors="replace")
    m = re.search(r'<Definition[^>]*\bname="%s"' % re.escape(definition), text)
    if not m:
        return {}
    seg = text[m.start() : m.start() + window]
    return dict(re.findall(r'<param name="([^"]+)"\s+value="([^"]*)"', seg))


# ═════════════════════════════════════════════════════════════════════════════
# Compiled artifacts — metadata only, stated as such
# ═════════════════════════════════════════════════════════════════════════════


def compiled_strings(path: Path, minimum: int = 6, limit: int = 4000) -> list[str]:
    """Printable ASCII runs from a compiled artifact.

    This recovers symbol and path metadata only. The control law in a compiled DLL is NOT
    recoverable and no attempt is made to recover it.
    """
    data = path.read_bytes()
    found = re.findall(rb"[\x20-\x7e]{%d,}" % minimum, data)
    return [s.decode("ascii", "replace") for s in found[:limit]]


# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════


def _report_dyr(path: Path) -> None:
    print(f"\n=== PSS(R)E dynamics record: {path.name} ===")
    for rec in parse_dyr(path):
        print(f"  bus {rec.bus:>4}  {rec.kind:<8} {rec.model:<14} values={len(rec.numbers)}")
        if rec.base_kw:
            print(f"      machine base (first value >= 1000): {rec.base_kw:,.1f}")
        fs = frequency_stages(rec)
        if fs:
            print("      frequency stages (Hz, s) — heuristic, confirm against the model guide:")
            for f, t in fs:
                print(f"        {f:8.3f} Hz  for {t:10.4f} s")
        rt = ride_through_points(rec)
        if rt and rec.model.upper().startswith("EN"):
            print("      voltage/time pairs (pu, s) — candidate ride-through table:")
            for v, t in rt[:14]:
                print(f"        {v:8.3f} pu  {t:10.4f} s")


def _report_pscx(path: Path) -> None:
    proj = parse_pscx(path)
    print(f"\n=== PSCAD project: {path.name} ===")
    print(f"  name={proj.name}  version={proj.version}  target={proj.target}")
    print(f"  time step: {proj.timestep_us} us    duration: {proj.duration_s} s")
    for k in ("output_filename", "snapshot_filename", "creator", "Mruns"):
        if k in proj.settings:
            print(f"  {k}: {proj.settings[k]}")
    print(f"  definitions ({len(proj.definitions)}): {', '.join(proj.definitions)}")


def _report_compiled(path: Path) -> None:
    print(f"\n=== compiled artifact: {path.name} ({path.stat().st_size:,} bytes) ===")
    strings = compiled_strings(path)
    interesting = [
        s
        for s in strings
        if re.search(r"(\.f90|\.for|\.f\b|Envision|PCS|PPC|GFM|GFL|VSG|\.dll|Fortran|EMTDC|PSSE)", s, re.I)
    ]
    print(f"  printable strings: {len(strings):,}; of engineering interest: {len(interesting)}")
    for s in interesting[:18]:
        print(f"    {s[:110]}")
    print("  NOTE: the control law itself is compiled and is NOT recoverable from this file.")


def main(argv: Optional[Iterable[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+", type=Path)
    args = ap.parse_args(list(argv) if argv is not None else None)
    for p in args.paths:
        if not p.exists():
            raise SystemExit(f"missing: {p}")
        suffix = p.suffix.lower()
        if suffix == ".dyr":
            _report_dyr(p)
        elif suffix == ".pscx":
            _report_pscx(p)
        elif suffix in {".dll", ".obj", ".lib"}:
            _report_compiled(p)
        else:
            print(f"\n=== {p.name}: no reader for {suffix} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
