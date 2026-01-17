"""Unit tests for MarketPenetrationEstimator."""

import pytest
from src.market_penetration_estimator import (
    MarketPenetrationEstimator,
    DiseaseAreaData,
    PenetrationEstimate,
)


@pytest.fixture
def estimator():
    return MarketPenetrationEstimator()


def make_data(
    disease_id="T2DM",
    disease_name="Type 2 Diabetes",
    country="Indonesia",
    total_pop=220_000_000,
    incidence=450,
    prevalence=8_500,
    diagnosis=60.0,
    treatment=70.0,
    brand_share=15.0,
    brand_name="GlucoPrime",
):
    return DiseaseAreaData(
        disease_id=disease_id,
        disease_name=disease_name,
        country=country,
        total_population=total_pop,
        incidence_rate_per_100k=incidence,
        prevalence_rate_per_100k=prevalence,
        diagnosis_rate_pct=diagnosis,
        treatment_rate_pct=treatment,
        brand_market_share_pct=brand_share,
        brand_name=brand_name,
    )


class TestDiseaseAreaData:
    def test_valid_data(self):
        d = make_data()
        assert d.disease_id == "T2DM"

    def test_zero_population_raises(self):
        with pytest.raises(ValueError, match="total_population"):
            make_data(total_pop=0)

    def test_diagnosis_rate_out_of_range(self):
        with pytest.raises(ValueError, match="diagnosis_rate_pct"):
            make_data(diagnosis=110.0)

    def test_brand_share_out_of_range(self):
        with pytest.raises(ValueError, match="brand_market_share_pct"):
            make_data(brand_share=-5.0)

    def test_brand_plus_competitor_over_100(self):
        with pytest.raises(ValueError, match="brand \+ competitor"):
            DiseaseAreaData(
                "X", "X", "X", 1_000_000, 100, 1000,
                60.0, 70.0, 70.0,
                competitor_share_pct=50.0,
            )


class TestMarketPenetrationEstimator:
    def test_prevalent_patients_calculated(self, estimator):
        d = make_data(total_pop=1_000_000, prevalence=1_000)
        result = estimator.estimate(d)
        assert result.prevalent_patients == 10_000

    def test_funnel_decreases(self, estimator):
        d = make_data()
        result = estimator.estimate(d)
        assert result.prevalent_patients >= result.diagnosed_patients
        assert result.diagnosed_patients >= result.treated_patients
        assert result.treated_patients >= result.brand_patients

    def test_diagnosis_gap(self, estimator):
        d = make_data(total_pop=1_000_000, prevalence=1_000, diagnosis=60.0)
        result = estimator.estimate(d)
        assert result.undiagnosed_gap == result.prevalent_patients - result.diagnosed_patients

    def test_brand_penetration_of_treated(self, estimator):
        d = make_data(brand_share=25.0)
        result = estimator.estimate(d)
        assert result.brand_penetration_of_treated_pct == pytest.approx(25.0)

    def test_high_brand_share_low_brand_opp_score(self, estimator):
        d = make_data(brand_share=80.0)
        result = estimator.estimate(d)
        assert result.brand_opportunity_score == pytest.approx(20.0)

    def test_low_diagnosis_high_diag_opp(self, estimator):
        d = make_data(diagnosis=20.0)
        result = estimator.estimate(d)
        assert result.diagnosis_opportunity_score == pytest.approx(80.0)

    def test_primary_opportunity_set(self, estimator):
        d = make_data(diagnosis=30.0, treatment=80.0, brand_share=70.0)
        result = estimator.estimate(d)
        assert "diagnosis" in result.primary_opportunity.lower()

    def test_recommendations_present(self, estimator):
        d = make_data()
        result = estimator.estimate(d)
        assert len(result.recommendations) >= 1

    def test_to_dict_structure(self, estimator):
        d = make_data()
        result = estimator.estimate(d)
        dct = result.to_dict()
        assert "funnel" in dct
        assert "gaps" in dct
        assert "opportunity_scores" in dct

    def test_well_penetrated_recommendation(self, estimator):
        d = make_data(diagnosis=90.0, treatment=90.0, brand_share=75.0)
        result = estimator.estimate(d)
        assert any("retention" in r.lower() or "adherence" in r.lower() for r in result.recommendations)

    def test_incidence_mode(self):
        estimator_inc = MarketPenetrationEstimator(use_prevalence=False)
        d = make_data(total_pop=1_000_000, incidence=200, prevalence=2000)
        r_prev = MarketPenetrationEstimator(use_prevalence=True).estimate(d)
        r_inc = estimator_inc.estimate(d)
        # Prevalence > incidence rate, so prevalent_patients should differ
        assert r_prev.prevalent_patients > r_inc.prevalent_patients

    def test_compare_markets_sorted(self, estimator):
        d1 = make_data("D1", brand_share=10.0)   # high opportunity
        d2 = make_data("D2", brand_share=80.0)   # low opportunity
        results = estimator.compare_markets([d1, d2])
        assert results[0].brand_opportunity_score >= results[1].brand_opportunity_score

    def test_brand_of_prevalent_pct(self, estimator):
        d = make_data(total_pop=1_000_000, prevalence=1_000, diagnosis=100.0, treatment=100.0, brand_share=50.0)
        result = estimator.estimate(d)
        assert result.brand_penetration_of_prevalent_pct == pytest.approx(50.0, rel=1e-2)

    def test_untreated_diagnosed_gap(self, estimator):
        d = make_data(total_pop=100_000, prevalence=10_000, diagnosis=100.0, treatment=80.0)
        result = estimator.estimate(d)
        assert result.untreated_diagnosed_gap == result.diagnosed_patients - result.treated_patients

    def test_zero_treated_zero_brand_patients(self, estimator):
        d = make_data(treatment=0.0, brand_share=0.0)
        result = estimator.estimate(d)
        assert result.brand_patients == 0
        assert result.treated_patients == 0
