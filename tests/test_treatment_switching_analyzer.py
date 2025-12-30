"""
Unit tests for TreatmentSwitchingAnalyzer.
"""

import pytest
from src.treatment_switching_analyzer import (
    TreatmentSwitchingAnalyzer,
    SwitchEvent,
    SwitchFlowSummary,
)


@pytest.fixture
def sample_events():
    """Mixed switching events for 'BrandA' analysis."""
    return [
        # Departures from BrandA
        SwitchEvent("P001", "2025-01-10", "BrandA", "generic_a", 1, "cost", "commercial"),
        SwitchEvent("P002", "2025-01-20", "BrandA", "Competitor", 1, "formulary", "medicare"),
        SwitchEvent("P003", "2025-02-05", "BrandA", "Competitor", 2, "efficacy", "commercial"),
        SwitchEvent("P004", "2025-02-15", "BrandA", "OtherBrand", 1, "physician", "medicaid"),
        SwitchEvent("P005", "2025-03-01", "BrandA", "generic_a", 1, "cost", "cash"),
        # Arrivals to BrandA
        SwitchEvent("P006", "2025-01-12", "Competitor", "BrandA", 1, "efficacy", "commercial"),
        SwitchEvent("P007", "2025-02-08", "OtherBrand", "BrandA", 2, "physician", "commercial"),
        # Unrelated events
        SwitchEvent("P008", "2025-01-25", "Competitor", "OtherBrand", 1, "cost", "commercial"),
    ]


@pytest.fixture
def analyzer(sample_events):
    return TreatmentSwitchingAnalyzer(sample_events)


# ---------------------------------------------------------------------------
# brand_switch_summary
# ---------------------------------------------------------------------------

class TestBrandSwitchSummary:
    def test_returns_switch_flow_summary(self, analyzer):
        result = analyzer.brand_switch_summary("BrandA")
        assert isinstance(result, SwitchFlowSummary)

    def test_correct_departures_count(self, analyzer):
        result = analyzer.brand_switch_summary("BrandA")
        assert result.switches_from_target == 5

    def test_correct_arrivals_count(self, analyzer):
        result = analyzer.brand_switch_summary("BrandA")
        assert result.switches_to_target == 2

    def test_net_flow_negative_when_more_departures(self, analyzer):
        result = analyzer.brand_switch_summary("BrandA")
        assert result.net_patient_flow < 0

    def test_brand_to_generic_rate_correct(self, analyzer):
        # 2 out of 5 departures → generic_a (has "generic" in name)
        result = analyzer.brand_switch_summary("BrandA")
        assert result.brand_to_generic_rate_pct == pytest.approx(40.0)

    def test_competitive_loss_with_named_competitor(self, analyzer):
        result = analyzer.brand_switch_summary("BrandA", competitors=["Competitor"])
        # 2 events went to Competitor
        assert result.competitive_loss_rate_pct == pytest.approx(40.0)

    def test_top_destinations_present(self, analyzer):
        result = analyzer.brand_switch_summary("BrandA")
        assert len(result.top_destinations) > 0

    def test_top_origins_present(self, analyzer):
        result = analyzer.brand_switch_summary("BrandA")
        assert len(result.top_origins) > 0

    def test_case_insensitive_target(self, analyzer):
        r1 = analyzer.brand_switch_summary("BrandA")
        r2 = analyzer.brand_switch_summary("branda")
        assert r1.switches_from_target == r2.switches_from_target

    def test_therapy_line_filter(self, analyzer):
        result = analyzer.brand_switch_summary("BrandA", therapy_line=2)
        # Only P003 departure and P007 arrival are line 2
        assert result.switches_from_target == 1
        assert result.switches_to_target == 1

    def test_payer_type_filter(self, analyzer):
        result = analyzer.brand_switch_summary("BrandA", payer_type="commercial")
        # P001 is commercial departure; P002 is medicare; P003 is commercial departure
        assert result.switches_from_target == 2

    def test_empty_events_returns_zero_counts(self):
        analyzer_empty = TreatmentSwitchingAnalyzer([])
        result = analyzer_empty.brand_switch_summary("BrandA")
        assert result.total_switches == 0
        assert result.switches_from_target == 0


# ---------------------------------------------------------------------------
# therapy_line_progression
# ---------------------------------------------------------------------------

class TestTherapyLineProgression:
    def test_returns_dict_with_line_counts(self, analyzer):
        result = analyzer.therapy_line_progression()
        assert isinstance(result, dict)
        assert 1 in result

    def test_line1_has_most_events(self, analyzer):
        result = analyzer.therapy_line_progression()
        assert result.get(1, 0) > result.get(2, 0)

    def test_patient_filter_returns_single_patient_events(self, analyzer):
        result = analyzer.therapy_line_progression(patient_id="P001")
        total = sum(result.values())
        assert total == 1

    def test_unknown_patient_returns_empty(self, analyzer):
        result = analyzer.therapy_line_progression(patient_id="UNKNOWN_9999")
        assert sum(result.values()) == 0


# ---------------------------------------------------------------------------
# formulary_signal_detector
# ---------------------------------------------------------------------------

class TestFormularySignalDetector:
    def test_returns_signal_dict(self, analyzer):
        result = analyzer.formulary_signal_detector("BrandA")
        assert "formulary_switch_count" in result
        assert "signal_strength" in result

    def test_detects_formulary_events(self, analyzer):
        result = analyzer.formulary_signal_detector("BrandA")
        # P002 has reason_code="formulary"
        assert result["formulary_switch_count"] >= 1

    def test_insufficient_data_when_too_few_events(self):
        # Only 3 events (below min_events=5)
        events = [
            SwitchEvent("P1", "2025-01-01", "SmallBrand", "Other", 1, "formulary"),
            SwitchEvent("P2", "2025-01-02", "SmallBrand", "Other", 1, "cost"),
        ]
        analyzer_small = TreatmentSwitchingAnalyzer(events)
        result = analyzer_small.formulary_signal_detector("SmallBrand", min_events=5)
        assert result["signal_strength"] == "insufficient_data"


# ---------------------------------------------------------------------------
# reason_code_distribution
# ---------------------------------------------------------------------------

class TestReasonCodeDistribution:
    def test_counts_all_reason_codes(self, analyzer):
        result = analyzer.reason_code_distribution()
        assert sum(result.values()) == len(analyzer._events)

    def test_filter_by_from_drug(self, analyzer):
        result = analyzer.reason_code_distribution(from_drug="BrandA")
        assert sum(result.values()) == 5  # 5 departures from BrandA

    def test_none_reason_code_mapped_to_unknown(self):
        events = [SwitchEvent("P1", "2025-01-01", "A", "B", 1, None)]
        a = TreatmentSwitchingAnalyzer(events)
        result = a.reason_code_distribution()
        assert "unknown" in result
