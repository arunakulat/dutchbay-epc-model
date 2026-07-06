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

* ``DUTCHBAY_ENV`` — deployment posture selector. ``production`` / ``prod`` engages the
  hardened posture below; anything else (unset, ``development``, ``test``, …) keeps the
  permissive dev/backward-compatible behaviour. This is the single switch that turns the
  opt-in #842 defences into mandatory production ones (#858).
* ``DUTCHBAY_JWT_SECRET`` — HMAC signing secret. **Required**; a missing/empty value
  is a *server misconfiguration* and surfaces as a 500, never a baked-in default. In a
  **production** context a *known insecure placeholder* (e.g. ``changeme``, ``secret``,
  ``dev``) or a too-short secret is ALSO rejected 500 — no weak-secret fallback (#858).
* ``DUTCHBAY_API_USERS`` — ``"user:<pbkdf2-hash>,user2:<hash>"``. Absent ⇒ no user can
  authenticate (every login is rejected). Hashes are produced by :func:`hash_password`.
* ``DUTCHBAY_JWT_ISSUER`` / ``DUTCHBAY_JWT_AUDIENCE`` — ``iss`` / ``aud`` binding. When
  set, issued tokens carry the claim and validation *requires* an exact match (a token
  minted for a different issuer/audience is rejected 401). In a **development** context
  the binding is **opt-in** (unset ⇒ neither stamped nor enforced, backward-compatible
  with #842). In a **production** context BOTH are **mandatory**: an unset issuer or
  audience is a misconfiguration (500) so the surface can never accept an unbound token
  (CCCDIR — documented, config-driven; no baked-in default issuer/audience) (#858).

Token validation additionally enforces ``exp`` (expiry), the pinned ``HS256`` algorithm
(defeating ``alg: none`` / alg-confusion), and — when present — ``iat`` / ``nbf`` against
a small clock-skew tolerance so a token minted "in the future" (a mis-set issuer clock or
a forged forward-dated claim) is rejected rather than silently trusted (#858, closing the
``nbf`` / ``iat`` residual #842 flagged).

Every authentication failure is a 401 with a ``WWW-Authenticate: Bearer`` challenge;
the token *subject* is what the API binds each :class:`~app.jobs.models.JobRecord` to
for per-client isolation.

Out of code scope (user-held ops, tracked on #858): token revocation / ``jti`` denylist /
rotation, the secret store choice, and transport (TLS) termination — a leaked token stays
valid until ``exp`` and no code-only change can revoke it.
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
#: ``DUTCHBAY_ENV`` values that engage the hardened production posture (case-insensitive).
_PRODUCTION_ENV_VALUES = frozenset({"production", "prod"})
#: Minimum acceptable secret length (bytes) in a production context. A ~256-bit random
#: secret is ~43 base64url chars; 32 is a conservative floor that still rejects trivially
#: guessable short strings while not fighting a genuinely random operator-provided secret.
_MIN_PROD_SECRET_LEN = 32
#: Known insecure placeholder secrets refused outright in production (lower-cased compare).
#: These are the classic copy-paste-from-a-tutorial values; a real deployment must never
#: ship one. Not exhaustive — the length floor is the general guard; this is defence in
#: depth against the specific values that slip through review.
_INSECURE_SECRET_VALUES = frozenset(
    {
        "changeme",
        "change-me",
        "changethis",
        "secret",
        "secretkey",
        "secret-key",
        "password",
        "dev",
        "development",
        "test",
        "testing",
        "default",
        "insecure",
        "please-change",
        "your-secret-here",
        "your-256-bit-secret",
    }
)
#: Clock-skew tolerance (seconds) applied to ``iat`` / ``nbf`` so a token minted on a peer
#: whose clock is a few seconds fast is not spuriously rejected, while a wildly future-dated
#: (forged) token still is. Symmetric with typical JWT-library defaults.
_CLOCK_SKEW_SECONDS = 60

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
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
) -> str:
    """Mint a signed ``HS256`` JWT for ``sub`` with an expiry claim.

    Args:
        sub: The token subject (the authenticated username / client id).
        secret: The HMAC signing secret.
        expires_in: Token lifetime in seconds from ``now``.
        now: Optional issue time (epoch seconds) for deterministic tests; defaults
            to the current time.
        issuer: Optional ``iss`` claim to stamp (omitted from the payload when
            ``None`` so tokens stay backward-compatible with issuer-agnostic
            deployments).
        audience: Optional ``aud`` claim to stamp (omitted when ``None``).

    Returns:
        The compact ``header.payload.signature`` JWT string.
    """
    issued = int(time.time()) if now is None else now
    header = {"alg": _JWT_ALG, "typ": "JWT"}
    payload = {"sub": sub, "iat": issued, "exp": issued + expires_in}
    if issuer is not None:
        payload["iss"] = issuer
    if audience is not None:
        payload["aud"] = audience
    segments = [
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ]
    signing_input = ".".join(segments).encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    segments.append(_b64url_encode(signature))
    return ".".join(segments)


def decode_token(
    token: str,
    *,
    secret: str,
    now: Optional[int] = None,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
) -> str:
    """Validate a JWT and return its subject, or raise :class:`AuthError`.

    Verifies the signature in constant time, rejects any algorithm other than the
    pinned ``HS256`` (defeating ``alg: none`` / alg-confusion forgeries), and
    enforces the ``exp`` claim. A present ``iat`` / ``nbf`` claim is checked against
    ``now`` with a small clock-skew tolerance, so a token dated in the future (a
    mis-set clock or a forged forward-dated claim) is rejected rather than trusted.
    When ``issuer`` / ``audience`` are supplied, the matching ``iss`` / ``aud`` claim
    must be present and equal (defeating token replay across issuers/audiences); when
    they are ``None`` the claim is not inspected (opt-in binding).

    Args:
        token: The compact JWT string.
        secret: The HMAC secret the token must be signed with.
        now: Optional validation time (epoch seconds) for deterministic tests.
        issuer: When set, the required ``iss`` claim (exact match, else 401).
        audience: When set, the required ``aud`` claim (exact match, else 401).

    Returns:
        The token's ``sub`` claim.

    Raises:
        AuthError: If the token is malformed, mis-signed, uses an unexpected
            algorithm, is expired, is not yet valid / future-dated (``nbf`` / ``iat``),
            has a mismatched/absent issuer or audience (when one is required), or
            carries no usable subject.
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
    # "Not-yet-valid" checks: a token whose nbf/iat is in the future (beyond the skew
    # tolerance) is a mis-set clock or a forged forward-dated claim -- reject it rather
    # than silently accept a token that shouldn't be usable yet (#858, residual #842).
    nbf = payload.get("nbf")
    if isinstance(nbf, (int, float)) and not isinstance(nbf, bool):
        if current + _CLOCK_SKEW_SECONDS < nbf:
            raise AuthError("token not yet valid")
    iat = payload.get("iat")
    if isinstance(iat, (int, float)) and not isinstance(iat, bool):
        if current + _CLOCK_SKEW_SECONDS < iat:
            raise AuthError("token issued in the future")
    if issuer is not None and payload.get("iss") != issuer:
        raise AuthError("issuer mismatch")
    if audience is not None and payload.get("aud") != audience:
        raise AuthError("audience mismatch")
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise AuthError("missing subject")
    return sub


# --------------------------------------------------------------------------- #
# Environment-backed configuration (read every call; fail-closed — CESSPIT).
# --------------------------------------------------------------------------- #
def _is_production() -> bool:
    """Return ``True`` when ``DUTCHBAY_ENV`` selects the hardened production posture.

    The switch is deliberately explicit and opt-*in*: an unset/unknown value stays in
    the permissive dev posture, so a developer running the app locally never has to
    provision a mandatory issuer/audience. Only ``production`` / ``prod`` (case- and
    whitespace-insensitive) engages the mandatory posture (#858).
    """
    return os.environ.get("DUTCHBAY_ENV", "").strip().lower() in _PRODUCTION_ENV_VALUES


def _misconfigured(detail: str) -> HTTPException:
    """Build the canonical 500 for a server-side auth misconfiguration (fail-closed)."""
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail,
    )


def _jwt_secret() -> str:
    """Return the configured JWT secret, or 500 if the server is unconfigured.

    A missing secret is an operator error, not a client error: failing closed with
    a 500 (and never a hard-coded fallback secret) is the only safe behaviour. In a
    **production** context (:func:`_is_production`) a *known insecure placeholder*
    (``changeme``, ``secret``, ``dev``, …) or a secret shorter than
    :data:`_MIN_PROD_SECRET_LEN` is *also* rejected 500 — there is no silent weak-secret
    fallback, so a deployment cannot accidentally ship a guessable signing key (#858).
    The weak-secret rules are relaxed off-production so tests and local dev may use a
    short literal secret without provisioning a 32-byte one.
    """
    secret = os.environ.get("DUTCHBAY_JWT_SECRET", "")
    if not secret:
        raise _misconfigured(
            "authentication is not configured (DUTCHBAY_JWT_SECRET unset)"
        )
    if _is_production():
        if secret.strip().lower() in _INSECURE_SECRET_VALUES:
            raise _misconfigured(
                "DUTCHBAY_JWT_SECRET is a known insecure default; "
                "set a strong random secret in production"
            )
        if len(secret) < _MIN_PROD_SECRET_LEN:
            raise _misconfigured(
                "DUTCHBAY_JWT_SECRET is too short for production "
                f"(need >= {_MIN_PROD_SECRET_LEN} chars)"
            )
    return secret


def _jwt_issuer() -> Optional[str]:
    """Return the configured ``iss`` binding — mandatory in production, opt-in in dev.

    An empty/whitespace value is treated as unset so a blank env var never becomes a
    token-rejecting ``iss=""`` requirement by accident. In a **production** context an
    unset issuer is a misconfiguration (500): a production surface must not accept an
    unbound token (#858). Off-production the binding stays opt-in (unset ⇒ ``None`` ⇒
    not enforced), backward-compatible with #842.
    """
    issuer = os.environ.get("DUTCHBAY_JWT_ISSUER", "").strip() or None
    if issuer is None and _is_production():
        raise _misconfigured(
            "DUTCHBAY_JWT_ISSUER is required in production "
            "(issuer/audience binding is mandatory)"
        )
    return issuer


def _jwt_audience() -> Optional[str]:
    """Return the configured ``aud`` binding — mandatory in production, opt-in in dev.

    Mirror of :func:`_jwt_issuer`: an unset audience is a 500 in a production context so
    no unbound token is accepted, and stays opt-in off-production (#858 / #842).
    """
    audience = os.environ.get("DUTCHBAY_JWT_AUDIENCE", "").strip() or None
    if audience is None and _is_production():
        raise _misconfigured(
            "DUTCHBAY_JWT_AUDIENCE is required in production "
            "(issuer/audience binding is mandatory)"
        )
    return audience


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


# A fixed dummy PBKDF2 hash (random password + salt, computed once at import) used to
# equalize the cost of an unknown-username login with a known-username-wrong-password login.
# Without it, authenticate_user short-circuits on an unknown username and never runs the
# ~600k-iteration PBKDF2, so the 401 returns in microseconds while a real username pays the
# full hashing cost -- a measurable timing side channel that lets an unauthenticated caller
# enumerate valid usernames on the public /token route (CWE-208 / CWE-204, round-2 audit).
_DUMMY_PASSWORD_HASH = hash_password(os.urandom(32).hex())


def authenticate_user(username: str, password: str) -> Optional[str]:
    """Return the username if the credentials are valid, else ``None``.

    Runs a PBKDF2 verification on both the known- and unknown-username paths so the
    response time does not reveal whether ``username`` exists (constant-time w.r.t.
    username existence; the identical 401 body already closes the message channel).

    Args:
        username: The submitted username.
        password: The submitted plaintext password.

    Returns:
        The authenticated subject (``username``) on success, ``None`` otherwise.
    """
    encoded = _api_users().get(username)
    if encoded is None:
        # Unknown user: still pay the PBKDF2 cost against a dummy hash and discard it, so
        # this path is indistinguishable by timing from a wrong password for a real user.
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None
    if not verify_password(password, encoded):
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
    return create_access_token(
        subject,
        secret=_jwt_secret(),
        issuer=_jwt_issuer(),
        audience=_jwt_audience(),
    )


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
        return decode_token(
            token,
            secret=secret,
            issuer=_jwt_issuer(),
            audience=_jwt_audience(),
        )
    except AuthError as exc:
        raise _unauthorized() from exc
