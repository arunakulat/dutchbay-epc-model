"""Bankability evidence-completeness score — analytics/evidence_score.py (issue #616).

Covers the config-sourced weights (incl. the CESSPIT cross-check against the register
taxonomy), the score computation (tier strength, missing-evidence penalty, ungradeable
entries), the band mapping, and the fail-loud config contract. KPI-neutral: a pure
read-only derivation over the evidence-register coverage — no finance metric is recomputed.
"""

from __future__ import annotations

import pytest

from analytics import evidence_score as es
from analytics.evidence_register import load_taxonomy
from analytics.evidence_score import (
    build_evidence_score,
    load_evidence_score_weights,
)


def _register(entries: dict) -> dict:
    return {"evidence_register": {"entries": entries}}


def _all_at_tier(tier: str) -> dict:
    tax = load_taxonomy()
    return _register(
        {
            name: {"source": "s", "as_of": "2026-01-01", "tier": tier}
            for name in tax.assumptions
        }
    )


# ── weights load + CESSPIT cross-check ──────────────────────────────────────────
def test_weights_load_and_match_register_taxonomy() -> None:
    w = load_evidence_score_weights()
    tax = load_taxonomy()
    # every register tier has a weight, and no weight is for a non-tier (single source)
    assert set(w.tier_weights) == set(tax.tiers)
    # strongest tier is 1.0, all weights in [0, 1], monotone with the register order
    assert w.tier_weights[tax.tiers[0]] == 1.0
    strengths = [w.tier_weights[t] for t in tax.tiers]
    assert strengths == sorted(strengths, reverse=True)  # strongest -> weakest
    assert all(0.0 <= s <= 1.0 for s in strengths)
    assert w.missing_weight == 0.0
    assert w.bands[-1].min == 0.0  # a floor band exists


def test_band_for_maps_scores_to_labels() -> None:
    w = load_evidence_score_weights()
    assert w.band_for(100.0) == "bankable"
    assert w.band_for(85.0) == "bankable"
    assert w.band_for(84.99) == "substantially evidenced"
    assert w.band_for(0.0) == "insufficiently evidenced"


# ── score: coverage + tier strength ─────────────────────────────────────────────
def test_full_measured_register_scores_100_bankable() -> None:
    score = build_evidence_score(_all_at_tier("measured"))
    assert score.score == 100.0
    assert score.band == "bankable"
    assert score.n_covered == score.n_total
    assert score.n_missing == 0
    assert score.coverage_fraction == 1.0
    assert score.mean_covered_strength == 1.0


def test_empty_register_scores_zero_insufficient() -> None:
    score = build_evidence_score({})
    assert score.score == 0.0
    assert score.band == "insufficiently evidenced"
    assert score.n_covered == 0
    assert score.n_missing == score.n_total
    assert score.coverage_fraction == 0.0
    assert score.mean_covered_strength == 0.0
    assert set(score.missing) == set(load_taxonomy().assumptions)


def test_tier_strength_differentiates_full_registers() -> None:
    # full coverage at every tier, but stronger tiers score higher (same coverage!)
    measured = build_evidence_score(_all_at_tier("measured")).score
    benchmark = build_evidence_score(_all_at_tier("benchmark")).score
    placeholder = build_evidence_score(_all_at_tier("placeholder")).score
    assert measured > benchmark > placeholder
    # all three have full COVERAGE — the difference is purely tier strength
    for tier in ("measured", "benchmark", "placeholder"):
        s = build_evidence_score(_all_at_tier(tier))
        assert s.n_covered == s.n_total
        assert s.coverage_fraction == 1.0


def test_all_placeholder_score_matches_the_weight() -> None:
    w = load_evidence_score_weights()
    score = build_evidence_score(_all_at_tier("placeholder"))
    # every assumption at the placeholder weight -> score == 100 * weight
    assert score.score == pytest.approx(100.0 * w.tier_weights["placeholder"])
    assert score.mean_covered_strength == pytest.approx(w.tier_weights["placeholder"])


