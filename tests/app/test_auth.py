"""Tests for the web-surface authentication (RPT-3).

Covers the stdlib crypto layer (PBKDF2 hashing, HS256 JWTs and every rejection
branch of :func:`~app.api.auth.decode_token`), the fail-closed environment config,
and the HTTP-level flow — login, a 401 on unauthenticated access, and cross-client
job isolation — driven through the unified app.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import pytest
from fastapi import HTTPException

from app.api import auth
from app.api.auth import (
    AuthError,
    authenticate_user,
    create_access_token,
    decode_token,
    get_current_subject,
    hash_password,
    login_for_access_token,
    verify_password,
)

_SECRET = "test-signing-secret"


# --------------------------------------------------------------------------- #
# Password hashing (PBKDF2)
# --------------------------------------------------------------------------- #
def test_hash_password_roundtrip() -> None:
    encoded = hash_password("correct horse")
    assert encoded.startswith("pbkdf2_sha256$")
    assert verify_password("correct horse", encoded) is True
    assert verify_password("wrong", encoded) is False


def test_hash_password_is_salted() -> None:
    # Random salt => two hashes of the same password differ, yet both verify.
    a = hash_password("pw")
    b = hash_password("pw")
    assert a != b
    assert verify_password("pw", a) and verify_password("pw", b)


def test_hash_password_explicit_salt_is_deterministic() -> None:
    salt = b"\x00" * 16
    assert hash_password("pw", salt=salt, iterations=1000) == hash_password(
        "pw", salt=salt, iterations=1000
    )


@pytest.mark.parametrize(
    "bad",
    [
        "not-a-hash",
        "a$b$c",  # too few fields
        "scrypt$1$x$y",  # wrong scheme
        "pbkdf2_sha256$notanint$AAAA$AAAA",  # iterations not an int
        "pbkdf2_sha256$1000$!!!!$AAAA",  # salt not base64
    ],
)
def test_verify_password_rejects_malformed_without_raising(bad: str) -> None:
    assert verify_password("pw", bad) is False


# --------------------------------------------------------------------------- #
# JWT create / decode
# --------------------------------------------------------------------------- #
def test_token_roundtrip() -> None:
    token = create_access_token("alice", secret=_SECRET, expires_in=100, now=1000)
    assert decode_token(token, secret=_SECRET, now=1000) == "alice"


def test_decode_rejects_wrong_secret() -> None:
    token = create_access_token("alice", secret=_SECRET, now=1000)
    with pytest.raises(AuthError):
        decode_token(token, secret="other-secret", now=1000)


def test_decode_rejects_tampered_payload() -> None:
    token = create_access_token("alice", secret=_SECRET, now=1000)
    header, payload, sig = token.split(".")
    forged_payload = auth._b64url_encode(
        json.dumps({"sub": "attacker", "exp": 9999999999}).encode()
    )
    with pytest.raises(AuthError):
        decode_token(f"{header}.{forged_payload}.{sig}", secret=_SECRET, now=1000)


def test_decode_rejects_expired() -> None:
    token = create_access_token("alice", secret=_SECRET, expires_in=10, now=1000)
    with pytest.raises(AuthError, match="expired"):
        decode_token(token, secret=_SECRET, now=2000)


# --------------------------------------------------------------------------- #
# Issuer / audience binding (opt-in; enforced only when required)
# --------------------------------------------------------------------------- #
def test_token_roundtrip_with_issuer_and_audience() -> None:
    token = create_access_token(
        "alice",
        secret=_SECRET,
        expires_in=100,
        now=1000,
        issuer="dutchbay",
        audience="wizard",
    )
    assert (
        decode_token(
            token, secret=_SECRET, now=1000, issuer="dutchbay", audience="wizard"
        )
        == "alice"
    )


def test_decode_rejects_wrong_issuer() -> None:
    token = create_access_token("alice", secret=_SECRET, now=1000, issuer="dutchbay")
    with pytest.raises(AuthError, match="issuer"):
        decode_token(token, secret=_SECRET, now=1000, issuer="other")


def test_decode_rejects_missing_issuer_when_required() -> None:
    # Token minted with no iss, but validation requires one -> reject.
    token = create_access_token("alice", secret=_SECRET, now=1000)
    with pytest.raises(AuthError, match="issuer"):
        decode_token(token, secret=_SECRET, now=1000, issuer="dutchbay")


def test_decode_rejects_wrong_audience() -> None:
    token = create_access_token("alice", secret=_SECRET, now=1000, audience="wizard")
    with pytest.raises(AuthError, match="audience"):
        decode_token(token, secret=_SECRET, now=1000, audience="other")


def test_decode_rejects_missing_audience_when_required() -> None:
    token = create_access_token("alice", secret=_SECRET, now=1000)
    with pytest.raises(AuthError, match="audience"):
        decode_token(token, secret=_SECRET, now=1000, audience="wizard")


def test_decode_ignores_issuer_audience_when_not_required() -> None:
    # A token carrying iss/aud still validates when the verifier doesn't require them
    # (opt-in binding; backward-compatible with issuer/audience-agnostic deployments).
    token = create_access_token(
        "alice", secret=_SECRET, now=1000, issuer="dutchbay", audience="wizard"
    )
    assert decode_token(token, secret=_SECRET, now=1000) == "alice"


@pytest.mark.parametrize("bad", ["only-one-part", "two.parts", "a.b.c.d"])
def test_decode_rejects_wrong_segment_count(bad: str) -> None:
    with pytest.raises(AuthError, match="malformed"):
        decode_token(bad, secret=_SECRET)


def _signed(header: Any, payload: Any, *, secret: str = _SECRET) -> str:
    """Build a token signed with ``secret`` but arbitrary header/payload objects."""
    h = auth._b64url_encode(json.dumps(header).encode())
    p = auth._b64url_encode(json.dumps(payload).encode())
    sig = hmac.new(secret.encode(), f"{h}.{p}".encode("ascii"), hashlib.sha256).digest()
    return f"{h}.{p}.{auth._b64url_encode(sig)}"


def test_decode_rejects_alg_none() -> None:
    # Validly signed, but the header pins a non-HS256 algorithm (alg-confusion).
    token = _signed({"alg": "none", "typ": "JWT"}, {"sub": "x", "exp": 9999999999})
    with pytest.raises(AuthError, match="algorithm"):
        decode_token(token, secret=_SECRET, now=1000)


def test_decode_rejects_non_dict_header() -> None:
    token = _signed(["not", "a", "dict"], {"sub": "x", "exp": 9999999999})
    with pytest.raises(AuthError, match="algorithm"):
        decode_token(token, secret=_SECRET, now=1000)


def test_decode_rejects_non_dict_payload() -> None:
    token = _signed({"alg": "HS256"}, ["not", "a", "dict"])
    with pytest.raises(AuthError, match="payload"):
        decode_token(token, secret=_SECRET, now=1000)


@pytest.mark.parametrize("exp", [None, "soon", True])
def test_decode_rejects_bad_or_missing_exp(exp: Any) -> None:
    payload = {"sub": "x"} if exp is None else {"sub": "x", "exp": exp}
    token = _signed({"alg": "HS256"}, payload)
    with pytest.raises(AuthError, match="expired"):
        decode_token(token, secret=_SECRET, now=1000)


def test_decode_rejects_missing_subject() -> None:
    token = _signed({"alg": "HS256"}, {"exp": 9999999999})
    with pytest.raises(AuthError, match="subject"):
        decode_token(token, secret=_SECRET, now=1000)


def test_decode_rejects_invalid_base64_signature() -> None:
    # A 1-char final segment can never be valid base64 (binascii.Error path).
    token = "aGVhZGVy.cGF5bG9hZA.x"
    with pytest.raises(AuthError, match="malformed"):
        decode_token(token, secret=_SECRET, now=1000)


def test_decode_rejects_non_json_header() -> None:
    h = auth._b64url_encode(b"{not json")
    p = auth._b64url_encode(json.dumps({"sub": "x", "exp": 9999999999}).encode())
    sig = hmac.new(
        _SECRET.encode(), f"{h}.{p}".encode("ascii"), hashlib.sha256
    ).digest()
    with pytest.raises(AuthError, match="malformed"):
        decode_token(f"{h}.{p}.{auth._b64url_encode(sig)}", secret=_SECRET, now=1000)


# --------------------------------------------------------------------------- #
# Environment config (fail-closed)
# --------------------------------------------------------------------------- #
def test_jwt_secret_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DUTCHBAY_JWT_SECRET", "s3cret")
    assert auth._jwt_secret() == "s3cret"


@pytest.mark.parametrize("value", [None, ""])
def test_jwt_secret_missing_is_500(monkeypatch: pytest.MonkeyPatch, value: Any) -> None:
    if value is None:
        monkeypatch.delenv("DUTCHBAY_JWT_SECRET", raising=False)
    else:
        monkeypatch.setenv("DUTCHBAY_JWT_SECRET", value)
    with pytest.raises(HTTPException) as exc:
        auth._jwt_secret()
    assert exc.value.status_code == 500


def test_api_users_parsing_skips_malformed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DUTCHBAY_API_USERS",
        " alice:HASH1 , bob:HASH2 ,, no-colon , :no-user , trailing: ",
    )
    assert auth._api_users() == {"alice": "HASH1", "bob": "HASH2"}


def test_api_users_absent_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DUTCHBAY_API_USERS", raising=False)
    assert auth._api_users() == {}


@pytest.mark.parametrize(
    ("reader", "env"),
    [
        (auth._jwt_issuer, "DUTCHBAY_JWT_ISSUER"),
        (auth._jwt_audience, "DUTCHBAY_JWT_AUDIENCE"),
    ],
)
def test_jwt_iss_aud_readers(
    monkeypatch: pytest.MonkeyPatch, reader: Any, env: str
) -> None:
    monkeypatch.delenv(env, raising=False)
    assert reader() is None  # unset -> opt-out
    monkeypatch.setenv(env, "   ")
    assert reader() is None  # blank/whitespace treated as unset (never iss="")
    monkeypatch.setenv(env, " dutchbay ")
    assert reader() == "dutchbay"  # trimmed


# --------------------------------------------------------------------------- #
# authenticate_user / login_for_access_token
# --------------------------------------------------------------------------- #
def _set_user(monkeypatch: pytest.MonkeyPatch, username: str, password: str) -> None:
    monkeypatch.setenv("DUTCHBAY_API_USERS", f"{username}:{hash_password(password)}")


def test_authenticate_user_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_user(monkeypatch, "alice", "pw")
    assert authenticate_user("alice", "pw") == "alice"


def test_authenticate_user_wrong_password(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_user(monkeypatch, "alice", "pw")
    assert authenticate_user("alice", "nope") is None


def test_authenticate_user_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_user(monkeypatch, "alice", "pw")
    assert authenticate_user("mallory", "pw") is None


def test_authenticate_user_unknown_still_runs_pbkdf2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Round-2 audit: an unknown username must still pay the PBKDF2 cost (against the fixed
    dummy hash) so it is indistinguishable by response time from a wrong password for a real
    user. Without this, the unknown-user path short-circuits and skips the ~600k-iteration
    PBKDF2, leaking username existence via timing (CWE-208 user-enumeration oracle)."""
    _set_user(monkeypatch, "alice", "pw")
    real_verify = auth.verify_password
    calls: list[str] = []

    def spy(password: str, encoded: str) -> bool:
        calls.append(encoded)
        return real_verify(password, encoded)

    monkeypatch.setattr(auth, "verify_password", spy)
    assert authenticate_user("mallory", "pw") is None
    # verify_password ran exactly once on the unknown-user path, against the dummy hash
    # (not any real user's stored hash) -- so the PBKDF2 cost is paid on both paths.
    assert calls == [auth._DUMMY_PASSWORD_HASH]


