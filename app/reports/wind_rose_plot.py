"""Polar wind-rose renderer for the lender report layer (issue #853.2) — display only.

Renders the :func:`analytics.wind.wind_rose.build_wind_rose` output (the merged
calm-exclusion + energy-frequency + sectorwise-Weibull rose from #742/#826) as a polar
bar chart (matplotlib ``projection='polar'``) and returns it as a self-contained base64
``data:image/png`` URI, so the report embeds the rose inline without leaking a server
filesystem path (MRM, matching the NPV-distribution embed in :func:`app.reports.report_model`).

CASPER call-time guard: matplotlib is an OPTIONAL plotting dependency. It is imported
inside :func:`render_wind_rose_polar_data_uri` (never at module import), so a deployment
without matplotlib degrades gracefully — the function returns ``None`` and the report
renders the existing frequency TABLE alone rather than crashing. The plot NEVER touches
the AEP / wake path: it is a pure re-projection of a rose block already surfaced as
provenance (the KPI-moving live-PyWake activation is the separate, oracle-gated #853.3).

The rose is drawn in the meteorological convention the builder uses: 0 deg = North at
the top, bearings increasing CLOCKWISE (``set_theta_zero_location('N')`` +
``set_theta_direction(-1)``), so a bar's angular position matches its ``sector_deg``
compass bearing. When the rose carries the #826 ``energy_frequency`` enrichment, both the
sample-frequency rose and the energy rose are drawn as overlaid sector bars; otherwise the
frequency rose alone is drawn (byte-identical intent to the direction-only rose).

GWTF: config-free pure renderer, fully typed, fail-soft (returns ``None``, never raises)
on a bad/empty rose or an absent plotting lib; no ``argparse``/``input()``; no finance
imports.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Sequence

logger = logging.getLogger(__name__)

__all__ = ["render_wind_rose_polar_data_uri"]


def _to_float_list(values: Any) -> Optional[list[float]]:
    """Coerce a rose vector into a plain ``list[float]``; ``None`` if it is not a sequence."""
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return None
    try:
        return [float(v) for v in values]
    except (TypeError, ValueError):
        return None


def render_wind_rose_polar_data_uri(
    rose: Mapping[str, Any],
    *,
    dpi: int = 150,
) -> Optional[str]:
    """Render a wind-rose block as a polar PNG, returned as a base64 ``data:image/png`` URI.

    Args:
        rose: A :func:`analytics.wind.wind_rose.build_wind_rose` output block (or the
            report-normalised equivalent) — must carry co-indexed ``sector_deg`` and
            ``frequency`` lists. When it also carries the #826 ``energy_frequency``
            enrichment, the energy rose is overlaid on the sample-frequency rose.
        dpi: Raster resolution of the embedded PNG.

    Returns:
        A ``data:image/png;base64,...`` URI string, or ``None`` when the plot cannot be
        produced — matplotlib is absent (CASPER graceful degradation), the rose is
        missing/empty/malformed (``sector_deg`` and ``frequency`` must be non-empty,
        same length), or rendering raises. The caller then renders the frequency table
        alone rather than a broken image.
    """
    sector_deg = _to_float_list(rose.get("sector_deg"))
    frequency = _to_float_list(rose.get("frequency"))
    if not sector_deg or not frequency or len(sector_deg) != len(frequency):
        logger.debug("wind-rose polar plot skipped: sector_deg/frequency invalid")
        return None

    # Optional #826 energy rose (overlaid when present, same-length as frequency).
    energy = _to_float_list(rose.get("energy_frequency"))
    if energy is not None and len(energy) != len(frequency):
        energy = None

    # CASPER call-time guard: matplotlib is optional; import here, degrade to None if absent.
    try:
        import matplotlib

        matplotlib.use("Agg", force=False)  # headless backend for a server/CI report
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover - only when matplotlib is not installed
        logger.warning("wind-rose polar plot skipped: matplotlib unavailable: %s", exc)
        return None

    import base64
    import io
    import math

    try:
        n = len(sector_deg)
        width = 2.0 * math.pi / n  # equal-width sector arc (radians)
        theta = [math.radians(d) for d in sector_deg]

        fig = plt.figure(figsize=(5.0, 5.0))
        ax = fig.add_subplot(111, projection="polar")
        # Meteorological orientation: North at top, clockwise (matches sector_deg bearings).
        # These are PolarAxes methods; mypy sees the base Axes type from add_subplot, so the
        # projection-specific calls are annotated (they exist at runtime under projection="polar").
        ax.set_theta_zero_location("N")  # type: ignore[attr-defined]
        ax.set_theta_direction(-1)  # type: ignore[attr-defined]

        ax.bar(
            theta,
            frequency,
            width=width,
            bottom=0.0,
            align="center",
            color="#4C72B0",
            edgecolor="white",
            alpha=0.85,
            label="Sample frequency",
        )
        if energy is not None:
            # Overlay the energy rose as an outlined bar so both are legible without hiding
            # either (energy share ∝ fᵢ·⟨vᵢ³⟩ from the #826 enrichment).
            ax.bar(
                theta,
                energy,
                width=width,
                bottom=0.0,
                align="center",
                facecolor="none",
                edgecolor="#C44E52",
                linewidth=1.4,
                label="Energy frequency",
            )

        ax.set_title("Directional wind rose", va="bottom", fontsize=11)
        ax.legend(loc="upper right", bbox_to_anchor=(1.18, 1.10), fontsize=8)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi)
        plt.close(fig)
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except (
        Exception
    ) as exc:  # pragma: no cover - belt-and-braces: never crash the report
        logger.warning("wind-rose polar plot failed to render: %s", exc)
        try:
            plt.close("all")
        except Exception:
            pass
        return None