# ── missing-evidence penalty ────────────────────────────────────────────────────
def test_partial_coverage_is_penalized() -> None:
    tax = load_taxonomy()
    w = load_evidence_score_weights()
    # cover exactly half the assumptions at 'measured' (strength 1.0), rest missing
    half = list(tax.assumptions)[: len(tax.assumptions) // 2]
    cfg = _register(
        {name: {"source": "s", "as_of": "2026", "tier": "measured"} for name in half}
    )
    score = build_evidence_score(cfg)
    assert score.n_covered == len(half)
    # score == 100 * (covered * 1.0 + missing * missing_weight) / total
    expected = (
        100.0
        * (len(half) * 1.0 + (tax.assumptions.__len__() - len(half)) * w.missing_weight)
        / len(tax.assumptions)
    )
    assert score.score == pytest.approx(round(expected, 2))
    # coverage drags the score below a fully-measured register even at the top tier
    assert score.score < 100.0
    # mean_covered_strength still reflects only the covered (all measured => 1.0)
    assert score.mean_covered_strength == 1.0


def test_coverage_and_strength_are_separated() -> None:
    # A: full coverage, weak tier. B: half coverage, strongest tier.
    tax = load_taxonomy()
    a = build_evidence_score(_all_at_tier("placeholder"))
    half = list(tax.assumptions)[: len(tax.assumptions) // 2]
    b = build_evidence_score(
        _register(
            {n: {"source": "s", "as_of": "2026", "tier": "measured"} for n in half}
        )
    )
    # A has full coverage but low strength; B has partial coverage but max strength
    assert a.coverage_fraction == 1.0 and a.mean_covered_strength < 0.2
    assert b.coverage_fraction < 1.0 and b.mean_covered_strength == 1.0


# ── ungradeable entries score at the missing floor ──────────────────────────────
def test_entry_without_tier_is_ungradeable() -> None:
    cfg = _register({"tariff": {"source": "s", "as_of": "2026"}})  # no tier
    score = build_evidence_score(cfg)
    tariff = next(a for a in score.assumptions if a.assumption == "tariff")
    assert tariff.covered is False
    assert tariff.strength == load_evidence_score_weights().missing_weight
    assert "tariff" in score.missing


def test_entry_with_unknown_tier_is_ungradeable() -> None:
    cfg = _register({"capex": {"source": "s", "as_of": "2026", "tier": "gut_feel"}})
    score = build_evidence_score(cfg)
    capex = next(a for a in score.assumptions if a.assumption == "capex")
    assert capex.covered is False
    assert capex.tier == ""
    assert "capex" in score.missing


def test_unknown_assumption_does_not_inflate_score() -> None:
    # an entry for a NON-canonical assumption is ignored by the score (the register
    # flags it unknown_assumption); the score only credits canonical assumptions.
    cfg = _register(
        {"made_up_thing": {"source": "s", "as_of": "2026", "tier": "measured"}}
    )
    score = build_evidence_score(cfg)
    assert score.score == 0.0
    assert score.n_covered == 0


# ── faithfulness: un-sourced / below-bar evidence must NOT read as bankable ──────
def test_tier_without_source_or_as_of_earns_no_credit() -> None:
    # The load-bearing faithfulness property (Fable BLOCK #707): every canonical assumption
    # declared {tier: measured} but with NO source/as_of is flagged missing_field by the
    # register, so it must score at the floor — NOT 100/bankable for a zero-provenance base.
    tax = load_taxonomy()
    cfg = _register({name: {"tier": "measured"} for name in tax.assumptions})
    score = build_evidence_score(cfg)
    assert score.score == 0.0
    assert score.band == "insufficiently evidenced"
    assert score.n_covered == 0
    assert all(not a.covered for a in score.assumptions)


def test_empty_string_source_earns_no_credit() -> None:
    # empty-string provenance is falsy -> register flags missing_field -> floored.
    cfg = _register({"tariff": {"source": "", "as_of": "", "tier": "measured"}})
    score = build_evidence_score(cfg)
    tariff = next(a for a in score.assumptions if a.assumption == "tariff")
    assert tariff.covered is False
    assert tariff.strength == load_evidence_score_weights().missing_weight


def test_well_formed_entry_still_earns_full_credit() -> None:
    # the fix must NOT over-floor: a fully-sourced measured entry still earns 1.0.
    cfg = _register(
        {"tariff": {"source": "signed PPA", "as_of": "2026", "tier": "measured"}}
    )
    score = build_evidence_score(cfg)
    tariff = next(a for a in score.assumptions if a.assumption == "tariff")
    assert tariff.covered is True
    assert tariff.strength == 1.0


def test_entry_below_scenario_min_tier_earns_no_credit() -> None:
    # a scenario that sets its own min_tier rejects weaker evidence; the register flags
    # below_min_tier, so the score must not count it as covered (coverage overstatement fix).
    tax = load_taxonomy()
    cfg = {
        "evidence_register": {
            "min_tier": "benchmark",
            "entries": {
                name: {"source": "s", "as_of": "2026", "tier": "placeholder"}
                for name in tax.assumptions
            },
        }
    }
    score = build_evidence_score(cfg)
    assert score.n_covered == 0
    assert score.score == 0.0


def test_min_tier_still_credits_entries_at_or_above_the_bar() -> None:
    # the below_min_tier floor must not punish evidence that MEETS the scenario's bar.
    cfg = {
        "evidence_register": {
            "min_tier": "benchmark",
            "entries": {"tariff": {"source": "s", "as_of": "2026", "tier": "measured"}},
        }
    }
    score = build_evidence_score(cfg)
    tariff = next(a for a in score.assumptions if a.assumption == "tariff")
    assert tariff.covered is True and tariff.strength == 1.0


# ── display/band consistency ────────────────────────────────────────────────────
def test_band_matches_the_displayed_rounded_score() -> None:
    # band is computed from the rounded score, so the label always describes the number
    # the report shows (no 85.0-displayed / "substantially evidenced" mismatch).
    for tier in load_taxonomy().tiers:
        score = build_evidence_score(_all_at_tier(tier))
        assert score.band == load_evidence_score_weights().band_for(score.score)


# ── model contracts ─────────────────────────────────────────────────────────────
def test_per_assumption_covers_every_canonical_assumption_once() -> None:
    score = build_evidence_score(_all_at_tier("contracted"))
    names = [a.assumption for a in score.assumptions]
    assert sorted(names) == sorted(load_taxonomy().assumptions)
    assert len(names) == len(set(names))  # no duplicates


def test_score_does_not_mutate_config() -> None:
    cfg = _all_at_tier("measured")
    before = repr(cfg)
    build_evidence_score(cfg)
    assert repr(cfg) == before  # pure derivation — byte-identical economics


# ── fail-loud config contract (CESSPIT) ─────────────────────────────────────────
def test_load_weights_fails_loud_on_missing_keys(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "evidence_score.yaml"
    bad.write_text("tier_weights: {measured: 1.0}\n")  # no missing_weight / bands
    monkeypatch.setattr(es, "_WEIGHTS_PATH", bad)
    load_evidence_score_weights.cache_clear()
    try:
        with pytest.raises(ValueError, match="missing_weight"):
            load_evidence_score_weights()
    finally:
        load_evidence_score_weights.cache_clear()


def test_load_weights_fails_loud_on_tier_drift(tmp_path, monkeypatch) -> None:
    # weights missing a register tier -> loud drift error (single source)
    bad = tmp_path / "evidence_score.yaml"
    bad.write_text(
        "tier_weights: {measured: 1.0}\n"
        "missing_weight: 0.0\n"
        "bands: [{min: 0, label: x}]\n"
    )
    monkeypatch.setattr(es, "_WEIGHTS_PATH", bad)
    load_evidence_score_weights.cache_clear()
    try:
        with pytest.raises(ValueError, match="must exactly match"):
            load_evidence_score_weights()
    finally:
        load_evidence_score_weights.cache_clear()


def test_load_weights_fails_loud_on_out_of_range_weight(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "evidence_score.yaml"
    bad.write_text(
        "tier_weights: {measured: 1.5}\n"
        "missing_weight: 0.0\n"
        "bands: [{min: 0, label: x}]\n"
    )
    monkeypatch.setattr(es, "_WEIGHTS_PATH", bad)
    load_evidence_score_weights.cache_clear()
    try:
        with pytest.raises(ValueError, match=r"must be a finite number in \[0, 1\]"):
            load_evidence_score_weights()
    finally:
        load_evidence_score_weights.cache_clear()


def _full_weights_yaml(bands: str) -> str:
    tier_lines = "\n".join(f"  {t}: 0.5" for t in load_taxonomy().tiers)
    return f"tier_weights:\n{tier_lines}\nmissing_weight: 0.0\nbands: {bands}\n"


def test_load_weights_fails_loud_without_zero_floor_band(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "evidence_score.yaml"
    bad.write_text(_full_weights_yaml("[{min: 50, label: x}]"))  # no min=0 floor
    monkeypatch.setattr(es, "_WEIGHTS_PATH", bad)
    load_evidence_score_weights.cache_clear()
    try:
        with pytest.raises(ValueError, match="min=0 floor"):
            load_evidence_score_weights()
    finally:
        load_evidence_score_weights.cache_clear()


def test_load_weights_fails_loud_on_band_min_out_of_range(
    tmp_path, monkeypatch
) -> None:
    bad = tmp_path / "evidence_score.yaml"
    bad.write_text(_full_weights_yaml("[{min: 0, label: a}, {min: 150, label: b}]"))
    monkeypatch.setattr(es, "_WEIGHTS_PATH", bad)
    load_evidence_score_weights.cache_clear()
    try:
        with pytest.raises(
            ValueError, match=r"must be a finite number\s+in \[0, 100\]"
        ):
            load_evidence_score_weights()
    finally:
        load_evidence_score_weights.cache_clear()


def test_load_weights_fails_loud_on_duplicate_band_min(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "evidence_score.yaml"
    bad.write_text(
        _full_weights_yaml(
            "[{min: 0, label: a}, {min: 50, label: b}, {min: 50, label: c}]"
        )
    )
    monkeypatch.setattr(es, "_WEIGHTS_PATH", bad)
    load_evidence_score_weights.cache_clear()
    try:
        with pytest.raises(ValueError, match="duplicate band min"):
            load_evidence_score_weights()
    finally:
        load_evidence_score_weights.cache_clear()
