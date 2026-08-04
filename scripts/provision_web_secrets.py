"""Mint production secrets for the DutchBay web surface (paste into ``fly secrets set``).

This helper generates the two *secret* environment values the auth gate
(:mod:`app.api.auth`) requires in a production posture and prints them, clearly
labelled, ready to paste into ``fly secrets set``:

* ``DUTCHBAY_JWT_SECRET`` — a fresh 48-byte URL-safe HMAC signing secret
  (:func:`secrets.token_urlsafe`). In a production context
  (``DUTCHBAY_ENV=production``) :func:`app.api.auth._jwt_secret` rejects a known
  insecure placeholder or a secret shorter than 32 characters, so a random
  ``token_urlsafe(48)`` (~64 characters) satisfies the length floor.
* ``DUTCHBAY_API_USERS`` — a ``"<user>:<pbkdf2-hash>"`` entry whose hash is produced
  by :func:`app.api.auth.hash_password` (PBKDF2-HMAC-SHA256, the same routine
  :func:`app.api.auth.verify_password` checks a login against).

Inputs are read from the environment (R3/R4/CST-01: argparse, Typer/Click and
``input()`` are banned in these paths):

* ``DUTCHBAY_PROVISION_USER`` — the username to provision (default ``"admin"``).
* ``DUTCHBAY_PROVISION_PASSWORD`` — the plaintext password to hash. Required; an
  absent or empty value is an operator error and exits non-zero (code 2) with an
  actionable message on stderr rather than provisioning a blank credential.

The generated JWT secret is printed once and is not persisted by this script; the
operator is responsible for capturing it into the secret store. Run from the repo
root with the inputs exported::

    DUTCHBAY_PROVISION_USER=admin DUTCHBAY_PROVISION_PASSWORD='...' \\
        python scripts/provision_web_secrets.py

See ``docs/deploy/DEPLOY.md`` for the surrounding deployment runbook (#845, #788,
#663) and ``app/api/auth.py`` for the exact secret semantics enforced at runtime.
"""

from __future__ import annotations

import os
import secrets
import sys

from app.api.auth import hash_password

#: Environment variable naming the username to provision.
_USER_ENV = "DUTCHBAY_PROVISION_USER"
#: Environment variable carrying the plaintext password to hash (required).
_PASSWORD_ENV = "DUTCHBAY_PROVISION_PASSWORD"
#: Default username when :data:`_USER_ENV` is unset.
_DEFAULT_USER = "admin"
#: Byte length passed to :func:`secrets.token_urlsafe` for the JWT secret. 48 bytes
#: yields a ~64-character URL-safe string, comfortably above the 32-character
#: production floor enforced by :func:`app.api.auth._jwt_secret`.
_JWT_SECRET_BYTES = 48
#: Exit code returned when the required password input is missing/empty.
_EXIT_MISSING_PASSWORD = 2


def _read_env(name: str, default: str = "") -> str:
    """Read and strip an environment variable, or return ``default``.

    Args:
        name: The environment variable name to read.
        default: The value returned when the variable is unset or blank.

    Returns:
        The stripped variable value, or ``default`` when unset/blank.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    stripped = raw.strip()
    return stripped if stripped else default


def main() -> int:
    """Generate the web-surface secrets and print them for ``fly secrets set``.

    Reads :data:`_USER_ENV` (default :data:`_DEFAULT_USER`) and the required
    :data:`_PASSWORD_ENV` from the environment, generates a fresh JWT secret,
    hashes the password with :func:`app.api.auth.hash_password`, and prints the
    ``DUTCHBAY_JWT_SECRET`` value, the ``DUTCHBAY_API_USERS`` value, and a ready-to-run
    ``fly secrets set`` line with the generated values substituted.

    Returns:
        ``0`` on success; :data:`_EXIT_MISSING_PASSWORD` (2) when the required
        password input is absent or empty (an actionable error is written to
        stderr in that case).
    """
    user = _read_env(_USER_ENV, _DEFAULT_USER)
    password = _read_env(_PASSWORD_ENV)
    if not password:
        print(
            f"error: {_PASSWORD_ENV} is required and must be non-empty.\n"
            f"  Set it in the environment before running, for example:\n"
            f"    {_PASSWORD_ENV}='<strong-password>' "
            f"{_USER_ENV}={user} python scripts/provision_web_secrets.py",
            file=sys.stderr,
        )
        return _EXIT_MISSING_PASSWORD

    jwt_secret = secrets.token_urlsafe(_JWT_SECRET_BYTES)
    pw_hash = hash_password(password)
    api_users = f"{user}:{pw_hash}"

    print("# DutchBay web-surface secrets (generated) --------------------------------")
    print("# The JWT secret below is shown once and is NOT stored by this script;")
    print("# capture it into your secret store now (it cannot be recovered later).")
    print("")
    print("# DUTCHBAY_JWT_SECRET value:")
    print(jwt_secret)
    print("")
    print(f"# DUTCHBAY_API_USERS value (username '{user}'):")
    print(api_users)
    print("")
    print("# Ready-to-run (sets both secrets on the Fly app):")
    print(
        "# NOTE: values are single-quoted because the pbkdf2 hash in DUTCHBAY_API_USERS"
    )
    print(
        "# contains '$' field separators that an unquoted shell would expand (mangling"
    )
    print("# the credential map -> every login 401s). Keep the quotes when you paste.")
    print(
        f"fly secrets set "
        f"DUTCHBAY_JWT_SECRET='{jwt_secret}' "
        f"DUTCHBAY_API_USERS='{api_users}'"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
