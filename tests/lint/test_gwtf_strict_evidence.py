"""Strict operational evidence parsing controls; no real journal mutation."""

from __future__ import annotations

import json

import pytest

from scripts import gwtf_checkpoint_readiness as ready
from scripts import gwtf_checkpoint_receipt as receipt


@pytest.mark.parametrize(
    "raw",
    [
        '{"schema":2,"schema":3}',
        '{"nested":{"x":1,"x":2}}',
        '{"x":NaN}',
        '{"x":Infinity}',
        '{"x":-Infinity}',
        '{"x":1e999}',
        '{"x":' + "[" * 64 + "0" + "]" * 64 + "}",
        b'{"x":"\xff"}',
        b"\xff\xfe{\x00}\x00",
    ],
)
def test_strict_json_refuses_ambiguous_evidence(raw: str | bytes) -> None:
    with pytest.raises(ValueError):
        ready.strict_json(raw)


def test_strict_json_size_and_quoted_brackets(monkeypatch: pytest.MonkeyPatch) -> None:
    value = {"escaped": '"' + "\\" + "[" * 128 + "}" * 128, "finite": 0.25}
    assert ready.strict_json(json.dumps(value)) == value
    monkeypatch.setattr(ready, "MAX_JSON_BYTES", 16)
    with pytest.raises(ValueError, match="size limit"):
        ready.strict_json('{"x":"' + "a" * 20 + '"}')
    with pytest.raises(ValueError, match="size limit"):
        ready.strict_json(b'{"x":"' + b"a" * 20 + b'"}')


@pytest.mark.parametrize(
    "raw",
    [
        '{"schema":2,"schema":3}\n',
        '{"data":{"x":1,"x":2}}\n',
        '{"data":NaN}\n',
        '{"data":1e999}\n',
        '{"data":' + "[" * 64 + "0" + "]" * 64 + "}\n",
    ],
)
def test_journal_parser_refuses_ambiguous_rows(raw: str) -> None:
    with pytest.raises(ValueError):
        receipt.parse_rows(raw)
