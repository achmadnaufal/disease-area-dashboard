"""
Unit tests for the patient journey funnel analysis module.
"""

import pytest
from src.patient_journey_funnel import (
    FunnelStage,
    PatientJourneyFunnel,
    PatientJourneyAnalyzer,
    BENCHMARK_CONVERSION_RATES,
)


# ---------------------------------------------------------------------------
# FunnelStage tests
# ---------------------------------------------------------------------------


class TestFunnelStage:
    def test_valid_creation(self):
        s = FunnelStage("diagnosed", 100000, 0.72, "Not eligible")
        assert s.patient_count == 100000

    def test_drop_count(self):
        s = FunnelStage("stage", 1000, 0.7)
        assert s.drop_count == 300

    def test_pass_through_count(self):
        s = FunnelStage("stage", 1000, 0.7)
        assert s.pass_through_count == 700

    def test_negative_patients_raises(self):
        with pytest.raises(ValueError, match="patient_count cannot be negative"):
            FunnelStage("stage", -100, 0.5)

    def test_conversion_above_one_raises(self):
        with pytest.raises(ValueError, match="conversion_rate_to_next"):
            FunnelStage("stage", 1000, 1.5)

    def test_conversion_below_zero_raises(self):
        with pytest.raises(ValueError):
            FunnelStage("stage", 1000, -0.1)


# ---------------------------------------------------------------------------
# PatientJourneyAnalyzer tests
# ---------------------------------------------------------------------------


@pytest.fixture
def analyzer():
    return PatientJourneyAnalyzer(
        disease_area="Type 2 Diabetes",
        total_diagnosed_patients=500_000,
    )


@pytest.fixture
def funnel(analyzer):
    return analyzer.build_funnel(
        brand_name="BrandX",
        brand_initiation_share=0.28,
        persistence_6m=0.74,
        persistence_12m=0.55,
    )


class TestPatientJourneyAnalyzer:
    def test_creation_valid(self, analyzer):
        assert analyzer.disease_area == "Type 2 Diabetes"
        assert analyzer.total_diagnosed_patients == 500_000

    def test_empty_disease_area_raises(self):
        with pytest.raises(ValueError, match="disease_area cannot be empty"):
            PatientJourneyAnalyzer("  ", 100000)

    def test_zero_patients_raises(self):
        with pytest.raises(ValueError, match="total_diagnosed_patients"):
            PatientJourneyAnalyzer("Diabetes", 0)

    def test_build_funnel_returns_funnel(self, analyzer, funnel):
        assert isinstance(funnel, PatientJourneyFunnel)

    def test_funnel_has_6_stages(self, funnel):
        assert len(funnel.stages) == 6

    def test_first_stage_equals_total_diagnosed(self, analyzer, funnel):
        assert funnel.stages[0].patient_count == analyzer.total_diagnosed_patients

    def test_stages_decreasing(self, funnel):
        counts = [s.patient_count for s in funnel.stages]
        assert all(counts[i] >= counts[i + 1] for i in range(len(counts) - 1))

    def test_empty_brand_name_raises(self, analyzer):
        with pytest.raises(ValueError, match="brand_name cannot be empty"):
            analyzer.build_funnel(" ")

    def test_invalid_rate_above_one_raises(self, analyzer):
        with pytest.raises(ValueError, match="treatment_eligible_rate"):
            analyzer.build_funnel("BrandX", treatment_eligible_rate=1.5)

    def test_invalid_rate_below_zero_raises(self, analyzer):
        with pytest.raises(ValueError, match="persistence_6m"):
            analyzer.build_funnel("BrandX", persistence_6m=-0.1)

    def test_overall_conversion_rate_between_0_and_1(self, funnel):
        assert 0.0 <= funnel.overall_conversion_rate() <= 1.0

    def test_biggest_drop_stage_is_funnel_stage(self, funnel):
        stage = funnel.biggest_drop_stage()
        assert stage is not None
        assert isinstance(stage, FunnelStage)

    def test_funnel_summary_length(self, funnel):
        summary = funnel.funnel_summary()
        assert len(summary) == 6

    def test_funnel_summary_keys(self, funnel):
        summary = funnel.funnel_summary()
        expected = {"stage", "patients", "conversion_to_next_pct",
                    "drop_count", "cumulative_conversion_pct", "drop_reason"}
        assert expected.issubset(summary[0].keys())

    def test_first_stage_cumulative_is_100(self, funnel):
        summary = funnel.funnel_summary()
        assert summary[0]["cumulative_conversion_pct"] == pytest.approx(100.0)

    def test_opportunity_score_keys(self, analyzer, funnel):
        score = analyzer.opportunity_score(funnel)
        expected = {
            "biggest_gap_stage", "untreated_patients", "competitor_share_patients",
            "persistence_gap_6m", "persistence_gap_12m", "total_opportunity_patients",
            "brand_penetration_pct",
        }
        assert expected.issubset(score.keys())

    def test_opportunity_total_is_sum_of_gaps(self, analyzer, funnel):
        score = analyzer.opportunity_score(funnel)
        total = (
            score["untreated_patients"]
            + score["competitor_share_patients"]
            + score["persistence_gap_6m"]
            + score["persistence_gap_12m"]
        )
        assert total == score["total_opportunity_patients"]

    def test_brand_penetration_pct_range(self, analyzer, funnel):
        score = analyzer.opportunity_score(funnel)
        assert 0.0 <= score["brand_penetration_pct"] <= 100.0

    def test_compare_brands_sorted_by_maintained(self, analyzer):
        funnel_x = analyzer.build_funnel("BrandX", brand_initiation_share=0.30, persistence_12m=0.60)
        funnel_y = analyzer.build_funnel("BrandY", brand_initiation_share=0.20, persistence_12m=0.50)
        comparison = analyzer.compare_brands([funnel_y, funnel_x])
        # BrandX should come first (more maintained_12m)
        assert comparison[0]["brand"] == "BrandX"

    def test_compare_brands_empty_raises(self, analyzer):
        with pytest.raises(ValueError, match="funnels list cannot be empty"):
            analyzer.compare_brands([])

    def test_compare_brands_keys(self, analyzer, funnel):
        comparison = analyzer.compare_brands([funnel])
        expected = {"brand", "on_brand_patients", "maintained_12m",
                    "overall_conversion_pct", "persistence_12m_pct"}
        assert expected.issubset(comparison[0].keys())

    def test_empty_funnel_overall_conversion(self, analyzer):
        f = PatientJourneyFunnel("DA", "BrandZ", [], 100000)
        assert f.overall_conversion_rate() == 0.0

    def test_empty_funnel_biggest_drop_none(self, analyzer):
        f = PatientJourneyFunnel("DA", "BrandZ", [], 100000)
        assert f.biggest_drop_stage() is None
