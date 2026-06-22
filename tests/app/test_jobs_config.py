"""Tests for the env-driven job config helpers (CCCDIR knobs)."""

from __future__ import annotations

import pytest

from app.jobs import config as cfg


def test_defaults_are_sane() -> None:
    assert cfg.MAX_RETAINED_JOBS >= 1
    assert cfg.JOB_TTL_SECONDS >= 0
    assert cfg.SSE_MAX_POLLS >= 1
    assert cfg.SSE_POLL_INTERVAL_SECONDS > 0


def test_int_env_reads_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X_INT", "42")
    assert cfg._int_env("X_INT", 7) == 42


def test_int_env_falls_back_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("X_INT", raising=False)
    assert cfg._int_env("X_INT", 7) == 7


def test_int_env_falls_back_on_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X_INT", "not-a-number")
    assert cfg._int_env("X_INT", 7) == 7
    monkeypatch.setenv("X_INT", "")
    assert cfg._int_env("X_INT", 7) == 7


def test_float_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X_FLOAT", "0.25")
    assert cfg._float_env("X_FLOAT", 1.0) == 0.25
    monkeypatch.setenv("X_FLOAT", "bad")
    assert cfg._float_env("X_FLOAT", 1.0) == 1.0
    monkeypatch.delenv("X_FLOAT", raising=False)
    assert cfg._float_env("X_FLOAT", 1.0) == 1.0
