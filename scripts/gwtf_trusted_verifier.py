"""Execute independently pinned verifier bytes, not candidate imports.

Bootstrap trust must be established outside this program: an independent
custodian reviews and pins the launcher, manifest and complete source bundle,
then invokes the external launcher with the retained manifest SHA256. A pin
supplied by the candidate or a self-check is not proof of independent review.
This launcher does not authenticate execution, establish a sandbox, or grant
writer, review, push or merge authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import types
from pathlib import Path
from typing import Any

LAUNCHER = "gwtf_trusted_verifier.py"
MANIFEST = "manifest.json"
MODULES = (
    "gwtf_checkpoint_readiness",
    "gwtf_checkpoint_receipt",
    "gwtf_interruption_recovery",
    "gwtf_incident",
    "gwtf_checkpoint_workflow",
)
FILES = frozenset({LAUNCHER, *(name + ".py" for name in MODULES)})
HEX = re.compile(r"[0-9a-f]{64}\Z")
MAX_SOURCE_BYTES = 2 * 1024 * 1024


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "duplicate manifest key")
        result[key] = value
    return result


def read_owned(dir_fd: int, name: str) -> bytes:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_uid == os.geteuid()
            and not before.st_mode & 0o022
            and before.st_size <= MAX_SOURCE_BYTES,
            "uncontrolled bundle file",
        )
        raw = stream.read(MAX_SOURCE_BYTES + 1)
        after = os.fstat(stream.fileno())
        require(
            len(raw) <= MAX_SOURCE_BYTES
            and (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            == (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ),
            "bundle file changed while reading",
        )
        return raw


def load_sources(bundle: Path, expected: str) -> dict[str, bytes]:
    require(bool(HEX.fullmatch(expected)), "external manifest pin required")
    require(
        bundle.is_absolute() and bundle == bundle.resolve(),
        "canonical external bundle required",
    )
    require(
        not any((p / ".git").exists() for p in (bundle, *bundle.parents)),
        "bundle inside Git worktree",
    )
    require(
        Path(__file__).absolute() == bundle / LAUNCHER, "external launcher required"
    )
    fd = os.open(bundle, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        require(
            info.st_uid == os.geteuid() and not info.st_mode & 0o077,
            "private bundle directory required",
        )
        require(set(os.listdir(fd)) == FILES | {MANIFEST}, "unexpected bundle files")
        manifest_raw = read_owned(fd, MANIFEST)
        require(sha(manifest_raw) == expected, "manifest pin mismatch")
        data = json.loads(manifest_raw, object_pairs_hook=unique_object)
        require(
            isinstance(data, dict)
            and set(data) == {"schema", "reviewed_commit", "files"}
            and type(data["schema"]) is int
            and data["schema"] == 1
            and isinstance(data["reviewed_commit"], str)
            and bool(re.fullmatch(r"[0-9a-f]{40}", data["reviewed_commit"]))
            and isinstance(data["files"], dict)
            and set(data["files"]) == FILES,
            "invalid manifest schema",
        )
        sources = {name: read_owned(fd, name) for name in sorted(FILES)}
        require(
            all(
                isinstance(data["files"][name], str) and sha(raw) == data["files"][name]
                for name, raw in sources.items()
            ),
            "source digest mismatch",
        )
        return sources
    finally:
        os.close(fd)


def execute(sources: dict[str, bytes], entry: str, arguments: list[str]) -> int:
    # The entire fixed dependency closure has been read and checked before
    # executing any verifier module. No directory is added to sys.path.
    require(
        not any(name in sys.modules for name in MODULES), "verifier already imported"
    )
    for name in MODULES:
        module = types.ModuleType(name)
        module.__file__ = "<pinned-verifier>/" + name + ".py"
        module.__package__ = ""
        sys.modules[name] = module
        exec(compile(sources[name + ".py"], module.__file__, "exec"), module.__dict__)
    sys.argv = [entry + ".py", *arguments]
    result = sys.modules[entry].main()
    if type(result) is not int:
        raise ValueError("invalid verifier exit")
    return result


def main() -> int:
    try:
        require(
            bool(
                sys.flags.isolated
                and sys.flags.no_site
                and sys.flags.dont_write_bytecode
            ),
            "use isolated interpreter with -I -S -B",
        )
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--bundle", type=Path, required=True)
        parser.add_argument("--manifest-sha256", required=True)
        parser.add_argument("entry", choices=MODULES)
        parser.add_argument("arguments", nargs=argparse.REMAINDER)
        args = parser.parse_args()
        sources = load_sources(args.bundle, args.manifest_sha256)
        return execute(sources, args.entry, args.arguments)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print(
            "STOP: trusted verifier bootstrap refused; reconcile independent custody",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