def test_login_for_access_token_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_user(monkeypatch, "alice", "pw")
    monkeypatch.setenv("DUTCHBAY_JWT_SECRET", _SECRET)
    token = login_for_access_token("alice", "pw")
    assert decode_token(token, secret=_SECRET) == "alice"


def test_login_for_access_token_bad_creds_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_user(monkeypatch, "alice", "pw")
    monkeypatch.setenv("DUTCHBAY_JWT_SECRET", _SECRET)
    with pytest.raises(HTTPException) as exc:
        login_for_access_token("alice", "wrong")
    assert exc.value.status_code == 401


def test_login_for_access_token_no_secret_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_user(monkeypatch, "alice", "pw")
    monkeypatch.delenv("DUTCHBAY_JWT_SECRET", raising=False)
    with pytest.raises(HTTPException) as exc:
        login_for_access_token("alice", "pw")
    assert exc.value.status_code == 500


# --------------------------------------------------------------------------- #
# get_current_subject dependency
# --------------------------------------------------------------------------- #
def test_get_current_subject_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DUTCHBAY_JWT_SECRET", _SECRET)
    token = create_access_token("alice", secret=_SECRET)
    assert get_current_subject(token) == "alice"


def test_get_current_subject_missing_token_401() -> None:
    with pytest.raises(HTTPException) as exc:
        get_current_subject(None)
    assert exc.value.status_code == 401
    assert exc.value.headers == {"WWW-Authenticate": "Bearer"}


