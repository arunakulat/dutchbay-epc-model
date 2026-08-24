"""Bounded listener-specific readiness control for the Codespaces SSH daemon."""

from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

EXPECTED_MARKER = "sshd_started_before_post_create"
EXPECTED_BANNER_PREFIX = b"SSH-2.0-OpenSSH_"
MAX_IDENTIFICATION_LINE_BYTES = 255


class SshdReadinessError(RuntimeError):
    """Raised when the governed SSH listener is not ready before the deadline."""


def _marker_is_ready(marker_path: Path | None) -> bool:
    """Return whether the runtime-only pre-lifecycle marker is exact and safe."""
    if marker_path is None:
        return True
    try:
        return (
            marker_path.is_file()
            and not marker_path.is_symlink()
            and marker_path.read_text(encoding="ascii").strip() == EXPECTED_MARKER
        )
    except (OSError, UnicodeError):
        return False


def wait_for_sshd(
    *,
    host: str,
    port: int,
    timeout_seconds: float,
    marker_path: Path | None = None,
) -> None:
    """Wait for the exact OpenSSH banner and, when required, its runtime marker."""
    if host != "127.0.0.1" or not 1 <= port <= 65535 or timeout_seconds <= 0:
        raise SshdReadinessError("SSH readiness parameters differ from policy")
    deadline = time.monotonic() + timeout_seconds
    last_error = "listener unavailable"
    while time.monotonic() < deadline:
        if not _marker_is_ready(marker_path):
            last_error = "pre-lifecycle marker unavailable"
            time.sleep(0.05)
            continue
        try:
            remaining = max(deadline - time.monotonic(), 0.01)
            with socket.create_connection(
                (host, port), timeout=min(0.25, remaining)
            ) as stream:
                banner = bytearray()
                while b"\n" not in banner:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or len(banner) >= MAX_IDENTIFICATION_LINE_BYTES:
                        raise TimeoutError("SSH identification line was incomplete")
                    stream.settimeout(min(0.25, remaining))
                    chunk = stream.recv(MAX_IDENTIFICATION_LINE_BYTES - len(banner))
                    if not chunk:
                        raise ConnectionError("SSH identification peer closed early")
                    banner.extend(chunk)
        except OSError as exc:
            last_error = type(exc).__name__
            time.sleep(0.05)
            continue
        line, _, _ = bytes(banner).partition(b"\n")
        identification = line + b"\n"
        if (
            identification.endswith(b"\r\n")
            and identification.startswith(EXPECTED_BANNER_PREFIX)
            and len(identification) > len(EXPECTED_BANNER_PREFIX) + 2
            and len(identification) <= MAX_IDENTIFICATION_LINE_BYTES
        ):
            return
        last_error = "unexpected or incomplete listener banner"
        time.sleep(0.05)
    raise SshdReadinessError(
        f"OpenSSH listener was not ready before deadline: {last_error}"
    )


def main() -> int:
    """Run the fixed Codespaces listener check without a general CLI surface."""
    if len(sys.argv) not in {2, 3}:
        raise SshdReadinessError(
            "expected timeout seconds and optional pre-lifecycle marker"
        )
    try:
        timeout_seconds = float(sys.argv[1])
    except ValueError as exc:
        raise SshdReadinessError("timeout seconds must be numeric") from exc
    marker_path = Path(sys.argv[2]) if len(sys.argv) == 3 else None
    wait_for_sshd(
        host="127.0.0.1",
        port=2222,
        timeout_seconds=timeout_seconds,
        marker_path=marker_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
