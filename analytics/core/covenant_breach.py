"""Noise-tolerant covenant-breach probability primitives (single source of truth).

A dual-DSCR sculpt sets each year's debt service so the binding DSCR equals the
covenant floor, which pins every trial's *minimum* DSCR at that floor to within
floating-point representation noise (values like ``1.2999999999999996``). A
strict ``arr < floor`` comparison miscounts that sub-ULP noise as covenant
breaches and fabricates an 85-93% breach probability on a case whose TRUE breach
probability is ``0.0`` (#657, Fable blocker; the same latent bug lived in four
sibling paths, #725).

Every covenant-breach probability in the codebase must route through
:func:`prob_breach` so a ``covenant == sculpt-floor`` case is never reported as a
spurious lender risk, and lender-facing surfaces should disclose the degeneracy
via :func:`is_floor_pinned` (a structural ``0.0`` carries no distributional
signal). Kept as a pure-``numpy`` leaf (no intra-package imports) so it can be
imported from anywhere in ``analytics`` without risking an import cycle.
"""

from __future__ import annotations

import numpy as np

# 1e-9 relative: many orders of magnitude above the ~1e-16 pin scatter yet far
# below any economically-meaningful DSCR margin (0.001 of a 1.30 covenant is
# 0.0013), so a value counts as a breach only if it is below the floor by more
# than representation noise. Mirrors ``numpy.isclose``'s default ``rtol`` scale.
PROB_BREACH_RTOL: float = 1e-9


def prob_breach(arr: np.ndarray, floor: float) -> float:
    """Fraction of trials that breach ``floor``, robust to floating-point pin noise.

    A trial counts as a breach only when it sits below ``floor`` by *more than*
    representation noise: ``arr < floor`` **and not** ``np.isclose(arr, floor)``
    at :data:`PROB_BREACH_RTOL`. Without the tolerance a sculpted-amortization
    DSCR array pinned at the covenant floor (all trials within ~1e-16 of the
    floor, some just below it) would report a spurious 85-93% breach probability
    where the true value is ``0.0``. The tolerance is representation-noise-scale,
    far tighter than any real DSCR margin, so genuine breaches below the floor
    are still counted.

    Args:
        arr: Per-trial metric values (e.g. per-trial minimum DSCR).
        floor: Covenant floor to test against.

    Returns:
        The breach fraction in ``[0, 1]``, or ``nan`` for an empty array.
    """
    arr = np.asarray(arr, dtype=float)
    if arr.size == 0:
        return float("nan")
    floor_f = float(floor)
    below = arr < floor_f
    at_floor = np.isclose(arr, floor_f, rtol=PROB_BREACH_RTOL, atol=0.0)
    return float(np.mean(below & ~at_floor))


def is_floor_pinned(arr: np.ndarray, floor: float) -> bool:
    """Whether every trial sits at ``floor`` within noise (sculpt degeneracy).

    A dual-DSCR sculpt makes the per-trial minimum DSCR invariant at the covenant
    floor by construction. When that holds the min-DSCR breach probability is a
    structural ``0.0`` and carries no distributional signal, so a lender-facing
    caller should disclose the degeneracy rather than present an uninformative
    statistic as a risk read. Uses the same :data:`PROB_BREACH_RTOL`
    representation-noise scale as :func:`prob_breach`.

    Args:
        arr: Per-trial metric values (e.g. per-trial minimum DSCR).
        floor: Covenant floor to test against.

    Returns:
        ``True`` if every value is within noise of ``floor``; ``False`` for an
        empty array or any value more than noise away from the floor.
    """
    arr = np.asarray(arr, dtype=float)
    if arr.size == 0:
        return False
    return bool(np.all(np.isclose(arr, float(floor), rtol=PROB_BREACH_RTOL, atol=0.0)))