def test_get_current_subject_bad_token_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DUTCHBAY_JWT_SECRET", _SECRET)
    with pytest.raises(HTTPException) as exc:
        get_current_subject("garbage.token.here")
    assert exc.value.status_code == 401


def test_get_current_subject_no_secret_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DUTCHBAY_JWT_SECRET", raising=False)
    token = create_access_token("alice", secret=_SECRET)
    with pytest.raises(HTTPException) as exc:
        get_current_subject(token)
    assert exc.value.status_code == 500


# --------------------------------------------------------------------------- #
# HTTP end-to-end (gated on httpx)
# --------------------------------------------------------------------------- #
def _valid_case_body() -> dict[str, Any]:
    # Matches tests/app/test_api.py::_valid_kwargs — the 159.6 MW x 0.332 CF figures
    # reconcile with the frozen lendercase AEP so the service-seam guard passes.
    return {
        "site_name": "DutchBay",
        "capacity_mw": 159.6,
        "capacity_factor": 0.332,
        "project_life_years": 20,
        "ppa_price_lkr_per_kwh": 20.30,
        "ppa_term_years": 20,
        "capex_total_usd": 159_600_000.0,
        "opex_annual_usd": 5_000_000.0,
        "fx_start_lkr_per_usd": 333.79,
    }


