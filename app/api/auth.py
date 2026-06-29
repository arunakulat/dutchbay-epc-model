"""Authentication for the wizard-facing web surface (CASPER / CESSPIT).

The web service exposes client financials and full KPI results; ``RPT-3`` flagged
that ``/cases*`` and ``/jobs*`` had *no* authentication and no per-client
isolation. This module is the gate: an OAuth2 bearer flow backed by **stdlib-only**
primitives —

* **HMAC-SHA256 JWTs** (``HS256``), hand-rolled on :mod:`hmac`/:mod:`hashlib`, and
* **PBKDF2-HMAC-SHA256** password hashing (:func:`hashlib.pbkdf2_hmac`),

so the feature adds **no new dependency** and leaves the strict ``requirements.txt``
lock and the ``pip-audit`` security gate untouched (no JWT/passlib/multipart).

Configuration is read from the environment on **every** call and is **fail-closed**
(CESSPIT — config explicit, fail loud):

* ``DUTCHBAY_JWT_SECRET`` — HMAC signing secret. **Required**; a missing/empty value
  is a *server misconfiguration* and surfaces as a 500, never a baked-in default.
* ``DUTCHBAY_API_USERS`` — ``"user:<pbkdf2-hash>,user2:<hash>"``. Absent ⇒ no user can
  authenticate (every login is rejected). Hashes are produced by :func:`hash_password`.

Every authentication failure is a 401 with a ``WWW-Authenticate: Bearer`` challenge;
the token *subject* is what the API binds each :class:`~app.jobs.models.JobRecord` to
for per-client isolation.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from typing import Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# --------------------------------------------------------------------------- #
# Constants (CESSPIT: explicit, documented — not buried magic).
# --------------------------------------------------------------------------- #
#: PBKDF2 hash scheme tag stored as the first ``$``-delimited field.
_PBKDF2_SCHEME = "pbkdf2_sha256"
#: PBKDF2 iteration count for new hashes (OWASP 2023 floor for PBKDF2-HMAC-SHA256).
_PBKDF2_ITERATIONS = 600_000
#: Salt length in bytes for new password hashes.
_PBKDF2_SALT_BYTES = 16
#: The only JWT algorithm accepted — pinned to defeat ``alg: none`` / alg-confusion.
_JWT_ALG = "HS256"
#: Default access-token lifetime (seconds).
_DEFAULT_TOKEN_TTL_SECONDS = 3600

#: Bearer-token extractor. ``auto_error=False`` so *this* module owns the 401 shape
#: (consistent ``WWW-Authenticate`` challenge) rather than FastAPI's default.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


class AuthError(Exception):
    """Internal token-validation failure, translated to a 401 at the dependency.

    Raised by :func:`decode_token` for any malformed/forged/expired token. Callers
    that face the network (the FastAPI dependency) convert it to an
    :class:`fastapi.HTTPException` 401; the distinction keeps the pure crypto layer
    framework-agnostic and unit-testable (CASPER).
    """


# --------------------------------------------------------------------------- #
# base64url helpers (JWT + hash field encoding, no padding).
# --------------------------------------------------------------------------- #
def _b64url_encode(raw: bytes) -> str:
    """Encode bytes as unpadded base64url (the JWT/PBKDF2 field encoding)."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    """Decode unpadded base64url back to bytes (re-adding the stripped padding)."""
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


# --------------------------------------------------------------------------- #
# Password hashing (PBKDF2-HMAC-SHA256).
# --------------------------------------------------------------------------- #
def hash_password(
    password: str,
    *,
    iterations: int = _PBKDF2_ITERATIONS,
    salt: Optional[bytes] = None,
) -> str:
    """Hash a password as ``pbkdf2_sha256$<iters>$<salt>$<hash>`` (base64url fields).

    Args:
        password: The plaintext password to hash.
        iterations: PBKDF2 iteration count (defaults to the module floor).
        salt: Optional explicit salt (for deterministic tests); a fresh
            cryptographically-random salt is generated when omitted.

    Returns:
        The self-describing encoded hash, safe to store in ``DUTCHBAY_API_USERS``
        (no ``:`` or ``,`` in any field, so the env parsing stays unambiguous).
    """
    if salt is None:
        salt = os.urandom(_PBKDF2_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return (
        f"{_PBKDF2_SCHEME}${iterations}$"
        f"{_b64url_encode(salt)}${_b64url_encode(derived)}"
    )


def verify_password(password: str, encoded: str) -> bool:
    """Verify a plaintext password against an encoded PBKDF2 hash (constant-time).

    Args:
        password: The candidate plaintext.
        encoded: A hash previously produced by :func:`hash_password`.

    Returns:
        ``True`` iff the password matches. Any malformed ``encoded`` string returns
        ``False`` (never raises) — a bad stored hash must not 500 a login attempt.
    """
    try:
        scheme, iter_str, salt_str, hash_str = encoded.split("$")
        if scheme != _PBKDF2_SCHEME:
            return False
        iterations = int(iter_str)
        salt = _b64url_decode(salt_str)
        expected = _b64url_decode(hash_str)
    except (ValueError, binascii.Error):
        return False
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(derived, expected)


# --------------------------------------------------------------------------- #
# JWT (HS256) — hand-rolled on stdlib hmac/hashlib.
# --------------------------------------------------------------------------- #
def create_access_token(
    sub: str,
    *,
    secret: str,
    expires_in: int = _DEFAULT_TOKEN_TTL_SECONDS,
    now: Optional[int] = None,
) -> str:
    """Mint a signed ``HS256`` JWT for ``sub`` with an expiry claim.

    Args:
        sub: The token subject (the authenticated username / client id).
        secret: The HMAC signing secret.
        expires_in: Token lifetime in seconds from ``now``.
        now: Optional issue time (epoch seconds) for deterministic tests; defaults
            to the current time.

    Returns:
        The compact ``header.payload.signature`` JWT string.
    """
    issued = int(time.time()) if now is None else now
    header = {"alg": _JWT_ALG, "typ": "JWT"}
    payload = {"sub": sub, "iat": issued, "exp": issued + expires_in}
    segments = [
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ]
    signing_input = ".".join(segments).encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    segments.append(_b64url_encode(signature))
    return ".".join(segments)


def decode_token(token: str, *, secret: str, now: Optional[int] = None) -> str:
    """Validate a JWT and return its subject, or raise :class:`AuthError`.

    Verifies the signature in constant time, rejects any algorithm other than the
    pinned ``HS256`` (defeating ``alg: none`` / alg-confusion forgeries), and
    enforces the ``exp`` claim.

    Args:
        token: The compact JWT string.
        secret: The HMAC secret the token must be signed with.
        now: Optional validation time (epoch seconds) for deterministic tests.

    Returns:
        The token's ``sub`` claim.

    Raises:
        AuthError: If the token is malformed, mis-signed, uses an unexpected
            algorithm, is expired, or carries no usable subject.
    """
    current = int(time.time()) if now is None else now
    try:
        header_seg, payload_seg, sig_seg = token.split(".")
    except ValueError as exc:
        raise AuthError("malformed token") from exc

    signing_input = f"{header_seg}.{payload_seg}".encode("ascii")
    expected_sig = hmac.new(
        secret.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    try:
        actual_sig = _b64url_decode(sig_seg)
        header = json.loads(_b64url_decode(header_seg))
        payload = json.loads(_b64url_decode(payload_seg))
    except (binascii.Error, ValueError) as exc:
        raise AuthError("malformed token") from exc

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise AuthError("bad signature")
    if not isinstance(header, dict) or header.get("alg") != _JWT_ALG:
        raise AuthError("unexpected algorithm")
    if not isinstance(payload, dict):
        raise AuthError("malformed payload")

    exp = payload.get("exp")
    if not isinstance(exp, (int, float)) or isinstance(exp, bool) or current >= exp:
        raise AuthError("token expired")
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise AuthError("missing subject")
    return sub


# --------------------------------------------------------------------------- #
# Environment-backed configuration (read every call; fail-closed — CESSPIT).
# --------------------------------------------------------------------------- #
def _jwt_secret() -> str:
    """Return the configured JWT secret, or 500 if the server is unconfigured.

    A missing secret is an operator error, not a client error: failing closed with
    a 500 (and never a hard-coded fallback secret) is the only safe behaviour.
    """
    secret = os.environ.get("DUTCHBAY_JWT_SECRET", "")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="authentication is not configured (DUTCHBAY_JWT_SECRET unset)",
        )
    return secret


def _api_users() -> Dict[str, str]:
    """Parse ``DUTCHBAY_API_USERS`` into a ``{username: encoded_hash}`` map.

    Entries are comma-separated ``username:hash`` pairs. Blank or malformed entries
    are skipped (a single bad entry must not lock everyone out, nor crash a login).
    An absent variable yields an empty map ⇒ every login is rejected (fail-closed).
    """
    raw = os.environ.get("DUTCHBAY_API_USERS", "")
    users: Dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        username, sep, encoded = entry.partition(":")
        if sep and username and encoded:
            users[username] = encoded
    return users


def authenticate_user(username: str, password: str) -> Optional[str]:
    """Return the username if the credentials are valid, else ``None``.

    Args:
        username: The submitted username.
        password: The submitted plaintext password.

    Returns:
        The authenticated subject (``username``) on success, ``None`` otherwise.
    """
    encoded = _api_users().get(username)
    if encoded is None or not verify_password(password, encoded):
        return None
    return username


def login_for_access_token(username: str, password: str) -> str:
    """Authenticate credentials and mint an access token, or raise 401.

    Args:
        username: The submitted username.
        password: The submitted plaintext password.

    Returns:
        A freshly-minted ``HS256`` access token for the authenticated subject.

    Raises:
        HTTPException: 401 if the credentials are invalid; 500 (via
            :func:`_jwt_secret`) if the signing secret is unconfigured.
    """
    subject = authenticate_user(username, password)
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return create_access_token(subject, secret=_jwt_secret())


def _unauthorized() -> HTTPException:
    """Build the canonical 401 for a missing/invalid bearer token."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_subject(token: Optional[str] = Depends(oauth2_scheme)) -> str:
    """FastAPI dependency: resolve the bearer token to its subject, or 401.

    Args:
        token: The bearer token extracted from the ``Authorization`` header
            (``None`` when the header is absent).

    Returns:
        The authenticated subject (the token's ``sub`` claim) — bound by the API to
        each job for per-client isolation.

    Raises:
        HTTPException: 401 when the token is missing, malformed, forged, or expired;
            500 when the signing secret is unconfigured.
    """
    if not token:
        raise _unauthorized()
    secret = _jwt_secret()
    try:
        return decode_token(token, secret=secret)
    except AuthError as exc:
        raise _unauthorized() from exc
