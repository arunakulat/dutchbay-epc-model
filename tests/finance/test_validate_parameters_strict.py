"""Guard tests for ``validate_parameters(..., strict=...)`` — REINDEER-3 salvage.

Tracking: issue #133. These lock in two properties of the lenient-validation
change extracted from PR #61:

1. **Backward compatibility** — the production default (``strict=True``, and the
   no-arg call) still raises ``ValueError`` on an incomplete config, exactly as
   before.
2. **Lenient mode** — ``strict=False`` collects the same issues as warnings and
   returns ``[]`` without raising, so test/dev runs with partial configs proceed.
"""

import pytest

from finance.cashflow_v14_params import validate_parameters


def test_strict_true_raises_on_incomplete_config():
    """Explicit strict mode still raises on missing required fields."""
    with pytest.raises(ValueError):
        validate_parameters({}, strict=True)


def test_default_call_is_strict():
    """Calling without the flag preserves the historical strict behaviour."""
    with pytest.raises(ValueError):
        validate_parameters({})


def test_strict_false_does_not_raise():
    """Lenient mode returns an empty list instead of raising."""
    assert validate_parameters({}, strict=False) == []