def test_http_auth_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.api.main import app

    monkeypatch.setenv("DUTCHBAY_JWT_SECRET", _SECRET)
    monkeypatch.setenv("DUTCHBAY_API_USERS", f"alice:{hash_password('pw')}")
    client = TestClient(app)

    # Unauthenticated -> 401 with a Bearer challenge.
    unauth = client.post("/cases", json=_valid_case_body())
    assert unauth.status_code == 401
    assert unauth.headers["www-authenticate"] == "Bearer"

    # Bad credentials -> 401.
    assert (
        client.post("/token", json={"username": "alice", "password": "x"}).status_code
        == 401
    )

    # Good credentials -> a bearer token.
    tok = client.post("/token", json={"username": "alice", "password": "pw"})
    assert tok.status_code == 200
    token = tok.json()["access_token"]

    # Authenticated -> the case runs.
    ok = client.post(
        "/cases",
        json=_valid_case_body(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ok.status_code == 200
    assert "project_irr" in ok.json()["kpis"]


def test_login_and_get_current_subject_enforce_iss_aud_via_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """login_for_access_token stamps the configured iss/aud, and get_current_subject
    (which reads the same env) accepts it — the production wiring, end-to-end."""
    _set_user(monkeypatch, "alice", "pw")
    monkeypatch.setenv("DUTCHBAY_JWT_SECRET", _SECRET)
    monkeypatch.setenv("DUTCHBAY_JWT_ISSUER", "dutchbay")
    monkeypatch.setenv("DUTCHBAY_JWT_AUDIENCE", "wizard")

    token = login_for_access_token("alice", "pw")
    # The dependency, reading the same configured iss/aud, accepts the stamped token.
    assert get_current_subject(token) == "alice"

    # A token minted for a DIFFERENT audience is rejected once an audience is required,
    # even though the signature and expiry are valid (cross-audience replay defence).
    foreign = create_access_token(
        "alice", secret=_SECRET, issuer="dutchbay", audience="some-other-service"
    )
    with pytest.raises(HTTPException) as exc:
        get_current_subject(foreign)
    assert exc.value.status_code == 401


def test_http_cross_client_job_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    import app.api.jobs_router as jr
    from app.api.main import app
    from app.jobs.store import InMemoryJobStore

    monkeypatch.setenv("DUTCHBAY_JWT_SECRET", _SECRET)
    monkeypatch.setenv(
        "DUTCHBAY_API_USERS",
        f"alice:{hash_password('pw')},bob:{hash_password('pw')}",
    )
    # Don't actually run ERA5; share one store across both clients.
    monkeypatch.setattr(jr, "run_wind_job", lambda *a, **k: None)
    shared = InMemoryJobStore()
    app.dependency_overrides[jr.get_store] = lambda: shared
    try:
        client = TestClient(app)

        def token_for(user: str) -> str:
            resp = client.post("/token", json={"username": user, "password": "pw"})
            return str(resp.json()["access_token"])

        alice = {"Authorization": f"Bearer {token_for('alice')}"}
        bob = {"Authorization": f"Bearer {token_for('bob')}"}

        body = {
            "inputs": _valid_case_body(),
            "site_lat": 8.33,
            "site_lon": 79.76,
            "turbine_model": "IEA-10MW",
            "num_turbines": 15,
            "hub_height_m": 119.0,
        }
        accepted = client.post("/jobs", json=body, headers=alice)
        assert accepted.status_code == 202
        job_id = accepted.json()["job_id"]

        # Owner can read; the record is bound to alice.
        mine = client.get(f"/jobs/{job_id}", headers=alice)
        assert mine.status_code == 200
        assert mine.json()["owner"] == "alice"

        # A different client gets a non-leaking 404 on both the record and events.
        assert client.get(f"/jobs/{job_id}", headers=bob).status_code == 404
        assert client.get(f"/jobs/{job_id}/events", headers=bob).status_code == 404

        # And an unauthenticated request is rejected outright.
        assert client.get(f"/jobs/{job_id}").status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_http_cross_client_report_result_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A succeeded job carries its rendered report DATA in ``JobRecord.result`` — the only
    per-user report-read surface (the sync ``/cases/report.*`` routes persist nothing). Prove
    that the stored result payload is owner-scoped: the owner reads its own report data, and a
    different client gets a non-leaking 404 (never the other user's result) — the same
    subject-scoping the jobs record uses, applied to the report payload itself."""
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    import app.api.jobs_router as jr
    from app.api.main import app
    from app.jobs.models import JobProgress, JobRecord, JobState, utc_now_iso
    from app.jobs.store import InMemoryJobStore

    monkeypatch.setenv("DUTCHBAY_JWT_SECRET", _SECRET)
    monkeypatch.setenv(
        "DUTCHBAY_API_USERS",
        f"alice:{hash_password('pw')},bob:{hash_password('pw')}",
    )
    shared = InMemoryJobStore()
    app.dependency_overrides[jr.get_store] = lambda: shared
    try:
        client = TestClient(app)

        def token_for(user: str) -> str:
            resp = client.post("/token", json={"username": user, "password": "pw"})
            return str(resp.json()["access_token"])

        alice = {"Authorization": f"Bearer {token_for('alice')}"}
        bob = {"Authorization": f"Bearer {token_for('bob')}"}

        # Seed a SUCCEEDED job owned by alice, carrying a report/result payload — the state
        # a completed run leaves behind (bypassing the minutes-long ERA5 compute).
        now = utc_now_iso()
        secret_result = {
            "kpis": {"project_irr": 0.0203},
            "secret_client_marker": "ALICE",
        }
        shared.create(
            JobRecord(
                job_id="job-A",
                owner="alice",
                state=JobState.SUCCEEDED,
                progress=JobProgress(step=3, total_steps=3, message="Complete"),
                result=secret_result,
                created_at=now,
                updated_at=now,
            )
        )

        # Owner reads its own report result.
        mine = client.get("/jobs/job-A", headers=alice)
        assert mine.status_code == 200
        assert mine.json()["result"] == secret_result

        # A different authenticated client cannot read alice's result — non-leaking 404,
        # and crucially the response body never contains the other user's payload.
        theirs = client.get("/jobs/job-A", headers=bob)
        assert theirs.status_code == 404
        assert "secret_client_marker" not in theirs.text
        assert "ALICE" not in theirs.text
    finally:
        app.dependency_overrides.clear()
