"""Unit tests for UnmetNeedScorer."""
import pytest

from src.unmet_need_scorer import (
    DEFAULT_WEIGHTS,
    DiseaseAreaProfile,
    UnmetNeedScore,
    UnmetNeedScorer,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _profile(
    name: str,
    daly: float = 300.0,
    resp: float = 0.5,
    ae: float = 0.2,
    cov: float = 0.7,
    hrqol: float = 0.3,
    prev: float = None,
    ta: str = "Oncology",
) -> DiseaseAreaProfile:
    return DiseaseAreaProfile(
        disease_area=name,
        daly_per_100k=daly,
        five_year_response_rate=resp,
        grade3_ae_rate=ae,
        reimbursed_coverage=cov,
        hrqol_decrement=hrqol,
        prevalence_per_100k=prev,
        therapy_area=ta,
    )


@pytest.fixture
def portfolio_scorer() -> UnmetNeedScorer:
    s = UnmetNeedScorer()
    s.add(_profile("NSCLC", daly=310.0, resp=0.22, ae=0.38, cov=0.55, hrqol=0.42))
    s.add(_profile("HER2+ Breast Cancer", daly=260.0, resp=0.55, ae=0.24, cov=0.72, hrqol=0.30))
    s.add(_profile("T2DM", daly=620.0, resp=0.68, ae=0.08, cov=0.92, hrqol=0.17, ta="Cardiometabolic"))
    s.add(_profile("HFrEF", daly=480.0, resp=0.40, ae=0.18, cov=0.80, hrqol=0.38, ta="Cardiometabolic"))
    s.add(_profile("RA", daly=220.0, resp=0.60, ae=0.15, cov=0.78, hrqol=0.35, ta="Immunology"))
    return s


# ---------------------------------------------------------------------------
# DiseaseAreaProfile validation
# ---------------------------------------------------------------------------


def test_profile_valid_construction():
    p = _profile("NSCLC")
    assert p.disease_area == "NSCLC"
    assert p.therapy_area == "Oncology"


def test_profile_empty_name_rejected():
    with pytest.raises(ValueError, match="disease_area"):
        _profile("")


def test_profile_whitespace_name_rejected():
    with pytest.raises(ValueError, match="disease_area"):
        _profile("   ")


def test_profile_negative_daly_rejected():
    with pytest.raises(ValueError, match="daly_per_100k"):
        _profile("X", daly=-1.0)


def test_profile_response_rate_out_of_range():
    with pytest.raises(ValueError, match="five_year_response_rate"):
        _profile("X", resp=1.5)


def test_profile_ae_rate_out_of_range():
    with pytest.raises(ValueError, match="grade3_ae_rate"):
        _profile("X", ae=-0.1)


def test_profile_coverage_out_of_range():
    with pytest.raises(ValueError, match="reimbursed_coverage"):
        _profile("X", cov=1.01)


def test_profile_hrqol_out_of_range():
    with pytest.raises(ValueError, match="hrqol_decrement"):
        _profile("X", hrqol=2.0)


def test_profile_negative_prevalence_rejected():
    with pytest.raises(ValueError, match="prevalence_per_100k"):
        _profile("X", prev=-5.0)


def test_profile_is_frozen():
    p = _profile("NSCLC")
    with pytest.raises(Exception):
        p.disease_area = "Other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# UnmetNeedScorer construction & data management
# ---------------------------------------------------------------------------


def test_default_weights_sum_to_one():
    assert pytest.approx(sum(DEFAULT_WEIGHTS.values()), abs=1e-9) == 1.0


def test_scorer_default_weights_normalised():
    s = UnmetNeedScorer()
    assert pytest.approx(sum(s.weights.values()), abs=1e-9) == 1.0


def test_scorer_custom_weights_renormalised():
    s = UnmetNeedScorer(
        weights={
            "burden": 2.0,
            "effectiveness_gap": 2.0,
            "safety": 1.0,
            "access": 1.0,
            "hrqol": 1.0,
        }
    )
    assert pytest.approx(sum(s.weights.values()), abs=1e-9) == 1.0
    assert s.weights["burden"] == pytest.approx(2.0 / 7.0)


def test_scorer_missing_weight_key_rejected():
    with pytest.raises(ValueError, match="missing"):
        UnmetNeedScorer(weights={"burden": 1.0})


def test_scorer_unknown_weight_key_rejected():
    bad = dict(DEFAULT_WEIGHTS)
    bad["fun"] = 0.1
    with pytest.raises(ValueError, match="Unknown"):
        UnmetNeedScorer(weights=bad)


def test_scorer_negative_weight_rejected():
    bad = dict(DEFAULT_WEIGHTS)
    bad["burden"] = -0.1
    with pytest.raises(ValueError, match="non-negative"):
        UnmetNeedScorer(weights=bad)


def test_scorer_all_zero_weights_rejected():
    bad = {k: 0.0 for k in DEFAULT_WEIGHTS}
    with pytest.raises(ValueError, match="> 0"):
        UnmetNeedScorer(weights=bad)


def test_add_duplicate_disease_area_rejected(portfolio_scorer):
    with pytest.raises(ValueError, match="already"):
        portfolio_scorer.add(_profile("NSCLC"))


def test_initial_profiles_duplicate_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        UnmetNeedScorer(profiles=[_profile("A"), _profile("A")])


def test_add_bulk_count():
    s = UnmetNeedScorer()
    n = s.add_bulk([_profile("A"), _profile("B"), _profile("C")])
    assert n == 3
    assert len(s) == 3


def test_profiles_snapshot_is_immutable(portfolio_scorer):
    snapshot = portfolio_scorer.profiles
    assert isinstance(snapshot, tuple)
    # Mutating the tuple should be impossible
    with pytest.raises(AttributeError):
        snapshot.append(_profile("Z"))  # type: ignore[attr-defined]


def test_with_weights_returns_new_instance(portfolio_scorer):
    other = portfolio_scorer.with_weights(
        {
            "burden": 1.0,
            "effectiveness_gap": 0.0,
            "safety": 0.0,
            "access": 0.0,
            "hrqol": 0.0,
        }
    )
    assert other is not portfolio_scorer
    assert other.weights["burden"] == 1.0
    # original unchanged
    assert portfolio_scorer.weights == DEFAULT_WEIGHTS


# ---------------------------------------------------------------------------
# Scoring behaviour
# ---------------------------------------------------------------------------


def test_score_empty_portfolio_raises():
    with pytest.raises(RuntimeError, match="empty"):
        UnmetNeedScorer().score_portfolio()


def test_score_portfolio_returns_all(portfolio_scorer):
    scores = portfolio_scorer.score_portfolio()
    assert len(scores) == 5
    assert {s.disease_area for s in scores} == {
        "NSCLC",
        "HER2+ Breast Cancer",
        "T2DM",
        "HFrEF",
        "RA",
    }


def test_scores_sorted_desc(portfolio_scorer):
    scores = portfolio_scorer.score_portfolio()
    composites = [s.composite_score for s in scores]
    assert composites == sorted(composites, reverse=True)


def test_scores_in_valid_range(portfolio_scorer):
    for s in portfolio_scorer.score_portfolio():
        assert 0.0 <= s.composite_score <= 100.0
        for sub in s.sub_scores.values():
            assert 0.0 <= sub <= 100.0


def test_highest_burden_gets_top_burden_score(portfolio_scorer):
    # T2DM has highest daly (620) in the portfolio
    t2dm = portfolio_scorer.score_for("T2DM")
    assert t2dm.burden_score == 100.0


def test_lowest_response_gets_top_effectiveness_gap(portfolio_scorer):
    # NSCLC has lowest 5-year response rate (0.22)
    nsclc = portfolio_scorer.score_for("NSCLC")
    assert nsclc.effectiveness_gap_score == 100.0


def test_highest_coverage_gets_lowest_access_score(portfolio_scorer):
    # T2DM has highest reimbursed coverage (0.92) → inverted => score 0
    t2dm = portfolio_scorer.score_for("T2DM")
    assert t2dm.access_score == 0.0


def test_identical_inputs_give_neutral_score():
    s = UnmetNeedScorer()
    s.add(_profile("A", daly=100, resp=0.5, ae=0.2, cov=0.7, hrqol=0.3))
    s.add(_profile("B", daly=100, resp=0.5, ae=0.2, cov=0.7, hrqol=0.3))
    for score in s.score_portfolio():
        assert score.composite_score == 50.0
        assert all(v == 50.0 for v in score.sub_scores.values())


def test_single_profile_scores_to_50():
    s = UnmetNeedScorer()
    s.add(_profile("solo"))
    [score] = s.score_portfolio()
    assert score.composite_score == 50.0


def test_score_for_unknown_raises(portfolio_scorer):
    with pytest.raises(KeyError):
        portfolio_scorer.score_for("Acromegaly")


def test_top_n_returns_requested(portfolio_scorer):
    top2 = portfolio_scorer.top_n(2)
    assert len(top2) == 2
    scores = portfolio_scorer.score_portfolio()
    assert top2 == scores[:2]


def test_top_n_invalid_raises(portfolio_scorer):
    with pytest.raises(ValueError):
        portfolio_scorer.top_n(0)


def test_tier_distribution_sums_to_portfolio(portfolio_scorer):
    dist = portfolio_scorer.tier_distribution()
    assert sum(dist.values()) == len(portfolio_scorer)
    assert set(dist.keys()) == {"CRITICAL", "HIGH", "MODERATE", "LOW"}


def test_tier_classification_critical():
    # Build a lopsided portfolio where one DA dominates all 5 dimensions
    s = UnmetNeedScorer()
    s.add(_profile("Severe", daly=1000, resp=0.05, ae=0.9, cov=0.1, hrqol=0.95))
    s.add(_profile("Mild", daly=10, resp=0.95, ae=0.02, cov=0.99, hrqol=0.05))
    severe = s.score_for("Severe")
    mild = s.score_for("Mild")
    assert severe.tier == "CRITICAL"
    assert mild.tier == "LOW"
    assert severe.composite_score == 100.0
    assert mild.composite_score == 0.0


def test_sub_scores_property_keys(portfolio_scorer):
    score = portfolio_scorer.score_for("NSCLC")
    assert set(score.sub_scores.keys()) == {
        "burden",
        "effectiveness_gap",
        "safety",
        "access",
        "hrqol",
    }


def test_sub_score_table_rows_match_portfolio(portfolio_scorer):
    table = portfolio_scorer.sub_score_table()
    assert len(table) == len(portfolio_scorer)
    for row in table:
        assert "disease_area" in row
        assert "composite_score" in row
        assert "tier" in row
        assert "burden" in row


def test_full_report_structure(portfolio_scorer):
    report = portfolio_scorer.full_report()
    assert report["portfolio_size"] == 5
    assert set(report["weights"].keys()) == set(DEFAULT_WEIGHTS.keys())
    assert len(report["top_priorities"]) == 3
    assert "tier_distribution" in report
    assert "sub_scores" in report


def test_custom_weights_change_ranking():
    base = UnmetNeedScorer()
    base.add(_profile("HighBurdenOnly", daly=1000, resp=0.8, ae=0.05, cov=0.95, hrqol=0.1))
    base.add(_profile("HighAccessGap", daly=50, resp=0.2, ae=0.4, cov=0.1, hrqol=0.6))

    burden_heavy = base.with_weights(
        {"burden": 1.0, "effectiveness_gap": 0.0, "safety": 0.0, "access": 0.0, "hrqol": 0.0}
    )
    access_heavy = base.with_weights(
        {"burden": 0.0, "effectiveness_gap": 0.0, "safety": 0.0, "access": 1.0, "hrqol": 0.0}
    )
    assert burden_heavy.score_portfolio()[0].disease_area == "HighBurdenOnly"
    assert access_heavy.score_portfolio()[0].disease_area == "HighAccessGap"


def test_repr_and_len(portfolio_scorer):
    assert len(portfolio_scorer) == 5
    r = repr(portfolio_scorer)
    assert "UnmetNeedScorer" in r and "portfolio_size=5" in r


def test_unmet_need_score_is_frozen(portfolio_scorer):
    score = portfolio_scorer.score_for("NSCLC")
    assert isinstance(score, UnmetNeedScore)
    with pytest.raises(Exception):
        score.composite_score = 0.0  # type: ignore[misc]
