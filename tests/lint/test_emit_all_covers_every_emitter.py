"""emit_all must cover every emit_* switch the pipeline CLI reads (#1756).

A new emitter that reads its own switch with ``cfg.get("emit_...")`` would sit outside
``emit_all``. These checks tie the switch list in ``analytics/emit_selection.py`` to the CLI,
the conf and the applicability table.
"""

from __future__ import annotations

import re
from pathlib import Path

from omegaconf import OmegaConf

from analytics.emit_selection import APPLICABILITY, EMIT_FLAGS

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "run_full_pipeline_v14.py"
CONF = REPO_ROOT / "conf" / "run_full_pipeline_v14.yaml"


def test_cli_reads_no_emit_switch_directly() -> None:
    source = CLI.read_text(encoding="utf-8")
    direct = re.findall(r"""cfg\.get\(\s*["'](emit_\w+)["']""", source)
    assert direct == [], f"read these through analytics.emit_selection: {direct}"


def test_every_planned_switch_is_used_by_the_cli() -> None:
    source = CLI.read_text(encoding="utf-8")
    used = set(re.findall(r"""emit_plan\[\s*["'](emit_\w+)["']\s*\]""", source))
    assert used == set(EMIT_FLAGS)


def test_conf_declares_exactly_the_planned_switches() -> None:
    conf = OmegaConf.load(CONF)
    declared = {str(k) for k in conf if str(k).startswith("emit_")}
    assert declared == set(EMIT_FLAGS) | {"emit_all"}
    # On by default: owner ruling 2026-11-16.
    assert conf.emit_all is True
    for flag in EMIT_FLAGS:
        assert conf.get(flag) is None, f"{flag} must default to null (follow emit_all)"


def test_every_switch_has_an_applicability_check() -> None:
    assert set(APPLICABILITY) == set(EMIT_FLAGS)
    assert len(EMIT_FLAGS) == len(set(EMIT_FLAGS))
