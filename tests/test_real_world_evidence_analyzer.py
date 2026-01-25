"""Unit tests for RealWorldEvidenceAnalyzer."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from real_world_evidence_analyzer import (
    RealWorldEvidenceAnalyzer,
    RWEStudy,
    StudyDesign,
    ConfidenceLevel,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_study(
    study_id="RWE_001",
    n_brand=5_000,
    n_comparator=4_800,
    brand_rate=62.0,
    comparator_rate=48.0,
    p_value=0.003,
    grace_score=7.5,
    follow_up=18.0,
    has_pm=True,
    unmeasured=None,
    design=StudyDesign.COHORT,
    country="ID",
) -> RWEStudy:
    return RWEStudy(
        study_id=study_id,
        disease_area="Type 2 Diabetes",
        brand="BrandA",
        comparator="Metformin",
        study_design=design,
        n_brand=n_brand,
        n_comparator=n_comparator,
        follow_up_months=follow_up,
        primary_endpoint="HbA1c <7%",
        brand_event_rate_pct=brand_rate,
        comparator_event_rate_pct=comparator_rate,
        p_value=p_value,
        grace_score=grace_score,
        data_source="IQVIA Claims",
        publication_year=2024,
        country=country,
        has_propensity_matching=has_pm,
        unmeasured_confounders=unmeasured or [],
    )


# ---------------------------------------------------------------------------
# RWEStudy property tests
# ---------------------------------------------------------------------------

class TestRWEStudy:
    def test_relative_risk(self):
        s = make_study(brand_rate=60, comparator_rate=40)
        assert abs(s.relative_risk - 1.5) < 0.001

    def test_rr_zero_comparator_rate(self):
        s = make_study(comparator_rate=0)
        assert s.relative_risk is None

    def test_arr(self):
        s = make_study(brand_rate=62, comparator_rate=48)
        assert abs(s.absolute_risk_reduction_pct - 14.0) < 0.01

    def test_nnt(self):
        # ARR = 14%, NNT = 100/14 ≈ 7.14
        s = make_study(brand_rate=62, comparator_rate=48)
        assert abs(s.nnt - (100 / 14)) < 0.1

    def test_nnt_none_when_no_benefit(self):
        s = make_study(brand_rate=50, comparator_rate=30)
        # comparator_rate > brand_rate → ARR negative → no benefit
        assert s.nnt is None

    def test_significance(self):
        s = make_study(p_value=0.03)
        assert s.is_statistically_significant
        s2 = make_study(p_value=0.10)
        assert not s2.is_statistically_significant

    def test_grace_confidence_high(self):
        s = make_study(grace_score=9.0)
        assert s.confidence_level == ConfidenceLevel.HIGH

    def test_grace_confidence_moderate(self):
        s = make_study(grace_score=6.5)
        assert s.confidence_level == ConfidenceLevel.MODERATE

    def test_grace_confidence_low(self):
        s = make_study(grace_score=4.0)
        assert s.confidence_level == ConfidenceLevel.LOW

    def test_invalid_sample_size_raises(self):
        with pytest.raises(ValueError):
            make_study(n_brand=0)

    def test_invalid_p_value_raises(self):
        with pytest.raises(ValueError):
            make_study(p_value=1.5)


# ---------------------------------------------------------------------------
# RealWorldEvidenceAnalyzer tests
# ---------------------------------------------------------------------------

class TestAnalyzer:
    def setup_method(self):
        self.analyzer = RealWorldEvidenceAnalyzer()

    def test_analyze_study_returns_dict(self):
        s = make_study()
        result = self.analyzer.analyze_study(s)
        assert "relative_risk" in result
        assert "nnt" in result
        assert result["statistically_significant"] is True

    def test_analyze_study_invalid_type(self):
        with pytest.raises(TypeError):
            self.analyzer.analyze_study({"study_id": "bad"})

    def test_synthesize_single_study(self):
        s = make_study()
        insight = self.analyzer.synthesize([s])
        assert insight.n_studies == 1
        assert insight.weighted_rr is not None

    def test_synthesize_multiple_studies(self):
        studies = [make_study(f"S{i}", n_brand=1000*i+500, grace_score=7.0) for i in range(1, 4)]
        insight = self.analyzer.synthesize(studies)
        assert insight.n_studies == 3
        assert insight.pooled_n > 0

    def test_synthesize_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            self.analyzer.synthesize([])

    def test_filter_by_confidence(self):
        studies = [
            make_study("S1", grace_score=9.0),   # HIGH
            make_study("S2", grace_score=6.0),   # MODERATE
            make_study("S3", grace_score=3.5),   # LOW
        ]
        filtered = self.analyzer.filter_by_confidence(studies, ConfidenceLevel.MODERATE)
        assert len(filtered) == 2

    def test_evidence_gap_report_keys(self):
        s = make_study()
        report = self.analyzer.evidence_gap_report([s], "Type 2 Diabetes")
        assert "evidence_gaps" in report
        assert "countries_covered" in report
        assert "priority_next_study" in report

    def test_evidence_gap_flags_no_long_term(self):
        s = make_study(follow_up=12)  # <24 months
        report = self.analyzer.evidence_gap_report([s], "T2DM")
        assert any("long-term" in g.lower() for g in report["evidence_gaps"])
