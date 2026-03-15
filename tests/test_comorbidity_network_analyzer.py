"""Unit tests for ComorbidityNetworkAnalyzer."""

import pytest
from src.comorbidity_network_analyzer import (
    ComorbidityMetric,
    ComorbidityNetworkAnalyzer,
    PatientRecord,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def patients():
    return [
        PatientRecord("P001", {"T2DM", "Hypertension", "CKD"}),
        PatientRecord("P002", {"T2DM", "Dyslipidaemia", "NAFLD"}),
        PatientRecord("P003", {"Hypertension", "HF", "CKD"}),
        PatientRecord("P004", {"T2DM", "Hypertension", "HF"}),
        PatientRecord("P005", {"T2DM", "CKD", "Anaemia"}),
        PatientRecord("P006", {"Hypertension", "CKD", "T2DM"}),
        PatientRecord("P007", {"HF", "CKD", "Anaemia"}),
        PatientRecord("P008", {"T2DM", "Hypertension", "Dyslipidaemia"}),
    ]


@pytest.fixture
def analyzer(patients):
    return ComorbidityNetworkAnalyzer(patients, min_co_occurrence=2, top_n_comorbidities=10)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_empty_patients_raises(self):
        with pytest.raises(ValueError, match="patient"):
            ComorbidityNetworkAnalyzer([])

    def test_zero_min_co_raises(self, patients):
        with pytest.raises(ValueError, match="min_co"):
            ComorbidityNetworkAnalyzer(patients, min_co_occurrence=0)

    def test_empty_diagnoses_raises(self):
        with pytest.raises(ValueError, match="diagnosis"):
            PatientRecord("X", set())

    def test_invalid_age_raises(self):
        with pytest.raises(ValueError, match="age"):
            PatientRecord("X", {"T2DM"}, age=200)


# ---------------------------------------------------------------------------
# Prevalence
# ---------------------------------------------------------------------------


class TestPrevalence:
    def test_prevalence_sums_to_positive(self, analyzer):
        prevs = analyzer._disease_prevalences()
        assert sum(prevs.values()) > 0

    def test_t2dm_highest_prevalence(self, analyzer):
        prevs = analyzer._disease_prevalences()
        # T2DM appears in P001, P002, P004, P005, P006, P008 = 6 / 8 = 0.75
        assert prevs.get("T2DM", 0) == pytest.approx(0.75, rel=1e-3)

    def test_prevalence_between_0_and_1(self, analyzer):
        prevs = analyzer._disease_prevalences()
        for v in prevs.values():
            assert 0 < v <= 1


# ---------------------------------------------------------------------------
# Edge metrics
# ---------------------------------------------------------------------------


class TestEdgeMetrics:
    def test_jaccard_symmetric(self, analyzer):
        # Jaccard(A, B) == Jaccard(B, A)
        j1 = analyzer._jaccard(30, 20, 10)
        j2 = analyzer._jaccard(20, 30, 10)
        assert j1 == j2

    def test_jaccard_perfect_overlap(self, analyzer):
        assert analyzer._jaccard(10, 10, 10) == pytest.approx(1.0)

    def test_jaccard_no_overlap(self, analyzer):
        assert analyzer._jaccard(10, 10, 0) == pytest.approx(0.0)

    def test_phi_positive_when_co_occurrence_higher_than_expected(self, analyzer):
        phi = analyzer._phi(8, 6, 7, 10)
        assert phi > 0

    def test_rr_greater_than_one_when_positively_associated(self, analyzer):
        rr = analyzer._relative_risk(8, 8, 8, 10)
        assert rr > 1


# ---------------------------------------------------------------------------
# Build edges
# ---------------------------------------------------------------------------


class TestBuildEdges:
    def test_edges_not_empty(self, analyzer):
        pd, ad = analyzer._disease_sets()
        prevs = analyzer._disease_prevalences()
        edges = analyzer._build_edges(pd, ad, prevs)
        assert len(edges) > 0

    def test_edges_sorted_by_co_occurrence_desc(self, analyzer):
        pd, ad = analyzer._disease_sets()
        prevs = analyzer._disease_prevalences()
        edges = analyzer._build_edges(pd, ad, prevs)
        co = [e.co_occurrence_count for e in edges]
        assert co == sorted(co, reverse=True)

    def test_no_duplicate_pairs(self, analyzer):
        pd, ad = analyzer._disease_sets()
        prevs = analyzer._disease_prevalences()
        edges = analyzer._build_edges(pd, ad, prevs)
        pairs = set()
        for e in edges:
            pair = frozenset({e.disease_a, e.disease_b})
            assert pair not in pairs, f"Duplicate pair: {pair}"
            pairs.add(pair)

    def test_min_co_occurrence_filter(self, patients):
        a = ComorbidityNetworkAnalyzer(patients, min_co_occurrence=5)
        pd, ad = a._disease_sets()
        prevs = a._disease_prevalences()
        edges = a._build_edges(pd, ad, prevs)
        for e in edges:
            assert e.co_occurrence_count >= 5


# ---------------------------------------------------------------------------
# Multimorbidity stats
# ---------------------------------------------------------------------------


class TestMultimorbidity:
    def test_all_patients_have_2_plus(self, analyzer):
        # All fixtures have 3 diagnoses
        stats = analyzer._multimorbidity_stats()
        assert stats["pct_with_2_or_more"] == pytest.approx(100.0)

    def test_mean_conditions_positive(self, analyzer):
        stats = analyzer._multimorbidity_stats()
        assert stats["mean_conditions"] > 0


# ---------------------------------------------------------------------------
# Hub diseases
# ---------------------------------------------------------------------------


class TestHubDiseases:
    def test_hub_diseases_not_empty(self, analyzer):
        pd, ad = analyzer._disease_sets()
        prevs = analyzer._disease_prevalences()
        edges = analyzer._build_edges(pd, ad, prevs)
        hubs = analyzer._hub_diseases(edges)
        assert len(hubs) > 0

    def test_t2dm_is_hub(self, analyzer):
        pd, ad = analyzer._disease_sets()
        prevs = analyzer._disease_prevalences()
        edges = analyzer._build_edges(pd, ad, prevs)
        hubs = analyzer._hub_diseases(edges)
        assert "T2DM" in hubs[:3]


# ---------------------------------------------------------------------------
# Full analyse()
# ---------------------------------------------------------------------------


class TestAnalyse:
    def test_returns_report(self, analyzer):
        report = analyzer.analyse()
        assert report is not None

    def test_n_patients_correct(self, analyzer, patients):
        report = analyzer.analyse()
        assert report.n_patients == len(patients)

    def test_top_comorbidities_not_empty(self, analyzer):
        report = analyzer.analyse()
        assert len(report.top_comorbidities) > 0

    def test_hub_diseases_populated(self, analyzer):
        report = analyzer.analyse()
        assert len(report.hub_diseases) > 0

    def test_recommendations_populated(self, analyzer):
        report = analyzer.analyse()
        assert len(report.recommendations) > 0

    def test_multimorbidity_keys_present(self, analyzer):
        report = analyzer.analyse()
        for key in ("mean_conditions", "pct_with_2_or_more", "pct_with_3_or_more"):
            assert key in report.multimorbidity_stats

    def test_disease_prevalences_in_report(self, analyzer):
        report = analyzer.analyse()
        assert "T2DM" in report.disease_prevalences
        assert report.disease_prevalences["T2DM"] > 0

    def test_clusters_have_multiple_diseases(self, analyzer):
        report = analyzer.analyse()
        for cluster in report.disease_clusters:
            assert len(cluster.diseases) >= 2


# ---------------------------------------------------------------------------
# top_comorbidities_for()
# ---------------------------------------------------------------------------


class TestTopComorbidities:
    def test_returns_for_known_disease(self, analyzer):
        results = analyzer.top_comorbidities_for("T2DM")
        assert len(results) > 0

    def test_all_edges_involve_queried_disease(self, analyzer):
        results = analyzer.top_comorbidities_for("Hypertension")
        for e in results:
            assert "Hypertension" in (e.disease_a, e.disease_b)

    def test_unknown_disease_raises(self, analyzer):
        with pytest.raises(ValueError, match="not found"):
            analyzer.top_comorbidities_for("Unknown Disease XYZ")

    def test_jaccard_metric_sorts_by_jaccard(self, analyzer):
        results = analyzer.top_comorbidities_for("T2DM", metric=ComorbidityMetric.JACCARD)
        jaccards = [e.jaccard for e in results]
        assert jaccards == sorted(jaccards, reverse=True)
